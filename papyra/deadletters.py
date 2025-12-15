from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class DeadLetter:
    """
    A message sent to an actor that was no longer running.

    This is for diagnostics and observability only.
    """

    ref: Any
    message: Any
    kind: Literal["tell", "ask"]
    when: float
