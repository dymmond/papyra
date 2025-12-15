import pytest

from papyra import Actor, ActorSystem
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        if msg == "stop":
            await self.context.stop_self()
        return msg


async def test_ref_for_stopped_actor_raises():
    async with ActorSystem() as system:
        ref = system.spawn(Worker)
        addr = ref.address

        await ref.ask("stop")

        with pytest.raises(ActorStopped):
            system.ref_for(addr)
