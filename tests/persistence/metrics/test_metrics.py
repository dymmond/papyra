import pytest

from papyra.persistence.metrics import PersistenceMetrics

pytestmark = pytest.mark.anyio


def test_metrics_initial_state():
    metrics = PersistenceMetrics()

    snap = metrics.snapshot()

    assert snap == {
        "records_written": 0,
        "bytes_written": 0,
        "scans": 0,
        "anomalies_detected": 0,
        "recoveries": 0,
        "compactions": 0,
        "write_errors": 0,
        "scan_errors": 0,
        "recovery_errors": 0,
        "compaction_errors": 0,
    }


def test_metrics_snapshot_is_stable_copy():
    metrics = PersistenceMetrics()
    metrics.records_written = 5

    snap1 = metrics.snapshot()
    snap1["records_written"] = 999  # mutate snapshot

    snap2 = metrics.snapshot()
    assert snap2["records_written"] == 5


def test_metrics_manual_incrementing():
    metrics = PersistenceMetrics()

    metrics.records_written += 10
    metrics.bytes_written += 2048
    metrics.scans += 1
    metrics.anomalies_detected += 2
    metrics.recoveries += 1
    metrics.compactions += 3

    snap = metrics.snapshot()

    assert snap["records_written"] == 10
    assert snap["bytes_written"] == 2048
    assert snap["scans"] == 1
    assert snap["anomalies_detected"] == 2
    assert snap["recoveries"] == 1
    assert snap["compactions"] == 3


def test_metrics_error_counters():
    metrics = PersistenceMetrics()

    metrics.write_errors += 1
    metrics.scan_errors += 2
    metrics.recovery_errors += 3
    metrics.compaction_errors += 4

    snap = metrics.snapshot()

    assert snap["write_errors"] == 1
    assert snap["scan_errors"] == 2
    assert snap["recovery_errors"] == 3
    assert snap["compaction_errors"] == 4


def test_metrics_reset():
    metrics = PersistenceMetrics()

    metrics.records_written = 100
    metrics.bytes_written = 4096
    metrics.scans = 5
    metrics.anomalies_detected = 2
    metrics.recoveries = 1
    metrics.compactions = 1
    metrics.write_errors = 9
    metrics.scan_errors = 8
    metrics.recovery_errors = 7
    metrics.compaction_errors = 6

    metrics.reset()

    snap = metrics.snapshot()

    assert snap == {
        "records_written": 0,
        "bytes_written": 0,
        "scans": 0,
        "anomalies_detected": 0,
        "recoveries": 0,
        "compactions": 0,
        "write_errors": 9,
        "scan_errors": 8,
        "recovery_errors": 7,
        "compaction_errors": 6,
    }
