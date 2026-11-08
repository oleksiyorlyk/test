"""One isolated process per operation; original backend functions are unchanged."""

import os
import sys

import psutil

from backend.core.config import CONTROL_DATA, redact
from backend.core.errors import translate
from backend.storage import artifacts as archive
from backend.storage.store import Store


def execute(store, job_id):
    job = store.get(job_id)
    process = psutil.Process()
    store.update(job_id, status="RUNNING", pid=os.getpid(), process_started=process.create_time())
    before = {str(path): archive.fingerprint(path) for path in archive.sources(job["story_id"])}
    result, error = None, None
    try:
        if job["kind"] == "GENERATE":
            from backend.services.stage1 import prepare_scenarios

            result = prepare_scenarios(job["story_id"])
        else:
            from backend.services.stage1 import get_review
            from backend.services.stage2 import approve_execute_publish

            review = get_review(job["story_id"])
            if review["revision"] != job["request"]["revision"]:
                raise ValueError("Prepared Story revision mismatch")
            result = approve_execute_publish(
                job["story_id"], expected_hash=job["request"]["review_hash"]
            )
        store.update(job_id, revision=result["revision"])
    except Exception as exc:
        translated = translate(exc)
        error = {
            "code": translated.code,
            "message": translated.message,
            "details": translated.details,
        }
        print(translated.message, flush=True)
    try:
        artifacts, partial = archive.snapshot(store, job, before)
    except Exception as exc:
        artifacts, partial = [], {}
        error = error or {
            "code": "SNAPSHOT_FAILED",
            "message": "Nepodarilo sa archivovať artefakty.",
            "details": str(exc),
        }
    if error:
        result = {
            **partial,
            "publication": "PARTIAL"
            if partial.get("devops") or partial.get("result_uploads")
            else "NOT_COMPLETED",
        }
    sys.stdout.flush()
    log = store.root / job_id / "run.log"
    if log.is_file():
        log.write_text(redact(log.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    store.update(
        job_id,
        status="FAILED" if error else "SUCCEEDED",
        result=result,
        error=error,
        artifacts=artifacts,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    args = parser.parse_args()
    execute(Store(CONTROL_DATA), args.job_id)


if __name__ == "__main__":
    main()
