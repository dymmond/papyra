from __future__ import annotations

from pathlib import Path
from typing import Annotated

from sayer import Option, error, group, info

from papyra.cli.persistence.app import _get_persistence
from papyra.persistence.models import (
    PersistenceRecoveryConfig,
    PersistenceRecoveryMode,
)
from papyra.persistence.startup import PersistenceStartupMode

doctor = group(
    name="doctor",
    help="Run system pre-flight checks (persistence scan/recovery) without starting actors.",
)


@doctor.command()
async def run(
    path: Annotated[Path | None, Option(None, help="Persistence file path")],
    mode: Annotated[
        str,
        Option(help="Doctor behavior: ignore, fail_on_anomaly, recover"),
    ] = "fail_on_anomaly",
    recovery_mode: Annotated[
        str | None,
        Option(help="Recovery mode used when mode=recover (repair/quarantine)", required=False),
    ] = None,
    quarantine_dir: Annotated[
        Path | None,
        Option(None, help="Directory for quarantined files when recovery-mode=quarantine"),
    ] = None,
) -> None:
    """
    Execute the 'Doctor' utility to diagnose and repair persistence health issues.

    The Doctor command serves as a standalone pre-flight check tool. It operates mostly
    similarly to the internal startup checks performed by the ActorSystem but provides
    better visibility, explicit control via CLI flags, and human-readable output.

    Workflow:
    1.  **Scan**: The configured persistence backend is scanned for structural anomalies
        (e.g., truncated lines, corrupted JSON, orphaned files).
    2.  **Diagnosis**:
        - If the scan is clean, the tool reports health and exits successfully.
        - If anomalies are found, the behavior depends on the `mode` argument.
    3.  **Reaction (based on `mode`)**:
        - `IGNORE`: Reports the anomalies to stderr but exits with code 0.
        - `FAIL_ON_ANOMALY`: Reports anomalies and exits immediately with code 1.
        - `RECOVER`: Initiates the repair process using the specified `recovery_mode`.
    4.  **Verification**:
        - If recovery was attempted, a post-repair scan ensures the system is truly clean.
        - If anomalies persist after repair, the tool exits with code 2.

    Args:
        path (Path | None): Overrides the default persistence path. Useful for checking
            backups or specific log files. Defaults to None (uses system settings).
        mode (PersistenceStartupMode): The strategy to apply when anomalies are detected.
            Defaults to FAIL_ON_ANOMALY.
        recovery_mode (PersistenceRecoveryMode | None): The specific repair strategy
            (REPAIR or QUARANTINE) to use if `mode` is set to RECOVER.
            Defaults to None (backend default, usually REPAIR).
        quarantine_dir (Path | None): The directory to move corrupted files into if
            `recovery_mode` is set to QUARANTINE. Required if QUARANTINE is used.

    Raises:
        SystemExit:
            - Code 1: Anomalies found in FAIL_ON_ANOMALY mode.
            - Code 2: Recovery failed to fix all anomalies.
            - String: Invalid configuration (e.g., missing quarantine directory).
    """
    # Reuse the same resolver logic as the main application to ensure consistent behavior
    backend = _get_persistence(path)

    try:
        mode_enum = PersistenceStartupMode(mode.lower())
    except ValueError:
        raise SystemExit(f"Invalid mode: {mode}") from None

    # Perform the initial health scan
    scan = await backend.scan()
    if scan is None:
        info("Persistence scan not supported by backend.")
        return

    if not scan.has_anomalies:
        info("Persistence is healthy")
        return

    # ---------------------------------------------------------
    # Anomalies Detected
    # ---------------------------------------------------------

    # Case 1: IGNORE mode - Log issues but do not fail
    if mode_enum is PersistenceStartupMode.IGNORE:
        error(f"Persistence anomalies detected (ignored): {scan.anomalies}")
        return

    # Case 2: FAIL_ON_ANOMALY mode - strict failure
    if mode_enum is PersistenceStartupMode.FAIL_ON_ANOMALY:
        error(f"Persistence anomalies detected: {scan.anomalies}")
        raise SystemExit(1)

    # Case 3: RECOVER mode - Attempt to fix
    rm_raw = recovery_mode or PersistenceRecoveryMode.REPAIR.value
    try:
        rm_enum = PersistenceRecoveryMode(rm_raw.lower())
    except ValueError:
        raise SystemExit(f"Invalid recovery mode: {rm_raw}") from None

    if rm_enum is PersistenceRecoveryMode.QUARANTINE and quarantine_dir is None:
        raise SystemExit("quarantine recovery requires --quarantine-dir")

    cfg = PersistenceRecoveryConfig(
        mode=rm_enum,
        quarantine_dir=str(quarantine_dir) if quarantine_dir else None,
    )

    # Execute the backend-specific recovery logic
    await backend.recover(cfg)

    # Post-Recovery Guarantee: Re-scan to ensure the fix actually worked
    post = await backend.scan()
    if post is not None and post.has_anomalies:
        error("Recovery attempted but anomalies still exist")
        raise SystemExit(2)

    info("Recovery successful")
