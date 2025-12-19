import re

import pytest
from sayer.testing import SayerTestClient

from papyra import monkay
from papyra.cli.app import app
from papyra.persistence.memory import InMemoryPersistence


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
