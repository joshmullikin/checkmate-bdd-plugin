# checkmate-bdd-plugin

A Claude Code plugin for BDD scenario authoring and E2E testing. Project-agnostic — works with any web application.

## What it does

Provides five skills that add BDD-driven development to any project:

| Skill | Purpose |
|-------|---------|
| `bdd:setup` | One-time initialization — config, deps, CLAUDE.md wiring |
| `bdd:stack` | Start/stop/status the test environment (Docker or native) |
| `bdd:write` | Write UTML scenarios from natural language (Claude generates, no OpenAI key needed) |
| `bdd:run` | Execute scenarios, stream output, report failures with component-boundary hints |
| `bdd:ci` | Generate GitHub Actions workflow YAML |

## Service stack

The plugin manages:
- [checkmate](https://github.com/ksankaran/checkmate) — test case store + execution coordinator
- [playwright-http](https://github.com/ksankaran/playwright-http) — Playwright browser executor
- [checkmate-mcp](https://github.com/ksankaran/checkmate-mcp) — MCP server exposing checkmate to Claude

Your application runs natively — the plugin never containerizes it.

## Installation

```bash
claude plugin install https://github.com/joshmullikin/checkmate-bdd-plugin
```

Then in your project:

```bash
# Initialize BDD testing
claude -p "bdd:setup"
```

## Requirements

- Docker (recommended) **or** Python 3.11+ + uv + Node 22+
- Claude Code

## License

MIT
