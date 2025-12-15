import pytest

from papyra import Actor, ActorSystem, Strategy, SupervisionPolicy

pytestmark = pytest.mark.anyio

class FlakyCounter(Actor):
    """
    Actor that crashes on "boom" and otherwise counts increments.

    We use this to verify that RESTART:
    - recreates the actor (state resets),
    - keeps the same ActorRef usable afterwards.
    """

    def __init__(self) -> None:
        self.value = 0

    async def receive(self, message):
        if message == "inc":
            self.value += 1
            return None
        if message == "get":
            return self.value
        if message == "boom":
            raise RuntimeError("crash")
        raise ValueError(f"unknown: {message!r}")


async def test_restart_resets_state_and_ref_survives():
    async with ActorSystem() as system:
        ref = system.spawn(
            FlakyCounter,
            policy=SupervisionPolicy(strategy=Strategy.RESTART, max_restarts=5, within_seconds=60.0),
        )

        await ref.tell("inc")
        await ref.tell("inc")
        assert await ref.ask("get") == 2

        # Crash via ask: caller receives error, but actor restarts afterwards.
        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # After restart, state should be reset (new instance).
        assert await ref.ask("get") == 0

        await ref.tell("inc")
        assert await ref.ask("get") == 1


async def test_restart_limit_stops_actor():
    async with ActorSystem() as system:
        ref = system.spawn(
            FlakyCounter,
            policy=SupervisionPolicy(strategy=Strategy.RESTART, max_restarts=2, within_seconds=60.0),
        )

        # Two allowed restarts, third crash should stop the actor.
        with pytest.raises(RuntimeError):
            await ref.ask("boom")
        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # Third crash triggers budget exhaustion; actor should stop.
        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # Now any interaction should fail because actor is stopped.
        from papyra import ActorStopped

        with pytest.raises(ActorStopped):
            await ref.tell("inc")
