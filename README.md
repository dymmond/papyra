# Papyra

<p align="center">
  <a href="https://papyra.dymmond.com"><img src="https://res.cloudinary.com/dymmond/image/upload/v1768157736/Papyra/logo_nru9tf.png" alt='Papyra'></a>
</p>

<p align="center">
    <em>Durable persistence, retention and compaction for actor systems</em>
</p>

<p align="center">
<a href="https://github.com/dymmond/papyra/actions/workflows/test-suite.yml/badge.svg?event=push&branch=main" target="_blank">
    <img src="https://github.com/dymmond/papyra/actions/workflows/test-suite.yml/badge.svg?event=push&branch=main" alt="Test Suite">
</a>

<a href="https://pypi.org/project/papyra" target="_blank">
    <img src="https://img.shields.io/pypi/v/papyra?color=%2334D058&label=pypi%20package" alt="Package version">
</a>

<a href="https://pypi.org/project/papyra" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/papyra.svg?color=%2334D058" alt="Supported Python versions">
</a>
</p>

---

**Documentation**: [https://papyra.dymmond.com](https://papyra.dymmond.com) 📚

**Source Code**: [https://github.com/dymmond/papyra](https://github.com/dymmond/papyra)

**The official supported version is always the latest released**.

---

**Durable persistence, retention, recovery, and observability for actor systems.**

Papyra is a production-grade persistence layer designed specifically for **actor-based runtimes**.
It provides **durable system history**, **audits**, **dead-letter tracking**, **retention + compaction**,
**startup health checks**, **recovery orchestration**, and **operational tooling**.

> Papyra is not an actor framework.
> It's the **persistence and observability backbone** that makes an actor system operationally safe.

---

## Why Papyra?

Actor systems are excellent at concurrency and fault isolation, but production operators eventually need:

- A durable history of lifecycle events (start/stop/crash/restart)
- Audit snapshots for “what's running and what's broken?”
- Dead letters for undeliverable messages
- Retention to prevent unbounded growth
- Compaction to physically reclaim disk space
- Startup checks and deterministic recovery
- Metrics for observability
- CLI tools for real-world operations

Papyra solves this **explicitly** and safely.

---

## Features

### 🧱 Persistence backends

- **JSON NDJSON file** backend (simple, readable, portable)
- **Rotating files** backend (bounded disk usage)
- **Redis Streams** backend (production, distributed, consumer-groups)
- **In-memory** backend (tests, ephemeral)

### ♻️ Retention & compaction

- Record-count, age, and size-based retention
- Explicit **physical compaction / vacuum**
- Crash-safe atomic rewrite semantics where applicable

### 🩺 Health, startup checks & recovery

- Scan for corruption / anomalies
- Recovery modes: **IGNORE / REPAIR / QUARANTINE**
- Startup orchestration to guarantee a clean persistence layer before actors start

### 📊 Metrics & integration

- Backend metrics (writes, errors, scans, recoveries, compactions)
- CLI metrics output
- Optional OpenTelemetry integration

### 🛠️ CLI

- `persistence scan | recover | compact | inspect | startup-check`
- `doctor run`
- `inspect events | audits | dead-letters | summary`
- `metrics …`

---

## Installation

```bash
pip install papyra
```

Optional extras:

```bash
pip install papyra[redis]
```

---

## ActorSystem + Papyra: the mental model

An `ActorSystem` emits **observable facts** while it runs:

- **Events**: lifecycle transitions (started, stopped, crashed, restarted)
- **Audits**: point-in-time health snapshots (counts, registry status, dead letters)
- **Dead letters**: messages that couldn't be delivered

Papyra persists these facts using the configured backend.

A key guarantee: **startup checks happen before any actor is allowed to run**.
If the persistence layer is corrupted and startup mode is strict, `ActorSystem.start()` fails.

---

## Quickstart (with ActorSystem)

### 1) Pick a persistence backend

#### JSON file backend

```python
from papyra.persistence.json import JsonFilePersistence

persistence = JsonFilePersistence("./papyra.ndjson")
```

#### Redis Streams backend

```python
from papyra.persistence.backends.redis import RedisStreamsConfig, RedisStreamsPersistence

persistence = RedisStreamsPersistence(
    RedisStreamsConfig(url="redis://localhost:6379/0", prefix="papyra", system_id="local")
)
```

### 2) Start the ActorSystem with startup checks

```python
from papyra.system import ActorSystem
from papyra.persistence.startup import PersistenceStartupConfig, PersistenceStartupMode
from papyra.persistence.models import PersistenceRecoveryConfig, PersistenceRecoveryMode

system = ActorSystem(
    persistence=persistence,
    # Ensure the persistence layer is clean *before* any actor starts
    persistence_startup=PersistenceStartupConfig(
        mode=PersistenceStartupMode.RECOVER,
        recovery=PersistenceRecoveryConfig(mode=PersistenceRecoveryMode.REPAIR),
    ),
)

await system.start()
```

- `fail_on_anomaly` → start fails if corruption is detected
- `recover` → attempt recovery, then require a clean post-scan
- `ignore` / `scan_only` → don't fail startup

### 3) Spawn actors after the system starts

```python
from papyra.actor import Actor

class Echo(Actor):
    async def receive(self, message):
        return message

ref = system.spawn(Echo, name="echo")
```

### 4) Shut down cleanly

```python
await system.aclose()
```

---

## Operational CLI

### Health check (Doctor)

```bash
papyra doctor run
```

Fail hard if there are anomalies:

```bash
papyra doctor run --mode fail_on_anomaly
```

Attempt recovery:

```bash
papyra doctor run --mode recover --recovery-mode repair
```

### Persistence maintenance

Scan:

```bash
papyra persistence scan --path ./papyra.ndjson
```

Recover:

```bash
papyra persistence recover --mode repair --path ./papyra.ndjson
```

Compact:

```bash
papyra persistence compact --path ./papyra.ndjson
```

Inspect summary:

```bash
papyra persistence inspect --path ./papyra.ndjson --show-metrics
```

---

## Documentation

The full documentation covers:

- Core concepts and actor lifecycle observability
- All persistence backends (JSON, rotation, Redis, memory)
- Retention and compaction strategies
- Failure scenarios and recovery playbooks
- Startup guarantees
- Metrics + OpenTelemetry integration
- Extending Papyra with custom backends

---

## License

MIT © Dymmond
