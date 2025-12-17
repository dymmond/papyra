import pytest

from papyra._envelope import STOP
from papyra.actor import Actor
from papyra.exceptions import ActorStopped
from papyra.persistence.memory import InMemoryPersistence
from papyra.system import ActorSystem

pytestmark = pytest.mark.anyio


class Dummy(Actor):
    async def receive(self, msg):
        return "ok"


async def test_events_are_persisted():
    persistence = InMemoryPersistence()

    async with ActorSystem(persistence=persistence) as system:
        ref = system.spawn(Dummy)
        await ref.tell(STOP)

    events = persistence.events
    assert any(e.event_type == "ActorStarted" for e in events)
    assert any(e.event_type == "ActorStopped" for e in events)


async def test_audit_is_persisted():
    persistence = InMemoryPersistence()

    async with ActorSystem(persistence=persistence) as system:
        system.spawn(Dummy)
        system.audit()

    assert persistence.audits
    assert persistence.audits[0].total_actors == 1


async def test_dead_letters_are_persisted():
    persistence = InMemoryPersistence()

    async with ActorSystem(persistence=persistence) as system:
        ref = system.spawn(Dummy)
        await ref.tell(STOP)

        with pytest.raises(ActorStopped):
            await ref.tell("late")

    assert persistence.dead_letters
    dl = persistence.dead_letters[0]
    assert dl.message_type == "str"
