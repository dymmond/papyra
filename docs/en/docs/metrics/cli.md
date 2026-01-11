# Metrics CLI

Papyra exposes persistence and runtime metrics through a dedicated command-line interface.
This CLI is designed for **operators, SREs, and developers** who need immediate visibility
into system behavior without attaching debuggers or dashboards.

The metrics CLI is **read-only by default**, safe to run in production, and integrates
directly with the active persistence backend.

---

## Command Group

All metrics-related commands live under:

```bash
papyra metrics
```

Run the command without arguments to see available subcommands:

```bash
papyra metrics --help
```

---

## `metrics persistence`

Displays a snapshot of persistence-level metrics collected by the active backend.

```bash
papyra metrics persistence
```

### What it shows

Depending on the backend, this command may include:

- Records written
- Read operations
- Write errors
- Scan anomalies
- Recovery actions
- Compaction runs
- Retention drops

Example output:

```shell
records_written: 12450
records_read: 12001
write_errors: 0
scan_anomalies: 2
recovery_repairs: 1
compactions: 3
```

### Notes

- Metrics are **counters**, not gauges.
- Values are monotonic since process start (unless reset).
- Backends without metrics support will report:

```shell
metrics: <unavailable>
```

---

## `metrics reset`

Resets all persistence metrics **in-memory**.

```bash
papyra metrics reset
```

### When to use

- Before a benchmark or load test
- After a deployment
- To isolate a specific operational window

### Important

- This does **not** affect persisted data.
- Metrics reset is **process-local**.
- Restarting the process also resets metrics.

Example:

```bash
papyra metrics reset
papyra metrics persistence
```

---

## `metrics json`

Outputs the same metrics snapshot in machine-readable JSON format.

```bash
papyra metrics persistence --json
```

Example output:

```json
{
  "records_written": 12450,
  "records_read": 12001,
  "write_errors": 0,
  "scan_anomalies": 2,
  "recovery_repairs": 1,
  "compactions": 3
}
```

### Use cases

- CI pipelines
- Shell scripts
- Exporting to monitoring agents
- Debugging automation

---

## Backends and Support Matrix

| Backend              | Metrics Supported |
|---------------------|-------------------|
| Memory              | Yes               |
| JSON File           | Yes               |
| Rotating Files      | Yes               |
| Redis Streams       | Yes               |
| Custom Backends     | Optional          |

Custom backends must implement the metrics mixin to appear here.

---

## Operational Philosophy

The metrics CLI is intentionally:

- **Pull-based** (no background exporters)
- **Backend-owned** (no global registry)
- **Side-effect free**
- **Predictable**

This makes it ideal for:
- Kubernetes exec probes
- SSH-based diagnostics
- Cron-based health sampling
- Incident response

---

## Relationship to Observability Systems

The metrics CLI is **not a replacement** for Prometheus, OpenTelemetry, or dashboards.

Instead, it provides:

- Immediate introspection
- Zero-config visibility
- Ground truth during failures
- Debugging when telemetry pipelines are broken

For integration with external observability tools, see:

- `metrics/overview.md`
- OpenTelemetry integration guide

---

## Common Pitfalls

### Metrics are zero

- No writes occurred yet
- Backend does not support metrics
- Metrics were recently reset
- Process was restarted

### Metrics differ from persisted size

Metrics track **operations**, not storage size.
Use:

```bash
papyra persistence inspect
```

to inspect retained data.

---

## Summary

The metrics CLI gives you:

- Fast insight
- Operational confidence
- Production-safe diagnostics

It is designed to work **when everything else fails**.
