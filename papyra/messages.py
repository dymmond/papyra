from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AttrPath = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProxyCall:
    """
    Message asking an actor to call a method in its own actor loop.
    """

    attr_path: AttrPath
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ProxyGetAttr:
    """
    Message asking an actor to read an attribute in its own actor loop.
    """

    attr_path: AttrPath


@dataclass(frozen=True, slots=True)
class ProxySetAttr:
    """
    Message asking an actor to set an attribute in its own actor loop.
    """

    attr_path: AttrPath
    value: Any
