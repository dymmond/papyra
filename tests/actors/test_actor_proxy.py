import pytest

from papyra import Actor, ActorStopped, ActorSystem, ProxyCall

pytestmark = pytest.mark.anyio


class Calculator(Actor):
    def __init__(self) -> None:
        self.total = 0
        self._secret = "hidden"

    def add(self, value: int) -> int:
        self.total += value
        return self.total

    async def add_async(self, value: int) -> int:
        self.total += value
        return self.total

    def reset(self) -> None:
        self.total = 0

    async def receive(self, message):
        if message == "total":
            return self.total
        if message == "stop":
            await self.context.stop_self()
            return None
        return None


async def test_proxy_can_call_sync_and_async_actor_methods():
    async with ActorSystem() as system:
        ref = system.spawn(Calculator)
        proxy = ref.proxy()

        assert await proxy.add(2) == 2
        assert await proxy.add_async(3) == 5
        assert await ref.ask("total") == 5


async def test_proxy_can_read_and_set_actor_attributes():
    async with ActorSystem() as system:
        ref = system.spawn(Calculator)
        proxy = ref.proxy()

        assert await proxy.total == 0

        await proxy.total.set(7)

        assert await proxy.total == 7
        assert await ref.ask("total") == 7


async def test_proxy_defer_uses_tell_semantics():
    async with ActorSystem() as system:
        ref = system.spawn(Calculator)
        proxy = ref.proxy()

        await proxy.add.defer(4)

        assert await proxy.total == 4


async def test_proxy_rejects_private_attributes():
    async with ActorSystem() as system:
        ref = system.spawn(Calculator)
        proxy = ref.proxy()

        with pytest.raises(AttributeError):
            await proxy._secret


async def test_proxy_from_stopped_actor_ref_raises():
    async with ActorSystem() as system:
        ref = system.spawn(Calculator)

        await ref.ask("stop")

        with pytest.raises(ActorStopped):
            ref.proxy()


async def test_proxy_call_message_can_be_used_directly():
    async with ActorSystem() as system:
        ref = system.spawn(Calculator)

        result = await ref.ask(ProxyCall(attr_path=("add",), args=(6,)))

        assert result == 6
        assert await ref.ask("total") == 6
