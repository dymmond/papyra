from papyra.persistence.backends.memory import InMemoryPersistence

from .contract import (
    PersistenceBackendCapabilities,
    PersistenceBackendContract,
    backend_capabilities,
    safe_metrics_snapshot,
)
from .json import JsonFilePersistence

__all__ = [
    "InMemoryPersistence",
    "JsonFilePersistence",
    "PersistenceBackendCapabilities",
    "PersistenceBackendContract",
    "backend_capabilities",
    "safe_metrics_snapshot",
]

try:  # pragma: no cover
    from papyra.persistence.backends.redis import (
        RedisStreamsConfig,
        RedisStreamsPersistence,
    )

    __all__ += [
        "RedisStreamsConfig",
        "RedisStreamsPersistence",
    ]
except Exception:  # noqa
    ...
