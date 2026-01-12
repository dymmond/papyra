# Integrations & ASGI

Papyra comes with some out of the box integrations with your favourite ASGI Frameworks.

Since the authors of Papyra are the same as [Lilya][lilya] and [Ravyn][ravyn], it makes
sense providing examples and integrations with them but it **also provides with Starlette and FastAPI**.

!!! Tip "Important"
    Just because the authors are the same, that does not mean you cannot **contribute** with your favourite
    framework integration as well.

If you want to [contribute](../contributing.md) with any extra integrations with your favourtire frameworks,
feel free to open a pul request add it.

## Where do the integrations live

Papyra does not have a hard dependency on any specific ASGI framework, instead, it provides a `contrib` section
where those live.

Currently, Papyra supports the following:

- [Lilya][lilya]
- [Ravyn][ravyn]
- [Starlette][starlette]
- [FastAPI][fastapi]

## How to integrate Papyra with your ASGI framework

Each integration brings a Papyra configuration attached and that works out of the box for you to access and use.

Let's see what does this mean.

### Lilya

```python
from lilya.apps import Lilya

from papyra.contrib.lilya import LilyaPapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem


def get_application() -> Lilya:
    app = Lilya()
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    papyra_config = LilyaPapyra(make_system)
    papyra_config.install(app)
```

And this is it! Now you can access the endpoints via:

- [http://localhost:8000/healthz](http://localhost:8000/healthz)
- [http://localhost:8000/metrics](http://localhost:8000/metrics)


### Ravyn

```python
from ravyn import Ravyn

from papyra.contrib.ravyn import RavynPapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem


def get_application() -> Ravyn:
    app = Ravyn()
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    papyra_config = RavynPapyra(make_system)
    papyra_config.install(app)
```

And this is it! Now you can access the endpoints via:

- [http://localhost:8000/healthz](http://localhost:8000/healthz)
- [http://localhost:8000/metrics](http://localhost:8000/metrics)


### Starlette

```python
from starlette.applications import Starlette

from papyra.contrib.starlette import StarlettePapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem


def get_application() -> Starlette:
    app = Starlette()
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    papyra_config = StarlettePapyra(make_system)
    papyra_config.install(app)
```

And this is it! Now you can access the endpoints via:

- [http://localhost:8000/healthz](http://localhost:8000/healthz)
- [http://localhost:8000/metrics](http://localhost:8000/metrics)


### FastAPI

```python
from fastapi import FastAPI

from papyra.contrib.fastapi import FastAPIPapyra
from papyra.persistence.backends.memory import InMemoryPersistence
from papyra.system import ActorSystem


def get_application() -> FastAPI:
    app = FastAPI()
    persistence = InMemoryPersistence()

    def make_system() -> ActorSystem:
        system = ActorSystem(
            persistence=persistence,
        )
        return system

    papyra_config = FastAPIPapyra(make_system)
    papyra_config.install(app)
```

And this is it! Now you can access the endpoints via:

- [http://localhost:8000/healthz](http://localhost:8000/healthz)
- [http://localhost:8000/metrics](http://localhost:8000/metrics)

## Summary

Papyra current integrates with some ASGI frameworks and can be extended to integrate with any
other as well.

[lilya]: https://lilya.dev
[ravyn]: https://ravyn.dev
[starlette]: https://www.starlette.io
[fastapi]: https://fastapi.tiangolo.com
