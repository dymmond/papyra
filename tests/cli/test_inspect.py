import pytest

from papyra.persistence.models import (
    PersistedAudit,
    PersistedDeadLetter,
    PersistedEvent,
)

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


def test_inspect_dead_letters_empty(cli):
    result = cli.invoke("inspect dead-letters")

    assert result.exit_code == 0
    assert "No dead letters recorded." in result.output


def test_inspect_dead_letters_basic(cli, persistence):
    persistence._dead_letters.append(
        PersistedDeadLetter(
            system_id="local",
            target="local://1",
            message_type="str",
            payload="hello",
            timestamp=42.0,
        )
    )

    result = cli.invoke("inspect dead-letters")

    assert "local://1" in result.output
    assert "str" in result.output
    assert "hello" in result.output


def test_inspect_dead_letters_filter_target(cli, persistence):
    persistence._dead_letters.append(
        PersistedDeadLetter(
            system_id="local",
            target="local://1",
            message_type="str",
            payload="a",
            timestamp=1.0,
        )
    )
    persistence._dead_letters.append(
        PersistedDeadLetter(
            system_id="local",
            target="local://2",
            message_type="str",
            payload="b",
            timestamp=2.0,
        )
    )

    result = cli.invoke("inspect dead-letters --target local://2")

    assert "local://2" in result.output
    assert "local://1" not in result.output


def test_inspect_events_empty(cli):
    result = cli.invoke("inspect events")

    assert result.exit_code == 0
    assert "No events recorded." in result.output


def test_inspect_events_basic(cli, persistence):
    persistence._events.append(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=100.0,
        )
    )

    result = cli.invoke("inspect events")

    assert result.exit_code == 0
    assert "ActorStarted" in result.output
    assert "local://1" in result.output
    assert "100.000" in result.output


def test_inspect_events_filter_type(cli, persistence):
    persistence._events.append(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStarted",
            payload={},
            timestamp=1.0,
        )
    )
    persistence._events.append(
        PersistedEvent(
            system_id="local",
            actor_address="local://1",
            event_type="ActorStopped",
            payload={},
            timestamp=2.0,
        )
    )

    result = cli.invoke("inspect events --event-type ActorStopped")

    assert "ActorStopped" in result.output
    assert "ActorStarted" not in result.output


def test_inspect_events_limit(cli, persistence):
    for i in range(5):
        persistence._events.append(
            PersistedEvent(
                system_id="local",
                actor_address=f"local://{i}",
                event_type="ActorStarted",
                payload={},
                timestamp=float(i),
            )
        )

    result = cli.invoke("inspect events --limit 2")

    lines = result.output.strip().splitlines()
    assert len(lines) == 2


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
