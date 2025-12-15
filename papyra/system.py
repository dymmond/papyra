from __future__ import annotations
"""
ActorSystem: lifecycle, spawning, and shutdown.

This is the runtime entry-point. It owns:
- the task group where actors run,
- references to live actors,
- shutdown semantics.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar, Any

import anyio
import anyio.abc

from ._envelope import Reply
from .actor import Actor
from .exceptions import ActorStopped
from .mailbox import Mailbox
from .supervision import Strategy, SupervisionPolicy

A = TypeVar("A", bound=Actor)
ActorFactory = Callable[[], Actor]
AnyActorRef = Any


@dataclass(slots=True)
class _ActorRuntime:
    """
    Internal runtime record for a single actor.

    Notes
    -----
    - The mailbox remains stable across restarts.
    - `actor_factory` is kept so we can recreate the actor on RESTART.
    - `policy` is the failure handling policy applied by the parent (or system).
    """

    actor_factory: ActorFactory
    actor: Actor
    mailbox: Mailbox
    policy: SupervisionPolicy
    parent: Optional["_ActorRuntime"] = None
    children: list["_ActorRuntime"] = field(default_factory=list)

    alive: bool = True
    restart_timestamps: list[float] = field(default_factory=list)


class ActorSystem:
    """
    Root runtime container for actors.

    Supervision model (Step 3)
    --------------------------
    Each actor runtime has a `policy` describing what happens when it fails.

    - STOP: actor stops
    - RESTART: actor is recreated using its original factory
    - ESCALATE: failure is forwarded to the parent; if no parent, STOP is used

    Important semantic choices
    --------------------------
    - When an actor fails while processing an `ask`, the caller receives the error.
      The supervisor decision applies AFTER replying.
    - On RESTART, the mailbox is preserved and processing continues.
    - Lifecycle hook ordering on RESTART:
        old_actor.on_stop() -> new_actor.on_start()
    """

    def __init__(self) -> None:
        self._tg: anyio.abc.TaskGroup | None = None
        self._closed = False
        self._actors: list[_ActorRuntime] = []

    async def start(self) -> None:
        """
        Start the actor system.

        Must be called before `spawn(...)`.
        """
        if self._closed:
            raise ActorStopped("ActorSystem is closed.")
        if self._tg is not None:
            return
        self._tg = await anyio.create_task_group().__aenter__()

    def spawn(
        self,
        actor_factory: Callable[[], A] | type[A],
        *,
        mailbox_capacity: Optional[int] = 1024,
        policy: Optional[SupervisionPolicy] = None,
        parent: Optional["AnyActorRef"] = None,
    ):
        """
        Spawn a new actor and return an ActorRef.

        Parameters
        ----------
        actor_factory:
            Either an Actor subclass (type) or a zero-arg callable returning an Actor.
        mailbox_capacity:
            Size of mailbox buffer. None means unbounded.
        policy:
            Supervision policy applied to this actor when it fails.
            If not provided, defaults to STOP.
        parent:
            Optional parent ActorRef. If provided, failures may ESCALATE to this parent,
            and the parent keeps the child in its children list.

        Returns
        -------
        ActorRef
            A reference to the new actor.

        Raises
        ------
        ActorStopped
            If the system is not started or already closed.
        """
        from .ref import ActorRef  # keep coupling low

        if self._closed or self._tg is None:
            raise ActorStopped("ActorSystem is not running. Did you call await system.start()?")

        # Normalize into a zero-arg factory
        if isinstance(actor_factory, type):
            factory: ActorFactory = actor_factory  # type: ignore[assignment]
        else:
            factory = actor_factory

        actor = factory()

        rt = _ActorRuntime(
            actor_factory=factory,
            actor=actor,
            mailbox=Mailbox(capacity=mailbox_capacity),
            policy=policy or SupervisionPolicy(strategy=Strategy.STOP),
            parent=self._resolve_parent_runtime(parent),
        )

        if rt.parent is not None:
            rt.parent.children.append(rt)

        self._actors.append(rt)
        self._tg.start_soon(self._run_actor, rt)

        return ActorRef(
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive,
        )

    def _resolve_parent_runtime(self, parent_ref: Optional["AnyActorRef"]) -> Optional[_ActorRuntime]:
        """
        Resolve a parent ActorRef to its runtime.

        We locate the runtime by identity of the mailbox put method.
        """
        if parent_ref is None:
            return None

        mailbox_put = getattr(parent_ref, "_mailbox_put", None)
        if mailbox_put is None:
            return None

        for rt in self._actors:
            if rt.mailbox.put is mailbox_put:
                return rt
        return None

    async def _run_actor(self, rt: _ActorRuntime) -> None:
        """
        Actor event loop with lifecycle hooks and supervision.

        The loop continues while:
        - the system is running
        - the actor is alive

        Failures are handled by `_handle_failure(...)`.
        """
        try:
            # --- on_start ---
            if not await self._safe_on_start(rt):
                rt.alive = False
                return

            while not self._closed and rt.alive:
                try:
                    env = await rt.mailbox.get()
                except anyio.EndOfStream:
                    break

                try:
                    result = await rt.actor.receive(env.message)
                    if env.reply is not None:
                        await env.reply.send(Reply(value=result, error=None))
                except BaseException as e:
                    # Reply first (ask semantics)
                    if env.reply is not None:
                        try:
                            await env.reply.send(Reply(value=None, error=e))
                        except Exception:
                            pass

                    # Supervision decision
                    await self._handle_failure(rt, e)

        finally:
            # Always stop lifecycle for the currently installed actor instance.
            await self._safe_on_stop(rt)
            rt.alive = False
            await rt.mailbox.aclose()

    async def _safe_on_start(self, rt: _ActorRuntime) -> bool:
        """Run on_start safely. Returns False if actor should not proceed."""
        try:
            await rt.actor.on_start()
            return True
        except Exception:
            # If on_start fails, treat as a failure and apply policy.
            await self._handle_failure(rt, RuntimeError("actor.on_start() failed"))
            return rt.alive

    async def _safe_on_stop(self, rt: _ActorRuntime) -> None:
        """Run on_stop safely; never propagate."""
        try:
            await rt.actor.on_stop()
        except Exception:
            return

    async def _handle_failure(self, rt: _ActorRuntime, exc: BaseException) -> None:
        """
        Apply supervision policy for a failed actor runtime.

        Rules
        -----
        - STOP: stop actor
        - RESTART: restart actor (with restart limits)
        - ESCALATE: forward to parent; if no parent, STOP
        """
        strategy = rt.policy.strategy

        if strategy is Strategy.ESCALATE:
            if rt.parent is None:
                rt.alive = False
                return
            # Escalate to parent by treating parent as "failed".
            await self._handle_failure(rt.parent, exc)
            # Child stops unless parent restarts it explicitly (not implemented yet).
            rt.alive = False
            return

        if strategy is Strategy.STOP:
            rt.alive = False
            return

        if strategy is Strategy.RESTART:
            can_restart = await self._check_restart_limits(rt)
            if not can_restart:
                rt.alive = False
                return

            # Stop the current actor instance (best-effort)
            await self._safe_on_stop(rt)

            # Replace actor instance and start it
            rt.actor = rt.actor_factory()
            started = await self._safe_on_start(rt)
            if not started:
                rt.alive = False
            return

        # Fallback: safest default is STOP
        rt.alive = False

    async def _check_restart_limits(self, rt: _ActorRuntime) -> bool:
        """
        Enforce restart rate limits.

        Returns
        -------
        bool
            True if restart is allowed, False if restart budget is exhausted.
        """
        now = anyio.current_time()
        window = rt.policy.within_seconds
        rt.restart_timestamps = [t for t in rt.restart_timestamps if (now - t) <= window]

        if len(rt.restart_timestamps) >= rt.policy.max_restarts:
            return False

        rt.restart_timestamps.append(now)
        return True

    async def aclose(self) -> None:
        """
        Gracefully shutdown the actor system.

        This:
        - closes all mailboxes (no new messages),
        - cancels remaining actor tasks via task group exit.
        """
        if self._closed:
            return
        self._closed = True

        for rt in self._actors:
            try:
                await rt.mailbox.aclose()
            except Exception:
                pass

        if self._tg is not None:
            tg = self._tg
            self._tg = None
            await tg.__aexit__(None, None, None)

    async def __aenter__(self) -> "ActorSystem":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

