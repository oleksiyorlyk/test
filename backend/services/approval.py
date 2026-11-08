"""Reusable approval logic for generated test scenarios."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.models.scenarios import ScenarioBatch, validate_scenarios
from backend.storage.json_files import read_json
from backend.storage.json_files import write_json as save_json


class ApprovalError(ValueError):
    pass


def digest(value: dict) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def approve_draft(folder: Path, reviewer: str, *, replace: bool = False) -> dict:
    """
    Approve an existing draft after human review.

    Validation checks structure and AC references.
    It does not guarantee semantic correctness.
    """

    if not reviewer.strip():
        raise ApprovalError("A reviewer label is required")

    story = read_json(folder / "story.normalized.json")
    draft_data = read_json(folder / "scenarios.draft.json")

    batch = ScenarioBatch.model_validate(draft_data)

    if not story.get("ready_for_llm"):
        raise ApprovalError("The normalized Story is not ready for the LLM")

    report = validate_scenarios(story, batch)

    if not report["valid"]:
        raise ApprovalError("Cannot approve invalid scenarios: " + "; ".join(report["errors"]))

    approved_path = folder / "scenarios.approved.json"
    record_path = folder / "scenarios.approval.json"

    if not replace and (approved_path.exists() or record_path.exists()):
        raise ApprovalError("Approval already exists. Use --replace only after another review.")

    approved = batch.model_dump(mode="json")

    record = {
        "status": "APPROVED",
        "reviewer": reviewer.strip(),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "story_id": story["id"],
        "story_revision": story.get("revision"),
        "story_sha256": digest(story),
        "draft_sha256": digest(draft_data),
        "approved_sha256": digest(approved),
        "ready_count": report["ready_count"],
        "blocked_count": report["blocked_count"],
    }

    save_json(approved_path, approved)
    save_json(record_path, record)

    return record


def load_approved_scenarios(folder: Path) -> ScenarioBatch:
    """
    Load approved scenarios safely.

    The Playwright generator should use this function
    instead of reading scenarios.approved.json directly.
    """

    story = read_json(folder / "story.normalized.json")
    draft_data = read_json(folder / "scenarios.draft.json")
    approved_data = read_json(folder / "scenarios.approved.json")
    record = read_json(folder / "scenarios.approval.json")

    if (
        record.get("status") != "APPROVED"
        or record.get("story_id") != story.get("id")
        or record.get("story_revision") != story.get("revision")
        or record.get("story_sha256") != digest(story)
        or record.get("draft_sha256") != digest(draft_data)
        or record.get("approved_sha256") != digest(approved_data)
    ):
        raise ApprovalError("Approval is missing, changed, or stale. Review and approve again.")

    batch = ScenarioBatch.model_validate(approved_data)
    report = validate_scenarios(story, batch)

    if not report["valid"]:
        raise ApprovalError("Approved scenarios are no longer valid")

    return batch
