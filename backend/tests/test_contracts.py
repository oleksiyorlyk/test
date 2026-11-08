import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.models.http import JobResult
from backend.tests.fixtures import review


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_factory_and_openapi_do_not_create_data(self):
        data = self.root / "not-created"
        app = create_app(data)
        schema = app.openapi()
        self.assertFalse(data.exists())
        self.assertIn("Review", schema["components"]["schemas"])
        self.assertIn(
            "application/json", schema["paths"]["/api/jobs"]["get"]["responses"]["200"]["content"]
        )

    def test_offline_export_does_not_start_storage(self):
        data = self.root / "not-created"
        output = self.root / "openapi.json"
        subprocess.run(
            [sys.executable, "-m", "backend.export_openapi", "--output", str(output)],
            env={**os.environ, "CONTROL_DATA_DIR": str(data)},
            check=True,
            capture_output=True,
        )
        self.assertFalse(data.exists())
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), create_app().openapi())

    def test_review_preserves_omissions_nulls_and_extensions(self):
        expected = review()
        expected["story"]["source"] = {"url": "https://example.test/story/1", "extension": None}
        expected["story"]["acceptance_criteria"][0]["extension"] = {"original": True}
        expected["extra_metadata"] = {"nested": [None, {"value": 1}]}
        with TestClient(create_app(self.root / "data")) as client:
            with patch("backend.services.stage1.get_review", return_value=expected):
                response = client.get("/api/stories/1/review")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_job_wire_shape_keeps_partial_results(self):
        with TestClient(create_app(self.root / "data")) as client:
            store = client.app.state.store
            job = store.create(1, "EXECUTE", {"revision": 1})
            result = {
                "publication": "PARTIAL",
                "devops": {"test_cases": {"TC-001": 13}, "unknown": None},
                "result_uploads": {"attachments": {"html": {"status": "uploaded"}}},
            }
            store.update(
                job["id"],
                status="FAILED",
                result=result,
                error={"code": "SERVICE_ERROR", "message": "failure", "details": None},
            )
            listing = client.get("/api/jobs").json()["items"][0]
            detail = client.get("/api/jobs/" + job["id"]).json()
        self.assertEqual(listing["result"], result)
        self.assertEqual(listing["error"]["details"], None)
        self.assertNotIn("log", listing)
        self.assertEqual(detail["log"], "")
        self.assertNotIn("pid", detail)
        self.assertNotIn("request", detail)

    def test_result_models_preserve_extra_metadata(self):
        data = {"status": "PUBLISHED", "reviewer": "local", "custom": [1, None]}
        self.assertEqual(JobResult.model_validate(data).model_dump(exclude_unset=True), data)

    def test_retained_cli_entry_points_have_safe_help(self):
        for name in (
            "stage1",
            "stage2",
            "generate_playwright",
            "process_results",
            "publish_outputs",
            "worker",
            "migrate_data",
            "migrate_runner",
        ):
            with self.subTest(module=name):
                result = subprocess.run(
                    [sys.executable, "-m", "backend." + name, "--help"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
