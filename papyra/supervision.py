from __future__ import annotations
"""
Supervision primitives for Papyra.

Supervision is the mechanism by which actor failures are handled.

In actor systems inspired by Erlang/Akka, actors do not "catch everything"
everywhere. Instead, failures are explicit, isolated, and handled by a supervisor.

This module defines:
- the restart strategy enum
- the supervision policy (limits, time windows)
"""

from dataclasses import dataclass
from enum import Enum


class Strategy(str, Enum):
    """
    Failure handling strategies for a supervised actor.

    STOP
        Stop the actor when it fails.
    RESTART
        Restart the actor when it fails (recreate instance using the original factory).
    ESCALATE
        Propagate the failure to the parent supervisor. If there is no parent,
        the default behavior is to STOP.
    """

    STOP = "stop"
    RESTART = "restart"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class SupervisionPolicy:
    """
    Defines how a supervisor handles child failures.

    Parameters
    ----------
    strategy:
        What to do on failure (STOP/RESTART/ESCALATE).
    max_restarts:
        Maximum number of restarts allowed within the `within_seconds` window.
        Only relevant for RESTART.
    within_seconds:
        Sliding window size (seconds) used for restart rate limiting.
        Only relevant for RESTART.
    """

    strategy: Strategy = Strategy.STOP
    max_restarts: int = 3
    within_seconds: float = 60.0
