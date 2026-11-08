import os
import shutil

from fastapi import APIRouter, Request

from backend.core.config import RUNNER, credentials
from backend.models.http import (
    Health,
)
from backend.routes.common import ERROR_RESPONSES

router = APIRouter(responses=ERROR_RESPONSES)


@router.get("/api/health", response_model=Health, response_model_exclude_unset=True)
def health(http_request: Request):
    config = credentials()
    return {
        "organization": config["organization"],
        "project": config["project"],
        "checks": {
            "azure": all(config.values()),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "node": bool(shutil.which("node")),
            "npm": bool(shutil.which("npx.cmd") or shutil.which("npx")),
            "playwright": (RUNNER / "node_modules" / "@playwright" / "test").is_dir(),
        },
        "mode": "local",
    }
