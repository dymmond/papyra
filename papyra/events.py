from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any

from .address import ActorAddress


def _to_plain(value: Any) -> Any:
    """
    Recursively convert an arbitrary object into a JSON-serializable primitive representation.

    This utility is used to prepare payload data for persistence (e.g., event logs or audits). It
    safeguards against serialization errors by ensuring that complex types—such as custom objects,
    exceptions, or dataclasses—are reduced to simple dictionaries, lists, or strings.

    Conversion Rules
    ----------------
    - **Primitives** (None, str, int, float, bool): Returned as-is.
    - **Exceptions**: Converted to a string format "ExceptionName: message".
    - **Collections** (list, tuple, set): Converted to a list of recursively processed items.
    - **Dictionaries**: Keys are coerced to strings; values are recursively processed.
    - **Dataclasses**: Converted to a dictionary of their fields (recursive).
    - **Others**: Fallback to the object's `repr()` string.

    Parameters
    ----------
    value : Any
        The input object to normalize.

    Returns
    -------
    Any
        A structure composed entirely of JSON-safe types (dict, list, str, int, float, bool, None).
    """
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, BaseException):
        return f"{type(value).__name__}: {value}"

    if isinstance(value, (list, tuple, set)):
        return [_to_plain(v) for v in value]

    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}

    if is_dataclass(value):
        return {f.name: _to_plain(getattr(value, f.name)) for f in fields(value)}

    return repr(value)


def _serialize_address(address: ActorAddress) -> dict[str, Any]:
    """
    Convert an `ActorAddress` instance into a plain dictionary suitable for serialization.

    This internal utility prepares the address for persistence or network transmission by
    stripping away the class wrapper and returning the raw identifying components. It ensures
    compatibility with storage backends that accept standard JSON-like structures.

    Parameters
    ----------
    address : ActorAddress
        The logical actor address to serialize.

    Returns
    -------
    dict[str, Any]
        A dictionary containing the keys "system" (str) and "actor_id" (int).
    """
    return {
        "system": address.system,
        "actor_id": address.actor_id,
    }


@dataclass(slots=True, frozen=True)
class ActorEvent:
    """
    Base class for all public lifecycle events emitted by the actor system.

    These events are typically used for observability, auditing, or by specialized "watcher"
    actors that monitor the health and status of the system.

    Attributes
    ----------
    address : dict[str, object]
        The logical address of the actor that generated this event.
    """

    address: dict[str, object]

    @property
    def payload(self) -> dict[str, object]:
        """
        Generate a serializable dictionary of the event's specific payload data.

        This property extracts all instance attributes (via `__dict__`) to form the event's
        contextual payload. It automatically excludes the `address` field, as the address is
        typically stored as a distinct top-level field in persistence models (e.g.,
        `PersistedEvent.actor_address`).

        The values are processed through an internal helper (`_to_plain`) to ensure they are
        safe for serialization (e.g., converting nested objects to primitives).

        Returns
        -------
        dict[str, object]
            A dictionary containing the event-specific data fields.
        """
        return {field.name: _to_plain(getattr(self, field.name)) for field in fields(self) if field.name != "address"}


@dataclass(slots=True, frozen=True)
class ActorStarted(ActorEvent):
    """
    Event emitted when an actor has successfully started.

    This event signifies that the actor's `on_start` hook has completed successfully and the
    actor is now ready to process messages from its mailbox.
    """

    ...


@dataclass(slots=True, frozen=True)
class ActorRestarted(ActorEvent):
    """
    Event emitted when an actor has been restarted by its supervisor.

    This occurs when an actor crashes (raises an exception) and the supervision policy dictates
    a restart. The actor's state is reset (re-initialized via factory), but it retains its
    mailbox and address.

    Attributes
    ----------
    reason : BaseException
        The exception that caused the previous instance of the actor to crash.
    """

    reason: BaseException | str


@dataclass(slots=True, frozen=True)
class ActorStopped(ActorEvent):
    """
    Event emitted when an actor has stopped permanently.

    This marks the end of the actor's lifecycle. It is emitted after the `on_stop` hook has
    executed (or attempted to execute). No further messages will be processed by this actor.

    Attributes
    ----------
    reason : str | None
        An optional human-readable explanation for why the actor stopped (e.g., "shutdown",
        "failure"). Defaults to None.
    """

    reason: str | None = None


@dataclass(slots=True, frozen=True)
class ActorCrashed(ActorEvent):
    """
    Event emitted when an actor fails with an unhandled exception.

    This event typically precedes an `ActorRestarted` or `ActorStopped` event, depending on the
    supervision decision. It serves as a direct alert that an error occurred within the actor's
    logic.

    Attributes
    ----------
    error : BaseException
        The exception raised by the actor during message processing or initialization.
    """

    error: BaseException
    reason: str | None = None
