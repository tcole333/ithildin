import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from queue_system.queue import JobQueue  # noqa: E402 — bootstrap direct-script imports
from scripts import queue_dispatcher as dispatcher  # noqa: E402


class QueueDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.queue = JobQueue(db_path=self.db_path)
        self.orig_db_path = dispatcher.DB_PATH
        dispatcher.DB_PATH = self.db_path

    def tearDown(self):
        dispatcher.DB_PATH = self.orig_db_path
        self.tmpdir.cleanup()

    def test_get_pending_by_type_counts_pending(self):
        job_a = self.queue.create_job(job_type="echo", domain="system")
        self.queue.create_job(job_type="echo", domain="system")
        self.queue.create_job(job_type="source_scan", domain="discovery", payload={"profile_id": "test-profile"})
        self.queue.complete_job(job_a, {"ok": True})

        db = dispatcher._connect()
        try:
            pending = dispatcher.get_pending_by_type(db)
        finally:
            db.close()

        self.assertEqual(pending.get("echo"), 1)
        self.assertEqual(pending.get("source_scan"), 1)

    def test_get_active_agents_respects_heartbeat(self):
        self.queue.register_agent("agent-1", "surveyor", ["source_scan"])
        self.queue.register_agent("agent-2", "surveyor", ["source_scan"])

        db = self.queue._connect()
        try:
            db.execute(
                "UPDATE agent_instances SET last_heartbeat = datetime('now', '-300 seconds') WHERE id=?",
                ("agent-2",),
            )
            db.commit()
        finally:
            db.close()

        db = dispatcher._connect()
        try:
            active = dispatcher.get_active_agents(db, heartbeat_seconds=60)
        finally:
            db.close()

        self.assertEqual(active.get("surveyor"), 1)

    def test_compute_scale_actions(self):
        config = {
            "agents": [
                {
                    "persona": "surveyor",
                    "job_types": ["source_scan"],
                    "max_workers": 2,
                    "min_workers": 0,
                    "enabled": True,
                },
                {
                    "persona": "editor",
                    "job_types": ["editor_review"],
                    "max_workers": 1,
                    "min_workers": 1,
                    "enabled": True,
                },
                {
                    "persona": "echo",
                    "job_types": ["echo"],
                    "max_workers": 1,
                    "min_workers": 0,
                    "enabled": False,
                },
            ]
        }
        pending = {"source_scan": 3, "editor_review": 0}
        active = {"surveyor": 1}

        actions = dispatcher.compute_scale_actions(config, pending, active)

        self.assertEqual(
            actions,
            [
                {"persona": "surveyor", "spawn": 1, "pending": 3},
                {"persona": "editor", "spawn": 1, "pending": 0},
            ],
        )

    def test_spawn_workers_dry_run(self):
        actions = [{"persona": "surveyor", "spawn": 1, "pending": 2}]
        results = dispatcher.spawn_workers(actions, config={}, dry_run=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "dry_run")
        self.assertIn("agent_worker.py", results[0]["cmd"])
        self.assertIn("--persona surveyor", results[0]["cmd"])

    def test_is_paused_reflects_system_state(self):
        self.queue.set_paused(True, updated_by="test")
        db = dispatcher._connect()
        try:
            self.assertTrue(dispatcher.is_paused(db))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
