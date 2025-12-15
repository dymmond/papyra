from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

MessageT = TypeVar("MessageT", contravariant=True)
ReturnT = TypeVar("ReturnT", covariant=True)


@runtime_checkable
class Receives(Protocol[MessageT, ReturnT]):
    """
    A structural protocol defining the type signature for an actor's `receive` method.

    This protocol is used for static type checking to ensure that an actor implementation
    correctly handles specific message types and returns the expected reply types. It enables
    stricter type safety in an otherwise dynamic actor system.

    Type Variables
    --------------
    MessageT
        The type of message the actor expects to receive. This is contravariant, meaning an
        actor expecting `BaseMessage` can also handle `DerivedMessage`.
    ReturnT
        The type of the result returned by the actor. This is covariant, meaning if an actor
        returns `DerivedReply`, it satisfies a requirement for `BaseReply`.

    Usage
    -----
    ```python
    class MyMessage: ...


    class MyReply: ...


    class MyActor(Actor, Receives[MyMessage, MyReply]):
        async def receive(self, msg: MyMessage) -> MyReply:
            # Type checkers will validate this signature against the Protocol
            return MyReply()
    ```
    """

    async def receive(self, msg: MessageT) -> ReturnT:
        """
        Process the incoming typed message and return a typed result.

        Parameters
        ----------
        msg : MessageT
            The typed input message.

        Returns
        -------
        ReturnT
            The typed response.
        """
        ...


@runtime_checkable
class ReceivesAny(Protocol):
    """
    A marker protocol for actors designed to accept messages of any type.

    This is useful for generic actors, routers, or supervisors that do not enforce strict
    typing on their input messages. Implementing this protocol explicitly signals to type
    checkers (and human readers) that the use of `Any` in the signature is intentional
    design, not loose typing.
    """

    async def receive(self, msg: Any) -> Any:
        """
        Process an arbitrary message and return an arbitrary result.

        Parameters
        ----------
        msg : Any
            The input message.

        Returns
        -------
        Any
            The result of processing.
        """
        ...
