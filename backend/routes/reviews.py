from fastapi import APIRouter, Request

from backend.core.errors import ControlError
from backend.models.http import ApproveRequest, EditRequest, JobStarted, Review
from backend.routes.common import ERROR_RESPONSES, invoke, positive

router = APIRouter(responses=ERROR_RESPONSES)


@router.get(
    "/api/stories/{story_id}/review", response_model=Review, response_model_exclude_unset=True
)
def review(http_request: Request, story_id: int):
    jobs = http_request.app.state.jobs
    positive(story_id)
    with jobs.guard:
        jobs.ensure_idle()
        from backend.services.stage1 import get_review

        return invoke(get_review, story_id)


@router.put(
    "/api/stories/{story_id}/review", response_model=Review, response_model_exclude_unset=True
)
def save_review(http_request: Request, story_id: int, request: EditRequest):
    jobs = http_request.app.state.jobs
    positive(story_id)
    with jobs.guard:
        jobs.ensure_idle()
        from backend.services.stage1 import save_reviewed_scenarios

        return invoke(
            save_reviewed_scenarios, story_id, request.draft, expected_hash=request.review_hash
        )


@router.post(
    "/api/stories/{story_id}/approve-and-run",
    status_code=202,
    response_model=JobStarted,
    response_model_exclude_unset=True,
)
def approve(http_request: Request, story_id: int, request: ApproveRequest):
    jobs = http_request.app.state.jobs
    positive(story_id)
    with jobs.guard:
        jobs.ensure_idle()
        from backend.services.stage1 import get_review

        current = invoke(get_review, story_id)
        if current["review_hash"] != request.review_hash or current["revision"] != request.revision:
            raise ControlError(
                409, "STALE_REVIEW", "Koncept sa zmenil. Pred schválením načítajte aktuálnu verziu."
            )
        return jobs.start(story_id, "EXECUTE", request.model_dump())
