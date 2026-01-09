from __future__ import annotations

import time
from pathlib import Path

import pytest

from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.persistence.backends.retention import RetentionPolicy
from papyra.persistence.backends.rotating import RotatingFilePersistence
from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["json", "rotating"])
def persistence_factory(tmp_path: Path, request):
    def _factory(retention: RetentionPolicy | None = None):
        if request.param == "memory":
            return InMemoryPersistence(retention_policy=retention)

        if request.param == "json":
            return JsonFilePersistence(
                tmp_path / "events.ndjson",
                retention_policy=retention,
            )

        if request.param == "rotating":
            return RotatingFilePersistence(
                tmp_path / "events.ndjson",
                max_bytes=256,
                max_files=5,
                retention_policy=retention,
            )

        raise AssertionError("Unknown backend")

    return _factory


async def write_events(persistence, count: int, *, start_ts: float = 0.0):
    for i in range(count):
        await persistence.record_event(
            PersistedEvent(
                system_id="local",
                actor_address=f"local://{i}",
                event_type="ActorStarted",
                payload={},
                timestamp=start_ts + float(i),
            )
        )


async def test_retention_max_records(persistence_factory):
    persistence = persistence_factory(RetentionPolicy(max_records=5))

    await write_events(persistence, 10)

    events = await persistence.list_events()

    assert len(events) == 5
    assert [e.timestamp for e in events] == [5.0, 6.0, 7.0, 8.0, 9.0]


async def test_retention_max_age_seconds(persistence_factory):
    now = time.time()

    persistence = persistence_factory(RetentionPolicy(max_age_seconds=5.0))

    await write_events(persistence, 10, start_ts=now - 10)

    events = await persistence.list_events()

    assert all(e.timestamp >= now - 5 for e in events)


async def test_retention_max_total_bytes(persistence_factory):
    persistence = persistence_factory(RetentionPolicy(max_total_bytes=300))

    await write_events(persistence, 20)

    events = await persistence.list_events()

    # Must keep *some* events but not all
    assert 0 < len(events) < 20

    # Must keep the newest ones
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


async def test_combined_retention_policies(persistence_factory):
    persistence = persistence_factory(
        RetentionPolicy(
            max_records=5,
            max_age_seconds=10,
        )
    )

    await write_events(persistence, 20)

    events = await persistence.list_events()

    assert len(events) <= 5
    assert events == tuple(sorted(events, key=lambda e: e.timestamp))
