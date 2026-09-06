#!/usr/bin/env python3
"""
Investigation-aware pipeline dispatcher.

This script now supports two modes:

1. Legacy queue-driven auto-dispatch (`run`, `daemon`) for the existing lead/infra
   workflow.
2. Manual orchestration (`plan`, `launch`, `status`, `review`, `import`, `stop`)
   for staged Claude-backed investigation workers that emit reviewable artifacts.

Claude Code remains the only execution backend in v1. Repo-local Claude skills are
the canonical worker instructions for launched jobs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH", PROJECT_ROOT / "investigation.db"))
CONFIG_PATH = Path(__file__).resolve().parent / "dispatch_config.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

REQUIRED_ARTIFACTS = [
    "report.md",
    "run.json",
    "candidate_findings.jsonl",
    "candidate_leads.jsonl",
    "candidate_entities.jsonl",
]
OPTIONAL_ARTIFACTS = ["candidate_connections.jsonl"]
ALL_ARTIFACTS = REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS

DEFAULT_CONFIG: dict[str, Any] = {
    "poll_interval_seconds": 300,
    "max_concurrent": 6,
    "max_research_agents": 6,
    "max_analysis_agents": 1,
    "allowed_tools": "Bash,Read,Write,Edit,Glob,Grep,Task,WebFetch,WebSearch",
    "permission_mode": "bypassPermissions",
    "cooldown_seconds": 60,
    "timeout_seconds": 3600,
    "stall_seconds": 1800,
    "daily_budget_usd": 50.0,
    "model": "sonnet",
    "staging_root": ".dispatch_staging",
    "triggers": {
        "triage": {"min_pending": 1},
        "build_infra": {"min_open": 1},
        "pursue_lead": {"min_high_critical": 1},
        "auto_leads": {"completions_since_last": 10},
        "analyze_network": {"new_findings_since_last": 50, "cooldown_hours": 48},
        "generate_hunches": {"new_findings_since_last": 50, "cooldown_hours": 72},
        "timeline_analysis": {"new_findings_since_last": 30, "cooldown_hours": 72},
        "systemic_analysis": {"new_findings_since_last": 50, "cooldown_hours": 168},
    },
    "job_defaults": {},
}


JOB_DEFS: dict[str, dict[str, Any]] = {
    "triage": {
        "skill_name": "triage-leads",
        "prompt": (
            "Process the next batch of pending_triage leads. Claim up to 20, "
            "deduplicate against existing leads, adjust priorities, and promote to open. "
            "Dead-end duplicates. Report results."
        ),
        "default_target_kind": "batch",
    },
    "pursue_lead": {
        "skill_name": "pursue-lead",
        "prompt": (
            "Claim and investigate lead #{target}. Follow the pursue-lead methodology. "
            "Use the staged artifact contract if one is supplied."
        ),
        "default_target_kind": "lead",
    },
    "deep_investigate": {
        "skill_name": "deep-investigate",
        "prompt": (
            "Run a deep investigation on {target}. Follow the deep-investigate methodology. "
            "Use the staged artifact contract if one is supplied."
        ),
        "default_target_kind": "target",
    },
    "build_infra": {
        "skill_name": "build-infra",
        "prompt": (
            "Claim infra request #{target} and build it. Probe the endpoint first, "
            "confirm it works, then write the tool. Test against known targets. "
            "Update CLAUDE.md and TOOL_REFERENCE.md. Complete the request."
        ),
        "default_target_kind": "infra",
    },
    "auto_leads": {
        "skill_name": None,
        "prompt": "Run: uv run python tools/auto_leads.py run\nReport the results.",
        "default_target_kind": "batch",
    },
    "analyze_network": {
        "skill_name": "analyze-network",
        "prompt": (
            "Run the /analyze-network skill. Analyze the investigation graph for structural patterns, "
            "centrality, bridges, clusters, cross-thread actors, and coverage gaps. "
            "Record findings, tag clusters, generate hypotheses, create leads for gaps."
        ),
        "default_target_kind": "batch",
    },
    "generate_hunches": {
        "skill_name": "generate-hunches",
        "prompt": (
            "Run the /generate-hunches skill. Scan findings and entity data for emerging themes "
            "and recurring patterns that cross unexpected boundaries. "
            "Generate hypotheses with testable search plans. Quality over quantity."
        ),
        "default_target_kind": "batch",
    },
    "timeline_analysis": {
        "skill_name": "timeline-analysis",
        "prompt": (
            "Run the /timeline-analysis skill. Analyze temporal patterns in findings — "
            "activity clusters, pre-event spikes, silence periods, coordinated action windows. "
            "Cross-reference with event timeline."
        ),
        "default_target_kind": "batch",
    },
    "systemic_analysis": {
        "skill_name": "systemic-analysis",
        "prompt": (
            "Run the /systemic-analysis skill. Analyze the largest investigation thread's actors "
            "as a system — shared boards, co-investments, common counsel, jurisdiction clustering. "
            "Focus on non-subject connections between actors."
        ),
        "default_target_kind": "batch",
    },
    "investigate_infra": {
        "skill_name": "investigate-infra",
        "prompt": (
            "Investigate the digital infrastructure for {target}. Follow the investigate-infra methodology. "
            "Document domains, DNS, certificates, hosting, passive web artifacts, and linked infrastructure."
        ),
        "default_target_kind": "target",
    },
    "trace_entity": {
        "skill_name": "trace-entity",
        "prompt": (
            "Trace the entity {target}. Follow the trace-entity methodology. "
            "Document ownership, control, registrations, filings, officers, addresses, and negative results."
        ),
        "default_target_kind": "entity",
    },
    "investigate_person": {
        "skill_name": "investigate-person",
        "prompt": (
            "Investigate the person {target}. Follow the investigate-person methodology. "
            "Document employer history, affiliations, filings, co-occurrences, and negative results."
        ),
        "default_target_kind": "person",
    },
    "landscape_scan": {
        "skill_name": "landscape-scan",
        "prompt": (
            "Run a tier 0 landscape scan on {target}. Follow the landscape-scan methodology. "
            "Map 10-30 targets quickly with 2-3 structured sources each, record significant findings "
            "with provenance, create leads for promising targets, and produce a relationship map."
        ),
        "default_target_kind": "target",
    },
}


def _job_defaults_from_defs() -> dict[str, Any]:
    defaults = {}
    for job_type in JOB_DEFS:
        defaults[job_type] = {
            "timeout_seconds": 3600,
            "expected_artifacts": list(REQUIRED_ARTIFACTS),
            "priority": "medium",
            "review_required": False,
        }
    for job_type in [
        "pursue_lead",
        "deep_investigate",
        "trace_entity",
        "investigate_person",
        "triage",
        "analyze_network",
        "generate_hunches",
        "timeline_analysis",
        "systemic_analysis",
        "investigate_infra",
        "landscape_scan",
    ]:
        defaults[job_type]["review_required"] = True
    return defaults


DEFAULT_CONFIG["job_defaults"] = _job_defaults_from_defs()

PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
LEAD_CLUSTER_STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "for",
    "of",
    "to",
    "in",
    "on",
    "via",
    "vs",
    "with",
    "from",
    "trace",
    "deep",
    "investigate",
    "investigation",
    "identify",
    "map",
    "resolve",
    "retrieve",
    "search",
    "verify",
    "assess",
    "analyze",
    "audit",
    "monitor",
    "sweep",
    "follow",
    "lead",
    "entity",
    "entities",
    "person",
    "people",
    "corporate",
    "company",
    "companies",
    "structure",
    "timing",
    "history",
    "status",
    "registration",
    "registrations",
    "platform",
    "platforms",
    "infrastructure",
    "stack",
    "payment",
    "payments",
    "processor",
    "processors",
    "merchant",
    "program",
    "programme",
    "programmes",
    "affiliate",
    "affiliates",
    "consumer",
    "signals",
    "claims",
    "income",
    "pricing",
    "products",
    "product",
    "media",
    "network",
    "networks",
    "offshore",
    "operating",
    "operator",
    "operators",
    "current",
    "future",
    "post",
    "llc",
    "inc",
    "ltd",
    "corp",
    "corporation",
    "company",
    "co",
    "limited",
    "srl",
    "fzco",
}

SKILL_PATHS = {
    job_type: (SKILLS_DIR / spec["skill_name"] / "SKILL.md") if spec.get("skill_name") else None
    for job_type, spec in JOB_DEFS.items()
}


@dataclass
class TaskContract:
    job_type: str
    target: str | None = None
    lead_id: int | None = None
    profile_id: str | None = None
    hypothesis_id: int | None = None
    brief: str | None = None
    skill_name: str | None = None
    expected_artifacts: list[str] | None = None
    priority: str | None = None
    timeout_seconds: int | None = None
    cost_cap_usd: float | None = None
    review_required: bool = False
    orchestrator: str = "manual"
    backend: str = "claude"

    def to_json(self) -> str:
        return json.dumps(
            {
                "job_type": self.job_type,
                "target": self.target,
                "lead_id": self.lead_id,
                "profile_id": self.profile_id,
                "hypothesis_id": self.hypothesis_id,
                "brief": self.brief,
                "skill_name": self.skill_name,
                "expected_artifacts": self.expected_artifacts,
                "priority": self.priority,
                "timeout_seconds": self.timeout_seconds,
                "cost_cap_usd": self.cost_cap_usd,
                "review_required": self.review_required,
                "orchestrator": self.orchestrator,
                "backend": self.backend,
            },
            sort_keys=True,
        )


class ClaudeBackend:
    """Small adapter boundary for the Claude worker backend."""

    name = "claude"

    def preflight(self) -> tuple[bool, str, str]:
        try:
            proc = subprocess.run(
                ["claude", "auth", "status"],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                timeout=20,
            )
        except FileNotFoundError:
            return False, "launch_failed", "'claude' not found in PATH"
        except subprocess.TimeoutExpired:
            return False, "launch_failed", "Timed out while checking Claude auth"

        combined = "\n".join(
            part.strip() for part in [proc.stdout or "", proc.stderr or ""] if part.strip()
        ).strip()
        combined = combined or "No auth status output"
        lower = combined.lower()

        if proc.returncode == 0:
            return True, "healthy", combined
        if "expired" in lower or "oauth" in lower or "authentication" in lower:
            return False, "auth_failed", combined
        return False, "launch_failed", combined

    def build_command(self, prompt: str, config: dict[str, Any], system_prompts: list[str]) -> list[str]:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--allowedTools",
            config.get("allowed_tools", DEFAULT_CONFIG["allowed_tools"]),
            "--permission-mode",
            config.get("permission_mode", DEFAULT_CONFIG["permission_mode"]),
            "--no-session-persistence",
        ]
        for prompt_text in system_prompts:
            if prompt_text:
                cmd.extend(["--append-system-prompt", prompt_text])
        model = config.get("model")
        if model:
            cmd.extend(["--model", model])
        return cmd


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as handle:
            return deep_merge(DEFAULT_CONFIG, json.load(handle))
    return dict(DEFAULT_CONFIG)


def get_staging_root(config: dict[str, Any]) -> Path:
    root = Path(config.get("staging_root", DEFAULT_CONFIG["staging_root"]))
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def get_columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def ensure_column(db: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    if name not in get_columns(db, table):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def ensure_dispatch_table(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS dispatch_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            target TEXT,
            pid INTEGER,
            status TEXT DEFAULT 'running' CHECK(status IN ('running','completed','failed','timeout')),
            session_id TEXT,
            prompt_hash TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            exit_code INTEGER,
            cost_usd REAL,
            findings_added INTEGER,
            leads_created INTEGER,
            output_file TEXT,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_runs(status);
        CREATE INDEX IF NOT EXISTS idx_dispatch_type ON dispatch_runs(run_type);
        CREATE INDEX IF NOT EXISTS idx_dispatch_started ON dispatch_runs(started_at);

        CREATE TABLE IF NOT EXISTS dispatch_staging (
            run_id INTEGER PRIMARY KEY REFERENCES dispatch_runs(id) ON DELETE CASCADE,
            staging_dir TEXT NOT NULL,
            required_artifacts_json TEXT,
            artifact_presence_json TEXT,
            artifact_counts_json TEXT,
            duplicate_risks_json TEXT,
            validation_error TEXT,
            last_artifact_at TIMESTAMP,
            review_status TEXT DEFAULT 'pending'
                CHECK(review_status IN ('pending','approved','rejected','invalid','imported')),
            import_status TEXT DEFAULT 'pending'
                CHECK(import_status IN ('pending','imported','failed','skipped')),
            review_notes TEXT,
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            imported_by TEXT,
            imported_at TIMESTAMP,
            imported_counts_json TEXT
        );

        CREATE TABLE IF NOT EXISTS dispatch_import_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES dispatch_runs(id) ON DELETE CASCADE,
            artifact_name TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            record_json TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_dispatch_import_raw_run
            ON dispatch_import_raw(run_id, artifact_name, record_index);

        CREATE TABLE IF NOT EXISTS dispatch_import_diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL REFERENCES dispatch_runs(id) ON DELETE CASCADE,
            artifact_name TEXT NOT NULL,
            record_index INTEGER,
            severity TEXT NOT NULL DEFAULT 'warning',
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            record_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_dispatch_import_diag_run
            ON dispatch_import_diagnostics(run_id, artifact_name);
        """
    )

    extra_columns = {
        "job_type": "TEXT",
        "lead_id": "INTEGER",
        "hypothesis_id": "INTEGER",
        "brief": "TEXT",
        "skill_name": "TEXT",
        "expected_artifacts": "TEXT",
        "priority": "TEXT",
        "timeout_seconds": "INTEGER",
        "cost_cap_usd": "REAL",
        "review_required": "INTEGER DEFAULT 0",
        "orchestrator": "TEXT",
        "backend": "TEXT DEFAULT 'claude'",
        "task_contract_json": "TEXT",
        "staging_dir": "TEXT",
        "health_status": "TEXT",
        "health_detail": "TEXT",
        "last_artifact_at": "TIMESTAMP",
    }
    for name, ddl in extra_columns.items():
        ensure_column(db, "dispatch_runs", name, ddl)
    ensure_column(db, "dispatch_staging", "approved_bundle_hash", "TEXT")

    db.execute("UPDATE dispatch_runs SET job_type = run_type WHERE job_type IS NULL")
    db.execute("UPDATE dispatch_runs SET backend = 'claude' WHERE backend IS NULL")
    db.execute("UPDATE dispatch_runs SET review_required = 0 WHERE review_required IS NULL")
    db.execute("UPDATE dispatch_runs SET health_status = 'healthy' WHERE health_status IS NULL")
    db.commit()


def normalize_job_type(value: str) -> str:
    normalized = value.strip().lower().lstrip("/").replace("-", "_")
    aliases = {
        "trace_entity": "trace_entity",
        "investigate_person": "investigate_person",
        "pursue_lead": "pursue_lead",
        "deep_investigate": "deep_investigate",
        "build_infra": "build_infra",
        "auto_leads": "auto_leads",
        "analyze_network": "analyze_network",
        "generate_hunches": "generate_hunches",
        "timeline_analysis": "timeline_analysis",
        "systemic_analysis": "systemic_analysis",
        "investigate_infra": "investigate_infra",
        "landscape_scan": "landscape_scan",
        "triage": "triage",
    }
    if normalized not in aliases:
        raise ValueError(f"Unknown job type '{value}'")
    return aliases[normalized]


def build_prompt(job_type: str, target: str | None, brief: str | None = None) -> str:
    template = JOB_DEFS[job_type]["prompt"]
    prompt = template.format(target=target or "batch")
    if brief:
        prompt = f"{prompt}\n\nTask brief:\n{brief.strip()}"
    return prompt


def prompt_hash(contract: TaskContract) -> str:
    key = hashlib.md5(contract.to_json().encode()).hexdigest()
    return key[:12]


def slugify(value: str | None) -> str:
    if not value:
        return "batch"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-").lower()
    return cleaned or "batch"


def create_staging_dir(config: dict[str, Any], contract: TaskContract, hash_key: str) -> Path:
    ts = utcnow().strftime("%Y%m%d-%H%M%S")
    root = get_staging_root(config)
    return Path(tempfile.mkdtemp(
        prefix=f"{ts}-{contract.job_type}-{slugify(contract.target)}-{hash_key}-", dir=root
    ))


def artifact_manifest(staging_dir: Path, expected_artifacts: list[str]) -> dict[str, str]:
    manifest = {name: str(staging_dir / name) for name in expected_artifacts}
    for optional_name in OPTIONAL_ARTIFACTS:
        manifest[optional_name] = str(staging_dir / optional_name)
    manifest["raw_output.json"] = str(staging_dir / "raw_output.json")
    manifest["stderr.log"] = str(staging_dir / "stderr.log")
    return manifest


def build_staging_instruction(contract: TaskContract, manifest: dict[str, str]) -> str:
    example_records = {
        "candidate_findings.jsonl": {
            "target_name": contract.target or "Target name",
            "summary": "One evidence-backed finding",
            "finding_type": "financial",
            "detail": "Optional detail paragraph",
            "source_datasets": ["edgar"],
            "confidence": "high",
            "date_of_event": "2025-10-30",
            "claim_type": "paraphrase",
            "verification_status": "unverified",
            "evidence_ids": ["https://www.sec.gov/example-filing"],
            "source_quotes": {
                "https://www.sec.gov/example-filing": {"quote": "Exact supporting source text"}
            },
        },
        "candidate_leads.jsonl": {
            "title": "Follow-up lead title",
            "description": "Why the follow-up matters",
            "category": "entity",
            "priority": "high",
            "status": "open",
            "source": "staged_worker",
            "target_name": contract.target or "Target name",
            "recommended_skill": "/trace-entity",
        },
        "candidate_entities.jsonl": {
            "record_type": "entity",
            "name": contract.target or "Entity name",
            "entity_type": "ltd",
            "jurisdiction": "Hong Kong",
            "status": "active",
            "source": "hk_registry",
            "notes": "Optional note",
        },
        "candidate_entities.role.jsonl": {
            "record_type": "role",
            "entity_name": contract.target or "Entity name",
            "person_name": "Jane Doe",
            "role": "Chief Executive Officer",
            "source": "edgar",
            "notes": "Optional note",
        },
        "candidate_entities.address.jsonl": {
            "record_type": "address",
            "associated_entities": [contract.target or "Entity name"],
            "address": "123 Example Street, City, Country",
            "address_type": "registered",
            "source": "registry",
            "notes": "Optional note",
        },
        "candidate_connections.jsonl": {
            "person_a": contract.target or "Entity A",
            "person_b": "Related party",
            "relationship_type": "corporate",
            "description": "Relationship summary",
            "strength": "strong",
        },
    }
    return (
        "You are running as a staged research worker.\n"
        "Do not mutate canonical investigation state directly. Specifically do not call "
        "`findings_tracker.py add`, `lead_tracker.py add`, `entity_tracker.py add-*`, "
        "or write directly to `investigation.db`.\n\n"
        f"Write artifacts into `{Path(manifest['report.md']).parent}`.\n"
        "Required files:\n"
        + "".join(f"- `{name}` -> `{path}`\n" for name, path in manifest.items() if name in REQUIRED_ARTIFACTS)
        + "Optional file:\n"
        + f"- `candidate_connections.jsonl` -> `{manifest['candidate_connections.jsonl']}`\n\n"
        "Artifact rules:\n"
        "- Always create every required file, even when empty.\n"
        "- `report.md` must summarize what you checked, what you found, and what remains open.\n"
        "- `run.json` must be valid JSON and include `summary`, `status`, `sources_checked`, "
        "`counts`, `notes`, and `lead_disposition` keys. `status` must be completed, partial, blocked, or dead_end. "
        "`lead_disposition` must be keep_open, completed, blocked, or dead_end; default to keep_open. "
        "Only propose completed after resolving the investigative question.\n"
        "- `candidate_*.jsonl` files must contain one JSON object per line. Empty files are allowed.\n"
        "- For `candidate_entities.jsonl`, use `record_type` values `entity`, `role`, `address`, or `relation`.\n"
        "- For `record_type=role`, use `person_name` and `role`. Do not use `name` or `title` as substitutes.\n"
        "- For `record_type=address`, use `address`. Do not store the address in `name`.\n"
        "- If a role or address row belongs to the primary subject and no explicit entity is known, set "
        "`entity_name` or `associated_entities` to the primary subject.\n"
        "- Every finding must include claim_type, evidence_ids, and source_quotes mapping each reference to an exact quote. "
        "Use source_datasets as an array of registered source names.\n"
        "- Preserve provenance in each record using `source`, `source_datasets`, `notes`, or equivalent fields.\n\n"
        "JSONL examples:\n"
        + "\n".join(
            f"{name}: {json.dumps(record, sort_keys=True)}"
            for name, record in example_records.items()
        )
    )


def normalize_candidate_entity_record(
    record: dict[str, Any],
    default_entity_name: str | None = None,
) -> dict[str, Any]:
    normalized = dict(record)
    record_type = normalized.get("record_type", "entity")

    if record_type == "role":
        person_name = normalized.get("person_name") or normalized.get("person") or normalized.get("name")
        if person_name:
            normalized["person_name"] = person_name
            if normalized.get("name") == person_name:
                normalized.pop("name", None)

        if not normalized.get("role") and normalized.get("title"):
            normalized["role"] = normalized["title"]

        has_entity_ref = any(
            normalized.get(key)
            for key in ("entity_id", "entity_name", "entity", "associated_entities")
        )
        if default_entity_name and not has_entity_ref:
            normalized["entity_name"] = default_entity_name

    elif record_type == "address":
        if not normalized.get("address") and normalized.get("name"):
            normalized["address"] = normalized["name"]
            normalized.pop("name", None)

        has_entity_ref = any(
            normalized.get(key)
            for key in ("entity_id", "entity_name", "entity", "associated_entities")
        )
        if default_entity_name and not has_entity_ref:
            normalized["associated_entities"] = [default_entity_name]

    return normalized


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    # Reap a supervisor launched by this process; kill(pid, 0) alone sees zombies
    # as alive forever. A later dispatcher invocation is not its parent.
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
        if reaped == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_process_group(pid: int | None, grace_seconds: float = 2.0) -> None:
    """Stop the session created by launch_job, including surviving descendants."""
    if not pid or pid <= 1 or pid == os.getpgrp():
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        process_alive(pid)  # Reap our own supervisor if it exited on SIGTERM.
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            # An inaccessible group is not proof of termination. In particular,
            # a dying macOS child can briefly deny signal 0 before it is reaped.
            # Keep the bounded grace period and retain the final KILL/error path.
            pass
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process_alive(pid)


def process_exit_path(output_file: Path) -> Path:
    return output_file.with_name(output_file.name + ".exit.json")


def supervise_process(db_path: Path, run_id: int, output_file: Path, command: list[str]) -> int:
    """Persist the child status across one-shot dispatcher invocations.

    The parent reserves the run and its PID in one transaction. Wait for that
    commit before executing a worker, so a crashed/rolled-back launcher cannot
    leave an unregistered research process behind.
    """
    receipt = {"run_id": run_id, "supervisor_pid": os.getpid()}
    exit_code = 1
    try:
        deadline = time.monotonic() + 10
        with sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            while True:
                row = db.execute("SELECT status, pid FROM dispatch_runs WHERE id=?", (run_id,)).fetchone()
                if row and row[1] == os.getpid():
                    if row[0] != "running":
                        raise RuntimeError("Launch reservation is no longer running")
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Launch reservation was not committed")
                time.sleep(0.05)
        # Inherit the supervisor's session/process group and stdout/stderr.
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL)
        exit_code = proc.wait()
    except Exception as exc:  # noqa: BLE001 - record launch failures for the next supervisor pass
        receipt["error"] = str(exc)
    receipt["exit_code"] = exit_code
    receipt["completed_at"] = utcnow().isoformat()
    target = process_exit_path(output_file)
    temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(receipt, sort_keys=True))
    temporary.replace(target)
    return exit_code if exit_code >= 0 else 128 - exit_code


def latest_artifact_mtime(staging_dir: str | None) -> datetime | None:
    if not staging_dir:
        return None
    path = Path(staging_dir)
    if not path.exists():
        return None
    mtimes = [datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(tzinfo=None)]
    for child in path.glob("*"):
        if child.is_file():
            mtimes.append(datetime.fromtimestamp(child.stat().st_mtime, timezone.utc).replace(tzinfo=None))
    return max(mtimes) if mtimes else None


def load_json_file(path: Path) -> Any:
    raw = path.read_text().strip()
    if not raw:
        return None
    return json.loads(raw)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    raw = path.read_text().splitlines()
    for idx, line in enumerate(raw, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{idx}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path.name}:{idx}: record must be an object")
        records.append(record)
    return records


def read_staged_bundle(staging_dir: Path) -> tuple[dict[str, Any], str]:
    """Parse and fingerprint exactly the bytes the reviewer/importer will use."""
    bundle: dict[str, Any] = {}
    digest = hashlib.sha256()
    for name in ALL_ARTIFACTS:
        file_path = staging_dir / name
        if not file_path.is_file():
            if name in REQUIRED_ARTIFACTS:
                raise ValueError(f"Missing required artifact: {name}")
            raw = None
        else:
            raw = file_path.read_bytes()
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(raw).digest() if raw is not None else b"missing")
        if name.endswith(".jsonl"):
            records = []
            for index, line in enumerate((raw or b"").decode().splitlines(), 1):
                if line.strip():
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError(f"{name}:{index}: record must be an object")
                    records.append(record)
            bundle[name] = records
        elif name == "run.json":
            bundle[name] = json.loads(raw)
        else:
            bundle[name] = raw.decode()
    run = bundle["run.json"]
    if not isinstance(run, dict):
        raise ValueError("run.json must contain an object")
    required = {"summary", "status", "sources_checked", "counts", "notes", "lead_disposition"}
    if required - run.keys():
        raise ValueError(f"run.json missing fields: {', '.join(sorted(required - run.keys()))}")
    if not isinstance(run["summary"], str) or not run["summary"].strip():
        raise ValueError("run.json summary must be nonempty text")
    if run["status"] not in {"completed", "partial", "blocked", "dead_end"}:
        raise ValueError("run.json has an invalid research status")
    disposition = run["lead_disposition"]
    if disposition not in {"keep_open", "completed", "blocked", "dead_end"}:
        raise ValueError("run.json has an invalid lead_disposition")
    if disposition == "completed" and run["status"] != "completed":
        raise ValueError("Only completed research may propose completing its lead")
    if not isinstance(run["sources_checked"], list) or not all(isinstance(s, str) for s in run["sources_checked"]):
        raise ValueError("run.json sources_checked must be a list of source names")
    if not isinstance(run["notes"], list) or not all(isinstance(note, str) for note in run["notes"]):
        raise ValueError("run.json notes must be a list of strings")
    if not isinstance(run["counts"], dict):
        raise ValueError("run.json counts must be an object")
    for kind in ("findings", "leads", "entities", "connections"):
        actual = len(bundle[f"candidate_{kind}.jsonl"])
        expected = run["counts"].get(kind, 0)
        if type(expected) is not int or expected != actual:
            raise ValueError(f"run.json {kind} count does not match its artifact ({actual})")
    for record in bundle["candidate_findings.jsonl"]:
        staged_finding_arguments(record)
    return bundle, digest.hexdigest()


def staged_finding_arguments(record: dict[str, Any]) -> dict[str, Any]:
    """The artifact boundary uses the same fields as the canonical finding writer."""
    target = record.get("target_name") or record.get("target")
    if not target or not record.get("summary") or not record.get("claim_type"):
        raise ValueError("Staged findings require target_name, summary, and claim_type")
    refs = record.get("evidence_ids")
    quotes = record.get("source_quotes")
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref.strip() for ref in refs):
        raise ValueError("Staged findings require a nonempty evidence_ids list")
    if not isinstance(quotes, dict) or any(
        not isinstance(quotes.get(ref), dict)
        or not isinstance(quotes[ref].get("quote"), str)
        or not quotes[ref]["quote"].strip()
        for ref in refs
    ):
        raise ValueError("Every staged evidence reference requires an exact source quote")
    sources = record.get("source_datasets") or record.get("sources")
    if isinstance(sources, str):
        sources = [source.strip() for source in sources.split(",") if source.strip()]
    return {
        "target_name": target,
        "summary": record["summary"],
        "finding_type": record.get("finding_type") or record.get("type"),
        "detail": record.get("detail"),
        "evidence_ids": refs,
        "source_quotes": quotes,
        "source_datasets": sources,
        "confidence": record.get("confidence", "medium"),
        "claim_type": record["claim_type"],
        "date_of_event": record.get("date_of_event") or record.get("date"),
        "lead_id": record.get("lead_id"),
        "thread_id": record.get("thread_id"),
        "profile_id": record.get("profile_id"),
    }


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def sanitize_insert_payload(columns: set[str], mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key in columns and value is not None}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def archive_raw_records(
    db: sqlite3.Connection,
    run_id: int,
    artifact_name: str,
    records: list[dict[str, Any]],
) -> int:
    captured = 0
    for index, record in enumerate(records, start=1):
        record_json = canonical_json(record)
        db.execute(
            """
            INSERT INTO dispatch_import_raw (
                run_id, artifact_name, record_index, record_json, record_hash
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                artifact_name,
                index,
                record_json,
                hashlib.sha256(record_json.encode("utf-8")).hexdigest(),
            ),
        )
        captured += 1
    return captured


def log_import_diagnostic(
    db: sqlite3.Connection,
    run_id: int,
    artifact_name: str,
    record_index: int | None,
    status: str,
    reason: str,
    record: dict[str, Any] | None = None,
    severity: str = "warning",
) -> None:
    db.execute(
        """
        INSERT INTO dispatch_import_diagnostics (
            run_id, artifact_name, record_index, severity, status, reason, record_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            artifact_name,
            record_index,
            severity,
            status,
            reason,
            canonical_json(record) if record is not None else None,
        ),
    )


ALLOWED_CONNECTION_TYPES = {
    "financial",
    "social",
    "legal",
    "intelligence",
    "employment",
    "familial",
    "corporate",
    "advisory",
    "political",
    "owns",
    "controls",
    "funds",
    "subsidiary_of",
    "contracts_with",
    "successor_to",
    "shares_officer",
    "supplies",
}


def normalize_connection_type(raw_value: str | None) -> str:
    if not raw_value:
        return "corporate"

    value = raw_value.strip().lower().replace("-", "_")
    if value in ALLOWED_CONNECTION_TYPES:
        return value

    mapping = {
        "founder_executive": "controls",
        "founded_and_controlled": "controls",
        "co_defendant": "legal",
        "co_conspirator": "legal",
        "romantic_financial": "social",
        "former_business_partner": "corporate",
        "defense_attorney": "legal",
        "site_operator": "corporate",
        "co_owner": "owns",
        "employee_conspirator": "employment",
        "former_employee": "employment",
        "original_incorporator": "corporate",
        "co_owner_operator": "owns",
        "regulatory_oversight": "legal",
        "related_entity_unconfirmed": "corporate",
        "family_co_conspirator": "familial",
        "prosecutor_defendant": "legal",
        "sponsor_operator": "funds",
    }
    return mapping.get(value, "corporate")


def count_duplicate_findings(db: sqlite3.Connection, records: list[dict[str, Any]]) -> int:
    columns = get_columns(db, "findings")
    if "summary" not in columns or "target_name" not in columns:
        return 0
    duplicates = 0
    for record in records:
        target = record.get("target_name") or record.get("target")
        summary = record.get("summary")
        if not target or not summary:
            continue
        row = db.execute(
            "SELECT 1 FROM findings WHERE target_name = ? AND summary = ? LIMIT 1",
            (target, summary),
        ).fetchone()
        duplicates += 1 if row else 0
    return duplicates


def count_duplicate_leads(db: sqlite3.Connection, records: list[dict[str, Any]]) -> int:
    duplicates = 0
    for record in records:
        title = record.get("title")
        if not title:
            continue
        row = db.execute("SELECT 1 FROM leads WHERE title = ? LIMIT 1", (title,)).fetchone()
        duplicates += 1 if row else 0
    return duplicates


def count_duplicate_entities(db: sqlite3.Connection, records: list[dict[str, Any]]) -> int:
    duplicates = 0
    for record in records:
        if record.get("record_type", "entity") != "entity":
            continue
        name = record.get("name")
        jurisdiction = record.get("jurisdiction")
        if not name:
            continue
        row = db.execute(
            "SELECT 1 FROM entities WHERE name = ? AND COALESCE(jurisdiction,'') = COALESCE(?, '') LIMIT 1",
            (name, jurisdiction),
        ).fetchone()
        duplicates += 1 if row else 0
    return duplicates


def count_duplicate_connections(db: sqlite3.Connection, records: list[dict[str, Any]]) -> int:
    if not table_exists(db, "connections"):
        return 0
    duplicates = 0
    for record in records:
        a = record.get("person_a")
        b = record.get("person_b")
        rel = normalize_connection_type(record.get("relationship_type"))
        if not a or not b or not rel:
            continue
        row = db.execute(
            """
            SELECT 1 FROM connections
            WHERE person_a = ? AND person_b = ? AND relationship_type = ?
            LIMIT 1
            """,
            (a, b, rel),
        ).fetchone()
        duplicates += 1 if row else 0
    return duplicates


def inspect_staging_bundle(
    db: sqlite3.Connection,
    run: sqlite3.Row | dict[str, Any],
    config: dict[str, Any],
    update_db: bool = False,
) -> dict[str, Any]:
    run_dict = dict(run)
    staging_dir = run_dict.get("staging_dir")
    expected = json.loads(run_dict.get("expected_artifacts") or "[]") or list(REQUIRED_ARTIFACTS)
    path = Path(staging_dir) if staging_dir else None

    artifact_presence: dict[str, bool] = {}
    artifact_counts = {
        "findings": 0,
        "leads": 0,
        "entities": 0,
        "connections": 0,
    }
    duplicate_risks = dict(artifact_counts)
    validation_error = None
    files: dict[str, Path] = {}

    for artifact in expected + OPTIONAL_ARTIFACTS:
        artifact_path = path / artifact if path else None
        files[artifact] = artifact_path
        artifact_presence[artifact] = bool(artifact_path and artifact_path.exists())

    bundle: dict[str, Any] = {}
    bundle_hash = None
    try:
        if not path or not path.is_dir():
            raise ValueError("Missing staging directory")
        unknown = set(expected) - set(ALL_ARTIFACTS)
        if unknown:
            raise ValueError(f"Unknown required artifacts: {', '.join(sorted(unknown))}")
        bundle, bundle_hash = read_staged_bundle(path)
    except (ValueError, OSError, UnicodeError) as exc:
        validation_error = str(exc)
    findings_records = bundle.get("candidate_findings.jsonl", [])
    leads_records = bundle.get("candidate_leads.jsonl", [])
    entities_records = bundle.get("candidate_entities.jsonl", [])
    connections_records = bundle.get("candidate_connections.jsonl", [])

    artifact_counts["findings"] = len(findings_records)
    artifact_counts["leads"] = len(leads_records)
    artifact_counts["entities"] = len(entities_records)
    artifact_counts["connections"] = len(connections_records)

    if validation_error is None:
        duplicate_risks["findings"] = count_duplicate_findings(db, findings_records)
        duplicate_risks["leads"] = count_duplicate_leads(db, leads_records)
        duplicate_risks["entities"] = count_duplicate_entities(db, entities_records)
        duplicate_risks["connections"] = count_duplicate_connections(db, connections_records)

    last_at = latest_artifact_mtime(staging_dir)
    ready = validation_error is None and all(artifact_presence.get(name, False) for name in expected)

    if update_db and run_dict.get("id"):
        db.execute(
            """
            INSERT INTO dispatch_staging (
                run_id, staging_dir, required_artifacts_json, artifact_presence_json,
                artifact_counts_json, duplicate_risks_json, validation_error, last_artifact_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                staging_dir=excluded.staging_dir,
                required_artifacts_json=excluded.required_artifacts_json,
                artifact_presence_json=excluded.artifact_presence_json,
                artifact_counts_json=excluded.artifact_counts_json,
                duplicate_risks_json=excluded.duplicate_risks_json,
                validation_error=excluded.validation_error,
                last_artifact_at=excluded.last_artifact_at
            """,
            (
                run_dict["id"],
                staging_dir,
                json.dumps(expected, sort_keys=True),
                json.dumps(artifact_presence, sort_keys=True),
                json.dumps(artifact_counts, sort_keys=True),
                json.dumps(duplicate_risks, sort_keys=True),
                validation_error,
                last_at.isoformat() if last_at else None,
            ),
        )
        if validation_error:
            db.execute(
                """
                UPDATE dispatch_staging
                SET review_status = CASE
                    WHEN review_status = 'imported' THEN review_status
                    ELSE 'invalid'
                END
                WHERE run_id = ?
                """,
                (run_dict["id"],),
            )
        db.execute(
            "UPDATE dispatch_runs SET last_artifact_at = ?, health_detail = ? WHERE id = ?",
            (last_at.isoformat() if last_at else None, validation_error, run_dict["id"]),
        )

    return {
        "ready": ready,
        "bundle": bundle,
        "bundle_hash": bundle_hash,
        "artifact_presence": artifact_presence,
        "artifact_counts": artifact_counts,
        "duplicate_risks": duplicate_risks,
        "validation_error": validation_error,
        "last_artifact_at": last_at.isoformat() if last_at else None,
    }


def refresh_running_health(db: sqlite3.Connection, config: dict[str, Any]) -> None:
    stall_seconds = config.get("stall_seconds", DEFAULT_CONFIG["stall_seconds"])
    running = get_running_instances(db)
    for run in running:
        health_status = "healthy"
        detail = None
        last_at = latest_artifact_mtime(run["staging_dir"])
        started = datetime.fromisoformat(run["started_at"])
        baseline = last_at or started
        idle_seconds = (utcnow() - baseline).total_seconds()

        if run["review_required"]:
            if idle_seconds > stall_seconds:
                health_status = "stalled"
                detail = f"No staged artifact updates for {int(idle_seconds)}s"
            elif last_at:
                detail = f"Last staged artifact update {int(idle_seconds)}s ago"
            else:
                detail = "Awaiting first staged artifact"

            db.execute(
                """
                INSERT INTO dispatch_staging (run_id, staging_dir, last_artifact_at, required_artifacts_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    staging_dir = excluded.staging_dir,
                    last_artifact_at = excluded.last_artifact_at,
                    required_artifacts_json = COALESCE(dispatch_staging.required_artifacts_json, excluded.required_artifacts_json)
                """,
                (
                    run["id"],
                    run["staging_dir"],
                    last_at.isoformat() if last_at else None,
                    run["expected_artifacts"] or json.dumps(REQUIRED_ARTIFACTS),
                ),
            )

        db.execute(
            """
            UPDATE dispatch_runs
            SET health_status = ?, health_detail = ?, last_artifact_at = ?
            WHERE id = ?
            """,
            (health_status, detail, last_at.isoformat() if last_at else None, run["id"]),
        )
    db.commit()


def insert_failure_run(
    db: sqlite3.Connection,
    contract: TaskContract,
    hash_key: str,
    health_status: str,
    error: str,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO dispatch_runs (
            run_type, job_type, target, status, prompt_hash, exit_code, error,
            lead_id, hypothesis_id, brief, skill_name, expected_artifacts, priority,
            timeout_seconds, cost_cap_usd, review_required, orchestrator, backend,
            task_contract_json, staging_dir, health_status, health_detail, completed_at
        ) VALUES (?, ?, ?, 'failed', ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            contract.job_type,
            contract.job_type,
            contract.target,
            hash_key,
            error,
            contract.lead_id,
            contract.hypothesis_id,
            contract.brief,
            contract.skill_name,
            json.dumps(contract.expected_artifacts or REQUIRED_ARTIFACTS),
            contract.priority,
            contract.timeout_seconds,
            contract.cost_cap_usd,
            1 if contract.review_required else 0,
            contract.orchestrator,
            contract.backend,
            contract.to_json(),
            None,
            health_status,
            error,
        ),
    )
    db.commit()
    return cursor.lastrowid


def launch_job(
    db: sqlite3.Connection,
    config: dict[str, Any],
    contract: TaskContract,
    backend: ClaudeBackend | None = None,
    dry_run: bool = False,
) -> bool:
    backend = backend or ClaudeBackend()
    # Resolve a caller's interactive default once, before hashing or preflight.
    if not contract.profile_id:
        contract = replace(contract, profile_id=resolve_active_profile_id(db))
    hash_key = prompt_hash(contract)

    row = db.execute(
        "SELECT id FROM dispatch_runs WHERE prompt_hash = ? AND status = 'running'",
        (hash_key,),
    ).fetchone()
    if row:
        print(f"  [skip] {contract.job_type} target={contract.target or 'batch'} already running (#{row['id']})")
        return False

    if dry_run:
        print(
            f"  [dry-run] Would launch {contract.job_type} target={contract.target or 'batch'} "
            f"review_required={contract.review_required} orchestrator={contract.orchestrator}"
        )
        return True

    ok, preflight_status, detail = backend.preflight()
    if not ok:
        run_id = insert_failure_run(db, contract, hash_key, preflight_status, detail)
        print(f"  [error] preflight failed for {contract.job_type} (#{run_id}): {detail}")
        return False

    if not contract.profile_id and contract.job_type != "build_infra":
        message = "No investigation profile resolved; pin ITHILDIN_PROFILE before launching scoped work"
        insert_failure_run(db, contract, hash_key, "context_missing", message)
        print(f"  [error] {message}")
        return False

    prompt = build_prompt(contract.job_type, contract.target, contract.brief)
    skill_path = SKILL_PATHS.get(contract.job_type)
    skill_content = skill_path.read_text() if skill_path and skill_path.exists() else None

    staging_dir: Path | None = None
    system_prompts = [skill_content] if skill_content else []
    expected_artifacts = contract.expected_artifacts or list(REQUIRED_ARTIFACTS)

    if contract.review_required:
        staging_dir = create_staging_dir(config, contract, hash_key)
        manifest = artifact_manifest(staging_dir, expected_artifacts)
        system_prompts.append(build_staging_instruction(contract, manifest))
        output_file = Path(manifest["raw_output.json"])
        stderr_file = Path(manifest["stderr.log"])
    else:
        output_dir = Path(tempfile.mkdtemp(prefix=f"dispatch-{contract.job_type}-"))
        output_file = output_dir / "raw_output.json"
        stderr_file = output_dir / "stderr.log"

    cmd = backend.build_command(prompt, config, [p for p in system_prompts if p])
    database_file = next(row[2] for row in db.execute("PRAGMA database_list") if row[1] == "main")
    if not database_file:
        raise ValueError("Launching a worker requires a persistent dispatcher database")
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env["ITHILDIN_DB_PATH"] = str(Path(database_file).resolve())
    if contract.profile_id:
        env["ITHILDIN_PROFILE"] = contract.profile_id

    # Serialize the duplicate check and reservation across dispatcher processes.
    # Preflight and prompt construction remain outside the write lock.
    if db.in_transaction:
        raise ValueError("launch_job requires a connection with no pending transaction")
    proc = None
    try:
        db.execute("BEGIN IMMEDIATE")
        duplicate = db.execute(
            "SELECT id FROM dispatch_runs WHERE prompt_hash=? AND status='running'",
            (hash_key,),
        ).fetchone()
        if duplicate:
            db.rollback()
            print(f"  [skip] {contract.job_type} already running (#{duplicate['id']})")
            return False
        cursor = db.execute(
            """
            INSERT INTO dispatch_runs (
                run_type, job_type, target, status, prompt_hash, output_file,
                lead_id, hypothesis_id, brief, skill_name, expected_artifacts, priority,
                timeout_seconds, cost_cap_usd, review_required, orchestrator, backend,
                task_contract_json, staging_dir, health_status, health_detail
            ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contract.job_type, contract.job_type, contract.target, hash_key, str(output_file),
                contract.lead_id, contract.hypothesis_id, contract.brief, contract.skill_name,
                json.dumps(expected_artifacts), contract.priority, contract.timeout_seconds,
                contract.cost_cap_usd, int(contract.review_required), contract.orchestrator,
                contract.backend, contract.to_json(), str(staging_dir) if staging_dir else None,
                "healthy", detail,
            ),
        )
        run_id = cursor.lastrowid
        if staging_dir:
            db.execute(
                """INSERT INTO dispatch_staging (run_id, staging_dir, required_artifacts_json)
                   VALUES (?, ?, ?)""",
                (run_id, str(staging_dir), json.dumps(expected_artifacts)),
            )
        supervisor_command = [
            sys.executable, str(Path(__file__).resolve()), "_supervise",
            "--database", env["ITHILDIN_DB_PATH"], "--run-id", str(run_id),
            "--output-file", str(output_file), "--", *cmd,
        ]
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w") as out_fh, stderr_file.open("w") as err_fh:
            proc = subprocess.Popen(
                supervisor_command, stdin=subprocess.DEVNULL, stdout=out_fh, stderr=err_fh,
                cwd=str(PROJECT_ROOT), env=env, start_new_session=True,
            )
        db.execute("UPDATE dispatch_runs SET pid=? WHERE id=?", (proc.pid, run_id))
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if proc is not None:
            terminate_process_group(proc.pid)
            proc.wait(timeout=5)
        run_id = insert_failure_run(db, contract, hash_key, "launch_failed", str(exc))
        print(f"  [error] launch failed for {contract.job_type} (#{run_id}): {exc}")
        return False
    print(
        f"  [launch] {contract.job_type} target={contract.target or 'batch'} PID={proc.pid} "
        f"orchestrator={contract.orchestrator} review_required={contract.review_required}"
    )
    return True


# ── Queue depth queries ──────────────────────────────────────────────

def is_system_paused(db: sqlite3.Connection) -> bool:
    try:
        row = db.execute("SELECT value FROM system_state WHERE key='paused'").fetchone()
        return bool(row and row["value"] == "true")
    except sqlite3.OperationalError:
        return False


def get_queue_depths(db: sqlite3.Connection, profile_id: str | None = None) -> dict[str, Any]:
    depths: dict[str, Any] = {}
    profile_sql, profile_params = _profile_filter_clause(profile_id)

    row = db.execute(
        f"SELECT COUNT(*) AS n FROM leads WHERE status='pending_triage'{profile_sql}",
        profile_params,
    ).fetchone()
    depths["pending_triage"] = row["n"]

    row = db.execute(
        f"SELECT COUNT(*) AS n FROM leads WHERE status='open'{profile_sql}",
        profile_params,
    ).fetchone()
    depths["open_leads"] = row["n"]

    row = db.execute(
        f"SELECT COUNT(*) AS n FROM leads WHERE status='open' AND priority IN ('critical','high'){profile_sql}",
        profile_params,
    ).fetchone()
    depths["high_critical_open"] = row["n"]

    try:
        rows = db.execute(
            f"""
            SELECT COALESCE(depth_tier, 'untiered') AS tier, COUNT(*) AS n
            FROM leads WHERE status='open'{profile_sql} GROUP BY tier
            """,
            profile_params,
        ).fetchall()
        for tier_row in rows:
            depths[f"tier_{tier_row['tier']}"] = tier_row["n"]
    except sqlite3.OperationalError:
        pass

    row = db.execute(
        "SELECT COUNT(*) AS n FROM infra_requests WHERE status IN ('open','evaluating')"
    ).fetchone()
    depths["infra_open"] = row["n"]

    last_auto = db.execute(
        "SELECT MAX(started_at) AS t FROM dispatch_runs WHERE run_type='auto_leads' AND status='completed'"
    ).fetchone()
    since = last_auto["t"] if last_auto and last_auto["t"] else "1970-01-01"
    row = db.execute(
        f"SELECT COUNT(*) AS n FROM leads WHERE status='completed' AND completed_at > ?{profile_sql}",
        [since] + profile_params,
    ).fetchone()
    depths["completions_since_last_auto"] = row["n"]

    analysis_skills = [
        "analyze_network",
        "generate_hunches",
        "timeline_analysis",
        "systemic_analysis",
    ]
    findings_total = db.execute("SELECT COUNT(*) AS n FROM findings").fetchone()["n"]

    for skill in analysis_skills:
        try:
            last = db.execute(
                """
                SELECT findings_at_start, completed_at
                FROM analysis_runs
                WHERE skill_name = ? AND status = 'completed'
                ORDER BY completed_at DESC LIMIT 1
                """,
                (skill.replace("_", "-"),),
            ).fetchone()
            if last:
                depths[f"{skill}_new_findings"] = findings_total - (last["findings_at_start"] or 0)
                depths[f"{skill}_last_run"] = last["completed_at"]
            else:
                depths[f"{skill}_new_findings"] = findings_total
                depths[f"{skill}_last_run"] = None
        except sqlite3.OperationalError:
            depths[f"{skill}_new_findings"] = findings_total
            depths[f"{skill}_last_run"] = None

    return depths


def get_running_instances(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM dispatch_runs WHERE status='running' ORDER BY started_at"
    ).fetchall()


def any_running(db: sqlite3.Connection, run_type: str) -> bool:
    row = db.execute(
        "SELECT COUNT(*) AS n FROM dispatch_runs WHERE status='running' AND run_type=?",
        (run_type,),
    ).fetchone()
    return row["n"] > 0


def count_running(db: sqlite3.Connection, run_type: str) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS n FROM dispatch_runs WHERE status='running' AND run_type=?",
        (run_type,),
    ).fetchone()
    return row["n"]


def get_running_lead_ids(db: sqlite3.Connection) -> list[int]:
    return [
        int(row["lead_id"])
        for row in db.execute(
            """
            SELECT lead_id FROM dispatch_runs
            WHERE status='running'
              AND run_type IN ('pursue_lead','deep_investigate','trace_entity','investigate_person','investigate_infra')
              AND lead_id IS NOT NULL
            """
        ).fetchall()
    ]


def _profile_filter_clause(profile_id: str | None, column: str = "profile_id") -> tuple[str, list[Any]]:
    if not profile_id:
        return "", []
    return f" AND {column} = ?", [profile_id]


def _lead_sort_key(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        PRIORITY_RANK.get(row["priority"], 99),
        row["created_at"] or "",
        row["id"],
    )


def _normalize_cluster_text(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.lower()
    lowered = re.sub(r"\btrw\b", "the real world", lowered)
    lowered = re.sub(r"\([^)]*\)", " ", lowered)
    lowered = lowered.replace("&", " and ")
    lowered = lowered.replace("/", " ")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _lead_cluster_phrases(row: sqlite3.Row) -> set[str]:
    phrases: set[str] = set()
    for source_text in [row["target_name"], row["title"]]:
        normalized = _normalize_cluster_text(source_text)
        if not normalized:
            continue
        tokens = [token for token in normalized.split() if token and token not in LEAD_CLUSTER_STOPWORDS]
        max_n = min(4, len(tokens))
        for n in range(max_n, 1, -1):
            for i in range(len(tokens) - n + 1):
                gram = tokens[i:i + n]
                if not any(len(token) > 2 for token in gram):
                    continue
                phrases.add(" ".join(gram))
    return phrases


def get_next_lead_id(
    db: sqlite3.Connection,
    profile_id: str | None = None,
    for_skill: str | None = None,
) -> str | None:
    running_lead_ids = get_running_lead_ids(db)
    placeholders = ",".join("?" for _ in running_lead_ids) if running_lead_ids else ""
    exclude_sql = f" AND id NOT IN ({placeholders})" if running_lead_ids else ""
    profile_sql, profile_params = _profile_filter_clause(profile_id)

    if for_skill:
        skill_map = {"pursue_lead": "/pursue-lead", "deep_investigate": "/deep-investigate"}
        skill_value = skill_map.get(for_skill, for_skill)
        query = f"""
            SELECT id FROM leads
            WHERE status = 'open' AND recommended_skill = ?{profile_sql}{exclude_sql}
            ORDER BY
                CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                              WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
                created_at ASC
            LIMIT 1
        """
        row = db.execute(query, [skill_value] + profile_params + running_lead_ids).fetchone()
        if row:
            return str(row["id"])

    query = f"""
        SELECT id FROM leads
        WHERE status = 'open' AND priority IN ('critical','high'){profile_sql}{exclude_sql}
        ORDER BY
            CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 END,
            created_at ASC
        LIMIT 1
    """
    row = db.execute(query, profile_params + running_lead_ids).fetchone()
    return str(row["id"]) if row else None


def get_next_infra_id(db: sqlite3.Connection) -> str | None:
    running_targets = [
        r["target"]
        for r in db.execute(
            """
            SELECT target FROM dispatch_runs
            WHERE status='running' AND run_type='build_infra'
            """
        ).fetchall()
    ]
    placeholders = ",".join("?" for _ in running_targets) if running_targets else "''"
    query = f"""
        SELECT id FROM infra_requests
        WHERE status IN ('open','evaluating')
        AND CAST(id AS TEXT) NOT IN ({placeholders})
        ORDER BY
            CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                          WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
            created_at ASC
        LIMIT 1
    """
    row = db.execute(query, running_targets).fetchone()
    return str(row["id"]) if row else None


def check_daily_budget(db: sqlite3.Connection, config: dict[str, Any]) -> tuple[float, float, bool]:
    limit = float(config.get("daily_budget_usd", DEFAULT_CONFIG["daily_budget_usd"]))
    today = utcnow().strftime("%Y-%m-%d")
    row = db.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM dispatch_runs WHERE started_at >= ?",
        (today,),
    ).fetchone()
    spent = float(row["total"] or 0)
    return spent, limit, spent < limit


# ── Finalization / supervision ───────────────────────────────────────

def finalize_run(db: sqlite3.Connection, run: sqlite3.Row, config: dict[str, Any]) -> None:
    output_file = Path(run["output_file"]) if run["output_file"] else None
    exit_code = None
    cost = None
    session_id = None
    error_msg = None
    findings_added = 0
    leads_created = 0
    health_status = "completed"
    health_detail = run["health_detail"]
    errors = []
    try:
        if output_file is None:
            raise ValueError("No process output path recorded")
        receipt = load_json_file(process_exit_path(output_file))
        if (not isinstance(receipt, dict) or receipt.get("run_id") != run["id"]
                or receipt.get("supervisor_pid") != run["pid"]
                or type(receipt.get("exit_code")) is not int):
            raise ValueError("Process exit receipt does not match this run")
        exit_code = receipt["exit_code"]
        if exit_code != 0:
            errors.append(receipt.get("error") or f"Worker exited with status {exit_code}")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"Process exit status unavailable: {exc}")

    if output_file and output_file.exists():
        try:
            data = load_json_file(output_file)
            if not isinstance(data, dict) or not data:
                raise ValueError("Worker output must be a nonempty JSON object")
            if data.get("is_error") or str(data.get("subtype", "")).startswith("error"):
                errors.append(f"Worker reported an error: {data.get('result') or data.get('subtype')}")
            cost = data.get("total_cost_usd") or data.get("cost_usd") or data.get("costUSD")
            session_id = data.get("session_id") or data.get("sessionId")
            result = data.get("result", "")
            if isinstance(result, str):
                finding_match = re.search(r"(\d+)\s+finding", result, flags=re.I)
                lead_match = re.search(r"(\d+)\s+lead", result, flags=re.I)
                if finding_match:
                    findings_added = int(finding_match.group(1))
                if lead_match:
                    leads_created = int(lead_match.group(1))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Failed to parse JSON output: {exc}")
    else:
        errors.append("No output file found")

    if run["review_required"]:
        inspection = inspect_staging_bundle(db, run, config, update_db=True)
        findings_added = inspection["artifact_counts"]["findings"]
        leads_created = inspection["artifact_counts"]["leads"]
        if inspection["validation_error"]:
            health_status = "invalid_artifacts"
            health_detail = inspection["validation_error"]
            errors.append(inspection["validation_error"])

    error_msg = "; ".join(errors) or None
    status = "completed" if exit_code == 0 and not errors else "failed"
    if status == "failed" and health_status == "completed":
        health_status = "failed"
        health_detail = error_msg
    last_artifact_at = latest_artifact_mtime(run["staging_dir"])
    cursor = db.execute(
        """
        UPDATE dispatch_runs SET
            status = ?, completed_at = CURRENT_TIMESTAMP, exit_code = ?,
            cost_usd = ?, session_id = ?, findings_added = ?, leads_created = ?,
            error = ?, health_status = ?, health_detail = ?, last_artifact_at = ?
        WHERE id = ? AND status = 'running'
        """,
        (
            status,
            exit_code,
            cost,
            session_id,
            findings_added,
            leads_created,
            error_msg,
            health_status,
            health_detail,
            last_artifact_at.isoformat() if last_artifact_at else run["last_artifact_at"],
            run["id"],
        ),
    )
    db.commit()
    if not cursor.rowcount:
        return  # A concurrent stop/timeout already chose the terminal outcome.
    print(
        f"  [{status}] #{run['id']} {run['run_type']} target={run['target'] or 'batch'} "
        f"health={health_status} cost=${float(cost or 0):.2f}"
    )


def reap_completed(db: sqlite3.Connection, config: dict[str, Any]) -> None:
    timeout_default = config.get("timeout_seconds", DEFAULT_CONFIG["timeout_seconds"])
    running = get_running_instances(db)
    refresh_running_health(db, config)

    for run in running:
        pid = run["pid"]
        started = datetime.fromisoformat(run["started_at"])
        elapsed = (utcnow() - started).total_seconds()
        timeout = run["timeout_seconds"] or timeout_default

        if not process_alive(pid):
            # A failed leader can leave a child alive in the recorded group.
            terminate_process_group(pid)
            finalize_run(db, run, config)
        elif elapsed > timeout:
            terminate_process_group(pid)
            db.execute(
                """
                UPDATE dispatch_runs
                SET status='timeout', completed_at=CURRENT_TIMESTAMP,
                    error=?, health_status='timeout', health_detail=?
                WHERE id=?
                """,
                (
                    f"Exceeded timeout of {timeout}s",
                    f"Exceeded timeout of {timeout}s",
                    run["id"],
                ),
            )
            db.commit()
            print(f"  [timeout] #{run['id']} {run['run_type']} (PID {pid}, {elapsed:.0f}s)")


# ── Dispatch cycle ───────────────────────────────────────────────────

def dispatch_cycle(config: dict[str, Any], dry_run: bool = False) -> None:
    db = get_db()
    ensure_dispatch_table(db)

    reap_completed(db, config)
    profile_id = resolve_active_profile_id(db)

    if is_system_paused(db):
        print("  [paused] system_state.paused=true — no launches")
        db.close()
        return

    spent, limit, within_budget = check_daily_budget(db, config)
    if not within_budget:
        print(f"  [budget] Daily budget exhausted (${spent:.2f}/${limit:.2f})")
        db.close()
        return

    queues = get_queue_depths(db, profile_id=profile_id)
    running = get_running_instances(db)
    total_running = len(running)
    max_concurrent = config.get("max_concurrent", DEFAULT_CONFIG["max_concurrent"])

    if total_running >= max_concurrent:
        print(f"  [full] {total_running}/{max_concurrent} slots occupied — no launches")
        db.close()
        return

    slots_available = max_concurrent - total_running
    launches: list[tuple[str, str | None]] = []
    triggers = config.get("triggers", {})

    trig = triggers.get("triage", {})
    if queues["pending_triage"] >= trig.get("min_pending", 1) and not any_running(db, "triage"):
        launches.append(("triage", None))

    trig = triggers.get("build_infra", {})
    if queues["infra_open"] >= trig.get("min_open", 1) and not any_running(db, "build_infra"):
        next_infra = get_next_infra_id(db)
        if next_infra:
            launches.append(("build_infra", next_infra))

    trig = triggers.get("pursue_lead", {})
    max_research = config.get("max_research_agents", DEFAULT_CONFIG["max_research_agents"])
    research_running = count_running(db, "pursue_lead") + count_running(db, "deep_investigate")
    if queues["high_critical_open"] >= trig.get("min_high_critical", 1) and research_running < max_research:
        deep_lead = get_next_lead_id(db, profile_id=profile_id, for_skill="deep_investigate")
        if deep_lead and not any_running(db, "deep_investigate"):
            launches.append(("deep_investigate", deep_lead))
        else:
            next_lead = (
                get_next_lead_id(db, profile_id=profile_id, for_skill="pursue_lead")
                or get_next_lead_id(db, profile_id=profile_id)
            )
            if next_lead:
                launches.append(("pursue_lead", next_lead))

        while research_running + sum(
            1 for launch_type, _ in launches if launch_type in ("pursue_lead", "deep_investigate")
        ) < max_research:
            another = get_next_lead_id(db, profile_id=profile_id)
            used = {target for _, target in launches}
            if another and another not in used:
                launches.append(("pursue_lead", another))
            else:
                break

    trig = triggers.get("auto_leads", {})
    if queues["completions_since_last_auto"] >= trig.get("completions_since_last", 10) and not any_running(db, "auto_leads"):
        launches.append(("auto_leads", None))

    max_analysis = config.get("max_analysis_agents", DEFAULT_CONFIG["max_analysis_agents"])
    analysis_running = sum(
        count_running(db, skill)
        for skill in ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]
    )
    if analysis_running < max_analysis:
        for skill in ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]:
            trig = triggers.get(skill, {})
            min_new = trig.get("new_findings_since_last", 50)
            cooldown_hours = trig.get("cooldown_hours", 48)
            new_findings = queues.get(f"{skill}_new_findings", 0)
            last_run = queues.get(f"{skill}_last_run")

            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run)
                    hours_since = (utcnow() - last_dt).total_seconds() / 3600
                    if hours_since < cooldown_hours:
                        continue
                except (TypeError, ValueError):
                    pass

            if new_findings >= min_new and not any_running(db, skill):
                launches.append((skill, None))
                break

    launches = launches[:slots_available]
    if not launches:
        print("  [idle] No launches needed")
        db.close()
        return

    for job_type, target in launches:
        job_defaults = config.get("job_defaults", {}).get(job_type, {})
        contract = TaskContract(
            job_type=job_type,
            target=target,
            profile_id=profile_id,
            lead_id=int(target) if job_type in {"pursue_lead", "deep_investigate"} and str(target).isdigit() else None,
            skill_name=JOB_DEFS[job_type].get("skill_name"),
            expected_artifacts=job_defaults.get("expected_artifacts", list(REQUIRED_ARTIFACTS)),
            priority=job_defaults.get("priority", "medium"),
            timeout_seconds=job_defaults.get("timeout_seconds", config.get("timeout_seconds")),
            cost_cap_usd=job_defaults.get("cost_cap_usd"),
            # Research/analysis honors the staged default. Maintenance retains
            # its existing direct operation; explicit research config can opt out.
            review_required=(job_type not in {"triage", "build_infra", "auto_leads"}
                             and bool(job_defaults.get("review_required", True))),
            orchestrator="auto",
        )
        launch_job(db, config, contract, dry_run=dry_run)

    db.close()


# ── Planning / review / import helpers ───────────────────────────────

def recommend_next_wave(
    db: sqlite3.Connection,
    profile_id: str | None = None,
    limit: int = 15,
) -> list[sqlite3.Row]:
    running_lead_ids = get_running_lead_ids(db)
    profile_sql, profile_params = _profile_filter_clause(profile_id)
    exclude_sql = ""
    params: list[Any] = list(profile_params)
    if running_lead_ids:
        exclude_sql = " AND id NOT IN ({})".format(",".join("?" for _ in running_lead_ids))
        params.extend(running_lead_ids)
    try:
        return db.execute(
            f"""
            SELECT id, title, target_name, priority, depth_tier, recommended_skill, category
            FROM leads
            WHERE status='open'{profile_sql}{exclude_sql}
            ORDER BY
                CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                              WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
                created_at ASC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
    except sqlite3.OperationalError:
        return []


def recommend_related_groups(
    db: sqlite3.Connection,
    profile_id: str | None = None,
    limit: int = 4,
    max_group_leads: int = 4,
) -> list[dict[str, Any]]:
    running_lead_ids = get_running_lead_ids(db)
    profile_sql, profile_params = _profile_filter_clause(profile_id)
    exclude_sql = ""
    params: list[Any] = list(profile_params)
    if running_lead_ids:
        exclude_sql = " AND id NOT IN ({})".format(",".join("?" for _ in running_lead_ids))
        params.extend(running_lead_ids)

    rows = db.execute(
        f"""
        SELECT id, title, target_name, priority, depth_tier, recommended_skill, category, created_at
        FROM leads
        WHERE status='open'{profile_sql}{exclude_sql}
        ORDER BY
            CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                          WHEN 'medium' THEN 2 WHEN 'low' THEN 3 END,
            created_at ASC
        """,
        params,
    ).fetchall()

    groups: dict[str, dict[int, sqlite3.Row]] = defaultdict(dict)
    for row in rows:
        for phrase in _lead_cluster_phrases(row):
            groups[phrase][row["id"]] = row

    candidates: list[dict[str, Any]] = []
    for phrase, mapping in groups.items():
        members = sorted(mapping.values(), key=_lead_sort_key)
        if len(members) < 2:
            continue
        candidates.append(
            {
                "label": phrase,
                "rows": members[:max_group_leads],
                "score": (len(members) * 100) + (len(phrase.split()) * 10),
                "member_ids": tuple(row["id"] for row in members),
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["label"]))
    selected: list[dict[str, Any]] = []
    seen_signatures: set[tuple[int, ...]] = set()
    for candidate in candidates:
        signature = candidate["member_ids"]
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def hydrate_contract(args: argparse.Namespace, config: dict[str, Any]) -> TaskContract:
    job_type = normalize_job_type(args.type)
    job_defaults = config.get("job_defaults", {}).get(job_type, {})
    skill_name = args.skill_name or JOB_DEFS[job_type].get("skill_name")
    expected_artifacts = args.expected_artifact or job_defaults.get("expected_artifacts", list(REQUIRED_ARTIFACTS))
    review_required = args.review_required
    if review_required is None:
        review_required = job_defaults.get("review_required", False)

    lead_id = args.lead_id
    target = args.target
    if job_type == "pursue_lead" and not lead_id and target and str(target).isdigit():
        lead_id = int(target)
    if lead_id and not target:
        target = str(lead_id)

    profile_id = None
    db = get_db()
    try:
        profile_id = resolve_active_profile_id(db)
    finally:
        db.close()

    return TaskContract(
        job_type=job_type,
        target=target,
        lead_id=lead_id,
        profile_id=profile_id,
        hypothesis_id=args.hypothesis_id,
        brief=args.brief,
        skill_name=skill_name,
        expected_artifacts=list(expected_artifacts),
        priority=args.priority or job_defaults.get("priority", "medium"),
        timeout_seconds=args.timeout_seconds or job_defaults.get("timeout_seconds", config.get("timeout_seconds")),
        cost_cap_usd=args.cost_cap_usd or job_defaults.get("cost_cap_usd"),
        review_required=bool(review_required),
        orchestrator=args.orchestrator or "manual",
    )


def resolve_active_profile_id(db: sqlite3.Connection) -> str | None:
    if os.environ.get("ITHILDIN_PROFILE"):
        return os.environ["ITHILDIN_PROFILE"]
    row = None
    try:
        row = db.execute(
            "SELECT value FROM investigation_config WHERE key = 'active_profile'"
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row and row["value"]:
        return row["value"]

    try:
        row = db.execute(
            "SELECT value FROM system_state WHERE key='active_investigation'"
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row and row["value"]:
        return row["value"]
    return None


def resolve_entity_id(db: sqlite3.Connection, record: dict[str, Any]) -> int:
    entity_id = record.get("entity_id")
    if entity_id:
        return int(entity_id)

    associated = record.get("associated_entities") or []
    if isinstance(associated, str):
        associated = [associated]

    name = (
        record.get("name")
        or record.get("entity_name")
        or record.get("entity")
        or record.get("entity_a_name")
        or record.get("entity_a")
        or record.get("related_entity_name")
        or record.get("entity_b_name")
        or record.get("entity_b")
        or (associated[0] if associated else None)
    )
    if not name:
        raise ValueError("Entity record missing name/entity_name")
    jurisdiction = record.get("jurisdiction")
    row = db.execute(
        "SELECT id FROM entities WHERE name = ? AND COALESCE(jurisdiction,'') = COALESCE(?, '') LIMIT 1",
        (name, jurisdiction),
    ).fetchone()
    if row:
        return int(row["id"])

    entity_columns = get_columns(db, "entities")
    payload = sanitize_insert_payload(
        entity_columns,
        {
            "name": name,
            "entity_type": record.get("entity_type", "unknown"),
            "jurisdiction": jurisdiction,
            "ein": record.get("ein"),
            "address": record.get("address"),
            "status": record.get("status", "active"),
            "source": record.get("source"),
            "notes": record.get("notes"),
            "date_formed": record.get("date_formed"),
        },
    )
    fields = ", ".join(payload)
    placeholders = ", ".join("?" for _ in payload)
    cursor = db.execute(
        f"INSERT INTO entities ({fields}) VALUES ({placeholders})",
        tuple(payload.values()),
    )
    return int(cursor.lastrowid)


def import_findings(
    db: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    run_id: int,
    artifact_name: str = "candidate_findings.jsonl",
) -> int:
    from tools.findings_tracker import add_finding_to_db

    for record in records:
        add_finding_to_db(db, **staged_finding_arguments(record))
    return len(records)


def import_leads(
    db: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    run_id: int,
    artifact_name: str = "candidate_leads.jsonl",
) -> int:
    columns = get_columns(db, "leads")
    inserted = 0
    default_profile_id = resolve_active_profile_id(db)
    for index, record in enumerate(records, start=1):
        title = record.get("title")
        if not title:
            log_import_diagnostic(
                db,
                run_id,
                artifact_name,
                index,
                "missing_required_field",
                "Lead record missing required field: title",
                record,
            )
            continue
        profile_id = record.get("profile_id") or default_profile_id
        # Skip duplicate: an open/in_progress lead with same title already exists
        existing = db.execute(
            "SELECT id FROM leads WHERE title = ? AND profile_id = ? AND status IN ('open', 'in_progress', 'pending_triage') LIMIT 1",
            (title, profile_id),
        ).fetchone()
        if existing:
            log_import_diagnostic(
                db,
                run_id,
                artifact_name,
                index,
                "duplicate_ignored",
                f"Lead with same title already exists as #{existing['id']}",
                record,
            )
            continue
        payload = sanitize_insert_payload(
            columns,
            {
                "title": title,
                "description": record.get("description"),
                "category": record.get("category", "entity"),
                "priority": record.get("priority", "medium"),
                "status": record.get("status", "open"),
                "source": record.get("source", "staged_worker"),
                "target_name": record.get("target_name"),
                "findings": record.get("findings"),
                "thread_id": record.get("thread_id"),
                "profile_id": profile_id,
                "depth_tier": record.get("depth_tier"),
                "recommended_skill": record.get("recommended_skill"),
                "triage_rationale": record.get("triage_rationale"),
                "stop_reason": record.get("stop_reason"),
                "blocked_by_infra_id": record.get("blocked_by_infra_id"),
            },
        )
        fields = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        try:
            db.execute(f"INSERT INTO leads ({fields}) VALUES ({placeholders})", tuple(payload.values()))
        except sqlite3.IntegrityError as exc:
            log_import_diagnostic(
                db,
                run_id,
                artifact_name,
                index,
                "integrity_error",
                f"Lead insert failed: {exc}",
                record,
            )
            continue
        inserted += 1
    return inserted


def import_entities(
    db: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    run_id: int,
    default_entity_name: str | None = None,
    artifact_name: str = "candidate_entities.jsonl",
) -> int:
    inserted = 0
    entity_columns = get_columns(db, "entities")
    role_columns = get_columns(db, "entity_roles") if table_exists(db, "entity_roles") else set()
    addr_columns = get_columns(db, "entity_addresses") if table_exists(db, "entity_addresses") else set()
    relation_columns = get_columns(db, "entity_relations") if table_exists(db, "entity_relations") else set()

    for index, record in enumerate(records, start=1):
        record = normalize_candidate_entity_record(record, default_entity_name=default_entity_name)
        record_type = record.get("record_type", "entity")
        if record_type == "entity":
            payload = sanitize_insert_payload(
                entity_columns,
                {
                    "name": record.get("name"),
                    "entity_type": record.get("entity_type", "unknown"),
                    "jurisdiction": record.get("jurisdiction"),
                    "ein": record.get("ein"),
                    "address": record.get("address"),
                    "status": record.get("status", "active"),
                    "source": record.get("source"),
                    "notes": record.get("notes"),
                    "date_formed": record.get("date_formed"),
                },
            )
            if not payload.get("name"):
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_required_field",
                    "Entity record missing required field: name",
                    record,
                )
                continue
            fields = ", ".join(payload)
            placeholders = ", ".join("?" for _ in payload)
            try:
                db.execute(f"INSERT INTO entities ({fields}) VALUES ({placeholders})", tuple(payload.values()))
                inserted += 1
            except sqlite3.IntegrityError as exc:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "integrity_error",
                    f"Entity insert failed: {exc}",
                    record,
                )
            continue

        if record_type == "role":
            if not role_columns:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_supporting_table",
                    "entity_roles table is unavailable",
                    record,
                )
                continue
            try:
                entity_id = resolve_entity_id(db, record)
            except (ValueError, sqlite3.IntegrityError) as exc:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "entity_resolution_failed",
                    f"Role record could not resolve entity: {exc}",
                    record,
                )
                continue
            payload = sanitize_insert_payload(
                role_columns,
                {
                    "entity_id": entity_id,
                    "person_name": record.get("person_name"),
                    "role": record.get("role"),
                    "date_start": record.get("date_start"),
                    "date_end": record.get("date_end"),
                    "source": record.get("source"),
                },
            )
            if not payload.get("person_name") or not payload.get("role"):
                missing = []
                if not payload.get("person_name"):
                    missing.append("person_name")
                if not payload.get("role"):
                    missing.append("role")
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_required_field",
                    f"Role record missing required field(s): {', '.join(missing)}",
                    record,
                )
                continue
            fields = ", ".join(payload)
            placeholders = ", ".join("?" for _ in payload)
            cursor = db.execute(
                f"INSERT OR IGNORE INTO entity_roles ({fields}) VALUES ({placeholders})",
                tuple(payload.values()),
            )
            if cursor.rowcount:
                inserted += 1
            else:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "duplicate_ignored",
                    "Role record already exists",
                    record,
                    severity="info",
                )
            continue

        if record_type == "address":
            if not addr_columns:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_supporting_table",
                    "entity_addresses table is unavailable",
                    record,
                )
                continue
            associated = record.get("associated_entities") or []
            if isinstance(associated, str):
                associated = [associated]
            entity_refs = associated or [record]
            if not record.get("address"):
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_required_field",
                    "Address record missing required field: address",
                    record,
                )
                continue
            for entity_ref in entity_refs:
                try:
                    entity_id = resolve_entity_id(
                        db,
                        entity_ref if isinstance(entity_ref, dict) else {"name": entity_ref},
                    )
                except (ValueError, sqlite3.IntegrityError) as exc:
                    ref_record = entity_ref if isinstance(entity_ref, dict) else {"name": entity_ref}
                    log_import_diagnostic(
                        db,
                        run_id,
                        artifact_name,
                        index,
                        "entity_resolution_failed",
                        f"Address record could not resolve entity: {exc}",
                        {**record, "entity_ref": ref_record},
                    )
                    continue
                payload = sanitize_insert_payload(
                    addr_columns,
                    {
                        "entity_id": entity_id,
                        "address": record.get("address"),
                        "address_type": record.get("address_type", "registered"),
                        "date_observed": record.get("date_observed"),
                        "source": record.get("source"),
                    },
                )
                if payload.get("address"):
                    fields = ", ".join(payload)
                    placeholders = ", ".join("?" for _ in payload)
                    cursor = db.execute(
                        f"INSERT OR IGNORE INTO entity_addresses ({fields}) VALUES ({placeholders})",
                        tuple(payload.values()),
                    )
                    if cursor.rowcount:
                        inserted += 1
                    else:
                        log_import_diagnostic(
                            db,
                            run_id,
                            artifact_name,
                            index,
                            "duplicate_ignored",
                            "Address record already exists",
                            record,
                            severity="info",
                        )
            continue

        if record_type == "relation":
            if not relation_columns:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_supporting_table",
                    "entity_relations table is unavailable",
                    record,
                )
                continue
            a_name = record.get("entity_a_name") or record.get("entity_a") or record.get("entity_name")
            b_name = record.get("entity_b_name") or record.get("entity_b") or record.get("related_entity_name")
            if not a_name or not b_name:
                missing = []
                if not a_name:
                    missing.append("entity_a_name")
                if not b_name:
                    missing.append("entity_b_name")
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "missing_required_field",
                    f"Relation record missing required field(s): {', '.join(missing)}",
                    record,
                )
                continue
            try:
                entity_a_id = resolve_entity_id(
                    db,
                    {"name": a_name, "jurisdiction": record.get("entity_a_jurisdiction")},
                )
                entity_b_id = resolve_entity_id(
                    db,
                    {"name": b_name, "jurisdiction": record.get("entity_b_jurisdiction")},
                )
            except (ValueError, sqlite3.IntegrityError) as exc:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "entity_resolution_failed",
                    f"Relation record could not resolve entity: {exc}",
                    record,
                )
                continue
            payload = sanitize_insert_payload(
                relation_columns,
                {
                    "entity_a_id": entity_a_id,
                    "entity_b_id": entity_b_id,
                    "relation_type": record.get("relation_type") or record.get("relationship") or "related_to",
                    "description": record.get("description") or record.get("notes"),
                    "source": record.get("source"),
                },
            )
            fields = ", ".join(payload)
            placeholders = ", ".join("?" for _ in payload)
            try:
                db.execute(f"INSERT INTO entity_relations ({fields}) VALUES ({placeholders})", tuple(payload.values()))
            except sqlite3.IntegrityError as exc:
                log_import_diagnostic(
                    db,
                    run_id,
                    artifact_name,
                    index,
                    "integrity_error",
                    f"Relation insert failed: {exc}",
                    record,
                )
                continue
            inserted += 1
            continue

        log_import_diagnostic(
            db,
            run_id,
            artifact_name,
            index,
            "unsupported_record_type",
            f"Unsupported entity record_type: {record_type}",
            record,
        )
    return inserted


def import_connections(
    db: sqlite3.Connection,
    records: list[dict[str, Any]],
    *,
    run_id: int,
    artifact_name: str = "candidate_connections.jsonl",
) -> int:
    if not records or not table_exists(db, "connections"):
        return 0
    columns = get_columns(db, "connections")
    inserted = 0
    for index, record in enumerate(records, start=1):
        a = record.get("person_a")
        b = record.get("person_b")
        rel = normalize_connection_type(record.get("relationship_type"))
        if not a or not b or not rel:
            missing = []
            if not a:
                missing.append("person_a")
            if not b:
                missing.append("person_b")
            if not rel:
                missing.append("relationship_type")
            log_import_diagnostic(
                db,
                run_id,
                artifact_name,
                index,
                "missing_required_field",
                f"Connection record missing required field(s): {', '.join(missing)}",
                record,
            )
            continue
        payload = sanitize_insert_payload(
            columns,
            {
                "person_a": a,
                "person_b": b,
                "relationship_type": rel,
                "description": record.get("description"),
                "strength": record.get("strength", "medium"),
                "date_range": record.get("date_range"),
                "finding_id": record.get("finding_id"),
                "verification_status": record.get("verification_status"),
                "profile_id": record.get("profile_id"),
            },
        )
        fields = ", ".join(payload)
        placeholders = ", ".join("?" for _ in payload)
        cursor = db.execute(
            f"INSERT OR IGNORE INTO connections ({fields}) VALUES ({placeholders})",
            tuple(payload.values()),
        )
        if cursor.rowcount:
            inserted += 1
        else:
            log_import_diagnostic(
                db,
                run_id,
                artifact_name,
                index,
                "duplicate_ignored",
                "Connection record already exists",
                record,
                severity="info",
            )
    return inserted


def approve_staged_run(
    db: sqlite3.Connection, run_id: int, config: dict[str, Any], actor: str, note: str | None = None,
) -> None:
    """Approval binds the reviewed outcome and records to their exact content."""
    db.execute("BEGIN IMMEDIATE")
    try:
        run = db.execute("SELECT * FROM dispatch_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            raise ValueError(f"Run #{run_id} not found")
        if run["status"] != "completed":
            raise ValueError("Only a finished successful worker process can be approved")
        previous = db.execute("SELECT import_status FROM dispatch_staging WHERE run_id=?", (run_id,)).fetchone()
        if previous and previous["import_status"] == "imported":
            raise ValueError(f"Run #{run_id} has already been imported")
        inspection = inspect_staging_bundle(db, run, config, update_db=True)
        if not inspection["ready"]:
            raise ValueError(inspection["validation_error"] or "Required artifacts are missing")
        db.execute(
            """UPDATE dispatch_staging SET review_status='approved', approved_bundle_hash=?,
               review_notes=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE run_id=?""",
            (inspection["bundle_hash"], note, actor, run_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def import_staged_run(
    db: sqlite3.Connection,
    run_id: int,
    config: dict[str, Any],
    actor: str,
    force: bool = False,
) -> dict[str, int]:
    # Keep the lock from the eligibility check through canonical insertion and the
    # receipt. No separate connection may write as part of this transaction.
    db.execute("BEGIN IMMEDIATE")
    try:
        run = db.execute("SELECT * FROM dispatch_runs WHERE id=?", (run_id,)).fetchone()
        staging = db.execute("SELECT * FROM dispatch_staging WHERE run_id=?", (run_id,)).fetchone()
        if not run or not staging:
            raise ValueError(f"Run #{run_id} has no staged artifact record")
        if staging["import_status"] == "imported":
            counts = json.loads(staging["imported_counts_json"] or "{}")
            db.commit()
            return counts
        if run["status"] != "completed":
            raise ValueError("Worker process has not completed successfully")
        if staging["review_status"] != "approved" or not staging["approved_bundle_hash"]:
            raise ValueError(f"Run #{run_id} requires approval of its current artifact contents; --force cannot bypass review")
        inspection = inspect_staging_bundle(db, run, config)
        if not inspection["ready"]:
            raise ValueError(inspection["validation_error"] or "Required artifacts are missing")
        if inspection["bundle_hash"] != staging["approved_bundle_hash"]:
            raise ValueError("Staged artifacts changed after approval; review the current bundle again")
        bundle = inspection["bundle"]
        contract = json.loads(run["task_contract_json"] or "{}")
        profile_id = contract.get("profile_id")
        default_entity_name = run["target"] if run["target"] and not str(run["target"]).isdigit() else None
        source_lead = None
        if run["lead_id"]:
            source_lead = db.execute("SELECT * FROM leads WHERE id=?", (run["lead_id"],)).fetchone()
            if not source_lead:
                raise ValueError("Source lead no longer exists")
            if profile_id and source_lead["profile_id"] != profile_id:
                raise ValueError("Source lead does not belong to the task profile")
            profile_id = source_lead["profile_id"]
            default_entity_name = source_lead["target_name"] or default_entity_name
        if not profile_id:
            raise ValueError("Staged task must pin profile_id before import")
        records = {}
        for kind in ("findings", "leads", "entities", "connections"):
            artifact = f"candidate_{kind}.jsonl"
            records[kind] = [dict(record) for record in bundle[artifact]]
            for record in records[kind]:
                if kind != "entities":
                    if record.get("profile_id") not in (None, profile_id):
                        raise ValueError(f"{artifact} contains a record from another profile")
                    record["profile_id"] = profile_id
            archive_raw_records(db, run_id, artifact, bundle[artifact])
        counts = {
            "entities": import_entities(db, records["entities"], run_id=run_id, default_entity_name=default_entity_name),
            "findings": import_findings(db, records["findings"], run_id=run_id),
            "leads": import_leads(db, records["leads"], run_id=run_id),
            "connections": import_connections(db, records["connections"], run_id=run_id),
        }
        invalid = db.execute(
            """SELECT reason FROM dispatch_import_diagnostics WHERE run_id=?
               AND status NOT IN ('duplicate_ignored') ORDER BY id LIMIT 1""", (run_id,),
        ).fetchone()
        if invalid:
            raise ValueError(f"Invalid staged record: {invalid['reason']}")
        disposition = bundle["run.json"]["lead_disposition"]
        if source_lead and disposition != "keep_open":
            if source_lead["status"] not in {"open", "in_progress", "blocked"}:
                raise ValueError("Source lead changed to a terminal state; review its disposition before importing")
            db.execute(
                """UPDATE leads SET status=?, completed_at=CASE WHEN ? IN ('completed','dead_end')
                   THEN CURRENT_TIMESTAMP ELSE NULL END, findings=COALESCE(findings,'') || ? WHERE id=?""",
                (disposition, disposition, f"\n[Reviewed disposition from staged run #{run_id}: {bundle['run.json']['summary']}]", run["lead_id"]),
            )
        db.execute(
            """UPDATE dispatch_staging SET import_status='imported', imported_by=?,
               imported_at=CURRENT_TIMESTAMP, imported_counts_json=?, review_status='imported' WHERE run_id=?""",
            (actor, json.dumps(counts, sort_keys=True), run_id),
        )
        db.execute("UPDATE dispatch_runs SET health_status='completed', health_detail='Imported reviewed artifacts' WHERE id=?", (run_id,))
        db.commit()
        return counts
    except Exception:
        db.rollback()
        raise


# ── Subcommands ──────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> None:
    config = load_config()
    ts = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Dispatcher one-shot ({ts})")
    dispatch_cycle(config, dry_run=args.dry_run)


def cmd_daemon(args: argparse.Namespace) -> None:
    config = load_config()
    interval = args.interval or config.get("poll_interval_seconds", DEFAULT_CONFIG["poll_interval_seconds"])
    print(f"Dispatcher daemon started (poll every {interval}s, Ctrl-C to stop)")
    try:
        while True:
            ts = utcnow().strftime("%H:%M:%S")
            print(f"\n[{ts}] Dispatch cycle")
            try:
                dispatch_cycle(config)
            except Exception as exc:  # noqa: BLE001
                print(f"  [error] {exc}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


def cmd_status(args: argparse.Namespace) -> None:
    db = get_db()
    ensure_dispatch_table(db)
    config = load_config()
    reap_completed(db, config)
    refresh_running_health(db, config)
    profile_id = resolve_active_profile_id(db)
    paused = is_system_paused(db)

    auth_ok, auth_status, auth_detail = ClaudeBackend().preflight()
    max_c = config.get("max_concurrent", DEFAULT_CONFIG["max_concurrent"])
    running = get_running_instances(db)

    print(f"Dispatcher Status ({utcnow().strftime('%Y-%m-%d %H:%M UTC')})")
    print(f"Paused: {'yes' if paused else 'no'}")
    print(f"Active profile: {profile_id or 'none'}")
    print(f"Backend health: {'ok' if auth_ok else auth_status} | {auth_detail.splitlines()[0]}")
    print("=" * 72)

    if running:
        print(f"\nRUNNING ({len(running)}/{max_c} max):")
        for run in running:
            started = datetime.fromisoformat(run["started_at"])
            elapsed = int((utcnow() - started).total_seconds() / 60)
            alive = "alive" if process_alive(run["pid"]) else "dead"
            print(
                f"  #{run['id']:>3} {run['job_type'] or run['run_type']:<18} "
                f"target={run['target'] or 'batch':<18} PID={run['pid'] or '-':<7} "
                f"{elapsed:>3}m health={run['health_status'] or 'healthy'} [{alive}]"
            )
            if run["health_detail"]:
                print(f"       {run['health_detail']}")
    else:
        print(f"\nRUNNING (0/{max_c} max): none")

    cutoff = (utcnow() - timedelta(hours=24)).isoformat()
    recent = db.execute(
        """
        SELECT * FROM dispatch_runs
        WHERE status != 'running' AND started_at > ?
        ORDER BY started_at DESC LIMIT 20
        """,
        (cutoff,),
    ).fetchall()
    if recent:
        print("\nRECENT (24h):")
        for run in recent:
            started = datetime.fromisoformat(run["started_at"])
            ended = datetime.fromisoformat(run["completed_at"]) if run["completed_at"] else utcnow()
            duration = int((ended - started).total_seconds() / 60)
            print(
                f"  #{run['id']:>3} {run['job_type'] or run['run_type']:<18} "
                f"status={run['status']:<9} health={run['health_status'] or '-':<18} "
                f"{duration:>3}m findings={run['findings_added'] or 0} leads={run['leads_created'] or 0}"
            )
            if run["error"]:
                print(f"       error: {run['error'][:120]}")
    else:
        print("\nRECENT (24h): none")

    review_rows = db.execute(
        """
        SELECT ds.run_id, dr.job_type, dr.target, ds.review_status, ds.import_status,
               ds.validation_error, ds.artifact_counts_json, ds.duplicate_risks_json
        FROM dispatch_staging ds
        JOIN dispatch_runs dr ON dr.id = ds.run_id
        WHERE dr.review_required = 1
        ORDER BY dr.started_at DESC
        LIMIT 20
        """
    ).fetchall()
    if review_rows:
        print("\nREVIEW QUEUE:")
        for row in review_rows:
            counts = json.loads(row["artifact_counts_json"] or "{}")
            risks = json.loads(row["duplicate_risks_json"] or "{}")
            print(
                f"  #{row['run_id']:>3} {row['job_type']:<18} review={row['review_status']:<9} "
                f"import={row['import_status']:<8} target={row['target'] or 'batch'}"
            )
            print(
                f"       candidates: findings={counts.get('findings', 0)} "
                f"leads={counts.get('leads', 0)} entities={counts.get('entities', 0)} "
                f"connections={counts.get('connections', 0)}"
            )
            if any(risks.values()):
                print(f"       duplicate_risk: {risks}")
            if row["validation_error"]:
                print(f"       validation: {row['validation_error']}")
    else:
        print("\nREVIEW QUEUE: none")

    queues = get_queue_depths(db, profile_id=profile_id)
    print("\nQUEUES:")
    print(f"  {queues['pending_triage']:>5} pending_triage")
    print(f"  {queues['infra_open']:>5} infra open")
    print(f"  {queues['open_leads']:>5} open leads in profile ({queues['high_critical_open']} high/critical)")
    print(f"  {queues['completions_since_last_auto']:>5} completions in profile since last auto_leads")

    print("\nANALYSIS:")
    for skill in ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]:
        new_findings = queues.get(f"{skill}_new_findings", "?")
        last_run = queues.get(f"{skill}_last_run")
        trigger = config.get("triggers", {}).get(skill, {})
        threshold = trigger.get("new_findings_since_last", "?")
        cooldown = trigger.get("cooldown_hours", "?")
        ready = "READY" if isinstance(new_findings, int) and isinstance(threshold, int) and new_findings >= threshold else "wait"
        print(
            f"  {skill:<20} +{new_findings} findings (threshold={threshold}, cooldown={cooldown}h) "
            f"last={last_run or 'never'} [{ready}]"
        )

    db.close()


def cmd_plan(args: argparse.Namespace) -> None:
    db = get_db()
    ensure_dispatch_table(db)
    config = load_config()
    reap_completed(db, config)
    refresh_running_health(db, config)
    profile_id = resolve_active_profile_id(db)

    queues = get_queue_depths(db, profile_id=profile_id)
    candidates = recommend_next_wave(db, profile_id=profile_id)
    related_groups = recommend_related_groups(db, profile_id=profile_id)
    max_c = config.get("max_concurrent", DEFAULT_CONFIG["max_concurrent"])
    max_research = config.get("max_research_agents", DEFAULT_CONFIG["max_research_agents"])
    max_analysis = config.get("max_analysis_agents", DEFAULT_CONFIG["max_analysis_agents"])

    print(f"Dispatch Plan ({utcnow().strftime('%Y-%m-%d %H:%M UTC')})")
    print("=" * 72)
    print(f"Active profile: {profile_id or 'none'}")
    print(f"Slots: {max_c} total / {max_research} research / {max_analysis} analysis")
    print("Suggested next wave:")
    if queues["pending_triage"] > 0:
        print(f"  - triage: {queues['pending_triage']} pending_triage leads need scheduling")
    if queues["infra_open"] > 0:
        print(f"  - build_infra: {queues['infra_open']} open/evaluating infra requests")
    if queues["high_critical_open"] > 0:
        print(f"  - pursue_lead/deep_investigate: {queues['high_critical_open']} high/critical open leads")

    if candidates:
        print("\nTop lead candidates:")
        for row in candidates[:10]:
            print(
                f"  - lead #{row['id']}: {row['title']} "
                f"[priority={row['priority']}, tier={row['depth_tier'] or 'untiered'}, "
                f"recommended={row['recommended_skill'] or 'n/a'}]"
            )
    else:
        print("\nNo open lead candidates found.")

    if related_groups:
        print("\nRelated clusters:")
        for group in related_groups:
            members = ", ".join(
                f"#{row['id']} {row['recommended_skill'] or 'n/a'}"
                for row in group["rows"]
            )
            print(f"  - {group['label']}: {members}")

    ready_analysis = []
    for skill in ["analyze_network", "generate_hunches", "timeline_analysis", "systemic_analysis"]:
        new_findings = queues.get(f"{skill}_new_findings", 0)
        threshold = config.get("triggers", {}).get(skill, {}).get("new_findings_since_last", 50)
        if isinstance(new_findings, int) and new_findings >= threshold:
            ready_analysis.append((skill, new_findings, threshold))
    if ready_analysis:
        print("\nAnalysis jobs ready:")
        for skill, new_findings, threshold in ready_analysis:
            print(f"  - {skill}: +{new_findings} findings since last run (threshold={threshold})")

    db.close()


def cmd_launch(args: argparse.Namespace) -> None:
    config = load_config()
    db = get_db()
    ensure_dispatch_table(db)

    contract = hydrate_contract(args, config)
    print(
        f"Manual launch: {contract.job_type} target={contract.target or 'batch'} "
        f"orchestrator={contract.orchestrator} review_required={contract.review_required}"
    )
    launch_job(db, config, contract, dry_run=args.dry_run)
    db.close()


def cmd_review(args: argparse.Namespace) -> None:
    db = get_db()
    ensure_dispatch_table(db)
    config = load_config()

    if args.approve is not None:
        try:
            approve_staged_run(db, args.approve, config, args.reviewer, args.note)
            print(f"Approved run #{args.approve} for import.")
        except ValueError as exc:
            print(f"Run #{args.approve} cannot be approved: {exc}")
        finally:
            db.close()
        return

    if args.reject is not None:
        db.execute(
            """
            UPDATE dispatch_staging
            SET review_status='rejected', review_notes=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP
            WHERE run_id = ?
            """,
            (args.note, args.reviewer, args.reject),
        )
        db.commit()
        print(f"Rejected run #{args.reject}.")
        db.close()
        return

    query = """
        SELECT dr.*, ds.review_status, ds.import_status
        FROM dispatch_runs dr
        JOIN dispatch_staging ds ON ds.run_id = dr.id
        WHERE dr.review_required = 1
    """
    params: list[Any] = []
    if args.run_id is not None:
        query += " AND dr.id = ?"
        params.append(args.run_id)
    query += " ORDER BY dr.started_at DESC"

    rows = db.execute(query, params).fetchall()
    if not rows:
        print("No staged runs found.")
        db.close()
        return

    for row in rows:
        inspection = inspect_staging_bundle(db, row, config, update_db=True)
        print(
            f"Run #{row['id']} {row['job_type'] or row['run_type']} target={row['target'] or 'batch'} "
            f"review={row['review_status']} import={row['import_status']}"
        )
        print(
            f"  ready={inspection['ready']} validation={inspection['validation_error'] or 'ok'} "
            f"last_artifact_at={inspection['last_artifact_at'] or 'n/a'}"
        )
        print(f"  counts={inspection['artifact_counts']}")
        print(f"  duplicate_risks={inspection['duplicate_risks']}")
        missing = [name for name, present in inspection["artifact_presence"].items() if not present and name in REQUIRED_ARTIFACTS]
        if missing:
            print(f"  missing_required={missing}")
        print(f"  staging_dir={row['staging_dir']}")
    db.commit()
    db.close()


def cmd_import(args: argparse.Namespace) -> None:
    db = get_db()
    ensure_dispatch_table(db)
    config = load_config()

    if args.all_approved:
        run_ids = [
            row["run_id"]
            for row in db.execute(
                "SELECT run_id FROM dispatch_staging WHERE review_status='approved' AND import_status='pending'"
            ).fetchall()
        ]
    elif args.run_id is not None:
        run_ids = [args.run_id]
    else:
        print("Specify --run-id N or --all-approved.")
        db.close()
        return

    if not run_ids:
        print("No approved staged runs to import.")
        db.close()
        return

    for run_id in run_ids:
        try:
            counts = import_staged_run(db, run_id, config, actor=args.actor, force=args.force)
            print(f"Imported run #{run_id}: {counts}")
        except Exception as exc:  # noqa: BLE001
            db.execute(
                """
                UPDATE dispatch_staging
                SET import_status='failed', review_notes=COALESCE(review_notes, '') || ?
                WHERE run_id = ? AND import_status != 'imported'
                """,
                (f"\nImport failed: {exc}", run_id),
            )
            db.commit()
            print(f"Failed to import run #{run_id}: {exc}")

    db.close()


def cmd_stop(args: argparse.Namespace) -> None:
    db = get_db()
    ensure_dispatch_table(db)
    running = get_running_instances(db)
    if not running:
        print("No running instances to stop.")
        db.close()
        return

    selected = []
    for row in running:
        if args.run_id and str(row["id"]) != str(args.run_id):
            continue
        selected.append(row)

    if not selected:
        print("No matching running instances to stop.")
        db.close()
        return

    for run in selected:
        pid = run["pid"]
        print(f"  Stopping #{run['id']} {run['job_type'] or run['run_type']} process group {pid}...")
        terminate_process_group(pid)
        db.execute(
            """
            UPDATE dispatch_runs
            SET status='failed', completed_at=CURRENT_TIMESTAMP, error='Manually stopped',
                health_status='failed', health_detail='Manually stopped'
            WHERE id = ?
            """,
            (run["id"],),
        )
        db.commit()
        print(f"    Marked #{run['id']} as failed")

    db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dispatch headless Claude Code investigation agents")
    sub = parser.add_subparsers(dest="command")
    p_supervisor = sub.add_parser("_supervise", help=argparse.SUPPRESS)
    p_supervisor.add_argument("--database", type=Path, required=True)
    p_supervisor.add_argument("--run-id", type=int, required=True)
    p_supervisor.add_argument("--output-file", type=Path, required=True)
    p_supervisor.add_argument("worker_command", nargs=argparse.REMAINDER)

    p_run = sub.add_parser("run", help="One-shot: check queues and launch needed agents")
    p_run.add_argument("--dry-run", action="store_true", help="Show what would launch without launching")

    p_daemon = sub.add_parser("daemon", help="Loop: poll and launch on schedule")
    p_daemon.add_argument("--interval", type=int, help="Override poll interval (seconds)")

    sub.add_parser("status", help="Show running/recent dispatch runs, auth health, and review queue")
    sub.add_parser("plan", help="Show suggested next-wave launches with rationale")
    sub.add_parser("recommend", help="Alias for plan")

    p_launch = sub.add_parser("launch", help="Manually launch a staged or legacy worker")
    p_launch.add_argument("type", help=f"Job type to launch: {', '.join(sorted(JOB_DEFS))}")
    p_launch.add_argument("target", nargs="?", help="Target name or ID for the job")
    p_launch.add_argument("--lead-id", type=int, help="Lead ID tied to the job")
    p_launch.add_argument("--hypothesis-id", type=int, help="Hypothesis ID tied to the job")
    p_launch.add_argument("--brief", help="Additional task brief to append to the worker prompt")
    p_launch.add_argument("--skill-name", help="Override the default worker skill name")
    p_launch.add_argument(
        "--expected-artifact",
        action="append",
        dest="expected_artifact",
        help="Artifact filename expected from the staged bundle (repeatable)",
    )
    p_launch.add_argument("--priority", choices=["critical", "high", "medium", "low"])
    p_launch.add_argument("--timeout-seconds", type=int, help="Per-run timeout override")
    p_launch.add_argument("--cost-cap-usd", type=float, help="Soft cost cap recorded on the task contract")
    p_launch.add_argument(
        "--review-required",
        dest="review_required",
        action="store_true",
        help="Require staged review/import for this launch",
    )
    p_launch.add_argument(
        "--no-review-required",
        dest="review_required",
        action="store_false",
        help="Launch in legacy direct mode",
    )
    p_launch.set_defaults(review_required=None)
    p_launch.add_argument("--orchestrator", help="Record the orchestrator identity (for wrapper skills)")
    p_launch.add_argument("--dry-run", action="store_true", help="Show the launch contract without launching")

    p_review = sub.add_parser("review", help="Inspect, approve, or reject staged run artifacts")
    p_review.add_argument("--run-id", type=int, help="Inspect a specific staged run")
    p_review.add_argument("--approve", type=int, help="Approve a staged run for import")
    p_review.add_argument("--reject", type=int, help="Reject a staged run")
    p_review.add_argument("--note", help="Optional review note")
    p_review.add_argument("--reviewer", default="manual", help="Reviewer identity to store")

    p_import = sub.add_parser("import", help="Import approved staged artifacts into canonical tables")
    p_import.add_argument("--run-id", type=int, help="Import a specific staged run")
    p_import.add_argument("--all-approved", action="store_true", help="Import all approved staged runs")
    p_import.add_argument("--actor", default="manual", help="Actor identity to store on import")
    p_import.add_argument("--force", action="store_true", help="Compatibility option; current artifact approval is always required")

    p_stop = sub.add_parser("stop", help="Stop running instances")
    p_stop.add_argument("run_id", nargs="?", help="Specific dispatch_run ID to stop (default: all)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "_supervise":
        command = args.worker_command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("_supervise requires a worker command after --")
        sys.exit(supervise_process(args.database, args.run_id, args.output_file, command))
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "daemon":
        cmd_daemon(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command in {"plan", "recommend"}:
        cmd_plan(args)
    elif args.command == "launch":
        try:
            cmd_launch(args)
        except ValueError as exc:
            print(f"  [error] {exc}")
            sys.exit(1)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "stop":
        cmd_stop(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
