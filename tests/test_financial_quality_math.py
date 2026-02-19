import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "financial_quality.py"
SPEC = importlib.util.spec_from_file_location("financial_quality", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["financial_quality"] = MODULE
SPEC.loader.exec_module(MODULE)

PARSER_PATH = ROOT / "tools" / "parse_ds10_financials.py"
PARSER_SPEC = importlib.util.spec_from_file_location("parse_ds10_financials", PARSER_PATH)
PARSER = importlib.util.module_from_spec(PARSER_SPEC)
assert PARSER_SPEC and PARSER_SPEC.loader
PARSER_SPEC.loader.exec_module(PARSER)


def _init_inv_db(path: Path) -> None:
    db = sqlite3.connect(str(path))
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
    db.commit()
    db.close()


def _init_ds10_db(path: Path) -> None:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    PARSER.create_tables(db)
    db.close()


def _seed_statement(
    ds10_path: Path,
    *,
    statement_id: str | None = None,
    file_id: int = 1,
    efta_id: str = "EFTA00000001",
    account_holder: str = "PLAN D, LLC",
    account_number: str = "42952771",
    start_date: str = "2016-10-01",
    end_date: str = "2016-10-31",
    beginning_balance: float | None = 1000.0,
    ending_balance: float | None = 975.0,
    tx_rows: list[tuple[int, str, float, float]] | None = None,
    qa_status: str = "approved",
) -> str:
    tx_rows = tx_rows or [
        (1, "incoming", 50.0, 1050.0),
        (2, "outgoing", 100.0, 950.0),
        (3, "incoming", 25.0, 975.0),
    ]
    effective_end_date = end_date if ending_balance is not None else start_date
    if statement_id is None:
        statement_id = MODULE._build_statement_id(
            file_id,
            efta_id,
            account_number,
            account_holder,
            start_date,
            effective_end_date,
        )
    db = sqlite3.connect(str(ds10_path))
    db.execute("PRAGMA foreign_keys=OFF")
    if beginning_balance is not None:
        db.execute(
            """
            INSERT INTO ds10_balances
            (file_id, efta_id, account_holder, account_number, account_type, balance_date, balance, bank, raw_extract)
            VALUES (?, ?, ?, ?, 'checking', ?, ?, 'Deutsche Bank', 'begin')
            """,
            (file_id, efta_id, account_holder, account_number, start_date, beginning_balance),
        )
    if ending_balance is not None:
        db.execute(
            """
            INSERT INTO ds10_balances
            (file_id, efta_id, account_holder, account_number, account_type, balance_date, balance, bank, raw_extract)
            VALUES (?, ?, ?, ?, 'checking', ?, ?, 'Deutsche Bank', 'end')
            """,
            (file_id, efta_id, account_holder, account_number, end_date, ending_balance),
        )
    for seq, direction, amount, running_balance in tx_rows:
        db.execute(
            """
            INSERT INTO ds10_transactions
            (file_id, efta_id, tx_date, amount, currency, direction, sender, receiver, bank, raw_extract, confidence,
             statement_id, statement_seq, running_balance, running_balance_raw, parsed_from_statement, qa_status)
            VALUES (?, ?, ?, ?, 'USD', ?, 'SENDER', 'RECEIVER', 'Deutsche Bank', 'ctx', 0.9, ?, ?, ?, ?, 1, ?)
            """,
            (
                file_id,
                efta_id,
                f"2016-10-{seq:02d}",
                amount,
                direction,
                statement_id,
                seq,
                running_balance,
                f"{running_balance:.2f}",
                qa_status,
            ),
        )
    db.commit()
    db.close()
    return statement_id


class FinancialQualityMathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.ds10_path = self.tmp_path / "ds10.db"
        self.inv_path = self.tmp_path / "inv.db"
        self.export_path = self.tmp_path / "ds10-flows.json"
        _init_ds10_db(self.ds10_path)
        _init_inv_db(self.inv_path)

        MODULE.DS10_DB_PATH = self.ds10_path
        MODULE.INV_DB_PATH = self.inv_path
        MODULE.EXPORT_JSON_PATH = self.export_path
        MODULE.DOCS_DB_PATH = self.tmp_path / "docs_missing.db"

        inv_db = MODULE.connect_db(self.inv_path)
        ds10_db = MODULE.connect_db(self.ds10_path)
        MODULE.ensure_quality_schema(inv_db)
        MODULE._ensure_ds10_quality_schema(ds10_db)
        inv_db.close()
        ds10_db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_parser_statement_metadata_present(self):
        text = """
New York, NY 10154
PLAN D, LLC
For personal assistance
October 1.2016 to October 31. 2016
Summary of Account Balance(s)
Beginning Balance $1,000.00
Account Account Number Balance
Business Checking 42952771 $900.00
Transaction Detail
10-02 Incoming Money Trnsf 50.00 1,050.00 ORG= TEST SOURCE
10-03 Outgoing Money Trnsf 100.00 950.00 TO BANK A/C RECEIVER LLC
10-04 Incoming Money Trnsf 25.00 975.00 ORG= SECOND SOURCE
"""
        balances, tx = PARSER.parse_db_statement(1, "EFTA12345678.pdf", text)
        self.assertGreaterEqual(len(balances), 1)
        self.assertGreaterEqual(len(tx), 3)
        statement_ids = {t.get("statement_id") for t in tx}
        self.assertEqual(len(statement_ids), 1)
        self.assertIn("running_balance", tx[0])
        self.assertTrue(all(t.get("parsed_from_statement") == 1 for t in tx))
        seqs = [t.get("statement_seq") for t in tx]
        self.assertEqual(seqs, sorted(seqs))

    def test_recon_eligibility_pass_and_noneligible_warning(self):
        stmt_good = _seed_statement(self.ds10_path)
        stmt_bad = _seed_statement(
            self.ds10_path,
            file_id=2,
            efta_id="EFTA00000002",
            beginning_balance=1000.0,
            ending_balance=None,
            tx_rows=[(1, "incoming", 10.0, 1010.0), (2, "outgoing", 5.0, 1005.0), (3, "incoming", 2.0, 1007.0)],
        )

        inv_db = MODULE.connect_db(self.inv_path)
        ds10_db = MODULE.connect_db(self.ds10_path)
        run_db_id = MODULE.start_quality_run(inv_db, dataset="ds10", run_type="qa", run_id="run_eligibility")
        MODULE.run_ds10_math_checks(ds10_db=ds10_db, inv_db=inv_db, run_db_id=run_db_id, run_id="run_eligibility", with_math=True)

        recon_good = ds10_db.execute("SELECT recon_eligible, recon_status FROM ds10_statement_recon WHERE statement_id=?", (stmt_good,)).fetchone()
        recon_bad = ds10_db.execute("SELECT recon_eligible FROM ds10_statement_recon WHERE statement_id=?", (stmt_bad,)).fetchone()
        self.assertEqual(recon_good["recon_eligible"], 1)
        self.assertEqual(recon_good["recon_status"], "pass")
        self.assertEqual(recon_bad["recon_eligible"], 0)

        warn_issue = inv_db.execute(
            "SELECT severity FROM quality_issues WHERE record_ref=? AND issue_code='MATH003_NON_ELIGIBLE' AND status='open'",
            (f"ds10_statement:{stmt_bad}",),
        ).fetchone()
        self.assertIsNotNone(warn_issue)
        self.assertEqual(warn_issue["severity"], "warning")
        ds10_db.close()
        inv_db.close()

    def test_math002_running_balance_step_warning(self):
        _seed_statement(
            self.ds10_path,
            beginning_balance=1000.0,
            ending_balance=980.0,
            tx_rows=[
                (1, "outgoing", 100.0, 900.0),
                (2, "incoming", 50.0, 970.0),  # should be 950.0
                (3, "incoming", 80.0, 980.0),
            ],
        )
        inv_db = MODULE.connect_db(self.inv_path)
        ds10_db = MODULE.connect_db(self.ds10_path)
        run_db_id = MODULE.start_quality_run(inv_db, dataset="ds10", run_type="qa", run_id="run_step")
        MODULE.run_ds10_math_checks(ds10_db=ds10_db, inv_db=inv_db, run_db_id=run_db_id, run_id="run_step", with_math=True)
        issue = inv_db.execute(
            "SELECT issue_code, severity FROM quality_issues WHERE issue_code='MATH002_RUNNING_BALANCE_STEP' AND status='open'"
        ).fetchone()
        self.assertIsNotNone(issue)
        self.assertEqual(issue["severity"], "warning")
        ds10_db.close()
        inv_db.close()

    def test_math003_reconciliation_fail_is_critical(self):
        stmt_recon_fail = _seed_statement(
            self.ds10_path,
            beginning_balance=1000.0,
            ending_balance=900.0,
            tx_rows=[(1, "incoming", 50.0, 1050.0), (2, "outgoing", 100.0, 950.0), (3, "incoming", 25.0, 975.0)],
        )
        inv_db = MODULE.connect_db(self.inv_path)
        ds10_db = MODULE.connect_db(self.ds10_path)
        run_db_id = MODULE.start_quality_run(inv_db, dataset="ds10", run_type="qa", run_id="run_recon_fail")
        MODULE.run_ds10_math_checks(ds10_db=ds10_db, inv_db=inv_db, run_db_id=run_db_id, run_id="run_recon_fail", with_math=True)
        issue = inv_db.execute(
            "SELECT severity FROM quality_issues WHERE record_ref=? AND issue_code='MATH003_BEGIN_END_RECON' AND status='open'",
            (f"ds10_statement:{stmt_recon_fail}",),
        ).fetchone()
        self.assertIsNotNone(issue)
        self.assertEqual(issue["severity"], "critical")
        ds10_db.close()
        inv_db.close()

    def test_export_parity_mismatch_detection(self):
        _seed_statement(self.ds10_path, qa_status="promoted")
        self.export_path.write_text(
            json.dumps(
                {
                    "links": [{"source": "SENDER", "target": "RECEIVER", "value": 1.0, "tx_count": 1}],
                    "top_transactions": [],
                    "stats": {"total_value": 1.0},
                }
            )
        )
        inv_db = MODULE.connect_db(self.inv_path)
        ds10_db = MODULE.connect_db(self.ds10_path)
        run_db_id = MODULE.start_quality_run(inv_db, dataset="ds10", run_type="gate", run_id="run_export")
        result = MODULE.run_export_parity_checks(ds10_db=ds10_db, inv_db=inv_db, run_db_id=run_db_id)
        self.assertFalse(result["math_checks_passed"])
        issue = inv_db.execute(
            "SELECT issue_code FROM quality_issues WHERE issue_code IN ('MATH004_EXPORT_TOTAL_PARITY','MATH005_EXPORT_LINK_PARITY','MATH006_TOP_TX_PARITY') AND status='open'"
        ).fetchone()
        self.assertIsNotNone(issue)
        ds10_db.close()
        inv_db.close()

    def test_gate_blocks_on_critical_issue(self):
        _seed_statement(self.ds10_path, qa_status="promoted")
        inv_db = MODULE.connect_db(self.inv_path)
        MODULE.ensure_quality_schema(inv_db)
        inv_db.execute(
            """
            INSERT INTO quality_issues (dataset, record_ref, issue_code, severity, status, details_json)
            VALUES ('ds10', 'ds10_transactions:1', 'MATH001_DIRECTION_AMOUNT', 'critical', 'open', '{}')
            """
        )
        inv_db.commit()
        inv_db.close()
        rc = MODULE.cmd_gate(
            Namespace(scope="publish", strict=True, with_math=False, json=True, run_id="run_gate")
        )
        self.assertEqual(rc, 2)

    def test_backfill_demotes_and_queues_review_task(self):
        _seed_statement(self.ds10_path, qa_status="promoted")
        inv_db = MODULE.connect_db(self.inv_path)
        MODULE.ensure_quality_schema(inv_db)
        inv_db.execute(
            """
            INSERT INTO quality_issues (dataset, record_ref, issue_code, severity, status, details_json)
            VALUES ('ds10', 'ds10_transactions:1', 'MATH001_DIRECTION_AMOUNT', 'critical', 'open', '{}')
            """
        )
        inv_db.commit()
        inv_db.close()

        rc = MODULE.cmd_backfill_financial(
            Namespace(auto_cap=False, queue=True, dry_run=False, apply=True, run_id="run_backfill")
        )
        self.assertEqual(rc, 0)

        ds10_db = MODULE.connect_db(self.ds10_path)
        inv_db = MODULE.connect_db(self.inv_path)
        status = ds10_db.execute("SELECT qa_status FROM ds10_transactions WHERE id=1").fetchone()["qa_status"]
        self.assertEqual(status, "needs_review")
        task = inv_db.execute(
            "SELECT COUNT(*) AS c FROM review_tasks WHERE dataset='ds10' AND record_ref='ds10_transactions:1'"
        ).fetchone()["c"]
        self.assertEqual(task, 1)
        ds10_db.close()
        inv_db.close()


if __name__ == "__main__":
    unittest.main()
