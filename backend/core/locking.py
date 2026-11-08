import os
from contextlib import contextmanager

from backend.core.config import STORY_DATA as DATA


@contextmanager
def workflow_lock():
    """Serialize local work using shared files / Playwright report directory.

    This is a simple single-machine lock. Production multi-instance deployment
    needs a database/distributed job lock. A hard crash may leave a stale file.
    """
    DATA.mkdir(parents=True, exist_ok=True)
    lock = DATA / ".workflow.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Another workflow is running; retry after it finishes") from exc
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)
