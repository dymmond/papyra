from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

import anyio
import anyio.abc

from ._envelope import STOP, ActorTerminated, DeadLetter, Envelope, Reply
from .actor import Actor
from .context import ActorContext
from .exceptions import ActorStopped
from .mailbox import Mailbox
from .supervision import Strategy, SupervisionPolicy
from .supervisor import SupervisorDecision

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

    rid: int
    actor_factory: ActorFactory
    actor: Actor
    mailbox: Mailbox
    policy: SupervisionPolicy

    parent: Optional["_ActorRuntime"] = None
    children: list["_ActorRuntime"] = field(default_factory=list)
    watchers: set[int] = field(default_factory=set)

    alive: bool = True
    stopping: bool = False
    restart_timestamps: list[float] = field(default_factory=list)


class DeadLetterMailbox:
    """
    A simple in-memory dead-letter mailbox.

    This is intentionally tiny for Papyra's current phase:
    - append-only list storage
    - optional user hook on each dead letter
    """

    def __init__(self, *, on_dead_letter: Callable[[DeadLetter], None] | None = None) -> None:
        self._messages: list[DeadLetter] = []
        self._on_dead_letter = on_dead_letter

    @property
    def messages(self) -> list[DeadLetter]:
        return self._messages

    def push(self, dl: DeadLetter) -> None:
        self._messages.append(dl)
        if self._on_dead_letter is not None:
            self._on_dead_letter(dl)


class ActorSystem:
    """Root runtime container for actors."""

    def __init__(self, *, on_dead_letter: Callable[[DeadLetter], None] | None = None) -> None:
        self._tg: anyio.abc.TaskGroup | None = None
        self._closed = False

        self._actors: list[_ActorRuntime] = []
        self._by_id: dict[int, _ActorRuntime] = {}
        self._next_id: int = 1
        self.dead_letters = DeadLetterMailbox(on_dead_letter=on_dead_letter)

    async def start(self) -> None:
        """Start the actor system. Must be called before `spawn(...)`."""
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
        parent: Optional[Any] = None,
    ):
        """
        Spawn a new actor and return an ActorRef.
        """
        from .ref import ActorRef  # local import to avoid cycles

        if self._closed or self._tg is None:
            raise ActorStopped("ActorSystem is not running. Did you call await system.start()?")

        # Normalize into a zero-arg factory
        if isinstance(actor_factory, type):
            factory: ActorFactory = actor_factory  # type: ignore[assignment]
        else:
            factory = actor_factory

        rid = self._next_id
        self._next_id += 1

        mailbox = Mailbox(capacity=mailbox_capacity)
        actor = factory()

        rt = _ActorRuntime(
            rid=rid,
            actor_factory=factory,
            actor=actor,
            mailbox=mailbox,
            policy=policy or SupervisionPolicy(strategy=Strategy.STOP),
            parent=self._resolve_parent_runtime(parent),
        )

        if rt.parent is not None:
            rt.parent.children.append(rt)

        self._actors.append(rt)
        self._by_id[rid] = rt

        ref = ActorRef(
            _rid=rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive and (not rt.stopping),
            _dead_letter=self.dead_letters.push,
        )

        self._inject_context(rt, self_ref=ref)
        self._tg.start_soon(self._run_actor, rt)
        return ref

    async def stop(self, ref: Any) -> None:
        """
        Request an actor to stop gracefully.

        This is a *cascading stop*: children are stopped before the parent.

        Parameters
        ----------
        ref:
            ActorRef pointing to a running actor.

        Notes
        -----
        - Idempotent.
        - Stop is processed in-order with existing messages for each actor.
        """
        if self._closed:
            return

        rid = getattr(ref, "_rid", None)
        if not isinstance(rid, int):
            return

        rt = self._by_id.get(rid)
        if rt is None:
            return

        await self._stop_runtime(rt)

    async def _stop_runtime(self, rt: _ActorRuntime, *, _seen: set[int] | None = None) -> None:
        """
        Stop an actor runtime and all of its descendants.

        Notes
        -----
        - Best-effort: if a mailbox is already closed, we still mark the runtime stopped.
        - Stop order is children-first to mimic supervision-tree shutdown semantics.
        - `_seen` prevents cycles (should never happen, but makes it robust).
        """
        from .ref import ActorRef

        if _seen is None:
            _seen = set()

        if rt.rid in _seen:
            return
        _seen.add(rt.rid)

        # Stop children first
        for child in list(rt.children):
            await self._stop_runtime(child, _seen=_seen)

        # Then stop this actor
        if not rt.alive or rt.stopping:
            return

        # Mark stopping first
        rt.stopping = True

        self_ref = ActorRef(
            _rid=rt.rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: False,
            _dead_letter=self.dead_letters.push,
        )

        for watcher_rid in list(rt.watchers):
            watcher_rt = self._by_id.get(watcher_rid)
            if watcher_rt is None or not watcher_rt.alive:
                continue
            try:
                await watcher_rt.mailbox.put(
                    Envelope(message=ActorTerminated(self_ref), reply=None)
                )
            except Exception:
                pass

        try:
            await rt.mailbox.put(Envelope(message=STOP, reply=None))
        except Exception:
            rt.alive = False

    def _resolve_parent_runtime(self, parent_ref: Optional[Any]) -> Optional[_ActorRuntime]:
        """Resolve a parent ActorRef to its runtime using the stable runtime id."""
        if parent_ref is None:
            return None
        rid = getattr(parent_ref, "_rid", None)
        if not isinstance(rid, int):
            return None
        return self._by_id.get(rid)

    def _inject_context(self, rt: _ActorRuntime, *, self_ref: Any) -> None:
        """
        Inject ActorContext into the currently installed actor instance.

        This runs:
        - on initial spawn
        - on restart (after actor instance replacement)
        """
        parent_ref = None
        if rt.parent is not None:
            from .ref import ActorRef

            parent_ref = ActorRef(
                _rid=rt.parent.rid,
                _mailbox_put=rt.parent.mailbox.put,
                _is_alive=lambda: (not self._closed)
                and rt.parent.alive
                and (not rt.parent.stopping),
                _dead_letter=self.dead_letters.push,
            )

        rt.actor._context = ActorContext(system=self, self_ref=self_ref, parent=parent_ref)

    async def _run_actor(self, rt: _ActorRuntime) -> None:
        """Actor event loop with lifecycle hooks, supervision, and stop control."""
        from .ref import ActorRef

        try:
            if not await self._safe_on_start(rt):
                rt.alive = False
                return

            while not self._closed and rt.alive:
                try:
                    env = await rt.mailbox.get()
                except anyio.EndOfStream:
                    break

                if env.message is STOP:
                    break

                try:
                    result = await rt.actor.receive(env.message)
                    if env.reply is not None:
                        await env.reply.send(Reply(value=result, error=None))
                except BaseException as e:
                    # Apply supervision/stop/restart first so the caller observes
                    # the post-failure liveness state deterministically.
                    await self._handle_failure(rt, e)

                    if env.reply is not None:
                        try:
                            await env.reply.send(Reply(value=None, error=e))
                        except Exception:
                            pass

                # If a stop was requested during message handling (e.g. stop_self),
                # terminate the loop; watcher notification is centralized in `finally`.
                if rt.stopping:
                    break

        finally:
            # Mark actor as dead first
            rt.alive = False

            # Create inert ref for termination notification
            self_ref = ActorRef(
                _rid=rt.rid,
                _mailbox_put=rt.mailbox.put,
                _is_alive=lambda: False,
                _dead_letter=self.dead_letters.push,
            )

            # Notify watchers exactly once
            for watcher_rid in list(rt.watchers):
                watcher_rt = self._by_id.get(watcher_rid)
                if watcher_rt is None or not watcher_rt.alive:
                    continue
                try:
                    await watcher_rt.mailbox.put(
                        Envelope(
                            message=ActorTerminated(self_ref),
                            reply=None,
                        )
                    )
                except Exception:
                    pass

            await self._safe_on_stop(rt)
            await rt.mailbox.aclose()

    async def _safe_on_start(self, rt: _ActorRuntime) -> bool:
        """Run on_start safely. Returns False if actor should not proceed."""
        try:
            await rt.actor.on_start()
            return True
        except Exception:
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

        Order of evaluation
        -------------------
        1. Notify parent via `on_child_failure(...)`
        2. If parent returns a decision, obey it
        3. Otherwise, fall back to child's SupervisionPolicy
        """

        # If already stopping, do nothing further
        if rt.stopping:
            rt.alive = False
            return

        # --- 1. Parent callback ---
        if rt.parent is not None:
            parent_actor = rt.parent.actor
            try:
                decision = await parent_actor.on_child_failure(
                    child_ref=rt.actor._context.self_ref,
                    exc=exc,
                )
            except Exception:
                decision = None

            if decision is not None:
                await self._apply_supervisor_decision(rt, decision, exc)
                return

        # --- 2. Fallback to policy ---
        strategy = rt.policy.strategy

        if strategy is Strategy.ESCALATE:
            if rt.parent is None:
                rt.alive = False
                return
            await self._handle_failure(rt.parent, exc)
            rt.alive = False
            return

        if strategy is Strategy.STOP:
            await self._stop_runtime(rt)
            return

        if strategy is Strategy.RESTART:
            await self._restart_actor(rt)
            return

        rt.alive = False

    async def _apply_supervisor_decision(
        self,
        rt: _ActorRuntime,
        decision,
        exc: BaseException,
    ) -> None:
        """Apply a SupervisorDecision returned by a parent actor."""

        if decision is SupervisorDecision.IGNORE:
            await self._stop_runtime(rt)
            return

        if decision is SupervisorDecision.STOP:
            await self._stop_runtime(rt)
            return

        if decision is SupervisorDecision.RESTART:
            await self._restart_actor(rt)
            return

        if decision is SupervisorDecision.ESCALATE:
            if rt.parent is None:
                await self._stop_runtime(rt)
                return
            await self._handle_failure(rt.parent, exc)
            await self._stop_runtime(rt)
            return

        await self._stop_runtime(rt)

    async def _restart_actor(self, rt: _ActorRuntime) -> None:
        """Restart an actor instance while preserving its mailbox and ActorRef."""
        can_restart = await self._check_restart_limits(rt)
        if not can_restart:
            rt.alive = False
            rt.stopping = True
            await rt.mailbox.aclose()
            return

        await self._safe_on_stop(rt)
        rt.restart_timestamps.append(anyio.current_time())

        rt.actor = rt.actor_factory()
        rt.stopping = False

        from .ref import ActorRef

        self_ref = ActorRef(
            _rid=rt.rid,
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive and (not rt.stopping),
            _dead_letter=self.dead_letters.push,
        )

        self._inject_context(rt, self_ref=self_ref)

        started = await self._safe_on_start(rt)
        if not started:
            rt.alive = False

    async def _check_restart_limits(self, rt: _ActorRuntime) -> bool:
        """Enforce restart rate limits."""
        now = anyio.current_time()
        window = rt.policy.within_seconds

        # Drop timestamps outside the window
        rt.restart_timestamps = [t for t in rt.restart_timestamps if (now - t) <= window]

        return len(rt.restart_timestamps) < rt.policy.max_restarts

    async def _add_watch(self, watcher_ref: Any, target_ref: Any) -> None:
        watcher_rt = self._by_id.get(getattr(watcher_ref, "_rid", None))
        target_rt = self._by_id.get(getattr(target_ref, "_rid", None))
        if watcher_rt is None or target_rt is None:
            return
        target_rt.watchers.add(watcher_rt.rid)

    async def _remove_watch(self, watcher_ref: Any, target_ref: Any) -> None:
        watcher_rt = self._by_id.get(getattr(watcher_ref, "_rid", None))
        target_rt = self._by_id.get(getattr(target_ref, "_rid", None))
        if watcher_rt is None or target_rt is None:
            return
        target_rt.watchers.discard(watcher_rt.rid)

    def _record_dead_letter(self, *, ref: Any, message: Any, kind: str) -> None:
        dl = DeadLetter(
            ref=ref,
            message=message,
            kind=kind,  # type: ignore
            when=anyio.current_time(),
        )
        self._dead_letters.append(dl)
        if self.on_dead_letter is not None:
            try:
                self.on_dead_letter(dl)
            except Exception:
                pass

    def dead_letters_snapshot(self) -> list[DeadLetter]:
        return list(self._dead_letters)

    async def aclose(self) -> None:
        """Gracefully shutdown the actor system."""
        if self._closed:
            return
        self._closed = True

        # Request stop for all root actors and cascade to children.
        roots = [rt for rt in self._actors if rt.parent is None]
        for rt in roots:
            try:
                await self._stop_runtime(rt)
            except Exception:
                pass

        # Force-close all mailboxes to unblock actor loops.
        for rt in self._actors:
            try:
                await rt.mailbox.aclose()
            except Exception:
                pass

        # Wait for all actor tasks to finish.
        if self._tg is not None:
            tg = self._tg
            self._tg = None
            await tg.__aexit__(None, None, None)

    async def __aenter__(self) -> "ActorSystem":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()
