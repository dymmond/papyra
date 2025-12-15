import pytest

from papyra import (
    Actor,
    ActorStopped,
    ActorSystem,
    SupervisorDecision,
)

pytestmark = pytest.mark.anyio


class Child(Actor):
    async def receive(self, message):
        if message == "boom":
            raise RuntimeError("fail")
        return "ok"


class Supervisor(Actor):
    async def on_start(self) -> None:
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        if message == "child":
            return self.child
        return None

    async def on_child_failure(self, child_ref, exc):
        # Explicitly restart child
        return SupervisorDecision.RESTART


async def test_supervisor_can_restart_child():
    async with ActorSystem() as system:
        supervisor = system.spawn(Supervisor)
        child = await supervisor.ask("child")

        assert await child.ask("ok") == "ok"

        with pytest.raises(RuntimeError):
            await child.ask("boom")

        # Child should be alive again
        assert await child.ask("ok") == "ok"


class StopSupervisor(Actor):
    async def on_start(self) -> None:
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        return self.child

    async def on_child_failure(self, child_ref, exc):
        return SupervisorDecision.STOP


async def test_supervisor_can_stop_child():
    async with ActorSystem() as system:
        supervisor = system.spawn(StopSupervisor)
        child = await supervisor.ask("any")

        with pytest.raises(RuntimeError):
            await child.ask("boom")

        with pytest.raises(ActorStopped):
            await child.tell("after")
