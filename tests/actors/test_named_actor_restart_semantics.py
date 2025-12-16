import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio


class Service(Actor):
    async def receive(self, msg):
        if msg == "boom":
            raise RuntimeError("crash")
        return msg


async def test_named_actor_ref_survives_restart():
    async with ActorSystem() as system:
        ref = system.spawn(Service, name="svc")

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # same ref must still work
        assert await ref.ask("ping") == "ping"


async def test_named_actor_mailbox_survives_restart():
    async with ActorSystem() as system:
        ref = system.spawn(Service, name="svc")

        # cause restart
        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # message sent immediately after restart
        assert await ref.ask("ok") == "ok"
