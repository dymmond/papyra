from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from papyra.persistence.models import PersistenceRecoveryConfig
from papyra.persistence.startup import PersistenceStartupConfig
from papyra.system import ActorSystem


class ActorSystemFactory(Protocol):
    def __call__(self) -> ActorSystem: ...


JsonDict = dict[str, Any]


@dataclass(frozen=True)
class PapyraASGIConfig:
    """
    Configuration for ASGI integration.

    This can be used for ANY ASGI framework (Lilya, FastAPI, Starlette, Litestar, etc.).
    """

    health_path: str = "/healthz"
    metrics_path: str = "/metrics"

    health_mode: str = "scan"

    persistence_startup: PersistenceStartupConfig | None = None
    persistence_recovery: PersistenceRecoveryConfig | None = None

    metrics_format: str = "json"
