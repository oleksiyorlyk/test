"""Check the pip-compatible runtime export without rewriting repository files."""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    executable = shutil.which("uv")
    if executable is None:
        local = ROOT / ".venv" / ("Scripts/uv.exe" if os.name == "nt" else "bin/uv")
        executable = str(local)
    result = subprocess.run(
        [
            executable,
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--no-header",
            "--no-annotate",
            "--no-hashes",
            "--quiet",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    expected = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
    if result.stdout != expected:
        raise SystemExit(
            "Runtime requirements are out of date; export them from uv.lock (see README)."
        )
    print("Runtime requirements match uv.lock.")


if __name__ == "__main__":
    main()
