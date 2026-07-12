import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio


class Counter(Actor):
    def __init__(self) -> None:
        self.value = 0

    async def receive(self, message):
        if message == "broadcast-inc":
            self.value += 10
            return None
        if message == "inc":
            self.value += 1
            return None
        if message == "get":
            return self.value
        return None


class Child(Actor):
    async def receive(self, message):
        if message == "parent_address":
            return str(self.context.parent.address)
        return None


class Parent(Actor):
    async def on_start(self) -> None:
        self.child = self.context.spawn_child(Child)

    async def receive(self, message):
        if message == "child_parent_address":
            return await self.child.ask("parent_address")
        return None


async def test_control_panel_lists_actor_identity_and_type():
    async with ActorSystem() as system:
        ref = system.spawn(Counter, name="counter")

        info = system.actor_info(ref)
        assert info.actor_type == "Counter"
        assert info.state == "alive"
        assert ref.is_alive() is True

        text = "\n".join(system.control_panel())

        assert "RID" in text
        assert "ADDRESS" in text
        assert str(ref.address) in text
        assert "counter" in text
        assert "Counter" in text
        assert "alive" in text


async def test_actor_info_panel_line_contains_parent_and_children():
    async with ActorSystem() as system:
        parent = system.spawn(Parent, name="parent")

        assert await parent.ask("child_parent_address") == str(parent.address)

        parent_info = system.actor_info(parent)
        assert parent_info.actor_type == "Parent"
        assert parent_info.children_rids
        assert "children=" in parent_info.panel_line()


async def test_refs_by_type_and_broadcast_target_actor_classes():
    async with ActorSystem() as system:
        first = system.spawn(Counter, name="first")
        second = system.spawn(Counter, name="second")
        system.spawn(Parent, name="parent")

        refs = system.refs_by_type(Counter)

        assert {ref.address for ref in refs} == {first.address, second.address}
        assert await system.broadcast("broadcast-inc", actor_type="Counter") == 2
        assert await first.ask("get") == 10
        assert await second.ask("get") == 10


async def test_stop_all_stops_live_registry_refs_without_closing_system():
    async with ActorSystem() as system:
        first = system.spawn(Counter, name="first")
        second = system.spawn(Counter, name="second")

        assert len(system.refs()) == 2

        await system.stop_all()

        assert first.is_alive() is False
        assert second.is_alive() is False
        assert system.refs() == ()
        assert {ref.address for ref in system.refs(alive_only=False)} == {first.address, second.address}

        later = system.spawn(Counter, name="later")
        assert later.is_alive() is True
