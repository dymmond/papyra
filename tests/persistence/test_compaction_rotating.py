import json

import pytest

from papyra.address import ActorAddress
from papyra.persistence.backends.retention import RetentionPolicy
from papyra.persistence.backends.rotating import RotatingFilePersistence
from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


async def test_rotating_compaction_rewrites_and_deletes_old_files(tmp_path):
    path = tmp_path / "rot.log"

    retention = RetentionPolicy(max_records=3)

    backend = RotatingFilePersistence(
        path,
        max_bytes=80,
        max_files=3,
        retention_policy=retention,
    )

    addr = ActorAddress(system="local", actor_id=1)

    # Write enough events to force rotation
    for i in range(10):
        ev = PersistedEvent(
            system_id="local",
            actor_address=addr,
            event_type="Evt",
            payload={"i": i},
            timestamp=float(i),
        )
        await backend.record_event(ev)

    paths_before = list(tmp_path.iterdir())
    assert len(paths_before) >= 2  # rotation happened

    report = await backend.compact()

    paths_after = sorted(tmp_path.iterdir(), key=lambda p: p.name)

    # Only up to max_files files remain
    assert len(paths_after) <= 3

    # Read all remaining lines
    lines = []
    for p in paths_after:
        lines.extend(p.read_text().splitlines())

    assert len(lines) == 3
    assert report.after_records == 3
    assert report.before_records >= 3
    assert report.removed_records >= 1


async def test_rotating_compaction_handles_corrupted_lines(tmp_path):
    path = tmp_path / "rot.log"

    backend = RotatingFilePersistence(path, max_bytes=100, max_files=2)

    # Manually create corrupted rotated file
    bad = path.with_name(path.name + ".1")
    bad.write_text("{not-json\n")

    # Valid active file
    path.write_text(json.dumps({"kind": "event", "timestamp": 1}) + "\n")

    report = await backend.compact()

    paths = list(tmp_path.iterdir())
    lines = []
    for p in paths:
        lines.extend(p.read_text().splitlines())

    assert len(lines) == 1
    assert report.after_records == 1
