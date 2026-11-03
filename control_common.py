"""Small helpers for the four HUMAN-CHECKPOINT workflow controllers.

Run the controller scripts from the repository root (the parent of backend/).
They intentionally reuse the existing backend CLI modules.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
APP_DIR = ROOT / "test aplikacia"


class WorkflowError(RuntimeError):
    """An expected workflow precondition or subprocess failed."""


def positive(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise ValueError("ID and revision must be positive integers")
    return result


def story_folder(story_id: int, revision: int) -> Path:
    return BACKEND / "data" / "stories" / str(story_id) / f"rev_{revision}"


def latest_revision(story_id: int) -> int:
    root = BACKEND / "data" / "stories" / str(story_id)
    revisions = []
    for p in root.glob("rev_*/story.normalized.json"):
        try:
            revisions.append(int(p.parent.name.removeprefix("rev_")))
        except ValueError:
            pass
    if not revisions:
        raise WorkflowError(f"No normalized Story found for #{story_id}")
    return max(revisions)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"Missing file: {path}") from exc


def run_module(module: str, *args: str) -> None:
    command = [sys.executable, "-m", module, *map(str, args)]
    print("\n> " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise WorkflowError(f"{module} failed with exit code {result.returncode}")


def section(title: str) -> None:
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66, flush=True)
