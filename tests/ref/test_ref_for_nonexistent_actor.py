import pytest

from papyra import ActorSystem
from papyra.address import ActorAddress
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


async def test_ref_for_unknown_actor_raises():
    async with ActorSystem() as system:
        addr = ActorAddress(system=system.system_id, actor_id=999)

        with pytest.raises(ActorStopped):
            system.ref_for(addr)
