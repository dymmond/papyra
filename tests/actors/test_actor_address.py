from papyra.address import ActorAddress


def test_actor_address_is_stable_and_stringifiable():
    addr = ActorAddress(system="test-system", actor_id=42)

    assert addr.system == "test-system"
    assert addr.actor_id == 42
    assert str(addr) == "test-system:42"
