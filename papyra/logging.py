from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Annotated, Any, cast

from typing_extensions import Doc

from papyra.protocols.logging import LoggerProtocol


class LoggerProxy:
    """
    A thread-safe proxy that defers access to the actual logger implementation until it is
    configured.

    This proxy allows the global `logger` variable to be imported and used at the module level
    throughout the codebase without worrying about import order or initialization timing. All
    attribute access (e.g., `logger.info`, `logger.error`) is intercepted and forwarded to the
    underlying `LoggerProtocol` instance once it is bound.

    Key Features
    ------------
    - **Lazy Initialization**: The actual logger can be set up late in the application startup
      sequence.
    - **Auto-Configuration**: If accessed before explicit binding, it triggers a default logging
      setup to ensure no messages are lost.
    - **Thread Safety**: Uses a reentrant lock to ensure the logger swap is atomic.

    Attributes
    ----------
    _logger : LoggerProtocol | None
        The actual logger instance. This is `None` until `bind_logger` is called.
    _lock : threading.RLock
        A reentrant lock used to synchronize access when binding the logger or lazy-loading
        defaults.
    """

    def __init__(self) -> None:
        """
        Initialize the proxy with no bound logger.
        """
        self._logger: LoggerProtocol | None = None
        self._lock: threading.RLock = threading.RLock()

    def bind_logger(self, logger: LoggerProtocol | None) -> None:
        """
        Bind a concrete logger implementation to this proxy.

        Once bound, all subsequent calls to the proxy will be forwarded to this instance.
        This operation is thread-safe.

        Parameters
        ----------
        logger : LoggerProtocol | None
            The configured logger instance to use. If None is passed, the proxy is effectively
            reset (though usually this receives a valid logger).
        """
        with self._lock:
            self._logger = logger

    def __getattr__(self, item: str) -> Any:
        """
        Intercept attribute access to forward calls to the underlying logger.

        If the logger has not yet been bound, this method automatically triggers `setup_logging`
        with default settings to prevent runtime errors during early application execution.

        Parameters
        ----------
        item : str
            The name of the attribute or method being accessed (e.g., "info", "debug").

        Returns
        -------
        Any
            The corresponding attribute from the bound logger instance.

        Raises
        ------
        RuntimeError
            Implicitly, if `setup_logging` fails to bind a logger for some reason, though the
            auto-setup logic attempts to prevent this.
        """
        if not self._logger:
            with self._lock:
                if not self._logger:
                    setup_logging()
        return getattr(self._logger, item)


# Global logger instance used throughout the application.
logger: LoggerProtocol = cast(LoggerProtocol, LoggerProxy())


class LoggingConfig(ABC):
    """
    Abstract base class for defining logging configurations.

    This class serves as a contract for different logging backends (e.g., standard `logging`,
    `loguru`, `structlog`). Subclasses must implement the logic to configure the backend and
    retrieve the root logger instance.

    Attributes
    ----------
    __logging_levels__ : list[str]
        A list of valid standard logging level names (uppercase).
    level : str
        The active logging level (e.g., "DEBUG", "INFO") used for configuration.
    options : dict[str, Any]
        Arbitrary additional configuration options passed during initialization.
    skip_setup_configure : bool
        Flag indicating if the `configure()` step should be skipped (e.g., if the environment
        is already configured externally).
    name : str
        The name of the logger to configure. Defaults to "papyra".
    """

    __logging_levels__: list[str] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(
        self,
        level: Annotated[
            str,
            Doc(
                """
                The minimum logging level to capture. Must be one of the values in
                `__logging_levels__` (case-insensitive). Defaults to "DEBUG".
                """
            ),
        ] = "DEBUG",
        **kwargs: Any,
    ) -> None:
        """
        Initialize the logging configuration.

        Parameters
        ----------
        level : str, optional
            The desired logging level. Defaults to "DEBUG".
        **kwargs : Any
            Additional options to be stored in `self.options`.

        Raises
        ------
        AssertionError
            If the provided `level` is not a valid logging level.
        """
        levels: str = ", ".join(self.__logging_levels__)
        assert (
            level.upper() in self.__logging_levels__
        ), f"'{level}' is not a valid logging level. Available levels: '{levels}'."

        self.level = level.upper()
        self.options = kwargs
        self.skip_setup_configure: bool = kwargs.get("skip_setup_configure", False)
        self.name = kwargs.get("name", "papyra")

    @abstractmethod
    def configure(self) -> None:
        """
        Apply the side effects required to configure the logging backend.

        This might involve setting up formatters, adding handlers to the root logger, or
        configuring third-party libraries.
        """
        raise NotImplementedError("`configure()` must be implemented in subclasses.")

    @abstractmethod
    def get_logger(self) -> Any:
        """
        Retrieve the configured logger instance.

        Returns
        -------
        Any
            The logger object that adheres to the `LoggerProtocol`.
        """
        raise NotImplementedError("`get_logger()` must be implemented in subclasses.")


def setup_logging(logging_config: LoggingConfig | None = None) -> None:
    """
    Initialize and bind the global logging system.

    This function serves as the entry point for configuring application-wide logging.
    It performs three main steps:
    1. Selects a configuration strategy (either the provided one or a default standard one).
    2. Executes the configuration logic (unless skipped).
    3. Binds the resulting logger to the global `logger` proxy, enabling logging across the app.

    Parameters
    ----------
    logging_config : LoggingConfig | None, optional
        A custom configuration instance. If None, `StandardLoggingConfig` is used with default
        settings. Defaults to None.

    Raises
    ------
    ValueError
        If the provided `logging_config` is not an instance of the `LoggingConfig` class.
    """
    from papyra.utils.logging import StandardLoggingConfig

    if logging_config is not None and not isinstance(logging_config, LoggingConfig):
        raise ValueError("`logging_config` must be an instance of LoggingConfig.")

    config = logging_config or StandardLoggingConfig()

    if not config.skip_setup_configure:
        config.configure()

    _logger = config.get_logger()
    logger.bind_logger(_logger)
