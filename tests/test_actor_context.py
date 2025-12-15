import pytest
from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio

class Child(Actor):
    async def receive(self, message):
        if message == "parent?":
            # parent should exist for child
            return self.context.parent is not None
        return message


class Parent(Actor):
    async def on_start(self) -> None:
        # Must be available in on_start
        assert self.context.parent is None
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        if message == "child_ref?":
            return self.child is not None
        if message == "ask_child":
            return await self.child.ask("parent?")
        return None


async def test_actor_context_self_and_parent_and_spawn_child():
    async with ActorSystem() as system:
        parent = system.spawn(Parent)

        assert await parent.ask("child_ref?") is True
        assert await parent.ask("ask_child") is True
