---
name: bdd:stack
description: Use to start, stop, or check the status of the BDD test environment (checkmate + playwright-http + checkmate-mcp + application under test). Supports subcommands: up, down, status.
---

# bdd:stack

Manages the full test environment. The plugin owns the three service processes; the application under test is started via `stack.start_command` from `checkmate.config.json`.

## Subcommands

### `bdd:stack up`

1. Read `tests/e2e/checkmate.config.json`. If missing, instruct user to run `bdd:setup` first.
2. Determine service mode: Docker if `services.prefer_docker: true` AND `docker info` succeeds; otherwise native.
3. Start services:
   - **Docker:** `docker compose -f <plugin-root>/docker/docker-compose.yml up -d`
   - **Native:** start checkmate, playwright-http, checkmate-mcp as background processes
4. Wait for health endpoints (retry with exponential backoff, 30s timeout each):
   - checkmate: `GET http://127.0.0.1:8000/health`
   - playwright-http: `GET http://127.0.0.1:8932/health`
   - checkmate-mcp: `GET http://127.0.0.1:3003/health`
5. Start the application under test: execute `stack.start_command` from repo root.
6. Poll `stack.ready_url` with exponential backoff up to `stack.ready_timeout_secs`.
7. Ensure checkmate project exists: `GET /api/projects/` — create if `checkmate.project_name` not found.
8. Register any unregistered scenarios from `tests/e2e/scenarios/` into checkmate.
9. Report ready/failed status for each component.

**Idempotent** — skips services already passing health checks. Safe to re-run during a dev session.

### `bdd:stack down`

1. Stop the application under test (kill the process started by `start_command`).
2. Stop services:
   - **Docker:** `docker compose -f <plugin-root>/docker/docker-compose.yml down`
   - **Native:** kill the background processes started by `bdd:stack up`

### `bdd:stack status`

1. Check health endpoints for all three services.
2. Check if the application under test is responding at `ready_url`.
3. Report: running / not running / unhealthy for each component.

## Local dev pattern

Run `bdd:stack up` once at the start of a dev session. Services stay running between `bdd:run` calls. Run `bdd:stack down` when done for the day.
