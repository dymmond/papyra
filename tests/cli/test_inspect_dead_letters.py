import pytest

from papyra.persistence.models import PersistedDeadLetter

pytestmark = pytest.mark.anyio


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
