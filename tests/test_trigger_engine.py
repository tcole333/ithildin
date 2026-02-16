import json
import os
import tempfile
import unittest

from queue_system.queue import JobQueue
from queue_system.triggers import TriggerEngine


class TriggerEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test.db")
        self.config_path = os.path.join(self.tmpdir.name, "trigger_config.json")
        self.queue = JobQueue(db_path=self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_config(self, config):
        with open(self.config_path, "w") as f:
            json.dump(config, f)

    def test_scheduled_trigger_creates_job(self):
        config = {
            "scheduled": [
                {
                    "name": "scheduled_echo",
                    "enabled": True,
                    "interval_minutes": 60,
                    "job_type": "echo",
                    "domain": "system",
                    "payload": {"message": "hello"},
                }
            ],
            "thresholds": [],
        }
        self._write_config(config)
        engine = TriggerEngine(
            self.queue,
            db_path=self.db_path,
            config_path=self.config_path,
        )
        results = engine.run_scheduled()
        self.assertEqual(len(results), 1)
        jobs = self.queue.list_jobs(limit=10)
        self.assertEqual(len(jobs), 1)

        results = engine.run_scheduled()
        self.assertEqual(len(results), 0)

    def test_threshold_trigger_queue_pending(self):
        self.queue.create_job(job_type="echo", domain="system")
        config = {
            "scheduled": [],
            "thresholds": [
                {
                    "name": "pending_queue",
                    "enabled": True,
                    "metric": "queue_pending",
                    "threshold": 1,
                    "job_type": "echo",
                    "domain": "system",
                    "payload": {"message": "threshold hit"},
                }
            ],
        }
        self._write_config(config)
        engine = TriggerEngine(
            self.queue,
            db_path=self.db_path,
            config_path=self.config_path,
        )
        results = engine.run_thresholds()
        self.assertEqual(len(results), 1)
        jobs = self.queue.list_jobs(limit=10)
        self.assertEqual(len(jobs), 2)


if __name__ == "__main__":
    unittest.main()
