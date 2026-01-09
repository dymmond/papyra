from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import anyio
import anyio.abc

from ._retention import apply_retention
from ._utils import _json_default, _pick_dataclass_fields
from .base import PersistenceBackend
from .models import (
    CompactionReport,
    PersistedAudit,
    PersistedDeadLetter,
    PersistedEvent,
    PersistenceAnomaly,
    PersistenceAnomalyType,
    PersistenceRecoveryConfig,
    PersistenceRecoveryMode,
    PersistenceRecoveryReport,
    PersistenceScanReport,
)
from .retention import RetentionPolicy


@dataclass(slots=True)
class RedisStreamsConfig:
    """
    Configuration settings for the Redis Streams persistence backend.

    This class defines connection parameters, key naming conventions, and operational
    tuning limits for interacting with a Redis server.

    Stream Organization:
        The backend maps logical persistence types to distinct Redis Streams using
        a hierarchical key pattern:
        - Events: `{prefix}:{system_id}:events`
        - Audits: `{prefix}:{system_id}:audits`
        - Dead Letters: `{prefix}:{system_id}:dead_letters`

    Entry Format:
        Each entry in a stream contains a single field named "data", which holds
        the full record serialized as a JSON string. This includes the "kind"
        discriminator.

    Attributes:
        url (str): The Redis connection URL (e.g., redis://localhost:6379/0).
            Defaults to local default.
        prefix (str): A namespace prefix for all keys used by this backend.
        system_id (str): The unique identifier of the actor system, used to isolate
            data in a multi-system environment.
        scan_sample_size (int): The number of recent records to inspect during a
            startup health scan. Limiting this prevents slow startups on massive streams.
        max_read (int): The maximum number of records to retrieve in a single
            `list_*` query. This protects memory and prevents blocking the Redis
            server with unbounded `XRANGE` commands.
        approx_trim (bool): Whether to use approximate trimming (`XTRIM ~`) during
            compaction. Approximate trimming is significantly more efficient for
            Redis performance. Defaults to True.
        quarantine_prefix (str | None): A custom key prefix for storing quarantined
            (corrupted) records during recovery. If None, a default based on the
            main prefix is used.
    """

    url: str = "redis://localhost:6379/0"
    prefix: str = "papyra"
    system_id: str = "local"

    # Scan/recovery sampling bounds (avoid scanning huge streams at startup)
    scan_sample_size: int = 1000

    # Read bounds for list_* to avoid unbounded XRANGE on massive streams
    max_read: int = 50_000

    # Physical trim settings when compaction uses XTRIM
    approx_trim: bool = True

    # Optional: quarantine key prefix for QUARANTINE recovery mode
    quarantine_prefix: str | None = None


def _require_redis() -> Any:
    """
    Lazily import the Redis asyncio client library.

    This function ensures that the heavy `redis` dependency is only imported when
    the Redis backend is actually instantiated, keeping the core library lightweight.

    Returns:
        Any: The `redis.asyncio` module.

    Raises:
        RuntimeError: If the `redis` package is not installed in the environment.
    """
    try:
        import redis.asyncio as redis_async  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Redis backend requires optional dependency 'redis'. "
            "Install with: pip install papyra[redis] or pip install redis"
        ) from e
    return redis_async


class RedisStreamsPersistence(PersistenceBackend):
    """
    A persistence backend implementation using Redis Streams.

    This class provides a durable, append-only log storage mechanism suitable for
    production environments where a managed Redis instance is available. It leverages
    Redis Streams (`XADD`, `XRANGE`) to store events, audits, and dead letters sequentially.

    Architecture:
        - **Storage**: Records are stored as JSON strings within the `data` field of
          Redis Stream entries.
        - **Isolation**: Data is namespaced by `system_id`, allowing multiple actor
          systems to share the same Redis instance.
        - **Concurrency**: While Redis itself is atomic, this class uses an internal
          lock to coordinate local state metrics and ensure orderly shutdown.

    Performance:
        - Uses `anyio` for asynchronous IO.
        - Metrics are tracked for writes, scans, and compactions.
        - Large reads are capped via configuration to prevent memory exhaustion.
    """

    def __init__(
        self,
        config: RedisStreamsConfig | None = None,
        *,
        retention_policy: RetentionPolicy | None = None,
    ) -> None:
        """
        Initialize the Redis Streams persistence backend.

        Args:
            config (RedisStreamsConfig | None, optional): Connection and tuning configuration.
                If None, defaults are used.
            retention_policy (RetentionPolicy | None, optional): Policies defining
                data lifecycle (e.g., max records). Passed to the base class.
        """
        super().__init__(retention_policy=retention_policy)
        self._cfg = config or RedisStreamsConfig()
        self._lock: anyio.abc.Lock = anyio.Lock()

        # Check for redis library availability immediately upon initialization
        redis_async = _require_redis()
        # decode_responses=True ensures we receive str instead of bytes from Redis,
        # simplifying JSON handling.
        self._redis = redis_async.Redis.from_url(self._cfg.url, decode_responses=True)

        self._closed = False

    def _key(self, suffix: str) -> str:
        """
        Construct a fully qualified Redis key.

        Args:
            suffix (str): The specific resource identifier (e.g., "events").

        Returns:
            str: The namespaced key string (e.g., "papyra:local:events").
        """
        return f"{self._cfg.prefix}:{self._cfg.system_id}:{suffix}"

    @property
    def _events_key(self) -> str:
        """Return the Redis key for the events stream."""
        return self._key("events")

    @property
    def _audits_key(self) -> str:
        """Return the Redis key for the audits stream."""
        return self._key("audits")

    @property
    def _dead_letters_key(self) -> str:
        """Return the Redis key for the dead letters stream."""
        return self._key("dead_letters")

    def _quarantine_key(self, source_key: str) -> str:
        """
        Generate a key for storing quarantined (corrupted) records.

        The generated key is derived from the source key to ensure that quarantined
        data can be traced back to its origin. Colons in the source key are replaced
        to maintain a clean hierarchy.

        Args:
            source_key (str): The original key where corruption was found.

        Returns:
            str: The key used for the quarantine stream.
        """
        base = self._cfg.quarantine_prefix or f"{self._cfg.prefix}:{self._cfg.system_id}:quarantine"
        # keep key name stable + readable
        return f"{base}:{source_key.replace(':', '_')}"

    async def _xadd(self, key: str, record: dict[str, Any]) -> int:
        """
        Append a single record to a Redis Stream using `XADD`.

        The record is serialized to JSON and stored under the field name "data".

        Args:
            key (str): The Redis stream key.
            record (dict[str, Any]): The data dictionary to store.

        Returns:
            int: The size of the serialized payload in bytes, used for metrics.
        """
        payload = json.dumps(record, ensure_ascii=False, default=_json_default)
        # XADD key * data <payload>
        # The '*' ID argument tells Redis to auto-generate a timestamp-based ID.
        await self._redis.xadd(key, {"data": payload})
        return len(payload.encode("utf-8"))

    async def _xlen(self, key: str) -> int:
        """
        Get the current length of a Redis Stream.

        Returns:
            int: The number of items in the stream, or 0 if an error occurs.
        """
        try:
            return int(await self._redis.xlen(key))
        except Exception:
            return 0

    async def _read_stream_all(self, key: str) -> list[dict[str, Any]]:
        """
        Retrieve all records from a stream (up to the configured limit).

        This method performs an `XRANGE` from the beginning (`-`) to the end (`+`)
        of the stream. It deserializes the JSON payloads and gracefully skips
        malformed entries.

        Args:
            key (str): The Redis stream key to read from.

        Returns:
            list[dict[str, Any]]: A list of parsed dictionary records in chronological order.
        """
        # XRANGE key - + COUNT <max_read>
        entries = await self._redis.xrange(key, min="-", max="+", count=self._cfg.max_read)
        out: list[dict[str, Any]] = []

        for _id, fields in entries:
            raw = None
            if isinstance(fields, dict):
                raw = fields.get("data")

            # Validate that we have a string payload to parse
            if not isinstance(raw, str):
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                # Silently skip records that are not valid JSON
                continue

            if isinstance(obj, dict):
                out.append(obj)
        return out

    async def record_event(self, event: PersistedEvent) -> None:  # type: ignore
        """
        Persist a domain event to the Redis event stream.

        Args:
            event (PersistedEvent): The event object to store.
        """
        try:
            if self._closed:
                return
            record = {"kind": "event", **_json_default(event)}

            # Acquire lock to ensure metrics update and write are coordinated if needed
            async with self._lock:
                nbytes = await self._xadd(self._events_key, record)

            await self._metrics_on_write_ok(records=1, bytes_written=nbytes)
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def record_audit(self, audit: PersistedAudit) -> None:  # type: ignore
        """
        Persist an audit log to the Redis audit stream.

        Args:
            audit (PersistedAudit): The audit object to store.
        """
        try:
            if self._closed:
                return
            record = {"kind": "audit", **_json_default(audit)}

            async with self._lock:
                nbytes = await self._xadd(self._audits_key, record)

            await self._metrics_on_write_ok(records=1, bytes_written=nbytes)
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def record_dead_letter(self, dead_letter: PersistedDeadLetter) -> None:  # type: ignore
        """
        Persist a dead letter to the Redis dead letter stream.

        Args:
            dead_letter (PersistedDeadLetter): The dead letter object to store.
        """
        try:
            if self._closed:
                return
            record = {"kind": "dead_letter", **_json_default(dead_letter)}

            async with self._lock:
                nbytes = await self._xadd(self._dead_letters_key, record)

            await self._metrics_on_write_ok(records=1, bytes_written=nbytes)
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def list_events(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedEvent, ...]:
        """
        Retrieve persisted events from Redis.

        Args:
            limit (int | None, optional): Max number of recent events to return.
            since (float | None, optional): Only return events after this timestamp.

        Returns:
            tuple[PersistedEvent, ...]: A collection of event objects.
        """
        rows = await self._read_stream_all(self._events_key)

        # Apply application-level retention filtering if configured
        if self.retention is not None:
            rows = apply_retention(rows, self.retention)

        items: list[PersistedEvent] = []
        for row in rows:
            if row.get("kind") != "event":
                continue
            row = dict(row)
            row.pop("kind", None)

            # Attempt to convert the dict back into a strongly-typed dataclass
            try:
                ev = PersistedEvent(**_pick_dataclass_fields(PersistedEvent, row))
            except Exception:
                # Fallback: manually construct partial object to tolerate schema evolution
                try:
                    ev = PersistedEvent(
                        system_id=row.get("system_id", self._cfg.system_id),
                        actor_address=row.get("actor_address"),
                        event_type=row.get("event_type", ""),
                        payload=row.get("payload", {}),
                        timestamp=row["timestamp"],
                    )
                except Exception:
                    continue

            if since is not None and ev.timestamp < since:
                continue
            items.append(ev)

        if limit is not None:
            items = items[-limit:]

        return tuple(items)

    async def list_audits(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedAudit, ...]:
        """
        Retrieve persisted audit logs from Redis.

        Args:
            limit (int | None, optional): Max number of recent audits to return.
            since (float | None, optional): Only return audits after this timestamp.

        Returns:
            tuple[PersistedAudit, ...]: A collection of audit objects.
        """
        rows = await self._read_stream_all(self._audits_key)

        if self.retention is not None:
            rows = apply_retention(rows, self.retention)

        items: list[PersistedAudit] = []
        for row in rows:
            if row.get("kind") != "audit":
                continue
            row = dict(row)
            row.pop("kind", None)

            try:
                au = PersistedAudit(**_pick_dataclass_fields(PersistedAudit, row))
            except Exception:
                try:
                    au = PersistedAudit(
                        system_id=row.get("system_id", self._cfg.system_id),
                        timestamp=row["timestamp"],
                        total_actors=row.get("total_actors", 0),
                        alive_actors=row.get("alive_actors", 0),
                        stopping_actors=row.get("stopping_actors", 0),
                        restarting_actors=row.get("restarting_actors", 0),
                        registry_size=row.get("registry_size", 0),
                        registry_orphans=tuple(row.get("registry_orphans", ())),
                        registry_dead=tuple(row.get("registry_dead", ())),
                        dead_letters_count=row.get("dead_letters_count", 0),
                    )
                except Exception:
                    continue

            if since is not None and au.timestamp < since:
                continue
            items.append(au)

        if limit is not None:
            items = items[-limit:]

        return tuple(items)

    async def list_dead_letters(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedDeadLetter, ...]:
        """
        Retrieve persisted dead letters from Redis.

        Args:
            limit (int | None, optional): Max number of recent dead letters to return.
            since (float | None, optional): Only return items after this timestamp.

        Returns:
            tuple[PersistedDeadLetter, ...]: A collection of dead letter objects.
        """
        rows = await self._read_stream_all(self._dead_letters_key)

        if self.retention is not None:
            rows = apply_retention(rows, self.retention)

        items: list[PersistedDeadLetter] = []
        for row in rows:
            if row.get("kind") != "dead_letter":
                continue
            row = dict(row)
            row.pop("kind", None)

            try:
                dl = PersistedDeadLetter(**_pick_dataclass_fields(PersistedDeadLetter, row))
            except Exception:
                try:
                    dl = PersistedDeadLetter(
                        system_id=row.get("system_id", self._cfg.system_id),
                        target=row.get("target"),
                        message_type=row.get("message_type", ""),
                        payload=row.get("payload"),
                        timestamp=row["timestamp"],
                    )
                except Exception:
                    continue

            if since is not None and dl.timestamp < since:
                continue
            items.append(dl)

        if limit is not None:
            items = items[-limit:]

        return tuple(items)

    async def compact(self) -> CompactionReport:
        """
        Perform physical compaction on the Redis streams by trimming old records.

        This method enforces the `max_records` retention policy at the storage level
        using the Redis `XTRIM` command. If no `max_records` limit is defined in the
        retention policy, this operation essentially becomes a no-op that just
        reports current sizes.

        Mechanism:
            - Reads current stream lengths.
            - If `retention.max_records` is set, executes `XTRIM` on all three streams.
            - Uses approximate trimming (`~`) if configured, which is higher performance
              for Redis clusters.

        Returns:
            CompactionReport: A summary of record counts before and after the operation.
        """
        await self._metrics_on_compact_start()
        try:
            # Measure initial state
            before = (
                (await self._xlen(self._events_key))
                + (await self._xlen(self._audits_key))
                + (await self._xlen(self._dead_letters_key))
            )

            max_records: int | None = None
            if self.retention is not None:
                max_records = getattr(self.retention, "max_records", None)

            # If a numeric limit is configured, perform the trim
            if isinstance(max_records, int) and max_records > 0:
                # approx trim uses "~" which is faster and safe for log data
                approx = self._cfg.approx_trim
                await self._redis.xtrim(
                    self._events_key,
                    maxlen=max_records,
                    approximate=approx,
                )
                await self._redis.xtrim(
                    self._audits_key,
                    maxlen=max_records,
                    approximate=approx,
                )
                await self._redis.xtrim(
                    self._dead_letters_key,
                    maxlen=max_records,
                    approximate=approx,
                )

            # Measure final state
            after = (
                (await self._xlen(self._events_key))
                + (await self._xlen(self._audits_key))
                + (await self._xlen(self._dead_letters_key))
            )

            return CompactionReport(
                backend="redis",
                before_records=before,
                after_records=after,
                before_bytes=None,
                after_bytes=None,
            )
        except Exception:
            await self._metrics_on_compact_error()
            raise

    async def scan(self) -> PersistenceScanReport:
        """
        Scan a sample of recent stream entries for data integrity.

        While Redis Streams ensure structural integrity, the application payload (JSON)
        could be corrupted. This method checks the `scan_sample_size` most recent entries
        to ensure they contain a valid JSON string in the "data" field.

        Detection:
            - Checks if the 'data' field is missing.
            - Checks if 'data' is not a string.
            - Checks if 'data' cannot be parsed as JSON.
            - Checks if the parsed JSON is not a dictionary.

        Returns:
            PersistenceScanReport: A report containing any detected anomalies.
        """
        await self._metrics_on_scan_start()
        anomalies: list[PersistenceAnomaly] = []

        try:
            keys = (self._events_key, self._audits_key, self._dead_letters_key)
            sample = max(1, int(self._cfg.scan_sample_size))

            for key in keys:
                # Read from newest to oldest up to the sample limit
                entries = await self._redis.xrevrange(key, max="+", min="-", count=sample)
                for _id, fields in entries:
                    raw = None
                    if isinstance(fields, dict):
                        raw = fields.get("data")

                    # Check 1: Payload must be a string
                    if not isinstance(raw, str):
                        anomalies.append(
                            PersistenceAnomaly(
                                type=PersistenceAnomalyType.CORRUPTED_LINE,
                                path=str(key),
                                detail="Missing 'data' field or non-string payload",
                            )
                        )
                        continue
                    # Check 2: Payload must be valid JSON
                    try:
                        obj = json.loads(raw)
                    except Exception:
                        anomalies.append(
                            PersistenceAnomaly(
                                type=PersistenceAnomalyType.CORRUPTED_LINE,
                                path=str(key),
                                detail="Invalid JSON payload in stream entry",
                            )
                        )
                        continue
                    # Check 3: Parsed JSON must be an object (dict)
                    if not isinstance(obj, dict):
                        anomalies.append(
                            PersistenceAnomaly(
                                type=PersistenceAnomalyType.CORRUPTED_LINE,
                                path=str(key),
                                detail="JSON payload is not an object/dict",
                            )
                        )

            if anomalies:
                await self._metrics_on_scan_anomalies(len(anomalies))

            return PersistenceScanReport(
                backend="redis",
                anomalies=tuple(anomalies),
            )
        except Exception:
            await self._metrics_on_scan_error()
            raise

    async def recover(self, config: Any | None = None) -> PersistenceRecoveryReport | None:
        """
        Execute a recovery process to handle corrupted stream entries.

        Based on the configured mode, this method processes anomalies detected by `scan()`:
        - **IGNORE**: Take no action.
        - **REPAIR**: Delete the malformed stream entries using `XDEL`.
        - **QUARANTINE**: Copy the malformed data to a separate quarantine stream
          (with metadata like source key and timestamp) before deleting the original entry.

        Args:
            config (Any | None, optional): Recovery configuration settings.

        Returns:
            PersistenceRecoveryReport | None: A report of repaired/quarantined items,
                or None if the scan was clean/ignored.
        """
        await self._metrics_on_recover_start()

        cfg = config or PersistenceRecoveryConfig()
        scan = await self.scan()

        if cfg.mode is PersistenceRecoveryMode.IGNORE or scan is None or not scan.has_anomalies:
            return PersistenceRecoveryReport(backend="redis", scan=scan) if scan is not None else None

        repaired: list[str] = []
        quarantined: list[str] = []

        try:
            keys = (self._events_key, self._audits_key, self._dead_letters_key)
            sample = max(1, int(self._cfg.scan_sample_size))

            for key in keys:
                entries = await self._redis.xrevrange(key, max="+", min="-", count=sample)
                bad_ids: list[str] = []
                bad_payloads: list[str] = []

                for _id, fields in entries:
                    raw = None
                    if isinstance(fields, dict):
                        raw = fields.get("data")

                    # Validation logic mirrors scan()
                    ok = isinstance(raw, str)
                    if ok:
                        try:
                            obj = json.loads(raw)
                            ok = isinstance(obj, dict)
                        except Exception:
                            ok = False

                    if not ok:
                        bad_ids.append(str(_id))
                        bad_payloads.append(str(raw) if raw is not None else "")

                if not bad_ids:
                    continue

                # Handle Quarantine: Move bad data to a separate stream
                if cfg.mode is PersistenceRecoveryMode.QUARANTINE:
                    qkey = self._quarantine_key(str(key))
                    for payload in bad_payloads:
                        await self._redis.xadd(
                            qkey,
                            {
                                "source": str(key),
                                "data": payload,
                                "timestamp": str(time.time()),
                            },
                        )
                    quarantined.append(qkey)

                # Repair: Delete the identified bad entries from the main stream
                await self._redis.xdel(key, *bad_ids)
                repaired.append(str(key))

            return PersistenceRecoveryReport(
                backend="redis",
                scan=scan,
                repaired_files=tuple(repaired),
                quarantined_files=tuple(quarantined),
            )
        except Exception:
            await self._metrics_on_recover_error()
            raise

    async def aclose(self) -> None:
        """
        Close the Redis connection and release resources.

        This sets the internal closed flag and attempts to cleanly close the
        Redis client connection.
        """
        async with self._lock:
            self._closed = True
        try:
            await self._redis.aclose()
        except Exception:
            # Swallow errors during close to ensure best-effort cleanup
            return

    @property
    def closed(self) -> bool:
        """Check if the backend has been closed."""
        return self._closed
