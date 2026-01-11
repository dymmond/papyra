# CLI Overview

Papyra ships with a **first-class command-line interface (CLI)** designed for
operators, SREs, platform engineers, and developers who need **direct control**
and **deep visibility** into the persistence layer—without starting the actor
runtime.

The CLI is not a convenience wrapper.
It is a **production-grade operational surface**.

---

## Design Philosophy

The Papyra CLI follows four strict principles:

1. **Safety First**
    - Read-only commands never mutate state
    - Destructive operations require explicit flags
    - Failures return non-zero exit codes

2. **Scriptable by Default**
    - Deterministic output
    - Stable exit codes
    - CI / automation friendly

3. **Backend-Agnostic**
    - Same commands work for JSON, Redis, rotating files, or memory
    - Behavior is delegated to the backend, not duplicated in CLI code

4. **Parity with Runtime Behavior**
    - CLI logic mirrors ActorSystem startup checks
    - No “special CLI-only” behavior

---

## Command Groups

The CLI is organized into **logical command groups**, each mapping to a core operational concern.

```
papyra
├── doctor
├── persistence
├── metrics
```

Each group is fully independent and can be used standalone.

---

## Global Behavior

### Persistence Resolution

Most commands accept an optional `--path` argument.

Resolution rules:

1. If `--path` is provided:
    - A file-backed persistence backend is instantiated directly
2. If not provided:
    - The globally configured backend (`monkay.settings.persistence`) is used

This allows:

- Offline inspection of backups
- One-off recovery operations
- Debugging production data without booting the system

---

## Exit Codes (Contract)

Exit codes are **part of the public API**.

| Code | Meaning |
|----:|--------|
| 0 | Success / healthy |
| 1 | Anomalies detected (fail-fast mode) |
| 2 | Scan failed or anomalies remain |
| 3 | Recovery incomplete |
| 4+ | Startup check failures |

Never parse output strings in automation.
Always rely on exit codes.

---

## `doctor` Command

The **Doctor** is a pre-flight diagnostic tool.

Use cases:
- Kubernetes init containers
- CI validation
- Manual health checks
- Incident response

Key modes:

- `ignore`
- `fail_on_anomaly`
- `recover`

Doctor runs:

1. Scan
2. Optional recovery
3. Post-recovery verification

See: [doctor](./doctor.md) for full details.

---

## `persistence` Command Group

The persistence group exposes **direct storage management** operations.

Available commands:

- `scan` – detect corruption
- `recover` – repair or quarantine
- `startup-check` – simulate system startup logic
- `compact` – reclaim physical storage
- `inspect` – summarize backend state

These commands are **safe to run without actors**.

---

## `metrics` Command Group

The metrics CLI exposes **live internal counters** and backend statistics.

Supports:

- Snapshot inspection
- Resetting counters
- Backend capability detection

Metrics are:

- In-memory
- Zero overhead when unused
- Optional per backend

---

## Automation Examples

### CI Preflight Check

```bash
papyra doctor run --mode fail_on_anomaly
```

Fail the pipeline immediately if corruption is detected.

---

### Scheduled Compaction

```bash
papyra persistence compact
```

Run nightly to reclaim disk space.

---

### Offline Backup Validation

```bash
papyra persistence scan --path backups/events.ndjson
```

Validate backups without restoring them.

---

## What the CLI Is *Not*

- ❌ Not a debugging REPL
- ❌ Not a configuration generator
- ❌ Not tied to a specific backend
- ❌ Not required at runtime

It is an **operational interface**, not a development crutch.

---

## Summary

The Papyra CLI provides:

- Deterministic automation
- Safe recovery tooling
- Backend-independent operations
- Production-grade guarantees

If your actors never start, the CLI still works.
If your data is broken, the CLI is your first tool.
