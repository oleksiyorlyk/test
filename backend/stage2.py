
"""Stage 2 service: reviewed scenarios -> approval -> tests -> Azure publication.

From repository root (calling this confirms you reviewed the draft):
    python -m backend.stage2 1

Frontend integration:
    result = approve_execute_publish(story_id, reviewer=authenticated_user,
                                     expected_hash=review_hash)

All operations run synchronously: invoke via a background job from a web API.
"""

from __future__ import annotations

import argparse
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

from .approval import approve_draft, digest, load_approved_scenarios
from .devops_publish import AzurePublisher
from .scenarios import ScenarioBatch, validate_scenarios
from .stage1 import BACKEND, _prepared_folder, _read_json, _write_json, workflow_lock

ROOT = BACKEND.parent
APP_DIR = ROOT / "test aplikacia"


def _run_module(module: str, *args: str) -> None:
    command = [sys.executable, "-m", module, *map(str, args)]
    print("\n> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _zip_html_report(report_dir: Path, destination: Path) -> bool:
    if not (report_dir / "index.html").is_file():
        return False
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(report_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(report_dir))
    return True


def _upload_results(story_id: int, folder: Path, revision: int, result_json: Path, exit_code: int) -> dict:
    publisher = AzurePublisher(
        os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
        os.getenv("AZURE_DEVOPS_PROJECT", ""),
        os.getenv("AZURE_DEVOPS_PAT", ""),
    )
    summary = folder / "execution.summary.json"
    if not summary.is_file():
        raise FileNotFoundError("Missing execution.summary.json")

    artifacts = {"execution-summary": summary, "playwright-results": result_json}
    zip_path = folder / "playwright-report.zip"
    if _zip_html_report(APP_DIR / "playwright-report", zip_path):
        artifacts["html-report"] = zip_path

    manifest_path = folder / "results.publish.json"
    manifest = {
        "story_id": story_id,
        "story_revision": revision,
        "playwright_exit_code": exit_code,
        "attachments": {},
    }
    for kind, path in artifacts.items():
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        filename = f"story-{story_id}-rev-{revision}-{kind}-{sha}{path.suffix}"
        key = f"AI-EXECUTION-RESULT story={story_id} revision={revision} kind={kind} sha256={sha}"
        story = publisher.work_item(story_id, relations=True)
        if publisher.already_attached(story, filename, key):
            entry = {"filename": filename, "status": "already attached"}
        else:
            url = publisher.attach_file(story_id, path, filename, key)
            entry = {"filename": filename, "status": "uploaded", "url": url}
        manifest["attachments"][kind] = entry
        _write_json(manifest_path, manifest)
    return manifest


def approve_execute_publish(
    story_id: int,
    *,
    reviewer: str | None = None,
    expected_hash: str | None = None,
) -> dict:
    """One deliberate approval action followed by full automatic execution/upload.

    Story ID is the only required input for local use. A frontend should pass
    authenticated reviewer identity and the draft hash the user actually saw.
    """
    if type(story_id) is not int or story_id < 1:
        raise ValueError("story_id must be a positive integer")
    reviewer = (reviewer or getpass.getuser()).strip()
    if not reviewer:
        raise ValueError("A reviewer identity is required")
    load_dotenv(BACKEND / ".env")

    with workflow_lock():
        folder, revision = _prepared_folder(story_id)
        story = _read_json(folder / "story.normalized.json")
        draft_data = _read_json(folder / "scenarios.draft.json")
        if story.get("id") != story_id or story.get("revision") != revision:
            raise ValueError("Prepared Story ID/revision mismatch")
        if expected_hash is not None and digest(draft_data) != expected_hash:
            raise ValueError("Draft changed since review. Reload and approve the current version.")

        batch = ScenarioBatch.model_validate(draft_data)
        validation = validate_scenarios(story, batch)
        _write_json(folder / "scenarios.validation.json", validation)
        if not validation["valid"]:
            raise ValueError("Draft validation failed: " + "; ".join(validation["errors"]))
        if validation["ready_count"] == 0:
            raise ValueError("No READY scenarios available to generate Playwright tests")

        # Invoking this method is the approval action, not an automatic Stage 1 step.
        approve_draft(folder, reviewer=reviewer, replace=True)
        load_approved_scenarios(folder)

        _run_module("backend.generate_playwright", "--id", str(story_id),
                    "--revision", str(revision), "--replace")

        npx = shutil.which("npx.cmd") if os.name == "nt" else shutil.which("npx")
        if not npx:
            raise RuntimeError("Node.js/npm not installed: npx unavailable")
        if not (APP_DIR / "node_modules" / "@playwright" / "test").is_dir():
            raise RuntimeError('Playwright missing: run npm ci and npx playwright install chromium in "test aplikacia"')
        result_json = APP_DIR / "test-results" / "results.json"
        result_json.unlink(missing_ok=True)
        command = [npx, "--no-install", "playwright", "test",
                   f"generated-tests/story-{story_id}-rev-{revision}"]
        print("\n> " + " ".join(command), flush=True)
        execution = subprocess.run(command, cwd=APP_DIR, check=False)
        # An assertion failure must not prevent result reporting and publication.
        if not result_json.is_file():
            raise RuntimeError("Playwright did not produce a JSON report")

        _run_module("backend.process_results", "--id", str(story_id),
                    "--revision", str(revision), "--input", str(result_json))
        _run_module("backend.publish_outputs", "--id", str(story_id),
                    "--revision", str(revision), "--publish")
        uploaded_results = _upload_results(story_id, folder, revision, result_json, execution.returncode)

        return {
            "story_id": story_id,
            "revision": revision,
            "status": "PUBLISHED",
            "reviewer": reviewer,
            "execution": _read_json(folder / "execution.summary.json"),
            "devops": _read_json(folder / "devops.publish.json"),
            "result_uploads": uploaded_results,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Approve, test and publish a reviewed Story")
    parser.add_argument("story_id", type=int, help="Azure DevOps User Story ID")
    args = parser.parse_args()
    result = approve_execute_publish(args.story_id)
    print(json.dumps({
        "story_id": result["story_id"],
        "revision": result["revision"],
        "status": result["status"],
        "reviewer": result["reviewer"],
        "execution": {
            field: result["execution"][field]
            for field in ("total", "passed", "failed", "timed_out", "not_run")
        },
        "devops": result["devops"]["test_cases"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
