
"""Step 3: Generate and validate scenarios for a saved User Story."""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .llm import generate_scenarios
from .scenarios import validate_scenarios


BACKEND_DIR = Path(__file__).resolve().parent


def save_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def find_story_file(story_id: int, revision: int | None) -> Path:
    base = BACKEND_DIR / "data" / "stories" / str(story_id)

    if revision is not None:
        return base / f"rev_{revision}" / "story.normalized.json"

    choices = []

    for path in base.glob("rev_*/story.normalized.json"):
        try:
            rev = int(path.parent.name.removeprefix("rev_"))
            choices.append((rev, path))
        except ValueError:
            continue

    if not choices:
        raise FileNotFoundError(
            f"No normalized Story found for #{story_id}. "
            "Run getus.py first."
        )

    return max(choices, key=lambda item: item[0])[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate scenarios from a normalized User Story"
    )

    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--revision", type=int)

    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")

    try:
        source = find_story_file(args.id, args.revision)

        story = json.loads(source.read_text(encoding="utf-8"))

        if story["id"] != args.id:
            raise ValueError("Story ID does not match the requested ID")

        batch, metadata = generate_scenarios(story)
        report = validate_scenarios(story, batch)

        folder = source.parent

        save_json(
            folder / "scenarios.draft.json",
            batch.model_dump(),
        )

        save_json(
            folder / "scenarios.validation.json",
            report,
        )

        save_json(
            folder / "scenarios.generation.json",
            metadata,
        )

        print(f"Saved draft: {folder / 'scenarios.draft.json'}")
        print(f"Validation: {folder / 'scenarios.validation.json'}")

        print(
            f"Scenarios: {report['scenario_count']}, "
            f"READY: {report['ready_count']}, "
            f"BLOCKED: {report['blocked_count']}"
        )

        if report["errors"]:
            for error in report["errors"]:
                print(f"VALIDATION ERROR: {error}")
            return 2

        print("Validation passed. Review scenarios before generating code.")
        return 0

    except Exception as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
