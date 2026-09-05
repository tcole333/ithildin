#!/usr/bin/env python3
"""Builder: normalized financial model in epstein_derived.db.

Reads the immutable corpora (kabasshouse re-OCR + LMSBAND typed extraction) and
populates the financial tables owned by tools/epstein_derived.py:
  merchant, financial_account, financial_transaction, balance_snapshot,
  position_snapshot, security, financial_statement, fin_flight.

Design contract:
  * Read-only against source DBs. Writes ONLY epstein_derived.db.
  * Never CREATE TABLE (schema owned by epstein_derived.py). init_schema only.
  * Amounts are signed INTEGER minor units (cents). raw_amount always preserved.
  * Idempotent: UNIQUE(source_system_id, source_native_id) + INSERT OR IGNORE.
    Re-running rebuilds derived flags/dedupe in place (delete-and-reinsert per
    source-owned table) without touching source data.
  * Outliers are FLAGGED (is_outlier=1), never dropped: the -99999 OCR sentinel
    family, |amount| > $50M, absurd cost_basis > 1e12.
  * evidence_item_id is set by joining evidence_item on canonical_ref = EFTA.
    Rows whose EFTA is absent from evidence_item leave it NULL.
  * Raw source strings are never overwritten. counterparty_raw is only PARSED for
    rows where the source had no counterparty field of its own; where it did,
    counterparty_parse_rule = 'source_field'.
  * Account identity is tiered, not asserted: financial_account.key_basis records
    which fields formed the key so an owner-only grouping can never be mistaken
    for a single account. See build_accounts.
  * Statement reconciliation only runs on a genuinely closed ledger (both boundary
    balances present, all member amounts parseable). Anything else is
    'not_computable' — never a zero residual. See reconcile_statements.
  * This corpus is account/card statements, NOT a two-sided transfer ledger. Do
    not pair instructions to receipts by same-day/same-amount/opposite-sign:
    that manufactures conservation out of reversals and duplicate representations.

Usage:
    uv run python tools/build_financials.py [--limit N] [--stage STAGE ...]
      stages: merchants transactions accounts balances positions statements
              flights all
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from tools.epstein_derived import (  # noqa: E402
    get_db, attach, init_schema, new_run, source_system_id,
    KABASS_DB, LMSBAND_DB,
)
from tools.parse_ds10_financials import parse_dollar_amount  # noqa: E402
from tools.date_normalize import normalize_date, to_epoch_day  # noqa: E402

# ── outlier thresholds (minor units unless noted) ─────────────────────────────
OUTLIER_ABS_MINOR = 50_000_000 * 100      # |amount| > $50M
COST_BASIS_ABSURD_MINOR = int(1e12 * 100)  # cost_basis > $1e12
# SQLite stores signed 64-bit ints; OCR garbage like 5.17e+33 overflows when
# scaled to cents. Such values are already outliers — keep the flag, null the int.
_INT64_MAX = 2**63 - 1
# The OCR sentinel family: 99999.xx / 999999.xx (all-nines placeholder).
_SENTINEL_RE = re.compile(r"^-?9{4,6}(\.\d+)?$")

# Statement-marker merchant names that are NOT real spend. Matched
# case-insensitively as a prefix so OCR tails ("Check Paid ...") still hit.
STRUCTURAL_MERCHANT_PREFIXES = [
    "beginning balance", "ending balance", "interest payment", "interest paid",
    "interest", "deposit", "check paid", "check payment", "check",
    "internal funds transfer", "internal transfer", "fedwire debit",
    "fedwire credit", "book transfer", "cash management transfer",
    "funds transfer", "funds transferred", "wire transfer", "outgoing money",
    "incoming money", "preauthorized debit", "balance", "payment received",
    "electronic payment", "automatic transfer", "transfer of funds", "sweep",
    "net sweep", "reinvestment", "misc disbursement",
]

# merchant_category (kabass) -> (direction, txn_type)
CATEGORY_MAP = {
    "debit": ("debit", "card"),
    "credit": ("credit", "card"),
    "check": ("debit", "check"),
    "wire_out": ("debit", "wire"),
    "wire_in": ("credit", "wire"),
    "deposit": ("credit", "deposit"),
    "transfer": ("unknown", "transfer"),
    "transfer_in": ("credit", "transfer"),
    "transfer_out": ("debit", "transfer"),
    "fee": ("debit", "fee"),
    "interest": ("credit", "interest"),
    "dividend": ("credit", "dividend"),
    "withdrawal": ("debit", "withdrawal"),
    "payment": ("debit", "payment"),
    "electronic_payment": ("debit", "payment"),
    "card_purchase": ("debit", "card"),
    "purchase": ("debit", "card"),
    "sale": ("credit", "sale"),
    "foreign_exchange": ("unknown", "fx"),
    "exchange": ("unknown", "fx"),
    "income": ("credit", "income"),
    "investment": ("debit", "investment"),
    "reinvestment": ("credit", "investment"),
    "sweep": ("unknown", "transfer"),
    "net_sweep": ("unknown", "transfer"),
    "balance": ("unknown", "balance"),
}


def _amount_to_minor(dollars):
    """Round a float dollar value to signed integer cents.

    Returns None if the scaled value would overflow SQLite's signed 64-bit
    INTEGER (OCR-garbage magnitudes) — callers flag those as outliers separately.
    """
    if dollars is None:
        return None
    try:
        minor = int(round(dollars * 100))
    except (ValueError, OverflowError):
        return None
    return minor if abs(minor) <= _INT64_MAX else None


def _is_sentinel(raw_amount):
    if not raw_amount:
        return False
    s = str(raw_amount).strip().replace("$", "").replace(",", "")
    return bool(_SENTINEL_RE.match(s))


def _norm_desc(s):
    """Collapse whitespace + lowercase for dedupe hashing (OCR-stable-ish)."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _dedupe_key(canonical_ref, day, amount_minor, description, salt=None):
    """Page + date + amount + normalized description.

    `salt` must be passed (with the row's source id) whenever canonical_ref is a
    syntactically truncated EFTA: those short refs are shared by unrelated pages,
    so hashing them unsalted invites a false merge of two distinct transactions.
    """
    h = hashlib.sha1(
        "|".join([
            str(canonical_ref or ""),
            str(day if day is not None else ""),
            str(amount_minor if amount_minor is not None else ""),
            _norm_desc(description),
            str(salt or ""),
        ]).encode("utf-8")
    ).hexdigest()
    return h[:16]


def _dedupe_key_for(canonical_ref, day, amount_minor, description, native_id):
    """_dedupe_key, auto-salting rows whose provenance ref is untrustworthy."""
    salt = native_id if is_truncated_ref(canonical_ref) else None
    return _dedupe_key(canonical_ref, day, amount_minor, description, salt=salt)


def _is_structural(name):
    if not name:
        return 0
    low = name.strip().lower()
    return 1 if any(low.startswith(p) for p in STRUCTURAL_MERCHANT_PREFIXES) else 0


# ── counterparty / intermediary-bank extraction from the statement line ───────
# Wire lines in this corpus follow the JPMorgan/CHIPS advice layout:
#   Fedwire Debit Via: <CORRESPONDENT>/<ABA> A/C: <BENEFICIARY> [Ben: <ULTIMATE>] ...
#   Fedwire Credit Via: <ORIGINATING BK>/<ABA> B/O: <ORIGINATOR> Ref: ...
# so the counterparty is Ben:/A/C: on an outflow and B/O: on an inflow, and the
# "Via:" party is the correspondent bank, never the counterparty.

# Tag tokens that terminate a party span. Tags whose colon form gets OCR-glued to
# the preceding word ("...NY 10021ORG:", "...Incref:") carry no leading \b.
_PARTY_STOP = re.compile("|".join([
    r"a/c\s*[:#]", r"\bben\b\s*:?", r"bnf\s*bk\s*:", r"\bbnf\b", r"b\s*/\s*[o0]\s*:",
    r"org\s*\.?\s*[:=]", r"ogb\s*\.?\s*[:=]", r"obi\s*[:=]", r"ref\s*[:=]", r"ref\s*#",
    r"rfb\s*[-=]", r"bbi\s*=", r"imad\s*:", r"trn\s*:", r"\btm\s+\d", r"ssn\s*:",
    r"iassn\s*:", r"\bid\s*:", r"\buid\b\s+", r"cid\s*/", r"nbnf\s*=", r"pmt\s+det\s*:",
    r"\bdate\s*:", r"\btime\s*[:/]", r"\bvia\b\s*:?", r"\bfao\b", r"\bfbo\b", r"\battn\b",
    r"/acc/", r"\bocmt\b", r"web\s+id\b", r"swift\s*:", r"\baba\s*/", r"transaction\s*#",
    r"\bamt\s*=", r"\bcur\s*=", r"\brate\s*=", r"as\s+requested\b", r"\bffc\b",
    r"\bbene\b", r"\bre\s*:", r"\bd/b/a\b", r"\[redacted\]",
    r"\bat\s+(?=[A-Za-z. ]{0,30}\b(?:bank|bk|n\.a|trust)\b)",
]), re.I)

_US_STATES = set(("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
                  "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY "
                  "DC").split())
_ZIP_TAIL = re.compile(r"[,\s]+\d{5,9}(?:-\d{1,4})?-?\s*$")
# "<City> ST <ZIP>" — the ZIP is what proves the 2-letter token is a state, so the
# two are stripped together. Without that anchor, a corporate "Co"/"In"/"La"/"Pa"
# suffix looks exactly like Colorado/Indiana/Louisiana/Pennsylvania.
_STATE_ZIP_TAIL = re.compile(r"[,\s]+([A-Za-z]{2})[,\s]+\d{5,9}(?:-\d{1,4})?-?\s*$")
_COMMA_STATE_TAIL = re.compile(r",\s*([A-Za-z]{2})\s*$")
# 2-letter state codes that double as ordinary business abbreviations. Only ever
# stripped when a ZIP proves they are an address.
_AMBIGUOUS_STATE_ABBREV = {"CO", "IN", "LA", "PA", "OR", "ME", "DE", "OK", "MD"}
_AC_TAIL = re.compile(r"[,\s/]*-?/?\s*a/?c\s*-?\s*\d*\s*$", re.I)
_ZERO_ACCT_TAIL = re.compile(r"[,\s/]*0{4,}\d*\s*$")
_ABA_HEAD = re.compile(r"^\s*(?:aba\s*/?|/)\s*\d{6,12}\s*", re.I)
_ACCT_HEAD = re.compile(r"^\s*/?\s*[A-Z]?\d{5,}\s+", re.I)
_MEMO_TAIL = re.compile(r"[.,\s]+(?:letter from client|as requested|no name given|"
                        r"(?:operating\s+)?ac invoice)\s*$", re.I)
_REDACTION = re.compile(r"/?\s*\[redacted\]", re.I)

# Strings that never name an external counterparty: masked/internal account
# references, and the bank's own clearing and suspense pseudo-parties.
_NOT_A_PARTY = re.compile(
    r"x{4,}|\bck\s*:|\bchk\b|\bbrkrg\b|\bdda\b|\bmma\b|\bacct?\s*#|\bac\s*#|^\s*aba\b|"
    r"\bdep\s*\d|cb\s+funds\s+trans|funds\s+transfer\s+same|jpmc\b|wire\s+clearing|"
    r"trust\s+wire|internal\s+accounts?\s+processing|fx\s+usd\s+(?:in|out)|"
    r"card\s+ending|reimbursement|invalid\s+beneficiary|"
    r"^\s*(?:jp\s*morgan|jpmorgan)\s+(?:clearing|chase)\b|"
    # Fedwire IMAD / trace identifiers: 4 digits then a run of mixed alphanumerics
    # with no spaces ("0525B1qgc01C004205"). Machine ids, never a party.
    r"^\s*\d{4}[A-Za-z0-9]{8,}\s*$|"
    r"^\s*(?:account|transfer|funds?|deposit|wire|payment|credit|debit|balance|client|"
    r"letter|no\s+name\s+given|new\s+york)\s*$", re.I)

# Whole-line families that are internal bookkeeping, not a transfer to a party.
_INTERNAL_LINE = re.compile(
    r"^[#\s]*(?:\d{1,2}/\d{1,2}\s+)?(?:ref\s+\S+\s+)?"
    r"(funds transferred|funds transfer (?:to|frm|from)|internal (?:funds )?transfer|"
    r"online transfer|net sweep|sweep\b|reinvestment|beginning balance|ending balance|"
    r"opening balance|closing balance|interest (?:payment|paid|earned)|service charge|"
    r"balance|misc\.? disbursement\s*-?\s*funds transferred|automatic transfer|"
    r"payment to chase card|transfer (?:to|from) account\b|cash mgmt|transfer of funds|"
    r"return of wire|deposit\s*$|check\s*$)", re.I)

# Ref-block echoes of a name the statement's column width cut off.
_REF_ECHO_LABELS = (r"bene\s*[-:.]", r"bene\s+", r"\bben\s*-", r"account\s+name\s*:",
                    r"\bname\s*:", r"/bnf/")


def _clean_party(s, is_bank=False):
    """Trim routing/address/memo noise off a captured span. Deliberately does NOT
    canonicalize the name — the column is `_raw` and OCR spellings are evidence."""
    if not s:
        return None
    s = _REDACTION.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" .,:;-/*=&")
    s = _ABA_HEAD.sub("", s)
    s = _ACCT_HEAD.sub("", s)
    s = _MEMO_TAIL.sub("", s)
    for _ in range(4):
        before = s
        s = _ZERO_ACCT_TAIL.sub("", s)
        s = _AC_TAIL.sub("", s)
        if not is_bank:
            # A trailing US address is noise on a party name, but a state suffix is
            # part of a bank's identity ("Firstbank PR", "Wachovia Bk NA FL").
            m = _STATE_ZIP_TAIL.search(s)
            if m and m.group(1).upper() in _US_STATES:
                s = s[:m.start()]
            m = _COMMA_STATE_TAIL.search(s)
            if (m and m.group(1).upper() in _US_STATES
                    and m.group(1).upper() not in _AMBIGUOUS_STATE_ABBREV):
                s = s[:m.start()]
        s = _ZIP_TAIL.sub("", s)
        s = s.strip(" .,:;-/=&")
        if s == before:
            break
    if len(s) < 3 or not re.search(r"[A-Za-z]{3}", s):
        return None
    return s


def _party_span(text, label_re):
    """(raw value, truncated) for the span after `label_re`. `truncated` means the
    next tag ran straight into the value (no space) or the value ends in a comma —
    both signal the source itself cut the name short."""
    m = re.search(label_re, text, re.I)
    if not m:
        return None, False
    rest = text[m.end():]
    stop = _PARTY_STOP.search(rest)
    if not stop:
        return rest, False
    val = rest[:stop.start()]
    glued = bool(stop.start() and not rest[stop.start() - 1].isspace())
    return val, glued or bool(re.search(r",\s*$", val))


def _party_field(text, label_re, is_bank=False):
    val, _trunc = _party_span(text, label_re)
    return _clean_party(val, is_bank=is_bank)


def _via_bank(text):
    m = re.search(r"\bvia\b\s*:?\s*", text, re.I)
    if not m:
        return None
    rest = text[m.end():]
    stop = _PARTY_STOP.search(rest)
    seg = re.sub(r"/\s*\d[\d\s]*", " ", rest[:stop.start()] if stop else rest)
    return _clean_party(seg, is_bank=True)


def _external(party):
    return party if (party and not _NOT_A_PARTY.search(party)) else None


def _alnum(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _completes(short, long_):
    """True when `long_` is the same name as `short`, just not cut off. Guards the
    Ref-echo recovery against grabbing an unrelated memo string."""
    a, b = _alnum(short), _alnum(long_)
    return (len(b) > len(a)
            and b.startswith(a[:max(8, int(len(a) * 0.7))])
            and len(b) < len(a) * 2 + 12)


def _ref_echo(text):
    for label in _REF_ECHO_LABELS:
        v = _external(_party_field(text, label))
        if v:
            return v
    return None


def parse_parties(text):
    """Statement line -> (counterparty_raw, intermediary_bank_raw, rule).

    Any element may be None. `rule` is stored so precision can be audited per
    extraction family rather than assumed uniform.
    """
    if not text or not text.strip():
        return None, None, None
    t = re.sub(r"\s+", " ", text.strip())
    if _INTERNAL_LINE.match(t):
        return None, None, "internal_or_structural"
    low = t.lower()
    bank = _via_bank(t) if re.search(r"\bvia\b", low) else None

    # "for account of" / "for benefit of" names the true beneficiary; whatever
    # precedes it is the receiving institution.
    m = re.search(r"\b(?:fao|fbo)\b\s*:?\s*", t, re.I)
    if m:
        cp = _external(_clean_party(t[m.end():]))
        if cp:
            head = re.search(r"\b(?:to|a/c\s*:|ben\s*:)\s*(.{3,60})$", t[:m.start()], re.I)
            return cp, (_clean_party(head.group(1), is_bank=True) if head else bank), "fao"

    # Inflow: the counterparty is the ordering party (B/O). A JPMorgan clearing
    # stub in B/O means the real originator sits in Org:.
    if "credit" in low and re.search(r"b\s*/\s*[o0]\s*:", low):
        cp = _party_field(t, r"b\s*/\s*[o0]\s*:")
        if cp and _NOT_A_PARTY.search(cp):
            cp = _party_field(t, r"org\s*\.?\s*[:=]")
        cp = _external(cp)
        if cp:
            return cp, bank, "wire_credit_bo"

    # Outflow: Ben:/Bnf: is the ultimate beneficiary and outranks A/C:, which on a
    # correspondent-routed wire is the beneficiary's *bank*.
    if re.search(r"\b(?:debit|wire out)\b", low) or re.match(r"(?:book transfer|foreign remittance)", low):
        for label, rule in ((r"\bben\b\s*:?", "wire_debit_ben"),
                            (r"bnf\s*:", "wire_debit_bnf"),
                            (r"a/c\s*:", "wire_debit_ac")):
            raw, truncated = _party_span(t, label)
            cp = _external(_clean_party(raw))
            if cp and truncated:
                full = _ref_echo(t)
                if full and _completes(cp, full):
                    return full, bank, rule + "_ref_recovered"
            if cp:
                return cp, bank, rule

    for label, rule in ((r"b\s*/\s*[o0]\s*:", "bo_bare"), (r"\bben\b\s*:", "ben_bare"),
                        (r"a/c\s*:", "ac_bare")):
        if re.search(label, low):
            cp = _external(_party_field(t, label))
            if cp:
                return cp, bank, rule

    # Plain-English lines: "WIRE TRANSFER TO <NAME>", "TRANSFER FROM <NAME>".
    m = re.search(r"\b(?:wire|payment|transfer|transferred|remittance|remit)\b[^.]{0,20}?"
                  r"\b(to|from)\b\s+(.{3,90})", t, re.I)
    if m:
        seg = re.split(r"\s+-\s+|\s{2,}", m.group(2))[0]
        # "<BANK> A/C <digits> <BENEFICIARY>" -> the trailing name is the party.
        ac = re.search(r"^(.{3,50}?)\s+a/c\s*:?\s*\d{4,}\s+(.{3,60})$", seg, re.I)
        if ac:
            cp = _external(_clean_party(ac.group(2)))
            if cp:
                return cp, _clean_party(ac.group(1), is_bank=True), "prose_to_ac"
        stop = _PARTY_STOP.search(seg)
        cp = _external(_clean_party(seg[:stop.start()] if stop else seg))
        if cp:
            return cp, bank, f"prose_{m.group(1).lower()}"
    return None, bank, "via_only" if bank else "no_match"


# ── account / statement identity ─────────────────────────────────────────────
_ORG_SUFFIX = re.compile(r"\b(?:LLC|INC|LTD|LP|LLP|PLLC|CORP|CO|FOUNDATION|TRUST|THE)\b")


def normalize_owner(s):
    """Fold an account-owner string to a comparison key. Deliberately coarse:
    'NES LLC' / 'NES, LLC' / 'NES  Llc' are one owner."""
    if not s:
        return None
    s = re.sub(r"[^A-Z0-9 ]", " ", str(s).upper())
    s = _ORG_SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip() or None


def account_digits(s):
    """Digits of an account/card identifier, verbatim length. NOT truncated to
    last-4: '1005', '31005', '61005' and '71005' are four different Epstein
    accounts, and folding them would merge them."""
    if not s:
        return None
    d = re.sub(r"\D", "", str(s))
    return d or None


def is_truncated_ref(ref):
    """A syntactically short EFTA id ('EFTA00', 'EFTA0013'). These are shared by
    unrelated pages, so they are unsafe as a dedupe or join key."""
    return bool(ref) and ref.startswith("EFTA") and len(ref) < 12


def _efta_map(db):
    """canonical_ref (EFTA) -> evidence_item_id, for rows that have one."""
    return {r["canonical_ref"]: r["evidence_item_id"]
            for r in db.execute("SELECT canonical_ref, evidence_item_id FROM evidence_item")}


# ─────────────────────────────── merchants ───────────────────────────────────

def build_merchants(db, limit=None):
    """Canonicalize merchant from kab.financial_transactions.merchant_name."""
    print("building merchant canon from kabass merchant_name ...")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT merchant_name AS name, merchant_category AS cat, COUNT(*) AS n
        FROM kab.financial_transactions
        WHERE merchant_name IS NOT NULL AND TRIM(merchant_name) != ''
        GROUP BY merchant_name
        ORDER BY n DESC {lim}
    """).fetchall()

    payload = []
    for r in rows:
        name = r["name"].strip()
        payload.append((name, r["cat"], _is_structural(name)))
    db.executemany(
        "INSERT OR IGNORE INTO merchant(canonical_name, merchant_category, is_structural) "
        "VALUES (?, ?, ?)", payload)
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM merchant").fetchone()[0]
    n_struct = db.execute("SELECT COUNT(*) FROM merchant WHERE is_structural=1").fetchone()[0]
    print(f"  merchant: {n:,}  (structural markers: {n_struct:,})")
    return {r["canonical_name"]: r["merchant_id"]
            for r in db.execute("SELECT merchant_id, canonical_name FROM merchant")}


# ────────────────────────────── transactions ─────────────────────────────────

def _reset_transactions(db):
    """Idempotency: transactions are fully owned by this builder; rebuild clean.

    (is_duplicate_of is a self-FK, so clear it before deleting parents.)"""
    db.execute("UPDATE financial_transaction SET is_duplicate_of = NULL")
    db.execute("DELETE FROM financial_transaction")
    db.commit()


def build_kabass_transactions(db, ss, merchant_ids, efta, limit=None):
    print("loading kabass financial_transactions -> financial_transaction ...")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT id, file_key, transaction_date, amount, merchant_name, merchant_raw,
               merchant_category, cardholder, description, account_digits, card_type,
               statement_date, source_page
        FROM kab.financial_transactions {lim}
    """).fetchall()

    batch, inserted = [], 0
    for r in rows:
        raw_amount = r["amount"]
        dollars, conf = parse_dollar_amount(raw_amount) if raw_amount not in (None, "") else (None, 0.0)
        amount_minor = _amount_to_minor(dollars)

        is_outlier = 0
        if _is_sentinel(raw_amount):
            is_outlier = 1
        elif amount_minor is not None and abs(amount_minor) > OUTLIER_ABS_MINOR:
            is_outlier = 1

        iso, _prec = normalize_date(r["transaction_date"])
        day = to_epoch_day(iso)

        cat = (r["merchant_category"] or "").strip().lower()
        direction, txn_type = CATEGORY_MAP.get(cat, ("unknown", cat or None))

        mname = (r["merchant_name"] or "").strip()
        merchant_id = merchant_ids.get(mname)

        file_key = r["file_key"]
        canonical_ref = file_key
        ev_id = efta.get(file_key)  # NULL if this file_key is not an evidence_item

        # `description` and `merchant_raw` are mutually exclusive in this source
        # (49,680 rows carry exactly one, 0 carry both): the extractor wrote the
        # statement line to one column or the other. Both are the same field.
        raw_desc = ((r["description"] or "").strip()
                    or (r["merchant_raw"] or "").strip() or None)
        counterparty, via_bank, cp_rule = parse_parties(raw_desc)

        ddk = _dedupe_key(canonical_ref, day, amount_minor, raw_desc)
        batch.append((
            ss["kabasshouse"], str(r["id"]), ev_id, canonical_ref,
            day, day, amount_minor, direction, txn_type, merchant_id,
            r["cardholder"], counterparty, via_bank, cp_rule, raw_amount, raw_desc,
            conf if conf else None, is_outlier, ddk,
        ))
        if len(batch) >= 5000:
            inserted += _flush_txn(db, batch)
            batch = []
    if batch:
        inserted += _flush_txn(db, batch)
    db.commit()
    print(f"  kabass transactions inserted: {inserted:,}")
    return inserted


def _flush_txn(db, batch):
    db.executemany("""
        INSERT OR IGNORE INTO financial_transaction
            (source_system_id, source_native_id, evidence_item_id, canonical_ref,
             txn_day_min, txn_day_max, amount_minor, direction, txn_type, merchant_id,
             cardholder_raw, counterparty_raw, intermediary_bank_raw,
             counterparty_parse_rule, raw_amount, raw_description,
             parse_confidence, is_outlier, dedupe_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    return len(batch)


def _load_lms_signed(row):
    """LMSBAND typed amounts are unsigned REAL + a direction column. Sign them:
    outgoing -> negative (outflow), incoming/credit -> positive."""
    amt = row["amount"]
    if amt is None:
        return None, None
    direction_raw = (row["direction"] or "").strip().lower()
    signed = -abs(amt) if direction_raw in ("outgoing", "debit", "out") else abs(amt)
    minor = _amount_to_minor(signed)
    dir_norm = "debit" if signed < 0 else ("credit" if signed > 0 else "unknown")
    return minor, dir_norm


def build_lmsband_transactions(db, ss, efta, limit=None):
    """ds10_transactions (wires), ds09_transactions (wires), ds09_cc_transactions (cards)."""
    lim = f"LIMIT {limit}" if limit else ""
    total = 0

    # -- ds10_transactions (Deutsche Bank wires / statement lines) --------------
    print("loading lms.ds10_transactions -> financial_transaction ...")
    rows = db.execute(f"""
        SELECT id, efta_id, tx_date, amount, direction, sender, receiver,
               bank, reference, running_balance, confidence, statement_id
        FROM lms.ds10_transactions {lim}
    """).fetchall()
    batch = []
    for r in rows:
        minor, dir_norm = _load_lms_signed(r)
        is_outlier = 1 if (minor is not None and abs(minor) > OUTLIER_ABS_MINOR) else 0
        iso, _p = normalize_date(r["tx_date"])
        day = to_epoch_day(iso)
        # For an outgoing wire sender=self, receiver=counterparty; incoming flips.
        self_side, counterparty = (
            (r["sender"], r["receiver"]) if dir_norm == "debit" else (r["receiver"], r["sender"]))
        desc = " ".join(x for x in [r["sender"], "->", r["receiver"], r["reference"]] if x)
        ev_id = efta.get(r["efta_id"])
        native = f"ds10:{r['id']}"
        ddk = _dedupe_key_for(r["efta_id"], day, minor, desc, native)
        batch.append((
            ss["lmsband"], native, ev_id, r["efta_id"],
            day, day, minor, dir_norm, "wire", None,
            self_side, counterparty, r["bank"], "source_field" if counterparty else None,
            str(r["amount"]) if r["amount"] is not None else None,
            desc, r["confidence"], is_outlier, ddk,
        ))
    total += _flush_txn(db, batch) if batch else 0
    print(f"  ds10 wires inserted: {len(batch):,}")

    # -- ds09_transactions (wire threads) ---------------------------------------
    print("loading lms.ds09_transactions -> financial_transaction ...")
    rows = db.execute(f"""
        SELECT id, efta_id, tx_date, amount, direction, sender, receiver,
               bank, reference, tx_type, confidence
        FROM lms.ds09_transactions {lim}
    """).fetchall()
    batch = []
    for r in rows:
        minor, dir_norm = _load_lms_signed(r)
        is_outlier = 1 if (minor is not None and abs(minor) > OUTLIER_ABS_MINOR) else 0
        iso, _p = normalize_date(r["tx_date"])
        day = to_epoch_day(iso)
        self_side, counterparty = (
            (r["sender"], r["receiver"]) if dir_norm == "debit" else (r["receiver"], r["sender"]))
        desc = " ".join(x for x in [r["sender"], "->", r["receiver"], r["reference"]] if x)
        ev_id = efta.get(r["efta_id"])
        native = f"ds09:{r['id']}"
        ddk = _dedupe_key_for(r["efta_id"], day, minor, desc, native)
        batch.append((
            ss["lmsband"], native, ev_id, r["efta_id"],
            day, day, minor, dir_norm, r["tx_type"] or "wire", None,
            self_side, counterparty, r["bank"], "source_field" if counterparty else None,
            str(r["amount"]) if r["amount"] is not None else None,
            desc, r["confidence"], is_outlier, ddk,
        ))
    total += _flush_txn(db, batch) if batch else 0
    print(f"  ds09 wires inserted: {len(batch):,}")

    # -- ds09_cc_transactions (credit-card lines) -------------------------------
    print("loading lms.ds09_cc_transactions -> financial_transaction ...")
    rows = db.execute(f"""
        SELECT id, efta_id, tx_date, description, merchant, location,
               amount, tx_category, confidence
        FROM lms.ds09_cc_transactions {lim}
    """).fetchall()
    batch = []
    for r in rows:
        # cc statement convention: purchases are positive, payments/credits are
        # negative in the source. Re-sign to the model's convention (outflow
        # negative, inflow positive): a purchase is a debit (-), a payment/credit
        # received against the card is a credit (+).
        amt = r["amount"]
        cat = (r["tx_category"] or "").strip().lower()
        if amt is None:
            minor, dir_norm = None, "unknown"
        elif cat in ("payment", "interest") or amt < 0:
            minor = _amount_to_minor(abs(amt))    # credit -> inflow (+)
            dir_norm = "credit"
        else:
            minor = _amount_to_minor(-abs(amt))   # purchase -> outflow (-)
            dir_norm = "debit"
        is_outlier = 1 if (minor is not None and abs(minor) > OUTLIER_ABS_MINOR) else 0
        iso, _p = normalize_date(r["tx_date"])
        day = to_epoch_day(iso)
        desc = r["description"] or r["merchant"]
        ev_id = efta.get(r["efta_id"])
        native = f"ds09cc:{r['id']}"
        ddk = _dedupe_key_for(r["efta_id"], day, minor, desc, native)
        batch.append((
            ss["lmsband"], native, ev_id, r["efta_id"],
            day, day, minor, dir_norm, "card", None,
            None, r["merchant"], None, "source_field" if r["merchant"] else None,
            str(amt) if amt is not None else None,
            desc, r["confidence"], is_outlier, ddk,
        ))
    total += _flush_txn(db, batch) if batch else 0
    print(f"  ds09 cc inserted: {len(batch):,}")

    db.commit()
    return total


def _dedupe_within_source(db, source_name):
    """Collapse rows of ONE source that share a dedupe_key (same page, date, amount
    and normalized description) — keep MIN(transaction_id), point the rest at it."""
    ss_id = source_system_id(db, source_name)
    collapsed = 0
    for grp in db.execute("""
        SELECT dedupe_key, MIN(transaction_id) AS keep_id, COUNT(*) AS c
        FROM financial_transaction
        WHERE source_system_id = ? AND dedupe_key IS NOT NULL
        GROUP BY dedupe_key HAVING c > 1
    """, (ss_id,)).fetchall():
        cur = db.execute("""
            UPDATE financial_transaction
            SET is_duplicate_of = ?
            WHERE dedupe_key = ? AND source_system_id = ? AND transaction_id != ?
              AND is_duplicate_of IS NULL
        """, (grp["keep_id"], grp["dedupe_key"], ss_id, grp["keep_id"]))
        collapsed += cur.rowcount
    db.commit()
    return collapsed


def audit_truncated_refs(db):
    """Report rows whose canonical_ref is a syntactically short EFTA id.

    Such refs ('EFTA00', 'EFTA0013') are shared by unrelated pages, so they are
    unsafe as provenance or as a join/dedupe key. The builder salts their
    dedupe_key with the source row id; this surfaces the population so a caller
    can exclude it before any page-based reasoning.
    """
    rows = db.execute("""
        SELECT ss.name AS source, t.canonical_ref AS ref, COUNT(*) AS n
        FROM financial_transaction t
        JOIN source_system ss ON ss.source_system_id = t.source_system_id
        WHERE t.canonical_ref LIKE 'EFTA%' AND LENGTH(t.canonical_ref) < 12
        GROUP BY ss.name, t.canonical_ref ORDER BY n DESC
    """).fetchall()
    total = sum(r["n"] for r in rows)
    if total:
        detail = ", ".join(f"{r['ref']}×{r['n']}" for r in rows[:6])
        print(f"  ! truncated canonical_ref: {total:,} rows across {len(rows)} refs ({detail})"
              "\n    -> dedupe_key salted with source row id; exclude from page-based joins")
    else:
        print("  truncated canonical_ref: none")
    return total


def dedupe_transactions(db):
    """Three passes:

    1. within-kabass same-page dups: rows sharing (canonical_ref, day, amount,
       normalized description) — keep MIN(transaction_id), point the rest at it.
    2. within-LMSBAND, the same test. Skipping this pass was the documented
       asymmetry that left repeated-hash LMSBAND groups uncollapsed while the
       equivalent kabass groups were flagged.
    3. cross-source: an LMSBAND row and a kabass row sharing (canonical_ref, day,
       amount) -> PREFER LMSBAND as canonical; mark the kabass row duplicate.
    """
    print("deduping transactions ...")
    kab = source_system_id(db, "kabasshouse")
    lms = source_system_id(db, "lmsband")

    same_page = _dedupe_within_source(db, "kabasshouse")
    print(f"  within-kabass same-page dups collapsed: {same_page:,}")
    within_lms = _dedupe_within_source(db, "lmsband")
    print(f"  within-lmsband same-page dups collapsed: {within_lms:,}")

    # Pass 3: cross-source. Only where a shared canonical_ref (EFTA) exists, and
    # only pointing at an LMSBAND row that survived pass 2 — otherwise a kabass
    # row would chain through a collapsed duplicate.
    cross = db.execute("""
        UPDATE financial_transaction AS k
        SET is_duplicate_of = (
            SELECT MIN(l.transaction_id) FROM financial_transaction l
            WHERE l.source_system_id = ?
              AND l.is_duplicate_of IS NULL
              AND l.canonical_ref = k.canonical_ref
              AND l.txn_day_min IS k.txn_day_min
              AND l.amount_minor = k.amount_minor
        )
        WHERE k.source_system_id = ?
          AND k.is_duplicate_of IS NULL
          AND k.canonical_ref IS NOT NULL
          AND k.amount_minor IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM financial_transaction l
            WHERE l.source_system_id = ?
              AND l.is_duplicate_of IS NULL
              AND l.canonical_ref = k.canonical_ref
              AND l.txn_day_min IS k.txn_day_min
              AND l.amount_minor = k.amount_minor
          )
    """, (lms, kab, lms))
    db.commit()
    print(f"  cross-source (kabass->lmsband) dups collapsed: {cross.rowcount:,}")
    audit_truncated_refs(db)
    return same_page, within_lms, cross.rowcount


# ───────────────────────────── accounts ──────────────────────────────────────
# Confidence by key_basis. The distinction matters: an owner-only key groups one
# party's statements but is NOT a single account (Jeffrey E Epstein alone appears
# under 30 distinct account_digits), so a query that means "per account" must
# filter on the digit-anchored tiers.
_KEY_CONFIDENCE = {
    "source_account_number": 0.95,   # LMSBAND gave a full account number + bank
    "owner_digits": 0.9,             # statement carried both owner and card/acct digits
    "digits": 0.6,                   # digits with no owner attributed
    "owner": 0.3,                    # owner only — a party grouping, not an account
}


class AccountRegistry:
    """Interns account keys so every builder stage resolves the same identity."""

    def __init__(self, db):
        self.db = db
        self._cache = {}

    @staticmethod
    def make_key(owner=None, digits=None, institution=None):
        """-> (account_key, key_basis) or (None, None) if nothing identifies it."""
        o, d = normalize_owner(owner), account_digits(digits)
        inst = normalize_owner(institution)
        if o and d:
            return f"{o}|{inst or ''}|{d}", "owner_digits"
        if d:
            return f"|{inst or ''}|{d}", "digits"
        if o:
            return f"{o}|{inst or ''}|", "owner"
        return None, None

    def resolve(self, owner=None, digits=None, institution=None,
                account_type=None, key_basis=None):
        """Upsert an account and return its id (None when unidentifiable)."""
        key, basis = self.make_key(owner, digits, institution)
        if not key:
            return None
        basis = key_basis or basis
        if key in self._cache:
            return self._cache[key]
        cur = self.db.execute("""
            INSERT INTO financial_account
                (account_key, institution_name, owner_raw, account_type,
                 account_digits, resolution_confidence, key_basis)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_key) DO UPDATE SET
                institution_name = COALESCE(financial_account.institution_name, excluded.institution_name),
                owner_raw        = COALESCE(financial_account.owner_raw, excluded.owner_raw),
                account_type     = COALESCE(NULLIF(financial_account.account_type,'unknown'),
                                            NULLIF(excluded.account_type,'unknown'))
            RETURNING account_id
        """, (key, (institution or "").strip() or None, (owner or "").strip() or None,
              (account_type or "").strip() or None, account_digits(digits),
              _KEY_CONFIDENCE.get(basis), basis)).fetchone()
        self._cache[key] = cur["account_id"]
        return cur["account_id"]


def build_accounts(db, limit=None):
    """Mint financial_account rows from every source that identifies an account.

    Sources, in descending identity strength:
      * LMSBAND ds10_balances  — account_number + bank + holder + type
      * LMSBAND ds09_cc_statements — cardholder + card_last4
      * kabass financial_transactions — cardholder + account_digits (+ card_type)
    """
    print("building financial_account ...")
    # Every referrer must be released before the parent rows go, or the self/child
    # FKs abort the DELETE. financial_statement.account_id is one of them.
    db.execute("UPDATE financial_transaction SET account_id = NULL, statement_id = NULL")
    db.execute("UPDATE balance_snapshot SET account_id = NULL")
    db.execute("UPDATE position_snapshot SET account_id = NULL")
    db.execute("UPDATE financial_statement SET account_id = NULL")
    db.execute("DELETE FROM financial_account")
    db.commit()
    reg = AccountRegistry(db)
    lim = f"LIMIT {limit}" if limit else ""

    for r in db.execute(f"""SELECT DISTINCT account_holder, account_number, account_type, bank
                            FROM lms.ds10_balances {lim}""").fetchall():
        reg.resolve(owner=r["account_holder"], digits=r["account_number"],
                    institution=r["bank"], account_type=r["account_type"],
                    key_basis="source_account_number" if account_digits(r["account_number"]) else None)
    for r in db.execute(f"""SELECT DISTINCT cardholder, card_last4
                            FROM lms.ds09_cc_statements {lim}""").fetchall():
        reg.resolve(owner=r["cardholder"], digits=r["card_last4"], account_type="credit_card")
    for r in db.execute(f"""SELECT DISTINCT cardholder, account_digits, card_type
                            FROM kab.financial_transactions {lim}""").fetchall():
        reg.resolve(owner=r["cardholder"], digits=r["account_digits"],
                    account_type=r["card_type"])
    db.commit()

    # Seeded only: the linking stages below resolve parties this pass never saw
    # (LMSBAND wire sender/receiver accounts, position owners) and mint more.
    # report_accounts() prints the final population.
    total = db.execute("SELECT COUNT(*) FROM financial_account").fetchone()[0]
    print(f"  financial_account seeded: {total:,}")
    return reg


def report_accounts(db):
    """Final account population by tier, after every linking stage has run."""
    tiers = db.execute("""SELECT key_basis, COUNT(*) n FROM financial_account
                          GROUP BY key_basis ORDER BY n DESC""").fetchall()
    total = db.execute("SELECT COUNT(*) FROM financial_account").fetchone()[0]
    print(f"  financial_account: {total:,}  ("
          + ", ".join(f"{r['key_basis']}={r['n']}" for r in tiers) + ")")
    return total


def _native_id_map(db, source_name):
    """source_native_id -> transaction_id for one source.

    The source tables have no index on their id column, so every linking stage
    resolves through this in-memory map instead of a SQL join — a join here is a
    nested scan of ~50K x ~50K rows.
    """
    ss_id = source_system_id(db, source_name)
    return {r["source_native_id"]: r["transaction_id"] for r in db.execute(
        "SELECT source_native_id, transaction_id FROM financial_transaction "
        "WHERE source_system_id = ?", (ss_id,))}


def link_transaction_accounts(db, reg, limit=None):
    """Set financial_transaction.account_id from the row's own owner/digit fields."""
    print("linking transactions -> financial_account ...")
    lim = f"LIMIT {limit}" if limit else ""
    kab_ids = _native_id_map(db, "kabasshouse")
    updates = []
    for r in db.execute(f"""SELECT id, cardholder, account_digits, card_type
                            FROM kab.financial_transactions {lim}""").fetchall():
        txn_id = kab_ids.get(str(r["id"]))
        if txn_id is None:
            continue
        acct = reg.resolve(owner=r["cardholder"], digits=r["account_digits"],
                           account_type=r["card_type"])
        if acct:
            updates.append((acct, txn_id))

    # LMSBAND wires name the account on the self side of the transfer.
    lms_ids = _native_id_map(db, "lmsband")
    for table, prefix in (("ds10_transactions", "ds10"), ("ds09_transactions", "ds09")):
        for r in db.execute(f"""
            SELECT id, direction, sender, sender_account, receiver, receiver_account, bank
            FROM lms.{table} {lim}
        """).fetchall():
            txn_id = lms_ids.get(f"{prefix}:{r['id']}")
            if txn_id is None:
                continue
            outgoing = (r["direction"] or "").strip().lower() in ("outgoing", "debit", "out")
            owner = r["sender"] if outgoing else r["receiver"]
            digits = r["sender_account"] if outgoing else r["receiver_account"]
            acct = reg.resolve(owner=owner, digits=digits, institution=r["bank"])
            if acct:
                updates.append((acct, txn_id))
    db.executemany("UPDATE financial_transaction SET account_id = ? WHERE transaction_id = ?",
                   updates)
    db.commit()

    n = db.execute("SELECT COUNT(account_id) FROM financial_transaction").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM financial_transaction").fetchone()[0]
    strong = db.execute("""
        SELECT COUNT(*) FROM financial_transaction t JOIN financial_account a USING(account_id)
        WHERE a.key_basis IN ('owner_digits','digits','source_account_number')
    """).fetchone()[0]
    print(f"  transactions with account_id: {n:,}/{total:,} ({n/total:.2%}) — of which "
          f"digit-anchored: {strong:,} ({strong/total:.2%})")
    return n


# ─────────────────────────── balances / positions ────────────────────────────

def build_balances(db, efta, reg=None, limit=None):
    print("loading lms.ds10_balances -> balance_snapshot ...")
    db.execute("DELETE FROM balance_snapshot")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT efta_id, account_holder, account_number, account_type, bank,
               balance_date, balance FROM lms.ds10_balances {lim}
    """).fetchall()
    batch = []
    for r in rows:
        minor = _amount_to_minor(r["balance"])
        if minor is None:
            continue
        iso, _p = normalize_date(r["balance_date"])
        day = to_epoch_day(iso)
        if day is None:
            continue
        acct = reg.resolve(owner=r["account_holder"], digits=r["account_number"],
                           institution=r["bank"], account_type=r["account_type"],
                           key_basis="source_account_number"
                           if account_digits(r["account_number"]) else None) if reg else None
        batch.append((acct, r["account_holder"], day, minor, efta.get(r["efta_id"])))
    db.executemany("""
        INSERT INTO balance_snapshot(account_id, owner_raw, as_of_day, balance_minor,
                                     evidence_item_id)
        VALUES (?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    linked = db.execute("SELECT COUNT(account_id) FROM balance_snapshot").fetchone()[0]
    print(f"  balance_snapshot: {len(batch):,}  (account_id set: {linked:,})")
    return len(batch)


def build_positions(db, efta, reg=None, limit=None):
    print("loading lms.ds10_positions -> position_snapshot (+ security) ...")
    db.execute("DELETE FROM position_snapshot")
    lim = f"LIMIT {limit}" if limit else ""
    rows = db.execute(f"""
        SELECT efta_id, entity, investment, position_date, value, cost_basis
        FROM lms.ds10_positions {lim}
    """).fetchall()

    # securities first
    secs = {r["investment"].strip() for r in rows if r["investment"] and r["investment"].strip()}
    db.executemany("INSERT OR IGNORE INTO security(canonical_name) VALUES (?)", [(s,) for s in secs])
    db.commit()
    sec_ids = {r["canonical_name"]: r["security_id"]
               for r in db.execute("SELECT security_id, canonical_name FROM security")}

    batch = []
    for r in rows:
        # Detect absurdity from the raw float (before scaling, which may overflow
        # to None). cost_basis > $1e12 is the flagged case from the spec.
        raw_cb, raw_mv = r["cost_basis"], r["value"]
        is_outlier = 0
        if raw_cb is not None and abs(raw_cb) > 1e12:
            is_outlier = 1
        if raw_mv is not None and abs(raw_mv) > 1e12:
            is_outlier = 1
        mv = _amount_to_minor(raw_mv)
        cb = _amount_to_minor(raw_cb)
        iso, _p = normalize_date(r["position_date"])
        day = to_epoch_day(iso)
        if day is None:
            continue
        sid = sec_ids.get((r["investment"] or "").strip())
        acct = reg.resolve(owner=r["entity"]) if reg else None
        batch.append((acct, r["entity"], sid, day, mv, cb, is_outlier, efta.get(r["efta_id"])))
    db.executemany("""
        INSERT INTO position_snapshot
            (account_id, owner_raw, security_id, as_of_day, market_value_minor,
             cost_basis_minor, is_outlier, evidence_item_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    n_out = db.execute("SELECT COUNT(*) FROM position_snapshot WHERE is_outlier=1").fetchone()[0]
    print(f"  position_snapshot: {len(batch):,}  (securities: {len(sec_ids):,}, outliers: {n_out})")
    return len(batch)


# ────────────────────────────── statements ───────────────────────────────────
# Balance-marker merchant/description names that bound a statement period. These
# are the boundary balances the closed-ledger identity needs.
BEGIN_MARKERS = {"beginning balance", "opening balance", "balance forward",
                 "previous balance", "beginning cash balance"}
END_MARKERS = {"ending balance", "closing balance", "total ending balance",
               "new balance", "ending cash balance"}
RECON_TOLERANCE_MINOR = 1          # ±1 cent, for rounding only


def _marker(*fields):
    for f in fields:
        key = (f or "").strip().lower().rstrip(":")
        if key in BEGIN_MARKERS:
            return "begin"
        if key in END_MARKERS:
            return "end"
    return None


def build_statements(db, efta, reg=None, limit=None):
    """Populate financial_statement from every source that delimits a period.

    Statements are DOCUMENT-scoped for kabass (file_key + statement_date), not
    (account, date): the extractor emitted one balance pair per document, and
    merging documents that share an account and statement date produces groups
    with several 'Beginning Balance' rows that cannot be reconciled. Measured on
    the full corpus, document scoping yields 574 boundary-paired statements
    against 516 for account-scoping.
    """
    print("building financial_statement ...")
    db.execute("UPDATE financial_transaction SET statement_id = NULL")
    db.execute("DELETE FROM financial_statement")
    db.commit()
    lim = f"LIMIT {limit}" if limit else ""
    inserted = 0

    def upsert(key, **cols):
        cols["statement_key"] = key
        names = ", ".join(cols)
        holes = ", ".join("?" for _ in cols)
        row = db.execute(
            f"INSERT INTO financial_statement ({names}) VALUES ({holes}) "
            f"ON CONFLICT(statement_key) DO UPDATE SET statement_key = excluded.statement_key "
            f"RETURNING statement_id", tuple(cols.values())).fetchone()
        return row["statement_id"]

    # 1. kabass: one statement per (document, statement_date).
    kab = source_system_id(db, "kabasshouse")
    kab_ids = _native_id_map(db, "kabasshouse")
    groups = {}
    for r in db.execute(f"""
        SELECT id, file_key, statement_date, cardholder, account_digits, card_type
        FROM kab.financial_transactions {lim}
    """).fetchall():
        txn_id = kab_ids.get(str(r["id"]))
        if txn_id is None:
            continue
        sd = (r["statement_date"] or "").strip() or None
        key = f"kab:{r['file_key']}|{sd or ''}"
        g = groups.setdefault(key, {"txns": [], "row": r, "sd": sd})
        g["txns"].append(txn_id)

    links = []
    for key, g in groups.items():
        r = g["row"]
        iso, _p = normalize_date(g["sd"]) if g["sd"] else (None, None)
        sid = upsert(
            key,
            account_id=(reg.resolve(owner=r["cardholder"], digits=r["account_digits"],
                                    account_type=r["card_type"]) if reg else None),
            source_system_id=kab,
            canonical_ref=r["file_key"],
            statement_date_day=to_epoch_day(iso),
            period_end_day=to_epoch_day(iso),
            evidence_item_id=efta.get(r["file_key"]),
            recon_basis="none",
            recon_status="not_computable",
        )
        links.extend((sid, t) for t in g["txns"])
        inserted += 1
    db.executemany("UPDATE financial_transaction SET statement_id = ? WHERE transaction_id = ?",
                   links)
    db.commit()
    print(f"  kabass document statements: {inserted:,} (linked {len(links):,} transactions)")

    # 2. LMSBAND credit-card statements: the totals are declared on the statement.
    lms_ids = _native_id_map(db, "lmsband")
    cc_members = {}
    for r in db.execute("SELECT id, statement_id FROM lms.ds09_cc_transactions").fetchall():
        txn_id = lms_ids.get(f"ds09cc:{r['id']}")
        if txn_id is not None and r["statement_id"] is not None:
            cc_members.setdefault(r["statement_id"], []).append(txn_id)
    cc, cc_links = 0, []
    for r in db.execute(f"SELECT * FROM lms.ds09_cc_statements {lim}").fetchall():
        s_iso, _ = normalize_date(r["billing_start"])
        e_iso, _ = normalize_date(r["billing_end"])
        begin = _amount_to_minor(r["previous_balance"])
        end = _amount_to_minor(r["statement_balance"])
        # A card statement's declared totals are unsigned: purchases add to the
        # balance, payments reduce it. Re-sign into the model's convention.
        charges = _amount_to_minor(abs(r["purchases_total"])) if r["purchases_total"] is not None else None
        payments = -_amount_to_minor(abs(r["payments_total"])) if r["payments_total"] is not None else None
        sid = upsert(
            f"ds09cc:{r['id']}",
            account_id=(reg.resolve(owner=r["cardholder"], digits=r["card_last4"],
                                    account_type="credit_card") if reg else None),
            source_system_id=source_system_id(db, "lmsband"),
            canonical_ref=r["efta_id"],
            period_start_day=to_epoch_day(s_iso), period_end_day=to_epoch_day(e_iso),
            statement_date_day=to_epoch_day(e_iso),
            beginning_balance_minor=begin, ending_balance_minor=end,
            charges_minor=charges, payments_minor=payments,
            evidence_item_id=efta.get(r["efta_id"]),
            recon_basis="declared_totals", recon_status="not_computable",
        )
        cc_links.extend((sid, t) for t in cc_members.get(r["id"], ()))
        cc += 1
    db.executemany("UPDATE financial_transaction SET statement_id = ? WHERE transaction_id = ?",
                   cc_links)
    db.commit()
    print(f"  lmsband credit-card statements: {cc:,}")

    # 3. LMSBAND fund statements: beginning + additions + redemptions + income.
    fund = 0
    for r in db.execute(f"SELECT * FROM lms.ds09_fund_statements {lim}").fetchall():
        iso, _ = normalize_date(r["statement_date"])
        additions = _amount_to_minor(r["additions"]) or 0
        income = _amount_to_minor(r["net_income_mtd"]) or 0
        redemptions = _amount_to_minor(r["redemptions"])
        redemptions = -abs(redemptions) if redemptions else 0
        upsert(
            f"ds09fund:{r['id']}",
            account_id=(reg.resolve(owner=r["investor_name"], digits=r["investor_number"],
                                    institution=r["fund_name"],
                                    account_type="fund_investment") if reg else None),
            source_system_id=source_system_id(db, "lmsband"),
            canonical_ref=r["efta_id"],
            period_end_day=to_epoch_day(iso), statement_date_day=to_epoch_day(iso),
            beginning_balance_minor=_amount_to_minor(r["beginning_balance_mtd"]),
            ending_balance_minor=_amount_to_minor(r["ending_balance"]),
            charges_minor=redemptions, payments_minor=additions + income,
            evidence_item_id=efta.get(r["efta_id"]),
            recon_basis="fund_totals", recon_status="not_computable",
        )
        fund += 1
    db.commit()
    print(f"  lmsband fund statements: {fund:,}")

    # 4. LMSBAND ds10 statement reconciliation (currently 0 source rows; kept so a
    #    future extraction run flows through without a builder change).
    recon = 0
    for r in db.execute(f"""
        SELECT rowid AS rid, efta_id, statement_start_date, statement_end_date,
               beginning_balance, ending_balance, recon_delta, recon_status
        FROM lms.ds10_statement_recon {lim}""").fetchall():
        s_iso, _ = normalize_date(r["statement_start_date"])
        e_iso, _ = normalize_date(r["statement_end_date"])
        upsert(
            f"ds10recon:{r['rid']}",
            source_system_id=source_system_id(db, "lmsband"),
            canonical_ref=r["efta_id"],
            period_start_day=to_epoch_day(s_iso), period_end_day=to_epoch_day(e_iso),
            statement_date_day=to_epoch_day(e_iso),
            beginning_balance_minor=_amount_to_minor(r["beginning_balance"]),
            ending_balance_minor=_amount_to_minor(r["ending_balance"]),
            recon_delta_minor=_amount_to_minor(r["recon_delta"]),
            recon_status=r["recon_status"] or "not_computable",
            recon_basis="declared_totals",
            evidence_item_id=efta.get(r["efta_id"]),
        )
        recon += 1
    db.commit()
    if recon:
        print(f"  lmsband ds10 statement_recon: {recon:,}")

    total = db.execute("SELECT COUNT(*) FROM financial_statement").fetchone()[0]
    linked = db.execute("SELECT COUNT(statement_id) FROM financial_transaction").fetchone()[0]
    n_txn = db.execute("SELECT COUNT(*) FROM financial_transaction").fetchone()[0]
    print(f"  financial_statement: {total:,}  (transactions linked: {linked:,}/{n_txn:,}"
          f" = {linked/n_txn:.2%})" if n_txn else f"  financial_statement: {total:,}")
    return total


def reconcile_statements(db):
    """Closed-ledger reconciliation: ending = beginning + charges + payments.

    Runs only where a statement has BOTH boundary balances and a complete set of
    parseable member amounts. Everything else stays 'not_computable' — a missing
    boundary is not a zero residual. Statements whose members are already flagged
    as duplicates are excluded so one page counted twice cannot create a delta.
    """
    print("reconciling statements ...")
    # Boundary balances for kabass document statements come from marker rows.
    kab = source_system_id(db, "kabasshouse")
    rows = db.execute("""
        SELECT t.transaction_id, t.statement_id, t.amount_minor, t.raw_amount,
               t.is_duplicate_of, m.canonical_name AS merchant, t.raw_description
        FROM financial_transaction t
        LEFT JOIN merchant m ON m.merchant_id = t.merchant_id
        WHERE t.source_system_id = ? AND t.statement_id IS NOT NULL
    """, (kab,)).fetchall()

    per_stmt = {}
    for r in rows:
        s = per_stmt.setdefault(r["statement_id"], {"begin": [], "end": [], "body": []})
        kind = _marker(r["merchant"], r["raw_description"])
        if kind == "begin":
            s["begin"].append(r)
        elif kind == "end":
            s["end"].append(r)
        elif r["is_duplicate_of"] is None:
            s["body"].append(r)

    updates, computable, ok = [], 0, 0
    for sid, s in per_stmt.items():
        if len(s["begin"]) != 1 or len(s["end"]) != 1:
            continue                                  # no pair, or ambiguous
        begin = s["begin"][0]["amount_minor"]
        end = s["end"][0]["amount_minor"]
        amounts = [r["amount_minor"] for r in s["body"]]
        if begin is None or end is None or any(a is None for a in amounts):
            continue                                  # an unparseable member
        charges = sum(a for a in amounts if a < 0)
        payments = sum(a for a in amounts if a > 0)
        computed = begin + charges + payments
        delta = end - computed
        computable += 1
        status = "ok" if abs(delta) <= RECON_TOLERANCE_MINOR else "delta"
        ok += status == "ok"
        updates.append((begin, end, charges, payments, computed, len(s["body"]),
                        "boundary_markers", status, delta, sid))
    db.executemany("""
        UPDATE financial_statement
        SET beginning_balance_minor = ?, ending_balance_minor = ?, charges_minor = ?,
            payments_minor = ?, computed_ending_minor = ?, txn_count = ?,
            recon_basis = ?, recon_status = ?, recon_delta_minor = ?
        WHERE statement_id = ?
    """, updates)

    # Declared-total statements (card / fund) reconcile from their own fields.
    declared = db.execute("""
        SELECT statement_id, beginning_balance_minor AS b, ending_balance_minor AS e,
               charges_minor AS c, payments_minor AS p
        FROM financial_statement
        WHERE recon_basis IN ('declared_totals','fund_totals')
          AND beginning_balance_minor IS NOT NULL AND ending_balance_minor IS NOT NULL
          AND charges_minor IS NOT NULL AND payments_minor IS NOT NULL
    """).fetchall()
    d_updates = []
    for r in declared:
        computed = r["b"] + r["c"] + r["p"]
        delta = r["e"] - computed
        status = "ok" if abs(delta) <= RECON_TOLERANCE_MINOR else "delta"
        d_updates.append((computed, status, delta, r["statement_id"]))
    db.executemany("""
        UPDATE financial_statement
        SET computed_ending_minor = ?, recon_status = ?, recon_delta_minor = ?
        WHERE statement_id = ?
    """, d_updates)
    db.commit()

    total = db.execute("SELECT COUNT(*) FROM financial_statement").fetchone()[0]
    by = dict(db.execute("""SELECT recon_status, COUNT(*) FROM financial_statement
                            GROUP BY recon_status""").fetchall())
    n_comp = computable + len(d_updates)
    n_ok = ok + sum(1 for _c, s, _d, _i in d_updates if s == "ok")
    print(f"  reconcilable statements: {n_comp:,}/{total:,} ({n_comp/total:.2%})"
          if total else "  reconcilable statements: 0")
    print(f"    residual within +/-1c: {n_ok:,}"
          + (f" ({n_ok/n_comp:.1%} of computable)" if n_comp else ""))
    print(f"    by recon_status: {by}")
    return n_comp, n_ok


def build_flights(db, ss, efta, limit=None):
    """ds09_travel_flights joined to invoices (ticket cost) + passengers (names)."""
    print("loading lms.ds09_travel_flights -> fin_flight ...")
    db.execute("DELETE FROM fin_flight")
    lim = f"LIMIT {limit}" if limit else ""
    # Scalar subquery for the invoice total keeps this 1 row per source flight —
    # a plain LEFT JOIN fans out when a record_locator maps to several invoices.
    rows = db.execute(f"""
        SELECT f.id, f.efta_id, f.passenger_name, f.flight_date, f.airline,
               f.flight_number, f.origin, f.destination, f.ticket_number,
               f.ticket_cost, f.record_locator,
               (SELECT MAX(inv.total_charged) FROM lms.ds09_travel_invoices inv
                 WHERE inv.record_locator = f.record_locator
                   AND f.record_locator IS NOT NULL AND f.record_locator != ''
               ) AS inv_total
        FROM lms.ds09_travel_flights f
        {lim}
    """).fetchall()
    batch = []
    for r in rows:
        iso, _p = normalize_date(r["flight_date"])
        day = to_epoch_day(iso)
        cost = r["ticket_cost"] if r["ticket_cost"] is not None else r["inv_total"]
        cost_minor = _amount_to_minor(cost)
        batch.append((
            ss["lmsband"], f"ds09flt:{r['id']}", efta.get(r["efta_id"]),
            r["passenger_name"], day, r["airline"], r["flight_number"],
            r["origin"], r["destination"], cost_minor, r["ticket_number"],
            r["record_locator"],
        ))
    db.executemany("""
        INSERT INTO fin_flight
            (source_system_id, source_native_id, evidence_item_id, passenger_raw,
             flight_day, airline, flight_number, origin, destination,
             ticket_cost_minor, ticket_number, record_locator)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    db.commit()
    print(f"  fin_flight: {len(batch):,}")
    return len(batch)


# ─────────────────────────────────── main ────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, help="cap rows per source table (testing)")
    ap.add_argument("--stage", action="append",
                    choices=["merchants", "transactions", "accounts", "balances",
                             "positions", "statements", "flights", "all"],
                    help="run only these stages (default: all)")
    args = ap.parse_args()
    stages = set(args.stage or ["all"])
    run_all = "all" in stages

    db = get_db()
    init_schema(db)
    attach(db, "kab", KABASS_DB)
    attach(db, "lms", LMSBAND_DB)
    run_id = new_run(db, "build_financials", note="normalized financial model")
    ss = {n: source_system_id(db, n) for n in ("kabasshouse", "lmsband")}
    efta = _efta_map(db)

    total = 0
    merchant_ids = None
    if run_all or "merchants" in stages:
        merchant_ids = build_merchants(db, limit=args.limit)
    if run_all or "transactions" in stages:
        if merchant_ids is None:
            merchant_ids = {r["canonical_name"]: r["merchant_id"]
                            for r in db.execute("SELECT merchant_id, canonical_name FROM merchant")}
        _reset_transactions(db)
        total += build_kabass_transactions(db, ss, merchant_ids, efta, limit=args.limit)
        total += build_lmsband_transactions(db, ss, efta, limit=args.limit)
        dedupe_transactions(db)

    # Accounts underpin balances/positions/statements, so they are rebuilt whenever
    # any of those stages runs. Rebuilding accounts re-mints account_id values, so
    # balances and positions MUST be rebuilt with them — otherwise a
    # `--stage statements` run would leave their account_id NULL.
    reg = None
    needs_accounts = run_all or stages & {"accounts", "balances", "positions", "statements"}
    if needs_accounts:
        reg = build_accounts(db, limit=args.limit)
        link_transaction_accounts(db, reg, limit=args.limit)
        build_balances(db, efta, reg=reg, limit=args.limit)
        build_positions(db, efta, reg=reg, limit=args.limit)
        report_accounts(db)
    if run_all or "statements" in stages:
        build_statements(db, efta, reg=reg, limit=args.limit)
        reconcile_statements(db)
    if run_all or "flights" in stages:
        build_flights(db, ss, efta, limit=args.limit)

    n_txn = db.execute("SELECT COUNT(*) FROM financial_transaction").fetchone()[0]
    n_out = db.execute("SELECT COUNT(*) FROM financial_transaction WHERE is_outlier=1").fetchone()[0]
    n_dup = db.execute("SELECT COUNT(*) FROM financial_transaction WHERE is_duplicate_of IS NOT NULL").fetchone()[0]
    n_cp = db.execute("SELECT COUNT(counterparty_raw) FROM financial_transaction").fetchone()[0]
    n_bank = db.execute("SELECT COUNT(intermediary_bank_raw) FROM financial_transaction").fetchone()[0]
    db.execute("UPDATE derivation_run SET completed_at=CURRENT_TIMESTAMP, record_count=? WHERE run_id=?",
               (n_txn, run_id))
    db.commit()
    print(f"\nfinancial_transaction: {n_txn:,}  (outliers {n_out:,}, duplicates {n_dup:,})")
    if n_txn:
        print(f"  counterparty_raw: {n_cp:,} ({n_cp/n_txn:.2%})   "
              f"intermediary_bank_raw: {n_bank:,} ({n_bank/n_txn:.2%})")
    db.close()


if __name__ == "__main__":
    main()
