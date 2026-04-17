# checkmate-bdd-plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code plugin with five BDD skills (setup, stack, write, run, ci) that adds project-agnostic BDD E2E testing via checkmate + playwright-http + checkmate-mcp.

**Architecture:** Skills are markdown files in `skills/*/SKILL.md` — Claude Code loads them as instructions. Supporting files (docker-compose with build contexts, wait-for-ready script, CI template, CLAUDE.md snippet) are referenced by the skills. `bdd:setup` clones upstream repos for Docker builds since no pre-built images exist.

**Tech Stack:** Claude Code plugin system (SKILL.md), Docker Compose (build contexts for checkmate/playwright-http/checkmate-mcp), Bash (scripts), JSON (UTML scenario format, checkmate.config.json)

---

## File Map

**Create:**
- `skills/setup/SKILL.md` — bdd:setup skill (exists as stub, rewrite to full)
- `skills/stack/SKILL.md` — bdd:stack skill (exists as stub, rewrite to full)
- `skills/write/SKILL.md` — bdd:write skill (exists as stub, rewrite to full)
- `skills/run/SKILL.md` — bdd:run skill (exists as stub, rewrite to full)
- `skills/ci/SKILL.md` — bdd:ci skill (exists as stub, rewrite to full)
- `docker/docker-compose.yml` — build-context compose (rewrite existing)
- `scripts/wait-for-ready.sh` — readiness polling (exists, verify)
- `scripts/clone-deps.sh` — clone upstream repos for Docker builds
- `scripts/native-start.sh` — start services natively (no Docker)
- `scripts/native-stop.sh` — stop native services
- `templates/ci-workflow.yml` — GitHub Actions template (missing, create)
- `templates/claude-md-snippet.md` — CLAUDE.md addition (exists, verify)
- `templates/checkmate.config.json` — example config template

---

### Task 1: Verify wait-for-ready.sh and fix docker-compose for build contexts

Upstream repos (checkmate, playwright-http, checkmate-mcp) have Dockerfiles but no published registry images. The compose file must use `build:` contexts pointing at cloned source. This task rewrites docker-compose.yml and verifies the wait script works.

**Files:**
- Modify: `docker/docker-compose.yml`
- Verify: `scripts/wait-for-ready.sh`

- [ ] **Step 1: Test wait-for-ready.sh exists and is executable**

```bash
cd c:/tmp/checkmate-bdd-plugin
bash scripts/wait-for-ready.sh http://localhost:9999 2
```

Expected: prints "Timeout waiting for http://localhost:9999 after 2s", exits 1.

- [ ] **Step 2: Rewrite docker-compose.yml with build contexts**

The compose file must clone upstream repos before building, OR reference pre-cloned paths. Since `bdd:setup` will clone repos to `~/.checkmate-bdd/` (a fixed location outside project repos), the compose uses relative paths from `PLUGIN_DEPS_DIR` env var.

Write `docker/docker-compose.yml`:

```yaml
# docker/docker-compose.yml
# Requires PLUGIN_DEPS_DIR env var pointing to cloned upstream repos.
# Set by bdd:setup and bdd:stack. Default: ~/.checkmate-bdd/

services:
  checkmate:
    build:
      context: ${PLUGIN_DEPS_DIR:-~/.checkmate-bdd}/checkmate
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-changeme-replace-in-production}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 12

  playwright-http:
    build:
      context: ${PLUGIN_DEPS_DIR:-~/.checkmate-bdd}/playwright-http
      dockerfile: Dockerfile
    ports:
      - "8932:8932"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8932/health"]
      interval: 5s
      timeout: 3s
      retries: 12

  checkmate-mcp:
    build:
      context: ${PLUGIN_DEPS_DIR:-~/.checkmate-bdd}/checkmate-mcp
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

- [ ] **Step 3: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add docker/docker-compose.yml scripts/wait-for-ready.sh
git commit -m "fix: use build contexts in compose; upstream has no registry images"
```

---

### Task 2: Write scripts/clone-deps.sh

`bdd:setup` calls this script to clone checkmate, playwright-http, and checkmate-mcp into `~/.checkmate-bdd/`. Idempotent — pulls if already cloned.

**Files:**
- Create: `scripts/clone-deps.sh`

- [ ] **Step 1: Write clone-deps.sh**

```bash
#!/usr/bin/env bash
# clone-deps.sh
# Clones or updates upstream repos into ~/.checkmate-bdd/
# Usage: clone-deps.sh

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

clone_or_pull "ksankaran/checkmate"      "checkmate"
clone_or_pull "ksankaran/playwright-http" "playwright-http"
clone_or_pull "ksankaran/checkmate-mcp"   "checkmate-mcp"

echo "Dependencies ready at ${DEPS_DIR}"
echo "PLUGIN_DEPS_DIR=${DEPS_DIR}"
```

- [ ] **Step 2: Make executable**

```bash
cd c:/tmp/checkmate-bdd-plugin
chmod +x scripts/clone-deps.sh
```

- [ ] **Step 3: Test dry run (verify syntax)**

```bash
bash -n scripts/clone-deps.sh && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/clone-deps.sh
git commit -m "feat: add clone-deps.sh to fetch upstream service repos"
```

---

### Task 3: Write scripts/native-start.sh and scripts/native-stop.sh

Fallback when Docker is unavailable. Starts checkmate and playwright-http via `uv`, checkmate-mcp via `node`. Writes PIDs to `~/.checkmate-bdd/pids/` for stop.

**Files:**
- Create: `scripts/native-start.sh`
- Create: `scripts/native-stop.sh`

- [ ] **Step 1: Write native-start.sh**

```bash
#!/usr/bin/env bash
# native-start.sh
# Start checkmate, playwright-http, checkmate-mcp natively.
# Requires upstream repos already cloned by clone-deps.sh.

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

start_service "checkmate-mcp" \
  "${DEPS_DIR}/checkmate-mcp" \
  "CHECKMATE_URL=http://127.0.0.1:8000 PORT=3003 node dist/server.js"

echo "All services started. Check logs at ${LOG_DIR}/"
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

  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping ${name} (pid ${pid})..."
      kill "$pid"
    else
      echo "${name} not running"
    fi
    rm -f "$pid_file"
  else
    echo "${name}: no pid file found"
  fi
}

stop_service "checkmate-mcp"
stop_service "playwright-http"
stop_service "checkmate"
```

- [ ] **Step 3: Make executable and verify syntax**

```bash
cd c:/tmp/checkmate-bdd-plugin
chmod +x scripts/native-start.sh scripts/native-stop.sh
bash -n scripts/native-start.sh && bash -n scripts/native-stop.sh && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/native-start.sh scripts/native-stop.sh
git commit -m "feat: add native-start/stop scripts for non-Docker environments"
```

---

### Task 4: Write templates/ci-workflow.yml and templates/checkmate.config.json

The CI workflow template and example config that `bdd:ci` and `bdd:setup` emit.

**Files:**
- Create: `templates/ci-workflow.yml`
- Create: `templates/checkmate.config.json`

- [ ] **Step 1: Write templates/ci-workflow.yml**

```yaml
# templates/ci-workflow.yml
# Copy to .github/workflows/bdd.yml in your repo.
# Generated by `bdd:ci` — substitute {{PROJECT_NAME}} and {{START_COMMAND}} before copying.

name: BDD E2E Tests

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

env:
  PLUGIN_DEPS_DIR: /home/runner/.checkmate-bdd

jobs:
  bdd:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Clone BDD service dependencies
        run: bash ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/scripts/clone-deps.sh

      - name: Build and start BDD stack
        run: |
          PLUGIN_DEPS_DIR=${{ env.PLUGIN_DEPS_DIR }} \
          docker compose \
            -f ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/docker/docker-compose.yml \
            up -d --build
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ENCRYPTION_KEY: ${{ secrets.BDD_ENCRYPTION_KEY }}

      - name: Wait for services
        run: |
          bash ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/scripts/wait-for-ready.sh http://127.0.0.1:8000/health 60
          bash ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/scripts/wait-for-ready.sh http://127.0.0.1:8932/health 30
          bash ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/scripts/wait-for-ready.sh http://127.0.0.1:3003/health 30

      - name: Start application under test
        run: {{START_COMMAND}} &

      - name: Wait for application ready
        run: |
          bash ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/scripts/wait-for-ready.sh \
            $(cat tests/e2e/checkmate.config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['stack']['ready_url'])") \
            60

      - name: Run BDD scenarios
        run: |
          # Register scenarios and run full suite via checkmate API
          python3 ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/scripts/run-suite.py \
            --config tests/e2e/checkmate.config.json \
            --scenarios tests/e2e/scenarios/

      - name: Stop BDD stack
        if: always()
        run: |
          docker compose \
            -f ${GITHUB_WORKSPACE}/.claude/plugins/checkmate-bdd/docker/docker-compose.yml \
            down

      - name: Upload failure screenshots
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: bdd-screenshots-${{ github.run_id }}
          path: tests/e2e/screenshots/
          if-no-files-found: ignore
```

- [ ] **Step 2: Write templates/checkmate.config.json**

```json
{
  "base_url": "http://localhost:3000",
  "stack": {
    "start_command": "npm start",
    "ready_url": "http://localhost:3000/health",
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

- [ ] **Step 3: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add templates/ci-workflow.yml templates/checkmate.config.json
git commit -m "feat: add CI workflow template and example checkmate.config.json"
```

---

### Task 5: Write scripts/run-suite.py

CI needs a headless way to register and run all scenarios without Claude Code present. This script talks to the checkmate API directly.

**Files:**
- Create: `scripts/run-suite.py`

- [ ] **Step 1: Write run-suite.py**

```python
#!/usr/bin/env python3
"""
run-suite.py
Register UTML scenario files into checkmate and run them.
Used by CI workflow. Exits 0 if all pass, 1 if any fail.

Usage:
  python3 run-suite.py --config tests/e2e/checkmate.config.json \
                        --scenarios tests/e2e/scenarios/
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error


def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def checkmate_request(base_url: str, method: str, path: str, body=None) -> dict:
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} for {method} {path}: {e.read().decode()}", file=sys.stderr)
        raise


def ensure_project(checkmate_url: str, project_name: str) -> int:
    projects = checkmate_request(checkmate_url, "GET", "/api/projects/")
    for p in projects:
        if p["name"] == project_name:
            return p["id"]
    created = checkmate_request(checkmate_url, "POST", "/api/projects/",
                                 {"name": project_name})
    return created["id"]


def register_scenarios(checkmate_url: str, project_id: int,
                        scenarios_dir: str) -> list[int]:
    """Register all UTML JSON files in scenarios_dir. Return list of test case IDs."""
    case_ids = []
    for path in sorted(Path(scenarios_dir).rglob("*.json")):
        with open(path) as f:
            utml = json.load(f)
        name = path.stem
        # Upsert: check if test case with this name exists
        cases = checkmate_request(checkmate_url, "GET",
                                   f"/api/test-cases/project/{project_id}/")
        existing = next((c for c in cases if c["name"] == name), None)
        if existing:
            case_ids.append(existing["id"])
        else:
            case = checkmate_request(checkmate_url, "POST",
                                      f"/api/test-cases/project/{project_id}/",
                                      {"name": name, "utml": utml})
            case_ids.append(case["id"])
            print(f"  Registered: {name}")
    return case_ids


def run_test_case(checkmate_url: str, case_id: int) -> bool:
    """Run a single test case. Returns True if passed."""
    # Collect SSE stream from runs/stream endpoint
    url = f"{checkmate_url}/api/test-cases/{case_id}/runs/stream"
    req = urllib.request.Request(url, data=b"{}", method="POST",
                                  headers={"Content-Type": "application/json"})
    passed = False
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.decode().strip()
                if line.startswith("data:"):
                    event = json.loads(line[5:].strip())
                    if event.get("type") == "step":
                        status = "✓" if event.get("passed") else "✗"
                        print(f"    {status} {event.get('action','')} {event.get('target','')}")
                    elif event.get("type") == "result":
                        passed = event.get("passed", False)
    except Exception as e:
        print(f"  Error running case {case_id}: {e}", file=sys.stderr)
    return passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenarios", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    checkmate_url = cfg["checkmate"]["url"]
    project_name = cfg["checkmate"]["project_name"]

    print(f"Connecting to checkmate at {checkmate_url}")
    project_id = ensure_project(checkmate_url, project_name)
    print(f"Project '{project_name}' id={project_id}")

    print("Registering scenarios...")
    case_ids = register_scenarios(checkmate_url, project_id, args.scenarios)
    print(f"  {len(case_ids)} scenario(s) registered")

    passed = 0
    failed = 0
    for case_id in case_ids:
        print(f"\nRunning case {case_id}...")
        if run_test_case(checkmate_url, case_id):
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

```bash
cd c:/tmp/checkmate-bdd-plugin
python3 -c "import ast; ast.parse(open('scripts/run-suite.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/run-suite.py
git commit -m "feat: add run-suite.py for headless CI scenario execution"
```

---

### Task 6: Rewrite skills/setup/SKILL.md — full implementation

Replace the stub with complete, actionable instructions including exact shell commands, MCP registration format, and config file content.

**Files:**
- Modify: `skills/setup/SKILL.md`

- [ ] **Step 1: Write full SKILL.md for bdd:setup**

```markdown
---
name: bdd:setup
description: Use when initializing BDD E2E testing in a project for the first time, or re-configuring. Creates tests/e2e/checkmate.config.json, clones service dependencies, installs deps, and wires into CLAUDE.md.
---

# bdd:setup

One-time initialization of the BDD test stack for a consuming project. Idempotent — safe to re-run.

## Steps

### 1. Check for existing config

Look for `tests/e2e/checkmate.config.json` in the current repo root.

If it exists, read it and offer to update specific fields. Skip to step 3 for fields already present.

### 2. Collect config values (if creating new config)

Ask the following questions **one at a time**:

1. "What is the base URL of your application? (e.g. http://localhost:7792)"
2. "What shell command starts your application? (e.g. cargo run --manifest-path core/Cargo.toml)"
3. "What URL should I poll to know your app is ready? (e.g. http://localhost:7792/api/health). Press enter to skip (will wait for timeout instead)"
4. "How many seconds should I wait for the app to be ready? [default: 30]"
5. "Should BDD scenario results be **required** to pass before marking implementation complete (`required`), or just shown as a reminder (`prompted`)? [required/prompted, default: required]"

### 3. Check Docker availability

Run: `docker info > /dev/null 2>&1`

- If exit 0: Docker is available. Ask "Docker is available — run services as containers? [Y/n]". Default yes.
- If exit non-0: Docker unavailable. Services will run natively. Note this in the config.

### 4. Write tests/e2e/checkmate.config.json

Create `tests/e2e/` directory if absent. Write the config:

```json
{
  "base_url": "<user answer>",
  "stack": {
    "start_command": "<user answer>",
    "ready_url": "<user answer or omit if skipped>",
    "ready_timeout_secs": <user answer or 30>
  },
  "services": {
    "prefer_docker": <true if Docker available and user chose yes, else false>
  },
  "bdd": {
    "verification_mode": "<required or prompted>"
  },
  "checkmate": {
    "project_name": "<repo directory name>",
    "url": "http://127.0.0.1:8000"
  }
}
```

### 5. Clone upstream service repos

The plugin's Docker and native modes both require upstream source. Run:

```bash
bash <PLUGIN_ROOT>/scripts/clone-deps.sh
```

Where `<PLUGIN_ROOT>` is the plugin's install directory. On success, repos are at `~/.checkmate-bdd/{checkmate,playwright-http,checkmate-mcp}`.

### 6. Check native dependencies (always, even if using Docker)

Run these checks. Print install instructions for anything missing:

```bash
python3 --version     # need 3.11+
uv --version          # need any version; install: pip install uv
node --version        # need 22+
docker --version      # optional
docker compose version  # optional
```

If native mode: also run:
```bash
cd ~/.checkmate-bdd/checkmate-mcp && npm install
```

### 7. Build Docker images (if Docker mode)

```bash
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml build
```

This may take several minutes on first run. Images are cached after that.

### 8. Register checkmate-mcp as a Claude Code MCP server

Add to `~/.claude/settings.json` under `mcpServers`:

```json
"mcpServers": {
  "checkmate": {
    "type": "http",
    "url": "http://127.0.0.1:3003/mcp"
  }
}
```

Read the file first, merge the key, write it back. Do not overwrite existing mcpServers entries.

### 9. Create tests/e2e/scenarios/ directory

```bash
mkdir -p tests/e2e/scenarios
```

### 10. Append BDD section to CLAUDE.md

Read `<PLUGIN_ROOT>/templates/claude-md-snippet.md`. Ask: "Append the BDD testing section to CLAUDE.md? [Y/n]"

If yes: append the template content to `CLAUDE.md`.

### 11. Confirm completion

Print:
```
✓ BDD setup complete.

Next steps:
  1. Run `bdd:stack up` to start the test services.
  2. Run `bdd:write` to author your first scenario.
  3. Run `bdd:run all` to execute scenarios.
```
```

- [ ] **Step 2: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add skills/setup/SKILL.md
git commit -m "feat: write full bdd:setup skill"
```

---

### Task 7: Rewrite skills/stack/SKILL.md — full implementation

**Files:**
- Modify: `skills/stack/SKILL.md`

- [ ] **Step 1: Write full SKILL.md for bdd:stack**

```markdown
---
name: bdd:stack
description: Use to start (`bdd:stack up`), stop (`bdd:stack down`), or check (`bdd:stack status`) the BDD test environment. Manages checkmate, playwright-http, checkmate-mcp, and the application under test.
---

# bdd:stack

## Prerequisites

`tests/e2e/checkmate.config.json` must exist. If missing, run `bdd:setup` first.

The `PLUGIN_ROOT` below refers to the plugin's installed location. Resolve it as:
```bash
claude plugin path checkmate-bdd
```

---

## bdd:stack up

### 1. Read config

Load `tests/e2e/checkmate.config.json`. Extract `services.prefer_docker`, `stack.start_command`, `stack.ready_url`, `stack.ready_timeout_secs`.

### 2. Determine service mode

```bash
if [ "$(cat tests/e2e/checkmate.config.json | python3 -c "import sys,json; print(json.load(sys.stdin)['services']['prefer_docker'])")" = "True" ]; then
  docker info > /dev/null 2>&1 && MODE=docker || MODE=native
else
  MODE=native
fi
```

### 3. Start services

**Docker mode:**
```bash
PLUGIN_DEPS_DIR=~/.checkmate-bdd \
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml up -d
```

**Native mode:**
```bash
bash <PLUGIN_ROOT>/scripts/native-start.sh
```

### 4. Wait for all three service health endpoints

Run each in sequence (30s timeout each):
```bash
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh http://127.0.0.1:8000/health 30
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh http://127.0.0.1:8932/health 30
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh http://127.0.0.1:3003/health 30
```

If any times out: report which service failed, print its logs, stop.

**Docker logs:**
```bash
docker compose -f <PLUGIN_ROOT>/docker/docker-compose.yml logs <service-name>
```

**Native logs:** `~/.checkmate-bdd/logs/<service-name>.log`

### 5. Start application under test

Run `stack.start_command` from the repo root in the background. Save its PID to `~/.checkmate-bdd/pids/app.pid`.

```bash
eval "<start_command>" &
echo $! > ~/.checkmate-bdd/pids/app.pid
```

### 6. Poll app ready URL

```bash
bash <PLUGIN_ROOT>/scripts/wait-for-ready.sh "<ready_url>" <ready_timeout_secs>
```

If no `ready_url` is configured: sleep `ready_timeout_secs` seconds.

### 7. Ensure checkmate project exists

```bash
python3 - <<'EOF'
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
base = cfg["checkmate"]["url"]
name = cfg["checkmate"]["project_name"]
projects = json.loads(urllib.request.urlopen(f"{base}/api/projects/").read())
if not any(p["name"] == name for p in projects):
    req = urllib.request.Request(f"{base}/api/projects/",
          data=json.dumps({"name": name}).encode(),
          headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req)
    print(f"Created project '{name}'")
else:
    print(f"Project '{name}' already exists")
EOF
```

### 8. Register any unregistered scenarios

```bash
python3 <PLUGIN_ROOT>/scripts/run-suite.py \
  --config tests/e2e/checkmate.config.json \
  --scenarios tests/e2e/scenarios/ \
  --register-only
```

(Add `--register-only` flag to run-suite.py in Task 5 fix — see note below.)

### 9. Report status

Print ready/not-ready for each of: checkmate, playwright-http, checkmate-mcp, app under test.

---

## bdd:stack down

### 1. Stop app under test

```bash
if [ -f ~/.checkmate-bdd/pids/app.pid ]; then
  kill $(cat ~/.checkmate-bdd/pids/app.pid) 2>/dev/null || true
  rm ~/.checkmate-bdd/pids/app.pid
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

Check each health endpoint and print a table:

| Component | Status |
|-----------|--------|
| checkmate (:8000) | ✓ running / ✗ not running |
| playwright-http (:8932) | ✓ running / ✗ not running |
| checkmate-mcp (:3003) | ✓ running / ✗ not running |
| app under test | ✓ running / ✗ not running |

Check commands:
```bash
curl -sf http://127.0.0.1:8000/health > /dev/null && echo "✓" || echo "✗"
curl -sf http://127.0.0.1:8932/health > /dev/null && echo "✓" || echo "✗"
curl -sf http://127.0.0.1:3003/health > /dev/null && echo "✓" || echo "✗"
# App: check ready_url from config
```
```

- [ ] **Step 2: Add --register-only flag to run-suite.py**

Edit `scripts/run-suite.py` — add to argparse and main():

```python
parser.add_argument("--register-only", action="store_true",
                    help="Register scenarios without running them")
# In main(), after register_scenarios():
if args.register_only:
    print("Scenarios registered. Exiting (--register-only).")
    sys.exit(0)
```

- [ ] **Step 3: Verify run-suite.py syntax after edit**

```bash
python3 -c "import ast; ast.parse(open('scripts/run-suite.py').read()); print('syntax OK')"
```

Expected: `syntax OK`

- [ ] **Step 4: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add skills/stack/SKILL.md scripts/run-suite.py
git commit -m "feat: write full bdd:stack skill; add --register-only to run-suite.py"
```

---

### Task 8: Rewrite skills/write/SKILL.md — full implementation

**Files:**
- Modify: `skills/write/SKILL.md`

- [ ] **Step 1: Write full SKILL.md for bdd:write**

```markdown
---
name: bdd:write
description: Use before implementing any feature or fix to write the BDD acceptance scenario first. Claude generates UTML JSON from natural language — no external AI required. Write scenarios BEFORE writing implementation code.
---

# bdd:write

Write a BDD scenario in UTML format. Claude generates the scenario — no OpenAI key needed.

**Hard rule: write the scenario before implementation.** If you are tempted to skip this and implement first, stop. The scenario IS the spec. Write it first.

## Step 1: Understand the behavior

Ask: "What behavior do you want to test? Describe it in plain English."

Wait for the response.

## Step 2: Clarify preconditions

Ask: "What is the starting state before this behavior occurs? For example: 'the app is freshly started', 'the user is logged in', 'the model picker shows 3 candidates'."

## Step 3: Clarify the action sequence

Ask: "What does the user do, step by step? For example: 'navigates to /settings, fills in API key, clicks Save'."

## Step 4: Clarify the expected outcome

Ask: "What should be true after the actions complete? What does the user see? What data should be persisted?"

## Step 5: Generate UTML

From the answers, generate a UTML JSON document:

```json
{
  "base_url": "<value from tests/e2e/checkmate.config.json base_url>",
  "steps": [
    {
      "action": "navigate",
      "value": "<starting path>",
      "description": "<precondition context>"
    },
    // ... action steps ...
    {
      "action": "assert_text",
      "value": "<expected visible text>",
      "description": "<what this assertion verifies>"
    }
  ],
  "options": {
    "screenshot_on_failure": true
  }
}
```

**UTML action reference (use these exactly):**
- `navigate` — go to a URL path. `value`: path or full URL.
- `click` — click an element. `target`: natural language ("Submit button") or CSS selector.
- `type` — type into input. `target`: input label. `value`: text.
- `fill_form` — fill multiple fields. `value`: `{"Field label": "text", ...}`.
- `select` — pick from dropdown. `target`: dropdown label. `value`: option text.
- `wait` — wait for element or time. `target`: element (optional). `value`: ms (optional).
- `wait_for_page` — wait for page load. `value`: `"load"`, `"domcontentloaded"`, or `"networkidle"`.
- `assert_text` — assert text is visible. `value`: expected text.
- `assert_element` — assert element exists. `target`: element description.
- `assert_url` — assert URL matches. `value`: regex pattern.
- `evaluate` — run JavaScript. `value`: JS code string.
- `screenshot` — capture screenshot. `value`: filename (optional).

**Targeting guidance:**
- Prefer natural language targets: `"Submit button"`, `"Email input"`, `"Model picker dropdown"`.
- Use CSS selectors only for elements with no accessible label: `"#model-list > .fit-badge"`.

## Step 6: Review with user

Show the generated UTML. Ask: "Does this scenario look right? I can adjust any step."

Iterate until approved. One question per revision round.

## Step 7: Choose feature group and filename

List existing subdirectories under `tests/e2e/scenarios/` as numbered options. Offer "Create new group" as the last option.

Derive a filename: take the behavior description, lowercase, replace spaces with hyphens, remove special characters. Example: "wizard stores operator credentials" → `wizard-stores-operator-credentials.json`.

Confirm: "Save as `tests/e2e/scenarios/<group>/<filename>.json`?"

## Step 8: Save the file

Write the UTML JSON to the confirmed path.

## Step 9: Register in checkmate (if stack is running)

Check: `curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1`

If checkmate is running:
```python
# Get project id
import json, urllib.request
cfg = json.load(open("tests/e2e/checkmate.config.json"))
projects = json.loads(urllib.request.urlopen(f"{cfg['checkmate']['url']}/api/projects/").read())
proj = next(p for p in projects if p["name"] == cfg["checkmate"]["project_name"])
# Register test case
body = json.dumps({"name": "<filename-without-extension>", "utml": <utml_json>}).encode()
req = urllib.request.Request(
    f"{cfg['checkmate']['url']}/api/test-cases/project/{proj['id']}/",
    data=body, headers={"Content-Type": "application/json"}, method="POST")
urllib.request.urlopen(req)
print("Scenario registered in checkmate.")
```

If checkmate is not running: print "Scenario saved. It will be registered in checkmate on the next `bdd:stack up`."

## Step 10: Confirm

Print:
```
✓ Scenario written: tests/e2e/scenarios/<group>/<filename>.json

Run it with: bdd:run <filename-without-extension>
```
```

- [ ] **Step 2: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add skills/write/SKILL.md
git commit -m "feat: write full bdd:write skill"
```

---

### Task 9: Rewrite skills/run/SKILL.md — full implementation

**Files:**
- Modify: `skills/run/SKILL.md`

- [ ] **Step 1: Write full SKILL.md for bdd:run**

```markdown
---
name: bdd:run
description: Use to execute BDD scenarios. Accepts a scenario filename, feature group name, or "all". Streams step output and reports failures with component-boundary investigation hints.
---

# bdd:run

Execute scenarios via checkmate. Requires `bdd:stack up` to have been run first.

## Usage

- `bdd:run <scenario-name>` — single scenario (filename without .json, e.g. `wizard-stores-operator-credentials`)
- `bdd:run <feature-group>` — all scenarios in a group (e.g. `init-wizard`)
- `bdd:run all` — full suite

## Steps

### 1. Verify stack is up

```bash
curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1 || echo "checkmate not running"
curl -sf http://127.0.0.1:8932/health > /dev/null 2>&1 || echo "playwright-http not running"
```

If either is not running: print "Stack is not running. Run `bdd:stack up` first." and stop.

Offer to run `bdd:stack up` automatically: "Would you like me to start the stack now? [Y/n]"

### 2. Resolve target to file paths

**Single scenario name:** Search `tests/e2e/scenarios/**/<name>.json`. If not found, list available scenario names and ask user to clarify.

**Feature group:** All `.json` files under `tests/e2e/scenarios/<group>/`.

**`all`:** All `.json` files under `tests/e2e/scenarios/`.

### 3. Register scenarios if needed

Run:
```bash
python3 <PLUGIN_ROOT>/scripts/run-suite.py \
  --config tests/e2e/checkmate.config.json \
  --scenarios tests/e2e/scenarios/ \
  --register-only
```

### 4. Execute scenarios

For each scenario file:
1. Get test case ID from checkmate by name.
2. Stream execution via `POST /api/test-cases/{id}/runs/stream`.
3. Print each step as it completes:
   - `  ✓ navigate /wizard` (pass)
   - `  ✗ assert_text "Welcome" — got "Error loading"` (fail)

### 5. On failure: print component boundary hint

After each failing scenario, print a hint based on where it failed:

| Failing step type | Hint |
|-------------------|------|
| `navigate`, `click`, `assert_element`, `assert_style` | **UI layer** — check browser console errors, HTML rendering, CSS. Open the page manually at `<base_url><path>`. |
| `assert_text` on data returned by an API call | **HTTP API layer** — check the Axum route handler. Try `curl <base_url>/api/...` directly. |
| Step that follows a model load, prewarm, or IPC operation | **Runner IPC layer** — check that flost-inference/flost-modeldb are running. Check core logs for IPC errors. |
| First step fails (navigate) | **Startup/readiness** — app may not be running or ready. Try `bdd:stack status`. |
| `assert_url` after a form submit or credential step | **Auth/session layer** — check wizard completion, JWT handling, redirect logic. |

### 6. Print summary

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Results: 4 passed, 1 failed  (12.3s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAILED: wizard-stores-operator-credentials
  Step 6: assert_text "Dashboard" — got "Error: DB not initialized"
  Screenshot: tests/e2e/screenshots/wizard-stores-operator-credentials-step6.png
  Hint: HTTP API layer — check the wizard credentials endpoint and DB connection.
```

Exit with error if any scenario failed (so CI fails correctly).
```

- [ ] **Step 2: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add skills/run/SKILL.md
git commit -m "feat: write full bdd:run skill"
```

---

### Task 10: Rewrite skills/ci/SKILL.md — full implementation

**Files:**
- Modify: `skills/ci/SKILL.md`

- [ ] **Step 1: Write full SKILL.md for bdd:ci**

```markdown
---
name: bdd:ci
description: Use to generate a GitHub Actions workflow for running BDD scenarios in CI. Emits YAML for you to copy into .github/workflows/bdd.yml.
---

# bdd:ci

Generate a GitHub Actions workflow from `tests/e2e/checkmate.config.json`.

## Steps

### 1. Read config

Load `tests/e2e/checkmate.config.json`. If missing, run `bdd:setup` first.

Extract:
- `stack.start_command` → substitute into workflow
- `stack.ready_url` → used for wait step
- `stack.ready_timeout_secs` → timeout value
- `checkmate.project_name` → workflow name

### 2. Render workflow

Read `<PLUGIN_ROOT>/templates/ci-workflow.yml`. Substitute:
- `{{START_COMMAND}}` → `stack.start_command`
- `{{READY_URL}}` → `stack.ready_url`
- `{{READY_TIMEOUT}}` → `stack.ready_timeout_secs`
- `{{PROJECT_NAME}}` → `checkmate.project_name`

### 3. Output

Print the rendered YAML in a code block, then print:

```
Copy this to .github/workflows/bdd.yml in your repo.

CI environment notes:
- OPENAI_API_KEY is optional. Add as a GitHub secret if you want checkmate's AI features.
- BDD_ENCRYPTION_KEY should be set as a GitHub secret (any random string).
- The workflow uses Docker (available on GitHub-hosted ubuntu-latest runners).
```
```

- [ ] **Step 2: Update templates/ci-workflow.yml to use substitution placeholders**

Edit `templates/ci-workflow.yml` — replace the hardcoded `npm start` and similar with `{{START_COMMAND}}`, `{{READY_URL}}`, `{{READY_TIMEOUT}}`, `{{PROJECT_NAME}}` markers as shown in the skill above.

- [ ] **Step 3: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add skills/ci/SKILL.md templates/ci-workflow.yml
git commit -m "feat: write full bdd:ci skill; parameterize CI workflow template"
```

---

### Task 11: Update README and write CLAUDE.md for the plugin repo itself

The plugin repo needs a CLAUDE.md so agents working on it know the conventions.

**Files:**
- Modify: `README.md`
- Create: `CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md for the plugin repo**

```markdown
# checkmate-bdd-plugin — Agent Instructions

## What this repo is

A Claude Code plugin that adds BDD scenario authoring and E2E testing to any project.
It is project-agnostic — no knowledge of any specific application.

## Layout

- `skills/*/SKILL.md` — skill instructions loaded by Claude Code
- `docker/docker-compose.yml` — service stack (build contexts, not registry images)
- `scripts/` — bash and python helpers called by skills
- `templates/` — files emitted or appended by skills (CI workflow, CLAUDE.md snippet, example config)
- `docs/superpowers/specs/` — design spec
- `docs/superpowers/plans/` — implementation plans

## Key constraints

- **Project-agnostic.** Skills must not reference any specific application, framework, or language.
- **No registry images.** Upstream repos (checkmate, playwright-http, checkmate-mcp) don't publish images. Use `build:` contexts in docker-compose pointing at `~/.checkmate-bdd/`.
- **Claude generates UTML.** `bdd:write` never calls checkmate's AI agent. Claude generates UTML inline.
- **OpenAI key is optional.** No plugin skill requires it.

## Testing the plugin locally

Install from local path:
```bash
claude plugin install file://$(pwd)
```

Test each skill:
```bash
claude -p "bdd:setup"
claude -p "bdd:stack up"
claude -p "bdd:write"
claude -p "bdd:run all"
claude -p "bdd:stack down"
```
```

- [ ] **Step 2: Update README.md to add local install instructions**

Add to README under "Installation":

```markdown
### Local development install

```bash
claude plugin install file:///path/to/checkmate-bdd-plugin
```
```

- [ ] **Step 3: Commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add CLAUDE.md README.md
git commit -m "docs: add CLAUDE.md and local install instructions"
```

---

### Task 12: Final wiring — fix docker-compose typo and verify full file set

There is a YAML syntax error in docker-compose.yml from Task 1 (extra `]` on playwright-http ports). Fix it, verify all files are present, do a final commit.

**Files:**
- Modify: `docker/docker-compose.yml`

- [ ] **Step 1: Fix ports typo in docker-compose.yml**

Change:
```yaml
    ports:
      - "8932:8932"]
```
To:
```yaml
    ports:
      - "8932:8932"
```

- [ ] **Step 2: Verify all expected files exist**

```bash
cd c:/tmp/checkmate-bdd-plugin
find . -not -path './.git/*' -type f | sort
```

Expected files:
```
./.claude-plugin/plugin.json
./.gitignore
./CLAUDE.md
./README.md
./docker/docker-compose.yml
./docs/superpowers/plans/2026-04-17-checkmate-bdd-plugin.md
./docs/superpowers/specs/2026-04-17-checkmate-bdd-plugin-design.md
./scripts/clone-deps.sh
./scripts/native-start.sh
./scripts/native-stop.sh
./scripts/run-suite.py
./scripts/wait-for-ready.sh
./skills/ci/SKILL.md
./skills/run/SKILL.md
./skills/setup/SKILL.md
./skills/stack/SKILL.md
./skills/write/SKILL.md
./templates/checkmate.config.json
./templates/ci-workflow.yml
./templates/claude-md-snippet.md
```

- [ ] **Step 3: Validate docker-compose YAML syntax**

```bash
docker compose -f docker/docker-compose.yml config > /dev/null && echo "compose syntax OK"
```

Expected: `compose syntax OK` (or skip if Docker not available — visual inspection is sufficient)

- [ ] **Step 4: Final commit**

```bash
cd c:/tmp/checkmate-bdd-plugin
git add -A
git commit -m "fix: correct docker-compose ports typo; add plan doc"
```

---

## Self-Review

**Spec coverage:**
- ✓ Section 1 (Architecture, service stack, Docker/native) — Tasks 1–3
- ✓ Section 2 (checkmate.config.json schema) — Task 4 template + Task 6 setup skill
- ✓ Section 3 (all five skills) — Tasks 6–10
- ✓ Section 4 (superpowers integration) — Task 6 (setup appends CLAUDE.md), Task 11 (CLAUDE.md)
- ✓ Section 5 (Docker compose) — Task 1 (rewrite with build contexts)
- ✓ Open question 1 (no registry images → build contexts) — addressed in Task 1
- ✓ Open question 2 (MCP registration → user-scoped settings.json) — addressed in Task 6
- ✓ Open question 3 (no OpenAI required) — addressed in Tasks 6, 8, 11
- ✓ Open question 4 (checkmate-mcp image) — build from source in compose, no separate image needed

**Placeholder scan:** No TBD/TODO in task steps. All code blocks are complete.

**Type consistency:** `run-suite.py` is referenced in Tasks 5, 7, 9 consistently. `PLUGIN_ROOT` is used consistently in skills 6–10 with the same resolution command.

**One gap found and fixed:** Task 7 (bdd:stack) references `--register-only` flag that doesn't exist in the Task 5 run-suite.py — added as a step in Task 7 to patch it.
