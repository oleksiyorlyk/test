# Frontend integration guide — AI Test Automation Generator

This guide explains how to build and connect a frontend to the **two-stage Python backend** in [oleksiyorlyk/test](https://github.com/oleksiyorlyk/test). It describes the **current repository implementation** and separates it from the HTTP API, frontend UI, and production safeguards that still need to be built.

> **Main rule:** The frontend does **not** import Python files. A **FastAPI backend** imports `backend.stage1` and `backend.stage2`, exposes HTTP endpoints, and returns JSON to the frontend.
>
> There are **only two processing stages**: **(1) generate scenarios**, and **(2) approve, generate tests, execute, and publish**. Reading/editing scenarios between the stages is part of the human-review checkpoint, not a third processing stage.

## 1. Architecture and user journey

```text
Frontend (React / JavaScript / HTML)
  │
  ├─ User selects an Azure DevOps User Story ID
  ├─ Clicks "Generate scenarios"
  │     │ POST /api/stories/{id}/generate
  │     ▼
  │   FastAPI → backend.stage1.prepare_scenarios(id)
  │     ├─ Azure DevOps: fetch User Story
  │     ├─ Normalize title, description, acceptance criteria
  │     ├─ OpenAI: generate structured test scenarios
  │     ├─ Validate and save scenario draft
  │     └─ Return story + draft + validation + review_hash
  │
  ├─ Human reviews TC-001, TC-002, ...
  ├─ Optional: edits scenarios and saves them
  │     │ PUT /api/stories/{id}/review
  │     ▼
  │   FastAPI → backend.stage1.save_reviewed_scenarios(...)
  │     └─ Return updated draft and NEW review_hash
  │
  ├─ Clicks "Approve and run" (explicit approval)
  │     │ POST /api/stories/{id}/approve-and-run
  │     ▼
  │   FastAPI → backend.stage2.approve_execute_publish(...)
  │     ├─ Verify reviewed draft hash and validation
  │     ├─ Record approval as JSON files
  │     ├─ OpenAI: generate Playwright .spec.js files
  │     ├─ Playwright: execute tests against target app
  │     ├─ Summarize pass/fail/timeout results
  │     ├─ Azure DevOps: create/update Test Case work items
  │     ├─ Azure DevOps: attach JS files and execution reports
  │     └─ Return execution + publication summary
  │
  └─ Display result summary and Azure DevOps work-item IDs
```

The frontend **never receives the Azure DevOps PAT or OpenAI API key**. Keep credentials in `backend/.env` on the server.

## 2. Stage 1: generate scenarios

**Python function:** `backend.stage1.prepare_scenarios(story_id: int) -> dict`

**Call from backend:**

```python
from backend.stage1 import prepare_scenarios

result = prepare_scenarios(1)
```

**Input from frontend:** only the numeric Azure DevOps **User Story ID**, for example `1`.

**What Stage 1 receives internally:** the User Story returned by Azure DevOps (`id`, `revision`, `title`, HTML `description`, HTML acceptance criteria), and the OpenAI settings in `.env`.

**What Stage 1 does:**

1. `azure.py`: fetch work item and verify type `User Story`.
2. `normalizer.py`: convert HTML to readable text, parse acceptance criteria (`AC1`, `AC2`, ...), reject ambiguous requirements.
3. `llm.py` + `prompts.py`: generate structured scenarios using OpenAI.
4. `scenarios.py`: validate scenario IDs, AC coverage, evidence quotes, required actions/results, and `READY`/`BLOCKED` statuses.
5. `stage1.py`: save a draft and return it for review. **No approval and no Azure DevOps write occur in Stage 1.**

**Actual top-level return keys:**

```json
{
  "story_id": 1,
  "revision": 84,
  "status": "PENDING_REVIEW",
  "story": { "id": 1, "title": "...", "acceptance_criteria": [] },
  "draft": { "story_id": 1, "scenarios": [] },
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": [],
    "coverage": {},
    "scenario_count": 5,
    "ready_count": 5,
    "blocked_count": 0
  },
  "review_hash": "<sha256 of this exact draft>"
}
```

*Values and abbreviated nested objects are illustrative; the real return includes the complete Story and scenarios.*

Each `draft.scenarios[]` contains:

| Field | Meaning |
| --- | --- |
| `test_id`, `title` | Example: `TC-001`, scenario title |
| `acceptance_criterion_id`, `evidence_quote` | Trace back to Story requirement |
| `test_type` | `positive`, `negative`, or `boundary` |
| `preconditions`, `test_data` | Arrays of strings |
| `actions`, `expected_results` | Arrays of human-readable strings |
| `status`, `blocked_reason` | `READY`/`BLOCKED`; reason if blocked |

**Saved locally:**

```text
backend/data/stories/1/
├── last_prepared.json       # {"story_id": 1, "revision": 84}
└── rev_84/
    ├── story.raw.json
    ├── story.normalized.json
    ├── scenarios.draft.json
    ├── scenarios.validation.json
    └── scenarios.generation.json
```

The backend discovers the current prepared revision via `last_prepared.json`, so the frontend does **not** need to pass the revision to Stage 2. Starting a new Stage 1 regeneration invalidates old approval files and the old prepared marker.

## 3. Human-review checkpoint: what it really means

Human approval is **not** an Azure DevOps approval workflow. It is a deliberate action performed in the frontend and recorded by the Python backend.

### Display the generated scenarios

After Stage 1, show:

- Story title, description, and acceptance criteria.
- Each scenario's `test_id`, title, linked AC, type, preconditions, test data, actions, expected results, and `READY`/`BLOCKED` status.
- Validation errors/warnings and coverage.
- Two actions: **Save edits** (if editable) and **Approve and run**.

**Do not automatically call Stage 2 after Stage 1.** The user must explicitly approve.

### Reload draft after page refresh

```python
from backend.stage1 import get_review

review = get_review(story_id=1)
```

This returns the same review payload shape as Stage 1, including the *current* `review_hash`, but does not regenerate scenarios.

### Save edits without approving

```python
from backend.stage1 import save_reviewed_scenarios

review = save_reviewed_scenarios(
    story_id=1,
    edited_batch=updated_draft,   # Full ScenarioBatch object
    expected_hash=previous_review_hash,
)
```

- Validates the edited draft and replaces `scenarios.draft.json`.
- Rejects the save if another edit changed the draft (hash mismatch).
- Clears previous approval files.
- Returns a **new** `review_hash`. Store it in frontend state and send that new value for approval.
- `edited_batch` must contain the full `{"story_id": 1, "scenarios": [...]}` object with all required scenario fields.

### What actually happens when the user approves

The **Approve and run** click should trigger the API to invoke:

```python
from backend.stage2 import approve_execute_publish

result = approve_execute_publish(
    story_id=1,
    reviewer=authenticated_user_id,   # Derived server-side from login
    expected_hash=current_review_hash, # Supplied by the review screen
)
```

Inside Stage 2:

1. Read `last_prepared.json` and the saved draft for the Story.
2. Verify `story_id`, revision, and (when provided) `expected_hash == digest(current_draft)`.
3. Validate the scenarios again; require at least one `READY` scenario.
4. Call `approve_draft(folder, reviewer=..., replace=True)` in `backend/approval.py`.
5. Call `load_approved_scenarios(folder)` to verify the approval record and hashes.
6. Only then generate executable tests.

Approval creates:

```text
backend/data/stories/1/rev_84/
├── scenarios.approved.json  # Copy of the approved scenario batch
└── scenarios.approval.json  # Approval metadata and checksums
```

**Example approval record (abridged):**

```json
{
  "status": "APPROVED",
  "reviewer": "authenticated-user-id",
  "approved_at": "<UTC timestamp>",
  "story_id": 1,
  "story_revision": 84,
  "story_sha256": "...",
  "draft_sha256": "...",
  "approved_sha256": "...",
  "ready_count": 5,
  "blocked_count": 0
}
```

SHA-256 checks bind the approval to the **exact saved Story and scenario draft**. If the approved JSON, draft, or Story changes afterward, `load_approved_scenarios()` refuses to proceed. **Hashes verify consistency, not who actually clicked approval.** Authentication/authorization must be enforced by the API.

> **Current-code caveat:** `expected_hash` and `reviewer` are optional in `approve_execute_publish()` for local CLI convenience. The **web API must require the hash** and derive the reviewer from an authenticated session. Otherwise the intended human-approval safeguard can be bypassed by calling Stage 2 directly.

## 4. Stage 2: generate, execute, publish

**Python function:** `backend.stage2.approve_execute_publish(story_id, *, reviewer=None, expected_hash=None) -> dict`

**Inputs:** Story ID from URL, review hash from the review screen, reviewer identity from backend authentication; the actual scenario draft and Story are read from saved files.

| Order | Internal step | Result |
| --- | --- | --- |
| 1 | Validate draft and record approval | `scenarios.approved.json`, `scenarios.approval.json` |
| 2 | `backend.generate_playwright` + OpenAI | Generated `tc-001.spec.js`, etc.; `playwright.generation.json` |
| 3 | Run Playwright | `test-results/results.json`, HTML report |
| 4 | `backend.process_results` | `execution.summary.json` with statuses per test |
| 5 | `backend.publish_outputs --publish` | Create/update linked Test Case work items; attach `.spec.js` files to the User Story |
| 6 | Stage 2 result uploader | Attach summary JSON, raw Playwright JSON, zipped HTML report to the User Story |

Only `READY` scenarios become Playwright tests; `BLOCKED` scenarios are excluded.

**Actual top-level return keys:**

```json
{
  "story_id": 1,
  "revision": 84,
  "status": "PUBLISHED",
  "reviewer": "authenticated-user-id",
  "execution": { "total": 5, "passed": 4, "failed": 1, "timed_out": 0, "tests": [] },
  "devops": {
    "story_id": 1,
    "story_revision": 84,
    "test_cases": { "TC-001": 2, "TC-002": 3 },
    "test_case_actions": { "TC-001": "updated", "TC-002": "created" },
    "ignored_duplicate_test_cases": {},
    "attachments": {},
    "blocked": []
  },
  "result_uploads": {
    "story_id": 1,
    "story_revision": 84,
    "playwright_exit_code": 0,
    "attachments": {}
  }
}
```

*Abbreviated example, not actual execution data.* `execution.tests[]` includes individual results, durations, and available failure details. `devops.test_cases` maps scenario IDs to real Azure DevOps work item IDs.

**Important:** `status: "PUBLISHED"` means the publishing workflow completed, **not** that every test passed. Test assertion failures are intentionally processed and published. The uploader stores reports as **User Story attachments**, not official Azure Test Plans test runs.

The current publisher updates an existing generated Test Case in place if its generator signature matches the Story and TC number; with multiple matches it selects the lowest Azure work item ID and leaves the other duplicates alone. It checks whether the Story's requirement text changed before publishing.

## 5. Recommended HTTP API (FastAPI)

The repository already contains the service functions, but **does not yet contain HTTP API routes**. Create `backend/api.py` and have it import the functions, rather than asking JavaScript to import `.py` files.

### Routes

| Method | URL | What the frontend does | Python function |
| --- | --- | --- | --- |
| `POST` | `/api/stories/{story_id}/generate` | Start Stage 1 | `prepare_scenarios(story_id)` |
| `GET` | `/api/stories/{story_id}/review` | Reload current draft | `get_review(story_id)` |
| `PUT` | `/api/stories/{story_id}/review` | Save edits, not approve | `save_reviewed_scenarios(story_id, edited_batch, expected_hash=...)` |
| `POST` | `/api/stories/{story_id}/approve-and-run` | Explicit approval; start Stage 2 | `approve_execute_publish(story_id, reviewer=..., expected_hash=...)` |

The last two routes are support operations within the two-stage workflow, not new processing stages.

### Minimal development-only FastAPI example

Install FastAPI and Uvicorn in the backend's Python environment. The following demonstrates the wiring and can run **locally**, but **must not be exposed publicly without authentication, authorization, and job handling**.

Create `backend/api.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel

from backend.stage1 import (
    prepare_scenarios,
    get_review,
    save_reviewed_scenarios,
)
from backend.stage2 import approve_execute_publish

app = FastAPI(title="AI Test Automation Generator")

class EditRequest(BaseModel):
    draft: dict
    review_hash: str

class ApproveRequest(BaseModel):
    review_hash: str

@app.post("/api/stories/{story_id}/generate")
def generate(story_id: int):
    return prepare_scenarios(story_id)

@app.get("/api/stories/{story_id}/review")
def review(story_id: int):
    return get_review(story_id)

@app.put("/api/stories/{story_id}/review")
def edit_review(story_id: int, body: EditRequest):
    return save_reviewed_scenarios(
        story_id, body.draft, expected_hash=body.review_hash
    )

@app.post("/api/stories/{story_id}/approve-and-run")
def approve_and_run(story_id: int, body: ApproveRequest):
    # LOCAL DEMONSTRATION ONLY. Replace with authenticated identity.
    return approve_execute_publish(
        story_id,
        reviewer="local-dev-reviewer",
        expected_hash=body.review_hash,
    )
```

**Run from repository root:**

```powershell
pip install fastapi uvicorn
python -m uvicorn backend.api:app --reload --host 127.0.0.1 --port 8001
```

For testing: open `http://127.0.0.1:8001/docs` (Swagger UI). Stage 2 can take a long time, so the synchronous route above is only a local proof of concept and may hit HTTP/proxy timeouts. Handle errors cleanly and map known validation/hash conflicts to suitable HTTP responses when building the real API.

### Example frontend JavaScript calls

```javascript
const API_BASE = "http://127.0.0.1:8001"; // Use your configured API URL
const storyId = 1;

// STAGE 1 — generate and display scenarios
const generateResponse = await fetch(
  `${API_BASE}/api/stories/${storyId}/generate`,
  { method: "POST" }
);
if (!generateResponse.ok) throw new Error(await generateResponse.text());
let review = await generateResponse.json();
console.log(review.draft.scenarios);

// If the user edits the scenarios, SAVE (does not approve)
// Build this object from the edited values in the review form.
const editedDraft = review.draft; // Replace with the user-edited full batch
const editResponse = await fetch(
  `${API_BASE}/api/stories/${storyId}/review`,
  {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      draft: editedDraft,            // Full edited ScenarioBatch
      review_hash: review.review_hash
    })
  }
);
if (!editResponse.ok) throw new Error(await editResponse.text());
review = await editResponse.json(); // Save the NEW review hash

// STAGE 2 — ONLY inside a real "Approve and run" click handler
const approveResponse = await fetch(
  `${API_BASE}/api/stories/${storyId}/approve-and-run`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ review_hash: review.review_hash })
  }
);
if (!approveResponse.ok) throw new Error(await approveResponse.text());
const published = await approveResponse.json();
console.log(published.execution, published.devops.test_cases);
```

**Cross-origin note:** if the frontend and API run on different ports/domains, configure CORS on the API for the frontend's **specific** development origin, or use a frontend development proxy. Example for **local development only**, just after `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)
```

Match this origin to the frontend's actual dev URL. Authentication still needs to be implemented; CORS is **not** an access-control mechanism.

## 6. Suggested frontend screens and states

| Screen/state | Contents and actions |
| --- | --- |
| **Story selection** | Enter/select numeric User Story ID; **Generate scenarios** button |
| **Generating** | Show loading state; prevent duplicate submissions |
| **Pending review** | Story title/ACs, scenario cards/editors, validation, **Save edits**, **Approve and run** |
| **Running** | Show progress and prevent accidental repeated approval/publishing |
| **Complete** | Counts (`passed`, `failed`, `timed_out`, `not_run`), per-TC failures, Azure Test Case IDs, report/attachment information |
| **Error** | Meaningful error, ability to retry safely or reload the latest draft |

Store the *latest* `review_hash` returned by Stage 1, `GET review`, or `PUT review`. Send it when approving. The frontend should never approve automatically on page load or after a generation response.

## 7. Local manual testing without a frontend

```powershell
# From repository root:
python -m backend.stage1 1

# Open backend/data/stories/1/rev_<revision>/scenarios.draft.json
# and review the proposed scenarios.

# Calling Stage 2 is itself the explicit local approval action:
python -m backend.stage2 1
```

These CLI commands print short summaries. The **imported functions return richer dictionaries** for API use. For local CLI use, Stage 2 defaults the reviewer to the OS username and does not require `expected_hash`; web API integration should **never rely on those optional defaults**.

## 8. Current limitations / production checklist

Before deploying a real web frontend:

1. **Authentication and permissions:** authenticate users (for example Microsoft Entra ID), verify that the authenticated user may access/approve the Story; derive reviewer identity server-side. Never trust a browser-supplied reviewer label. Enforce a review hash on all approvals.
2. **Background jobs:** both AI generation and especially Stage 2 can run for minutes. Use a job queue/worker with `202 Accepted`, job ID, progress/status polling or server events instead of holding one HTTP connection open. The example above is synchronous on purpose for local illustration.
3. **Concurrent users:** `stage1.py` currently has a single-machine `.workflow.lock`; reports and tests use shared paths. Use per-run isolated workspaces, durable job storage and a distributed lock before multi-worker/multi-instance deployment.
4. **Safe execution:** the backend executes AI-generated JavaScript. Run it only in a controlled, isolated test environment with restricted credentials and network access. The current generator checks syntax/structure but **cannot guarantee runtime correctness or code safety**.
5. **Website configuration:** code generation currently depends on the repository's `test aplikacia` fixtures, selectors and local app. Testing unrelated sites needs separate site configuration, reliable browser inspection, target credentials and environment setup.
6. **Error handling and retries:** return meaningful HTTP error codes for invalid IDs, validation errors, stale hashes, Azure failures and concurrent runs. Distinguish **workflow failure** from **test failure**; failed assertions may still yield a successfully published report.
7. **Result access:** Azure attachments are not official Azure Test Plans executions. The current code does not provide a separate API for fetching past results after a refresh; implement one if needed.
8. **Approval integrity:** JSON hashes are consistency checks, not digital signatures; use proper authorization and audit logs. The current local approval file is not a secure multi-user approval database.

## 9. Ownership: who implements which part?

| Component | Owner / purpose |
| --- | --- |
| **Frontend** | Story selection, review/edit UI, approval button, result display; sends HTTP requests |
| **FastAPI (`backend/api.py`)** | Validates requests, authenticates reviewer, calls backend functions, returns JSON |
| **`backend/stage1.py`** | Fetches Story, generates/validates/saves scenario draft; returns review payload |
| **`backend/approval.py`** | Records approval and verifies Story/draft/approved hashes |
| **`backend/stage2.py`** | Approves reviewed draft, generates/runs Playwright, processes/publishes results |
| **Azure DevOps** | Source User Story; linked Test Case work items; code and report attachments |

**Bottom line:** A frontend developer needs the endpoint contracts, the `draft.scenarios` schema, and the two user actions: **Generate scenarios** then **Approve and run**. The frontend communicates with FastAPI via HTTP; FastAPI imports the two Python service functions.
