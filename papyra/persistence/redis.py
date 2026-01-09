from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Mapping

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

StreamKind = Literal["events", "audits", "dead_letters"]


@dataclass(frozen=True, slots=True)
class RedisConsumerGroupConfig:
    """
    Configuration for consuming persisted records via Redis Streams consumer groups.

    This is for external tools and integrations (shipping, analytics, monitoring).
    It does NOT affect how the ActorSystem writes records.

    Notes:
    - Each kind (events/audits/dead_letters) is a separate Redis stream.
    - Consumer group semantics provide at-least-once delivery.
    """

    group: str
    consumer: str

    # How many items to request per XREADGROUP call
    count: int = 100

    # Block time in milliseconds (0 = no block, None = block forever)
    block_ms: int | None = 1000

    # Where to start when group is created:
    # "0" = from beginning, "$" = only new entries
    start_id: str = "0"

    # If True, ensure groups exist at first read
    ensure_group: bool = True


@dataclass(frozen=True, slots=True)
class RedisStreamEntry:
    """
    One consumed entry from a Redis stream.

    `id` is the Redis stream entry id (e.g., "1700000000-0").
    `data` is the decoded dictionary payload.
    """

    id: str
    data: Mapping[str, Any]


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

    def _stream_key(self, kind: StreamKind) -> str:
        """
        Resolve the specific Redis stream key for a given persistence category.

        This internal helper maps the logical classification of data (events, audits,
        or dead letters) to the actual configured Redis key. This allows the key naming
        schema to be decoupled from the internal logic.

        Args:
            kind (StreamKind): The category of the stream to resolve (e.g., 'events').

        Returns:
            str: The fully qualified Redis key used for storage.

        Raises:
            ValueError: If the provided `kind` does not match any known stream category.
        """
        if kind == "events":
            return self._events_key
        if kind == "audits":
            return self._audits_key
        if kind == "dead_letters":
            return self._dead_letters_key
        raise ValueError(f"Unknown stream kind: {kind}")

    def _decode_entry(self, fields: Any) -> dict[str, Any] | None:
        """
        Attempt to extract and deserialize a JSON payload from a Redis stream entry.

        This helper method isolates the logic for converting raw Redis field data into a
        usable Python dictionary. It specifically looks for a field named 'data' which
        is expected to contain a JSON string.

        Validation Logic:
        - Input `fields` must be a dictionary.
        - The 'data' key must exist and be a string.
        - The string must be valid JSON.
        - The resulting JSON object must be a dictionary.

        Args:
            fields (Any): The raw fields structure returned by the Redis client (typically
                a dict mapping bytes/str to bytes/str).

        Returns:
            dict[str, Any] | None: The parsed dictionary if successful, or None if the
                entry is malformed, missing the 'data' field, or contains invalid JSON.
        """
        # The Redis client should return a dict of fields, but we validate strictly
        if not isinstance(fields, dict):
            return None

        raw = fields.get("data")
        # Ensure the payload exists and is a string (client should decode_responses=True)
        if not isinstance(raw, str):
            return None

        try:
            obj = json.loads(raw)
        except Exception:
            # Parsing failed implies data corruption
            return None

        # We strictly require the persisted record to be a JSON object (dict)
        return obj if isinstance(obj, dict) else None

    async def ensure_consumer_group(
        self,
        *,
        kind: StreamKind,
        group: str,
        start_id: str = "0",
    ) -> None:
        """
        Idempotently ensure that a Redis Stream consumer group exists.

        This method attempts to create a consumer group for the specified stream kind.
        It handles the common race condition where the group might already exist, suppressing
        the resulting "BUSYGROUP" error to ensure idempotency.

        Mechanics:
            - Uses `XGROUP CREATE ... MKSTREAM` to create the stream automatically if
              it does not exist yet.
            - Sets the initial pointer to `start_id` (default "0", meaning the beginning
              of the stream) if the group is being newly created.

        Args:
            kind (StreamKind): The category of the stream (e.g., 'events').
            group (str): The name of the consumer group to create.
            start_id (str, optional): The stream ID from which the group should begin
                processing if it is newly created. Defaults to "0" (process all history).
        """
        key = self._stream_key(kind)
        try:
            await self._redis.xgroup_create(
                name=key,
                groupname=group,
                id=start_id,
                mkstream=True,
            )
        except Exception as e:
            # Redis raises a specific error if the group name is already taken.
            # We catch generic Exception to be safe across redis-py versions, but check
            # the message content to ensure we only suppress "already exists" errors.
            msg = str(e).lower()
            if "busygroup" in msg or "exists" in msg:
                return
            raise

    async def consume(
        self,
        *,
        kind: StreamKind,
        cfg: RedisConsumerGroupConfig,
        read_id: str = ">",
    ) -> tuple[RedisStreamEntry, ...]:
        """
        Consume records from a Redis Stream using a consumer group.

        This method wraps the `XREADGROUP` command to fetch messages distributed to
        this specific consumer. It handles the raw Redis response format and decodes
        valid JSON payloads into `RedisStreamEntry` objects.

        Processing Semantics:
            - **No Auto-Ack**: Messages returned here are added to the Pending Entries List
              (PEL) and must be explicitly acknowledged via `ack()` later.
            - **New vs. Pending**: If `read_id` is ">", Redis delivers new, unread messages.
              If `read_id` is "0" (or another ID), it delivers unacknowledged pending messages.

        Args:
            kind (StreamKind): The stream category to consume from.
            cfg (RedisConsumerGroupConfig): Configuration object containing the group name,
                consumer name, batch count, and blocking behavior.
            read_id (str, optional): The ID to start reading from. Defaults to ">" (new messages).

        Returns:
            tuple[RedisStreamEntry, ...]: A tuple of decoded stream entries. Corrupted
                or malformed entries are skipped gracefully.
        """
        key = self._stream_key(kind)

        # Lazy initialization: Ensure the group exists before trying to read.
        if cfg.ensure_group:
            await self.ensure_consumer_group(
                kind=kind,
                group=cfg.group,
                start_id=cfg.start_id,
            )

        # Execute XREADGROUP. The response structure is:
        # [[stream_name, [[id, fields], [id, fields], ...]]]
        resp = await self._redis.xreadgroup(
            groupname=cfg.group,
            consumername=cfg.consumer,
            streams={key: read_id},
            count=cfg.count,
            block=cfg.block_ms,
        )

        out: list[RedisStreamEntry] = []

        # Iterate over streams (we usually only query one)
        for _stream, entries in resp or []:
            for entry_id, fields in entries:
                # Attempt to parse the 'data' field JSON
                obj = self._decode_entry(fields)
                if obj is None:
                    continue

                # Append valid entries to the result list
                out.append(RedisStreamEntry(id=str(entry_id), data=obj))

        return tuple(out)

    async def claim(
        self,
        kind: StreamKind,
        *,
        group: str,
        consumer: str,
        min_idle_ms: int,
        entry_ids: list[str],
    ) -> list[RedisStreamEntry]:
        """
        Transfer ownership of pending stream messages to a specific consumer.

        This method executes the Redis `XCLAIM` command, which is essential for
        recovering from consumer failures. If a consumer crashes or fails to acknowledge
        a message within `min_idle_ms`, another consumer (or the same one upon restart)
        can "claim" it.

        Effects:
        - The ownership of the messages with `entry_ids` is transferred to `consumer`.
        - The idle time for these messages is reset.
        - The messages are returned so they can be processed immediately.

        Behavior:
        - Only messages that have been idle longer than `min_idle_ms` are successfully claimed.
        - Invalid or non-existent message IDs are ignored.
        - Malformed payloads (non-JSON) found during the claim are skipped in the output,
          but ownership is still transferred in Redis.

        Args:
            kind (StreamKind): The stream category (e.g., 'events').
            group (str): The name of the consumer group.
            consumer (str): The name of the consumer taking ownership.
            min_idle_ms (int): The minimum time (in milliseconds) a message must have
                been idle (unacknowledged) before it can be claimed.
            entry_ids (list[str]): The list of message IDs to attempt to claim.

        Returns:
            list[RedisStreamEntry]: A list of successfully claimed and parsed messages.
        """
        key = self._stream_key(kind)

        if not entry_ids:
            return []

        # Attempt XCLAIM. We use a try-except block to handle historical variations
        # in the redis-py library's method signature, ensuring robustness across versions.
        try:
            entries = await self._redis.xclaim(
                key,
                groupname=group,
                consumername=consumer,
                min_idle_time=min_idle_ms,
                message_ids=entry_ids,
            )
        except TypeError:
            # Fallback for older or alternative redis-py signatures
            entries = await self._redis.xclaim(
                key,
                group,
                consumer,
                min_idle_ms,
                entry_ids,
            )

        out: list[RedisStreamEntry] = []

        # Process the returned entries. Redis returns: list[tuple[id, dict[field, value]]]
        for _id, fields in entries or []:
            raw = None
            if isinstance(fields, dict):
                raw = fields.get("data")

            # Validate payload is a string
            if not isinstance(raw, str):
                continue

            try:
                obj = json.loads(raw)
            except Exception:
                # Silently skip corruption; claiming is about delivery, not repair
                continue

            if isinstance(obj, dict):
                out.append(RedisStreamEntry(id=str(_id), data=obj))

        return out

    async def ack(
        self,
        *,
        kind: StreamKind,
        group: str,
        ids: list[str] | tuple[str, ...],
    ) -> int:
        """
        Acknowledge successful processing of messages.

        This calls `XACK` to remove the specified message IDs from the consumer group's
        Pending Entries List (PEL). Once acknowledged, a message will not be redelivered
        to other consumers.

        Args:
            kind (StreamKind): The stream category.
            group (str): The name of the consumer group.
            ids (list[str] | tuple[str, ...]): A collection of message IDs to acknowledge.

        Returns:
            int: The number of messages successfully acknowledged.
        """
        if not ids:
            return 0
        key = self._stream_key(kind)
        return int(await self._redis.xack(key, group, *ids))

    async def pending_summary(
        self,
        *,
        kind: StreamKind,
        group: str,
    ) -> dict[str, Any]:
        """
        Retrieve a summary of pending messages for a consumer group.

        This method wraps `XPENDING` to provide observability into consumer lag.
        It returns data such as the total number of pending messages, the range of
        message IDs, and a breakdown of pending counts per consumer.

        Args:
            kind (StreamKind): The stream category.
            group (str): The consumer group name.

        Returns:
            dict[str, Any]: A dictionary containing the raw pending summary from Redis.
                Useful for metrics or debugging tools.
        """
        key = self._stream_key(kind)
        res = await self._redis.xpending(key, group)
        # Wrap in a dict to future-proof against varying return types from different
        # redis-py versions or mocks.
        return {"raw": res}

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
