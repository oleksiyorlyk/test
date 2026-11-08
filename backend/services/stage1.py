"""Stage 1 service: Azure Story -> normalized requirements -> reviewed scenario draft.

From repository root:
    python -m backend.services.stage1 1

Frontend integration:
    result = prepare_scenarios(story_id)
    result = get_review(story_id)
    result = save_reviewed_scenarios(story_id, edited_batch, expected_hash=...)

All functions return JSON-serializable dictionaries. This module performs no approval.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from backend.core.config import BACKEND
from backend.core.config import STORY_DATA as DATA
from backend.core.locking import workflow_lock
from backend.core.validation import validate_story_id as _validate_id
from backend.integrations.azure import fetch_story
from backend.integrations.llm import generate_scenarios
from backend.models.scenarios import ScenarioBatch, validate_scenarios
from backend.services.approval import digest
from backend.services.normalizer import normalize_story
from backend.storage.json_files import read_json as _read_json
from backend.storage.json_files import write_json as _write_json
from backend.storage.stories import prepared_folder as _prepared_folder


def _review_result(story_id: int, folder: Path, revision: int) -> dict:
    story = _read_json(folder / "story.normalized.json")
    draft = _read_json(folder / "scenarios.draft.json")
    report = _read_json(folder / "scenarios.validation.json")
    return {
        "story_id": story_id,
        "revision": revision,
        "status": "PENDING_REVIEW",
        "story": story,
        "draft": draft,
        "validation": report,
        "review_hash": digest(draft),
    }


def prepare_scenarios(story_id: int) -> dict:
    """Regenerate a Story's scenario draft and return everything for human review."""
    _validate_id(story_id)
    load_dotenv(BACKEND / ".env")
    with workflow_lock():
        root = DATA / "stories" / str(story_id)
        root.mkdir(parents=True, exist_ok=True)
        marker = root / "last_prepared.json"
        marker.unlink(missing_ok=True)  # A failed new generation cannot approve the old draft.

        raw = fetch_story(
            story_id,
            organization=os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
            project=os.getenv("AZURE_DEVOPS_PROJECT", ""),
            pat=os.getenv("AZURE_DEVOPS_PAT", ""),
        )
        if raw.get("work_item_type") != "User Story":
            raise ValueError(f"Work item #{story_id} is not a User Story")
        revision = raw.get("revision")
        if type(revision) is not int or revision < 1:
            raise ValueError("Azure returned an invalid Story revision")
        folder = root / f"rev_{revision}"
        normalized = normalize_story(raw)
        _write_json(folder / "story.raw.json", raw)
        _write_json(folder / "story.normalized.json", normalized)
        # Regeneration requires a fresh review, even when Azure revision is unchanged.
        for name in ("scenarios.approved.json", "scenarios.approval.json"):
            (folder / name).unlink(missing_ok=True)

        if not normalized["ready_for_llm"]:
            raise ValueError(
                "Story requirements need attention: " + "; ".join(normalized["warnings"])
            )

        batch, metadata = generate_scenarios(normalized)
        report = validate_scenarios(normalized, batch)
        draft = batch.model_dump(mode="json")
        _write_json(folder / "scenarios.draft.json", draft)
        _write_json(folder / "scenarios.validation.json", report)
        _write_json(folder / "scenarios.generation.json", metadata)
        if not report["valid"]:
            raise ValueError("Generated scenarios are invalid: " + "; ".join(report["errors"]))

        _write_json(marker, {"story_id": story_id, "revision": revision})
        return _review_result(story_id, folder, revision)


def get_review(story_id: int) -> dict:
    """Read the current draft so the frontend can redisplay it after refresh."""
    folder, revision = _prepared_folder(story_id)
    return _review_result(story_id, folder, revision)


def save_reviewed_scenarios(story_id: int, edited_batch: dict, *, expected_hash: str) -> dict:
    """Validate and save edits made during human review (without approving them)."""
    _validate_id(story_id)
    if not expected_hash:
        raise ValueError("An expected draft hash is required to avoid overwriting newer edits")
    with workflow_lock():
        folder, revision = _prepared_folder(story_id)
        current = _read_json(folder / "scenarios.draft.json")
        if digest(current) != expected_hash:
            raise ValueError("Draft changed since you opened it; reload before saving")
        story = _read_json(folder / "story.normalized.json")
        batch = ScenarioBatch.model_validate(edited_batch)
        report = validate_scenarios(story, batch)
        if not report["valid"]:
            raise ValueError("Edited draft is invalid: " + "; ".join(report["errors"]))
        for name in ("scenarios.approved.json", "scenarios.approval.json"):
            (folder / name).unlink(missing_ok=True)
        _write_json(folder / "scenarios.draft.json", batch.model_dump(mode="json"))
        _write_json(folder / "scenarios.validation.json", report)
        return _review_result(story_id, folder, revision)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and validate Story scenarios")
    parser.add_argument("story_id", type=int, help="Azure DevOps User Story ID")
    args = parser.parse_args()
    result = prepare_scenarios(args.story_id)
    print(
        json.dumps(
            {
                "story_id": result["story_id"],
                "revision": result["revision"],
                "status": result["status"],
                "validation": result["validation"],
                "review_hash": result["review_hash"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
