# CI/CD for Papyra

This document describes how to integrate **Papyra** into Continuous Integration (CI) and Continuous Deployment (CD)
pipelines. It focuses on correctness, safety, and operational guarantees rather than convenience shortcuts.

Papyra's persistence model, startup checks, and recovery tooling make it especially
well‑suited for automated validation in CI and for safe rollouts in production.

---

## Goals of CI/CD with Papyra

A correct CI/CD pipeline for a Papyra-based system should:

- Prevent deployment when persistence corruption exists
- Detect incompatible persistence format changes early
- Enforce deterministic startup behavior
- Make recovery explicit and observable
- Support safe rollbacks

---

## CI: Continuous Integration

### 1. Test Suite (Mandatory)

Your CI pipeline **must** run the full test suite, including:

- Unit tests
- Persistence backend tests (JSON / Redis / rotation as applicable)
- CLI tests (`persistence`, `doctor`, `inspect`)

Example:

```bash
pytest
```

This ensures that:

- Persistence contracts are not accidentally broken
- Recovery logic remains valid
- Retention and compaction behavior is stable

---

### 2. Persistence Format Compatibility Checks

If your application evolves persisted schemas (events, audits, dead letters), CI should validate
**backward compatibility**.

Recommended strategy:

1. Keep a small set of persisted fixtures from previous versions
2. In CI:
    - Run `persistence scan` against them
    - Ensure no anomalies are reported

Example:

```bash
papyra persistence scan --path tests/fixtures/v1/events.ndjson
```

Failure here means:

- You introduced a breaking persistence change
- A migration or compatibility layer is required

---

### 3. Startup Check Validation

Simulate application startup in CI using the same logic as production.

Example:

```bash
papyra persistence startup-check --mode FAIL_ON_ANOMALY --path tests/fixtures/events.ndjson
```

This guarantees:

- The application will not boot with corrupted data
- Startup behavior matches production exactly

---

## CD: Continuous Deployment

### 1. Pre‑Deployment Gate (Required)

Before deploying a new version, run a **doctor check** or startup check against the live persistence volume (or a snapshot of it).

Example (Kubernetes init container):

```bash
papyra doctor run --mode FAIL_ON_ANOMALY
```

If this command exits non‑zero, deployment **must stop**.

---

### 2. Controlled Recovery in Deployment Pipelines

If your operational policy allows automated recovery, make it explicit:

```bash
papyra doctor run \
  --mode RECOVER \
  --recovery-mode REPAIR
```

Or quarantine mode:

```bash
papyra doctor run \
  --mode RECOVER \
  --recovery-mode QUARANTINE \
  --quarantine-dir /var/lib/papyra/quarantine
```

**Never hide recovery behind implicit behavior.**

---

### 3. Blue‑Green / Canary Deployments

Recommended pattern:

1. Deploy new version pointing to a **read-only copy** or snapshot
2. Run:

    ```bash
    papyra persistence startup-check --mode fail_on_anomaly
    ```

3. If clean, switch traffic
4. Only then allow writes

This avoids corrupting live data with incompatible binaries.

---

## Rollbacks

Papyra supports safe rollbacks **if persistence format is compatible**.

Best practices:

- Do not deploy destructive migrations automatically
- Keep backups before each deployment
- Validate old binaries against new data in CI

Rollback validation example:

```bash
papyra persistence scan --path /backup/events.ndjson
```

---

## CI/CD Anti‑Patterns (Avoid These)

- ❌ Skipping persistence scans in CI
- ❌ Auto‑recovering without logging or alerts
- ❌ Deploying new binaries before validating startup checks
- ❌ Treating persistence errors as warnings

These lead to silent corruption and irrecoverable failures.

---

## Minimal CI Pipeline Example

```yaml
steps:
  - name: test
    run: pytest

  - name: persistence-scan
    run: papyra persistence scan --path tests/fixtures/events.ndjson

  - name: startup-check
    run: papyra persistence startup-check --mode FAIL_ON_ANOMALY
```

---

## Production Readiness Checklist

Before enabling automatic deployment:

- [ ] CI runs full persistence tests
- [ ] Startup checks are enforced
- [ ] Recovery is explicit and observable
- [ ] Backups are taken pre‑deploy
- [ ] Rollback path is tested

---

## Summary

Papyra is **designed for automation**, but not for blind automation.

A correct CI/CD pipeline:
- Makes persistence health a hard gate
- Treats recovery as a first‑class operation
- Aligns CI, startup checks, and production behavior

If CI/CD passes, you can deploy with confidence.
