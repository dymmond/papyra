# Exit codes

Papyra's CLI commands are designed to be automation-friendly.

That means they don't just print messages — they also return **stable, meaningful process exit codes** so that:

- CI pipelines can fail fast
- Kubernetes init containers can block startup safely
- cron jobs can alert on real corruption
- operators can distinguish **“clean”** vs **“needs attention”** vs **“misconfigured”**

This page is the **contract** for those exit codes.

---

## Conventions

- **0** means “success” (or “nothing to do”).
- **Non-zero** means “attention required.”
- “Invalid CLI usage” (unknown flags, bad argument syntax) is handled by the CLI framework and may return a framework-defined non-zero code.
    - Treat these as **misconfiguration**.

---

## Doctor command

Command:

```bash
papyra doctor run [--mode ...] [--recovery-mode ...] [--quarantine-dir ...] [--path ...]
```

`doctor` is a pre-flight tool: it runs scan/recovery **without starting actors**.

### `doctor run` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Healthy OR recovery succeeded | No anomalies, or recovery succeeded and post-scan is clean |
| 1 | Anomalies detected and **FAIL_ON_ANOMALY** mode requested | Corruption/truncation/orphans detected |
| 2 | Recovery attempted but anomalies still remain | Recovery could not fully repair the storage |

Notes:

- If `--mode IGNORE` is used and anomalies exist, the command **still exits 0** by design.
    - This mode is for “report-only” runs where you don't want to block automation.
- If `--mode RECOVER` and `--recovery-mode QUARANTINE` are used without `--quarantine-dir`, the command exits non-zero due to **invalid configuration**.
    - Treat this as misconfiguration.

---

## Persistence command group

Commands:

```bash
papyra persistence scan
papyra persistence recover
papyra persistence startup-check
papyra persistence compact
papyra persistence inspect
```

### `persistence scan` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Clean scan | No anomalies detected |
| 2 | Scan completed and anomalies detected | Truncated line, corrupted JSON, orphaned rotated file, etc. |

Notes:

- If the backend does not support scanning, the command exits **0** and prints an informational message.

### `persistence recover` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Recovery completed | Repairs applied (or no actionable work), command executed successfully |

Notes:

- If `--mode quarantine` is used without `--quarantine-dir`, the command exits non-zero due to **invalid configuration**.
- Some backends may report “no recovery needed” and still exit 0.

### `persistence startup-check` exit codes

`startup-check` simulates the same scan/recovery decision logic used by `ActorSystem.start()`.

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Startup check passed | Scan clean OR recovery succeeded (when requested) |
| 1 | FAIL_ON_ANOMALY requested and anomalies exist | Corruption found and strict mode enabled |

Notes:

- If `--mode recover` is used, the command attempts recovery then prints **“Recovery successful”** and exits 0.
- If invalid `--mode` or invalid `--recovery-mode` values are provided, the command exits non-zero as **misconfiguration**.

### `persistence compact` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Compaction completed | Compaction succeeded OR backend is a no-op |

Notes:

- Some backends return a structured `CompactionReport`, others return a dict or `None`.
- This command is best-effort: it is intended for maintenance automation.

### `persistence inspect` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Inspect completed | Always returns info unless CLI invocation fails |

Notes:

- `inspect` is observational. It should not mutate storage.

---

## Metrics command group

Commands:

```bash
papyra metrics persistence
papyra metrics reset
```

### `metrics persistence` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Metrics printed | Backend supports metrics OR command degrades gracefully |

Notes:

- If a backend does not expose metrics, Papyra prints an informational message but still exits 0.

### `metrics reset` exit codes

| Exit code | Meaning | Typical cause |
|---:|---|---|
| 0 | Metrics reset performed | Metrics were reset on the active backend |

---

## How to use exit codes in automation

### CI: fail on anomalies

```bash
papyra persistence scan --path ./events.ndjson
```

- exit 0 → proceed
- exit 2 → fail the job, upload artifacts

### Kubernetes init container: strict startup

Use `doctor run --mode fail_on_anomaly`:

```bash
papyra doctor run --mode fail_on_anomaly --path /data/events.ndjson
```

- exit 0 → allow the pod to start
- exit 1 → block startup (data is corrupted)

### Kubernetes init container: auto-repair

```bash
papyra doctor run --mode recover --recovery-mode repair --path /data/events.ndjson
```

- exit 0 → recovery succeeded (or storage was already clean)
- exit 2 → recovery couldn't fully fix it (requires manual intervention)

### Cron: quarantine then alert

```bash
papyra persistence recover --mode quarantine --quarantine-dir /data/quarantine --path /data/events.ndjson
```

Recommended follow-up:

- run `persistence scan` again
- alert if scan still returns 2

---

## Summary

If you remember only one thing:

- **0** = safe
- **2** = corruption/anomaly detected (or recovery incomplete)

Use these codes to make Papyra deployments and operations **deterministic**.
