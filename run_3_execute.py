"""Stage 3: Run reviewed Playwright code -> process JSON -> STOP for result review.

Prerequisites (run once in the test aplikacia directory):
    npm ci
    npx playwright install chromium

Usage:
    python run_3_execute.py --id 1 --revision 7 --reviewed-code

A failed Playwright assertion does NOT abort result processing: failures are expected
outputs of software testing. Nonzero test process status is still reported.
"""
import argparse
import os
import shutil
import subprocess

from control_common import (
    APP_DIR, WorkflowError, positive, run_module, section, story_folder,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", type=positive, required=True)
    parser.add_argument("--revision", type=positive, required=True)
    parser.add_argument("--reviewed-code", action="store_true",
                        help="Confirm you inspected the generated code before execution")
    args = parser.parse_args()

    try:
        if not args.reviewed_code:
            raise WorkflowError(
                "Review the generated .spec.js code first, then pass --reviewed-code."
            )
        from backend.approval import load_approved_scenarios
        folder = story_folder(args.id, args.revision)
        approved = load_approved_scenarios(folder)
        ready = [s for s in approved.scenarios if s.status == "READY"]
        if not ready:
            raise WorkflowError("No approved READY scenarios to execute")
        code_dir = APP_DIR / "generated-tests" / f"story-{args.id}-rev-{args.revision}"
        for s in ready:
            code = code_dir / f"{s.test_id.lower()}.spec.js"
            if not code.is_file():
                raise WorkflowError(f"Missing generated test file: {code}")

        cmd = shutil.which("npx.cmd") if os.name == "nt" else shutil.which("npx")
        if not cmd:
            raise WorkflowError("npx is missing. Install Node.js and run npm ci.")
        if not (APP_DIR / "node_modules" / "@playwright" / "test").is_dir():
            raise WorkflowError('Playwright not installed. Run npm ci in "test aplikacia".')

        section("STAGE 3/4: Execute reviewed Playwright tests")
        report = APP_DIR / "test-results" / "results.json"
        # Never accidentally summarize a stale report from a previous run.
        if report.is_file():
            report.unlink()

        # The positional filter scopes execution to the requested Story revision.
        command = [cmd, "--no-install", "playwright", "test",
                   f"generated-tests/story-{args.id}-rev-{args.revision}"]
        print("\n> " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=APP_DIR, check=False)
        print(f"Playwright exited with code {result.returncode}.")

        if not report.is_file():
            raise WorkflowError(
                "Playwright did not create a new JSON report. Check test collection, "
                "browser installation, and console errors."
            )
        run_module("backend.process_results", "--id", str(args.id),
                   "--revision", str(args.revision), "--input", str(report))

        section("STOP: HUMAN REVIEW #3 - TEST OUTCOMES")
        print("Review:")
        print(" -", folder / "execution.summary.json")
        print(" -", APP_DIR / "playwright-report" / "index.html")
        print("To open HTML report: cd \"test aplikacia\"; npx playwright show-report")
        print("Failing assertions (e.g. demo TC-005) should remain recorded as FAILED.")
        print("Next, when ready to publish generated cases and files (NOT results):")
        print(f"python run_4_publish.py --id {args.id} --revision {args.revision} --publish")
        return 0
    except (WorkflowError, OSError, ValueError, ImportError) as exc:
        parser.exit(1, f"Stage 3 stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
