import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psutil

from backend.core.errors import ControlError


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database = root / "history.sqlite3"
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, story_id INTEGER NOT NULL, kind TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER, pid INTEGER, process_started REAL, request TEXT NOT NULL,
                result TEXT, error TEXT, artifacts TEXT NOT NULL DEFAULT '[]')""")
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs ((1)) WHERE status IN ('QUEUED','RUNNING')"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(row)
        for key in ("request", "result", "error", "artifacts"):
            result[key] = json.loads(result[key]) if result[key] is not None else None
        return result

    def get(self, job_id):
        with self.connect() as db:
            return self.decode(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list(self, story_id=None):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs"
                + (" WHERE story_id=?" if story_id else "")
                + " ORDER BY created_at DESC",
                (story_id,) if story_id else (),
            ).fetchall()
            return [self.decode(row) for row in rows]

    def active(self):
        with self.connect() as db:
            return self.decode(
                db.execute(
                    "SELECT * FROM jobs WHERE status IN ('QUEUED','RUNNING') LIMIT 1"
                ).fetchone()
            )

    def create(self, story_id, kind, request):
        job_id = str(uuid.uuid4())
        try:
            with self.connect() as db:
                db.execute(
                    "INSERT INTO jobs (id,story_id,kind,status,created_at,updated_at,revision,request) VALUES (?,?,?,'QUEUED',?,?,?,?)",
                    (
                        job_id,
                        story_id,
                        kind,
                        now(),
                        now(),
                        request.get("revision"),
                        json.dumps(request),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ControlError(
                409, "BUSY", "Iná operácia už beží. Počkajte na jej dokončenie."
            ) from exc
        (self.root / job_id).mkdir()
        return self.get(job_id)

    def update(self, job_id, **values):
        allowed = {"status", "revision", "pid", "process_started", "result", "error", "artifacts"}
        if not values.keys() <= allowed:
            raise ValueError("Unsupported database field")
        for key in ("result", "error", "artifacts"):
            if key in values:
                values[key] = json.dumps(values[key], ensure_ascii=False)
        values["updated_at"] = now()
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?",
                (*values.values(), job_id),
            )

    def reconcile(self):
        for job in self.list():
            if job["status"] not in ("QUEUED", "RUNNING"):
                continue
            try:
                process = psutil.Process(job["pid"]) if job["pid"] else None
                # Epoch-based create_time changes when the Docker VM clock is
                # corrected. Match the actual worker invocation and unique job
                # ID instead: a recycled PID running another command is not ours.
                alive = False
                if process and process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    command = process.cmdline()
                    for index, argument in enumerate(command[:-2]):
                        if (
                            argument == "-m"
                            and command[index + 1]
                            in ("backend.worker", "backend.execution.worker", "control_api.worker")
                            and command[index + 2] == job["id"]
                        ):
                            alive = True
                            break
            except psutil.AccessDenied:
                # Failure to inspect a process is not evidence that it stopped.
                continue
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                alive = False
            except OSError:
                continue
            # A freshly queued worker may not have registered its PID yet.
            age = (
                datetime.now(timezone.utc) - datetime.fromisoformat(job["created_at"])
            ).total_seconds()
            if not alive and (job["pid"] or age > 30):
                self.interrupt_if_active(
                    job, "Proces bol prerušený. Operácia sa automaticky neopakuje."
                )

    def interrupt_if_active(self, observed: dict, message: str) -> bool:
        """Do not overwrite a worker's completion or newer PID registration."""
        error = json.dumps({"code": "INTERRUPTED", "message": message}, ensure_ascii=False)
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status='INTERRUPTED',error=?,updated_at=? "
                "WHERE id=? AND status IN ('QUEUED','RUNNING') "
                "AND pid IS ? AND process_started IS ?",
                (error, now(), observed["id"], observed["pid"], observed["process_started"]),
            )
            return cursor.rowcount == 1
