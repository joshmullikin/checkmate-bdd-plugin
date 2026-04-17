## BDD testing

This project uses [checkmate-bdd-plugin](https://github.com/joshmullikin/checkmate-bdd-plugin)
for BDD scenario authoring and E2E testing.

Install the plugin before starting any feature work:

```bash
claude plugin install https://github.com/joshmullikin/checkmate-bdd-plugin
```

Workflow:
- After brainstorming a feature, run `bdd:write` for each key behavior before writing plans.
- Before marking any implementation complete, run `bdd:run all` and confirm scenarios pass.
- Scenario files live in `tests/e2e/scenarios/`.
- Service stack: `bdd:stack up` to start, `bdd:stack down` to stop.
