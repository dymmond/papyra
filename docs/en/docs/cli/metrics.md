
# Metrics CLI

The **metrics CLI** provides direct, human-readable access to persistence metrics collected by Papyra.
It is designed for **operators, SREs, and developers** who need immediate visibility into system behavior
without attaching external observability stacks.

Unlike inspection commands, metrics are **counters and gauges**, not data samples.
They reflect *what happened*, not *what exists*.

---

## Why Metrics Exist

Persistence metrics answer questions like:

- Are we writing data successfully?
- Are recoveries or compactions happening?
- Are errors accumulating silently?
- Is retention actively dropping data?
- Is the backend behaving as expected under load?

Metrics are:

- **Backend-local**
- **Monotonic unless reset**
- **Safe to read at any time**
- **Cheap to collect**

---

## Metrics Command Group

```bash
papyra metrics --help
```

This group exposes metrics-related subcommands.

Available commands:

- `metrics persistence`
- `metrics reset`

---

## `metrics persistence`

Display the current snapshot of persistence metrics.

```bash
papyra metrics persistence
```

### Example Output

```shell
records_written: 12420
bytes_written: 981233
write_errors: 0
scans: 3
scan_errors: 0
anomalies_detected: 1
recoveries: 1
recovery_errors: 0
compactions: 2
compaction_errors: 0
```

### What These Numbers Mean

| Metric | Meaning |
|------|--------|
| `records_written` | Total records successfully persisted |
| `bytes_written` | Approximate bytes written to storage |
| `write_errors` | Failed persistence attempts |
| `scans` | Number of persistence scans performed |
| `scan_errors` | Scan failures |
| `anomalies_detected` | Corruption or structural issues found |
| `recoveries` | Recovery attempts executed |
| `recovery_errors` | Failed recovery attempts |
| `compactions` | Compaction / vacuum runs |
| `compaction_errors` | Compaction failures |

---

## JSON Output

For automation or tooling integration:

```bash
papyra metrics persistence --json
```

This emits structured JSON suitable for scripts or ingestion.

---

## `metrics reset`

Reset all metrics counters to zero.

```bash
papyra metrics reset
```

### When to Reset Metrics

Resetting metrics is **intentional and destructive**.
Use it when:

- Starting a new benchmark run
- After maintenance windows
- Before controlled experiments
- During test isolation

### Example

```bash
papyra metrics reset
ℹ Metrics reset
```

After reset, all counters restart from zero.

---

## Backends Without Metrics

Some persistence backends may not expose metrics.

In this case:

```shell
metrics: <unavailable>
```

This is **not an error**.
It simply means the backend does not implement `PersistenceMetricsMixin`.

---

## Metrics vs Inspect vs Doctor

| Command | Purpose | Mutates Data | Uses Metrics |
|------|--------|-------------|-------------|
| `metrics` | Runtime counters | ❌ | ✅ |
| `inspect` | Configuration & sampling | ❌ | Optional |
| `doctor` | Health enforcement | ✅ (optional) | ❌ |

---

## Operational Guidance

**Good practices:**

- Read metrics regularly in production
- Alert on monotonic error counters
- Reset metrics before load tests
- Export metrics externally for long-term analysis

**Bad practices:**

- Resetting metrics automatically
- Treating metrics as audit logs
- Using metrics instead of scans

---

## Next Steps

- See **Metrics Internals** for how metrics are collected
- See **OpenTelemetry Integration** for exporting metrics
- See **External Tools** for Prometheus / Grafana usage

Metrics are not optional in production systems.
They are the *heartbeat* of your persistence layer.
