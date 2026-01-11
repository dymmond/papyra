# Retention Policy

Retention in Papyra refers to the systematic management of data lifecycle within message streams to control resource usage, ensure compliance, and maintain performance. It defines rules that determine how long messages are logically retained and accessible, as well as when they are physically removed from storage. Retention exists to prevent unbounded growth of data, reduce storage costs, and facilitate efficient querying by discarding obsolete or irrelevant data.

## What a Retention Policy Does

A retention policy in Papyra governs two primary aspects of data lifecycle:

- **Logical Retention:** This determines which messages are visible and returned during read operations.
Messages outside the retention criteria are filtered out at read time, effectively making them inaccessible to consumers without immediately deleting them from storage.
- **Physical Retention:** This involves the actual deletion or archival of messages from the
underlying storage backend, freeing storage space.
Physical retention may be applied asynchronously or on a schedule and is backend-dependent.

Retention policies thus control both what data clients can see and what data is physically stored,
balancing usability and resource constraints.

## Retention Dimensions

Papyra supports retention policies based on three principal dimensions. Each dimension can be configured independently or in combination to tailor retention behavior.

### max_records

**Behavior:** Limits retention to the most recent *N* messages. When the number of messages exceeds *max_records*, older messages are logically excluded and eventually deleted.
**Evaluation Order:** This limit is evaluated after applying other retention criteria. Messages beyond the *max_records* count are filtered out.

!!! Example
    If `max_records` is set to `1000`, only the latest 1000 messages are retained logically. Reading the stream returns messages from the newest going backward up to 1000 messages.

### max_age_seconds

**Behavior:** Retains messages only if they are newer than the specified age threshold, measured in seconds from the current time.
**Evaluation Order:** Messages older than `max_age_seconds` are excluded during reads and marked for deletion.

!!! Example
    With `max_age_seconds` set to 86400 (24 hours), only messages created within the last 24 hours are retained.

### max_total_bytes

**Behavior:** Limits the total size of retained messages to a maximum number of bytes. When the total size exceeds this limit, the oldest messages are logically excluded.
**Evaluation Order:** Evaluated in conjunction with other limits; the total byte size of retained messages must not exceed this threshold.

!!! Example
    Setting `max_total_bytes` to 10,485,760 (10 MB) ensures that the combined size of all retained messages does not exceed 10 MB.

## Evaluation Semantics

When multiple retention limits are specified, Papyra evaluates them collectively to determine the final set of retained messages. The effective retention set is the intersection of all criteria:

- Messages must satisfy all configured limits simultaneously to be retained.
- The retention engine first filters messages by age (`max_age_seconds`), then by record count (`max_records`), and finally by total size (`max_total_bytes`).
- If limits conflict, the strictest limit governs retention.

This combined evaluation ensures predictable and consistent retention behavior across all dimensions.

## Backend Support Matrix

Retention enforcement and physical deletion behavior vary by storage backend:

- **In-memory backend:** Retention is applied logically by filtering messages during read operations. Physical deletion occurs immediately as messages are removed from memory.
- **JSON file backend:** Supports logical retention via read-time filtering. Physical deletion requires explicit file rotation or cleanup, which may be manual or scheduled.
- **Rotating file backend:** Implements physical retention by periodically rotating and pruning files based on retention criteria. Logical filtering is applied during reads.
- **Redis Streams backend:** Supports logical retention through stream trimming commands (`XTRIM`) based on count or age. Physical deletion is handled by Redis internally during trimming.

Understanding backend capabilities is critical for configuring retention policies that align with operational expectations.

## Retention vs Compaction

Retention and compaction address different aspects of data management:

- **Retention** filters out data based on age, count, or size limits to maintain a manageable dataset. It governs both visibility and physical existence of messages.
- **Compaction** focuses on reducing data redundancy by merging or removing obsolete updates, often preserving only the latest state per key.

Retention policies control data lifecycle boundaries, whereas compaction optimizes data representation within those boundaries.

## Configuration Examples

This does not currently exists and only serves as examples.

### Retention via Settings

```python
from papyra import Stream

stream = Stream(
    "example_stream",
    retention={
        "max_records": 5000,
        "max_age_seconds": 3600 * 24 * 7,  # 7 days
        "max_total_bytes": 50 * 1024 * 1024,  # 50 MB
    }
)
```

### Backend-specific Retention

```python
from papyra.persistence.backends.stream import RedisStreamBackend
from papyra import Stream

redis_backend = RedisStreamBackend(
    retention={
        "max_records": 10000,
        "max_age_seconds": 3600 * 24,
    }
)

stream = Stream("redis_stream", backend=redis_backend)
```

## Operational Guidance

- **Safe Defaults:** Use conservative retention settings to avoid premature data loss, such as retaining data for at least 24 hours or a few thousand records.
- **Production Tuning:** Adjust retention parameters based on message volume, storage capacity, and query patterns. Monitor storage usage and latency to refine limits.
- **Failure Modes:** Improper retention settings can cause data unavailability or storage exhaustion. Ensure retention policies are compatible with backend capabilities and that physical deletion processes are operational.

## Common Pitfalls

- **Ignoring Backend Limitations:** Applying retention settings unsupported by the backend leads to unexpected behavior. Always verify backend retention support.
- **Overlapping Limits Confusion:** Misunderstanding how multiple limits interact can cause data to be retained less or more than intended.
- **Inconsistent Time Sources:** Retention based on age requires synchronized clocks. Clock skew can cause premature or delayed data expiration.
- **Neglecting Physical Deletion:** Assuming logical retention implies physical deletion can result in storage bloat.

## Summary

Papyra's retention policy framework provides robust control over message lifecycle through configurable dimensions of record count, age, and total size. It differentiates between logical filtering and physical deletion, with backend-specific implementations. Proper configuration and understanding of retention semantics are essential for maintaining performant and reliable data streams in production environments.
