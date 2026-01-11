# Glossary

This glossary defines the core terminology used throughout **Papyra**.

It is intended as a **precise technical reference**, not a tutorial.
All definitions reflect **actual runtime behavior**, **persistence guarantees**, and **operational semantics** implemented in the Papyra codebase.

---

## Actor

An **Actor** is the fundamental unit of computation in Papyra.

An actor:

- Encapsulates state and behavior
- Processes one message at a time from its mailbox
- Never shares mutable state with other actors
- Communicates exclusively via message passing

Actors are single-threaded by design, which removes the need for locks while preserving concurrency at the system level.

---

## ActorSystem

The **ActorSystem** is the top-level runtime responsible for:

- Spawning and supervising actors
- Routing messages
- Managing mailboxes
- Emitting lifecycle events
- Coordinating persistence, audits, and metrics

An application typically runs exactly one ActorSystem instance per process.

---

## ActorRef

An **ActorRef** is a stable, serializable reference to an actor.

It represents:

- The actor's logical address
- The only safe way to interact with an actor

ActorRefs can be sent across actors, persisted, or logged without exposing the underlying actor instance.

---

## ActorContext

The **ActorContext** is injected by the runtime into each actor after startup.

It provides access to:

- The actor's own ActorRef
- Parent and child relationships
- The ActorSystem
- System time and utilities

The context is **not available during `__init__`** and must be accessed from lifecycle hooks or message handlers.

---

## Message

A **Message** is any Python object sent to an actor.

Messages are:

- Immutable by convention
- Delivered asynchronously
- Processed sequentially by the receiving actor

Papyra supports both fire-and-forget (`tell`) and request–response (`ask`) messaging patterns.

---

## Mailbox

A **Mailbox** is the internal queue holding pending messages for an actor.

Each actor has exactly one mailbox.
Messages are processed in FIFO order unless a custom mailbox strategy is used.

---

## Dead Letter

A **Dead Letter** is a message that could not be delivered.

Common causes include:

- Target actor no longer exists
- Actor stopped before message delivery
- Invalid or unreachable actor reference

Dead letters are persisted and exposed through inspection and metrics tooling.

---

## Event

An **Event** is a persisted record describing a lifecycle transition or significant runtime occurrence.

Examples:

- Actor started
- Actor stopped
- Actor crashed
- Actor restarted

Events are immutable and append-only.

---

## Audit

An **Audit** is a periodic snapshot of system state.

Audits include:

- Total actor count
- Alive, stopping, restarting actors
- Dead letter counts
- Registry health

Audits are designed for operational visibility rather than debugging individual message flows.

---

## Persistence Backend

A **Persistence Backend** is a storage implementation responsible for:

- Writing events, audits, and dead letters
- Serving historical queries
- Applying retention policies
- Performing recovery and compaction

Examples include:

- In-memory backend
- JSON file backend
- Rotating file backend
- Redis Streams backend

---

## Retention Policy

A **Retention Policy** defines how much data is kept.

Retention can be based on:

- Maximum record count
- Maximum age
- Maximum total size

Retention is **logical by default** (applied at read time) and **physical only during compaction**.

---

## Compaction

**Compaction** (also called vacuuming) is the physical process of reclaiming storage space.

During compaction:

- Retention rules are applied
- Obsolete records are removed
- Storage files or streams are rewritten or trimmed

Compaction is explicit and never automatic.

---

## Startup Check

A **Startup Check** simulates the persistence validation phase of system startup.

It can:

- Scan for anomalies
- Fail fast
- Attempt recovery
- Validate post-recovery integrity

Startup checks are exposed via both API and CLI.

---

## Doctor

The **Doctor** is a standalone CLI utility for diagnosing persistence health.

It provides:

- Scanning
- Strict failure modes
- Controlled recovery
- Human-readable output

Doctor is intended for operators, CI pipelines, and production troubleshooting.

---

## Anomaly

An **Anomaly** is a detected inconsistency or corruption in persisted data.

Examples:

- Truncated JSON records
- Invalid payloads
- Missing required fields

Anomalies trigger different behavior depending on configured recovery strategy.

---

## Recovery

**Recovery** is the process of handling detected anomalies.

Recovery modes include:

- Repair (fix in place)
- Quarantine (move corrupted data aside)
- Ignore

Recovery is explicit and always operator-controlled.

---

## Quarantine

**Quarantine** is a recovery strategy where corrupted records are moved to a separate location.

This preserves forensic evidence while allowing the system to continue operating.

---

## Metrics

**Metrics** are internal counters tracking runtime and persistence behavior.

Metrics include:

- Writes
- Reads
- Scans
- Recoveries
- Errors

Metrics are exposed via CLI, snapshots, and external integrations.

---

## Redis Streams

**Redis Streams** is a persistence backend using Redis append-only streams.

It provides:

- Durability
- Horizontal scalability
- Consumer group support
- At-least-once delivery semantics

---

## Consumer Group

A **Consumer Group** is a Redis Streams construct allowing multiple consumers to process persisted records cooperatively.

It supports:

- Pending entry tracking
- Message claiming
- Explicit acknowledgements

Used primarily for external tooling and integrations.

---

## Pending Entry

A **Pending Entry** is a stream record delivered to a consumer but not yet acknowledged.

Pending entries indicate:

- Processing delays
- Crashes
- Backpressure issues

---

## At-least-once Delivery

**At-least-once delivery** guarantees that a record is delivered one or more times.

Consumers must be idempotent to handle potential duplicates.

---

## Idempotency

**Idempotency** means an operation can be safely repeated without changing the outcome.

It is a critical requirement when consuming persisted records from Redis Streams.

---

## Metrics Snapshot

A **Metrics Snapshot** is a point-in-time export of all metrics counters.

Snapshots are read-only and safe to query at any time.

---

## Compaction Scheduling

**Compaction Scheduling** refers to running compaction as a planned operational task, often via cron or orchestration tools.

Compaction is never implicit and must be triggered explicitly.

---

## Persistence Inspection

**Persistence Inspection** is the act of querying historical data for visibility and debugging.

Inspection commands expose:

- Events
- Audits
- Dead letters
- System summaries

Inspection never mutates state.

---

## Exit Code

An **Exit Code** is a numeric status returned by CLI commands to signal success or failure.

Exit codes are stable and documented for automation and CI usage.
