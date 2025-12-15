import pytest

from papyra import Actor, ActorStopped, ActorSystem

pytestmark = pytest.mark.anyio


class Child(Actor):
    async def receive(self, message):
        if message == "ping":
            return "pong"
        return None


class Parent(Actor):
    async def on_start(self) -> None:
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        if message == "get_child":
            return self.child
        if message == "stop":
            await self.context.stop_self()
            return "stopping"
        return None


async def test_stopping_parent_stops_child():
    async with ActorSystem() as system:
        parent = system.spawn(Parent)
        child = await parent.ask("get_child")

        assert await child.ask("ping") == "pong"
        assert await parent.ask("stop") == "stopping"

        # Parent should be stopped
        with pytest.raises(ActorStopped):
            await parent.tell("after")

        # Child should also be stopped (cascade)
        with pytest.raises(ActorStopped):
            await child.tell("after")


class CrashParent(Actor):
    async def on_start(self) -> None:
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        if message == "get_child":
            return self.child
        if message == "boom":
            raise RuntimeError("parent crashed")
        return None


async def test_parent_crash_stops_child():
    async with ActorSystem() as system:
        parent = system.spawn(CrashParent)
        child = await parent.ask("get_child")

        assert await child.ask("ping") == "pong"

        with pytest.raises(RuntimeError):
            await parent.ask("boom")

        # Parent should be stopped
        with pytest.raises(ActorStopped):
            await parent.tell("after")

        # Child should also be stopped (cascade)
        with pytest.raises(ActorStopped):
            await child.tell("after")
