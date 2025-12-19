import pytest

from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


async def test_json_write_metrics(tmp_path):
    path = tmp_path / "events.ndjson"
    backend = JsonFilePersistence(path)

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


async def test_json_scan_anomaly_metrics(tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text('{"kind":"event","timestamp":1}\n{"kind"', encoding="utf-8")

    backend = JsonFilePersistence(path)
    report = await backend.scan()

    snap = backend.metrics.snapshot()
    assert snap["scans"] == 1
    assert snap["anomalies_detected"] == len(report.anomalies)
