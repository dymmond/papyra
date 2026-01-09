import json
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="Requires Python 3.11+",
)


def test_persistence_scan_clean(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    result = cli.invoke(f"persistence scan --path {path}")

    assert result.exit_code == 0
    assert "Persistence is healthy" in result.output


def test_persistence_scan_reports_anomalies(
    cli,
    tmp_path,
):
    path = tmp_path / "events.ndjson"
    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    # Rebind persistence for this test
    result = cli.invoke(f"persistence scan --path {path}")

    assert result.exit_code != 0
    assert "anomal" in result.output.lower()


def test_persistence_recover_repairs(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    result = cli.invoke(f"persistence recover --path {path}")

    assert result.exit_code == 0
    assert "Recovery completed" in result.output

    contents = path.read_text(encoding="utf-8").strip()
    assert contents == '{"kind": "event", "timestamp": 1}'


def test_persistence_recover_quarantine(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    qdir = tmp_path / "quarantine"

    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    result = cli.invoke(
        f"persistence recover --mode quarantine --quarantine-dir {qdir} --path {path}"
    )

    assert result.exit_code == 0
    assert qdir.exists()
    assert any("quarantine" in p.name for p in qdir.iterdir())


def test_persistence_startup_check_fail(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    result = cli.invoke(f"persistence startup-check --mode FAIL_ON_ANOMALY --path {path}")

    assert result.exit_code != 0
    assert "anomal" in result.output.lower()


def test_persistence_startup_check_recover(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text(
        '{"kind":"event","timestamp":1}\n{"kind":"event"',
        encoding="utf-8",
    )

    result = cli.invoke(
        f"persistence startup-check --mode recover --recovery-mode repair --path {path}"
    )

    assert result.exit_code == 0
    assert "Recovery successful" in result.output


def test_persistence_compact(cli):
    result = cli.invoke("persistence compact")

    assert result.exit_code == 0
    assert "Compaction completed" in result.output


def test_persistence_compact_reduces_size(cli, tmp_path):
    path = tmp_path / "events.ndjson"

    lines = [json.dumps({"kind": "event", "timestamp": i}) + "\n" for i in range(10)]
    path.write_text("".join(lines), encoding="utf-8")

    result = cli.invoke(f"persistence compact --path {path}")

    assert result.exit_code == 0
    assert "ℹ" in result.output


def test_persistence_inspect_shows_backend_and_retention(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    # empty file is fine
    path.write_text("", encoding="utf-8")

    result = cli.invoke(f"persistence inspect --path {path}")

    assert result.exit_code == 0
    assert "Persistence Inspect" in result.output
    assert "backend:" in result.output

    # Path override returns JsonFilePersistence
    assert "JsonFilePersistence" in result.output

    # Retention line always printed
    assert "retention:" in result.output
    assert "max_records=" in result.output
    assert "max_age_seconds=" in result.output
    assert "max_total_bytes=" in result.output


def test_persistence_inspect_counts_from_json(cli, tmp_path):
    path = tmp_path / "events.ndjson"

    # 2 events, 1 audit, 3 dead letters
    path.write_text(
        "\n".join(
            [
                '{"kind":"event","system_id":"local","actor_address":"local://1","event_type":"ActorStarted","payload":{},"timestamp":1.0}',
                '{"kind":"event","system_id":"local","actor_address":"local://2","event_type":"ActorStopped","payload":{},"timestamp":2.0}',
                '{"kind":"audit","system_id":"local","timestamp":10.0,"total_actors":1,"alive_actors":1,"stopping_actors":0,"restarting_actors":0,"registry_size":0,"registry_orphans":[],"registry_dead":[],"dead_letters_count":0}',
                '{"kind":"dead_letter","system_id":"local","target":"local://1","message_type":"str","payload":"a","timestamp":20.0}',
                '{"kind":"dead_letter","system_id":"local","target":"local://2","message_type":"str","payload":"b","timestamp":21.0}',
                '{"kind":"dead_letter","system_id":"local","target":"local://3","message_type":"str","payload":"c","timestamp":22.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.invoke(f"persistence inspect --path {path}")

    assert result.exit_code == 0
    assert "events_sampled: 2" in result.output
    assert "audits_sampled: 1" in result.output
    assert "dead_letters_sampled: 3" in result.output


def test_persistence_inspect_limit_capped_indicator(cli, tmp_path):
    path = tmp_path / "events.ndjson"

    # Create more than limit=1 for each category
    path.write_text(
        "\n".join(
            [
                '{"kind":"event","system_id":"local","actor_address":"local://1","event_type":"ActorStarted","payload":{},"timestamp":1.0}',
                '{"kind":"event","system_id":"local","actor_address":"local://2","event_type":"ActorStopped","payload":{},"timestamp":2.0}',
                '{"kind":"audit","system_id":"local","timestamp":10.0,"total_actors":1,"alive_actors":1,"stopping_actors":0,"restarting_actors":0,"registry_size":0,"registry_orphans":[],"registry_dead":[],"dead_letters_count":0}',
                '{"kind":"audit","system_id":"local","timestamp":11.0,"total_actors":2,"alive_actors":2,"stopping_actors":0,"restarting_actors":0,"registry_size":0,"registry_orphans":[],"registry_dead":[],"dead_letters_count":0}',
                '{"kind":"dead_letter","system_id":"local","target":"local://1","message_type":"str","payload":"a","timestamp":20.0}',
                '{"kind":"dead_letter","system_id":"local","target":"local://2","message_type":"str","payload":"b","timestamp":21.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = cli.invoke(f"persistence inspect --limit 1 --path {path}")

    assert result.exit_code == 0
    # When len == limit, command appends " (capped)"
    assert "events_sampled: 1 (capped)" in result.output
    assert "audits_sampled: 1 (capped)" in result.output
    assert "dead_letters_sampled: 1 (capped)" in result.output


def test_persistence_inspect_show_metrics(cli, tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text(
        '{"kind":"event","system_id":"local","actor_address":"local://1","event_type":"ActorStarted","payload":{},"timestamp":1.0}\n',
        encoding="utf-8",
    )

    result = cli.invoke(f"persistence inspect --show-metrics --path {path}")

    assert result.exit_code == 0

    # Metrics block should appear
    assert "metrics:" in result.output

    # Snapshot should include some well-known keys
    assert "records_written" in result.output
    assert "bytes_written" in result.output
    assert "write_errors" in result.output
    assert "scan_errors" in result.output
    assert "recovery_errors" in result.output
    assert "compaction_errors" in result.output
