---
name: api_corrections
description: Corrected run-suite.py code fixing wrong API assumptions in the implementation plan — wrong endpoints, missing required fields, wrong field names, SSE parsing
type: reference
---

# API Corrections for run-suite.py

The plan's `run-suite.py` (Task 5) has several bugs. Use the corrected code below when implementing Task 5.

## What was wrong

| Plan assumption | Reality |
|----------------|---------|
| `POST /api/projects/` with `{"name": ...}` | `base_url` is also required |
| `POST /api/test-cases/project/{id}/` | Endpoint doesn't exist; use `POST /api/test-cases` with `project_id` in body |
| Body field `"utml": <json>` | No `utml` field; use `"steps": json.dumps(utml["steps"])` + `"natural_query": "string"` |
| SSE event type `"done"` for completion | Completion event type is `"result"` |
| `resp["passed"]` on result event | Field exists: `event["passed"]` — correct |

## Corrected run-suite.py

```python
#!/usr/bin/env python3
"""
run-suite.py
Register UTML scenario files into checkmate and run them.
Used by CI workflow and bdd:stack up --register-only.
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
        print(f"HTTP {e.code} {method} {path}: {e.read().decode()}", file=sys.stderr)
        raise


def ensure_project(checkmate_url: str, project_name: str, base_url: str) -> int:
    """Get or create project. Returns project id."""
    projects = checkmate_get(checkmate_url, "/api/projects")
    for p in projects:
        if p["name"] == project_name:
            return p["id"]
    # ProjectCreate requires both name AND base_url
    created = checkmate_post(checkmate_url, "/api/projects", {
        "name": project_name,
        "base_url": base_url,  # REQUIRED — use app base_url from config
    })
    print(f"  Created project '{project_name}' id={created['id']}")
    return created["id"]


def register_scenarios(checkmate_url: str, project_id: int,
                        scenarios_dir: str) -> list:
    """Register all UTML JSON files. Returns list of (test_case_id, scenario_name) tuples."""
    # Fetch existing test cases for this project
    existing = checkmate_get(checkmate_url, f"/api/test-cases/project/{project_id}")
    existing_by_name = {tc["name"]: tc["id"] for tc in existing}

    results = []
    for path in sorted(Path(scenarios_dir).rglob("*.json")):
        with open(path) as f:
            utml = json.load(f)

        name = path.stem  # filename without .json

        if name in existing_by_name:
            results.append((existing_by_name[name], name))
            continue

        # TestCaseCreate requires: project_id, name, natural_query, steps (JSON string)
        # steps must be a JSON-encoded string, not an array
        steps_json = json.dumps(utml.get("steps", []))

        tc = checkmate_post(checkmate_url, "/api/test-cases", {
            "project_id": project_id,
            "name": name,
            "natural_query": name.replace("-", " "),  # readable description
            "steps": steps_json,                       # JSON-encoded string
        })
        results.append((tc["id"], name))
        print(f"  Registered: {name} (id={tc['id']})")

    return results


def run_test_case(checkmate_url: str, case_id: int, name: str) -> bool:
    """Run a single test case via SSE stream. Returns True if passed."""
    url = f"{checkmate_url}/api/test-cases/{case_id}/runs/stream"
    req = urllib.request.Request(
        url,
        data=b"{}",   # optional body — empty JSON is fine
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
                payload_str = line[5:].strip()
                if not payload_str:
                    continue
                try:
                    event = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue

                if event.get("type") == "step":
                    # step event fields: step_number, action, target, value, passed, error, screenshot
                    status = "✓" if event.get("passed") else "✗"
                    action = event.get("action", "")
                    target = event.get("target") or event.get("value") or ""
                    err = f" — {event['error']}" if event.get("error") else ""
                    print(f"    {status} {action} {target}{err}")

                elif event.get("type") == "result":
                    # result event fields: passed, total_steps, passed_steps, failed_steps
                    passed = bool(event.get("passed", False))

    except urllib.error.HTTPError as e:
        print(f"  HTTP error running case {case_id}: {e.code} {e.read().decode()}", file=sys.stderr)
    except Exception as e:
        print(f"  Error running case {case_id}: {e}", file=sys.stderr)

    return passed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to checkmate.config.json")
    parser.add_argument("--scenarios", required=True, help="Path to scenarios directory")
    parser.add_argument("--register-only", action="store_true",
                        help="Register scenarios without running them")
    args = parser.parse_args()

    cfg = load_config(args.config)
    checkmate_url = cfg["checkmate"]["url"]
    project_name = cfg["checkmate"]["project_name"]
    app_base_url = cfg["base_url"]  # passed to ProjectCreate

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
        if run_test_case(checkmate_url, case_id, name):
            passed_count += 1
        else:
            failed_count += 1
            failures.append(name)

    print(f"\n{'='*40}")
    print(f"Results: {passed_count} passed, {failed_count} failed")
    if failures:
        print("Failed:")
        for name in failures:
            print(f"  - {name}")

    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
```

## Summary of changes from plan version

- `ensure_project`: added `base_url` arg; passes it to `POST /api/projects`
- `register_scenarios`: changed endpoint from `/api/test-cases/project/{id}/` to `/api/test-cases`; changed body from `{"name": ..., "utml": ...}` to `{"project_id": ..., "name": ..., "natural_query": ..., "steps": json.dumps(...)}`
- `run_test_case`: SSE parse looks for `type == "result"` not `type == "done"`; corrected field names on step events
- `--register-only` flag: added (was noted as missing in plan self-review)
