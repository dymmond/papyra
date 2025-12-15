from __future__ import annotations

"""
Supervisor callback primitives.

This module defines the contract between a failing child actor and its parent
(supervisor).

The parent may override the default supervision policy by implementing
`on_child_failure(...)`.
"""

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
