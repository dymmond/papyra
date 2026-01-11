# Production Checklist

This checklist is a **practical, operational guide** for running Papyra safely and predictably in production.

It is intentionally opinionated. Every item exists because it prevents a real failure mode.

Use this document:

- before first production deployment
- during incident reviews
- when onboarding new operators
- when changing persistence backends or retention policies

---

## 1. Persistence Backend Readiness

### ✅ Choose the correct backend

| Backend | Use when | Avoid when |
|------|---------|-----------|
| Memory | Tests, local development | Any restart matters |
| JSON | Small systems, simple recovery | High write throughput |
| Rotation | Long-running services | Strict ordering is required |
| Redis | Distributed systems | Redis is not operationally mature |

---

### ✅ Verify backend health before startup

Always run one of:

```bash
papyra persistence scan
```

or

```bash
papyra persistence startup-check --mode fail_on_anomaly
```

This prevents booting into a corrupted state.

---

### ❌ Never auto-ignore anomalies in production

**Forbidden configuration**:

```text
startup mode = IGNORE
```

If corruption exists, you *want to fail fast*.

---

## 2. Retention Configuration

### ✅ Explicit retention is mandatory

Production systems **must define retention**, even if generous.

At minimum, define one of:

- `max_records`
- `max_age_seconds`
- `max_total_bytes`

Leaving retention unbounded guarantees disk exhaustion.

---

### ⚠️ Retention ≠ deletion

Retention:

- marks data as logically expired

Compaction:

- removes it physically

You must run **both**.

---

## 3. Compaction Strategy

### ✅ Schedule compaction

Examples:

```bash
papyra persistence compact
```

Recommended cadence:

- JSON / Rotation: daily
- Redis: weekly (or via XTRIM)
- High-throughput systems: off-peak hours

---

### ⚠️ Validate compaction impact

After compaction:

- disk usage should decrease
- metrics should reflect reclaimed data
- no anomalies should appear on scan

Always verify with:

```bash
papyra persistence scan
```

---

## 4. Startup Safety

### ✅ Use startup-checks in orchestration

Kubernetes / systemd should block startup unless:

- persistence scan is clean
- or recovery succeeded fully

Example:

```bash
papyra persistence startup-check --mode recover --recovery-mode repair
```

---

### ❌ Do not combine recovery with live traffic

Recovery must run:

- before actors start
- without concurrent writers

Never attempt recovery during runtime.

---

## 5. Metrics & Observability

### ✅ Enable metrics early

Metrics are not optional in production.

Monitor at least:

- write counts
- retention drops
- compaction runs
- error counters

---

### ✅ Integrate external monitoring

Recommended:

- OpenTelemetry
- Prometheus-compatible exporters
- Centralized log aggregation

Metrics should answer:

- Is data being dropped?
- Is compaction effective?
- Is recovery happening unexpectedly?

---

## 6. Redis-Specific Checks (If Applicable)

### ✅ Consumer group hygiene

Verify:

- pending count trends toward zero
- no abandoned consumer groups
- claim logic is exercised under failure

Use:

```bash
papyra inspect events
```

---

### ⚠️ Redis memory pressure

Ensure Redis:

- has eviction policy defined
- is not shared with unrelated workloads
- has persistence configured (AOF / RDB)

---

## 7. Failure Handling Readiness

### ✅ Validate failure scenarios

At least once, test:

- truncated persistence files
- Redis restarts
- unacked consumer messages
- compaction during retention pressure

Use:

```bash
papyra doctor run --mode fail_on_anomaly
```

---

### ❌ Never silence failures

If `doctor` reports anomalies:

- stop the system
- investigate
- recover explicitly

Silent corruption is worse than downtime.

---

## 8. Operational Defaults (Recommended)

| Setting | Recommendation |
|------|----------------|
| Startup mode | FAIL_ON_ANOMALY |
| Recovery mode | REPAIR |
| Retention | Explicit |
| Compaction | Scheduled |
| Metrics | Enabled |
| Redis | Isolated instance |

---

## 9. Pre-Release Gate

Before releasing a new version:

- [ ] Run persistence scan
- [ ] Run compaction
- [ ] Verify metrics snapshot
- [ ] Confirm retention thresholds
- [ ] Simulate failure recovery
- [ ] Validate startup-check behavior

---

## 10. Final Rule

> **If you cannot explain what happens when persistence breaks, you are not production-ready.**

Papyra gives you the tools.
This checklist ensures you actually use them.
