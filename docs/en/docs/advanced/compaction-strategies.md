# Compaction Strategies

Compaction is the **physical cleanup phase** of Papyra persistence.
Where *retention* defines **what is no longer valid**, compaction defines **when and how invalid data is physically removed**.

This document explains compaction deeply: why it exists, how it works across backends, and how to operate it safely in production.

---

## 1. Retention vs Compaction (Critical Distinction)

Papyra intentionally separates **logical retention** from **physical compaction**.

| Concept | What it does | When it runs |
|------|-------------|-------------|
| Retention | Decides which records are *expired* | During reads / scans |
| Compaction | Rewrites storage to remove expired data | Explicit operation |

!!! Tip "Important"
    Retention alone **does not shrink disk usage**. Only compaction does.

This separation guarantees:

- Deterministic reads
- Crash-safe storage
- No hidden I/O work during normal operation

---

## 2. Why Compaction Is Explicit

Many systems compact automatically. Papyra does **not**, by design.

Reasons:

- Compaction is I/O heavy
- Compaction may lock files or streams
- Operators must control *when* it happens
- Predictability > convenience

Instead, Papyra exposes compaction via:

- CLI
- API
- Operator scheduling (cron, systemd, Kubernetes jobs)

---

## 3. Backend-Specific Compaction Behavior

### 3.1 JSON File Persistence

**Mechanism**

  - Reads the source `.ndjson`
  - Applies retention rules
  - Writes a new compacted file
  - Atomically replaces the original

**Guarantees**

  - Crash-safe (temp file + rename)
  - No partial writes
  - Original file preserved until success

**Disk Impact**

  - Temporary double disk usage during compaction

**Typical Use**

```bash
papyra persistence compact
```

---

### 3.2 Rotating File Persistence

**Mechanism**

  - Iterates rotated segments
  - Drops fully expired segments
  - Rewrites partially expired segments
  - Renames safely

**Advantages**

  - Faster compaction than monolithic files
  - Natural disk locality
  - Easier recovery

**Best Practice**

  - Pair with size-based rotation
  - Compact during off-peak hours

---

### 3.3 Redis Streams

Redis does **not** support true compaction in the filesystem sense.

Papyra uses:

- `XTRIM` with retention-derived bounds
- Optional approximate trimming (`~`)

**Trade-offs**

| Mode | Behavior |
|----|---------|
| Exact | Strong guarantees, slower |
| Approximate | Faster, slightly lossy |

Compaction here means:

> “Advance the stream head to forget expired history”

---

### 3.4 In-Memory Persistence

- No-op
- Python garbage collection handles cleanup
- Compaction exists for API symmetry only

---

## 4. Compaction Triggers

Papyra **never** auto-compacts.

You trigger compaction via:

### CLI

```bash
papyra persistence compact
```

### API

```python
await system.persistence.compact()
```

### Automation

- Cron
- systemd timer
- Kubernetes Job / CronJob

---

## 5. Safe Compaction Windows

Recommended times:

- Low traffic periods
- After large retention drops
- Before backups
- After incident recovery

Avoid:

- During heavy write bursts
- During recovery operations
- While disk is near full capacity

---

## 6. Observability During Compaction

If metrics are enabled, compaction emits:

- Records scanned
- Records dropped
- Files rewritten
- Errors encountered

CLI example:

```bash
papyra metrics persistence
```

---

## 7. Failure Modes & Guarantees

### Crash During Compaction

✔ Original data preserved
✔ Temporary files discarded
✔ Safe to retry

### Disk Full

- Compaction aborts
- No data loss
- Operator must free space

### Partial Backend Support

- Backends may return `None`
- CLI reports best-effort completion

---

## 8. Compaction vs Recovery

| Operation | Purpose |
|--------|--------|
| Recovery | Fix corruption |
| Compaction | Reduce size |

**Never confuse the two.**

Recovery may *rewrite*, but its goal is correctness — not size.

---

## 9. Real-World Compaction Strategies

### High-Volume Event Systems

- Daily retention
- Weekly compaction

### Compliance Systems

- Long retention
- Monthly compaction + archive

### Embedded / Edge Systems

- Aggressive retention
- Frequent compaction

---

## 10. Design Philosophy Recap

Papyra compaction is:

- Explicit
- Predictable
- Crash-safe
- Backend-aware

You control *when* storage is rewritten — not the framework.
