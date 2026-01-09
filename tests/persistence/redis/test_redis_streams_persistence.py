from __future__ import annotations

import uuid

import pytest

from papyra.persistence.backends.retention import RetentionPolicy
from papyra.persistence.models import (
    PersistedAudit,
    PersistedDeadLetter,
    PersistedEvent,
    PersistenceAnomalyType,
    PersistenceRecoveryConfig,
    PersistenceRecoveryMode,
)
from tests.conftest import _redis_available, _redis_url

pytestmark = pytest.mark.anyio


async def test_redis_event_is_persisted_and_read_back(redis_backend):
    ev = PersistedEvent(
        system_id="local",
        actor_address="local://1",
        event_type="ActorStarted",
        payload={},
        timestamp=1.0,
    )
    await redis_backend.record_event(ev)

    events = await redis_backend.list_events()
    assert len(events) == 1
    assert events[0].event_type == "ActorStarted"
    assert str(events[0].actor_address) == "local://1"
    assert events[0].timestamp == 1.0


async def test_redis_audit_is_persisted_and_read_back(redis_backend):
    au = PersistedAudit(
        system_id="local",
        timestamp=2.0,
        total_actors=10,
        alive_actors=8,
        stopping_actors=1,
        restarting_actors=1,
        registry_size=5,
        registry_orphans=(),
        registry_dead=(),
        dead_letters_count=0,
    )
    await redis_backend.record_audit(au)

    audits = await redis_backend.list_audits()
    assert len(audits) == 1
    assert audits[0].total_actors == 10
    assert audits[0].alive_actors == 8


async def test_redis_dead_letter_is_persisted_and_read_back(redis_backend):
    dl = PersistedDeadLetter(
        system_id="local",
        target="local://9",
        message_type="str",
        payload="hello",
        timestamp=3.0,
    )
    await redis_backend.record_dead_letter(dl)

    dls = await redis_backend.list_dead_letters()
    assert len(dls) == 1
    assert str(dls[0].target) == "local://9"
    assert dls[0].message_type == "str"
    assert dls[0].payload == "hello"


async def test_redis_retention_max_records_applies_on_reads(tmp_path):
    """
    This test requires RetentionPolicy to support max_records.
    If your RetentionPolicy does not expose it, we skip.
    """
    try:
        from papyra.persistence.backends.redis import RedisStreamsConfig, RedisStreamsPersistence
    except Exception:
        pytest.skip("Redis backend not available (install papyra[redis])")

    url = _redis_url()
    if not await _redis_available(url):
        pytest.skip("Redis not available")

    rp = RetentionPolicy(max_records=2)
    if not hasattr(rp, "max_records"):
        pytest.skip("RetentionPolicy has no max_records field")

    prefix = f"papyra_test_{uuid.uuid4().hex}"
    cfg = RedisStreamsConfig(url=url, prefix=prefix, system_id="local")
    backend = RedisStreamsPersistence(cfg, retention_policy=rp)

    try:
        for i in range(5):
            await backend.record_event(
                PersistedEvent(
                    system_id="local",
                    actor_address=f"local://{i}",
                    event_type="ActorStarted",
                    payload={},
                    timestamp=float(i),
                )
            )

        events = await backend.list_events()
        # logical retention -> only last 2
        assert len(events) == 2
        assert str(events[0].actor_address) == "local://3"
        assert str(events[1].actor_address) == "local://4"
    finally:
        try:
            await backend._redis.delete(backend._events_key, backend._audits_key, backend._dead_letters_key)  # noqa: SLF001
        except Exception:
            pass
        await backend.aclose()


async def test_redis_scan_detects_corrupted_payload(redis_backend):
    # Insert a corrupted entry directly in Redis stream.
    await redis_backend._redis.xadd(redis_backend._events_key, {"data": "{not-json"})  # noqa: SLF001

    scan = await redis_backend.scan()
    assert scan.has_anomalies

    # At least one corrupted anomaly for the events key.
    assert any(a.type == PersistenceAnomalyType.CORRUPTED_LINE for a in scan.anomalies)


async def test_redis_recover_repair_deletes_bad_entries(redis_backend):
    await redis_backend._redis.xadd(redis_backend._events_key, {"data": "{not-json"})  # noqa: SLF001

    scan1 = await redis_backend.scan()
    assert scan1.has_anomalies

    report = await redis_backend.recover(PersistenceRecoveryConfig(mode=PersistenceRecoveryMode.REPAIR))
    assert report is not None

    scan2 = await redis_backend.scan()
    assert not scan2.has_anomalies


async def test_redis_recover_quarantine_moves_bad_entries(redis_backend):
    await redis_backend._redis.xadd(redis_backend._events_key, {"data": "{not-json"})  # noqa: SLF001

    qkey = redis_backend._quarantine_key(redis_backend._events_key)  # noqa: SLF001

    report = await redis_backend.recover(
        PersistenceRecoveryConfig(
            mode=PersistenceRecoveryMode.QUARANTINE,
            quarantine_dir="ignored-for-redis",
        )
    )
    assert report is not None

    # Ensure quarantine stream got at least one entry.
    qlen = await redis_backend._redis.xlen(qkey)  # noqa: SLF001
    assert qlen >= 1

    scan2 = await redis_backend.scan()
    assert not scan2.has_anomalies


async def test_redis_compaction_trims_when_max_records_supported(tmp_path):
    """
    Redis compaction uses XTRIM only if retention.max_records exists.
    """
    try:
        from papyra.persistence.backends.redis import RedisStreamsConfig, RedisStreamsPersistence
    except Exception:
        pytest.skip("Redis backend not available (install papyra[redis])")

    url = _redis_url()
    if not await _redis_available(url):
        pytest.skip("Redis not available")

    rp = RetentionPolicy(max_records=1)
    if not hasattr(rp, "max_records"):
        pytest.skip("RetentionPolicy has no max_records field")

    prefix = f"papyra_test_{uuid.uuid4().hex}"
    cfg = RedisStreamsConfig(url=url, prefix=prefix, system_id="local", approx_trim=False)
    backend = RedisStreamsPersistence(cfg, retention_policy=rp)

    try:
        for i in range(3):
            await backend.record_event(
                PersistedEvent(
                    system_id="local",
                    actor_address=f"local://{i}",
                    event_type="ActorStarted",
                    payload={},
                    timestamp=float(i),
                )
            )

        before_len = await backend._redis.xlen(backend._events_key)  # noqa: SLF001
        report = await backend.compact()
        after_len = await backend._redis.xlen(backend._events_key)  # noqa: SLF001

        assert before_len >= 3
        assert after_len <= 1
        assert report.backend == "redis"
        assert report.before_records >= report.after_records
    finally:
        try:
            await backend._redis.delete(backend._events_key, backend._audits_key, backend._dead_letters_key)  # noqa: SLF001
        except Exception:
            pass
        await backend.aclose()
