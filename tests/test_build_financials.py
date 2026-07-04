"""Behavior tests for the normalized financial model builder + query CLI.

Unit-level: amount->minor conversion (incl. int64-overflow guard), sentinel
detection, structural-merchant classification, dedupe-key stability.

Integration-level: run build_financials against a tiny fixture that mirrors the
kabass + LMSBAND source schemas, then assert the invariants the task cares about
— signed minor units, outlier flagging (never dropped), same-page dedupe,
cross-source (kabass->lmsband) collapse, and that a max-amount query is numeric
(not the old lexicographic TEXT sort).
"""

import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(mod_name, rel):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


DERIVED = _load("epstein_derived_t", "tools/epstein_derived.py")
BUILD = _load("build_financials_t", "tools/build_financials.py")


class HelperTests(unittest.TestCase):
    def test_amount_to_minor_signs_and_rounds(self):
        self.assertEqual(BUILD._amount_to_minor(1234.56), 123456)
        self.assertEqual(BUILD._amount_to_minor(-5000000.0), -500000000)
        self.assertEqual(BUILD._amount_to_minor(0.1), 10)
        self.assertIsNone(BUILD._amount_to_minor(None))

    def test_amount_to_minor_overflow_returns_none(self):
        # OCR garbage like 5.17e+33 overflows int64 when scaled to cents.
        self.assertIsNone(BUILD._amount_to_minor(5.17e33))

    def test_sentinel_family(self):
        for s in ("-99999.74", "99999.99", "999999.75", "-999999.75", "9999"):
            self.assertTrue(BUILD._is_sentinel(s), s)
        for s in ("635.12", "12660.5", "-2121318.85", "", None):
            self.assertFalse(BUILD._is_sentinel(s), s)

    def test_structural_merchant_classification(self):
        for s in ("Beginning Balance", "Ending Balance", "Interest Payment",
                  "Check Paid", "Internal Funds Transfer", "Fedwire Debit"):
            self.assertEqual(BUILD._is_structural(s), 1, s)
        for s in ("FedEx", "ADP", "Cingular Wireless", "LSJ, LLC"):
            self.assertEqual(BUILD._is_structural(s), 0, s)

    def test_dedupe_key_stable_and_normalizes_desc(self):
        a = BUILD._dedupe_key("EFTA1", 100, 5000, "Wire  To   ACME")
        b = BUILD._dedupe_key("EFTA1", 100, 5000, "wire to acme")
        self.assertEqual(a, b)  # whitespace + case normalized
        c = BUILD._dedupe_key("EFTA1", 100, 5001, "wire to acme")
        self.assertNotEqual(a, c)  # amount participates


def _make_source_dbs(tmp):
    """Minimal kabass + lmsband source DBs with the columns the builder reads."""
    kab = tmp / "kab.db"
    lms = tmp / "lms.db"
    k = sqlite3.connect(kab)
    k.executescript("""
        CREATE TABLE financial_transactions (
            id TEXT, file_key TEXT, dataset TEXT, transaction_date TEXT,
            amount TEXT, currency TEXT, merchant_name TEXT, merchant_raw TEXT,
            merchant_category TEXT, location TEXT, cardholder TEXT, description TEXT,
            card_type TEXT, account_digits TEXT, statement_date TEXT,
            flight_from TEXT, flight_to TEXT, flight_carrier TEXT, flight_departure TEXT,
            flight_ticket TEXT, flight_passenger TEXT, source_page TEXT,
            extraction_model TEXT, extraction_confidence TEXT
        );
    """)
    kab_rows = [
        # normal debit
        ("1", "EFTA001", "DataSet10", "2019-03-07", "-2000000.00", "USD",
         "FIRSTBANK", None, "wire_out", None, "JEFFREY EPSTEIN", "wire to firstbank"),
        # same-page duplicate of row 1 (same file_key/date/amount/desc)
        ("2", "EFTA001", "DataSet10", "2019-03-07", "-2000000.00", "USD",
         "FIRSTBANK", None, "wire_out", None, "JEFFREY EPSTEIN", "wire to firstbank"),
        # structural marker (Beginning Balance) -> is_structural merchant
        ("3", "EFTA002", "DataSet10", "2019-03-01", "1000000.00", "USD",
         "Beginning Balance", None, "balance", None, "JEFFREY EPSTEIN", "beginning balance"),
        # sentinel outlier
        ("4", "EFTA003", "DataSet10", "2016-04-20", "-99999.74", "USD",
         "Outgoing Money Trnsf", None, "wire_out", None, "GHISLAINE MAXWELL", "outgoing"),
        # over-$50M outlier (kept, flagged)
        ("5", "EFTA004", "DataSet10", "2016-04-25", "60000000.00", "USD",
         "Deposit", None, "deposit", None, "GHISLAINE MAXWELL", "big deposit"),
        # a Maxwell card debit (for counterparty/spend queries)
        ("6", "EFTA005", "DataSet10", "2016-05-01", "-250.00", "USD",
         "ESPA", None, "debit", None, "GHISLAINE MAXWELL", "spa"),
        # lexicographically-large but numerically-small raw amount ("9..." sorts
        # above "60000000" as TEXT): this is exactly what tripped the old bug.
        ("7", "EFTA006", "DataSet10", "2016-06-01", "9500.00", "USD",
         "ADP", None, "fee", None, "JEFFREY EPSTEIN", "payroll fee"),
    ]
    for r in kab_rows:
        k.execute(
            "INSERT INTO financial_transactions "
            "(id, file_key, dataset, transaction_date, amount, currency, merchant_name, "
            " merchant_raw, merchant_category, location, cardholder, description) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", r)
    k.commit()
    k.close()

    l = sqlite3.connect(lms)
    l.executescript("""
        CREATE TABLE ds10_transactions (
            id INTEGER PRIMARY KEY, efta_id TEXT, tx_date TEXT, amount REAL,
            direction TEXT, sender TEXT, receiver TEXT, bank TEXT, reference TEXT,
            running_balance REAL, confidence REAL, statement_id TEXT);
        CREATE TABLE ds09_transactions (
            id INTEGER PRIMARY KEY, efta_id TEXT, tx_date TEXT, amount REAL,
            direction TEXT, sender TEXT, receiver TEXT, bank TEXT, reference TEXT,
            tx_type TEXT, confidence REAL);
        CREATE TABLE ds09_cc_transactions (
            id INTEGER PRIMARY KEY, efta_id TEXT, tx_date TEXT, description TEXT,
            merchant TEXT, location TEXT, amount REAL, tx_category TEXT, confidence REAL);
        CREATE TABLE ds10_balances (
            id INTEGER PRIMARY KEY, efta_id TEXT, account_holder TEXT,
            account_number TEXT, account_type TEXT, balance_date TEXT, balance REAL, bank TEXT);
        CREATE TABLE ds10_positions (
            id INTEGER PRIMARY KEY, efta_id TEXT, entity TEXT, investment TEXT,
            position_date TEXT, value REAL, cost_basis REAL);
        CREATE TABLE ds10_statement_recon (
            id INTEGER PRIMARY KEY, efta_id TEXT, statement_start_date TEXT,
            statement_end_date TEXT, beginning_balance REAL, ending_balance REAL,
            recon_delta REAL, recon_status TEXT);
        CREATE TABLE ds09_travel_flights (
            id INTEGER PRIMARY KEY, invoice_id INTEGER, efta_id TEXT,
            passenger_name TEXT, flight_date TEXT, airline TEXT, flight_number TEXT,
            origin TEXT, destination TEXT, ticket_number TEXT, ticket_cost REAL,
            record_locator TEXT, confidence REAL);
        CREATE TABLE ds09_travel_invoices (
            id INTEGER PRIMARY KEY, efta_id TEXT, record_locator TEXT,
            invoice_date TEXT, total_charged REAL, card_last4 TEXT);
        CREATE TABLE ds09_travel_passengers (
            id INTEGER PRIMARY KEY, invoice_id INTEGER, passenger_name TEXT,
            passenger_normalized TEXT);
    """)
    # ds10 wire that cross-source-duplicates kabass row 1 (same EFTA/date/amount)
    l.execute("INSERT INTO ds10_transactions (id, efta_id, tx_date, amount, direction, "
              "sender, receiver, bank, reference, confidence) VALUES "
              "(1, 'EFTA001', '2019-03-07', 2000000.0, 'outgoing', 'JEFFREY EPSTEIN', "
              "'FIRSTBANK PUERTO RICO', 'DB', 'wire', 0.9)")
    # a cc purchase (positive -> outflow) and a payment (negative -> credit)
    l.execute("INSERT INTO ds09_cc_transactions (id, efta_id, tx_date, description, "
              "merchant, amount, tx_category, confidence) VALUES "
              "(1, 'EFTA010', '2019-04-22', 'WALDORF NY', 'WALDORF', 200.8, 'purchase', 0.9)")
    l.execute("INSERT INTO ds09_cc_transactions (id, efta_id, tx_date, description, "
              "merchant, amount, tx_category, confidence) VALUES "
              "(2, 'EFTA010', '2019-04-18', 'PAYMENT THANK YOU', 'PAYMENT', -95.68, 'payment', 0.9)")
    # balance, position (with absurd cost_basis), flight + fan-out invoice
    l.execute("INSERT INTO ds10_balances (id, efta_id, account_holder, balance_date, balance) "
              "VALUES (1, 'EFTA020', 'SOUTHERN FINANCIAL LLC', '2019-05-01', 156947.36)")
    l.execute("INSERT INTO ds10_positions (id, efta_id, entity, investment, position_date, "
              "value, cost_basis) VALUES (1, 'EFTA021', 'SOUTHERN FINANCIAL LLC', "
              "'TOTAL PORTFOLIO', '2019-05-01', 5292229.53, 5.17e33)")
    l.execute("INSERT INTO ds09_travel_flights (id, efta_id, passenger_name, flight_date, "
              "airline, flight_number, origin, destination, ticket_cost, record_locator) "
              "VALUES (1, 'EFTA030', 'MAXWELL/GHISLAINE', '2019-02-10', 'AA', '100', "
              "'JFK', 'LHR', NULL, 'ABC123')")
    # two invoices share the locator -> must NOT fan the flight into 2 rows
    l.execute("INSERT INTO ds09_travel_invoices (id, efta_id, record_locator, total_charged) "
              "VALUES (1, 'EFTA030', 'ABC123', 4200.0)")
    l.execute("INSERT INTO ds09_travel_invoices (id, efta_id, record_locator, total_charged) "
              "VALUES (2, 'EFTA030', 'ABC123', 4200.0)")
    l.commit()
    l.close()
    return kab, lms


class BuilderIntegrationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.derived = tmp / "derived.db"
        self.kab, self.lms = _make_source_dbs(tmp)

        # Seed a derived DB with schema + an evidence_item for the EFTAs we use,
        # so evidence_item_id linkage is exercised.
        db = DERIVED.get_db(self.derived)
        DERIVED.init_schema(db)
        run = DERIVED.new_run(db, "test-seed")
        for ref in ("EFTA001", "EFTA020", "EFTA030"):
            db.execute("INSERT OR IGNORE INTO evidence_item(canonical_ref, item_kind, "
                       "dataset, created_by_run) VALUES (?, 'page', 'DataSet10', ?)", (ref, run))
        db.commit()
        db.close()

        # Point the builder at the fixture DBs. get_db's default path is bound at
        # def-time, so patch the imported symbol to always open the fixture — this
        # guarantees the test NEVER touches the real datasets/epstein_derived.db.
        fixture = self.derived
        self._orig_get_db = BUILD.get_db
        BUILD.get_db = lambda path=fixture: DERIVED.get_db(fixture)
        self._orig_paths = (BUILD.KABASS_DB, BUILD.LMSBAND_DB)
        BUILD.KABASS_DB = self.kab
        BUILD.LMSBAND_DB = self.lms

    def tearDown(self):
        BUILD.get_db = self._orig_get_db
        BUILD.KABASS_DB, BUILD.LMSBAND_DB = self._orig_paths
        self.tmp.cleanup()

    def _run_builder(self):
        import argparse
        argv = sys.argv
        sys.argv = ["build_financials.py"]
        try:
            BUILD.main()
        finally:
            sys.argv = argv

    def test_full_build_invariants(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row

        def one(q, *p):
            return db.execute(q, p).fetchone()[0]

        # signed minor units: the wire_out is negative.
        amt = one("SELECT amount_minor FROM financial_transaction WHERE source_native_id='1'")
        self.assertEqual(amt, -200000000)

        # evidence_item_id set where EFTA is registered (EFTA001), NULL otherwise.
        self.assertIsNotNone(one("SELECT evidence_item_id FROM financial_transaction WHERE source_native_id='6' OR source_native_id='1' ORDER BY (evidence_item_id IS NULL) LIMIT 1"))
        self.assertIsNone(one("SELECT evidence_item_id FROM financial_transaction WHERE source_native_id='6'"))

        # structural marker merchant flagged.
        self.assertEqual(one("SELECT is_structural FROM merchant WHERE canonical_name='Beginning Balance'"), 1)

        # outliers flagged, not dropped: sentinel + over-$50M both present.
        self.assertEqual(one("SELECT is_outlier FROM financial_transaction WHERE source_native_id='4'"), 1)
        self.assertEqual(one("SELECT is_outlier FROM financial_transaction WHERE source_native_id='5'"), 1)
        self.assertEqual(one("SELECT COUNT(*) FROM financial_transaction WHERE source_native_id IN ('4','5')"), 2)

        # same-page dup: row 2 collapsed into row 1 (or the cross-source LMSBAND row).
        dup2 = one("SELECT is_duplicate_of FROM financial_transaction WHERE source_native_id='2'")
        self.assertIsNotNone(dup2)

        # cross-source: kabass row 1 collapses into the LMSBAND ds10 row (preferred canonical).
        lms_id = one("SELECT transaction_id FROM financial_transaction WHERE source_native_id='ds10:1'")
        dup1 = one("SELECT is_duplicate_of FROM financial_transaction WHERE source_native_id='1'")
        self.assertEqual(dup1, lms_id)

        # cc purchase -> negative (debit), payment -> positive (credit).
        self.assertEqual(one("SELECT amount_minor FROM financial_transaction WHERE source_native_id='ds09cc:1'"), -20080)
        self.assertEqual(one("SELECT amount_minor FROM financial_transaction WHERE source_native_id='ds09cc:2'"), 9568)

        # position with absurd cost_basis: flagged outlier, minor nulled (overflow-safe).
        self.assertEqual(one("SELECT is_outlier FROM position_snapshot"), 1)
        self.assertIsNone(one("SELECT cost_basis_minor FROM position_snapshot"))

        # flight fan-out guard: exactly one flight row despite two matching invoices.
        self.assertEqual(one("SELECT COUNT(*) FROM fin_flight"), 1)
        self.assertEqual(one("SELECT ticket_cost_minor FROM fin_flight"), 420000)

        db.close()

    def test_max_amount_is_numeric_not_lexicographic(self):
        """The TEXT-sort bug: sorting raw string amounts puts '999...' above
        '60000000'. The normalized amount_minor INTEGER must sort numerically."""
        self._run_builder()
        db = sqlite3.connect(self.derived)
        # numeric max should be the $60M deposit (row 5), not a lexicographic pick.
        numeric_top = db.execute(
            "SELECT raw_amount FROM financial_transaction "
            "ORDER BY ABS(amount_minor) DESC LIMIT 1").fetchone()[0]
        self.assertEqual(numeric_top, "60000000.00")
        # a lexicographic TEXT sort of the SAME raw strings picks "9500.00"
        # ("9" > "6"), a numerically-tiny value -> the two disagree, which is the
        # whole reason amount_minor exists.
        lex_top = db.execute(
            "SELECT raw_amount FROM financial_transaction WHERE raw_amount IS NOT NULL "
            "ORDER BY raw_amount DESC LIMIT 1").fetchone()[0]
        self.assertEqual(lex_top, "9500.00")
        self.assertNotEqual(numeric_top, lex_top)
        db.close()

    def test_idempotent_rerun(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        first = db.execute("SELECT COUNT(*) FROM financial_transaction").fetchone()[0]
        db.close()
        self._run_builder()  # second run
        db = sqlite3.connect(self.derived)
        second = db.execute("SELECT COUNT(*) FROM financial_transaction").fetchone()[0]
        dups = db.execute(
            "SELECT COUNT(*) FROM financial_transaction WHERE is_duplicate_of IS NOT NULL").fetchone()[0]
        db.close()
        self.assertEqual(first, second)  # no double-insert
        self.assertGreaterEqual(dups, 1)  # dedupe still applied after rebuild


if __name__ == "__main__":
    unittest.main()
