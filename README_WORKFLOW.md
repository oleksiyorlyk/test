# AI Test Automation Generator: Human-checkpoint workflow controllers

Put the five `.py` controller/helper files in the **repository root**, alongside `backend/` and `test aplikacia/`. Put `process_results.py` in `backend/` if it is not already there. These are CLI wrappers over existing modules; you do not need to rewrite existing modules.

## Execution and human review boundaries

```
python run_1_prepare.py --id 1
    backend.getus                -> fetch/normalize User Story
    backend.generate_scenarios  -> OpenAI generation + validation
    STOP: human reviews story.normalized.json and scenarios.draft.json

python run_2_generate.py --id 1 --revision 7 --reviewer "QA Reviewer" --approve-reviewed
    backend.approve_scenarios   -> saves human approval
    backend.generate_playwright -> OpenAI generates .spec.js files
    STOP: human reviews every .spec.js file

python run_3_execute.py --id 1 --revision 7 --reviewed-code
    npx playwright test          -> executes ONLY this Story revision
    backend.process_results     -> creates execution.summary.json
    STOP: human reviews HTML report and summary; failures do not block summary

python run_4_publish.py --id 1 --revision 7
    backend.publish_outputs     -> DRY RUN (no Azure API writes)

python run_4_publish.py --id 1 --revision 7 --publish
    backend.publish_outputs     -> creates Azure Test Cases and attaches JS files
```

The revision is printed by Stage 1; do **not** assume it will always be 7. Every command must be run from the repository root, e.g. `C:\Users\Someone\Desktop\ai-test-automation-generator`.

## Existing Story #1 / revision 7

The GitHub repository already has the generated `.spec.js` files, so you probably **do not want** to regenerate them. Stage 2 refuses to overwrite generated tests without `--replace-tests`. You can start at Stage 3 after manually reviewing them, assuming local approval and scenario data exist. Then Stage 4 can publish them.

## Flags and safety

- `--refresh` on Stage 1 allows re-fetching/regeneration for an ID with existing data. This can make earlier scenario approvals stale. OpenAI calls cost money.
- `--approve-reviewed` on Stage 2 is an explicit acknowledgment of *human* scenario review, not an automatic approval. A previously valid approval is reused. For changed drafts, use `--replace-approval` after reviewing again.
- `--replace-tests` on Stage 2 overwrites generated tests for that Story revision.
- `--reviewed-code` on Stage 3 is an acknowledgment that the user has manually reviewed the generated JavaScript. Generated code is not guaranteed safe just because syntax checks passed. Run the prototype app and Playwright in an isolated dev environment.
- Stage 3 deliberately continues processing a JSON report even if Playwright exits nonzero due to assertion failures. It removes the old `results.json` before execution to avoid stale results.
- Stage 4 previews by default. `--publish` explicitly opts in to Azure DevOps modifications. M5 currently publishes test cases and code attachments, NOT execution results.
- Reports in `backend/data/` are ignored by `.gitignore` and will remain local.

## First-time local setup

Install Python packages with `pip install -r backend/requirements.txt`. In `test aplikacia/` run `npm ci` and `npx playwright install chromium` once. Put credentials in your existing `backend/.env`; do not commit it.

## Future frontend integration

Each controller represents a backend workflow boundary that can later become a job or API endpoint. The CLI orchestrators are for local development; do not expose them directly as unauthenticated web API operations. Use authenticated endpoints, durable job states, and reviewed artifacts for multi-user deployments.
