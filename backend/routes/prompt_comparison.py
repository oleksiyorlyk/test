"""Local-only API for archived prompt-strategy experiments.

Runs the existing experiment in a background task, then snapshots its output.
No writes to Azure DevOps or existing job data.
"""
import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.core.config import ROOT, STORY_DATA

router = APIRouter(prefix="/api/prompt-comparisons", tags=["Prompt comparisons"])
RUNS = STORY_DATA / "experiments" / "web_runs"
BUSY = threading.Lock()


class RunRequest(BaseModel):
    story_id: int = Field(ge=1)


def now():
    return datetime.now(timezone.utc).isoformat()


def _save_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _public(record: dict):
    return {key: value for key, value in record.items() if key != "internal_error"}


def _execute(run_id: str, story_id: int):
    folder = RUNS / run_id
    status_file = folder / "status.json"
    status = _load_json(status_file)
    status["status"] = "RUNNING"
    _save_json(status_file, status)
    try:
        command = [sys.executable, "-m", "backend.experiments.compare_prompts", str(story_id), "--output-dir", str(folder)]
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=300, check=False,
        )
        if completed.returncode:
            raise RuntimeError("Experiment failed. Check backend configuration and logs.")
        report = _load_json(folder / "comparison.json")
        status.update({"status": "SUCCEEDED", "finished_at": now(), "results": report.get("results", {})})
    except Exception:
        status.update({"status": "FAILED", "finished_at": now(), "message": "Porovnanie zlyhalo. Skontrolujte nastavenia Azure a LLM alebo serverový denník."})
    finally:
        _save_json(status_file, status)
        BUSY.release()


def _folder(run_id: str) -> Path:
    if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
        raise HTTPException(status_code=404, detail="Porovnanie sa nenašlo")
    return RUNS / run_id


@router.get("")
def list_runs():
    items = []
    if RUNS.exists():
        for file in RUNS.glob("*/status.json"):
            try:
                record = _load_json(file)
                if record["status"] in ("RUNNING", "QUEUED") and not BUSY.locked():
                    record["status"] = "INTERRUPTED"
                items.append(_public(record))
            except (OSError, ValueError, KeyError):
                continue
    items.sort(key=lambda item: item.get("started_at", ""), reverse=True)
    return {"items": items}


@router.get("/{run_id}")
def get_run(run_id: str):
    folder = _folder(run_id)
    try:
        status = _load_json(folder / "status.json")
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Porovnanie sa nenašlo")
    if status["status"] in ("RUNNING", "QUEUED") and not BUSY.locked():
        status["status"] = "INTERRUPTED"
    output = _public(status)
    if output["status"] == "SUCCEEDED":
        output["report"] = _load_json(folder / "comparison.json")
        output["prompt_a"] = _load_json(folder / "prompt_A_scenarios.json")
        output["prompt_b"] = _load_json(folder / "prompt_B_scenarios.json")
    return output


@router.post("", status_code=202)
def start_run(body: RunRequest, tasks: BackgroundTasks):
    if os.getenv("PUBLIC_ORIGIN"):
        raise HTTPException(status_code=403, detail="Spustenie porovnania je povolené iba v lokálnom režime.")
    if not BUSY.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Iné porovnanie práve prebieha")
    try:
        run_id = uuid.uuid4().hex
        record = {"id": run_id, "story_id": body.story_id, "status": "QUEUED", "started_at": now()}
        _save_json(RUNS / run_id / "status.json", record)
        tasks.add_task(_execute, run_id, body.story_id)
        return record
    except Exception:
        BUSY.release()
        raise


@router.get("/{run_id}/report")
def download_report(run_id: str):
    folder = _folder(run_id)
    try:
        status = _load_json(folder / "status.json")
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Porovnanie sa nenašlo")
    report = folder / "comparison.md"
    if status.get("status") != "SUCCEEDED" or not report.is_file():
        raise HTTPException(status_code=404, detail="Report nie je dostupný")
    return FileResponse(report, filename=f"prompt-comparison-story-{status['story_id']}.md", media_type="text/markdown")
