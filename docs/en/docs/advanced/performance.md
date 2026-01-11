# Performance & Tuning

This page explains how to reason about performance in **Papyra**, how to identify real
bottlenecks, and how to tune the system safely without breaking its guarantees.

Papyra is intentionally **not micro‑optimized by default**. Its design favors correctness,
durability, and observability first. Performance tuning is something you do *after* you
understand your workload.

---

## Performance Philosophy

Papyra follows three core performance principles:

1. **Append-first, optimize later**
    - Writes are sequential and durable
    - Reads are filtered logically
    - Physical optimization happens explicitly (compaction)

2. **Bounded operations**
    - All scans, reads, and inspections are capped
    - No unbounded file reads or Redis ranges by default

3. **Visibility before speed**
    - Metrics exist so you can see pressure *before* failure
    - Slow behavior is observable, not silent

This means:

- You will rarely see sudden performance cliffs
- You *will* see metrics increase before problems occur

---

## What Actually Affects Performance

### 1. Write Throughput

Write performance depends on:

- Backend type (memory, JSON, rotating files, Redis)
- Serialization cost
- Flush / fsync behavior (file backends)
- Network latency (Redis)

**Good news:** Writes are append-only and never require reads.

### 2. Read Amplification

Reads are affected by:

- Retention filtering at read time
- Limit / since usage
- Backend scan cost

**Rule of thumb** If you read frequently, **always use `limit` or `since`**.

---

## Backend-Specific Characteristics

### Memory Backend

- Fastest possible backend
- Zero IO
- No persistence guarantees

**Use for**

- Tests
- Short-lived systems
- Benchmarks

**Avoid**

- Long-running production systems

---

### JSON File Backend

- Append-only newline-delimited JSON
- Excellent durability
- Predictable IO behavior

**Costs**

- Full-file scans during reads
- Compaction required to reclaim space

**Tuning**

- Use retention aggressively
- Schedule compaction during low activity
- Avoid frequent full reads

---

### Rotating File Backend

- Bounded file sizes
- Better locality
- Faster scans than monolithic files

**Recommended for**

- Long-running systems
- Moderate to high write volume

**Key knobs**

- Rotation size
- Retention window
- Compaction cadence

---

### Redis Streams Backend

- Network-bound performance
- Atomic operations
- Built-in trimming support

**Strengths**

- High throughput
- Consumer groups
- Horizontal scalability

**Costs**

- Network latency
- Redis memory pressure

**Best practices**

- Enable approximate trimming
- Use consumer groups for external tools
- Monitor pending entries

---

## Retention & Performance

Retention directly impacts performance.

### Logical Retention

Applied at read time:

- Cheap
- Safe
- Does not reclaim disk

### Physical Retention (Compaction)

- Rewrites storage
- Reclaims space
- More expensive

**Guideline**

> Use logical retention always.
> Use compaction periodically.

---

## Scan Performance

Startup and health scans are intentionally **sampled**.

Controlled by:

- `scan_sample_size`
- Backend implementation

This guarantees:

- Startup does not degrade with data size
- Corruption is detected probabilistically, not exhaustively

---

## Metrics-Driven Tuning

Never tune blind.

Key metrics to watch:

- `records_written`
- `bytes_written`
- `scans`
- `scan_errors`
- `compactions`
- `write_errors`

### Warning Signals

| Symptom | Likely Cause |
|------|------------|
| Rising scan errors | Corruption or partial writes |
| High compaction time | Retention too loose |
| Rapid file growth | Missing compaction |
| Redis pending growth | Consumers not acking |

---

## What *Not* To Do

- ❌ Disable scans
- ❌ Remove retention
- ❌ Run compaction continuously
- ❌ Read entire history repeatedly
- ❌ Ignore metrics

These actions usually hide problems rather than solve them.

---

## Real‑World Tuning Scenarios

### High Write Volume System

- Use Rotating or Redis backend
- Enable retention by count
- Compact off‑peak
- Avoid full history reads

### Audit‑Heavy System

- Increase retention limits
- Separate inspection tooling
- Sample reads

### External Analytics via Redis

- Use consumer groups
- Monitor pending entries
- Ack aggressively

---

## Final Advice

Performance tuning in Papyra is **deliberate**, not reactive.

If you remember one thing:

> **If performance matters, metrics come first.**

Only tune what you can observe.
