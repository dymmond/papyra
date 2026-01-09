import pytest

from papyra.address import ActorAddress
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


async def test_memory_compaction_is_noop():
    backend = InMemoryPersistence()

    addr = ActorAddress(system="local", actor_id=1)

    for i in range(5):
        await backend.record_event(
            PersistedEvent(
                system_id="local",
                actor_address=addr,
                event_type="Evt",
                payload={"i": i},
                timestamp=float(i),
            )
        )

    report = await backend.compact()

    assert report["backend"] == "memory"
    assert report["before_records"] == 5
    assert report["after_records"] == 5
