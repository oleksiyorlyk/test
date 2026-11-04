import getpass
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from backend.approval import approve_draft, load_approved_scenarios
from backend.scenarios import ScenarioBatch, validate_scenarios
from backend.devops_publish import AzurePublisher


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
APP_DIR = ROOT / "test aplikacia"
STORY_ID = 1  # Must match launch_1_scenarios.py.
REVIEWER = getpass.getuser()  # Label for the local scenario-approval record.
PREPARED_MARKER = BACKEND / "data" / "stories" / str(STORY_ID) / "last_prepared.json"


def write_json(path: Path, data: dict) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def run_module(module: str, *args: str) -> None:
    command = [sys.executable, "-m", module, *map(str, args)]
    print("\n> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def zip_html_report(report_dir: Path, destination: Path) -> bool:
    if not (report_dir / "index.html").is_file():
        return False
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(report_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(report_dir))
    return True


def upload_result_artifacts(folder: Path, revision: int, result_json: Path, exit_code: int) -> None:
    """Attach execution evidence to the Azure Story after regular M5 publishing."""
    publisher = AzurePublisher(
        os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
        os.getenv("AZURE_DEVOPS_PROJECT", ""),
        os.getenv("AZURE_DEVOPS_PAT", ""),
    )

    summary = folder / "execution.summary.json"
    if not summary.is_file():
        raise FileNotFoundError("Missing execution.summary.json; refusing to publish results")

    artifacts = {
        "execution-summary": summary,
        "playwright-results": result_json,
    }
    report_zip = folder / "playwright-report.zip"
    if zip_html_report(APP_DIR / "playwright-report", report_zip):
        artifacts["html-report"] = report_zip
    else:
        print("Warning: no HTML report found; uploading JSON results only.")

    manifest_path = folder / "results.publish.json"
    manifest = {
        "story_id": STORY_ID,
        "story_revision": revision,
        "playwright_exit_code": exit_code,
        "attachments": {},
    }

    for kind, path in artifacts.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        filename = f"story-{STORY_ID}-rev-{revision}-{kind}-{digest}{path.suffix}"
        key = f"AI-EXECUTION-RESULT story={STORY_ID} revision={revision} kind={kind} sha256={digest}"

        # Fetch updated relations each time: attaching one file modifies the Story.
        live_story = publisher.work_item(STORY_ID, relations=True)
        if publisher.already_attached(live_story, filename, key):
            manifest["attachments"][kind] = {"filename": filename, "status": "already attached"}
            print(f"  Already attached: {filename}")
        else:
            url = publisher.attach_file(STORY_ID, path, filename, key)
            manifest["attachments"][kind] = {"filename": filename, "status": "uploaded", "url": url}
            print(f"  Uploaded to User Story #{STORY_ID}: {filename}")
        write_json(manifest_path, manifest)

    print(f"  Upload record: {manifest_path}")


def main() -> None:
    load_dotenv(BACKEND / ".env")
    if not PREPARED_MARKER.is_file():
        raise FileNotFoundError("No completed Stage 1 draft. Run launch_1_scenarios.py first.")

    prepared = json.loads(PREPARED_MARKER.read_text(encoding="utf-8"))
    if prepared.get("story_id") != STORY_ID:
        raise ValueError("Prepared draft belongs to another Story")
    revision = prepared.get("revision")
    if type(revision) is not int or revision < 1:
        raise ValueError("Prepared draft contains an invalid Story revision")

    folder = BACKEND / "data" / "stories" / str(STORY_ID) / f"rev_{revision}"
    story = json.loads((folder / "story.normalized.json").read_text(encoding="utf-8"))
    draft_data = json.loads((folder / "scenarios.draft.json").read_text(encoding="utf-8"))

    print(f"\n[1/6] Validating reviewed Story #{STORY_ID}, revision {revision}...", flush=True)
    if story.get("id") != STORY_ID or story.get("revision") != revision:
        raise ValueError("Saved Story does not match Stage 1 selection")
    batch = ScenarioBatch.model_validate(draft_data)
    validation = validate_scenarios(story, batch)
    write_json(folder / "scenarios.validation.json", validation)
    if not validation["valid"]:
        raise ValueError("Your reviewed scenario draft is invalid: " + "; ".join(validation["errors"]))
    if validation["ready_count"] == 0:
        raise ValueError("No READY scenarios to generate executable tests from")

    # Pressing Play on this second script is the explicit HUMAN approval action.
    print(f"[2/6] Recording scenario approval as {REVIEWER!r}...", flush=True)
    approve_draft(folder, reviewer=REVIEWER, replace=True)
    approved = load_approved_scenarios(folder)
    print(f"  Approved {len(approved.scenarios)} scenarios; READY {validation['ready_count']}.")

    print("[3/6] Generating/replacing Playwright tests via OpenAI...", flush=True)
    run_module("backend.generate_playwright", "--id", str(STORY_ID),
               "--revision", str(revision), "--replace")

    print("[4/6] Running Playwright tests...", flush=True)
    npx = shutil.which("npx.cmd") if os.name == "nt" else shutil.which("npx")
    if not npx:
        raise RuntimeError("Node.js/npm not installed: npx is unavailable")
    if not (APP_DIR / "node_modules" / "@playwright" / "test").is_dir():
        raise RuntimeError('Install Playwright once: cd "test aplikacia"; npm ci; npx playwright install chromium')

    result_json = APP_DIR / "test-results" / "results.json"
    result_json.unlink(missing_ok=True)  # Never accidentally reuse a previous run.
    command = [npx, "--no-install", "playwright", "test", f"generated-tests/story-{STORY_ID}-rev-{revision}"]
    print("\n> " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=APP_DIR, check=False)
    print(f"Playwright returned {completed.returncode}; test failures do not stop reporting.")
    if not result_json.is_file():
        raise RuntimeError("Playwright produced no new results.json; publication stopped.")

    print("[5/6] Processing test results...", flush=True)
    run_module("backend.process_results", "--id", str(STORY_ID),
               "--revision", str(revision), "--input", str(result_json))

    print("[6/6] Publishing Test Cases, JS code and execution results to Azure DevOps...", flush=True)
    # The existing publisher validates live requirements before writing and avoids
    # duplicate Test Cases and code attachments.
    run_module("backend.publish_outputs", "--id", str(STORY_ID),
               "--revision", str(revision), "--publish")
    # The existing publisher deliberately does NOT publish execution results;
    # add them as work-item attachments using its existing AzurePublisher API.
    upload_result_artifacts(folder, revision, result_json, completed.returncode)

    summary = json.loads((folder / "execution.summary.json").read_text(encoding="utf-8"))
    print(f"\nCOMPLETE — Story #{STORY_ID}, revision {revision}")
    print(f"Tests: {summary['total']} | PASSED: {summary['passed']} | FAILED: {summary['failed']} | "
          f"TIMED_OUT: {summary['timed_out']} | NOT_RUN: {summary['not_run']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nSTAGE 2 FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
