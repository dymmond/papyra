from __future__ import annotations

import pytest

from papyra import monkay
from papyra.conf import settings
from papyra.persistence.json import JsonFilePersistence

pytestmark = pytest.mark.anyio


def test_doctor_healthy(cli):
    result = cli.invoke("doctor run")
    assert result.exit_code == 0
    assert "Persistence is healthy" in result.output


def test_doctor_fail_on_anomaly(cli, tmp_path, monkeypatch):
    # Swap persistence to JSON file that contains corruption
    path = tmp_path / "events.ndjson"
    path.write_text('{"kind":"event","timestamp":1}\n{"kind":"event"', encoding="utf-8")

    backend = JsonFilePersistence(path)
    monkeypatch.setattr(monkay.settings, "persistence", backend, raising=False)

    result = cli.invoke("doctor run --mode fail_on_anomaly")

    assert result.exit_code != 0
    assert "anomal" in result.output.lower()


def test_doctor_recover_repairs(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text('{"kind":"event","timestamp":1}\n{"kind":"event"', encoding="utf-8")

    settings.persistence = JsonFilePersistence(path)

    result = cli.invoke("doctor run --mode recover --recovery-mode repair")

    assert result.exit_code == 0
    assert "Recovery successful" in result.output

    # should be repaired
    assert path.read_text(encoding="utf-8").strip() == '{"kind": "event", "timestamp": 1}'


def test_doctor_recover_quarantine_requires_dir(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text('{"kind":"event","timestamp":1}\n{"kind":"event"', encoding="utf-8")

    settings.persistence = JsonFilePersistence(path)

    # no quarantine dir -> should exit non-zero
    result = cli.invoke("doctor run --mode recover --recovery-mode quarantine")
    assert result.exit_code != 0
