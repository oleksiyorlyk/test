"""Offline Compose checks; does not generate, execute or publish user scenarios."""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from backend.core.config import BACKEND, CONTROL_DATA, RUNNER


def check_contents():
    assert not (BACKEND / ".env").exists(), "Secret file was baked into the image"
    assert not Path("/app/control_api").exists()
    assert not Path("/app/frontend").exists()
    assert not Path("/app/deprecated").exists()
    assert not Path("/app/docs").exists()


def check_history():
    # Read API only: no workflow writes and no external integration requests.
    with urllib.request.urlopen("http://127.0.0.1:8001/api/jobs") as response:
        jobs = json.load(response)["items"]
    artifacts = 0
    for job in jobs:
        for item in job["artifacts"]:
            with urllib.request.urlopen(
                f"http://127.0.0.1:8001/api/jobs/{job['id']}/artifacts/{item['id']}"
            ) as response:
                body = response.read()
            assert len(body) == item["size"]
            artifacts += 1
    print(json.dumps({"history_jobs": len(jobs), "downloadable_artifacts": artifacts}), flush=True)


def check_browser():
    # Use the existing YourTask Playwright webServer config, override reporters
    # and output paths so the user's reports are not replaced by this smoke test.
    token = "docker-smoke-" + str(os.getpid())
    directory = RUNNER / "generated-tests" / token
    directory.mkdir()
    spec = directory / "smoke.spec.js"
    spec.write_text(
        "const {test,expect}=require('@playwright/test');test('YourTask Chromium smoke',async({page})=>{await page.goto('/');await expect(page.getByTestId('login-tab')).toBeVisible();});",
        encoding="utf-8",
    )
    try:
        with tempfile.TemporaryDirectory(prefix="testforge-smoke-") as output:
            subprocess.run(
                [
                    "npx",
                    "--no-install",
                    "playwright",
                    "test",
                    f"generated-tests/{token}",
                    "--reporter=line",
                    "--output=" + output,
                    "--workers=1",
                ],
                cwd=RUNNER,
                check=True,
            )
    finally:
        spec.unlink(missing_ok=True)
        directory.rmdir()
    print("Chromium and YourTask webServer: OK", flush=True)


if __name__ == "__main__":
    if "--image-only" in sys.argv:
        check_contents()
        assert not (CONTROL_DATA / "history.sqlite3").exists(), "History was baked into the image"
        assert not list((RUNNER / "generated-tests").rglob("*.spec.js"))
        print("Image contains no local credentials, history, reports or user scenarios.")
    else:
        check_history()
        check_browser()
