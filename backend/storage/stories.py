from pathlib import Path

from backend.core.config import STORY_DATA as DATA
from backend.core.validation import validate_story_id
from backend.storage.json_files import read_json


def prepared_folder(story_id: int) -> tuple[Path, int]:
    validate_story_id(story_id)
    marker = read_json(DATA / "stories" / str(story_id) / "last_prepared.json")
    revision = marker.get("revision")
    if marker.get("story_id") != story_id or type(revision) is not int or revision < 1:
        raise ValueError("Saved prepared Story marker is invalid")
    return DATA / "stories" / str(story_id) / f"rev_{revision}", revision
