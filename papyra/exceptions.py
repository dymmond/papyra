from __future__ import annotations


class PapyraError(Exception):
    """
    The fundamental base class for all exceptions raised within the Papyra actor framework.

    All custom exceptions defined in this library inherit from this class. Users wishing to catch
    any error specific to the actor runtime (as opposed to standard Python errors like
    `ValueError` or `TypeError`) should catch this exception.
    """

    ...


class ActorStopped(PapyraError):
    """
    Raised when an operation attempts to interact with an actor that is no longer running.

    This exception serves as a signal that the target actor reference is invalid for the
    requested operation. It typically occurs in the following scenarios:
    1. The entire actor system has been shut down or is in the process of shutting down.
    2. The specific actor has crashed, and its supervision policy resulted in a permanent stop.
    3. The actor was explicitly stopped via `stop()` or `stop_self()`.

    Notes
    -----
    This ensures strict consistency; messages are never silently dropped into a void without
    feedback if the target is known to be dead.
    """

    def __init__(self, message: str = "Actor stopped", *, reason: str | None = None):
        super().__init__(message)
        self.reason = reason


class AskTimeout(PapyraError):
    """
    Raised when a request-response operation (`ask`) fails to complete within the allotted time.

    This exception indicates that the target actor did not send a `Reply` back before the
    timeout duration specified by the caller expired.

    Notes
    -----
    - Timeouts are enforced on the caller side (the sender), not by the actor processing the
      message.
    - A timeout does not necessarily mean the message wasn't processed; it only means the
      reply didn't arrive in time. The actor might still be working on it.
    """

    ...


class MailboxClosed(PapyraError):
    """
    Raised when attempting to push a message into a mailbox that has been permanently closed.

    Mailboxes are closed automatically during the actor shutdown sequence. Once closed, a
    mailbox cannot be reopened. This exception prevents new work from being accepted by an
    actor that is terminating.
    """

    ...
