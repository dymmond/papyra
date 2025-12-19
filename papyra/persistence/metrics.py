from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class PersistenceMetrics:
    """
    A data container for tracking operational metrics of the persistence layer.

    This class serves as a centralized registry for monitoring the health and activity
    of the storage backend. It tracks write volume, maintenance operations (scans,
    recoveries, compactions), and detected issues.

    These metrics are typically aggregated and exposed via monitoring systems (e.g.,
    Prometheus) to provide observability into the persistence layer's performance
    and stability.

    Attributes:
        records_written (int): The total number of individual records (events, audits,
            etc.) successfully appended to storage.
        bytes_written (int): The total volume of data in bytes written to the storage
            medium.
        scans (int): The number of times a health scan has been initiated.
        anomalies_detected (int): The cumulative count of structural or data anomalies
            found during scans (e.g., corrupted lines, orphaned files).
        recoveries (int): The number of recovery procedures executed to repair anomalies.
        compactions (int): The number of times a compaction or vacuum operation has
            been run to reclaim space.
    """

    records_written: int = 0
    bytes_written: int = 0

    scans: int = 0
    anomalies_detected: int = 0

    recoveries: int = 0
    compactions: int = 0

    write_errors: int = 0
    scan_errors: int = 0
    recovery_errors: int = 0
    compaction_errors: int = 0

    def reset(self) -> None:
        """
        Reset all metric counters to zero.

        This method is useful for clearing statistics between test runs or at the
        start of a new monitoring interval if cumulative metrics are not desired.
        """
        self.records_written = 0
        self.bytes_written = 0
        self.scans = 0
        self.anomalies_detected = 0
        self.recoveries = 0
        self.compactions = 0

    def snapshot(self) -> Mapping[str, int]:
        """
        Return a stable, read-only snapshot of current metrics.

        This method must never raise and must not expose internal state.
        """
        try:
            return {
                "records_written": self.records_written,
                "bytes_written": self.bytes_written,
                "scans": self.scans,
                "anomalies_detected": self.anomalies_detected,
                "recoveries": self.recoveries,
                "compactions": self.compactions,
                "write_errors": self.write_errors,
                "scan_errors": self.scan_errors,
                "recovery_errors": self.recovery_errors,
                "compaction_errors": self.compaction_errors,
            }
        except Exception:
            # Absolute safety net
            return {}


class PersistenceMetricsMixin:
    """
    A mixin class that equips persistence backends with metric tracking capabilities.

    This class provides a standardized mechanism for backends to initialize and expose
    operational statistics (e.g., write counts, error rates). It ensures that metrics
    are handled consistently across different storage implementations.

    Usage Guidelines:
    - Backends MAY inherit from this mixin if they wish to support observability.
    - The core system (e.g., ActorSystem) MUST NOT strictly depend on the presence
      of this mixin or assume that metrics are available on every backend. Metrics
      should be treated as an optional enhancement.

    Attributes:
        _metrics (PersistenceMetrics): The internal container for tracking statistics.
    """

    def __init__(self) -> None:
        """
        Initialize the metrics mixin.

        This sets up a fresh `PersistenceMetrics` instance with all counters reset
        to zero, ready to track backend activity.
        """
        self._metrics = PersistenceMetrics()

    @property
    def metrics(self) -> PersistenceMetrics:
        """
        Retrieve the current operational metrics for this backend.

        This property exposes the `PersistenceMetrics` object, allowing external
        monitors or the system to inspect performance data such as records written,
        bytes stored, and anomalies detected.

        Returns:
            PersistenceMetrics: The container holding the current statistical counters.
        """
        return self._metrics
