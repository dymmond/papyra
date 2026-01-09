from .contract import (
    PersistenceBackendCapabilities,
    PersistenceBackendContract,
    backend_capabilities,
    safe_metrics_snapshot,
)
from .json import JsonFilePersistence
from .memory import InMemoryPersistence

__all__ = [
    "InMemoryPersistence",
    "JsonFilePersistence",
    "PersistenceBackendCapabilities",
    "PersistenceBackendContract",
    "backend_capabilities",
    "safe_metrics_snapshot",
]

try:  # pragma: no cover
    from .redis import RedisStreamsConfig, RedisStreamsPersistence  # noqa: F401

    __all__ += [
        "RedisStreamsConfig",
        "RedisStreamsPersistence",
    ]
except Exception:  # noqa
    ...
