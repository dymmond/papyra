# Quickstart

This guide gets you from **zero → safe persistence** with minimal theory.

If you only read one practical page, read this one.

---

## What You Get by Default

Out of the box, Papyra provides:

- A **JSON file persistence backend**
- Safe append-only writes
- Startup health checks
- CLI tooling
- Retention support
- Compaction & recovery tools

You do **not** need Redis to start.

---

## Minimal Setup (JSON Backend)

### 1. Enable persistence

```python
from papyra.conf import settings
from papyra.persistence.json import JsonFilePersistence

settings.persistence = JsonFilePersistence("events.ndjson")
```

That's it.

No migrations.
No schemas.
No bootstrap step.


## 2. Run your application

Persistence starts writing immediately.

You now have:
- events
- audits
- dead letters (if any)

All stored append-only.

## Inspect Persistence Health

Before doing anything else, inspect.

```shell
papyra persistence inspect
```

Example output:

```shell
Persistence Inspect
------------------
backend: JsonFilePersistence
retention: max_records=None max_age_seconds=None max_total_bytes=None
events_sampled: 12
audits_sampled: 4
dead_letters_sampled: 0
```

This confirms:
- backend is active
- data is being written
- no anomalies

## Scan for Corruption

Scanning is read-only and safe.

```shell
papyra persistence scan
```

Healthy output:

```shell
✔ Persistence is healthy.
```

If corruption exists:

```shell
✖ Found 1 persistence anomalies:
- TRUNCATED_LINE: events.ndjson (unexpected EOF)
```

Exit code will be non-zero.

## Recover from Corruption

Repair (default)

```shell
papyra persistence recover
```

This:
- truncates invalid tails
- preserves valid data
- exits successfully if clean

## Quarantine (for forensics)

```shell
papyra persistence recover \
  --mode quarantine \
  --quarantine-dir ./quarantine
```

This:
- moves corrupted files aside
- preserves evidence
- creates clean logs

## Startup Safety Check

Simulate what happens during application startup.

Fail on anomaly (recommended for prod)

```shell
papyra persistence startup-check --mode fail_on_anomaly
```

Startup will abort if corruption exists.

## Auto-recover on startup

```shell
papyra persistence startup-check \
  --mode recover \
  --recovery-mode repair
```

Used in self-healing environments.

## Retention (Logical Limits)

Retention does not delete data.

```python
from papyra.persistence.backends.retention import RetentionPolicy
from papyra.persistence.json import JsonFilePersistence
from papyra.conf import settings

settings.persistence = JsonFilePersistence(
    "events.ndjson",
    retention_policy=RetentionPolicy(
        max_records=10_000,
        max_age_seconds=7 * 24 * 3600,
    ),
)
```

Effects:
- queries are bounded
- memory usage is controlled
- disk is untouched

## Physical Cleanup (Compaction)

To reclaim disk space:

```shell
papyra persistence compact
```

This:
- rewrites storage
- removes expired records
- is irreversible

Run manually or via cron.

## Redis Quickstart (Optional)

When to use Redis

Use Redis when:
- multiple consumers exist
- fan-out is required
- acknowledgements matter

### Enable Redis Streams

Make sure you install redis: `pip install redis` or `pip install papyra[redis]`

```python
from papyra.persistence.backends.redis import (
    RedisStreamsPersistence,
    RedisStreamsConfig,
)
from papyra.conf import settings

settings.persistence = RedisStreamsPersistence(
    RedisStreamsConfig(
        url="redis://localhost:6379/0",
        prefix="papyra",
        system_id="prod",
    )
)
```

Everything else stays the same.

## Common Mistakes

### ❌ Expecting retention to shrink disk

Retention only affects visibility.

Use compaction.

### ❌ Assuming persistence replays state

Persistence records facts.
It does not replay behavior.

### ❌ Running compaction automatically

Compaction is destructive.
Run it explicitly.
