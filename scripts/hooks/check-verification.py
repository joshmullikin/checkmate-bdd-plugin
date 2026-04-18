#!/usr/bin/env python3
"""
Stop hook: verify BDD scenarios have been run before Claude finishes.
Reads bdd.verification_mode from checkmate.config.json:
  required  → block with instruction to run bdd:run all (only when stack is up)
  prompted  → systemMessage reminder (only when stack is up)
Does nothing if no config, no scenarios, or stack is not running.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    config_path = Path(project_dir) / "tests/e2e/checkmate.config.json"

    if not config_path.exists():
        sys.exit(0)

    try:
        cfg = json.loads(config_path.read_text())
        mode = cfg.get("bdd", {}).get("verification_mode", "prompted")
        base = cfg["checkmate"]["url"]
    except Exception:
        sys.exit(0)

    # Only act if there are scenario files to verify
    scenarios_dir = Path(project_dir) / "tests/e2e/scenarios"
    scenarios = list(scenarios_dir.rglob("*.json")) if scenarios_dir.exists() else []
    if not scenarios:
        sys.exit(0)

    # Only act if checkmate is currently running (no stack = nothing to verify)
    try:
        urllib.request.urlopen(f"{base}/health", timeout=2)
    except Exception:
        sys.exit(0)

    count = len(scenarios)
    names = ", ".join(s.stem for s in scenarios[:3])
    if count > 3:
        names += f" (+{count - 3} more)"

    if mode == "required":
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"BDD verification required before completing. "
                f"{count} scenario(s) found ({names}). "
                f"Run `bdd:run all` and confirm all pass, then continue."
            ),
        }))
    else:
        print(json.dumps({
            "systemMessage": (
                f"[checkmate-bdd] Reminder: {count} BDD scenario(s) present ({names}). "
                f"Run `bdd:run all` before marking work complete."
            ),
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
