"""CLI for M5. Create/update linked Test Cases; preview by default."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .approval import load_approved_scenarios
from .devops_publish import AzurePublisher, PublishError, signature
from .normalizer import normalize_story

BACKEND = Path(__file__).resolve().parent
PROJECT = BACKEND.parent


def save_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description="Publish reviewed Test Cases and Playwright code")
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--publish", action="store_true", help="Perform Azure DevOps writes")
    args = parser.parse_args()
    if args.id < 1 or args.revision < 1:
        parser.error("ID and revision must be positive")

    load_dotenv(BACKEND / ".env")
    folder = BACKEND / "data" / "stories" / str(args.id) / f"rev_{args.revision}"
    code_dir = PROJECT / "test aplikacia" / "generated-tests" / f"story-{args.id}-rev-{args.revision}"
    try:
        # This also verifies that approval still matches the draft and source Story.
        approved = load_approved_scenarios(folder)
        ready = [item for item in approved.scenarios if item.status == "READY"]
        blocked = [item.test_id for item in approved.scenarios if item.status == "BLOCKED"]
        if not ready:
            raise PublishError("No approved READY scenarios")

        # Preflight all code files BEFORE any remote changes.
        files = {}
        for scenario in ready:
            path = code_dir / (scenario.test_id.lower() + ".spec.js")
            if not path.is_file():
                raise PublishError(f"Generated test file missing: {path}")
            if f"Generated for {scenario.test_id} / {scenario.acceptance_criterion_id}" not in path.read_text(encoding="utf-8"):
                raise PublishError(f"Generated file does not match the approved test: {path.name}")
            files[scenario.test_id] = path

        print(f"Story #{args.id}, revision {args.revision}: {len(ready)} READY, {len(blocked)} BLOCKED")
        for scenario in ready:
            print(f"  {scenario.test_id}: {scenario.title} -> {files[scenario.test_id].name}")
        if not args.publish:
            print("DRY RUN ONLY — no network requests or Azure DevOps changes.")
            print("Run again with --publish to create/update cases and attach code.")
            return 0

        publisher = AzurePublisher(
            os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
            os.getenv("AZURE_DEVOPS_PROJECT", ""),
            os.getenv("AZURE_DEVOPS_PAT", ""),
        )
        story = publisher.work_item(args.id, relations=True)
        if story.get("fields", {}).get("System.WorkItemType") != "User Story":
            raise PublishError("The supplied ID does not refer to a User Story")
        if story.get("rev", 0) < args.revision:
            raise PublishError("The live Story revision is older than the approved revision")
        # Creating Test Cases and attachments increments the Story revision.
        # Therefore compare its actual requirements, not only its revision.
        fields = story["fields"]
        live_normalized = normalize_story({
            "id": story["id"],
            "title": fields.get("System.Title", ""),
            "description": fields.get("System.Description", ""),
            "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
        })
        saved_story = json.loads(
            (folder / "story.normalized.json").read_text(encoding="utf-8")
        )
        for field in ("title", "description", "acceptance_criteria"):
            if live_normalized[field] != saved_story[field]:
                raise PublishError(
                    "Story requirements changed in Azure DevOps. "
                    "Fetch, regenerate, and review the updated Story before publishing."
                )

        # Look across ALL Story revisions so TC-001 keeps the same Azure ID.
        # If duplicates exist, choose the lowest Azure ID and leave the rest alone.
        existing = publisher.find_existing(
            story, args.revision, {x.test_id for x in ready}
        )
        result = {
            "story_id": args.id,
            "story_revision": args.revision,
            "test_cases": {},
            "test_case_actions": {},
            "ignored_duplicate_test_cases": publisher.ignored_duplicates,
            "attachments": {},
            "blocked": blocked,
        }
        manifest = folder / "devops.publish.json"

        for scenario in ready:
            test_id = scenario.test_id
            if test_id in existing:
                case_id = existing[test_id]
                changed = publisher.update_case(
                    case_id, args.id, args.revision, scenario
                )
                action = "updated" if changed else "unchanged"
                print(f"{action.capitalize()} Test Case #{case_id} for {test_id}")
            else:
                case_id = publisher.create_case(
                    args.id, args.revision, scenario
                )
                action = "created"
                print(f"Created Test Case #{case_id} for {test_id}")

            result["test_cases"][test_id] = case_id
            result["test_case_actions"][test_id] = action
            save_json(manifest, result)

        for scenario in ready:
            test_id = scenario.test_id
            file_path = files[test_id]
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:12]
            filename = (
                f"story-{args.id}-rev-{args.revision}-{test_id.lower()}"
                f"-{file_hash}.spec.js"
            )
            key = signature(args.id, args.revision, test_id) + f" sha256={file_hash}"
            live_story = publisher.work_item(args.id, relations=True)
            if publisher.already_attached(live_story, filename, key):
                result["attachments"][test_id] = "already linked"
                print(f"Skipping existing attachment for {test_id}")
            else:
                result["attachments"][test_id] = publisher.attach_file(
                    args.id, file_path, filename, key
                )
                print(f"Attached {filename} to Story #{args.id}")
            save_json(manifest, result)

        print(f"M5 complete. Local publication manifest: {manifest}")
        return 0
    except (OSError, ValueError, KeyError, PublishError) as exc:
        print(f"M5 failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
