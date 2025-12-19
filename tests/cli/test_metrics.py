import json

import pytest

from tests.conftest import parse_cli_output

pytestmark = pytest.mark.anyio


def test_metrics_group_help(cli):
    result = cli.invoke("metrics")

    assert result.exit_code == 0
    assert "Inspect runtime metrics" in result.output


def test_metrics_persistence_empty(cli, persistence):
    result = cli.invoke("metrics persistence")

    output = parse_cli_output(result.output)

    assert result.exit_code == 0
    assert "Persistence Metrics" in result.output
    assert output["records_written"] == "0"
    assert output["write_errors"] == "0"


def test_metrics_persistence_after_writes(cli, persistence):
    persistence.metrics.records_written = 5
    persistence.metrics.bytes_written = 123

    result = cli.invoke("metrics persistence")

    output = parse_cli_output(result.output)

    assert result.exit_code == 0
    assert output["records_written"] == "5"
    assert output["bytes_written"] == "123"


def test_metrics_persistence_scan_and_anomalies(cli, persistence):
    persistence.metrics.scans = 2
    persistence.metrics.anomalies_detected = 1

    result = cli.invoke("metrics persistence")

    output = parse_cli_output(result.output)

    assert result.exit_code == 0
    assert output["scans"] == "2"
    assert output["anomalies_detected"] == "1"


def test_metrics_persistence_recovery_and_compaction(cli, persistence):
    persistence.metrics.recoveries = 3
    persistence.metrics.compactions = 1

    result = cli.invoke("metrics persistence")

    output = parse_cli_output(result.output)

    assert result.exit_code == 0
    assert output["recoveries"] == "3"
    assert output["compactions"] == "1"


def test_metrics_persistence_error_counters(cli, persistence):
    persistence.metrics.write_errors = 2
    persistence.metrics.scan_errors = 1
    persistence.metrics.recovery_errors = 1
    persistence.metrics.compaction_errors = 1

    result = cli.invoke("metrics persistence")

    output = parse_cli_output(result.output)

    assert result.exit_code == 0
    assert output["write_errors"] == "2"
    assert output["scan_errors"] == "1"
    assert output["recovery_errors"] == "1"
    assert output["compaction_errors"] == "1"


def test_metrics_persistence_json(cli, persistence):
    persistence.metrics.records_written = 1
    persistence.metrics.bytes_written = 50

    result = cli.invoke("metrics persistence --json")

    assert result.exit_code == 0

    data = json.loads(result.output)
    assert data["records_written"] == 1
    assert data["bytes_written"] == 50
    assert "scan_errors" in data


def test_metrics_reset(cli, persistence):
    persistence.metrics.reset()
    persistence.metrics.records_written = 10
    persistence.metrics.write_errors = 5

    result = cli.invoke("metrics reset")

    assert result.exit_code == 0
    assert "Metrics" in result.output

    # Verify reset worked
    result2 = cli.invoke("metrics persistence")
    output = parse_cli_output(result2.output)

    assert output == {
        "records_written": "0",
        "bytes_written": "0",
        "scans": "0",
        "anomalies_detected": "0",
        "recoveries": "0",
        "compactions": "0",
        "write_errors": "5",
        "scan_errors": "0",
        "recovery_errors": "0",
        "compaction_errors": "0",
    }


def test_metrics_backend_without_metrics(cli, monkeypatch):
    class NoMetricsBackend:
        pass

    from papyra import monkay

    monkeypatch.setattr(monkay.settings, "persistence", NoMetricsBackend())

    result = cli.invoke("metrics persistence")

    assert result.exit_code == 0
    assert "does not expose metrics" in result.output.lower()
