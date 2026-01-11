# Compaction Scheduling

This document explains how to **safely schedule, automate, and operate persistence compaction**
in Papyra deployments.

Compaction is **not optional** in production. Retention defines *what should no longer exist*;
compaction is the mechanism that **physically removes it**.

---

## What Compaction Does

Compaction is a **physical rewrite operation** that:

- Applies retention rules
- Removes dropped / expired records
- Rewrites storage into a smaller, consistent form
- Reclaims disk space
- Improves read performance over time

What compaction **does not** do:

- It does **not** change logical semantics
- It does **not** reorder events
- It does **not** mutate surviving records
- It does **not** run automatically unless you schedule it

---

## Why Scheduling Matters

Without scheduled compaction:

- Disk usage grows indefinitely
- Retention becomes a *logical illusion*
- Backup size increases over time
- Recovery scans take longer
- Cold start latency increases

With proper scheduling:

- Storage stays bounded
- Retention guarantees are enforced
- Operational costs are predictable
- Failure recovery remains fast

---

## Supported Backends

| Backend | Compaction Support | Notes |
|------|-------------------|------|
| Memory | No-op | No persistence |
| JSON | Full rewrite | Atomic replace |
| Rotating Files | Segment rewrite | Per-file compaction |
| Redis Streams | XTRIM-based | Approximate trimming |

---

## When to Run Compaction

### Recommended Intervals

| Workload | Schedule |
|-------|---------|
| Low traffic | Daily |
| Medium traffic | Every 6–12 hours |
| High traffic | Hourly |
| Redis streams | Continuous / periodic |

**Rule of thumb:**
> Compaction should run **more frequently than retention thresholds**.

---

## Scheduling Strategies

### 1. Cron-Based Scheduling (Recommended)

Use system cron or Kubernetes CronJobs.

Example (Linux cron):

```bash
0 2 * * * papyra persistence compact
```

Kubernetes CronJob:

```yaml
schedule: "0 */6 * * *"
```

---

### 2. Orchestrator-Based Scheduling

- Kubernetes Jobs
- Nomad periodic jobs
- Systemd timers

This is preferred in containerized environments.

---

### 3. Manual / Emergency Compaction

Use when:

- Disk pressure alerts fire
- After large incident recovery
- Before migrations
- Before backups

```bash
papyra persistence compact
```

---

## Compaction Safety Model

Papyra compaction is **designed to be safe by default**:

- Atomic file replacement
- Temporary files only committed on success
- Original data preserved until final swap
- Failure leaves original storage intact

If compaction fails:

- No data loss
- Next run can retry safely

---

## Interaction With Retention

Retention rules define *eligibility*.
Compaction enforces *physical deletion*.

Example:

```python
RetentionPolicy(
    max_records=10_000,
    max_age_seconds=86400
)
```

Without compaction:

- Old records still exist on disk

With compaction:

- Old records are physically removed

---

## Redis-Specific Scheduling

Redis Streams compaction uses `XTRIM`.

### Recommended Approach

- Use **approximate trimming** (`~`)
- Run compaction frequently
- Avoid large trim operations

Config:

```python
RedisStreamsConfig(
    approx_trim=True
)
```

Scheduling:

- Hourly or continuous
- Never large batch trims

---

## Metrics to Monitor

Before and after compaction, monitor:

- `records_written`
- `records_dropped`
- `compactions_run`
- `compaction_errors`
- Disk usage

CLI:

```bash
papyra metrics persistence
```

---

## Warning Signs of Misconfiguration

- Disk usage grows despite retention
- Compaction runs but size does not shrink
- Long startup scan times
- Frequent recovery scans
- Redis memory pressure

These indicate:

- Compaction not scheduled
- Retention misconfigured
- Incorrect backend assumptions

---

## Production Checklist

Before enabling compaction scheduling:

- [ ] Retention policy explicitly defined
- [ ] Compaction tested in staging
- [ ] Backups verified
- [ ] Metrics enabled
- [ ] Alerts configured for failures

---

## Recommended Defaults

| Environment | Interval |
|-----------|----------|
| Development | Manual |
| Staging | Daily |
| Production | 1–6 hours |
| Redis-heavy | Continuous / hourly |

---

## Final Guidance

> **Retention without compaction is incomplete.**

Treat compaction as a **first-class operational task**, not a maintenance afterthought.

If you schedule compaction correctly:
- Papyra remains fast
- Storage remains bounded
- Failures remain recoverable

This is non-negotiable for long-running systems.
