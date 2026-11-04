import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from backend.azure import fetch_story
from backend.normalizer import normalize_story
from backend.llm import generate_scenarios
from backend.scenarios import validate_scenarios


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
STORY_ID = 1  # Change here for a different Azure DevOps User Story.
PREPARED_MARKER = BACKEND / "data" / "stories" / str(STORY_ID) / "last_prepared.json"


def write_json(path: Path, data: dict) -> None:
    """Write a complete JSON file, replacing any previous version."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    load_dotenv(BACKEND / ".env")

    # An interrupted regeneration must not leave the previous draft selected
    # for automatic approval by Stage 2.
    PREPARED_MARKER.unlink(missing_ok=True)

    print(f"\n[1/4] Fetching Azure DevOps User Story #{STORY_ID}...", flush=True)
    raw = fetch_story(
        STORY_ID,
        organization=os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
        project=os.getenv("AZURE_DEVOPS_PROJECT", ""),
        pat=os.getenv("AZURE_DEVOPS_PAT", ""),
    )
    if raw.get("work_item_type") != "User Story":
        raise ValueError(f"Work item #{STORY_ID} is not a User Story")
    revision = raw.get("revision")
    if type(revision) is not int or revision < 1:
        raise ValueError(f"Azure returned an invalid revision: {revision!r}")

    folder = BACKEND / "data" / "stories" / str(STORY_ID) / f"rev_{revision}"

    print("[2/4] Normalizing requirements and writing Story files...", flush=True)
    normalized = normalize_story(raw)
    write_json(folder / "story.raw.json", raw)
    write_json(folder / "story.normalized.json", normalized)

    # A new preparation requires a NEW human review, even if the revision number
    # stayed the same. Old approvals must not be silently reused.
    for name in ("scenarios.approved.json", "scenarios.approval.json"):
        (folder / name).unlink(missing_ok=True)

    if not normalized["ready_for_llm"]:
        raise ValueError(
            "Story is not ready for AI generation. Review story.normalized.json. "
            + "; ".join(normalized["warnings"])
        )

    print("[3/4] Generating scenarios with OpenAI...", flush=True)
    batch, metadata = generate_scenarios(normalized)
    validation = validate_scenarios(normalized, batch)

    write_json(folder / "scenarios.draft.json", batch.model_dump(mode="json"))
    write_json(folder / "scenarios.validation.json", validation)
    write_json(folder / "scenarios.generation.json", metadata)

    if not validation["valid"]:
        raise ValueError(
            "Generated draft did not pass validation. Inspect scenarios.validation.json: "
            + "; ".join(validation["errors"])
        )

    # Stage 2 reads this marker, so nobody has to type a changing Story revision.
    # It is written LAST, only after a valid draft was fully saved.
    write_json(PREPARED_MARKER, {"story_id": STORY_ID, "revision": revision})

    print("[4/4] Scenarios validated and saved.")
    print(f"  Story revision: {revision}")
    print(f"  Scenarios: {validation['scenario_count']}; READY: {validation['ready_count']}; "
          f"BLOCKED: {validation['blocked_count']}")
    print(f"  Draft: {folder / 'scenarios.draft.json'}")
    print(f"  Validation: {folder / 'scenarios.validation.json'}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nSTAGE 1 FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
