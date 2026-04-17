---
name: bdd:run
description: Use to execute BDD scenarios against the running application. Supports running a single scenario, a feature group, or the full suite. Streams step-level output and reports failures with component-boundary hints.
---

# bdd:run

Executes scenarios via checkmate-mcp and reports results.

## Usage

- `bdd:run <filename>` — single scenario by filename or path (e.g. `wizard-stores-operator-credentials`)
- `bdd:run <feature-group>` — all scenarios in a group (e.g. `init-wizard`)
- `bdd:run all` — full suite

## Steps

1. Verify stack is up: check `bdd:stack status`. If any service is not running, offer to run `bdd:stack up` before proceeding.

2. Resolve the target to checkmate test case ID(s):
   - Single file: match by name in `tests/e2e/scenarios/`
   - Feature group: all files in `tests/e2e/scenarios/<group>/`
   - All: every file under `tests/e2e/scenarios/`

3. Execute via checkmate-mcp `run_test` tool (single) or sequentially for suites. Stream step output in real time.

4. On failure:
   - Print the failing step action, target, and value.
   - Print the assertion that failed.
   - Print screenshot path if captured.
   - Suggest which component boundary to investigate:
     - `navigate` / `click` / `assert_text` on visible UI → **UI layer** (check browser console, HTML rendering)
     - `assert_text` on API response data → **HTTP API layer** (check Axum route handler, DB query)
     - Step that follows a model load or prewarm → **Runner IPC layer** (check core↔runner stdin/stdout)
     - Startup-sequence scenario → **Startup sequencing** (check main.rs step order, readiness polling)

5. Print summary: N passed / M failed / duration.

## Local dev guidance

For inner-loop development, run a single scenario or feature group — not `bdd:run all`. Full suite is for pre-completion verification and CI.

If a scenario is flaky (passes sometimes, fails others), investigate timing: add `wait_for_page` or `wait` steps before assertions on async operations.
