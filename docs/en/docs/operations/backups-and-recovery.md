# Backups and Recovery

This document describes **how to back up and recover Papyra persistence safely** in
production environments.

Papyra persistence is **append-only, deterministic, and replayable**. This makes
backups simpler than traditional databases, but only if you respect the correct
operational rules described here.

---

## What Needs to Be Backed Up

Papyra persistence backends store **system history**, not live state.

Depending on your backend, this includes:

### JSON / Rotating File Backends

- Event logs (`*.ndjson`)
- Audit logs
- Dead-letter logs
- Rotation segments (if enabled)

### Redis Backend

- Redis Streams keys
- Consumer group metadata
- Pending entries (PEL)

!!! Warning
    ⚠️ **You do not back up in-memory state.**
    Actors rebuild state by replaying persisted history.

---

## Backup Principles

### 1. Backups Are Snapshot-Based

Backups should capture a **point-in-time snapshot** of persistence files or Redis data.

Do **not**:

- Copy files while compaction is running
- Snapshot mid-recovery
- Truncate logs manually

### 2. Persistence Is Append-Only

This guarantees:

- Partial backups are still readable
- Recovery can skip corrupted tails
- Older backups remain valid indefinitely

---

## File-Based Backups (JSON / Rotation)

### Recommended Strategy

1. **Pause Writes (Optional but Best)**
    - Stop the ActorSystem
    - Or route traffic away

2. **Copy Persistence Files**
   ```bash
   cp -r persistence/ backups/papyra-$(date +%F)/
   ```

3. **Resume System**

### Live Backups (Advanced)

If stopping is not possible:

- Copy files anyway
- Rely on recovery tools to clean partial writes

Papyra's scanner is designed for this.

---

## Redis Backups

### Option 1: Redis RDB Snapshots (Recommended)

Use Redis-native snapshotting:

- `SAVE`
- `BGSAVE`
- Cloud-managed Redis snapshots

This preserves:

- Streams
- Consumer groups
- Pending entries

### Option 2: AOF (Advanced)

If using AOF:

- Ensure `appendfsync everysec`
- Verify replay time during recovery

---

## Verifying Backups

Always validate backups before trusting them.

### Use the CLI

```bash
papyra persistence scan --path backups/papyra-2026-01-01/events.ndjson
```

Expected results:

- Clean scan → backup is valid
- Anomalies → backup still usable after recovery

---

## Recovery Scenarios

### Scenario 1: Clean Restore

1. Stop system
2. Restore files / Redis snapshot
3. Start system normally

```bash
papyra persistence startup-check
```

---

### Scenario 2: Corrupted Backup

Run recovery manually:

```bash
papyra persistence recover --path events.ndjson
```

Or quarantine:

```bash
papyra persistence recover \
  --mode quarantine \
  --quarantine-dir ./quarantine \
  --path events.ndjson
```

---

### Scenario 3: Redis Partial Failure

- Restore Redis snapshot
- Recreate consumer groups if needed
- Pending messages may reappear — this is expected

---

## Disaster Recovery Guarantees

Papyra guarantees:

- ✔ Deterministic replay
- ✔ Safe truncation of corrupted tails
- ✔ Idempotent recovery
- ✔ No hidden state

What it does **not** guarantee:

- Zero message duplication (at-least-once semantics apply)
- Automatic recovery without operator intent

---

## Operational Checklist

Before production:

- [ ] Automated daily backups
- [ ] Weekly restore test
- [ ] `persistence scan` in CI or cron
- [ ] Documented restore procedure
- [ ] Quarantine directory configured

---

## Key Takeaways

- Persistence is history, not state
- Backups are cheap and robust
- Recovery is explicit and observable
- Operator intent is always required

Papyra favors **correctness and transparency over magic**.
