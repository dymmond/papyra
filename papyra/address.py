from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActorAddress:
    """
    Logical actor address.

    This is *not* a runtime pointer.
    It is a stable, serializable identity.

    Phase 11:
    - Can be serialized
    - Can be reconstructed
    - Transport-agnostic
    """

    system: str
    actor_id: int

    def __str__(self) -> str:
        return f"{self.system}:{self.actor_id}"

    @classmethod
    def parse(cls, value: str) -> "ActorAddress":
        system, raw_id = value.split(":", 1)
        return cls(system=system, actor_id=int(raw_id))

    def to_dict(self) -> dict[str, object]:
        return {"system": self.system, "actor_id": self.actor_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorAddress":
        return cls(system=str(data["system"]), actor_id=int(data["actor_id"]))
