# Redis Persistence Backend

The Redis persistence backend provides **distributed, durable, and horizontally scalable**
storage for Papyra actor systems. It is designed for **production deployments** where
multiple processes, machines, or containers must coordinate reliably.

Unlike file-based persistence, Redis enables:

- Multi-consumer event streams
- Consumer groups and message claiming
- Near-real-time recovery
- Operational introspection via Redis tooling

This backend is built on **Redis Streams**, not simple lists or pub/sub.

---

## When to Use Redis Persistence

Choose the Redis backend when you need:

- Multiple actor systems consuming the same event stream
- High write throughput with low latency
- Crash recovery across machines
- Operational tooling (pending messages, lag, consumers)
- Kubernetes / cloud-native deployments

Avoid Redis persistence if:

- You need zero external dependencies
- You are running embedded or single-process workloads
- You require immutable append-only logs on disk

---

## Architecture Overview

Each logical persistence category maps to a Redis Stream:

| Category | Redis Key |
|--------|-----------|
| Events | `{prefix}:{system_id}:events` |
| Audits | `{prefix}:{system_id}:audits` |
| Dead Letters | `{prefix}:{system_id}:dead_letters` |

Each stream entry contains:

- A Redis Stream ID
- A single `data` field containing JSON
- A `kind` discriminator (`event`, `audit`, `dead_letter`)

All writes are **append-only**.

---

## Configuration

```python
from papyra.persistence.backends.redis import RedisStreamsConfig

config = RedisStreamsConfig(
    url="redis://localhost:6379/0",
    prefix="papyra",
    system_id="orders",
)
```

### Configuration Fields

- `url` – Redis connection URL
- `prefix` – Namespace for all keys
- `system_id` – Logical system identifier
- `scan_sample_size` – Safety bound for startup scans
- `max_read` – Upper bound for XRANGE reads
- `approx_trim` – Use approximate trimming during compaction
- `quarantine_prefix` – Optional quarantine namespace

---

## Enabling Redis Persistence

```python
from papyra.conf import settings
from papyra.persistence.backends.redis import RedisStreamsPersistence

settings.persistence = RedisStreamsPersistence(config)
```

Once enabled:

- All actors automatically persist events
- Startup scans run through Redis
- Recovery and compaction use Redis-native primitives

---

## Consumer Groups

Redis persistence supports **consumer groups** for scalable consumption.

### Reading with a Consumer Group

```python
items = await backend.consume(
    kind="events",
    cfg=RedisConsumerGroupConfig(
        group="workers",
        consumer="worker-1",
        count=100,
        block_ms=1000,
    ),
    read_id=">",
)
```

This guarantees:

- Each message is delivered to only one consumer
- Pending messages are tracked by Redis
- Crashed consumers do not lose messages

---

## Acknowledgement

Messages must be explicitly acknowledged:

```python
await backend.ack(
    kind="events",
    group="workers",
    ids=[item.id for item in items],
)
```

Unacked messages remain **pending**.

---

## Pending Messages & Claiming

### Inspect Pending Messages

```python
summary = await backend.pending_summary(
    kind="events",
    group="workers",
)
```

The summary includes:

- Pending count
- Min / max IDs
- Per-consumer breakdown

### Claiming Messages

If a consumer crashes, another consumer can claim its messages:

```python
claimed = await backend.claim(
    kind="events",
    group="workers",
    consumer="worker-2",
    min_idle_ms=0,
    entry_ids=[entry_id],
)
```

This is a **hard recovery mechanism**.

---

## Recovery Semantics

Redis recovery is **logical**, not physical.

- Corrupted JSON entries are detected during scans
- Recovery rewrites clean entries
- Invalid entries are skipped or quarantined
- Streams themselves are never deleted

Redis never blocks on recovery.

---

## Compaction

Compaction uses `XTRIM` internally.

- Old entries are removed based on retention policy
- Approximate trimming is used by default
- No stream locks are taken
- Operation is atomic per stream

```bash
papyra persistence compact
```

---

## Retention Interaction

Redis retention applies during:
- Compaction
- Startup recovery
- Explicit maintenance runs

Retention **does not** block writes.

---

## Operational Visibility

Because Redis is external, you gain:

- `XPENDING` visibility
- Consumer lag inspection
- Redis slowlog
- Redis keyspace monitoring
- Prometheus / Redis exporter integration

This makes Redis persistence ideal for:
- SRE teams
- Cloud deployments
- Large actor fleets

---

## Guarantees

| Property | Guarantee |
|--------|----------|
| Ordering | Per stream |
| Durability | Redis-backed |
| Delivery | At-least-once |
| Duplication | Possible (must be idempotent) |
| Recovery | Manual or automated |

---

## Summary

Redis persistence turns Papyra into a **distributed actor system**.

It trades simplicity for:
- Scalability
- Fault tolerance
- Operational control

For production-grade systems, Redis is the recommended backend.
