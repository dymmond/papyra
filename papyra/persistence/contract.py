from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PersistenceBackendCapabilities:
    """
    A data object declaring which optional persistence features a backend supports.

    This class serves as a runtime introspection tool for the system. It allows
    orchestration layers (such as startup checks, CLI tools, and diagnostics)
    and test suites to validate or adapt to the behavior of a specific backend
    implementation without needing to import or rely on concrete backend types.

    Note that core, required persistence operations (like `record_*` methods and
    `aclose`) are not represented here, as all valid backends must support them.

    Attributes:
        supports_scan (bool): True if the backend implements the `scan()` method
            for integrity checking.
        supports_recover (bool): True if the backend implements the `recover()`
            method for repairing corruption.
        supports_compact (bool): True if the backend implements the `compact()`
            method for storage optimization.
        supports_metrics (bool): True if the backend exposes a `metrics` property
            with a `snapshot()` method.
    """

    supports_scan: bool
    supports_recover: bool
    supports_compact: bool
    supports_metrics: bool


@runtime_checkable
class PersistenceBackendContract(Protocol):
    """
    The minimal interface contract that third-party persistence backends must satisfy.

    This protocol defines both mandatory and optional behaviors for storage
    implementations used by the actor system.

    REQUIRED Operations:
    --------------------
    - `record_event`, `record_audit`, `record_dead_letter`: Append-only methods
      to persist facts.
    - `aclose`: A teardown method to ensure resources are released at the end of
      the lifecycle.

    OPTIONAL Operations:
    --------------------
    - `scan`: A non-mutating method to inspect storage integrity during startup.
    - `recover`: A method to perform best-effort repair or quarantine of corrupted data.
    - `compact`: A method to physically enforce retention policies (e.g., vacuuming).

    Implementation Guarantees:
    --------------------------
    - **Stability**: `record_*` methods MUST be best-effort. Callers may treat
      failures as non-fatal logging errors. The actor runtime MUST NEVER crash
      due to persistence failures.
    - **Safety**: `scan` MUST NOT mutate storage. It must be strictly read-only.
    - **Atomicity**: `recover` and `compact` SHOULD be crash-safe and atomic
      wherever the underlying storage medium permits.
    """

    # NOTE: The type signatures here are intentionally broad (using Any) to avoid tight coupling.
    # While concrete backends will use strongly-typed models (e.g., PersistedEvent), this
    # contract must remain stable and flexible for external implementers.

    @property
    def retention(self) -> Any:
        """
        Retrieve the configured retention policy for this backend, if any.
        """
        ...

    async def record_event(self, event: Any) -> None:
        """
        Persist a domain event.
        """
        ...

    async def record_audit(self, report: Any) -> None:
        """
        Persist an audit log entry.
        """
        ...

    async def record_dead_letter(self, dead_letter: Any) -> None:
        """
        Persist a dead letter (undeliverable message).
        """
        ...

    async def aclose(self) -> None:
        """
        Close the backend connection and release resources.
        """
        ...

    async def scan(self) -> Any:
        """
        (Optional) Perform an integrity scan of the storage.
        """
        ...

    async def recover(self, config: Any | None = None) -> Any:
        """
        (Optional) Attempt to recover from detected storage anomalies.
        """
        ...

    async def compact(self) -> Any:
        """
        (Optional) Perform physical compaction or cleanup of storage.
        """
        ...


def backend_capabilities(backend: Any) -> PersistenceBackendCapabilities:
    """
    Inspect a backend instance to detect its supported capabilities at runtime.

    This utility function checks for the presence of optional methods (`scan`, `recover`,
    `compact`) and the metrics interface. It is designed to be robust, never raising exceptions,
    and does not depend on importing concrete backend classes.

    Args:
        backend (Any): The persistence backend instance to inspect.

    Returns:
        PersistenceBackendCapabilities: An immutable object describing the supported features.
    """
    try:
        # Check for optional methods by verifying if the attribute exists and is callable
        supports_scan = callable(getattr(backend, "scan", None))
        supports_recover = callable(getattr(backend, "recover", None))
        supports_compact = callable(getattr(backend, "compact", None))

        # Check for metrics support: strictly requires a 'metrics' property with a 'snapshot' method
        metrics = getattr(backend, "metrics", None)
        supports_metrics = metrics is not None and callable(getattr(metrics, "snapshot", None))
    except Exception:
        # Fail safe: assume minimal capabilities if introspection crashes (e.g., bad property access)
        return PersistenceBackendCapabilities(
            supports_scan=False,
            supports_recover=False,
            supports_compact=False,
            supports_metrics=False,
        )

    return PersistenceBackendCapabilities(
        supports_scan=supports_scan,
        supports_recover=supports_recover,
        supports_compact=supports_compact,
        supports_metrics=supports_metrics,
    )


def safe_metrics_snapshot(backend: Any) -> Mapping[str, int]:
    """
    Safely retrieve a snapshot of metrics from a backend instance.

    This function attempts to access the backend's metrics and call `snapshot()`.
    It handles missing attributes or exceptions gracefully, ensuring that monitoring
    code does not crash the application.

    Args:
        backend (Any): The persistence backend instance to query.

    Returns:
        Mapping[str, int]: A dictionary of metric names to values. Returns an empty dict
            if metrics are unavailable, malformed, or if an error occurs.
    """
    try:
        metrics = getattr(backend, "metrics", None)
        if metrics is None:
            return {}

        snap = metrics.snapshot()
        # Verify the result is actually a dictionary before returning
        return snap if isinstance(snap, dict) else {}
    except Exception:
        return {}
