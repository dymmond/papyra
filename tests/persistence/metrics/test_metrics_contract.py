import pytest

pytestmark = pytest.mark.anyio


async def test_assert_write_metrics(persistence):
    await persistence.record_event(type("Evt", (), {"timestamp": 1})())  # dummy

    snap = persistence.metrics.snapshot()
    assert snap["records_written"] == 1
    assert snap["write_errors"] == 0


async def test_assert_scan_metrics(persistence):
    await persistence.scan()

    snap = persistence.metrics.snapshot()
    assert snap["scans"] == 1


async def test_assert_compact_metrics(persistence):
    await persistence.compact()

    snap = persistence.metrics.snapshot()
    assert snap["compactions"] == 1
