# Actor Registry and Control Panel

Papyra keeps a live, system-scoped registry of the actors it owns. Use it when you need to answer
operational questions while the system is running:

- Which actors exist?
- What are their ids and addresses?
- Which actor class is running at each address?
- Which actors are alive, stopping, or restarting?
- How do I fan out a maintenance message to a class of actors?

This registry is local to the `ActorSystem`. That keeps ownership explicit when one process hosts
multiple systems or when persistence backends are separated by tenant, service, or environment.

## Worker Fleet Example

```python
from __future__ import annotations

import anyio

from papyra.actor import Actor
from papyra.system import ActorSystem


class Worker(Actor):
    def __init__(self) -> None:
        self.jobs = 0
        self.paused = False

    async def receive(self, message):
        if message == "pause":
            self.paused = True
            return None

        if message == "resume":
            self.paused = False
            return None

        if message == "stats":
            return {"jobs": self.jobs, "paused": self.paused}

        if not self.paused:
            self.jobs += 1
        return None


class Coordinator(Actor):
    async def receive(self, message):
        if message == "health":
            return "ok"
        return None


async def main() -> None:
    async with ActorSystem(system_id="orders") as system:
        coordinator = system.spawn(Coordinator, name="coordinator")
        worker_1 = system.spawn(Worker, name="worker-1")
        worker_2 = system.spawn(Worker, name="worker-2")

        await worker_1.tell("job")
        await worker_2.tell("job")

        print("\n".join(system.control_panel()))

        # Resolve by name when a specific service actor is needed.
        assert await system.ref_for_name("coordinator").ask("health") == "ok"

        # Resolve by actor class when operating on a fleet.
        workers = system.refs_by_type(Worker)
        print("worker addresses:", [str(ref.address) for ref in workers])

        # Broadcast maintenance commands to all Worker actors.
        paused = await system.broadcast("pause", actor_type=Worker)
        print("paused workers:", paused)

        print(await worker_1.ask("stats"))
        print(await worker_2.ask("stats"))

        # Stop all actors without closing the system object.
        await system.stop_all()
        assert system.refs() == ()


if __name__ == "__main__":
    anyio.run(main)
```

Typical panel output:

```text
RID  ADDRESS   NAME         ACTOR        STATE  PARENT  CHILDREN
1    orders:1  coordinator  Coordinator  alive  -       -
2    orders:2  worker-1     Worker       alive  -       -
3    orders:3  worker-2     Worker       alive  -       -
```

## Registry API

- `system.control_panel()` returns printable lines with runtime id, address, name, actor class,
  lifecycle state, parent id, and child ids.
- `system.refs()` returns fresh `ActorRef` objects for live actors by default.
- `system.refs(alive_only=False)` includes stopped runtimes for diagnostics.
- `system.refs_by_type(Worker)` returns live refs for a specific actor class.
- `system.refs_by_type("Worker")` is useful for tools that only have class names.
- `await system.broadcast(message, actor_type=Worker)` sends a fire-and-forget message to all
  matching actors and returns the number that accepted it.
- `await system.stop_all()` stops all root actors and cascades to their children without closing
  the `ActorSystem`; you can still spawn new actors afterward.

## When to Use Audits Instead

Use `system.control_panel()` and registry methods for live runtime operations. Use `system.audit()`
when you want a structured snapshot that can be persisted, checked by hooks, or exposed through
your own diagnostics endpoint.
