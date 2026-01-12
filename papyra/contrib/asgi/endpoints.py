from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping

from papyra.persistence.models import PersistenceScanReport
from papyra.persistence.startup import PersistenceStartupConfig, PersistenceStartupMode
from papyra.serializers import serializer
from papyra.system import ActorSystem


def _base_response(
    status: int,
    payload: Mapping[str, Any] | str | PersistenceScanReport,
    media_type: str = "application/json",
) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """
    Helper to create a base response for ASGI endpoints.

    Args:
        status: HTTP status code.
        payload: The payload to serialize as JSON or plain text.
    Returns:
        A tuple of (status, headers, body) suitable for ASGI response.
    """
    media = f"{media_type}; charset=utf-8"
    body = serializer.dumps(payload).encode("utf-8")
    headers = [
        (b"Content-Type", media.encode("ascii")),
        (b"Content-Length", str(len(body)).encode("ascii")),
    ]
    return status, headers, body


def _json_response(status: int, payload: Any) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """
    Helper to create a JSON response for ASGI endpoints.

    Args:
        status: HTTP status code.
        payload: The payload to serialize as JSON.

    Returns:
        A tuple of (status, headers, body) suitable for ASGI response.
    """
    return _base_response(status, payload, media_type="application/json")


def _text_response(status: int, payload: Any) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """
    Helper to create a plain text response for ASGI endpoints.

    Args:
        status: HTTP status code.
        payload: The payload to serialize as plain text.

    Returns:
        A tuple of (status, headers, body) suitable for ASGI response.
    """
    return _base_response(status, payload, media_type="text/plain")


async def healthz(
    scope: dict[str, Any],
    receive: Callable[[], Any],
    send: Callable[[dict[str, Any]], Any],
    *,
    system: ActorSystem,
    mode: str = "scan",
    startup_config: PersistenceStartupConfig | None = None,
) -> None:
    """
    Framework agnostic ASGI health check endpoint.

    mode:
        - "scan": calls backend.scan() and reports anomalies.
        - "startup_check": mimics ActorSystem startup behaviour "without" starting actors (scan + maybe recorver depending on startup_config).
    """

    if scope["type"] != "http":
        return

    status: int = 200
    payload: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "backend": type(system.persistence).__name__,
    }

    try:
        backend = system.persistence

        if mode == "scan":
            scan: PersistenceScanReport = await backend.scan()

            if scan is None:
                payload["ok"] = True
                payload["scan_supported"] = False
            else:
                payload["scan_supported"] = True
                payload["anomalies"] = [asdict(anomaly) for anomaly in scan.anomalies]

                if scan.has_anomalies:
                    payload["ok"] = False
                    status = 503

        elif mode == "startup-check":
            config = startup_config or PersistenceStartupConfig(mode=PersistenceStartupMode.FAIL_ON_ANOMALY)

            scan = await backend.scan()

            if scan is None or not scan.has_anomalies:
                payload["ok"] = True
                payload["anomalies"] = []
            else:
                payload["anomalies"] = [asdict(anomaly) for anomaly in scan.anomalies]

                if config.mode is PersistenceStartupMode.FAIL_ON_ANOMALY:
                    payload["ok"] = False
                    status = 503
                elif config.mode is PersistenceStartupMode.RECOVER:
                    rep = await backend.recover(config.recovery)
                    post = await backend.scan()
                    payload["recovery"] = asdict(rep) if rep is not None else None
                    payload["post_anomalies"] = [] if post is None else [asdict(anomaly) for anomaly in post.anomalies]

                    if post is not None and post.has_anomalies:
                        payload["ok"] = False
                        status = 503
        else:
            payload = {"ok": False, "error": f"invalid mode: {mode!r}"}
            status = 400
    except Exception as e:
        payload = {"ok": False, "error": type(e).__name__, "message": e}
        status = 500

    code, headers, body = _json_response(status, payload)
    await send(
        {
            "type": "http.response.start",
            "status": code,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
        }
    )


async def metrics(
    scope: dict[str, Any],
    receive: Callable[[], Any],
    send: Callable[[dict[str, Any]], Any],
    *,
    system: ActorSystem,
    format: str = "json",
) -> None:
    """
    Framework agnostic ASGI metrics endpoint.

    format:
        - "json": returns metrics as JSON.
    """

    if scope["type"] != "http":
        return

    backend = system.persistence

    snap: Mapping[str, Any] | None = None

    try:
        snap = backend.metrics.snapshot()
        if not snap:
            snap = None
    except Exception:
        snap = None

    if format == "json":
        if snap is None:
            code, headers, body = _text_response(200, "metrics: <unavailable>")
        else:
            lines = ["Persistence Metrics", "-------------------"]
            for key, value in snap.items():
                lines.append(f"{key}: {value}")

            code, headers, body = _text_response(200, "\n".join(lines))
    else:
        code, headers, body = _text_response(200, dict(snap or {}))

    await send(
        {
            "type": "http.response.start",
            "status": code,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
        }
    )
