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
