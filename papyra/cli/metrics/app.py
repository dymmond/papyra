from __future__ import annotations

import json as _json
from typing import Annotated, Any

from rich.table import Table
from sayer import Option, echo, group, info
from sayer.core.console.sayer import console  # type: ignore

from papyra import monkay

metrics = group(
    name="metrics",
    help="Inspect runtime metrics and observability counters",
)


def _get_persistence() -> Any:
    """
    Resolve the appropriate persistence backend instance based on the provided inputs.

    This helper function determines which persistence strategy to use for the current
    operation. It allows for an override via a specific file path, which is useful for
    ad-hoc operations like recovery or inspection. If no path is specified, it defaults
    to the globally configured application persistence.

    Args:
        path (Path | None): An optional file system path.
            - If provided: A new `JsonFilePersistence` instance is created pointing
              to this specific file.
            - If None: The function returns the system-wide persistence backend
              defined in `monkay.settings`.

    Returns:
        Any: An initialized persistence backend instance (e.g., JsonFilePersistence or
            the global default).
    """
    # Otherwise, return the standard persistence backend configured for the application.
    return monkay.settings.persistence


@metrics.command(name="persistence")
async def persistence_metrics(
    json: Annotated[
        bool,
        Option(False, help="Output metrics as JSON"),
    ],
) -> None:
    """
    Retrieve and display the current operational metrics for the persistence backend.

    This command queries the active persistence layer for its internal telemetry data,
    such as the total number of records written, bytes stored, errors encountered, and
    maintenance operations performed (scans, recoveries, compactions).

    Output Formats:
    - Default: A human-readable list of key-value pairs printed to the console.
    - JSON: A structured JSON object, useful for parsing by external monitoring tools
      or scripts.

    Args:
        json (bool): If True, the output will be formatted as a valid JSON string.
            Defaults to False.
    """
    backend = _get_persistence()

    # Check if the configured backend supports metric tracking (via the mixin)
    if not hasattr(backend, "metrics"):
        info("Persistence backend does not expose metrics.")
        return

    # Retrieve a point-in-time snapshot of the metric counters
    snapshot = backend.metrics.snapshot()

    if not snapshot:
        info("No metrics available.")
        return

    if json:
        echo(_json.dumps(snapshot, indent=2))
        return

    table = Table(title="Persistence Metrics", header_style="bold magenta")
    table.add_column("Key", style="green")
    table.add_column("Value", style="cyan")

    for key, value in snapshot.items():
        table.add_row(key, str(value))
    console.print(table)


@metrics.command()
async def reset() -> None:
    """
    Reset all runtime metric counters to their initial zero state.

    This command is primarily intended for use in testing environments or during
    controlled monitoring intervals where isolated measurements are required.
    It clears accumulated statistics like write counts, error rates, and operation
    totals on the active persistence backend.

    Behavior:
    - If the backend supports metrics, all counters are reset immediately.
    - If the backend does not track metrics, the command exits gracefully with a message.
    """
    backend = _get_persistence()

    if not hasattr(backend, "metrics"):
        info("Persistence backend does not expose metrics.")
        return

    backend.metrics.reset()
    info("Metrics reset")
