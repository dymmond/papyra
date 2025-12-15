from __future__ import annotations
"""
Actor context for Papyra.

Actors should not reach into the ActorSystem directly via globals or singletons.
Instead, the runtime injects an ActorContext into each actor instance.

This enables:
- accessing `self` ActorRef (address)
- accessing the parent ActorRef (if any)
- spawning children in a structured way
- (later) tracing, deadlines, cancellation, supervision signals, etc.

The context is intentionally minimal in Step 4.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .ref import ActorRef
    from .system import ActorSystem
    from .supervision import SupervisionPolicy


@dataclass(frozen=True, slots=True)
class ActorContext:
    """
    Runtime context injected into every actor.

    Attributes
    ----------
    system:
        The ActorSystem that owns this actor.
    self_ref:
        ActorRef pointing to this actor instance (stable across restarts).
    parent:
        ActorRef pointing to the parent actor, if any.
    """

    system: "ActorSystem"
    self_ref: "ActorRef"
    parent: Optional["ActorRef"] = None

    def spawn_child(
        self,
        actor_factory,
        *,
        mailbox_capacity: int | None = 1024,
        policy: "SupervisionPolicy | None" = None,
    ) -> "ActorRef":
        """
        Spawn a child actor under the current actor.

        Parameters
        ----------
        actor_factory:
            Actor type or zero-arg callable returning an Actor instance.
        mailbox_capacity:
            Mailbox buffer size for the child.
        policy:
            Supervision policy applied to the child.

        Returns
        -------
        ActorRef
            Reference to the spawned child actor.
        """
        return self.system.spawn(
            actor_factory,
            mailbox_capacity=mailbox_capacity,
            policy=policy,
            parent=self.self_ref,
        )
