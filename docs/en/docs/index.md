# Papyra

**Durable persistence, retention, recovery, and observability for async actor systems.**

Papyra is a persistence and operational tooling layer designed for **long-running, event-driven systems**.
It provides **safe storage**, **controlled retention**, **explicit recovery**, and **deep visibility** into what happens to your data over time.

Papyra is not a database.
It is not a message broker.

It is the missing persistence layer for systems that must **run continuously**, **survive crashes**, and **remain inspectable and debuggable in production**.

---

## Why Papyra Exists

Most async systems focus on **execution**:

- actors
- tasks
- queues
- concurrency

Very few focus on **what happens after months or years of runtime**:

- logs growing endlessly
- corrupted files after crashes
- silent data loss
- no way to inspect, recover, or compact data
- no operational visibility

Papyra exists to solve **the lifecycle problem** of async systems.

It treats persistence as a **first-class operational concern**, not an afterthought.

---

## Core Concepts

Papyra is built around a small set of explicit, composable concepts.

### Persistence Backends

A persistence backend is responsible for **physically storing records**.

Built-in backends include:

- In-memory persistence (for tests and ephemeral systems)
- JSON / NDJSON file persistence
- Rotating file persistence
- Redis Streams persistence

Each backend implements the same **explicit contract**:

- write
- read
- scan
- recover
- compact

---

### Retention Policies

Retention is **not implicit** and **not hidden**.

You decide:

- how many records to keep
- how old records are allowed to be
- how much storage may be used

Retention is enforced:

- during reads
- during compaction
- during recovery

This ensures systems do not grow unbounded over time.

---

### Physical Compaction

Papyra separates **logical retention** from **physical storage**.

Deleting records logically does **not** shrink disk usage.

Compaction:

- rewrites storage
- applies retention rules
- removes obsolete data
- reclaims disk space safely

Compaction is explicit, safe, and observable.

---

### Recovery & Quarantine

Papyra assumes **things will go wrong**.

It supports:

- detecting corrupted records
- repairing damaged files
- quarantining broken data
- validating recovery success

Recovery is:

- explicit
- testable
- scriptable
- auditable

No silent fixes. No hidden behavior.

---

### Metrics & Observability

Papyra exposes structured metrics for:

- writes
- reads
- scans
- recoveries
- compactions
- errors and anomalies

These metrics are available via:

- CLI
- API
- structured snapshots
- external observability tooling

This makes persistence **observable**, not opaque.

---

## Designed for Operations

Papyra is designed for **production operations**, not just development.

It supports:

- pre-flight startup checks
- CI/CD validation
- Kubernetes init containers
- cron-based maintenance
- emergency recovery workflows

Everything that affects data is:

- explicit
- testable
- inspectable

---

## Who Should Use Papyra?

Papyra is ideal if you are building:

- async actor systems
- event-sourced services
- long-running workers
- background processing platforms
- systems where data must survive restarts and crashes

If your system:

- runs for weeks or months
- writes continuously
- cannot afford silent data corruption

Papyra is for you.

---

## What This Documentation Covers

This documentation is intentionally **thorough and practical**.

You will find:

- conceptual explanations
- step-by-step guides
- real-world scenarios
- CLI workflows
- recovery playbooks
- observability integration patterns

You do **not** need prior experience with actor systems or persistence internals.

---

## Next Steps

If you are new to Papyra, start here:

- **Concepts** → understand the model
- **Persistence Backends** → choose storage
- **Retention & Compaction** → control growth
- **CLI Tools** → operate safely
- **Metrics & Observability** → gain visibility

Papyra is built to be **boring, safe, and predictable** —
exactly what persistence should be.
