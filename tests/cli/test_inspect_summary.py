import pytest

from papyra.persistence.models import PersistedAudit

pytestmark = pytest.mark.anyio


def test_inspect_summary(cli, persistence):
    persistence._audits.append(
        PersistedAudit(
            system_id="local",
            timestamp=999.0,
            total_actors=3,
            alive_actors=2,
            stopping_actors=1,
            restarting_actors=0,
            registry_size=3,
            registry_orphans=(),
            registry_dead=(),
            dead_letters_count=4,
        )
    )

    result = cli.invoke("inspect summary")

    assert "Actors:" in result.output
    assert "Dead letters: 4" in result.output
