from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from papyra.persistence.models import PersistenceRecoveryConfig


class PersistenceStartupMode(str, Enum):
    """
    Enumeration defining the strategies for handling persistence anomalies during startup.

    This enum dictates the behavior of the system when it initializes the persistence layer.
    It controls whether the system should proceed blindly, check for errors, attempt repairs,
    or halt execution upon finding data issues.

    Attributes:
        IGNORE: Proceed with startup immediately, skipping any checks for data corruption
            or structural anomalies. This is the fastest mode but risks operating on
            corrupt data.
        SCAN_ONLY: Perform a scan to detect anomalies and log a warning report, but continue
            startup regardless of the findings. Useful for auditing without intervention.
        RECOVER: Scan for anomalies and automatically attempt to repair them using the
            configured recovery strategy before completing startup. This ensures the
            system starts with a clean state.
        FAIL_ON_ANOMALY: Scan for anomalies and abort the startup process by raising an
            exception if any issues are detected. This enforces strict data integrity.
    """

    IGNORE = "ignore"
    SCAN_ONLY = "scan_only"
    RECOVER = "recover"
    FAIL_ON_ANOMALY = "fail_on_anomaly"


@dataclass(slots=True)
class PersistenceStartupConfig:
    """
    Configuration object controlling the persistence layer's behavior during initialization.

    This configuration is used by the ActorSystem (or equivalent runner) to determine
    how to handle the state of the persistence backend when the application boots up.

    Attributes:
        mode (PersistenceStartupMode): The specific startup strategy to employ.
            Defaults to PersistenceStartupMode.IGNORE.
        recovery (PersistenceRecoveryConfig | None): The configuration settings for
            the recovery process (e.g., quarantine directories, repair modes).
            This is only relevant if `mode` is set to RECOVER. Defaults to None.
        timeout_seconds (float | None): A timeout limit for the startup scan/recovery
            process. If the process takes longer than this duration, it may be aborted.
            Defaults to None (no timeout).
    """

    mode: PersistenceStartupMode | str = PersistenceStartupMode.IGNORE
    recovery: PersistenceRecoveryConfig | None = None
    timeout_seconds: float | None = None
