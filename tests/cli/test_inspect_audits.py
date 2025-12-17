import pytest

from papyra.persistence.models import PersistedAudit

pytestmark = pytest.mark.anyio


def test_inspect_audits_empty(cli):
    result = cli.invoke("inspect audits")

    assert result.exit_code == 0
    assert "No audit reports recorded." in result.output


def test_inspect_audits_basic(cli, persistence):
    persistence._audits.append(
        PersistedAudit(
            system_id="local",
            timestamp=123.0,
            total_actors=10,
            alive_actors=8,
            stopping_actors=1,
            restarting_actors=1,
            registry_size=5,
            registry_orphans=(),
            registry_dead=(),
            dead_letters_count=2,
        )
    )

    result = cli.invoke("inspect audits")

    assert "total=10" in result.output
    assert "alive=8" in result.output
    assert "dead_letters=2" in result.output
