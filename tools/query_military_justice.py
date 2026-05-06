#!/usr/bin/env python3
"""
Military justice appellate court query tool.

Unified scraper for the U.S. Court of Appeals for the Armed Forces (CAAF) and the
four service Courts of Criminal Appeals (ACCA, NMCCA, AFCCA, CGCCA). These courts
publish dockets and opinions on disparate static sites and are NOT in
CourtListener — Eddie Gallagher's 2019 court-martial, for example, has no
CourtListener record.

Killer feature: the `attorney` subcommand cross-searches all available indices
and opinion text for a civilian counsel name (Parlatore, Kageleiry, Cave, etc.)
and returns every case where that name appears.

Court coverage and data layout (as of 2026-04-29 probe):

CAAF — armfor.uscourts.gov  (HTML term indices + PDF opinions)
  Index pages: /opinions/<YEAR>OctTerm.htm and /opinions/CurrentOpins.htm
  Opinion PDFs: /opinions/<YEAR>OctTerm/<DOCKET6>.pdf  (e.g. 240156.pdf)
  Daily Journal: /journal/<YEAR>Jrnl/<YEAR><Mon>.htm  (paragraphs, not table)
  Hearing Calendar: /calendar.htm

ACCA — jagcnet.army.mil/ACCALibrary  (HTML lists + PDF opinions)
  Opinion-of-the-Court list: /cases/opinions/OC  (also MO, SFA, SD)
  Opinion files: /cases/opinion/file/<numeric_id>

NMCCA — jag.navy.mil/about/organization/ojag/code-05/nmcca/opinions/
  Has a server-side search form (parties, docket, date, type). Form-rendered.

AFCCA — afcca.law.af.mil  (HTML lists + PDF opinions)
  Opinions: /opinions.html
  Docket: /docket.html  (case name, ACM number, hearing date, panel — no attorneys)
  Opinion PDFs: /afcca_opinions/cp/<slug>.pdf

CGCCA — uscg.mil/Resources/Legal/Court-of-Criminal-Appeals/CGCCA-Opinions/
  Public site returns 403 to bare HTTP UAs (Akamai/CDN). Use --user-agent
  override or fall back to FindLaw mirror at caselaw.findlaw.com.

PDF text extraction uses pypdf if installed (pymupdf as alternate).

Usage:
    tools/query_military_justice.py search "Edward Gallagher" --output /tmp/x.json
    tools/query_military_justice.py attorney "Parlatore" --output /tmp/x.json
    tools/query_military_justice.py caaf-dockets 2024 --output /tmp/x.json
    tools/query_military_justice.py caaf-opinion 24-0156 --output /tmp/x.json
    tools/query_military_justice.py acca-search "Robert Burke" --output /tmp/x.json
    tools/query_military_justice.py case-detail "24-0156/AR" --output /tmp/x.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from output_util import add_output_args, write_output

try:
    from tools.lead_tracker import log_search
except ImportError:
    try:
        from lead_tracker import log_search  # type: ignore
    except ImportError:
        def log_search(*a, **kw):  # type: ignore
            pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "datasets"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "military_justice_cache.db"

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 ithildin-osint/1.0"
)
DEFAULT_RATE_LIMIT_S = 1.0  # 1 req/sec by default

CAAF_BASE = "https://www.armfor.uscourts.gov"
ACCA_BASE = "https://www.jagcnet.army.mil"
NMCCA_BASE = "https://www.jag.navy.mil"
AFCCA_BASE = "https://afcca.law.af.mil"
CGCCA_BASE = "https://www.uscg.mil"

COURTS = ("CAAF", "ACCA", "NMCCA", "AFCCA", "CGCCA")

# Service codes used in CAAF docket numbers (e.g. "24-0156/AR")
CAAF_SERVICE_CODES = {
    "AR": "ACCA",   # Army
    "AF": "AFCCA",  # Air Force
    "NA": "NMCCA",  # Navy
    "MC": "NMCCA",  # Marine Corps (under NMCCA)
    "CG": "CGCCA",  # Coast Guard
}


# ---------------------------------------------------------------------------
# HTTP fetcher with rate limiting + SQLite cache
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes
    fetched_at: str
    cached: bool = False
    error: Optional[str] = None


def _init_cache() -> sqlite3.Connection:
    db = sqlite3.connect(CACHE_DB)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pages (
            url TEXT PRIMARY KEY,
            status INTEGER,
            content_type TEXT,
            body BLOB,
            fetched_at TEXT,
            error TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pdf_text (
            url TEXT PRIMARY KEY,
            sha256 TEXT,
            text TEXT,
            extracted_at TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS docket_index (
            court TEXT,
            docket TEXT,
            case_name TEXT,
            cca_number TEXT,
            decision_date TEXT,
            citation TEXT,
            opinion_url TEXT,
            term TEXT,
            indexed_at TEXT,
            PRIMARY KEY (court, docket, term, decision_date)
        )
        """
    )
    # Index for lookups
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_docket_case ON docket_index(case_name)"
    )
    db.commit()
    return db


_LAST_FETCH_HOST: dict[str, float] = {}


def _polite_sleep(url: str, rate_limit: float) -> None:
    if rate_limit <= 0:
        return
    host = re.match(r"https?://([^/]+)", url)
    key = host.group(1) if host else url
    last = _LAST_FETCH_HOST.get(key, 0.0)
    delta = time.time() - last
    if delta < rate_limit:
        time.sleep(rate_limit - delta)
    _LAST_FETCH_HOST[key] = time.time()


def fetch(
    url: str,
    *,
    rate_limit: float = DEFAULT_RATE_LIMIT_S,
    user_agent: str = DEFAULT_UA,
    use_cache: bool = True,
    timeout: int = 30,
) -> FetchResult:
    """Fetch a URL with rate limiting and SQLite caching.

    Returns a FetchResult with status, content_type and bytes body.
    """
    if use_cache:
        db = _init_cache()
        row = db.execute(
            "SELECT status, content_type, body, fetched_at, error FROM pages WHERE url=?",
            (url,),
        ).fetchone()
        db.close()
        if row is not None:
            status, ctype, body, fetched_at, err = row
            return FetchResult(
                url=url,
                status=status,
                content_type=ctype or "",
                body=body or b"",
                fetched_at=fetched_at or "",
                cached=True,
                error=err,
            )

    _polite_sleep(url, rate_limit)
    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "close",
        },
    )
    body = b""
    status = 0
    ctype = ""
    err: Optional[str] = None
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec - public OSINT scraping
            status = resp.status
            ctype = resp.headers.get("Content-Type", "")
            body = resp.read()
    except HTTPError as e:
        status = e.code
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
        try:
            body = e.read()
        except Exception:
            body = b""
        err = f"HTTPError {e.code}: {e.reason}"
    except URLError as e:
        err = f"URLError: {e.reason}"
    except Exception as e:  # pragma: no cover
        err = f"{type(e).__name__}: {e}"

    fetched_at = _utc_now_iso()
    if use_cache:
        db = _init_cache()
        db.execute(
            "INSERT OR REPLACE INTO pages (url, status, content_type, body, fetched_at, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (url, status, ctype, body, fetched_at, err),
        )
        db.commit()
        db.close()
    return FetchResult(
        url=url, status=status, content_type=ctype, body=body,
        fetched_at=fetched_at, cached=False, error=err,
    )


# ---------------------------------------------------------------------------
# PDF text extraction (cached)
# ---------------------------------------------------------------------------

def _pdf_to_text(body: bytes) -> str:
    """Extract text from PDF bytes. Tries pypdf, falls back to pymupdf."""
    if not body or not body.startswith(b"%PDF"):
        return ""
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(io.BytesIO(body))
        chunks = []
        for page in reader.pages:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(chunks).strip()
    except Exception:
        pass
    try:
        import pymupdf  # type: ignore

        doc = pymupdf.open(stream=body, filetype="pdf")
        chunks = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(chunks).strip()
    except Exception as e:
        return f"[pdf_extract_error: {e}]"


def fetch_pdf_text(url: str, *, rate_limit: float = DEFAULT_RATE_LIMIT_S,
                   user_agent: str = DEFAULT_UA, use_cache: bool = True) -> dict:
    """Fetch a PDF and return extracted text (cached separately)."""
    if use_cache:
        db = _init_cache()
        row = db.execute(
            "SELECT sha256, text, extracted_at FROM pdf_text WHERE url=?",
            (url,),
        ).fetchone()
        db.close()
        if row is not None:
            sha, text, extracted_at = row
            return {"url": url, "sha256": sha, "text": text or "",
                    "extracted_at": extracted_at, "cached": True}

    res = fetch(url, rate_limit=rate_limit, user_agent=user_agent, use_cache=use_cache)
    if res.error or not res.body:
        return {"url": url, "error": res.error or "empty body", "text": "",
                "status": res.status, "cached": False}
    if not res.body.startswith(b"%PDF") and "pdf" not in res.content_type.lower():
        return {"url": url, "error": f"not a PDF (content-type={res.content_type})",
                "text": "", "status": res.status, "cached": False}

    text = _pdf_to_text(res.body)
    sha = hashlib.sha256(res.body).hexdigest()
    extracted_at = _utc_now_iso()
    if use_cache:
        db = _init_cache()
        db.execute(
            "INSERT OR REPLACE INTO pdf_text (url, sha256, text, extracted_at) VALUES (?, ?, ?, ?)",
            (url, sha, text, extracted_at),
        )
        db.commit()
        db.close()
    return {"url": url, "sha256": sha, "text": text, "extracted_at": extracted_at,
            "status": res.status, "cached": False}


# ---------------------------------------------------------------------------
# CAAF parsers
# ---------------------------------------------------------------------------

# CAAF docket entry pattern in opinion term pages, e.g.
#   "U.S. v. Downum    24-0156/AR    Sep 30, 2025    86 MJ 200"
# In the underlying HTML the pieces appear as inline text; we parse with
# regex against the visible text.
CAAF_DOCKET_RE = re.compile(
    r"(U\.?S\.?\s+v\.?\s+[A-Za-z'\-\.\s,]+?)\s*(?:[\|\t]|\s{2,}|<[^>]+>)*\s*"
    r"(\d{2}-\d{4}\/(?:AR|AF|NA|MC|CG))\s*(?:[\|\t]|\s{2,}|<[^>]+>)*\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},\s+\d{4})"
    r"(?:\s*(?:[\|\t]|\s{2,}|<[^>]+>)*\s*(\d{2,3}\s*MJ\s*\d{1,4}))?",
    re.IGNORECASE,
)

# Daily Journal entry pattern: "No. 24-0237/NA. U.S. v. Eddie A. Tyson. CCA 202300083."
# Names contain periods (initials), so we look for "U.S. v." then non-greedy
# match up to the next " CCA " or another " No. " entry.
DAILY_JOURNAL_RE = re.compile(
    r"No\.?\s+(\d{2}-\d{4}\/(?:AR|AF|NA|MC|CG))\.?\s+"
    r"(U\.?S\.?\s+v\.?\s+.+?)\s*\.\s*"
    r"(?:CCA\s+([A-Za-z0-9-]+)|(?=No\.\s+\d{2}-\d{4}\/))",
    re.IGNORECASE,
)


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                  flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>|</p>|</tr>|</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#?\w+;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return text


def parse_caaf_term_page(html: str, term_year: str, term_url: str) -> list[dict]:
    """Parse a CAAF October Term opinions page (table-row layout) into rows."""
    out: list[dict] = []
    seen: set[str] = set()
    docket_pat = re.compile(r"(\d{2}-\d{4}/(?:AR|AF|NA|MC|CG))", re.IGNORECASE)
    href_pat = re.compile(r'href=["\']([^"\']+\.pdf)["\']', re.IGNORECASE)
    for tr_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        tr = tr_match.group(1)
        if not docket_pat.search(tr):
            continue
        # Capture PDF href before stripping tags
        href_match = href_pat.search(tr)
        opinion_url = urljoin(term_url, href_match.group(1)) if href_match else None

        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.DOTALL | re.IGNORECASE)
        if not cells:
            continue
        cells_text = []
        for c in cells:
            t = re.sub(r"<[^>]+>", " ", c)
            t = re.sub(r"&nbsp;", " ", t)
            t = re.sub(r"&amp;", "&", t)
            t = re.sub(r"\s+", " ", t).strip()
            cells_text.append(t)
        # Layout: case_name | "<docket> ( PDF )" | decision_date | citation
        case_name = cells_text[0].rstrip("*").strip().rstrip(",")
        docket_cell = cells_text[1] if len(cells_text) > 1 else ""
        decision_date = cells_text[2] if len(cells_text) > 2 else ""
        citation = cells_text[3] if len(cells_text) > 3 else ""
        d_match = docket_pat.search(docket_cell)
        if not d_match:
            continue
        docket = d_match.group(1).strip()
        if docket in seen:
            continue
        seen.add(docket)
        if not opinion_url and term_year:
            d_no_dash = re.sub(r"[^\d]", "", docket)[:6]
            opinion_url = f"{CAAF_BASE}/opinions/{term_year}OctTerm/{d_no_dash}.pdf"
        service = docket.rsplit("/", 1)[-1].upper()
        out.append({
            "court": "CAAF",
            "docket": docket,
            "case_name": case_name,
            "decision_date": decision_date,
            "citation": citation,
            "opinion_url": opinion_url,
            "service_court": CAAF_SERVICE_CODES.get(service),
            "term_url": term_url,
        })
    return out


def parse_caaf_daily_journal(html: str, journal_url: str) -> list[dict]:
    """Parse one CAAF monthly Daily Journal page into action records.

    Pages are loosely structured: a "Day, Month DD, YYYY" date heading
    introduces an action section heading (e.g. "Petitions for Grant of Review
    Filed"), which is followed by a run of "No. <docket>. U.S. v. <name>. CCA
    <num>." entries. We tokenize the flattened text and walk it.
    """
    text = _strip_html(html)
    text = re.sub(r"\s+", " ", text)
    out: list[dict] = []

    date_pat = re.compile(
        r"\b(?:Sun|Mon|Tues|Wednes|Thurs|Fri|Satur)?day,?\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    )
    section_phrases = [
        "Petitions for Grant of Review Filed",
        "Petitions for Grant of Review Denied",
        "Petitions for Grant of Review Granted",
        "Order Granting Petition for Review",
        "Order Denying Petition for Review",
        "Notice of Certificate for Review Filed",
        "Certificate for Review Filed",
        "Miscellaneous Docket",
        "Miscellaneous Pleadings",
        "Notices of Withdrawal",
        "Appeals - Summary Disposition",
    ]
    section_pat = re.compile(
        r"\b(" + "|".join(re.escape(p) for p in section_phrases) + r")\b",
        re.IGNORECASE,
    )

    # Build position index of dates and sections
    markers: list[tuple[int, str, str]] = []
    for m in date_pat.finditer(text):
        markers.append((m.start(), "date", m.group(0)))
    for m in section_pat.finditer(text):
        markers.append((m.start(), "section", m.group(1)))
    markers.sort()

    def lookup_context(pos: int) -> tuple[Optional[str], Optional[str]]:
        date = section = None
        for p, kind, val in markers:
            if p > pos:
                break
            if kind == "date":
                date = val
            elif kind == "section":
                section = val
        return date, section

    for m in DAILY_JOURNAL_RE.finditer(text):
        docket = m.group(1).strip()
        case_name = re.sub(r"\s+", " ", m.group(2)).strip()
        cca_no = (m.group(3) or "").strip()
        service = docket.rsplit("/", 1)[-1].upper()
        date, section = lookup_context(m.start())
        out.append({
            "court": "CAAF",
            "docket": docket,
            "case_name": case_name,
            "cca_number": cca_no,
            "service_court": CAAF_SERVICE_CODES.get(service),
            "action": section,
            "action_date": date,
            "journal_url": journal_url,
        })
    return out


# ---------------------------------------------------------------------------
# AFCCA parser
# ---------------------------------------------------------------------------

# Opinion link in AFCCA opinions index: <a href="afcca_opinions/cp/smith_-_40437_f_rev_u_2636159.pdf">United States v. Smith</a>
AFCCA_LINK_RE = re.compile(
    r'href=["\'](afcca_opinions/cp/[^"\']+\.pdf)["\'][^>]*>([^<]+)</a>',
    re.IGNORECASE,
)
# AFCCA filename docket extractors. Standard cases:
#   smith_-_40437_f_rev_u_2636159.pdf      -> 40437
#   gill_-_s32822_pc1_2793127.pdf          -> S32822
# Misc dockets:
#   in_re_dombrowski_-_misc__dkt__no__2025-16_-_order_2657979.pdf -> 2025-16
AFCCA_DOCKET_FROM_FN_RE = re.compile(
    r"(?:misc__dkt__no__|misc_dkt_no_|-_?)([Ss]?\d{4,6}|\d{4}-\d{2,3})(?:_|\.|-)",
    re.IGNORECASE,
)


def parse_afcca_opinions_page(html: str, page_url: str) -> list[dict]:
    """Parse the AFCCA opinions list. Returns rows with case_name, docket, opinion_url."""
    out: list[dict] = []
    seen = set()
    for m in AFCCA_LINK_RE.finditer(html):
        rel = m.group(1)
        case_name = re.sub(r"\s+", " ", m.group(2)).strip()
        url = urljoin(page_url, rel)
        fn = rel.rsplit("/", 1)[-1]
        docket_m = AFCCA_DOCKET_FROM_FN_RE.search(fn)
        docket = docket_m.group(1).upper() if docket_m else ""
        if url in seen:
            continue
        seen.add(url)
        out.append({
            "court": "AFCCA",
            "docket": docket,
            "case_name": case_name,
            "opinion_url": url,
            "filename": fn,
        })
    return out


# ---------------------------------------------------------------------------
# ACCA parser
# ---------------------------------------------------------------------------

# Anchor tag pointing to /ACCALibrary/cases/opinion/file/<id>
ACCA_LINK_RE = re.compile(
    r'href=["\']([^"\']*ACCALibrary/cases/opinion/file/(\d+))["\'][^>]*>'
    r'([^<]+)</a>',
    re.IGNORECASE,
)


def parse_acca_opinions_page(html: str, page_url: str) -> list[dict]:
    out: list[dict] = []
    seen = set()
    for m in ACCA_LINK_RE.finditer(html):
        rel = m.group(1)
        opinion_id = m.group(2)
        case_name = re.sub(r"\s+", " ", m.group(3)).strip()
        url = urljoin(page_url, rel)
        if opinion_id in seen:
            continue
        seen.add(opinion_id)
        out.append({
            "court": "ACCA",
            "docket": opinion_id,  # ACCA uses internal numeric IDs in the URL
            "case_name": case_name,
            "opinion_url": url,
        })
    return out


# ---------------------------------------------------------------------------
# Counsel-name extraction from opinion text (works on PDF-extracted text)
# ---------------------------------------------------------------------------

# Common headings that introduce counsel blocks in military-justice opinions.
COUNSEL_HEADINGS = [
    "For Appellant", "For Petitioner", "For the Appellant",
    "For Appellee", "For the Appellee", "For the United States",
    "Counsel for Appellant", "Counsel for Appellee",
    "Civilian Counsel", "Civilian Defense Counsel",
    "Appellate Defense Counsel", "Appellate Government Counsel",
    "Military Defense Counsel", "Military Counsel",
]


def extract_counsel_blocks(text: str) -> dict:
    """Find counsel/attorney names from extracted opinion text.

    Returns dict with keys: appellant_counsel, government_counsel, panel,
    decision_date, disposition. Best-effort string extraction.
    """
    blocks: dict[str, list[str]] = {}
    if not text:
        return blocks

    # Find each heading and capture the chunk until the next heading or blank
    indices = []
    for h in COUNSEL_HEADINGS:
        for m in re.finditer(rf"\b{re.escape(h)}\b", text, re.IGNORECASE):
            indices.append((m.start(), h))
    indices.sort()

    for i, (pos, heading) in enumerate(indices):
        end = indices[i + 1][0] if i + 1 < len(indices) else min(pos + 800, len(text))
        chunk = text[pos:end]
        # Strip the heading prefix
        chunk = re.sub(rf"^[^\n]*{re.escape(heading)}[^\n]*[:\-]?\s*", "", chunk,
                       count=1, flags=re.IGNORECASE)
        # Names: heuristic — capture title-cased word groups before a comma
        # or "Esq."/"Captain"/"Colonel" etc.
        names = []
        for m in re.finditer(
            r"((?:[A-Z][a-z]+\.?\s+)?(?:[A-Z]\.?\s*)?[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+(?:Jr|Sr|II|III|IV)\.?)?)",
            chunk[:600],
        ):
            n = m.group(1).strip()
            if (n.lower() not in {"for appellant", "for appellee"}
                    and len(n) >= 5 and " " in n):
                names.append(n)
        if names:
            key = heading.lower().replace(" ", "_")
            blocks.setdefault(key, []).extend(dict.fromkeys(names))  # de-dup

    # Disposition heuristics
    disposition = None
    for pat in [
        r"the\s+findings?\s+and\s+sentence\s+are\s+(AFFIRMED|REVERSED|SET ASIDE)",
        r"the\s+(?:judgment|decision)\s+(?:of\s+the\s+\w+)?\s+is\s+(AFFIRMED|REVERSED|VACATED|REMANDED)",
        r"\b(AFFIRMED|REVERSED|VACATED|REMANDED|DISMISSED)\b\.?\s*$",
    ]:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            disposition = m.group(1).upper()
            break

    # Decision date
    date_m = re.search(
        r"(?:Decided|Filed|Date\s+Decided)[:\s]+"
        r"((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4})",
        text, re.IGNORECASE,
    )
    decision_date = date_m.group(1) if date_m else None

    # Panel — judges' names usually listed near the disposition
    panel = []
    panel_m = re.search(
        r"(?:Before|Senior\s+Judge|Judge[s]?)\s+([A-Z][A-Z]+(?:,?\s+[A-Z][A-Z]+)*)",
        text,
    )
    if panel_m:
        panel = [n.strip() for n in re.split(r",\s*|\s+and\s+", panel_m.group(1))]

    return {
        "counsel": blocks,
        "disposition": disposition,
        "decision_date": decision_date,
        "panel": panel,
    }


# ---------------------------------------------------------------------------
# Subcommand: caaf-dockets
# ---------------------------------------------------------------------------

def cmd_caaf_dockets(args) -> int:
    term = args.term
    # Accept "2024" or "2024OctTerm" or "current"
    if term.lower() in {"current", "now"}:
        url = f"{CAAF_BASE}/opinions/CurrentOpins.htm"
        term_year = ""
    else:
        term_year = re.sub(r"[^\d]", "", term)[:4]
        url = f"{CAAF_BASE}/opinions/{term_year}OctTerm.htm"

    res = fetch(url, rate_limit=args.rate_limit, user_agent=args.user_agent,
                use_cache=not args.no_cache)
    if res.error or res.status >= 400:
        payload = {"court": "CAAF", "term": term, "url": url,
                   "status": res.status, "error": res.error,
                   "results": []}
        write_output(payload, args, summary=f"CAAF term {term}: error {res.status}")
        if not getattr(args, "output", None):
            print(json.dumps(payload, indent=2))
        return 1

    rows = parse_caaf_term_page(res.body.decode("utf-8", errors="replace"),
                                term_year, url)
    # Persist to docket_index cache
    db = _init_cache()
    now = _utc_now_iso()
    for r in rows:
        db.execute(
            "INSERT OR REPLACE INTO docket_index "
            "(court, docket, case_name, cca_number, decision_date, citation, "
            " opinion_url, term, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("CAAF", r["docket"], r["case_name"], r.get("cca_number", ""),
             r.get("decision_date", ""), r.get("citation", ""),
             r.get("opinion_url", ""), term_year, now),
        )
    db.commit()
    db.close()

    log_search(f"caaf_term:{term}", "military_justice", len(rows))
    payload = {"court": "CAAF", "term": term, "url": url,
               "result_count": len(rows), "results": rows}
    if write_output(payload, args, summary=f"CAAF {term}: {len(rows)} opinions"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: caaf-opinion
# ---------------------------------------------------------------------------

def cmd_caaf_opinion(args) -> int:
    docket = args.docket.strip().upper()
    # Parse year prefix from docket number
    m = re.match(r"(\d{2})-(\d{4})/?([A-Z]{2})?", docket)
    if not m:
        print(f"ERROR: could not parse docket '{docket}'", file=sys.stderr)
        return 2
    yy = m.group(1)
    no = m.group(2)
    # Determine term year: "24-0156" was decided in October 2024 Term => 2024OctTerm
    term_year = f"20{yy}"
    candidate_urls = [
        f"{CAAF_BASE}/opinions/{term_year}OctTerm/{yy}{no}.pdf",
        # Some opinions are filed in the *prior* term page (filed late). Try
        # the previous year too.
        f"{CAAF_BASE}/opinions/{int(term_year) - 1}OctTerm/{yy}{no}.pdf",
    ]

    result: dict[str, Any] = {"court": "CAAF", "docket": docket,
                              "tried_urls": candidate_urls}
    found_url = None
    pdf_data: dict[str, Any] = {}
    for url in candidate_urls:
        pdf_data = fetch_pdf_text(url, rate_limit=args.rate_limit,
                                  user_agent=args.user_agent,
                                  use_cache=not args.no_cache)
        if pdf_data.get("text"):
            found_url = url
            break

    if not found_url:
        result["error"] = "PDF not located at expected term URLs. Try --url <override>."
        write_output(result, args, summary=f"CAAF {docket}: not found")
        if not getattr(args, "output", None):
            print(json.dumps(result, indent=2))
        return 1

    text = pdf_data["text"]
    metadata = extract_counsel_blocks(text)
    result.update({
        "opinion_url": found_url,
        "decision_date": metadata.get("decision_date"),
        "disposition": metadata.get("disposition"),
        "panel": metadata.get("panel"),
        "counsel": metadata.get("counsel"),
        "text_length": len(text),
        "text_preview": text[:1500],
    })
    if args.full_text:
        result["full_text"] = text

    log_search(f"caaf_op:{docket}", "military_justice", 1)
    if write_output(result, args, summary=f"CAAF {docket}: {len(text):,} chars"):
        return 0
    print(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: acca-search / afcca-search / nmcca-search / cgcca-search
# ---------------------------------------------------------------------------

def _list_afcca_year(year: int, args) -> list[dict]:
    """Fetch the AFCCA opinions index page (covers all years)."""
    url = f"{AFCCA_BASE}/opinions.html"
    res = fetch(url, rate_limit=args.rate_limit, user_agent=args.user_agent,
                use_cache=not args.no_cache)
    if res.error or res.status >= 400:
        return []
    rows = parse_afcca_opinions_page(res.body.decode("utf-8", errors="replace"), url)
    return rows


def _list_acca_opinions(args, opinion_type: str = "OC") -> list[dict]:
    """Fetch ACCA opinion lists. opinion_type ∈ {OC, MO, SFA, SD}."""
    url = f"{ACCA_BASE}/ACCALibrary/cases/opinions/{opinion_type}"
    res = fetch(url, rate_limit=args.rate_limit, user_agent=args.user_agent,
                use_cache=not args.no_cache)
    if res.error or res.status >= 400:
        return []
    rows = parse_acca_opinions_page(res.body.decode("utf-8", errors="replace"), url)
    return rows


def cmd_afcca_search(args) -> int:
    rows = _list_afcca_year(0, args)
    q = args.query.lower() if args.query else ""
    if q:
        rows = [r for r in rows if q in r["case_name"].lower()
                or q in r["docket"].lower()]
    log_search(f"afcca:{args.query or ''}", "military_justice", len(rows))
    payload = {"court": "AFCCA", "query": args.query, "result_count": len(rows),
               "results": rows[: args.limit]}
    if write_output(payload, args, summary=f"AFCCA '{args.query}': {len(rows)}"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


def cmd_acca_search(args) -> int:
    all_rows: list[dict] = []
    for opt in ("OC", "MO", "SFA", "SD"):
        all_rows.extend(_list_acca_opinions(args, opt))
    q = args.query.lower() if args.query else ""
    if q:
        all_rows = [r for r in all_rows if q in r["case_name"].lower()
                    or q in r["docket"]]
    log_search(f"acca:{args.query or ''}", "military_justice", len(all_rows))
    payload = {"court": "ACCA", "query": args.query,
               "result_count": len(all_rows), "results": all_rows[: args.limit]}
    if write_output(payload, args, summary=f"ACCA '{args.query}': {len(all_rows)}"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


def cmd_nmcca_search(args) -> int:
    """NMCCA: server-rendered search form. Posts to opinions/ with form fields.

    Form fields confirmed during probe: "Parties", "Docket Number",
    start_date, end_date, "Type". Form submission method is HTTP POST and
    returns server-rendered HTML.
    """
    url = f"{NMCCA_BASE}/about/organization/ojag/code-05/nmcca/opinions/"
    # NMCCA uses Sitecore-style POST form. We attempt a GET first to capture
    # the index page; results listing requires cookies + form POST. We
    # document the limitation rather than fake results.
    res = fetch(url, rate_limit=args.rate_limit, user_agent=args.user_agent,
                use_cache=not args.no_cache)
    note = (
        "NMCCA opinions search uses a server-rendered POST form (Sitecore). "
        "This tool currently fetches the index page only. Use --url to pass "
        "a captured search-result URL, or use the cross-court `attorney`/`search` "
        "commands which scan PDF opinion text where reachable."
    )
    payload = {
        "court": "NMCCA",
        "query": args.query,
        "url": url,
        "status": res.status,
        "limitation": note,
        "result_count": 0,
        "results": [],
    }
    log_search(f"nmcca:{args.query or ''}", "military_justice", 0)
    if write_output(payload, args,
                    summary=f"NMCCA '{args.query}': form-POST not supported"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


def cmd_cgcca_search(args) -> int:
    """CGCCA: site returns 403 to bare HTTP UAs.

    We attempt the official site, then fall back to FindLaw mirror.
    """
    primary = f"{CGCCA_BASE}/Resources/Legal/Court-of-Criminal-Appeals/CGCCA-Opinions/"
    res = fetch(primary, rate_limit=args.rate_limit,
                user_agent=args.user_agent, use_cache=not args.no_cache)
    rows: list[dict] = []
    note = None
    if res.status == 403 or res.error:
        note = (
            "uscg.mil returns 403 to non-browser User-Agents (Akamai/CDN). "
            "Use --user-agent override with a real browser UA, or query the "
            "FindLaw mirror at caselaw.findlaw.com/court/u-s-coa-gua-crt-cri-app."
        )
    else:
        # Attempt to extract media.defense.gov PDF links
        body = res.body.decode("utf-8", errors="replace")
        for m in re.finditer(
            r'href=["\'](https?://media\.defense\.gov/[^"\']+\.[Pp][Dd][Ff])["\']'
            r'[^>]*>([^<]+)</a>', body,
        ):
            url = m.group(1)
            label = re.sub(r"\s+", " ", m.group(2)).strip()
            rows.append({"court": "CGCCA", "docket": "",
                         "case_name": label, "opinion_url": url})

    q = args.query.lower() if args.query else ""
    if q:
        rows = [r for r in rows if q in r["case_name"].lower()]

    log_search(f"cgcca:{args.query or ''}", "military_justice", len(rows))
    payload = {"court": "CGCCA", "query": args.query, "url": primary,
               "status": res.status, "limitation": note,
               "result_count": len(rows), "results": rows[: args.limit]}
    if write_output(payload, args, summary=f"CGCCA '{args.query}': {len(rows)}"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: search (cross-court name/keyword search across cached indices)
# ---------------------------------------------------------------------------

def _persist_rows(rows: Iterable[dict], court: str, term: str = "") -> None:
    """Insert/replace rows into the docket_index cache."""
    db = _init_cache()
    now = _utc_now_iso()
    for r in rows:
        db.execute(
            "INSERT OR REPLACE INTO docket_index "
            "(court, docket, case_name, cca_number, decision_date, citation, "
            " opinion_url, term, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (court, r.get("docket", ""), r.get("case_name", ""),
             r.get("cca_number", ""), r.get("decision_date", ""),
             r.get("citation", ""), r.get("opinion_url", ""),
             term or r.get("term", ""), now),
        )
    db.commit()
    db.close()


def _refresh_indices(args, courts: tuple[str, ...]) -> None:
    """Make sure we have at least the recent index pages cached."""
    if "AFCCA" in courts:
        rows = _list_afcca_year(0, args)
        _persist_rows(rows, "AFCCA")
    if "ACCA" in courts:
        for opt in ("OC", "MO", "SFA", "SD"):
            rows = _list_acca_opinions(args, opt)
            _persist_rows(rows, "ACCA", term=opt)
    if "CAAF" in courts:
        # Pull current term + last two terms
        this_year = datetime.now(timezone.utc).year
        for y in (this_year, this_year - 1, this_year - 2):
            url = f"{CAAF_BASE}/opinions/{y}OctTerm.htm"
            res = fetch(url, rate_limit=args.rate_limit,
                        user_agent=args.user_agent,
                        use_cache=not args.no_cache)
            if res.status < 400 and not res.error:
                rows = parse_caaf_term_page(
                    res.body.decode("utf-8", errors="replace"), str(y), url)
                db = _init_cache()
                now = _utc_now_iso()
                for r in rows:
                    db.execute(
                        "INSERT OR REPLACE INTO docket_index "
                        "(court, docket, case_name, cca_number, decision_date, "
                        " citation, opinion_url, term, indexed_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        ("CAAF", r["docket"], r["case_name"], "",
                         r.get("decision_date", ""), r.get("citation", ""),
                         r.get("opinion_url", ""), str(y), now),
                    )
                db.commit()
                db.close()
        # Also Daily Journal for current + last year
        for y in (this_year, this_year - 1):
            for mon in ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"):
                url = f"{CAAF_BASE}/journal/{y}Jrnl/{y}{mon}.htm"
                res = fetch(url, rate_limit=args.rate_limit,
                            user_agent=args.user_agent,
                            use_cache=not args.no_cache)
                if res.status < 400 and not res.error and res.body:
                    rows = parse_caaf_daily_journal(
                        res.body.decode("utf-8", errors="replace"), url)
                    db = _init_cache()
                    now = _utc_now_iso()
                    for r in rows:
                        db.execute(
                            "INSERT OR REPLACE INTO docket_index "
                            "(court, docket, case_name, cca_number, decision_date, "
                            " citation, opinion_url, term, indexed_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            ("CAAF_JRNL", r["docket"], r["case_name"],
                             r.get("cca_number", ""), r.get("action_date", ""),
                             "", r.get("journal_url", ""), str(y), now),
                        )
                    db.commit()
                    db.close()


def cmd_search(args) -> int:
    courts = tuple(c.upper() for c in (args.courts.split(",") if args.courts
                                       else COURTS))
    if args.refresh:
        _refresh_indices(args, courts)

    db = _init_cache()
    q = f"%{args.query.lower()}%"
    sql = (
        "SELECT court, docket, case_name, cca_number, decision_date, citation, "
        " opinion_url, term FROM docket_index "
        "WHERE (lower(case_name) LIKE ? OR lower(docket) LIKE ? "
        "       OR lower(cca_number) LIKE ?)"
    )
    params: list[Any] = [q, q, q]
    if courts and "ALL" not in courts:
        court_set = set()
        for c in courts:
            court_set.add(c)
            if c == "CAAF":
                court_set.add("CAAF_JRNL")
        placeholders = ",".join("?" * len(court_set))
        sql += f" AND court IN ({placeholders})"
        params.extend(sorted(court_set))
    sql += " ORDER BY decision_date DESC LIMIT ?"
    params.append(args.limit)
    rows = [dict(zip([
        "court", "docket", "case_name", "cca_number", "decision_date",
        "citation", "opinion_url", "term"
    ], r)) for r in db.execute(sql, params).fetchall()]
    db.close()

    # Also search live ACCA / AFCCA opinions index by free text (their lists are
    # small enough). Use the cached _list_* helpers.
    extra: list[dict] = []
    if "AFCCA" in courts:
        for r in _list_afcca_year(0, args):
            if (args.query.lower() in r["case_name"].lower()
                    or args.query.lower() in r["docket"].lower()):
                extra.append(r)
    if "ACCA" in courts:
        for opt in ("OC", "MO", "SFA", "SD"):
            for r in _list_acca_opinions(args, opt):
                if args.query.lower() in r["case_name"].lower():
                    extra.append(r)

    # de-dup by (court, docket, opinion_url)
    seen = {(r["court"], r.get("docket", ""), r.get("opinion_url", ""))
            for r in rows}
    for r in extra:
        key = (r["court"], r.get("docket", ""), r.get("opinion_url", ""))
        if key not in seen:
            rows.append(r)
            seen.add(key)

    log_search(f"mj_search:{args.query}", "military_justice", len(rows))
    payload = {"query": args.query, "courts": list(courts),
               "result_count": len(rows), "results": rows[: args.limit]}
    if write_output(payload, args,
                    summary=f"MJ search '{args.query}': {len(rows)}"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: attorney (the killer feature)
# ---------------------------------------------------------------------------

def cmd_attorney(args) -> int:
    """Find every reachable opinion where <NAME> appears as counsel.

    Strategy:
      1. Refresh recent indices for all 5 courts (cached).
      2. Scan PDF text for every reachable opinion, looking for the name.
      3. For each hit, extract the surrounding counsel block to confirm.
    """
    courts = tuple(c.upper() for c in (args.courts.split(",") if args.courts
                                       else COURTS))
    if args.refresh or not args.skip_refresh:
        _refresh_indices(args, courts)

    db = _init_cache()
    # Prioritize courts with full-text opinion PDFs. CAAF_JRNL rows have HTML
    # journal_url, not opinion text, so skip them in attorney scans.
    sql = (
        "SELECT court, docket, case_name, opinion_url FROM docket_index "
        "WHERE opinion_url IS NOT NULL AND opinion_url != '' "
        "AND court IN ('CAAF','AFCCA','ACCA') "
        "ORDER BY CASE court WHEN 'CAAF' THEN 1 WHEN 'AFCCA' THEN 2 "
        "  WHEN 'ACCA' THEN 3 ELSE 9 END, decision_date DESC"
    )
    rows = db.execute(sql).fetchall()
    db.close()

    # Also pull AFCCA / ACCA index URLs live (in case the cache is empty)
    if "AFCCA" in courts and not any(r[0] == "AFCCA" for r in rows):
        rows.extend(("AFCCA", r["docket"], r["case_name"], r["opinion_url"])
                    for r in _list_afcca_year(0, args))

    name = args.name.strip()
    name_lower = name.lower()
    hits: list[dict] = []
    pdfs_scanned = 0
    pdfs_skipped = 0
    pdf_limit = args.pdf_limit

    # ACCA URLs end in /file/<id> but return PDF content; treat them as PDFs.
    def _is_pdf_url(u: str) -> bool:
        if not u:
            return False
        ul = u.lower()
        return ul.endswith(".pdf") or "/acca" in ul.lower() or "ACCALibrary" in u

    for court, docket, case_name, opinion_url in rows:
        if pdfs_scanned >= pdf_limit:
            pdfs_skipped += 1
            continue
        if not _is_pdf_url(opinion_url):
            continue
        pdf_data = fetch_pdf_text(
            opinion_url, rate_limit=args.rate_limit,
            user_agent=args.user_agent, use_cache=not args.no_cache,
        )
        pdfs_scanned += 1
        text = pdf_data.get("text", "")
        if not text:
            continue
        if name_lower not in text.lower():
            continue
        meta = extract_counsel_blocks(text)
        # Confirm name appears in a counsel block, not just a passing reference
        in_counsel = False
        for k, names in (meta.get("counsel") or {}).items():
            for n in names:
                if name_lower in n.lower():
                    in_counsel = True
                    break
            if in_counsel:
                break
        # Build context snippet around the name
        idx = text.lower().find(name_lower)
        context = text[max(0, idx - 200): idx + 200] if idx >= 0 else ""
        hits.append({
            "court": court,
            "docket": docket,
            "case_name": case_name,
            "opinion_url": opinion_url,
            "name_in_counsel_block": in_counsel,
            "decision_date": meta.get("decision_date"),
            "disposition": meta.get("disposition"),
            "context_snippet": re.sub(r"\s+", " ", context).strip(),
        })

    log_search(f"mj_atty:{name}", "military_justice", len(hits))
    payload = {
        "attorney": name,
        "courts": list(courts),
        "pdfs_scanned": pdfs_scanned,
        "pdfs_skipped_over_limit": pdfs_skipped,
        "hit_count": len(hits),
        "results": hits,
    }
    if write_output(payload, args,
                    summary=f"MJ attorney '{name}': {len(hits)} hits "
                            f"({pdfs_scanned} PDFs scanned)"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: case-detail
# ---------------------------------------------------------------------------

def cmd_case_detail(args) -> int:
    docket = args.docket.strip()
    db = _init_cache()
    rows = db.execute(
        "SELECT court, docket, case_name, cca_number, decision_date, citation, "
        " opinion_url, term FROM docket_index WHERE docket=? OR cca_number=?",
        (docket, docket),
    ).fetchall()
    db.close()
    matches = [dict(zip([
        "court", "docket", "case_name", "cca_number", "decision_date",
        "citation", "opinion_url", "term"
    ], r)) for r in rows]

    detail = None
    # Prefer a match with a PDF opinion URL over a Daily Journal stub
    pdf_match = next(
        (m for m in matches
         if (m.get("opinion_url") or "").lower().endswith(".pdf")),
        None,
    )
    if pdf_match:
        pdf_data = fetch_pdf_text(
            pdf_match["opinion_url"], rate_limit=args.rate_limit,
            user_agent=args.user_agent, use_cache=not args.no_cache,
        )
        text = pdf_data.get("text", "")
        meta = extract_counsel_blocks(text)
        detail = {
            "opinion_url": pdf_match["opinion_url"],
            "decision_date": meta.get("decision_date") or pdf_match.get("decision_date"),
            "disposition": meta.get("disposition"),
            "panel": meta.get("panel"),
            "counsel": meta.get("counsel"),
            "text_length": len(text),
            "text_preview": text[:1500],
        }

    payload = {"docket": docket, "matches": matches, "detail": detail}
    log_search(f"mj_case:{docket}", "military_justice", len(matches))
    if write_output(payload, args,
                    summary=f"MJ case {docket}: {len(matches)} index hits"):
        return 0
    print(json.dumps(payload, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI assembly
# ---------------------------------------------------------------------------

def _add_common(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)
    parser.add_argument("--rate-limit", type=float, default=DEFAULT_RATE_LIMIT_S,
                        help="Seconds between requests to the same host (default 1.0)")
    parser.add_argument("--user-agent", default=DEFAULT_UA,
                        help="HTTP User-Agent (override for sites that block bots)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Bypass the SQLite cache (always re-fetch)")
    parser.add_argument("--limit", type=int, default=50,
                        help="Maximum results to return (default 50)")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Military justice appellate court query tool — CAAF + ACCA + NMCCA + "
            "AFCCA + CGCCA. Some sites (CGCCA, NMCCA) restrict programmatic "
            "access; see --help for limitations."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search",
                              help="Cross-court keyword search (uses cached indices).")
    p_search.add_argument("query")
    p_search.add_argument("--courts",
                          help="Comma-separated subset (CAAF,ACCA,NMCCA,AFCCA,CGCCA)")
    p_search.add_argument("--refresh", action="store_true",
                          help="Re-fetch and re-parse index pages before searching")
    _add_common(p_search)
    p_search.set_defaults(func=cmd_search)

    p_caaf_d = sub.add_parser("caaf-dockets",
                              help="Fetch CAAF October Term opinion index for a year.")
    p_caaf_d.add_argument("term",
                          help="Term year (e.g. 2024) or 'current'")
    _add_common(p_caaf_d)
    p_caaf_d.set_defaults(func=cmd_caaf_dockets)

    p_caaf_o = sub.add_parser("caaf-opinion",
                              help="Fetch CAAF opinion PDF and extract metadata.")
    p_caaf_o.add_argument("docket", help="CAAF docket number e.g. 24-0156/AR")
    p_caaf_o.add_argument("--full-text", action="store_true",
                          help="Include full opinion text in JSON output")
    _add_common(p_caaf_o)
    p_caaf_o.set_defaults(func=cmd_caaf_opinion)

    p_acca = sub.add_parser("acca-search", help="Search ACCA (Army) opinion lists.")
    p_acca.add_argument("query", nargs="?", default="")
    _add_common(p_acca)
    p_acca.set_defaults(func=cmd_acca_search)

    p_afcca = sub.add_parser("afcca-search",
                             help="Search AFCCA (Air Force) opinion list.")
    p_afcca.add_argument("query", nargs="?", default="")
    _add_common(p_afcca)
    p_afcca.set_defaults(func=cmd_afcca_search)

    p_nmcca = sub.add_parser("nmcca-search",
                             help="Probe NMCCA opinions index (form-POST limitation).")
    p_nmcca.add_argument("query", nargs="?", default="")
    _add_common(p_nmcca)
    p_nmcca.set_defaults(func=cmd_nmcca_search)

    p_cgcca = sub.add_parser("cgcca-search",
                             help="Probe CGCCA opinions (often 403 from CDN).")
    p_cgcca.add_argument("query", nargs="?", default="")
    _add_common(p_cgcca)
    p_cgcca.set_defaults(func=cmd_cgcca_search)

    p_atty = sub.add_parser("attorney",
                            help="Find every opinion where <NAME> appears as counsel.")
    p_atty.add_argument("name")
    p_atty.add_argument("--courts",
                        help="Comma-separated subset (CAAF,ACCA,NMCCA,AFCCA,CGCCA)")
    p_atty.add_argument("--refresh", action="store_true",
                        help="Re-fetch indices before scanning")
    p_atty.add_argument("--skip-refresh", action="store_true",
                        help="Skip the index-refresh step (use cached indices only)")
    p_atty.add_argument("--pdf-limit", type=int, default=200,
                        help="Maximum number of PDFs to scan (default 200)")
    _add_common(p_atty)
    p_atty.set_defaults(func=cmd_attorney)

    p_case = sub.add_parser("case-detail",
                            help="Look up one docket across cached indices and "
                                 "extract counsel/panel/disposition.")
    p_case.add_argument("docket",
                        help="Docket number (CAAF format e.g. 24-0156/AR or "
                             "service CCA number)")
    _add_common(p_case)
    p_case.set_defaults(func=cmd_case_detail)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
