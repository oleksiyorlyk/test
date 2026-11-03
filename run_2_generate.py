"""Stage 2: Human-approved scenario draft -> Playwright code -> STOP for code review.

Usage:
    python run_2_generate.py --id 1 --revision 7 --reviewer "QA Reviewer" --approve-reviewed

If an approval already exists for an unchanged draft, reuse it. Use --replace-approval
only after a NEW review and --replace-tests to overwrite old generated code.
"""
import argparse

from control_common import (
    BACKEND, WorkflowError, positive, run_module, section, story_folder,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", type=positive, required=True)
    parser.add_argument("--revision", type=positive, required=True)
    parser.add_argument("--reviewer", help="Label of the person reviewing scenarios")
    parser.add_argument("--approve-reviewed", action="store_true",
                        help="Confirm the human has reviewed the draft scenarios")
    parser.add_argument("--replace-approval", action="store_true")
    parser.add_argument("--replace-tests", action="store_true")
    args = parser.parse_args()

    try:
        folder = story_folder(args.id, args.revision)
        if not folder.is_dir():
            raise WorkflowError(f"Missing Story folder: {folder}. Run Stage 1 first.")

        section("STAGE 2/4: Approve reviewed scenarios and generate Playwright")
        from backend.approval import load_approved_scenarios

        existing_valid = False
        if (folder / "scenarios.approval.json").is_file() and not args.replace_approval:
            try:
                load_approved_scenarios(folder)
                existing_valid = True
            except (OSError, ValueError, KeyError):
                raise WorkflowError(
                    "An existing approval is stale/invalid. Review the draft again "
                    "and use --approve-reviewed --reviewer ... --replace-approval."
                )

        if existing_valid:
            print("Reusing existing valid approval (no new approval action).")
        else:
            if not args.approve_reviewed or not (args.reviewer or "").strip():
                raise WorkflowError(
                    "Human review is required before approval. Provide both "
                    '--reviewer "..." and --approve-reviewed.'
                )
            approve_args = ["--id", str(args.id), "--revision", str(args.revision),
                            "--reviewer", args.reviewer]
            if args.replace_approval:
                approve_args.append("--replace")
            run_module("backend.approve_scenarios", *approve_args)

        generate_args = ["--id", str(args.id), "--revision", str(args.revision)]
        if args.replace_tests:
            generate_args.append("--replace")
        run_module("backend.generate_playwright", *generate_args)

        output = (BACKEND.parent / "test aplikacia" / "generated-tests" /
                  f"story-{args.id}-rev-{args.revision}")
        section("STOP: HUMAN REVIEW #2 - GENERATED JAVASCRIPT")
        print("Review every generated .spec.js file in:")
        print(" -", output)
        print("Generated AI code must not run until manually reviewed.")
        print("Next, only AFTER reviewing the code:")
        print(f"python run_3_execute.py --id {args.id} --revision {args.revision} --reviewed-code")
        return 0
    except (WorkflowError, OSError, ValueError, ImportError) as exc:
        parser.exit(1, f"Stage 2 stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
