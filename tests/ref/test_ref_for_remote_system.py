import pytest

from papyra import ActorSystem
from papyra.address import ActorAddress
from papyra.exceptions import ActorStopped

pytestmark = pytest.mark.anyio


async def test_ref_for_remote_system_rejected():
    async with ActorSystem() as system:
        addr = ActorAddress(system="remote-system", actor_id=1)

        with pytest.raises(ActorStopped):
            system.ref_for(addr)
