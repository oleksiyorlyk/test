import time
from typing import Literal

from fastapi import APIRouter, Query, Request

from backend.integrations import azure_catalog
from backend.models.http import Catalog, JobStarted, Story
from backend.routes.common import ERROR_RESPONSES, invoke, positive

router = APIRouter(responses=ERROR_RESPONSES)


@router.get("/api/stories", response_model=Catalog, response_model_exclude_unset=True)
def list_stories(
    http_request: Request,
    search: str = "",
    state: str = "",
    sort: Literal["changed", "title", "id"] = "changed",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    refresh: bool = False,
):
    # Cache Azure reads for 30 seconds; never cache secrets or errors.
    cache = http_request.app.state.catalog_cache
    cache_guard = http_request.app.state.catalog_guard
    with cache_guard:
        if refresh or not cache["result"] or time.monotonic() - cache["at"] > 30:
            cache["result"] = invoke(azure_catalog.catalog, page_size=2**31 - 1)
            cache["at"] = time.monotonic()
        rows = cache["result"]["items"]
        needle = search.strip().casefold().lstrip("#")
        filtered = [
            row
            for row in rows
            if (not state or row["state"] == state)
            and (not needle or needle in row["title"].casefold() or needle == str(row["id"]))
        ]
        key = {"changed": "changed_at", "title": "title", "id": "id"}[sort]
        filtered = sorted(
            filtered,
            key=lambda row: row[key].casefold() if key == "title" else row[key],
            reverse=sort != "title",
        )
        return {
            "items": filtered[(page - 1) * page_size : page * page_size],
            "total": len(filtered),
            "states": cache["result"]["states"],
            "page": page,
            "page_size": page_size,
        }


@router.get("/api/stories/{story_id}", response_model=Story, response_model_exclude_unset=True)
def get_story(http_request: Request, story_id: int):
    positive(story_id)
    return invoke(azure_catalog.story, story_id)


@router.post(
    "/api/stories/{story_id}/generate",
    status_code=202,
    response_model=JobStarted,
    response_model_exclude_unset=True,
)
def generate(http_request: Request, story_id: int):
    jobs = http_request.app.state.jobs
    positive(story_id)
    return jobs.start(story_id, "GENERATE", {})
