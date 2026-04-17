---
name: bdd:setup
description: Use when initializing BDD E2E testing in a project for the first time, or when re-configuring the test stack. Creates tests/e2e/checkmate.config.json, installs service dependencies, and wires into CLAUDE.md.
---

# bdd:setup

One-time initialization of the BDD test stack for a consuming project.

## Steps

1. Check for `tests/e2e/checkmate.config.json`. If missing, ask:
   - Base URL of the application under test (e.g. `http://localhost:7792`)
   - Shell command to start the application (e.g. `cargo run --manifest-path core/Cargo.toml`)
   - Health/ready URL to poll (e.g. `http://localhost:7792/api/health`)
   - Ready timeout in seconds (default: 30)

2. Ask: "Should BDD scenario results be **required** to pass before marking implementation complete, or just **prompted** as a reminder?"
   - Write the answer as `bdd.verification_mode` (`required` or `prompted`) in config.

3. Detect Docker: run `docker info` (suppress output). If available and user doesn't object, set `services.prefer_docker: true`.

4. Write `tests/e2e/checkmate.config.json` using the schema from the design spec.

5. Check dependencies:
   - If Docker: confirm `docker compose` is available.
   - If native: check Python 3.11+ (`python --version`), uv (`uv --version`), Node 22+ (`node --version`). Print install instructions for anything missing.

6. If native: run `npm install` in the checkmate-mcp directory (from plugin install path).

7. Offer to append the BDD section to `CLAUDE.md` from `templates/claude-md-snippet.md`. Apply if user agrees.

8. Create `tests/e2e/scenarios/` directory if it doesn't exist.

9. Remind user: run `bdd:stack up` to start services before writing or running scenarios.

**Idempotent** — re-running updates config values without destroying existing scenarios.
