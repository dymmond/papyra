from __future__ import annotations

import pytest
from lilya.apps import Lilya
from lilya.testclient import TestClient

from papyra.contrib.lilya import LilyaPapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem

pytestmark = pytest.mark.anyio


def test_lilya_endpoints_healthz_and_metrics():
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    integ = LilyaPapyra(make_system)

    app = Lilya()
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
