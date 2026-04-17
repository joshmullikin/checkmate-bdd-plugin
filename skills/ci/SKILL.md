---
name: bdd:ci
description: Use to generate a GitHub Actions workflow for running BDD scenarios in CI. Outputs YAML to copy into .github/workflows/bdd.yml.
---

# bdd:ci

Emits a GitHub Actions workflow YAML parameterized from `checkmate.config.json`. The consuming repo copies this file in — the plugin does not modify `.github/` directly.

## Steps

1. Read `tests/e2e/checkmate.config.json`. If missing, instruct user to run `bdd:setup` first.
2. Render `templates/ci-workflow.yml` substituting project-specific values.
3. Print the rendered YAML.
4. Tell the user: "Copy this to `.github/workflows/bdd.yml` in your repo."

## Generated workflow structure

```yaml
name: BDD E2E Tests

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

jobs:
  bdd:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install plugin dependencies
        run: |
          # checkmate-mcp (Node)
          npm install --prefix <plugin-root>
          # playwright browsers
          pip install uv
          uv run playwright install chromium

      - name: Start BDD stack
        run: claude -p "bdd:stack up"
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}   # optional

      - name: Run scenarios
        run: claude -p "bdd:run all"

      - name: Stop BDD stack
        if: always()
        run: claude -p "bdd:stack down"

      - name: Upload failure screenshots
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: bdd-screenshots
          path: tests/e2e/screenshots/
```

Note: The workflow uses Docker (available on GitHub-hosted runners). `services.prefer_docker` is always treated as `true` in CI regardless of local config.
