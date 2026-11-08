import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import requests
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.core.errors import ControlError, translate
from backend.execution.worker import execute
from backend.integrations.azure_catalog import catalog
from backend.services.jobs import Jobs
from backend.storage.artifacts import fingerprint, snapshot
from backend.storage.store import Store


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.app = create_app(self.root)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.store = self.app.state.store

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temporary.cleanup()

    def test_single_operation_is_atomic(self):
        self.store.create(1, "GENERATE", {})
        with self.assertRaises(ControlError) as caught:
            self.store.create(2, "GENERATE", {})
        self.assertEqual(caught.exception.status, 409)

    def test_health_does_not_leak_credentials(self):
        with patch.dict(
            os.environ, {"AZURE_DEVOPS_PAT": "secret-pat", "OPENAI_API_KEY": "secret-openai"}
        ):
            response = self.client.get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("secret-pat", response.text)
            self.assertNotIn("secret-openai", response.text)

    def test_origin_and_host_protection(self):
        self.assertEqual(
            self.client.post(
                "/api/stories/1/generate", headers={"Origin": "https://evil.test"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get("/api/health", headers={"Host": "evil.test"}).status_code, 403
        )

    def test_docker_proxy_origin_and_host(self):
        for origin in ("http://localhost:8080", "http://127.0.0.1:8080"):
            with patch.object(
                self.app.state.jobs, "start", return_value={"job_id": "docker", "status": "QUEUED"}
            ):
                response = self.client.post(
                    "/api/stories/42/generate",
                    headers={"Origin": origin, "Host": origin.split("://")[1]},
                )
                self.assertEqual(response.status_code, 202)
        self.assertEqual(
            self.client.post(
                "/api/stories/1/generate",
                headers={"Origin": "http://evil.test:8080", "Host": "localhost:8080"},
            ).status_code,
            403,
        )

    def test_catalog_filter_sort_and_page(self):
        rows = [
            {
                "id": i,
                "title": f"Story {i}",
                "state": "Custom",
                "assigned_to": "",
                "changed_at": "2026-01-01",
            }
            for i in range(1, 26)
        ]
        with patch(
            "backend.integrations.azure_catalog.catalog",
            return_value={"items": rows, "states": ["Custom"]},
        ):
            response = self.client.get("/api/stories?page=2&sort=id").json()
            self.assertEqual(response["total"], 25)
            self.assertEqual(response["items"][0]["id"], 5)
            self.assertEqual(
                self.client.get("/api/stories?search=%2321").json()["items"][0]["id"], 21
            )
            self.assertEqual(self.client.get("/api/stories?state=Absent").json()["total"], 0)

    def test_azure_batches_never_exceed_200(self):
        session = MagicMock()
        session.__enter__.return_value = session
        responses = []
        for data in (
            {"workItems": [{"id": i} for i in range(401)]},
            {"value": []},
            {"value": []},
            {"value": []},
        ):
            response = MagicMock()
            response.json.return_value = data
            responses.append(response)
        session.post.side_effect = responses
        with patch(
            "backend.integrations.azure_catalog.client",
            return_value=(session, "https://example.test"),
        ):
            catalog()
        sizes = [len(call.kwargs["json"]["ids"]) for call in session.post.call_args_list[1:]]
        self.assertEqual(sizes, [200, 200, 1])

    def test_azure_authorization_has_distinct_message(self):
        response = requests.Response()
        response.status_code = 403
        with patch(
            "backend.integrations.azure_catalog.catalog",
            side_effect=requests.HTTPError(response=response),
        ):
            result = self.client.get("/api/stories")
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json()["error"]["code"], "AZURE_ACCESS")

    def test_missing_story(self):
        from backend.integrations.azure import AzureStoryError

        with patch(
            "backend.integrations.azure_catalog.story",
            side_effect=AzureStoryError("Work item #1 was not found (HTTP 404)"),
        ):
            self.assertEqual(self.client.get("/api/stories/1").status_code, 404)

    def test_model_errors_are_not_mislabeled_as_azure_errors(self):
        model_error = type("AuthenticationError", (Exception,), {"__module__": "openai"})(
            "HTTP 401"
        )
        self.assertEqual(translate(model_error).code, "LLM_ERROR")

    def test_edit_forwards_exact_hash_and_batch(self):
        from backend.tests.fixtures import review

        expected = review()
        expected["review_hash"] = "new"
        with patch(
            "backend.services.stage1.save_reviewed_scenarios", return_value=expected
        ) as save:
            response = self.client.put(
                "/api/stories/1/review",
                json={"draft": {"story_id": 1, "scenarios": []}, "review_hash": "old"},
            )
        self.assertEqual(response.status_code, 200)
        save.assert_called_once_with(1, {"story_id": 1, "scenarios": []}, expected_hash="old")

    def test_invalid_review_and_conflict(self):
        self.assertEqual(
            self.client.put("/api/stories/1/review", json={"draft": {}}).status_code, 422
        )
        with patch(
            "backend.services.stage1.save_reviewed_scenarios",
            side_effect=ValueError("Draft changed since you opened it; reload before saving"),
        ):
            response = self.client.put(
                "/api/stories/1/review", json={"draft": {}, "review_hash": "old"}
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "STALE_REVIEW")

    def test_approval_requires_current_revision_and_hash(self):
        with (
            patch(
                "backend.services.stage1.get_review",
                return_value={"revision": 2, "review_hash": "current"},
            ),
            patch.object(self.app.state.jobs, "start") as start,
        ):
            self.assertEqual(
                self.client.post(
                    "/api/stories/1/approve-and-run", json={"revision": 1, "review_hash": "current"}
                ).status_code,
                409,
            )
            self.assertEqual(
                self.client.post(
                    "/api/stories/1/approve-and-run", json={"revision": 2, "review_hash": "old"}
                ).status_code,
                409,
            )
            start.assert_not_called()

    def test_generation_returns_202_and_job_id(self):
        with patch.object(
            self.app.state.jobs, "start", return_value={"job_id": "test", "status": "QUEUED"}
        ) as start:
            response = self.client.post("/api/stories/42/generate")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["job_id"], "test")
        start.assert_called_once_with(42, "GENERATE", {})

    def test_process_reconciliation(self):
        job = self.store.create(1, "GENERATE", {})
        self.store.update(
            job["id"], pid=os.getpid(), process_started=psutil.Process().create_time()
        )
        process = MagicMock()
        process.is_running.return_value = True
        process.status.return_value = psutil.STATUS_RUNNING
        process.cmdline.return_value = ["python", "-m", "backend.worker", job["id"]]
        with patch("backend.storage.store.psutil.Process", return_value=process):
            self.store.reconcile()
            self.assertEqual(self.store.get(job["id"])["status"], "QUEUED")
            process.cmdline.return_value = ["python", "-m", "backend.worker", "another-job"]
            self.store.reconcile()
        self.assertEqual(self.store.get(job["id"])["status"], "INTERRUPTED")

    def test_clock_adjustment_does_not_interrupt_live_worker(self):
        job = self.store.create(1, "EXECUTE", {})
        self.store.update(job["id"], status="RUNNING", pid=12345, process_started=1000.0)
        process = MagicMock()
        process.is_running.return_value = True
        process.status.return_value = psutil.STATUS_RUNNING
        process.create_time.return_value = 4600.0  # VM epoch clock moved one hour.
        process.cmdline.return_value = ["/opt/venv/bin/python", "-m", "backend.worker", job["id"]]
        with patch("backend.storage.store.psutil.Process", return_value=process):
            self.store.reconcile()
        self.assertEqual(self.store.get(job["id"])["status"], "RUNNING")
        self.assertIsNone(self.store.get(job["id"])["error"])

    def test_process_inspection_denied_is_not_interruption(self):
        job = self.store.create(1, "EXECUTE", {})
        self.store.update(job["id"], status="RUNNING", pid=12345, process_started=1000.0)
        with patch("backend.storage.store.psutil.Process", side_effect=psutil.AccessDenied(12345)):
            self.store.reconcile()
        self.assertEqual(self.store.get(job["id"])["status"], "RUNNING")

    def test_reconcile_cannot_overwrite_worker_completion(self):
        job = self.store.create(1, "EXECUTE", {})
        self.store.update(job["id"], status="RUNNING", pid=12345, process_started=1000.0)
        observed = self.store.get(job["id"])

        def completed_before_process_check(pid):
            self.store.update(job["id"], status="SUCCEEDED", result={"status": "PUBLISHED"})
            raise psutil.NoSuchProcess(pid)

        with (
            patch.object(self.store, "list", return_value=[observed]),
            patch(
                "backend.storage.store.psutil.Process", side_effect=completed_before_process_check
            ),
        ):
            self.store.reconcile()
        saved = self.store.get(job["id"])
        self.assertEqual(saved["status"], "SUCCEEDED")
        self.assertEqual(saved["result"], {"status": "PUBLISHED"})
        self.assertIsNone(saved["error"])

    def test_stale_check_cannot_overwrite_worker_registration(self):
        job = self.store.create(1, "EXECUTE", {})
        self.store.update(job["id"], status="RUNNING", pid=12345, process_started=1000.0)
        self.assertFalse(self.store.interrupt_if_active(job, "Stale queued observation"))
        self.assertEqual(self.store.get(job["id"])["status"], "RUNNING")

    def test_orphan_queued_job_releases_reservation(self):
        job = self.store.create(1, "GENERATE", {})
        with self.store.connect() as db:
            db.execute(
                "UPDATE jobs SET created_at=? WHERE id=?",
                ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), job["id"]),
            )
        self.store.reconcile()
        self.assertEqual(self.store.get(job["id"])["status"], "INTERRUPTED")

    def test_snapshots_ignore_old_reports_and_are_immutable(self):
        job = self.store.create(1, "EXECUTE", {"revision": 1, "review_hash": "x"})
        old = self.root / "execution.summary.json"
        old.write_text('{"passed":9}', encoding="utf-8")
        new = self.root / "tc-001.spec.js"
        new.write_text("old", encoding="utf-8")
        before = {str(path): fingerprint(path) for path in [old, new]}
        new.write_text("new", encoding="utf-8")
        with patch("backend.storage.artifacts.sources", return_value=[old, new]):
            artifacts, partial = snapshot(self.store, job, before)
        self.assertEqual([a["name"] for a in artifacts], ["tc-001.spec.js"])
        self.assertEqual(partial, {})
        new.write_text("changed again", encoding="utf-8")
        stored = self.root / job["id"] / "artifacts" / artifacts[0]["stored_name"]
        self.assertEqual(stored.read_text(), "new")

    def test_failed_tests_can_have_successful_workflow(self):
        job = self.store.create(1, "EXECUTE", {"revision": 1, "review_hash": "x"})
        result = {
            "revision": 1,
            "status": "PUBLISHED",
            "execution": {"failed": 1, "passed": 0, "total": 1},
        }
        with (
            patch("backend.storage.artifacts.sources", return_value=[]),
            patch("backend.services.stage1.get_review", return_value={"revision": 1}),
            patch(
                "backend.services.stage2.approve_execute_publish", return_value=result
            ) as approve,
        ):
            execute(self.store, job["id"])
        saved = self.store.get(job["id"])
        self.assertEqual(saved["status"], "SUCCEEDED")
        self.assertEqual(saved["result"]["execution"]["failed"], 1)
        approve.assert_called_once_with(1, expected_hash="x")

    def test_partial_publication_is_not_success(self):
        job = self.store.create(1, "EXECUTE", {"revision": 1, "review_hash": "x"})
        manifest = self.root / "devops.publish.json"

        def fail(*args, **kwargs):
            manifest.write_text(json.dumps({"test_cases": {"TC-001": 8}}), encoding="utf-8")
            raise RuntimeError("Azure unavailable")

        with (
            patch(
                "backend.storage.artifacts.sources",
                side_effect=lambda _: [manifest] if manifest.exists() else [],
            ),
            patch("backend.services.stage1.get_review", return_value={"revision": 1}),
            patch("backend.services.stage2.approve_execute_publish", side_effect=fail),
        ):
            execute(self.store, job["id"])
        saved = self.store.get(job["id"])
        self.assertEqual(saved["status"], "FAILED")
        self.assertEqual(saved["result"]["publication"], "PARTIAL")
        self.assertEqual(len(saved["artifacts"]), 1)

    def test_artifact_ids_do_not_allow_arbitrary_paths(self):
        job = self.store.create(1, "GENERATE", {})
        self.assertEqual(
            self.client.get(f"/api/jobs/{job['id']}/artifacts/unknown").status_code, 404
        )
        self.assertEqual(self.client.get("/api/jobs/unknown").status_code, 404)

    def test_artifact_download_and_durable_history(self):
        job = self.store.create(1, "GENERATE", {})
        directory = self.root / job["id"] / "artifacts"
        directory.mkdir()
        (directory / "a1.json").write_text('{"passed":1}', encoding="utf-8")
        self.store.update(
            job["id"],
            status="SUCCEEDED",
            artifacts=[{"id": "a1", "name": "results.json", "size": 12, "stored_name": "a1.json"}],
        )
        response = self.client.get(f"/api/jobs/{job['id']}/artifacts/a1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"passed": 1})
        self.assertIn("results.json", response.headers["content-disposition"])
        self.assertEqual(Store(self.root).get(job["id"])["status"], "SUCCEEDED")

    def test_generation_worker_uses_existing_backend(self):
        job = self.store.create(42, "GENERATE", {})
        with (
            patch("backend.storage.artifacts.sources", return_value=[]),
            patch(
                "backend.services.stage1.prepare_scenarios",
                return_value={"revision": 7, "status": "PENDING_REVIEW"},
            ) as prepare,
        ):
            execute(self.store, job["id"])
        prepare.assert_called_once_with(42)
        saved = self.store.get(job["id"])
        self.assertEqual(saved["status"], "SUCCEEDED")
        self.assertEqual(saved["revision"], 7)

    def test_real_worker_process_uses_new_module_and_store(self):
        # Missing local review fails before any network/API operation. This checks
        # the actual python -m backend.execution.worker launch and CONTROL_DATA_DIR handoff.
        threads = []
        thread_class = threading.Thread

        def capture_thread(*args, **kwargs):
            thread = thread_class(*args, **kwargs)
            threads.append(thread)
            return thread

        with (
            patch("backend.services.jobs.threading.Thread", side_effect=capture_thread),
            patch("backend.services.jobs.STORY_DATA", self.root / "stories"),
            patch("backend.services.jobs.MIGRATION_LOCK", self.root / "migration.lock"),
        ):
            response = Jobs(self.store).start(
                2147483647, "EXECUTE", {"revision": 1, "review_hash": "missing-local-review"}
            )
        threads[0].join(timeout=30)
        self.assertFalse(threads[0].is_alive(), "Worker process did not complete")
        saved = self.store.get(response["job_id"])
        self.assertEqual(saved["status"], "FAILED")
        self.assertEqual(saved["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
