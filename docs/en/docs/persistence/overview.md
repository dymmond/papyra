# Overview

Papyra's persistence system is **not a database**, and it is **not event sourcing**.

It exists to record *observable system facts* produced by the actor runtime:
`events`, `audits`, and `delivery failures`  **without interfering with execution**.

This page explains:
- What persistence is (and is not)
- Why it exists
- What guarantees it provides
- How it fits into production systems

---

## What Persistence Means in Papyra

Persistence in Papyra is an **append-only observability layer**.

It records *facts about what happened*, not *state used to compute behavior*.

**Examples of persisted facts**:
- An actor started or stopped
- An audit snapshot of system health
- A message could not be delivered (dead letter)
- Corruption detected during a scan
- Recovery actions taken by the system

Persistence is **never required** for the actor system to function.
If persistence fails, actors continue running.

This is intentional.

---

## What Persistence Is NOT

Persistence in Papyra is **not**:

- ❌ A database
- ❌ A replacement for business storage
- ❌ Event sourcing
- ❌ Actor mailbox persistence
- ❌ State recovery for actors

Actor state lives in memory.
If an actor crashes, it restarts clean.

Persistence exists to answer questions like:

> “What happened to my system?”

**not**:

> “What should my system do next?”

---

## Design Principles

The persistence layer follows strict rules.

### 1. Append-Only

Persistence backends **append records**.
They do not update or mutate existing entries.

**This makes persistence**:
- Simple
- Auditable
- Safe under failure

Physical cleanup happens only during **explicit compaction**.

---

### 2. Non-Blocking

Persistence must **never block the actor runtime**.

**If a backend**:
- Is slow
- Is unavailable
- Encounters corruption

…the actor system continues running.

Failures are recorded as metrics and anomalies.

---

### 3. Best-Effort Guarantees

Persistence operations are **best-effort**.

This means:
- Writes may fail
- Reads may be incomplete
- Recovery may be partial

Failures are surfaced through:
- Metrics
- CLI tools
- Structured logs

But never through runtime crashes.

---

### 4. Explicit Lifecycle Control

Nothing happens automatically.

There is **no background cleanup**.

Instead, operators explicitly invoke:
- `scan` → detect anomalies
- `recover` → repair or quarantine
- `compact` → physically shrink storage

This avoids hidden behavior and surprises.

---

## Persistence Categories

Papyra persists **three categories** of data:

### Events

Lifecycle events emitted by actors:
- start
- stop
- restart
- crash

These are **low-level runtime facts**, not domain events.

---

### Audits

Point-in-time snapshots of system health:
- number of actors
- registry integrity
- dead letter counts

Audits are typically triggered manually or on schedules.

---

### Dead Letters

Messages that could not be delivered:
- target actor missing
- actor stopped
- routing failure

Dead letters are essential for debugging message loss.

---

## Supported Backends

Papyra supports multiple persistence backends with identical semantics:

- **JSON File** — simplest, local, inspectable
- **Rotating File** — bounded disk usage
- **Redis Streams** — production-grade, distributed
- **In-Memory** — testing / development

Backends can be swapped without changing application code.

---

## Retention vs Compaction

Retention and compaction are **not the same**.

### Retention

Retention is **logical**.

It filters:
- How many records are *visible*
- Which records are *returned*

Retention does **not** delete data.

---

### Compaction

Compaction is **physical**.

It:
- Rewrites storage
- Deletes expired records
- Shrinks disk usage

Compaction is:
- Explicit
- Destructive
- Operator-controlled

---

## Startup Safety

On startup, persistence can be checked before actors run.

Papyra supports:
- Ignore anomalies
- Fail fast
- Recover automatically

This allows safe deployment workflows:
- CI validation
- Kubernetes init containers
- Blue/green deploys

---

## Who This Is For

Persistence is designed for:

- Operators
- Platform engineers
- SREs
- System developers

It is intentionally **boring**, **predictable**, and **transparent**.

---

## Next Steps

Continue with:

- **Concepts** — mental model & lifecycle
- **Quickstart** — minimal setup
- **Backends** — choosing the right storage
