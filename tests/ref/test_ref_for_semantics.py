import pytest

from papyra import Actor, ActorSystem
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        if msg == "stop":
            await self.context.stop_self()
        return "ok"


async def test_ref_for_returns_fresh_actorref_instances():
    async with ActorSystem() as system:
        ref = system.spawn(Worker)
        addr = ref.address

        r1 = system.ref_for(addr)
        r2 = system.ref_for(addr)

        assert r1 is not r2
        assert r1._rid == r2._rid


async def test_ref_for_reflects_liveness_dynamically():
    async with ActorSystem() as system:
        ref = system.spawn(Worker)
        addr = ref.address

        ref2 = system.ref_for(addr)
        await ref.ask("stop")

        with pytest.raises(ActorStopped):
            await ref2.tell("x")
