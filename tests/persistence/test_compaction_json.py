import json

import pytest

from papyra.address import ActorAddress
from papyra.persistence.backends.retention import RetentionPolicy
from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


async def test_json_compaction_applies_retention_physically(tmp_path):
    path = tmp_path / "events.log"

    retention = RetentionPolicy(max_records=2)
    backend = JsonFilePersistence(path, retention_policy=retention)

    addr = ActorAddress(system="local", actor_id=1)

    # Write 5 events
    for i in range(5):
        ev = PersistedEvent(
            system_id="local",
            actor_address=addr,
            event_type="TestEvent",
            payload={"i": i},
            timestamp=float(i),
        )
        await backend.record_event(ev)

    size_before = path.stat().st_size
    lines_before = path.read_text().splitlines()
    assert len(lines_before) == 5

    report = await backend.compact()

    size_after = path.stat().st_size
    lines_after = path.read_text().splitlines()

    assert len(lines_after) == 2
    assert size_after < size_before

    assert report.before_records == 5
    assert report.after_records == 2
    assert report.removed_records == 3


async def test_json_compaction_skips_corrupted_lines(tmp_path):
    path = tmp_path / "events.log"

    backend = JsonFilePersistence(path)

    # Write valid line
    path.write_text(
        json.dumps({"kind": "event", "timestamp": 1})
        + "\n"
        + "{this is not json\n"
        + json.dumps({"kind": "event", "timestamp": 2})
        + "\n"
    )

    report = await backend.compact()

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert report.before_records == 2
    assert report.after_records == 2
