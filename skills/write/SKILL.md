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
