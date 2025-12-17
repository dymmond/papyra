import anyio
import pytest

from papyra.actor import Actor
from papyra.events import (
    ActorCrashed,
    ActorEvent,
    ActorRestarted,
    ActorStopped,
)
from papyra.system import STOP, ActorSystem

pytestmark = pytest.mark.anyio


class DummyActor(Actor):
    async def receive(self, message):
        if message == "boom":
            raise RuntimeError("boom")
        return "ok"


def is_plain_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(is_plain_value(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and is_plain_value(v) for k, v in value.items())
    return False


def event_fields(event):
    for attr in dir(event):
        if attr.startswith("_"):
            continue
        value = getattr(event, attr)
        if callable(value):
            continue
        yield attr, value


async def test_event_fields_are_plain_data():
    async with ActorSystem() as system:
        system.spawn(DummyActor)
        await anyio.sleep(0)

        events = system.events()
        assert events

        for event in events:
            assert isinstance(event, ActorEvent)
            for name, value in event_fields(event):
                assert is_plain_value(value), f"{event.__class__.__name__}.{name} is not persistence-safe: {value!r}"


async def test_no_runtime_objects_leak_into_events():
    async with ActorSystem() as system:
        ref = system.spawn(DummyActor)
        await anyio.sleep(0)

        await ref.tell(STOP)
        await anyio.sleep(0)

        for event in system.events():
            for _, value in event_fields(event):
                assert not hasattr(value, "tell")
                assert not hasattr(value, "ask")
                assert not callable(value)


async def test_exception_is_serialized_as_string():
    async with ActorSystem() as system:
        ref = system.spawn(DummyActor)

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        crashes = [e for e in system.events() if isinstance(e, ActorCrashed)]
        assert crashes

        crash = crashes[0]
        assert isinstance(crash.reason, str)
        assert "boom" in crash.reason


async def test_restart_event_is_serializable():
    async with ActorSystem() as system:
        ref = system.spawn(DummyActor, name="dummy")

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        restarts = [e for e in system.events() if isinstance(e, ActorRestarted)]
        assert restarts

        for _, value in event_fields(restarts[0]):
            assert is_plain_value(value)


async def test_stopped_event_is_serializable():
    async with ActorSystem() as system:
        ref = system.spawn(DummyActor)
        await ref.tell(STOP)
        await anyio.sleep(0)

        stops = [e for e in system.events() if isinstance(e, ActorStopped)]
        assert stops

        for _, value in event_fields(stops[0]):
            assert is_plain_value(value)
