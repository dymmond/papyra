from papyra.address import ActorAddress


def test_actor_address_roundtrip_string_parse():
    addr = ActorAddress(system="local", actor_id=42)
    parsed = ActorAddress.parse(str(addr))

    assert parsed == addr


def test_actor_address_equality_and_hash():
    a1 = ActorAddress(system="local", actor_id=1)
    a2 = ActorAddress(system="local", actor_id=1)
    a3 = ActorAddress(system="local", actor_id=2)

    assert a1 == a2
    assert a1 != a3
    assert len({a1, a2, a3}) == 2
