import os
import tempfile
import unittest

from queue_system.queue import JobQueue


class QueueSystemTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.queue = JobQueue(db_path=self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_job_lifecycle(self):
        job_id = self.queue.create_job(
            job_type="echo",
            domain="system",
            payload={"message": "hi"},
            priority=7,
            created_by="tester",
        )
        job = self.queue.get_job(job_id)
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["payload"]["message"], "hi")

        claimed = self.queue.claim_next("agent-1", capabilities=["echo"])
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job_id)

        self.queue.start_job(job_id, "agent-1")
        self.queue.complete_job(job_id, {"ok": True})
        completed = self.queue.get_job(job_id)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["ok"], True)

    def test_pause_blocks_claim(self):
        self.queue.set_paused(True, updated_by="tester")
        job_id = self.queue.create_job(job_type="echo", domain="system")
        claimed = self.queue.claim_next("agent-2", capabilities=["echo"])
        self.assertIsNone(claimed)
        self.queue.set_paused(False, updated_by="tester")
        claimed = self.queue.claim_next("agent-2", capabilities=["echo"])
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job_id)

    def test_capability_filter(self):
        job_a = self.queue.create_job(job_type="echo", domain="system")
        job_b = self.queue.create_job(job_type="other", domain="system")
        claimed = self.queue.claim_next("agent-3", capabilities=["echo"])
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job_a)
        claimed_second = self.queue.claim_next("agent-3", capabilities=["echo"])
        self.assertIsNone(claimed_second)

    def test_fail_job(self):
        job_id = self.queue.create_job(job_type="echo", domain="system")
        self.queue.start_job(job_id, "agent-4")
        self.queue.fail_job(job_id, "boom", "trace")
        job = self.queue.get_job(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_message"], "boom")

    def test_agent_registration(self):
        self.queue.register_agent("agent-5", "echo", ["echo"])
        job_id = self.queue.create_job(job_type="echo", domain="system")
        self.queue.update_agent_job("agent-5", job_id)
        self.queue.update_agent_stats("agent-5", completed=True)
        self.queue.update_agent_stats("agent-5", completed=False)


if __name__ == "__main__":
    unittest.main()
