# Persistence Metrics

Observability is a critical aspect of actor-based persistence systems. Metrics provide essential
insights into the internal operations and health of persistence backends, enabling developers and operators to monitor,
debug, and optimize system behavior. In Papyra, metrics are built-in rather than optional,
ensuring consistent, reliable visibility across all persistence layers.

## Design Philosophy

The design of persistence metrics in Papyra follows three core principles:

- **Local, Synchronous, and Deterministic**: Metrics are updated immediately and deterministically within the
persistence backend's execution flow. This guarantees that metric values accurately reflect the current
- state without asynchronous delays or race conditions.
- **No External Dependency Requirement**: Metrics are collected internally without relying on external monitoring
or storage systems. This ensures that metrics remain available and consistent even in isolated or
constrained environments.
- **Safe to Snapshot and Reset at Runtime**: Metrics can be safely snapshotted and reset without affecting
backend operation. This allows for flexible runtime inspection and management without disrupting ongoing persistence activities.

## Metrics Lifecycle

Persistence metrics are incremented at specific operational points within the backend:

- **Increment Timing**: Metrics counters are incremented synchronously during persistence operations such as writes, reads, scans, recoveries, and compactions.
- **Persistence Across Operations**: Metrics maintain their state across multiple operations and actor lifecycles, providing cumulative counts that reflect the overall backend activity.
- **Reset Semantics**: Metrics can be reset programmatically or via CLI commands without impacting the persistence backend's internal state. Resetting clears counters to zero, enabling fresh measurement intervals.

## Metrics Provided

Papyra persistence backends provide a comprehensive set of metrics categorized as follows:

### Write Metrics

- **`records_written`**
  Counts the total number of records successfully written to the backend.
  *Increments:* After each successful write operation.
  *Does NOT count:* Failed writes or retries.

- **`write_errors`**
  Counts the number of write operations that failed due to errors.
  *Increments:* On every write failure.
  *Does NOT count:* Successful writes or read errors.

### Read/List Metrics

- **`records_read`**
  Counts the total number of records successfully read during load or list operations.
  *Increments:* After each successful read or list operation.
  *Does NOT count:* Failed reads or partial reads.

- **`read_errors`**
  Counts the number of read operations that encountered errors.
  *Increments:* On every read failure.
  *Does NOT count:* Successful reads.

### Scan & Anomaly Metrics

- **`scan_operations`**
  Counts the number of scan operations performed on the backend.
  *Increments:* Each time a scan is initiated.
  *Does NOT count:* Reads or writes.

- **`anomaly_detected`**
  Counts occurrences of detected anomalies such as data corruption or unexpected state.
  *Increments:* When an anomaly is detected during any operation.
  *Does NOT count:* Normal operation events.

### Recovery Metrics

- **`recovery_attempts`**
  Counts the number of recovery attempts triggered after failure or restart.
  *Increments:* On each recovery attempt.
  *Does NOT count:* Successful operations outside recovery.

- **`recovery_failures`**
  Counts the number of failed recovery attempts.
  *Increments:* On recovery failure.
  *Does NOT count:* Successful recoveries or normal operations.

### Compaction Metrics

- **`compactions_triggered`**
  Counts the number of compaction operations initiated.
  *Increments:* Each time compaction starts.
  *Does NOT count:* Normal writes or reads.

- **`compaction_errors`**
  Counts errors encountered during compaction.
  *Increments:* On compaction failure.
  *Does NOT count:* Successful compactions.

## PersistenceMetricsMixin

The `PersistenceMetricsMixin` exists to provide a consistent and reusable metrics implementation for all persistence backends.

- **Why It Exists**: To centralize metric collection logic and ensure uniform behavior across diverse backend implementations.
- **How Backends Inherit It**: Persistence backends inherit from `PersistenceMetricsMixin` to gain built-in metric counters and lifecycle management.
- **What Guarantees It Provides**: It guarantees synchronous, deterministic metric updates and safe snapshot/reset operations without requiring backends to implement these features independently.

## Accessing Metrics Programmatically

Persistence metrics can be accessed and managed programmatically via the backend's `metrics` attribute.
Common operations include snapshotting and resetting metrics:

```python
# Obtain a snapshot of current metrics as a dictionary
snapshot = backend.metrics.snapshot()
print(snapshot)
```

```python
# Reset all metrics counters to zero
backend.metrics.reset()
```

These methods enable runtime inspection and management of persistence metrics within application code.

## CLI Integration

Papyra provides CLI commands to interact with persistence metrics:

- **`papyra metrics persistence`**
  Displays current persistence metrics in a human-readable format.

- **`papyra metrics reset`**
  Resets all persistence metrics counters to zero.

- **JSON Output Mode**
  Both commands support a `--json` flag to output metrics in JSON format for integration with external tools or scripts.

Example:

```bash
papyra metrics persistence --json
```

## External Monitoring & OpenTelemetry

Papyra does **not** impose OpenTelemetry or any external monitoring framework. Instead, it provides raw metric data that users can export manually.

Users can map Papyra metrics to OpenTelemetry counters or other monitoring systems as needed. For example:

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
records_written_counter = meter.create_counter("records_written")

snapshot = backend.metrics.snapshot()
records_written_counter.add(snapshot["records_written"])
```

This approach provides maximum flexibility, allowing users to integrate persistence metrics into their preferred observability stacks without vendor lock-in.

## Backend Support Matrix

| Backend   | records_written | write_errors | records_read | read_errors | scan_operations | anomaly_detected | recovery_attempts | recovery_failures | compactions_triggered | compaction_errors |
|-----------|-----------------|--------------|--------------|-------------|-----------------|------------------|-------------------|-------------------|----------------------|-------------------|
| Memory    | Yes             | Yes          | Yes          | Yes         | Yes             | Yes              | Yes               | Yes               | No                   | No                |
| JSON      | Yes             | Yes          | Yes          | Yes         | Yes             | Yes              | Yes               | Yes               | Yes                  | Yes               |
| Rotating  | Yes             | Yes          | Yes          | Yes         | Yes             | Yes              | Yes               | Yes               | Yes                  | Yes               |
| Redis     | Yes             | Yes          | Yes          | Yes         | Yes             | Yes              | Yes               | Yes               | Yes                  | Yes               |

## Operational Guidance

When using persistence metrics in production environments, consider the following best practices:

- **Use Metrics for Alerting**: Set up alerts on error counters such as `write_errors`, `read_errors`, `recovery_failures`, and `compaction_errors` to detect operational issues early.
- **Track Throughput and Load**: Monitor `records_written`, `records_read`, and `scan_operations` to understand system load and performance trends.
- **Debugging**: Use anomaly and recovery metrics to diagnose issues related to data integrity and system restarts.
- **Reset Metrics Periodically**: Reset metrics counters after analysis or on deployment to maintain relevant measurement intervals.

## Why This Matters

Persistence metrics are fundamental to the reliability and operability of actor-based systems. They provide a window into the internal state and behavior
of persistence backends, enabling proactive monitoring, rapid troubleshooting, and informed capacity planning.
By embedding metrics deeply and consistently, Papyra ensures that developers and operators have the visibility
they need to maintain robust, performant persistence layers.
