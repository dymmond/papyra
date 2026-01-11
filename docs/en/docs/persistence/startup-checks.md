# Startup Checks

Startup checks are a critical safety mechanism in Papyra.
They ensure that persisted state is **structurally valid**, **consistent**, and **recoverable** *before* an `ActorSystem` begins processing messages.

Unlike traditional systems that discover corruption only after runtime failures, Papyra treats persistence validation as a **first‑class startup concern**.

---

## Why Startup Checks Matter

Actor systems rely on persisted data for:

- Recovery after crashes
- Replay of events
- Audit history
- Dead letter inspection
- Diagnostics and observability

If corrupted persistence is loaded blindly:

- Actors may crash immediately
- Subtle state corruption can propagate
- Failures may appear non‑deterministic
- Recovery becomes harder or impossible

Startup checks prevent this by **failing early and explicitly**.

---

## What Is a Startup Check?

A startup check is a controlled sequence that:

1. **Scans** the persistence backend for anomalies
2. **Decides** what to do if anomalies are found
3. Optionally **recovers** corrupted data
4. **Verifies** the result before startup continues

This logic is used in three places:

- ActorSystem startup
- `persistence startup-check` CLI command
- `doctor run` CLI command

All three use the **same underlying rules**.

---

## PersistenceStartupMode

Startup behavior is controlled by `PersistenceStartupMode`.

### Available Modes

| Mode              | Behavior |
|-------------------|----|
| `ignore`          | Logs anomalies and continues startup |
| `fail_on_anomaly` | Fails immediately if anomalies are detected |
| `recover`         | Attempts recovery before continuing |

### Default Behavior

```shell
fail_on_anomaly
```

This default is intentionally strict.
Production systems should never silently continue with corrupted data.

---

## What Counts as an Anomaly?

An anomaly is any structural or semantic issue detected by `backend.scan()`.

Examples include:

- Truncated JSON lines
- Invalid JSON payloads
- Missing required fields
- Corrupted stream entries (Redis)
- Invalid record formats
- Unknown record kinds

Each backend defines its own scan logic, but all report anomalies uniformly.

---

## Startup Flow (Conceptual)

```
┌───────────────┐
│ Startup Begin │
└───────┬───────┘
        │
        ▼
┌──────────────────┐
│ Persistence Scan │
└───────┬──────────┘
        │
        ├── No anomalies ───────────▶ START SYSTEM
        │
        ▼
┌──────────────────────┐
│ Anomalies Detected   │
└───────┬──────────────┘
        │
        ├─ IGNORE ───────────────▶ START SYSTEM (logged)
        │
        ├─ FAIL_ON_ANOMALY ──────▶ ABORT STARTUP
        │
        ▼
┌──────────────────┐
│ RECOVER          │
└───────┬──────────┘
        │
        ▼
┌──────────────────────┐
│ Post‑Recovery Scan   │
└───────┬──────────────┘
        │
        ├─ Clean ───────────────▶ START SYSTEM
        │
        └─ Still Broken ───────▶ ABORT STARTUP
```

---

## Recovery During Startup

When using `recover` mode, Papyra applies a `PersistenceRecoveryConfig`.

### Recovery Modes

| Mode         | Description |
|--------------|----|
| `repair`     | Fix issues in place where possible |
| `quarantine` | Move corrupted records aside before repairing |

### Important Guarantees

- Recovery **never** runs implicitly unless explicitly enabled
- Recovery is always followed by a **second scan**
- Startup only continues if the system is verified clean

---

## Using Startup Checks in the CLI

### Simulate Startup Without Running Actors

```bash
papyra persistence startup-check
```

### Fail If Any Corruption Exists

```bash
papyra persistence startup-check --mode fail_on_anomaly
```

### Attempt Recovery Before Startup

```bash
papyra persistence startup-check --mode recover --recovery-mode repair
```

### Quarantine Corrupted Data

```bash
papyra persistence startup-check \
  --mode recover \
  --recovery-mode quarantine \
```

---

## Using Startup Checks Programmatically

Startup checks are automatically executed when an `ActorSystem` starts.

Example (conceptual):

```python
system = ActorSystem(
    persistence=JsonFilePersistence("events.ndjson"),
    startup_mode=PersistenceStartupMode.FAIL_ON_ANOMALY,
)
```

If anomalies are found, the system **will not start**.

---

## Relationship to the Doctor Command

| Feature | Startup Check | Doctor |
|------|------|------|
| Used during system startup | ✅ | ❌ |
| Manual diagnostics | ❌ | ✅ |
| Recovery support | ✅ | ✅ |
| Strict failure modes | ✅ | ✅ |
| Intended for automation | ✅ | ⚠️ |

Use **startup checks** for safety.
Use **doctor** for investigation and maintenance.

---

## Production Recommendations

- Use `fail_on_anomaly` in production
- Run `persistence startup-check` in CI/CD pipelines
- Use `recover` only with backups or supervision
- Never auto‑recover silently in critical systems

---

## Key Takeaways

- Startup checks are **non‑optional safety mechanisms**
- Corruption is detected *before* actors run
- Recovery is explicit, controlled, and verified
- Startup behavior is predictable and testable

Papyra fails early — so your system doesn't fail later.
