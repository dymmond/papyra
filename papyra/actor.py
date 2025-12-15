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


class Actor:
    """
    Base class for actors.

    Contract
    --------
    - Actors handle one message at a time (enforced by runtime).
    - `receive(...)` may mutate actor state.
    - `receive(...)` may return a value, which is used only by `ask(...)`.

    Notes
    -----
    We keep this class minimal. Lifecycle hooks (pre_start, post_stop, etc.)
    will be added later once supervision lands.
    """

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
