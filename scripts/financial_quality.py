#!/usr/bin/env python3
"""Financial quality gates and arithmetic sanity checks (DS10-first)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DS10_DB_PATH = PROJECT_ROOT / "datasets" / "lmsband_epstein_files.db"
INV_DB_PATH = PROJECT_ROOT / "investigation.db"
EXPORT_JSON_PATH = PROJECT_ROOT / "content" / "financials" / "ds10-flows.json"
DOCS_DB_PATH = Path("/Users/travcole/projects/epstein-docs/output/documents.db")

RECON_TOLERANCE = 1.0
ROW_TOLERANCE = 0.01


@dataclass(frozen=True)
class IssueKey:
    dataset: str
    record_ref: str
    issue_code: str


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _path_from_args(args, attr: str, default: Path) -> Path:
    raw = getattr(args, attr, None)
    if raw in (None, ""):
        return default
    return Path(raw)


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return bool(row)


def _parse_record_id(record_ref: str, prefix: str) -> int | None:
    if not record_ref.startswith(prefix):
        return None
    try:
        return int(record_ref.split(":", 1)[1])
    except (TypeError, ValueError):
        return None


def _normalize_ocr(text: str | None) -> str:
    if not text:
        return ""
    norm = text.replace("=\n", "")
    norm = " ".join(norm.split())
    return norm.lower()


def quote_matches_ocr(source_quote: str | None, ocr_text: str | None) -> bool:
    q = _normalize_ocr(source_quote)
    doc = _normalize_ocr(ocr_text)
    if not q or not doc:
        return False
    if q in doc:
        return True
    return q[:40] in doc if len(q) >= 40 else False


def ensure_quality_schema(inv_db: sqlite3.Connection) -> None:
    inv_db.executescript(
        """
        CREATE TABLE IF NOT EXISTS quality_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset TEXT NOT NULL,
            run_type TEXT NOT NULL,
            run_id TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running' CHECK(status IN ('running','passed','failed')),
            tool_version TEXT,
            metrics_json TEXT
        );

        CREATE TABLE IF NOT EXISTS quality_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset TEXT NOT NULL,
            record_ref TEXT NOT NULL,
            issue_code TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','waived')),
            details_json TEXT,
            detected_in_run_id INTEGER REFERENCES quality_runs(id),
            resolved_by TEXT,
            resolved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS review_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset TEXT NOT NULL,
            record_ref TEXT NOT NULL,
            tier TEXT NOT NULL CHECK(tier IN ('tier1','tier2')),
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_review','approved','rejected')),
            required_approvals INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS review_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES review_tasks(id),
            reviewer TEXT NOT NULL,
            decision TEXT NOT NULL CHECK(decision IN ('approve','reject','needs_fix')),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, reviewer)
        );

        CREATE INDEX IF NOT EXISTS idx_quality_runs_dataset ON quality_runs(dataset, run_type);
        CREATE INDEX IF NOT EXISTS idx_quality_issues_open ON quality_issues(dataset, severity, status);
        CREATE INDEX IF NOT EXISTS idx_quality_issues_record ON quality_issues(record_ref, issue_code, status);
        CREATE INDEX IF NOT EXISTS idx_review_tasks_record ON review_tasks(dataset, record_ref, status);
        CREATE INDEX IF NOT EXISTS idx_review_decisions_task ON review_decisions(task_id);
        """
    )
    for stmt in [
        "ALTER TABLE findings ADD COLUMN quality_state TEXT DEFAULT 'unchecked'",
        "ALTER TABLE findings ADD COLUMN confidence_requested TEXT",
    ]:
        try:
            inv_db.execute(stmt)
        except sqlite3.OperationalError:
            pass
    inv_db.commit()


def start_quality_run(
    inv_db: sqlite3.Connection,
    *,
    dataset: str,
    run_type: str,
    run_id: str,
) -> int:
    cur = inv_db.execute(
        """
        INSERT INTO quality_runs (dataset, run_type, run_id, status, tool_version)
        VALUES (?, ?, ?, 'running', ?)
        """,
        (dataset, run_type, run_id, "financial_quality_v1"),
    )
    inv_db.commit()
    return int(cur.lastrowid)


def finish_quality_run(
    inv_db: sqlite3.Connection,
    *,
    run_db_id: int,
    status: str,
    metrics: dict,
) -> None:
    inv_db.execute(
        """
        UPDATE quality_runs
        SET status = ?, completed_at = ?, metrics_json = ?
        WHERE id = ?
        """,
        (status, _utcnow(), json.dumps(metrics, sort_keys=True), run_db_id),
    )
    inv_db.commit()


def upsert_issue(
    inv_db: sqlite3.Connection,
    *,
    dataset: str,
    record_ref: str,
    issue_code: str,
    severity: str,
    details: dict,
    run_db_id: int,
) -> int:
    row = inv_db.execute(
        """
        SELECT id
        FROM quality_issues
        WHERE dataset = ? AND record_ref = ? AND issue_code = ? AND status = 'open'
        """,
        (dataset, record_ref, issue_code),
    ).fetchone()
    payload = json.dumps(details, sort_keys=True)
    if row:
        inv_db.execute(
            """
            UPDATE quality_issues
            SET severity = ?, details_json = ?, detected_in_run_id = ?
            WHERE id = ?
            """,
            (severity, payload, run_db_id, row["id"]),
        )
        return int(row["id"])
    cur = inv_db.execute(
        """
        INSERT INTO quality_issues
            (dataset, record_ref, issue_code, severity, status, details_json, detected_in_run_id)
        VALUES (?, ?, ?, ?, 'open', ?, ?)
        """,
        (dataset, record_ref, issue_code, severity, payload, run_db_id),
    )
    return int(cur.lastrowid)


def resolve_stale_issues(
    inv_db: sqlite3.Connection,
    *,
    dataset: str,
    issue_codes: Iterable[str],
    active_keys: set[IssueKey],
) -> int:
    codes = list(issue_codes)
    if not codes:
        return 0
    placeholders = ",".join("?" * len(codes))
    rows = inv_db.execute(
        f"""
        SELECT id, record_ref, issue_code
        FROM quality_issues
        WHERE dataset = ? AND status = 'open' AND issue_code IN ({placeholders})
        """,
        [dataset, *codes],
    ).fetchall()
    resolved = 0
    for row in rows:
        key = IssueKey(dataset=dataset, record_ref=row["record_ref"], issue_code=row["issue_code"])
        if key in active_keys:
            continue
        inv_db.execute(
            """
            UPDATE quality_issues
            SET status = 'resolved', resolved_by = 'financial_quality', resolved_at = ?
            WHERE id = ?
            """,
            (_utcnow(), row["id"]),
        )
        resolved += 1
    if resolved:
        inv_db.commit()
    return resolved


def _ensure_ds10_quality_schema(ds10_db: sqlite3.Connection) -> None:
    ds10_db.executescript(
        """
        CREATE TABLE IF NOT EXISTS ds10_statement_recon (
            id INTEGER PRIMARY KEY,
            statement_id TEXT UNIQUE,
            file_id INTEGER,
            efta_id TEXT,
            account_holder TEXT,
            account_number TEXT,
            statement_start_date TEXT,
            statement_end_date TEXT,
            beginning_balance REAL,
            ending_balance REAL,
            parsed_inflow_total REAL,
            parsed_outflow_total REAL,
            recomputed_ending_balance REAL,
            recon_delta REAL,
            recon_eligible INTEGER DEFAULT 0,
            eligibility_reason TEXT,
            recon_status TEXT DEFAULT 'pending',
            run_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_recon_statement_id ON ds10_statement_recon(statement_id);
        CREATE INDEX IF NOT EXISTS idx_recon_status ON ds10_statement_recon(recon_status);
        CREATE INDEX IF NOT EXISTS idx_recon_run_id ON ds10_statement_recon(run_id);
        """
    )
    for stmt in [
        "ALTER TABLE ds10_transactions ADD COLUMN statement_id TEXT",
        "ALTER TABLE ds10_transactions ADD COLUMN statement_seq INTEGER",
        "ALTER TABLE ds10_transactions ADD COLUMN running_balance REAL",
        "ALTER TABLE ds10_transactions ADD COLUMN running_balance_raw TEXT",
        "ALTER TABLE ds10_transactions ADD COLUMN parsed_from_statement INTEGER DEFAULT 0",
        "ALTER TABLE ds10_transactions ADD COLUMN qa_status TEXT DEFAULT 'pending'",
        "ALTER TABLE ds10_transactions ADD COLUMN qa_flags_json TEXT",
        "ALTER TABLE ds10_transactions ADD COLUMN extract_run_id TEXT",
        "ALTER TABLE ds10_transactions ADD COLUMN parser_version TEXT",
    ]:
        try:
            ds10_db.execute(stmt)
        except sqlite3.OperationalError:
            pass
    ds10_db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_tx_statement_id ON ds10_transactions(statement_id);
        CREATE INDEX IF NOT EXISTS idx_tx_statement_seq ON ds10_transactions(statement_id, statement_seq);
        CREATE INDEX IF NOT EXISTS idx_tx_qa_status ON ds10_transactions(qa_status);
        CREATE INDEX IF NOT EXISTS idx_tx_extract_run_id ON ds10_transactions(extract_run_id);
        """
    )
    ds10_db.commit()


def _build_statement_id(file_id, efta_id, account_number, holder, start_date, end_date):
    # Keep aligned with parse_ds10_financials build_statement_id logic.
    try:
        from tools.parse_ds10_financials import build_statement_id

        return build_statement_id(file_id, efta_id, account_number, holder, start_date, end_date)
    except Exception:
        key = "|".join(
            [
                str(file_id or ""),
                str(efta_id or ""),
                str(account_number or ""),
                str(start_date or ""),
                str(end_date or ""),
                str(holder or ""),
            ]
        )
        return key.replace(" ", "_")


def _collect_balance_context(ds10_db: sqlite3.Connection) -> dict[str, dict]:
    groups = ds10_db.execute(
        """
        SELECT file_id, efta_id, account_holder, account_number,
               MIN(balance_date) AS start_date, MAX(balance_date) AS end_date,
               COUNT(*) AS balance_rows
        FROM ds10_balances
        GROUP BY file_id, efta_id, account_holder, account_number
        """
    ).fetchall()
    out: dict[str, dict] = {}
    for g in groups:
        start_row = ds10_db.execute(
            """
            SELECT balance
            FROM ds10_balances
            WHERE file_id = ? AND efta_id IS ? AND account_holder IS ? AND account_number IS ? AND balance_date = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (g["file_id"], g["efta_id"], g["account_holder"], g["account_number"], g["start_date"]),
        ).fetchone()
        end_row = ds10_db.execute(
            """
            SELECT balance
            FROM ds10_balances
            WHERE file_id = ? AND efta_id IS ? AND account_holder IS ? AND account_number IS ? AND balance_date = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (g["file_id"], g["efta_id"], g["account_holder"], g["account_number"], g["end_date"]),
        ).fetchone()
        statement_id = _build_statement_id(
            g["file_id"],
            g["efta_id"],
            g["account_number"],
            g["account_holder"],
            g["start_date"],
            g["end_date"],
        )
        out[statement_id] = {
            "file_id": g["file_id"],
            "efta_id": g["efta_id"],
            "account_holder": g["account_holder"],
            "account_number": g["account_number"],
            "statement_start_date": g["start_date"],
            "statement_end_date": g["end_date"],
            "beginning_balance": start_row["balance"] if start_row else None,
            "ending_balance": end_row["balance"] if end_row else None,
            "balance_rows": int(g["balance_rows"] or 0),
        }
    return out


def _statement_transactions(ds10_db: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    rows = ds10_db.execute(
        """
        SELECT id, statement_id, statement_seq, tx_date, amount, direction, running_balance
        FROM ds10_transactions
        WHERE statement_id IS NOT NULL AND statement_id != '' AND parsed_from_statement = 1
        ORDER BY statement_id, statement_seq, id
        """
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(row["statement_id"], []).append(row)
    return grouped


def _recon_eligibility(beginning_balance, ending_balance, rows: list[sqlite3.Row], balance_rows: int) -> tuple[bool, str]:
    if beginning_balance is None or ending_balance is None or balance_rows < 2:
        return False, "missing beginning or ending balance"
    rb_count = sum(1 for r in rows if r["running_balance"] is not None)
    if rb_count < 3:
        return False, "fewer than 3 running-balance rows"
    return True, "eligible"


def run_ds10_math_checks(
    *,
    ds10_db: sqlite3.Connection,
    inv_db: sqlite3.Connection,
    run_db_id: int,
    run_id: str,
    with_math: bool,
) -> dict:
    active_keys: set[IssueKey] = set()
    tx_issue_codes = {"MATH001_DIRECTION_AMOUNT", "MATH002_RUNNING_BALANCE_STEP", "MATH003_BEGIN_END_RECON", "MATH003_NON_ELIGIBLE"}

    tx_rows = ds10_db.execute(
        """
        SELECT id, statement_id, amount, direction, qa_status
        FROM ds10_transactions
        WHERE COALESCE(qa_status, 'pending') != 'rejected'
        """
    ).fetchall()

    for row in tx_rows:
        bad = row["amount"] is None or row["amount"] <= 0 or row["direction"] not in ("incoming", "outgoing")
        if not bad:
            continue
        record_ref = f"ds10_transactions:{row['id']}"
        key = IssueKey(dataset="ds10", record_ref=record_ref, issue_code="MATH001_DIRECTION_AMOUNT")
        active_keys.add(key)
        upsert_issue(
            inv_db,
            dataset="ds10",
            record_ref=record_ref,
            issue_code=key.issue_code,
            severity="critical",
            details={"amount": row["amount"], "direction": row["direction"]},
            run_db_id=run_db_id,
        )

    recon_rows_written = 0
    if with_math:
        balance_ctx = _collect_balance_context(ds10_db)
        grouped_tx = _statement_transactions(ds10_db)
        for statement_id, rows in grouped_tx.items():
            ctx = balance_ctx.get(statement_id, {})
            beginning_balance = ctx.get("beginning_balance")
            ending_balance = ctx.get("ending_balance")
            eligible, reason = _recon_eligibility(beginning_balance, ending_balance, rows, int(ctx.get("balance_rows", 0) or 0))

            inflow = sum(float(r["amount"] or 0) for r in rows if r["direction"] == "incoming")
            outflow = sum(float(r["amount"] or 0) for r in rows if r["direction"] == "outgoing")
            recomputed = None
            delta = None
            recon_status = "warn"
            if beginning_balance is not None:
                recomputed = float(beginning_balance) + inflow - outflow
            if recomputed is not None and ending_balance is not None:
                delta = float(recomputed) - float(ending_balance)
                recon_status = "pass" if abs(delta) <= RECON_TOLERANCE else "fail"

            ds10_db.execute(
                """
                INSERT INTO ds10_statement_recon
                    (statement_id, file_id, efta_id, account_holder, account_number,
                     statement_start_date, statement_end_date, beginning_balance, ending_balance,
                     parsed_inflow_total, parsed_outflow_total, recomputed_ending_balance,
                     recon_delta, recon_eligible, eligibility_reason, recon_status, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(statement_id) DO UPDATE SET
                    file_id = excluded.file_id,
                    efta_id = excluded.efta_id,
                    account_holder = excluded.account_holder,
                    account_number = excluded.account_number,
                    statement_start_date = excluded.statement_start_date,
                    statement_end_date = excluded.statement_end_date,
                    beginning_balance = excluded.beginning_balance,
                    ending_balance = excluded.ending_balance,
                    parsed_inflow_total = excluded.parsed_inflow_total,
                    parsed_outflow_total = excluded.parsed_outflow_total,
                    recomputed_ending_balance = excluded.recomputed_ending_balance,
                    recon_delta = excluded.recon_delta,
                    recon_eligible = excluded.recon_eligible,
                    eligibility_reason = excluded.eligibility_reason,
                    recon_status = excluded.recon_status,
                    run_id = excluded.run_id,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    statement_id,
                    ctx.get("file_id"),
                    ctx.get("efta_id"),
                    ctx.get("account_holder"),
                    ctx.get("account_number"),
                    ctx.get("statement_start_date"),
                    ctx.get("statement_end_date"),
                    beginning_balance,
                    ending_balance,
                    inflow,
                    outflow,
                    recomputed,
                    delta,
                    1 if eligible else 0,
                    reason,
                    recon_status,
                    run_id,
                ),
            )
            recon_rows_written += 1

            if not eligible:
                key = IssueKey(dataset="ds10", record_ref=f"ds10_statement:{statement_id}", issue_code="MATH003_NON_ELIGIBLE")
                active_keys.add(key)
                upsert_issue(
                    inv_db,
                    dataset="ds10",
                    record_ref=key.record_ref,
                    issue_code=key.issue_code,
                    severity="warning",
                    details={"eligibility_reason": reason},
                    run_db_id=run_db_id,
                )
                continue

            # MATH003 statement reconciliation.
            if delta is None or abs(delta) > RECON_TOLERANCE:
                key = IssueKey(dataset="ds10", record_ref=f"ds10_statement:{statement_id}", issue_code="MATH003_BEGIN_END_RECON")
                active_keys.add(key)
                upsert_issue(
                    inv_db,
                    dataset="ds10",
                    record_ref=key.record_ref,
                    issue_code=key.issue_code,
                    severity="critical",
                    details={
                        "beginning_balance": beginning_balance,
                        "ending_balance": ending_balance,
                        "recomputed_ending_balance": recomputed,
                        "delta": delta,
                        "tolerance": RECON_TOLERANCE,
                    },
                    run_db_id=run_db_id,
                )

            # MATH002 running balance step checks.
            prior_balance = float(beginning_balance)
            for row in rows:
                rb = row["running_balance"]
                if rb is None:
                    continue
                expected = prior_balance + float(row["amount"] or 0) if row["direction"] == "incoming" else prior_balance - float(row["amount"] or 0)
                diff = abs(expected - float(rb))
                if diff > ROW_TOLERANCE:
                    key = IssueKey(dataset="ds10", record_ref=f"ds10_transactions:{row['id']}", issue_code="MATH002_RUNNING_BALANCE_STEP")
                    active_keys.add(key)
                    upsert_issue(
                        inv_db,
                        dataset="ds10",
                        record_ref=key.record_ref,
                        issue_code=key.issue_code,
                        severity="warning",
                        details={
                            "statement_id": statement_id,
                            "expected_running_balance": round(expected, 2),
                            "actual_running_balance": rb,
                            "difference": round(diff, 2),
                            "tolerance": ROW_TOLERANCE,
                        },
                        run_db_id=run_db_id,
                    )
                prior_balance = float(rb)

    resolve_stale_issues(inv_db, dataset="ds10", issue_codes=tx_issue_codes, active_keys=active_keys)
    inv_db.commit()
    ds10_db.commit()

    # Refresh transaction qa_status + flags.
    issues = inv_db.execute(
        """
        SELECT record_ref, issue_code, severity
        FROM quality_issues
        WHERE dataset = 'ds10' AND status = 'open'
        """
    ).fetchall()
    by_record: dict[str, list[tuple[str, str]]] = {}
    for row in issues:
        by_record.setdefault(row["record_ref"], []).append((row["issue_code"], row["severity"]))

    tx_records = ds10_db.execute(
        "SELECT id, statement_id, qa_status FROM ds10_transactions"
    ).fetchall()
    updated = 0
    for tx in tx_records:
        tx_ref = f"ds10_transactions:{tx['id']}"
        st_ref = f"ds10_statement:{tx['statement_id']}" if tx["statement_id"] else None
        flags = list(by_record.get(tx_ref, []))
        if st_ref:
            flags.extend(by_record.get(st_ref, []))
        flag_codes = sorted({f[0] for f in flags})
        has_critical = any(f[1] == "critical" for f in flags)
        new_status = tx["qa_status"] or "pending"
        if new_status != "promoted":
            new_status = "needs_review" if has_critical else "approved"
        ds10_db.execute(
            """
            UPDATE ds10_transactions
            SET qa_status = ?, qa_flags_json = ?
            WHERE id = ?
            """,
            (new_status, json.dumps(flag_codes), tx["id"]),
        )
        updated += 1
    ds10_db.commit()

    critical_open = inv_db.execute(
        "SELECT COUNT(*) FROM quality_issues WHERE dataset='ds10' AND status='open' AND severity='critical'"
    ).fetchone()[0]
    warning_open = inv_db.execute(
        "SELECT COUNT(*) FROM quality_issues WHERE dataset='ds10' AND status='open' AND severity='warning'"
    ).fetchone()[0]

    return {
        "transactions_scanned": len(tx_rows),
        "transactions_updated": updated,
        "recon_rows_written": recon_rows_written,
        "critical_open": int(critical_open),
        "warning_open": int(warning_open),
    }


def create_review_tasks(inv_db: sqlite3.Connection, ds10_db: sqlite3.Connection, dataset: str) -> dict:
    created = 0
    if dataset != "ds10":
        return {"created": 0, "dataset": dataset}

    rows = ds10_db.execute(
        """
        SELECT t.id, t.amount
        FROM ds10_transactions t
        WHERE t.qa_status = 'needs_review'
        """
    ).fetchall()
    for row in rows:
        record_ref = f"ds10_transactions:{row['id']}"
        existing = inv_db.execute(
            """
            SELECT id
            FROM review_tasks
            WHERE dataset = 'ds10' AND record_ref = ? AND status IN ('open','in_review')
            """,
            (record_ref,),
        ).fetchone()
        if existing:
            continue
        tier = "tier2" if float(row["amount"] or 0) >= 1_000_000 else "tier1"
        required = 2 if tier == "tier2" else 1
        inv_db.execute(
            """
            INSERT INTO review_tasks (dataset, record_ref, tier, status, required_approvals)
            VALUES ('ds10', ?, ?, 'open', ?)
            """,
            (record_ref, tier, required),
        )
        created += 1

    inv_db.commit()
    return {"created": created, "dataset": dataset}


def _record_has_open_critical(inv_db: sqlite3.Connection, dataset: str, record_ref: str) -> bool:
    row = inv_db.execute(
        """
        SELECT 1
        FROM quality_issues
        WHERE dataset = ? AND record_ref = ? AND status = 'open' AND severity = 'critical'
        LIMIT 1
        """,
        (dataset, record_ref),
    ).fetchone()
    return bool(row)


def apply_review_decision(
    *,
    inv_db: sqlite3.Connection,
    ds10_db: sqlite3.Connection,
    task_id: int,
    decision: str,
    reviewer: str,
    notes: str | None,
) -> dict:
    task = inv_db.execute(
        "SELECT * FROM review_tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    if not task:
        raise ValueError(f"review task {task_id} not found")

    inv_db.execute(
        """
        INSERT INTO review_decisions (task_id, reviewer, decision, notes)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, reviewer, decision, notes),
    )
    if decision in ("reject", "needs_fix"):
        inv_db.execute(
            "UPDATE review_tasks SET status='rejected', closed_at = ? WHERE id = ?",
            (_utcnow(), task_id),
        )
        tx_id = _parse_record_id(task["record_ref"], "ds10_transactions:")
        if tx_id is not None:
            ds10_db.execute("UPDATE ds10_transactions SET qa_status='needs_review' WHERE id = ?", (tx_id,))
            ds10_db.commit()
        inv_db.commit()
        return {"task_id": task_id, "status": "rejected"}

    approvals = inv_db.execute(
        """
        SELECT COUNT(DISTINCT reviewer)
        FROM review_decisions
        WHERE task_id = ? AND decision = 'approve'
        """,
        (task_id,),
    ).fetchone()[0]
    if approvals >= int(task["required_approvals"]):
        inv_db.execute(
            "UPDATE review_tasks SET status='approved', closed_at = ? WHERE id = ?",
            (_utcnow(), task_id),
        )
        tx_id = _parse_record_id(task["record_ref"], "ds10_transactions:")
        if tx_id is not None and not _record_has_open_critical(inv_db, "ds10", f"ds10_transactions:{tx_id}"):
            ds10_db.execute("UPDATE ds10_transactions SET qa_status='approved' WHERE id = ?", (tx_id,))
            ds10_db.commit()
    else:
        inv_db.execute("UPDATE review_tasks SET status='in_review' WHERE id = ?", (task_id,))
    inv_db.commit()
    return {"task_id": task_id, "approvals": int(approvals), "required_approvals": int(task["required_approvals"])}


def promote_ds10(ds10_db: sqlite3.Connection, inv_db: sqlite3.Connection, run_id: str) -> dict:
    promoted = 0
    demoted = 0
    rows = ds10_db.execute(
        "SELECT id, statement_id, qa_status FROM ds10_transactions WHERE qa_status IN ('approved','promoted')"
    ).fetchall()
    for row in rows:
        tx_ref = f"ds10_transactions:{row['id']}"
        st_ref = f"ds10_statement:{row['statement_id']}" if row["statement_id"] else None
        has_critical = _record_has_open_critical(inv_db, "ds10", tx_ref) or (st_ref and _record_has_open_critical(inv_db, "ds10", st_ref))
        if has_critical:
            if row["qa_status"] == "promoted":
                ds10_db.execute("UPDATE ds10_transactions SET qa_status='needs_review' WHERE id = ?", (row["id"],))
                demoted += 1
            continue
        if row["qa_status"] == "approved":
            ds10_db.execute("UPDATE ds10_transactions SET qa_status='promoted', extract_run_id = COALESCE(extract_run_id, ?) WHERE id = ?", (run_id, row["id"]))
            promoted += 1
    ds10_db.commit()
    return {"promoted": promoted, "demoted": demoted}


def _load_docs_ocr(docs_db_path: Path | None = None) -> sqlite3.Connection | None:
    target = docs_db_path or DOCS_DB_PATH
    if not target.exists():
        return None
    db = sqlite3.connect(str(target))
    db.row_factory = sqlite3.Row
    return db


def _finding_has_quote_page(inv_db: sqlite3.Connection, finding_id: int) -> tuple[bool, bool, list[sqlite3.Row]]:
    rows = inv_db.execute(
        """
        SELECT evidence_ref, evidence_type, source_quote, source_page
        FROM finding_evidence
        WHERE finding_id = ?
        """,
        (finding_id,),
    ).fetchall()
    has_quote = any((r["source_quote"] or "").strip() for r in rows)
    has_page = any((r["source_page"] or "").strip() for r in rows)
    return has_quote, has_page, rows


def _insert_correction(
    inv_db: sqlite3.Connection,
    *,
    finding_id: int,
    old_confidence: str,
    new_confidence: str,
    reason: str,
) -> None:
    inv_db.execute(
        """
        INSERT INTO corrections (table_name, record_id, field_name, old_value, new_value,
                                 reason, corrected_by, correction_type)
        VALUES ('findings', ?, 'confidence', ?, ?, ?, 'financial_quality', 'refinement')
        """,
        (finding_id, old_confidence, new_confidence, reason),
    )


def evaluate_financial_findings(
    *,
    inv_db: sqlite3.Connection,
    run_db_id: int,
    auto_cap: bool,
    apply_changes: bool,
    docs_db_path: Path | None = None,
) -> dict:
    active_keys: set[IssueKey] = set()
    issue_codes = {"FQ001_SOURCE_QUOTE_REQUIRED", "FQ002_SOURCE_PAGE_REQUIRED", "FQ003_QUOTE_CROSSCHECK_REQUIRED"}
    docs_db = _load_docs_ocr(docs_db_path)

    findings = inv_db.execute(
        """
        SELECT id, confidence, finding_type, quality_state, confidence_requested
        FROM findings
        WHERE finding_type = 'financial' AND confidence IN ('high','confirmed')
        """
    ).fetchall()

    capped = 0
    for finding in findings:
        fid = int(finding["id"])
        ref = f"findings:{fid}"
        has_quote, has_page, evidence_rows = _finding_has_quote_page(inv_db, fid)

        if not has_quote:
            key = IssueKey(dataset="findings", record_ref=ref, issue_code="FQ001_SOURCE_QUOTE_REQUIRED")
            active_keys.add(key)
            upsert_issue(
                inv_db,
                dataset="findings",
                record_ref=ref,
                issue_code=key.issue_code,
                severity="critical",
                details={"finding_id": fid},
                run_db_id=run_db_id,
            )
        if not has_page:
            key = IssueKey(dataset="findings", record_ref=ref, issue_code="FQ002_SOURCE_PAGE_REQUIRED")
            active_keys.add(key)
            upsert_issue(
                inv_db,
                dataset="findings",
                record_ref=ref,
                issue_code=key.issue_code,
                severity="critical",
                details={"finding_id": fid},
                run_db_id=run_db_id,
            )

        crosscheck_fail = False
        if docs_db:
            for ev in evidence_rows:
                evidence_ref = (ev["evidence_ref"] or "").strip()
                quote = (ev["source_quote"] or "").strip()
                if not evidence_ref.startswith("EFTA") or not quote:
                    continue
                doc = docs_db.execute(
                    "SELECT ocr_text FROM documents WHERE bates_id = ?",
                    (evidence_ref,),
                ).fetchone()
                if not doc or not quote_matches_ocr(quote, doc["ocr_text"]):
                    crosscheck_fail = True
                    break
        if crosscheck_fail:
            key = IssueKey(dataset="findings", record_ref=ref, issue_code="FQ003_QUOTE_CROSSCHECK_REQUIRED")
            active_keys.add(key)
            upsert_issue(
                inv_db,
                dataset="findings",
                record_ref=ref,
                issue_code=key.issue_code,
                severity="critical",
                details={"finding_id": fid},
                run_db_id=run_db_id,
            )

        has_critical = any(
            IssueKey(dataset="findings", record_ref=ref, issue_code=code) in active_keys
            for code in issue_codes
        )
        if has_critical and auto_cap and apply_changes:
            old_confidence = finding["confidence"]
            inv_db.execute(
                """
                UPDATE findings
                SET confidence_requested = COALESCE(confidence_requested, confidence),
                    confidence = 'medium',
                    quality_state = 'capped'
                WHERE id = ?
                """,
                (fid,),
            )
            _insert_correction(
                inv_db,
                finding_id=fid,
                old_confidence=old_confidence,
                new_confidence="medium",
                reason="Hard-gate financial evidence requirements not met",
            )
            capped += 1

    if docs_db:
        docs_db.close()

    resolve_stale_issues(inv_db, dataset="findings", issue_codes=issue_codes, active_keys=active_keys)
    if apply_changes:
        inv_db.commit()

    open_critical = inv_db.execute(
        "SELECT COUNT(*) FROM quality_issues WHERE dataset='findings' AND status='open' AND severity='critical'"
    ).fetchone()[0]
    return {
        "financial_high_confirmed_scanned": len(findings),
        "capped": capped,
        "open_critical": int(open_critical),
    }


def run_export_parity_checks(
    *,
    ds10_db: sqlite3.Connection,
    inv_db: sqlite3.Connection,
    run_db_id: int,
    export_path: Path | None = None,
) -> dict:
    export_path = export_path or EXPORT_JSON_PATH
    record_ref = "financial_export:ds10-flows.json"
    active_keys: set[IssueKey] = set()
    if not export_path.exists():
        key = IssueKey(dataset="ds10", record_ref=record_ref, issue_code="MATH004_EXPORT_TOTAL_PARITY")
        active_keys.add(key)
        upsert_issue(
            inv_db,
            dataset="ds10",
            record_ref=record_ref,
            issue_code=key.issue_code,
            severity="critical",
            details={"error": f"missing export file: {export_path}"},
            run_db_id=run_db_id,
        )
        return {"math_checks_passed": False, "critical": 1}

    payload = json.loads(export_path.read_text())
    links = payload.get("links", [])
    top_tx = payload.get("top_transactions", [])

    from tools.financial_flows import promoted_flows

    src_grouped = promoted_flows(ds10_db, inv_db=inv_db, min_amount=50000.0)
    src_total = round(sum(float(r["value"] or 0) for r in src_grouped), 2)
    json_total = round(sum(float(link.get("value", 0) or 0) for link in links), 2)
    if abs(src_total - json_total) > ROW_TOLERANCE:
        key = IssueKey(dataset="ds10", record_ref=record_ref, issue_code="MATH004_EXPORT_TOTAL_PARITY")
        active_keys.add(key)
        upsert_issue(
            inv_db,
            dataset="ds10",
            record_ref=record_ref,
            issue_code=key.issue_code,
            severity="critical",
            details={"source_total": src_total, "json_total": json_total},
            run_db_id=run_db_id,
        )

    source_map = {(r["source"], r["target"]): (round(float(r["value"] or 0), 2), int(r["tx_count"])) for r in src_grouped}
    json_map = {(link.get("source"), link.get("target")): (round(float(link.get("value", 0) or 0), 2), int(link.get("tx_count", 0) or 0)) for link in links}
    if source_map != json_map:
        key = IssueKey(dataset="ds10", record_ref=record_ref, issue_code="MATH005_EXPORT_LINK_PARITY")
        active_keys.add(key)
        upsert_issue(
            inv_db,
            dataset="ds10",
            record_ref=record_ref,
            issue_code=key.issue_code,
            severity="critical",
            details={"source_links": len(source_map), "json_links": len(json_map)},
            run_db_id=run_db_id,
        )

    src_top = ds10_db.execute(
        """
        SELECT tx_date,
               ROUND(amount, 2) AS amount,
               COALESCE(sender,'') AS sender_norm,
               COALESCE(receiver,'') AS receiver_norm,
               COALESCE(efta_id,'') AS efta_norm
        FROM ds10_transactions
        WHERE qa_status='promoted' AND amount >= 1000000
        ORDER BY amount DESC
        LIMIT 50
        """
    ).fetchall()
    src_set = {
        (r["tx_date"], float(r["amount"] or 0), r["sender_norm"], r["receiver_norm"], r["efta_norm"])
        for r in src_top
    }
    json_set = {
        (
            item.get("tx_date"),
            float(item.get("amount", 0) or 0),
            item.get("sender") or "",
            item.get("receiver") or "",
            item.get("efta_id") or "",
        )
        for item in top_tx
    }
    if src_set != json_set:
        key = IssueKey(dataset="ds10", record_ref=record_ref, issue_code="MATH006_TOP_TX_PARITY")
        active_keys.add(key)
        upsert_issue(
            inv_db,
            dataset="ds10",
            record_ref=record_ref,
            issue_code=key.issue_code,
            severity="critical",
            details={"source_top_count": len(src_set), "json_top_count": len(json_set)},
            run_db_id=run_db_id,
        )

    resolve_stale_issues(
        inv_db,
        dataset="ds10",
        issue_codes={"MATH004_EXPORT_TOTAL_PARITY", "MATH005_EXPORT_LINK_PARITY", "MATH006_TOP_TX_PARITY"},
        active_keys=active_keys,
    )
    inv_db.commit()
    critical = inv_db.execute(
        """
        SELECT COUNT(*)
        FROM quality_issues
        WHERE dataset='ds10' AND status='open' AND severity='critical'
          AND issue_code IN ('MATH004_EXPORT_TOTAL_PARITY', 'MATH005_EXPORT_LINK_PARITY', 'MATH006_TOP_TX_PARITY')
        """
    ).fetchone()[0]
    return {"math_checks_passed": int(critical) == 0, "critical": int(critical), "source_total": src_total, "json_total": json_total}


def _critical_publish_issues(inv_db: sqlite3.Connection, ds10_db: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = inv_db.execute(
        """
        SELECT id, dataset, record_ref, issue_code, severity, details_json
        FROM quality_issues
        WHERE status='open' AND severity='critical' AND dataset IN ('ds10','findings')
        ORDER BY id
        """
    ).fetchall()
    out: list[sqlite3.Row] = []
    for row in rows:
        if row["dataset"] == "findings":
            out.append(row)
            continue
        ref = row["record_ref"] or ""
        if ref == "financial_export:ds10-flows.json":
            out.append(row)
            continue
        if ref.startswith("ds10_transactions:"):
            tx_id = _parse_record_id(ref, "ds10_transactions:")
            if tx_id is None:
                out.append(row)
                continue
            match = ds10_db.execute(
                "SELECT 1 FROM ds10_transactions WHERE id = ? AND qa_status='promoted'",
                (tx_id,),
            ).fetchone()
            if match:
                out.append(row)
            continue
        if ref.startswith("ds10_statement:"):
            st = ref.split(":", 1)[1]
            match = ds10_db.execute(
                "SELECT 1 FROM ds10_transactions WHERE statement_id = ? AND qa_status='promoted' LIMIT 1",
                (st,),
            ).fetchone()
            if match:
                out.append(row)
            continue
        out.append(row)
    return out


def cmd_qa_ds10(args) -> int:
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    ensure_quality_schema(inv_db)
    _ensure_ds10_quality_schema(ds10_db)

    run_db_id = start_quality_run(inv_db, dataset="ds10", run_type="qa", run_id=args.run_id)
    try:
        metrics = run_ds10_math_checks(
            ds10_db=ds10_db,
            inv_db=inv_db,
            run_db_id=run_db_id,
            run_id=args.run_id,
            with_math=args.with_math,
        )
        finish_quality_run(inv_db, run_db_id=run_db_id, status="passed", metrics=metrics)
        print(json.dumps({"status": "pass", "run_db_id": run_db_id, **metrics}, indent=2))
        return 0
    except Exception as exc:
        finish_quality_run(inv_db, run_db_id=run_db_id, status="failed", metrics={"error": str(exc)})
        raise
    finally:
        ds10_db.close()
        inv_db.close()


def cmd_recon_report(args) -> int:
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    _ensure_ds10_quality_schema(ds10_db)
    run_id = args.run_id
    if not run_id:
        row = ds10_db.execute(
            "SELECT run_id FROM ds10_statement_recon WHERE run_id IS NOT NULL ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        run_id = row["run_id"] if row else None
    if run_id:
        rows = ds10_db.execute(
            "SELECT * FROM ds10_statement_recon WHERE run_id = ?",
            (run_id,),
        ).fetchall()
    else:
        rows = ds10_db.execute("SELECT * FROM ds10_statement_recon").fetchall()
    total = len(rows)
    eligible = sum(1 for r in rows if r["recon_eligible"] == 1)
    passed = sum(1 for r in rows if r["recon_status"] == "pass")
    failed = sum(1 for r in rows if r["recon_status"] == "fail")
    warned = sum(1 for r in rows if r["recon_status"] == "warn")
    out = {
        "run_id": run_id,
        "total_statements": total,
        "eligible_statements": eligible,
        "eligible_coverage_pct": round((eligible / total) * 100, 2) if total else 0.0,
        "pass_count": passed,
        "fail_count": failed,
        "warn_count": warned,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Run: {run_id or 'all'}")
        print(f"Statements: {total} total, {eligible} eligible ({out['eligible_coverage_pct']}%)")
        print(f"Recon: {passed} pass, {failed} fail, {warned} warn")
    ds10_db.close()
    return 0


def cmd_gate(args) -> int:
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    ensure_quality_schema(inv_db)
    _ensure_ds10_quality_schema(ds10_db)
    run_id = args.run_id or _utcnow().replace(":", "").replace("-", "")
    run_db_id = start_quality_run(inv_db, dataset="ds10", run_type="gate", run_id=run_id)
    try:
        parity = {"math_checks_passed": True, "critical": 0}
        if args.with_math:
            parity = run_export_parity_checks(
                ds10_db=ds10_db,
                inv_db=inv_db,
                run_db_id=run_db_id,
                export_path=_path_from_args(args, "export_json", EXPORT_JSON_PATH),
            )
        critical = _critical_publish_issues(inv_db, ds10_db)
        result = {
            "status": "pass" if not critical else "fail",
            "scope": args.scope,
            "strict": bool(args.strict),
            "run_db_id": run_db_id,
            "critical_count": len(critical),
            "warning_count": inv_db.execute(
                "SELECT COUNT(*) FROM quality_issues WHERE status='open' AND severity='warning' AND dataset IN ('ds10','findings')"
            ).fetchone()[0],
            "blocking_rules": sorted({row["issue_code"] for row in critical}),
            "sample_issues": [
                {"record_ref": row["record_ref"], "issue_code": row["issue_code"], "severity": row["severity"]}
                for row in critical[:25]
            ],
            "math_checks_passed": bool(parity.get("math_checks_passed", True)),
            "quality_run_id": run_id,
        }
        finish_quality_run(inv_db, run_db_id=run_db_id, status=result["status"] == "pass" and "passed" or "failed", metrics=result)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Gate status: {result['status']}")
            print(f"Critical issues: {result['critical_count']}")
        if args.strict and critical:
            return 2
        return 0
    finally:
        ds10_db.close()
        inv_db.close()


def cmd_create_review_tasks(args) -> int:
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    ensure_quality_schema(inv_db)
    _ensure_ds10_quality_schema(ds10_db)
    result = create_review_tasks(inv_db, ds10_db, args.dataset)
    print(json.dumps(result, indent=2))
    ds10_db.close()
    inv_db.close()
    return 0


def cmd_review(args) -> int:
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    ensure_quality_schema(inv_db)
    _ensure_ds10_quality_schema(ds10_db)
    result = apply_review_decision(
        inv_db=inv_db,
        ds10_db=ds10_db,
        task_id=args.task_id,
        decision=args.decision,
        reviewer=args.by,
        notes=args.notes,
    )
    print(json.dumps(result, indent=2))
    ds10_db.close()
    inv_db.close()
    return 0


def cmd_promote_ds10(args) -> int:
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    ensure_quality_schema(inv_db)
    _ensure_ds10_quality_schema(ds10_db)
    result = promote_ds10(ds10_db, inv_db, args.run_id)
    print(json.dumps(result, indent=2))
    ds10_db.close()
    inv_db.close()
    return 0


def cmd_evaluate_findings(args) -> int:
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ensure_quality_schema(inv_db)
    run_id = args.run_id or _utcnow().replace(":", "").replace("-", "")
    run_db_id = start_quality_run(inv_db, dataset="findings", run_type="gate", run_id=run_id)
    try:
        metrics = evaluate_financial_findings(
            inv_db=inv_db,
            run_db_id=run_db_id,
            auto_cap=args.auto_cap,
            apply_changes=True,
            docs_db_path=_path_from_args(args, "docs_db", DOCS_DB_PATH),
        )
        finish_quality_run(inv_db, run_db_id=run_db_id, status="passed", metrics=metrics)
        print(json.dumps(metrics, indent=2))
        return 0
    finally:
        inv_db.close()


def _ensure_review_task(inv_db: sqlite3.Connection, dataset: str, record_ref: str, tier: str, required_approvals: int) -> None:
    row = inv_db.execute(
        """
        SELECT id
        FROM review_tasks
        WHERE dataset = ? AND record_ref = ? AND status IN ('open','in_review')
        LIMIT 1
        """,
        (dataset, record_ref),
    ).fetchone()
    if row:
        return
    inv_db.execute(
        """
        INSERT INTO review_tasks (dataset, record_ref, tier, status, required_approvals)
        VALUES (?, ?, ?, 'open', ?)
        """,
        (dataset, record_ref, tier, required_approvals),
    )


def cmd_backfill_financial(args) -> int:
    apply_changes = bool(args.apply)
    inv_db = connect_db(_path_from_args(args, "inv_db", INV_DB_PATH))
    ds10_db = connect_db(_path_from_args(args, "ds10_db", DS10_DB_PATH))
    ensure_quality_schema(inv_db)
    _ensure_ds10_quality_schema(ds10_db)
    run_id = args.run_id or _utcnow().replace(":", "").replace("-", "")
    run_db_id = start_quality_run(inv_db, dataset="ds10", run_type="backfill", run_id=run_id)
    try:
        findings_metrics = evaluate_financial_findings(
            inv_db=inv_db,
            run_db_id=run_db_id,
            auto_cap=args.auto_cap,
            apply_changes=apply_changes,
            docs_db_path=_path_from_args(args, "docs_db", DOCS_DB_PATH),
        )

        # Demote promoted DS10 rows with open critical math issues.
        demoted = 0
        promoted = ds10_db.execute(
            "SELECT id, statement_id FROM ds10_transactions WHERE qa_status='promoted'"
        ).fetchall()
        for row in promoted:
            tx_ref = f"ds10_transactions:{row['id']}"
            st_ref = f"ds10_statement:{row['statement_id']}" if row["statement_id"] else None
            has_critical = _record_has_open_critical(inv_db, "ds10", tx_ref) or (st_ref and _record_has_open_critical(inv_db, "ds10", st_ref))
            if not has_critical:
                continue
            if apply_changes:
                ds10_db.execute(
                    "UPDATE ds10_transactions SET qa_status='needs_review' WHERE id = ?",
                    (row["id"],),
                )
            demoted += 1
            if args.queue and apply_changes:
                _ensure_review_task(inv_db, "ds10", tx_ref, "tier2", 2)
        if apply_changes:
            ds10_db.commit()
            inv_db.commit()

        result = {
            "apply_changes": apply_changes,
            "findings": findings_metrics,
            "demoted_promoted_transactions": demoted,
        }
        finish_quality_run(inv_db, run_db_id=run_db_id, status="passed", metrics=result)
        print(json.dumps(result, indent=2))
        return 0
    finally:
        ds10_db.close()
        inv_db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Financial quality controls and hard-gates")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_db_path_args(
        cmd: argparse.ArgumentParser,
        *,
        include_inv: bool = True,
        include_ds10: bool = True,
        include_docs: bool = False,
    ) -> None:
        if include_inv:
            cmd.add_argument(
                "--inv-db",
                default=str(INV_DB_PATH),
                help=f"Path to investigation DB (default: {INV_DB_PATH})",
            )
        if include_ds10:
            cmd.add_argument(
                "--ds10-db",
                default=str(DS10_DB_PATH),
                help=f"Path to DS10 DB (default: {DS10_DB_PATH})",
            )
        if include_docs:
            cmd.add_argument(
                "--docs-db",
                default=str(DOCS_DB_PATH),
                help=f"Path to docs OCR DB (default: {DOCS_DB_PATH})",
            )

    qa = sub.add_parser("qa-ds10", help="Run DS10 quality checks")
    add_db_path_args(qa, include_inv=True, include_ds10=True)
    qa.add_argument("--run-id", required=True)
    qa.add_argument("--with-math", action="store_true")
    qa.set_defaults(func=cmd_qa_ds10)

    recon = sub.add_parser("recon-report", help="Report statement reconciliation results")
    add_db_path_args(recon, include_inv=False, include_ds10=True)
    recon.add_argument("--run-id")
    recon.add_argument("--json", action="store_true")
    recon.set_defaults(func=cmd_recon_report)

    gate = sub.add_parser("gate", help="Run publish/deploy gate")
    add_db_path_args(gate, include_inv=True, include_ds10=True)
    gate.add_argument("--scope", default="publish")
    gate.add_argument("--strict", action="store_true")
    gate.add_argument("--with-math", action="store_true")
    gate.add_argument(
        "--export-json",
        default=str(EXPORT_JSON_PATH),
        help="Financial export to compare with promoted source rows",
    )
    gate.add_argument("--json", action="store_true")
    gate.add_argument("--run-id")
    gate.set_defaults(func=cmd_gate)

    crt = sub.add_parser("create-review-tasks", help="Create review tasks for DS10 rows")
    add_db_path_args(crt, include_inv=True, include_ds10=True)
    crt.add_argument("--dataset", default="ds10")
    crt.set_defaults(func=cmd_create_review_tasks)

    review = sub.add_parser("review", help="Submit a review decision")
    add_db_path_args(review, include_inv=True, include_ds10=True)
    review.add_argument("--task-id", type=int, required=True)
    review.add_argument("--decision", choices=["approve", "reject", "needs_fix"], required=True)
    review.add_argument("--by", required=True)
    review.add_argument("--notes")
    review.set_defaults(func=cmd_review)

    promote = sub.add_parser("promote-ds10", help="Promote approved DS10 rows")
    add_db_path_args(promote, include_inv=True, include_ds10=True)
    promote.add_argument("--run-id", required=True)
    promote.set_defaults(func=cmd_promote_ds10)

    evalf = sub.add_parser("evaluate-findings", help="Evaluate financial finding hard-gates")
    add_db_path_args(evalf, include_inv=True, include_ds10=False, include_docs=True)
    evalf.add_argument("--type", default="financial")
    evalf.add_argument("--auto-cap", action="store_true")
    evalf.add_argument("--run-id")
    evalf.set_defaults(func=cmd_evaluate_findings)

    backfill = sub.add_parser("backfill-financial", help="Backfill hard-gate decisions on existing financial data")
    add_db_path_args(backfill, include_inv=True, include_ds10=True, include_docs=True)
    backfill.add_argument("--auto-cap", action="store_true")
    backfill.add_argument("--queue", action="store_true")
    backfill.add_argument("--dry-run", action="store_true")
    backfill.add_argument("--apply", action="store_true")
    backfill.add_argument("--run-id")
    backfill.set_defaults(func=cmd_backfill_financial)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "backfill-financial":
        if args.dry_run and args.apply:
            parser.error("choose one of --dry-run or --apply")
        if not args.dry_run and not args.apply:
            # Default safety: dry run.
            args.dry_run = True
        if args.dry_run:
            args.apply = False
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(0)
