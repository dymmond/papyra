# Persistence CLI

The `persistence` command group provides **direct operational control** over Papyra's
persistence layer. These commands are designed for operators, SREs, and advanced users
who need to **inspect, validate, repair, or maintain** persisted actor data outside of
normal runtime execution.

Unlike the `doctor` command, which is opinionated and safety-focused, the `persistence`
CLI is **explicit and imperative**: you tell it exactly what to do, and it does it.

---

## Command Overview

```bash
papyra persistence <command> [options]
```

Available subcommands:

- `scan` – Detect structural anomalies
- `recover` – Repair or quarantine corrupted data
- `startup-check` – Simulate startup validation logic
- `compact` – Physically compact persistence storage
- `inspect` – Summarize backend configuration and data volume

Each command operates either on:

- the **globally configured persistence backend**, or
- a **specific file path** provided via `--path`

---

## Common Concepts

### Path Override (`--path`)

Most persistence commands accept a `--path` option:

```bash
papyra persistence scan --path ./events.ndjson
```

When provided:

- The global application persistence is **ignored**
- A temporary file-based backend is instantiated
- No configuration changes are persisted globally

This is ideal for:

- Offline inspection
- Backups
- Incident forensics
- CI/CD preflight checks

---

## `scan`

Perform a **read-only structural integrity check**.

```bash
papyra persistence scan [--path PATH]
```

### What it detects

- Truncated or malformed records
- Corrupted JSON lines
- Orphaned or inconsistent persistence artifacts

### Exit Codes

| Code | Meaning |
|-----:|--------|
| 0 | Scan clean |
| 2 | Anomalies detected |

### Example

```bash
papyra persistence scan --path events.ndjson
```

If anomalies are found, each is reported with:

- anomaly type
- affected path
- human-readable detail

---

## `recover`

Attempt to repair detected anomalies.

```bash
papyra persistence recover [options]
```

### Options

- `--mode repair` (default)
- `--mode quarantine`
- `--quarantine-dir PATH` (required for quarantine)

### Repair Mode

```bash
papyra persistence recover --path events.ndjson
```

- Fixes records in place where possible
- Drops unrecoverable fragments
- Preserves valid data

### Quarantine Mode

```bash
papyra persistence recover \
  --mode quarantine \
  --quarantine-dir ./quarantine \
  --path events.ndjson
```

- Moves corrupted files aside
- Ensures clean state reconstruction
- Preferred for regulated or audited environments

---

## `startup-check`

Simulate **ActorSystem startup persistence validation** without starting the system.

```bash
papyra persistence startup-check [options]
```

### Options

- `--mode ignore | fail_on_anomaly | recover`
- `--recovery-mode repair | quarantine`

### Example: Fail fast

```bash
papyra persistence startup-check --mode fail_on_anomaly
```

### Example: Startup recovery

```bash
papyra persistence startup-check \
  --mode recover \
  --recovery-mode repair
```

### Exit Codes

| Code | Meaning |
|-----:|--------|
| 0 | Startup check passed |
| 4 | Anomalies detected (fail_on_anomaly) |
| 5 | Recovery attempted but failed |

This command is **CI/CD and InitContainer friendly**.

---

## `compact`

Trigger a **physical compaction** of the persistence backend.

```bash
papyra persistence compact [--path PATH]
```

### What compaction does

Backend-specific behavior:

- JSON / rotating logs: rewrite files without obsolete records
- Redis: trim streams according to retention
- Memory: no-op

### Example

```bash
papyra persistence compact --path events.ndjson
```

This operation is **safe** and **idempotent**.

---

## `inspect`

Display a high-level snapshot of the persistence backend.

```bash
papyra persistence inspect [options]
```

### Output Includes

- Backend implementation
- Retention policy configuration
- Sampled counts:
   - events
   - audits
   - dead letters
- Optional metrics snapshot

### Options

- `--limit N` – cap sampling size
- `--show-metrics` – include metrics counters

### Example

```bash
papyra persistence inspect --show-metrics
```

This command is designed for:

- quick diagnostics
- operational dashboards
- sanity checks during incidents

---

## When to Use Which Command

| Use Case | Command |
|--------|--------|
| Pre-deploy validation | `startup-check` |
| Health monitoring | `scan` |
| Incident recovery | `recover` |
| Disk usage reduction | `compact` |
| Debug configuration | `inspect` |

---

## Operational Philosophy

The persistence CLI follows three principles:

1. **Explicitness over magic**
2. **Safe defaults**
3. **Automation-friendly exit codes**

Nothing is hidden. Nothing is implicit.
If data is modified, you explicitly asked for it.
