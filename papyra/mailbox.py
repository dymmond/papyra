from __future__ import annotations

from dataclasses import dataclass, field

import anyio

from ._envelope import Envelope
from .exceptions import MailboxClosed


@dataclass(slots=True)
class Mailbox:
    """
    A lightweight, asynchronous mailbox implementation backed by AnyIO memory streams.

    The mailbox acts as a buffered FIFO (First-In-First-Out) queue that holds `Envelope` objects
    for an actor. It provides the mechanism for asynchronous message passing, allowing senders
    to push messages without waiting for the receiver to process them immediately, subject to
    capacity limits.

    Attributes
    ----------
    capacity : int | None
        The maximum number of items the mailbox can hold before blocking senders.
        If set to None or 0, the behavior depends on the underlying AnyIO implementation
        (typically treated as infinite or unbuffered depending on context, but here treated as
        a buffer size). Defaults to 1024.
    _send : anyio.abc.ObjectSendStream[Envelope]
        The internal write-end of the stream used to enqueue messages.
    _recv : anyio.abc.ObjectReceiveStream[Envelope]
        The internal read-end of the stream used by the actor to dequeue messages.
    _closed : bool
        Internal flag tracking whether the mailbox has been explicitly closed.
    """

    capacity: int | None = 1024
    _send: anyio.abc.ObjectSendStream[Envelope] = field(init=False)
    _recv: anyio.abc.ObjectReceiveStream[Envelope] = field(init=False)
    _closed: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        """
        Initialize the internal AnyIO streams after the dataclass fields are set.
        """
        # 0 in AnyIO usually implies an unbuffered channel where send waits for receive.
        # However, high-level Actor mailboxes usually want at least some buffer or infinite.
        # If capacity is None, we pass math.inf if AnyIO supported it, but here we pass 0
        # or large int. (Implementation detail: AnyIO streams with size 0 are unbuffered).
        buffer_size = self.capacity if self.capacity is not None else 0
        send, recv = anyio.create_memory_object_stream[Envelope](buffer_size)
        self._send = send
        self._recv = recv
        self._closed = False

    async def put(self, env: Envelope) -> None:
        """
        Asynchronously push a message envelope into the mailbox.

        If the mailbox is full (backpressure), this method will suspend execution until space
        becomes available.

        Parameters
        ----------
        env : Envelope
            The message envelope to enqueue.

        Raises
        ------
        MailboxClosed
            If the mailbox has been closed and cannot accept new messages.
        """
        if self._closed:
            raise MailboxClosed("Mailbox is closed.")
        try:
            await self._send.send(env)
        except (anyio.ClosedResourceError, anyio.BrokenResourceError) as e:
            raise MailboxClosed("Mailbox is closed.") from e

    async def get(self) -> Envelope:
        """
        Asynchronously retrieve the next message envelope from the mailbox.

        This method suspends execution if the mailbox is empty, waiting for a new message to
        arrive.

        Returns
        -------
        Envelope
            The next message in the queue.

        Raises
        ------
        anyio.EndOfStream
            If the mailbox has been closed and no more messages are available. The actor runtime
            uses this exception to detect when to shut down the message loop.
        """
        return await self._recv.receive()

    async def aclose(self) -> None:
        """
        Gracefully close the mailbox.

        This closes the sending end of the stream, preventing any new messages from being
        enqueued. Messages already in the buffer can still be retrieved via `get()`. Once the
        buffer is drained, `get()` will raise `EndOfStream`.
        """
        if self._closed:
            return
        self._closed = True
        await self._send.aclose()
