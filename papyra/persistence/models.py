from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from papyra.address import ActorAddress


@dataclass(frozen=True, slots=True)
class PersistedEvent:
    """
    A serializable, storage-optimized representation of a lifecycle event within the actor system.

    Unlike runtime `ActorEvent` objects, which are transient and meant for immediate handling,
    this class is designed for long-term persistence (e.g., in a database or event log). It
    captures the essential metadata ("facts") of an event in a format that remains stable even
    if the internal runtime class definitions change.

    Attributes
    ----------
    system_id : str
        The unique identifier of the actor system where the event originated.
    actor_address : ActorAddress
        The logical address of the actor involved in the event.
    event_type : str
        The string name of the original event class (e.g., "ActorStarted", "ActorCrashed").
        This allows for polymorphic reconstruction or query filtering without needing the
        original class to be imported.
    payload : Mapping[str, Any]
        A dictionary containing relevant context specific to the event type (e.g., the
        exception message for a crash or the reason for a stop).
    timestamp : float
        The Unix timestamp (seconds) indicating when the event occurred.
    """

    system_id: str
    actor_address: ActorAddress
    event_type: str
    payload: Mapping[str, Any]
    timestamp: float


@dataclass(frozen=True, slots=True)
class PersistedAudit:
    """
    A serializable snapshot of the system's health and operational metrics.

    This class serves as a persistent record of an `AuditReport`. By storing sequences of these
    records, operators can analyze trends over time, such as growing actor counts (potential
    leaks) or spikes in dead letters.

    Attributes
    ----------
    system_id : str
        The unique identifier of the system being audited.
    timestamp : float
        The Unix timestamp (seconds) when the audit was performed.
    total_actors : int
        The total count of actors known to the system at the time of the audit.
    alive_actors : int
        The number of actors that were in the `alive` state.
    stopping_actors : int
        The number of actors that were in the process of shutting down.
    restarting_actors : int
        The number of actors that were undergoing a restart procedure.
    registry_size : int
        The total number of entries in the name registry.
    registry_orphans : tuple[str, ...]
        A list of registered names that did not point to a valid actor runtime.
    registry_dead : tuple[str, ...]
        A list of registered names pointing to actors that were not alive.
    dead_letters_count : int
        The cumulative count of dead letter messages observed by the system.
    """

    system_id: str
    timestamp: float
    total_actors: int
    alive_actors: int
    stopping_actors: int
    restarting_actors: int
    registry_size: int
    registry_orphans: tuple[str, ...]
    registry_dead: tuple[str, ...]
    dead_letters_count: int


@dataclass(frozen=True, slots=True)
class PersistedDeadLetter:
    """
    A serializable record of a message delivery failure.

    This class captures the context of a `DeadLetter` event for offline analysis. It is
    essential for debugging distributed systems, allowing developers to inspect what messages
    failed, when they failed, and who the intended recipient was.

    Attributes
    ----------
    system_id : str
        The unique identifier of the system where the delivery failure occurred.
    target : ActorAddress | None
        The address of the intended recipient. May be None if the address could not be
        resolved or parsed.
    message_type : str
        The string name of the message class/type (e.g., "PaymentRequest").
    payload : Any
        The actual content of the message that failed delivery.
    timestamp : float
        The Unix timestamp (seconds) when the message was routed to dead letters.
    """

    system_id: str
    target: ActorAddress | None
    message_type: str
    payload: Any
    timestamp: float


@dataclass(frozen=True)
class CompactionReport:
    """
    Result metadata produced by a physical compaction / vacuum operation.

    This object is observational only. It must never influence runtime behavior,
    but provides valuable insight for audits, CLI tooling, metrics, and debugging.

    Fields are intentionally optional where a backend cannot reasonably compute
    them (e.g. memory-only backends).
    """

    backend: str
    before_records: int
    after_records: int
    before_bytes: int | None = None
    after_bytes: int | None = None

    @property
    def removed_records(self) -> int:
        """
        Number of records physically removed by compaction.
        """
        return self.before_records - self.after_records

    @property
    def reclaimed_bytes(self) -> int | None:
        """
        Number of bytes reclaimed by compaction, if measurable.
        """
        if self.before_bytes is None or self.after_bytes is None:
            return None
        return self.before_bytes - self.after_bytes


class PersistenceAnomalyType(Enum):
    """
    Classification of persistence-level anomalies detected during startup scans.
    """

    TRUNCATED_LINE = auto()
    PARTIAL_WRITE = auto()
    CORRUPTED_LINE = auto()
    ORPHANED_ROTATED_FILE = auto()
    UNEXPECTED_FILE = auto()


@dataclass(frozen=True)
class PersistenceAnomaly:
    """
    Represents a detected persistence anomaly.

    This object is purely observational in Step 1.
    No repair or mutation is performed at this stage.
    """

    type: PersistenceAnomalyType
    path: str
    detail: str | None = None


@dataclass(frozen=True)
class PersistenceScanReport:
    """
    Result of a startup persistence scan.

    The scan reports all detected anomalies without modifying storage.
    """

    backend: str
    anomalies: tuple[PersistenceAnomaly, ...]

    @property
    def has_anomalies(self) -> bool:
        return bool(self.anomalies)


class PersistenceRecoveryMode(Enum):
    """
    How startup recovery should behave when anomalies are detected.
    """

    IGNORE = "ignore"
    REPAIR = "repair"
    QUARANTINE = "quarantine"
    REBUILD = "rebuild"


@dataclass(frozen=True)
class PersistenceRecoveryConfig:
    """
    Configuration for startup recovery.

    mode:
        IGNORE     -> only scan, never mutate
        REPAIR     -> rewrite in place (atomic replace)
        QUARANTINE -> move originals aside, then write repaired files
    quarantine_dir:
        Optional directory for quarantined files. If not provided, uses the same directory
        as the target file.
    """

    mode: PersistenceRecoveryMode = PersistenceRecoveryMode.IGNORE
    quarantine_dir: str | None = None


@dataclass(frozen=True)
class PersistenceRecoveryReport:
    """
    Result of a recovery run.

    repaired_files:
        Files that were rewritten/repaired.
    quarantined_files:
        Files that were moved aside (only in QUARANTINE mode).
    scan:
        The scan report that motivated recovery (always included).
    """

    backend: str
    scan: PersistenceScanReport
    repaired_files: tuple[str, ...] = ()
    quarantined_files: tuple[str, ...] = ()
