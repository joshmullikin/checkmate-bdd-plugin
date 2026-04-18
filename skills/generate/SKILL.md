---
name: bdd:generate
description: Use when starting a new feature area to bulk-ideate BDD test cases. Claude reads the upstream generator prompt and schema to produce a set of scenario ideas. You pick which to materialize into full UTML files via bdd:write.
---

# bdd:generate

Bulk-ideate acceptance test cases for a feature area. Claude reads the backend's generator schema and produces structured ideas — no duplication, no drift.

## Step 1: Ask for feature area

Ask: "What feature or area do you want to generate test cases for? (e.g. 'user login', 'checkout flow', 'model picker')"

## Step 2: Ask for count (optional)

Ask: "How many test case ideas? [default: 5]"

## Step 3: Read backend source — generator

Read the file at `~/.checkmate-bdd/checkmate/agent/nodes/generator.py`.

Find the `GENERATOR_PROMPT` and the `GeneratedTestCases` / `GeneratedTestCase` Pydantic classes.

Using the project info from `tests/e2e/checkmate.config.json` (`checkmate.project_name`, `base_url`) and the user's feature area, produce a `GeneratedTestCases`-shaped result following the generator system prompt:
- Each `GeneratedTestCase` has: `name`, `natural_query`, `priority`, `tags`
- Generate the requested count; cover happy path + edge cases + error scenarios per the prompt

## Step 4: Present ideas and let user pick

Present the generated list as a numbered table:

```
Generated 5 test cases for "user login":

1. [HIGH]     user-login-success
   "User enters valid credentials and is redirected to the dashboard"
   Tags: auth, happy-path

2. [HIGH]     user-login-invalid-password
   "User enters wrong password and sees an error message"
   Tags: auth, error

3. [MEDIUM]   user-login-empty-fields
   "User submits login form with empty fields and sees validation errors"
   Tags: auth, validation

4. [MEDIUM]   user-login-account-locked
   "User account is locked after 5 failed attempts"
   Tags: auth, security

5. [LOW]      user-login-remember-me
   "User checks remember-me and session persists after browser restart"
   Tags: auth, session
```

Ask: "Which would you like to write scenarios for? Enter numbers (e.g. 1,3) or 'all'."

## Step 5: Materialize selected scenarios

For each selected test case, run the `bdd:write` flow using `natural_query` as the pre-filled behavior description. Skip the initial "what behavior" question — pass `natural_query` directly into Step 2 of `bdd:write`.

Confirm the feature group once and reuse it for all selected scenarios in this session.
