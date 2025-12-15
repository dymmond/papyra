from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .context import ActorContext
from .supervisor import SupervisorDecision

if TYPE_CHECKING:
    from .ref import ActorRef


class Actor:
    """
    The base class for all actors in the system.

    An actor is the fundamental unit of computation, encapsulating state and behavior. Actors
    communicate exclusively by exchanging messages. Each actor runs essentially single-threaded,
    processing messages one at a time from its mailbox, which ensures thread safety for internal
    state without the need for locks.

    Lifecycle
    ---------
    1. `on_start()`: Invoked immediately after the actor is spawned and before it begins
       processing any messages.
    2. `receive(message)`: Invoked repeatedly for every message delivered to the actor's
       mailbox.
    3. `on_stop()`: Invoked when the actor is shutting down, either gracefully or due to a
       failure (if the supervision policy dictates a stop).

    Context
    -------
    The runtime automatically injects an `ActorContext` instance into the actor. This context
    provides access to essential metadata, such as the actor's own reference (`self_ref`), its
    parent, and the underlying system. It is accessible via the `self.context` property.

    Attributes
    ----------
    _context : ActorContext | None
        Internal storage for the injected runtime context. Initialized to None and populated by
        the system upon spawn.
    """

    _context: ActorContext | None = None

    @property
    def context(self) -> ActorContext:
        """
        Retrieve the runtime context for this actor.

        The context provides access to the actor's identity (reference), its parent, and the
        actor system it belongs to. It is the primary mechanism for an actor to interact with
        its environment (e.g., spawning children, getting system time).

        Returns
        -------
        ActorContext
            The active context object for this actor instance.

        Raises
        ------
        RuntimeError
            If this property is accessed before the actor has been fully initialized by the
            system. This typically happens if `self.context` is accessed inside `__init__`
            instead of `on_start`.
        """
        if self._context is None:
            raise RuntimeError(
                "ActorContext is not available yet. "
                "Access `self.context` from on_start/receive/on_stop."
            )
        return self._context

    async def on_start(self) -> None:
        """
        Asynchronous hook called immediately after the actor is started.

        This method is the designated place for initialization logic that requires asynchronous
        operations or access to `self.context` (which is not available in `__init__`). Common
        use cases include:
        - Establishing database connections or network sockets.
        - Allocating heavy resources.
        - Sending initial messages to other actors.
        - Scheduling periodic tasks.

        Returns
        -------
        None
        """
        return None

    async def on_stop(self) -> None:
        """
        Asynchronous hook called when the actor is stopping.

        The system guarantees that this method is called exactly once when the actor terminates,
        regardless of whether the termination was voluntary (graceful stop) or due to a crash
        (failure), provided the process itself does not crash hard.

        Override this method to perform necessary cleanup, such as:
        - Closing open files, sockets, or connections.
        - Cancelling pending background tasks.
        - Releasing external resources.
        - Flushing buffers or saving final state.

        Returns
        -------
        None
        """
        return None

    async def receive(self, message: Any) -> Any | None:
        """
        The main message handling loop.

        This method is invoked for every message retrieved from the actor's mailbox. It contains
        the core business logic of the actor.

        Parameters
        ----------
        message : Any
            The user-defined message payload sent to this actor.

        Returns
        -------
        Any | None
            If the message was sent using the request-response pattern (`ask`), the value
            returned here is sent back to the caller as the reply. If the message was sent
            using fire-and-forget (`tell`), the return value is ignored.

        Raises
        ------
        NotImplementedError
            If the subclass does not implement this method.
        """
        raise NotImplementedError("Actors must implement receive(...)")

    async def on_child_failure(
        self,
        child_ref: ActorRef,
        exc: BaseException,
    ) -> SupervisorDecision | None:
        """
        Hook called when a child actor fails with an exception.

        This method allows a parent actor to define custom supervision logic for its children.
        By returning a `SupervisorDecision`, the parent can override the child's default
        supervision policy for the specific failure encountered.

        Parameters
        ----------
        child_ref : ActorRef
            The reference to the child actor that failed.
        exc : BaseException
            The exception that caused the child to fail.

        Returns
        -------
        SupervisorDecision | None
            A decision instruction (STOP, RESTART, ESCALATE, IGNORE) telling the system how to
            handle the failure. If `None` is returned, the system falls back to the supervision
            policy defined on the child actor itself.
        """
        return None
