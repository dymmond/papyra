from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .messages import AttrPath, ProxyCall, ProxyGetAttr, ProxySetAttr

if TYPE_CHECKING:
    from .ref import ActorRef


def _join_attr_path(attr_path: AttrPath) -> str:
    return ".".join(attr_path)


def _validate_attr_path(attr_path: AttrPath) -> None:
    for name in attr_path:
        if name.startswith("_"):
            raise AttributeError(f"ActorProxy does not expose private attribute {_join_attr_path(attr_path)!r}")


@dataclass(frozen=True, slots=True)
class ActorProxy:
    """
    Async method-and-attribute proxy for an actor reference.

    Method calls use ``ask`` semantics and should be awaited. Attribute access returns a
    ``ProxyAccessor`` that can be awaited for reads or used with ``set`` for writes.
    """

    actor_ref: ActorRef

    def __getattr__(self, name: str) -> ProxyAccessor:
        attr_path = (name,)
        _validate_attr_path(attr_path)
        return ProxyAccessor(actor_ref=self.actor_ref, attr_path=attr_path)


@dataclass(frozen=True, slots=True)
class ProxyAccessor:
    """
    Proxy for one actor attribute path.
    """

    actor_ref: ActorRef
    attr_path: AttrPath

    def __getattr__(self, name: str) -> ProxyAccessor:
        attr_path = (*self.attr_path, name)
        _validate_attr_path(attr_path)
        return ProxyAccessor(actor_ref=self.actor_ref, attr_path=attr_path)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Call the target actor method with request/reply semantics.
        """
        _validate_attr_path(self.attr_path)
        return self.actor_ref.ask(
            ProxyCall(
                attr_path=self.attr_path,
                args=args,
                kwargs=dict(kwargs),
            )
        )

    async def defer(self, *args: Any, **kwargs: Any) -> None:
        """
        Call the target actor method with fire-and-forget semantics.
        """
        _validate_attr_path(self.attr_path)
        await self.actor_ref.tell(
            ProxyCall(
                attr_path=self.attr_path,
                args=args,
                kwargs=dict(kwargs),
            )
        )

    async def get(self) -> Any:
        """
        Read the target actor attribute with request/reply semantics.
        """
        _validate_attr_path(self.attr_path)
        return await self.actor_ref.ask(ProxyGetAttr(attr_path=self.attr_path))

    async def set(self, value: Any) -> None:
        """
        Set the target actor attribute with request/reply semantics.
        """
        _validate_attr_path(self.attr_path)
        await self.actor_ref.ask(ProxySetAttr(attr_path=self.attr_path, value=value))

    def __await__(self) -> Any:
        return self.get().__await__()
