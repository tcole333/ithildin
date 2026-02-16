import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import ContentBuildWorker, DossierWriterWorker, VisualExportWorker


class ContentPipelineWorkerTests(unittest.TestCase):
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
        job_id = self.queue.create_job(job_type=job_type, domain="understanding", payload=payload)
        return self.queue.get_job(job_id)

    def _assert_report(self, result):
        report_path = Path(result["report_path"])
        self.assertTrue(report_path.exists())

    def test_dossier_writer_dry_run(self):
        job = self._make_job("wiki_dossier_update", {"target_name": "Test", "dry_run": True})
        worker = DossierWriterWorker(self.queue, "agent", "dossier_writer", ["wiki_dossier_update"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_visual_export_dry_run(self):
        job = self._make_job("visual_export", {"export_type": "network_graph", "dry_run": True})
        worker = VisualExportWorker(self.queue, "agent", "visual_exporter", ["visual_export"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)

    def test_content_build_dry_run(self):
        job = self._make_job("content_build", {"dry_run": True})
        worker = ContentBuildWorker(self.queue, "agent", "content_pipeline", ["content_build"], poll_interval=0)
        result = worker.execute(job)
        self._assert_report(result)


if __name__ == "__main__":
    unittest.main()
