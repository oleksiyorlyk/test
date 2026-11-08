import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.storage.migrate_data import manifest
from backend.storage.migrate_runner import migrate
from backend.storage.store import Store


class RunnerMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "legacy"
        self.destination = self.root / "runner"
        self.backups = self.root / "backups"
        self.control = self.root / "control"
        for name in ("generated-tests/story-12-rev-5", "test-results", "playwright-report/data"):
            folder = self.source / name
            folder.mkdir(parents=True)
            (folder / "file").write_bytes(b"original\x00\xff")
        (self.source / "unknown.txt").write_text("keep me", encoding="utf-8")
        self.addCleanup(patch.stopall)
        patch("backend.storage.migrate_runner.ensure_server_stopped").start()
        patch("backend.storage.migrate_runner.ensure_compose_stopped").start()

    def run_migration(self):
        return migrate(
            self.source,
            self.destination,
            self.backups,
            lock=self.root / ".migration.lock",
            control=self.control,
            workflow=self.root / ".workflow.lock",
        )

    def test_preserves_bytes_backup_and_unknown_files(self):
        original = manifest(self.source)
        result = self.run_migration()
        expected = {name: value for name, value in original.items() if name != "unknown.txt"}
        self.assertEqual(manifest(self.destination), expected)
        self.assertEqual(manifest(Path(result["backup"])), expected)
        self.assertEqual(manifest(self.source), {"unknown.txt": original["unknown.txt"]})

    def test_repeat_does_not_change_destination(self):
        self.run_migration()
        before = manifest(self.destination)
        self.assertFalse(self.run_migration()["migrated"])
        self.assertEqual(manifest(self.destination), before)
        self.assertEqual(len(list(self.backups.iterdir())), 1)

    def test_resumes_identical_destination(self):
        shutil.copytree(self.source / "generated-tests", self.destination / "generated-tests")
        self.assertTrue(self.run_migration()["migrated"])

    def test_conflict_preflights_all_directories(self):
        folder = self.destination / "playwright-report"
        folder.mkdir(parents=True)
        (folder / "other").write_text("different", encoding="utf-8")
        before = manifest(self.source)
        with self.assertRaisesRegex(ValueError, "will not be merged"):
            self.run_migration()
        self.assertEqual(manifest(self.source), before)
        self.assertFalse(self.backups.exists())

    def test_active_job_is_refused(self):
        Store(self.control).create(1, "GENERATE", {})
        with self.assertRaisesRegex(ValueError, "active jobs"):
            self.run_migration()
        self.assertTrue((self.source / "generated-tests").exists())

    def test_workflow_lock_is_refused(self):
        (self.root / ".workflow.lock").touch()
        with self.assertRaisesRegex(RuntimeError, "Workflow lock"):
            self.run_migration()

    def test_running_compose_is_refused(self):
        with patch(
            "backend.storage.migrate_runner.ensure_compose_stopped",
            side_effect=RuntimeError("Stop Docker Compose"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Compose"):
                self.run_migration()

    def test_failed_backup_retains_source(self):
        original = manifest(self.source)
        real = shutil.copytree

        def corrupt(source, destination, *args, **kwargs):
            result = real(source, destination, *args, **kwargs)
            (Path(destination) / "corruption").write_text("bad", encoding="utf-8")
            return result

        with patch("backend.storage.migrate_runner.shutil.copytree", side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, "Backup verification"):
                self.run_migration()
        self.assertEqual(manifest(self.source), original)

    def test_backup_can_restore_original_data(self):
        result = self.run_migration()
        restored = self.root / "restored"
        shutil.copytree(Path(result["backup"]), restored)
        self.assertEqual(manifest(restored), manifest(self.destination))

    def test_nested_paths_are_refused(self):
        self.destination = self.source / "runner"
        with self.assertRaisesRegex(ValueError, "separate"):
            self.run_migration()
