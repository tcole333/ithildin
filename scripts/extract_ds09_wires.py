#!/usr/bin/env python3
"""
Extract wire transfers, check disbursements, and wire instructions from DS09
(Epstein email production, EFTA00039025-EFTA01262781) in lmsband_epstein_files.db.

Document types:
  - Deutsche Bank ebanking wire confirmations (~87 in DS09)
  - BELLAKLEIN/RICHARDKAHN email threads with wire references (~2500)
  - Trust fund disbursement records with ck# check numbers (~56)

Usage:
  uv run python scripts/extract_ds09_wires.py create-tables
  uv run python scripts/extract_ds09_wires.py parse-confirmations [--limit N]
  uv run python scripts/extract_ds09_wires.py parse-wire-threads [--limit N]
  uv run python scripts/extract_ds09_wires.py parse-checks [--limit N]
  uv run python scripts/extract_ds09_wires.py parse-all [--limit N]
  uv run python scripts/extract_ds09_wires.py report
  uv run python scripts/extract_ds09_wires.py query [--entity X] [--amount-min N] [--date-start D] [--date-end D]
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

# Import shared utilities from DS10 parser
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.parse_ds10_financials import (
    extract_efta_id,
    normalize_date,
    parse_dollar_amount,
)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'lmsband_epstein_files.db')
PARSER_VERSION = "ds09_wire_v1"
DS09_DATASET = 9


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
        CREATE TABLE IF NOT EXISTS ds09_transactions (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            efta_id TEXT,
            tx_date TEXT,
            amount REAL,
            currency TEXT DEFAULT 'USD',
            direction TEXT,
            sender TEXT,
            sender_account TEXT,
            receiver TEXT,
            receiver_account TEXT,
            bank TEXT,
            reference TEXT,
            confirmation_number TEXT,
            operator TEXT,
            tx_type TEXT,
            raw_extract TEXT,
            confidence REAL,
            parser_version TEXT,
            extract_run_id TEXT,
            UNIQUE(file_id, tx_date, amount, sender, receiver)
        );

        CREATE INDEX IF NOT EXISTS idx_ds09_tx_sender ON ds09_transactions(sender);
        CREATE INDEX IF NOT EXISTS idx_ds09_tx_receiver ON ds09_transactions(receiver);
        CREATE INDEX IF NOT EXISTS idx_ds09_tx_date ON ds09_transactions(tx_date);
        CREATE INDEX IF NOT EXISTS idx_ds09_tx_amount ON ds09_transactions(amount);
        CREATE INDEX IF NOT EXISTS idx_ds09_tx_efta ON ds09_transactions(efta_id);
        CREATE INDEX IF NOT EXISTS idx_ds09_tx_type ON ds09_transactions(tx_type);
    """)
    db.commit()
    print("ds09_transactions table created.")


# ---------------------------------------------------------------------------
# Insert helper
# ---------------------------------------------------------------------------

def insert_transactions(db, transactions):
    inserted = 0
    run_id = _run_id()
    for tx in transactions:
        if tx.get('amount') and tx['amount'] > 10_000_000_000:
            continue
        if tx.get('tx_date'):
            try:
                yr = int(tx['tx_date'][:4])
                if yr < 1990 or yr > 2025:
                    continue
            except (ValueError, IndexError):
                continue
        try:
            db.execute('''
                INSERT OR IGNORE INTO ds09_transactions
                (file_id, efta_id, tx_date, amount, currency, direction,
                 sender, sender_account, receiver, receiver_account,
                 bank, reference, confirmation_number, operator, tx_type,
                 raw_extract, confidence, parser_version, extract_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx.get('file_id'),
                tx.get('efta_id'),
                tx.get('tx_date'),
                tx.get('amount'),
                tx.get('currency', 'USD'),
                tx.get('direction', 'outgoing'),
                tx.get('sender'),
                tx.get('sender_account'),
                tx.get('receiver'),
                tx.get('receiver_account'),
                tx.get('bank'),
                tx.get('reference'),
                tx.get('confirmation_number'),
                tx.get('operator'),
                tx.get('tx_type'),
                tx.get('raw_extract', '')[:2000],
                tx.get('confidence'),
                tx.get('parser_version', PARSER_VERSION),
                tx.get('extract_run_id', run_id),
            ))
            if db.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    return inserted


# ---------------------------------------------------------------------------
# Fetch DS09 documents
# ---------------------------------------------------------------------------

def fetch_docs(db, text_filter, limit=None):
    """Fetch DS09 docs matching a text filter SQL fragment."""
    sql = f"""
        SELECT f.id AS file_id, f.filename, t.extracted_text
        FROM files f
        JOIN text_cache t ON f.id = t.file_id
        WHERE f.dataset = {DS09_DATASET}
          AND ({text_filter})
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.execute(sql).fetchall()


# ---------------------------------------------------------------------------
# Parser 1: Structured wire confirmations
# ---------------------------------------------------------------------------

def _extract_account_name(text):
    """Extract account holder and last-4 from account field text.
    E.g. "Jeffrey Epstein - NOW -'9691" -> ("Jeffrey Epstein", "9691")
    E.g. "LSJE, LLC - DDA - '9295" -> ("LSJE, LLC", "9295")
    """
    if not text:
        return None, None
    # Find last-4 digits after ' or - or *
    acct_match = re.search(r"['\-\*](\d{4})", text)
    last4 = acct_match.group(1) if acct_match else None
    # Account holder is everything before the first " - "
    holder_match = re.match(r'^(.+?)\s*-\s', text)
    holder = holder_match.group(1).strip() if holder_match else text.strip()
    # Clean OCR artifacts from holder
    holder = re.sub(r'\s+', ' ', holder)
    return holder, last4


def _infer_bank(text):
    """Infer bank from document text."""
    if 'db.ebanking-services.com' in text or 'Deutsche Bank' in text or 'DBTCA' in text:
        return 'Deutsche Bank'
    if 'WELLS FARGO' in text:
        return 'Wells Fargo'
    if 'JPM' in text.upper() or 'JPMORGAN' in text.upper():
        return 'JPMorgan'
    return 'Deutsche Bank'  # Default for BELLAKLEIN portal


def _normalize_currency(raw):
    """Normalize OCR-mangled currency codes."""
    if not raw:
        return 'USD'
    raw = raw.strip().upper()
    if raw in ('USD', 'USO', 'LIED', 'USI', 'US0', 'LSD'):
        return 'USD'
    if raw in ('EUR', 'ELIR', 'ELR', 'ELJR'):
        return 'EUR'
    if raw in ('GBP', 'G8P', 'G13P'):
        return 'GBP'
    if raw == 'CHF':
        return 'CHF'
    # Pass through valid ISO currency codes
    if len(raw) == 3 and raw.isalpha():
        return raw
    return 'USD'


def parse_confirmation_layout_b(file_id, filename, text):
    """Parse key-value layout (Deutsche Bank WM portal with labeled fields).

    Handles two OCR sub-variants:
      1. Labels and values on same lines: "Transmitted: 02/07/2018..."
      2. Split: all labels first, then all values in order (common OCR artifact
         for two-column form layouts).
    """
    transactions = []
    efta_id = extract_efta_id(filename)

    # --- Strategy: extract fields by scanning for known value patterns ---
    # These work regardless of whether labels and values are adjacent or split.

    # Date: find MM/DD/YYYY pattern near "Transmitted" or after labels block
    all_dates = re.findall(r'(\d{2}/\d{2}/\d{4})', text)
    # Operator: BELLAKLEIN or RICHARDKAHN
    op_match = re.search(r'\b(BELLAKLEIN|RICHARDKAHN)\b', text)
    operator = op_match.group(1) if op_match else None

    # Confirmation number: large digit sequence before "1 of 1 received"
    conf_match = re.search(r'(\d{7,})\s+\d+\s+of\s+\d+\s+received', text)
    conf_num = conf_match.group(1) if conf_match else None

    # Transmitted date: first date in the document (before balance dates)
    tx_date = normalize_date(all_dates[0]) if all_dates else None

    # Template name: text after operator that looks like a name/description
    # In split layout: operator is followed by template name on next token
    template_name = None
    if operator:
        # Find text right after operator up to next account-like pattern
        after_op = text[text.index(operator) + len(operator):]
        tmpl_match = re.match(r'\s+(.+?)(?=\s+(?:Jeffrey|LSJE|Gratitude|Zorro|Plan D|NES|LLC|Inc))', after_op)
        if tmpl_match:
            candidate = tmpl_match.group(1).strip()
            # Template names contain "to" or are short descriptive strings
            if len(candidate) < 80 and not candidate.startswith('Recipient'):
                template_name = candidate

    # Account: look for account pattern "Name - TYPE - 'NNNN - DBTCA"
    acct_match = re.search(
        r'((?:Jeffrey Epstein|LSJE[,.]?\s*LLC|Gratitude America|Zorro Management|NES\b|Plan D)[^(]*?[\'*]\d{4})',
        text
    )
    account_text = acct_match.group(1).strip() if acct_match else None
    sender, sender_acct = _extract_account_name(account_text) if account_text else (None, None)

    # Send-on date: may differ from transmitted date
    send_date = None
    if len(all_dates) >= 3:
        # Third date is often send-on date (after transmitted and balance-as-of)
        send_date = normalize_date(all_dates[2])

    # Amount + Currency extraction
    # The wire amount appears AFTER wire type description ("Domestic wire", "Foreign currency
    # international wire") and BEFORE the currency code. Balance amounts appear in
    # "Balance as of:" parenthetical context — exclude those.
    amount, amt_conf = None, 0.0
    currency = 'USD'

    # Strategy 1: Find amount right after wire type keyword
    wt_match = re.search(
        r'(?:Domestic|Foreign\s+currency\s+international|International|USD\s+International)\s+wire\s+'
        r'(\d{2}/\d{2}/\d{4}\s+)?'  # optional date between wire type and amount
        r'([\d,.]+)\s*'
        r'([A-Z]{3})?',
        text, re.IGNORECASE
    )
    if wt_match:
        raw_amt = wt_match.group(2)
        # Fix OCR artifact: "34.51000" should be "34,510.00" (comma rendered as period,
        # more than 2 decimal places indicates thousands separator, not decimal)
        if re.match(r'^\d+\.\d{3,}$', raw_amt):
            # Reinterpret: period is thousands separator, last 2 digits are cents
            digits = raw_amt.replace('.', '')
            raw_amt = digits[:-2] + '.' + digits[-2:] if len(digits) > 2 else raw_amt
            amt_conf = 0.8  # Lower confidence for format correction
        amount, amt_conf_parsed = parse_dollar_amount(raw_amt)
        if amt_conf == 0.0:
            amt_conf = amt_conf_parsed
        if wt_match.group(3):
            currency = _normalize_currency(wt_match.group(3))

    # Strategy 2: Find amount on a line by itself (not in balance context)
    if amount is None:
        # Find all number-like tokens, exclude those near "Balance" or "$"
        for m in re.finditer(r'(?:^|\s)([\d,]+\.\d{2,5})\s', text):
            pos = m.start()
            context = text[max(0, pos-50):pos+50]
            if 'Balance' in context or '$' in context[max(0, pos-3-max(0,pos-50)):]:
                continue
            val, conf = parse_dollar_amount(m.group(1))
            if val and 1 <= val <= 50_000_000:
                amount = val
                amt_conf = conf
                break

    # If no currency found from wire type line, look for currency near "Currency:" label
    if currency == 'USD':
        # Check if there's a Currency: value in the split layout
        curr_match = re.search(r'Currency[:\s]+([A-Z]{3})', text)
        if curr_match:
            currency = _normalize_currency(curr_match.group(1))

    # Recipient: look for a name after recipient-related values
    receiver = None
    # Strategy 1: named entity after SWIFT/ABA bank info
    recip_name_match = re.search(
        r'(?:SWIFT|ABA)\s+.+?(?:Bank|NA|AG|PLC)\b[^A-Z]*([A-Z][a-zA-Z\s,.\-&]+?)(?:\s+\d|\s+\n|$)',
        text
    )
    if recip_name_match:
        candidate = recip_name_match.group(1).strip()
        if 3 < len(candidate) < 80:
            receiver = candidate

    # Strategy 2: extract from template name "X to Y"
    if not receiver and template_name:
        to_match = re.search(r'\bto\s+(.+)', template_name, re.IGNORECASE)
        if to_match:
            receiver = to_match.group(1).strip()

    # Strategy 3: look for Recipient name value in split layout
    if not receiver:
        # After "Additional information for recipient:" the values continue
        # Recipient name appears after bank address values
        recip_block = re.search(
            r'(?:Recipient name:|Recipient address|Additional information)[:\s]*\n?(.*?)(?=First Intermediary|Second Intermediary|Wire Initiator|EFTA\d)',
            text, re.DOTALL | re.IGNORECASE
        )
        if recip_block:
            # Look for a proper name in this block
            lines = [l.strip() for l in recip_block.group(1).split('\n') if l.strip()]
            for line in lines:
                # Skip addresses, reference text, bank info
                if re.match(r'^\d', line) or len(line) < 3:
                    continue
                if any(kw in line.lower() for kw in ['bank', 'swift', 'aba', 'iban', 'address', 'information']):
                    continue
                receiver = line[:80]
                break

    # If we still don't have a receiver, try the region after bank address values
    if not receiver:
        # Look for capitalized name after bank routing info
        after_bank = re.search(r'(?:LONDON|MONACO|CA|NY|NA)\s+([A-Z][a-zA-Z\s\-&.,]+?)(?:\s+\d|\s*$)', text)
        if after_bank:
            candidate = after_bank.group(1).strip().rstrip('.,')
            if 3 < len(candidate) < 80:
                receiver = candidate

    bank = _infer_bank(text)
    effective_date = send_date or tx_date

    if amount and effective_date:
        transactions.append({
            'file_id': file_id,
            'efta_id': efta_id,
            'tx_date': effective_date,
            'amount': amount,
            'currency': currency,
            'direction': 'outgoing',
            'sender': sender,
            'sender_account': sender_acct,
            'receiver': receiver,
            'bank': bank,
            'reference': template_name,
            'confirmation_number': conf_num,
            'operator': operator,
            'tx_type': 'wire_confirmation',
            'raw_extract': text[:1500],
            'confidence': 0.95 * amt_conf,
        })

    return transactions


def parse_confirmation_layout_a(file_id, filename, text):
    """Parse tabular layout (single-row table after column headers).

    Format: "Account  Template Name  Recipient Name  Amount  Currency  Effective Date  Confirmation Number  Approval Status"
    followed by one data row like:
    "Jeffrey Epstein - NOW -'9691  JEE to Arda  Mehmet Arda, ESQ.  6,000.00  USD  10/03/2018  1234567  1 of 1 received"
    """
    transactions = []
    efta_id = extract_efta_id(filename)

    # Operator
    op_match = re.search(r'\b(BELLAKLEIN|RICHARDKAHN)\b', text)
    operator = op_match.group(1) if op_match else None

    # All dates in text
    all_dates = re.findall(r'(\d{2}/\d{2}/\d{4})', text)

    # Find the data row: everything after the header line until EFTA marker or email start
    header_match = re.search(
        r'(?:Approval\s*\n\s*Status|Number\s+Approval\s+Status|Approval\s+Status)\s*\n(.+?)(?=\nEFTA\d|\nFrom[:\s]|\nMenu|\nHon,|$)',
        text, re.DOTALL
    )
    if not header_match:
        header_match = re.search(
            r'(?:Account\s+Template\s+Name.*?)\n(.+?)(?=\nEFTA\d|\nFrom[:\s]|$)',
            text, re.DOTALL
        )

    if header_match:
        data_block = header_match.group(1).strip()
        data_line = re.sub(r'\s*\n\s*', ' ', data_block)

        amounts = re.findall(r'([\d,]+\.\d{2})', data_line)
        dates = re.findall(r'(\d{2}/\d{2}/\d{4})', data_line)
        confs = re.findall(r'(\d{7,10})', data_line)
        currs = re.findall(r'\b(USD|USO|EUR|GBP|CHF|LIED|USI)\b', data_line)

        effective_date = normalize_date(dates[0]) if dates else (normalize_date(all_dates[0]) if all_dates else None)
        amount_raw = amounts[0] if amounts else None
        amount, amt_conf = parse_dollar_amount(amount_raw) if amount_raw else (None, 0.0)
        conf_num = confs[0] if confs else None
        currency = _normalize_currency(currs[0]) if currs else 'USD'

        sender, sender_acct = None, None
        receiver = None
        reference = None

        acct_pattern = re.search(r'^(.+?[\'*]\d{4})\s+(.+?)(?=\s+[\d,]+\.\d{2})', data_line)
        if acct_pattern:
            account_text = acct_pattern.group(1)
            middle = acct_pattern.group(2)
            sender, sender_acct = _extract_account_name(account_text)
            to_match = re.search(r'\bto\s+(.+)', middle, re.IGNORECASE)
            if to_match:
                recip_region = to_match.group(1).strip()
                reference = middle.strip()
                receiver = recip_region
            else:
                reference = middle.strip()
        else:
            # Fallback: find account pattern anywhere
            acct_match2 = re.search(
                r'((?:Jeffrey Epstein|LSJE|Gratitude|Zorro|NES|Plan D)[^\']*[\'*]\d{4})',
                data_line
            )
            if acct_match2:
                sender, sender_acct = _extract_account_name(acct_match2.group(1))

        if receiver:
            receiver = re.sub(r'\s+[\d,]+\.\d{2}.*$', '', receiver).strip()
            receiver = re.sub(r'\s+(USD|EUR|GBP|CHF|USO|LIED)\s*$', '', receiver).strip()

        bank = _infer_bank(text)

        if amount and effective_date:
            transactions.append({
                'file_id': file_id,
                'efta_id': efta_id,
                'tx_date': effective_date,
                'amount': amount,
                'currency': currency,
                'direction': 'outgoing',
                'sender': sender,
                'sender_account': sender_acct,
                'receiver': receiver,
                'bank': bank,
                'reference': reference,
                'confirmation_number': conf_num,
                'operator': operator or 'BELLAKLEIN',
                'tx_type': 'wire_confirmation',
                'raw_extract': text[:1500],
                'confidence': 0.90 * amt_conf,
            })

    return transactions


def parse_wire_confirmation(file_id, filename, text):
    """Route to Layout A or B parser based on document structure.

    Layout B (key-value): "Schedule Information" with labeled fields (or split labels/values).
    Layout A (tabular): Column headers followed by data rows.
    """
    # Layout B indicator: "Schedule Information" or "Template name:" label
    is_layout_b = bool(re.search(r'Schedule Information|Template\s+name:', text))
    # Layout A indicator: tabular column headers
    is_layout_a = bool(re.search(r'Account\s+Template\s+Name|Effective\s+Date\s+.*Confirmation', text, re.IGNORECASE))

    if is_layout_b:
        results = parse_confirmation_layout_b(file_id, filename, text)
        if results:
            return results
    if is_layout_a:
        results = parse_confirmation_layout_a(file_id, filename, text)
        if results:
            return results

    # Fallback: try both
    results = parse_confirmation_layout_b(file_id, filename, text)
    if not results:
        results = parse_confirmation_layout_a(file_id, filename, text)
    return results


def run_parse_confirmations(db, limit=None):
    """Parse structured wire confirmations."""
    # Wire Confirmation header AND either BELLAKLEIN/RICHARDKAHN or Deutsche Bank portal
    docs = fetch_docs(db,
        "t.extracted_text LIKE '%Wire Confirmation%' "
        "AND (t.extracted_text LIKE '%BELLAKLEIN%' OR t.extracted_text LIKE '%RICHARDKAHN%' "
        "     OR t.extracted_text LIKE '%db.ebanking%' OR t.extracted_text LIKE '%Deutsche Bank Wealth%')",
        limit=limit
    )
    print(f"Found {len(docs)} wire confirmation documents")
    total_tx = 0
    skipped = 0
    for doc in docs:
        txns = parse_wire_confirmation(doc['file_id'], doc['filename'], doc['extracted_text'])
        if txns:
            n = insert_transactions(db, txns)
            total_tx += n
        else:
            skipped += 1
    db.commit()
    print(f"Inserted {total_tx} wire confirmation transactions ({skipped} docs yielded no parse)")


# ---------------------------------------------------------------------------
# Parser 2: Wire instruction email threads
# ---------------------------------------------------------------------------

def _is_likely_money(raw_amt, preceding_ctx, following_ctx):
    """Check if a number is likely a dollar amount vs a year/zip/phone/page number."""
    # Must have $ prefix, comma separators, or .00 decimal to be money
    has_dollar = '$' in preceding_ctx[-5:] if preceding_ctx else False
    has_comma = ',' in raw_amt
    has_cents = re.search(r'\.\d{2}$', raw_amt)
    has_k_suffix = following_ctx[:3].strip().lower().startswith('k') if following_ctx else False

    # Reject common false positives
    try:
        val = float(raw_amt.replace(',', ''))
    except ValueError:
        return False

    # Years (2000-2025) without dollar sign or decimal
    if 2000 <= val <= 2030 and not has_dollar and not has_cents:
        return False
    # Zip codes (5-digit round numbers like 10022)
    if 10000 <= val <= 99999 and not has_dollar and not has_cents and not has_comma:
        return False
    # Phone-like numbers
    if val > 1000000 and not has_dollar and not has_cents and not has_comma:
        return False
    # Small numbers (< 100) without dollar sign are rarely wire amounts
    if val < 100 and not has_dollar and not has_k_suffix:
        return False
    # Numbers 100-999 without dollar sign or comma/decimal: could be street numbers, etc.
    if 100 <= val <= 999 and not has_dollar and not has_cents and not has_k_suffix:
        # Only accept if very close to wire keyword
        return False

    return True


def parse_wire_thread(file_id, filename, text):
    """Extract wire amounts from BELLAKLEIN/RICHARDKAHN email threads.

    Conservative extraction: requires explicit dollar signs or money formatting.
    """
    transactions = []
    efta_id = extract_efta_id(filename)

    # Skip if this is a structured wire confirmation (handled by parser 1)
    if re.search(r'Wire Confirmation', text[:200]):
        return []

    # Wire keyword pattern — words that indicate money movement
    wire_keywords = r'(?:wire|please\s+send|transfer|payment\s+of|pay\s+(?:from|to|today|tomorrow|him|her)|disburse)'

    # Dollar amount patterns — require explicit money formatting
    # Pattern 1: $N,NNN.NN or $N,NNN or $NNN
    # Pattern 2: N,NNN.NN (comma-formatted)
    # Pattern 3: NNk or NNK (shorthand)
    dollar_patterns = [
        re.compile(r'\$\s*([\d,]+(?:\.\d{2})?)', re.IGNORECASE),          # $150,000.00
        re.compile(r'([\d,]+\.\d{2})\s*(?:dollars?|usd)?', re.IGNORECASE), # 150,000.00
        re.compile(r'(\d{1,3}(?:,\d{3})+)\b'),                             # 150,000 (comma-formatted)
        re.compile(r'(\d+)\s*k\b', re.IGNORECASE),                         # 150k
    ]

    # Extract email dates for context
    email_dates = re.findall(r'Date:\s*(.+?)(?:\n|$)', text)

    # Find segments near wire keywords
    wire_segments = []
    for m in re.finditer(wire_keywords, text, re.IGNORECASE):
        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 250)
        segment = text[start:end]
        wire_segments.append((m.start(), segment))

    seen_amounts = set()
    for pos, segment in wire_segments:
        for pattern in dollar_patterns:
            for amt_match in pattern.finditer(segment):
                raw_amt = amt_match.group(1)
                preceding = segment[max(0, amt_match.start()-5):amt_match.start()]
                following = segment[amt_match.end():amt_match.end()+5]

                if not _is_likely_money(raw_amt, preceding, following):
                    continue

                amount, amt_conf = parse_dollar_amount(raw_amt)
                if amount is None or amount < 50:
                    continue
                # Cap: individual wire transfers > $50M are almost certainly parse errors
                if amount > 50_000_000:
                    continue

                # Handle k suffix
                if pattern.pattern.endswith(r'k\b', 0, -1) or (following.strip().lower().startswith('k')):
                    if amount < 10000:  # Only apply k if not already large
                        # Check if 'k' follows
                        if following.strip().lower().startswith('k'):
                            amount *= 1000

                # Dedup within document
                amount_key = round(amount, 2)
                if amount_key in seen_amounts:
                    continue
                seen_amounts.add(amount_key)

                tx_date = None
                for date_str in email_dates:
                    parsed = _try_parse_email_date(date_str)
                    if parsed:
                        tx_date = parsed
                        break

                receiver = _extract_nearby_recipient(segment, amt_match.start())

                sender = None
                from_match = re.search(r'From:\s*(?:.*?<)?(\S+@\S+)', text[:500])
                if from_match:
                    sender = from_match.group(1)

                ctx_start = max(0, pos - 100)
                ctx_end = min(len(text), pos + 400)
                raw_extract = text[ctx_start:ctx_end]

                confidence = 0.5
                # Higher confidence if explicit $ sign
                if '$' in preceding:
                    confidence = 0.65
                # Higher if comma-formatted
                if ',' in raw_amt:
                    confidence = max(confidence, 0.6)

                transactions.append({
                    'file_id': file_id,
                    'efta_id': efta_id,
                    'tx_date': tx_date,
                    'amount': amount,
                    'currency': 'USD',
                    'direction': 'outgoing',
                    'sender': sender,
                    'receiver': receiver,
                    'bank': 'Deutsche Bank',
                    'tx_type': 'wire_thread',
                    'raw_extract': raw_extract[:2000],
                    'confidence': confidence,
                    'operator': 'BELLAKLEIN',
                })

    return transactions


def _try_parse_email_date(date_str):
    """Try to parse an email Date header into ISO format."""
    date_str = date_str.strip()
    # Try common formats
    for fmt in [
        '%B %d, %Y',           # February 6, 2018
        '%B %d %Y',            # February 6 2018
        '%b %d, %Y',           # Feb 6, 2018
        '%m/%d/%Y',            # 02/06/2018
        '%A, %B %d, %Y',      # Tuesday, February 6, 2018
        '%A. %B %d. %Y',      # Tuesday. February 6. 2018 (OCR)
    ]:
        try:
            dt = datetime.strptime(date_str[:len(fmt)+10].strip(), fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue

    # Fallback: look for MM/DD/YYYY
    m = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_str)
    if m:
        return normalize_date(m.group(1))

    # Look for Month DD, YYYY
    m = re.search(r'(\w+\s+\d{1,2},?\s+\d{4})', date_str)
    if m:
        for fmt in ['%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y']:
            try:
                dt = datetime.strptime(m.group(1), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


def _extract_nearby_recipient(text, amount_pos):
    """Try to extract recipient name near a dollar amount mention."""
    # Look for "to <Name>" pattern near amount
    search_region = text[max(0, amount_pos-150):amount_pos+150]
    to_match = re.search(r'\bto\s+([A-Z][a-zA-Z\s&.,]+?)(?:\s+for\b|\s+from\b|\s*\n|\s+\d)', search_region)
    if to_match:
        name = to_match.group(1).strip().rstrip('.,')
        if 3 < len(name) < 80:
            return name

    # Look for "pay <Name>" pattern
    pay_match = re.search(r'\b(?:pay|send)\s+([A-Z][a-zA-Z\s&.,]+?)(?:\s+\$|\s+\d|\s*\n)', search_region, re.IGNORECASE)
    if pay_match:
        name = pay_match.group(1).strip().rstrip('.,')
        if 3 < len(name) < 80:
            return name

    return None


def run_parse_wire_threads(db, limit=None):
    """Parse wire instruction email threads."""
    docs = fetch_docs(db,
        "(t.extracted_text LIKE '%BELLAKLEIN%' OR t.extracted_text LIKE '%RICHARDKAHN%' "
        " OR t.extracted_text LIKE '%please wire%' OR t.extracted_text LIKE '%please send%wire%')"
        " AND t.extracted_text NOT LIKE 'Wire Confirmation%'",
        limit=limit
    )
    print(f"Found {len(docs)} wire thread documents")
    total_tx = 0
    docs_with_tx = 0
    for doc in docs:
        txns = parse_wire_thread(doc['file_id'], doc['filename'], doc['extracted_text'])
        if txns:
            n = insert_transactions(db, txns)
            total_tx += n
            if n > 0:
                docs_with_tx += 1
    db.commit()
    print(f"Inserted {total_tx} wire thread transactions from {docs_with_tx} documents")


# ---------------------------------------------------------------------------
# Parser 3: Check disbursements
# ---------------------------------------------------------------------------

def parse_check_disbursements(file_id, filename, text):
    """Parse check disbursement records (ck#NNNN payee amount)."""
    transactions = []
    efta_id = extract_efta_id(filename)

    # Pattern: date  ck#NNNN  payee  amount
    # Also: date  wire  payee  amount (wire disbursements in same format)
    # Example: "05/15/09 ck#6225 Podhurst & 50,000.00"
    ck_pattern = re.compile(
        r'(\d{2}/\d{2}/\d{2,4})\s+'      # date
        r'(ck#\d+|wire|CHECK|WIRE)\s+'     # type + number
        r'(.+?)\s+'                        # payee
        r'\$?([\d,]+\.\d{2})',             # amount
        re.IGNORECASE
    )

    for m in ck_pattern.finditer(text):
        date_raw = m.group(1)
        tx_ref = m.group(2).strip()
        payee = m.group(3).strip()
        amount_raw = m.group(4)

        # Normalize 2-digit year
        if len(date_raw.split('/')[-1]) == 2:
            parts = date_raw.split('/')
            yr = int(parts[2])
            yr = yr + 2000 if yr < 50 else yr + 1900
            date_raw = f"{parts[0]}/{parts[1]}/{yr}"

        tx_date = normalize_date(date_raw)
        amount, amt_conf = parse_dollar_amount(amount_raw)

        if amount is None or amount < 1:
            continue

        # Extract check number
        ck_match = re.match(r'ck#(\d+)', tx_ref, re.IGNORECASE)
        check_num = ck_match.group(1) if ck_match else None

        tx_type = 'check' if ck_match else 'wire_disbursement'

        # Context: surrounding lines
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 50)

        transactions.append({
            'file_id': file_id,
            'efta_id': efta_id,
            'tx_date': tx_date,
            'amount': amount,
            'currency': 'USD',
            'direction': 'outgoing',
            'receiver': payee,
            'reference': tx_ref,
            'confirmation_number': check_num,
            'tx_type': tx_type,
            'raw_extract': text[start:end],
            'confidence': 0.90 * amt_conf,
        })

    return transactions


def run_parse_checks(db, limit=None):
    """Parse check disbursement documents."""
    docs = fetch_docs(db, "t.extracted_text LIKE '%ck#%'", limit=limit)
    print(f"Found {len(docs)} check disbursement documents")
    total_tx = 0
    docs_with_tx = 0
    for doc in docs:
        txns = parse_check_disbursements(doc['file_id'], doc['filename'], doc['extracted_text'])
        if txns:
            n = insert_transactions(db, txns)
            total_tx += n
            if n > 0:
                docs_with_tx += 1
    db.commit()
    print(f"Inserted {total_tx} check transactions from {docs_with_tx} documents")


# ---------------------------------------------------------------------------
# parse-all
# ---------------------------------------------------------------------------

def run_parse_all(db, limit=None):
    print("=== DS09 Wire Transfer Extraction ===\n")
    run_parse_confirmations(db, limit=limit)
    print()
    run_parse_checks(db, limit=limit)
    print()
    run_parse_wire_threads(db, limit=limit)
    print()
    report(db)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(db):
    total = db.execute("SELECT COUNT(*) FROM ds09_transactions").fetchone()[0]
    print(f"=== DS09 Transactions Report ===")
    print(f"Total transactions: {total}\n")

    # By type
    print("By type:")
    rows = db.execute(
        "SELECT tx_type, COUNT(*), SUM(amount), AVG(confidence) "
        "FROM ds09_transactions GROUP BY tx_type ORDER BY SUM(amount) DESC"
    ).fetchall()
    for r in rows:
        avg_conf = f"{r[3]:.2f}" if r[3] else "N/A"
        total_amt = f"${r[2]:,.2f}" if r[2] else "$0"
        print(f"  {r[0] or 'unknown':<20s} {r[1]:>5d} txns  {total_amt:>20s}  avg_conf={avg_conf}")

    # By operator
    print("\nBy operator:")
    rows = db.execute(
        "SELECT operator, COUNT(*), SUM(amount) "
        "FROM ds09_transactions WHERE operator IS NOT NULL GROUP BY operator ORDER BY COUNT(*) DESC"
    ).fetchall()
    for r in rows:
        total_amt = f"${r[2]:,.2f}" if r[2] else "$0"
        print(f"  {r[0]:<20s} {r[1]:>5d} txns  {total_amt:>20s}")

    # By sender entity
    print("\nTop senders:")
    rows = db.execute(
        "SELECT sender, COUNT(*), SUM(amount) "
        "FROM ds09_transactions WHERE sender IS NOT NULL "
        "GROUP BY sender ORDER BY SUM(amount) DESC LIMIT 15"
    ).fetchall()
    for r in rows:
        total_amt = f"${r[2]:,.2f}" if r[2] else "$0"
        print(f"  {r[0]:<40s} {r[1]:>5d} txns  {total_amt:>20s}")

    # Top receivers
    print("\nTop receivers:")
    rows = db.execute(
        "SELECT receiver, COUNT(*), SUM(amount) "
        "FROM ds09_transactions WHERE receiver IS NOT NULL "
        "GROUP BY receiver ORDER BY SUM(amount) DESC LIMIT 15"
    ).fetchall()
    for r in rows:
        total_amt = f"${r[2]:,.2f}" if r[2] else "$0"
        print(f"  {r[0]:<40s} {r[1]:>5d} txns  {total_amt:>20s}")

    # Largest transactions
    print("\nTop 20 by amount:")
    rows = db.execute(
        "SELECT efta_id, tx_date, amount, currency, sender, receiver, tx_type, confidence "
        "FROM ds09_transactions ORDER BY amount DESC LIMIT 20"
    ).fetchall()
    for r in rows:
        sender = (r[4] or '?')[:25]
        receiver = (r[5] or '?')[:25]
        print(f"  {r[0] or '':>15s}  {r[1] or 'no-date':>10s}  {r[3]} {r[2]:>14,.2f}  "
              f"{sender:<25s} -> {receiver:<25s}  [{r[6]}] conf={r[7]:.2f}")

    # Date range
    row = db.execute(
        "SELECT MIN(tx_date), MAX(tx_date) FROM ds09_transactions WHERE tx_date IS NOT NULL"
    ).fetchone()
    if row[0]:
        print(f"\nDate range: {row[0]} to {row[1]}")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query(db, args):
    conditions = []
    params = []
    if args.entity:
        conditions.append("(sender LIKE ? OR receiver LIKE ?)")
        params.extend([f'%{args.entity}%', f'%{args.entity}%'])
    if args.amount_min:
        conditions.append("amount >= ?")
        params.append(args.amount_min)
    if args.date_start:
        conditions.append("tx_date >= ?")
        params.append(args.date_start)
    if args.date_end:
        conditions.append("tx_date <= ?")
        params.append(args.date_end)
    if args.tx_type:
        conditions.append("tx_type = ?")
        params.append(args.tx_type)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"""
        SELECT efta_id, tx_date, amount, currency, sender, receiver,
               tx_type, confidence, operator, reference
        FROM ds09_transactions
        WHERE {where}
        ORDER BY amount DESC
        LIMIT ?
    """
    params.append(args.limit or 50)

    rows = db.execute(sql, params).fetchall()
    print(f"Found {len(rows)} transactions:\n")
    for r in rows:
        sender = (r[4] or '?')[:30]
        receiver = (r[5] or '?')[:30]
        ref = (r[9] or '')[:40]
        print(f"  {r[0] or '':>15s}  {r[1] or 'no-date':>10s}  {r[3]} {r[2]:>14,.2f}  "
              f"{sender:<30s} -> {receiver:<30s}  [{r[6]}] op={r[8] or '?'}")
        if ref:
            print(f"{'':>15s}  ref: {ref}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Extract DS09 wire transfers')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('create-tables')

    p = sub.add_parser('parse-confirmations')
    p.add_argument('--limit', type=int)

    p = sub.add_parser('parse-wire-threads')
    p.add_argument('--limit', type=int)

    p = sub.add_parser('parse-checks')
    p.add_argument('--limit', type=int)

    p = sub.add_parser('parse-all')
    p.add_argument('--limit', type=int)

    sub.add_parser('report')

    p = sub.add_parser('query')
    p.add_argument('--entity', type=str)
    p.add_argument('--amount-min', type=float)
    p.add_argument('--date-start', type=str)
    p.add_argument('--date-end', type=str)
    p.add_argument('--tx-type', type=str)
    p.add_argument('--limit', type=int, default=50)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    db = get_db()

    if args.command == 'create-tables':
        create_tables(db)
    elif args.command == 'parse-confirmations':
        run_parse_confirmations(db, limit=args.limit)
    elif args.command == 'parse-wire-threads':
        run_parse_wire_threads(db, limit=args.limit)
    elif args.command == 'parse-checks':
        run_parse_checks(db, limit=args.limit)
    elif args.command == 'parse-all':
        run_parse_all(db, limit=args.limit)
    elif args.command == 'report':
        report(db)
    elif args.command == 'query':
        query(db, args)

    db.close()


if __name__ == '__main__':
    main()
