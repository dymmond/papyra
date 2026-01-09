import pytest

from papyra.persistence.backends.rotating import RotatingFilePersistence
from papyra.persistence.models import PersistenceRecoveryConfig, PersistenceRecoveryMode

pytestmark = pytest.mark.anyio


async def test_rotating_recover_repairs_truncated_lines(tmp_path):
    path = tmp_path / "rot.log"

    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    backend = RotatingFilePersistence(path, max_bytes=100, max_files=3)

    report = await backend.recover(PersistenceRecoveryConfig(mode=PersistenceRecoveryMode.REPAIR))

    assert report is not None
    assert report.repaired_files

    # rebuilt content is authoritative
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"kind": "event", "timestamp": 1}']


async def test_rotating_recover_quarantines_orphaned_files(tmp_path):
    path = tmp_path / "rot.log"

    orphan = tmp_path / "rot.log.orphan"
    orphan.write_text('{"kind":"event","timestamp":999}\n', encoding="utf-8")

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

    # Orphan is detected
    assert report.scan.has_anomalies
    assert any(a.type.name == "ORPHANED_ROTATED_FILE" and a.path == str(orphan) for a in report.scan.anomalies)

    # Recovery correctness is preserved
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"kind": "event", "timestamp": 1}']

    # Orphan is intentionally left untouched
    assert orphan.exists()
