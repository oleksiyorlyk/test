"""Stage 1: Azure fetch -> normalization -> AI scenarios -> STOP for human review.

Usage:
    python run_1_prepare.py --id 1
    python run_1_prepare.py --id 1 --refresh

Consumes Azure DevOps PAT and OpenAI key from backend/.env. AI usage is billable.
"""
import argparse

from control_common import (
    BACKEND, WorkflowError, latest_revision, positive, read_json,
    run_module, section, story_folder,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", type=positive, required=True)
    parser.add_argument(
        "--refresh", action="store_true",
        help="Explicitly fetch/generate again for a Story with existing local data",
    )
    args = parser.parse_args()

    try:
        root = BACKEND / "data" / "stories" / str(args.id)
        if root.exists() and any(root.glob("rev_*/story.normalized.json")) and not args.refresh:
            raise WorkflowError(
                f"Story #{args.id} already has saved data. "
                "Use --refresh to fetch/generate again, or proceed to Stage 2."
            )

        section("STAGE 1/4: Fetch and normalize User Story, generate AI scenarios")
        run_module("backend.getus", "--id", str(args.id))
        revision = latest_revision(args.id)
        folder = story_folder(args.id, revision)
        # Explicit revision avoids accidentally choosing another revision.
        run_module("backend.generate_scenarios", "--id", str(args.id),
                   "--revision", str(revision))

        report = read_json(folder / "scenarios.validation.json")
        if not report.get("valid", False):
            raise WorkflowError("Scenario validation did not pass")

        section("STOP: HUMAN REVIEW #1 - SCENARIOS")
        print("Review these files before approving:")
        print(" -", folder / "story.normalized.json")
        print(" -", folder / "scenarios.draft.json")
        print(" -", folder / "scenarios.validation.json")
        print(f"\nRevision found: {revision}")
        print("Next, only AFTER review:")
        print(f'python run_2_generate.py --id {args.id} --revision {revision} '
              '--reviewer "QA Reviewer" --approve-reviewed')
        print("IMPORTANT: Nothing was approved or executed.")
        return 0
    except (WorkflowError, OSError, ValueError) as exc:
        parser.exit(1, f"Stage 1 stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
