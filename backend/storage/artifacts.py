import hashlib
import json

from backend.core.config import RUNNER, STORY_DATA

NAMES = {
    "story.normalized.json",
    "scenarios.draft.json",
    "scenarios.validation.json",
    "scenarios.generation.json",
    "scenarios.approved.json",
    "scenarios.approval.json",
    "playwright.generation.json",
    "execution.summary.json",
    "devops.publish.json",
    "results.publish.json",
    "playwright-report.zip",
}


def sources(story_id):
    root = STORY_DATA / "stories" / str(story_id)
    paths = [p for p in root.glob("rev_*/*") if p.is_file() and p.name in NAMES]
    paths += list((RUNNER / "generated-tests").glob(f"story-{story_id}-rev-*/*.spec.js"))
    report = RUNNER / "test-results" / "results.json"
    if report.is_file():
        paths.append(report)
    return paths


def fingerprint(path):
    return (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())


def snapshot(store, job, before):
    artifacts, partial = [], {}
    directory = store.root / job["id"] / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    for path in sources(job["story_id"]):
        if before.get(str(path)) == fingerprint(path):
            continue
        # Snapshot only files written by this run, never old reports left by a failed run.
        artifact_id = f"a{len(artifacts) + 1}"
        destination = directory / (artifact_id + path.suffix)
        destination.write_bytes(path.read_bytes())
        artifacts.append(
            {
                "id": artifact_id,
                "name": path.name,
                "size": destination.stat().st_size,
                "stored_name": destination.name,
            }
        )
        if path.name in ("execution.summary.json", "devops.publish.json", "results.publish.json"):
            key = {
                "execution.summary.json": "execution",
                "devops.publish.json": "devops",
                "results.publish.json": "result_uploads",
            }[path.name]
            partial[key] = json.loads(path.read_text(encoding="utf-8"))
    return artifacts, partial
