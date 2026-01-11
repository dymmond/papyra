# Backend contract

This page defines the **extension contract** for persistence backends.

If you are implementing a custom backend (or maintaining a third‑party backend), this is the document to treat as the source of truth.

Papyra persistence is **observability persistence**: it stores *system facts* (events, audits, dead letters)
in an append-only form so operators and tools can inspect what happened.

## What a persistence backend is responsible for

A persistence backend:

- records *facts* (events, audits, dead letters)
- provides read access to those facts
- supports optional operational maintenance (scan, recover, compact)
- may expose optional metrics

A persistence backend is **not**:

- actor state persistence
- mailbox persistence
- a database abstraction for application business data

## Primary interface

All backends implement `PersistenceBackend`.

### Required write methods

Backends must implement:

- `record_event(event)`
- `record_audit(audit)`
- `record_dead_letter(dead_letter)`

#### Write semantics

Writes must follow these rules:

1. **Best-effort / non-fatal**
    - A persistence write must not crash the actor runtime.
    - The ActorSystem already treats persistence writes as best-effort.

2. **Append-only**
    - Writes must never mutate existing records.
    - If the storage technology is mutable (SQL, KV store), simulate append-only by inserting immutable rows/entries.

3. **Fast**
    - Writes are on the hot path.
    - Prefer amortized O(1) appends.

4. **Concurrency-safe**
    - Multiple actors can write concurrently.
    - If the storage client is not concurrency-safe, guard it with a lock.

5. **Ordering**
    - Within a single process, writes should preserve logical ordering **as much as the backend allows**.
    - Strong total ordering is not required, but avoid unnecessary reordering.

6. **No partial records**
    - If an operation fails mid-write, it must not leave a partially serialized record visible to reads.
    - For file-based backends: write full lines and flush; truncate/repair on startup as needed.

### Required read methods

Backends are expected to implement:

- `list_events(limit: int | None = None, since: float | None = None)`
- `list_audits(limit: int | None = None, since: float | None = None)`
- `list_dead_letters(limit: int | None = None, since: float | None = None)`

If a backend cannot support reads (rare), it must still behave safely, but most Papyra tooling assumes these exist.

#### Read semantics

1. **Return immutable snapshots**
    - Return tuples (or other immutable containers) to prevent accidental mutation by callers.

2. **Retention is applied on reads**
    - If the backend supports retention, reads must apply the configured `RetentionPolicy` the same way file-based backends do.
    - “Retention on reads” is the default retention model in Papyra.

3. **Filtering**
    - `since` filters out records older than the timestamp.
    - `limit` returns the most recent N records.

4. **Corruption tolerance**
    - If the underlying store can contain malformed entries (NDJSON line truncation, Redis payload corruption), reads must skip bad entries rather than failing the whole operation.

## Retention contract

Retention is configured via `RetentionPolicy`.

### Policy shape

`RetentionPolicy` is a frozen dataclass. Do not mutate it.

If you need a policy with different values, construct a new one:

```python
from papyra.persistence.backends.retention import RetentionPolicy

rp = RetentionPolicy(max_records=10_000)
```

### How retention is applied

Retention in Papyra is **logical by default**:

- Writes keep everything.
- Reads apply retention and only return the retained subset.

This gives predictable behavior and avoids unexpected deletion.

### Physical retention (compaction)

Some backends can enforce retention physically (e.g., rewriting files, trimming Redis Streams, VACUUM in SQL).

That is done via `compact()`.

## Compaction contract (`compact()`)

Compaction is the **explicit, destructive** operation that makes retention physical.

Rules:

- **MUST** be **explicit**. Never run automatically in the actor loop.
- **SHOULD** be crash-safe and atomic (for file stores: write-to-temp + atomic replace).
- **MUST** apply the same retention semantics as reads.
- **MUST** not crash the system. Callers treat this as best-effort.

Return value:

- Backends may return a `CompactionReport` or any backend-specific structure.
- Returning `None` is allowed.

## Startup health scan (`scan()`)

`scan()` is used for **startup guarantees** and tooling (CLI / doctor).

Rules:

- **MUST NOT** mutate storage.
- **MUST** be safe to call before any actors are started.
- **SHOULD** be fast and bounded.

Return value:

- `PersistenceScanReport` if supported.
- `None` if not supported.

### What should be detected

Examples of anomalies:

- truncated NDJSON lines
- corrupted JSON payloads
- orphaned rotated files
- unreadable files / partial writes
- corrupted Redis payload field(s)

Backends must encode issues using `PersistenceAnomaly` + `PersistenceAnomalyType`.

## Recovery (`recover()`)

Recovery is a controlled repair step, typically invoked at startup when configured.

Rules:

- MAY mutate storage.
- Must obey `PersistenceRecoveryConfig.mode`:
    - `IGNORE`: no mutation
    - `REPAIR`: repair in place
    - `QUARANTINE`: move bad data aside then repair

Return value:

- `PersistenceRecoveryReport` when work was performed (or when scan was requested).
- `None` is allowed when recovery is unsupported.

### Recovery safety

Recovery must be:

- bounded (avoid scanning huge datasets unboundedly)
- deterministic in behavior
- atomic when possible

For file backends:

- stop at the first truncated line and drop the rest
- discard corrupted JSON lines
- rewrite to a new file then atomically replace

For Redis streams:

- detect corrupted entries by payload validation
- in REPAIR mode: delete bad entries
- in QUARANTINE mode: copy bad entries to quarantine streams then delete

## Metrics support (optional)

Metrics are an optional enhancement.

### How metrics are provided

Backends typically inherit `PersistenceMetricsMixin` through `PersistenceBackend`.

The mixin exposes:

- `backend.metrics` (a `PersistenceMetrics` instance)
- async helpers like:
    - `_metrics_on_write_ok(...)`
    - `_metrics_on_write_error()`
    - `_metrics_on_scan_start()`
    - `_metrics_on_scan_anomalies(count)`
    - `_metrics_on_recover_start()`
    - `_metrics_on_recover_error()`
    - `_metrics_on_compact_start()`
    - `_metrics_on_compact_error()`

### Metrics contract

- Metrics must never raise.
- Metrics updates must be thread-safe.
- Metrics are internal counters; exporting them to Prometheus / OpenTelemetry is done outside the backend (see the Metrics docs).

## External consumption extension (Redis consumer groups)

Some backends provide additional capabilities for external tools.

For Redis Streams, this includes consumer-group operations used by shippers and analytics:

- `consume(kind=..., cfg=..., read_id=...)`
- `ack(kind=..., group=..., ids=[...])`
- `pending_summary(kind=..., group=...)`
- `claim(kind=..., group=..., consumer=..., min_idle_ms=..., entry_ids=[...])`

These methods are intentionally **not** part of the minimal `PersistenceBackend` interface.

If you build tooling around these features, feature-detect them (e.g., `hasattr(backend, "consume")`) and degrade gracefully.

## Error handling rules

Backends must keep the actor runtime stable.

### Required behavior

- Never let a backend exception crash the ActorSystem.
- Catch, count (metrics), and either:
    - swallow (if called by the actor loop), or
    - raise for explicit CLI/maintenance operations where the user expects failure.

### Recommended pattern

```python
async def record_event(self, event):
    try:
        ...
        await self._metrics_on_write_ok(records=1, bytes_written=nbytes)
    except Exception:
        await self._metrics_on_write_error()
        # If the caller is a CLI command, you might re-raise.
        # If the caller is the actor system, swallowing is acceptable.
        raise
```

## Testing contract

A backend implementation should come with:

- unit tests for:
    - record_* writes
    - list_* reads
    - retention application on reads
    - scan detection
    - recover in REPAIR and QUARANTINE (if supported)
    - compact behavior (if supported)
    - metrics counters (writes/scans/anomalies/recoveries/compactions)

- integration tests (when applicable):
    - Redis availability checks + skip if not available
    - consumer group ack/claim flows (for Redis)

### Minimal acceptance checklist

A backend is considered “contract compliant” if:

- it records facts without breaking runtime stability
- it can read facts back and apply retention
- scan + recover behave correctly (or return `None` if explicitly unsupported)
- compaction is explicit and safe (or a documented no-op)
- metrics do not break anything and reflect operations reasonably

## Reference implementations

Use these as guides:

- **InMemoryPersistence**: reference semantics, easiest to read
- **JsonFilePersistence**: NDJSON corruption tolerance + atomic recovery + compaction
- **RotatingFilePersistence**: rotation + orphan detection + recovery
- **RedisStreamsPersistence**: production-grade log with consumer-group support

If you are implementing a new backend (SQLite/Postgres/etc.), start by mirroring these patterns.
