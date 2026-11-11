"""Explicit, unattended CI workflow for one Azure DevOps User Story.

Runs only when requested with --unattended. Uses the existing Stage 1 and
Stage 2 services; Stage 2's approval record is labelled as CI automation.
No app server or Oracle VM is involved.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from backend.core.config import redact
from backend.services.stage1 import prepare_scenarios
from backend.services.stage2 import approve_execute_publish


def run(story_id: int) -> int:
    if story_id <= 0:
        raise ValueError("Story ID must be positive")

    print(f"[CI] Stage 1: prepare scenarios for Story #{story_id}", flush=True)
    prepared = prepare_scenarios(story_id)
    validation = prepared["validation"]
    if not validation["valid"] or validation["ready_count"] < 1:
        raise ValueError("No valid READY scenarios; stopping before code generation")

    print(
        f"[CI] Prepared revision {prepared['revision']}; "
        f"{validation['ready_count']} READY scenario(s)",
        flush=True,
    )
    print("[CI] Stage 2: unattended approval, code generation, execution, publication", flush=True)
    result = approve_execute_publish(
        story_id,
        reviewer=f"CI_UNATTENDED:{os.getenv('CI_PIPELINE_ID', 'local')}",
        expected_hash=prepared["review_hash"],
    )

    summary = result["execution"]
    counts = {
        name: summary.get(name, 0)
        for name in (
            "total",
            "passed",
            "failed",
            "timed_out",
            "flaky",
            "skipped",
            "not_run",
            "interrupted",
            "unknown",
        )
    }
    print("[CI] Published to Azure DevOps. Test counts:", json.dumps(counts), flush=True)

    # Stage 2 intentionally publishes reports even if some tests fail.
    # Fail the GitLab job *after* publication when test results are not all passing.
    if counts["total"] < 1 or counts["passed"] != counts["total"]:
        print("[CI] Publication completed; Playwright results are not all PASSED.", flush=True)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story-id", type=int, required=True)
    parser.add_argument(
        "--unattended",
        action="store_true",
        help="Explicitly opt into automated scenario approval and Azure DevOps publication",
    )
    args = parser.parse_args()
    if not args.unattended:
        parser.error("Unattended execution requires --unattended")
    try:
        return run(args.story_id)
    except Exception as exc:
        print("[CI] Workflow failed: " + redact(str(exc)), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
