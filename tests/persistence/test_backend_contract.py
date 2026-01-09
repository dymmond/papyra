from __future__ import annotations

import pytest

from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.persistence.backends.rotating import RotatingFilePersistence
from papyra.persistence.contract import (
    PersistenceBackendContract,
    backend_capabilities,
    safe_metrics_snapshot,
)
from papyra.persistence.json import JsonFilePersistence

pytestmark = pytest.mark.anyio


async def test_contract_inmemory_satisfies_minimal_contract() -> None:
    backend = InMemoryPersistence()
    assert isinstance(backend, PersistenceBackendContract)

    caps = backend_capabilities(backend)
    assert caps.supports_scan is True
    assert caps.supports_recover is True
    assert caps.supports_compact is True
    assert caps.supports_metrics is True

    # Must not raise
    await backend.record_event(
        {
            "system_id": "local",
            "actor_address": "local://1",
            "event_type": "ActorStarted",
            "payload": {},
            "timestamp": 1.0,
        }
    )
    await backend.record_audit(
        {
            "system_id": "local",
            "timestamp": 1.0,
            "total_actors": 0,
            "alive_actors": 0,
            "stopping_actors": 0,
            "restarting_actors": 0,
            "registry_size": 0,
            "registry_orphans": (),
            "registry_dead": (),
            "dead_letters_count": 0,
        }
    )
    await backend.record_dead_letter(
        {
            "system_id": "local",
            "target": "local://1",
            "message_type": "str",
            "payload": "x",
            "timestamp": 1.0,
        }
    )

    scan = await backend.scan()
    assert scan is not None

    report = await backend.recover()
    assert report is not None

    comp = await backend.compact()
    assert comp is not None

    snap = safe_metrics_snapshot(backend)
    assert isinstance(snap, dict)
    assert "records_written" in snap

    await backend.aclose()


async def test_contract_jsonfile_satisfies_minimal_contract(tmp_path) -> None:
    path = tmp_path / "events.ndjson"
    backend = JsonFilePersistence(path)

    assert isinstance(backend, PersistenceBackendContract)

    caps = backend_capabilities(backend)
    assert caps.supports_scan is True
    assert caps.supports_recover is True
    assert caps.supports_compact is True
    assert caps.supports_metrics is True

    # Use the real persisted models expected by the backend
    from papyra.persistence.models import PersistedAudit, PersistedDeadLetter, PersistedEvent

    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )
    await backend.record_audit(
        PersistedAudit(
            system_id="local",
            timestamp=1.0,
            total_actors=0,
            alive_actors=0,
            stopping_actors=0,
            restarting_actors=0,
            registry_size=0,
            registry_orphans=(),
            registry_dead=(),
            dead_letters_count=0,
        )
    )
    await backend.record_dead_letter(
        PersistedDeadLetter(
            system_id="local",
            target="local://1",
            message_type="str",
            payload="x",
            timestamp=1.0,
        )
    )

    scan = await backend.scan()
    assert scan is not None

    # recover must be best-effort and must not raise
    report = await backend.recover()
    assert report is not None

    comp = await backend.compact()
    assert comp is not None

    snap = safe_metrics_snapshot(backend)
    assert isinstance(snap, dict)
    assert "records_written" in snap

    await backend.aclose()


async def test_contract_rotating_satisfies_minimal_contract(tmp_path) -> None:
    path = tmp_path / "rot.log"
    backend = RotatingFilePersistence(path, max_bytes=200, max_files=2)

    assert isinstance(backend, PersistenceBackendContract)

    caps = backend_capabilities(backend)
    assert caps.supports_scan is True
    assert caps.supports_recover is True
    assert caps.supports_compact is True
    assert caps.supports_metrics is True

    from papyra.persistence.models import PersistedEvent

    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )

    scan = await backend.scan()
    assert scan is not None

    report = await backend.recover()
    assert report is not None

    comp = await backend.compact()
    assert comp is not None

    snap = safe_metrics_snapshot(backend)
    assert isinstance(snap, dict)
    assert "records_written" in snap

    await backend.aclose()


def test_safe_metrics_snapshot_is_safe_on_non_metrics_backend() -> None:
    class NoMetrics:
        pass

    snap = safe_metrics_snapshot(NoMetrics())
    assert snap == {}
