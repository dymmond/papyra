from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Strategy(str, Enum):
    """
    Defines the available directives for handling actor failures within the supervision hierarchy.

    In the actor model, supervision delegates failure handling to the parent actor. This enum
    represents the set of standard choices a supervisor can make when a child actor crashes
    (raises an exception).

    Members
    -------
    STOP
        Instructs the system to permanently stop the failing actor. The actor's post-stop hooks
        will run, resources will be cleaned up, and the actor will not process any further
        messages.
    RESTART
        Instructs the system to restart the failing actor. This involves suspending the mailbox,
        stopping the current instance, creating a new instance via the factory, and resuming
        processing.
    ESCALATE
        Instructs the system to bubble the failure up to the parent of the current supervisor.
        This implies the current supervisor cannot handle the specific error.
    """

    STOP = "stop"
    RESTART = "restart"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class SupervisionPolicy:
    """
    Configuration object defining the rules for supervising a child actor.

    This policy determines how the system reacts when an actor raises an exception. It allows
    for defining simple behaviors (always stop) or resilient patterns (restart with limits to
    prevent infinite crash loops).

    Attributes
    ----------
    strategy : Strategy
        The primary action to take when a failure occurs (STOP, RESTART, or ESCALATE).
        Defaults to Strategy.STOP.
    max_restarts : int
        The maximum number of times an actor is allowed to restart within the time window
        defined by `within_seconds`. If this limit is exceeded, the strategy falls back to STOP
        to prevent infinite restart loops (thrashing). Defaults to 3.
    within_seconds : float
        The duration of the sliding window (in seconds) for tracking restart frequency.
        Defaults to 60.0.
    """

    strategy: Strategy = Strategy.STOP
    max_restarts: int = 3
    within_seconds: float = 60.0
