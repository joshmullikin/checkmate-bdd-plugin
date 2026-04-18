## BDD testing

This project uses [checkmate-bdd-plugin](https://github.com/joshmullikin/checkmate-bdd-plugin)
for BDD scenario authoring and E2E testing. No API keys required — all AI work runs inline.

Install the plugin before starting any feature work:

```bash
claude plugin install https://github.com/joshmullikin/checkmate-bdd-plugin
```

### Workflow

**Starting a feature:**
- After brainstorming, run `bdd:generate` to bulk-ideate acceptance scenarios for the feature area.
- Pick the relevant ones and materialize each with `bdd:write`.
- Or skip bulk ideation and go straight to `bdd:write` for a single scenario.
- For complex UI flows, record a scenario directly with `bdd:record`.
- Written scenarios become acceptance criteria — commit them before writing implementation code.

**During implementation:**
- Run `bdd:run <scenario-name>` after completing each piece of functionality.
- On failure, `bdd:run` will classify the error and propose a heal automatically.

**Before marking implementation complete:**
- Run `bdd:run all` and confirm all scenarios pass.

**Service stack:**
- `bdd:stack up` — start checkmate + playwright-http + checkmate-mcp
- `bdd:stack down` — stop all services
- `bdd:stack status` — check health

**Scenario files:** `tests/e2e/scenarios/<feature-group>/<scenario-name>.json`
