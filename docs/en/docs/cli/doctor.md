# Doctor CLI

The **Doctor** command is a production‑grade diagnostic and recovery tool for Papyra’s
persistence layer. It allows operators, CI pipelines, and deployment systems to **verify,
fail fast, or recover persistence state** without starting an `ActorSystem`.

This command mirrors the *exact same logic* used during system startup checks, but exposes
it explicitly through a CLI interface with clear exit codes and human‑readable output.

---

## Why the Doctor Exists

Persistence corruption is not theoretical. It happens due to:

- abrupt process termination
- disk‑full scenarios
- partial writes
- filesystem or container crashes
- manual file edits during debugging

The Doctor CLI exists to ensure that:

- corruption is detected *before* actors start
- recovery behavior is deterministic and auditable
- automation tools can reliably gate deployments

Think of `doctor` as **`fsck` for your actor system**.

---

## Command Overview

```bash
papyra doctor run [OPTIONS]
```

This command performs:

1. A **persistence scan**
2. A **decision phase** (based on mode)
3. An optional **recovery**
4. A **post‑recovery verification scan**

---

## Options

| Option | Description |
|------|------------|
| `--path PATH` | Override the configured persistence path |
| `--mode MODE` | Behavior when anomalies are found |
| `--recovery-mode MODE` | Recovery strategy when mode is `RECOVER` |
| `--quarantine-dir PATH` | Directory used when quarantine recovery is enabled |

---

## Modes of Operation

### IGNORE

```bash
papyra doctor run --mode ignore
```

- Scans persistence
- Logs anomalies
- **Exits with code 0**
- Does **not** block startup

Use this when:

- running diagnostics only
- gathering telemetry
- experimenting in non‑critical environments

---

### FAIL_ON_ANOMALY (default)

```bash
papyra doctor run
```

or explicitly:

```bash
papyra doctor run --mode fail_on_anomaly
```

Behavior:

- Scans persistence
- If anomalies are found → **exit code 1**
- No recovery is attempted

This is the **recommended default** for production.

Typical usage:

- CI pipelines
- Kubernetes init containers
- pre‑deployment hooks

---

### RECOVER

```bash
papyra doctor run --mode recover
```

In this mode the Doctor will:

1. Detect anomalies
2. Attempt recovery
3. Re‑scan persistence
4. Fail if corruption remains

If recovery does not fully resolve the issue, the command exits with **code 2**.

---

## Recovery Strategies

### Repair (default)

```bash
papyra doctor run --mode recover --recovery-mode repair
```

- Tries to repair corrupted entries in place
- Truncates partial records
- Preserves valid data

This is safe for most use cases.

---

### Quarantine

```bash
papyra doctor run \
  --mode recover \
  --recovery-mode quarantine \
  --quarantine-dir ./quarantine
```

- Corrupted files are moved aside
- Clean data is rebuilt
- Original files are preserved for forensic analysis

If `--quarantine-dir` is missing, the command **fails immediately**.

---

## Exit Codes

| Code | Meaning |
|----|-------|
| `0` | Healthy or recovery successful |
| `1` | Anomalies detected (FAIL_ON_ANOMALY) |
| `2` | Recovery attempted but anomalies remain |
| `>0` | Invalid configuration or misuse |

These exit codes are stable and designed for automation.

---

## Example: CI Gate

```bash
papyra doctor run --mode fail_on_anomaly
```

Fail your pipeline immediately if persistence is corrupted.

---

## Example: Kubernetes Init Container

```yaml
initContainers:
  - name: persistence-check
    image: myapp
    command:
      - papyra
      - doctor
      - run
      - --mode
      - recover
```

Guarantees persistence is clean *before* actors start.

---

## Relationship to Startup Checks

The Doctor CLI uses **the same scan and recovery logic** as:

- `ActorSystem` startup checks
- `persistence startup-check` CLI

The difference is **intent**:

| Tool | Purpose |
|----|--------|
| `doctor` | Human & automation diagnostics |
| `startup-check` | System boot simulation |
| `ActorSystem` | Enforced runtime safety |

---

## When to Use Doctor

Use `doctor` when you want:

- explicit control
- visibility
- predictable exit behavior
- operational confidence

If persistence matters (it does), **run Doctor**.
