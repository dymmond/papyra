# Actor Proxies

ActorRefs are the lowest-level way to talk to actors: `tell(...)` for fire-and-forget and
`ask(...)` for request/reply. Actor proxies add a more ergonomic option when your actor exposes
ordinary methods or attributes that you want to call through the actor loop.

Proxy calls are still actor messages. They are serialized with the rest of the mailbox, so actor
state is not accessed concurrently.

## Service Example

```python
from __future__ import annotations

import anyio

from papyra.actor import Actor
from papyra.system import ActorSystem


class Inventory(Actor):
    def __init__(self) -> None:
        self.stock: dict[str, int] = {"book": 3}

    def reserve(self, sku: str, quantity: int = 1) -> bool:
        available = self.stock.get(sku, 0)
        if available < quantity:
            return False
        self.stock[sku] = available - quantity
        return True

    def restock(self, sku: str, quantity: int) -> None:
        self.stock[sku] = self.stock.get(sku, 0) + quantity

    async def receive(self, message):
        if message == "snapshot":
            return dict(self.stock)
        return None


async def main() -> None:
    async with ActorSystem() as system:
        inventory_ref = system.spawn(Inventory, name="inventory")
        inventory = inventory_ref.proxy()

        reserved = await inventory.reserve("book", quantity=2)
        print("reserved:", reserved)

        # Attribute reads are awaited.
        print("stock:", await inventory.stock)

        # Fire-and-forget method call.
        await inventory.restock.defer("book", 5)

        # This ask happens after the deferred call in the same mailbox.
        print("snapshot:", await inventory_ref.ask("snapshot"))


if __name__ == "__main__":
    anyio.run(main)
```

## Proxy API

- `proxy = ref.proxy()` creates a proxy for the actor reference.
- `await proxy.method(*args, **kwargs)` calls an actor method with request/reply semantics.
- `await proxy.method.defer(*args, **kwargs)` calls an actor method with fire-and-forget semantics.
- `await proxy.attribute` reads an actor attribute.
- `await proxy.attribute.set(value)` sets an actor attribute.

Private attributes are intentionally hidden: paths containing names that start with `_` raise
`AttributeError`.

## Direct Proxy Messages

For lower-level integrations, proxy operations are just messages:

```python
from papyra.messages import ProxyCall

result = await ref.ask(
    ProxyCall(
        attr_path=("reserve",),
        args=("book",),
        kwargs={"quantity": 1},
    )
)
```

Use direct messages when you are building tooling and want to avoid creating proxy objects. For
application code, `ref.proxy()` is usually clearer.
