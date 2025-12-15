import pytest

from papyra import Actor, ActorStopped, ActorSystem

pytestmark = pytest.mark.anyio


class StopSelfActor(Actor):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def on_start(self) -> None:
        self.events.append("start")

    async def receive(self, message):
        if message == "stop":
            self.events.append("stopping")
            await self.context.stop_self()
            return "ok"
        self.events.append(f"recv:{message}")
        return "ok"

    async def on_stop(self) -> None:
        self.events.append("stop")


async def test_actor_can_stop_itself_and_runs_on_stop():
    async with ActorSystem() as system:
        ref = system.spawn(StopSelfActor)

        assert await ref.ask("hello") == "ok"
        assert await ref.ask("stop") == "ok"

        # After stop is requested, ActorRef should reject new interactions.
        with pytest.raises(ActorStopped):
            await ref.tell("after")

    actor = system._by_id[ref._rid].actor
    assert actor.events[0] == "start"
    assert "stop" in actor.events


class Child(Actor):
    async def receive(self, message):
        if message == "ping":
            return "child-ok"
        return None


class Parent(Actor):
    async def on_start(self) -> None:
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        if message == "get_child":
            return self.child
        if message == "stop_child":
            await self.context.stop(self.child)
            return "stopped"
        return None


async def test_parent_can_stop_child():
    async with ActorSystem() as system:
        parent = system.spawn(Parent)

        # Ask the parent for the child reference (actor-model correct)
        child = await parent.ask("get_child")

        assert await child.ask("ping") == "child-ok"
        assert await parent.ask("stop_child") == "stopped"

        with pytest.raises(ActorStopped):
            await child.tell("after")
