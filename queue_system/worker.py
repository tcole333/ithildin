#!/usr/bin/env python3
"""
Minimal agent worker loop for SQLite queue processing.
"""

from __future__ import annotations

import time
import traceback
from typing import Any, Dict, List, Optional

from queue_system.queue import JobQueue


class AgentWorker:
    def __init__(
        self,
        queue: JobQueue,
        agent_id: str,
        persona: str,
        capabilities: Optional[List[str]] = None,
        poll_interval: float = 5.0,
    ) -> None:
        self.queue = queue
        self.agent_id = agent_id
        self.persona = persona
        self.capabilities = capabilities or []
        self.poll_interval = poll_interval

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def run_forever(self) -> None:
        self.queue.register_agent(self.agent_id, self.persona, self.capabilities)
        while True:
            if self.queue.is_paused():
                time.sleep(self.poll_interval)
                continue

            job = self.queue.claim_next(self.agent_id, self.capabilities)
            if not job:
                time.sleep(self.poll_interval)
                continue

            job_id = job["id"]
            self.queue.update_agent_job(self.agent_id, job_id)
            self.queue.start_job(job_id, self.agent_id)

            try:
                output = self.execute(job)
                self.queue.complete_job(job_id, output)
                self.queue.update_agent_stats(self.agent_id, completed=True)
            except Exception as exc:
                self.queue.fail_job(job_id, str(exc), traceback.format_exc())
                self.queue.update_agent_stats(self.agent_id, completed=False)
            finally:
                self.queue.update_agent_job(self.agent_id, None)


class EchoWorker(AgentWorker):
    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "echo": job.get("payload", {}),
            "job_id": job["id"],
            "persona": self.persona,
        }


WORKER_REGISTRY = {
    "echo": EchoWorker,
}
