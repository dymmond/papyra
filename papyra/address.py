from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActorAddress:
    """
    Logical actor address.

    This is *not* a runtime pointer.
    It is a stable, serializable identity.
    """

    system: str
    actor_id: int

    def __str__(self) -> str:
        return f"{self.system}:{self.actor_id}"

    @classmethod
    def parse(cls, raw: str) -> "ActorAddress":
        """
        Parse an address string in the format: "<system>:<actor_id>".

        Raises
        ------
        ValueError
            If the format is invalid.
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
        return {"system": self.system, "actor_id": self.actor_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorAddress":
        return cls(system=str(data["system"]), actor_id=int(data["actor_id"]))
