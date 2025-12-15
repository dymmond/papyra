import pytest

from papyra import ActorSystem
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


async def test_ref_for_name_unknown_raises():
    async with ActorSystem() as system:
        with pytest.raises(ActorStopped):
            system.ref_for_name("missing")


async def test_ref_for_invalid_address_string():
    async with ActorSystem() as system:
        with pytest.raises(ValueError):
            system.ref_for("not-an-address")
