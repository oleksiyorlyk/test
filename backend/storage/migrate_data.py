"""Offline, verified migration of the former control_api history directory."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import psutil

from backend.core.config import BACKEND, CONTROL_DATA, LEGACY_CONTROL_DATA, MIGRATION_LOCK, ROOT


def manifest(folder: Path) -> dict[str, str]:
    result = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError("Migration does not follow symbolic links")
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def check_database(folder: Path, *, idle=False):
    path = folder / "history.sqlite3"
    if not path.exists():
        return
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        if (
            idle
            and connection.execute(
                "SELECT count(*) FROM jobs WHERE status IN ('QUEUED','RUNNING')"
            ).fetchone()[0]
        ):
            raise ValueError("Finish or reconcile active jobs before migration")
    finally:
        connection.close()


def ensure_server_stopped():
    for process in psutil.process_iter(["name", "cmdline", "cwd"]):
        try:
            if process.pid == os.getpid() or "python" not in (process.info["name"] or "").lower():
                continue
            args = " ".join(process.info["cmdline"] or [])
            is_server = "uvicorn" in args and any(
                name in args for name in ("control_api.app", "backend.api")
            )
            is_worker = any(
                name in args
                for name in (
                    "-m control_api.worker",
                    "-m backend.worker",
                    "-m backend.execution.worker",
                )
            )
            if (is_server or is_worker) and Path(process.info["cwd"] or "").resolve() == ROOT:
                raise RuntimeError("Stop the local API and workers before migration")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


@contextmanager
def migration_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Another migration is already running") from exc
    os.close(fd)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def migrate(
    source: Path, destination: Path, backups: Path, *, lock: Path = MIGRATION_LOCK, copy=False
):
    source, destination, backups = source.resolve(), destination.resolve(), backups.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate directories")
    if source == Path(source.anchor) or destination == Path(destination.anchor):
        raise ValueError("A filesystem root cannot be migrated")
    if source == backups or source in backups.parents:
        raise ValueError("Backup must be outside the source directory")
    ensure_server_stopped()
    with migration_lock(lock):
        if not source.exists():
            if destination.exists():
                check_database(destination)
            return {
                "migrated": False,
                "reason": "already_migrated_or_no_legacy_data",
                "destination": str(destination),
            }
        if source.is_symlink() or not source.is_dir():
            raise ValueError("Migration source must be a real directory")
        check_database(source, idle=True)
        before = manifest(source)
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            if copy and destination.is_dir() and manifest(destination) == before:
                check_database(destination)
                return {
                    "migrated": False,
                    "reason": "already_copied",
                    "destination": str(destination),
                }
            raise ValueError(
                "Destination is not empty; histories will not be merged or overwritten"
            )
        backup = backups / (
            datetime.now(timezone.utc).strftime("control-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        )
        shutil.copytree(source, backup)
        if manifest(backup) != before:
            raise RuntimeError("Backup verification failed; source left in place")
        check_database(backup)
        if manifest(source) != before:
            raise RuntimeError("Source changed during migration; source left in place")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.rmdir()  # Verified empty, resolved, explicit destination only.
        if copy:
            shutil.copytree(source, destination)
        else:
            source.rename(destination)
        if manifest(destination) != before:
            raise RuntimeError(
                "Destination verification failed; verified backup is available at " + str(backup)
            )
        check_database(destination)
        return {
            "migrated": True,
            "files": len(before),
            "destination": str(destination),
            "backup": str(backup),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=LEGACY_CONTROL_DATA)
    parser.add_argument("--destination", type=Path, default=CONTROL_DATA)
    parser.add_argument("--backups", type=Path, default=BACKEND / "data" / "backups")
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy between mounts and retain the source (for Docker migrations)",
    )
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                migrate(args.source, args.destination, args.backups, copy=args.copy),
                ensure_ascii=True,
            )
        )
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
