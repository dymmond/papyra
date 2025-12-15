from __future__ import annotations
"""
ActorSystem: lifecycle, spawning, and shutdown.

This is the runtime entry-point. It owns:
- the task group where actors run,
- references to live actors,
- shutdown semantics.
"""

from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

import anyio
import anyio.abc

from ._envelope import Reply
from .actor import Actor
from .exceptions import ActorStopped
from .mailbox import Mailbox

A = TypeVar("A", bound=Actor)


@dataclass(slots=True)
class _ActorRuntime:
    actor: Actor
    mailbox: Mailbox
    alive: bool = True


class ActorSystem:
    """
    The root runtime container for actors.

    Usage
    -----
    system = ActorSystem()
    await system.start()

    ref = system.spawn(MyActor)
    await ref.tell(...)

    await system.aclose()

    Notes
    -----
    We use AnyIO so users can run this on asyncio or trio without code changes.
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
    ):
        """
        Spawn a new actor and return an ActorRef.

        Parameters
        ----------
        actor_factory:
            Either a type (class) of Actor or a zero-arg callable returning an Actor.
        mailbox_capacity:
            Size of the mailbox buffer. None means unbounded.

        Returns
        -------
        ActorRef
            A reference to the new actor.

        Raises
        ------
        ActorStopped
            If the system is not started or already closed.
        """
        from .ref import ActorRef  # local import to keep modules loosely coupled

        if self._closed or self._tg is None:
            raise ActorStopped("ActorSystem is not running. Did you call await system.start()?")

        actor: Actor
        if isinstance(actor_factory, type):
            actor = actor_factory()
        else:
            actor = actor_factory()

        rt = _ActorRuntime(actor=actor, mailbox=Mailbox(capacity=mailbox_capacity), alive=True)
        self._actors.append(rt)

        self._tg.start_soon(self._run_actor, rt)

        return ActorRef(
            _mailbox_put=rt.mailbox.put,
            _is_alive=lambda: (not self._closed) and rt.alive,
        )

    async def _run_actor(self, rt: _ActorRuntime) -> None:
        """
        Actor event loop with lifecycle hooks.

        Execution order
        ---------------
        1. actor.on_start()
        2. message processing loop
        3. actor.on_stop()

        Failure semantics (Step 2)
        --------------------------
        - Exceptions in `receive()` stop the actor
        - Exceptions in lifecycle hooks do NOT crash the system
        - `on_stop()` always runs
        """
        try:
            # --- on_start ---
            try:
                await rt.actor.on_start()
            except Exception:
                # Lifecycle hooks must never bring down the system
                rt.alive = False
                return

            # --- message loop ---
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
                    if env.reply is not None:
                        try:
                            await env.reply.send(Reply(value=None, error=e))
                        except Exception:
                            pass
                    rt.alive = False
                    break

        finally:
            # --- on_stop (guaranteed) ---
            try:
                await rt.actor.on_stop()
            except Exception:
                pass

            rt.alive = False
            await rt.mailbox.aclose()

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
