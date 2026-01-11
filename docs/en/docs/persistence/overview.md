# Overview

Papyra persistence is **not application state storage**.

It is a **system-level, append-only fact log** that records *what happened* inside an actor system so the system itself can be:

- inspected
- audited
- recovered
- compacted
- validated before startup

This page explains **what persistence means in Papyra**, what it deliberately does *not* do, and how the different pieces fit together.

---

## What Papyra Persistence Is

Papyra persistence records **immutable system facts** produced by the actor runtime:

- actor lifecycle events
- supervision failures
- dead letters
- audits and health signals

Each persisted record answers one of these questions:

- *What happened?*
- *When did it happen?*
- *Which actor was involved?*
- *Was the system healthy at that moment?*

Persistence is therefore **observational**, not behavioral.

It does **not** influence how actors process messages.
It does **not** replay messages.
It does **not** restore actor state.

---

## What Papyra Persistence Is NOT

It is important to be explicit about what persistence does *not* do.

Papyra persistence is **not**:

- Event Sourcing
- CQRS
- Message replay
- Actor state recovery
- A database abstraction

Actors **do not read from persistence**.

Persistence exists *outside* the actor execution model and never affects scheduling, ordering, or delivery.

If you need state recovery, snapshots, or replay semantics, those belong in **your application layer**, not the runtime.

---

## Persistence Categories

Papyra persists different kinds of system facts, each with a clear purpose.

### Events

Events describe **actor-level activity**:

- actor started
- actor stopped
- message processed
- supervision decisions

They are useful for:

- debugging behavior
- reconstructing timelines
- understanding system load

---

### Audits

Audits capture **system-wide snapshots**:

- number of actors
- registry state
- dead letter counts
- system health indicators

Audits are typically written periodically and are used for:

- monitoring
- capacity planning
- long-term trend analysis

---

### Dead Letters

Dead letters record messages that **could not be delivered**.

They are critical for:

- detecting routing bugs
- identifying message storms
- diagnosing misconfigured supervision trees

Dead letters are never dropped silently.

---

## Backends

Persistence is implemented through **pluggable backends**.

Each backend guarantees:

- append-only writes
- read-after-write consistency
- safe scanning
- deterministic recovery

### Built-in Backends

- **JSON File Backend** — local durability, human-readable
- **Redis Streams Backend** — production-grade, distributed, durable
- **Memory Backend** — testing and ephemeral systems

Backends may support different capabilities (metrics, compaction, recovery), but they all conform to the same contract.

---

## Retention

Persistence grows forever unless constrained.

Retention policies allow you to define **when old facts are dropped**:

- maximum number of records
- maximum age
- maximum total size

Retention is:

- applied logically at read time
- applied physically during compaction

Retention never breaks ordering or consistency guarantees.

---

## Compaction

Compaction is the process of **physically rewriting storage** to apply retention.

Why compaction exists:

- files do not shrink automatically
- Redis streams must be trimmed
- old data must be removed safely

Compaction is:

- explicit
- atomic
- safe to run repeatedly

Compaction never changes *meaning*, only *storage footprint*.

---

## Health, Scanning, and Recovery

Every backend may support:

- scanning for corruption
- detecting anomalies
- repairing or quarantining bad data

This enables:

- startup validation
- CI/CD pre-flight checks
- operational safety in production

Papyra treats corrupted persistence as a **first-class operational concern**, not an edge case.

---

## Observability

Persistence integrates tightly with metrics:

- records written
- bytes written
- scan counts
- anomaly counts
- recovery attempts

Metrics can be:

- inspected via CLI
- exported to OpenTelemetry
- consumed by external monitoring tools

This makes persistence *observable*, not opaque.

---

## Design Philosophy

Papyra persistence follows a few strict principles:

1. **Never interfere with actor execution**
2. **Prefer explicit operations over magic**
3. **Make corruption visible, not silent**
4. **Support operations, not frameworks**

Persistence exists to help **humans understand systems**.

That is its only job.
