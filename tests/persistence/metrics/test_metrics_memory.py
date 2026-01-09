import pytest

from papyra.persistence.backends.memory import InMemoryPersistence

pytestmark = pytest.mark.anyio


async def test_memory_write_metrics():
    backend = InMemoryPersistence()

    await backend.record_event(type("Evt", (), {"timestamp": 1})())
    await backend.record_audit(type("Audit", (), {"timestamp": 2})())

    snap = backend.metrics.snapshot()
    assert snap["records_written"] == 2
    assert snap["write_errors"] == 0


async def test_memory_scan_metrics():
    backend = InMemoryPersistence()

    await backend.scan()

    snap = backend.metrics.snapshot()
    assert snap["scans"] == 1
    assert snap["anomalies_detected"] == 0


async def test_memory_compact_metrics():
    backend = InMemoryPersistence()

    await backend.compact()

    snap = backend.metrics.snapshot()
    assert snap["compactions"] == 1
