#!/usr/bin/env python3
"""Build deterministic test fixtures derived from local real project data."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INV_DB = REPO_ROOT / "investigation.db"
DEFAULT_DS10_DB = REPO_ROOT / "datasets" / "lmsband_epstein_files.db"
DEFAULT_DOSSIER_DIR = REPO_ROOT / "content" / "dossiers"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tests" / "fixtures" / "data"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.financial_quality import ensure_quality_schema  # noqa: E402
from tools.parse_ds10_financials import create_tables as create_ds10_tables  # noqa: E402


def _connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    return db


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _iter_dossier_paths(dossier_dir: Path) -> list[Path]:
    return sorted(p for p in dossier_dir.glob("*.json") if p.is_file() and not p.name.startswith("_"))


def _load_check_sync_source(inv_db: sqlite3.Connection, dossier_dir: Path) -> dict[str, Any]:
    for dossier_path in _iter_dossier_paths(dossier_dir):
        dossier = json.loads(dossier_path.read_text())
        findings = dossier.get("findings", [])
        for finding in findings:
            finding_id = finding.get("id")
            if finding_id is None:
                continue
            try:
                finding_id = int(finding_id)
            except (TypeError, ValueError):
                continue

            rows = inv_db.execute(
                """
                SELECT finding_id, evidence_type, evidence_ref, source_quote, source_page, assessment
                FROM finding_evidence
                WHERE finding_id = ? AND COALESCE(TRIM(evidence_ref), '') != ''
                """,
                (finding_id,),
            ).fetchall()
            if len(rows) < 2:
                continue

            connection_info = None
            for connection in dossier.get("connections", []):
                connection_id = connection.get("id")
                if connection_id is None:
                    continue
                try:
                    connection_id = int(connection_id)
                except (TypeError, ValueError):
                    continue
                c_rows = inv_db.execute(
                    """
                    SELECT connection_id, evidence_type, evidence_ref, source_quote, source_page
                    FROM connection_evidence
                    WHERE connection_id = ? AND COALESCE(TRIM(evidence_ref), '') != ''
                    """,
                    (connection_id,),
                ).fetchall()
                if c_rows:
                    connection_info = {
                        "id": connection_id,
                        "rows": [dict(r) for r in c_rows],
                    }
                    break

            return {
                "dossier_path": dossier_path,
                "finding_id": finding_id,
                "finding_rows": [dict(r) for r in rows],
                "connection": connection_info,
            }

    raise RuntimeError("Unable to find a dossier/finding pair with at least two evidence rows.")


def _build_check_sync_fixture(
    *,
    source_inv_path: Path,
    source_dossier_dir: Path,
    out_db_path: Path,
    out_dossier_path: Path,
) -> dict[str, Any]:
    src_db = _connect(source_inv_path)
    try:
        source = _load_check_sync_source(src_db, source_dossier_dir)
    finally:
        src_db.close()

    finding_rows = source["finding_rows"]
    first = finding_rows[0]
    second = finding_rows[1]
    packed_refs = f"{first['evidence_ref']},{second['evidence_ref']}"

    if out_db_path.exists():
        out_db_path.unlink()
    out_db_path.parent.mkdir(parents=True, exist_ok=True)
    db = _connect(out_db_path)
    try:
        db.executescript(
            """
            CREATE TABLE finding_evidence (
                finding_id INTEGER,
                evidence_type TEXT,
                evidence_ref TEXT,
                source_quote TEXT,
                source_page TEXT,
                assessment TEXT
            );
            CREATE TABLE connection_evidence (
                connection_id INTEGER,
                evidence_type TEXT,
                evidence_ref TEXT,
                source_quote TEXT,
                source_page TEXT
            );
            """
        )

        db_rows = [
            {
                "finding_id": source["finding_id"],
                "evidence_type": first.get("evidence_type"),
                "evidence_ref": first.get("evidence_ref"),
                "source_quote": first.get("source_quote"),
                "source_page": first.get("source_page"),
                "assessment": first.get("assessment"),
            },
            {
                "finding_id": source["finding_id"],
                "evidence_type": first.get("evidence_type"),
                "evidence_ref": second.get("evidence_ref"),
                "source_quote": first.get("source_quote"),
                "source_page": first.get("source_page"),
                "assessment": first.get("assessment"),
            },
        ]
        db.executemany(
            """
            INSERT INTO finding_evidence
            (finding_id, evidence_type, evidence_ref, source_quote, source_page, assessment)
            VALUES (:finding_id, :evidence_type, :evidence_ref, :source_quote, :source_page, :assessment)
            """,
            db_rows,
        )

        connection_block = None
        if source["connection"]:
            c_row = source["connection"]["rows"][0]
            db.execute(
                """
                INSERT INTO connection_evidence
                (connection_id, evidence_type, evidence_ref, source_quote, source_page)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    source["connection"]["id"],
                    c_row.get("evidence_type"),
                    c_row.get("evidence_ref"),
                    c_row.get("source_quote"),
                    c_row.get("source_page"),
                ),
            )
            connection_block = {
                "id": source["connection"]["id"],
                "evidence": [
                    {
                        "evidence_type": c_row.get("evidence_type"),
                        "evidence_ref": c_row.get("evidence_ref"),
                        "source_quote": c_row.get("source_quote"),
                        "source_page": c_row.get("source_page"),
                    }
                ],
            }

        db.commit()
    finally:
        db.close()

    dossier_payload = {
        "slug": "fixture-check-sync",
        "findings": [
            {
                "id": source["finding_id"],
                "evidence": [
                    {
                        "evidence_type": first.get("evidence_type"),
                        "evidence_ref": packed_refs,
                        "source_quote": first.get("source_quote"),
                        "source_page": first.get("source_page"),
                        "assessment": first.get("assessment"),
                    }
                ],
            }
        ],
        "connections": [],
    }
    if connection_block:
        dossier_payload["connections"].append(connection_block)

    _write_json(out_dossier_path, dossier_payload)

    return {
        "source_dossier": source["dossier_path"].name,
        "source_finding_id": source["finding_id"],
        "packed_refs": packed_refs,
        "finding_rows_in_fixture": len(dossier_payload["findings"][0]["evidence"]),
        "has_connection_fixture": bool(connection_block),
    }


def _load_real_transaction(ds10_db_path: Path) -> dict[str, Any]:
    db = _connect(ds10_db_path)
    try:
        row = db.execute(
            """
            SELECT
                id, file_id, efta_id, tx_date, amount, currency, direction,
                sender, sender_account, receiver, receiver_account,
                bank, reference, raw_extract, confidence,
                statement_id, statement_seq, running_balance, running_balance_raw,
                parsed_from_statement, qa_flags_json, extract_run_id, parser_version
            FROM ds10_transactions
            WHERE amount > 0
              AND direction IN ('incoming', 'outgoing')
              AND COALESCE(TRIM(sender), '') != ''
              AND COALESCE(TRIM(receiver), '') != ''
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()
        if not row:
            raise RuntimeError("No suitable DS10 transaction row found in source dataset.")
        return dict(row)
    finally:
        db.close()


def _create_minimal_inv_fixture(inv_db_path: Path) -> None:
    if inv_db_path.exists():
        inv_db_path.unlink()
    db = _connect(inv_db_path)
    try:
        db.executescript(
            """
            CREATE TABLE findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_type TEXT,
                confidence TEXT,
                quality_state TEXT,
                confidence_requested TEXT
            );
            CREATE TABLE finding_evidence (
                finding_id INTEGER,
                evidence_ref TEXT,
                evidence_type TEXT,
                source_quote TEXT,
                source_page TEXT
            );
            CREATE TABLE corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT,
                record_id INTEGER,
                field_name TEXT,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                corrected_by TEXT,
                correction_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        ensure_quality_schema(db)
        db.commit()
    finally:
        db.close()


def _build_financial_fixture(
    *,
    source_ds10_path: Path,
    out_ds10_path: Path,
    out_inv_path: Path,
) -> dict[str, Any]:
    real_tx = _load_real_transaction(source_ds10_path)

    if out_ds10_path.exists():
        out_ds10_path.unlink()
    out_ds10_path.parent.mkdir(parents=True, exist_ok=True)
    ds10_db = _connect(out_ds10_path)
    try:
        create_ds10_tables(ds10_db)
        ds10_db.execute("PRAGMA foreign_keys=OFF")
        ds10_db.execute(
            """
            INSERT INTO ds10_transactions
            (id, file_id, efta_id, tx_date, amount, currency, direction,
             sender, sender_account, receiver, receiver_account, bank, reference,
             raw_extract, confidence, statement_id, statement_seq, running_balance,
             running_balance_raw, parsed_from_statement, qa_status, qa_flags_json,
             extract_run_id, parser_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'promoted', ?, ?, ?)
            """,
            (
                1,
                real_tx.get("file_id"),
                real_tx.get("efta_id"),
                real_tx.get("tx_date"),
                real_tx.get("amount"),
                real_tx.get("currency") or "USD",
                real_tx.get("direction"),
                real_tx.get("sender"),
                real_tx.get("sender_account"),
                real_tx.get("receiver"),
                real_tx.get("receiver_account"),
                real_tx.get("bank"),
                real_tx.get("reference"),
                real_tx.get("raw_extract"),
                real_tx.get("confidence"),
                real_tx.get("statement_id") or "fixture_statement_id",
                real_tx.get("statement_seq"),
                real_tx.get("running_balance"),
                real_tx.get("running_balance_raw"),
                real_tx.get("parsed_from_statement") or 0,
                real_tx.get("qa_flags_json"),
                real_tx.get("extract_run_id"),
                real_tx.get("parser_version"),
            ),
        )
        ds10_db.commit()
    finally:
        ds10_db.close()

    _create_minimal_inv_fixture(out_inv_path)

    return {
        "source_tx_id": real_tx.get("id"),
        "source_efta_id": real_tx.get("efta_id"),
        "fixture_transaction_id": 1,
        "fixture_qa_status": "promoted",
    }


def build_fixtures(
    *,
    source_inv_path: Path,
    source_ds10_path: Path,
    source_dossier_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    _reset_dir(output_dir)
    (output_dir / "dossiers").mkdir(parents=True, exist_ok=True)

    sync_meta = _build_check_sync_fixture(
        source_inv_path=source_inv_path,
        source_dossier_dir=source_dossier_dir,
        out_db_path=output_dir / "check_sync_investigation.db",
        out_dossier_path=output_dir / "dossiers" / "check-sync.json",
    )
    financial_meta = _build_financial_fixture(
        source_ds10_path=source_ds10_path,
        out_ds10_path=output_dir / "financial_ds10.db",
        out_inv_path=output_dir / "financial_inv.db",
    )

    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "investigation_db": str(source_inv_path),
            "ds10_db": str(source_ds10_path),
            "dossier_dir": str(source_dossier_dir),
        },
        "artifacts": {
            "check_sync": sync_meta,
            "financial": financial_meta,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build small real-derived fixtures for pytest integration tests.")
    parser.add_argument("--inv-db", default=str(DEFAULT_INV_DB))
    parser.add_argument("--ds10-db", default=str(DEFAULT_DS10_DB))
    parser.add_argument("--dossier-dir", default=str(DEFAULT_DOSSIER_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--manifest", default=str(REPO_ROOT / "tests" / "fixtures" / "manifest.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inv_db = Path(args.inv_db)
    ds10_db = Path(args.ds10_db)
    dossier_dir = Path(args.dossier_dir)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)

    for path, label in ((inv_db, "investigation DB"), (ds10_db, "DS10 DB"), (dossier_dir, "dossier directory")):
        if not path.exists():
            print(f"Missing {label}: {path}", file=sys.stderr)
            return 2

    metadata = build_fixtures(
        source_inv_path=inv_db,
        source_ds10_path=ds10_db,
        source_dossier_dir=dossier_dir,
        output_dir=output_dir,
    )
    _write_json(manifest_path, metadata)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
