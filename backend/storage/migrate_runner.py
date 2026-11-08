"""Verified migration of generated tests and reports; never rewrites their contents."""

import argparse
import json
import shutil
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.core.config import BACKEND, CONTROL_DATA, MIGRATION_LOCK, ROOT, RUNNER, STORY_DATA
from backend.storage.migrate_data import (
    check_database,
    ensure_server_stopped,
    manifest,
    migration_lock,
)

DIRECTORIES = ("generated-tests", "test-results", "playwright-report")


def ensure_compose_stopped():
    docker = shutil.which("docker")
    if not docker:
        windows = Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe")
        docker = str(windows) if windows.is_file() else None
    if docker:
        daemon = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if daemon.returncode:
            return  # No reachable local engine; no local Compose mounts are in use.
        result = subprocess.run(
            [docker, "compose", "ps", "--status", "running", "-q"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode:
            raise RuntimeError(
                "Cannot verify Compose state; stop Compose and resolve docker compose ps first"
            )
        if result.stdout.strip():
            raise RuntimeError("Stop Docker Compose before migrating runner data")


def checked_directory(path: Path):
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError("Expected a real directory: " + str(path))


def migrate(
    source: Path,
    destination: Path,
    backups: Path,
    *,
    lock: Path = MIGRATION_LOCK,
    control: Path = CONTROL_DATA,
    workflow: Path = STORY_DATA / ".workflow.lock",
):
    # Check links before resolve so they cannot silently redirect migration.
    for path in (source, destination, backups):
        checked_directory(path)
        if any(parent.is_symlink() for parent in path.absolute().parents):
            raise ValueError("Migration does not follow symbolic links")
    source, destination, backups = source.resolve(), destination.resolve(), backups.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate directories")
    if source == Path(source.anchor) or destination == Path(destination.anchor):
        raise ValueError("A filesystem root cannot be migrated")
    if (
        source == backups
        or source in backups.parents
        or destination == backups
        or destination in backups.parents
    ):
        raise ValueError("Backup must be outside source and destination")
    ensure_server_stopped()
    ensure_compose_stopped()
    with migration_lock(lock):
        if workflow.exists():
            raise RuntimeError("Workflow lock exists; finish the workflow before migration")
        check_database(control, idle=True)
        selected = {}
        # Preflight every directory before copying or removing anything.
        for name in DIRECTORIES:
            old, new = source / name, destination / name
            checked_directory(old)
            checked_directory(new)
            if not old.exists():
                continue
            before = manifest(old)
            if new.exists() and any(new.iterdir()) and manifest(new) != before:
                raise ValueError(
                    "Destination differs; runner data will not be merged or overwritten: "
                    + str(new)
                )
            selected[name] = before
        if not selected:
            return {"migrated": False, "reason": "already_migrated_or_no_legacy_data"}
        backup = backups / (
            datetime.now(timezone.utc).strftime("runner-%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        )
        for name, before in selected.items():
            shutil.copytree(source / name, backup / name)
            if manifest(backup / name) != before:
                raise RuntimeError("Backup verification failed; source left in place")
        for name, before in selected.items():
            if manifest(source / name) != before:
                raise RuntimeError("Source changed during migration; source left in place")
            new = destination / name
            if not new.exists():
                shutil.copytree(source / name, new)
            elif not any(new.iterdir()):
                shutil.copytree(source / name, new, dirs_exist_ok=True)
            if manifest(new) != before:
                raise RuntimeError("Destination verification failed; source and backup retained")
        # All backups and destinations have passed verification before removal.
        for name, before in selected.items():
            if manifest(source / name) != before:
                raise RuntimeError("Source changed during migration; source retained")
        for name in selected:
            shutil.rmtree(source / name)
        return {
            "migrated": True,
            "files": sum(len(value) for value in selected.values()),
            "backup": str(backup),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "test aplikacia")
    parser.add_argument("--destination", type=Path, default=RUNNER)
    parser.add_argument("--backups", type=Path, default=BACKEND / "data/backups")
    args = parser.parse_args()
    try:
        print(json.dumps(migrate(args.source, args.destination, args.backups), ensure_ascii=True))
    except (OSError, ValueError, RuntimeError, sqlite3.Error, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
