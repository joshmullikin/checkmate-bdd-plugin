# checkmate-bdd-plugin Design

**Date:** 2026-04-17
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

## Non-goals

- Containerizing the application under test (plugin never owns the app stack)
- Providing scenario templates (deferred to Option C / future)
- Managing any app-specific infrastructure

---

## Section 1: Architecture

### Service stack

The plugin owns three services:

| Service | Port | Role |
|---------|------|------|
| checkmate | 8000 | AI agent + project manager + test case store |
| playwright-http | 8932 | Playwright executor (runs UTML) |
| checkmate-mcp | 3003 | MCP server exposing checkmate to Claude |

When Docker is available (`docker info` succeeds), all three run as containers via `docker/docker-compose.yml`. Otherwise they run natively — checkmate and playwright-http via Python/uv, checkmate-mcp via Node/npm.

The application under test always runs natively. The plugin starts it by executing `stack.start_command` from `checkmate.config.json` and polls `stack.ready_url` until ready. It never attempts to containerize the app.

### Plugin repo layout

```
checkmate-bdd-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── setup/SKILL.md
│   ├── stack/SKILL.md
│   ├── write/SKILL.md
│   ├── run/SKILL.md
│   └── ci/SKILL.md
├── docker/
│   └── docker-compose.yml
├── templates/
│   ├── claude-md-snippet.md
│   └── ci-workflow.yml
├── scripts/
│   └── wait-for-ready.sh
└── docs/superpowers/specs/
    └── 2026-04-17-checkmate-bdd-plugin-design.md
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
    "verification_mode": "required"
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

**`services.prefer_docker`** — If true and Docker is available, run services as containers. If false or Docker unavailable, run natively. Default: true.

**`bdd.verification_mode`** — Set during `bdd:setup`. Values: `required` (verification blocks completion), `prompted` (reminder but skippable). Asked once during initialization.

**`checkmate.project_name`** — Name of the project created in checkmate.

**`checkmate.url`** — URL of the checkmate backend. Default: `http://127.0.0.1:8000`.

---

## Section 3: Skill design

See individual `skills/*/SKILL.md` files for full detail. Summary:

| Skill | Purpose |
|-------|---------|
| `bdd:setup` | One-time initialization. Creates config, installs deps, appends CLAUDE.md snippet. |
| `bdd:stack` | Start/stop/status the service stack + app under test. Docker or native. |
| `bdd:write` | Claude generates UTML from natural language. Saves to `scenarios/`. No OpenAI required. |
| `bdd:run` | Execute scenarios via checkmate-mcp. Stream output. Failure hints by component boundary. |
| `bdd:ci` | Emit GitHub Actions workflow YAML to copy into `.github/workflows/bdd.yml`. |

---

## Section 4: Superpowers integration

The plugin hooks into two points in the superpowers workflow. Consuming repos add the hook instructions to their `CLAUDE.md` (applied by `bdd:setup`):

### Hook 1: After brainstorming → before writing-plans

After `superpowers:brainstorming` produces an approved design, run `bdd:write` for each significant behavior before invoking `superpowers:writing-plans`. Scenarios become acceptance criteria for the implementation plan.

### Hook 2: Inside verification-before-completion

- `verification_mode: required` → `superpowers:verification-before-completion` must include `bdd:run all` passing before work is declared complete.
- `verification_mode: prompted` → verification skill reminds developer to run `bdd:run` and asks for confirmation, but does not block.

---

## Section 5: Docker compose

See `docker/docker-compose.yml`. Key notes:
- `OPENAI_API_KEY` is optional — checkmate's AI features are disabled if absent, but execution works normally.
- `ENCRYPTION_KEY` has a placeholder default — consuming projects should set this in their `.env` or CI secrets.
- checkmate-mcp image (`ghcr.io/joshmullikin/checkmate-mcp`) must be published as part of this repo's CI.

---

## Open questions

1. **checkmate/playwright-http Docker images** — do upstream repos publish images to `ghcr.io/ksankaran/`? If not, the plugin's `docker-compose.yml` must use `build:` contexts pointing at cloned source. Verify before implementing `bdd:stack`.

2. **checkmate-mcp MCP registration** — `bdd:setup` should write the MCP server entry to `~/.claude/mcp.json` (user-scoped). Confirm the correct config key format for Claude Code.

3. **OPENAI_API_KEY** — not required for any plugin skill. Optional for checkmate's own AI UI. Document clearly in README.

4. **checkmate-mcp image** — needs to be built and published by this repo's CI (`ghcr.io/joshmullikin/checkmate-mcp`). Part of implementation plan.
