from __future__ import annotations

from dataclasses import dataclass

from .address import ActorAddress


@dataclass(frozen=True, slots=True)
class ActorInfo:
    """
    A read-only, point-in-time snapshot of an actor's runtime state.

    This data structure is primarily intended for debugging, testing, and system inspection tools.
    It exposes internal details about the actor's lifecycle and hierarchy without granting access
    to the mutable runtime itself.

    Attributes
    ----------
    rid : int
        The unique runtime identifier for the actor instance.
    address : ActorAddress
        The logical address associated with the actor.
    name : str | None
        The symbolic name registered for this actor, if any.
    parent_rid : int | None
        The runtime ID of the parent actor. None if this is a root actor.
    children_rids : tuple[int, ...]
        A tuple containing the runtime IDs of all direct children currently supervised by this
        actor.
    alive : bool
        True if the actor is currently running and processing messages; False otherwise.
    stopping : bool
        True if the actor is in the process of shutting down (gracefully or forcefully).
    restarting : bool
        True if the actor is currently undergoing a restart procedure (e.g., due to a failure).
    """

    rid: int
    address: ActorAddress
    name: str | None

    parent_rid: int | None
    children_rids: tuple[int, ...]

    alive: bool
    stopping: bool
    restarting: bool


@dataclass(frozen=True, slots=True)
class AuditReport:
    """
    A comprehensive report detailing the global state and health of the ActorSystem.

    This report captures aggregate statistics, invariant violations (such as registry inconsistencies),
    and optionally a detailed list of all actor snapshots. It is useful for diagnosing leaks,
    verifying shutdown sequences, or monitoring system load.

    Attributes
    ----------
    system_id : str
        The unique identifier of the actor system being audited.
    total_actors : int
        The total number of actor runtimes currently tracked by the system.
    alive_actors : int
        The count of actors that are currently alive.
    stopping_actors : int
        The count of actors currently in the stopping state.
    restarting_actors : int
        The count of actors currently restarting.
    registry_size : int
        The number of entries in the name registry.
    registry_orphans : tuple[str, ...]
        A list of registered names that point to an address for which no corresponding runtime
        exists (e.g., the actor was removed but the name wasn't).
    registry_dead : tuple[str, ...]
        A list of registered names that point to an actor runtime that is dead (not alive and
        not restarting).
    dead_letters_count : int
        The total number of messages accumulated in the dead letter mailbox.
    actors : tuple[ActorInfo, ...]
        A tuple containing snapshots of all individual actors in the system. Defaults to an
        empty tuple.
    """

    system_id: str
    total_actors: int
    alive_actors: int
    stopping_actors: int
    restarting_actors: int

    registry_size: int
    registry_orphans: tuple[str, ...]
    registry_dead: tuple[str, ...]

    dead_letters_count: int

    actors: tuple[ActorInfo, ...] = ()

    def summary_lines(self) -> tuple[str, ...]:
        """
        Generate a human-readable summary of the audit report.

        Returns
        -------
        tuple[str, ...]
            A sequence of formatted strings summarizing system health, actor counts, registry
            status, and dead letters.
        """
        return (
            f"system_id={self.system_id}",
            f"actors(total={self.total_actors}, alive={self.alive_actors}, stopping={self.stopping_actors}, restarting={self.restarting_actors})",
            f"registry(size={self.registry_size}, orphans={len(self.registry_orphans)}, dead={len(self.registry_dead)})",
            f"dead_letters={self.dead_letters_count}",
        )
