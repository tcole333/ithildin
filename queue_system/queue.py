#!/usr/bin/env python3
"""
SQLite-backed job queue for the autonomous research platform.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "investigation.db"
DEFAULT_BUSY_TIMEOUT_MS = 5000
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 0.1


class JobQueue:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.busy_timeout_ms = busy_timeout_ms
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
        return db

    def _with_retry(self, func):
        last_err = None
        for attempt in range(self.retry_attempts):
            try:
                return func()
            except sqlite3.OperationalError as exc:
                last_err = exc
                msg = str(exc).lower()
                if "database is locked" in msg or "database is busy" in msg:
                    time.sleep(self.retry_backoff * (attempt + 1))
                    continue
                raise
        if last_err:
            raise last_err

    def _ensure_schema(self) -> None:
        def _apply():
            db = self._connect()
            try:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS job_queue (
                        id TEXT PRIMARY KEY,
                        job_type TEXT NOT NULL,
                        domain TEXT NOT NULL CHECK (domain IN (
                            'discovery', 'investigation', 'analysis', 'understanding',
                            'curation', 'infrastructure', 'system'
                        )),
                        priority INTEGER NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
                        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
                            'pending', 'claimed', 'in_progress', 'awaiting_review',
                            'completed', 'failed', 'blocked', 'stale', 'cancelled'
                        )),
                        payload TEXT NOT NULL DEFAULT '{}',
                        output TEXT DEFAULT NULL,
                        error_message TEXT DEFAULT NULL,
                        error_traceback TEXT DEFAULT NULL,
                        parent_job_id TEXT REFERENCES job_queue(id) ON DELETE SET NULL,
                        thread_id TEXT REFERENCES job_queue(id) ON DELETE SET NULL,
                        claimed_by TEXT DEFAULT NULL,
                        claimed_at TIMESTAMP DEFAULT NULL,
                        started_at TIMESTAMP DEFAULT NULL,
                        completed_at TIMESTAMP DEFAULT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        max_attempts INTEGER NOT NULL DEFAULT 3,
                        retry_delay_seconds INTEGER DEFAULT 300,
                        timeout_seconds INTEGER DEFAULT 1800,
                        stale_after TIMESTAMP DEFAULT NULL,
                        scheduled_for TIMESTAMP DEFAULT NULL,
                        cron_expression TEXT DEFAULT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT DEFAULT NULL,
                        tags TEXT DEFAULT '[]',
                        workdir_path TEXT DEFAULT NULL,
                        source_trigger TEXT DEFAULT NULL,
                        source_finding_id INTEGER DEFAULT NULL,
                        source_lead_id INTEGER DEFAULT NULL,
                        search_queries TEXT DEFAULT '[]'
                    );

                    CREATE TABLE IF NOT EXISTS job_dependencies (
                        job_id TEXT NOT NULL REFERENCES job_queue(id) ON DELETE CASCADE,
                        depends_on_job_id TEXT NOT NULL REFERENCES job_queue(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (job_id, depends_on_job_id)
                    );

                    CREATE TABLE IF NOT EXISTS job_events (
                        id TEXT PRIMARY KEY,
                        job_id TEXT NOT NULL REFERENCES job_queue(id) ON DELETE CASCADE,
                        event_type TEXT NOT NULL CHECK (event_type IN (
                            'created', 'claimed', 'started', 'progress', 'completed',
                            'failed', 'blocked', 'unblocked', 'stale', 'cancelled',
                            'retry_scheduled', 'spawned_child', 'dependency_added'
                        )),
                        payload TEXT DEFAULT NULL,
                        agent_id TEXT DEFAULT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS agent_instances (
                        id TEXT PRIMARY KEY,
                        persona TEXT NOT NULL,
                        status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'stopped')),
                        current_job_id TEXT REFERENCES job_queue(id) ON DELETE SET NULL,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        jobs_completed INTEGER DEFAULT 0,
                        jobs_failed INTEGER DEFAULT 0,
                        capabilities TEXT DEFAULT '[]',
                        version TEXT DEFAULT '1.0.0'
                    );

                    CREATE TABLE IF NOT EXISTS queue_metrics (
                        id TEXT PRIMARY KEY,
                        sampled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        pending_count INTEGER DEFAULT 0,
                        claimed_count INTEGER DEFAULT 0,
                        in_progress_count INTEGER DEFAULT 0,
                        awaiting_review_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        discovery_pending INTEGER DEFAULT 0,
                        investigation_pending INTEGER DEFAULT 0,
                        analysis_pending INTEGER DEFAULT 0,
                        understanding_pending INTEGER DEFAULT 0,
                        infrastructure_pending INTEGER DEFAULT 0,
                        jobs_completed_1h INTEGER DEFAULT 0,
                        jobs_failed_1h INTEGER DEFAULT 0,
                        avg_processing_time_seconds REAL DEFAULT 0,
                        active_agents INTEGER DEFAULT 0,
                        idle_agents INTEGER DEFAULT 0,
                        has_stuck_jobs INTEGER DEFAULT 0,
                        has_failed_jobs INTEGER DEFAULT 0,
                        queue_depth_critical INTEGER DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_by TEXT DEFAULT NULL
                    );

                    INSERT OR IGNORE INTO system_state (key, value) VALUES ('paused', 'false');

                    CREATE INDEX IF NOT EXISTS idx_job_queue_status_priority
                        ON job_queue(status, priority DESC, created_at);
                    CREATE INDEX IF NOT EXISTS idx_job_queue_type_pending
                        ON job_queue(job_type) WHERE status = 'pending';
                    CREATE INDEX IF NOT EXISTS idx_job_queue_domain_pending
                        ON job_queue(domain) WHERE status = 'pending';
                    CREATE INDEX IF NOT EXISTS idx_job_queue_claimed
                        ON job_queue(claimed_by) WHERE status = 'in_progress';
                    CREATE INDEX IF NOT EXISTS idx_job_queue_parent
                        ON job_queue(parent_job_id);
                    CREATE INDEX IF NOT EXISTS idx_job_queue_thread
                        ON job_queue(thread_id);
                    CREATE INDEX IF NOT EXISTS idx_job_queue_scheduled
                        ON job_queue(scheduled_for) WHERE scheduled_for IS NOT NULL;
                    CREATE INDEX IF NOT EXISTS idx_job_queue_pending
                        ON job_queue(status, priority DESC, created_at)
                        WHERE status = 'pending';

                    CREATE INDEX IF NOT EXISTS idx_job_dependencies_blocked
                        ON job_dependencies(depends_on_job_id);

                    CREATE INDEX IF NOT EXISTS idx_job_events_job
                        ON job_events(job_id, created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_job_events_type
                        ON job_events(event_type, created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_agent_instances_status
                        ON agent_instances(status, last_heartbeat);
                    """
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_apply)

    def _parse_json(self, value: Optional[str]) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        for key in ("payload", "output", "tags", "search_queries"):
            data[key] = self._parse_json(data.get(key))
        return data

    def is_paused(self) -> bool:
        def _check():
            db = self._connect()
            try:
                row = db.execute(
                    "SELECT value FROM system_state WHERE key='paused'"
                ).fetchone()
                return row and row["value"] == "true"
            finally:
                db.close()

        return bool(self._with_retry(_check))

    def set_paused(self, paused: bool, updated_by: Optional[str] = None) -> None:
        def _set():
            db = self._connect()
            try:
                db.execute(
                    "UPDATE system_state SET value=?, updated_at=CURRENT_TIMESTAMP, updated_by=? "
                    "WHERE key='paused'",
                    ("true" if paused else "false", updated_by),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_set)

    def create_job(
        self,
        job_type: str,
        domain: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        status: str = "pending",
        created_by: Optional[str] = None,
        tags: Optional[List[str]] = None,
        scheduled_for: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        source_trigger: Optional[str] = None,
        source_finding_id: Optional[int] = None,
        source_lead_id: Optional[int] = None,
    ) -> str:
        job_id = str(uuid4())
        payload_json = json.dumps(payload or {})
        tags_json = json.dumps(tags or [])

        def _insert():
            db = self._connect()
            try:
                db.execute(
                    """
                    INSERT INTO job_queue (
                        id, job_type, domain, priority, status, payload, created_by,
                        tags, scheduled_for, parent_job_id, thread_id,
                        source_trigger, source_finding_id, source_lead_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        job_type,
                        domain,
                        priority,
                        status,
                        payload_json,
                        created_by,
                        tags_json,
                        scheduled_for,
                        parent_job_id,
                        thread_id,
                        source_trigger,
                        source_finding_id,
                        source_lead_id,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO job_events (id, job_id, event_type, payload, agent_id)
                    VALUES (?, ?, 'created', ?, ?)
                    """,
                    (str(uuid4()), job_id, payload_json, created_by),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_insert)
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        def _fetch():
            db = self._connect()
            try:
                row = db.execute(
                    "SELECT * FROM job_queue WHERE id=?",
                    (job_id,),
                ).fetchone()
                return self._row_to_dict(row) if row else None
            finally:
                db.close()

        return self._with_retry(_fetch)

    def list_jobs(
        self,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        def _fetch():
            db = self._connect()
            try:
                clauses = []
                params: List[Any] = []
                if status:
                    clauses.append("status = ?")
                    params.append(status)
                if domain:
                    clauses.append("domain = ?")
                    params.append(domain)
                if job_type:
                    clauses.append("job_type = ?")
                    params.append(job_type)
                where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
                query = (
                    "SELECT * FROM job_queue "
                    f"{where} "
                    "ORDER BY created_at DESC "
                    "LIMIT ?"
                )
                params.append(limit)
                rows = db.execute(query, params).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                db.close()

        return self._with_retry(_fetch)

    def _select_next(self, db: sqlite3.Connection, capabilities: Iterable[str]) -> Optional[sqlite3.Row]:
        clauses = [
            "status = 'pending'",
            "(scheduled_for IS NULL OR scheduled_for <= CURRENT_TIMESTAMP)",
        ]
        params: List[Any] = []
        caps = list(capabilities) if capabilities else []
        if caps:
            placeholders = ",".join("?" for _ in caps)
            clauses.append(f"job_type IN ({placeholders})")
            params.extend(caps)
        where = " AND ".join(clauses)
        query = f"""
            SELECT * FROM job_queue
            WHERE {where}
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        """
        return db.execute(query, params).fetchone()

    def claim_next(self, agent_id: str, capabilities: Optional[Iterable[str]] = None) -> Optional[Dict[str, Any]]:
        if self.is_paused():
            return None

        def _claim():
            db = self._connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                row = self._select_next(db, capabilities or [])
                if not row:
                    db.commit()
                    return None
                updated = db.execute(
                    """
                    UPDATE job_queue
                    SET status='claimed', claimed_by=?, claimed_at=CURRENT_TIMESTAMP, attempts=attempts+1
                    WHERE id=? AND status='pending'
                    """,
                    (agent_id, row["id"]),
                )
                if updated.rowcount != 1:
                    db.commit()
                    return None
                db.execute(
                    "INSERT INTO job_events (id, job_id, event_type, agent_id) "
                    "VALUES (?, ?, 'claimed', ?)",
                    (str(uuid4()), row["id"], agent_id),
                )
                db.commit()
                return self._row_to_dict(row)
            finally:
                db.close()

        return self._with_retry(_claim)

    def start_job(self, job_id: str, agent_id: Optional[str] = None) -> None:
        def _start():
            db = self._connect()
            try:
                db.execute(
                    """
                    UPDATE job_queue
                    SET status='in_progress', started_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (job_id,),
                )
                db.execute(
                    "INSERT INTO job_events (id, job_id, event_type, agent_id) "
                    "VALUES (?, ?, 'started', ?)",
                    (str(uuid4()), job_id, agent_id),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_start)

    def complete_job(self, job_id: str, output: Optional[Dict[str, Any]] = None) -> None:
        output_json = json.dumps(output or {})

        def _complete():
            db = self._connect()
            try:
                db.execute(
                    """
                    UPDATE job_queue
                    SET status='completed', completed_at=CURRENT_TIMESTAMP, output=?
                    WHERE id=?
                    """,
                    (output_json, job_id),
                )
                db.execute(
                    "INSERT INTO job_events (id, job_id, event_type, payload) "
                    "VALUES (?, ?, 'completed', ?)",
                    (str(uuid4()), job_id, output_json),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_complete)

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        error_traceback: Optional[str] = None,
    ) -> None:
        def _fail():
            db = self._connect()
            try:
                db.execute(
                    """
                    UPDATE job_queue
                    SET status='failed', completed_at=CURRENT_TIMESTAMP,
                        error_message=?, error_traceback=?
                    WHERE id=?
                    """,
                    (error_message, error_traceback, job_id),
                )
                db.execute(
                    "INSERT INTO job_events (id, job_id, event_type, payload) "
                    "VALUES (?, ?, 'failed', ?)",
                    (str(uuid4()), job_id, error_message),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_fail)

    def register_agent(self, agent_id: str, persona: str, capabilities: Optional[List[str]] = None) -> None:
        caps_json = json.dumps(capabilities or [])

        def _register():
            db = self._connect()
            try:
                db.execute(
                    """
                    INSERT INTO agent_instances (id, persona, capabilities)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        persona=excluded.persona,
                        capabilities=excluded.capabilities,
                        status='active',
                        last_heartbeat=CURRENT_TIMESTAMP
                    """,
                    (agent_id, persona, caps_json),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_register)

    def update_agent_job(self, agent_id: str, job_id: Optional[str]) -> None:
        def _update():
            db = self._connect()
            try:
                db.execute(
                    """
                    UPDATE agent_instances
                    SET current_job_id=?, last_heartbeat=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (job_id, agent_id),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_update)

    def update_agent_stats(self, agent_id: str, completed: bool) -> None:
        field = "jobs_completed" if completed else "jobs_failed"

        def _update():
            db = self._connect()
            try:
                db.execute(
                    f"""
                    UPDATE agent_instances
                    SET {field} = {field} + 1, last_heartbeat=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (agent_id,),
                )
                db.commit()
            finally:
                db.close()

        self._with_retry(_update)

    def status_counts(self) -> Dict[str, int]:
        def _counts():
            db = self._connect()
            try:
                rows = db.execute(
                    "SELECT status, COUNT(*) as n FROM job_queue GROUP BY status"
                ).fetchall()
                return {row["status"]: row["n"] for row in rows}
            finally:
                db.close()

        return self._with_retry(_counts)

    def domain_counts(self) -> Dict[str, int]:
        def _counts():
            db = self._connect()
            try:
                rows = db.execute(
                    "SELECT domain, COUNT(*) as n FROM job_queue WHERE status='pending' GROUP BY domain"
                ).fetchall()
                return {row["domain"]: row["n"] for row in rows}
            finally:
                db.close()

        return self._with_retry(_counts)
