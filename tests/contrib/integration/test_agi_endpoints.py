from __future__ import annotations

import pytest

from papyra.contrib.asgi.endpoints import healthz, metrics
from papyra.persistence.models import (
    PersistenceAnomaly,
    PersistenceAnomalyType,
    PersistenceScanReport,
)
from papyra.serializers import serializer

pytestmark = pytest.mark.anyio


class FakeBackend:
    def __init__(self, *, anomalies: int = 0, scan_supported: bool = True) -> None:
        self._scan_supported = scan_supported
        self._anonalies = anomalies
        self._recovered = False

        class _Metrics:
            def snapshot(self):
                return {
                    "records_written": 1,
                    "bytes_written": 10,
                    "scans": 2,
                    "anomalies_detected": 3,
                    "recoveries": 4,
                    "compactions": 5,
                    "write_errors": 0,
                    "scan_errors": 0,
                    "recovery_errors": 0,
                    "compaction_errors": 0,
                }

        self._metrics = _Metrics()

    @property
    def metrics(self):
        return self._metrics

    async def scan(self):
        if not self._scan_supported:
            return None

        anomalies = []

        for i in range(self._anonalies):
            anomalies.append(
                PersistenceAnomaly(type=PersistenceAnomalyType.CORRUPTED_LINE, path="fake", detail=f"bad {i}")
            )

        return PersistenceScanReport(backend="fake", anomalies=tuple(anomalies))

    async def recover(self, cfg):
        self._recovered = True
        return None


class FakeSystem:
    def __init__(self, backend: FakeBackend) -> None:
        self._persistence = backend

    @property
    def persistence(self) -> FakeBackend:
        return self._persistence


async def call_asgi(app, *, path: str) -> tuple[int, dict[str, str], bytes]:
    body_parts: list[bytes] = []
    status_code: int | None = None
    headers: dict[str, str] = {}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code, headers

        if message["type"] == "http.response.start":
            status_code = message["status"]
            for name, value in message.get("headers", []):
                headers[name.decode()] = value.decode()
        elif message["type"] == "http.response.body":
            body_parts.append(message.get("body", b""))

    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
    }

    await app(scope, receive, send)
    assert status_code is not None
    return status_code, headers, b"".join(body_parts)


async def test_healthz_scan_ok_returns_200():
    sys = FakeSystem(backend=FakeBackend(anomalies=0))

    async def app(scope, receive, send):
        return await healthz(scope, receive, send, system=sys, mode="scan", startup_config=None)

    status, _, body = await call_asgi(app, path="/healthz")
    assert status == 200

    payload = serializer.loads(body.decode())

    assert payload["ok"] is True
    assert payload["anomalies"] == []
    assert payload["mode"] == "scan"


async def test_healthz_scan_ok_returns_503():
    sys = FakeSystem(backend=FakeBackend(anomalies=2))

    async def app(scope, receive, send):
        return await healthz(scope, receive, send, system=sys, mode="scan", startup_config=None)

    status, _, body = await call_asgi(app, path="/healthz")
    assert status == 503

    payload = serializer.loads(body.decode())

    assert payload["ok"] is False
    assert len(payload["anomalies"]) == 2
    assert payload["mode"] == "scan"


async def test_metrics_json_returns_snapshot():
    sys = FakeSystem(backend=FakeBackend())

    async def app(scope, receive, send):
        return await metrics(scope, receive, send, system=sys, format="json")

    status, headers, body = await call_asgi(app, path="/metrics")

    assert status == 200
    assert "application/json" in headers.get("content-type", "")

    payload = serializer.loads(body.decode())

    assert payload["records_written"] == 1
    assert payload["bytes_written"] == 10
    assert "scan_errors" in payload


async def test_metrics_text_returns_text():
    sys = FakeSystem(backend=FakeBackend())

    async def app(scope, receive, send):
        return await metrics(scope, receive, send, system=sys, format="text")

    status, headers, body = await call_asgi(app, path="/metrics")

    assert status == 200
    assert "text/plain" in headers.get("content-type", "")

    text = body.decode()

    assert "Persistence Metrics" in text
    assert "records_written" in text
    assert "bytes_written" in text
    assert "scan_errors" in text
