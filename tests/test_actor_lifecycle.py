import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio

class LifecycleActor(Actor):
    def __init__(self) -> None:
        self.events: list[str] = []

    async def on_start(self) -> None:
        self.events.append("start")

    async def receive(self, message):
        self.events.append(f"recv:{message}")
        if message == "boom":
            raise RuntimeError("crash")

    async def on_stop(self) -> None:
        self.events.append("stop")


async def test_lifecycle_normal_flow():
    async with ActorSystem() as system:
        ref = system.spawn(LifecycleActor)

        await ref.tell("a")
        await ref.tell("b")

    # actor is stopped after context exit
    actor = system._actors[0].actor
    assert actor.events == ["start", "recv:a", "recv:b", "stop"]


async def test_lifecycle_on_crash():
    async with ActorSystem() as system:
        ref = system.spawn(LifecycleActor)

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

    actor = system._actors[0].actor
    assert actor.events == ["start", "recv:boom", "stop"]
