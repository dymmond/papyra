# Why Papyra Exists

Modern systems rarely fail because of *code*.
They fail because of **state**.

Corrupted logs, half-written files, silent data loss, disk pressure, race conditions during shutdown, or
recovery paths that were never exercised until production.

These are not edge cases, they are *inevitable* in long‑running systems.

Papyra exists to make those realities **explicit, observable, and controllable**.

---

## The Problem Papyra Solves

Most persistence solutions assume one of two worlds:

1. **Databases**
   Strong guarantees, heavy infrastructure, operational overhead.
2. **Logs / Files**
   Lightweight, fast, but fragile and opaque once things go wrong.

Many systems sit uncomfortably in between:

- Actor systems
- Event-driven runtimes
- Async pipelines
- Durable queues
- Long-lived services with append-only state

They need:

- Durability
- Predictable recovery
- Low overhead
- Clear operational semantics

But they **do not** need a full relational database.

Papyra is designed for this middle ground.

---

## What Makes Papyra Different

Papyra is not “just persistence”.
It is a **persistence lifecycle system**.

That means it explicitly models:

- Writing records
- Reading records
- Detecting corruption
- Recovering from corruption
- Enforcing retention
- Compacting physical storage
- Measuring and exposing health

Most libraries stop at *“write succeeded”*.
Papyra continues until *“the system is healthy again”*.

---

## Designed for Failure, Not Optimism

A core design principle of Papyra is:

> **Failure is normal. Recovery must be boring.**

This leads to concrete design choices:

- Scans are first-class operations
- Recovery is explicit and testable
- Startup behavior is configurable (fail, ignore, recover)
- Corruption is modeled, not hidden
- Compaction is intentional, not accidental
- Metrics exist from day one

Nothing here is implicit or magical.

---

## Why Not Just Use a Database?

Databases are excellent — when you need them.

But they come with:

- Operational complexity
- External dependencies
- Deployment coupling
- Performance trade-offs for simple append-only workloads

Papyra is intentionally:

- Embedded
- Lightweight
- Backend-agnostic
- Async-native

You can start with:

- In-memory persistence
- JSON files
- Rotating logs

And later move to:

- Redis Streams
- PostgreSQL-backed stores
- Custom backends

Without rewriting your application logic.

---

## Why Not Just Use Files Directly?

Because files alone do not give you:

- Health checks
- Anomaly detection
- Structured recovery
- Retention enforcement
- Safe compaction
- Metrics
- Consistent operational tooling

Most teams reinvent these features *poorly*, *inconsistently*, and *without tests*.

Papyra gives you a **coherent model** instead.

---

## Operational Clarity as a First-Class Feature

Papyra treats operators as first-class users.

This is why it ships with:

- CLI tools (`scan`, `recover`, `inspect`, `doctor`)
- Explicit exit codes
- Human-readable output
- Machine-friendly metrics
- Deterministic startup behavior

You should never have to:
- Guess whether persistence is healthy
- Manually inspect corrupted files
- Write one-off recovery scripts at 3am

---

## A Stable Contract for Extension

Papyra is designed to be extended safely.

Backends must:

- Implement explicit contracts
- Declare supported capabilities
- Integrate with metrics and lifecycle hooks
- Behave consistently under failure

This allows:

- Official backends (JSON, Redis, Postgres)
- Third-party implementations
- Internal custom storage engines

Without accidental coupling.

---

## Who Papyra Is For

Papyra is a good fit if you are building:

- Actor systems
- Event-sourced services
- Async runtimes
- Durable background workers
- Systems that must survive crashes cleanly

It is **not** a replacement for:

- OLTP databases
- Analytical data stores
- Full message brokers

It is a **foundation layer**, not an everything-layer.

---

## The Philosophy in One Sentence

> Papyra makes persistence **explicit**, **observable**, and **recoverable**, by design.

The rest of this documentation explains how.
