# Metrics Overview

## What Are Metrics in Papyra?

In Papyra, metrics refer to persistence-level observability data that provide insight into the behavior and performance of the underlying storage and data management layers. These metrics focus on the persistence mechanisms rather than the actor logic or business processes. They enable developers and operators to monitor, analyze, and understand how data is written, read, and maintained within the system.

## Why Do Metrics Exist?

Metrics serve several critical purposes:

- **Debugging:** Quickly identify issues related to data persistence, such as failed writes or unexpected read errors.
- **Operations:** Monitor system health and performance in real time to maintain reliable service.
- **Capacity Planning:** Understand workload patterns and storage usage to plan for scaling and resource allocation.
- **Confidence:** Provide quantitative evidence that the persistence layer is functioning correctly and efficiently.

## PersistenceMetricsMixin Concept and Guarantees

The `PersistenceMetricsMixin` is a mixin class that can be integrated into persistence components within Papyra.
It automatically collects and exposes a comprehensive set of metrics related to data operations.
This mixin guarantees consistent metric collection across different persistence backends and ensures
that metrics are updated atomically with persistence events, providing accurate and reliable observability.

## Core Metric Categories

Papyra collects the following core metrics to cover key aspects of persistence:

- **records_written:** The total number of records successfully written to storage.
- **records_read:** The total number of records successfully read from storage.
- **write_errors:** The count of errors encountered during write operations.
- **read_errors:** The count of errors encountered during read operations.
- **scan_runs:** The number of times a scan operation has been executed over the stored data.
- **anomalies_detected:** The count of detected anomalies in data or persistence behavior.
- **recoveries_attempted:** The number of attempts to recover from persistence failures.
- **recoveries_failed:** The count of recovery attempts that did not succeed.
- **compactions_run:** The number of compaction operations performed to optimize storage.

## Metrics API: `snapshot()` and `reset()`

- **snapshot():** Returns a consistent snapshot of all current metric values. This method is thread-safe and provides a point-in-time view of the metrics without modifying them.
- **reset():** Resets all metrics to zero. This can be useful for clearing counters after a monitoring interval or test run.

## Backend Support Matrix

Papyra supports multiple metrics backends, each with different capabilities:

- **memory:** In-memory storage for metrics, suitable for lightweight or testing scenarios.
- **json:** Exports metrics as JSON files for integration with external tools.
- **rotation:** Supports rotating log files for metrics to manage disk usage.
- **redis:** Enables metrics storage and retrieval via Redis for distributed and scalable environments.

Each backend fully supports the core metric categories and ensures consistent behavior.

## Automatic Metrics Collection

Metrics in Papyra are collected automatically by the persistence layer through the `PersistenceMetricsMixin`.
Users do not need to write any additional code to enable or maintain metrics collection. This design minimizes overhead and ensures that metrics are always in sync with persistence operations.

## Conceptual Example

```python
from papyra.persistence import SomePersistenceBackend, PersistenceMetricsMixin

class MyPersistence(SomePersistenceBackend, PersistenceMetricsMixin):
    ...

persistence = MyPersistence()

# Perform data operations
persistence.write(record)
persistence.read(key)

# Obtain metrics snapshot
metrics = persistence.snapshot()
print(metrics["records_written"], metrics["records_read"])
```

This example demonstrates how metrics are integrated transparently into persistence components.

## What Metrics Are NOT

- **Not Tracing:** Metrics do not provide detailed tracing of individual operations or call stacks.
- **Not Profiling:** Metrics do not measure CPU or memory usage or performance profiling of code.

Metrics focus solely on persistence-level counters and events to provide operational insight.
