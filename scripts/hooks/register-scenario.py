#!/usr/bin/env python3
"""
PostToolUse/Write hook: auto-register UTML scenario files in checkmate.
Fires after any Write tool call. Exits 0 always (non-blocking).
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")

    # Only process scenario JSON files
    if "tests/e2e/scenarios/" not in file_path.replace("\\", "/"):
        sys.exit(0)
    if not file_path.endswith(".json"):
        sys.exit(0)

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    config_path = Path(project_dir) / "tests/e2e/checkmate.config.json"
    if not config_path.exists():
        sys.exit(0)

    try:
        cfg = json.loads(config_path.read_text())
        base = cfg["checkmate"]["url"]
        project_name = cfg["checkmate"]["project_name"]
    except Exception:
        sys.exit(0)

    # Only proceed if checkmate is running
    try:
        urllib.request.urlopen(f"{base}/health", timeout=2)
    except Exception:
        sys.exit(0)

    scenario_path = Path(file_path)
    if not scenario_path.exists():
        sys.exit(0)

    scenario_name = scenario_path.stem

    try:
        projects = json.loads(urllib.request.urlopen(f"{base}/api/projects", timeout=5).read())
        proj = next((p for p in projects if p["name"] == project_name), None)
        if not proj:
            sys.exit(0)
        project_id = proj["id"]

        existing = json.loads(
            urllib.request.urlopen(f"{base}/api/test-cases/project/{project_id}", timeout=5).read()
        )
        if any(c["name"] == scenario_name for c in existing):
            sys.exit(0)

        utml = json.loads(scenario_path.read_text())
        body = json.dumps({
            "project_id": project_id,
            "name": scenario_name,
            "natural_query": scenario_name.replace("-", " "),
            "steps": json.dumps(utml.get("steps", [])),
        }).encode()
        req = urllib.request.Request(
            f"{base}/api/test-cases",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        result = json.loads(urllib.request.urlopen(req, timeout=10).read())

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[checkmate-bdd] Scenario '{scenario_name}' registered in checkmate "
                    f"(id={result['id']}). Run it with: bdd:run {scenario_name}"
                ),
            }
        }))
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
