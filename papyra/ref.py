from __future__ import annotations

"""
ActorRef: the only way user code interacts with an actor.

An ActorRef is an address/handle to an actor. It intentionally hides actor
implementation details and prevents direct calls into actor state.

This is critical for maintaining isolation and message-driven semantics.
"""

from dataclasses import dataclass
from typing import Any, Optional

import anyio

from ._envelope import Envelope
from .exceptions import ActorStopped, AskTimeout, MailboxClosed


@dataclass(frozen=True, slots=True)
class ActorRef:
    """
    Reference to a running actor.

    Notes
    -----
    ActorRef is intentionally small:
    - `tell(...)` sends a message and does not wait for a response.
    - `ask(...)` sends a message and waits for one response.

    `_rid` is an internal stable identifier used by the system to resolve
    parent/child relationships and future routing features.
    """

    _rid: int
    _mailbox_put: Any
    _is_alive: Any

    async def tell(self, message: Any) -> None:
        """
        Send a message without expecting a reply.

        Raises
        ------
        ActorStopped
            If the actor is not running.
        """
        if not self._is_alive():
            raise ActorStopped("Actor is not running.")

        try:
            await self._mailbox_put(Envelope(message=message, reply=None))
        except Exception:
            raise ActorStopped("Actor is not running.")

    async def ask(self, message: Any, *, timeout: Optional[float] = None) -> Any:
        """
        Send a message and await a reply.

        Parameters
        ----------
        message:
            The message to deliver.
        timeout:
            Optional timeout (seconds). If set, the caller controls how long
            they are willing to wait.

        Returns
        -------
        Any
            The value returned by the actor's `receive(...)`.

        Raises
        ------
        ActorStopped
            If the actor is not running.
        AskTimeout
            If `timeout` is set and expires before a reply arrives.
        BaseException
            Re-raises any exception thrown by the actor while processing.
        """
        if not self._is_alive():
            raise ActorStopped("Actor is not running.")

        # One-shot reply channel
        send, recv = anyio.create_memory_object_stream(1)

        try:
            await self._mailbox_put(Envelope(message=message, reply=send))

            try:
                if timeout is not None:
                    with anyio.fail_after(timeout):
                        reply = await recv.receive()
                else:
                    reply = await recv.receive()
            except TimeoutError as e:
                raise AskTimeout(f"ask() timed out after {timeout} seconds.") from e

            if reply.error is not None:
                raise reply.error

            return reply.value
        finally:
            await send.aclose()
            await recv.aclose()
