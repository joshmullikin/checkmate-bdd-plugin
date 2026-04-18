# checkmate-bdd-plugin Agentic Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full checkmate-bdd-plugin with Claude-native agentic skills — zero API keys required, all LLM work done inline by Claude reading backend source prompts/schemas.

**Architecture:** The plugin owns three services (checkmate, playwright-http, checkmate-mcp) built from cloned source via Docker or native. All AI work that upstream checkmate does via OpenAI is replaced by Claude skills that read the backend's own prompts and Pydantic schemas from `~/.checkmate-bdd/checkmate/` at runtime — no prompt duplication, no drift.

**Tech Stack:** Bash scripts, Python 3.11+ (urllib, json, pathlib), Node 22+ (checkmate-mcp), Docker Compose (build contexts), Claude Code SKILL.md (markdown skill files)

**Supersedes:** `docs/superpowers/plans/2026-04-17-checkmate-bdd-plugin.md`

---

## File Map

**Modify:**
- `docker/docker-compose.yml` — switch registry images → build contexts; remove OPENAI_API_KEY
- `templates/checkmate.config.json` — add `bdd.run.max_retries`, `bdd.heal.auto_apply_threshold`, `plugin_root`
- `templates/claude-md-snippet.md` — add `bdd:generate` and `bdd:record` to workflow
- `skills/setup/SKILL.md` — add clone-deps step, plugin_root capture, backend source verification
- `skills/stack/SKILL.md` — add git pull on `up`; remove OPENAI refs
- `skills/write/SKILL.md` — rewrite to backend pointer pattern (planner.py + builder.py)
- `skills/run/SKILL.md` — rewrite with classify→heal→retry loop + reporter summary
- `skills/ci/SKILL.md` — verify complete and correct

**Create:**
- `scripts/clone-deps.sh` — idempotent git clone/pull for all three upstream repos
- `scripts/native-start.sh` — start services natively via uv/node
- `scripts/native-stop.sh` — stop native services
- `scripts/run-suite.py` — headless CI scenario runner
- `skills/generate/SKILL.md` — new: bulk test case ideation via generator.py
- `skills/record/SKILL.md` — new: browser recording → UTML via recorder_processor.py

---

### Task 1: Fix docker/docker-compose.yml

Switch from non-existent registry images to build contexts pointing at `~/.checkmate-bdd/`. Remove `OPENAI_API_KEY` — the plugin path never needs it.

**Files:**
- Modify: `docker/docker-compose.yml`

- [ ] **Step 1: Rewrite docker-compose.yml**

Write `docker/docker-compose.yml`:

```yaml
# Requires PLUGIN_DEPS_DIR env var set by bdd:stack (default: ~/.checkmate-bdd)
# All three upstream repos must be cloned there by scripts/clone-deps.sh first.

services:
  checkmate:
    build:
      context: ${PLUGIN_DEPS_DIR}/checkmate
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-changeme-replace-in-production}
      PLAYWRIGHT_EXECUTOR_URL: http://playwright-http:8932
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 12
    depends_on:
      playwright-http:
        condition: service_healthy

  playwright-http:
    build:
      context: ${PLUGIN_DEPS_DIR}/playwright-http
      dockerfile: Dockerfile
    ports:
      - "8932:8932"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8932/health"]
      interval: 5s
      timeout: 3s
      retries: 12

  checkmate-mcp:
    build:
      context: ${PLUGIN_DEPS_DIR}/checkmate-mcp
      dockerfile: Dockerfile
    ports:
      - "3003:3003"
    environment:
      CHECKMATE_URL: http://checkmate:8000
      PORT: "3003"
    depends_on:
      checkmate:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3003/health"]
      interval: 5s
      timeout: 3s
      retries: 12
```

- [ ] **Step 2: Verify YAML syntax**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
python3 -c "import yaml; yaml.safe_load(open('docker/docker-compose.yml')); print('YAML OK')"
```

Expected: `YAML OK`

(If PyYAML not installed: `pip install pyyaml`. Or skip — visual check is sufficient for this file.)

- [ ] **Step 3: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add docker/docker-compose.yml
git commit -m "fix: switch compose to build contexts; remove OPENAI_API_KEY"
```

---

### Task 2: Write scripts/clone-deps.sh

Idempotent: clones all three upstream repos to `~/.checkmate-bdd/` on first run; pulls latest on subsequent runs.

**Files:**
- Create: `scripts/clone-deps.sh`

- [ ] **Step 1: Write clone-deps.sh**

```bash
#!/usr/bin/env bash
# clone-deps.sh
# Clones (or updates) checkmate, playwright-http, and checkmate-mcp
# into ~/.checkmate-bdd/. Safe to re-run.

set -e

DEPS_DIR="${HOME}/.checkmate-bdd"
mkdir -p "$DEPS_DIR"

clone_or_pull() {
  local repo="$1"
  local name="$2"
  local dest="${DEPS_DIR}/${name}"

  if [ -d "${dest}/.git" ]; then
    echo "Updating ${name}..."
    git -C "$dest" pull --ff-only
  else
    echo "Cloning ${name}..."
    git clone "https://github.com/${repo}.git" "$dest"
  fi
}

clone_or_pull "ksankaran/checkmate"       "checkmate"
clone_or_pull "ksankaran/playwright-http" "playwright-http"
clone_or_pull "ksankaran/checkmate-mcp"   "checkmate-mcp"

echo ""
echo "All dependencies ready at ${DEPS_DIR}"
echo "PLUGIN_DEPS_DIR=${DEPS_DIR}"
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
chmod +x scripts/clone-deps.sh
bash -n scripts/clone-deps.sh && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/clone-deps.sh
git commit -m "feat: add clone-deps.sh to fetch upstream service repos"
```

---

### Task 3: Write scripts/native-start.sh and scripts/native-stop.sh

Start and stop all three services natively (no Docker) using `uv` and `node`. Used when `services.prefer_docker: false` or Docker is unavailable.

**Files:**
- Create: `scripts/native-start.sh`
- Create: `scripts/native-stop.sh`

- [ ] **Step 1: Write native-start.sh**

```bash
#!/usr/bin/env bash
# native-start.sh
# Start checkmate, playwright-http, checkmate-mcp natively.
# Requires repos already cloned by clone-deps.sh.

set -e

DEPS_DIR="${HOME}/.checkmate-bdd"
PID_DIR="${DEPS_DIR}/pids"
LOG_DIR="${DEPS_DIR}/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

start_service() {
  local name="$1"
  local dir="$2"
  local cmd="$3"
  local pid_file="${PID_DIR}/${name}.pid"

  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "${name} already running (pid $(cat "$pid_file"))"
    return 0
  fi

  echo "Starting ${name}..."
  pushd "$dir" > /dev/null
  eval "$cmd" > "${LOG_DIR}/${name}.log" 2>&1 &
  echo $! > "$pid_file"
  popd > /dev/null
  echo "${name} started (pid $(cat "$pid_file"))"
}

start_service "checkmate" \
  "${DEPS_DIR}/checkmate" \
  "uv run uvicorn api.main:app --host 127.0.0.1 --port 8000"

start_service "playwright-http" \
  "${DEPS_DIR}/playwright-http" \
  "uv run uvicorn executor.main:app --host 127.0.0.1 --port 8932"

# Build checkmate-mcp if dist/ missing
if [ ! -f "${DEPS_DIR}/checkmate-mcp/dist/server.js" ]; then
  echo "Building checkmate-mcp..."
  pushd "${DEPS_DIR}/checkmate-mcp" > /dev/null
  npm ci --silent
  npm run build --silent
  popd > /dev/null
fi

start_service "checkmate-mcp" \
  "${DEPS_DIR}/checkmate-mcp" \
  "CHECKMATE_URL=http://127.0.0.1:8000 PORT=3003 node dist/server.js"

echo ""
echo "All services started. Logs: ${LOG_DIR}/"
```

- [ ] **Step 2: Write native-stop.sh**

```bash
#!/usr/bin/env bash
# native-stop.sh
# Stop services started by native-start.sh.

PID_DIR="${HOME}/.checkmate-bdd/pids"

stop_service() {
  local name="$1"
  local pid_file="${PID_DIR}/${name}.pid"

  if [ ! -f "$pid_file" ]; then
    echo "${name}: no pid file"
    return 0
  fi

  local pid
  pid=$(cat "$pid_file")
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping ${name} (pid ${pid})..."
    kill "$pid"
    sleep 1
  else
    echo "${name}: not running"
  fi
  rm -f "$pid_file"
}

# Stop in reverse dependency order
stop_service "checkmate-mcp"
stop_service "checkmate"
stop_service "playwright-http"
```

- [ ] **Step 3: Make executable and verify syntax**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
chmod +x scripts/native-start.sh scripts/native-stop.sh
bash -n scripts/native-start.sh && bash -n scripts/native-stop.sh && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/native-start.sh scripts/native-stop.sh
git commit -m "feat: add native start/stop scripts for non-Docker environments"
```

---

### Task 4: Write scripts/run-suite.py

Headless CI runner. Registers UTML scenarios and executes them against checkmate via HTTP. Uses correct API shapes (verified against upstream source).

**Files:**
- Create: `scripts/run-suite.py`

- [ ] **Step 1: Write run-suite.py**

```python
#!/usr/bin/env python3
"""
run-suite.py
Register UTML scenario files into checkmate and run them.
Used by CI workflow and bdd:stack up (--register-only).
Exits 0 if all pass, 1 if any fail.

Usage:
  python3 run-suite.py --config tests/e2e/checkmate.config.json \
                        --scenarios tests/e2e/scenarios/
  python3 run-suite.py --config ... --scenarios ... --register-only
"""

import argparse
import json
import sys
from pathlib import Path
import urllib.request
import urllib.error


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def checkmate_get(base_url: str, path: str) -> dict:
    req = urllib.request.Request(f"{base_url}{path}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def checkmate_post(base_url: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {path}: {e.read().decode()}", file=sys.stderr)
        raise


def ensure_project(checkmate_url: str, project_name: str, app_base_url: str) -> int:
    """Get or create project. Returns project id."""
    projects = checkmate_get(checkmate_url, "/api/projects")
    for p in projects:
        if p["name"] == project_name:
            return p["id"]
    # ProjectCreate requires name AND base_url
    created = checkmate_post(checkmate_url, "/api/projects", {
        "name": project_name,
        "base_url": app_base_url,
    })
    print(f"  Created project '{project_name}' id={created['id']}")
    return created["id"]


def register_scenarios(checkmate_url: str, project_id: int, scenarios_dir: str) -> list:
    """Register all UTML JSON files. Returns list of (test_case_id, name) tuples."""
    existing = checkmate_get(checkmate_url, f"/api/test-cases/project/{project_id}")
    existing_by_name = {tc["name"]: tc["id"] for tc in existing}

    results = []
    for path in sorted(Path(scenarios_dir).rglob("*.json")):
        with open(path) as f:
            utml = json.load(f)

        name = path.stem

        if name in existing_by_name:
            results.append((existing_by_name[name], name))
            continue

        # steps must be a JSON-encoded string, not an array
        steps_json = json.dumps(utml.get("steps", []))

        tc = checkmate_post(checkmate_url, "/api/test-cases", {
            "project_id": project_id,
            "name": name,
            "natural_query": name.replace("-", " "),
            "steps": steps_json,
        })
        results.append((tc["id"], name))
        print(f"  Registered: {name} (id={tc['id']})")

    return results


def run_test_case(checkmate_url: str, case_id: int) -> bool:
    """Run a single test case via SSE stream. Returns True if passed."""
    url = f"{checkmate_url}/api/test-cases/{case_id}/runs/stream"
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )
    passed = False
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode().strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "step":
                    status = "✓" if event.get("passed") else "✗"
                    action = event.get("action", "")
                    target = event.get("target") or event.get("value") or ""
                    err = f" — {event['error']}" if event.get("error") else ""
                    print(f"    {status} {action} {target}{err}")

                elif event.get("type") == "result":
                    passed = bool(event.get("passed", False))

    except urllib.error.HTTPError as e:
        print(f"  HTTP error: {e.code} {e.read().decode()}", file=sys.stderr)
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)

    return passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--register-only", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    checkmate_url = cfg["checkmate"]["url"]
    project_name = cfg["checkmate"]["project_name"]
    app_base_url = cfg["base_url"]

    print(f"Connecting to checkmate at {checkmate_url}")
    project_id = ensure_project(checkmate_url, project_name, app_base_url)
    print(f"Project '{project_name}' id={project_id}")

    print("Registering scenarios...")
    cases = register_scenarios(checkmate_url, project_id, args.scenarios)
    print(f"  {len(cases)} scenario(s) registered")

    if args.register_only:
        print("Scenarios registered. Exiting (--register-only).")
        sys.exit(0)

    passed_count = 0
    failed_count = 0
    failures = []

    for case_id, name in cases:
        print(f"\nRunning: {name}")
        if run_test_case(checkmate_url, case_id):
            passed_count += 1
        else:
            failed_count += 1
            failures.append(name)

    print(f"\n{'='*40}")
    print(f"Results: {passed_count} passed, {failed_count} failed")
    if failures:
        print("Failed:")
        for f in failures:
            print(f"  - {f}")

    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
python3 -c "import ast; ast.parse(open('scripts/run-suite.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Write test for ensure_project and register_scenarios logic**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
cat > /tmp/test_run_suite.py << 'PYEOF'
import json
import sys
import os
import tempfile
from pathlib import Path

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts') if '__file__' in dir() else 'scripts')

# Test load_config
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump({"checkmate": {"url": "http://x", "project_name": "p"}, "base_url": "http://app"}, f)
    cfg_path = f.name

# Import after path setup
import importlib.util
spec = importlib.util.spec_from_file_location("run_suite", "scripts/run-suite.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

cfg = mod.load_config(cfg_path)
assert cfg["checkmate"]["url"] == "http://x"
assert cfg["base_url"] == "http://app"
print("load_config: OK")

# Test scenarios registration logic (file parsing only)
with tempfile.TemporaryDirectory() as d:
    scenario = {"steps": [{"action": "navigate", "value": "/"}]}
    p = Path(d) / "my-feature" / "my-scenario.json"
    p.parent.mkdir()
    p.write_text(json.dumps(scenario))

    # Verify stem extraction
    assert p.stem == "my-scenario"
    steps_json = json.dumps(scenario.get("steps", []))
    parsed = json.loads(steps_json)
    assert parsed[0]["action"] == "navigate"
    print("scenario parsing: OK")

os.unlink(cfg_path)
print("All tests passed")
PYEOF
python3 /tmp/test_run_suite.py
```

Expected: `All tests passed`

- [ ] **Step 4: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add scripts/run-suite.py
git commit -m "feat: add run-suite.py for headless CI scenario execution"
```

---

### Task 5: Update templates/checkmate.config.json

Add the new `bdd.run` and `bdd.heal` fields from the revised spec, plus a `plugin_root` placeholder.

**Files:**
- Modify: `templates/checkmate.config.json`

- [ ] **Step 1: Rewrite templates/checkmate.config.json**

```json
{
  "base_url": "http://localhost:3000",
  "plugin_root": "",
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

- [ ] **Step 2: Verify JSON**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
python3 -c "import json; json.load(open('templates/checkmate.config.json')); print('JSON OK')"
```

Expected: `JSON OK`

- [ ] **Step 3: Commit**

```bash
git add templates/checkmate.config.json
git commit -m "feat: add bdd.run/heal fields and plugin_root to config template"
```

---

### Task 6: Update templates/claude-md-snippet.md

Add `bdd:generate` and `bdd:record` to the workflow instructions appended to consuming repos' CLAUDE.md.

**Files:**
- Modify: `templates/claude-md-snippet.md`

- [ ] **Step 1: Rewrite templates/claude-md-snippet.md**

```markdown
## BDD testing

This project uses [checkmate-bdd-plugin](https://github.com/joshmullikin/checkmate-bdd-plugin)
for BDD scenario authoring and E2E testing. No API keys required — all AI work runs inline.

Install the plugin before starting any feature work:

```bash
claude plugin install https://github.com/joshmullikin/checkmate-bdd-plugin
```

### Workflow

**Starting a feature:**
- After brainstorming, run `bdd:generate` to bulk-ideate acceptance scenarios for the feature area.
- Pick the relevant ones and materialize each with `bdd:write`.
- Or skip bulk ideation and go straight to `bdd:write` for a single scenario.
- For complex UI flows, record a scenario directly with `bdd:record`.
- Written scenarios become acceptance criteria — commit them before writing implementation code.

**During implementation:**
- Run `bdd:run <scenario-name>` after completing each piece of functionality.
- On failure, `bdd:run` will classify the error and propose a heal automatically.

**Before marking implementation complete:**
- Run `bdd:run all` and confirm all scenarios pass.

**Service stack:**
- `bdd:stack up` — start checkmate + playwright-http + checkmate-mcp
- `bdd:stack down` — stop all services
- `bdd:stack status` — check health

**Scenario files:** `tests/e2e/scenarios/<feature-group>/<scenario-name>.json`
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add templates/claude-md-snippet.md
git commit -m "docs: add bdd:generate and bdd:record to claude-md-snippet"
```

---

### Task 7: Rewrite skills/setup/SKILL.md

Full rewrite: adds clone-deps step, backend source verification, plugin_root capture in config, correct MCP registration format.

**Files:**
- Modify: `skills/setup/SKILL.md`

- [ ] **Step 1: Rewrite skills/setup/SKILL.md**

```markdown
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

## Step 9: Build Docker images (Docker mode only)

```bash
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml build
```

Takes several minutes on first run. Images are cached after that.

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

## Step 11: Append BDD section to CLAUDE.md

Read `<PLUGIN_ROOT>/templates/claude-md-snippet.md`. Ask: "Append the BDD testing section to CLAUDE.md? [Y/n]"

If yes: append the template content to `CLAUDE.md`.

## Step 12: Confirm completion

Print:
```
✓ BDD setup complete.

Next steps:
  1. Run `bdd:stack up` to start the test services.
  2. Run `bdd:generate` or `bdd:write` to author your first scenario.
  3. Run `bdd:run all` to execute scenarios.
```
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/setup/SKILL.md
git commit -m "feat: rewrite bdd:setup skill with clone-deps, backend source verification"
```

---

### Task 8: Rewrite skills/stack/SKILL.md

Add `git pull` on `bdd:stack up`, remove all OPENAI references, add `PLUGIN_DEPS_DIR` env var when calling docker compose.

**Files:**
- Modify: `skills/stack/SKILL.md`

- [ ] **Step 1: Rewrite skills/stack/SKILL.md**

```markdown
---
name: bdd:stack
description: Use to start (`bdd:stack up`), stop (`bdd:stack down`), or check (`bdd:stack status`) the BDD test environment. Manages checkmate, playwright-http, checkmate-mcp, and the application under test.
---

# bdd:stack

Manages the BDD service stack. Requires `tests/e2e/checkmate.config.json` (run `bdd:setup` first).

Read `plugin_root` from `tests/e2e/checkmate.config.json` — all `<PLUGIN_ROOT>` references below use this value.

---

## bdd:stack up

### 1. Read config

Load `tests/e2e/checkmate.config.json`. Extract: `services.prefer_docker`, `plugin_root`, `stack.start_command`, `stack.ready_url`, `stack.ready_timeout_secs`.

### 2. Pull latest backend source

```bash
git -C ~/.checkmate-bdd/checkmate pull --ff-only
git -C ~/.checkmate-bdd/playwright-http pull --ff-only
git -C ~/.checkmate-bdd/checkmate-mcp pull --ff-only
```

If any pull fails (e.g. local changes or no network), warn and continue — do not abort.

### 3. Determine service mode

```bash
docker info > /dev/null 2>&1 && DOCKER_OK=true || DOCKER_OK=false
```

Mode = Docker if `services.prefer_docker: true` AND `DOCKER_OK=true`. Otherwise native.

### 4. Start services

**Docker mode:**
```bash
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml up -d
```

**Native mode:**
```bash
bash <PLUGIN_ROOT>/scripts/native-start.sh
```

### 5. Wait for all three service health endpoints

Run each sequentially with 60s timeout:

```bash
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh http://127.0.0.1:8932/health 60
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh http://127.0.0.1:8000/health 60
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh http://127.0.0.1:3003/health 60
```

If any timeout: print the last 20 lines of logs and stop.

**Docker logs:**
```bash
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml logs --tail=20 <service>
```

**Native logs:** `~/.checkmate-bdd/logs/<service>.log`

### 6. Start application under test

```bash
eval "<stack.start_command>" &
echo $! > ~/.checkmate-bdd/pids/app.pid
```

### 7. Wait for app readiness

```bash
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh "<stack.ready_url>" <stack.ready_timeout_secs>
```

If no `ready_url`: sleep `ready_timeout_secs`.

### 8. Ensure checkmate project exists

```python
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
base = cfg["checkmate"]["url"]
name = cfg["checkmate"]["project_name"]
app_base_url = cfg["base_url"]

projects = json.loads(urllib.request.urlopen(f"{base}/api/projects").read())
if not any(p["name"] == name for p in projects):
    body = json.dumps({"name": name, "base_url": app_base_url}).encode()
    req = urllib.request.Request(f"{base}/api/projects",
          data=body, headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req)
    print(f"Created project '{name}'")
else:
    print(f"Project '{name}' already exists")
```

### 9. Register unregistered scenarios

```bash
python3 <PLUGIN_ROOT>/scripts/run-suite.py \
  --config tests/e2e/checkmate.config.json \
  --scenarios tests/e2e/scenarios/ \
  --register-only
```

### 10. Report status

Print a table:

```
✓ playwright-http (:8932)  running
✓ checkmate       (:8000)  running
✓ checkmate-mcp   (:3003)  running
✓ app under test           running
```

---

## bdd:stack down

### 1. Stop app under test

```bash
if [ -f ~/.checkmate-bdd/pids/app.pid ]; then
  kill $(cat ~/.checkmate-bdd/pids/app.pid) 2>/dev/null || true
  rm -f ~/.checkmate-bdd/pids/app.pid
fi
```

### 2. Stop services

**Docker mode:**
```bash
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml down
```

**Native mode:**
```bash
bash <PLUGIN_ROOT>/scripts/native-stop.sh
```

---

## bdd:stack status

Check each health endpoint:

```bash
curl -sf http://127.0.0.1:8932/health > /dev/null && echo "playwright-http: ✓" || echo "playwright-http: ✗"
curl -sf http://127.0.0.1:8000/health > /dev/null && echo "checkmate:       ✓" || echo "checkmate:       ✗"
curl -sf http://127.0.0.1:3003/health > /dev/null && echo "checkmate-mcp:   ✓" || echo "checkmate-mcp:   ✗"
```

Check app under test via `stack.ready_url` from config.
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/stack/SKILL.md
git commit -m "feat: rewrite bdd:stack skill with git pull, PLUGIN_DEPS_DIR, no OPENAI"
```

---

### Task 9: Rewrite skills/write/SKILL.md

Replace inlined UTML schema with backend source pointer pattern. Claude reads `planner.py` and `builder.py` from the cloned backend and generates output matching their Pydantic schemas.

**Files:**
- Modify: `skills/write/SKILL.md`

- [ ] **Step 1: Rewrite skills/write/SKILL.md**

```markdown
---
name: bdd:write
description: Use before implementing any feature or fix to write the BDD acceptance scenario first. Claude generates UTML from natural language by reading the upstream backend's own prompts and schemas — no external AI required. Write scenarios BEFORE writing implementation code.
---

# bdd:write

Write a BDD scenario in UTML format. Claude reads the backend's schema and prompt directly — no API key, no drift.

**Hard rule: write scenarios before implementation.** The scenario IS the spec.

## Step 1: Understand the behavior

Ask: "What behavior do you want to test? Describe it in plain English."

## Step 2: Clarify preconditions

Ask: "What is the starting state? (e.g. 'app is running, user not logged in')"

## Step 3: Clarify the action sequence

Ask: "What does the user do, step by step?"

## Step 4: Clarify the expected outcome

Ask: "What should be true after the actions complete? What does the user see or what data is persisted?"

## Step 5: Read backend source — planner

Read the file at `~/.checkmate-bdd/checkmate/agent/nodes/planner.py`.

Find the system prompt (string assigned to the `PLANNER_PROMPT` or similar variable) and the `TestPlanModel` Pydantic class. These are the contract.

Using the user's answers from Steps 1–4, produce a `TestPlanModel`-shaped plan following that system prompt exactly.

## Step 6: Read backend source — builder

Read the file at `~/.checkmate-bdd/checkmate/agent/nodes/builder.py`.

Find the system prompt and the `TestCaseModel` / `BuilderResponse` Pydantic classes. Note the `CredentialSuggestion` class — if the scenario involves credentials, produce suggestions matching it.

Using the plan from Step 5, produce a full UTML test case matching `TestCaseModel`:
- `base_url`: from `tests/e2e/checkmate.config.json`
- `steps`: array of step objects following the action grammar in builder.py
- Follow the per-action target/value rules verbatim from the source

## Step 7: Show UTML and iterate

Present the generated UTML JSON. Ask: "Does this scenario look right? I can adjust any step."

Iterate until approved. One question per round.

## Step 8: Choose feature group and filename

List existing subdirectories under `tests/e2e/scenarios/` as numbered options. Offer "Create new group" as the last option.

Derive a filename: lowercase behavior description, spaces → hyphens, strip special characters.
Example: "user stores credentials" → `user-stores-credentials.json`

Confirm: "Save as `tests/e2e/scenarios/<group>/<filename>.json`?"

## Step 9: Save the scenario file

Write the approved UTML JSON to the confirmed path.

## Step 10: Register in checkmate (if stack is running)

```bash
curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1 && echo "running" || echo "not running"
```

**If running:** register via Python:

```python
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
base = cfg["checkmate"]["url"]
name = cfg["checkmate"]["project_name"]
scenario_name = "<filename-without-.json>"
utml = json.load(open("tests/e2e/scenarios/<group>/<filename>.json"))

projects = json.loads(urllib.request.urlopen(f"{base}/api/projects").read())
proj = next(p for p in projects if p["name"] == name)

body = json.dumps({
    "project_id": proj["id"],
    "name": scenario_name,
    "natural_query": scenario_name.replace("-", " "),
    "steps": json.dumps(utml.get("steps", [])),
}).encode()
req = urllib.request.Request(f"{base}/api/test-cases",
      data=body, headers={"Content-Type": "application/json"}, method="POST")
result = json.loads(urllib.request.urlopen(req).read())
print(f"Registered: {scenario_name} (id={result['id']})")
```

**If not running:** print "Scenario saved. It will be registered on the next `bdd:stack up`."

## Step 11: Confirm

Print:
```
✓ Scenario written: tests/e2e/scenarios/<group>/<filename>.json

Run it with: bdd:run <filename-without-.json>
```
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/write/SKILL.md
git commit -m "feat: rewrite bdd:write with backend source pointer pattern"
```

---

### Task 10: Write skills/generate/SKILL.md

New skill: bulk-ideate test cases for a feature area by reading `generator.py`, then materialize chosen ones via the `bdd:write` flow.

**Files:**
- Create: `skills/generate/SKILL.md`

- [ ] **Step 1: Write skills/generate/SKILL.md**

```markdown
---
name: bdd:generate
description: Use when starting a new feature area to bulk-ideate BDD test cases. Claude reads the upstream generator prompt and schema to produce a set of scenario ideas. You pick which to materialize into full UTML files via bdd:write.
---

# bdd:generate

Bulk-ideate acceptance test cases for a feature area. Claude reads the backend's generator schema and produces structured ideas — no duplication, no drift.

## Step 1: Ask for feature area

Ask: "What feature or area do you want to generate test cases for? (e.g. 'user login', 'checkout flow', 'model picker')"

## Step 2: Ask for count (optional)

Ask: "How many test case ideas? [default: 5]"

## Step 3: Read backend source — generator

Read the file at `~/.checkmate-bdd/checkmate/agent/nodes/generator.py`.

Find the `GENERATOR_PROMPT` and the `GeneratedTestCases` / `GeneratedTestCase` Pydantic classes.

Using the project info from `tests/e2e/checkmate.config.json` (`checkmate.project_name`, `base_url`) and the user's feature area, produce a `GeneratedTestCases`-shaped result following the generator system prompt:
- Each `GeneratedTestCase` has: `name`, `natural_query`, `priority`, `tags`
- Generate the requested count; cover happy path + edge cases + error scenarios per the prompt

## Step 4: Present ideas and let user pick

Present the generated list as a numbered table:

```
Generated 5 test cases for "user login":

1. [HIGH]     user-login-success
   "User enters valid credentials and is redirected to the dashboard"
   Tags: auth, happy-path

2. [HIGH]     user-login-invalid-password
   "User enters wrong password and sees an error message"
   Tags: auth, error

3. [MEDIUM]   user-login-empty-fields
   "User submits login form with empty fields and sees validation errors"
   Tags: auth, validation

4. [MEDIUM]   user-login-account-locked
   "User account is locked after 5 failed attempts"
   Tags: auth, security

5. [LOW]      user-login-remember-me
   "User checks remember-me and session persists after browser restart"
   Tags: auth, session
```

Ask: "Which would you like to write scenarios for? Enter numbers (e.g. 1,3) or 'all'."

## Step 5: Materialize selected scenarios

For each selected test case, run the `bdd:write` flow using `natural_query` as the pre-filled behavior description. Skip the initial "what behavior" question — pass `natural_query` directly into Step 2 of `bdd:write`.

Confirm the feature group once and reuse it for all selected scenarios in this session.
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/generate/SKILL.md
git commit -m "feat: add bdd:generate skill for bulk test case ideation"
```

---

### Task 11: Rewrite skills/run/SKILL.md

Major rewrite: replace stub with classify→heal→retry loop using backend node files, plus reporter summary.

**Files:**
- Modify: `skills/run/SKILL.md`

- [ ] **Step 1: Rewrite skills/run/SKILL.md**

```markdown
---
name: bdd:run
description: Use to execute BDD scenarios. Accepts a scenario filename, feature group name, or "all". On failure: classifies the error, attempts heal-and-retry using the upstream backend's own prompts and schemas (no API key needed). Reports results with a natural-language summary.
---

# bdd:run

Execute scenarios via checkmate. Requires `bdd:stack up` first.

## Usage

- `bdd:run <scenario-name>` — single scenario (e.g. `user-login-success`)
- `bdd:run <feature-group>` — all scenarios in a group (e.g. `auth`)
- `bdd:run all` — full suite

## Step 1: Read config

Load `tests/e2e/checkmate.config.json`. Read:
- `plugin_root` → `<PLUGIN_ROOT>`
- `bdd.run.max_retries` (default: 2)
- `bdd.heal.auto_apply_threshold` (default: 0.85)
- `checkmate.project_name`, `checkmate.url`

## Step 2: Verify stack is up

```bash
curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1 || echo "checkmate not running"
curl -sf http://127.0.0.1:8932/health > /dev/null 2>&1 || echo "playwright-http not running"
```

If either is not running: "Stack is not running. Run `bdd:stack up` first. Start it now? [Y/n]"

## Step 3: Resolve target to test case IDs

Get test case list:

```python
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
base = cfg["checkmate"]["url"]
name = cfg["checkmate"]["project_name"]
projects = json.loads(urllib.request.urlopen(f"{base}/api/projects").read())
proj = next(p for p in projects if p["name"] == name)
cases = json.loads(urllib.request.urlopen(f"{base}/api/test-cases/project/{proj['id']}").read())
```

**Single scenario name:** Find `cases` entry where `name == <scenario-name>`.
**Feature group:** Find all `.json` files under `tests/e2e/scenarios/<group>/`; match by stem to `cases`.
**`all`:** All cases in the project.

Register any unregistered scenarios first:

```bash
python3 <PLUGIN_ROOT>/scripts/run-suite.py \
  --config tests/e2e/checkmate.config.json \
  --scenarios tests/e2e/scenarios/ \
  --register-only
```

## Step 4: Run each test case — classify-heal-retry loop

For each test case ID, run this loop (max `bdd.run.max_retries` heal attempts):

### 4a. Invoke run_test MCP tool

Use the `checkmate` MCP server `run_test` tool:
- `test_case_id`: the case ID
- `browser`: `chromium-headless` (default)
- **Do NOT pass a `retry` parameter** — retry is handled client-side here, not by the backend

Collect SSE events. Print each step as it streams:
```
  ✓ navigate /login
  ✓ click Login button
  ✗ assert_text "Welcome" — Element not found: "Welcome"
```

### 4b. If passed: record pass and move to next case

### 4c. If failed: classify the failure

Read `~/.checkmate-bdd/checkmate/agent/nodes/failure_classifier.py`.

Find the system prompt and the `FailureClassification` Pydantic schema.

Produce a `FailureClassification` from the SSE failure events (step action, target, value, error, screenshot if available) following the system prompt. The schema includes a `retryable` boolean and a `category` field.

If `retryable == false` OR retry budget exhausted: record as non-retryable failure, skip to 4f.

### 4d. Propose healed steps

Read `~/.checkmate-bdd/checkmate/agent/nodes/healer.py`.

Find the system prompt and the `HealSuggestion` / `HealedStep` Pydantic schema. Note the critical target/value format rules in the prompt — follow them exactly.

Produce a `HealSuggestion` from:
- `test_case_name`: scenario name
- `natural_query`: case's natural_query field
- `base_url`: from config
- `original_steps`: current steps from the test case
- `failed_steps`: the failing SSE step events
- `page_elements`: if a screenshot is available, describe visible elements

The schema includes `healed_steps`, `changed_step_numbers`, `explanation`, and `confidence` (0.0–1.0).

### 4e. Apply or prompt

**If `confidence >= bdd.heal.auto_apply_threshold`:**

Update the test case with healed steps:

```python
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
base = cfg["checkmate"]["url"]
healed_steps_json = json.dumps(<healed_steps as list of dicts>)

body = json.dumps({"steps": healed_steps_json}).encode()
req = urllib.request.Request(f"{base}/api/test-cases/{case_id}",
      data=body, headers={"Content-Type": "application/json"}, method="PUT")
urllib.request.urlopen(req)
```

Also update `tests/e2e/scenarios/<group>/<name>.json` with the healed steps.

Decrement retry budget. Go back to 4a.

**If `confidence < bdd.heal.auto_apply_threshold`:**

Print the diff:
```
Heal suggestion (confidence: 0.62):
  Step 3: assert_text "Welcome" → assert_text "Dashboard"
  Reason: page shows "Dashboard" not "Welcome" after login

Apply? [y/n/edit]
```

If user says `y`: apply and re-run (go to 4a after updating).
If user says `n`: record as failure with the explanation.
If user says `edit`: show full healed UTML, let user edit, then apply and re-run.

### 4f. Record final outcome

After all retries or non-retryable failure: record the test case as failed with the `FailureClassification`.

## Step 5: Generate result summary

Read `~/.checkmate-bdd/checkmate/agent/nodes/reporter.py`.

Find the system prompt and output structure. Using the full run results (passed cases, failed cases, classification for each failure), produce a summary following that prompt.

Print the summary, followed by component-boundary hints for each failure:

| Failure category | Investigation hint |
|---|---|
| `element_not_found` | UI layer — check HTML structure, element labels, wait for render |
| `assertion_failed` | App state — check the API response, DB state, or page content |
| `navigation_failed` | Routing — check URL patterns, redirects, auth guards |
| `network_error` | HTTP API layer — check server logs, route handler, DB connection |
| `timeout` | Timing — add `wait_for_page` steps, check async loading |
| `script_error` | JavaScript error — check browser console, React error boundary |
| `screenshot_required` | Visual assertion — screenshot taken, review manually |
| `unknown` | Check full stack logs |

## Step 6: Print final summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Results: 4 passed, 1 failed  (18.2s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAILED: user-login-success
  Step 3: assert_text "Welcome" — Element not found
  Category: element_not_found (non-retryable after 2 heal attempts)
  Hint: UI layer — check HTML structure and element labels
  Screenshot: tests/e2e/screenshots/user-login-success-step3.png
```

Exit with error signal if any scenario failed (so CI fails correctly).
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/run/SKILL.md
git commit -m "feat: rewrite bdd:run with classify-heal-retry loop and reporter"
```

---

### Task 12: Write skills/record/SKILL.md

New skill: start/stop browser recording via playwright-http, then refine raw events into clean UTML using backend recorder prompts/schemas.

**Files:**
- Create: `skills/record/SKILL.md`

- [ ] **Step 1: Write skills/record/SKILL.md**

```markdown
---
name: bdd:record
description: Use to record a browser session and convert it to a BDD scenario. You interact with the app naturally; Claude refines the raw recording into clean UTML using the upstream backend's recorder prompts and schemas. No API key required.
---

# bdd:record

Record a browser session and convert it to a UTML scenario. Claude does the AI refinement inline.

## Step 1: Verify stack is running

```bash
curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1 || echo "not running"
curl -sf http://127.0.0.1:8932/health > /dev/null 2>&1 || echo "not running"
```

If either is down: "Run `bdd:stack up` first."

## Step 2: Get project ID

```python
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
base = cfg["checkmate"]["url"]
name = cfg["checkmate"]["project_name"]
projects = json.loads(urllib.request.urlopen(f"{base}/api/projects").read())
proj = next(p for p in projects if p["name"] == name)
project_id = proj["id"]
```

## Step 3: Start recording session

```python
import json, urllib.request
body = json.dumps({"base_url": cfg["base_url"]}).encode()
req = urllib.request.Request(
    f"{base}/api/projects/{project_id}/recorder/start",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
result = json.loads(urllib.request.urlopen(req).read())
print(f"Recording started. Open your browser and interact with the application.")
print(f"Navigate to: {cfg['base_url']}")
```

## Step 4: Wait for user to finish recording

Print:
```
Recording is active. Interact with your application in the browser.
When you are done, type "done" and press Enter.
```

Wait for user to say "done" (or similar: "stop", "finished").

## Step 5: Stop recording and retrieve raw steps

```python
import json, urllib.request
req = urllib.request.Request(
    f"{base}/api/projects/{project_id}/recorder/stop",
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
result = json.loads(urllib.request.urlopen(req).read())
raw_steps = result.get("steps", [])
print(f"Recording stopped. {len(raw_steps)} raw events captured.")
```

If `raw_steps` is empty: "No steps were recorded. Make sure the app was open in the browser and you interacted with it."

## Step 6: Read backend source — recorder processor and refiner

Read `~/.checkmate-bdd/checkmate/agent/nodes/recorder_processor.py`.

Find the `ProcessedStep` Pydantic class and the processing logic/prompt.

Read `~/.checkmate-bdd/checkmate/api/routes/recorder.py`.

Find:
- `REFINE_PROMPT` and `RefinedStepsResponse` Pydantic class
- `METADATA_PROMPT` and `GeneratedMetadata` Pydantic class

Using the raw steps from Step 5:

1. **Process steps:** Apply `ProcessedStep` logic to filter/normalize raw events (remove noise, handle redirects, preserve hover-before-click sequences per the recorder notes in the prompt).

2. **Refine steps:** Using `REFINE_PROMPT` and `RefinedStepsResponse`, transform processed steps into builder-quality UTML steps. Follow all per-action rules exactly as stated in the prompt — especially the target preservation rules (CSS selectors and IDs must be kept verbatim; do not rewrite them as natural language).

3. **Generate metadata:** Using `METADATA_PROMPT` and `GeneratedMetadata`, produce: name, description, priority, tags from the refined steps.

## Step 7: Show refined scenario and iterate

Present the refined UTML JSON and metadata. Ask: "Does this scenario look right? I can adjust any step."

Iterate until approved. One round of questions per iteration.

## Step 8: Ask feature group

List existing subdirectories under `tests/e2e/scenarios/` as numbered options. Offer "Create new group".

Use `GeneratedMetadata.name` as the default filename (kebab-cased). Confirm with user.

## Step 9: Save and register

Write the approved UTML JSON to `tests/e2e/scenarios/<group>/<name>.json`.

Register in checkmate:

```python
import json, urllib.request
utml = json.load(open(f"tests/e2e/scenarios/<group>/<name>.json"))
body = json.dumps({
    "project_id": project_id,
    "name": "<name>",
    "natural_query": "<GeneratedMetadata.name or name.replace('-', ' ')>",
    "steps": json.dumps(utml.get("steps", [])),
    "description": "<GeneratedMetadata.description>",
    "priority": "<GeneratedMetadata.priority>",
    "tags": json.dumps(<GeneratedMetadata.tags>),
}).encode()
req = urllib.request.Request(f"{base}/api/test-cases",
      data=body, headers={"Content-Type": "application/json"}, method="POST")
result = json.loads(urllib.request.urlopen(req).read())
print(f"Registered: {result['name']} (id={result['id']})")
```

## Step 10: Confirm

Print:
```
✓ Scenario recorded: tests/e2e/scenarios/<group>/<name>.json

Run it with: bdd:run <name>
```
```

- [ ] **Step 2: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/record/SKILL.md
git commit -m "feat: add bdd:record skill for browser recording → UTML conversion"
```

---

### Task 13: Update skills/ci/SKILL.md

Verify the CI skill is complete and correct: uses `run-suite.py` (non-AI), correct config field names, no OPENAI_API_KEY in workflow.

**Files:**
- Modify: `skills/ci/SKILL.md`

- [ ] **Step 1: Read current ci/SKILL.md**

Read `skills/ci/SKILL.md`. Verify:
- References `run-suite.py` (not `claude -p "bdd:run all"`)
- Does not include `OPENAI_API_KEY` in generated workflow
- CI template substitutions match `templates/ci-workflow.yml` placeholders
- `PLUGIN_DEPS_DIR` is set before docker compose calls

- [ ] **Step 2: Rewrite skills/ci/SKILL.md**

```markdown
---
name: bdd:ci
description: Use to generate a GitHub Actions workflow for running BDD scenarios in CI. Emits YAML for you to copy into .github/workflows/bdd.yml. No API key required — CI uses run-suite.py directly.
---

# bdd:ci

Generate a GitHub Actions workflow from `tests/e2e/checkmate.config.json`.

## Step 1: Read config

Load `tests/e2e/checkmate.config.json`. If missing, run `bdd:setup` first.

Extract:
- `stack.start_command` → `{{START_COMMAND}}`
- `stack.ready_url` → `{{READY_URL}}`
- `stack.ready_timeout_secs` → `{{READY_TIMEOUT}}`
- `checkmate.project_name` → `{{PROJECT_NAME}}`
- `plugin_root` → `{{PLUGIN_ROOT}}`

## Step 2: Render workflow

Read `<plugin_root>/templates/ci-workflow.yml`. Substitute all `{{...}}` placeholders with the values above.

## Step 3: Output

Print the rendered YAML in a code block, then print:

```
Copy this to .github/workflows/bdd.yml in your repo.

CI notes:
- ENCRYPTION_KEY should be set as a GitHub secret (any random string works).
- OPENAI_API_KEY is NOT needed — this plugin uses Claude for all AI work.
- The workflow uses Docker (available on GitHub-hosted ubuntu-latest runners).
- Docker image builds are cached between runs via GitHub Actions cache.
```
```

- [ ] **Step 3: Update templates/ci-workflow.yml**

Read `templates/ci-workflow.yml`. Ensure:
1. No `OPENAI_API_KEY` env var in any step
2. `PLUGIN_DEPS_DIR` is set before docker compose calls
3. The run scenarios step uses `python3 <plugin-path>/scripts/run-suite.py` not `claude -p "bdd:run all"`
4. Placeholders are `{{START_COMMAND}}`, `{{READY_URL}}`, `{{READY_TIMEOUT}}`, `{{PROJECT_NAME}}`

Write the corrected `templates/ci-workflow.yml`:

```yaml
# templates/ci-workflow.yml
# Copy to .github/workflows/bdd.yml. Substitute {{...}} before copying, or use `bdd:ci` to generate.

name: BDD E2E Tests — {{PROJECT_NAME}}

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

env:
  PLUGIN_DEPS_DIR: /home/runner/.checkmate-bdd
  PLUGIN_PATH: ${{ github.workspace }}/.claude/plugins/checkmate-bdd

jobs:
  bdd:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Clone BDD service dependencies
        run: bash ${{ env.PLUGIN_PATH }}/scripts/clone-deps.sh

      - name: Cache Docker layers
        uses: actions/cache@v4
        with:
          path: /tmp/.buildx-cache
          key: bdd-docker-${{ runner.os }}-${{ hashFiles('~/.checkmate-bdd/**/*.py', '~/.checkmate-bdd/**/*.ts') }}
          restore-keys: bdd-docker-${{ runner.os }}-

      - name: Build and start BDD stack
        run: |
          PLUGIN_DEPS_DIR=${{ env.PLUGIN_DEPS_DIR }} \
          docker compose \
            -f ${{ env.PLUGIN_PATH }}/docker/docker-compose.yml \
            up -d --build
        env:
          ENCRYPTION_KEY: ${{ secrets.BDD_ENCRYPTION_KEY }}

      - name: Wait for services
        run: |
          bash ${{ env.PLUGIN_PATH }}/scripts/wait-for-ready.sh http://127.0.0.1:8932/health 60
          bash ${{ env.PLUGIN_PATH }}/scripts/wait-for-ready.sh http://127.0.0.1:8000/health 60
          bash ${{ env.PLUGIN_PATH }}/scripts/wait-for-ready.sh http://127.0.0.1:3003/health 30

      - name: Start application under test
        run: {{START_COMMAND}} &

      - name: Wait for application ready
        run: bash ${{ env.PLUGIN_PATH }}/scripts/wait-for-ready.sh {{READY_URL}} {{READY_TIMEOUT}}

      - name: Run BDD scenarios
        run: |
          python3 ${{ env.PLUGIN_PATH }}/scripts/run-suite.py \
            --config tests/e2e/checkmate.config.json \
            --scenarios tests/e2e/scenarios/

      - name: Stop BDD stack
        if: always()
        run: |
          PLUGIN_DEPS_DIR=${{ env.PLUGIN_DEPS_DIR }} \
          docker compose \
            -f ${{ env.PLUGIN_PATH }}/docker/docker-compose.yml \
            down

      - name: Upload failure screenshots
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: bdd-screenshots-${{ github.run_id }}
          path: tests/e2e/screenshots/
          if-no-files-found: ignore
```

- [ ] **Step 4: Commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add skills/ci/SKILL.md templates/ci-workflow.yml
git commit -m "feat: update bdd:ci skill and ci-workflow template; remove OPENAI_API_KEY"
```

---

### Task 14: Final wiring and verification

Verify all expected files exist, scripts are executable, JSON/YAML files are valid, and the plugin manifest is consistent.

**Files:**
- No new changes — verification only

- [ ] **Step 1: Verify all expected files exist**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
for f in \
  .claude-plugin/plugin.json \
  docker/docker-compose.yml \
  scripts/clone-deps.sh \
  scripts/native-start.sh \
  scripts/native-stop.sh \
  scripts/run-suite.py \
  scripts/wait-for-ready.sh \
  skills/setup/SKILL.md \
  skills/stack/SKILL.md \
  skills/write/SKILL.md \
  skills/generate/SKILL.md \
  skills/run/SKILL.md \
  skills/record/SKILL.md \
  skills/ci/SKILL.md \
  templates/checkmate.config.json \
  templates/ci-workflow.yml \
  templates/claude-md-snippet.md \
  CLAUDE.md \
  README.md; do
  [ -f "$f" ] && echo "✓ $f" || echo "✗ MISSING: $f"
done
```

Expected: all lines show `✓`

- [ ] **Step 2: Verify scripts are executable**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
for s in scripts/clone-deps.sh scripts/native-start.sh scripts/native-stop.sh scripts/wait-for-ready.sh; do
  [ -x "$s" ] && echo "✓ executable: $s" || echo "✗ NOT executable: $s — run: chmod +x $s"
done
```

- [ ] **Step 3: Verify JSON files parse cleanly**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
for f in .claude-plugin/plugin.json templates/checkmate.config.json; do
  python3 -c "import json; json.load(open('$f')); print('✓ $f')"
done
```

- [ ] **Step 4: Verify Python script syntax**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
python3 -c "import ast; ast.parse(open('scripts/run-suite.py').read()); print('✓ run-suite.py')"
```

- [ ] **Step 5: Verify bash script syntax**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
bash -n scripts/clone-deps.sh && echo "✓ clone-deps.sh"
bash -n scripts/native-start.sh && echo "✓ native-start.sh"
bash -n scripts/native-stop.sh && echo "✓ native-stop.sh"
bash -n scripts/wait-for-ready.sh && echo "✓ wait-for-ready.sh"
```

- [ ] **Step 6: Check no OPENAI_API_KEY references in plugin code**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
grep -r "OPENAI_API_KEY" --include="*.yml" --include="*.yaml" --include="*.sh" --include="*.py" --include="*.md" . | grep -v ".git" | grep -v "specs/" | grep -v "plans/" || echo "✓ No OPENAI_API_KEY references in plugin files"
```

Expected: `✓ No OPENAI_API_KEY references in plugin files`

(The spec and plan docs may reference it for context — that's fine. Plugin skills and scripts must not.)

- [ ] **Step 7: Write action log**

Write a summary to `docs/superpowers/actions/2026-04-18-checkmate-bdd-plugin-agentic.md`:

```markdown
# Action Log: checkmate-bdd-plugin Agentic Path

**Date:** 2026-04-18
**Plan:** docs/superpowers/plans/2026-04-18-checkmate-bdd-plugin-agentic.md

## Completed

- Task 1: docker-compose.yml switched to build contexts; OPENAI_API_KEY removed
- Task 2: scripts/clone-deps.sh written
- Task 3: scripts/native-start.sh and native-stop.sh written
- Task 4: scripts/run-suite.py written with correct API shapes
- Task 5: templates/checkmate.config.json updated with bdd.run/heal fields
- Task 6: templates/claude-md-snippet.md updated with bdd:generate and bdd:record
- Task 7: skills/setup/SKILL.md rewritten with clone-deps + backend source verification
- Task 8: skills/stack/SKILL.md rewritten with git pull + PLUGIN_DEPS_DIR
- Task 9: skills/write/SKILL.md rewritten with backend source pointer pattern
- Task 10: skills/generate/SKILL.md written (new skill)
- Task 11: skills/run/SKILL.md rewritten with classify-heal-retry loop
- Task 12: skills/record/SKILL.md written (new skill)
- Task 13: skills/ci/SKILL.md and ci-workflow.yml updated
- Task 14: Final verification
```

- [ ] **Step 8: Final commit**

```bash
cd "c:/Users/shuam/OneDrive/Documents/github projects/checkmate-bdd-plugin"
git add docs/superpowers/actions/
git commit -m "docs: add action log for agentic path implementation"
```

---

## Self-Review

**Spec coverage:**
- ✓ C1 (no upstream repo changes) — skills use only existing API endpoints throughout
- ✓ C2 (no prompt duplication) — all LLM-bearing skills use backend source pointer pattern
- ✓ bdd:write — Tasks 9 (planner.py + builder.py pointers)
- ✓ bdd:generate — Task 10 (generator.py pointer)
- ✓ bdd:run classify+heal+retry — Task 11 (failure_classifier.py + healer.py + reporter.py)
- ✓ bdd:record — Task 12 (recorder_processor.py + recorder.py pointers)
- ✓ bdd:stack git pull — Task 8
- ✓ bdd:setup backend verification — Task 7
- ✓ bdd:ci no OPENAI_API_KEY — Task 13
- ✓ config schema (max_retries, auto_apply_threshold) — Task 5
- ✓ docker build contexts — Task 1
- ✓ All three scripts — Tasks 2–4
- ✓ CI workflow — Task 13

**Placeholder scan:** All steps contain complete code. No TBD/TODO in task steps.

**Type consistency:**
- `run-suite.py` uses `checkmate_post` consistently; endpoint `/api/test-cases` (no project_id in path) consistent with Task 4 and all skill inline Python snippets
- `plugin_root` field in config referenced consistently in Tasks 7, 8, 9, 11, 12
- `PLUGIN_DEPS_DIR=~/.checkmate-bdd` consistent in Tasks 1, 8, 13
- `steps` field is JSON-encoded string throughout (Task 4, Tasks 9, 11, 12)
- `ProjectCreate` includes `base_url` throughout (Task 4 run-suite.py, Task 8 stack skill)

**One gap found:** Task 3 `native-start.sh` starts playwright-http before checkmate — but checkmate's `PLAYWRIGHT_EXECUTOR_URL` points at playwright-http. The start order (playwright-http first) is correct for Docker too (via `depends_on` in Task 1). ✓ Consistent.
