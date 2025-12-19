from __future__ import annotations

from typing import Any

from papyra._envelope import DeadLetter
from papyra.audit import AuditReport
from papyra.events import ActorEvent

from .metrics import PersistenceMetricsMixin
from .models import PersistenceScanReport
from .retention import RetentionPolicy


class PersistenceBackend(PersistenceMetricsMixin):
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

    def __init__(self, *, retention_policy: RetentionPolicy | None = None) -> None:
        super().__init__()
        self._retention = retention_policy or RetentionPolicy()

    @property
    def retention(self) -> RetentionPolicy | None:
        """
        Retrieve the currently configured retention policy.

        This property provides access to the rules governing data lifecycle management,
        specifying constraints such as the maximum number of records, data age, or
        storage size limits.

        Returns:
            RetentionPolicy | None: The retention policy instance if configured,
                otherwise None.
        """
        return self._retention

    async def record_event(self, event: ActorEvent | Any) -> None:
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

    async def record_audit(self, report: AuditReport | Any) -> None:
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

    async def record_dead_letter(self, dead_letter: DeadLetter | Any) -> None:
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

    async def compact(self) -> Any:
        """
        Physically compact / vacuum the underlying storage by rewriting it while applying retention.

        Retention in Papyra is typically enforced logically at read time. Compaction is the explicit,
        destructive operation that makes retention *physical* by rewriting the stored records so that
        old/expired records are removed from disk.

        Contract
        --------
        - This operation MUST be explicit (never automatic).
        - Implementations SHOULD be crash-safe and atomic (e.g. write-to-temp + `os.replace`).
        - Implementations MUST apply the configured `RetentionPolicy` in the same way as reads.
        - Memory-only backends MAY implement this as a no-op.
        - This method MUST NOT raise in a way that can crash the actor system; callers may treat it
          as best-effort.

        Returns
        -------
        Any
            Optional backend-specific compaction report/metadata (e.g. before/after counts/bytes).
            Backends may return `None` if no report is produced.
        """
        return None

    async def scan(self) -> PersistenceScanReport | None:
        """
        Scan the persistence backend for corruption or structural anomalies.

        This method MUST NOT mutate storage.
        It is intended to run at startup before actors begin processing.

        Startup semantics
        -----------------
        - MUST be safe to call before any actors are started
        - MUST NOT mutate storage
        - MUST NOT emit events or audits
        - MAY return None if unsupported

        Returns
        -------
        PersistenceScanReport | None
            A scan report describing detected anomalies, or None if unsupported.
        """
        return None

    async def recover(self, config: Any | None = None) -> Any:
        """
        Run startup recovery according to the provided configuration.

        This method MAY mutate storage depending on config.mode.
        Default implementation does nothing.

        Startup semantics
        -PersistenceBackend

        Returns
        -------
        PersistenceRecoveryReport | None
        """
        return None

    async def aclose(self) -> None:
        """
        Asynchronously close the persistence backend connection.

        This method should ensure that any pending writes are flushed (if possible) and that
        underlying resources (e.g., database connections, file handles) are released gracefully.
        After this method returns, the backend should no longer accept new write operations.
        """
        ...
