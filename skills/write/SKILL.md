---
name: bdd:write
description: Use when you need to write a new BDD scenario before implementing a feature or fixing a bug. Claude generates UTML JSON from natural language — no external AI service required. Write scenarios BEFORE implementation.
---

# bdd:write

Guided BDD scenario authoring. Claude (the coding agent) generates UTML JSON directly — no call to checkmate's AI agent, no OpenAI key required.

**Core rule: write the scenario before writing implementation code.** This skill enforces BDD discipline. It does not run the scenario — use `bdd:run` for that.

## Steps

1. Ask: "What behavior do you want to test?" Accept natural language.

2. Ask clarifying questions **one at a time**:
   - What is the starting state / precondition? (e.g. "app is running, wizard not completed")
   - What actions does the user or system take? (e.g. "user fills in credentials, clicks Submit")
   - What is the expected outcome / assertion? (e.g. "main dashboard appears, no error shown")

3. Generate UTML JSON inline from the answers. Follow the UTML 1.0 schema:
   ```json
   {
     "base_url": "<from checkmate.config.json>",
     "steps": [
       { "action": "navigate", "value": "/path", "description": "..." },
       { "action": "fill_form", "value": { "Field": "value" } },
       { "action": "click", "target": "Button label" },
       { "action": "assert_text", "value": "Expected text" }
     ]
   }
   ```

4. Show the generated UTML to the user. Ask if it looks right. Iterate until approved.

5. Ask which feature group this belongs to. List existing subdirectories under `tests/e2e/scenarios/` as options. Allow creating a new group.

6. Derive a kebab-case filename from the behavior description (e.g. "wizard stores operator credentials" → `wizard-stores-operator-credentials.json`).

7. Write to `tests/e2e/scenarios/<feature-group>/<filename>.json`.

8. If the stack is running (`bdd:stack status` shows checkmate healthy): register in checkmate via `POST /api/test-cases/project/{id}/` with `{"name": "<filename>", "utml": <json>}`.
   If the stack is not running: note that registration will happen automatically on the next `bdd:stack up`.

## UTML authoring guidelines

- Use natural language targets (`"Submit button"`, `"Email input"`) not CSS selectors unless the app has no accessible labels.
- Each scenario should test one behavior end-to-end — not a unit, not a full regression suite.
- Preconditions that require API setup (seeded data, auth state) should use `evaluate` steps to call setup endpoints directly.
- Keep scenarios independent — no shared state between scenario files.
- Add `"description"` fields to non-obvious steps.
