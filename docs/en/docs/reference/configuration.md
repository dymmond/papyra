# Configuration Reference

This document provides a complete reference for configuring **Papyra**.
It describes all supported configuration surfaces, defaults, and how
configuration flows through the system at runtime.

The goal of this page is not to teach *why* configuration exists (see
Core Concepts), but to precisely describe *what* can be configured and *how*.

---

## Configuration Sources

Papyra configuration is resolved from the following sources, in order of precedence:

1. **Explicit arguments** passed when constructing objects (e.g. `ActorSystem`)
2. **Global settings** stored in `papyra.settings`
3. **Backend defaults**

This design allows:

- Deterministic behavior in production
- Easy overrides for CLI tools and tests
- Zero hidden magic at runtime

---

## Global Settings (`papyra.settings`)

Papyra uses a centralized settings object exposed via:

```python
from papyra import monkay
```

The following attributes are commonly configured.

---

## `papyra.settings.persistence`

**Type:** `PersistenceBackend`

Defines the persistence backend used by the actor system, CLI tools,
startup checks, and diagnostics.

### Default

```python
InMemoryPersistence()
```

### Examples

#### JSON File Persistence

```python
from papyra.persistence.json import JsonFilePersistence
from papyra import settings

settings.persistence = JsonFilePersistence("events.ndjson")
```

#### Redis Streams Persistence

```python
from papyra.persistence.backends.redis import RedisStreamsPersistence, RedisStreamsConfig

cfg = RedisStreamsConfig(
    url="redis://localhost:6379/0",
    prefix="papyra",
)

settings.persistence = RedisStreamsPersistence(cfg)
```

---

## Persistence Retention Policy

Most persistence backends accept an optional **retention policy**.

**Type:** `RetentionPolicy`

```python
from papyra.persistence.backends.retention import RetentionPolicy

RetentionPolicy(
    max_records=1_000_000,
    max_age_seconds=86400,
    max_total_bytes=2_000_000_000,
)
```

### Fields

| Field | Description |
|------|-------------|
| `max_records` | Maximum number of records to retain |
| `max_age_seconds` | Maximum age of records |
| `max_total_bytes` | Maximum on-disk size |

Retention is **enforced logically** and **physically applied during compaction**.

---

## Actor System Configuration

### `ActorSystem(...)`

Most runtime behavior is configured when constructing the system.

```python
from papyra import ActorSystem, settings

system = ActorSystem(
    persistence=settings.persistence,
)
```

If omitted, the system automatically uses `monkay.settings.persistence`.

---

## Startup Behavior

Startup validation behavior is controlled via:

**Type:** `PersistenceStartupMode`

Values:

- `IGNORE`
- `FAIL_ON_ANOMALY`
- `RECOVER`

Used internally during system startup and externally via:

```bash
papyra persistence startup-check
papyra doctor run
```

---

## Recovery Configuration

**Type:** `PersistenceRecoveryConfig`

```python
PersistenceRecoveryConfig(
    mode=PersistenceRecoveryMode.REPAIR,
    quarantine_dir="/var/lib/papyra/quarantine",
)
```

### Recovery Modes

| Mode | Behavior |
|-----|---------|
| `REPAIR` | Fix corruption in-place |
| `QUARANTINE` | Move corrupted files aside |

---

## CLI Configuration Overrides

All persistence-related CLI commands accept a `--path` argument.

Example:

```bash
papyra persistence scan --path backup.ndjson
```

This **bypasses global configuration** and operates on the specified file.

---

## Test Configuration

In tests, configuration is commonly overridden using `monkeypatch`:

```python
monkeypatch.setattr(
    monkay.settings,
    "persistence",
    JsonFilePersistence(tmp_path / "events.ndjson"),
)
```

This ensures test isolation and deterministic behavior.

---

## Configuration Design Guarantees

Papyra configuration is designed to be:

- Explicit
- Immutable during runtime
- Test-friendly
- CLI-safe
- Observable

There are no hidden environment variables or implicit global mutation.

---

## Summary

- Configuration is centralized in `monkay.settings`
- Persistence is the primary configurable surface
- Startup, recovery, and diagnostics all reuse the same configuration
- CLI tools and production systems behave identically

For advanced scenarios, see:
- **Extending → Backend Contract**
- **Operations → Production Checklist**
- **Metrics → OpenTelemetry Integration**
-
