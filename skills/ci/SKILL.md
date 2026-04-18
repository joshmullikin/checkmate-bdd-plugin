---
name: bdd:ci
description: Use to generate a GitHub Actions workflow for running BDD scenarios in CI. Emits YAML for you to copy into .github/workflows/bdd.yml. No API key required — CI uses run-suite.py directly.
---

# bdd:ci

Generate a GitHub Actions workflow from `tests/e2e/checkmate.config.json`.

## Step 1: Read config

Load `tests/e2e/checkmate.config.json`. If missing, run `bdd:setup` first.

Extract:
- `stack.start_command` → `{{START_COMMAND}}`
- `stack.ready_url` → `{{READY_URL}}`
- `stack.ready_timeout_secs` → `{{READY_TIMEOUT}}`
- `checkmate.project_name` → `{{PROJECT_NAME}}`
- `plugin_root` → `{{PLUGIN_ROOT}}`

## Step 2: Render workflow

Read `<plugin_root>/templates/ci-workflow.yml`. Substitute all `{{...}}` placeholders with the values above.

## Step 3: Output

Print the rendered YAML in a code block, then print:

```
Copy this to .github/workflows/bdd.yml in your repo.

CI notes:
- ENCRYPTION_KEY should be set as a GitHub secret (any random string works).
- OPENAI_API_KEY is NOT needed — this plugin uses Claude for all AI work.
- The workflow uses Docker (available on GitHub-hosted ubuntu-latest runners).
- Docker image builds are cached between runs via GitHub Actions cache.
```
