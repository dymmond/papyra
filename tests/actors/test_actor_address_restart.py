import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio


class Flaky(Actor):
    async def receive(self, msg):
        if msg == "boom":
            raise RuntimeError("crash")
        return "ok"


async def test_actor_address_survives_restart():
    async with ActorSystem() as system:
        ref = system.spawn(Flaky)
        addr = ref.address

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # Actor restarted, address must be identical
        assert ref.address == addr
