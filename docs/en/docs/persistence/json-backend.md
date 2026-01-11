# JSON Persistence Backend

The JSON persistence backend is the reference file-based durability layer in Papyra.

It provides a transparent, append-only persistence mechanism that is easy to inspect,
debug, recover, and reason about. This backend is intentionally simple by design,
while still supporting advanced operational features such as retention policies,
anomaly detection, recovery, compaction, metrics, and CLI tooling.

This backend is suitable for:

- Local development
- Single-node deployments
- Debugging and auditing
- Small to medium production workloads where simplicity and transparency matter

It is not intended to replace databases or distributed log systems.

---

## Design Philosophy

The JSON backend follows four strict principles:

1. **Append-only durability**: All records are written sequentially. Existing data is never modified in place.
2. **Crash safety**: Partial writes, truncated lines, and malformed JSON are expected failure modes  and are explicitly handled by scan and recovery logic.
3. **Human inspectability**: Data is stored as newline-delimited JSON (NDJSON) and can be inspected using standard tools such as `cat`, `less`, `jq`, or text editors.
4. **Operational correctness over performance**: Predictable behavior and recoverability are prioritized over raw throughput.

---

## File Format (NDJSON)

Each line in the persistence file represents **one immutable record**.

Example:

```json
{"kind": "event", "timestamp": 1710000000.123, "actor": "user/123", "type": "UserCreated", "payload": {...}}
{"kind": "audit", "timestamp": 1710000001.456, "action": "spawn", "actor": "worker/7"}
{"kind": "dead_letter", "timestamp": 1710000002.789, "reason": "no_handler"}
```

Key properties:

- Each record occupies **exactly one line**
- Records are written using `fsync` semantics (backend-dependent)
- A corrupted or partial line does not affect previous valid records

---

## Supported Record Types

The backend persists multiple logical categories:

| Kind          | Purpose |
|---------------|--------|
| `event`       | Actor-level events |
| `audit`       | System-level lifecycle actions |
| `dead_letter` | Undeliverable messages |
| `metric`      | Optional metrics snapshots |

The `kind` field is mandatory and drives classification during scans and inspection.

---

## Retention Policies

The JSON backend supports retention via a pluggable retention policy.

Retention is **logical**, not physical:

- Old records are ignored at read time
- Files are compacted separately to reclaim disk space

Supported retention constraints include:

- Maximum record count
- Maximum age (seconds)
- Maximum total file size

Example configuration:

```python
from papyra.persistence.backends.retention import RetentionPolicy

policy = RetentionPolicy(
    max_records=1_000_000,
    max_age_seconds=7 * 24 * 3600,
)
```

Retention is enforced during:

- Reads
- Startup checks
- Compaction

---

## Scanning and Anomaly Detection

The backend supports structural scanning via `scan()`.

A scan detects:

- Truncated JSON lines
- Malformed JSON
- Unknown record kinds
- Structural inconsistencies

Example CLI usage:

```bash
papyra persistence scan --path events.ndjson
```

Possible outcomes:

- **Healthy** → exit code 0
- **Anomalies detected** → exit code 2 with details

Anomalies never modify data automatically.

---

## Recovery Modes

When anomalies are detected, recovery can be explicitly triggered.

### Repair Mode (default)

- Drops corrupted or partial lines
- Preserves all valid preceding records
- Rewrites the file safely

```bash
papyra persistence recover --path events.ndjson
```

### Quarantine Mode

- Moves corrupted files to a quarantine directory
- Rewrites a clean file
- Preserves evidence for forensic analysis

```bash
papyra persistence recover \
  --mode quarantine \
  --quarantine-dir ./quarantine \
  --path events.ndjson
```

Quarantine mode **requires** an explicit directory.

---

## Compaction

Because the backend is append-only, disk usage can grow indefinitely.

Compaction:

- Applies retention rules
- Rewrites the file atomically
- Removes expired or ignored records
- Shrinks disk usage safely

CLI example:

```bash
papyra persistence compact --path events.ndjson
```

Compaction guarantees:
- No data loss within retention limits
- Atomic replacement
- Crash-safe behavior

---

## Inspection

The `inspect` command provides a high-level overview of the backend state.

```bash
papyra persistence inspect --path events.ndjson
```

Output includes:

- Backend type
- Retention configuration
- Sampled counts of events, audits, dead letters
- Optional metrics snapshot

This command is **read-only** and safe to run in production.

---

## Metrics Support

If metrics are enabled, the backend exposes internal counters such as:

- Writes performed
- Reads performed
- Scan operations
- Recovery attempts
- Compactions

Metrics can be displayed via:

```bash
papyra persistence inspect --show-metrics
```

Metrics are backend-local and reset on process restart.

---

## Performance Characteristics

| Aspect | Behavior |
|------|---------|
| Writes | Sequential, O(1) |
| Reads | Linear scan (bounded by retention) |
| Startup | Scan cost proportional to file size |
| Recovery | Linear rewrite |
| Compaction | Linear rewrite |

This backend scales **vertically**, not horizontally.

---

## When to Use This Backend

Recommended:

- Development and testing
- Single-node actor systems
- Debugging production issues
- Auditing and traceability

Not recommended:

- High-throughput distributed systems
- Multi-writer scenarios
- Very large datasets requiring indexed queries

---

## Summary

The JSON persistence backend is the **foundation** of Papyra's durability model.

It trades raw performance for:
- Predictability
- Recoverability
- Transparency
- Operational confidence

For many systems, this tradeoff is not a limitation — it is a feature.
