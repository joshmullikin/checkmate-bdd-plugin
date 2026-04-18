# checkmate-bdd-plugin Design

**Date:** 2026-04-17
**Last revised:** 2026-04-18
**Status:** Approved
**Repo:** joshmullikin/checkmate-bdd-plugin

---

## Problem

Multi-component integration bugs are not caught until the full stack runs together. Unit tests and per-component integration tests pass while real interactions between components fail. A BDD approach with automated E2E testing catches these at the scenario level, before they surface as user-visible bugs.

## Goals

- Provide a reusable Claude Code plugin that adds BDD authoring and E2E test execution to any project
- Own the full service stack (checkmate + playwright-http + checkmate-mcp) so consuming repos don't configure it
- Support local dev loop as first-class citizen alongside CI
- Integrate with the superpowers workflow so BDD is part of planning and verification, not an afterthought
- Be completely project-agnostic — no knowledge of any specific application
- Replace every OpenAI-dependent feature in the upstream checkmate backend with a Claude-native skill, so the full stack works with zero API keys

## Non-goals

- Containerizing the application under test (plugin never owns the app stack)
- Providing scenario templates (deferred to future)
- Managing any app-specific infrastructure
- Modifying upstream repos (`ksankaran/checkmate`, `ksankaran/checkmate-mcp`, `ksankaran/playwright-http`) — this plugin never requires a change to those to function

---

## Hard constraints

These two constraints are load-bearing for every skill design decision. Reviewers should reject any PR that violates them.

### C1. Do not touch the other checkmate repos

All plugin functionality lives in **this repo** (`checkmate-bdd-plugin`). The upstream repos — `checkmate` (backend), `checkmate-mcp` (MCP server), and `playwright-http` (executor) — must remain unmodified.

**Why:** Upstream repos are maintained by a different owner (`ksankaran`) and serve users on the OpenAI path. We must preserve backward compatibility: anyone with `OPENAI_API_KEY` set and using the upstream stack today must keep working unchanged. This plugin is purely additive and parallel — it offers a Claude-native path alongside the OpenAI path, never replacing it.

**How to apply:**
- A skill that would require a new endpoint or a prompt change in the backend is **out of scope**. Route around it instead (see C2 for the pattern).
- If upstream changes land that genuinely unblock a plugin feature, request them via upstream PR — do not fork.
- Plugin integration points with upstream: only the **existing** non-AI HTTP endpoints (`POST /api/test-cases`, `PUT /api/test-cases/{id}`, `POST /api/test-cases/{id}/runs/stream`, `POST /api/projects/{id}/recorder/start|stop`, WS `/api/projects/{id}/recorder/ws`, etc.) and the **existing** MCP tools exposed by `checkmate-mcp` (`list_projects`, `list_test_cases`, `run_test`).

### C2. Do not duplicate prompts, schemas, or action grammar

The upstream checkmate backend is the single source of truth for:
- UTML action grammar (23 action types, per-action `target`/`value` rules)
- Pydantic output schemas (`TestPlanModel`, `BuilderResponse`, `HealSuggestion`, `FailureClassification`, `RefinedStepsResponse`, `GeneratedMetadata`, `GeneratedTestCases`, `ProcessedStep`)
- System prompts in `agent/nodes/` and `api/routes/recorder.py`

**Why:** Copy-pasting prompts into SKILL.md files creates drift. Every upstream fix (new action, tightened rule, corrected edge case) would require a manual sync. Our goal: `bdd:stack up` pulls latest backend source; new skills instantly pick up the latest rules.

**How to apply:**
- `bdd:setup` / `bdd:stack up` clones the backend to `~/.checkmate-bdd/checkmate/` via `scripts/clone-deps.sh`. Skills reference those files at runtime.
- Skills tell Claude: "Read `~/.checkmate-bdd/checkmate/<path>` — the system prompt and Pydantic output model in that file are the contract. Generate output matching that model."
- SKILL.md contains the **workflow** (inputs to gather, outputs to produce, files to persist). It does **not** restate the action grammar or output schema.
- If a skill needs to evolve faster than the backend (plugin-specific UX), document the delta as a **supplement** to the backend prompt, never a replacement.

---

## Section 1: Architecture

### Service stack

The plugin owns three services:

| Service | Port | Role |
|---------|------|------|
| checkmate | 8000 | Project manager + test case store + recorder proxy (AI unused by plugin) |
| playwright-http | 8932 | Playwright executor + raw browser recorder |
| checkmate-mcp | 3003 | MCP server exposing UI panels + non-AI tools (`list_projects`, `list_test_cases`, `run_test`) |

When Docker is available (`docker info` succeeds), all three run as containers via `docker/docker-compose.yml`. Otherwise they run natively — checkmate and playwright-http via Python/uv, checkmate-mcp via Node/npm.

The application under test always runs natively. The plugin starts it by executing `stack.start_command` from `checkmate.config.json` and polls `stack.ready_url` until ready. It never attempts to containerize the app.

### Division of AI work

All agentic work that upstream checkmate does with an LLM is done inline by Claude instead, driven by the backend's own prompts and schemas read from cloned source. `OPENAI_API_KEY` is never set or required.

| Backend node / route | Purpose | Plugin replacement |
|---|---|---|
| `agent/nodes/classifier.py` (IntentClassification) | Route user intent | N/A — Claude is the router |
| `agent/nodes/planner.py` (TestPlanModel) | Intent → test plan | `bdd:write` step 1 |
| `agent/nodes/builder.py` (BuilderResponse) | Plan → full UTML | `bdd:write` step 2 |
| `agent/nodes/generator.py` (GeneratedTestCases) | Bulk test case ideation | `bdd:generate` |
| `agent/nodes/healer.py` (HealSuggestion) | Failed run → corrected UTML | `bdd:run` inner retry loop |
| `agent/nodes/failure_classifier.py` (FailureClassification) | Classify 8 failure categories | `bdd:run` inner retry loop |
| `agent/nodes/reporter.py` | Result summary | `bdd:run` final output |
| `agent/nodes/recorder_processor.py` (ProcessedStep) | Raw recorder events → UTML | `bdd:record` step 3 |
| `api/routes/recorder.py` (GeneratedMetadata, RefinedStepsResponse) | Metadata + refinement from recording | `bdd:record` step 3 |
| `agent/nodes/executor.py` | Placeholder — real exec via playwright-http | N/A |

### MCP surface used

- `list_projects` — UI panel
- `list_test_cases` — UI panel
- `run_test` — UI panel + SSE stream; **invoked without `retryMode: "intelligent"`** so retries happen client-side in `bdd:run` (no backend LLM call)
- `run_natural_test` — **not used**; replaced by `bdd:write` + `bdd:run`

### Plugin repo layout

```
checkmate-bdd-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── setup/SKILL.md
│   ├── stack/SKILL.md
│   ├── write/SKILL.md
│   ├── generate/SKILL.md      (new)
│   ├── record/SKILL.md        (new)
│   ├── run/SKILL.md
│   └── ci/SKILL.md
├── docker/
│   └── docker-compose.yml
├── templates/
│   ├── claude-md-snippet.md
│   ├── checkmate.config.json
│   └── ci-workflow.yml
├── scripts/
│   ├── clone-deps.sh
│   ├── wait-for-ready.sh
│   ├── native-start.sh
│   ├── native-stop.sh
│   └── run-suite.py
└── docs/superpowers/
    ├── specs/2026-04-17-checkmate-bdd-plugin-design.md
    └── plans/2026-04-17-checkmate-bdd-plugin.md
```

### Consuming repo layout

```
tests/e2e/
├── checkmate.config.json
└── scenarios/
    └── <feature-group>/
        └── <scenario-name>.json   (UTML)
```

---

## Section 2: `checkmate.config.json` schema

```json
{
  "base_url": "http://localhost:7792",
  "stack": {
    "start_command": "cargo run --manifest-path core/Cargo.toml",
    "ready_url": "http://localhost:7792/api/health",
    "ready_timeout_secs": 30
  },
  "services": {
    "prefer_docker": true
  },
  "bdd": {
    "verification_mode": "required",
    "run": {
      "max_retries": 2
    },
    "heal": {
      "auto_apply_threshold": 0.85
    }
  },
  "checkmate": {
    "project_name": "my-project",
    "url": "http://127.0.0.1:8000"
  }
}
```

### Fields

**`base_url`** — Base URL passed to UTML scenarios. Must be reachable after `start_command` completes.

**`stack.start_command`** — Shell command to start the application under test. Executed from the repo root.

**`stack.ready_url`** — Polled with exponential backoff until HTTP 200 or timeout. If absent, plugin waits `ready_timeout_secs` unconditionally.

**`stack.ready_timeout_secs`** — Hard timeout for app readiness. Default: 30.

**`services.prefer_docker`** — If true and Docker is available, run services as containers. Default: true.

**`bdd.verification_mode`** — `required` (verification blocks completion) or `prompted` (reminder only).

**`bdd.run.max_retries`** — Number of heal-and-retry attempts on scenario failure. Default: 2 (matches checkmate-mcp upstream default).

**`bdd.heal.auto_apply_threshold`** — If `HealSuggestion.confidence` ≥ this value, apply healed steps automatically; else show diff and prompt user. Default: 0.85 (matches healer.py guidance).

**`checkmate.project_name`** — Name of the project created in checkmate.

**`checkmate.url`** — URL of the checkmate backend. Default: `http://127.0.0.1:8000`.

---

## Section 3: Skill design

All AI-bearing skills follow the **backend source pointer pattern**: the skill tells Claude which backend file to read; Claude uses the Pydantic schema and system prompt in that file verbatim as the contract. SKILL.md never restates schemas or prompts.

| Skill | Purpose | Backend files referenced |
|-------|---------|--------------------------|
| `bdd:setup` | One-time init. Creates config, clones deps, verifies backend source readable, appends CLAUDE.md snippet. | — |
| `bdd:stack` | Start/stop/status stack + app under test. Docker or native. `up` pulls latest backend source. | — |
| `bdd:write` | Natural language → UTML scenario. Saves to `scenarios/`, registers in checkmate. | `agent/nodes/planner.py`, `agent/nodes/builder.py` |
| `bdd:generate` | Bulk-ideate test cases for a feature area. User picks which to materialize via `bdd:write`. | `agent/nodes/generator.py` |
| `bdd:run` | Execute scenario(s) via checkmate-mcp `run_test`. On failure: classify → heal → retry (≤ `max_retries`). Final summary. | `agent/nodes/failure_classifier.py`, `agent/nodes/healer.py`, `agent/nodes/reporter.py` |
| `bdd:record` | Start/stop browser recording via playwright-http. Refine raw events → UTML + metadata. | `agent/nodes/recorder_processor.py`, `api/routes/recorder.py` (GeneratedMetadata, RefinedStepsResponse) |
| `bdd:ci` | Emit GitHub Actions workflow YAML. | — (headless `run-suite.py` is non-AI) |

### `bdd:run` retry loop

1. Invoke `run_test` MCP tool without `retryMode: "intelligent"`. Collect SSE events.
2. If passed: go to step 6.
3. Read `agent/nodes/failure_classifier.py`. Produce `FailureClassification`. If category non-retryable or retry budget exhausted: go to step 6.
4. Read `agent/nodes/healer.py`. Produce `HealSuggestion` (healed_steps, changed_step_numbers, explanation, confidence).
5. If `confidence ≥ bdd.heal.auto_apply_threshold`: `PUT /api/test-cases/{id}` with healed steps, decrement retry budget, re-run (step 1). Else show diff, ask user to apply/skip/edit, then continue per user choice.
6. Read `agent/nodes/reporter.py`. Produce result summary. Print component-boundary hints derived from final `FailureClassification` (if any).

### `bdd:record` flow

1. `POST /api/projects/{id}/recorder/start` → browser opens, WS URL returned.
2. Connect WS `/api/projects/{id}/recorder/ws`; accumulate raw events until user signals done.
3. `POST /api/projects/{id}/recorder/stop` → returns final raw event list.
4. Read `agent/nodes/recorder_processor.py` + `api/routes/recorder.py`. Claude produces refined `ProcessedStep[]` + `GeneratedMetadata` matching those models.
5. Show refined scenario; iterate with user.
6. Save `tests/e2e/scenarios/<group>/<name>.json` and `POST /api/test-cases/project/{id}/`.

---

## Section 4: Superpowers integration

The plugin hooks into two points in the superpowers workflow. Consuming repos add the hook instructions to their `CLAUDE.md` (applied by `bdd:setup`):

### Hook 1: After brainstorming → before writing-plans

After `superpowers:brainstorming` produces an approved design, run `bdd:write` (or `bdd:generate` → pick → `bdd:write`) for each significant behavior before invoking `superpowers:writing-plans`. Scenarios become acceptance criteria for the implementation plan.

### Hook 2: Inside verification-before-completion

- `verification_mode: required` → `superpowers:verification-before-completion` must include `bdd:run all` passing before work is declared complete.
- `verification_mode: prompted` → verification skill reminds developer to run `bdd:run` and asks for confirmation, but does not block.

---

## Section 5: Docker compose

See `docker/docker-compose.yml`. Key notes:
- `OPENAI_API_KEY` is **not set and not needed**. All AI in the plugin path runs inline in Claude; checkmate's own AI nodes are bypassed.
- `ENCRYPTION_KEY` has a placeholder default — consuming projects should set this in their `.env` or CI secrets.
- All three service images use `build:` contexts pointing at `${PLUGIN_DEPS_DIR:-~/.checkmate-bdd}`, populated by `scripts/clone-deps.sh`. No registry images are required.

---

## Open questions

1. **Recorder WS client.** `bdd:record` needs a WebSocket client for `/api/projects/{id}/recorder/ws`. Python `websockets` library (added to the Python deps already required by `run-suite.py`) vs. shelling out to `websocat`. Decide at plan time. Default lean: `websockets`.

2. **Backend source staleness.** Skills reference `~/.checkmate-bdd/checkmate/` at runtime. If user hasn't run `bdd:stack up` recently the source may be stale. Resolution: `bdd:stack up` is responsible for `git pull`; other skills fail fast with "run bdd:stack up first" if the directory is missing. Document clearly.

3. **Output validation.** Should skills validate Claude's output against the Pydantic model before persisting or calling the backend? Leaning yes — a small helper that imports the model from `~/.checkmate-bdd/checkmate/`, validates, and raises on drift. Keeps the spec contract enforced without duplication.

4. **`run_test` retry override.** Confirm that omitting `retry` in the `run_test` payload disables backend intelligent retry (so no backend LLM call happens). Per `src/checkmate-client.ts:145-151`, `retry` is only added when `maxRetries` is passed — safe to omit. Verify at implementation time.
