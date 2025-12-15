from __future__ import annotations

from enum import Enum


class SupervisorDecision(str, Enum):
    """
    Possible decisions a supervisor can make when a child fails.

    RESTART
        Restart the child actor immediately.
    STOP
        Stop the child actor.
    ESCALATE
        Escalate the failure to the supervisor's parent.
    IGNORE
        Ignore the failure (child remains stopped).
    """

    RESTART = "restart"
    STOP = "stop"
    ESCALATE = "escalate"
    IGNORE = "ignore"
