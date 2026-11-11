"""Offline API smoke tests; never call Azure or an LLM."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.routes import prompt_comparison


class PromptComparisonApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.run_patch = patch.object(prompt_comparison, "RUNS", self.dir / "runs")
        self.run_patch.start()
        self.client_context = TestClient(create_app(data_dir=self.dir / "control"))
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.run_patch.stop()
        self.temp.cleanup()

    def test_empty_history(self):
        response = self.client.get("/api/prompt-comparisons")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})

    def test_reject_invalid_story_id_without_starting_run(self):
        response = self.client.post("/api/prompt-comparisons", json={"story_id": 0})
        self.assertEqual(response.status_code, 422)
        self.assertFalse((self.dir / "runs").exists())

    def test_reject_invalid_run_identifier(self):
        response = self.client.get("/api/prompt-comparisons/../../foo")
        self.assertIn(response.status_code, (404, 400))
        response = self.client.get("/api/prompt-comparisons/not-a-run-id")
        self.assertEqual(response.status_code, 404)

    def test_report_unavailable_for_unknown_run(self):
        response = self.client.get("/api/prompt-comparisons/" + "a" * 32 + "/report")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
