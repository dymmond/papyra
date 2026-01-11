# Minimal Example

This page shows the smallest practical Papyra program:

- define an `Actor`
- start an `ActorSystem`
- spawn the actor
- send a couple of messages
- shut the system down cleanly

!!! Warning
    Papyra persistence records **system facts** (lifecycle events, audits, dead letters).
    It does **not** automatically persist or restore your actor's internal state.
    If you want state restoration (event sourcing, snapshots, etc.), you build that on top.

## 1) A tiny actor

Create an actor that keeps a counter in memory and returns values for request/reply calls.

```python
from __future__ import annotations

from dataclasses import dataclass

from papyra.actor import Actor


@dataclass(slots=True)
class Increment:
    by: int = 1


class Counter(Actor):
    def __init__(self) -> None:
        self.value = 0

    async def on_start(self) -> None:
        # `self.context` becomes available only after the actor is spawned.
        # You can inspect system metadata from here.
        _ = self.context.system.system_id

    async def receive(self, message):
        if isinstance(message, Increment):
            self.value += message.by
            return self.value
        if message == "get":
            return self.value
        return None
```

## 2) Start a system, spawn the actor, send messages

```python
from __future__ import annotations

import anyio

from papyra.system import ActorSystem

# from your_module import Counter, Increment


async def main() -> None:
    # The system can be used as an async context manager.
    # It will start automatically on enter and close on exit.
    async with ActorSystem() as system:
        ref = system.spawn(Counter, name="counter")

        # Fire-and-forget (no result expected)
        # Depending on your ActorRef API, this is typically `tell(...)`.
        await ref.tell(Increment())

        # Request/reply (returns the value from `receive`)
        # Depending on your ActorRef API, this is typically `ask(...)`.
        value = await ref.ask("get")
        print("counter =", value)


if __name__ == "__main__":
    anyio.run(main)
```

### Notes

- `ActorSystem()` defaults to an in-memory persistence backend (great for local dev/tests).
- In `receive(...)`, you can return a value for request/reply usage.
- `on_start()` is the right place for initialization that needs `self.context`.

## 3) Adding persistence (optional)

To persist **system facts** to disk (events/audits/dead letters), pass a persistence backend.

```python
from __future__ import annotations

import anyio

from papyra.persistence.json import JsonFilePersistence
from papyra.system import ActorSystem

# from your_module import Counter


async def main() -> None:
    persistence = JsonFilePersistence("./papyra.ndjson")

    async with ActorSystem(persistence=persistence) as system:
        system.spawn(Counter, name="counter")


if __name__ == "__main__":
    anyio.run(main)
```

That file will grow over time because it is append-only. To physically shrink it, use compaction:

```bash
papyra persistence compact --path ./papyra.ndjson
```

## 4) Where persistence is accessible at runtime

Actors can access the system's configured persistence backend via:

- `self.context.system.persistence`
- and via system operations exposed by the `ActorSystem`

If you need to write your own application-level state, keep it separate from the persistence of system facts.
