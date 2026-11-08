import json

from backend.core.config import redact
from backend.core.errors import ControlError, translate
from backend.models.http import ErrorResponse

# HTTPStatus renamed 422 in newer Python versions. Keep the public schema stable
# across the supported interpreters instead of deriving descriptions at runtime.
ERROR_RESPONSES = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in {
        403: "Forbidden",
        404: "Not Found",
        409: "Conflict",
        422: "Unprocessable Content",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
    }.items()
}


def invoke(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        raise translate(exc) from exc


def positive(story_id):
    if story_id < 1:
        raise ControlError(422, "VALIDATION", "ID musí byť kladné celé číslo.")


def public_job(job):
    result = {
        key: value for key, value in job.items() if key not in ("request", "pid", "process_started")
    }
    result["artifacts"] = [
        {key: value for key, value in item.items() if key != "stored_name"}
        for item in job["artifacts"]
    ]
    return json.loads(redact(json.dumps(result, ensure_ascii=False)))
