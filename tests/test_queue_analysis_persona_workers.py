import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import NetworkAnalystWorker, TimelineAnalystWorker, SystemicAnalystWorker


class AnalysisPersonaWorkerTests(unittest.TestCase):
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
        job_id = self.queue.create_job(job_type=job_type, domain="analysis", payload=payload)
        return self.queue.get_job(job_id)

    def _assert_report(self, result):
        report_path = Path(result["report_path"])
        self.assertTrue(report_path.exists())

    def test_network_analyst_dry_run(self):
        job = self._make_job("network_analysis", {"dry_run": True})
        worker = NetworkAnalystWorker(self.queue, "agent", "network_analyst", ["network_analysis"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_timeline_analyst_dry_run(self):
        job = self._make_job("timeline_correlation", {"dry_run": True})
        worker = TimelineAnalystWorker(self.queue, "agent", "timeline_analyst", ["timeline_correlation"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_systemic_analyst_dry_run(self):
        job = self._make_job("systemic_analysis", {"dry_run": True})
        worker = SystemicAnalystWorker(self.queue, "agent", "systemic_analyst", ["systemic_analysis"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)


if __name__ == "__main__":
    unittest.main()
