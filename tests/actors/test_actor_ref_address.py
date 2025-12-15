import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio


class SimpleActor(Actor):
    async def receive(self, msg):
        return msg


async def test_actor_ref_exposes_address():
    async with ActorSystem() as system:
        ref = system.spawn(SimpleActor)

        addr = ref.address

        assert addr.actor_id == ref._rid
        assert isinstance(addr.system, str)
