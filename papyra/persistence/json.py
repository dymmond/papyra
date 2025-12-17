from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

import anyio
import anyio.abc

from papyra.persistence.retention import RetentionPolicy

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
    PersistenceScanReport,
)

T = TypeVar("T")


class JsonFilePersistence(PersistenceBackend):
    """
    A persistent backend that stores records in a local NDJSON (Newline Delimited JSON) file.

    This implementation writes system facts (events, audits, dead letters) to a single file,
    where each line corresponds to a distinct JSON object. This format is simple, append-only,
    and easily readable by humans or external log processing tools.

    Features
    --------
    - **Append-Only**: New records are strictly appended to the end of the file, minimizing
      write conflicts and corruption risks.
    - **Discriminator Field**: Each record includes a "kind" field ("event", "audit", or
      "dead_letter") to distinguish its type within the single stream.
    - **Fault Tolerance**: The read path silently skips invalid JSON lines or unknown record
      types, ensuring that a single corrupted line does not render the entire log unreadable.
    - **Thread Safety**: Writes are guarded by an asynchronous lock (`anyio.Lock`) to prevent
      race conditions between concurrent actors.

    Attributes
    ----------
    _path : Path
        The filesystem path to the storage file.
    _lock : anyio.abc.Lock
        Async lock ensuring exclusive write access.
    _closed : bool
        Flag indicating if the backend has been shut down.
    """

    def __init__(self, path: str | Path, retention_policy: RetentionPolicy | None = None) -> None:
        """
        Initialize the file-based persistence backend.

        Parameters
        ----------
        path : str | Path
            The location where the log file should be created or opened. If the parent directory
            does not exist, it will be created automatically upon the first write.
        """
        super().__init__(retention_policy=retention_policy)
        self._path = Path(path)
        self._lock: anyio.abc.Lock = anyio.Lock()
        self._closed: bool = False

    @property
    def path(self) -> Path:
        """
        Return the configured storage path.

        Returns
        -------
        Path
            The file path used for persistence.
        """
        return self._path

    async def _append(self, record: dict[str, Any]) -> None:
        """
        Internal helper to safely append a dictionary record to the file as a JSON line.

        This method handles directory creation, JSON serialization, and atomic file locking.

        Parameters
        ----------
        record : dict[str, Any]
            The dictionary to persist.
        """
        async with self._lock:
            if self._closed:
                return

            # Ensure the directory structure exists before writing.
            self._path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize without ASCII escaping to support UTF-8 characters natively.
            line = json.dumps(record, ensure_ascii=False, default=_json_default) + "\n"

            # Open, write, and flush to ensure data is on disk.
            async with await anyio.open_file(self._path, mode="a", encoding="utf-8") as f:
                await f.write(line)
                await f.flush()

    async def record_event(self, event: PersistedEvent) -> None:  # type: ignore
        """
        Persist a lifecycle event to the file.

        The event is wrapped with `kind="event"` before storage.
        """
        await self._append(
            {
                "kind": "event",
                **_json_default(event),
            }
        )

    async def record_audit(self, audit: PersistedAudit) -> None:  # type: ignore
        """
        Persist an audit snapshot to the file.

        The record is wrapped with `kind="audit"` before storage.
        """
        await self._append(
            {
                "kind": "audit",
                **_json_default(audit),
            }
        )

    async def record_dead_letter(self, dead_letter: PersistedDeadLetter) -> None:  # type: ignore
        """
        Persist a dead letter to the file.

        The record is wrapped with `kind="dead_letter"` before storage.
        """
        await self._append(
            {
                "kind": "dead_letter",
                **_json_default(dead_letter),
            }
        )

    async def _read_all(self) -> Iterable[dict[str, Any]]:
        """
        Internal helper to read and parse all valid JSON lines from the file.

        This method iterates through the file line by line. Malformed lines are silently
        ignored to ensure robustness.

        Returns
        -------
        Iterable[dict[str, Any]]
            A list of successfully parsed JSON objects (dictionaries). Returns an empty list
            if the file does not exist.
        """
        # No lock needed for reads, but check for existence first.
        if not self._path.exists():
            return ()

        async with await anyio.open_file(self._path, mode="r", encoding="utf-8") as f:
            out: list[dict[str, Any]] = []
            async for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    # Skip corrupted lines
                    continue
                if isinstance(obj, dict):
                    out.append(obj)

            if self.retention is not None:
                out = apply_retention(out, self.retention)

            return out

    async def list_events(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedEvent, ...]:
        """
        Retrieve persisted events, optionally filtered by time or count.

        Parameters
        ----------
        limit : int | None, optional
            The maximum number of recent events to return. Defaults to None (all events).
        since : float | None, optional
            Exclude events that occurred before this timestamp. Defaults to None.

        Returns
        -------
        tuple[PersistedEvent, ...]
            A tuple of reconstructed `PersistedEvent` objects.
        """
        rows = apply_retention(await self._read_all(), self.retention)  # type: ignore
        items: list[PersistedEvent] = []

        for row in rows:
            if row.get("kind") != "event":
                continue
            # Clone and remove the discriminator
            row = dict(row)
            row.pop("kind", None)

            try:
                ev = PersistedEvent(**_pick_dataclass_fields(PersistedEvent, row))
            except Exception:
                # Allow partially valid records (e.g. timestamp-only) to survive
                try:
                    ev = PersistedEvent(
                        system_id=row.get("system_id", "local"),
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
            # Slice to get the last `limit` items (most recent usually at end)
            items = items[-limit:]

        return tuple(items)

    async def list_audits(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedAudit, ...]:
        """
        Retrieve persisted audit records.

        Parameters
        ----------
        limit : int | None, optional
            Max number of records to return.
        since : float | None, optional
            Filter records older than this timestamp.

        Returns
        -------
        tuple[PersistedAudit, ...]
        """
        rows = apply_retention(await self._read_all(), self.retention)  # type: ignore
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
                        system_id=row.get("system_id", "local"),
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
        Retrieve persisted dead letters.

        Parameters
        ----------
        limit : int | None, optional
            Max number of records to return.
        since : float | None, optional
            Filter records older than this timestamp.

        Returns
        -------
        tuple[PersistedDeadLetter, ...]
        """
        rows = apply_retention(await self._read_all(), self.retention)  # type: ignore
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
                        system_id=row.get("system_id", "local"),
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

    async def aclose(self) -> None:
        """
        Close the persistence backend.

        Sets the closed flag to prevent further writes.
        """
        async with self._lock:
            self._closed = True

    @property
    def closed(self) -> bool:
        """
        Check if the backend is closed.
        """
        return self._closed

    async def compact(self) -> CompactionReport:
        """
        Physically compact the NDJSON file by rewriting it while applying retention.

        This operation is explicit, destructive, and atomic:
        - Corrupted lines are discarded
        - Retention is enforced physically
        - The original file is replaced via os.replace()
        """
        async with self._lock:
            before_bytes = self._path.stat().st_size if self._path.exists() else 0

            rows: list[dict[str, Any]] = []

            if self._path.exists():
                async with await anyio.open_file(self._path, mode="r", encoding="utf-8") as f:
                    async for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        if isinstance(obj, dict):
                            rows.append(obj)

            before_records = len(rows)

            if self.retention is not None:
                rows = apply_retention(rows, self.retention)

            after_records = len(rows)

            tmp_path = self._path.with_suffix(self._path.suffix + ".compact.tmp")

            async with await anyio.open_file(tmp_path, mode="w", encoding="utf-8") as f:
                for row in rows:
                    await f.write(json.dumps(row, ensure_ascii=False, default=_json_default) + "\n")
                await f.flush()

            os.replace(tmp_path, self._path)

            after_bytes = self._path.stat().st_size if self._path.exists() else 0

        return CompactionReport(
            backend="json",
            before_records=before_records,
            after_records=after_records,
            before_bytes=before_bytes,
            after_bytes=after_bytes,
        )

    async def scan(self) -> PersistenceScanReport:
        """
        Scan the JSON log file for structural anomalies.

        Detects:
        - truncated / corrupted JSON lines
        """
        anomalies: list[PersistenceAnomaly] = []

        if not self._path.exists():
            return PersistenceScanReport(backend="json", anomalies=())

        async with await anyio.open_file(self._path, mode="r", encoding="utf-8") as file:
            async for idx, line in enumerate(file):  # type: ignore
                if not line.endswith("\n"):
                    anomalies.append(
                        PersistenceAnomaly(
                            type=PersistenceAnomalyType.TRUNCATED_LINE,
                            path=str(self._path),
                            detail=f"Line {idx + 1} missing newline",
                        )
                    )
                    break

                try:
                    json.loads(line)
                except Exception:
                    anomalies.append(
                        PersistenceAnomaly(
                            type=PersistenceAnomalyType.CORRUPTED_LINE,
                            path=str(self._path),
                            detail=f"Invalid JSON at line {idx + 1}",
                        )
                    )

        return PersistenceScanReport(
            backend="json",
            anomalies=tuple(anomalies),
        )
