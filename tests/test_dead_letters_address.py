import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        return "ok"


async def test_dead_letter_contains_actor_address():
    async with ActorSystem() as system:
        ref = system.spawn(Worker)
        addr = ref.address

        await system.stop(ref)

        try:
            await ref.tell("msg")
        except Exception:
            pass

        dl = system.dead_letters.messages[-1]
        assert dl.target.address == addr
