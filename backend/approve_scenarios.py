
"""Approve generated scenarios from the command line."""

import argparse
import sys
from pathlib import Path

from .approval import approve_draft, load_approved_scenarios


BACKEND_DIR = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Approve a reviewed scenario draft"
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
        required=True,
        help="Saved Story revision"
    )

    parser.add_argument(
        "--reviewer",
        required=True,
        help="Human reviewer label"
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing approval after another review"
    )

    args = parser.parse_args()

    if args.id < 1 or args.revision < 1:
        parser.error(
            "--id and --revision must be positive"
        )

    folder = (
        BACKEND_DIR
        / "data"
        / "stories"
        / str(args.id)
        / f"rev_{args.revision}"
    )

    try:
        record = approve_draft(
            folder,
            reviewer=args.reviewer,
            replace=args.replace
        )

        batch = load_approved_scenarios(folder)

    except (OSError, ValueError, KeyError) as exc:
        print(f"Approval failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Approved: {folder / 'scenarios.approved.json'}"
    )

    print(
        f"Approval record: {folder / 'scenarios.approval.json'}"
    )

    print(
        f"Scenarios: {len(batch.scenarios)}, "
        f"READY: {record['ready_count']}, "
        f"BLOCKED: {record['blocked_count']}"
    )

    print(
        "Approved scenarios are ready "
        "for Playwright code generation."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
