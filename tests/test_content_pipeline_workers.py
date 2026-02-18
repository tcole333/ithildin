import json
import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import (
    ContentBuildWorker,
    DossierFreshnessWorker,
    DossierWriterWorker,
    VisualExportWorker,
)


class ContentPipelineWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.queue = JobQueue(db_path=self.db_path)
        self.workdir = Path(self.tmpdir.name) / "jobs"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.content_root = Path(self.tmpdir.name) / "content"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self._prev_workdir = os.environ.get("OSINT_WORKDIR_BASE")
        self._prev_content = os.environ.get("ITHILDIN_CONTENT_ROOT")
        os.environ["OSINT_WORKDIR_BASE"] = str(self.workdir)
        os.environ["ITHILDIN_CONTENT_ROOT"] = str(self.content_root)

    def tearDown(self):
        if self._prev_workdir is None:
            os.environ.pop("OSINT_WORKDIR_BASE", None)
        else:
            os.environ["OSINT_WORKDIR_BASE"] = self._prev_workdir
        if self._prev_content is None:
            os.environ.pop("ITHILDIN_CONTENT_ROOT", None)
        else:
            os.environ["ITHILDIN_CONTENT_ROOT"] = self._prev_content
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

    def test_dossier_freshness_audit_dry_run(self):
        import tools.lead_tracker as lead_tracker

        orig_db = lead_tracker.DB_PATH
        lead_tracker.DB_PATH = Path(self.db_path)
        try:
            lead_tracker.get_db().close()
            db = lead_tracker.get_db()
            db.execute(
                """
                INSERT INTO findings (target_name, finding_type, summary, confidence, claim_type, verification_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Alpha", "financial", "Test finding", "medium", "inference", "unverified"),
            )
            db.commit()
            db.close()
        finally:
            lead_tracker.DB_PATH = orig_db

        dossiers_dir = self.content_root / "dossiers"
        dossiers_dir.mkdir(parents=True, exist_ok=True)
        dossier_path = dossiers_dir / "alpha.json"
        dossier_path.write_text(
            json.dumps(
                {
                    "name": "Alpha",
                    "slug": "alpha",
                    "aliases": [],
                    "generated_at": "2000-01-01T00:00:00",
                    "last_updated": "2000-01-01T00:00:00",
                    "stats": {
                        "total_findings": 1,
                        "total_connections": 0,
                        "total_entities": 0,
                    },
                    "findings": [{"evidence": ["ref"]}],
                    "connections": [],
                    "entities": [],
                    "timeline": [],
                },
                indent=2,
            )
        )

        job = self._make_job("dossier_freshness_audit", {"min_findings": 1, "dry_run": True})
        worker = DossierFreshnessWorker(
            self.queue,
            "agent",
            "dossier_freshness_audit",
            ["dossier_freshness_audit"],
            poll_interval=0,
        )
        result = worker.execute(job)
        self._assert_report(result)
        self.assertIn("Alpha", result["updates_needed"])


if __name__ == "__main__":
    unittest.main()
