# Concepts and Mental Model

This document explains the **conceptual model** behind Papyra's persistence system.

If you understand this page, everything else becomes predictable.

---

## The Core Idea

Papyra persistence records **facts**, not **state**.

A fact is something that already happened and cannot be changed.

Examples:
- An actor started
- A message failed delivery
- A scan detected corruption
- Recovery quarantined a file

Persistence does **not** influence execution.
Execution influences persistence.

This one-way relationship is critical.

---

## One-Way Data Flow

The persistence flow always looks like this:

```shell
Actor Runtime
↓
Persistence Backend
↓
Inspection / Metrics / CLI
```

Never the opposite.

Persistence:
- never controls actors
- never replays behavior
- never mutates runtime state

---

## Append-Only Log Model

All persistence backends follow the same logical structure:

```shell
[ Record 1 ]
[ Record 2 ]
[ Record 3 ]
[ Record 4 ]
```

Records are:
- appended
- immutable
- timestamped

There is no “update”.
There is no “delete”.

**This applies even when using Redis.**

---

## Logical vs Physical State

This distinction is essential.

### Logical State

Logical state answers:

> “Which records are visible right now?”

Logical state is affected by:
- retention rules
- query limits
- sampling

Logical filtering does **not** delete data.

---

### Physical State

Physical state answers:

> “What bytes exist on disk or in Redis?”

Physical state changes **only** during:
- compaction
- quarantine
- recovery

**These are explicit operations.**

---

## Retention Is Not Cleanup

Retention rules **hide records**, they do not remove them.

**Example**:

- `Retention: max_records = 100`
- `Physical records on disk = 10,000`
- `Visible records = 100`

Retention:
- protects memory
- bounds queries
- prevents overload

But disk usage remains unchanged.

---

## Compaction Is Destructive

Compaction rewrites storage.

Before compaction:

```shell
[ valid ]
[ expired ]
[ expired ]
[ valid ]
[ expired ]
```

After compaction:

```shell
[ valid ]
[ valid ]
```

Compaction:
- permanently deletes data
- may change file layout
- cannot be reversed

This is why compaction is **never automatic**.

---

## Scan → Recover → Verify Lifecycle

All persistence maintenance follows the same lifecycle.

### 1. Scan

Scan answers:

> “Is the persistence structurally sound?”

It detects:
- truncated files
- invalid JSON
- orphaned segments
- malformed entries

Scan never mutates data.

---

### 2. Recover (Optional)

Recovery is explicit.

Two modes exist:

#### Repair

- Attempts to fix in place
- Truncates corrupted tails
- Keeps valid data

#### Quarantine

- Moves corrupted files aside
- Preserves evidence
- Starts clean

Recovery always produces a report.

---

### 3. Verification Scan

After recovery, the system **re-scans**.

If anomalies remain:
- recovery is considered failed
- exit codes reflect partial failure

No silent success.

---

## Startup Modes

Persistence startup checks reuse the same logic.

Available behaviors:

### ignore

- Scan runs
- Anomalies are logged
- Startup continues

Used in development.

---

### fain_on_anomaly

- Scan runs
- Any anomaly aborts startup

Used in CI and strict production.

---

### recover

- Scan runs
- Recovery is attempted
- Startup continues only if clean

Used in self-healing environments.

---

## Redis Is Not Special

Redis Streams **do not change semantics**.

Even with Redis:
- records are append-only
- retention is logical
- compaction is explicit
- acknowledgements affect visibility, not existence

This consistency allows backend swapping.

---

## Failure Is Expected

Persistence assumes failures will happen.

Examples:
- power loss during write
- disk full
- Redis restart
- partial network outages

The system is designed so that:
- failures are observable
- recovery is possible
- runtime continues

---

## Why This Model Matters

This model ensures:
- debuggability
- operational safety
- predictable behavior
- low cognitive load under stress

You always know:
- what happened
- what exists
- what was ignored
- what was destroyed

---

## Next Steps

Continue with:

- **Quickstart** — minimal setup
- **Backends** — choosing storage
- **Retention** — rules and limits
