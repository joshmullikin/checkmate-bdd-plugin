---
name: bdd:setup
description: Use when initializing BDD E2E testing in a project for the first time, or re-configuring. Creates tests/e2e/checkmate.config.json, clones service dependencies, and wires into CLAUDE.md. Idempotent — safe to re-run.
---

# bdd:setup

One-time initialization of the BDD test stack. Idempotent — safe to re-run.

## Step 1: Resolve plugin root

Find the absolute path to the plugin's installed directory. Run:

```bash
claude plugin list
```

Look for `checkmate-bdd` in the output and note its installed path. Store as `PLUGIN_ROOT`.

If the command is unavailable, resolve manually: this SKILL.md is at `<PLUGIN_ROOT>/skills/setup/SKILL.md`. The plugin root is two directories up.

## Step 2: Check for existing config

Look for `tests/e2e/checkmate.config.json` in the current repo root.

If it exists, read it and offer to update specific fields. Skip to Step 4 for fields already present.

## Step 3: Collect config values (if no existing config)

Ask the following questions **one at a time**:

1. "What is the base URL of your application? (e.g. http://localhost:3000)"
2. "What shell command starts your application? (e.g. npm start)"
3. "What URL should I poll to know your app is ready? (e.g. http://localhost:3000/health) — press enter to skip"
4. "How many seconds to wait for the app to be ready? [default: 30]"
5. "Should BDD scenario results be **required** to pass before marking implementation complete (`required`), or just a reminder (`prompted`)? [required/prompted, default: required]"

## Step 4: Check Docker availability

```bash
docker info > /dev/null 2>&1
```

- Exit 0: ask "Docker is available — run services as containers? [Y/n]"
- Exit non-0: services will run natively. Note this.

## Step 5: Write tests/e2e/checkmate.config.json

Create `tests/e2e/` directory if absent:

```bash
mkdir -p tests/e2e tests/e2e/scenarios
```

Write `tests/e2e/checkmate.config.json`:

```json
{
  "base_url": "<user answer>",
  "plugin_root": "<PLUGIN_ROOT>",
  "stack": {
    "start_command": "<user answer>",
    "ready_url": "<user answer or omit if skipped>",
    "ready_timeout_secs": <user answer or 30>
  },
  "services": {
    "prefer_docker": <true if Docker available and user said yes, else false>
  },
  "bdd": {
    "verification_mode": "<required or prompted>",
    "run": { "max_retries": 2 },
    "heal": { "auto_apply_threshold": 0.85 }
  },
  "checkmate": {
    "project_name": "<name of the current directory>",
    "url": "http://127.0.0.1:8000"
  }
}
```

## Step 6: Clone upstream service repos

```bash
bash <PLUGIN_ROOT>/scripts/clone-deps.sh
```

This clones checkmate, playwright-http, and checkmate-mcp to `~/.checkmate-bdd/`. Takes 1–2 minutes on first run; fast on subsequent runs.

## Step 7: Verify backend source readable

```bash
ls ~/.checkmate-bdd/checkmate/agent/nodes/builder.py
ls ~/.checkmate-bdd/checkmate/agent/nodes/healer.py
ls ~/.checkmate-bdd/checkmate/agent/nodes/recorder_processor.py
```

All three must exist. If any are missing, run Step 6 again. If the directory is still wrong, check `scripts/clone-deps.sh` output for errors.

## Step 8: Check native dependencies

Run and print missing-install instructions for anything absent:

```bash
python3 --version    # need 3.11+
uv --version         # install: pip install uv
node --version       # need 22+
git --version        # need any version
```

If native mode (not Docker): also install playwright browsers after clone:

```bash
cd ~/.checkmate-bdd/playwright-http && uv run playwright install chromium
```

## Step 9: Pull/build Docker images (Docker mode only)

Pull the registry images and build checkmate-mcp from source:

```bash
docker pull ghcr.io/joshmullikin/checkmate:latest
docker pull ghcr.io/joshmullikin/playwright-http:latest
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml build checkmate-mcp
```

The pulls are fast. The checkmate-mcp build takes 1–2 minutes on first run and is cached after that.

## Step 10: Register checkmate-mcp as a Claude Code MCP server

Read `~/.claude/settings.json`. Merge the following under `mcpServers` (do not overwrite existing entries):

```json
{
  "mcpServers": {
    "checkmate": {
      "type": "http",
      "url": "http://127.0.0.1:3003/mcp"
    }
  }
}
```

Write the merged file back.

## Step 11: Append BDD section to agent instruction files

Read `<PLUGIN_ROOT>/templates/claude-md-snippet.md`. This is the canonical snippet.

For each agent instruction file found in the repo root, ask once:
"Append the BDD testing section to agent instruction files? [Y/n]"

If yes, append the canonical snippet to every file that exists:

| File | Agent platform |
|---|---|
| `CLAUDE.md` | Claude Code |
| `AGENTS.md` | OpenAI Codex / generic agents |
| `GEMINI.md` | Gemini CLI |
| `.github/copilot-instructions.md` | GitHub Copilot |

Create any missing files only if the user confirms ("Also create AGENTS.md? [Y/n]").
Do not create files for platforms the user is not using.

The same snippet content goes into every file — no platform-specific variants needed.

## Step 12: Confirm completion

Print:
```
✓ BDD setup complete.

Next steps:
  1. Run `bdd:stack up` to start the test services.
  2. Run `bdd:generate` or `bdd:write` to author your first scenario.
  3. Run `bdd:run all` to execute scenarios.
```
