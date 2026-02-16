import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import DeepPersonWorker, LeadTriageWorker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.queue = JobQueue(db_path=self.db_path)

        import tools.lead_tracker as lead_tracker
        self.lead_tracker = lead_tracker
        self.orig_db_path = lead_tracker.DB_PATH
        lead_tracker.DB_PATH = self.db_path
        lead_tracker.get_db().close()

        self.orig_workdir_base = os.environ.get("OSINT_WORKDIR_BASE")
        os.environ["OSINT_WORKDIR_BASE"] = self.tmpdir.name

    def tearDown(self):
        self.lead_tracker.DB_PATH = self.orig_db_path
        if self.orig_workdir_base is None:
            os.environ.pop("OSINT_WORKDIR_BASE", None)
        else:
            os.environ["OSINT_WORKDIR_BASE"] = self.orig_workdir_base
        self.tmpdir.cleanup()

    def _insert_lead(self, title, status, target_name=None):
        db = self.lead_tracker.get_db()
        cursor = db.execute(
            "INSERT INTO leads (title, status, target_name) VALUES (?, ?, ?)",
            (title, status, target_name),
        )
        db.commit()
        lead_id = cursor.lastrowid
        db.close()
        return lead_id

    def test_lead_triage_worker(self):
        existing = self._insert_lead("Existing Lead", "open", "Alpha")
        dup = self._insert_lead("Dup Lead", "pending_triage", "Alpha")
        pending = self._insert_lead("New Lead", "pending_triage", "Bravo")

        job_id = self.queue.create_job(
            job_type="lead_triage",
            domain="discovery",
            payload={"batch_size": 10, "triaged_by": "test:triage"},
        )
        job = self.queue.claim_next("triage-1", capabilities=["lead_triage"])
        worker = LeadTriageWorker(self.queue, "triage-1", "lead_triage", ["lead_triage"])
        result = worker.execute(job)

        db = self.lead_tracker.get_db()
        dup_row = db.execute("SELECT status FROM leads WHERE id=?", (dup,)).fetchone()
        pending_row = db.execute("SELECT status, triaged_by FROM leads WHERE id=?", (pending,)).fetchone()
        db.close()

        self.assertEqual(dup_row["status"], "dead_end")
        self.assertEqual(pending_row["status"], "open")
        self.assertEqual(pending_row["triaged_by"], "test:triage")
        self.assertIn(pending, result["opened"])
        self.assertTrue(any(r["lead_id"] == dup for r in result["duplicates"]))
        self.assertEqual(existing, existing)

    def test_deep_person_worker_minimal(self):
        lead_id = self._insert_lead("Investigation Lead", "open", "Charlie")
        job_id = self.queue.create_job(
            job_type="deep_person",
            domain="investigation",
            payload={"target_name": "Charlie", "lead_id": lead_id, "sources": []},
        )
        job = self.queue.claim_next("deep-1", capabilities=["deep_person"])
        worker = DeepPersonWorker(self.queue, "deep-1", "deep_person", ["deep_person"])
        output = worker.execute(job)

        db = self.lead_tracker.get_db()
        row = db.execute("SELECT status, findings FROM leads WHERE id=?", (lead_id,)).fetchone()
        db.close()

        self.assertEqual(row["status"], "completed")
        self.assertIn("Deep investigation completed", row["findings"])
        self.assertTrue(Path(output["report_path"]).exists())


if __name__ == "__main__":
    unittest.main()
