# checkmate-bdd-plugin

A coding agent plugin for BDD scenario authoring and E2E testing. Project-agnostic — works with any web application, any language, any framework.

All AI work runs **inline in your coding agent** using the upstream backend's own prompts and Pydantic schemas. No OpenAI API key. No separate AI service. No prompt drift.

Works natively with Claude Code. Also supports GitHub Copilot, Gemini CLI, OpenAI Codex, and other agents via shared instruction files.

## How it works

The plugin owns three services — [checkmate](https://github.com/ksankaran/checkmate), [playwright-http](https://github.com/ksankaran/playwright-http), and [checkmate-mcp](https://github.com/ksankaran/checkmate-mcp) — and replaces every OpenAI-dependent feature in those services with an agent skill that reads the backend's own source at runtime.

```
Your app (native)
     ↑
checkmate :8000  ←  playwright-http :8932
     ↑
checkmate-mcp :3003
     ↑
your coding agent (all AI runs here, reads upstream source from ~/.checkmate-bdd/)
```

Your application always runs natively. The plugin starts it via `stack.start_command` in your config and never containerizes it.

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `bdd:setup` | Once per project | Create config, clone upstream deps, verify backend source, register MCP server, append agent instruction snippet |
| `bdd:stack` | `up` / `down` / `status` | Start/stop checkmate + playwright-http + checkmate-mcp + your app. Pulls latest backend source on `up`. |
| `bdd:write` | Before implementing a feature | Natural language → UTML scenario. Reads `planner.py` + `builder.py` from upstream source. |
| `bdd:generate` | Starting a new feature area | Bulk-ideate acceptance scenarios. Reads `generator.py`. Pick which to materialize via `bdd:write`. |
| `bdd:run` | After implementation | Execute scenarios. On failure: classify → heal → retry (up to `max_retries`). Reads `failure_classifier.py` + `healer.py` + `reporter.py`. |
| `bdd:record` | Complex UI flows | Record a browser session, refine raw events into clean UTML. Reads `recorder_processor.py` + `recorder.py`. |
| `bdd:ci` | Once per repo | Generate GitHub Actions workflow. CI uses `run-suite.py` directly — no external agent in the loop. |

## Slash commands

| Command | Args | Equivalent |
|---------|------|------------|
| `/bdd-stack` | `up` \| `down` \| `status` | `bdd:stack` skill |
| `/bdd-run` | scenario \| group \| `all` | `bdd:run` skill |
| `/bdd-ci` | — | `bdd:ci` skill |

## Agent

`bdd-scenario-writer` — specialist subagent for multi-agent workflows. Receives a feature description, returns ready-to-save UTML JSON without interactive back-and-forth. Used by `subagent-driven-development` plans that need BDD scenarios written before implementation.

## Hooks

| Hook | Event | Behavior |
|------|-------|----------|
| `register-scenario` | `PostToolUse/Write` | Auto-registers any file written to `tests/e2e/scenarios/` in checkmate (if stack is running) |
| `check-verification` | `Stop` | If `verification_mode: required` and checkmate is running, blocks the agent from finishing until `bdd:run all` passes |

## Installation

```bash
# Install the plugin
claude plugin install https://github.com/joshmullikin/checkmate-bdd-plugin

# Or add via marketplace
claude plugin marketplace add joshmullikin/checkmate-bdd-plugin
claude plugin install checkmate-bdd@checkmate-bdd-marketplace
```

Then initialize in your project:

```bash
claude -p "bdd:setup"
```

`bdd:setup` will ask a few questions, clone the upstream service repos to `~/.checkmate-bdd/`, wire the MCP server into your agent's settings, and append usage instructions to whichever agent instruction files exist in your project (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`).

## Agent support

The plugin ships with symlinked instruction files so every supported agent reads the same content — no duplication:

| File | Agent |
|------|-------|
| `CLAUDE.md` | Claude Code (canonical source) |
| `AGENTS.md` | OpenAI Codex and generic agents |
| `GEMINI.md` | Gemini CLI |
| `.github/copilot-instructions.md` | GitHub Copilot |

`AGENTS.md`, `GEMINI.md`, and `.github/copilot-instructions.md` are git symlinks pointing to `CLAUDE.md`. `bdd:setup` replicates the same pattern in your project.

## Typical workflow

```
1. bdd:setup          ← once per project
2. bdd:stack up       ← start services
3. bdd:generate       ← ideate scenarios for a feature
4. bdd:write          ← materialize each scenario (before writing code)
5. [implement]
6. bdd:run all        ← verify
7. bdd:stack down     ← stop services
```

In CI, steps 2–6 run headlessly via the generated GitHub Actions workflow.

## Configuration

`tests/e2e/checkmate.config.json` (created by `bdd:setup`):

```json
{
  "base_url": "http://localhost:3000",
  "plugin_root": "/path/to/installed/plugin",
  "stack": {
    "start_command": "npm start",
    "ready_url": "http://localhost:3000/health",
    "ready_timeout_secs": 30
  },
  "services": {
    "prefer_docker": true
  },
  "bdd": {
    "verification_mode": "required",
    "run": { "max_retries": 2 },
    "heal": { "auto_apply_threshold": 0.85 }
  },
  "checkmate": {
    "project_name": "my-project",
    "url": "http://127.0.0.1:8000"
  }
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `bdd.verification_mode` | `required` | `required` blocks the agent from finishing until `bdd:run all` passes; `prompted` is a reminder only |
| `bdd.run.max_retries` | `2` | Heal-and-retry attempts on scenario failure |
| `bdd.heal.auto_apply_threshold` | `0.85` | Auto-apply healed steps if confidence ≥ this; otherwise show diff and ask |
| `services.prefer_docker` | `true` | Use Docker if available; fall back to native (uv + node) |

## Scenario format

Scenarios are stored as UTML JSON in `tests/e2e/scenarios/<feature-group>/<name>.json`:

```json
{
  "base_url": "http://localhost:3000",
  "steps": [
    { "action": "navigate", "target": null, "value": "/login", "description": "Go to login page" },
    { "action": "type", "target": "Email", "value": "user@example.com", "description": "Enter email" },
    { "action": "type", "target": "Password", "value": "secret", "description": "Enter password" },
    { "action": "click", "target": "Sign In", "value": null, "description": "Submit login form" },
    { "action": "assert_url", "target": null, "value": ".*dashboard.*", "description": "Verify redirect" }
  ]
}
```

Your agent generates UTML by reading the upstream backend's action grammar directly — the rules never drift.

## Requirements

- A supported coding agent (Claude Code, Gemini CLI, GitHub Copilot, or OpenAI Codex)
- Docker **or** Python 3.11+ · uv · Node 22+
- git (for cloning upstream service repos)

## Upstream services

This plugin clones and manages (but never modifies) these repos:

| Repo | Role |
|------|------|
| [ksankaran/checkmate](https://github.com/ksankaran/checkmate) | Test case store, execution coordinator, recorder proxy |
| [ksankaran/playwright-http](https://github.com/ksankaran/playwright-http) | Playwright browser executor |
| [ksankaran/checkmate-mcp](https://github.com/ksankaran/checkmate-mcp) | MCP server (UI panels + `run_test` tool) |

The plugin uses only their existing non-AI HTTP endpoints and MCP tools. Upstream repos are never modified.

## License

MIT
