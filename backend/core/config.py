import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TARGET_APP = ROOT / "target-app"
RUNNER = ROOT / "runner"
load_dotenv(BACKEND / ".env")
STORY_DATA = BACKEND / "data"
CONTROL_DATA = Path(os.environ.get("CONTROL_DATA_DIR", STORY_DATA / "control")).resolve()
LEGACY_CONTROL_DATA = ROOT / "control_api" / "data"
MIGRATION_LOCK = STORY_DATA / ".migration.lock"


def redact(value: str) -> str:
    for name in ("AZURE_DEVOPS_PAT", "OPENAI_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            value = value.replace(secret, "[REDACTED]")
    return value


def credentials() -> dict:
    return {
        "organization": os.getenv("AZURE_DEVOPS_ORGANIZATION", ""),
        "project": os.getenv("AZURE_DEVOPS_PROJECT", ""),
        "pat": os.getenv("AZURE_DEVOPS_PAT", ""),
    }
