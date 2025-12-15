import pytest

from papyra import Actor, ActorSystem
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        if msg == "boom":
            raise RuntimeError("crash")
        if msg == "stop":
            await self.context.stop_self()
        return "ok"


async def test_named_actor_is_resolvable():
    async with ActorSystem() as system:
        ref = system.spawn(Worker, name="worker")

        resolved = system.ref_for_name("worker")
        assert resolved.address == ref.address


async def test_duplicate_actor_name_is_rejected():
    async with ActorSystem() as system:
        system.spawn(Worker, name="dup")

        with pytest.raises(ValueError):
            system.spawn(Worker, name="dup")


async def test_name_removed_after_actor_stops():
    async with ActorSystem() as system:
        ref = system.spawn(Worker, name="gone")

        await ref.ask("stop")

        with pytest.raises(ActorStopped):
            system.ref_for_name("gone")


async def xtest_name_survives_actor_restart():
    async with ActorSystem() as system:
        ref = system.spawn(Worker, name="svc")

        # force restart via crash
        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        resolved = system.ref_for_name("svc")
        assert resolved.address == ref.address
