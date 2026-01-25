# Release Notes

## 0.1.1

### Fixed

- When using the settings it was causing a conflict with the types and not casting properly to the right type due
to the `from future import __annotations__`.

## 0.1.0

### Added

- Core **async actor system** with strict message isolation and single-threaded actor execution
- `ActorSystem` lifecycle management (startup, shutdown, supervision)
- Base `Actor` API with lifecycle hooks:
  - `on_start`
  - `receive`
  - `on_stop`
  - `on_child_failure`
- Supervision model with restart, stop, escalate, and ignore strategies
- Built-in **persistence subsystem** with pluggable backends:
  - In-memory backend
  - JSON file backend
  - Rotating file backend
  - Redis Streams backend (including consumer groups)
- Retention policies based on:
  - Maximum record count
  - Maximum age
  - Maximum storage size
- Compaction mechanisms to reclaim storage safely
- Persistence health scanning and anomaly detection
- Recovery strategies:
  - In-place repair
  - Quarantine-based recovery
- First-class **metrics system** with:
  - Write/read counters
  - Error tracking
  - Recovery and compaction statistics
- CLI tooling for operational control:
  - Persistence scan, recovery, compaction, and inspection
  - Doctor command for pre-flight health checks
  - Metrics inspection and reset
- ASGI integrations with **Lilya** and **Ravyn**:
  - Automatic lifecycle hooks
  - Health endpoints
  - Metrics endpoints (JSON-compatible)
- OpenTelemetry-compatible metrics exposure hooks

### Notes

- This is the **initial public release** of Papyra.
- APIs are considered **stable enough for early adopters**, but minor breaking changes may occur before `1.0.0`.
- The project prioritizes correctness, observability, and operational safety over premature optimization.
