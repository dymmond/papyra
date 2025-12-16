import anyio
import pytest

from papyra import Actor, ActorSystem
from papyra.events import ActorCrashed, ActorStarted
from papyra.hooks import FailureInfo

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        if msg == "boom":
            raise RuntimeError("crash")
        return "ok"


class RecordingHooks:
    def __init__(self):
        self.events = []
        self.failures = []
        self.dead_letters = []
        self.audits = []

    def on_event(self, event):
        self.events.append(event)

    def on_failure(self, failure: FailureInfo):
        self.failures.append(failure)

    def on_dead_letter(self, dl):
        self.dead_letters.append(dl)

    def on_audit(self, report):
        self.audits.append(report)


async def test_hooks_receive_lifecycle_events():
    hooks = RecordingHooks()
    async with ActorSystem(hooks=hooks) as system:
        system.spawn(Worker)
        await anyio.sleep(0)

    assert any(isinstance(e, ActorStarted) for e in hooks.events)


async def test_hooks_receive_failure_info_on_crash():
    hooks = RecordingHooks()
    async with ActorSystem(hooks=hooks) as system:
        ref = system.spawn(Worker, name="svc")  # restart policy
        await anyio.sleep(0)

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        await anyio.sleep(0)

    assert any(isinstance(e, ActorCrashed) for e in hooks.events)
    assert hooks.failures
    assert hooks.failures[-1].error is not None


async def test_hooks_receive_audit_snapshot():
    hooks = RecordingHooks()
    async with ActorSystem(hooks=hooks) as system:
        system.spawn(Worker)
        report = system.audit()
        await anyio.sleep(0)

    assert hooks.audits
    assert hooks.audits[-1] is report
