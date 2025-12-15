from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anyio.abc


class _Stop:
    """
    An internal sentinel class used to signal actor termination.

    This class is instantiated exactly once as the `STOP` singleton. It is injected into an
    actor's mailbox to instruct the event loop to cease processing and shut down gracefully.
    It ensures that the `on_stop` lifecycle hook is executed before the actor loop exits.

    Notes
    -----
    This type is not intended to be instantiated by users or exposed in the public API.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "<PapyraStop>"


# The singleton instance used to signal stopping.
STOP = _Stop()


@dataclass(frozen=True, slots=True)
class Envelope:
    """
    A container used to transport a message to an actor, optionally including a channel for a
    response.

    This class encapsulates the user-defined message and the mechanism required to send a reply
    back to the sender, facilitating the request-response pattern (often referred to as 'ask').
    The actor runtime automatically unwraps this envelope before passing the message to the
    actor instance.

    Attributes
    ----------
    message : Any
        The actual content of the message sent by the user or another actor.
    reply : anyio.abc.ObjectSendStream[Reply] | None
        An optional one-shot channel (send stream) used to transmit a `Reply` object back to
        the sender. If this is `None`, the message is treated as a "tell" (fire-and-forget)
        operation, and no response is expected. Defaults to None.
    """

    message: Any
    reply: anyio.abc.ObjectSendStream[Reply] | None = None


@dataclass(frozen=True, slots=True)
class Reply:
    """
    A wrapper representing the outcome of processing a message sent via the `ask` pattern.

    This structure carries either the successful result of a computation or an error that
    occurred during processing. It ensures that exceptions raised within an actor can be
    propagated back to the caller safely across async boundaries.

    Attributes
    ----------
    value : Any
        The return value obtained from the actor's `receive` method upon successful processing.
        Defaults to None.
    error : BaseException | None
        An exception instance if one was raised while the actor was handling the message. If
        this is set, `value` is typically ignored (or None). Defaults to None.
    """

    value: Any = None
    error: BaseException | None = None


@dataclass(frozen=True)
class ActorTerminated:
    """
    A system message broadcast to watching actors when a specific actor stops.

    This message is generated automatically by the actor system when a monitored actor reaches
    the end of its lifecycle (either normally or due to failure) and is delivered to the
    mailboxes of all actors that called `watch()` on the terminated actor.

    Attributes
    ----------
    ref : Any
        The `ActorRef` of the actor that has just terminated. The type is `Any` to avoid
        circular import dependencies with the reference implementation.
    """

    ref: Any


@dataclass(frozen=True, slots=True)
class DeadLetter:
    """
    A record of a message that could not be delivered to its destination.

    Dead letters occur when a message is sent to an actor that is no longer running or does
    not exist. These records are collected by the system's `DeadLetterMailbox` to aid in
    debugging, observability, and diagnostics of message flows.

    Attributes
    ----------
    target : Any
        The `ActorRef` (or equivalent identifier) of the intended recipient that was unreachable.
        Typed as `Any` to avoid circular imports.
    message : Any
        The original message payload that failed to be delivered.
    expects_reply : bool
        A boolean flag indicating whether the sender was waiting for a response (i.e., if the
        message was sent using `ask`). This helps identify if a process might be hanging
        waiting for a reply that will never arrive.
    """

    target: Any
    message: Any
    expects_reply: bool
