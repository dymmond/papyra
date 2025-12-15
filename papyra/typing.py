from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

MessageT = TypeVar("MessageT", contravariant=True)
ReturnT = TypeVar("ReturnT", covariant=True)


@runtime_checkable
class Receives(Protocol[MessageT, ReturnT]):
    """
    Protocol for typed actor receive methods.

    Usage
    -----
    class MyActor(Actor, Receives[MyMessage, MyReply]):
        async def receive(self, msg: MyMessage) -> MyReply:
            ...
    """

    async def receive(self, msg: MessageT) -> ReturnT: ...


@runtime_checkable
class ReceivesAny(Protocol):
    """
    Explicit marker for actors that intentionally accept Any messages.
    """

    async def receive(self, msg: Any) -> Any: ...
