from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """
    Configuration defining rules for data retention.

    This policy allows specifying limits based on record count, data age, or
    total storage size. It is used to determine when old data should be purged
    to maintain system health and storage constraints.

    Attributes:
        max_records (int | None): The maximum number of records to retain.
            If the count exceeds this limit, the oldest records are dropped.
            Defaults to None (no limit).
        max_age_seconds (float | None): The maximum age of a record in seconds.
            Records older than this duration are eligible for deletion.
            Defaults to None (no time limit).
        max_total_bytes (int | None): The maximum total size in bytes allowed
            for the stored data. If the storage usage exceeds this limit,
            older records are removed until usage drops below the threshold.
            Defaults to None (no size limit).
    """

    max_records: int | None = None
    max_age_seconds: float | None = None
    max_total_bytes: int | None = None
