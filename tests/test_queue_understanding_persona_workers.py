import os
import tempfile
import unittest
from pathlib import Path

from queue_system.queue import JobQueue
from queue_system.worker import ContextualAnalystWorker, EditorReviewWorker, ExplainerWriterWorker


class UnderstandingPersonaWorkerTests(unittest.TestCase):
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
        payload = {"profile_id": "test-profile", **payload}
        job_id = self.queue.create_job(job_type=job_type, domain="understanding", payload=payload)
        return self.queue.get_job(job_id)

    def test_explainer_writer_creates_content(self):
        job = self._make_job("mechanism_explainer", {"mechanism_type": "trust_structure"})
        worker = ExplainerWriterWorker(self.queue, "agent", "explainer_writer", ["mechanism_explainer"], poll_interval=0)
        result = worker.execute(job)
        content_path = Path(result["content_path"])
        self.assertTrue(content_path.exists())
        review = self.queue.get_job(result["review_job_id"])
        self.assertEqual(review["parent_job_id"], job["id"])
        self.assertEqual(review["payload"]["profile_id"], "test-profile")
        self.assertEqual(review["payload"]["db_path"], str(self.queue.db_path))

    def test_contextual_analyst_creates_content(self):
        job = self._make_job("analytical_article", {"title": "Test Analysis", "lens": "financial"})
        worker = ContextualAnalystWorker(self.queue, "agent", "contextual_analyst", ["analytical_article"], poll_interval=0)
        result = worker.execute(job)
        content_path = Path(result["content_path"])
        self.assertTrue(content_path.exists())
        review = self.queue.get_job(result["review_job_id"])
        self.assertEqual(review["parent_job_id"], job["id"])
        self.assertEqual(review["payload"]["profile_id"], "test-profile")

    def test_editor_review(self):
        job = self._make_job("mechanism_explainer", {"mechanism_type": "compliance_gap"})
        writer = ExplainerWriterWorker(self.queue, "agent", "explainer_writer", ["mechanism_explainer"], poll_interval=0)
        result = writer.execute(job)
        content_path = result["content_path"]

        review_job = self._make_job("editor_review", {"content_path": content_path, "min_words": 1})
        reviewer = EditorReviewWorker(self.queue, "agent", "editor", ["editor_review"], poll_interval=0)
        review = reviewer.execute(review_job)
        report_path = Path(review["report_path"])
        self.assertTrue(report_path.exists())
        self.assertIn("decision", review["review"])


if __name__ == "__main__":
    unittest.main()
