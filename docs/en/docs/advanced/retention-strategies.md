# Advanced retention strategies

Retention is deceptively hard.

Most systems treat “retention” as “delete old data.” In Papyra, retention is intentionally designed as
**a read-time filter first**, with an explicit, opt-in **physical compaction** step for storage that can shrink.

This page explains how to build safe, production-grade retention strategies that match how Papyra
persistence actually behaves.

---

## What retention means in Papyra

Papyra persistence stores *system facts* (events, audits, dead letters) as an append-only log.
Retention defines what should be considered *in scope* when reading these facts.

### Logical retention

Logical retention is enforced **when you read**.

- `list_events(...)`, `list_audits(...)`, and `list_dead_letters(...)` return a view of the log.
- If a `RetentionPolicy` is configured, older/out-of-scope records are filtered out.
- The underlying storage **may still contain** the dropped records.

This default is deliberate:

- It is safe (no automatic destructive behavior).
- It is predictable (reads always apply the same policy).
- It keeps the write path fast.

### Physical compaction

Physical compaction is the explicit operation that makes retention *real* on disk / in storage.

- On file backends, compaction rewrites files and atomically replaces the original.
- On Redis Streams, compaction can use `XTRIM` when a record-count limit exists.
- On in-memory backends, compaction is a no-op.

You must call compaction explicitly:

- `ActorSystem.compact()`
- CLI: `papyra persistence compact`

> Papyra will **never** run compaction automatically at startup.

---

## RetentionPolicy is immutable

`RetentionPolicy` is a frozen dataclass.

That means you **cannot** do this:

```py
rp = RetentionPolicy()
# ❌ raises FrozenInstanceError
rp.max_records = 1000
```

Instead, you create a new policy:

```py
rp = RetentionPolicy(max_records=1000)
```

This matters in production because:

- your runtime configuration is stable and hashable
- you avoid accidental mutation that changes retention semantics mid-flight

---

## The three retention dimensions

Papyra retention can be expressed in three independent dimensions:

- **Count-based**: `max_records`
- **Time-based**: `max_age_seconds`
- **Size-based**: `max_total_bytes`

You can use any single constraint or combine them.

### Count-based retention

Count-based retention is the most predictable and the most commonly used.

Use it when you want:

- bounded storage growth
- stable read performance
- an easy mental model (“keep the last N records”)

Example:

```py
from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.backends.retention import RetentionPolicy

persistence = JsonFilePersistence(
    path="./events.ndjson",
    retention_policy=RetentionPolicy(max_records=50_000),
)
```

Operational note:

- On file backends, `compact()` is what reclaims disk.
- On Redis Streams, compaction can leverage `XTRIM MAXLEN`.

### Time-based retention

Time-based retention is useful when your operational questions are time-scoped:

- "show me the last 7 days"
- "keep audits for 30 days"

Example:

```py
from papyra.persistence.backends.rotating import RotatingFilePersistence
from papyra.persistence.backends.retention import RetentionPolicy

# Keep ~7 days of data
persistence = RotatingFilePersistence(
    path="./rot.log",
    max_bytes=10_000_000,
    max_files=10,
    retention_policy=RetentionPolicy(max_age_seconds=7 * 24 * 60 * 60),
)
```

Caveat:

- Time-based retention relies on **timestamps in the stored records**.
- If you ingest historical data (older timestamps), those records may be dropped immediately at read time.

### Size-based retention

Size-based retention is the hardest to get perfectly right, because the “true” size depends on backend representation.

Use it when you have:

- strict disk budgets
- very high throughput systems
- extremely large payloads

In Papyra, size-based retention is best treated as:

- a safety net
- a secondary constraint

You should still cap by **count** or **age** to keep the system predictable.

---

## Strategy patterns

This section gives strategies you can implement today, with tradeoffs.

### Strategy 1: Safety-first (read retention only)

**Recommended for early production**.

- Configure retention policy.
- Do not schedule compaction initially.
- Use `doctor` and startup checks to ensure integrity.

Pros:

- zero risk of accidental data loss
- simplest operations

Cons:

- disk/stream size may keep growing until you compact

### Strategy 2: Count retention + periodic compaction

**Recommended for most production deployments**.

- `max_records` in policy
- scheduled compaction (daily / weekly depending on volume)

Why it works:

- predictable volume
- predictable read cost
- bounded storage

Example operational schedule:

- small / medium systems: weekly compaction
- high throughput: daily compaction

### Strategy 3: Hybrid (age + count)

Use this when you want both:

- a time window (e.g. last 30 days)
- a hard upper bound if load spikes (e.g. 2 million records)

```py
RetentionPolicy(
    max_age_seconds=30 * 24 * 60 * 60,
    max_records=2_000_000,
)
```

This is often the best “production default.”

### Strategy 4: Cold storage + short hot retention

If you want long-term history without keeping it in Papyra's primary persistence:

- keep a short retention window in Papyra (hot data)
- ship the stream elsewhere (cold data)

Typical pattern:

- Redis Streams persistence
- external consumer group reads events
- consumer exports into your analytics / data lake

Papyra supports this by exposing consumer group primitives on the Redis backend.

---

## Backend-specific guidance

Retention policy is universal, but compaction is backend-specific.

### JSON file backend

- Writes: append-only NDJSON
- Logical retention: applied on reads
- Physical compaction: rewrites the file and uses atomic replace

Recommended:

- use count-based retention
- compact periodically
- run `scan` at startup in strict environments

### Rotating file backend

- Writes: append-only with rotation
- Logical retention: applied on reads across rotated files
- Physical compaction: can rewrite rotation set to remove expired records

Recommended:

- pick rotation parameters (`max_bytes`, `max_files`) for worst-case throughput
- use retention + compaction only if disk pressure matters

### Redis Streams backend

- Writes: `XADD` into per-kind streams
- Logical retention: applied on reads
- Physical compaction: can leverage `XTRIM MAXLEN` when `max_records` is configured

Recommended:

- `max_records` as the primary limiter
- consider approximate trimming for performance (`~`)

---

## Startup guarantees vs retention

Startup scanning/recovery is about **integrity**, not retention.

- `scan()` detects structural anomalies
- `recover()` repairs or quarantines
- startup modes decide whether to ignore, fail, or recover

Retention does not fix corruption.

If you want a robust production posture:

- run `doctor` in CI / deployment pipelines
- use `persistence startup-check` for pre-flight checks
- configure ActorSystem startup mode to FAIL_ON_ANOMALY or RECOVER

---

## Operational playbooks

### When should you compact?

Compact when:

- disk usage keeps growing and must be reclaimed
- you have predictable low-traffic windows
- you want to physically enforce retention for compliance

Don't compact when:

- you don't need disk reclamation yet
- your storage backend already enforces a size bound (e.g., Redis trimming)
- you can't tolerate any rewrite pressure during peak time

### How to verify retention is doing what you think

1. Confirm policy in your runtime configuration.
2. Use CLI:

```bash
papyra persistence inspect
```

3. Observe read counts (sampled): events / audits / dead letters.
4. If using metrics:

```bash
papyra metrics persistence
```

5. Run compaction explicitly and compare before/after.

### How to debug “missing data”

Common causes:

- retention policy filtering records at read time
- timestamps older than your `max_age_seconds`
- `max_records` too small for your query horizon

Checklist:

- print retention settings (`persistence inspect`)
- temporarily run with `RetentionPolicy()` (no limits)
- re-run the same read and compare

---

## Real-world examples

### Example: local development

Goal: keep things simple.

- Use `InMemoryPersistence()` (default)
- No retention needed

### Example: a single-node production service

Goal: stable disk usage and readable logs.

- `JsonFilePersistence`
- `RetentionPolicy(max_records=200_000, max_age_seconds=14 days)`
- schedule `compact()` weekly

### Example: high throughput service with external analytics

Goal: durable write path + external consumption.

- `RedisStreamsPersistence`
- `RetentionPolicy(max_records=5_000_000)`
- consumer group reads `events` and ships them to analytics
- periodic `XTRIM` via `compact()`

---

## Summary

- Retention is **logical** by default.
- Compaction is **explicit** and makes retention physical.
- Prefer **count-based retention** for predictability.
- Combine **age + count** for a strong production default.
- Use Redis consumer groups when you need external tooling.
