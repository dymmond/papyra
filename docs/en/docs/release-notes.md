# Release Notes

## 0.2.0

### Added

- Live actor registry controls on `ActorSystem`, including `refs()`, `refs_by_type()`, `broadcast()`, and `stop_all()`.
- `system.control_panel()` for a printable snapshot of actor ids, addresses, names, actor classes, lifecycle state, and hierarchy.
- `ActorRef.is_alive()` for lightweight liveness checks.
- Async actor proxies via `ref.proxy()`, allowing method-style calls such as `await proxy.reserve(...)` while preserving actor mailbox isolation.
- Fire-and-forget proxy method calls with `await proxy.method.defer(...)`.
- Direct proxy messages (`ProxyCall`, `ProxyGetAttr`, `ProxySetAttr`) for integrations that need lower-level control.
- Real-world documentation for actor registries, control-panel usage, and actor proxies.

### Fixed

- Persisted lifecycle event and dead-letter records now store stable actor address strings instead of leaking runtime-shaped address values.
- Actor parent references now expose their address consistently through `context.parent.address`.
- Watchers now receive one termination notification per stopped actor.
- Startup persistence hooks are awaited correctly before actors are allowed to run.
- Actor mailbox and internal event streams now close cleanly during shutdown and failed startup.
- `ActorAddress.parse()` accepts the documented `system://actor_id` form while preserving the existing `system:actor_id` form.
- Added the correctly spelled `persistence_recovery` property while keeping `persistance_recovery` as a compatibility alias.

## 0.1.1

### Fixed

- When using the settings it was causing a conflict with the types and not casting properly to the right type due
to the `from future import __annotations__`.
- Settings inheritance now preserves typed fields from parent classes when type hint resolution falls back,
allowing child settings classes to override inherited values without re-annotating fields.

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
