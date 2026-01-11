# Health Checks & Doctor CLI

Papyra treats **persistence health as a first‑class operational concern**, not an afterthought.
Corruption, partial writes, truncated files, or incompatible formats must be detected **before**
an actor system starts processing messages.

This document explains:

- What “health” means in Papyra
- How scans, recovery, and startup checks work
- How to use the `doctor` CLI safely in real systems
- When to automate vs when to intervene manually

---

## What Is Persistence Health?

Persistence health answers one simple question:

> *Can this persistence backend be trusted to load and append data safely?*

A backend is considered **healthy** if:

- All persisted records are structurally valid
- No truncated or malformed entries exist
- The backend can guarantee forward‑only appends
- Retention and compaction rules can be applied safely

Health checks are **read‑only by default**.

---

## The Scan Phase

A **scan** inspects persistence storage without modifying it.

### What a Scan Detects

Depending on backend type, a scan may detect:

- Truncated JSON lines
- Invalid JSON payloads
- Missing required fields
- Corrupted Redis stream entries
- Inconsistent metadata

### What a Scan Never Does

- It does **not** delete data
- It does **not** repair corruption
- It does **not** rewrite files

Scans are safe to run at any time.

---

## The Doctor CLI

The `doctor` command is a **standalone pre‑flight tool**.
It runs the same health logic used during system startup, but with explicit CLI control.

```
papyra doctor run
```

By default, Doctor runs in **FAIL_ON_ANOMALY** mode.

---

## Doctor Modes

### IGNORE

```
papyra doctor run --mode ignore
```

- Scans persistence
- Reports anomalies
- Always exits with code `0`

**Use cases**

- Diagnostics
- Monitoring
- Non‑blocking CI checks

---

### FAIL_ON_ANOMALY (default)

```
papyra doctor run --mode fail_on_anomaly
```

- Scans persistence
- If anomalies exist → exits immediately with non‑zero status

**Use cases**

- Production startup gates
- Kubernetes initContainers
- CI/CD deployment checks

This mode prevents **unsafe startup**.

---

### RECOVER

```
papyra doctor run --mode recover --recovery-mode repair
```

- Scans persistence
- Attempts recovery
- Re‑scans after recovery
- Fails if anomalies remain

Recovery is **explicit** — nothing is repaired unless you ask.

---

## Recovery Modes

### REPAIR

```
--recovery-mode repair
```

- Removes corrupted records in place
- Preserves valid data
- May rewrite files or trim streams

Used when corruption is acceptable to discard.

---

### QUARANTINE

```
--recovery-mode quarantine --quarantine-dir ./quarantine
```

- Moves corrupted records aside
- Preserves original data for inspection
- Safest option for production incidents

If `--quarantine-dir` is missing, Doctor **fails immediately**.

---

## Exit Codes

Doctor uses meaningful exit codes for automation:

| Code | Meaning |
|----|----|
| 0 | Healthy or recovery successful |
| 1 | Anomalies detected (FAIL_ON_ANOMALY) |
| 2 | Recovery attempted but anomalies remain |
| non‑numeric | Invalid configuration |

---

## Relationship to Startup Checks

The Doctor CLI mirrors the internal startup logic used by `ActorSystem`.

Internally, Papyra runs:

- `scan()`
- Optional `recover()`
- Verification scan

Doctor allows you to run **the same logic manually**, before starting actors.

---

## When to Use Doctor

### Recommended

- Before deploying new versions
- Before migrating persistence formats
- As a Kubernetes initContainer
- After crashes or power loss
- Before enabling retention or compaction

### Not Required

- For in‑memory persistence
- For test environments (unless debugging corruption)

---

## Example: Safe Production Startup

```bash
papyra doctor run --mode fail_on_anomaly
papyra persistence compact
papyra start
```

This guarantees:
- No corrupted data is loaded
- Storage is compacted
- Actors only start on trusted data

---

## Design Philosophy

Doctor exists because **silent corruption is worse than downtime**.

Papyra always chooses:

- Explicit failure over silent recovery
- Human‑visible output over magic
- Deterministic exits over best‑effort guesses

If Doctor fails, it is telling you something important.

Listen to it.
