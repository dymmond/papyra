from __future__ import annotations

import json
import os
import time
from pathlib import Path
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
        and performs the write operation safely using a lock. Persistence metrics are updated
        on write success or error.

        Args:
            record (dict[str, Any]): The dictionary containing data to be stored.
        """
        if self._closed:
            return

        line = json.dumps(record, default=_json_default) + "\n"
        line_bytes = len(line.encode("utf-8"))

        try:
            async with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                await self._maybe_rotate(line_bytes)

                async with await anyio.open_file(self._path, "a", encoding="utf-8") as f:
                    await f.write(line)
                    await f.flush()
                    if self._fsync:
                        await anyio.to_thread.run_sync(os.fsync, f.fileno)  # type: ignore

            await self._metrics_on_write_ok(records=1, bytes_written=line_bytes)
        except Exception:
            await self._metrics_on_write_error()
            raise

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

    async def compact(self) -> CompactionReport:
        """
        Physically compact all rotated log files by rewriting them while applying retention.

        This operation:
        - Reads all existing log files (oldest -> newest)
        - Discards corrupted lines
        - Applies retention once
        - Rewrites records into a minimal set of files respecting max_bytes
        - Atomically replaces old files
        """
        await self._metrics_on_compact_start()
        try:
            async with self._lock:
                # Read all raw rows
                rows: list[dict[str, Any]] = []
                before_bytes = 0

                for p in self._iter_read_paths_oldest_first():
                    if not p.exists():
                        continue

                    try:
                        before_bytes += p.stat().st_size
                        async with await anyio.open_file(p, "r", encoding="utf-8") as f:
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
                    except OSError:
                        # File may disappear during compaction preparation
                        continue

                before_records = len(rows)

                # Apply retention
                if self.retention is not None:
                    rows = apply_retention(rows, self.retention)

                after_records = len(rows)

                # Split rows into chunks respecting max_bytes
                chunks: list[list[str]] = []
                current_chunk: list[str] = []
                current_size = 0

                for row in rows:
                    line = json.dumps(row, default=_json_default) + "\n"
                    size = len(line.encode("utf-8"))

                    if current_chunk and current_size + size > self._max_bytes:
                        chunks.append(current_chunk)
                        current_chunk = []
                        current_size = 0

                    current_chunk.append(line)
                    current_size += size

                if current_chunk:
                    chunks.append(current_chunk)

                # Enforce max_files limit (keep newest chunks)
                if len(chunks) > self._max_files:
                    chunks = chunks[-self._max_files :]

                # --- Write temp files ---
                tmp_paths: list[Path] = []

                for idx, chunk in enumerate(reversed(chunks)):
                    # idx == 0 → active file
                    if idx == 0:
                        tmp = self._path.with_suffix(self._path.suffix + ".compact.tmp")
                    else:
                        tmp = self._rotated_path(idx).with_suffix(self._rotated_path(idx).suffix + ".compact.tmp")

                    async with await anyio.open_file(tmp, "w", encoding="utf-8") as f:
                        for line in chunk:
                            await f.write(line)
                        await f.flush()

                    tmp_paths.append(tmp)

                # First remove old files
                for p in self._iter_read_paths_oldest_first():
                    try:
                        p.unlink()
                    except FileNotFoundError:
                        pass

                # Then move new compacted files into place
                for tmp in tmp_paths:
                    final = Path(str(tmp).replace(".compact.tmp", ""))
                    os.replace(tmp, final)

                after_bytes = sum(p.stat().st_size for p in self._iter_read_paths_oldest_first() if p.exists())

            return CompactionReport(
                backend="rotating",
                before_records=before_records,
                after_records=after_records,
                before_bytes=before_bytes,
                after_bytes=after_bytes,
            )
        except Exception:
            await self._metrics_on_compact_error()
            raise

    async def scan(self) -> PersistenceScanReport:
        """
        Scan the storage directory to detect structural and data anomalies.

        This method performs a comprehensive health check on the persistence layer by
        examining both the file system state and the content of individual log files.

        The scan detects:
        - **Orphaned Files**: Files in the directory that match the naming pattern
          but do not fit within the configured `max_files` rotation limit.
        - **Truncated Lines**: Lines that end abruptly without a newline character,
          often caused by crashes during a write operation.
        - **Corrupted Lines**: Lines that contain invalid JSON data.
        - **Unreadable Files**: Files that exist but cannot be opened or read.

        Returns:
            PersistenceScanReport: A report object containing a tuple of all detected
                anomalies. If no issues are found, the tuple is empty.
        """
        await self._metrics_on_scan_start()
        try:
            anomalies: list[PersistenceAnomaly] = []

            # ---------------------------------------------------------
            # Phase 1: Detect File System Anomalies (Orphans)
            # ---------------------------------------------------------
            # Calculate the set of file paths that are valid according to the rotation policy
            expected = {
                str(self._path),
                *(str(self._rotated_path(i)) for i in range(1, self._max_files)),
            }

            # Find all files actually present on disk that match the base filename pattern
            existing = {str(p) for p in self._path.parent.glob(self._path.name + "*")}

            # Any existing file that is not in the expected set is considered orphaned
            for p in existing - expected:
                anomalies.append(
                    PersistenceAnomaly(
                        type=PersistenceAnomalyType.ORPHANED_ROTATED_FILE,
                        path=p,
                        detail="Unexpected file in rotation set",
                    )
                )

            # ---------------------------------------------------------
            # Phase 2: Detect Content Anomalies (Corruption/Truncation)
            # ---------------------------------------------------------
            # Iterate over all valid files, generally checking oldest first
            for p in self._iter_read_paths_oldest_first():  # type: ignore
                if not p.exists():  # type: ignore
                    continue

                try:
                    async with await anyio.open_file(p, "r", encoding="utf-8") as file:
                        idx = 0
                        async for line in file:
                            idx += 1
                            # Check for truncation: The last written line must have a newline
                            if not line.endswith("\n"):
                                anomalies.append(
                                    PersistenceAnomaly(
                                        type=PersistenceAnomalyType.TRUNCATED_LINE,
                                        path=str(p),
                                        detail=f"Line {idx} missing newline",
                                    )
                                )
                                # A truncated line usually means the end of valid data
                                break

                            # Check for corruption: Ensure the line is valid JSON
                            try:
                                json.loads(line)
                            except Exception:
                                anomalies.append(
                                    PersistenceAnomaly(
                                        type=PersistenceAnomalyType.CORRUPTED_LINE,
                                        path=str(p),
                                        detail=f"Invalid JSON at line {idx}",
                                    )
                                )
                except OSError:
                    # If the file exists but cannot be read, report it as a partial/failed write
                    anomalies.append(
                        PersistenceAnomaly(
                            type=PersistenceAnomalyType.PARTIAL_WRITE,
                            path=str(p),
                            detail="File could not be read fully",
                        )
                    )

            await self._metrics_on_anomalies_detected(len(anomalies))
            return PersistenceScanReport(
                backend="rotating",
                anomalies=tuple(anomalies),
            )
        except Exception:
            await self._metrics_on_scan_error()
            raise

    async def recover(self, config: Any = None) -> PersistenceRecoveryReport | None:
        """
        Execute a recovery process for the rotating log files based on the specified configuration.

        This method is responsible for restoring the integrity of the persistence layer in the
        event of corruption or filesystem anomalies. The recovery process involves several
        distinct phases:

        1.  **Scanning**: The current state of the log files is analyzed to detect anomalies
            such as orphaned files, missing files, or corrupted data within the files.
        2.  **Quarantine (Optional)**: If the recovery mode is set to QUARANTINE, unexpected
            or corrupted files are moved to a separate directory for manual inspection,
            preserving the original state before repair.
        3.  **Repair**: The method iterates through all expected log files. It attempts to read
            valid JSON records from them. If a file contains corrupted lines (non-JSON) or is
            truncated (missing a newline at the end), those specific anomalies are discarded
            or handled, and the file is rewritten with only the valid data.

        Args:
            config (Any, optional): A configuration object (PersistenceRecoveryConfig)
                dictating the recovery mode (e.g., IGNORE, QUARANTINE) and parameters.
                If None, a default configuration is instantiated.

        Returns:
            PersistenceRecoveryReport | None: A detailed report summarizing the scan results,
                which files were repaired, and which were quarantined. Returns None if the
                initial scan fails to initialize.
        """
        await self._metrics_on_recover_start()
        try:
            cfg = config or PersistenceRecoveryConfig()

            scan = await self.scan()
            if scan is None:
                return None

            if cfg.mode is PersistenceRecoveryMode.IGNORE or not scan.has_anomalies:
                return PersistenceRecoveryReport(backend="rotating", scan=scan)

            repaired_files: list[str] = []
            quarantined_files: list[str] = []

            # ---------------------------------------------------------
            # STEP 1: Collect all valid records globally
            # ---------------------------------------------------------
            records: list[dict[str, Any]] = []

            for p in self._iter_read_paths_oldest_first():
                if not p.exists():
                    continue

                try:
                    async with await anyio.open_file(p, "r", encoding="utf-8") as f:
                        async for line in f:
                            if not line.endswith("\n"):
                                break
                            try:
                                obj = json.loads(line)
                            except Exception:
                                continue
                            if isinstance(obj, dict):
                                records.append(obj)
                except OSError:
                    continue

            # ---------------------------------------------------------
            # STEP 2: Apply retention globally
            # ---------------------------------------------------------
            if self.retention is not None:
                records = apply_retention(records, self.retention)

            # ---------------------------------------------------------
            # STEP 3: Quarantine entire previous rotation set (optional)
            # ---------------------------------------------------------
            if cfg.mode is PersistenceRecoveryMode.QUARANTINE:
                qdir = Path(cfg.quarantine_dir) if cfg.quarantine_dir else self._path.parent
                qdir.mkdir(parents=True, exist_ok=True)
                stamp = int(time.time() * 1000)

                for p in self._iter_read_paths_oldest_first():
                    if not p.exists():
                        continue
                    qpath = qdir / f"{p.name}.quarantine.{stamp}"
                    os.replace(p, qpath)
                    quarantined_files.append(str(qpath))

            # ---------------------------------------------------------
            # STEP 4: Rebuild rotation set from scratch
            # ---------------------------------------------------------
            buffers: list[list[str]] = [[]]
            current_bytes = 0

            for row in records:
                line = json.dumps(row, default=_json_default) + "\n"
                size = len(line.encode("utf-8"))

                if current_bytes + size > self._max_bytes:
                    buffers.append([])
                    current_bytes = 0

                buffers[-1].append(line)
                current_bytes += size

            # Enforce max_files (drop oldest if overflow)
            buffers = buffers[-self._max_files :]

            # Write files oldest -> newest
            for idx, lines in enumerate(reversed(buffers)):
                if idx == 0:
                    target = self._path
                else:
                    target = self._rotated_path(idx)

                tmp = target.with_suffix(target.suffix + ".recovered.tmp")
                async with await anyio.open_file(tmp, "w", encoding="utf-8") as wf:
                    for line in lines:
                        await wf.write(line)
                    await wf.flush()

                os.replace(tmp, target)
                repaired_files.append(str(target))

            return PersistenceRecoveryReport(
                backend="rotating",
                scan=scan,
                repaired_files=tuple(repaired_files),
                quarantined_files=tuple(quarantined_files),
            )
        except Exception:
            await self._metrics_on_recovery_error()
            raise
