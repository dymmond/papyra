from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from papyra.contrib.fastapi import FastAPIPapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem

pytestmark = pytest.mark.anyio


def test_fastapi_endpoints_healthz_and_metrics():
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    integ = FastAPIPapyra(make_system)

    app = FastAPI()
    integ.install(app)

    client = TestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["mode"] == "scan"

    response = client.get("/metrics")
    assert response.status_code == 200

    data = response.json()

    assert "records_written" in data
    assert "write_errors" in data
