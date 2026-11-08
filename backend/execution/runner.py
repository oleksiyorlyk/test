"""Execute the selected approved revision using the local Node runner."""

import os
import shutil
import subprocess
from pathlib import Path

from backend.core.config import RUNNER


def run_tests(story_id: int, revision: int) -> tuple[Path, int]:
    npx = shutil.which("npx.cmd") if os.name == "nt" else shutil.which("npx")
    if not npx:
        raise RuntimeError("Node.js/npm not installed: npx unavailable")
    if not (RUNNER / "node_modules" / "@playwright" / "test").is_dir():
        raise RuntimeError(
            'Playwright missing: run npm ci and npx playwright install chromium in "runner"'
        )
    result_json = RUNNER / "test-results" / "results.json"
    result_json.unlink(missing_ok=True)
    command = [
        npx,
        "--no-install",
        "playwright",
        "test",
        f"generated-tests/story-{story_id}-rev-{revision}",
    ]
    print("\n> " + " ".join(command), flush=True)
    execution = subprocess.run(command, cwd=RUNNER, check=False)
    # Assertion failures still produce publishable reports.
    if not result_json.is_file():
        raise RuntimeError("Playwright did not produce a JSON report")
    return result_json, execution.returncode
