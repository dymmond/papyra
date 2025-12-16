import pytest

from papyra import Actor, ActorSystem
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


class Worker(Actor):
    async def receive(self, msg):
        if msg == "boom":
            raise RuntimeError("crash")
        if msg == "stop":
            await self.context.stop_self()
        return "ok"


async def test_audit_registry_has_name_after_spawn():
    async with ActorSystem() as system:
        system.spawn(Worker, name="svc")

        report = system.audit()

        assert "svc" in system.list_names()
        assert "svc" not in report.registry_orphans
        assert "svc" not in report.registry_dead


async def test_audit_registry_removes_name_after_stop():
    async with ActorSystem() as system:
        ref = system.spawn(Worker, name="gone")
        await ref.ask("stop")

        # existing behavior: name lookup should fail
        with pytest.raises(ActorStopped):
            system.ref_for_name("gone")

        report = system.audit()

        assert "gone" not in system.list_names()
        assert "gone" not in report.registry_orphans
        assert "gone" not in report.registry_dead


async def test_audit_restart_keeps_name_mapped():
    async with ActorSystem() as system:
        ref = system.spawn(Worker, name="svc")

        with pytest.raises(RuntimeError):
            await ref.ask("boom")

        # name must still resolve
        resolved = system.ref_for_name("svc")
        assert resolved.address == ref.address

        report = system.audit()

        assert "svc" in system.list_names()
        assert "svc" not in report.registry_orphans
        assert "svc" not in report.registry_dead
