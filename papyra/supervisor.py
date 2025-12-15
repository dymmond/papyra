from __future__ import annotations

from enum import Enum


class SupervisorDecision(str, Enum):
    """
    Defines the explicit set of directives a parent actor can return to determine the fate of a
    failed child.

    When a child actor raises an exception, the `on_child_failure` hook of the parent is invoked.
    The parent must return one of these decisions to instruct the actor system on how to resolve
    the failure state. This mechanism allows for fine-grained, context-aware error recovery
    strategies (e.g., restarting on network errors but stopping on configuration errors).

    Members
    -------
    RESTART
        Instructs the system to restart the child actor. The existing actor instance is
        discarded, and a new one is created using the original factory. The mailbox is
        preserved, so pending messages are processed by the new instance.
    STOP
        Instructs the system to permanently stop the child actor. The actor's lifecycle ends,
        resources are cleaned up, and no restart is attempted.
    ESCALATE
        Indicates that the parent cannot handle the failure. The failure is propagated upward,
        causing the parent itself to fail with the same exception, deferring the decision to
        the grandparent.
    IGNORE
        Instructs the system to take no specific supervision action. Depending on the implementation,
        this typically results in the child remaining in its failed (stopped) state without triggering
        further recovery logic.
    """

    RESTART = "restart"
    STOP = "stop"
    ESCALATE = "escalate"
    IGNORE = "ignore"
