# Core Concepts

Papyra is not just a persistence backend.
It is a **persistence lifecycle system** designed to make failure, recovery, inspection,
and operational safety explicit.

This document explains the foundational ideas behind Papyra.
Understanding these concepts will make the rest of the documentation significantly easier
to reason about and apply in real systems.

---

## 1. Persistence Is a Lifecycle

Most systems treat persistence as a simple API:

> write → read

Papyra treats persistence as a **continuous lifecycle**:

1. Write
2. Retain
3. Scan
4. Recover
5. Compact
6. Inspect
7. Observe

Each phase exists because real systems:

- crash mid-write
- are upgraded while data lives on
- accumulate obsolete or invalid records
- require human operators to intervene
- must be debugged under time pressure

Papyra makes each phase **explicit, testable, and automatable**.

---

## 2. Append-Only First

All Papyra persistence backends follow one core rule:

> **Writes are append-only**

This means:
- No in-place mutation during normal operation
- New records are always appended
- Old data is never silently overwritten

### Why append-only?

Append-only storage:

- makes partial writes detectable
- avoids catastrophic corruption
- enables deterministic recovery
- mirrors how production systems actually fail

Examples:

- JSON backend → newline-delimited append
- Redis Streams → `XADD`
- Future SQL backends → append-only tables or WAL-style patterns

Mutation only happens during **explicit compaction or recovery**.

---

## 3. Logical State vs Physical State

Papyra makes a strict distinction between:

### Logical state

What the application *considers valid*:

- active events
- recent audits
- relevant dead letters

### Physical state

What *actually exists* in storage:

- expired records
- corrupted entries
- quarantined data
- unused disk space

Retention, scanning, and compaction bridge this gap.

Nothing disappears implicitly.

---

## 4. Retention Is Not Deletion

Retention in Papyra is **logical filtering**, not immediate deletion.

A retention policy may specify:

- maximum record count
- maximum age
- maximum total bytes

Retention is applied:

- during reads
- during inspection
- during compaction

This ensures:

- deterministic behavior
- safe upgrades
- predictable recovery

Deletion only happens during **explicit compaction**.

---

## 5. Scanning: Detecting Reality

The `scan()` phase answers one question:

> “Is the stored data structurally valid?”

Scanning detects:

- truncated records
- invalid JSON
- missing required fields
- backend-specific inconsistencies

Key properties:

- read-only
- safe to run anytime
- sample-based where necessary
- backend-aware

If a backend cannot support scanning, it must explicitly say so.

---

## 6. Anomalies Are First-Class

When something is wrong, Papyra does not hide it.

An anomaly includes:

- type (corruption, truncation, invalid record)
- location (file, stream, key)
- human-readable details

Anomalies:

- are returned programmatically
- are visible via CLI
- can block startup
- can trigger automated recovery

Nothing is auto-fixed without visibility.

---

## 7. Recovery Is Explicit

Recovery never happens implicitly.

You must explicitly choose:

- when recovery runs
- which strategy is used
- what happens to corrupted data

Supported strategies:

- **REPAIR** → fix in place when possible
- **QUARANTINE** → move corrupted data aside
- **IGNORE** → acknowledge risk and continue

Every recovery is followed by a **post-recovery scan**.

---

## 8. Startup Safety Modes

Papyra formalizes startup behavior via explicit modes:

- `IGNORE` - Start regardless of anomalies

- `FAIL_ON_ANOMALY` - Fail fast if anything is wrong

- `RECOVER` - Attempt recovery, then re-scan

These modes exist because environments differ:

- local development
- CI pipelines
- production deployments
- emergency maintenance

Startup behavior is never implicit.

---

## 9. Compaction Is Physical Maintenance

Compaction is the only operation that:

- rewrites data
- reclaims disk space
- removes expired records physically

Compaction:

- is explicit
- is backend-specific
- is safe by design
- respects retention policies

Running compaction is an operational decision, not a side effect.

---

## 10. Inspection Is for Humans

Inspection exists for operators and developers.

The inspect phase provides:

- backend identity
- retention configuration
- approximate data volumes
- metrics snapshots (if supported)

Inspection favors **clarity over completeness**.

It is designed to answer:

> “Is this system behaving the way I expect?”

---

## 11. Observability Is Built In

Papyra exposes internal metrics:

- write counts
- error counts
- scan results
- recovery outcomes
- compaction statistics

Metrics:

- are backend-aware
- can be reset
- can be exported
- integrate naturally with monitoring systems

This makes Papyra suitable for production environments that require visibility.

---

## 12. Philosophy Summary

Papyra is built on a few non-negotiable principles:

- Failure is normal
- Corruption must be visible
- Recovery must be explicit
- Operators must be empowered
- Data must never disappear silently

If you understand these principles, you understand Papyra.

The rest of the documentation builds directly on them.
