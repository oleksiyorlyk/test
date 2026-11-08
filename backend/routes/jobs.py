from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from backend.core.config import redact
from backend.core.errors import ControlError
from backend.models.http import Job, JobList
from backend.routes.common import ERROR_RESPONSES, public_job

router = APIRouter(responses=ERROR_RESPONSES)


@router.get("/api/jobs", response_model=JobList, response_model_exclude_unset=True)
def list_jobs(http_request: Request, story_id: int | None = None):
    store = http_request.app.state.store
    store.reconcile()
    return {"items": [public_job(job) for job in store.list(story_id)]}


@router.get("/api/jobs/{job_id}", response_model=Job, response_model_exclude_unset=True)
def get_job(http_request: Request, job_id: str):
    store = http_request.app.state.store
    store.reconcile()
    job = store.get(job_id)
    if not job:
        raise ControlError(404, "NOT_FOUND", "Operácia sa nenašla.")
    result = public_job(job)
    log = store.root / job_id / "run.log"
    result["log"] = redact(log.read_text(encoding="utf-8")[-100_000:]) if log.is_file() else ""
    return result


@router.get("/api/jobs/{job_id}/artifacts/{artifact_id}")
def artifact(http_request: Request, job_id: str, artifact_id: str):
    store = http_request.app.state.store
    job = store.get(job_id)
    item = (
        next((item for item in job["artifacts"] if item["id"] == artifact_id), None)
        if job
        else None
    )
    if not item:
        raise ControlError(404, "NOT_FOUND", "Artefakt sa nenašiel.")
    return FileResponse(
        store.root / job_id / "artifacts" / item["stored_name"],
        filename=item["name"],
        media_type="application/octet-stream",
    )
