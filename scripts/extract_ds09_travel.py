#!/usr/bin/env python3
"""
Extract AmEx travel invoices from DS09 into structured travel tables.

Parses ~1,090 American Express Travel invoices from the Epstein email production,
extracting passenger names, flight legs (origin, destination, date, airline, flight#,
class, cost), hotel bookings, and invoice metadata.

Two invoice formats:
  - New format (post-2017): "Invoice Passenger Name(s)" + compact "Flight Details"
  - Old format (pre-2017): "Travel Arrangements for LAST/FIRST" + detailed flight tables

Usage:
  uv run python scripts/extract_ds09_travel.py create-tables
  uv run python scripts/extract_ds09_travel.py parse [--limit N]
  uv run python scripts/extract_ds09_travel.py report
  uv run python scripts/extract_ds09_travel.py query [--passenger X] [--origin X] [--dest X] [--date-start D] [--date-end D]
  uv run python scripts/extract_ds09_travel.py travelers              # Passenger summary
  uv run python scripts/extract_ds09_travel.py routes                 # Route frequency
"""

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.parse_ds10_financials import extract_efta_id, normalize_date, parse_dollar_amount

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'lmsband_epstein_files.db')
PARSER_VERSION = "ds09_travel_v1"
DS09_DATASET = 9


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def _run_id():
    env_id = os.getenv("DS09_EXTRACT_RUN_ID")
    return env_id or datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def create_tables(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS ds09_travel_invoices (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            efta_id TEXT,
            record_locator TEXT,
            invoice_number TEXT,
            invoice_date TEXT,
            customer_number TEXT,
            total_charged REAL,
            currency TEXT DEFAULT 'USD',
            card_last4 TEXT,
            parser_version TEXT,
            extract_run_id TEXT,
            UNIQUE(file_id, record_locator)
        );

        CREATE TABLE IF NOT EXISTS ds09_travel_passengers (
            id INTEGER PRIMARY KEY,
            invoice_id INTEGER REFERENCES ds09_travel_invoices(id),
            passenger_name TEXT,
            passenger_normalized TEXT,
            UNIQUE(invoice_id, passenger_name)
        );

        CREATE TABLE IF NOT EXISTS ds09_travel_flights (
            id INTEGER PRIMARY KEY,
            invoice_id INTEGER REFERENCES ds09_travel_invoices(id),
            file_id INTEGER,
            efta_id TEXT,
            passenger_name TEXT,
            flight_date TEXT,
            airline TEXT,
            flight_number TEXT,
            origin TEXT,
            destination TEXT,
            depart_time TEXT,
            arrive_time TEXT,
            cabin_class TEXT,
            seat TEXT,
            ticket_number TEXT,
            ticket_cost REAL,
            record_locator TEXT,
            confidence REAL,
            UNIQUE(file_id, flight_date, flight_number, passenger_name)
        );

        CREATE INDEX IF NOT EXISTS idx_travel_inv_efta ON ds09_travel_invoices(efta_id);
        CREATE INDEX IF NOT EXISTS idx_travel_inv_date ON ds09_travel_invoices(invoice_date);
        CREATE INDEX IF NOT EXISTS idx_travel_pax_name ON ds09_travel_passengers(passenger_normalized);
        CREATE INDEX IF NOT EXISTS idx_travel_flt_date ON ds09_travel_flights(flight_date);
        CREATE INDEX IF NOT EXISTS idx_travel_flt_origin ON ds09_travel_flights(origin);
        CREATE INDEX IF NOT EXISTS idx_travel_flt_dest ON ds09_travel_flights(destination);
        CREATE INDEX IF NOT EXISTS idx_travel_flt_pax ON ds09_travel_flights(passenger_name);
        CREATE INDEX IF NOT EXISTS idx_travel_flt_airline ON ds09_travel_flights(airline);
        CREATE INDEX IF NOT EXISTS idx_travel_flt_efta ON ds09_travel_flights(efta_id);
    """)
    db.commit()
    print("Travel tables created.")


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def normalize_passenger_name(raw):
    """Normalize 'LASTNAME/FIRSTNAME MIDDLE' -> 'Firstname Lastname'."""
    if not raw:
        return None
    raw = raw.strip()
    if '/' in raw:
        parts = raw.split('/')
        last = parts[0].strip()
        first = parts[1].strip() if len(parts) > 1 else ''
        # Handle multiple passengers: "BACH/JOSCHA BACH/MIRA MARIA"
        # Just take the first passenger for normalization
        first = first.split()[0] if first else ''
        return f"{first.title()} {last.title()}".strip()
    return raw.title()


def extract_all_passengers(text):
    """Extract all passenger names from invoice text."""
    passengers = []

    # New format: "Invoice Passenger Name(s) LASTNAME/FIRSTNAME"
    pax_match = re.search(
        r'Invoice Passenger Name\(s\)\s+(.+?)(?:\s+Your invoice|\s+Centurion)',
        text, re.DOTALL
    )
    if pax_match:
        pax_block = pax_match.group(1).strip()
        # Split multiple passengers on whitespace between LAST/FIRST patterns
        for m in re.finditer(r'([A-Z][A-Z]+/[A-Z][A-Z\s]*?)(?=\s+[A-Z]+/|\s*$)', pax_block):
            passengers.append(m.group(1).strip())

    # Old format: "Travel Arrangements for LASTNAME/FIRSTNAME"
    if not passengers:
        arr_match = re.search(
            r'Travel Arrangements for\s+([A-Z][A-Z/\s]+?)(?:\s+American Express)',
            text
        )
        if arr_match:
            pax_block = arr_match.group(1).strip()
            for m in re.finditer(r'([A-Z][A-Z]+/[A-Z][A-Z\s]*?)(?=\s+[A-Z]+/|\s*$)', pax_block):
                passengers.append(m.group(1).strip())

    # Also check "Ticket Information for LASTNAME"
    for m in re.finditer(r'Ticket Information for\s+([A-Z][A-Z/\s]+?)(?:\s+Charges|\s+Agent)', text):
        name = m.group(1).strip()
        if '/' in name and name not in passengers:
            passengers.append(name)

    # Also from "Passenger Name LASTNAME/FIRSTNAME"
    for m in re.finditer(r'Passenger Name\s+([A-Z][A-Z]+/[A-Z][A-Z\s]+?)(?:\s+Gov|$)', text):
        name = m.group(1).strip()
        if name not in passengers:
            passengers.append(name)

    # Clean up: remove trailing noise, deduplicate
    cleaned = []
    for p in passengers:
        p = re.sub(r'\s+$', '', p)
        p = re.sub(r'\s+(Charges|Agent|Gov|Ticket|Your).*$', '', p)
        if '/' in p and len(p) > 3:
            cleaned.append(p)

    return list(dict.fromkeys(cleaned))  # Deduplicate preserving order


# ---------------------------------------------------------------------------
# Flight parsing
# ---------------------------------------------------------------------------

# Month abbreviation mapping
MONTHS = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'june': '06', 'july': '07', 'august': '08', 'september': '09',
    'october': '10', 'november': '11', 'december': '12',
}


def _parse_travel_date(raw):
    """Parse dates like '24 Apr 2019', '11 Nov 2016', 'Thursday 07 Jan 16'."""
    if not raw:
        return None
    raw = raw.strip()

    # "24 Apr 2019" or "11 Nov 2016"
    m = re.search(r'(\d{1,2})\s+(\w{3,})\s+(\d{2,4})', raw)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year_str = m.group(3)
        month = MONTHS.get(month_str)
        if month and 1 <= day <= 31:
            year = int(year_str)
            if year < 100:
                year += 2000
            return f"{year:04d}-{month}-{day:02d}"

    # MM/DD/YYYY
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', raw)
    if m:
        return normalize_date(m.group(0))

    return None


def parse_flights_new_format(text):
    """Parse compact flight details from new format invoices.

    Pattern: "24 Apr 2019 SU103 Z Class New York-Kennedy/Moscow-Sheremetye"
    Multiple flights appear consecutively. Split on date patterns first.
    """
    flights = []

    # Split the flight details section into individual flight lines
    # Each flight starts with a date like "24 Apr 2019" or "05 Dec 2018"
    # Find all flight detail lines
    flight_line_pattern = re.compile(
        r'(\d{1,2}\s+\w{3}\s+\d{2,4})\s+'  # date
        r'([A-Z0-9]{2}\d{1,4})\s+'          # flight number
        r'(\w[\w\s]*?Class)\s+'              # class
        r'(.+?)/'                             # origin (up to /)
        r'([A-Za-z][A-Za-z\s,.\-\(\)]+?)'   # destination
        r'(?=\s+\d{1,2}\s+\w{3}\s+\d{2,4}\s+[A-Z]|'  # next flight line
        r'\s+Credit\s+Card|'
        r'\s+Page\s|'
        r'\s+Charged\s|'
        r'\s*$)',
    )

    for m in flight_line_pattern.finditer(text):
        flight_date = _parse_travel_date(m.group(1))
        flight_num = m.group(2).strip()
        cabin_class = m.group(3).strip()
        origin = m.group(4).strip()
        destination = m.group(5).strip()

        # Clean destination: remove trailing noise
        destination = re.sub(r'\s+(?:Credit|Page|Charged|Optional|Travel Info|Flight Detail).*$', '', destination, flags=re.IGNORECASE).strip()

        airline_code = re.match(r'([A-Z0-9]{2})', flight_num)
        airline = airline_code.group(1) if airline_code else None

        flights.append({
            'flight_date': flight_date,
            'flight_number': flight_num,
            'airline_code': airline,
            'cabin_class': cabin_class,
            'origin': origin,
            'destination': destination,
            'confidence': 0.90,
        })

    return flights


def parse_flights_old_format(text):
    """Parse detailed flight tables from old format invoices.

    Pattern: "Airline Flight Origin Destination Departing Arriving..."
    followed by data rows like "United Airlines UA1482 Charlotte Amalie... Newark..."
    """
    flights = []

    # Find "Travel Details" date headers
    travel_dates = {}
    for m in re.finditer(r'Travel Details\s+(\w+day)?\s*(\d{1,2}\s+\w{3}\s+\d{2,4})', text):
        pos = m.start()
        date = _parse_travel_date(m.group(2))
        if date:
            travel_dates[pos] = date

    # Find flight info blocks: "Airline Record Locator ... Airline Flight Origin Destination..."
    # Then data: "United Airlines UA1482 Charlotte Amalie, Cyril E King Airport Newark..."
    flight_blocks = list(re.finditer(
        r'(?:Airline Record Locator\s+)?'
        r'(?:Airline\s+Flight\s+Origin\s+Destination\s+Departing\s+Arriving|'
        r'([A-Z][A-Za-z\s]{2,30}?)\s+([A-Z]{2}\d{1,5})\s+(.+?)(?:\s+\d{1,2}:\d{2}\s|\s+Terminal))',
        text
    ))

    # Alternative: parse flight rows directly
    # Pattern: airline_name flight# origin destination time time terminal class seat
    flight_row_pattern = re.compile(
        r'([A-Z][A-Za-z\s]{2,25}?)\s+'        # Airline name
        r'([A-Z0-9]{2}\d{1,4})\s+'            # Flight number
        r'(.+?)\s{2,}'                          # Origin (has spaces in names)
        r'(.+?)\s+'                              # Destination
        r'(\d{1,2}[.:]\d{2}\s*[AP]M)\s+'       # Depart time
        r'(\d{1,2}[.:]\d{2}\s*[AP]M)',         # Arrive time
    )

    for m in flight_row_pattern.finditer(text):
        airline = m.group(1).strip()
        flight_num = m.group(2).strip()
        origin = m.group(3).strip().rstrip('.')
        destination = m.group(4).strip().rstrip('.')
        depart_time = m.group(5).strip()
        arrive_time = m.group(6).strip()

        # Find nearest travel date before this match
        flight_date = None
        for dpos, dval in sorted(travel_dates.items()):
            if dpos < m.start():
                flight_date = dval
            else:
                break

        # Extract class from nearby text
        after = text[m.end():m.end()+200]
        class_match = re.search(r'(\w+\s+Class)', after)
        cabin_class = class_match.group(1) if class_match else None

        seat_match = re.search(r'Class\s+(\w{1,4})\b', after)
        seat = seat_match.group(1) if seat_match else None

        airline_code = re.match(r'([A-Z0-9]{2})', flight_num)

        flights.append({
            'flight_date': flight_date,
            'flight_number': flight_num,
            'airline': airline,
            'airline_code': airline_code.group(1) if airline_code else None,
            'cabin_class': cabin_class,
            'origin': origin,
            'destination': destination,
            'depart_time': depart_time,
            'arrive_time': arrive_time,
            'seat': seat,
            'confidence': 0.85,
        })

    return flights


# Airline code -> name mapping (from observed data)
AIRLINE_CODES = {
    'SU': 'Aeroflot', 'DL': 'Delta', 'AA': 'American Airlines',
    'UA': 'United Airlines', 'B6': 'JetBlue', 'JL': 'Japan Airlines',
    'DY': 'Norwegian Air', 'BA': 'British Airways', 'AF': 'Air France',
    'LH': 'Lufthansa', 'AY': 'Finnair', 'SK': 'SAS',
    'EK': 'Emirates', 'QR': 'Qatar Airways', 'EY': 'Etihad',
    'TK': 'Turkish Airlines', 'LX': 'Swiss', 'OS': 'Austrian',
    'KL': 'KLM', 'IB': 'Iberia', 'TP': 'TAP Portugal',
    'VS': 'Virgin Atlantic', 'AC': 'Air Canada', 'NH': 'ANA',
    '9K': 'Cape Air', 'US': 'US Airways', 'WN': 'Southwest',
    'AS': 'Alaska Airlines', 'NK': 'Spirit', 'F9': 'Frontier',
    'HA': 'Hawaiian Airlines',
}


def _resolve_airline(code, name_from_text=None):
    """Resolve airline from code and/or text name."""
    if name_from_text:
        return name_from_text
    if code and code in AIRLINE_CODES:
        return AIRLINE_CODES[code]
    return code


# ---------------------------------------------------------------------------
# Invoice parsing
# ---------------------------------------------------------------------------

def parse_amex_invoice(file_id, filename, text):
    """Parse a single AmEx travel invoice, returning (invoice_dict, passengers, flights)."""
    efta_id = extract_efta_id(filename)

    # Invoice metadata
    record_locator = None
    rl_match = re.search(r'Record Locator\s+([A-Z0-9]{6})', text)
    if rl_match:
        record_locator = rl_match.group(1)

    invoice_number = None
    inv_match = re.search(r'Invoice\s+(\d{4,})', text)
    if inv_match:
        invoice_number = inv_match.group(1)

    invoice_date = None
    # "Generated: Mon. 03 December 2018 18:19:05" or "Ticket Date 04/04/2019"
    gen_match = re.search(r'Generated:\s*\w+[.\s]+(\d{1,2}\s+\w+\s+\d{4})', text)
    if gen_match:
        invoice_date = _parse_travel_date(gen_match.group(1))
    if not invoice_date:
        td_match = re.search(r'Ticket Date\s+(\d{2}/\d{2}/\d{4})', text)
        if td_match:
            invoice_date = normalize_date(td_match.group(1))

    customer_number = None
    cn_match = re.search(r'Customer Number\s+(\d+)', text)
    if cn_match:
        customer_number = cn_match.group(1)

    # Total cost
    total_charged = None
    total_match = re.search(r'Invoice Total\s+USD\s*([\d,.]+)', text)
    if not total_match:
        total_match = re.search(r'Total Charged to American Express\s+([\d,.]+)', text)
    if total_match:
        total_charged, _ = parse_dollar_amount(total_match.group(1))

    # Card last 4
    card_match = re.search(r'Card\s+[A-Z]{2}\s*\)?\d*\(?(\d{4})\)?', text)
    if not card_match:
        card_match = re.search(r'\((\d{4})\)\s*$', text[:2000], re.MULTILINE)
    card_last4 = card_match.group(1) if card_match else None

    # Ticket numbers
    ticket_numbers = re.findall(r'Ticket Number\s+(\d{10,})', text)

    # Ticket cost per ticket
    ticket_costs = []
    for m in re.finditer(r'Total Ticket Amount\s+([\d,.]+)', text):
        val, _ = parse_dollar_amount(m.group(1))
        if val:
            ticket_costs.append(val)

    # Passengers
    passengers = extract_all_passengers(text)

    # Airline from text
    airline_name = None
    al_match = re.search(r'Airline\s+([\w\s]+?)(?:\s+Total|\s+Original|\s+Flight)', text)
    if not al_match:
        al_match = re.search(r'Baggage Rules of\s+([\w\s]+?)\s+apply', text)
    if al_match:
        airline_name = al_match.group(1).strip()

    # Parse flights — try new format first, fall back to old
    is_new_format = bool(re.search(r'Invoice Passenger Name', text))
    if is_new_format:
        flights = parse_flights_new_format(text)
    else:
        flights = parse_flights_old_format(text)

    # Deduplicate flights by (date, flight_number) within this document
    seen = set()
    deduped = []
    for f in flights:
        key = (f.get('flight_date'), f.get('flight_number'))
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    flights = deduped

    # Enrich flights with invoice-level data
    for i, f in enumerate(flights):
        f['file_id'] = file_id
        f['efta_id'] = efta_id
        f['record_locator'] = record_locator
        if not f.get('airline'):
            f['airline'] = _resolve_airline(f.get('airline_code'), airline_name)
        else:
            f['airline'] = _resolve_airline(f.get('airline_code'), f['airline'])
        # Assign passenger name (first passenger if only one)
        if passengers and not f.get('passenger_name'):
            f['passenger_name'] = passengers[0]
        # Assign ticket cost (first ticket if only one)
        if ticket_costs and len(ticket_costs) == 1:
            f['ticket_cost'] = ticket_costs[0]
        elif ticket_costs and i < len(ticket_costs):
            f['ticket_cost'] = ticket_costs[i]
        # Ticket number
        if ticket_numbers and i < len(ticket_numbers):
            f['ticket_number'] = ticket_numbers[i]
        elif ticket_numbers:
            f['ticket_number'] = ticket_numbers[0]

    invoice = {
        'file_id': file_id,
        'efta_id': efta_id,
        'record_locator': record_locator,
        'invoice_number': invoice_number,
        'invoice_date': invoice_date,
        'customer_number': customer_number,
        'total_charged': total_charged,
        'card_last4': card_last4,
    }

    return invoice, passengers, flights


# ---------------------------------------------------------------------------
# Insertion
# ---------------------------------------------------------------------------

def insert_invoice(db, invoice, passengers, flights, run_id):
    """Insert invoice, passengers, and flights. Returns counts."""
    inv_inserted = 0
    pax_inserted = 0
    flt_inserted = 0

    try:
        db.execute('''
            INSERT OR IGNORE INTO ds09_travel_invoices
            (file_id, efta_id, record_locator, invoice_number, invoice_date,
             customer_number, total_charged, currency, card_last4,
             parser_version, extract_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?)
        ''', (
            invoice['file_id'], invoice['efta_id'], invoice['record_locator'],
            invoice['invoice_number'], invoice['invoice_date'],
            invoice['customer_number'], invoice['total_charged'],
            invoice['card_last4'], PARSER_VERSION, run_id,
        ))
        if db.execute("SELECT changes()").fetchone()[0] > 0:
            inv_inserted = 1
    except sqlite3.IntegrityError:
        pass

    # Get invoice id
    row = db.execute(
        "SELECT id FROM ds09_travel_invoices WHERE file_id=? AND record_locator IS ?",
        (invoice['file_id'], invoice['record_locator'])
    ).fetchone()
    inv_id = row['id'] if row else None

    if inv_id:
        for pax in passengers:
            try:
                db.execute('''
                    INSERT OR IGNORE INTO ds09_travel_passengers
                    (invoice_id, passenger_name, passenger_normalized)
                    VALUES (?, ?, ?)
                ''', (inv_id, pax, normalize_passenger_name(pax)))
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    pax_inserted += 1
            except sqlite3.IntegrityError:
                pass

        for f in flights:
            try:
                db.execute('''
                    INSERT OR IGNORE INTO ds09_travel_flights
                    (invoice_id, file_id, efta_id, passenger_name, flight_date,
                     airline, flight_number, origin, destination,
                     depart_time, arrive_time, cabin_class, seat,
                     ticket_number, ticket_cost, record_locator, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    inv_id, f['file_id'], f['efta_id'],
                    f.get('passenger_name'), f.get('flight_date'),
                    f.get('airline'), f.get('flight_number'),
                    f.get('origin'), f.get('destination'),
                    f.get('depart_time'), f.get('arrive_time'),
                    f.get('cabin_class'), f.get('seat'),
                    f.get('ticket_number'), f.get('ticket_cost'),
                    f.get('record_locator'), f.get('confidence', 0.85),
                ))
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    flt_inserted += 1
            except sqlite3.IntegrityError:
                pass

    return inv_inserted, pax_inserted, flt_inserted


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run_parse(db, limit=None):
    sql = f"""
        SELECT f.id AS file_id, f.filename, t.extracted_text
        FROM files f JOIN text_cache t ON f.id = t.file_id
        WHERE f.dataset = {DS09_DATASET}
          AND t.extracted_text LIKE '%AMERICAN EX%TRAVEL INVOICE%'
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    docs = db.execute(sql).fetchall()
    print(f"Found {len(docs)} AmEx travel invoices")

    run_id = _run_id()
    total_inv = total_pax = total_flt = 0
    no_flights = 0

    for doc in docs:
        invoice, passengers, flights = parse_amex_invoice(
            doc['file_id'], doc['filename'], doc['extracted_text']
        )
        ni, np, nf = insert_invoice(db, invoice, passengers, flights, run_id)
        total_inv += ni
        total_pax += np
        total_flt += nf
        if not flights:
            no_flights += 1

    db.commit()
    print(f"Inserted: {total_inv} invoices, {total_pax} passengers, {total_flt} flights")
    if no_flights:
        print(f"  ({no_flights} invoices yielded no flight legs)")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(db):
    inv_count = db.execute("SELECT COUNT(*) FROM ds09_travel_invoices").fetchone()[0]
    pax_count = db.execute("SELECT COUNT(DISTINCT passenger_normalized) FROM ds09_travel_passengers").fetchone()[0]
    flt_count = db.execute("SELECT COUNT(*) FROM ds09_travel_flights").fetchone()[0]
    total_cost = db.execute("SELECT SUM(total_charged) FROM ds09_travel_invoices").fetchone()[0]

    print(f"=== DS09 Travel Report ===")
    print(f"Invoices: {inv_count}")
    print(f"Unique passengers: {pax_count}")
    print(f"Flight legs: {flt_count}")
    print(f"Total charged: ${total_cost:,.2f}" if total_cost else "Total charged: $0")

    # Date range
    row = db.execute(
        "SELECT MIN(flight_date), MAX(flight_date) FROM ds09_travel_flights WHERE flight_date IS NOT NULL"
    ).fetchone()
    if row[0]:
        print(f"Date range: {row[0]} to {row[1]}")

    # Top passengers
    print(f"\nTop travelers:")
    rows = db.execute("""
        SELECT p.passenger_normalized, COUNT(DISTINCT f.id) as flights,
               COUNT(DISTINCT f.flight_date) as travel_days,
               SUM(f.ticket_cost) as total_cost
        FROM ds09_travel_passengers p
        JOIN ds09_travel_flights f ON f.invoice_id = p.invoice_id
        GROUP BY p.passenger_normalized
        ORDER BY flights DESC LIMIT 20
    """).fetchall()
    for r in rows:
        cost = f"${r['total_cost']:,.0f}" if r['total_cost'] else "N/A"
        print(f"  {r['passenger_normalized'] or '?':<35s} {r['flights']:>4d} flights  {r['travel_days']:>3d} days  {cost:>10s}")

    # Top routes
    print(f"\nTop routes:")
    rows = db.execute("""
        SELECT origin, destination, COUNT(*) as cnt
        FROM ds09_travel_flights
        WHERE origin IS NOT NULL AND destination IS NOT NULL
        GROUP BY origin, destination
        ORDER BY cnt DESC LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"  {r['origin']:<45s} -> {r['destination']:<45s} {r['cnt']:>4d}")

    # Top airlines
    print(f"\nTop airlines:")
    rows = db.execute("""
        SELECT airline, COUNT(*) as cnt
        FROM ds09_travel_flights WHERE airline IS NOT NULL
        GROUP BY airline ORDER BY cnt DESC LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r['airline']:<30s} {r['cnt']:>4d}")


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query(db, args):
    conditions = []
    params = []
    if args.passenger:
        conditions.append("(f.passenger_name LIKE ? OR p.passenger_normalized LIKE ?)")
        params.extend([f'%{args.passenger}%', f'%{args.passenger}%'])
    if args.origin:
        conditions.append("f.origin LIKE ?")
        params.append(f'%{args.origin}%')
    if args.dest:
        conditions.append("f.destination LIKE ?")
        params.append(f'%{args.dest}%')
    if args.date_start:
        conditions.append("f.flight_date >= ?")
        params.append(args.date_start)
    if args.date_end:
        conditions.append("f.flight_date <= ?")
        params.append(args.date_end)

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"""
        SELECT DISTINCT f.efta_id, f.flight_date, f.airline, f.flight_number,
               f.origin, f.destination, f.cabin_class, f.ticket_cost,
               p.passenger_normalized
        FROM ds09_travel_flights f
        LEFT JOIN ds09_travel_passengers p ON f.invoice_id = p.invoice_id
        WHERE {where}
        ORDER BY f.flight_date, f.flight_number
        LIMIT ?
    """
    params.append(args.limit or 50)
    rows = db.execute(sql, params).fetchall()
    print(f"Found {len(rows)} flights:\n")
    for r in rows:
        pax = (r['passenger_normalized'] or '?')[:25]
        cost = f"${r['ticket_cost']:,.0f}" if r['ticket_cost'] else ""
        print(f"  {r['flight_date'] or 'no-date':>10s}  {r['airline'] or '':>15s} {r['flight_number'] or '':>6s}  "
              f"{(r['origin'] or '?')[:30]:<30s} -> {(r['destination'] or '?')[:30]:<30s}  "
              f"{pax:<25s} {cost}")


def travelers(db):
    rows = db.execute("""
        SELECT p.passenger_normalized,
               COUNT(DISTINCT f.id) as flights,
               MIN(f.flight_date) as first_flight,
               MAX(f.flight_date) as last_flight,
               GROUP_CONCAT(DISTINCT f.origin) as origins,
               GROUP_CONCAT(DISTINCT f.destination) as destinations,
               SUM(f.ticket_cost) as total_cost
        FROM ds09_travel_passengers p
        JOIN ds09_travel_flights f ON f.invoice_id = p.invoice_id
        GROUP BY p.passenger_normalized
        ORDER BY flights DESC
    """).fetchall()
    print(f"{'Passenger':<35s} {'Flights':>7s} {'First':>10s} {'Last':>10s} {'Cost':>10s}")
    print("-" * 80)
    for r in rows:
        cost = f"${r['total_cost']:,.0f}" if r['total_cost'] else "N/A"
        print(f"  {r['passenger_normalized'] or '?':<35s} {r['flights']:>5d}  {r['first_flight'] or '':>10s}  "
              f"{r['last_flight'] or '':>10s}  {cost:>10s}")


def routes(db):
    rows = db.execute("""
        SELECT origin, destination, COUNT(*) as cnt,
               GROUP_CONCAT(DISTINCT p.passenger_normalized) as passengers
        FROM ds09_travel_flights f
        LEFT JOIN ds09_travel_passengers p ON f.invoice_id = p.invoice_id
        WHERE origin IS NOT NULL
        GROUP BY origin, destination
        ORDER BY cnt DESC LIMIT 30
    """).fetchall()
    for r in rows:
        pax = (r['passengers'] or '')[:60]
        print(f"  {r['cnt']:>3d}x  {r['origin']:<40s} -> {r['destination']:<40s}  [{pax}]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Extract DS09 AmEx travel invoices')
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('create-tables')

    p = sub.add_parser('parse')
    p.add_argument('--limit', type=int)

    sub.add_parser('report')

    p = sub.add_parser('query')
    p.add_argument('--passenger', type=str)
    p.add_argument('--origin', type=str)
    p.add_argument('--dest', type=str)
    p.add_argument('--date-start', type=str)
    p.add_argument('--date-end', type=str)
    p.add_argument('--limit', type=int, default=50)

    sub.add_parser('travelers')
    sub.add_parser('routes')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    db = get_db()

    if args.command == 'create-tables':
        create_tables(db)
    elif args.command == 'parse':
        run_parse(db, limit=args.limit)
    elif args.command == 'report':
        report(db)
    elif args.command == 'query':
        query(db, args)
    elif args.command == 'travelers':
        travelers(db)
    elif args.command == 'routes':
        routes(db)

    db.close()


if __name__ == '__main__':
    main()
