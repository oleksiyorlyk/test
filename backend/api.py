"""FastAPI composition root. Import and OpenAPI export have no storage effects."""

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import CONTROL_DATA, LEGACY_CONTROL_DATA, MIGRATION_LOCK, ROOT, STORY_DATA
from backend.core.errors import ControlError, translate
from backend.routes import health, jobs, reviews, stories
from backend.services.jobs import Jobs
from backend.storage.store import Store

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "testserver"})
LOCAL_ORIGINS = frozenset(
    {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    }
)


def public_origin_from_env() -> str | None:
    """Read the exact public HTTPS origin for the deployed application."""
    value = os.environ.get("PUBLIC_ORIGIN", "").strip().rstrip("/")
    if not value:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("PUBLIC_ORIGIN must be an HTTPS origin such as https://app.example.com")
    return value


def create_app(data_dir: Path = CONTROL_DATA):
    @asynccontextmanager
    async def lifespan(app):
        if data_dir.resolve() == CONTROL_DATA:
            if MIGRATION_LOCK.exists():
                raise RuntimeError("Data migration is in progress. Wait before starting the API.")
            if (
                CONTROL_DATA == (STORY_DATA / "control").resolve()
                and (LEGACY_CONTROL_DATA / "history.sqlite3").exists()
            ):
                raise RuntimeError(
                    "Legacy history found. Stop the old server and run: python -m backend.migrate_data"
                )
        app.state.store = Store(data_dir)
        app.state.jobs = Jobs(app.state.store)
        app.state.catalog_cache = {"at": 0, "result": None}
        app.state.catalog_guard = threading.Lock()
        app.state.store.reconcile()
        yield

    app = FastAPI(title="AI Test Automation Control", lifespan=lifespan)
    public_origin = public_origin_from_env()
    allowed_hosts = set(LOCAL_HOSTS)
    allowed_origins = set(LOCAL_ORIGINS)
    if public_origin:
        allowed_hosts.add(urlsplit(public_origin).hostname)
        allowed_origins.add(public_origin)

    @app.middleware("http")
    async def allowed_requests(request: Request, call_next):
        # Validate the actual HTTP Host header, not X-Forwarded-Host.
        host_header = request.headers.get("host", "")
        try:
            host = urlsplit("//" + host_header).hostname
        except ValueError:
            host = None
        if host not in allowed_hosts:
            return JSONResponse(
                {"error": {"code": "HOST", "message": "Nepovolený názov hostiteľa."}},
                status_code=403,
            )

        # Check browser Origin on state-changing requests. This is not authentication.
        origin = request.headers.get("origin")
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and origin
            and origin not in allowed_origins
        ):
            return JSONResponse(
                {"error": {"code": "ORIGIN", "message": "Nepovolený pôvod požiadavky."}},
                status_code=403,
            )
        return await call_next(request)

    @app.exception_handler(ControlError)
    async def control_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {
                "error": {
                    "code": "VALIDATION",
                    "message": "Skontrolujte povinné polia a formát údajov.",
                }
            },
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        error = translate(exc)
        return JSONResponse(
            {"error": {"code": error.code, "message": error.message, "details": error.details}},
            status_code=error.status,
        )

    for router in (health.router, stories.router, reviews.router, jobs.router):
        app.include_router(router)

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise ControlError(404, "NOT_FOUND", "API endpoint sa nenašiel.")
            return FileResponse(dist / "index.html")

    return app


app = create_app()
