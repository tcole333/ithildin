import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import (
    DocumentMineWorker,
    EntityTracerWorker,
    PatternSpotterWorker,
    SurveyorWorker,
    SynthesistWorker,
)


class PersonaWorkerTests(unittest.TestCase):
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

    def test_surveyor_dry_run(self):
        job = self._make_job("source_scan", {"query": "Epstein", "dry_run": True})
        worker = SurveyorWorker(self.queue, "agent", "surveyor", ["source_scan"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_document_mine_dry_run(self):
        job = self._make_job("document_mine", {"query": "Epstein", "dry_run": True})
        worker = DocumentMineWorker(self.queue, "agent", "document_miner", ["document_mine"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_entity_tracer_dry_run(self):
        job = self._make_job("trace_entity", {"entity_name": "LSJE LLC", "dry_run": True})
        worker = EntityTracerWorker(self.queue, "agent", "entity_tracer", ["trace_entity"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_pattern_spotter_dry_run(self):
        job = self._make_job("pattern_trigger", {"dry_run": True})
        worker = PatternSpotterWorker(self.queue, "agent", "pattern_spotter", ["pattern_trigger"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_synthesist_dry_run(self):
        job = self._make_job("synthesis", {"query": "Epstein", "dry_run": True})
        worker = SynthesistWorker(self.queue, "agent", "synthesist", ["synthesis"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)


if __name__ == "__main__":
    unittest.main()
