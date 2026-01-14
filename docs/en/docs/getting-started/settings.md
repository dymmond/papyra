# Settings

In every application, there comes a point where you need **project-specific configuration**.

As Papyra grows (multiple environments, different persistence backends, custom logging, different serializer policies),
spreading configuration across the codebase becomes hard to manage.

Papyra solves this by providing a single **Settings** object (and a global **settings** instance)
that can be overridden by your application.

## How to use

There are two supported ways to configure Papyra:

- Using the **`PAPYRA_SETTINGS_MODULE`** environment variable (recommended for deployments)
- Importing and using the global **`settings`** (recommended for scripts/tests and simple apps)

Both approaches work together.

---

## The Settings object

Papyra exposes:

- `from papyra import Settings` → the base class you inherit from
- `from papyra import settings` (or `from papyra.conf import settings`) → the global settings instance

### What you should override

You override configuration by creating your own subclass of `Settings` and changing attributes/properties.

At minimum, most apps override:

- `debug`
- `logging_level`
- `persistence`
- (optionally) `serializer_config`

---

## Custom settings

You should **always inherit from** `papyra.Settings`.

A common pattern is to have:

- one base settings class with shared values
- one settings class per environment (development/testing/production)

### Example project structure

```text
myapp/
  __init__.py
  main.py
  configs/
    __init__.py
    base.py
    development.py
    testing.py
    production.py
```

### Base settings

```python
# myapp/configs/base.py
from papyra import Settings
from papyra.persistence.backends.memory import InMemoryPersistence


class AppSettings(Settings):
    debug: bool = False
    logging_level: str = "INFO"

    # Default persistence (override in env-specific settings)
    persistence = InMemoryPersistence()
```

### Development settings

```python
# myapp/configs/development.py
from papyra.persistence.json import JsonFilePersistence

from .base import AppSettings


class DevelopmentSettings(AppSettings):
    debug: bool = True
    logging_level: str = "DEBUG"

    # Store facts locally for development
    persistence = JsonFilePersistence("./.papyra/events.ndjson")
```

### Testing settings

```python
# myapp/configs/testing.py
from papyra.persistence.backends.memory import InMemoryPersistence

from .base import AppSettings


class TestingSettings(AppSettings):
    # Tests usually prefer ephemeral persistence
    persistence = InMemoryPersistence()
```

### Production settings

```python
# myapp/configs/production.py
from papyra.persistence.redis import RedisStreamsConfig, RedisStreamsPersistence

from .base import AppSettings


class ProductionSettings(AppSettings):
    debug: bool = False
    logging_level: str = "INFO"

    # Example: Redis Streams persistence
    persistence = RedisStreamsPersistence(
        RedisStreamsConfig(
            url="redis://localhost:6379/0",
            prefix="papyra",
            system_id="local",
        )
    )
```

---

## Settings module

Papyra looks for an environment variable called **`PAPYRA_SETTINGS_MODULE`**.

It must be a **dotted path to your settings class**, e.g.:

```bash
export PAPYRA_SETTINGS_MODULE=myapp.configs.production.ProductionSettings
```

### Running with a settings module

```bash
PAPYRA_SETTINGS_MODULE=myapp.configs.production.ProductionSettings python -m myapp.main
```

If `PAPYRA_SETTINGS_MODULE` is not set, Papyra falls back to its defaults.

---

## Order of priority

Papyra reads configuration in a deterministic order.

1. **Explicit overrides** (when you directly assign to the global settings in code)
2. **Environment variables** (for individual fields like `DEBUG`, `LOGGING_LEVEL`, etc.)
3. **The Settings class defaults**

Important notes:

- `PAPYRA_SETTINGS_MODULE` selects the settings class.
- Then each field may still be overridden by **environment variables** because `BaseSettings` reads env vars for each declared setting.

So the practical order is:

- Class default → overridden by env var → overridden by direct assignment in code.

---

## Environment variables

Papyra's settings system reads environment variables based on the attribute name.

Example:

- `debug` → `DEBUG`
- `logging_level` → `LOGGING_LEVEL`

This happens automatically inside `BaseSettings.__init__()`.

### Example

```bash
export PAPYRA_SETTINGS_MODULE=myapp.configs.production.ProductionSettings
export LOGGING_LEVEL=WARNING
```

The settings class may default to `INFO`, but `LOGGING_LEVEL=WARNING` wins.

---

## Accessing settings

### Import the global settings

```python
from papyra import settings

print(settings.logging_level)
print(settings.debug)
```

### Import the Settings class

```python
from papyra import Settings

class MySettings(Settings):
    debug: bool = True
```

---

## Persistence and settings

Papyra persistence is configured via the `settings.persistence` attribute.

This must be an instance of a persistence backend (e.g. `InMemoryPersistence`, `JsonFilePersistence`, `RotatingFilePersistence`, `RedisStreamsPersistence`).

Examples:

```python
from papyra.persistence.backends.memory import InMemoryPersistence

settings.persistence = InMemoryPersistence()
```

```python
from papyra.persistence.json import JsonFilePersistence

settings.persistence = JsonFilePersistence("./events.ndjson")
```

```python
from papyra.persistence.redis import RedisStreamsConfig, RedisStreamsPersistence

settings.persistence = RedisStreamsPersistence(
    RedisStreamsConfig(url="redis://localhost:6379/0", prefix="papyra", system_id="local")
)
```

---

## Serializer config

Papyra exposes `settings.serializer_config` as a **property** that returns a `SerializerConfig`.

To override it, override the property in your settings class:

```python
from papyra import Settings
from papyra.serializers import SerializerConfig, StandardSerializerConfig


class AppSettings(Settings):
    @property
    def serializer_config(self) -> SerializerConfig:
        # Swap this for your own implementation/config
        return StandardSerializerConfig()
```

---

## Logging

Papyra exposes `settings.logging_config` as a property.

Most users only change `logging_level`:

```python
from papyra import Settings


class AppSettings(Settings):
    logging_level: str = "DEBUG"
```

---

## Common pitfalls

### 1) Using a module path instead of a class path

✅ Correct:

```bash
PAPYRA_SETTINGS_MODULE=myapp.configs.production.ProductionSettings
```

❌ Wrong:

```bash
PAPYRA_SETTINGS_MODULE=myapp.configs.production
```

### 2) Expecting env vars to override non-declared fields

Only attributes that exist on your `Settings` class are processed by `BaseSettings`.

If you add new settings fields, declare them on the class (with type hints) so they become part of `__type_hints__`.

### 3) Forgetting that persistence is an object

`settings.persistence` is not a string like "redis" or "sqlite" — it is an **instance**.

---

## Quick reference

| What you want | How to do it |
|---|---|
| Use production settings | `PAPYRA_SETTINGS_MODULE=...ProductionSettings` |
| Override a field via env var | `LOGGING_LEVEL=WARNING` |
| Override persistence in code | `settings.persistence = JsonFilePersistence(...)` |
| Inspect current settings | `settings.dict()` |
