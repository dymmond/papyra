import pytest

from papyra.persistence.models import PersistedEvent
from papyra.persistence.rotating import RotatingFilePersistence

pytestmark = pytest.mark.anyio


async def test_rotating_write_metrics(tmp_path):
    path = tmp_path / "rot.log"
    backend = RotatingFilePersistence(path, max_bytes=100, max_files=2)

    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )

    snap = backend.metrics.snapshot()
    assert snap["records_written"] == 1
    assert snap["bytes_written"] > 0


async def test_rotating_compact_metrics(tmp_path):
    path = tmp_path / "rot.log"
    backend = RotatingFilePersistence(path, max_bytes=50, max_files=2)

    await backend.compact()

    snap = backend.metrics.snapshot()
    assert snap["compactions"] == 1
