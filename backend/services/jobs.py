import os
import subprocess
import sys
import threading

import psutil

from backend.core.config import MIGRATION_LOCK, ROOT, STORY_DATA, redact
from backend.core.errors import ControlError


class Jobs:
    def __init__(self, store):
        self.store = store
        self.guard = threading.RLock()

    def ensure_idle(self):
        self.store.reconcile()
        if (
            self.store.active()
            or (STORY_DATA / ".workflow.lock").exists()
            or MIGRATION_LOCK.exists()
        ):
            raise ControlError(
                409, "BUSY", "Generátor práve pracuje. Počkajte na dokončenie operácie."
            )

    def start(self, story_id, kind, request):
        with self.guard:
            self.ensure_idle()
            job = self.store.create(story_id, kind, request)
            try:
                environment = {
                    **os.environ,
                    "CONTROL_DATA_DIR": str(self.store.root),
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONIOENCODING": "utf-8",
                }
                # The worker owns an inherited file handle: an API restart must not
                # close its output pipe and interrupt the backend's subprocesses.
                with (self.store.root / job["id"] / "run.log").open("ab") as log:
                    process = subprocess.Popen(
                        [sys.executable, "-m", "backend.worker", job["id"]],
                        cwd=ROOT,
                        env=environment,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                try:
                    started = psutil.Process(process.pid).create_time()
                    self.store.update(job["id"], pid=process.pid, process_started=started)
                except psutil.NoSuchProcess:
                    pass
                threading.Thread(
                    target=self.monitor, args=(process, job["id"]), daemon=True
                ).start()
            except Exception:
                self.store.update(
                    job["id"],
                    status="FAILED",
                    error={
                        "code": "START_FAILED",
                        "message": "Nepodarilo sa spustiť pracovný proces.",
                    },
                )
                raise
            return {"job_id": job["id"], "status": "QUEUED"}

    def monitor(self, process, job_id):
        process.wait()
        log = self.store.root / job_id / "run.log"
        if log.is_file():
            log.write_text(
                redact(log.read_text(encoding="utf-8", errors="replace")), encoding="utf-8"
            )
        observed = self.store.get(job_id)
        self.store.interrupt_if_active(observed, "Pracovný proces sa neočakávane ukončil.")
