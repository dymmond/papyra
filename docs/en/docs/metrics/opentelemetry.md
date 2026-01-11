# OpenTelemetry Integration

Papyra is designed to integrate cleanly with **OpenTelemetry (OTel)** without forcing
any specific observability stack or vendor. This page explains how Papyra's metrics,
traces, and lifecycle events map to OpenTelemetry concepts and how to wire them into
real-world monitoring systems.

This document assumes basic familiarity with OpenTelemetry concepts such as
**meters**, **traces**, **spans**, and **exporters**.

---

## Why OpenTelemetry in Papyra?

Distributed actor systems are inherently difficult to observe:

- Actors are asynchronous and short-lived
- Failures propagate through supervision trees
- Message flow is non-linear
- Persistence is append-only and often external

OpenTelemetry provides a **vendor-neutral standard** to:
- Export metrics to Prometheus, Datadog, Grafana, etc.
- Correlate persistence operations with failures
- Observe system health without tight coupling

Papyra intentionally does **not** embed an OpenTelemetry SDK.
Instead, it exposes **stable metrics and lifecycle hooks** that can be
bridged into OpenTelemetry by the application.

This keeps Papyra:

- Lightweight
- Dependency-minimal
- Compatible with any observability stack

---

## What Papyra Exposes

Papyra provides **structured metrics snapshots** and **well-defined lifecycle points**
that are ideal for OpenTelemetry instrumentation.

### Persistence Metrics

Available via:

```python
backend.metrics.snapshot()
```

Metrics include:

- `writes_total`
- `write_errors`
- `bytes_written`
- `scan_count`
- `scan_anomalies`
- `recover_count`
- `compact_count`

These map naturally to **OTel Counters and Gauges**.

---

### Actor System Lifecycle Events

Key lifecycle moments suitable for tracing:

- Actor spawn
- Actor stop
- Message receive
- Supervision decisions
- Persistence writes
- Recovery operations

These can be wrapped in **OTel spans** by the application.

---

## Metrics → OpenTelemetry Mapping

### Example Mapping Table

| Papyra Metric | OTel Instrument |
|--------------|----------------|
| writes_total | Counter |
| write_errors | Counter |
| bytes_written | Counter |
| scan_anomalies | Counter |
| compact_count | Counter |
| alive_actors | Observable Gauge |
| registry_size | Observable Gauge |

Papyra does not assume how often metrics are scraped.
You control the polling interval.

---

## Minimal OpenTelemetry Metrics Integration

### Install Dependencies

```bash
pip install opentelemetry-sdk opentelemetry-exporter-prometheus
```

---

### Create an OTel Meter

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader

reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("papyra.persistence")
```

---

### Bridge Papyra Metrics

```python
def export_papyra_metrics(backend):
    snap = backend.metrics.snapshot()

    for name, value in snap.items():
        counter = meter.create_counter(
            name=f"papyra_{name}",
            description=f"Papyra metric: {name}",
        )
        counter.add(value)
```

You can call this periodically using:

- Async task
- Scheduler
- Background thread
- Prometheus scrape callback

---

## Tracing with OpenTelemetry

Papyra does not emit traces by default.

This is intentional.

Instead, **you control trace boundaries**.

### Example: Tracing Message Handling

```python
from papyra import Actor
from opentelemetry import trace

tracer = trace.get_tracer("papyra.actors")

class MyActor(Actor):
    async def receive(self, message):
        with tracer.start_as_current_span("actor.receive"):
            ...
```

---

### Example: Tracing Persistence Writes

```python
async def persist_with_trace(backend, event):
    with tracer.start_as_current_span("persistence.write"):
        await backend.record_event(event)
```

This approach avoids:

- Hidden spans
- Excessive cardinality
- Vendor lock-in

---

## Correlating Metrics and Traces

Best practice:

- Use **trace_id** as a log field
- Attach actor address as span attributes
- Attach persistence backend name as attributes

Example:

```python
span.set_attribute("actor.address", self.context.self_ref.address)
span.set_attribute("persistence.backend", type(backend).__name__)
```

---

## Prometheus Example

If you use Prometheus:

```bash
curl http://localhost:8000/metrics
```

You will see:

```shell
papyra_writes_total 1243
papyra_scan_anomalies 0
papyra_compact_count 2
```

These metrics are safe to:

- Alert on
- Aggregate
- Visualize

---

## What Papyra Intentionally Does NOT Do

Papyra does **not**:

- Ship an OpenTelemetry SDK
- Auto-create spans
- Export metrics automatically
- Enforce metric naming
- Enforce cardinality limits

These decisions are deliberate.

Observability belongs at the **application boundary**, not the framework core.

---

## Recommended Observability Architecture

```
Papyra
  ├── Metrics Snapshot
  ├── Actor Lifecycle Hooks
  └── Persistence Hooks
        ↓
OpenTelemetry SDK
        ↓
Collector
        ↓
Prometheus / Grafana / Datadog
```

---

## Common Pitfalls

### ❌ Emitting metrics per message

Avoid high-cardinality metrics (actor IDs, message payloads).

### ❌ Tracing everything

Trace **flows**, not individual messages.

### ❌ Exporting on every write

Batch or poll metrics instead.

---

## When to Use OpenTelemetry

Use OTel when:

- Running Papyra in production
- Operating multiple actor systems
- Investigating performance regressions
- Monitoring persistence health

Skip it when:

- Prototyping
- Writing unit tests
- Running locally

---

## Summary

- Papyra is **OpenTelemetry-friendly**, not OpenTelemetry-dependent
- You control instrumentation boundaries
- Metrics are stable and low-cardinality
- Tracing is explicit and intentional
- Works with any OTel-compatible backend

This design keeps Papyra **observable, debuggable, and production-ready**
without compromising simplicity.
