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
from typing import Optional, TYPE_CHECKING, Any

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
        actor_factory: Any,
        *,
        mailbox_capacity: int | None = 1024,
        policy: "SupervisionPolicy | None" = None,
    ) -> "ActorRef":
        """
        Spawn a child actor under the current actor.
        """
        return self.system.spawn(
            actor_factory,
            mailbox_capacity=mailbox_capacity,
            policy=policy,
            parent=self.self_ref,
        )

    async def stop_self(self) -> None:
        """
        Request this actor to stop gracefully.

        Notes
        -----
        - This schedules a stop signal into the mailbox.
        - After stop is requested, further `tell/ask` via ActorRef will raise ActorStopped.
        - `on_stop()` is guaranteed to run once.
        """
        await self.system.stop(self.self_ref)

    async def stop(self, ref: "ActorRef") -> None:
        """
        Request another actor to stop gracefully.

        Typically used to stop children.

        Parameters
        ----------
        ref:
            ActorRef to stop.
        """
        await self.system.stop(ref)

    async def watch(self, ref: Any) -> None:
        """Receive ActorTerminated(ref) when the actor stops."""
        await self.system._add_watch(self.self_ref, ref)

    async def unwatch(self, ref: Any) -> None:
        """Stop watching an actor."""
        await self.system._remove_watch(self.self_ref, ref)
