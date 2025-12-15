import pytest

from papyra import Actor, ActorStopped, ActorSystem, DeadLetter

pytestmark = pytest.mark.anyio


class Target(Actor):
    async def receive(self, msg):
        if msg == "stop":
            await self.context.stop_self()
            return "stopping"
        return "ok"


async def test_dead_letter_on_tell_to_stopped_actor():
    async with ActorSystem() as system:
        ref = system.spawn(Target)

        # stop actor
        assert await ref.ask("stop") == "stopping"

        # tell after stop -> ActorStopped + dead letter
        with pytest.raises(ActorStopped):
            await ref.tell("after")

        assert len(system.dead_letters.messages) == 1

        dl = system.dead_letters.messages[0]

        assert isinstance(dl, DeadLetter)
        assert dl.target._rid == ref._rid
        assert dl.message == "after"
        assert dl.expects_reply is False


async def test_dead_letter_on_ask_to_stopped_actor():
    async with ActorSystem() as system:
        ref = system.spawn(Target)

        # stop actor
        await ref.ask("stop")

        # ask after stop -> ActorStopped + dead letter
        with pytest.raises(ActorStopped):
            await ref.ask("get")

        assert len(system.dead_letters.messages) == 1

        dl = system.dead_letters.messages[0]

        assert dl.target._rid == ref._rid
        assert dl.message == "get"
        assert dl.expects_reply is True


async def test_on_dead_letter_hook_is_called():
    seen: list[DeadLetter] = []

    def on_dead_letter(dl: DeadLetter) -> None:
        seen.append(dl)

    async with ActorSystem(on_dead_letter=on_dead_letter) as system:
        ref = system.spawn(Target)

        await ref.ask("stop")

        with pytest.raises(ActorStopped):
            await ref.tell("after")

        assert len(seen) == 1
        assert len(system.dead_letters.messages) == 1
        assert seen[0].message == "after"
