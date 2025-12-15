from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

import anyio

from ._envelope import DeadLetter, Envelope
from .address import ActorAddress
from .exceptions import ActorStopped, AskTimeout


@dataclass(frozen=True, slots=True)
class ActorRef:
    """
    Reference to a running actor.

    Phase 11:
    - Carries a stable ActorAddress
    - Address is serializable and transport-ready
    """

    _rid: int
    _mailbox_put: Callable[[Envelope], Any]
    _is_alive: Callable[[], bool]
    _dead_letter: Callable[[DeadLetter], Any] | None = None
    _address: ActorAddress | None = None

    @property
    def address(self) -> ActorAddress:
        if self._address is None:
            raise RuntimeError("ActorRef has no address bound")
        return self._address

    async def tell(self, message: Any) -> None:
        if not self._is_alive():
            self._dead_letter_emit(message, expects_reply=False)
            raise ActorStopped("Actor is not running.")

        try:
            await self._mailbox_put(Envelope(message=message, reply=None))
        except Exception:
            raise ActorStopped("Actor is not running.") from None

    async def ask(self, message: Any, *, timeout: Optional[float] = None) -> Any:
        if not self._is_alive():
            self._dead_letter_emit(message, expects_reply=True)
            raise ActorStopped("Actor is not running.")

        send, recv = anyio.create_memory_object_stream(1)

        try:
            await self._mailbox_put(Envelope(message=message, reply=send))

            try:
                if timeout is not None:
                    with anyio.fail_after(timeout):
                        reply = await recv.receive()
                else:
                    reply = await recv.receive()
            except TimeoutError as e:
                raise AskTimeout(f"ask() timed out after {timeout} seconds.") from e

            if reply.error is not None:
                raise reply.error

            return reply.value
        finally:
            await send.aclose()
            await recv.aclose()

    def _dead_letter_emit(self, message: Any, *, expects_reply: bool) -> None:
        if self._dead_letter is None:
            return
        try:
            self._dead_letter(
                DeadLetter(
                    target=self,
                    message=message,
                    expects_reply=expects_reply,
                )
            )
        except Exception:
            return
