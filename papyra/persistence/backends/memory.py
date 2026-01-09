from __future__ import annotations

from typing import Any

import anyio
import anyio.abc

from papyra.persistence.base import PersistenceBackend
from papyra.persistence.models import (
    PersistedAudit,
    PersistedDeadLetter,
    PersistedEvent,
    PersistenceRecoveryReport,
    PersistenceScanReport,
)


class InMemoryPersistence(PersistenceBackend):
    """
    A default, ephemeral implementation of the persistence backend storing data in memory.

    This class serves as the reference implementation for the persistence protocol. It stores
    all recorded facts (events, audits, dead letters) in standard Python lists protected by
    an asynchronous lock.

    Purpose
    -------
    - **Development & Testing**: Provides immediate, setup-free persistence for local development
      and deterministic unit tests.
    - **Reference**: Demonstrates the expected behavior of a persistence backend (non-blocking,
      append-only semantics).
    - **Concurrency Safety**: Uses `anyio.Lock` to ensure safe concurrent access from multiple
      actors or background tasks.

    Attributes
    ----------
    _lock : anyio.abc.Lock
        An asynchronous reentrant lock guarding access to the internal lists.
    _events : list[PersistedEvent]
        Internal storage for lifecycle events.
    _audits : list[PersistedAudit]
        Internal storage for audit snapshots.
    _dead_letters : list[PersistedDeadLetter]
        Internal storage for dead letter records.
    _closed : bool
        Flag indicating if the backend has been shut down. Once closed, write operations become
        silent no-ops.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock: anyio.abc.Lock = anyio.Lock()

        self._events: list[PersistedEvent] = []
        self._audits: list[PersistedAudit] = []
        self._dead_letters: list[PersistedDeadLetter] = []

        self._closed: bool = False

    async def record_event(self, event: PersistedEvent) -> None:  # type: ignore
        """
        Asynchronously append a lifecycle event record to the internal store.

        This operation is guarded by a lock to ensure thread safety. If the backend is closed,
        the event is silently discarded to prevent errors during system shutdown.

        Parameters
        ----------
        event : PersistedEvent
            The immutable event record to store.
        """
        try:
            async with self._lock:
                if self._closed:
                    return
                self._events.append(event)
                await self._metrics_on_write_ok(records=1, bytes_written=0)
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def record_audit(self, audit: PersistedAudit) -> None:  # type: ignore
        """
        Asynchronously append an audit snapshot record to the internal store.

        Parameters
        ----------
        audit : PersistedAudit
            The immutable audit snapshot to store.
        """
        try:
            async with self._lock:
                if self._closed:
                    return
                self._audits.append(audit)
                await self._metrics_on_write_ok(records=1, bytes_written=0)
        except Exception:
            await self._metrics_on_write_error()
            raise

    async def record_dead_letter(self, dead_letter: PersistedDeadLetter) -> None:  # type: ignore
        """
        Asynchronously append a dead-letter record to the internal store.

        Parameters
        ----------
        dead_letter : PersistedDeadLetter
            The immutable dead letter record to store.
        """
        try:
            async with self._lock:
                if self._closed:
                    return
                self._dead_letters.append(dead_letter)
                await self._metrics_on_write_ok(records=1, bytes_written=0)
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
        Retrieve a snapshot of all stored lifecycle events.

        Returns
        -------
        tuple[PersistedEvent, ...]
            A tuple containing the events in the order they were recorded. A tuple is returned
            to prevent external modification of the internal list.
        """
        async with self._lock:
            events = self._events

            if since is not None:
                events = [e for e in events if e.timestamp >= since]

            if limit is not None:
                events = events[-limit:]

            return tuple(events)

    async def list_audits(
        self,
        *,
        limit: int | None = None,
        since: float | None = None,
    ) -> tuple[PersistedAudit, ...]:
        """
        Retrieve a snapshot of all stored audit reports.

        Returns
        -------
        tuple[PersistedAudit, ...]
            A tuple containing the audit records.
        """
        async with self._lock:
            audits = self._audits

            if since is not None:
                audits = [audit for audit in audits if audit.timestamp >= since]

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
        Retrieve a snapshot of all stored dead letters.

        Returns
        -------
        tuple[PersistedDeadLetter, ...]
            A tuple containing the dead letter records.
        """
        async with self._lock:
            dead_letters = self._dead_letters

            if since is not None:
                dead_letters = [dl for dl in dead_letters if dl.timestamp >= since]

            if limit is not None:
                dead_letters = dead_letters[-limit:]

            return tuple(dead_letters)

    async def clear(self) -> None:
        """
        Truncate all internal storage lists.

        This method is primarily useful in test suites to reset the state between test cases
        without re-instantiating the entire backend.
        """
        async with self._lock:
            self._events.clear()
            self._audits.clear()
            self._dead_letters.clear()

    async def aclose(self) -> None:
        """
        Gracefully close the persistence backend.

        Once closed, the `_closed` flag is set to True, causing all subsequent write
        operations (`record_*`) to be ignored. Read operations (`list_*`) remain valid.
        """
        async with self._lock:
            self._closed = True

    @property
    def events(self) -> tuple[PersistedEvent, ...]:
        """
        Retrieve a read-only snapshot of all recorded lifecycle events.

        This property returns the internal list of events as a tuple to prevent external modification.
        It is useful for assertions in tests or for inspecting the history of the system after a
        workload has completed.

        Returns
        -------
        tuple[PersistedEvent, ...]
            A chronological sequence of persisted event records.
        """
        return tuple(self._events)

    @property
    def audits(self) -> tuple[PersistedAudit, ...]:
        """
        Retrieve a read-only snapshot of all recorded system audits.

        Returns
        -------
        tuple[PersistedAudit, ...]
            A chronological sequence of persisted audit reports.
        """
        return tuple(self._audits)

    @property
    def dead_letters(self) -> tuple[PersistedDeadLetter, ...]:
        """
        Retrieve a read-only snapshot of all recorded dead letters.

        Returns
        -------
        tuple[PersistedDeadLetter, ...]
            A chronological sequence of persisted dead letter records.
        """
        return tuple(self._dead_letters)

    @property
    def closed(self) -> bool:
        """
        Check if the backend is currently closed.

        Returns
        -------
        bool
            True if `aclose()` has been called, False otherwise.
        """
        return self._closed

    async def compact(self) -> dict[str, Any]:
        """
        No-op compaction for in-memory persistence.

        In-memory persistence has no physical storage, so compaction does not
        remove data or reclaim space. This method exists to satisfy the
        persistence lifecycle contract and to allow uniform orchestration
        across backends.
        """
        await self._metrics_on_compact_start()
        async with self._lock:
            return {
                "backend": "memory",
                "before_records": (len(self._events) + len(self._audits) + len(self._dead_letters)),
                "after_records": (len(self._events) + len(self._audits) + len(self._dead_letters)),
                "before_bytes": None,
                "after_bytes": None,
            }

    async def scan(self) -> PersistenceScanReport:
        """
        In-memory persistence has no startup anomalies.
        """
        await self._metrics_on_scan_start()
        report = PersistenceScanReport(
            backend="memory",
            anomalies=(),
        )
        return report

    async def recover(self, config: Any = None) -> PersistenceRecoveryReport:
        await self._metrics_on_recover_start()
        scan = PersistenceScanReport(backend="memory", anomalies=())
        return PersistenceRecoveryReport(backend="memory", scan=scan)
