# Installation

This guide explains how to install **Papyra**, choose the right extras, and verify that
your environment is correctly set up.

Papyra is intentionally lightweight at its core, with optional dependencies for
production-grade backends such as Redis. You only install what you actually need.

---

## Requirements

Before installing Papyra, ensure you have:

- **Python 3.10 or newer**
- A modern virtual environment tool (recommended: `venv`, `uv`, `pipx`, or `hatch`)
- (Optional) Redis 7+ if you plan to use Redis Streams persistence

You can verify your Python version with:

```bash
python --version
```

---

## Basic Installation

Install the core package:

```bash
pip install papyra
```

This installs:

- Core persistence abstractions
- JSON file persistence
- In-memory persistence
- Retention, compaction, and recovery logic
- CLI tools (`papyra doctor`, `papyra persistence`, etc.)

This setup is sufficient for:

- Local development
- Testing
- Small to medium workloads
- CI pipelines

---

## Installing with Redis Support (Recommended for Production)

To enable Redis Streams persistence, install the Redis extra:

```bash
pip install papyra[redis]
```

This adds:

- `redis` asyncio client
- Redis Streams persistence backend
- Consumer group support
- Redis-backed recovery and compaction

Use this when:

- You need durability beyond local files
- You want horizontal scalability
- You plan to integrate with external tools via consumer groups

---

## Optional Extras

Papyra may grow additional optional extras over time (e.g. PostgreSQL, observability),
but the philosophy remains the same:

> **No mandatory heavy dependencies. Install only what you use.**

You can always inspect installed extras with:

```bash
pip show papyra
```

---

## Verifying the Installation

After installation, verify that the CLI is available:

```bash
papyra --help
```

You should see commands such as:

- `doctor`
- `persistence`
- `metrics`
- `inspect`

Run a basic health check:

```bash
papyra doctor run
```

Expected output (healthy system):

```
ℹ Persistence is healthy
```

---

## Installing in Development Mode

If you are developing Papyra itself or contributing:

```bash
git clone https://github.com/dymmond/papyra.git
cd papyra
pip install -e .[redis]
```

This installs:

- Editable package
- All optional extras
- Test and development dependencies (if configured)

---

## Environment Isolation (Strongly Recommended)

Always install Papyra inside a virtual environment.

Example using `venv`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install papyra[redis]
```

Example using `hatch`:

```bash
hatch shell
pip install papyra[redis]
```

---

## Common Installation Issues

### `ModuleNotFoundError: redis`

You installed the base package but are using Redis persistence.

Fix:

```bash
pip install papyra[redis]
```

---

### Python Version Too Old

If you see errors related to typing or `dataclasses`:

- Ensure Python ≥ 3.11
- Upgrade your interpreter

---

## Next Steps

Once installed, continue with:

- **Core Concepts** — understand how Papyra works
- **Persistence Backends** — choose the right storage
- **CLI Usage** — inspect, recover, and operate safely

Papyra is designed to be *boring to install* and *reliable to operate*.
