#!/usr/bin/env python3
"""
Extract credit card statements and fund investor statements from DS09
(Epstein email production, EFTA00039025-EFTA01262781) in lmsband_epstein_files.db.

Document types:
  - UBS Visa Signature credit card statements (~74) — Ghislaine Maxwell
    Individual transaction lines: purchases, payments, fees, interest
  - Boothbay fund investor statements (~42) — Southern Financial, LLC
    Monthly: beginning/ending balance, additions, redemptions, net income, return

Usage:
  uv run python scripts/extract_ds09_financials.py create-tables
  uv run python scripts/extract_ds09_financials.py parse-cc [--limit N]
  uv run python scripts/extract_ds09_financials.py parse-fund [--limit N]
  uv run python scripts/extract_ds09_financials.py parse-all [--limit N]
  uv run python scripts/extract_ds09_financials.py report
  uv run python scripts/extract_ds09_financials.py query [--merchant X] [--amount-min N] [--date-start D] [--date-end D]
  uv run python scripts/extract_ds09_financials.py merchants   # top merchants by spend
  uv run python scripts/extract_ds09_financials.py monthly     # monthly spend summary
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.parse_ds10_financials import (
    extract_efta_id,
    normalize_date,
    parse_dollar_amount,
)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'lmsband_epstein_files.db')
PARSER_VERSION = "ds09_fin_v1"
DS09_DATASET = 9


def _dollar(text):
    """Wrapper around parse_dollar_amount that returns just the float (discards confidence)."""
    val, _ = parse_dollar_amount(text)
    return val


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def _run_id():
    env_id = os.getenv("DS09_EXTRACT_RUN_ID")
    if env_id:
        return env_id
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

def create_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS ds09_cc_statements (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            efta_id TEXT,
            cardholder TEXT,
            card_last4 TEXT,
            billing_start TEXT,
            billing_end TEXT,
            previous_balance REAL,
            payments_total REAL,
            purchases_total REAL,
            statement_balance REAL,
            credit_line REAL,
            parser_version TEXT,
            extract_run_id TEXT,
            UNIQUE(file_id)
        );

        CREATE TABLE IF NOT EXISTS ds09_cc_transactions (
            id INTEGER PRIMARY KEY,
            statement_id INTEGER REFERENCES ds09_cc_statements(id),
            file_id INTEGER,
            efta_id TEXT,
            tx_date TEXT,
            description TEXT,
            merchant TEXT,
            location TEXT,
            amount REAL,
            tx_category TEXT,  -- payment, purchase, fee, interest, credit, cash_advance
            confidence REAL,
            parser_version TEXT,
            extract_run_id TEXT,
            UNIQUE(file_id, tx_date, description, amount)
        );

        CREATE TABLE IF NOT EXISTS ds09_fund_statements (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            efta_id TEXT,
            fund_name TEXT,
            investor_name TEXT,
            investor_number TEXT,
            investor_class TEXT,
            statement_date TEXT,
            beginning_balance_mtd REAL,
            beginning_balance_ytd REAL,
            additions REAL,
            redemptions REAL,
            net_income_mtd REAL,
            net_income_ytd REAL,
            ending_balance REAL,
            return_mtd REAL,
            return_ytd REAL,
            currency TEXT DEFAULT 'USD',
            confidence REAL,
            parser_version TEXT,
            extract_run_id TEXT,
            UNIQUE(file_id)
        );

        CREATE INDEX IF NOT EXISTS idx_ds09_cc_stmt_efta ON ds09_cc_statements(efta_id);
        CREATE INDEX IF NOT EXISTS idx_ds09_cc_tx_date ON ds09_cc_transactions(tx_date);
        CREATE INDEX IF NOT EXISTS idx_ds09_cc_tx_merchant ON ds09_cc_transactions(merchant);
        CREATE INDEX IF NOT EXISTS idx_ds09_cc_tx_category ON ds09_cc_transactions(tx_category);
        CREATE INDEX IF NOT EXISTS idx_ds09_cc_tx_stmt ON ds09_cc_transactions(statement_id);
        CREATE INDEX IF NOT EXISTS idx_ds09_fund_date ON ds09_fund_statements(statement_date);
        CREATE INDEX IF NOT EXISTS idx_ds09_fund_name ON ds09_fund_statements(fund_name);
        CREATE INDEX IF NOT EXISTS idx_ds09_fund_investor ON ds09_fund_statements(investor_name);
    """)
    db.commit()
    print("ds09_cc_statements, ds09_cc_transactions, ds09_fund_statements tables created.")


# ---------------------------------------------------------------------------
# CC Statement Parser
# ---------------------------------------------------------------------------

def _parse_billing_period(text):
    """Extract billing period dates from statement header."""
    # Pattern: "Billing Period: 10/27/16- 11/26/16" or "Billing Period 03/27/16- 04/26/16"
    # OCR may mangle: "Sling Period", "Wing Period", "Billing Pend"
    m = re.search(r'(?:Billing|Sling|Wing|illing)\s*(?:Period|Pend|Penod)[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))
    # Fallback: look for "Statement" near two dates
    m = re.search(r'(?:Statement|sraternem)\s.*?(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})', text, re.IGNORECASE)
    if m:
        return normalize_date(m.group(1)), normalize_date(m.group(2))
    return None, None


def _parse_card_last4(text):
    """Extract last 4 digits of card number."""
    m = re.search(r'Card\s+Number\s+Ending\s+in\s*[:\s]*(\d{4})', text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'Card\s+ending\s+(?:in\s+)?(\d{4})', text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _parse_statement_balance(text):
    """Extract statement balance from Activity Summary section."""
    m = re.search(r'Statement\s+Balance\s+\$?([\d,.]+)', text)
    if m:
        return _dollar(m.group(1))
    return None


def _parse_previous_balance(text):
    """Extract previous balance."""
    m = re.search(r'Prev(?:ious|\.\.ous)?\s+Balance\s+\$?([\d,.]+)', text, re.IGNORECASE)
    if m:
        return _dollar(m.group(1))
    return None


def _parse_credit_line(text):
    """Extract credit line."""
    m = re.search(r'Credit\s+[Ll]ine\s+\$?([\d,.]+)', text)
    if m:
        return _dollar(m.group(1))
    return None


def _parse_amount_from_line(amount_str):
    """Parse an amount from a CC transaction line. Handles OCR noise."""
    # Clean OCR artifacts
    amount_str = amount_str.strip()
    # Remove leading - or . noise
    amount_str = re.sub(r'^[.\s]+', '', amount_str)
    # Handle negative (payment): -$95.68 or ($95.68)
    negative = False
    if amount_str.startswith('-') or amount_str.startswith('('):
        negative = True
        amount_str = amount_str.lstrip('-').strip('()')
    # Strip $ and any OCR spaces within the number
    amount_str = amount_str.replace('$', '').replace(' ', '')
    try:
        val = _dollar(amount_str)
        if val is not None and negative:
            val = -val
        return val
    except Exception:
        return None


def _extract_cc_transactions(text, file_id, efta_id, run_id):
    """Extract individual transaction lines from the Activity section.

    OCR typically produces one continuous line with no newlines, so we use
    finditer to locate all MM/DD + description + $amount patterns directly.
    """
    transactions = []

    # Find the "Activity for" section
    activity_match = re.search(r'Activity\s+for\s+.*?Card\s+end', text, re.IGNORECASE)
    if not activity_match:
        return transactions

    activity_text = text[activity_match.start():]
    # Truncate at fine print / legal text
    end_match = re.search(r'(?:Interest\s+Charge\s+Calculation|billing\s+period\s+if\s+you|Your\s+Annual\s+Percentage)', activity_text, re.IGNORECASE)
    if end_match:
        activity_text = activity_text[:end_match.start()]

    # Find all transaction patterns: MM/DD DESCRIPTION [-]$AMOUNT
    # Amount is preceded by space and has $ or -$, ends before next date or "Total" or section header
    tx_pattern = re.compile(
        r'(\d{2}/\d{2})\s+'                    # date MM/DD
        r'(.+?)\s+'                             # description (non-greedy)
        r'(-?\$[\d,. ]+\.\d{2})'               # amount with $ sign
    )

    seen = set()

    # Build a position map of section headers to determine category
    # Scan for "Payments" / "Purchases" / "Cash Advances" headers with positions
    section_markers = []
    for sm in re.finditer(r'\b(Payments?|Purchases?|Cash\s+Advance|Other\s+Credits?|Fees?|Interest\s+Charged?)\b', activity_text, re.IGNORECASE):
        word = sm.group(1).lower()
        if word.startswith('payment'):
            section_markers.append((sm.start(), 'payment'))
        elif word.startswith('purchase'):
            section_markers.append((sm.start(), 'purchase'))
        elif 'cash' in word:
            section_markers.append((sm.start(), 'cash_advance'))
        elif 'credit' in word:
            section_markers.append((sm.start(), 'credit'))
        elif word.startswith('fee'):
            section_markers.append((sm.start(), 'fee'))
        elif word.startswith('interest'):
            section_markers.append((sm.start(), 'interest'))

    def _get_category(pos):
        """Determine category based on position relative to section headers."""
        cat = 'purchase'  # default
        for marker_pos, marker_cat in section_markers:
            if marker_pos <= pos:
                cat = marker_cat
            else:
                break
        return cat

    for m in tx_pattern.finditer(activity_text):
        date_str = m.group(1)
        description = m.group(2).strip()
        amount_str = m.group(3).strip()

        # Skip "Total" lines that happen to match
        if re.match(r'^Total', description, re.IGNORECASE):
            continue
        # Skip "Summary" lines
        if re.match(r'^Summary', description, re.IGNORECASE):
            continue

        # Clean description: remove trailing section headers that got absorbed
        description = re.sub(r'\s+(?:Total\s+\w+\s+Activity|Purchases?|Payments?)\s*$', '', description, flags=re.IGNORECASE)
        description = re.sub(r'\s+(?:Summa(?:ry)?\s+of\s+Fees)', '', description, flags=re.IGNORECASE)

        amount = _parse_amount_from_line(amount_str)
        if amount is None:
            continue

        # Determine category
        cat = _get_category(m.start())
        if 'PAYMENT THANK YOU' in description.upper():
            cat = 'payment'
            if amount > 0:
                amount = -amount
        elif 'INTEREST CHARGE' in description.upper():
            cat = 'interest'

        # Extract merchant and location from description
        merchant = description
        location = None
        loc_match = re.match(r'^(.+?)\s+([A-Z][A-Za-z .]+)\s+([A-Z]{2})$', description)
        if loc_match:
            merchant = loc_match.group(1)
            location = f"{loc_match.group(2)}, {loc_match.group(3)}"

        # Dedup
        key = (date_str, description, amount)
        if key in seen:
            continue
        seen.add(key)

        transactions.append({
            'file_id': file_id,
            'efta_id': efta_id,
            'tx_date': date_str,
            'description': description,
            'merchant': merchant,
            'location': location,
            'amount': amount,
            'tx_category': cat,
            'confidence': 0.85,
            'parser_version': PARSER_VERSION,
            'extract_run_id': run_id,
        })

    return transactions


def _resolve_tx_year(billing_end, tx_date_mmdd):
    """Resolve MM/DD to full date using billing end date for year context."""
    if not billing_end or not tx_date_mmdd:
        return None
    try:
        # billing_end is YYYY-MM-DD
        bill_year = int(billing_end[:4])
        bill_month = int(billing_end[5:7])
        tx_month = int(tx_date_mmdd.split('/')[0])
        tx_day = int(tx_date_mmdd.split('/')[1])

        # If tx month > billing month, it's from previous year
        # (e.g., billing ends Jan, tx in Dec)
        if tx_month > bill_month + 1:
            year = bill_year - 1
        else:
            year = bill_year

        return f"{year}-{tx_month:02d}-{tx_day:02d}"
    except (ValueError, IndexError):
        return None


def parse_cc_statements(db, limit=None):
    """Parse UBS Visa credit card statements from DS09."""
    run_id = _run_id()

    query = """
        SELECT f.id as file_id, f.filename, tc.extracted_text
        FROM files f
        JOIN text_cache tc ON f.id = tc.file_id
        WHERE f.dataset = ?
        AND tc.extracted_text LIKE '%Card Number Ending%'
        AND (tc.extracted_text LIKE '%Activity for%' OR tc.extracted_text LIKE '%Activity Summary%')
        AND (tc.extracted_text LIKE '%MAXWELL%' OR tc.extracted_text LIKE '%Visa%Signature%')
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = db.execute(query, (DS09_DATASET,)).fetchall()
    print(f"Found {len(rows)} CC statement candidates")

    stmt_count = 0
    tx_count = 0

    for row in rows:
        file_id = row['file_id']
        text = row['extracted_text']
        efta_id = extract_efta_id(text) or row['filename'].replace('.pdf', '')

        # Parse statement header
        billing_start, billing_end = _parse_billing_period(text)
        card_last4 = _parse_card_last4(text)
        statement_balance = _parse_statement_balance(text)
        previous_balance = _parse_previous_balance(text)
        credit_line = _parse_credit_line(text)

        # Cardholder: usually "GHISLAINE MAXWELL" or OCR variants
        cardholder = None
        ch_match = re.search(r'(?:Prepared\s+for|Activity\s+for)[:\s]+([A-Z][A-Z\s]+?)(?:\s+Primary|\s+-\s*Card|\s+Card)', text, re.IGNORECASE)
        if ch_match:
            cardholder = ch_match.group(1).strip()
            # Clean OCR: "GI IISLA1NE" -> leave as-is, normalize later
            cardholder = re.sub(r'\s+', ' ', cardholder)

        # Calculate payments/purchases totals from text
        payments_total = None
        purchases_total = None
        pt_match = re.search(r'[-–]\s*Payments?\s+\$?([\d,.]+)', text)
        if pt_match:
            payments_total = _dollar(pt_match.group(1))
        pu_match = re.search(r'[+*]\s*(?:Purchases?|Paimiases)\s+\$?([\d,.]+)', text)
        if pu_match:
            purchases_total = _dollar(pu_match.group(1))

        # Insert statement
        try:
            cur = db.execute("""
                INSERT OR IGNORE INTO ds09_cc_statements
                (file_id, efta_id, cardholder, card_last4, billing_start, billing_end,
                 previous_balance, payments_total, purchases_total, statement_balance,
                 credit_line, parser_version, extract_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_id, efta_id, cardholder, card_last4, billing_start, billing_end,
                  previous_balance, payments_total, purchases_total, statement_balance,
                  credit_line, PARSER_VERSION, run_id))
            if cur.rowcount == 0:
                continue
            stmt_id = cur.lastrowid
            stmt_count += 1
        except sqlite3.IntegrityError:
            continue

        # Parse individual transactions
        transactions = _extract_cc_transactions(text, file_id, efta_id, run_id)

        for tx in transactions:
            # Resolve year from billing period
            full_date = _resolve_tx_year(billing_end, tx['tx_date'])
            if full_date:
                tx['tx_date'] = full_date

            try:
                db.execute("""
                    INSERT OR IGNORE INTO ds09_cc_transactions
                    (statement_id, file_id, efta_id, tx_date, description, merchant,
                     location, amount, tx_category, confidence, parser_version, extract_run_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (stmt_id, tx['file_id'], tx['efta_id'], tx['tx_date'],
                      tx['description'], tx['merchant'], tx['location'],
                      tx['amount'], tx['tx_category'], tx['confidence'],
                      tx['parser_version'], tx['extract_run_id']))
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    tx_count += 1
            except sqlite3.IntegrityError:
                pass

    db.commit()
    print(f"Parsed {stmt_count} CC statements, {tx_count} transactions")
    return stmt_count, tx_count


# ---------------------------------------------------------------------------
# Fund Investor Statement Parser
# ---------------------------------------------------------------------------

def _parse_fund_amount(text_val):
    """Parse a fund statement amount that may use periods as thousands separators."""
    if not text_val:
        return None
    text_val = text_val.strip()
    negative = False
    if text_val.startswith('(') and text_val.endswith(')'):
        negative = True
        text_val = text_val[1:-1]
    if text_val.startswith('-'):
        negative = True
        text_val = text_val[1:]

    text_val = text_val.replace('$', '').replace(' ', '')

    # Detect period-as-thousands: "46.193.632.11" has multiple periods
    if text_val.count('.') >= 2:
        # Split on last period — that's the decimal
        parts = text_val.rsplit('.', 1)
        integer_part = parts[0].replace('.', '').replace(',', '')
        decimal_part = parts[1] if len(parts) > 1 else '00'
        try:
            val = float(f"{integer_part}.{decimal_part}")
            return -val if negative else val
        except ValueError:
            return None

    # Standard format with comma thousands
    text_val = text_val.replace(',', '')
    try:
        val = float(text_val)
        return -val if negative else val
    except ValueError:
        return None


def _parse_return_pct(text_val):
    """Parse a percentage value like '0.09%' or '5.99%' or '-1.81%'."""
    if not text_val:
        return None
    text_val = text_val.strip().rstrip('%')
    negative = False
    if text_val.startswith('(') and text_val.endswith(')'):
        negative = True
        text_val = text_val[1:-1]
    if text_val.startswith('-'):
        negative = True
        text_val = text_val[1:]
    try:
        val = float(text_val)
        return -val if negative else val
    except ValueError:
        return None


def parse_fund_statements(db, limit=None):
    """Parse Boothbay (and similar) fund investor statements from DS09."""
    run_id = _run_id()

    query = """
        SELECT f.id as file_id, f.filename, tc.extracted_text
        FROM files f
        JOIN text_cache tc ON f.id = tc.file_id
        WHERE f.dataset = ?
        AND tc.extracted_text LIKE '%Individual Account Statement%'
        AND tc.extracted_text LIKE '%Ending Balance%'
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = db.execute(query, (DS09_DATASET,)).fetchall()
    print(f"Found {len(rows)} fund statement candidates")

    count = 0
    for row in rows:
        file_id = row['file_id']
        text = row['extracted_text']
        efta_id = extract_efta_id(text) or row['filename'].replace('.pdf', '')

        # Fund name: first line usually "Boothbay Absolute Return Strategies LP"
        fund_name = None
        fn_match = re.match(r'^(.+?(?:LP|LLC|Inc|Fund|Partners))\b', text.strip(), re.IGNORECASE)
        if fn_match:
            fund_name = fn_match.group(1).strip()

        # Investor name/number/class
        investor_name = None
        investor_number = None
        investor_class = None
        inv_match = re.search(r'Investor\s+No[:\s]+(\w+)', text, re.IGNORECASE)
        if inv_match:
            investor_number = inv_match.group(1)
        cls_match = re.search(r'Class[:\s]+([A-Z0-9\-]+)', text, re.IGNORECASE)
        if cls_match:
            investor_class = cls_match.group(1)

        # Investor name: look for entity before "6100 Red Hook" or after investor number
        inv_name_match = re.search(r'(?:Southern Financial|Financial Trust|HBRK|Zorro)[^,\n]*(?:LLC|Inc|LP|Associates)?', text, re.IGNORECASE)
        if inv_name_match:
            investor_name = inv_name_match.group(0).strip()

        # Statement date: "Month Ended: December 31, 2018"
        statement_date = None
        sd_match = re.search(r'Month\s+Ended[:\s]+(\w+\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE)
        if sd_match:
            try:
                raw_date = sd_match.group(1).replace(',', '')
                dt = datetime.strptime(raw_date, "%B %d %Y")
                statement_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        # Extract financial data from the MTD/YTD table
        # Pattern: "Beginning Balance    46,193,632.11  46,399,880.78"
        beginning_mtd = None
        beginning_ytd = None
        bb_match = re.search(r'Beginning\s+Balance\s+([\d.,()]+)\s+([\d.,()]+)', text, re.IGNORECASE)
        if bb_match:
            beginning_mtd = _parse_fund_amount(bb_match.group(1))
            beginning_ytd = _parse_fund_amount(bb_match.group(2))
        elif re.search(r'Beginning\s+Balance\s+([\d.,()]+)', text, re.IGNORECASE):
            bb_match = re.search(r'Beginning\s+Balance\s+([\d.,()]+)', text, re.IGNORECASE)
            beginning_mtd = _parse_fund_amount(bb_match.group(1))

        additions = None
        add_match = re.search(r'Additions?\s+([\d.,()]+)', text, re.IGNORECASE)
        if add_match:
            additions = _parse_fund_amount(add_match.group(1))

        redemptions = None
        red_match = re.search(r'Redemptions?\s+([\d.,()]+)', text, re.IGNORECASE)
        if red_match:
            redemptions = _parse_fund_amount(red_match.group(1))

        net_income_mtd = None
        net_income_ytd = None
        ni_match = re.search(r'Net\s+Income\s+([\d.,()-]+)\s+([\d.,()-]+)', text, re.IGNORECASE)
        if ni_match:
            net_income_mtd = _parse_fund_amount(ni_match.group(1))
            net_income_ytd = _parse_fund_amount(ni_match.group(2))
        elif re.search(r'Net\s+Income\s+([\d.,()-]+)', text, re.IGNORECASE):
            ni_match = re.search(r'Net\s+Income\s+([\d.,()-]+)', text, re.IGNORECASE)
            net_income_mtd = _parse_fund_amount(ni_match.group(1))

        ending_balance = None
        eb_match = re.search(r'Ending\s+Balance\s+([\d.,]+)', text, re.IGNORECASE)
        if eb_match:
            ending_balance = _parse_fund_amount(eb_match.group(1))

        return_mtd = None
        return_ytd = None
        rr_match = re.search(r'Rate\s+of\s+Return\s+([\d.%-]+)\s+([\d.%-]+)', text, re.IGNORECASE)
        if rr_match:
            return_mtd = _parse_return_pct(rr_match.group(1))
            return_ytd = _parse_return_pct(rr_match.group(2))

        # Must have at least ending balance to be worth inserting
        if ending_balance is None and beginning_mtd is None:
            continue

        try:
            db.execute("""
                INSERT OR IGNORE INTO ds09_fund_statements
                (file_id, efta_id, fund_name, investor_name, investor_number, investor_class,
                 statement_date, beginning_balance_mtd, beginning_balance_ytd,
                 additions, redemptions, net_income_mtd, net_income_ytd,
                 ending_balance, return_mtd, return_ytd, currency,
                 confidence, parser_version, extract_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?)
            """, (file_id, efta_id, fund_name, investor_name, investor_number, investor_class,
                  statement_date, beginning_mtd, beginning_ytd,
                  additions, redemptions, net_income_mtd, net_income_ytd,
                  ending_balance, return_mtd, return_ytd,
                  0.9, PARSER_VERSION, run_id))
            if db.execute("SELECT changes()").fetchone()[0] > 0:
                count += 1
        except sqlite3.IntegrityError:
            pass

    db.commit()
    print(f"Parsed {count} fund statements")
    return count


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(db):
    """Print extraction summary."""
    print("=" * 70)
    print("DS09 Financial Statement Extraction Report")
    print("=" * 70)

    # CC Statements
    row = db.execute("SELECT COUNT(*) as cnt FROM ds09_cc_statements").fetchone()
    print(f"\nCredit Card Statements: {row['cnt']}")
    row = db.execute("SELECT COUNT(*) as cnt FROM ds09_cc_transactions").fetchone()
    print(f"Credit Card Transactions: {row['cnt']}")

    # CC Summary
    row = db.execute("""
        SELECT COUNT(DISTINCT statement_id) as stmts,
               COUNT(*) as txns,
               SUM(CASE WHEN tx_category = 'purchase' THEN amount ELSE 0 END) as total_purchases,
               SUM(CASE WHEN tx_category = 'payment' THEN amount ELSE 0 END) as total_payments,
               MIN(tx_date) as earliest,
               MAX(tx_date) as latest
        FROM ds09_cc_transactions
    """).fetchone()
    if row['stmts']:
        print(f"  Statements with transactions: {row['stmts']}")
        print(f"  Total purchases: ${row['total_purchases']:,.2f}" if row['total_purchases'] else "  Total purchases: $0.00")
        print(f"  Total payments: ${row['total_payments']:,.2f}" if row['total_payments'] else "  Total payments: $0.00")
        print(f"  Date range: {row['earliest']} to {row['latest']}")

    # Cardholders
    rows = db.execute("""
        SELECT cardholder, COUNT(*) as cnt, card_last4
        FROM ds09_cc_statements
        GROUP BY cardholder, card_last4
        ORDER BY cnt DESC
    """).fetchall()
    if rows:
        print("\n  Cardholders:")
        for r in rows:
            print(f"    {r['cardholder'] or 'Unknown'} (****{r['card_last4'] or '????'}): {r['cnt']} statements")

    # Top merchants
    rows = db.execute("""
        SELECT merchant, COUNT(*) as cnt, SUM(amount) as total
        FROM ds09_cc_transactions
        WHERE tx_category = 'purchase'
        GROUP BY merchant
        ORDER BY total DESC
        LIMIT 15
    """).fetchall()
    if rows:
        print("\n  Top Merchants by Spend:")
        for r in rows:
            print(f"    {r['merchant']}: ${r['total']:,.2f} ({r['cnt']} txns)")

    # Fund Statements
    print()
    row = db.execute("SELECT COUNT(*) as cnt FROM ds09_fund_statements").fetchone()
    print(f"Fund Investor Statements: {row['cnt']}")

    rows = db.execute("""
        SELECT fund_name, investor_name, COUNT(*) as cnt,
               MIN(statement_date) as earliest, MAX(statement_date) as latest,
               MIN(ending_balance) as min_bal, MAX(ending_balance) as max_bal
        FROM ds09_fund_statements
        GROUP BY fund_name, investor_name
        ORDER BY max_bal DESC
    """).fetchall()
    if rows:
        print("\n  Fund/Investor Summaries:")
        for r in rows:
            print(f"    {r['fund_name'] or 'Unknown'} / {r['investor_name'] or 'Unknown'}")
            print(f"      {r['cnt']} statements, {r['earliest']} to {r['latest']}")
            print(f"      Balance range: ${r['min_bal']:,.2f} to ${r['max_bal']:,.2f}" if r['min_bal'] else "      Balance: N/A")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Query commands
# ---------------------------------------------------------------------------

def query_transactions(db, args):
    """Query CC transactions with filters."""
    conditions = ["1=1"]
    params = []

    if args.merchant:
        conditions.append("merchant LIKE ?")
        params.append(f"%{args.merchant}%")
    if args.amount_min:
        conditions.append("amount >= ?")
        params.append(args.amount_min)
    if args.date_start:
        conditions.append("tx_date >= ?")
        params.append(args.date_start)
    if args.date_end:
        conditions.append("tx_date <= ?")
        params.append(args.date_end)
    if args.category:
        conditions.append("tx_category = ?")
        params.append(args.category)

    where = " AND ".join(conditions)
    limit = args.limit or 50

    rows = db.execute(f"""
        SELECT t.tx_date, t.description, t.merchant, t.location,
               t.amount, t.tx_category, t.efta_id
        FROM ds09_cc_transactions t
        WHERE {where}
        ORDER BY t.tx_date DESC
        LIMIT ?
    """, params + [limit]).fetchall()

    print(f"{'Date':<12} {'Category':<10} {'Amount':>10} {'Merchant':<35} {'EFTA'}")
    print("-" * 90)
    for r in rows:
        amt = f"${r['amount']:,.2f}" if r['amount'] else "N/A"
        print(f"{r['tx_date'] or 'N/A':<12} {r['tx_category']:<10} {amt:>10} {(r['merchant'] or '')[:35]:<35} {r['efta_id'] or ''}")


def merchants_report(db):
    """Top merchants by spend."""
    rows = db.execute("""
        SELECT merchant, COUNT(*) as cnt, SUM(amount) as total,
               AVG(amount) as avg_amt, MIN(tx_date) as first, MAX(tx_date) as last
        FROM ds09_cc_transactions
        WHERE tx_category = 'purchase'
        GROUP BY merchant
        ORDER BY total DESC
        LIMIT 30
    """).fetchall()

    print(f"{'Merchant':<40} {'Count':>5} {'Total':>12} {'Avg':>10} {'First':<12} {'Last'}")
    print("-" * 100)
    for r in rows:
        print(f"{(r['merchant'] or '')[:40]:<40} {r['cnt']:>5} ${r['total']:>10,.2f} ${r['avg_amt']:>8,.2f} {r['first'] or 'N/A':<12} {r['last'] or 'N/A'}")


def monthly_report(db):
    """Monthly CC spend summary."""
    rows = db.execute("""
        SELECT substr(tx_date, 1, 7) as month,
               COUNT(*) as txns,
               SUM(CASE WHEN tx_category = 'purchase' THEN amount ELSE 0 END) as purchases,
               SUM(CASE WHEN tx_category = 'payment' THEN amount ELSE 0 END) as payments
        FROM ds09_cc_transactions
        WHERE tx_date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """).fetchall()

    print(f"{'Month':<10} {'Txns':>5} {'Purchases':>12} {'Payments':>12}")
    print("-" * 45)
    for r in rows:
        purch = f"${r['purchases']:,.2f}" if r['purchases'] else "$0.00"
        pay = f"${r['payments']:,.2f}" if r['payments'] else "$0.00"
        print(f"{r['month']:<10} {r['txns']:>5} {purch:>12} {pay:>12}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="DS09 Financial Statement Extractor")
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('create-tables')

    p = sub.add_parser('parse-cc')
    p.add_argument('--limit', type=int)

    p = sub.add_parser('parse-fund')
    p.add_argument('--limit', type=int)

    p = sub.add_parser('parse-all')
    p.add_argument('--limit', type=int)

    sub.add_parser('report')

    p = sub.add_parser('query')
    p.add_argument('--merchant', type=str)
    p.add_argument('--amount-min', type=float)
    p.add_argument('--date-start', type=str)
    p.add_argument('--date-end', type=str)
    p.add_argument('--category', type=str)
    p.add_argument('--limit', type=int, default=50)

    sub.add_parser('merchants')
    sub.add_parser('monthly')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    db = get_db()

    if args.command == 'create-tables':
        create_tables(db)
    elif args.command == 'parse-cc':
        create_tables(db)
        parse_cc_statements(db, args.limit)
    elif args.command == 'parse-fund':
        create_tables(db)
        parse_fund_statements(db, args.limit)
    elif args.command == 'parse-all':
        create_tables(db)
        parse_cc_statements(db, args.limit)
        parse_fund_statements(db, args.limit)
    elif args.command == 'report':
        report(db)
    elif args.command == 'query':
        query_transactions(db, args)
    elif args.command == 'merchants':
        merchants_report(db)
    elif args.command == 'monthly':
        monthly_report(db)

    db.close()


if __name__ == '__main__':
    main()
