from __future__ import annotations

from dataclasses import dataclass

from .address import ActorAddress


@dataclass(slots=True, frozen=True)
class ActorEvent:
    """
    Base class for all public lifecycle events emitted by the actor system.

    These events are typically used for observability, auditing, or by specialized "watcher"
    actors that monitor the health and status of the system.

    Attributes
    ----------
    address : ActorAddress
        The logical address of the actor that generated this event.
    """

    address: ActorAddress


@dataclass(slots=True, frozen=True)
class ActorStarted(ActorEvent):
    """
    Event emitted when an actor has successfully started.

    This event signifies that the actor's `on_start` hook has completed successfully and the
    actor is now ready to process messages from its mailbox.
    """

    pass


@dataclass(slots=True, frozen=True)
class ActorRestarted(ActorEvent):
    """
    Event emitted when an actor has been restarted by its supervisor.

    This occurs when an actor crashes (raises an exception) and the supervision policy dictates
    a restart. The actor's state is reset (re-initialized via factory), but it retains its
    mailbox and address.

    Attributes
    ----------
    reason : BaseException
        The exception that caused the previous instance of the actor to crash.
    """

    reason: BaseException


@dataclass(slots=True, frozen=True)
class ActorStopped(ActorEvent):
    """
    Event emitted when an actor has stopped permanently.

    This marks the end of the actor's lifecycle. It is emitted after the `on_stop` hook has
    executed (or attempted to execute). No further messages will be processed by this actor.

    Attributes
    ----------
    reason : str | None
        An optional human-readable explanation for why the actor stopped (e.g., "shutdown",
        "failure"). Defaults to None.
    """

    reason: str | None = None


@dataclass(slots=True, frozen=True)
class ActorCrashed(ActorEvent):
    """
    Event emitted when an actor fails with an unhandled exception.

    This event typically precedes an `ActorRestarted` or `ActorStopped` event, depending on the
    supervision decision. It serves as a direct alert that an error occurred within the actor's
    logic.

    Attributes
    ----------
    error : BaseException
        The exception raised by the actor during message processing or initialization.
    """

    error: BaseException
