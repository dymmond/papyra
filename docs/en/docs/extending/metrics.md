# Extending Metrics in Papyra

This guide explains how **metrics** work in Papyra, how built-in persistence metrics are produced, and how **custom backends or external tools** can extend, export, or integrate these metrics.

The goal is to keep metrics **optional, low-overhead, and backend-agnostic**, while still allowing deep observability in production.

---

## Why Metrics Are Optional

Papyra is designed to run in environments ranging from:

- Embedded systems
- Local developer tools
- CI pipelines
- Large distributed production systems

Because of this, **metrics are never required** for correctness.

If a backend does not support metrics:

- Nothing breaks
- CLI commands degrade gracefully
- External tooling simply sees no data

This philosophy ensures Papyra remains usable everywhere.

---

## The Metrics Model

Papyra metrics are:

- **Pull-based** (snapshots)
- **Monotonic counters** and gauges
- **Local to the backend** (no global registry)

Metrics are exposed via a small, stable interface rather than a hard dependency on a specific monitoring system.

---

## Persistence Metrics Mixin

Persistence backends that support metrics typically expose them via an internal metrics object.

Conceptually:

```python
backend.metrics
```

This object is responsible for tracking counters such as:

- Records written
- Records read
- Scan operations
- Recovery operations
- Compaction runs
- Error counts

The metrics object must be **safe to ignore** if not present.

---

## Snapshot-Based Access

All metric consumers interact with metrics through a **snapshot** API.

```python
snapshot = backend.metrics.snapshot()
```

A snapshot returns a **plain dictionary**:

```python
{
    "records_written": 120394,
    "records_read": 118822,
    "scan_runs": 3,
    "recovery_runs": 1,
    "compactions": 2,
    "write_errors": 0,
}
```

### Why Snapshots?

- No shared mutable state
- Safe for async + threading
- Easy to export
- Tooling-friendly

Snapshots may be taken at any time without locking the backend.

---

## Reset Semantics

Metrics objects may optionally support resetting:

```python
backend.metrics.reset()
```

Resetting metrics is typically used for:

- Test isolation
- Benchmarking
- Manual operational inspection

Resetting metrics **must never affect persistence state**.

---

## Implementing Custom Metrics

If you are writing a **custom persistence backend**, you may implement metrics in one of two ways:

### Option 1: Minimal (No Metrics)

Do nothing.

Your backend simply does not expose a `metrics` attribute.

All CLI commands and integrations will automatically skip metrics output.

---

### Option 2: Lightweight Metrics Object

Attach a metrics object to your backend:

```python
class MyBackendMetrics:
    def __init__(self) -> None:
        self.records_written = 0
        self.records_read = 0
        self.write_errors = 0

    def snapshot(self) -> dict[str, int]:
        return {
            "records_written": self.records_written,
            "records_read": self.records_read,
            "write_errors": self.write_errors,
        }

    def reset(self) -> None:
        self.records_written = 0
        self.records_read = 0
        self.write_errors = 0
```

Attach it in your backend:

```python
class MyPersistenceBackend:
    def __init__(self) -> None:
        self.metrics = MyBackendMetrics()
```

Update counters during backend operations.

---

## Error Accounting

Metrics should track **errors, not exceptions**.

Example:

```python
try:
    await self._write_record(record)
    self.metrics.records_written += 1
except Exception:
    self.metrics.write_errors += 1
    raise
```

This allows operators to observe failure rates without parsing logs.

---

## CLI Integration

The metrics CLI commands rely entirely on:

```python
backend.metrics.snapshot()
```

If a backend does not expose metrics:

- CLI prints `metrics: <unavailable>`
- Exit code remains `0`

This behavior is intentional and should not be overridden by backends.

---

## OpenTelemetry and External Export

Papyra **does not embed OpenTelemetry**, Prometheus, or StatsD directly.

Instead, metrics are designed to be *exported by adapters*.

### Example: OpenTelemetry Export Loop

```python
from opentelemetry import metrics

meter = metrics.get_meter("papyra")

written = meter.create_counter("papyra.records_written")

snapshot = backend.metrics.snapshot()
written.add(snapshot.get("records_written", 0))
```

This approach:

- Avoids dependency coupling
- Allows custom aggregation strategies
- Keeps Papyra lightweight

---

## Testing Metrics

When testing custom backends:

- Reset metrics before each test
- Assert against snapshots
- Never rely on exact ordering of operations

Example:

```python
backend.metrics.reset()
await backend.record_event(...)

snap = backend.metrics.snapshot()
assert snap["records_written"] == 1
```

---

## Design Guarantees

Metrics in Papyra are:

- Optional
- Non-blocking
- Side-effect free
- Backend-scoped
- Safe to ignore

You should never:

- Make metrics required
- Fail persistence operations due to metrics
- Perform I/O inside metric collection

---

## Summary

Metrics extension in Papyra is intentionally simple:

- Attach a metrics object
- Update counters
- Expose snapshots
- Let tooling decide how to export

This keeps observability powerful without compromising correctness or performance.
