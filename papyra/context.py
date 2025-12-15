from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .ref import ActorRef
    from .supervision import SupervisionPolicy
    from .system import ActorSystem


@dataclass(frozen=True, slots=True)
class ActorContext:
    """
    The runtime context injected into every actor instance.

    This class serves as the bridge between the user-defined `Actor` logic and the underlying
    `ActorSystem`. It provides the capabilities necessary for an actor to interact with its
    environment, such as spawning child actors, stopping itself or others, and setting up
    lifecycle monitors (watchers).

    The context is immutable and unique to each actor instance. It is automatically created
    by the system when an actor is spawned.

    Attributes
    ----------
    system : ActorSystem
        The `ActorSystem` instance that owns and manages this actor. This provides access to
        global system facilities.
    self_ref : ActorRef
        The canonical `ActorRef` pointing to this actor. This reference remains stable across
        restarts (if the actor fails and is recreated) and should be used when passing "self"
        to other actors.
    parent : ActorRef | None
        The `ActorRef` of the actor that spawned this instance. If this actor is a root actor
        (spawned directly from the system), this will be `None`. Defaults to None.
    """

    system: ActorSystem
    self_ref: ActorRef
    parent: ActorRef | None = None

    def spawn_child(
        self,
        actor_factory: Any,
        *,
        mailbox_capacity: int | None = 1024,
        policy: SupervisionPolicy | None = None,
    ) -> ActorRef:
        """
        Spawn a new actor as a direct child of the current actor.

        This method registers the new actor in the supervision tree strictly below the current
        actor. If the child fails, the current actor's `on_child_failure` hook will be invoked
        to decide the strategy.

        Parameters
        ----------
        actor_factory : Any
            A callable (function or class) that returns a new instance of an `Actor`.
        mailbox_capacity : int | None, optional
            The maximum number of messages the child's mailbox can hold before blocking senders.
            If None, the mailbox is unbounded. Defaults to 1024.
        policy : SupervisionPolicy | None, optional
            The supervision policy defining how the child should handle failures. If None,
            it uses the system default (typically stopping on failure). Defaults to None.

        Returns
        -------
        ActorRef
            A reference to the newly created child actor.
        """
        return self.system.spawn(
            actor_factory,
            mailbox_capacity=mailbox_capacity,
            policy=policy,
            parent=self.self_ref,
        )

    async def stop_self(self) -> None:
        """
        Request the current actor to stop gracefully.

        This method is the preferred way for an actor to terminate its own lifecycle. It operates
        asynchronously by sending a specialized internal signal (STOP) to the actor's own
        mailbox.

        Notes
        -----
        - The stop signal is processed in order with other messages.
        - Once the stop sequence begins, the actor's `on_stop` hook is guaranteed to execute.
        - Any subsequent attempts to send messages to this actor via `ActorRef` will raise
          `ActorStopped`.
        """
        await self.system.stop(self.self_ref)

    async def stop(self, ref: ActorRef) -> None:
        """
        Request another actor to stop gracefully.

        While an actor can request any other actor to stop, this is most commonly used by a
        parent to terminate specific children when they are no longer needed.

        Parameters
        ----------
        ref : ActorRef
            The reference to the target actor that should be stopped.
        """
        await self.system.stop(ref)

    async def watch(self, ref: Any) -> None:
        """
        Register a monitor on another actor to detect its termination.

        When the target actor stops (whether gracefully or due to failure), the system will
        send an `ActorTerminated` message to the current actor's mailbox.

        Parameters
        ----------
        ref : Any
            The reference of the actor to watch. Typed as `Any` to allow flexible reference
            types, but usually expects an `ActorRef`.
        """
        await self.system._add_watch(self.self_ref, ref)

    async def unwatch(self, ref: Any) -> None:
        """
        Unregister a previously established monitor on an actor.

        After calling this, the current actor will no longer receive `ActorTerminated` messages
        regarding the target actor.

        Parameters
        ----------
        ref : Any
            The reference of the actor to stop watching.
        """
        await self.system._remove_watch(self.self_ref, ref)
