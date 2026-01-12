from __future__ import annotations

import pytest
from ravyn import Ravyn
from ravyn.testclient import RavynTestClient

from papyra.contrib.ravyn import RavynPapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem

pytestmark = pytest.mark.anyio


def test_ravyn_endpoints_healthz_and_metrics():
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    integ = RavynPapyra(make_system)

    app = Ravyn()
    integ.install(app)

    client = RavynTestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["mode"] == "scan"

    response = client.get("/metrics")
    assert response.status_code == 200

    data = response.json()

    assert "records_written" in data
    assert "write_errors" in data
