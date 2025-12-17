from __future__ import annotations

from typing import Annotated

from sayer import Option, group, info

from papyra import monkay

inspect = group(name="inspect", help="Inspect persisted Papyra system state")


@inspect.command()
async def events(
    limit: Annotated[int | None, Option(None, help="Total limit to display")],
    since: Annotated[float | None, Option(None, help="From a given timestamp")],
    event_type: Annotated[str | None, Option(None, help="Type of events to show")],
    reverse: Annotated[bool, Option(False, help="Show newest events first")],
) -> None:
    """
    List all lifecycle events recorded by the persistence backend.

    This command retrieves the historical log of actor system events (starts, stops, crashes,
    restarts) and displays them in chronological order. This is essential for post-mortem
    analysis to reconstruct the sequence of operations that occurred during the system's runtime.

    **Output Format**

    ```
    [timestamp] EventType ActorAddress
    ```
    """
    # Retrieve the immutable snapshot of recorded events from the persistence layer.
    events = await monkay.settings.persistence.list_events(
        limit=limit,
        since=since,
    )

    if reverse:
        events = reversed(events)

    if event_type:
        events = [e for e in events if e.event_type == event_type]

    if not events:
        info("No events recorded.")
        return

    for event in events:
        # Format the output for readability: [1700000000.123] ActorStarted local://1
        info(f"[{event.timestamp:.3f}] " f"{event.event_type} " f"{event.actor_address}")


@inspect.command()
async def audits(
    limit: Annotated[int | None, Option(None, help="Total limit to display")],
    since: Annotated[float | None, Option(None, help="From a given timestamp")],
) -> None:
    """
    List all audit reports recorded by the persistence backend.

    Audit reports represent point-in-time snapshots of the actor system,
    including actor counts, registry health, and dead-letter statistics.

    **Output Format**

    ```
    [timestamp] total=X alive=Y stopping=Z restarting=W dead_letters=N
    ```
    """
    audits = await monkay.settings.persistence.list_audits(limit=limit, since=since)

    if not audits:
        info("No audit reports recorded.")
        return

    for audit in audits:
        info(
            f"[{audit.timestamp:.3f}] "
            f"total={audit.total_actors} "
            f"alive={audit.alive_actors} "
            f"stopping={audit.stopping_actors} "
            f"restarting={audit.restarting_actors} "
            f"dead_letters={audit.dead_letters_count}"
        )


@inspect.command(name="dead-letters")
async def dead_letters(
    limit: Annotated[int | None, Option(None, help="Total limit to display")],
    since: Annotated[float | None, Option(None, help="From a given timestamp")],
    reverse: Annotated[bool, Option(False, help="Reverse the order of dead letters")],
    target: Annotated[str | None, Option(None, help="The target of the search")],
) -> None:
    """
    List all dead letters recorded by the persistence backend.

    Dead letters represent messages that could not be delivered to their
    intended actor, usually because the actor had already stopped.

    **Output Format**

    ```
    [timestamp] target=ActorAddress type=MessageType payload=...
    ```
    """
    dead_letters = await monkay.settings.persistence.list_dead_letters(limit=limit, since=since)

    if reverse:
        dead_letters = reversed(dead_letters)

    if target:
        dead_letters = [dl for dl in dead_letters if str(dl.target) == target]

    if not dead_letters:
        info("No dead letters recorded.")
        return

    for dl in dead_letters:
        info(f"[{dl.timestamp:.3f}] " f"target={dl.target} " f"type={dl.message_type} " f"payload={dl.payload!r}")
