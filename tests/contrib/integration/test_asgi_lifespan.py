from __future__ import annotations

import pytest

from papyra.contrib.asgi.lifesycle import papyra_lifecycle

pytestmark = pytest.mark.anyio


class FakeSystem:
    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self._persistence_startup = None

        class Backend:
            async def recover(self, cfg):
                return None

        self._persistence = Backend()

    @property
    def persistence(self):
        return self._persistence

    async def start(self):
        self.started = True

    async def aclose(self):
        self.closed = True


async def test_papyra_lifespan_starts_and_closes():
    sys = FakeSystem()

    def factory_sync():
        return sys

    async with papyra_lifecycle(factory_sync) as fs:
        assert fs is sys
        assert fs.started is True
        assert fs.closed is False

    assert fs.closed is True
