# Backends

Papyra persistence backends define **how events are stored, consumed, recovered, and compacted**.

This document explains:
- What backends exist
- How they work internally
- Their guarantees
- When to use each one

---

## Overview

| Backend | Storage | Ordering | Ack | Multi-consumer | Disk usage |
|------|--------|---------|-----|----------------|-----------|
| JSON File | Local disk | Yes | No | No | Grows |
| Redis Streams | Redis | Yes | Yes | Yes | Bounded |
| Memory | RAM | Yes | No | No | Ephemeral |

---

## JSON File Persistence

### What It Is

The JSON backend uses an **append-only NDJSON file**:

```json
{“kind”:“event”, …}
{“kind”:“audit”, …}
{“kind”:“event”, …}
```

Each line is a **single atomic record**.

---

### Guarantees

* ✔ Append-only
* ✔ Order preserved
* ✔ Crash-safe writes
* ✔ Human-readable
* ✔ Recoverable
* ❌ No acknowledgements
* ❌ Single reader model
* ❌ Disk grows until compacted

---

### Internal Model

- Writes append one line per record
- Reads scan sequentially
- Retention filters at read time
- Compaction rewrites the file
- Corruption is detected line-by-line

This design prioritizes **safety over speed**.

---

### When to Use JSON

Use JSON persistence when:

- Running locally or on a single node
- You want **zero infrastructure**
- You need debuggable logs
- You value durability over throughput

Examples:
- Actor systems
- Event-sourced services
- Offline processing
- Local agents

---

### When NOT to Use JSON

Avoid JSON persistence when:

- You need multiple consumers
- You require acknowledgements
- You have very high write throughput
- You cannot afford compaction pauses

---

### Example Configuration

```python
from papyra.persistence.json import JsonFilePersistence
from papyra.conf import settings

settings.persistence = JsonFilePersistence("events.ndjson")
```

## Redis Streams Persistence

What It Is?

Redis Streams persistence uses Redis Streams + Consumer Groups.

Each event is written to a Redis stream and consumed via groups.

### Guarantees

* ✔ Ordered streams
* ✔ Acknowledgements
* ✔ Multiple consumers
* ✔ Pending tracking
* ✔ Claim / retry support
* ❌ Requires Redis
* ❌ External dependency
* ❌ Data not human-readable

Internal Model:
- Events written using XADD
- Consumer groups created lazily
- Consumption via XREADGROUP
- Acks via XACK
- Pending entries tracked by Redis
- Claims handled with XCLAIM

This enables true stream processing semantics.

### Consumer Groups Explained

Each consumer group:
- Tracks last delivered ID
- Knows pending messages
- Allows rebalancing
- Supports retries

This is how fault-tolerant processing is achieved.

### When to Use Redis

Use Redis Streams when:
- Multiple workers consume events
- You need retries
- You need delivery guarantees
- You scale horizontally

Examples:
- Distributed actors
- Event pipelines
- Stream processors
- Fan-out systems

### Example Configuration

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

### Consumer Group Configuration

```python
from papyra.persistence.backends.redis import RedisConsumerGroupConfig

group_cfg = RedisConsumerGroupConfig(
    group="workers",
    consumer="worker-1",
    count=10,
    block_ms=1000,
)
```

## In-Memory Persistence

What It Is?

An ephemeral persistence backend that stores everything in RAM.

### Guarantees

* ✔ Fast
* ✔ Ordered
* ❌ No durability
* ❌ No recovery
* ❌ No compaction


When to Use Memory?

- Tests
- Prototypes
- Local experimentation

Never use in production.

## Choosing the Right Backend

Decision Guide
- Single process, local, durable → **JSON**
- Distributed, scalable, resilient → **Redis**
- Tests only → **Memory**

## Hybrid Patterns

You can mix persistence strategies:
- JSON for audits
- Redis for events
- Memory for testing

Papyra does not force a single model.

## Failure Characteristics

**JSON Failure Modes**:
- Partial line → **recoverable**
- Truncation → **recoverable**
- Disk full → **fatal until space freed**

**Redis Failure Modes**:
- Redis down → writes fail
- Consumer crash → messages pending
- Network split → retries required

**Operational Notes**:
- Always enable startup checks
- Compact JSON periodically
- Monitor Redis pending counts
- Use CLI tools in automation
