from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any, Callable

from ravyn import get

from papyra.contrib.asgi.endpoints import healthz as asgi_health, metrics as asgi_metrics
from papyra.contrib.asgi.lifesycle import papyra_lifecycle
from papyra.contrib.asgi.types import PapyraASGIConfig
from papyra.system import ActorSystem


@dataclass(slots=True)
class RavynPapyra:
    """
    Small integration helper for Ravyn

    It is possible to use:
        - Use `lifespan()`.
        - Call `install(app, ... )` to register startup/shutdown events + routes.
    """

    system_factory: Callable[[], ActorSystem]
    config: PapyraASGIConfig = PapyraASGIConfig()

    async def lifespan(self) -> Any:
        """
        Get a lifespan context manager for
        Ravyn applications.

        Returns:
            A context manager that manages the lifecycle of the ActorSystem.
        """
        return await papyra_lifecycle(  # type: ignore[misc]
            system_factory=self.system_factory,
            persistence_startup=self.config.persistence_startup,
            persistence_recovery=self.config.persistence_recovery,
        )

    def install(self, app: Any) -> None:
        """
        Install the Papyra lifecycle events into a Ravyn application.

        Args:
            app: The Ravyn application instance.
        """
        system = self.system_factory()

        async def _startup() -> None:
            if self.config.persistence_startup is not None:
                with contextlib.suppress(Exception):
                    system.persistence_startup = self.config.persistence_startup

            if self.config.persistence_recovery is not None:
                with contextlib.suppress(Exception):
                    await system.persistence.recover(self.config.persistence_recovery)

            await system.start()

        async def _shutdown() -> None:
            await system.aclose()

        if hasattr(app, "on_startup"):
            app.on_startup.append(_startup)
        if hasattr(app, "on_shutdown"):
            app.on_shutdown.append(_shutdown)

        @get()
        async def _health(scope: Any, receive: Any, send: Any) -> None:
            return await asgi_health(
                scope=scope,
                receive=receive,
                send=send,
                system=system,
                mode=self.config.health_mode,
                startup_config=self.config.persistence_startup,
            )

        @get()
        async def _metrics(scope: Any, receive: Any, send: Any) -> None:
            return await asgi_metrics(
                scope=scope,
                receive=receive,
                send=send,
                system=system,
                format=self.config.metrics_format,
            )

        # Add the routes to the app
        app.add_route(self.config.health_path, _health)
        app.add_route(self.config.metrics_path, _metrics)

        raise RuntimeError(
            "Could not auto-install Papyra endpoints into the Ravyn app. "
            "Include `healthz` and `metrics` ASGI callables manually."
        )
