# External Tools & Integrations

Papyra is designed to be **observable-first** and **tool-friendly**.
Rather than locking users into a proprietary monitoring or debugging stack, Papyra exposes
clear contracts and data surfaces that external tools can consume safely and efficiently.

This document explains **how Papyra integrates with external systems**, what is officially
supported, and how to build your own tooling on top of it.

---

## Design Philosophy

Papyra follows three strict principles regarding external tools:

1. **No hidden state**: Everything observable (events, audits, metrics, anomalies) is explicit and structured.

2. **Pull or push — your choice**
   You can either:
    - Pull data via APIs / persistence backends
    - Push data into external systems (metrics, logs, tracing)

3. **Zero coupling**: External tools never depend on internal actor or runtime implementation details.

This ensures:

- Long-term stability
- Safe upgrades
- Third-party extensibility

---

## Supported Integration Categories

Papyra supports (or intentionally enables) integration in the following areas:

- Metrics & monitoring
- Persistence inspection
- Health checks & automation
- Log shipping
- Tracing & observability pipelines
- Backup, archival, and compliance tooling

Each category is described below.

---

## Metrics & Monitoring Tools

### Built-in Metrics Surface

All persistence backends may expose metrics through a **stable metrics interface**.

Examples of metrics:

- Records written
- Bytes written
- Scan operations
- Detected anomalies
- Recovery actions
- Compaction runs

These metrics are:

- Monotonic counters or gauges
- Snapshot-based
- Backend-agnostic

They can be accessed via:

- CLI (`papyra metrics ...`)
- Programmatic snapshot (`backend.metrics.snapshot()`)

---

### External Metrics Systems

Papyra does **not** hard-code a metrics backend (Prometheus, Datadog, etc.).
Instead, it allows exporting metrics to external systems.

Common patterns:

- Periodic polling and forwarding
- Direct export adapters
- OpenTelemetry metrics bridges

See:

- [OpenTelemetry](../metrics/opentelemetry.md)
- [Metrics CLI](../metrics/cli.md)

---

## OpenTelemetry Integration

OpenTelemetry is the **recommended standard** for production observability.

Papyra integrates cleanly with OpenTelemetry by:

- Exposing metrics that can be mapped to OTEL instruments
- Allowing trace/span creation around persistence operations
- Avoiding global state or implicit SDK initialization

Typical use cases:

- Export metrics to Prometheus
- Export traces to Jaeger / Tempo
- Correlate actor activity with infrastructure telemetry

!!! Warning
    1. Papyra does not bundle OpenTelemetry by default.
    2. Integration is **opt-in** and explicit.

---

## Persistence Backends as Integration Points

Persistence backends are a primary surface for external tooling.

External tools can:

- Inspect raw persistence files
- Read from Redis streams
- Consume rotated logs
- Scan for corruption or anomalies
- Perform compliance or retention audits

Backends are intentionally:

- Append-only where possible
- Structured
- Recoverable

This allows tools like:

- Backup systems
- Data pipelines
- Forensics and debugging tools
- Compliance scanners

---

## CLI as an Automation Interface

The Papyra CLI is designed to be:

- Scriptable
- Deterministic
- Machine-readable (with JSON output where applicable)

Common automation use cases:

- Kubernetes init containers
- CI/CD validation
- Pre-deployment health checks
- Scheduled maintenance jobs

**Examples**:

```bash
papyra doctor run --mode fail_on_anomaly
papyra persistence scan --path ./events.ndjson
papyra persistence compact
papyra metrics persistence --json
```

The CLI is considered a **stable external contract**.

---

## Health Checks & Supervisory Systems

External systems (Kubernetes, Nomad, systemd, etc.) can rely on Papyra's health checks:

- Startup checks
- Doctor mode
- Exit codes with semantic meaning

This allows:

- Failing fast on corrupted state
- Automatic remediation
- Safe rollouts

Recommended pattern:

- Run `doctor` or `startup-check` before starting actors
- Fail the container or service if anomalies exist

---

## Log Shipping & Event Pipelines

Papyra persistence is structured and machine-readable by design.

This enables:

- Log shippers (Fluent Bit, Vector)
- Data pipelines
- Event replay systems

Typical flow:
```
Persistence backend → external shipper → analytics / storage
```

No parsing of unstructured logs is required.

---

## Writing Your Own External Tool

If you want to build a custom tool on top of Papyra, you should rely on:

- Persistence backends
- Metrics snapshots
- CLI commands
- Explicit APIs only

You should **never**:

- Reach into actor internals
- Depend on private attributes
- Assume scheduling or execution order

This ensures your tool remains compatible across versions.

---

## Stability Guarantees

Papyra guarantees stability for:

- CLI commands and exit codes
- Persistence formats (within documented evolution rules)
- Metrics field names (once released)
- Backend extension contracts

Breaking changes are:
- Documented
- Versioned
- Announced

---

## Summary

Papyra is not just an actor framework — it is a **system-grade runtime**.

External tools are:

- First-class citizens
- Explicitly supported
- Encouraged

If you can observe it, inspect it, or automate it — Papyra wants you to.
