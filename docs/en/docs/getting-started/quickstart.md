# Quickstart

This guide takes you from **zero to a running Papyra system**, while explaining **what really happens** at runtime.

Papyra is intentionally explicit. Nothing starts, persists, or recovers unless you **ask for it**.

By the end of this guide, you will understand:

- What an `ActorSystem` really is
- How actors process messages
- What Papyra *automatically* persists (and what it does not)
- How startup checks and recovery work
- How to inspect and operate the system safely

---

## 1. What Is an ActorSystem?

`ActorSystem` is the **process-level runtime container** for everything that happens in Papyra.

It is responsible for:

- Hosting all actors and their mailboxes
- Running the internal async task group (via `anyio`)
- Routing messages
- Emitting and persisting **system facts** (events, audits, dead letters)
- Enforcing persistence startup guarantees

Think of it as **the runtime itself**, not just a registry.

Nothing runs until the system is explicitly started.

---

## 2. Minimal System Setup

A minimal Papyra system consists of:

- An `ActorSystem`
- A persistence backend
- Explicit startup behavior

```python
from papyra.system import ActorSystem
from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.startup import (
    PersistenceStartupConfig,
    PersistenceStartupMode,
)

system = ActorSystem(
    persistence=JsonFilePersistence("events.ndjson"),
    persistence_startup=PersistenceStartupConfig(
        mode=PersistenceStartupMode.FAIL_ON_ANOMALY,
    ),
)
```

At this point:

- ❌ No actors exist
- ❌ No background tasks are running
- ❌ No I/O has happened

The system is **configured**, not running.

---

## 3. Starting the System

The runtime becomes live only when you explicitly start it.

```python
await system.start()
```

What happens during `start()`:

1. Persistence startup checks are executed
2. Corruption is detected (or not)
3. Recovery is applied *if configured*
4. The internal task group is created
5. Actor mailboxes become active

If startup fails, **nothing runs**.

`start()` is idempotent — calling it twice is a no-op.

---

## 4. Defining an Actor (Correctly)

Actors are **pure message handlers**.

They do **not** magically persist state.

They do **not** have implicit storage.

They receive messages and optionally **emit system facts**.

```python
from papyra.actor import Actor

class Counter(Actor):
    async def on_start(self) -> None:
        self.total = 0

    async def receive(self, message: dict) -> None:
        if message["type"] == "increment":
            value = message.get("value", 1)
            self.total += value

            # This is NOT application state persistence
            # This records a system event
            await self.context.system.persistence.record_event({
                "system_id": "local",
                "actor_address": self.context.self_ref.address,
                "event_type": "counter.incremented",
                "payload": {"value": value, "total": self.total},
                "timestamp": self.context.system.clock.now(),
            })
```

Important clarifications:

- There is **no** `self.persist_event()` helper
- Persistence is accessed via `self.context.system.persistence`
- Events written here are **system facts**, not actor state snapshots

This is deliberate.

---

## 5. Registering Actors

Actors must be registered **before** the system is started.

```python
system.register("counter", Counter)
await system.start()
```

Registration defines **what can be spawned**, not what *is* spawned.

---

## 6. Sending Messages

Once the system is running, actors can be addressed and messaged.

```python
counter = system.actor("counter")

await counter.send({"type": "increment", "value": 5})
await counter.send({"type": "increment", "value": 2})
```

This produces persisted system events like:

```json
{"kind":"event","event_type":"counter.incremented","payload":{"value":5,"total":5}}
{"kind":"event","event_type":"counter.incremented","payload":{"value":2,"total":7}}
```

Guarantees:

- Message handling is sequential per actor
- Persistence is explicit
- Failures do not silently drop data

---

## 7. Restarting the System

Stop the process.
Start it again.

```python
await system.start()
```

What happens:

- Papyra **does not restore actor state**
- Only system facts remain persisted
- Actors start fresh

If you want **event-sourced state recovery**, you implement it explicitly
(e.g., by reading your own domain events during `on_start`).

This is intentional.

---

## 8. Inspecting Persistence

Papyra ships with built-in inspection tools.

```bash
papyra persistence inspect
```

Example output:

```shell
Persistence Inspect
------------------
backend: JsonFilePersistence
retention: max_records=None max_age_seconds=None max_total_bytes=None
events_sampled: 2
audits_sampled: 0
dead_letters_sampled: 0
```

This is safe, read-only, and production-grade.

---

## 9. Handling Corruption (Real World)

Simulate corruption:

```bash
echo '{"kind":"event"' >> events.ndjson
```

Now run:

```bash
papyra doctor run
```

You will see:

- Clear anomaly diagnostics
- A non-zero exit code
- No silent startup

Recover explicitly:

```bash
papyra doctor run --mode recover --recovery-mode repair
```

This is not best-effort.
This is **deterministic behavior**.

---

## 10. What You Learned

You now understand:

- What `ActorSystem` actually does
- How actors interact with persistence
- Why startup checks exist
- Why recovery is explicit
- Why state restoration is not implicit

Papyra favors **clarity over convenience**.
