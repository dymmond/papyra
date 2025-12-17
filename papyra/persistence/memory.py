from __future__ import annotations

from dataclasses import dataclass, field

import anyio
import anyio.abc

from .models import PersistedAudit, PersistedDeadLetter, PersistedEvent


@dataclass(slots=True)
class InMemoryPersistence:
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

    _lock: anyio.abc.Lock = field(default_factory=anyio.Lock)

    _events: list[PersistedEvent] = field(default_factory=list)
    _audits: list[PersistedAudit] = field(default_factory=list)
    _dead_letters: list[PersistedDeadLetter] = field(default_factory=list)

    _closed: bool = False

    async def record_event(self, event: PersistedEvent) -> None:
        """
        Asynchronously append a lifecycle event record to the internal store.

        This operation is guarded by a lock to ensure thread safety. If the backend is closed,
        the event is silently discarded to prevent errors during system shutdown.

        Parameters
        ----------
        event : PersistedEvent
            The immutable event record to store.
        """
        async with self._lock:
            if self._closed:
                return
            self._events.append(event)

    async def record_audit(self, audit: PersistedAudit) -> None:
        """
        Asynchronously append an audit snapshot record to the internal store.

        Parameters
        ----------
        audit : PersistedAudit
            The immutable audit snapshot to store.
        """
        async with self._lock:
            if self._closed:
                return
            self._audits.append(audit)

    async def record_dead_letter(self, dead_letter: PersistedDeadLetter) -> None:
        """
        Asynchronously append a dead-letter record to the internal store.

        Parameters
        ----------
        dead_letter : PersistedDeadLetter
            The immutable dead letter record to store.
        """
        async with self._lock:
            if self._closed:
                return
            self._dead_letters.append(dead_letter)

    async def list_events(self) -> tuple[PersistedEvent, ...]:
        """
        Retrieve a snapshot of all stored lifecycle events.

        Returns
        -------
        tuple[PersistedEvent, ...]
            A tuple containing the events in the order they were recorded. A tuple is returned
            to prevent external modification of the internal list.
        """
        async with self._lock:
            return tuple(self._events)

    async def list_audits(self) -> tuple[PersistedAudit, ...]:
        """
        Retrieve a snapshot of all stored audit reports.

        Returns
        -------
        tuple[PersistedAudit, ...]
            A tuple containing the audit records.
        """
        async with self._lock:
            return tuple(self._audits)

    async def list_dead_letters(self) -> tuple[PersistedDeadLetter, ...]:
        """
        Retrieve a snapshot of all stored dead letters.

        Returns
        -------
        tuple[PersistedDeadLetter, ...]
            A tuple containing the dead letter records.
        """
        async with self._lock:
            return tuple(self._dead_letters)

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
    def closed(self) -> bool:
        """
        Check if the backend is currently closed.

        Returns
        -------
        bool
            True if `aclose()` has been called, False otherwise.
        """
        return self._closed
