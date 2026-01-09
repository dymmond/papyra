from __future__ import annotations

from uuid import uuid4

import pytest

from papyra.persistence.models import PersistedEvent
from papyra.persistence.retention import RetentionPolicy
from tests.conftest import _redis_available, _redis_url

pytestmark = pytest.mark.anyio


async def test_redis_group_read_ack_roundtrip(tmp_path):
    prefix = f"papyra-test-group-1-{uuid4().hex}"
    try:
        from papyra.persistence.redis import (
            RedisConsumerGroupConfig,
            RedisStreamsConfig,
            RedisStreamsPersistence,
        )
    except Exception:
        pytest.skip("Redis backend not available (install papyra[redis])")

    url = _redis_url()
    if not await _redis_available(url):
        pytest.skip("Redis not available")

    cfg = RedisStreamsConfig(url=url, prefix=prefix)
    backend = RedisStreamsPersistence(cfg, retention_policy=RetentionPolicy())

    # Write 3 events
    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )
    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://2",
            event_type="ActorStarted",
            payload={},
            timestamp=2.0,
        )
    )
    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://3",
            event_type="ActorStarted",
            payload={},
            timestamp=3.0,
        )
    )

    group_cfg = RedisConsumerGroupConfig(group="g1", consumer="c1", count=10, block_ms=100)

    # Read new messages
    items = await backend.consume(kind="events", cfg=group_cfg, read_id=">")
    assert len(items) >= 3

    ids = [i.id for i in items]
    assert any(i.data.get("actor_address") == "local://1" for i in items)

    # Ack them
    acked = await backend.ack(kind="events", group="g1", ids=ids)
    assert acked >= 1

    # Pending should be 0 afterwards (eventually)
    pending = await backend.pending_summary(kind="events", group="g1")
    assert pending["raw"]["pending"] == 0


async def test_redis_pending_and_claim(tmp_path):
    prefix = f"papyra-test-group-2-{uuid4().hex}"
    try:
        from papyra.persistence.redis import (
            RedisConsumerGroupConfig,
            RedisStreamsConfig,
            RedisStreamsPersistence,
        )
    except Exception:
        pytest.skip("Redis backend not available (install papyra[redis])")

    url = _redis_url()
    if not await _redis_available(url):
        pytest.skip("Redis not available")

    cfg = RedisStreamsConfig(url=url, prefix=prefix)
    backend = RedisStreamsPersistence(cfg, retention_policy=RetentionPolicy())

    await backend.record_event(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=9.0,
        )
    )

    group = f"g2-{uuid4().hex[:8]}"
    gcfg1 = RedisConsumerGroupConfig(group=group, consumer="c1", count=10, block_ms=100)
    RedisConsumerGroupConfig(group=group, consumer="c2", count=10, block_ms=100)

    # c1 reads but does NOT ack → message becomes pending
    items = await backend.consume(kind="events", cfg=gcfg1, read_id=">")
    assert items
    entry_id = items[0].id

    pending = await backend.pending_summary(kind="events", group=group)
    assert pending["raw"]["pending"] >= 1

    # c2 claims it (idle=0ms so it can be claimed immediately)
    claimed = await backend.claim(
        kind="events",
        group=group,
        consumer="c2",
        min_idle_ms=0,
        entry_ids=[entry_id],
    )
    assert claimed
    assert claimed[0].id == entry_id

    # Now c2 acks it
    acked = await backend.ack(kind="events", group=group, ids=[entry_id])
    assert acked == 1

    pending2 = await backend.pending_summary(kind="events", group=group)
    assert pending2["raw"]["pending"] == 0
