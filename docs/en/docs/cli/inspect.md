# `papyra inspect`

The `inspect` command group lets you **read** what the persistence backend has recorded.
It’s meant for **humans** (operators, SREs, developers) who want to understand what happened in a
system run: lifecycle events, audit snapshots, and dead letters.

Important properties:

- **Read-only**: `inspect` never mutates persistence.
- **Uses configured persistence**: it reads from `monkay.settings.persistence`.
- **Best-effort output**: if there is no data recorded, commands print a friendly message.

`inspect` is different from:

- `papyra persistence scan` / `papyra doctor run`: those are about **health** and **startup guarantees**.
- `papyra persistence recover`: that **repairs** corruption.
- `papyra metrics ...`: that exposes **counters**, not the underlying records.

---

## Commands

- [`papyra inspect events`](#papyra-inspect-events)
- [`papyra inspect audits`](#papyra-inspect-audits)
- [`papyra inspect dead-letters`](#papyra-inspect-dead-letters)
- [`papyra inspect summary`](#papyra-inspect-summary)

---

## `papyra inspect events`

List lifecycle events recorded by the persistence backend (starts, crashes, stops, restarts, etc.).

### Usage

```bash
papyra inspect events
```

### Options

- `--limit <int>`: limit the number of events returned.
- `--since <float>`: only include events with `timestamp >= since`.
- `--event-type <str>`: filter by event class name (e.g. `ActorStarted`).
- `--reverse`: show newest events first.

### Output format

Each line is:

```shell
[timestamp] EventType ActorAddress
```

Example:

```shell
[1700000000.123] ActorStarted local://1
[1700000005.987] ActorCrashed local://1
```

### Examples

Show only stop events:

```bash
papyra inspect events --event-type ActorStopped
```

Show the last 50 events, newest first:

```bash
papyra inspect events --limit 50 --reverse
```

Show events since a Unix timestamp:

```bash
papyra inspect events --since 1700000000
```

If no events exist:

```bash
No events recorded.
```

---

## `papyra inspect audits`

List audit snapshots recorded by the persistence backend.

Audits are point-in-time summaries of system health invariants: actor counts, registry state,
and dead letter totals.

### Usage

```bash
papyra inspect audits
```

### Options

- `--limit <int>`: limit the number of audit records returned.
- `--since <float>`: only include audits with `timestamp >= since`.

### Output format

Each line is:

```bash
[timestamp] total=X alive=Y stopping=Z restarting=W dead_letters=N
```

Example:

```bash
[1700001234.000] total=10 alive=8 stopping=1 restarting=1 dead_letters=2
```

If no audits exist:

```bash
No audit reports recorded.
```

---

## `papyra inspect dead-letters`

List dead letters recorded by the persistence backend.

Dead letters are messages that could not be delivered to their intended actor (typically because
it was stopped or no longer existed).

### Usage

```bash
papyra inspect dead-letters
```

### Options

- `--limit <int>`: limit the number of dead letters returned.
- `--since <float>`: only include dead letters with `timestamp >= since`.
- `--reverse`: show newest dead letters first.
- `--target <str>`: filter by target actor address string (e.g. `local://2`).

### Output format

Each line is:

```bash
[timestamp] target=ActorAddress type=MessageType payload=...
```

Example:

```bash
[1700002000.500] target=local://2 type=str payload='hello'
```

Filter dead letters for a specific target:

```bash
papyra inspect dead-letters --target local://2
```

If no dead letters exist:

```bash
No dead letters recorded.
```

---

## `papyra inspect summary`

Show a quick “latest health” summary derived from the **most recent audit**.

This is the fastest way to answer: *what does the system look like right now (according to the
latest audit snapshot)?*

### Usage

```bash
papyra inspect summary
```

### Output

Example:

```bash
Actors: total=3 alive=2 stopping=1 restarting=0
Dead letters: 4
```

If no audits exist:

```text
No audit data available.
```

---

## Notes and common pitfalls

### `inspect` does not scan for corruption

`inspect` reads whatever the backend returns via `list_events`, `list_audits`, and `list_dead_letters`.
If you need correctness guarantees (e.g. detect truncated JSON lines), use:

- `papyra persistence scan`
- `papyra doctor run`

### `--since` is a float timestamp

The CLI passes `since` through to the backend as a float timestamp.
In most cases you’ll use Unix epoch seconds (possibly with decimals).

### Filtering is client-side for some options

- `--event-type` is applied **after** fetching events.
- `--target` is applied **after** fetching dead letters.

If you combine these with a small `--limit`, you may filter out everything.
In that case, increase `--limit`.
