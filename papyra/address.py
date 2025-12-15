from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActorAddress:
    """
    Represents the logical, location-independent identity of an actor.

    An `ActorAddress` serves as a stable, serializable reference to an actor within the distributed
    system. Unlike a runtime reference (which may be ephemeral or tied to a specific memory address),
    the address persists across network boundaries and system restarts (if configured).

    It follows a specific format consisting of a system identifier and a unique actor ID.

    Attributes
    ----------
    system : str
        The identifier of the actor system where this actor resides (e.g., "local", "sys-1").
    actor_id : int
        The unique integer identifier assigned to the actor within that system.
    """

    system: str
    actor_id: int

    def __str__(self) -> str:
        """
        Return the string representation of the address.

        Returns
        -------
        str
            The address formatted as "{system}:{actor_id}".
        """
        return f"{self.system}:{self.actor_id}"

    @classmethod
    def parse(cls, raw: str) -> ActorAddress:
        """
        Parse a raw string into an `ActorAddress` object.

        The expected format is "system_id:actor_id", where `system_id` is a non-empty string
        and `actor_id` is an integer.

        Parameters
        ----------
        raw : str
            The address string to parse.

        Returns
        -------
        ActorAddress
            The corresponding `ActorAddress` instance.

        Raises
        ------
        ValueError
            If the input string does not contain exactly one colon separator, if the system ID
            is empty, or if the actor ID cannot be converted to an integer.
        """
        if not isinstance(raw, str) or ":" not in raw:
            raise ValueError("Invalid address format. Expected '<system>:<actor_id>'.")

        system, actor_id_str = raw.split(":", 1)
        system = system.strip()
        actor_id_str = actor_id_str.strip()

        if not system:
            raise ValueError("Invalid address format. Missing system id.")

        try:
            actor_id = int(actor_id_str)
        except Exception as e:
            raise ValueError("Invalid address format. actor_id must be an int.") from e

        return cls(system=system, actor_id=actor_id)

    def to_dict(self) -> dict[str, object]:
        """
        Serialize the address to a dictionary.

        Useful for JSON serialization or transmitting the address over a network.

        Returns
        -------
        dict[str, object]
            A dictionary containing "system" and "actor_id".
        """
        return {"system": self.system, "actor_id": self.actor_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActorAddress:
        """
        Reconstruct an `ActorAddress` from a dictionary.

        Parameters
        ----------
        data : dict[str, Any]
            A dictionary containing keys "system" and "actor_id".

        Returns
        -------
        ActorAddress
            The reconstructed address instance.
        """
        return cls(system=str(data["system"]), actor_id=int(data["actor_id"]))
