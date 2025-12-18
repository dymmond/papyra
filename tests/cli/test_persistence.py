from __future__ import annotations

import json


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
