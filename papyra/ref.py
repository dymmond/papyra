from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anyio

from ._envelope import DeadLetter, Envelope
from .address import ActorAddress
from .exceptions import ActorStopped, AskTimeout


@dataclass(frozen=True, slots=True)
class ActorRef:
    """
    A handle or reference to a running actor instance.

    `ActorRef` is the primary public interface for interacting with an actor. It abstracts away
    the underlying runtime complexity (e.g., mailboxes, system IDs) and provides methods to send
    messages. It is lightweight, immutable, and safe to pass between actors.

    In distributed scenarios, the `ActorRef` carries the stable `ActorAddress`, allowing messages
    to be routed correctly even if the actor is remote or has been restarted (assuming persistence).

    Attributes
    ----------
    _rid : int
        The internal runtime ID of the actor.
    _mailbox_put : Callable[[Envelope], Any]
        A callable that pushes an `Envelope` into the actor's mailbox.
    _is_alive : Callable[[], bool]
        A callable that checks if the actor is currently running.
    _dead_letter : Callable[[DeadLetter], Any] | None, optional
        A callable to report messages that cannot be delivered. Defaults to None.
    _address : ActorAddress | None, optional
        The logical address of the actor. This is essential for addressing and location
        transparency. Defaults to None.
    """

    _rid: int
    _mailbox_put: Callable[[Envelope], Any]
    _is_alive: Callable[[], bool]
    _dead_letter: Callable[[DeadLetter], Any] | None = None
    _address: ActorAddress | None = None

    @property
    def address(self) -> ActorAddress:
        """
        Retrieve the logical address associated with this reference.

        Returns
        -------
        ActorAddress
            The stable address object.

        Raises
        ------
        RuntimeError
            If the `ActorRef` was initialized without an address (e.g., a pure internal test ref).
        """
        if self._address is None:
            raise RuntimeError("ActorRef has no address bound")
        return self._address

    async def tell(self, message: Any) -> None:
        """
        Send a message asynchronously without waiting for a reply ("fire-and-forget").

        This is the preferred method for actor-to-actor communication where no immediate response
        is required.

        Parameters
        ----------
        message : Any
            The message payload to deliver.

        Raises
        ------
        ActorStopped
            If the target actor is known to be stopped or if the mailbox is closed.
        """
        if not self._is_alive():
            self._dead_letter_emit(message, expects_reply=False)
            raise ActorStopped("Actor is not running.")

        try:
            await self._mailbox_put(Envelope(message=message, reply=None))
        except Exception:
            raise ActorStopped("Actor is not running.") from None

    async def ask(self, message: Any, *, timeout: float | None = None) -> Any:
        """
        Send a message and asynchronously wait for a reply.

        This method implements the request-response pattern. It creates a temporary one-time
        channel to receive the response from the target actor.

        Parameters
        ----------
        message : Any
            The message payload to deliver.
        timeout : float | None, optional
            The maximum time (in seconds) to wait for a reply. If None, waits indefinitely.
            Defaults to None.

        Returns
        -------
        Any
            The value returned by the target actor's `receive` method.

        Raises
        ------
        ActorStopped
            If the target actor is not running.
        AskTimeout
            If the timeout expires before a reply is received.
        BaseException
            If the target actor raises an exception while processing the message, that exception
            is re-raised here in the caller's context.
        """
        if not self._is_alive():
            self._dead_letter_emit(message, expects_reply=True)
            raise ActorStopped("Actor is not running.")

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

    def _dead_letter_emit(self, message: Any, *, expects_reply: bool) -> None:
        """
        Internal helper to route a message to the dead-letter queue.

        This is invoked when `tell` or `ask` detects that the actor is dead before sending.

        Parameters
        ----------
        message : Any
            The undelivered message.
        expects_reply : bool
            True if the message was sent via `ask`, False otherwise.
        """
        if self._dead_letter is None:
            return
        try:
            self._dead_letter(
                DeadLetter(
                    target=self,
                    message=message,
                    expects_reply=expects_reply,
                )
            )
        except Exception:
            return
