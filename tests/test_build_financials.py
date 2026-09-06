"""Behavior tests for the normalized financial model builder + query CLI.

Unit-level: amount->minor conversion (incl. int64-overflow guard), sentinel
detection, structural-merchant classification, dedupe-key stability (incl. the
salt that keeps truncated EFTA refs from false-merging), account-key tiering, and
counterparty/intermediary-bank extraction from real statement-line shapes.

Integration-level: run build_financials against a tiny fixture that mirrors the
kabass + LMSBAND source schemas, then assert the invariants the task cares about
— signed minor units, outlier flagging (never dropped), same-page dedupe,
within-LMSBAND dedupe, cross-source (kabass->lmsband) collapse, that a max-amount
query is numeric (not the old lexicographic TEXT sort), that account/statement
links survive a rebuild, and that statement reconciliation reports 'ok'/'delta'
only on a genuinely closed ledger and 'not_computable' otherwise.
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

    def test_truncated_ref_detection(self):
        for ref in ("EFTA00", "EFTA001", "EFTA0013"):
            self.assertTrue(BUILD.is_truncated_ref(ref), ref)
        for ref in ("EFTA00039357", "265-48", None, ""):
            self.assertFalse(BUILD.is_truncated_ref(ref), ref)

    def test_truncated_ref_dedupe_key_is_salted(self):
        """A short EFTA is shared by unrelated pages, so two distinct rows that
        collide on it must NOT hash the same — otherwise dedupe merges them."""
        a = BUILD._dedupe_key_for("EFTA00", 100, 5000, "wire", "ds10:1")
        b = BUILD._dedupe_key_for("EFTA00", 100, 5000, "wire", "ds10:2")
        self.assertNotEqual(a, b)
        # A full-length ref stays unsalted, so genuine duplicates still collapse.
        c = BUILD._dedupe_key_for("EFTA00039357", 100, 5000, "wire", "ds10:1")
        d = BUILD._dedupe_key_for("EFTA00039357", 100, 5000, "wire", "ds10:2")
        self.assertEqual(c, d)


class OwnerAndDigitTests(unittest.TestCase):
    def test_normalize_owner_folds_punctuation_and_org_suffix(self):
        self.assertEqual(BUILD.normalize_owner("NES, LLC"), BUILD.normalize_owner("NES LLC"))
        self.assertEqual(BUILD.normalize_owner("Jeffrey E. Epstein"), "JEFFREY E EPSTEIN")
        self.assertIsNone(BUILD.normalize_owner(""))
        self.assertIsNone(BUILD.normalize_owner(None))

    def test_account_digits_are_not_folded_to_last4(self):
        """'1005', '31005', '61005' and '71005' are four different Epstein
        accounts; truncating to last-4 would silently merge them."""
        keys = {BUILD.AccountRegistry.make_key("JEFFREY E EPSTEIN", d)[0]
                for d in ("1005", "31005", "61005", "71005")}
        self.assertEqual(len(keys), 4)

    def test_key_basis_tiers(self):
        mk = BUILD.AccountRegistry.make_key
        self.assertEqual(mk("NES LLC", "0438")[1], "owner_digits")
        self.assertEqual(mk(None, "0438")[1], "digits")
        self.assertEqual(mk("NES LLC", None)[1], "owner")
        self.assertEqual(mk(None, None), (None, None))


class CounterpartyParseTests(unittest.TestCase):
    """Behavioral tests for the statement-line party extraction. Each case is a
    real line shape from the corpus."""

    def test_outflow_prefers_ultimate_beneficiary_over_correspondent_bank(self):
        cp, bank, rule = BUILD.parse_parties(
            "Fedwire Debit Via: Nexity Fin Corp/062006330 A/C: Merchants Commercial Bank "
            "Ben: Big Bear Construction Inc Ref: Mechanical Desal Req No 10")
        self.assertEqual(cp, "Big Bear Construction Inc")
        self.assertEqual(bank, "Nexity Fin Corp")
        self.assertEqual(rule, "wire_debit_ben")

    def test_outflow_without_ben_uses_beneficiary_account(self):
        cp, bank, _r = BUILD.parse_parties(
            "Fedwire Debit Via: Wells Fargo NA/121000248 A/C: Zorro Development Corporation "
            "Imad: 0812B1qgc08C005138 Trn: 0606300225Es")
        self.assertEqual(cp, "Zorro Development Corporation")
        self.assertEqual(bank, "Wells Fargo NA")

    def test_inflow_uses_ordering_party_not_the_account_holder(self):
        cp, bank, rule = BUILD.parse_parties(
            "Fed Wire Credit Via: Wells Fargo NA/121000248 B/O: Theodore W Waitt LA Jolla "
            "CA 92038-2409 Ref: Chase Nyc/Ctr/Bnf=116 East 65th St Llc New York NY")
        self.assertEqual(cp, "Theodore W Waitt LA Jolla")
        self.assertEqual(bank, "Wells Fargo NA")
        self.assertEqual(rule, "wire_credit_bo")

    def test_fao_names_the_beneficiary_and_the_receiving_bank(self):
        cp, bank, rule = BUILD.parse_parties(
            "Misc. Disbursement - TRANSFERRED BY WIRE TO FIRSTBANK PUERTO RICO "
            "FAO FINANCIAL TRUST COMPANY, INC. LETTER FROM CLIENT")
        self.assertEqual(cp, "FINANCIAL TRUST COMPANY, INC")
        self.assertEqual(bank, "FIRSTBANK PUERTO RICO")
        self.assertEqual(rule, "fao")

    def test_source_truncated_name_recovered_from_ref_echo(self):
        cp, _b, rule = BUILD.parse_parties(
            "Fedwire Debit Via: Colonial Bk/063113222 A/C: Environmental Technology Contref: "
            "Bene:Environmental Technology Control Inc Ref:Jeffrey Epstein")
        self.assertEqual(cp, "Environmental Technology Control Inc")
        self.assertTrue(rule.endswith("_ref_recovered"))

    def test_ref_echo_never_substitutes_an_unrelated_string(self):
        """The echo must complete the SAME name — a memo in the Ref block is not
        a counterparty."""
        cp, _b, _r = BUILD.parse_parties(
            "Fedwire Debit Via: Grand Bk & Tr/067014466 A/C: Acme Bolt Co, "
            "Ref: Bene: Totally Different Holdings Sarl")
        self.assertEqual(cp, "Acme Bolt Co")

    def test_internal_bookkeeping_yields_no_counterparty(self):
        for line in ("Funds Transferred From DDA Ac# To DDA Ac# As Requested",
                     "Beginning Balance", "Interest Payment",
                     "Payment To Chase Card Ending IN 7668",
                     "# Transfer Of Funds Cr TRANSFER FROM ACCOUNT"):
            cp, _b, _r = BUILD.parse_parties(line)
            self.assertIsNone(cp, line)

    def test_bank_clearing_pseudo_parties_are_rejected(self):
        for line in ("Book Transfer Credit B/O: CB FUNDS TRANS PREVIOUS DAY TAMPA FL 33610ORG:",
                     "Foreign Remittance Debit A/C: Fx USD Incomingfedchipsdda Bournemouth",
                     "Book Transfer A/C: Pbmo TX Trust Wire Clearing Honewark DE 19714-6076"):
            cp, _b, _r = BUILD.parse_parties(line)
            self.assertIsNone(cp, line)

    def test_masked_account_references_are_not_parties(self):
        for line in ("5/3 ONLINE TRANSFER TO CK: XXXXXXXX2323 REF # 00522153055",
                     "REF 0661429L FUNDS TRANSFER TO DEP 42966807 FROM"):
            cp, _b, _r = BUILD.parse_parties(line)
            self.assertIsNone(cp, line)

    def test_prose_bank_plus_account_plus_beneficiary(self):
        cp, bank, rule = BUILD.parse_parties(
            "Outgoing Money Transfer TO TD BANK, NA A/C 4314643118 "
            "GEORGE BRITTAIN LAND DESIGN INC")
        self.assertEqual(cp, "GEORGE BRITTAIN LAND DESIGN INC")
        self.assertEqual(bank, "TD BANK, NA")
        self.assertEqual(rule, "prose_to_ac")

    def test_state_suffix_kept_on_banks_stripped_from_party_names(self):
        _cp, bank, _r = BUILD.parse_parties(
            "Fedwire Debit VIA: FIRSTBANK PR /221571473 A/C: LSJ, LLC")
        self.assertEqual(bank, "FIRSTBANK PR")   # 'PR' is part of the bank's name
        cp, _b, _r = BUILD.parse_parties(
            "Book Transfer A/C: Jet Aviation St Louis Inc Cahokia IL 62206-1458")
        self.assertEqual(cp, "Jet Aviation St Louis Inc Cahokia")   # zip + state gone

    def test_empty_and_unparseable_lines(self):
        self.assertEqual(BUILD.parse_parties(None), (None, None, None))
        self.assertEqual(BUILD.parse_parties("   "), (None, None, None))
        self.assertEqual(BUILD.parse_parties("ADP TX/FINCL SVC ADP - TAX")[0], None)


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
    # (id, file_key, dataset, txn_date, amount, currency, merchant_name, merchant_raw,
    #  merchant_category, location, cardholder, description, account_digits, statement_date)
    kab_rows = [
        # normal debit
        ("1", "EFTA00000001", "DataSet10", "2019-03-07", "-2000000.00", "USD",
         "FIRSTBANK", None, "wire_out", None, "JEFFREY EPSTEIN", "wire to firstbank",
         "0438", None),
        # same-page duplicate of row 1 (same file_key/date/amount/desc)
        ("2", "EFTA00000001", "DataSet10", "2019-03-07", "-2000000.00", "USD",
         "FIRSTBANK", None, "wire_out", None, "JEFFREY EPSTEIN", "wire to firstbank",
         "0438", None),
        # structural marker (Beginning Balance) -> is_structural merchant
        ("3", "EFTA00000002", "DataSet10", "2019-03-01", "1000000.00", "USD",
         "Beginning Balance", None, "balance", None, "JEFFREY EPSTEIN", "beginning balance",
         "0438", None),
        # sentinel outlier
        ("4", "EFTA00000003", "DataSet10", "2016-04-20", "-99999.74", "USD",
         "Outgoing Money Trnsf", None, "wire_out", None, "GHISLAINE MAXWELL", "outgoing",
         None, None),
        # over-$50M outlier (kept, flagged)
        ("5", "EFTA00000004", "DataSet10", "2016-04-25", "60000000.00", "USD",
         "Deposit", None, "deposit", None, "GHISLAINE MAXWELL", "big deposit", None, None),
        # a Maxwell card debit (for counterparty/spend queries)
        ("6", "EFTA00000005", "DataSet10", "2016-05-01", "-250.00", "USD",
         "ESPA", None, "debit", None, "GHISLAINE MAXWELL", "spa", None, None),
        # lexicographically-large but numerically-small raw amount ("9..." sorts
        # above "60000000" as TEXT): this is exactly what tripped the old bug.
        ("7", "EFTA00000006", "DataSet10", "2016-06-01", "9500.00", "USD",
         "ADP", None, "fee", None, "JEFFREY EPSTEIN", "payroll fee", None, None),
        # --- a complete, closed statement page: beginning + body + ending -------
        #     48,002.61 - 10,000 - 97.25 + 150,000 = 187,905.36
        ("8", "EFTA00000010", "DataSet10", "2016-08-01", "48002.61", "USD",
         "Beginning Balance", None, "balance", None, "NES LLC", "beginning balance",
         "3758", "2016-08-31"),
        ("9", "EFTA00000010", "DataSet10", "2016-08-11", "-10000.00", "USD",
         "Check", None, "check", None, "NES LLC", "Check 1158", "3758", "2016-08-31"),
        ("10", "EFTA00000010", "DataSet10", "2016-08-10", "-97.25", "USD",
         "Service Charge", None, "fee", None, "NES LLC", "Check 1152", "3758", "2016-08-31"),
        ("11", "EFTA00000010", "DataSet10", "2016-08-05", "150000.00", "USD",
         "Incoming Wire Transfer", None, "wire_in", None, "NES LLC",
         "Fedwire Credit Via: Wells Fargo NA/121000248 B/O: Theodore W Waitt", "3758",
         "2016-08-31"),
        ("12", "EFTA00000010", "DataSet10", "2016-08-31", "187905.36", "USD",
         "Ending Balance", None, "balance", None, "NES LLC", "ending balance",
         "3758", "2016-08-31"),
        # --- a statement whose ledger does NOT close (residual $25,000) --------
        ("13", "EFTA00000011", "DataSet10", "2015-01-01", "1000.00", "USD",
         "Beginning Balance", None, "balance", None, "JEGE INC", "beginning balance",
         "4340", "2015-01-31"),
        ("14", "EFTA00000011", "DataSet10", "2015-01-15", "-500.00", "USD",
         "Check", None, "check", None, "JEGE INC", "Check 90", "4340", "2015-01-31"),
        ("15", "EFTA00000011", "DataSet10", "2015-01-31", "2500000.00", "USD",
         "Ending Balance", None, "balance", None, "JEGE INC", "ending balance",
         "4340", "2015-01-31"),
        # --- the statement line lives in merchant_raw, not description ---------
        # Two distinct $600 checks, same page/date/amount. The old dedupe hashed
        # `description` (NULL here) and falsely merged them.
        ("16", "EFTA00000012", "DataSet10", "2018-05-21", "-600.00", "USD",
         "Check", "Check 1158", "check", None, "NES LLC", None, "3758", "2018-05-31"),
        ("17", "EFTA00000012", "DataSet10", "2018-05-21", "-600.00", "USD",
         "Check", "Check 1152", "check", None, "NES LLC", None, "3758", "2018-05-31"),
        # A wire whose counterparty must be parsed out of merchant_raw. Its
        # merchant_name is the statement marker "Wire Transfer" (as in the real
        # corpus), so it is is_structural -> excluded from spend aggregates but it
        # must still be reachable by a counterparty lookup.
        ("18", "EFTA00000012", "DataSet10", "2018-05-22", "-15000.00", "USD",
         "Wire Transfer", "Fedwire Debit Via: Jp Morgan Chase/021000021 A/C: Coative "
         "Enterprises Llc Ref: Inv 12 Trn: 0101010101Es", "wire_out", None,
         "NES LLC", None, "3758", "2018-05-31"),
    ]
    for r in kab_rows:
        k.execute(
            "INSERT INTO financial_transactions "
            "(id, file_key, dataset, transaction_date, amount, currency, merchant_name, "
            " merchant_raw, merchant_category, location, cardholder, description, "
            " account_digits, statement_date) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", r)
    k.commit()
    k.close()

    lm = sqlite3.connect(lms)
    lm.executescript("""
        CREATE TABLE ds10_transactions (
            id INTEGER PRIMARY KEY, efta_id TEXT, tx_date TEXT, amount REAL,
            direction TEXT, sender TEXT, sender_account TEXT, receiver TEXT,
            receiver_account TEXT, bank TEXT, reference TEXT,
            running_balance REAL, confidence REAL, statement_id TEXT);
        CREATE TABLE ds09_transactions (
            id INTEGER PRIMARY KEY, efta_id TEXT, tx_date TEXT, amount REAL,
            direction TEXT, sender TEXT, sender_account TEXT, receiver TEXT,
            receiver_account TEXT, bank TEXT, reference TEXT,
            confirmation_number TEXT, operator TEXT, tx_type TEXT, confidence REAL);
        CREATE TABLE ds09_cc_transactions (
            id INTEGER PRIMARY KEY, statement_id INTEGER, efta_id TEXT, tx_date TEXT,
            description TEXT, merchant TEXT, location TEXT, amount REAL,
            tx_category TEXT, confidence REAL);
        CREATE TABLE ds09_cc_statements (
            id INTEGER PRIMARY KEY, efta_id TEXT, cardholder TEXT, card_last4 TEXT,
            billing_start TEXT, billing_end TEXT, previous_balance REAL,
            payments_total REAL, purchases_total REAL, statement_balance REAL,
            credit_line REAL);
        CREATE TABLE ds09_fund_statements (
            id INTEGER PRIMARY KEY, efta_id TEXT, fund_name TEXT, investor_name TEXT,
            investor_number TEXT, investor_class TEXT, statement_date TEXT,
            beginning_balance_mtd REAL, beginning_balance_ytd REAL, additions REAL,
            redemptions REAL, net_income_mtd REAL, net_income_ytd REAL,
            ending_balance REAL, return_mtd REAL, return_ytd REAL, currency TEXT,
            confidence REAL);
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
    lm.execute("INSERT INTO ds10_transactions (id, efta_id, tx_date, amount, direction, "
              "sender, sender_account, receiver, bank, reference, confidence) VALUES "
              "(1, 'EFTA00000001', '2019-03-07', 2000000.0, 'outgoing', 'JEFFREY EPSTEIN', "
              "'739110438', 'FIRSTBANK PUERTO RICO', 'DB', 'wire', 0.9)")
    # two within-LMSBAND duplicates of one ds09 wire: same EFTA/date/amount/parties.
    # Only the within-LMSBAND dedupe pass collapses these.
    for i in (2, 3):
        lm.execute("INSERT INTO ds09_transactions (id, efta_id, tx_date, amount, direction, "
                  "sender, receiver, bank, reference, tx_type, confidence) VALUES "
                  f"({i}, 'EFTA00000040', '2018-02-02', 5000.0, 'outgoing', 'NES LLC', "
                  "'ACME CORP', 'DB', 'ref-x', 'wire', 0.9)")
    # two rows sharing a TRUNCATED efta id: distinct wires that must NOT be merged
    for i, (amt, ref) in enumerate(((7000.0, "a"), (7000.0, "b")), start=4):
        lm.execute("INSERT INTO ds09_transactions (id, efta_id, tx_date, amount, direction, "
                  "sender, receiver, bank, reference, tx_type, confidence) VALUES "
                  f"({i}, 'EFTA00', '2018-03-03', {amt}, 'outgoing', 'NES LLC', "
                  f"'BETA LLC', 'DB', '{ref}', 'wire', 0.9)")
    # a cc purchase (positive -> outflow) and a payment (negative -> credit),
    # both members of cc statement 1
    lm.execute("INSERT INTO ds09_cc_transactions (id, statement_id, efta_id, tx_date, "
              "description, merchant, amount, tx_category, confidence) VALUES "
              "(1, 1, 'EFTA00000050', '2019-04-22', 'WALDORF NY', 'WALDORF', 200.8, "
              "'purchase', 0.9)")
    lm.execute("INSERT INTO ds09_cc_transactions (id, statement_id, efta_id, tx_date, "
              "description, merchant, amount, tx_category, confidence) VALUES "
              "(2, 1, 'EFTA00000050', '2019-04-18', 'PAYMENT THANK YOU', 'PAYMENT', "
              "-95.68, 'payment', 0.9)")
    # cc statement whose declared totals close: 2429.04 + 4285.00 - 3000.00 = 3714.04
    lm.execute("INSERT INTO ds09_cc_statements (id, efta_id, cardholder, card_last4, "
              "billing_start, billing_end, previous_balance, payments_total, "
              "purchases_total, statement_balance) VALUES "
              "(1, 'EFTA00000050', 'GHISLAINE MAXWELL', '6592', '2019-03-23', "
              "'2019-04-22', 2429.04, 3000.0, 4285.0, 3714.04)")
    # cc statement missing a total -> must stay not_computable, never a 0 residual
    lm.execute("INSERT INTO ds09_cc_statements (id, efta_id, cardholder, previous_balance, "
              "statement_balance) VALUES (2, 'EFTA00000051', 'GHISLAINE MAXWELL', 50.0, 52.65)")
    # fund statement that closes: 100000 + 5000 + 500 - 2000 = 103500
    lm.execute("INSERT INTO ds09_fund_statements (id, efta_id, fund_name, investor_name, "
              "investor_number, statement_date, beginning_balance_mtd, additions, "
              "redemptions, net_income_mtd, ending_balance, currency) VALUES "
              "(1, 'EFTA00000060', 'Boothbay Absolute Return Strategies LP', "
              "'Southern Financial', '0033', '2018-12-31', 100000.0, 5000.0, 2000.0, "
              "500.0, 103500.0, 'USD')")
    # balance (with a full source account number + bank), position, flight + invoices
    lm.execute("INSERT INTO ds10_balances (id, efta_id, account_holder, account_number, "
              "account_type, bank, balance_date, balance) VALUES "
              "(1, 'EFTA00000020', 'SOUTHERN FINANCIAL LLC', '42953758', 'checking', "
              "'Deutsche Bank', '2019-05-01', 156947.36)")
    lm.execute("INSERT INTO ds10_positions (id, efta_id, entity, investment, position_date, "
              "value, cost_basis) VALUES (1, 'EFTA00000021', 'SOUTHERN FINANCIAL LLC', "
              "'TOTAL PORTFOLIO', '2019-05-01', 5292229.53, 5.17e33)")
    lm.execute("INSERT INTO ds09_travel_flights (id, efta_id, passenger_name, flight_date, "
              "airline, flight_number, origin, destination, ticket_cost, record_locator) "
              "VALUES (1, 'EFTA00000030', 'MAXWELL/GHISLAINE', '2019-02-10', 'AA', '100', "
              "'JFK', 'LHR', NULL, 'ABC123')")
    # two invoices share the locator -> must NOT fan the flight into 2 rows
    lm.execute("INSERT INTO ds09_travel_invoices (id, efta_id, record_locator, total_charged) "
              "VALUES (1, 'EFTA00000030', 'ABC123', 4200.0)")
    lm.execute("INSERT INTO ds09_travel_invoices (id, efta_id, record_locator, total_charged) "
              "VALUES (2, 'EFTA00000030', 'ABC123', 4200.0)")
    lm.commit()
    lm.close()
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
        for ref in ("EFTA00000001", "EFTA00000020", "EFTA00000030"):
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

        # evidence_item_id set where EFTA is registered (EFTA00000001), NULL otherwise.
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
        first = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                 ("financial_transaction", "financial_account", "financial_statement",
                  "balance_snapshot", "position_snapshot", "fin_flight")}
        db.close()
        self._run_builder()  # second run
        db = sqlite3.connect(self.derived)
        second = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in first}
        dups = db.execute(
            "SELECT COUNT(*) FROM financial_transaction WHERE is_duplicate_of IS NOT NULL").fetchone()[0]
        # Account/statement links must survive a rebuild, not be left dangling.
        acct_links = db.execute(
            "SELECT COUNT(account_id) FROM financial_transaction").fetchone()[0]
        bal_links = db.execute("SELECT COUNT(account_id) FROM balance_snapshot").fetchone()[0]
        orphans = db.execute("""
            SELECT COUNT(*) FROM financial_transaction t
            WHERE t.account_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM financial_account a WHERE a.account_id = t.account_id)
        """).fetchone()[0]
        db.close()
        self.assertEqual(first, second)  # no double-insert in any owned table
        self.assertGreaterEqual(dups, 1)  # dedupe still applied after rebuild
        self.assertGreater(acct_links, 0)
        self.assertGreater(bal_links, 0)
        self.assertEqual(orphans, 0)


class AccountStatementIntegrationTests(BuilderIntegrationTests):
    """Account/statement dimensions and the closed-ledger reconciliation."""

    def test_full_build_invariants(self):
        pass  # inherited fixture only; the parent class owns that assertion set

    def test_max_amount_is_numeric_not_lexicographic(self):
        pass

    def test_idempotent_rerun(self):
        pass

    def test_accounts_are_tiered_not_asserted(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        tiers = {r["key_basis"]: r["n"] for r in db.execute(
            "SELECT key_basis, COUNT(*) n FROM financial_account GROUP BY key_basis")}
        # owner+digits rows and the LMSBAND full account number are digit-anchored;
        # a cardholder with no digits must land in the weaker 'owner' tier.
        self.assertIn("owner_digits", tiers)
        self.assertIn("source_account_number", tiers)
        self.assertIn("owner", tiers)
        # confidence must be ordered so a query can threshold on it
        conf = {r["key_basis"]: r["resolution_confidence"] for r in db.execute(
            "SELECT DISTINCT key_basis, resolution_confidence FROM financial_account")}
        self.assertGreater(conf["owner_digits"], conf["owner"])
        # the LMSBAND balance carried a full account number + bank -> both stored
        acct = db.execute("""SELECT a.* FROM financial_account a
                             JOIN balance_snapshot b USING(account_id) LIMIT 1""").fetchone()
        self.assertEqual(acct["account_digits"], "42953758")
        self.assertEqual(acct["institution_name"], "Deutsche Bank")
        db.close()

    def test_statement_reconciles_when_ledger_closes(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        r = db.execute("""SELECT * FROM financial_statement
                          WHERE canonical_ref = 'EFTA00000010'""").fetchone()
        self.assertEqual(r["recon_basis"], "boundary_markers")
        self.assertEqual(r["recon_status"], "ok")
        self.assertEqual(r["beginning_balance_minor"], 4800261)
        self.assertEqual(r["charges_minor"], -1009725)     # -10,000.00 + -97.25
        self.assertEqual(r["payments_minor"], 15000000)
        self.assertEqual(r["computed_ending_minor"], r["ending_balance_minor"])
        self.assertEqual(r["recon_delta_minor"], 0)
        self.assertEqual(r["txn_count"], 3)
        db.close()

    def test_statement_residual_is_reported_not_hidden(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        r = db.execute("""SELECT * FROM financial_statement
                          WHERE canonical_ref = 'EFTA00000011'""").fetchone()
        self.assertEqual(r["recon_status"], "delta")
        # 1,000.00 - 500.00 = 500.00 computed vs a declared 2,500,000.00 ending
        self.assertEqual(r["computed_ending_minor"], 50000)
        self.assertEqual(r["recon_delta_minor"], 250000000 - 50000)
        db.close()

    def test_missing_boundary_is_not_computable_never_zero_residual(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        # the kabass page with no balance markers at all
        r = db.execute("""SELECT * FROM financial_statement
                          WHERE canonical_ref = 'EFTA00000012'""").fetchone()
        self.assertEqual(r["recon_status"], "not_computable")
        self.assertIsNone(r["recon_delta_minor"])
        # a card statement missing one declared total stays not_computable too
        r2 = db.execute("""SELECT * FROM financial_statement
                           WHERE canonical_ref = 'EFTA00000051'""").fetchone()
        self.assertEqual(r2["recon_status"], "not_computable")
        self.assertIsNone(r2["recon_delta_minor"])
        db.close()

    def test_declared_total_statements_reconcile(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        cc = db.execute("""SELECT * FROM financial_statement
                           WHERE canonical_ref = 'EFTA00000050'""").fetchone()
        self.assertEqual(cc["recon_basis"], "declared_totals")
        self.assertEqual(cc["recon_status"], "ok")
        self.assertEqual(cc["charges_minor"], 428500)      # purchases raise the balance
        self.assertEqual(cc["payments_minor"], -300000)    # payments reduce it
        # its member transactions are linked to it
        self.assertEqual(db.execute(
            "SELECT COUNT(*) FROM financial_transaction WHERE statement_id = ?",
            (cc["statement_id"],)).fetchone()[0], 2)
        fund = db.execute("""SELECT * FROM financial_statement
                             WHERE canonical_ref = 'EFTA00000060'""").fetchone()
        self.assertEqual(fund["recon_basis"], "fund_totals")
        self.assertEqual(fund["recon_status"], "ok")
        db.close()

    def test_within_lmsband_duplicates_are_collapsed(self):
        """The documented asymmetry: LMSBAND-only repeated hashes went unflagged."""
        self._run_builder()
        db = sqlite3.connect(self.derived)
        lms = db.execute(
            "SELECT source_system_id FROM source_system WHERE name='lmsband'").fetchone()[0]
        pair = db.execute("""
            SELECT COUNT(*) FROM financial_transaction
            WHERE source_native_id IN ('ds09:2','ds09:3') AND is_duplicate_of IS NOT NULL
        """).fetchone()[0]
        self.assertEqual(pair, 1)  # exactly one of the identical pair collapses
        excess = db.execute("""
            SELECT COALESCE(SUM(c - 1), 0) FROM (
              SELECT COUNT(*) c FROM financial_transaction
              WHERE source_system_id = ? AND dedupe_key IS NOT NULL
                AND is_duplicate_of IS NULL
              GROUP BY dedupe_key HAVING c > 1)
        """, (lms,)).fetchone()[0]
        self.assertEqual(excess, 0)
        db.close()

    def test_truncated_ref_rows_are_never_merged(self):
        """Two distinct wires sharing the short ref 'EFTA00' must both survive."""
        self._run_builder()
        db = sqlite3.connect(self.derived)
        survivors = db.execute("""
            SELECT COUNT(*) FROM financial_transaction
            WHERE canonical_ref = 'EFTA00' AND is_duplicate_of IS NULL
        """).fetchone()[0]
        self.assertEqual(survivors, 2)
        db.close()

    def test_statement_line_from_merchant_raw_is_preserved_and_parsed(self):
        """When the source put the statement line in merchant_raw instead of
        description, raw_description must still carry it — and the counterparty
        must be parsed out of it."""
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        r = db.execute("""SELECT raw_description, counterparty_raw, intermediary_bank_raw,
                                 counterparty_parse_rule
                          FROM financial_transaction WHERE source_native_id = '18'""").fetchone()
        self.assertIn("Coative Enterprises Llc", r["raw_description"])
        self.assertEqual(r["counterparty_raw"], "Coative Enterprises Llc")
        self.assertEqual(r["intermediary_bank_raw"], "Jp Morgan Chase")
        self.assertEqual(r["counterparty_parse_rule"], "wire_debit_ac")
        # the two $600 checks differ only in merchant_raw -> NOT duplicates
        kept = db.execute("""SELECT COUNT(*) FROM financial_transaction
                             WHERE source_native_id IN ('16','17')
                               AND is_duplicate_of IS NULL""").fetchone()[0]
        self.assertEqual(kept, 2)
        db.close()

    def test_counterparty_lookup_reaches_wire_rows(self):
        """A wire's merchant name starts with 'wire transfer', so it is classed as
        a statement marker. That exclusion belongs to the spend AGGREGATE — a
        lookup for the counterparty by name must still find the row."""
        self._run_builder()
        QF = _load("query_fin_t", "tools/query_fin.py")
        QF.DERIVED_DB = self.derived
        db = QF._db()
        rows = db.execute(f"""
            SELECT t.counterparty_raw FROM financial_transaction t
            WHERE t.counterparty_raw LIKE '%Coative%' AND {QF._NOT_DUPLICATE}
        """).fetchall()
        self.assertEqual([r["counterparty_raw"] for r in rows], ["Coative Enterprises Llc"])
        # the aggregate filter still excludes it, which is why they differ
        agg = db.execute(f"""
            SELECT COUNT(*) FROM financial_transaction t
            WHERE t.counterparty_raw LIKE '%Coative%' AND {QF._ACTIVE}
        """).fetchone()[0]
        self.assertEqual(agg, 0)
        db.close()

    def test_lmsband_counterparty_field_is_never_overwritten(self):
        self._run_builder()
        db = sqlite3.connect(self.derived)
        db.row_factory = sqlite3.Row
        r = db.execute("""SELECT counterparty_raw, counterparty_parse_rule,
                                 intermediary_bank_raw
                          FROM financial_transaction
                          WHERE source_native_id = 'ds10:1'""").fetchone()
        self.assertEqual(r["counterparty_raw"], "FIRSTBANK PUERTO RICO")
        self.assertEqual(r["counterparty_parse_rule"], "source_field")
        self.assertEqual(r["intermediary_bank_raw"], "DB")
        db.close()


if __name__ == "__main__":
    unittest.main()
