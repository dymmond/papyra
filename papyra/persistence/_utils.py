from __future__ import annotations

from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def _json_default(obj: Any) -> Any:
    """
    Provide a best-effort JSON serialization fallback for complex objects.

    This function is used as the `default` parameter for `json.dumps`. It converts types that
    are not natively supported by the standard JSON encoder into JSON-safe primitives.

    Conversion Logic
    ----------------
    - **Dataclasses**: Converted to a dictionary of their fields.
    - **Path objects**: Converted to their string representation.
    - **Others**: Fallback to the object's string representation (`str(obj)`).

    Parameters
    ----------
    obj : Any
        The object that failed standard JSON serialization.

    Returns
    -------
    Any
        A JSON-serializable representation of the object.
    """
    if is_dataclass(obj):
        return {f.name: getattr(obj, f.name) for f in fields(obj)}
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _pick_dataclass_fields(cls: type[T], data: dict[str, Any]) -> dict[str, Any]:
    """
    Filter an input dictionary to include only keys that match fields in a target dataclass.

    This utility ensures forward and backward compatibility for persistence models.
    - **Forward Compatibility**: If the stored record has extra fields (from a newer version),
      they are ignored when loading into an older dataclass definition.
    - **Safety**: Prevents `TypeError` during dataclass instantiation due to unexpected keyword
      arguments.

    Parameters
    ----------
    cls : type[T]
        The dataclass type to validate against.
    data : dict[str, Any]
        The raw dictionary loaded from storage.

    Returns
    -------
    dict[str, Any]
        A new dictionary containing only the keys that exist as fields in `cls`.
    """
    allowed = {f.name for f in fields(cls)}  # type: ignore[arg-type]
    return {k: v for k, v in data.items() if k in allowed}
