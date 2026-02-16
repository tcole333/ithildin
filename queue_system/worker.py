#!/usr/bin/env python3
"""
Minimal agent worker loop for SQLite queue processing.
"""

from __future__ import annotations

import json
import os
import re
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
    JOB_TYPES: List[str] = []

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
            self.queue.heartbeat_agent(self.agent_id)
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
    JOB_TYPES = ["echo"]

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


def _content_root() -> Path:
    root = os.environ.get("ITHILDIN_CONTENT_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent / "site" / "content"


def _slugify(value: str) -> str:
    slug = value.lower().strip()
    slug = re.sub(r"[^a-z0-9\\s-]", "", slug)
    slug = re.sub(r"[\\s-]+", "-", slug)
    return slug.strip("-")


def _unique_content_path(content_dir: Path, slug: str, suffix: str, job_id: str) -> Path:
    path = content_dir / f"{slug}.{suffix}"
    if path.exists():
        path = content_dir / f"{slug}-{job_id[:8]}.{suffix}"
    return path


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


def _run_script(script_path: Path, args: List[str]) -> Dict[str, Any]:
    cmd = [sys.executable, str(script_path)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _run_infra_action(action: str, infra_id: int, args: List[str]) -> Dict[str, Any]:
    tool_root = Path(__file__).resolve().parent.parent / "tools"
    script = tool_root / "infra_tracker.py"
    return _run_script(script, [action, str(infra_id)] + args)


def _run_query_sources(
    query: str,
    sources: List[str],
    limit: int,
    output_dir: Path,
    context: int = 120,
    dry_run: bool = False,
) -> Dict[str, Any]:
    tool_results: Dict[str, Any] = {}
    if dry_run:
        return tool_results

    tool_root = Path(__file__).resolve().parent.parent / "tools"

    if "doj" in sources:
        out = output_dir / "doj-search.json"
        tool_results["doj"] = _run_tool(
            tool_root / "query_doj.py",
            ["search", query, "--limit", str(limit), "--context", str(context)],
            out,
        )

    if "lmsband" in sources:
        out = output_dir / "lmsband-search.json"
        tool_results["lmsband"] = _run_tool(
            tool_root / "query_lmsband.py",
            ["search", query, "--limit", str(limit)],
            out,
        )

    if "unified_docs" in sources:
        out = output_dir / "unified-docs.json"
        tool_results["unified_docs"] = _run_tool(
            tool_root / "query_unified.py",
            ["docs", query, "--limit", str(limit)],
            out,
        )

    if "unified_emails" in sources:
        out = output_dir / "unified-emails.json"
        tool_results["unified_emails"] = _run_tool(
            tool_root / "query_unified.py",
            ["emails", query, "--limit", str(limit)],
            out,
        )

    if "unified_entities" in sources:
        out = output_dir / "unified-entities.json"
        tool_results["unified_entities"] = _run_tool(
            tool_root / "query_unified.py",
            ["entities", query, "--limit", str(limit)],
            out,
        )

    if "gdelt" in sources:
        out = output_dir / "gdelt-articles.json"
        tool_results["gdelt"] = _run_tool(
            tool_root / "query_gdelt.py",
            ["articles", query, "--limit", str(limit)],
            out,
        )

    if "findings" in sources:
        out = output_dir / "findings-search.json"
        tool_results["findings"] = _run_tool(
            tool_root / "findings_tracker.py",
            ["search", query],
            out,
        )

    return tool_results


class LeadTriageWorker(AgentWorker):
    JOB_TYPES = ["lead_triage"]

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
    JOB_TYPES = ["deep_person"]

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


class SurveyorWorker(AgentWorker):
    JOB_TYPES = ["source_scan"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        query = payload.get("query")
        if not query:
            raise ValueError("payload.query is required")

        sources = payload.get("sources") or [
            "doj",
            "lmsband",
            "unified_docs",
            "unified_emails",
            "gdelt",
        ]
        limit = int(payload.get("limit", 20))
        context = int(payload.get("context", 120))
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"

        tool_results = _run_query_sources(
            query=query,
            sources=sources,
            limit=limit,
            output_dir=output_dir,
            context=context,
            dry_run=dry_run,
        )

        report_lines = [
            f"# Source Scan Report: {query}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "query": query,
            "report_path": str(report_path),
            "tools": tool_results,
            "sources": sources,
        }


class DocumentMineWorker(AgentWorker):
    JOB_TYPES = ["document_mine"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        query = payload.get("query")
        if not query:
            raise ValueError("payload.query is required")

        sources = payload.get("sources") or [
            "doj",
            "lmsband",
            "unified_docs",
            "unified_emails",
            "unified_entities",
        ]
        limit = int(payload.get("limit", 20))
        context = int(payload.get("context", 120))
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"

        tool_results = _run_query_sources(
            query=query,
            sources=sources,
            limit=limit,
            output_dir=output_dir,
            context=context,
            dry_run=dry_run,
        )

        report_lines = [
            f"# Document Mine Report: {query}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "query": query,
            "report_path": str(report_path),
            "tools": tool_results,
            "sources": sources,
        }


class EntityTracerWorker(AgentWorker):
    JOB_TYPES = ["trace_entity"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        entity_name = payload.get("entity_name") or payload.get("target_name")
        if not entity_name:
            raise ValueError("payload.entity_name is required")

        sources = payload.get("sources") or ["registry", "opensanctions", "littlesis"]
        jurisdictions = payload.get("jurisdictions") or []
        limit = int(payload.get("limit", 20))
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            if "registry" in sources:
                if jurisdictions:
                    for code in jurisdictions:
                        out = output_dir / f"registry-{code}.json"
                        tool_results[f"registry_{code}"] = _run_tool(
                            tool_root / "query_registry.py",
                            ["search", entity_name, "--jurisdiction", code, "--limit", str(limit)],
                            out,
                        )
                else:
                    out = output_dir / "registry-search.json"
                    tool_results["registry"] = _run_tool(
                        tool_root / "query_registry.py",
                        ["search", entity_name, "--limit", str(limit)],
                        out,
                    )

            if "opensanctions" in sources:
                out = output_dir / "opensanctions-search.json"
                tool_results["opensanctions"] = _run_tool(
                    tool_root / "query_opensanctions.py",
                    ["search", entity_name, "--limit", str(limit)],
                    out,
                )

            if "littlesis" in sources:
                out = output_dir / "littlesis-search.json"
                tool_results["littlesis"] = _run_tool(
                    tool_root / "query_littlesis.py",
                    ["search", entity_name, "--limit", str(limit)],
                    out,
                )

        report_lines = [
            f"# Entity Trace Report: {entity_name}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "entity_name": entity_name,
            "report_path": str(report_path),
            "tools": tool_results,
            "sources": sources,
        }


class PatternSpotterWorker(AgentWorker):
    JOB_TYPES = ["pattern_trigger"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        analyses = payload.get("analyses") or ["stats", "bridges"]
        dry_run = bool(payload.get("dry_run", False))
        centrality_metric = payload.get("centrality_metric", "betweenness")
        centrality_top = int(payload.get("centrality_top", 25))
        min_size = int(payload.get("min_size", 3))
        min_degree = int(payload.get("min_degree", 5))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            for analysis in analyses:
                if analysis == "stats":
                    out = output_dir / "graph-stats.json"
                    tool_results["stats"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["stats"],
                        out,
                    )
                elif analysis == "bridges":
                    out = output_dir / "graph-bridges.json"
                    tool_results["bridges"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["bridges"],
                        out,
                    )
                elif analysis == "centrality":
                    out = output_dir / "graph-centrality.json"
                    tool_results["centrality"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["centrality", "--metric", centrality_metric, "--top", str(centrality_top)],
                        out,
                    )
                elif analysis == "components":
                    out = output_dir / "graph-components.json"
                    tool_results["components"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["components", "--min-size", str(min_size)],
                        out,
                    )
                elif analysis == "holes":
                    out = output_dir / "graph-holes.json"
                    tool_results["holes"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["holes", "--min-degree", str(min_degree)],
                        out,
                    )

        report_lines = [
            "# Pattern Spotter Report",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "report_path": str(report_path),
            "tools": tool_results,
            "analyses": analyses,
        }


class SynthesistWorker(AgentWorker):
    JOB_TYPES = ["synthesis"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        query = payload.get("query") or payload.get("target_name")
        finding_ids = payload.get("finding_ids") or []
        dry_run = bool(payload.get("dry_run", False))

        if not query and not finding_ids:
            raise ValueError("payload.query or payload.finding_ids is required")

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            if finding_ids:
                for finding_id in finding_ids:
                    out = output_dir / f"finding-{finding_id}.json"
                    tool_results[f"finding_{finding_id}"] = _run_tool(
                        tool_root / "findings_tracker.py",
                        ["show", str(finding_id)],
                        out,
                    )
            else:
                out = output_dir / "findings-search.json"
                tool_results["findings_search"] = _run_tool(
                    tool_root / "findings_tracker.py",
                    ["search", query],
                    out,
                )

        report_lines = [
            f"# Synthesis Report: {query or 'selected findings'}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "query": query,
            "report_path": str(report_path),
            "tools": tool_results,
            "finding_ids": finding_ids,
        }


class NetworkAnalystWorker(AgentWorker):
    JOB_TYPES = ["network_analysis"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        analyses = payload.get("analyses") or ["stats", "centrality", "bridges"]
        dry_run = bool(payload.get("dry_run", False))
        centrality_metric = payload.get("centrality_metric", "betweenness")
        centrality_top = int(payload.get("centrality_top", 25))
        min_size = int(payload.get("min_size", 3))
        min_degree = int(payload.get("min_degree", 5))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            for analysis in analyses:
                if analysis == "stats":
                    out = output_dir / "graph-stats.json"
                    tool_results["stats"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["stats"],
                        out,
                    )
                elif analysis == "bridges":
                    out = output_dir / "graph-bridges.json"
                    tool_results["bridges"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["bridges"],
                        out,
                    )
                elif analysis == "centrality":
                    out = output_dir / "graph-centrality.json"
                    tool_results["centrality"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["centrality", "--metric", centrality_metric, "--top", str(centrality_top)],
                        out,
                    )
                elif analysis == "components":
                    out = output_dir / "graph-components.json"
                    tool_results["components"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["components", "--min-size", str(min_size)],
                        out,
                    )
                elif analysis == "holes":
                    out = output_dir / "graph-holes.json"
                    tool_results["holes"] = _run_tool(
                        tool_root / "graph_tools.py",
                        ["holes", "--min-degree", str(min_degree)],
                        out,
                    )

        report_lines = [
            "# Network Analysis Report",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "report_path": str(report_path),
            "tools": tool_results,
            "analyses": analyses,
        }


class TimelineAnalystWorker(AgentWorker):
    JOB_TYPES = ["timeline_correlation"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        start = payload.get("start")
        end = payload.get("end")
        finding_id = payload.get("finding_id")
        date = payload.get("date")
        days = int(payload.get("days", 14))
        list_category = payload.get("category")
        list_year = payload.get("year")
        limit = int(payload.get("limit", 100))
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            if start and end:
                out = output_dir / "timeline-window.json"
                tool_results["window"] = _run_tool(
                    tool_root / "event_timeline.py",
                    ["window", "--start", start, "--end", end],
                    out,
                )
            elif finding_id or date:
                out = output_dir / "timeline-near.json"
                args = ["near", "--days", str(days)]
                if finding_id:
                    args.extend(["--finding-id", str(finding_id)])
                if date:
                    args.extend(["--date", date])
                tool_results["near"] = _run_tool(
                    tool_root / "event_timeline.py",
                    args,
                    out,
                )
            elif list_category or list_year:
                out = output_dir / "timeline-list.json"
                args = ["list", "--limit", str(limit)]
                if list_category:
                    args.extend(["--category", list_category])
                if list_year:
                    args.extend(["--year", str(list_year)])
                tool_results["list"] = _run_tool(
                    tool_root / "event_timeline.py",
                    args,
                    out,
                )
            else:
                out = output_dir / "timeline-stats.json"
                tool_results["stats"] = _run_tool(
                    tool_root / "event_timeline.py",
                    ["stats"],
                    out,
                )

        report_lines = [
            "# Timeline Analysis Report",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "report_path": str(report_path),
            "tools": tool_results,
        }


class SystemicAnalystWorker(AgentWorker):
    JOB_TYPES = ["systemic_analysis"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        top = int(payload.get("top", 50))
        thread_id = payload.get("thread_id")
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            out = output_dir / "coverage-matrix.json"
            tool_results["coverage_matrix"] = _run_tool(
                tool_root / "analysis_export.py",
                ["coverage-matrix", "--top", str(top)],
                out,
            )
            out = output_dir / "thread-summary.json"
            args = ["thread-summary"]
            if thread_id is not None:
                args.extend(["--thread-id", str(thread_id)])
            tool_results["thread_summary"] = _run_tool(
                tool_root / "analysis_export.py",
                args,
                out,
            )
            out = output_dir / "analysis-state.json"
            tool_results["analysis_state"] = _run_tool(
                tool_root / "analysis_export.py",
                ["analysis-state"],
                out,
            )

        report_lines = [
            "# Systemic Analysis Report",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tools executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            count = result.get("count")
            count_txt = f"{count} results" if count is not None else "unknown results"
            report_lines.append(f"- {name}: {status} ({count_txt}) -> {result.get('output_path')}")
        report_path.write_text("\n".join(report_lines))

        return {
            "report_path": str(report_path),
            "tools": tool_results,
        }


class ExplainerWriterWorker(AgentWorker):
    JOB_TYPES = ["mechanism_explainer"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        mechanism = payload.get("mechanism_type") or payload.get("mechanism")
        title = payload.get("title") or (f"Mechanism: {mechanism}" if mechanism else None)
        subtitle = payload.get("subtitle")
        targets = payload.get("targets") or []
        date_str = payload.get("date") or datetime.utcnow().date().isoformat()
        status = payload.get("status", "draft")
        dry_run = bool(payload.get("dry_run", False))

        if not title:
            raise ValueError("payload.title or payload.mechanism_type is required")

        slug = _slugify(title) or job["id"][:8]
        content_dir = _content_root() / "articles"
        content_dir.mkdir(parents=True, exist_ok=True)
        content_path = _unique_content_path(content_dir, slug, "mdx", job["id"])

        targets_text = ", ".join(targets) if isinstance(targets, list) else str(targets)
        frontmatter = [
            "---",
            f"title: \"{title}\"",
            f"subtitle: \"{subtitle}\"" if subtitle else None,
            f"cluster: {slug}",
            f"targets: \"{targets_text}\"" if targets_text else "targets: \"\"",
            f"date: \"{date_str}\"",
            f"status: {status}",
            "modality: mechanism_explainer",
            "---",
            "",
        ]
        frontmatter = [line for line in frontmatter if line is not None]

        body = [
            "## Overview",
            "Draft explainer for the mechanism.",
            "",
            "## Evidence",
            "- [ ] Add primary source citations",
            "",
            "## Open Questions",
            "- [ ] Add open questions",
            "",
            "## Sources",
            "- [ ] Add source references",
        ]
        content_text = "\n".join(frontmatter + body)

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        report_lines = [
            f"# Mechanism Explainer Draft: {title}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            f"## Content Path: {content_path}",
        ]

        review_job_id = None
        if not dry_run:
            content_path.write_text(content_text)
            if payload.get("spawn_review", True):
                review_job_id = self.queue.create_job(
                    job_type="editor_review",
                    domain="curation",
                    payload={
                        "content_path": str(content_path),
                        "modality": "mechanism_explainer",
                    },
                    priority=payload.get("review_priority", 5),
                    created_by=f"agent:{self.persona}",
                    source_trigger="mechanism_explainer",
                )
        else:
            report_lines.append("## Dry Run: content not written")

        report_path.write_text("\n".join(report_lines))
        return {
            "title": title,
            "content_path": str(content_path) if not dry_run else None,
            "report_path": str(report_path),
            "review_job_id": review_job_id,
        }


class ContextualAnalystWorker(AgentWorker):
    JOB_TYPES = ["analytical_article"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        title = payload.get("title") or payload.get("target_name") or "Analytical Article"
        lens = payload.get("lens", "general")
        subtitle = payload.get("subtitle")
        targets = payload.get("targets") or []
        date_str = payload.get("date") or datetime.utcnow().date().isoformat()
        status = payload.get("status", "draft")
        dry_run = bool(payload.get("dry_run", False))

        slug = _slugify(title) or job["id"][:8]
        content_dir = _content_root() / "articles"
        content_dir.mkdir(parents=True, exist_ok=True)
        content_path = _unique_content_path(content_dir, slug, "mdx", job["id"])

        targets_text = ", ".join(targets) if isinstance(targets, list) else str(targets)
        frontmatter = [
            "---",
            f"title: \"{title}\"",
            f"subtitle: \"{subtitle}\"" if subtitle else None,
            f"cluster: {slug}",
            f"targets: \"{targets_text}\"" if targets_text else "targets: \"\"",
            f"date: \"{date_str}\"",
            f"status: {status}",
            f"lens: \"{lens}\"",
            "modality: analytical_article",
            "---",
            "",
        ]
        frontmatter = [line for line in frontmatter if line is not None]

        body = [
            "## Summary",
            "Draft analytical article.",
            "",
            "## Findings",
            "- [ ] Summarize key findings with citations",
            "",
            "## Analysis",
            "- [ ] Provide lens-based analysis",
            "",
            "## Sources",
            "- [ ] Add source references",
        ]
        content_text = "\n".join(frontmatter + body)

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        report_lines = [
            f"# Analytical Article Draft: {title}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            f"## Content Path: {content_path}",
        ]

        review_job_id = None
        if not dry_run:
            content_path.write_text(content_text)
            if payload.get("spawn_review", True):
                review_job_id = self.queue.create_job(
                    job_type="editor_review",
                    domain="curation",
                    payload={
                        "content_path": str(content_path),
                        "modality": "analytical_article",
                    },
                    priority=payload.get("review_priority", 5),
                    created_by=f"agent:{self.persona}",
                    source_trigger="analytical_article",
                )
        else:
            report_lines.append("## Dry Run: content not written")

        report_path.write_text("\n".join(report_lines))
        return {
            "title": title,
            "content_path": str(content_path) if not dry_run else None,
            "report_path": str(report_path),
            "review_job_id": review_job_id,
        }


class EditorReviewWorker(AgentWorker):
    JOB_TYPES = ["editor_review", "fact_check"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        content_path = payload.get("content_path")
        slug = payload.get("slug")
        min_words = int(payload.get("min_words", 300))
        required_fields = payload.get("required_fields") or ["title", "date", "status"]

        if not content_path and slug:
            content_path = str(_content_root() / "articles" / f"{slug}.mdx")
        if not content_path:
            raise ValueError("payload.content_path or payload.slug is required")

        content_file = Path(content_path)
        if not content_file.exists():
            raise FileNotFoundError(f"Content not found: {content_path}")

        raw = content_file.read_text()
        frontmatter: Dict[str, str] = {}
        body = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1]
                body = parts[2].lstrip("\n")
                for line in fm_text.splitlines():
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip().strip("\"")

        missing = [field for field in required_fields if not frontmatter.get(field)]
        word_count = len(re.findall(r"\\b\\w+\\b", body))
        citations = sorted(set(re.findall(r"\[[^\]]+\]", body)))

        issues = []
        if missing:
            issues.append(f"Missing frontmatter fields: {', '.join(missing)}")
        if word_count < min_words:
            issues.append(f"Word count below minimum ({word_count} < {min_words})")
        if not citations:
            issues.append("No citations detected")

        decision = "approve" if not issues else "revise"
        report = {
            "content_path": content_path,
            "decision": decision,
            "issues": issues,
            "missing_fields": missing,
            "word_count": word_count,
            "citation_count": len(citations),
            "citations": citations,
        }

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.json"
        report_path.write_text(json.dumps(report, indent=2))

        return {
            "report_path": str(report_path),
            "review": report,
        }


class DedupeReviewWorker(AgentWorker):
    JOB_TYPES = ["dedupe_review"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        action = payload.get("action", "scan")
        dry_run = bool(payload.get("dry_run", False))
        keep_id = payload.get("keep_id")
        delete_id = payload.get("delete_id")

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        args: List[str] = []
        if action in {"scan", "stats", "seed", "apply"}:
            args = [action]
            if action in {"seed", "apply"} and dry_run:
                args.append("--dry-run")
        elif action == "merge":
            if keep_id is None or delete_id is None:
                raise ValueError("payload.keep_id and payload.delete_id are required for merge")
            args = ["merge", "--keep-id", str(keep_id), "--delete-id", str(delete_id)]
            if dry_run:
                args.append("--dry-run")
        else:
            raise ValueError(f"Unsupported dedupe action '{action}'")

        if not dry_run:
            tool_root = Path(__file__).resolve().parent.parent / "tools"
            tool_results["entity_dedup"] = _run_script(tool_root / "entity_dedup.py", args)

        report_lines = [
            f"# Dedupe Review: {action}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
        ]
        if dry_run:
            report_lines.append("## Dry Run: no dedupe actions executed")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "action": action,
            "report_path": str(report_path),
            "tools": tool_results,
        }


class FindingVerificationWorker(AgentWorker):
    JOB_TYPES = ["verify_finding"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        finding_id = payload.get("finding_id")
        mark_verified = bool(payload.get("mark_verified", False))
        verified_by = payload.get("verified_by", f"agent:{self.persona}")
        dry_run = bool(payload.get("dry_run", False))

        if finding_id is None:
            raise ValueError("payload.finding_id is required")

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        output_dir = workdir / "output"
        tool_results: Dict[str, Any] = {}

        tool_root = Path(__file__).resolve().parent.parent / "tools"
        if not dry_run:
            out = output_dir / f"finding-{finding_id}.json"
            tool_results["show"] = _run_tool(
                tool_root / "findings_tracker.py",
                ["show", str(finding_id)],
                out,
            )

            if mark_verified:
                tool_results["verify"] = _run_script(
                    tool_root / "findings_tracker.py",
                    ["verify", str(finding_id), "--by", verified_by],
                )

        report_lines = [
            f"# Finding Verification: {finding_id}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Tool Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no tool execution)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "finding_id": finding_id,
            "report_path": str(report_path),
            "tools": tool_results,
        }


class ToolBuilderWorker(AgentWorker):
    JOB_TYPES = ["tool_build", "bug_fix"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        infra_id = payload.get("infra_id")
        note = payload.get("note")
        script = payload.get("script")
        script_args = payload.get("args", [])
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        if infra_id and not dry_run:
            tool_results["claim"] = _run_infra_action("claim", infra_id, [])
            if note:
                tool_results["note"] = _run_infra_action("note", infra_id, [note])

        if script:
            script_path = Path(script)
            if not script_path.is_absolute():
                script_path = Path(__file__).resolve().parent.parent / script_path
            if not dry_run:
                tool_results["script"] = _run_script(script_path, list(script_args))

        report_lines = [
            f"# Tool Build: {infra_id or 'no infra id'}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
        ]
        if dry_run:
            report_lines.append("## Dry Run: no infra actions executed")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "infra_id": infra_id,
            "report_path": str(report_path),
            "tools": tool_results,
        }


class SourceIntegratorWorker(AgentWorker):
    JOB_TYPES = ["source_ingest"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        script = payload.get("script")
        script_args = payload.get("args", [])
        infra_id = payload.get("infra_id")
        dry_run = bool(payload.get("dry_run", False))

        if not script and not infra_id:
            raise ValueError("payload.script or payload.infra_id is required")

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        if infra_id and not dry_run:
            tool_results["claim"] = _run_infra_action("claim", infra_id, [])

        if script:
            script_path = Path(script)
            if not script_path.is_absolute():
                script_path = Path(__file__).resolve().parent.parent / script_path
            if not dry_run:
                tool_results["script"] = _run_script(script_path, list(script_args))

        report_lines = [
            f"# Source Ingest: {infra_id or script}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
        ]
        if dry_run:
            report_lines.append("## Dry Run: no ingest actions executed")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "infra_id": infra_id,
            "report_path": str(report_path),
            "tools": tool_results,
        }


class RegistryAdderWorker(AgentWorker):
    JOB_TYPES = ["registry_add"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        script = payload.get("script")
        script_args = payload.get("args", [])
        infra_id = payload.get("infra_id")
        dry_run = bool(payload.get("dry_run", False))

        if not script and not infra_id:
            raise ValueError("payload.script or payload.infra_id is required")

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        if infra_id and not dry_run:
            tool_results["claim"] = _run_infra_action("claim", infra_id, [])

        if script:
            script_path = Path(script)
            if not script_path.is_absolute():
                script_path = Path(__file__).resolve().parent.parent / script_path
            if not dry_run:
                tool_results["script"] = _run_script(script_path, list(script_args))

        report_lines = [
            f"# Registry Add: {infra_id or script}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
        ]
        if dry_run:
            report_lines.append("## Dry Run: no registry actions executed")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "infra_id": infra_id,
            "report_path": str(report_path),
            "tools": tool_results,
        }


class DeepInvestigationWorker(AgentWorker):
    JOB_TYPES = ["deep_investigate"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        target = payload.get("target_name") or payload.get("query")
        if not target:
            raise ValueError("payload.target_name is required")

        child_specs = payload.get("child_jobs")
        if not child_specs:
            child_specs = [
                {"job_type": "deep_person", "domain": "investigation"},
                {"job_type": "document_mine", "domain": "investigation"},
                {"job_type": "trace_entity", "domain": "investigation"},
                {"job_type": "pattern_trigger", "domain": "analysis"},
            ]

        thread_id = job.get("thread_id") or job["id"]
        parent_id = job["id"]
        child_jobs: List[str] = []
        for spec in child_specs:
            job_type = spec["job_type"]
            domain = spec.get("domain", "investigation")
            child_payload = dict(spec.get("payload", {}))

            if not child_payload:
                if job_type == "deep_person":
                    child_payload = {
                        "target_name": target,
                        "lead_id": payload.get("lead_id"),
                    }
                elif job_type == "document_mine":
                    child_payload = {
                        "query": target,
                        "dry_run": payload.get("dry_run", False),
                    }
                elif job_type == "trace_entity":
                    child_payload = {
                        "entity_name": target,
                        "dry_run": payload.get("dry_run", False),
                    }
                elif job_type == "pattern_trigger":
                    child_payload = {"dry_run": payload.get("dry_run", False)}

            for key in ("limit", "sources", "context", "jurisdictions"):
                if key in payload and key not in child_payload:
                    child_payload[key] = payload[key]

            child_id = self.queue.create_job(
                job_type=job_type,
                domain=domain,
                payload=child_payload,
                priority=payload.get("priority", 5),
                created_by=f"agent:{self.persona}",
                parent_job_id=parent_id,
                thread_id=thread_id,
                source_trigger="deep_investigate",
            )
            child_jobs.append(child_id)

        synthesis_id = None
        if payload.get("spawn_synthesis", True):
            synthesis_payload = {
                "query": target,
                "dry_run": payload.get("dry_run", False),
            }
            synthesis_id = self.queue.create_job(
                job_type="synthesis",
                domain="analysis",
                payload=synthesis_payload,
                priority=payload.get("priority", 5),
                created_by=f"agent:{self.persona}",
                parent_job_id=parent_id,
                thread_id=thread_id,
                depends_on=child_jobs,
                source_trigger="deep_investigate",
            )

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        child_path = workdir / "child_jobs.json"

        report_lines = [
            f"# Deep Investigation Orchestration: {target}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Child Jobs",
        ]
        for child_id in child_jobs:
            report_lines.append(f"- {child_id}")
        if synthesis_id:
            report_lines.append("")
            report_lines.append(f"## Synthesis Job: {synthesis_id}")

        report_path.write_text("\n".join(report_lines))
        child_path.write_text(
            json.dumps(
                {
                    "target": target,
                    "child_jobs": child_jobs,
                    "synthesis_job": synthesis_id,
                },
                indent=2,
            )
        )

        return {
            "target": target,
            "child_jobs": child_jobs,
            "synthesis_job": synthesis_id,
            "report_path": str(report_path),
            "child_jobs_path": str(child_path),
        }


class DossierWriterWorker(AgentWorker):
    JOB_TYPES = ["wiki_dossier_update"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        target = payload.get("target_name")
        min_findings = int(payload.get("min_findings", 5))
        update_backlinks = bool(payload.get("update_backlinks", False))
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        pipeline_root = Path(__file__).resolve().parent.parent / "site" / "pipeline"
        if not dry_run:
            args = []
            if target:
                args.extend(["--target", target])
            if min_findings:
                args.extend(["--min-findings", str(min_findings)])
            tool_results["export_dossiers"] = _run_script(
                pipeline_root / "export_dossiers.py",
                args,
            )

            if update_backlinks:
                tool_results["compute_backlinks"] = _run_script(
                    pipeline_root / "compute_backlinks.py",
                    [],
                )

        report_lines = [
            f"# Dossier Update: {target or 'all targets'}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Pipeline Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no pipeline scripts executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "target": target,
            "report_path": str(report_path),
            "pipeline": tool_results,
        }


class VisualExportWorker(AgentWorker):
    JOB_TYPES = ["visual_export"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        export_type = payload.get("export_type", "network_graph")
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        pipeline_root = Path(__file__).resolve().parent.parent / "site" / "pipeline"
        script_map = {
            "network_graph": "export_network.py",
            "financial_flows": "export_financials.py",
            "story_clusters": "story_clustering.py",
            "backlinks": "compute_backlinks.py",
        }
        script_name = script_map.get(export_type)
        if not script_name:
            raise ValueError(f"Unsupported export_type '{export_type}'")

        if not dry_run:
            tool_results[export_type] = _run_script(
                pipeline_root / script_name,
                [],
            )

        report_lines = [
            f"# Visual Export: {export_type}",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Pipeline Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no pipeline scripts executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "export_type": export_type,
            "report_path": str(report_path),
            "pipeline": tool_results,
        }


class ContentBuildWorker(AgentWorker):
    JOB_TYPES = ["content_build"]

    def execute(self, job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload", {})
        dry_run = bool(payload.get("dry_run", False))

        workdir = _ensure_workdir(job["id"])
        report_path = workdir / "report.md"
        tool_results: Dict[str, Any] = {}

        pipeline_root = Path(__file__).resolve().parent.parent / "site" / "pipeline"
        if not dry_run:
            tool_results["build_all"] = _run_script(
                pipeline_root / "build_all.py",
                [],
            )

        report_lines = [
            "# Content Build",
            f"## Job ID: {job['id']}",
            f"## Agent: {self.persona}",
            f"## Executed: {datetime.utcnow().isoformat()}",
            "",
            "## Pipeline Results",
        ]
        if dry_run:
            report_lines.append("- dry_run: true (no pipeline scripts executed)")
        for name, result in tool_results.items():
            status = "ok" if result.get("returncode") == 0 else "error"
            report_lines.append(f"- {name}: {status}")
            if result.get("stderr"):
                report_lines.append(f"  - stderr: {result['stderr'][:200]}")
        report_path.write_text("\n".join(report_lines))

        return {
            "report_path": str(report_path),
            "pipeline": tool_results,
        }


WORKER_REGISTRY = {
    "echo": EchoWorker,
    "lead_triage": LeadTriageWorker,
    "deep_person": DeepPersonWorker,
    "source_scan": SurveyorWorker,
    "surveyor": SurveyorWorker,
    "document_mine": DocumentMineWorker,
    "document_miner": DocumentMineWorker,
    "trace_entity": EntityTracerWorker,
    "entity_tracer": EntityTracerWorker,
    "pattern_trigger": PatternSpotterWorker,
    "pattern_spotter": PatternSpotterWorker,
    "synthesis": SynthesistWorker,
    "synthesist": SynthesistWorker,
    "network_analysis": NetworkAnalystWorker,
    "network_analyst": NetworkAnalystWorker,
    "timeline_correlation": TimelineAnalystWorker,
    "timeline_analyst": TimelineAnalystWorker,
    "systemic_analysis": SystemicAnalystWorker,
    "systemic_analyst": SystemicAnalystWorker,
    "mechanism_explainer": ExplainerWriterWorker,
    "explainer_writer": ExplainerWriterWorker,
    "analytical_article": ContextualAnalystWorker,
    "contextual_analyst": ContextualAnalystWorker,
    "editor_review": EditorReviewWorker,
    "editor": EditorReviewWorker,
    "fact_check": EditorReviewWorker,
    "dedupe_review": DedupeReviewWorker,
    "verify_finding": FindingVerificationWorker,
    "tool_build": ToolBuilderWorker,
    "bug_fix": ToolBuilderWorker,
    "source_ingest": SourceIntegratorWorker,
    "registry_add": RegistryAdderWorker,
    "deep_investigate": DeepInvestigationWorker,
    "investigation_orchestrator": DeepInvestigationWorker,
    "wiki_dossier_update": DossierWriterWorker,
    "dossier_writer": DossierWriterWorker,
    "visual_export": VisualExportWorker,
    "visual_exporter": VisualExportWorker,
    "content_build": ContentBuildWorker,
    "content_pipeline": ContentBuildWorker,
}
