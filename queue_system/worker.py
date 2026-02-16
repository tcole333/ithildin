#!/usr/bin/env python3
"""
Minimal agent worker loop for SQLite queue processing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from queue_system.queue import JobQueue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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

def _ensure_workdir(job_id: str) -> Path:
    base = Path(os.environ.get("OSINT_WORKDIR_BASE", "/tmp/osint-jobs"))
    workdir = base / job_id
    output_dir = workdir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return workdir


def _result_count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("results", "hits", "articles", "items", "records", "data"):
            if key in data and isinstance(data[key], list):
                return len(data[key])
    return 1 if data is not None else 0


def _run_tool(tool_path: Path, args: List[str], output_path: Path) -> Dict[str, Any]:
    cmd = [sys.executable, str(tool_path)] + args + ["--output", str(output_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    result = {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "output_path": str(output_path),
    }
    if proc.returncode == 0 and output_path.exists():
        try:
            data = json.loads(output_path.read_text())
            result["count"] = _result_count(data)
        except json.JSONDecodeError:
            result["count"] = None
    return result


class LeadTriageWorker(AgentWorker):
    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        from tools import lead_tracker

        payload = job.get("payload", {})
        batch_size = int(payload.get("batch_size", 20))
        dry_run = bool(payload.get("dry_run", False))
        triaged_by = payload.get("triaged_by", "agent:lead_triage")

        db = lead_tracker.get_db()
        rows = db.execute(
            """
            SELECT * FROM leads
            WHERE status = 'pending_triage'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()
        leads = [dict(r) for r in rows]
        db.close()

        results = {
            "total": len(leads),
            "opened": [],
            "duplicates": [],
            "dry_run": dry_run,
        }

        now = datetime.utcnow().isoformat()
        for lead in leads:
            lead_id = lead["id"]
            target_name = lead.get("target_name") or ""
            title = lead.get("title") or ""

            dup_id = None
            db = lead_tracker.get_db()
            try:
                if target_name:
                    dup = db.execute(
                        """
                        SELECT id FROM leads
                        WHERE LOWER(target_name) = LOWER(?)
                          AND id != ?
                          AND status != 'pending_triage'
                        ORDER BY created_at ASC
                        LIMIT 1
                        """,
                        (target_name, lead_id),
                    ).fetchone()
                    if dup:
                        dup_id = dup["id"]
                if not dup_id and title:
                    dup = db.execute(
                        """
                        SELECT id FROM leads
                        WHERE LOWER(title) = LOWER(?)
                          AND id != ?
                          AND status != 'pending_triage'
                        ORDER BY created_at ASC
                        LIMIT 1
                        """,
                        (title, lead_id),
                    ).fetchone()
                    if dup:
                        dup_id = dup["id"]
            finally:
                db.close()

            if dup_id:
                results["duplicates"].append({"lead_id": lead_id, "duplicate_of": dup_id})
                if not dry_run:
                    lead_tracker.dead_end_lead(lead_id, f"Duplicate of lead #{dup_id}")
                    lead_tracker.add_note(lead_id, f"Triage: duplicate of lead #{dup_id}")
                    db = lead_tracker.get_db()
                    try:
                        db.execute(
                            """
                            INSERT OR IGNORE INTO lead_relations
                            (lead_id, related_lead_id, relation_type)
                            VALUES (?, ?, 'duplicate')
                            """,
                            (lead_id, dup_id),
                        )
                        db.execute(
                            """
                            UPDATE leads
                            SET triaged_by = ?, triaged_at = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            (triaged_by, now, now, lead_id),
                        )
                        db.commit()
                    finally:
                        db.close()
                continue

            results["opened"].append(lead_id)
            if not dry_run:
                db = lead_tracker.get_db()
                try:
                    db.execute(
                        """
                        UPDATE leads
                        SET status = 'open',
                            triaged_by = ?,
                            triaged_at = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (triaged_by, now, now, lead_id),
                    )
                    db.execute(
                        "INSERT INTO lead_notes (lead_id, note) VALUES (?, ?)",
                        (lead_id, "Triage: promoted to open"),
                    )
                    db.commit()
                finally:
                    db.close()

        return results


class DeepPersonWorker(AgentWorker):
    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        from tools import lead_tracker

        payload = job.get("payload", {})
        target = payload.get("target_name") or payload.get("query")
        if not target:
            raise ValueError("payload.target_name is required")

        lead_id = payload.get("lead_id")
        limit = int(payload.get("limit", 20))
        if "sources" in payload:
            sources = payload.get("sources") or []
        else:
            sources = [
                "doj",
                "lmsband",
                "unified_docs",
                "unified_emails",
                "unified_entities",
                "findings",
            ]

        if lead_id:
            lead_tracker.claim_lead(lead_id)
            lead_tracker.add_note(lead_id, f"Deep investigation started for '{target}'")

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"

        tool_results: Dict[str, Any] = {}

        def add_tool_result(name: str, result: Dict[str, Any]) -> None:
            tool_results[name] = result

        tool_root = Path(__file__).resolve().parent.parent / "tools"

        if "doj" in sources:
            out = output_dir / "doj-search.json"
            result = _run_tool(
                tool_root / "query_doj.py",
                ["search", target, "--limit", str(limit), "--context", "120"],
                out,
            )
            add_tool_result("doj", result)

        if "lmsband" in sources:
            out = output_dir / "lmsband-search.json"
            result = _run_tool(
                tool_root / "query_lmsband.py",
                ["search", target, "--limit", str(limit)],
                out,
            )
            add_tool_result("lmsband", result)

        if "unified_docs" in sources:
            out = output_dir / "unified-docs.json"
            result = _run_tool(
                tool_root / "query_unified.py",
                ["docs", target, "--limit", str(limit)],
                out,
            )
            add_tool_result("unified_docs", result)

        if "unified_emails" in sources:
            out = output_dir / "unified-emails.json"
            result = _run_tool(
                tool_root / "query_unified.py",
                ["emails", target, "--limit", str(limit)],
                out,
            )
            add_tool_result("unified_emails", result)

        if "unified_entities" in sources:
            out = output_dir / "unified-entities.json"
            result = _run_tool(
                tool_root / "query_unified.py",
                ["entities", target, "--limit", str(limit)],
                out,
            )
            add_tool_result("unified_entities", result)

        if "findings" in sources:
            out = output_dir / "findings-search.json"
            result = _run_tool(
                tool_root / "findings_tracker.py",
                ["search", target],
                out,
            )
            add_tool_result("findings", result)

        report_lines = [
            f"# Investigation Report: {target}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")

        report_path.write_text("\n".join(report_lines))

        summary = f"Deep investigation completed for '{target}'."
        if lead_id:
            lead_tracker.complete_lead(lead_id, summary)
            lead_tracker.add_note(lead_id, f"Report: {report_path}")

        return {
            "target": target,
            "report_path": str(report_path),
            "tools": tool_results,
        }


WORKER_REGISTRY = {
    "echo": EchoWorker,
    "lead_triage": LeadTriageWorker,
    "deep_person": DeepPersonWorker,
}
