import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import DeepInvestigationWorker


class OrchestrationTests(unittest.TestCase):
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

    def test_deep_investigate_spawns_children(self):
        job_id = self.queue.create_job(
            job_type="deep_investigate",
            domain="investigation",
            payload={"target_name": "Test Target", "dry_run": True, "profile_id": "test-profile"},
        )
        job = self.queue.get_job(job_id)

        worker = DeepInvestigationWorker(
            self.queue,
            agent_id="agent-orch",
            persona="investigation_orchestrator",
            capabilities=["deep_investigate"],
            poll_interval=0,
        )
        result = worker.execute(job)
        child_jobs = result["child_jobs"]
        synthesis_id = result["synthesis_job"]

        self.assertTrue(child_jobs)
        self.assertIsNotNone(synthesis_id)

        synthesis = self.queue.get_job(synthesis_id)
        self.assertEqual(synthesis["status"], "blocked")

        db = sqlite3.connect(self.db_path)
        try:
            row = db.execute(
                "SELECT COUNT(*) FROM job_dependencies WHERE job_id=?",
                (synthesis_id,),
            ).fetchone()
            dep_count = row[0]
        finally:
            db.close()

        self.assertEqual(dep_count, len(child_jobs))


if __name__ == "__main__":
    unittest.main()
