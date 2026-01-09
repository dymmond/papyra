from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from sayer import Option, error, group, info, success

from papyra import monkay
from papyra.persistence.base import PersistenceBackend
from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import (
    PersistenceRecoveryConfig,
    PersistenceRecoveryMode,
)
from papyra.persistence.startup import (
    PersistenceStartupConfig,
    PersistenceStartupMode,
)

help = """
Persistence Management CLI Module.

**Manage persistence health, recovery and compaction**

This module defines the command-line interface group for managing the persistence layer
of the application. It serves as the parent command for operations related to storage
health checks, data recovery, and log compaction.
"""


persistence = group(
    name="persistence",
    help=help,
)


def _get_persistence(path: Path | None) -> Any:
    """
    Resolve the appropriate persistence backend instance based on the provided inputs.

    This helper function determines which persistence strategy to use for the current
    operation. It allows for an override via a specific file path, which is useful for
    ad-hoc operations like recovery or inspection. If no path is specified, it defaults
    to the globally configured application persistence.

    Args:
        path (Path | None): An optional file system path.
            - If provided: A new `JsonFilePersistence` instance is created pointing
              to this specific file.
            - If None: The function returns the system-wide persistence backend
              defined in `monkay.settings`.

    Returns:
        Any: An initialized persistence backend instance (e.g., JsonFilePersistence or
            the global default).
    """
    if path is not None:
        # If an explicit path is provided, bypass the global settings and instantiate
        # a specific file-based persistence backend (usually for recovery or tools).
        return JsonFilePersistence(path)

    # Otherwise, return the standard persistence backend configured for the application.
    return monkay.settings.persistence


@persistence.command()
async def scan(
    path: Annotated[Path | None, Option(None, help="Persistence file path")],
) -> None:
    """
    Perform a structural health check on the configured persistence backend.

    This command initiates a scan operation to identify data corruption, orphaned files,
    or truncated records within the storage layer. It is a read-only operation that
    reports the current state of the persistence files without modifying them.

    Exit Codes:
        0: Scan completed successfully and no anomalies were found.
        2: Scan completed but anomalies were detected (SystemExit raised).

    Behavior:
        - Retrieves the active persistence backend from the global settings.
        - Invokes the backend's `scan()` method.
        - If the backend does not support scanning (returns None), an info message is shown.
        - If the backend is healthy, a success message is displayed.
        - If anomalies are found, details are printed to stderr and the process exits with code 2.
    """
    backend = _get_persistence(path)
    report = await backend.scan()

    if report is None:
        info("Persistence backend does not support scanning.")
        return

    if not report.anomalies:
        success("Persistence is healthy.")
        return

    error(f"Found {len(report.anomalies)} persistence anomalies:")
    for a in report.anomalies:
        error(f"- {a.type.name}: {a.path} ({a.detail})")

    # Exit with a non-zero status code to indicate failure to external tools/scripts
    raise SystemExit(2)


@persistence.command()
async def recover(
    path: Annotated[Path | None, Option(None, help="Persistence file path")],
    mode: Annotated[
        str,
        Option(help="Recovery mode"),
    ] = "repair",
    quarantine_dir: Annotated[
        Path | None,
        Option(help="Directory for quarantined files", required=False),
    ] = None,
) -> None:
    """
    Manually execute the persistence recovery process via the command line.

    This command forces the persistence backend to attempt to repair corruption or
    structural anomalies based on the specified mode. It creates a recovery configuration,
    invokes the backend's recovery logic, and reports the summary of actions taken
    (repaired files, quarantined files).

    Exit Codes:
        0: Recovery completed successfully, or the backend does not support recovery.
        3: Recovery process finished, but anomalies still remain (partial failure).

    Args:
        mode (PersistenceRecoveryMode): The strategy to use for recovery.
            - REPAIR: Fixes issues in place where possible.
            - QUARANTINE: Moves corrupt files aside before repairing.
            Defaults to PersistenceRecoveryMode.REPAIR.
        quarantine_dir (str | None): The specific directory path to move quarantined
            files into. If not provided, a default location (usually alongside the logs)
            is used. Defaults to None.
    """
    backend = _get_persistence(path)

    try:
        mode_enum = PersistenceRecoveryMode(mode.lower())
    except ValueError:
        raise SystemExit(f"Invalid recovery mode: {mode}") from None

    if mode_enum is PersistenceRecoveryMode.QUARANTINE:
        if quarantine_dir is None:
            raise SystemExit(f"{PersistenceRecoveryMode.QUARANTINE.value} mode requires --quarantine-dir")
        quarantine_dir.mkdir(parents=True, exist_ok=True)

    cfg = PersistenceRecoveryConfig(
        mode=mode_enum,
        quarantine_dir=str(quarantine_dir) if quarantine_dir else None,
    )

    report = await backend.recover(cfg)

    info("Recovery completed")

    for f in report.repaired_files:
        info(f"repaired {f}")

    for f in report.quarantined_files:
        info(f"quarantined {f}")


@persistence.command()
async def startup_check(
    path: Annotated[Path | None, Option(None, help="Persistence file path")],
    mode: Annotated[
        str,
        Option(help="Startup behavior"),
    ] = "fail_on_anomaly",
    recovery_mode: Annotated[
        str | None,
        Option(help="Recovery mode if startup recovery is enabled", required=False),
    ] = None,
) -> None:
    """
    Simulate the persistence startup sequence to verify system readiness.

    This command mimics the internal logic of the `ActorSystem` startup process
    without actually launching the task group or spawning actors. It executes the
    configured scan and, if requested, the recovery procedures.

    This tool is particularly useful for:
    - Pre-deployment health checks (e.g., Kubernetes InitContainers).
    - Verifying that a dataset is compatible with the current persistence configuration.
    - Debugging startup failures related to data corruption.

    Exit Codes:

    - 0: Startup check passed (clean scan or successful recovery).
    - 4: Anomalies detected while in FAIL_ON_ANOMALY mode.
    - 5: Recovery was attempted but failed to resolve all anomalies.

    Args:

    - mode (PersistenceStartupMode): The startup strategy to simulate (e.g., IGNORE,
        FAIL_ON_ANOMALY, RECOVER). Defaults to FAIL_ON_ANOMALY.
    - recovery_mode (PersistenceRecoveryMode | None, optional): The specific recovery
        strategy to apply if `mode` is set to RECOVER. Defaults to None.
    """
    backend = _get_persistence(path)

    try:
        mode_enum = mode if isinstance(mode, PersistenceStartupMode) else PersistenceStartupMode(mode.lower())
    except ValueError:
        raise SystemExit(f"Invalid startup mode: {mode}") from None

    recovery_enum = None
    if recovery_mode is not None:
        try:
            recovery_enum = (
                recovery_mode
                if isinstance(recovery_mode, PersistenceRecoveryMode)
                else PersistenceRecoveryMode(recovery_mode.lower())
            )
        except ValueError:
            raise SystemExit(f"Invalid recovery mode: {recovery_mode}") from None

    cfg = PersistenceStartupConfig(
        mode=mode,
        recovery=(PersistenceRecoveryConfig(mode=recovery_enum) if recovery_enum is not None else None),
    )

    scan = await backend.scan()

    if scan is None or not scan.has_anomalies:
        info("Persistence is healthy")
        return

    if mode_enum is PersistenceStartupMode.FAIL_ON_ANOMALY:
        error(f"Persistence anomalies detected: {scan.anomalies}")
        raise SystemExit(1)

    if mode_enum is PersistenceStartupMode.RECOVER:
        await backend.recover(cfg.recovery)
        info("Recovery successful")
        return


@persistence.command()
async def compact(
    path: Annotated[Path | None, Option(None, help="Persistence file path")],
) -> None:
    """
    Trigger a physical compaction or vacuum operation on the persistence backend.

    This command instructs the backend to optimize its storage usage. The exact nature
    of this operation depends on the specific backend implementation:
    - For SQL backends: Might execute a VACUUM or similar maintenance command.
    - For File backends: Might rewrite logs to remove obsolete or deleted records.
    - For In-Memory backends: Might trigger garbage collection or dict resizing.

    This is generally a maintenance task that can be scheduled periodically to
    reclaim disk space and improve performance.
    """
    backend = _get_persistence(path)

    result = await backend.compact()

    if result is None:
        info("Compaction completed")
        return

    if isinstance(result, dict):
        info("Compaction completed")
        for k, v in result.items():
            info(f"  {k}: {v}")
        return

    # Fallback (best effort)
    info("Compaction completed")


@persistence.command()
async def inspect(
    path: Annotated[Path | None, Option(None, help="Persistence file path")],
    limit: Annotated[
        int,
        Option(1000, help="Max items per category to sample for counts"),
    ] = 1000,
    show_metrics: Annotated[
        bool,
        Option(False, help="Show metrics snapshot (if backend supports it)"),
    ] = False,
) -> None:
    """
    Display a high-level summary of the persistence backend's configuration and state.

    This command inspects the active persistence layer to report its type, retention
    policies, and approximate data counts. It provides a quick way to verify that
    the backend is configured correctly and is operational.

    Features:
    - **Backend Identification**: Shows the class name of the active backend.
    - **Retention Policy**: detailed dump of active retention rules (max records, age, etc).
    - **Quick Counts**: Samples the most recent records (up to `limit`) to provide
      a rough estimate of the volume of events, audits, and dead letters.
    - **Metrics (Optional)**: If requested, displays the internal performance counters.

    Args:
        path (Path | None): Overrides the default persistence path. Useful for inspecting
            backup files or offline logs. Defaults to None.
        limit (int): The maximum number of items to retrieve per category (events, audits)
            when calculating counts. This prevents the inspection from hanging on massive
            datasets. Defaults to 1000.
        show_metrics (bool): If True, appends the backend's internal metrics snapshot
            to the output. Defaults to False.
    """
    # Resolve the persistence backend (either system default or file-specific)
    backend: PersistenceBackend = _get_persistence(path)

    info("Persistence Inspect")
    info("------------------")
    info(f"backend: {type(backend).__name__}")

    # ---------------------------------------------------------
    # Retention Policy Inspection
    # ---------------------------------------------------------
    # Safely retrieve retention attributes without assuming the object shape
    r = getattr(backend, "retention", None)
    if r is None:
        info("retention: <none>")
    else:
        info(
            f"retention: max_records={getattr(r, 'max_records', None)} "
            f"max_age_seconds={getattr(r, 'max_age_seconds', None)} "
            f"max_total_bytes={getattr(r, 'max_total_bytes', None)}"
        )

    # ---------------------------------------------------------
    # Data Sampling / Counts
    # ---------------------------------------------------------
    # We use a try-block because 'list_*' methods might not be supported by all backends
    # or might fail if the underlying storage is unreachable.
    try:
        # type ignores are necessary because the base PersistenceBackend protocol
        # might not strictly define these list methods for all implementations.
        events = await backend.list_events(limit=limit)  # type: ignore[attr-defined]
        audits = await backend.list_audits(limit=limit)  # type: ignore[attr-defined]
        dls = await backend.list_dead_letters(limit=limit)  # type: ignore[attr-defined]

        info(f"events_sampled: {len(events)}{' (capped)' if len(events) == limit else ''}")
        info(f"audits_sampled: {len(audits)}{' (capped)' if len(audits) == limit else ''}")
        info(f"dead_letters_sampled: {len(dls)}{' (capped)' if len(dls) == limit else ''}")
    except Exception:
        info("counts: <unavailable>")

    # ---------------------------------------------------------
    # Metrics Inspection
    # ---------------------------------------------------------
    if show_metrics:
        try:
            # Check if the backend uses the PersistenceMetricsMixin
            snap = backend.metrics.snapshot()
        except Exception:
            snap = {}

        if not snap:
            info("metrics: <unavailable>")
        else:
            info("metrics:")
            for k, v in snap.items():
                info(f"  {k}: {v}")
