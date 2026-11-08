import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.storage.migrate_data import manifest, migrate
from backend.storage.store import Store


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "old"
        self.destination = self.root / "new"
        self.backups = self.root / "backups"
        self.lock = self.root / ".migration.lock"
        self.store = Store(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def run_migration(self):
        return migrate(self.source, self.destination, self.backups, lock=self.lock)

    def finished_job(self):
        job = self.store.create(1, "GENERATE", {})
        folder = self.source / job["id"] / "artifacts"
        folder.mkdir()
        (folder / "a1.json").write_text('{"passed":1}', encoding="utf-8")
        self.store.update(
            job["id"],
            status="SUCCEEDED",
            artifacts=[{"id": "a1", "name": "results.json", "size": 12, "stored_name": "a1.json"}],
        )
        return job

    def test_preserves_history_artifacts_and_verified_backup(self):
        job = self.finished_job()
        before = manifest(self.source)
        result = self.run_migration()
        self.assertTrue(result["migrated"])
        self.assertFalse(self.source.exists())
        self.assertEqual(manifest(self.destination), before)
        self.assertEqual(manifest(Path(result["backup"])), before)
        with TestClient(create_app(self.destination)) as client:
            response = client.get(f"/api/jobs/{job['id']}/artifacts/a1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"passed": 1})
            self.assertEqual(client.get(f"/api/jobs/{job['id']}").json()["status"], "SUCCEEDED")

    def test_repeat_is_idempotent(self):
        self.finished_job()
        self.run_migration()
        before = manifest(self.destination)
        self.assertFalse(self.run_migration()["migrated"])
        self.assertEqual(manifest(self.destination), before)
        self.assertEqual(len(list(self.backups.iterdir())), 1)

    def test_copy_mode_preserves_source_and_is_idempotent(self):
        self.finished_job()
        before = manifest(self.source)
        self.assertTrue(
            migrate(self.source, self.destination, self.backups, lock=self.lock, copy=True)[
                "migrated"
            ]
        )
        self.assertEqual(manifest(self.source), before)
        self.assertEqual(manifest(self.destination), before)
        self.assertFalse(
            migrate(self.source, self.destination, self.backups, lock=self.lock, copy=True)[
                "migrated"
            ]
        )

    def test_refuses_nonempty_destination(self):
        self.destination.mkdir()
        (self.destination / "history.sqlite3").write_text("another history", encoding="utf-8")
        before = manifest(self.source)
        with self.assertRaisesRegex(ValueError, "not empty"):
            self.run_migration()
        self.assertEqual(manifest(self.source), before)
        self.assertEqual((self.destination / "history.sqlite3").read_text(), "another history")

    def test_refuses_active_jobs(self):
        self.store.create(1, "EXECUTE", {})
        with self.assertRaisesRegex(ValueError, "active jobs"):
            self.run_migration()
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_refuses_running_server(self):
        with patch(
            "backend.storage.migrate_data.ensure_server_stopped",
            side_effect=RuntimeError("Stop the local API"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Stop the local API"):
                self.run_migration()
        self.assertTrue(self.source.exists())

    def test_refuses_corrupt_database(self):
        (self.source / "history.sqlite3").write_bytes(b"not a database")
        with self.assertRaises(sqlite3.DatabaseError):
            self.run_migration()
        self.assertTrue(self.source.exists())

    def test_failed_backup_verification_leaves_source(self):
        self.finished_job()
        original = manifest(self.source)
        with patch("backend.storage.migrate_data.manifest", side_effect=[original, {}]):
            with self.assertRaisesRegex(RuntimeError, "Backup verification failed"):
                self.run_migration()
        self.assertEqual(manifest(self.source), original)
        self.assertFalse(self.destination.exists())

    def test_rejects_nested_destination_and_handles_empty_target(self):
        with self.assertRaises(ValueError):
            migrate(self.source, self.source / "nested", self.backups, lock=self.lock)
        self.destination.mkdir()
        self.assertTrue(self.run_migration()["migrated"])


if __name__ == "__main__":
    unittest.main()
