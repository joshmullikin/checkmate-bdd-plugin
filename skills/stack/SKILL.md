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
