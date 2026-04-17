---
name: upstream_repos
description: Exact API shapes, model fields, SSE event format, health endpoints, env vars, and repo structure for checkmate, playwright-http, and checkmate-mcp — verified from source code
type: reference
---

# Upstream Repo Reference

## Repository locations

| Repo | URL | Language | Clone target |
|------|-----|----------|--------------|
| checkmate | https://github.com/ksankaran/checkmate | Python (FastAPI + SQLModel) | `~/.checkmate-bdd/checkmate` |
| playwright-http | https://github.com/ksankaran/playwright-http | Python (FastAPI) | `~/.checkmate-bdd/playwright-http` |
| checkmate-mcp | https://github.com/ksankaran/checkmate-mcp | TypeScript (Node) | `~/.checkmate-bdd/checkmate-mcp` |

None of the three repos publish Docker images to a registry. All have Dockerfiles. Docker compose must use `build:` contexts pointing at the cloned directories.

---

## checkmate (https://github.com/ksankaran/checkmate)

### Runtime
- Python 3.12, uv, FastAPI, SQLModel, SQLite (dev) / PostgreSQL (prod)
- Start: `uv run uvicorn api.main:app --host 0.0.0.0 --port 8000`
- Health endpoint: `GET /health` → `{"status": "healthy"}`

### Required environment variables
```
OPENAI_API_KEY=          # Required for AI agent features; optional for pure test execution
ENCRYPTION_KEY=          # Required (Fernet key). Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DATABASE_URL=            # Default: sqlite:///./qa_testing.db
PLAYWRIGHT_EXECUTOR_URL= # Default: http://localhost:8932
```

Optional:
```
LLM_PROVIDER=openai      # or "azure"
INTELLIGENT_RETRY_ENABLED=false
```

### API endpoints (all prefixed `/api`)

**Projects**
- `GET  /api/projects` — list all projects → `List[ProjectRead]`
- `POST /api/projects` — create project → `ProjectRead`
- `GET  /api/projects/{id}` — get project → `ProjectRead`

**`ProjectCreate` required fields:**
```json
{
  "name": "string",
  "base_url": "string"    // REQUIRED — not optional
}
```
Optional: `description`, `base_prompt`, `config`

**`ProjectRead` shape:**
```json
{
  "id": 1,
  "name": "string",
  "base_url": "string",
  "description": null,
  "base_prompt": null,
  "config": null,
  "next_test_case_number": 1,
  "created_at": "...",
  "updated_at": "..."
}
```

---

**Test Cases**
- `GET  /api/test-cases/project/{project_id}` — list test cases → `List[TestCaseRead]`
- `POST /api/test-cases` — create test case → `TestCaseRead`
- `GET  /api/test-cases/{id}` — get test case → `TestCaseRead`
- `PUT  /api/test-cases/{id}` — update test case → `TestCaseRead`

**`TestCaseCreate` required fields:**
```json
{
  "project_id": 1,
  "name": "string",
  "natural_query": "string",   // REQUIRED — human-readable description of what to test
  "steps": "[]"                // REQUIRED — JSON-encoded string of step objects (NOT a `utml` field)
}
```
Optional: `description`, `expected_result`, `tags`, `priority`, `status`

**`steps` field is a JSON-encoded string**, not an array:
```python
import json
steps_json = json.dumps([
    {"action": "navigate", "value": "/wizard"},
    {"action": "click", "target": "Submit button"},
    {"action": "assert_text", "value": "Welcome"}
])
# Pass steps_json (a string) as the "steps" field
```

**`TestCaseRead` shape:**
```json
{
  "id": 1,
  "project_id": 1,
  "name": "string",
  "natural_query": "string",
  "steps": "[{\"action\":\"navigate\",...}]",
  "description": null,
  "expected_result": null,
  "tags": null,
  "priority": "medium",
  "status": "draft",
  "test_case_number": 1,
  "created_at": "...",
  "updated_at": "...",
  "created_by": null
}
```

---

**Test Execution (SSE streaming)**
- `POST /api/test-cases/{id}/runs/stream` — execute a test case, returns SSE stream

Request body (all optional):
```json
{
  "browser": "chromium-headless",
  "viewport": {"width": 1280, "height": 720},
  "retry": {"max_retries": 0, "retry_mode": "simple"},
  "environment_id": null
}
```

SSE stream format — each event is `data: <json>\n\n`:
```jsonl
data: {"type": "step", "step_number": 1, "action": "navigate", "target": null, "value": "/wizard", "passed": true, "error": null, "screenshot": null}
data: {"type": "step", "step_number": 2, "action": "click", "target": "Submit button", "value": null, "passed": false, "error": "Element not found", "screenshot": "/path/to/screenshot.png"}
data: {"type": "result", "passed": false, "total_steps": 3, "passed_steps": 1, "failed_steps": 1}
```

**Batch execution:**
- `POST /api/projects/{project_id}/test-cases/runs/stream` — run multiple test cases
  - Body: `{"test_case_ids": [1, 2, 3], "browser": "chromium-headless", "parallel": 1}`

**Direct step execution (no stored test case needed):**
- `POST /api/test-runs/execute/stream` — execute steps directly
  - Body: `{"project_id": 1, "steps": [...], "browser": "chromium-headless"}`

---

### Dockerfile
- Base: `python:3.12-slim`
- Uses uv for deps
- Exposes port 8000
- CMD: `uv run uvicorn api.main:app --host 0.0.0.0 --port 8000`

---

## playwright-http (https://github.com/ksankaran/playwright-http)

### Runtime
- Python, uv, FastAPI, Playwright
- Start: `uv run uvicorn executor.main:app --host 127.0.0.1 --port 8932`
- After clone: must run `uv run playwright install chromium` (or other browsers)
- Health endpoint: `GET /health` (verified from main.py pattern; returns 200)

### Required environment variables
```
PORT=8932
AVAILABLE_BROWSERS=chromium-headless   # Comma-separated; first is default
BROWSER_TIMEOUT=30000
```

### Structure
```
executor/
├── main.py         # FastAPI app, lifespan manages browser startup/shutdown
├── runner.py       # execute_test() — runs UTML steps via Playwright
├── actions.py      # Individual action implementations (navigate, click, type, etc.)
├── browser.py      # Browser manager (startup, shutdown, get instance)
├── element_finder.py  # Natural language element resolution
└── ...
```

### Dockerfiles
- `Dockerfile` — standard Python base
- `Dockerfile.chainguard` — hardened Chainguard base (for production)

### How it fits in
checkmate calls playwright-http via `PLAYWRIGHT_EXECUTOR_URL`. playwright-http does not expose a public API that the plugin uses directly — it is called only by checkmate. The plugin interacts with playwright-http only to:
1. Start it (so checkmate can reach it)
2. Health-check it (to confirm it's ready)
3. Install browsers via `uv run playwright install chromium`

---

## checkmate-mcp (https://github.com/ksankaran/checkmate-mcp)

### Runtime
- Node.js 22+, TypeScript
- Start: `node dist/server.js` (after `npm run build`)
- Or dev: `npm run dev`
- Health endpoint: `GET /health` → 200
- MCP endpoint: `POST /mcp`

### Required environment variables
```
PORT=3003
CHECKMATE_URL=http://127.0.0.1:8000   # Must use 127.0.0.1, NOT localhost (per README)
```

### MCP tools exposed
- `list_projects` — list all Checkmate projects
- `list_test_cases` — list test cases in a project (arg: `project_id`)
- `run_test` — execute a test case by ID (args: `test_case_id`, optional `browser`)
- `run_natural_test` — execute test from natural language (args: `project_id`, `description`, optional `browser`)

### Claude Code MCP registration
Add to `~/.claude/settings.json` under `mcpServers`:
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

### Dockerfile
Multi-stage: Node 22 builder (npm ci, tsc), then Node 22 production image.
Exposes port 3003.
CMD: `node dist/server.js`

### Structure
```
server.ts              # MCP HTTP server entry point
src/
├── checkmate-client.ts  # HTTP client for checkmate API (listProjects, listTestCases, executeTestCase, etc.)
└── types.ts             # TypeScript interfaces
ui/                    # HTML UI for VS Code MCP Apps panel
```

---

## Key corrections to the plan's run-suite.py

The initial `run-suite.py` in the plan has several bugs based on wrong API assumptions:

1. **`POST /api/projects/` with just `{"name": ...}` will fail** — `base_url` is a required field on `ProjectCreate`. Must pass `{"name": "...", "base_url": "..."}` (use `base_url` from `checkmate.config.json`).

2. **`POST /api/test-cases/project/{id}/` does not exist** — correct endpoint is `POST /api/test-cases` (no project_id in path). `project_id` goes in the request body.

3. **There is no `utml` field** — `TestCaseCreate` has `steps` (JSON-encoded string) and `natural_query` (required string). To create a test case from a UTML file:
   - `steps` = `json.dumps(utml_json["steps"])` (JSON-encode the steps array)
   - `natural_query` = the scenario filename or a description string

4. **SSE stream returns `text/event-stream`** — parse with `data: ` prefix stripping. Event types are `"step"` and `"result"`, not `"step"` and `"done"`.

5. **`POST /api/test-cases/{id}/runs/stream` takes optional body** — can POST empty JSON `{}`. Does not require a body.

See `reference_api_corrections.md` for corrected run-suite.py code.
