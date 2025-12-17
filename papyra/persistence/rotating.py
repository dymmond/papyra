from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anyio
import anyio.abc

from ._rentention import apply_retention
from ._utils import _json_default, _pick_dataclass_fields
from .base import PersistenceBackend
from .models import PersistedAudit, PersistedDeadLetter, PersistedEvent
from .retention import RetentionPolicy


class RotatingFilePersistence(PersistenceBackend):
    """
    A persistence backend that stores data in Newline Delimited JSON (NDJSON) format
    with automatic log rotation capabilities.

    This class manages a set of files to store records. When the active file exceeds a
    configured size limit, it is rotated. The rotation strategy ensures that a fixed
    maximum number of files are kept, deleting the oldest ones as necessary.

    Storage Format:
        The data is stored as NDJSON, where each line represents a distinct JSON object.
        A 'kind' discriminator field is added to each record to distinguish between
        different record types:
        - {"kind": "event", ...}
        - {"kind": "audit", ...}
        - {"kind": "dead_letter", ...}

    Rotation Strategy:
        - The active file is located at `path`.
        - Rotated files are named with numerical suffixes: `path.1`, `path.2`, etc.
        - The file `path.1` represents the most recently rotated file.
        - The file `path.N` (where N is `max_files - 1`) represents the oldest file.
        - When the active file needs rotation:
            1. The oldest file (if it exists) is deleted.
            2. Existing rotated files are shifted (e.g., .2 becomes .3, .1 becomes .2).
            3. The active file is renamed to .1.
            4. A new empty active file is created.

    Attributes:
        _path (Path): The file system path to the active log file.
        _max_bytes (int): The maximum size in bytes allowed for the active file before rotation.
        _max_files (int): The maximum number of log files to keep (including the active one).
        _fsync (bool): Whether to force a file system sync after every write for durability.
        _lock (anyio.abc.Lock): An async lock to ensure thread-safe file operations.
        _closed (bool): A flag indicating if the persistence backend has been closed.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int = 50_000_000,
        max_files: int = 5,
        fsync: bool = False,
        retention_policy: RetentionPolicy | None = None,
    ) -> None:
        """
        Initialize the RotatingFilePersistence backend.

        Args:
            path (str | Path): The base file path where logs will be stored.
            max_bytes (int, optional): The maximum size of the file in bytes before it
                is rotated. Defaults to 50,000,000 (50MB).
            max_files (int, optional): The maximum number of history files to keep,
                including the active file. Defaults to 5.
            fsync (bool, optional): If True, os.fsync is called after every write to
                ensure data is flushed to physical storage. Defaults to False.

        Raises:
            ValueError: If `max_bytes` or `max_files` are less than or equal to 0.
        """
        super().__init__(retention_policy=retention_policy)
        self._path = Path(path)
        self._max_bytes = int(max_bytes)
        self._max_files = int(max_files)
        self._fsync = bool(fsync)

        self._lock: anyio.abc.Lock = anyio.Lock()
        self._closed: bool = False

        if self._max_bytes <= 0:
            raise ValueError("max_bytes must be > 0")
        if self._max_files <= 0:
            raise ValueError("max_files must be > 0")

    @property
    def path(self) -> Path:
        """
        Get the file system path of the active log file.

        Returns:
            Path: The path object representing the active log file location.
        """
        return self._path

    @property
    def closed(self) -> bool:
        """
        Check if the persistence backend is closed.

        Returns:
            bool: True if the backend is closed and no longer accepting writes, False otherwise.
        """
        return self._closed

    def _rotated_path(self, index: int) -> Path:
        """
        Construct the path for a rotated log file based on a given index.

        For example, if the base path is `app.log` and index is 1, this returns `app.log.1`.

        Args:
            index (int): The rotation index suffix.

        Returns:
            Path: The path object for the specific rotated file.
        """
        return self._path.with_name(f"{self._path.name}.{index}")

    def _iter_read_paths_oldest_first(self) -> list[Path]:
        """
        Generate a list of all existing log paths sorted chronologically from oldest to newest.

        This iterates through potential rotated files in reverse order (highest index to lowest)
        and appends the active file last.

        Example Order:
            [path.4, path.3, path.2, path.1, path]

        Returns:
            list[Path]: A list of existing Path objects ordered by age (oldest first).
        """
        paths: list[Path] = []
        # Check rotated files from highest index (oldest) down to 1 (newest rotated)
        for i in range(self._max_files - 1, 0, -1):
            p = self._rotated_path(i)
            if p.exists():
                paths.append(p)
        # Finally, add the active file if it exists (it is the newest)
        if self._path.exists():
            paths.append(self._path)
        return paths

    async def _truncate_active(self) -> None:
        """
        Truncate the active log file to zero length.

        This method is used specifically when `max_files` is set to 1, effectively
        resetting the single allowed log file instead of rotating it. It ensures the parent
        directory exists before opening the file.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with await anyio.open_file(self._path, "w", encoding="utf-8") as f:
            await f.write("")
            await f.flush()
            if self._fsync:
                await anyio.to_thread.run_sync(os.fsync, f.fileno)  # type: ignore

    async def _maybe_rotate(self, next_line_len: int) -> None:
        """
        Check if the active file needs rotation and perform the rotation if necessary.

        This method checks the current size of the active file. If adding `next_line_len`
        bytes would cause the file to exceed `_max_bytes`, a rotation sequence is triggered.

        Args:
            next_line_len (int): The length of the new line (in bytes) that is about
                to be written.
        """
        # We use anyio.Path for async file system operations to avoid blocking the loop
        main_file = anyio.Path(self._path)

        if not await main_file.exists():
            return

        stat = await main_file.stat()
        # If the current size plus the new line fits within the limit, no rotation is needed
        if stat.st_size + next_line_len <= self._max_bytes:
            return

        # Special case: If we only keep 1 file, we just clear the current file
        if self._max_files == 1:
            await self._truncate_active()
            return

        # Rotation needed
        oldest = self._rotated_path(self._max_files - 1)
        if oldest.exists():
            return

        # 2. Shift existing rotated files down: e.g., .3 -> .4, .2 -> .3, etc.
        # We iterate backwards to avoid overwriting files we haven't moved yet
        for i in range(self._max_files - 2, 0, -1):
            src = anyio.Path(self._rotated_path(i))
            if await src.exists():
                dest = anyio.Path(self._rotated_path(i + 1))
                await src.rename(dest)

        # 3. Rename current active file to .1 (the most recent rotated file)
        dest_one = anyio.Path(self._rotated_path(1))
        await main_file.rename(dest_one)

    async def _append(self, record: dict[str, Any]) -> None:
        """
        Append a single dictionary record to the active log file in NDJSON format.

        This method handles the serialization of the record, checks if rotation is required,
        and performs the write operation safely using a lock.

        Args:
            record (dict[str, Any]): The dictionary containing data to be stored.
        """
        if self._closed:
            return

        # Serialize to JSON and append a newline character
        line = json.dumps(record, default=_json_default) + "\n"
        line_bytes = len(line.encode("utf-8"))

        # Acquire lock to ensure no other coroutine is writing or rotating simultaneously
        async with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Check if this write triggers a rotation before actually writing
            await self._maybe_rotate(line_bytes)

            async with await anyio.open_file(self._path, "a", encoding="utf-8") as f:
                await f.write(line)
                await f.flush()
                # Perform fsync if durability is strictly required
                if self._fsync:
                    await anyio.to_thread.run_sync(os.fsync, f.fileno)  # type: ignore

    async def _read_all(self) -> list[dict[str, Any]]:
        """
        Read and parse all valid JSON lines from all log files.

        The files are read in chronological order (oldest rotated file -> active file).
        Lines that cannot be parsed as JSON are skipped gracefully.

        Returns:
            list[dict[str, Any]]: A list of dictionaries parsed from the log files.
        """
        results: list[dict[str, Any]] = []

        # Determine paths while lock is not held (reading old files is generally safe).
        # Note: We don't lock the whole read because reading large files could block
        # writers for too long.
        paths = self._iter_read_paths_oldest_first()

        for p in paths:
            if not p.exists():
                continue

            try:
                async with await anyio.open_file(p, "r", encoding="utf-8") as f:
                    async for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if isinstance(data, dict):
                                results.append(data)
                        except json.JSONDecodeError:
                            # Skip corrupted lines to prevent crashing the reader
                            continue
            except OSError:
                # File might have been rotated/deleted during iteration by a writer
                continue

        if getattr(self, "_retention_policy", None) is not None:
            results = apply_retention(results, self.retention)

        return results

    async def record_event(self, event: PersistedEvent) -> None:  # type: ignore
        """
        Persist an event record to storage.

        The event is converted to a dictionary, marked with kind="event", and appended.

        Args:
            event (PersistedEvent): The event data object to record.
        """
        data = _json_default(event)  # Converts dataclass to dict
        data["kind"] = "event"
        await self._append(data)

    async def record_audit(self, audit: PersistedAudit) -> None:  # type: ignore
        """
        Persist an audit record to storage.

        The audit log is converted to a dictionary, marked with kind="audit", and appended.

        Args:
            audit (PersistedAudit): The audit data object to record.
        """
        data = _json_default(audit)
        data["kind"] = "audit"
        await self._append(data)

    async def record_dead_letter(self, dead_letter: PersistedDeadLetter) -> None:  # type: ignore
        """
        Persist a dead letter record to storage.

        The dead letter is converted to a dictionary, marked with kind="dead_letter",
        and appended.

        Args:
            dead_letter (PersistedDeadLetter): The dead letter data object to record.
        """
        data = _json_default(dead_letter)
        data["kind"] = "dead_letter"
        await self._append(data)

    async def list_events(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedEvent, ...]:
        """
        Retrieve a list of persisted events, optionally filtered by time and limited by count.

        Args:
            limit (int | None, optional): The maximum number of most recent events to return.
                Defaults to None (return all).
            since (float | None, optional): A unix timestamp. Only events occurring after
                this time will be returned. Defaults to None.

        Returns:
            tuple[PersistedEvent, ...]: A tuple of PersistedEvent objects.
        """
        raw_records = apply_retention(await self._read_all(), self.retention)
        events: list[PersistedEvent] = []

        for r in raw_records:
            if r.get("kind") != "event":
                continue

            r = dict(r)
            r.pop("kind", None)

            # Timestamp filtering checks both 'timestamp' and 'created_at' fields
            if since is not None:
                ts = r.get("timestamp") or r.get("created_at")
                if ts is None or float(ts) < since:
                    continue

            # Convert back to dataclass using utility to filter valid fields
            fields_data = _pick_dataclass_fields(PersistedEvent, r)
            events.append(PersistedEvent(**fields_data))

        if limit is not None:
            # return the N most recent items
            events = events[-limit:]

        return tuple(events)

    async def list_audits(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedAudit, ...]:
        """
        Retrieve a list of persisted audit logs, optionally filtered by time and limited by count.

        Args:
            limit (int | None, optional): The maximum number of most recent audits to return.
                Defaults to None.
            since (float | None, optional): A unix timestamp. Only audits occurring after
                this time will be returned. Defaults to None.

        Returns:
            tuple[PersistedAudit, ...]: A tuple of PersistedAudit objects.
        """
        raw_records = apply_retention(await self._read_all(), self.retention)
        audits: list[PersistedAudit] = []

        for r in raw_records:
            if r.get("kind") != "audit":
                continue

            r = dict(r)
            r.pop("kind", None)

            if since is not None:
                ts = r.get("timestamp") or r.get("created_at")
                if ts is None or float(ts) < since:
                    continue

            fields_data = _pick_dataclass_fields(PersistedAudit, r)
            audits.append(PersistedAudit(**fields_data))

        if limit is not None:
            audits = audits[-limit:]

        return tuple(audits)

    async def list_dead_letters(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedDeadLetter, ...]:
        """
        Retrieve a list of dead letters, optionally filtered by time and limited by count.

        Args:
            limit (int | None, optional): The maximum number of most recent dead letters
                to return. Defaults to None.
            since (float | None, optional): A unix timestamp. Only dead letters occurring
                after this time will be returned. Defaults to None.

        Returns:
            tuple[PersistedDeadLetter, ...]: A tuple of PersistedDeadLetter objects.
        """
        raw_records = apply_retention(await self._read_all(), self.retention)
        dls: list[PersistedDeadLetter] = []

        for r in raw_records:
            if r.get("kind") != "dead_letter":
                continue

            r = dict(r)
            r.pop("kind", None)

            if since is not None:
                # Dead letters usually have a 'timestamp' field
                ts = r.get("timestamp")
                if ts is None or float(ts) < since:
                    continue

            fields_data = _pick_dataclass_fields(PersistedDeadLetter, r)
            dls.append(PersistedDeadLetter(**fields_data))

        if limit is not None:
            dls = dls[-limit:]

        return tuple(dls)

    async def clear(self) -> None:
        """
        Delete all log files associated with this persistence instance.

        This method acquires the lock and iterates through all possible rotated files
        as well as the active file, unlinking them from the file system.
        """
        async with self._lock:
            for p in self._iter_read_paths_oldest_first():
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass

    async def aclose(self) -> None:
        """
        Close the persistence backend.

        This sets the closed flag to True, preventing further writes. It is an async
        operation that acquires the lock to ensure state consistency.
        """
        async with self._lock:
            self._closed = True
