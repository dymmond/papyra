"""Benchmarks for core papyra components."""

from __future__ import annotations

import pytest

from papyra.address import ActorAddress
from papyra.events import ActorCrashed, ActorStarted, _to_plain
from papyra.persistence.models import PersistedEvent
from papyra.serializers import CompactSerializer

# ---------------------------------------------------------------------------
# ActorAddress
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_address_creation():
    """Benchmark creating ActorAddress instances."""
    for _ in range(1000):
        ActorAddress(system="local", actor_id=42)


@pytest.mark.benchmark
def test_address_parse():
    """Benchmark parsing address strings."""
    for _ in range(1000):
        ActorAddress.parse("local:42")


@pytest.mark.benchmark
def test_address_to_dict():
    """Benchmark address serialization to dict."""
    addr = ActorAddress(system="local", actor_id=42)
    for _ in range(1000):
        addr.to_dict()


@pytest.mark.benchmark
def test_address_str():
    """Benchmark address string representation."""
    addr = ActorAddress(system="local", actor_id=42)
    for _ in range(1000):
        str(addr)


# ---------------------------------------------------------------------------
# Event creation and payload serialization
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_event_creation_started():
    """Benchmark creating ActorStarted events."""
    address = {"system": "local", "actor_id": 1}
    for _ in range(1000):
        ActorStarted(address=address)


@pytest.mark.benchmark
def test_event_creation_crashed():
    """Benchmark creating ActorCrashed events."""
    address = {"system": "local", "actor_id": 1}
    exc = RuntimeError("test error")
    for _ in range(1000):
        ActorCrashed(address=address, error=exc, reason="RuntimeError: test error")


@pytest.mark.benchmark
def test_event_payload_serialization():
    """Benchmark event payload generation."""
    address = {"system": "local", "actor_id": 1}
    event = ActorCrashed(address=address, error=RuntimeError("boom"), reason="RuntimeError: boom")
    result = None
    for _ in range(1000):
        result = event.payload
    assert result is not None


# ---------------------------------------------------------------------------
# _to_plain serialization
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_to_plain_primitives():
    """Benchmark _to_plain with primitive types."""
    for _ in range(1000):
        _to_plain("hello")
        _to_plain(42)
        _to_plain(3.14)
        _to_plain(True)
        _to_plain(None)


@pytest.mark.benchmark
def test_to_plain_nested_dict():
    """Benchmark _to_plain with nested dictionary."""
    data = {
        "actors": [{"name": f"actor-{i}", "status": "alive", "messages": i * 10} for i in range(20)],
        "system": {"id": "local", "version": "0.1.1"},
    }
    for _ in range(1000):
        _to_plain(data)


@pytest.mark.benchmark
def test_to_plain_exception():
    """Benchmark _to_plain with exception objects."""
    exc = RuntimeError("connection failed")
    for _ in range(1000):
        _to_plain(exc)


# ---------------------------------------------------------------------------
# CompactSerializer (JSON)
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_compact_serializer_dumps():
    """Benchmark CompactSerializer.dumps."""
    data = {"system": "local", "actor_id": 42, "event": "started", "payload": {"key": "value"}}
    for _ in range(1000):
        CompactSerializer.dumps(data)


@pytest.mark.benchmark
def test_compact_serializer_loads():
    """Benchmark CompactSerializer.loads."""
    raw = '{"system":"local","actor_id":42,"event":"started","payload":{"key":"value"}}'
    for _ in range(1000):
        CompactSerializer.loads(raw)


@pytest.mark.benchmark
def test_compact_serializer_roundtrip():
    """Benchmark serialize/deserialize roundtrip."""
    data = {"actors": [{"id": i, "name": f"actor-{i}"} for i in range(50)]}
    for _ in range(500):
        raw = CompactSerializer.dumps(data)
        CompactSerializer.loads(raw)


# ---------------------------------------------------------------------------
# PersistedEvent creation
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
def test_persisted_event_creation():
    """Benchmark creating PersistedEvent instances."""
    addr = ActorAddress(system="local", actor_id=1)
    for _ in range(1000):
        PersistedEvent(
            system_id="local",
            actor_address=addr,
            event_type="ActorStarted",
            payload={},
            timestamp=1234567890.0,
        )
