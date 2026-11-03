
"""CLI entry point for steps 1–2: Azure fetch -> normalize -> save as JSON.

    python getus.py --id 1
    python getus.py --from-json examples/story_1.raw.json

Later FastAPI endpoints can call fetch_story() and normalize_story() directly.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from azure import AzureStoryError, fetch_story
from normalizer import normalize_story

ROOT = Path(__file__).resolve().parent


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and normalize an Azure DevOps Story"
    )

    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--id",
        type=int,
        help="Azure DevOps work-item ID"
    )
    inputs.add_argument(
        "--from-json",
        type=Path,
        help="Normalize a saved raw Story without API access"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "stories"
    )

    args = parser.parse_args()
    load_dotenv(ROOT / ".env")

    try:
        if args.from_json:
            raw = json.loads(
                args.from_json.read_text(encoding="utf-8")
            )
        else:
            raw = fetch_story(
                args.id,
                organization=os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
                project=os.getenv("AZURE_DEVOPS_PROJECT", ""),
                pat=os.getenv("AZURE_DEVOPS_PAT", ""),
            )

        normalized = normalize_story(raw)

    except (AzureStoryError, ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    revision = raw.get("revision")
    version = (
        f"rev_{revision}"
        if isinstance(revision, int)
        else "revision_unknown"
    )

    folder = args.output_dir / str(normalized["id"]) / version

    save_json(folder / "story.raw.json", raw)
    save_json(folder / "story.normalized.json", normalized)

    print(f"Raw Story:        {folder / 'story.raw.json'}")
    print(f"Normalized Story: {folder / 'story.normalized.json'}")
    print(
        f"Acceptance criteria: "
        f"{len(normalized['acceptance_criteria'])}"
    )

    for warning in normalized["warnings"]:
        print(f"Warning: {warning}")

    if not normalized["ready_for_llm"]:
        print("Needs manual review before sending to the LLM.")
        return 2

    print("Ready for the scenario-generation LLM (Step 3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
