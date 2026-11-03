
"""CLI: approved scenarios -> OpenAI -> checked Playwright .spec.js files."""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .approval import load_approved_scenarios
from .playwright_generator import generate_suite, validate_generated_suite


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent


def save_json(path: Path, data: dict):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate Playwright tests from approved scenarios"
    )

    parser.add_argument(
        "--id",
        type=int,
        required=True,
        help="Azure DevOps Story ID"
    )

    parser.add_argument(
        "--revision",
        type=int,
        required=True
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace old generated .spec.js files for this Story revision"
    )

    args = parser.parse_args()

    if args.id < 1 or args.revision < 1:
        parser.error("--id and --revision must be positive")

    load_dotenv(BACKEND_DIR / ".env")

    folder = (
        BACKEND_DIR
        / "data"
        / "stories"
        / str(args.id)
        / f"rev_{args.revision}"
    )

    app_dir = PROJECT_DIR / "test aplikacia"

    output = (
        app_dir
        / "generated-tests"
        / f"story-{args.id}-rev-{args.revision}"
    )

    try:
        existing = list(output.glob("*.spec.js"))

        if existing and not args.replace:
            raise ValueError(
                "Tests already exist. Review before regenerating; "
                "use --replace to overwrite."
            )

        # Also checks that approval matches the current Story and draft.
        approved = load_approved_scenarios(folder)

        ready = [
            s for s in approved.scenarios
            if s.status == "READY"
        ]

        blocked = [
            s.test_id for s in approved.scenarios
            if s.status == "BLOCKED"
        ]

        if not ready:
            raise ValueError(
                "No approved READY scenarios available"
            )

        story = json.loads(
            (folder / "story.normalized.json").read_text(
                encoding="utf-8"
            )
        )

        suite, test_ids, metadata = generate_suite(
            story,
            ready,
            app_dir
        )

        files = validate_generated_suite(
            suite,
            ready,
            test_ids
        )

        # Save only after every generated test passes validation.
        output.mkdir(parents=True, exist_ok=True)

        if args.replace:
            for old in existing:
                old.unlink()

        for filename, code in files.items():
            (output / filename).write_text(
                code,
                encoding="utf-8"
            )

        manifest = {
            "story_id": story["id"],
            "story_revision": story.get("revision"),
            "model": metadata["model"],
            "response_id": metadata["response_id"],
            "prompt_version": metadata["prompt_version"],
            "output_directory": str(output),
            "generated_test_ids": [
                s.test_id for s in ready
            ],
            "blocked_test_ids": blocked,
            "files": list(files),
            "checks": (
                "Structure, test IDs, literal selectors, assertions, "
                "node --check; NOT runtime correctness or security"
            ),
        }

        save_json(
            folder / "playwright.generation.json",
            manifest
        )

        print(
            f"Generated {len(files)} Playwright tests in: {output}"
        )

        for filename in files:
            print("  " + filename)

        print(
            "Code was NOT executed. Review it before "
            "Playwright test discovery or execution."
        )

        return 0

    except Exception as exc:
        print(
            f"Playwright generation failed: {exc}",
            file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
