import os
import re
import uuid

import pytest
from sayer.testing import SayerTestClient

from papyra import monkay
from papyra.cli.app import app
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.persistence.backends.retention import RetentionPolicy


def parse_cli_output(output_string):
    """
    Parses a CLI table with Unicode borders into a clean dictionary.

    Args:
        output_string (str): The raw output from the CLI runner.

    Returns:
        dict: A dictionary of {key: value} strings.
    """
    data = {}

    # Regex to handle both '┃' (bold) and '│' (thin) vertical bars
    # and strip ANSI color codes if present.
    lines = output_string.splitlines()

    for line in lines:
        # 1. Skip pure border lines (lines consisting only of box chars)
        if re.match(r"^[\u2500-\u257F]+$", line):
            continue

        # 2. Look for lines that look like: "┃  key  ┃  value  ┃"
        # We split by the vertical bar characters
        parts = re.split(r"[│┃]", line)

        # 3. If we found enough parts (usually [empty, key, value, empty])
        if len(parts) >= 3:
            key = parts[1].strip()
            val = parts[2].strip()

            # Filter out header rows like "Key" and "Value"
            if key and val and key != "Key":
                data[key] = val

    return data


@pytest.fixture(scope="function")
def persistence() -> InMemoryPersistence:
    backend = InMemoryPersistence()
    backend.metrics.reset()
    monkay.settings.persistence = backend
    return backend


@pytest.fixture()
def cli(persistence: InMemoryPersistence) -> SayerTestClient:
    return SayerTestClient(app)


@pytest.fixture(scope="module", params=["asyncio", "trio"])
def anyio_backend():
    return ("asyncio", {"debug": True})


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


async def _redis_available(url: str) -> bool:
    try:
        import redis.asyncio as redis_async  # type: ignore
    except Exception:
        return False

    try:
        client = redis_async.Redis.from_url(url, decode_responses=True)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


@pytest.fixture
async def redis_backend():
    try:
        from papyra.persistence.backends.redis import RedisStreamsConfig, RedisStreamsPersistence
    except Exception:
        pytest.skip("Redis backend not available (install papyra[redis])")

    url = _redis_url()
    if not await _redis_available(url):
        pytest.skip(f"Redis not available at {url!r} (set REDIS_URL or start Redis)")

    prefix = f"papyra_test_metrics_{uuid.uuid4().hex}"
    cfg = RedisStreamsConfig(
        url=url,
        prefix=prefix,
        system_id="local",
        scan_sample_size=2000,
        max_read=50_000,
        approx_trim=False,
        quarantine_prefix=f"{prefix}:quarantine",
    )

    backend = RedisStreamsPersistence(cfg, retention_policy=RetentionPolicy())
    yield backend

    try:
        keys = [
            backend._events_key,  # noqa: SLF001
            backend._audits_key,  # noqa: SLF001
            backend._dead_letters_key,  # noqa: SLF001
            backend._quarantine_key(backend._events_key),  # noqa: SLF001
            backend._quarantine_key(backend._audits_key),  # noqa: SLF001
            backend._quarantine_key(backend._dead_letters_key),  # noqa: SLF001
        ]
        await backend._redis.delete(*keys)  # noqa: SLF001
    except Exception:
        pass

    await backend.aclose()
