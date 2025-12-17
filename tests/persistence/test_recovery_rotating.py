import pytest

from papyra.persistence.models import PersistenceRecoveryConfig, PersistenceRecoveryMode
from papyra.persistence.rotating import RotatingFilePersistence

pytestmark = pytest.mark.anyio


async def test_rotating_recover_repairs_truncated_lines(tmp_path):
    path = tmp_path / "rot.log"

    # active file has truncated last line
    path.write_text('{"kind":"event","timestamp":1}\n{"kind":"event"', encoding="utf-8")

    backend = RotatingFilePersistence(path, max_bytes=100, max_files=3)

    report = await backend.recover(PersistenceRecoveryConfig(mode=PersistenceRecoveryMode.REPAIR))

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"kind": "event", "timestamp": 1}']
    assert report is not None
    assert str(path) in report.repaired_files


async def test_rotating_recover_quarantines_orphaned_files(tmp_path):
    path = tmp_path / "rot.log"

    # Create orphan file (unexpected suffix)
    orphan = tmp_path / "rot.log.orphan"
    orphan.write_text('{"kind":"event","timestamp":999}\n', encoding="utf-8")

    # Valid active file
    path.write_text('{"kind":"event","timestamp":1}\n', encoding="utf-8")

    backend = RotatingFilePersistence(path, max_bytes=100, max_files=2)

    qdir = tmp_path / "quarantine"
    report = await backend.recover(
        PersistenceRecoveryConfig(
            mode=PersistenceRecoveryMode.QUARANTINE,
            quarantine_dir=str(qdir),
        )
    )

    assert report is not None
    assert len(report.quarantined_files) >= 1
    assert not orphan.exists()
    assert qdir.exists()
