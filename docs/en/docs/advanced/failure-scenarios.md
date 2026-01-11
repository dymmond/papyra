# Failure scenarios

This page describes the most common failure modes you can encounter when running Papyra, what Papyra **does** and **does not** guarantee, and what you should do operationally when something goes wrong.

Papyra has two broad “failure domains”:

1. **Actor runtime failures** (exceptions, restarts, supervision decisions).
2. **Persistence failures** (truncated/corrupted logs, storage connectivity issues, recovery/compaction).

The goal of this guide is to make these failure domains predictable.

---

## What Papyra guarantees

### Actor runtime guarantees

- **Single-threaded message handling per actor**: an actor processes messages one at a time.
- **Supervision is deterministic**: for a given supervision policy and failure, the resulting decision (STOP/RESTART/ESCALATE) is applied consistently.
- **Actor lifecycle hooks are isolated**: exceptions in `on_start()`/`receive()`/`on_stop()` are handled through supervision logic.

### Persistence guarantees

Papyra persistence is **append-only** and treated as **observability**, not as primary application state.

- Persistence operations are **best-effort**: writes are attempted without crashing the runtime.
- **Startup checks can be enforced**: when enabled, the actor system can refuse to start if persistence is unhealthy.
- **Recovery is explicit and controllable**: you decide whether to ignore, fail, repair, or quarantine.
- **Compaction is explicit**: disk/stream trimming never happens automatically.

!!! Tip "Important"
    Papyra does not provide exactly-once persistence semantics. Treat persistence records as an
    *audit trail* and *debugging / ops* substrate.

---

## What Papyra does NOT guarantee

- **No atomic “event + actor state” transaction**. Persistence is not event-sourcing.
- **No guaranteed persistence ordering across concurrent actors**.
- **No guarantee that a persistence backend is always available** (network partitions, Redis outages, disk errors).
- **No automatic, silent data deletion**: retention is applied logically on reads and physically only when you run compaction.

---

## Failure domain 1: Actor failures

### Scenario A: An actor raises in `receive()`

**Symptom**

- You see an `ActorCrashed` event in the event log.
- The actor may stop or restart depending on its supervision policy.

**What happens**

- The actor's exception is routed through supervision.
- If the message was sent via request-reply (`ask` style), the caller receives the error.

**What to do**

- Inspect recent events:

```bash
papyra inspect events --limit 50 --reverse
```

- Inspect the last audit snapshot:

```bash
papyra inspect summary
```

- Check dead letters for undelivered follow-up messages:

```bash
papyra inspect dead-letters --reverse --limit 50
```

---

### Scenario B: An actor raises in `on_start()`

**Symptom**

- The actor never becomes “started”.
- You may see failure events.

**What happens**

- Papyra treats `on_start()` failures as startup failures.
- Supervision logic is applied; the actor may be restarted or stopped.

**What to do**

- Prefer moving IO-heavy initialization into `on_start()` (correct), but ensure it is resilient.
- Wrap external calls in retries/backoff if appropriate.

---

### Scenario C: Restart storms

**Symptom**

- An actor repeatedly restarts.

**What happens**

- Restarts are rate-limited using the supervision policy window and max restarts.
- When the limit is exceeded, the actor is stopped.

**What to do**

- Inspect the supervision policy on the failing actor.
- Reduce the restart rate or switch to STOP to avoid cascading failures.
- Use audits to understand system-level impact.

---

## Failure domain 2: Persistence failures

Persistence is where “unpleasant reality” shows up:

- disk truncations
- partial writes
- corrupted JSON
- Redis payloads that are not valid JSON
- orphaned rotated files

Papyra provides three primary tools:

- **scan**: detect anomalies (read-only)
- **recover**: repair or quarantine
- **compact**: reclaim physical space (explicit)

And one orchestrator:

- **doctor**: run a startup-style scan/recovery cycle without starting actors

---

## Scenario D: Truncated JSON line (file backends)

This is the most common failure for NDJSON logs.

**Example**

A process crashes mid-write:

```json
{"kind":"event","timestamp":1}\n
{"kind":"event"
```

**How Papyra detects it**

- File-based scan checks for missing final newline (`TRUNCATED_LINE`) and invalid JSON (`CORRUPTED_LINE`).

**Recommended response**

- Repair in place:

```bash
papyra persistence recover --mode repair --path ./events.ndjson
```

or quarantine the original before rewriting:

```bash
papyra persistence recover --mode quarantine --quarantine-dir ./quarantine --path ./events.ndjson
```

---

## Scenario E: Rotating logs contain orphaned files

**Symptom**

- You find unexpected files next to the rotation set.

**How Papyra detects it**

- Rotating scan compares existing files vs the expected rotation set.

**Recommended response**

- Quarantine unexpected files:

```bash
papyra persistence recover --mode quarantine --quarantine-dir ./quarantine --path ./rot.log
```

---

## Scenario F: Startup refuses to run because persistence is unhealthy

This happens only if you enable startup checks (recommended for production).

**Symptom**

- `ActorSystem.start()` raises a `RuntimeError` when `FAIL_ON_ANOMALY` is enabled.

**What to do**

- Use the CLI to reproduce the same behavior without starting actors:

```bash
papyra doctor run --mode fail_on_anomaly --path ./events.ndjson
```

- Or enable recovery mode:

```bash
papyra doctor run --mode recover --recovery-mode repair --path ./events.ndjson
```

---

## Scenario G: Recovery runs, but anomalies remain

**Symptom**

- Recovery completes, but a post-scan still reports anomalies.

**What happens**

- Papyra treats this as a hard failure in strict startup modes.
- The `doctor` command exits non-zero.

**Recommended response**

1. Run scan to list anomalies clearly:

```bash
papyra persistence scan --path ./events.ndjson
```

2. Run quarantine recovery (preserve the original):

```bash
papyra persistence recover --mode quarantine --quarantine-dir ./quarantine --path ./events.ndjson
```

3. If anomalies persist, keep the quarantined files and open an issue with the scan output.

---

## Scenario H: Compaction surprises

Compaction is explicit, but can still surprise you if you expect it to behave like retention.

**Key concept**

- Retention is typically **logical** (applied at read time).
- Compaction makes retention **physical** by rewriting/trimming storage.

**Recommended response**

- Always run compaction deliberately:

```bash
papyra persistence compact --path ./events.ndjson
```

- Verify before/after sizes via the compaction report output.

---

## Redis-specific scenarios

### Scenario I: Redis is unreachable during writes

**Symptom**

- Writes may fail.
- Metrics error counters may increase.

**What happens**

- Writes are best-effort.
- If exceptions propagate from your backend implementation, they may be suppressed by the actor system's persistence scheduling.

**What to do**

- Monitor persistence metrics:

```bash
papyra metrics persistence
```

- Verify Redis connectivity externally.

---

### Scenario J: Redis stream contains corrupted payloads

**Symptom**

- `scan()` reports anomalies for missing/invalid JSON in stream entries.

**What to do**

- Repair (delete bad entries):

```bash
papyra doctor run --mode recover --recovery-mode repair
```

- Quarantine (copy bad entries into quarantine streams first):

```bash
papyra doctor run --mode recover --recovery-mode quarantine --quarantine-dir ./quarantine
```

---

### Scenario K: Consumer group processing crashes

This affects external tools consuming streams (shipping/analytics), not the actor system's writes.

**Symptom**

- Entries become pending.

**What happens**

- Redis consumer groups provide **at-least-once** delivery.
- If a consumer crashes before ACK, messages remain pending.

**What to do**

- Inspect pending summary (programmatically, via your integration) and decide whether to:
  - ACK
  - CLAIM (transfer ownership to another consumer)
  - reprocess

Papyra exposes helper methods for consumer groups on the Redis backend.

---

## Operational playbooks

### “Something is broken” checklist

**Scan** the persistence backend:

```bash
papyra persistence scan
```

If anomalies exist:

- For production, prefer quarantine recovery:

```bash
papyra persistence recover --mode quarantine --quarantine-dir ./quarantine
```

Run doctor to validate:

```bash
papyra doctor run --mode fail_on_anomaly
```

Once healthy, optionally compact to reclaim space:

```bash
papyra persistence compact
```

Inspect events/audits/dead-letters to confirm expected behavior:

```bash
papyra inspect summary
papyra inspect events --limit 50 --reverse
papyra inspect dead-letters --limit 50 --reverse
```

---

## Choosing a startup strategy

In production, you typically want one of these:

- **fail_on_anomaly**: safest; never start in a corrupted state.
- **repair (REPAIR)**: auto-heal in place.
- **recover (QUARANTINE)**: auto-heal but preserve corrupted data.

For local/dev:

- **ignore**: fastest; don't block iteration.

---

## Summary

- Actor failures are handled by supervision.
- Persistence failures are handled by scan/recover/compact.
- Startup checks and doctor let you enforce safety.
- Redis consumer groups are for external tools and provide at-least-once semantics.

If you want Papyra to be boring in production (the best kind of runtime), enable startup checks, monitor metrics, and treat recovery/compaction as deliberate operator actions.
