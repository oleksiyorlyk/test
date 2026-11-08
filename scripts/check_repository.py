"""Offline repository checks: Markdown paths and Git ignore boundaries."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent


def main():
    documents = [
        ROOT / name
        for name in (
            "README.md",
            "backend/README_BACKEND.md",
            "frontend/README.md",
            "runner/README.md",
            "docs/ci.md",
        )
    ]
    for document in documents:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+://", target) or target.startswith("#"):
                continue
            target = unquote(target.split("#")[0].strip("<>"))
            if target and not (document.parent / target).exists():
                raise SystemExit(
                    f"Broken documentation link in {document.relative_to(ROOT)}: {target}"
                )
    ignored = [
        "backend/.env",
        "backend/data/control/history.sqlite3",
        "runner/generated-tests/example.spec.js",
        "runner/test-results/results.json",
        "runner/playwright-report/index.html",
        "frontend/dist/index.html",
        "runner/node_modules/package/file.js",
        ".venv/pyvenv.cfg",
        ".ci-artifacts/compose.log",
        ".cache/example",
        "frontend/.eslintcache",
    ]
    sources = [
        "backend/.env.example",
        "backend/tests/test_control.py",
        "runner/tests/helpers/app-state.js",
        "runner/test-data.json",
        "runner/package-lock.json",
        "frontend/package-lock.json",
        "uv.lock",
        "frontend/e2e/control.spec.ts",
        "frontend/src/features/scenarios/ScenarioEditor.test.tsx",
        "contracts/openapi.json",
        ".gitlab-ci.yml",
        "compose.ci.yaml",
        "scripts/ci/docker-smoke.sh",
        ".gitattributes",
    ]
    for expected, paths in ((True, ignored), (False, sources)):
        for name in paths:
            if not expected and not (ROOT / name).is_file():
                raise SystemExit(f"Required source file is missing: {name}")
            result = subprocess.run(["git", "check-ignore", "--no-index", "-q", name], cwd=ROOT)
            if result.returncode not in (0, 1) or (result.returncode == 0) != expected:
                raise SystemExit(f"Unexpected Git ignore rule for {name}")
    print("Documentation links and Git ignore boundaries: OK.")


if __name__ == "__main__":
    main()
