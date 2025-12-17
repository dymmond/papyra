import pytest
from sayer.testing import SayerTestClient

from papyra import monkay
from papyra.cli.app import app
from papyra.persistence.memory import InMemoryPersistence


@pytest.fixture()
def persistence() -> InMemoryPersistence:
    backend = InMemoryPersistence()
    monkay.settings.persistence = backend
    return backend


@pytest.fixture()
def cli(persistence: InMemoryPersistence) -> SayerTestClient:
    return SayerTestClient(app)


@pytest.fixture(scope="module", params=["asyncio", "trio"])
def anyio_backend():
    return ("asyncio", {"debug": True})
