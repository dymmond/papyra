import anyio
import pytest

from papyra import Actor, ActorSystem
from papyra._envelope import ActorTerminated

pytestmark = pytest.mark.anyio


class Target(Actor):
    async def receive(self, msg):
        if msg == "stop":
            await self.context.stop_self()


class Watcher(Actor):
    async def on_start(self):
        self.events = []

    async def receive(self, msg):
        # Command sent by the test to start watching
        if isinstance(msg, tuple) and msg and msg[0] == "watch":
            _, target = msg
            await self.context.watch(target)
            return "watching"

        # System message delivered by the runtime
        if isinstance(msg, ActorTerminated):
            self.events.append(msg.ref)
            return "terminated"


async def test_watch_notified_on_stop():
    async with ActorSystem() as system:
        target = system.spawn(Target)
        watcher = system.spawn(Watcher)

        # Start watching (must be done from inside the actor)
        assert await watcher.ask(("watch", target)) == "watching"

        # Stop target
        await target.ask("stop")

        # Give the scheduler a tick so the notification is delivered
        await anyio.sleep(0)

        # Inspect watcher actor state (test-only access)
        events = system._by_id[watcher._rid].actor.events
        assert len(events) == 1
        assert events[0]._rid == target._rid
