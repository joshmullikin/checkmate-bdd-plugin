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
