from __future__ import annotations

import pytest

from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


async def test_redis_write_metrics(redis_backend):
    before = redis_backend.metrics.snapshot()

    await redis_backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )

    snap = redis_backend.metrics.snapshot()
    assert snap["records_written"] == before["records_written"] + 1
    assert snap["bytes_written"] >= before["bytes_written"]


async def test_redis_scan_anomaly_metrics(redis_backend):
    before = redis_backend.metrics.snapshot()

    # Insert invalid JSON directly
    await redis_backend._redis.xadd(redis_backend._events_key, {"data": "{not-json"})  # noqa: SLF001

    scan = await redis_backend.scan()
    assert scan.has_anomalies

    snap = redis_backend.metrics.snapshot()
    assert snap["scans"] == before["scans"] + 1
    assert snap["anomalies_detected"] >= before["anomalies_detected"] + 1
