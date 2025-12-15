from __future__ import annotations


class PapyraError(Exception):
    """Base exception for all Papyra actor runtime errors."""


class ActorStopped(PapyraError):
    """
    Raised when interacting with an actor that is already stopped.

    This can happen if:
    - the system was shut down,
    - the actor crashed and supervision is not yet implemented,
    - the actor was explicitly stopped (future feature).
    """


class AskTimeout(PapyraError):
    """
    Raised when an `ask(...)` operation times out.

    Timeouts are controlled by the caller, not the actor.
    """


class MailboxClosed(PapyraError):
    """
    Raised when attempting to put messages into a mailbox that has been closed.

    Mailboxes are closed during actor shutdown.
    """
