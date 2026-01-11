# Rotating File Backend

The **Rotating File Persistence Backend** is a production‑grade, file‑based persistence
strategy designed for **long‑running systems** that must retain large volumes of events
without letting individual files grow unbounded.

It combines the **simplicity of append‑only files** with **predictable disk usage** and
**operational safety**, making it suitable for deployments where Redis or databases are
not available or not desired.

---

## When to Use the Rotating Backend

Choose the rotating backend when:

- You want **durable persistence without external infrastructure**
- You need **bounded file sizes**
- You want **human‑inspectable logs**
- You run in **edge, embedded, or restricted environments**
- You want **fast startup and recovery**

Typical environments:

- On‑prem deployments
- Edge/IoT systems
- Air‑gapped systems
- Local‑first architectures
- Compliance‑driven logging setups

---

## Core Design Principles

### Append‑Only Safety

Each file is written in **append‑only mode**, meaning:

- No in‑place mutation
- No partial overwrites
- Safe against crashes and power loss

If a crash occurs mid‑write, only the **last line** is affected and can be detected
during scanning.

---

### Rotation Instead of Truncation

Instead of growing one file forever, the backend **rotates files** based on size or
policy:

```
events-0001.ndjson
events-0002.ndjson
events-0003.ndjson
```

Older files remain immutable once closed.

---

### Deterministic Ordering

Across rotated files:

- Events remain **strictly ordered**
- File sequence numbers encode ordering
- Reads are replayed **file by file, line by line**

This guarantees deterministic recovery and replay.

---

## File Layout

A typical layout looks like:

```
papyra-data/
├── events/
│   ├── events-0001.ndjson
│   ├── events-0002.ndjson
│   └── events-0003.ndjson
├── audits/
│   ├── audits-0001.ndjson
│   └── audits-0002.ndjson
└── dead_letters/
    └── dead_letters-0001.ndjson
```

Each category rotates **independently**.

---

## Record Format

Each line is a valid JSON document:

```json
{
  "kind": "event",
  "system_id": "local",
  "actor_address": "actor://user/42",
  "event_type": "UserCreated",
  "payload": {"id": 42},
  "timestamp": 1700000000.123
}
```

Guarantees:

- One record per line
- UTF‑8 encoded
- JSON‑parseable
- Stream‑friendly

---

## Rotation Policy

Rotation is triggered when **any** configured threshold is exceeded.

Common triggers:

- Max file size (bytes)
- Max record count
- Retention constraints

When rotation happens:

1. Current file is **closed**
2. A new file is created
3. Writes continue seamlessly

Rotation never blocks reads.

---

## Retention Integration

Retention policies are applied **logically** at read time and **physically** during
compaction.

Examples:

- Keep last N records
- Keep records newer than X days
- Enforce max total disk usage

Retention never corrupts file structure.

---

## Scanning & Health Checks

The rotating backend fully supports:

- `scan()`
- `startup_check`
- `doctor`
- CLI inspection

During scanning:

- Each file is validated line by line
- Corrupted lines are reported with file + offset
- Healthy files are skipped efficiently

---

## Recovery Behavior

### Repair Mode

In `repair` mode:

- Truncated or invalid lines are removed
- Files are rewritten atomically
- Ordering is preserved

### Quarantine Mode

In `quarantine` mode:

- Corrupted files are moved aside
- Clean data is retained
- Quarantined files remain inspectable

---

## Compaction

Compaction rewrites rotated files to:

- Apply retention physically
- Remove obsolete records
- Reduce disk usage

Compaction is:

- Explicit (never automatic)
- Atomic
- Safe under concurrent reads

---

## Operational Guarantees

The rotating backend guarantees:

- **Crash safety**
- **Deterministic replay**
- **Bounded disk growth**
- **Human‑readable logs**
- **Zero external dependencies**

What it does NOT guarantee:

- Distributed consumption
- Cross‑process coordination
- Horizontal scalability

---

## Performance Characteristics

| Aspect | Behavior |
|------|---------|
| Writes | O(1), append‑only |
| Reads | Sequential |
| Startup | Fast (index‑free) |
| Recovery | Linear in corrupted region |
| Memory | Minimal |

---

## Comparison with Other Backends

| Backend | Best For |
|------|---------|
| In‑Memory | Tests, ephemeral systems |
| JSON File | Small, simple persistence |
| **Rotating File** | Long‑running local systems |
| Redis | Distributed systems |

---

## Summary

The Rotating File Backend is the **most robust file‑based option** in Papyra.

It sits between simple JSON files and Redis:

- More durable than single‑file persistence
- Simpler than distributed backends
- Ideal for production systems that value **predictability and control**

If you want durability without infrastructure, this is the backend to use.
