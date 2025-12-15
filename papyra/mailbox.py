from __future__ import annotations
"""
Mailbox primitives for Papyra actors.

A mailbox is a FIFO queue of messages. The actor runtime processes messages
sequentially, one at a time, from the mailbox.

Implementation notes
--------------------
We use `anyio.create_memory_object_stream` because:
- it is async-native,
- works across asyncio/trio backends,
- supports backpressure with bounded capacity.

We keep a small abstraction layer so we can add:
- priority mailboxes,
- persistent mailboxes,
- metrics,
without rewriting the runtime.
"""

from dataclasses import dataclass, field
from typing import Optional

import anyio

from ._envelope import Envelope
from .exceptions import MailboxClosed



@dataclass(slots=True)
class Mailbox:
    """
    A simple mailbox backed by an AnyIO memory object stream.

    Parameters
    ----------
    capacity:
        Maximum number of pending messages. If None, capacity is unbounded.
        In practice, bounded mailboxes are preferable to prevent memory blowups.
    """

    capacity: Optional[int] = 1024
    _send: anyio.abc.ObjectSendStream[Envelope] = field(init=False)
    _recv: anyio.abc.ObjectReceiveStream[Envelope] = field(init=False)
    _closed: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        send, recv = anyio.create_memory_object_stream[Envelope](self.capacity or 0)
        self._send = send
        self._recv = recv
        self._closed = False

    async def put(self, env: Envelope) -> None:
        """
        Enqueue a message envelope.

        Raises
        ------
        MailboxClosed
            If the mailbox is already closed.
        """
        if self._closed:
            raise MailboxClosed("Mailbox is closed.")
        try:
            await self._send.send(env)
        except (anyio.ClosedResourceError, anyio.BrokenResourceError) as e:
            raise MailboxClosed("Mailbox is closed.") from e

    async def get(self) -> Envelope:
        """
        Dequeue the next message envelope.

        Notes
        -----
        If the mailbox is closed and empty, `anyio.EndOfStream` will be raised
        by the underlying stream. The actor runtime treats this as a shutdown
        signal.
        """
        return await self._recv.receive()

    async def aclose(self) -> None:
        """
        Close the mailbox.

        Closing the send side prevents new messages from being enqueued.
        """
        if self._closed:
            return
        self._closed = True
        await self._send.aclose()
