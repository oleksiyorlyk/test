"""Convert Playwright's JSON reporter output into a Story execution summary.

Run from the repository root:
    python -m backend.process_results --id 1 --revision 7

Does not run tests, call OpenAI, or modify Azure DevOps.
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .approval import load_approved_scenarios

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
APP_DIR = PROJECT_DIR / "test aplikacia"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TC_ID = re.compile(r"^(TC-\d+)\b")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def walk_specs(suites):
    """Playwright can nest suites (e.g., when using test.describe())."""
    for suite in suites:
        for spec in suite.get("specs", []):
            yield spec
        yield from walk_specs(suite.get("suites", []))


def parse_failure(result: dict) -> dict | None:
    error = result.get("error") or (result.get("errors") or [{}])[0]
    message = ANSI.sub("", error.get("message", ""))
    if not message:
        return None

    expected = re.search(r'(?m)^Expected:\s*"([^"]*)"', message)
    received = re.search(r'(?m)^Received:\s*"([^"]*)"', message)
    first_line = next((line.strip() for line in message.splitlines() if line.strip()), "")

    return {
        "type": (
            "ASSERTION_MISMATCH"
            if expected and received
            else "EXECUTION_ERROR"
        ),
        "message": first_line[:300],
        "expected": expected.group(1) if expected else None,
        "received": received.group(1) if received else None,
    }


def evaluate(spec: dict) -> dict:
    tests = spec.get("tests", [])
    if len(tests) != 1:
        raise ValueError(
            f"Expected one Playwright test per scenario, got {len(tests)}: "
            f"{spec.get('title', '(no title)')}"
        )

    attempts = tests[0].get("results", [])
    if not attempts:
        return {"status": "NOT_RUN", "duration_ms": 0, "failure": None, "attachments": []}

    final = attempts[-1]
    raw = final.get("status", "unknown")
    status = {
        "passed": "PASSED",
        "failed": "FAILED",
        "timedOut": "TIMED_OUT",
        "skipped": "SKIPPED",
        "interrupted": "INTERRUPTED",
    }.get(raw, "UNKNOWN")

    if status == "PASSED" and any(
        a.get("status") in ("failed", "timedOut") for a in attempts[:-1]
    ):
        status = "FLAKY"

    return {
        "status": status,
        "duration_ms": sum(a.get("duration", 0) for a in attempts),
        "attempts": len(attempts),
        "failure": parse_failure(final) if status in ("FAILED", "TIMED_OUT", "INTERRUPTED") else None,
        "attachments": [
            {"name": a.get("name"), "content_type": a.get("contentType")}
            for a in final.get("attachments", [])
        ],
    }


def summarize(report: dict, story_id: int, revision: int, approved: dict[str, str]) -> dict:
    """approved maps scenario test IDs to acceptance criterion IDs."""
    prefix = f"story-{story_id}-rev-{revision}/"
    actual = {}

    for spec in walk_specs(report.get("suites", [])):
        file = str(spec.get("file", "")).replace("\\", "/")
        if prefix not in file:
            continue

        name = TC_ID.match(spec.get("title", ""))
        if not name:
            continue

        test_id = name.group(1)
        if test_id not in approved:
            continue
        if test_id in actual:
            raise ValueError(
                f"Duplicate result for {test_id}. This first version supports "
                "one Playwright project per generated test."
            )

        actual[test_id] = {
            "test_id": test_id,
            "acceptance_criterion_id": approved[test_id],
            "title": spec.get("title", ""),
            **evaluate(spec),
        }

    tests = []
    for test_id, ac_id in approved.items():
        tests.append(actual.get(test_id, {
            "test_id": test_id,
            "acceptance_criterion_id": ac_id,
            "title": "",
            "status": "NOT_RUN",
            "duration_ms": 0,
            "attempts": 0,
            "failure": None,
            "attachments": [],
        }))

    totals = Counter(t["status"] for t in tests)
    return {
        "story_id": story_id,
        "story_revision": revision,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "total": len(tests),
        "passed": totals["PASSED"],
        "failed": totals["FAILED"],
        "timed_out": totals["TIMED_OUT"],
        "flaky": totals["FLAKY"],
        "skipped": totals["SKIPPED"],
        "not_run": totals["NOT_RUN"],
        "interrupted": totals["INTERRUPTED"],
        "unknown": totals["UNKNOWN"],
        "tests": tests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a Playwright JSON report")
    parser.add_argument("--id", type=int, required=True, help="Azure DevOps Story ID")
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument(
        "--input", type=Path,
        default=APP_DIR / "test-results" / "results.json",
        help="Path to Playwright JSON results (default: test aplikacia/test-results/results.json)",
    )
    args = parser.parse_args()
    if args.id < 1 or args.revision < 1:
        parser.error("--id and --revision must be positive")

    folder = BACKEND_DIR / "data" / "stories" / str(args.id) / f"rev_{args.revision}"
    try:
        approved = load_approved_scenarios(folder)
        expected = {s.test_id: s.acceptance_criterion_id for s in approved.scenarios if s.status == "READY"}
        if not expected:
            raise ValueError("No approved READY scenarios")
        report = read_json(args.input)
        summary = summarize(report, args.id, args.revision, expected)
        if summary["not_run"] == len(expected):
            raise ValueError("No matching tests in the provided results.json. Run Playwright first.")
        output = folder / "execution.summary.json"
        output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved: {output}")
        print(f"Tests: {summary['total']}; passed: {summary['passed']}; failed: {summary['failed']}; "
              f"timed out: {summary['timed_out']}; not run: {summary['not_run']}")
        for test in summary["tests"]:
            failure = test.get("failure") or {}
            suffix = ""
            if failure.get("expected") is not None:
                suffix = f" (expected: {failure['expected']!r}; received: {failure['received']!r})"
            print(f"  {test['test_id']} {test['status']}{suffix}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Cannot process results: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
