from __future__ import annotations

import time
from typing import Any

from .retention import RetentionPolicy


def apply_retention(
    records: list[dict[str, Any]],
    policy: RetentionPolicy,
) -> list[dict[str, Any]]:
    """
    Apply a comprehensive set of retention rules to a list of records.

    This function processes the input records against the constraints defined in
    the provided `RetentionPolicy`. It filters data based on age, limits the
    total count, and restricts the total size in bytes.

    Processing Order:
    1. Time-based retention: Removes records older than `max_age_seconds`.
    2. Count-based retention: Truncates the list to the most recent `max_records`.
    3. Size-based retention: Retains the most recent records that fit within
       `max_total_bytes`, approximating size using the UTF-8 encoded representation.

    Assumptions:
        - The input `records` list is ordered chronologically from oldest to newest.
        - Records containing a "timestamp" key (float) are eligible for time-based filtering.

    Args:
        records (list[dict[str, Any]]): The list of record dictionaries to process.
        policy (RetentionPolicy): The configuration object containing retention limits.

    Returns:
        list[dict[str, Any]]: A new list of records that satisfy all active retention
            constraints.
    """
    result = records

    # 1. Apply time-based retention if configured
    if policy.max_age_seconds is not None:
        now = time.time()
        cutoff = now - policy.max_age_seconds
        # Filter out records that are older than the cutoff time.
        # We use the walrus operator to fetch the timestamp and check existence in one step.
        result = [r for r in result if (ts := r.get("timestamp")) is not None and ts >= cutoff]

    # 2. Apply count-based retention if configured
    if policy.max_records is not None:
        # Slice the list to keep only the last N records (the newest ones).
        result = result[-policy.max_records :]

    # 3. Apply size-based retention if configured
    if policy.max_total_bytes is not None:
        total = 0
        kept: list[dict[str, Any]] = []

        # Iterate backwards (newest -> oldest) to prioritize keeping recent data.
        # We stop accumulating once the max_total_bytes limit is exceeded.
        for r in reversed(result):
            # Approximate the size of the record using its UTF-8 string representation.
            size = len(repr(r).encode("utf-8"))
            if total + size > policy.max_total_bytes:
                break
            total += size
            kept.append(r)

        # Restore the original chronological order (oldest -> newest).
        result = list(reversed(kept))

    return result
