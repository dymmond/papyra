# In-Memory Persistence Backend

The **In-Memory Persistence Backend** is the simplest persistence implementation in Papyra.
It stores all events, audits, and dead letters entirely in process memory and performs no
disk I/O.

This backend is intentionally minimal and exists primarily for **testing**, **local
development**, and **ephemeral systems** where durability is not required.

---

## When to Use the Memory Backend

The memory backend is appropriate when:

- You are writing **unit tests** or integration tests.
- You want **maximum speed** with zero I/O.
- You are experimenting locally and do not care about persistence across restarts.
- You are building short-lived actor systems (e.g. CLI tools, simulations).

It is **not** suitable for production systems that require durability or crash recovery.

---

## Key Characteristics

| Feature                    | Supported |
|---------------------------|-----------|
| Durability                | ❌ No |
| Crash recovery            | ❌ No |
| Retention policies        | ⚠️ Partial |
| Compaction                | ❌ No-op |
| Metrics                   | ✅ Yes |
| Concurrency safety        | ✅ Yes (actor-serialized) |
| Disk usage                | ❌ None |

---

## How It Works

Internally, the backend keeps three in-memory collections:

- **Events**
- **Audits**
- **Dead letters**

Each record is appended to an in-memory list. When the process exits, all data is lost.

Because actors process messages sequentially, no explicit locking is required.

---

## Basic Usage

### Using the Memory Backend Explicitly

```python
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.conf import settings

settings.persistence = InMemoryPersistence()
```

Once configured, all actors automatically persist events through the configured backend.

---

## Retention Behavior

Retention policies **can be attached**, but they only apply logically during reads.
No physical compaction or memory reclamation is performed.

Example:

```python
from papyra.persistence.backends.retention import RetentionPolicy
from papyra.persistence.backends.memory import InMemoryPersistence

backend = InMemoryPersistence(
    retention_policy=RetentionPolicy(max_records=1000)
)
```

!!! Warning "Important"
    Important: Even if older records are hidden by retention rules, they still
    occupy memory for the lifetime of the process.

---

## Metrics Support

The memory backend fully supports persistence metrics via `PersistenceMetricsMixin`.

Tracked metrics include:

- Records written
- Bytes written
- Scans
- Anomalies (always zero)
- Recoveries (always zero)
- Compactions (always zero)
- Error counters

Example:

```python
snapshot = backend.metrics.snapshot()
print(snapshot)
```

---

## Scan, Recovery, and Compaction

### Scan

```python
await backend.scan()
```

- Always returns a **clean report**
- No anomalies can exist because no disk I/O occurs

### Recovery

```python
await backend.recover(...)
```

- No-op
- Always succeeds

### Compaction

```python
await backend.compact()
```

- No-op
- Returns immediately

---

## Limitations

The memory backend deliberately does **not** support:

- Persistence across restarts
- Startup validation
- File-based inspection
- Quarantine or repair workflows

Any CLI command that relies on disk artifacts will behave as a no-op or report
that the operation is unsupported.

---

## Example: Testing with the Memory Backend

```python
import pytest
from papyra.persistence.backends.memory import InMemoryPersistence

@pytest.fixture
def persistence():
    backend = InMemoryPersistence()
    backend.metrics.reset()
    return backend
```

This pattern is commonly used in Papyra's own test suite.

---

## Summary

The In-Memory Persistence Backend is:

- Extremely fast
- Zero-configuration
- Non-durable by design

It is ideal for **tests and experimentation**, but should never be used where
data loss matters.

For production systems, prefer:

- JSON File Persistence
- Rotating File Persistence
- Redis Streams Persistence
