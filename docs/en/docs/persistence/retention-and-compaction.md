# Retention & Compaction

Retention and compaction are the two mechanisms that prevent persistence backends
from growing without bound. While they are related, they solve **different problems**
and operate at **different layers** of the system.

Understanding this distinction is critical to using Papyra safely in production.

---

## Mental Model

Think in **three layers**:

1. **Logical history** – what records are *visible* to the system
2. **Physical storage** – what bytes actually exist on disk or in a backend
3. **Maintenance actions** – explicit operations that rewrite or trim storage

| Concern        | Solved by        | When it runs            |
|----------------|------------------|-------------------------|
| Limit history  | Retention        | Read time / scan time   |
| Reclaim space  | Compaction       | Explicit maintenance    |
| Fix corruption | Recovery         | Explicit / startup      |

Retention does **not** reclaim disk space.
Compaction does.

---

## Retention

### What Retention Is

Retention defines **rules for logical data visibility**.

When retention is active, older records may still exist physically, but they are:

- Ignored during reads
- Excluded from scans
- Considered obsolete during compaction

Retention is **declarative**: you describe *what should remain visible*, not *how to delete it*.

---

### RetentionPolicy

Retention is configured using `RetentionPolicy`:

```python
from papyra.persistence.backends.retention import RetentionPolicy

policy = RetentionPolicy(
    max_records=100_000,
    max_age_seconds=7 * 24 * 3600,
    max_total_bytes=None,
)
```

| Field             | Meaning |
|------------------|--------|
| `max_records`    | Keep only the most recent N records |
| `max_age_seconds`| Drop records older than this age |
| `max_total_bytes`| Enforce a soft logical size limit |

All fields are **optional**.
Unset fields mean “no limit”.

!!! Tip
    `RetentionPolicy` is immutable (`frozen=True`) by design to guarantee consistency.

---

### How Retention Is Applied

Retention is enforced at **read and scan time**.

Examples:

- `list_events()` returns only retained records
- `scan()` ignores records that fall outside retention
- Metrics reflect retained visibility, not raw storage

This guarantees **stable behavior** even if compaction has not yet occurred.

---

### Backend-Specific Behavior

| Backend | Retention Enforcement |
|-------|-----------------------|
| Memory | Immediate, in-memory |
| JSON  | Applied during reads |
| Rotating files | Applied per segment |
| Redis Streams | Applied via `XTRIM` + read filters |

Some backends may support **physical trimming** during compaction (see below).

---

## Compaction

### What Compaction Is

Compaction is a **physical rewrite operation**.

It:

- Removes obsolete records
- Drops corrupted entries (if already quarantined)
- Shrinks disk usage
- Improves read performance

Compaction is **never automatic**.

You must call it explicitly.

---

### Why Compaction Is Separate

Automatic deletion is dangerous:

- Partial writes
- Power loss
- Concurrent readers
- Distributed backends

By separating retention (logical) from compaction (physical), Papyra guarantees:

- Safe reads
- Deterministic recovery
- No surprise data loss

---

### Triggering Compaction

Via API:

```python
await backend.compact()
```

Via CLI:

```bash
papyra persistence compact
```

Some backends return stats:

```shell
Compaction completed
  backend: memory
  before_records: 0
  after_records: 0
  before_bytes: None
  after_bytes: None
```

---

### Backend Support Matrix

| Backend | Compaction Behavior |
|-------|---------------------|
| Memory | No-op |
| JSON  | Rewrite file |
| Rotating files | Rewrite / drop segments |
| Redis Streams | `XTRIM` |

If a backend does not support compaction, the call safely no-ops.

---

## Retention vs Compaction (Critical Distinction)

**Retention**

- Logical
- Cheap
- Always-on
- Safe during runtime

**Compaction**

- Physical
- Potentially expensive
- Explicit
- Maintenance operation

Never rely on retention alone to manage disk usage.

---

## Operational Guidance

### Recommended Strategy

1. **Always configure retention**
2. **Schedule compaction**
    - Daily for file backends
    - Periodic for Redis
3. **Run scans before compaction**
4. **Monitor metrics**

---

### Production Example

```shell
Retention:
  max_records = 5M
  max_age = 30 days

Compaction:
  nightly cron job
```

This ensures:

- Stable memory usage
- Predictable disk growth
- Safe crash recovery

---

## Failure Scenarios

| Scenario | Outcome |
|--------|--------|
| Crash before compaction | No data loss |
| Crash during compaction | Atomic replace protects integrity |
| Corruption detected | Recovery required before compaction |
| Retention misconfigured | Logical history affected, storage intact |

---

## Metrics Interaction

Retention and compaction feed into metrics:

- `records_written`
- `compactions`
- `bytes_written`
- `anomalies_detected`

Metrics always reflect **post-retention visibility**.

---

## Summary

- Retention controls **what is visible**
- Compaction controls **what exists**
- They are intentionally decoupled
- This design prevents silent data loss

If you understand this section, you understand Papyra persistence.
