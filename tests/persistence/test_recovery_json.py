import pytest

from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import PersistenceRecoveryConfig, PersistenceRecoveryMode

pytestmark = pytest.mark.anyio


async def test_json_recover_repairs_truncated_last_line(tmp_path):
    path = tmp_path / "events.log"

    # Valid line + truncated garbage (no newline)
    path.write_text('{"kind":"event","timestamp":1}\n{"kind":"event",', encoding="utf-8")

    backend = JsonFilePersistence(path)

    report = await backend.recover(PersistenceRecoveryConfig(mode=PersistenceRecoveryMode.REPAIR))

    data = path.read_text(encoding="utf-8").splitlines()
    assert data == ['{"kind": "event", "timestamp": 1}']
    assert report is not None
    assert report.repaired_files == (str(path),)


async def test_json_recover_quarantines_original(tmp_path):
    path = tmp_path / "events.log"
    qdir = tmp_path / "quarantine"

    path.write_text('{"kind":"event","timestamp":1}\n{"kind":\n', encoding="utf-8")

    backend = JsonFilePersistence(path)
    report = await backend.recover(
        PersistenceRecoveryConfig(
            mode=PersistenceRecoveryMode.QUARANTINE,
            quarantine_dir=str(qdir),
        )
    )

    assert report is not None
    assert len(report.quarantined_files) == 1
    assert qdir.exists()

    data = path.read_text(encoding="utf-8").splitlines()
    assert data == ['{"kind": "event", "timestamp": 1}']
