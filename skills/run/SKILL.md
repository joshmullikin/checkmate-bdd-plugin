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
