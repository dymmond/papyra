import pytest

from papyra import Actor, ActorSystem

pytestmark = pytest.mark.anyio


class Counter(Actor):
    def __init__(self) -> None:
        self.value = 0

    async def receive(self, message):
        if message == "inc":
            self.value += 1
            return None
        if message == "get":
            return self.value
        raise ValueError(f"unknown message: {message!r}")


async def test_tell_and_ask_roundtrip():
    async with ActorSystem() as system:
        counter = system.spawn(Counter)

        await counter.tell("inc")
        await counter.tell("inc")
        assert await counter.ask("get") == 2


async def test_ask_propagates_actor_exception():
    async with ActorSystem() as system:
        counter = system.spawn(Counter)

        with pytest.raises(ValueError):
            await counter.ask("boom")
