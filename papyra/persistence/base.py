from __future__ import annotations

from typing import Protocol, runtime_checkable

from papyra._envelope import DeadLetter
from papyra.audit import AuditReport
from papyra.events import ActorEvent


@runtime_checkable
class PersistenceBackend(Protocol):
    """
    Defines the interface for pluggable persistence and observability backends.

    A `PersistenceBackend` in this actor system is distinct from traditional database persistence
    layers used for application state (like event sourcing). Instead, this interface allows the
    actor runtime to offload *observable system facts*—such as lifecycle changes, health audits,
    and message delivery failures—to external storage or monitoring services.

    Implementations of this protocol are intended to be:
    1. **Append-only**: Recording a stream of facts rather than updating mutable records.
    2. **Non-intrusive**: Operations must not block the core actor loop or throw exceptions that
       could destabilize the runtime.
    3. **Fast**: Designed for high-throughput logging of events.

    This interface does **not** handle the serialization of actor internal state (variables) or
    the persistence of mailboxes.
    """

    def record_event(self, event: ActorEvent) -> None:
        """
        Persist a specific lifecycle event emitted by the actor system.

        This method is invoked synchronously by the system whenever a significant state change
        occurs (e.g., an actor starts, crashes, or stops). Implementations should ensure this
        operation is lightweight to avoid slowing down the event loop.

        Parameters
        ----------
        event : ActorEvent
            The event object detailing the occurrence (including timestamp, actor address, and
            event type).
        """
        ...

    def record_audit(self, report: AuditReport) -> None:
        """
        Persist a comprehensive system audit report.

        This method is invoked when a user or monitoring process requests a full system audit via
        `ActorSystem.audit()`. It allows for storing point-in-time snapshots of the system's
        health invariants.

        Parameters
        ----------
        report : AuditReport
            The data object containing aggregate statistics (actor counts, registry status) and
            individual actor snapshots.
        """
        ...

    def record_dead_letter(self, dead_letter: DeadLetter) -> None:
        """
        Persist a record of an undeliverable message.

        This method captures messages that were sent to stopped or non-existent actors. Storing
        these records is crucial for debugging lost message scenarios and verifying message flows
        in distributed systems.

        Parameters
        ----------
        dead_letter : DeadLetter
            The envelope containing the original message payload and metadata about the intended
            recipient.
        """
        ...

    async def aclose(self) -> None:
        """
        Asynchronously close the persistence backend connection.

        This method should ensure that any pending writes are flushed (if possible) and that
        underlying resources (e.g., database connections, file handles) are released gracefully.
        After this method returns, the backend should no longer accept new write operations.
        """
        ...
