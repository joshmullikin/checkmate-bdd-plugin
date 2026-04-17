# checkmate-bdd-plugin — Agent Instructions

## What this repo is

A Claude Code plugin that adds BDD scenario authoring and E2E testing to any project.
Project-agnostic — no knowledge of any specific application.

## Superpowers

This project uses [Superpowers](https://github.com/obra/superpowers) as its SDD framework.
Verify it is installed before starting any work:

```bash
claude plugin list
```

If missing:
```bash
claude plugin install https://github.com/obra/superpowers
```

## Repo layout

```
checkmate-bdd-plugin/
├── .claude-plugin/plugin.json   # Claude Code plugin manifest
├── skills/*/SKILL.md            # One skill per subdirectory
├── docker/docker-compose.yml    # Build-context compose (no registry images)
├── scripts/                     # Bash + Python helpers called by skills
├── templates/                   # Files emitted/appended by skills
└── docs/superpowers/
    ├── specs/                   # Design spec
    └── plans/                   # Implementation plan
```

## Implementation plan

`docs/superpowers/plans/2026-04-17-checkmate-bdd-plugin.md`

Use `superpowers:subagent-driven-development` to execute it task by task.

## Key constraints

**Project-agnostic.** Skills must not reference any specific application, framework, or language.

**No registry images.** Upstream repos (checkmate, playwright-http, checkmate-mcp) have Dockerfiles but no published images. Docker compose uses `build:` contexts pointing at `~/.checkmate-bdd/` (cloned by `scripts/clone-deps.sh`).

**Claude generates UTML.** `bdd:write` never calls checkmate's AI agent. Claude generates UTML inline from the user's natural language description.

**OpenAI key is optional.** No plugin skill requires it. It only enables checkmate's own AI UI features.

**MCP registration is user-scoped.** `bdd:setup` writes checkmate-mcp to `~/.claude/settings.json` under `mcpServers`, not to a project-local file.

## Platform

Windows 11, bash shell. Use Unix shell syntax (forward slashes, `/dev/null` not `NUL`). Never use PowerShell.

## Rust toolchain

Not applicable — this repo has no Rust. Scripts are Bash and Python 3.

## Testing the plugin locally

```bash
claude plugin install file://$(pwd)
```

Then test each skill in a scratch project:
```bash
claude -p "bdd:setup"
claude -p "bdd:stack up"
claude -p "bdd:write"
claude -p "bdd:run all"
claude -p "bdd:stack down"
```

## Agent action log

After completing any implementation task, write a summary to `docs/superpowers/actions/`.
Filename matches the plan file being acted on.
