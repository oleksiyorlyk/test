import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.execution.runner import run_tests


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "node_modules/@playwright/test").mkdir(parents=True)
        (self.root / "test-results").mkdir()
        self.report = self.root / "test-results/results.json"

    def test_failed_assertion_is_returned_with_new_report(self):
        self.report.write_text("stale", encoding="utf-8")

        def execute(command, *, cwd, check):
            self.assertFalse(self.report.exists())
            self.assertEqual(cwd, self.root)
            self.assertFalse(check)
            self.assertEqual(
                command[1:],
                ["--no-install", "playwright", "test", "generated-tests/story-12-rev-5"],
            )
            self.report.write_text('{"failed":1}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 1)

        with (
            patch("backend.execution.runner.RUNNER", self.root),
            patch("backend.execution.runner.shutil.which", return_value="npx"),
            patch("backend.execution.runner.subprocess.run", side_effect=execute),
        ):
            report, code = run_tests(12, 5)
        self.assertEqual(report, self.report)
        self.assertEqual(code, 1)

    def test_missing_report_cannot_reuse_old_results(self):
        self.report.write_text("stale", encoding="utf-8")
        with (
            patch("backend.execution.runner.RUNNER", self.root),
            patch("backend.execution.runner.shutil.which", return_value="npx"),
            patch(
                "backend.execution.runner.subprocess.run",
                return_value=subprocess.CompletedProcess([], 1),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not produce"):
                run_tests(12, 5)
        self.assertFalse(self.report.exists())

    def test_missing_playwright_does_not_launch_npx(self):
        with (
            patch("backend.execution.runner.RUNNER", self.root / "missing"),
            patch("backend.execution.runner.shutil.which", return_value="npx"),
            patch("backend.execution.runner.subprocess.run") as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "Playwright missing"):
                run_tests(12, 5)
        execute.assert_not_called()
