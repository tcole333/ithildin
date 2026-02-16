import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import (
    DedupeReviewWorker,
    FindingVerificationWorker,
    RegistryAdderWorker,
    SourceIntegratorWorker,
    ToolBuilderWorker,
)


class ValidationInfraWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.queue = JobQueue(db_path=self.db_path)
        self.workdir = Path(self.tmpdir.name) / "jobs"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._prev_workdir = os.environ.get("OSINT_WORKDIR_BASE")
        os.environ["OSINT_WORKDIR_BASE"] = str(self.workdir)

    def tearDown(self):
        if self._prev_workdir is None:
            os.environ.pop("OSINT_WORKDIR_BASE", None)
        else:
            os.environ["OSINT_WORKDIR_BASE"] = self._prev_workdir
        self.tmpdir.cleanup()

    def _make_job(self, job_type, payload):
        job_id = self.queue.create_job(job_type=job_type, domain="system", payload=payload)
        return self.queue.get_job(job_id)

    def _assert_report(self, result):
        report_path = Path(result["report_path"])
        self.assertTrue(report_path.exists())

    def test_dedupe_review_dry_run(self):
        job = self._make_job("dedupe_review", {"action": "scan", "dry_run": True})
        worker = DedupeReviewWorker(self.queue, "agent", "dedupe_review", ["dedupe_review"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_finding_verification_dry_run(self):
        job = self._make_job("verify_finding", {"finding_id": 1, "dry_run": True})
        worker = FindingVerificationWorker(self.queue, "agent", "verify_finding", ["verify_finding"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_tool_build_dry_run(self):
        job = self._make_job("tool_build", {"infra_id": 1, "dry_run": True})
        worker = ToolBuilderWorker(self.queue, "agent", "tool_build", ["tool_build"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_source_ingest_dry_run(self):
        job = self._make_job("source_ingest", {"script": "tools/ingest_dc.py", "dry_run": True})
        worker = SourceIntegratorWorker(self.queue, "agent", "source_ingest", ["source_ingest"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_registry_add_dry_run(self):
        job = self._make_job("registry_add", {"script": "tools/ingest_dc.py", "dry_run": True})
        worker = RegistryAdderWorker(self.queue, "agent", "registry_add", ["registry_add"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)


if __name__ == "__main__":
    unittest.main()
