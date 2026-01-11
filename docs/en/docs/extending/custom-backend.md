# Custom persistence backends

Papyra ships with multiple persistence backends (memory, JSON NDJSON, rotating files, Redis Streams). Those cover most needs, but sometimes you want to:

- store facts in a database you already operate (Postgres, ClickHouse, Elasticsearch)
- ship events/audits/dead letters to an internal pipeline
- apply organization-specific retention rules
- add stronger operational controls (per-tenant isolation, encryption-at-rest, dedicated compaction)

This page explains how to implement a **custom** persistence backend that is safe, predictable, and compatible with Papyra's startup guarantees.

## What a persistence backend is

A `PersistenceBackend` stores **observable facts** about the actor system:

- **events** (actor started, crashed, stopped, restarted)
- **audits** (system snapshots)
- **dead letters** (undeliverable messages)

It **does not** store mailbox contents or actor internal state.

The system treats persistence as best-effort for recording facts during runtime, but it can enforce strictness at **startup** (scan/recover/fail) depending on configuration.

## Design goals and non-goals

### Goals

- **Append-only semantics** for writes (facts are never updated in place)
- **Non-intrusive** behavior (backend errors must not crash the actor system)
- **Crash-safe maintenance** (compaction/recovery are atomic/best-effort)
- **Deterministic startup guarantees** (scan → optional recover → post-scan)
- **Metrics-ready** (optional metrics are available for observability)

### Non-goals

- Event-sourcing or application state persistence
- Distributed consensus or cross-system mailbox replication

## Minimal contract

A backend must implement:

- `record_event(...)`
- `record_audit(...)`
- `record_dead_letter(...)`
- `aclose()`

Optionally, it may implement:

- `list_events(...)`, `list_audits(...)`, `list_dead_letters(...)` (used by CLI inspection)
- `scan()` (startup health check)
- `recover(config)` (startup repair/quarantine)
- `compact()` (physical retention / disk reclaim)

Backends **should** implement `scan()` and `recover()` if they write to a medium that can be corrupted (files, databases, external services).

## Your first backend: a minimal skeleton

This example shows a simple in-process backend that writes JSON lines to a custom sink. It demonstrates:

- append-only writes
- safe error handling
- metrics wiring via the built-in mixin

```python
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import anyio
import anyio.abc

from papyra.persistence.base import PersistenceBackend
from papyra.persistence.models import PersistedAudit, PersistedDeadLetter, PersistedEvent


class MySink:
    """Replace this with your own storage (db client, http client, etc.)."""

    async def append(self, line: str) -> None:
        ...


class MyCustomBackend(PersistenceBackend):
    def __init__(self, sink: MySink) -> None:
        super().__init__()
        self._sink = sink
        self._lock: anyio.abc.Lock = anyio.Lock()
        self._closed = False

    async def record_event(self, event: PersistedEvent) -> None:  # type: ignore
        try:
            async with self._lock:
                if self._closed:
                    return
                payload = {"kind": "event", **asdict(event)}
                line = json.dumps(payload, ensure_ascii=False) + "\n"
                await self._sink.append(line)

            await self._metrics_on_write_ok(records=1, bytes_written=len(line.encode("utf-8")))
        except Exception:
            await self._metrics_on_write_error()
            # IMPORTANT: do not raise in production backends unless you are sure
            # the caller can tolerate it. Papyra itself suppresses most persistence
            # errors when called from the ActorSystem.
            raise

    async def record_audit(self, audit: PersistedAudit) -> None:  # type: ignore
        try:
            async with self._lock:
                if self._closed:
                    return
                payload = {"kind": "audit", **asdict(audit)}
                line = json.dumps(payload, ensure_ascii=False) + "\n"
                await self._sink.append(line)

            await self._metrics_on_write_ok(records=1, bytes_written=len(line.encode("utf-8")))
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def record_dead_letter(self, dead_letter: PersistedDeadLetter) -> None:  # type: ignore
        try:
            async with self._lock:
                if self._closed:
                    return
                payload = {"kind": "dead_letter", **asdict(dead_letter)}
                line = json.dumps(payload, ensure_ascii=False) + "\n"
                await self._sink.append(line)

            await self._metrics_on_write_ok(records=1, bytes_written=len(line.encode("utf-8")))
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def aclose(self) -> None:
        async with self._lock:
            self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed
```

### Notes on the skeleton

- The backend inherits from `PersistenceBackend`, which already includes the metrics mixin.
- We use an async lock to make writes deterministic and to coordinate shutdown.
- We increment metrics **after** successful write.

## Implementing reads (optional but recommended)

If you want your backend to be usable with the CLI inspection commands (`inspect events`, `inspect audits`, `inspect dead-letters`), implement:

- `list_events(limit=None, since=None)`
- `list_audits(limit=None, since=None)`
- `list_dead_letters(limit=None, since=None)`

Guidelines:

- Return tuples (immutable snapshots).
- Apply retention filtering consistently.
- Treat bad rows as non-fatal and skip them.

## Retention and compaction

### Retention is logical by default

Most Papyra backends apply retention **at read time** (logical retention). That means:

- the stored data can grow over time
- reads filter to only the retained subset

### Compaction makes retention physical

If your backend stores data on disk or long-lived storage, implement `compact()` to rewrite/trim storage such that old records are physically removed.

Rules:

- Compaction must be **explicit** (never automatic).
- Use crash-safe semantics (e.g. write-to-temp + atomic replace, or database transaction).
- Update metrics via `_metrics_on_compact_start()` and `_metrics_on_compact_error()`.

Return value:

- You may return a `CompactionReport` or a dict with before/after counts/bytes.

## Startup guarantees: scan and recover

Startup protection in Papyra follows a pattern:

1. `scan()`
2. if anomalies → depending on configured mode:
     - ignore
     - fail
     - recover
3. if recovered → `scan()` again and fail if anomalies still remain

### `scan()`

- Must **not** mutate storage.
- Must detect structural issues that would break reads.
- Should return `PersistenceScanReport(backend=..., anomalies=(...))`.

Update metrics:

- call `_metrics_on_scan_start()` at the beginning
- if anomalies found, call `_metrics_on_scan_anomalies(count)`
- on exceptions, call `_metrics_on_scan_error()`

### `recover(config)`

- May mutate storage depending on mode.
- Must be safe to run before the actor system starts.

Recovery modes:

- `IGNORE` → do nothing
- `REPAIR` → fix/delete corrupted items in place
- `QUARANTINE` → move aside corrupted items, then repair

Update metrics:

- call `_metrics_on_recover_start()` at the beginning
- on exceptions, call `_metrics_on_recover_error()`

Return a `PersistenceRecoveryReport` when possible.

## Metrics integration

All persistence backends inherit metrics support via `PersistenceBackend`.

You typically only need to call the helper hooks:

- successful write: `_metrics_on_write_ok(records=..., bytes_written=...)`
- write error: `_metrics_on_write_error()`
- scan start/error/anomalies: `_metrics_on_scan_start()`, `_metrics_on_scan_error()`, `_metrics_on_scan_anomalies(n)`
- recover start/error: `_metrics_on_recover_start()`, `_metrics_on_recover_error()`
- compaction start/error: `_metrics_on_compact_start()`, `_metrics_on_compact_error()`

The CLI can display metrics snapshots if your backend exposes them (it will for any `PersistenceBackend` implementation).

## Error handling rules

### Recording methods (`record_*`)

- Should be best-effort.
- Papyra suppresses most persistence errors when called from the system.
- Still, your backend should avoid raising unless you want callers (tools/tests) to see the failure.

### Maintenance methods (`scan`, `recover`, `compact`)

- These can raise when invoked explicitly via CLI or tooling.
- They should still be predictable and leave the system in a consistent state.

## Testing your backend

Minimum recommended tests:

- **writes**: events/audits/dead letters are persisted
- **reads**: list methods return expected values; limit/since filters work
- **retention**: applied consistently on reads; compaction reduces physical storage (if implemented)
- **scan**: detects corrupted/truncated items
- **recover**:
    - `REPAIR` removes corruption
    - `QUARANTINE` preserves bad data elsewhere
    - post-scan is clean
- **metrics**: counters increase for writes/scans/recoveries/compactions and error counters increment on failures

## Common pitfalls

- Treating persistence as actor state storage (wrong layer)
- Forgetting to apply retention in reads and compaction consistently
- Implementing `scan()` that mutates storage (breaks startup semantics)
- Doing expensive reads without bounds (always cap scan samples and reads)
- Raising exceptions from `record_*` in production paths without suppression

## When to extend an existing backend instead

If your goal is primarily *shipping events to other systems*, consider:

- using Redis Streams consumer groups (at-least-once shipping)
- exporting metrics via OpenTelemetry
- structured logs shipped by your runtime

Custom backends are best when you need **native storage semantics** (compliance, querying, enterprise operations).
