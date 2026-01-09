from __future__ import annotations

from pathlib import Path

import pytest

from papyra.persistence.backends.rotating import RotatingFilePersistence
from papyra.persistence.models import (
    PersistedAudit,
    PersistedDeadLetter,
    PersistedEvent,
)

pytestmark = pytest.mark.anyio


async def test_empty_directory_returns_nothing(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"
    persistence = RotatingFilePersistence(path)

    events = await persistence.list_events()
    audits = await persistence.list_audits()
    dead_letters = await persistence.list_dead_letters()

    assert events == ()
    assert audits == ()
    assert dead_letters == ()


async def test_single_records_are_persisted(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"
    persistence = RotatingFilePersistence(path)

    await persistence.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )

    await persistence.record_audit(
        PersistedAudit(
            system_id="local",
            timestamp=2.0,
            total_actors=1,
            alive_actors=1,
            stopping_actors=0,
            restarting_actors=0,
            registry_size=0,
            registry_orphans=(),
            registry_dead=(),
            dead_letters_count=0,
        )
    )

    await persistence.record_dead_letter(
        PersistedDeadLetter(
            system_id="local",
            target="local://1",
            message_type="str",
            payload="oops",
            timestamp=3.0,
        )
    )

    events = await persistence.list_events()
    audits = await persistence.list_audits()
    dead_letters = await persistence.list_dead_letters()

    assert len(events) == 1
    assert events[0].event_type == "ActorStarted"

    assert len(audits) == 1
    assert audits[0].total_actors == 1

    assert len(dead_letters) == 1
    assert dead_letters[0].message_type == "str"


async def test_rotation_creates_rotated_files(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"

    # Very small max_bytes to force rotation quickly
    persistence = RotatingFilePersistence(
        path,
        max_bytes=200,
        max_files=3,
    )

    # Write enough events to trigger rotation
    for i in range(10):
        await persistence.record_event(
            PersistedEvent(
                system_id="local",
                actor_address=f"local://{i}",
                event_type="ActorStarted",
                payload={"i": i},
                timestamp=float(i),
            )
        )

    # Active file must exist
    assert path.exists()

    # At least one rotated file should exist
    rotated_1 = path.with_name(path.name + ".1")
    assert rotated_1.exists()

    # No more than max_files total files should exist
    all_files = list(tmp_path.iterdir())
    assert len(all_files) <= 3


async def test_reading_across_rotations(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"

    persistence = RotatingFilePersistence(
        path,
        max_bytes=200,
        max_files=4,
    )

    timestamps = []

    for i in range(12):
        ts = float(i)
        timestamps.append(ts)
        await persistence.record_event(
            PersistedEvent(
                system_id="local",
                actor_address=f"local://{i}",
                event_type="ActorStarted",
                payload={},
                timestamp=ts,
            )
        )

    events = await persistence.list_events()

    # All events must be readable across rotations
    assert len(events) == len(timestamps)
    assert [e.timestamp for e in events] == timestamps


async def test_limit_and_since_filters_work_with_rotation(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"

    persistence = RotatingFilePersistence(
        path,
        max_bytes=150,
        max_files=5,
    )

    for i in range(20):
        await persistence.record_event(
            PersistedEvent(
                system_id="local",
                actor_address=f"local://{i}",
                event_type="ActorStarted",
                payload={},
                timestamp=float(i),
            )
        )

    # since filter
    events_since_10 = await persistence.list_events(since=10)
    assert all(e.timestamp >= 10 for e in events_since_10)

    # limit filter
    limited = await persistence.list_events(limit=5)
    assert len(limited) == 5
    assert [e.timestamp for e in limited] == [15.0, 16.0, 17.0, 18.0, 19.0]


async def test_invalid_json_lines_are_ignored(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"

    # Manually write corrupted content
    path.write_text(
        '{"kind": "event", "system_id": "local", "actor_address": "local://1", '
        '"event_type": "ActorStarted", "payload": {}, "timestamp": 1.0}\n'
        "not-json\n"
        '{"kind": "audit", "system_id": "local", "timestamp": 2.0, '
        '"total_actors": 1, "alive_actors": 1, "stopping_actors": 0, '
        '"restarting_actors": 0, "registry_size": 0, '
        '"registry_orphans": [], "registry_dead": [], "dead_letters_count": 0}\n'
    )

    persistence = RotatingFilePersistence(path)

    events = await persistence.list_events()
    audits = await persistence.list_audits()

    assert len(events) == 1
    assert events[0].timestamp == 1.0

    assert len(audits) == 1
    assert audits[0].timestamp == 2.0


async def test_extra_fields_do_not_break_deserialization(tmp_path: Path):
    path = tmp_path / "papyra.ndjson"

    path.write_text(
        '{"kind": "event", "system_id": "local", "actor_address": "local://1", '
        '"event_type": "ActorStarted", "payload": {}, "timestamp": 1.0, '
        '"unexpected": "ignored"}\n'
    )

    persistence = RotatingFilePersistence(path)

    events = await persistence.list_events()

    assert len(events) == 1
    assert events[0].event_type == "ActorStarted"
