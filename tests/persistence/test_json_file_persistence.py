from __future__ import annotations

import json
from pathlib import Path

import pytest

from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import (
    PersistedAudit,
    PersistedDeadLetter,
    PersistedEvent,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def json_path(tmp_path: Path) -> Path:
    return tmp_path / "papyra.ndjson"


@pytest.fixture
def persistence(json_path: Path) -> JsonFilePersistence:
    return JsonFilePersistence(json_path)


async def test_empty_file_returns_nothing(persistence: JsonFilePersistence):
    events = await persistence.list_events()
    audits = await persistence.list_audits()
    dead_letters = await persistence.list_dead_letters()

    assert events == ()
    assert audits == ()
    assert dead_letters == ()


async def test_event_is_persisted_and_read_back(
    persistence: JsonFilePersistence,
):
    event = PersistedEvent(
        system_id="local",
        actor_address={"system": "local", "actor_id": 1},
        event_type="ActorStarted",
        payload={},
        timestamp=100.0,
    )

    await persistence.record_event(event)

    events = await persistence.list_events()
    assert len(events) == 1

    ev = events[0]
    assert ev.event_type == "ActorStarted"
    assert ev.timestamp == 100.0
    assert ev.actor_address["actor_id"] == 1


async def test_audit_is_persisted_and_read_back(
    persistence: JsonFilePersistence,
):
    audit = PersistedAudit(
        system_id="local",
        timestamp=200.0,
        total_actors=3,
        alive_actors=2,
        stopping_actors=1,
        restarting_actors=0,
        registry_size=2,
        registry_orphans=(),
        registry_dead=(),
        dead_letters_count=0,
    )

    await persistence.record_audit(audit)

    audits = await persistence.list_audits()
    assert len(audits) == 1
    assert audits[0].total_actors == 3
    assert audits[0].timestamp == 200.0


async def test_dead_letter_is_persisted_and_read_back(
    persistence: JsonFilePersistence,
):
    dead = PersistedDeadLetter(
        system_id="local",
        target="local://1",
        message_type="str",
        payload="late",
        timestamp=300.0,
    )

    await persistence.record_dead_letter(dead)

    dls = await persistence.list_dead_letters()
    assert len(dls) == 1
    assert dls[0].message_type == "str"
    assert dls[0].payload == "late"


async def test_limit_and_since_filters(
    persistence: JsonFilePersistence,
):
    for ts in (10.0, 20.0, 30.0):
        await persistence.record_event(
            PersistedEvent(
                system_id="local",
                actor_address={"system": "local", "actor_id": 1},
                event_type="ActorStarted",
                payload={},
                timestamp=ts,
            )
        )

    events = await persistence.list_events(since=15.0)
    assert [e.timestamp for e in events] == [20.0, 30.0]

    events = await persistence.list_events(limit=1)
    assert [e.timestamp for e in events] == [30.0]


async def test_persistence_survives_reopen(json_path: Path):
    p1 = JsonFilePersistence(json_path)

    await p1.record_event(
        PersistedEvent(
            system_id="local",
            actor_address={"system": "local", "actor_id": 1},
            event_type="ActorStopped",
            payload={"reason": "stopped"},
            timestamp=400.0,
        )
    )
    await p1.aclose()

    p2 = JsonFilePersistence(json_path)
    events = await p2.list_events()

    assert len(events) == 1
    assert events[0].event_type == "ActorStopped"


async def test_invalid_json_lines_are_ignored(json_path: Path):
    json_path.write_text('{"kind": "event", "timestamp": 1}\n' "not-json\n" '{"kind": "audit", "timestamp": 2}\n')

    persistence = JsonFilePersistence(json_path)

    events = await persistence.list_events()
    audits = await persistence.list_audits()

    assert len(events) == 1
    assert len(audits) == 1


async def test_extra_fields_do_not_break_deserialization(json_path: Path):
    json_path.write_text(
        json.dumps(
            {
                "kind": "event",
                "system_id": "local",
                "actor_address": {"system": "local", "actor_id": 1},
                "event_type": "ActorStarted",
                "payload": {},
                "timestamp": 123.0,
                "future_field": "ignored",
            }
        )
        + "\n"
    )

    persistence = JsonFilePersistence(json_path)
    events = await persistence.list_events()

    assert len(events) == 1
    assert events[0].event_type == "ActorStarted"
