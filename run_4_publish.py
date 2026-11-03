"""Stage 4: Preview Azure DevOps publication, then explicitly publish after review.

Preview (NO Azure writes):
    python run_4_publish.py --id 1 --revision 7

Actual write (creates linked Test Cases and attaches generated .spec.js files):
    python run_4_publish.py --id 1 --revision 7 --publish

The existing publisher does NOT upload the execution.summary.json PASS/FAIL results.
"""
import argparse

from control_common import WorkflowError, positive, run_module, section


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", type=positive, required=True)
    parser.add_argument("--revision", type=positive, required=True)
    parser.add_argument("--publish", action="store_true",
                        help="Explicitly authorize live Azure DevOps write operations")
    args = parser.parse_args()

    try:
        section("STAGE 4/4: Azure DevOps publishing")
        command = ["--id", str(args.id), "--revision", str(args.revision)]
        if args.publish:
            command.append("--publish")
        run_module("backend.publish_outputs", *command)
        section("PUBLISH COMPLETE" if args.publish else "PREVIEW COMPLETE - NO AZURE WRITES")
        print("This stage publishes Test Case work items and test file attachments.")
        print("Execution PASS/FAIL result publishing is not implemented yet.")
        return 0
    except (WorkflowError, OSError, ValueError) as exc:
        parser.exit(1, f"Stage 4 stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
