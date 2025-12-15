from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import anyio
import anyio.abc


class _Stop:
    """
    Internal stop sentinel.

    This must never be exposed as public API. It is used to signal an actor loop
    to terminate gracefully (ensuring `on_stop()` runs).
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "<PapyraStop>"


STOP = _Stop()


@dataclass(frozen=True, slots=True)
class Envelope:
    """
    Wraps an incoming message for delivery to an actor.

    Attributes
    ----------
    message:
        The user-provided message.
    reply:
        Optional one-shot channel used for request/reply (`ask`).
        If present, the actor runtime will send back a `Reply` after processing.
    """

    message: Any
    reply: anyio.abc.ObjectSendStream["Reply"] | None = None


@dataclass(frozen=True, slots=True)
class Reply:
    """
    Represents the result of processing a message sent via `ask`.

    Exactly one of `value` or `error` is set.

    Attributes
    ----------
    value:
        The return value from the actor's `receive(...)`.
    error:
        An exception raised while handling the message.
    """

    value: Any = None
    error: BaseException | None = None


@dataclass(frozen=True)
class ActorTerminated:
    """System message delivered to watchers when an actor stops."""

    ref: Any
