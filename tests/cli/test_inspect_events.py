import pytest

from papyra.persistence.models import PersistedEvent

pytestmark = pytest.mark.anyio


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
