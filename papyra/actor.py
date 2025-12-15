from __future__ import annotations

"""
Actor base class for Papyra.

An actor encapsulates state and behavior. It processes messages sequentially and
communicates exclusively by exchanging messages (via ActorRef).

User code should subclass `Actor` and implement `receive(...)`.

Example
-------
class Counter(Actor):
    def __init__(self) -> None:
        self.value = 0

    async def receive(self, message: object) -> object | None:
        if message == "inc":
            self.value += 1
        elif message == "get":
            return self.value
"""

from typing import Any, Optional

from .context import ActorContext
from .supervisor import SupervisorDecision


class Actor:
    """
    Base class for actors.

    Lifecycle
    ---------
    - `on_start()` is called once before the first message is processed.
    - `receive(message)` is called for each incoming message.
    - `on_stop()` is called once when the actor stops (normal or failure).

    Context
    -------
    The runtime injects an ActorContext which is accessible via `self.context`.

    Notes
    -----
    Hooks are optional. Subclasses may override them.
    """
    _context: ActorContext | None = None

    @property
    def context(self) -> ActorContext:
        """
        Actor runtime context.

        Raises
        ------
        RuntimeError
            If accessed before the runtime has started the actor.
        """
        if self._context is None:
            raise RuntimeError(
                "ActorContext is not available yet. "
                "Access `self.context` from on_start/receive/on_stop."
            )
        return self._context

    async def on_start(self) -> None:
        """
        Called once before the actor starts processing messages.

        Override this method to perform initialization logic such as:
        - opening connections
        - allocating resources
        """
        return None

    async def receive(self, message: Any) -> Optional[Any]:
        """
        Handle a message.

        Parameters
        ----------
        message:
            An arbitrary user-defined message.

        Returns
        -------
        Optional[Any]
            A value for request/reply (`ask`). Ignored for `tell`.
        """
        raise NotImplementedError("Actors must implement receive(...)")

    async def on_stop(self) -> None:
        """
        Called once when the actor stops.

        This method is guaranteed to be called exactly once, even if
        `receive(...)` raises an exception.

        Override this method to:
        - release resources
        - flush state
        - perform cleanup
        """
        return None

    async def on_child_failure(
        self,
        child_ref,
        exc: BaseException,
    ) -> SupervisorDecision | None:
        """
        Called when a child actor fails.

        Return a SupervisorDecision to override the child's supervision policy.
        Return None to defer to the child's SupervisionPolicy.

        Default behaviour: do nothing.
        """
        return None
