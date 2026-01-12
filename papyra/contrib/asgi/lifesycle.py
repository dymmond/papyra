from __future__ import annotations

import contextlib
from typing import AsyncIterator, Callable

from papyra.persistence.models import PersistenceRecoveryConfig
from papyra.persistence.startup import PersistenceStartupConfig
from papyra.system import ActorSystem


async def _best_effort_recover(system: ActorSystem, config: PersistenceRecoveryConfig) -> None:
    """
    Attempt to recover the actor system's state from persistence, ignoring any errors.

    Args:
        system: The actor system to recover.
        config: The persistence recovery configuration.
    """
    with contextlib.suppress(Exception):
        await system.persistence.recover(config)


async def _best_effort_startup(system: ActorSystem, config: PersistenceStartupConfig) -> None:
    """
    Attempt to start up the actor system's state from persistence, ignoring any errors.

    Args:
        system: The actor system to start up.
        config: The persistence startup configuration.
    """
    with contextlib.suppress(Exception):
        system.persistence_startup = config


@contextlib.asynccontextmanager
async def papyra_lifecycle(
    system_factory: Callable[[], ActorSystem],
    *,
    persistence_startup: PersistenceStartupConfig | None = None,
    persistence_recovery: PersistenceRecoveryConfig | None = None,
) -> AsyncIterator[ActorSystem]:
    """
    ASGI lifespan context manager for managing the lifecycle of a Papyra actor system.

    This context manager initializes the actor system on startup and gracefully shuts it down on exit.
    It also handles optional persistence startup and recovery.

    Args:
        system_factory: A callable that returns an instance of ActorSystem.
        persistence_startup: Optional configuration for persistence startup.
        persistence_recovery: Optional configuration for persistence recovery.
        Yields:  An instance of ActorSystem.
    """
    system = system_factory()

    if persistence_startup is not None:
        await _best_effort_startup(system, persistence_startup)

    if persistence_recovery is not None:
        await _best_effort_recover(system, persistence_recovery)

    await system.start()

    try:
        yield system
    finally:
        with contextlib.suppress(Exception):
            await system.aclose()
