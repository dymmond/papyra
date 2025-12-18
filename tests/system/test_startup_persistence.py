import pytest

from papyra.actor import Actor
from papyra.persistence.json import JsonFilePersistence
from papyra.persistence.models import (
    PersistenceRecoveryConfig,
    PersistenceRecoveryMode,
)
from papyra.persistence.startup import (
    PersistenceStartupConfig,
    PersistenceStartupMode,
)
from papyra.system import ActorSystem

pytestmark = pytest.mark.anyio


async def test_startup_fails_if_corruption_and_fail_on_anomaly(tmp_path):
    path = tmp_path / "events.ndjson"

    # Corrupted / truncated line
    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    persistence = JsonFilePersistence(path)

    system = ActorSystem(
        persistence=persistence,
        persistence_startup=PersistenceStartupConfig(mode=PersistenceStartupMode.FAIL_ON_ANOMALY),
    )

    with pytest.raises(RuntimeError, match="Persistence anomalies detected"):
        await system.start()


async def test_startup_recovers_then_succeeds(tmp_path):
    path = tmp_path / "events.ndjson"

    # Truncated JSON
    path.write_text(
        '{"kind": "event", "timestamp": 1}\n{"kind": "event"',
        encoding="utf-8",
    )

    persistence = JsonFilePersistence(path)

    system = ActorSystem(
        persistence=persistence,
        persistence_startup=PersistenceStartupConfig(
            mode=PersistenceStartupMode.RECOVER,
            recovery=PersistenceRecoveryConfig(mode=PersistenceRecoveryMode.REPAIR),
        ),
    )

    await system.start()

    # Corruption must be fixed
    contents = path.read_text(encoding="utf-8")
    assert contents.strip() == '{"kind": "event", "timestamp": 1}'

    await system.aclose()


class FlagActor(Actor):
    async def on_start(self):
        raise AssertionError("Actor started before persistence startup completed")


async def test_actor_never_starts_if_persistence_startup_fails(tmp_path):
    path = tmp_path / "events.ndjson"

    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    persistence = JsonFilePersistence(path)

    system = ActorSystem(
        persistence=persistence,
        persistence_startup=PersistenceStartupConfig(mode=PersistenceStartupMode.FAIL_ON_ANOMALY),
    )

    with pytest.raises(RuntimeError):
        await system.start()

    # Task group never created -> spawn forbidden
    with pytest.raises(Exception):  # noqa
        system.spawn(FlagActor)
