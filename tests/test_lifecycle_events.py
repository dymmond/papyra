import anyio
import pytest

from papyra import Actor, ActorSystem
from papyra.events import (
    ActorCrashed,
    ActorRestarted,
    ActorStarted,
    ActorStopped,
)

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        if msg == "boom":
            raise RuntimeError("crash")
        if msg == "stop":
            await self.context.stop_self()
        return "ok"


async def test_actor_start_event_emitted():
    async with ActorSystem() as system:
        system.spawn(Worker)

        await anyio.sleep(0)

        events = system.events()
        assert any(isinstance(e, ActorStarted) for e in events)


async def test_persisted_event_uses_plain_actor_address():
    async with ActorSystem() as system:
        ref = system.spawn(Worker)
        await system.wait_for_event(ActorStarted)
        await anyio.sleep(0)

        events = await system.persistence.list_events()

        assert events
        assert events[-1].actor_address == str(ref.address)


async def test_actor_crash_and_restart_events():
    async with ActorSystem() as system:
        ref = system.spawn(Worker, name="svc")  # <-- REQUIRED

        await anyio.sleep(0)

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        events = system.events()

        assert any(isinstance(e, ActorCrashed) for e in events)
        assert any(isinstance(e, ActorRestarted) for e in events)


async def test_actor_stop_event_emitted():
    async with ActorSystem() as system:
        ref = system.spawn(Worker)

        await anyio.sleep(0)

        await ref.ask("stop")

        events = system.events()
        assert any(isinstance(e, ActorStopped) for e in events)
