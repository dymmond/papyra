import pytest

from papyra.actor import Actor
from papyra.events import ActorRestarted
from papyra.supervision import Strategy, SupervisionPolicy
from papyra.system import ActorSystem

pytestmark = pytest.mark.anyio


class BoomActor(Actor):
    async def receive(self, msg):
        raise RuntimeError("boom")


async def test_deterministic_time_used_for_restarts():
    t = 0.0

    def clock():
        return t

    async with ActorSystem(time_fn=clock) as system:
        ref = system.spawn(
            BoomActor,
            policy=SupervisionPolicy(strategy=Strategy.RESTART),
        )

        # First crash at t=1.0 -> first restart
        t = 1.0
        with pytest.raises(RuntimeError):
            await ref.ask("boom")
        await system.wait_for_event(ActorRestarted)

        # Second crash at t=2.0 -> second restart
        start_index = len(system.events())
        t = 2.0
        with pytest.raises(RuntimeError):
            await ref.ask("boom")
        await system.wait_for_event(ActorRestarted, start_index=start_index)
