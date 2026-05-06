#!/usr/bin/env python3
"""
Epstein document catalog — Stages 1-2 of cosmic-toasting-moore plan.

Stage 1: Walk all local Epstein corpora, extract metadata into a unified
doc_refs table in a working SQLite DB.

Stage 2: Apply rule-based classification (7 rule families) and write results
to the classifications table with per-rule provenance.

Usage:
    uv run python tools/catalog_epstein_docs.py ingest --workdir $WORKDIR
    uv run python tools/catalog_epstein_docs.py classify --workdir $WORKDIR
    uv run python tools/catalog_epstein_docs.py stats --workdir $WORKDIR

The working DB is written to $WORKDIR/catalog.db. It is an intermediate
artifact, not meant to live in the repo — snapshot into a report and discard.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

# --- Paths ----------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS = REPO_ROOT / "datasets"

CORPUS_PATHS = {
    "doj_vol11": Path.home() / "projects/epstein-docs/output/documents.db",
    "lmsband": DATASETS / "lmsband_epstein_files.db",
    "unified": DATASETS / "unified_epstein.db",
    "epstein_20k": DATASETS / "epstein_files_20k.db",
    "doc_explorer": DATASETS / "Epstein-doc-explorer/document_analysis.db",
    "epstein_exposed": DATASETS / "epstein_exposed.db",
}

LOOSE_DIRS = {
    "epstein_archive": DATASETS / "epstein-archive/data",
    "epstein_emails_hf": DATASETS / "epstein-emails-hf",
    "ds09_extracted": DATASETS / "epstein_files_ds09_extracted",
    "epstractor_sample": DATASETS / "epstractor-sample",
}

LOOSE_PDFS_AT_ROOT = [
    DATASETS / "EFTA00190141.pdf",
    DATASETS / "EFTA00198118.pdf",
    DATASETS / "EFTA00300480.pdf",
    DATASETS / "EFTA01091533.pdf",
    DATASETS / "EFTA01322916.pdf",
]

TAXONOMY_PATH = REPO_ROOT / "investigations/epstein/document_taxonomy.yaml"


# --- Schema ---------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS doc_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    corpus TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    filename TEXT,
    source_path TEXT,
    dataset_num INTEGER,
    source_prefix TEXT,
    existing_category TEXT,
    file_ext TEXT,
    page_count INTEGER,
    char_count INTEGER,
    date_earliest TEXT,
    date_latest TEXT,
    content_sample TEXT,    -- first ~2KB of text (lowercased) for rule #7 content scan
    UNIQUE(corpus, doc_id)
);
CREATE INDEX IF NOT EXISTS idx_doc_refs_corpus ON doc_refs(corpus);
CREATE INDEX IF NOT EXISTS idx_doc_refs_filename ON doc_refs(filename);

CREATE TABLE IF NOT EXISTS classifications (
    doc_ref_id INTEGER PRIMARY KEY REFERENCES doc_refs(id),
    axis1 TEXT NOT NULL DEFAULT 'unknown',
    axis2 TEXT NOT NULL DEFAULT 'unknown',
    axis3 TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL NOT NULL DEFAULT 0.0,
    rules_fired TEXT             -- JSON array of rule names that fired
);
CREATE INDEX IF NOT EXISTS idx_cls_axis1 ON classifications(axis1);
CREATE INDEX IF NOT EXISTS idx_cls_axis2 ON classifications(axis2);
CREATE INDEX IF NOT EXISTS idx_cls_axis3 ON classifications(axis3);

CREATE TABLE IF NOT EXISTS loose_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    file_ext TEXT,
    size_bytes INTEGER,
    UNIQUE(group_name, rel_path)
);

CREATE TABLE IF NOT EXISTS run_log (
    stage TEXT,
    corpus TEXT,
    rows INTEGER,
    notes TEXT,
    ts TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


# --- Helpers --------------------------------------------------------------


def open_work(workdir: Path) -> sqlite3.Connection:
    workdir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(workdir / "catalog.db")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def log(conn: sqlite3.Connection, stage: str, corpus: str, rows: int, notes: str = "") -> None:
    conn.execute(
        "INSERT INTO run_log(stage, corpus, rows, notes) VALUES (?, ?, ?, ?)",
        (stage, corpus, rows, notes),
    )
    conn.commit()
    print(f"[{stage}] {corpus}: {rows} rows {notes}", flush=True)


def batched(it: Iterable, n: int):
    batch = []
    for x in it:
        batch.append(x)
        if len(batch) >= n:
            yield batch
            batch = []
    if batch:
        yield batch


def file_ext(name: str | None) -> str | None:
    if not name:
        return None
    ext = Path(name).suffix.lower().lstrip(".")
    return ext or None


# --- Stage 1: ingest ------------------------------------------------------


def ingest_doj_vol11(work: sqlite3.Connection) -> None:
    db_path = CORPUS_PATHS["doj_vol11"]
    if not db_path.exists():
        log(work, "ingest", "doj_vol11", 0, f"missing: {db_path}")
        return
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = src.execute(
        "SELECT bates_id, pdf_path, page_count, word_count, extracted_dates, "
        "SUBSTR(ocr_text, 1, 2048) FROM documents"
    )
    rows = 0
    for chunk in batched(cur, 5000):
        work.executemany(
            """INSERT OR IGNORE INTO doc_refs
               (corpus, doc_id, filename, source_path, page_count, char_count,
                date_earliest, date_latest, file_ext, content_sample)
               VALUES ('doj_vol11', ?, ?, ?, ?, ?, ?, ?, 'pdf', ?)""",
            [
                (
                    bates,
                    Path(path).name if path else None,
                    path,
                    pc,
                    wc,
                    _first_date(dates),
                    _last_date(dates),
                    (sample or "").lower(),
                )
                for (bates, path, pc, wc, dates, sample) in chunk
            ],
        )
        rows += len(chunk)
        work.commit()
    src.close()
    log(work, "ingest", "doj_vol11", rows)


def _first_date(dates_json: str | None) -> str | None:
    if not dates_json:
        return None
    try:
        arr = json.loads(dates_json)
        return sorted(arr)[0] if arr else None
    except Exception:
        return None


def _last_date(dates_json: str | None) -> str | None:
    if not dates_json:
        return None
    try:
        arr = json.loads(dates_json)
        return sorted(arr)[-1] if arr else None
    except Exception:
        return None


def ingest_lmsband(work: sqlite3.Connection) -> None:
    db_path = CORPUS_PATHS["lmsband"]
    if not db_path.exists():
        log(work, "ingest", "lmsband", 0, f"missing: {db_path}")
        return
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    # Pre-pull ds09 & ds10 financial file_id sets so we can tag them later
    financial_ids = set()
    for tbl in ("ds10_transactions", "ds10_balances", "ds10_positions",
                "ds09_transactions", "ds09_cc_transactions", "ds09_cc_statements",
                "ds09_fund_statements"):
        try:
            financial_ids.update(
                r[0] for r in src.execute(f"SELECT DISTINCT file_id FROM {tbl}")
            )
        except sqlite3.OperationalError:
            pass
    travel_ids = set()
    for tbl in ("ds09_travel_flights", "ds09_travel_invoices", "ds09_travel_passengers"):
        try:
            travel_ids.update(
                r[0] for r in src.execute(f"SELECT DISTINCT file_id FROM {tbl}")
            )
        except sqlite3.OperationalError:
            pass

    # Main file rows, joined with text_cache for sample + char_count
    cur = src.execute(
        """SELECT f.id, f.filename, f.dataset, f.rel_path,
                  tc.char_count, SUBSTR(tc.extracted_text, 1, 2048)
           FROM files f LEFT JOIN text_cache tc ON tc.file_id = f.id"""
    )
    rows = 0
    for chunk in batched(cur, 5000):
        payload = []
        for (fid, fname, ds, rpath, cc, sample) in chunk:
            subtype = None
            if fid in financial_ids:
                subtype = "FIN"
            elif fid in travel_ids:
                subtype = "TRAVEL"
            payload.append(
                (
                    str(fid),
                    fname,
                    rpath,
                    ds,
                    subtype,  # source_prefix reused as subtype flag
                    cc,
                    file_ext(fname),
                    (sample or "").lower(),
                )
            )
        work.executemany(
            """INSERT OR IGNORE INTO doc_refs
               (corpus, doc_id, filename, source_path, dataset_num,
                source_prefix, char_count, file_ext, content_sample)
               VALUES ('lmsband', ?, ?, ?, ?, ?, ?, ?, ?)""",
            payload,
        )
        rows += len(payload)
        work.commit()
    src.close()
    log(work, "ingest", "lmsband", rows,
        f"(financial_tagged={len(financial_ids)}, travel_tagged={len(travel_ids)})")


def ingest_unified(work: sqlite3.Connection) -> None:
    db_path = CORPUS_PATHS["unified"]
    if not db_path.exists():
        log(work, "ingest", "unified", 0, f"missing: {db_path}")
        return
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    # documents table
    cur = src.execute(
        """SELECT id, source_dataset, doc_id, category,
                  date_earliest, date_latest, SUBSTR(full_text, 1, 2048)
           FROM documents"""
    )
    rows = 0
    for chunk in batched(cur, 5000):
        payload = [
            (
                f"doc:{rid}",
                None,
                None,
                None,
                src_ds,
                cat,
                de,
                dl,
                (sample or "").lower(),
            )
            for (rid, src_ds, _doc_id, cat, de, dl, sample) in chunk
        ]
        work.executemany(
            """INSERT OR IGNORE INTO doc_refs
               (corpus, doc_id, filename, source_path, dataset_num,
                source_prefix, existing_category, date_earliest, date_latest,
                content_sample)
               VALUES ('unified', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            payload,
        )
        rows += len(payload)
        work.commit()
    # emails table — separate doc_ids so we can classify as axis2=email trivially
    cur = src.execute(
        """SELECT id, source_dataset, subject, timestamp_iso,
                  SUBSTR(body_text, 1, 2048)
           FROM emails"""
    )
    email_rows = 0
    for chunk in batched(cur, 5000):
        payload = [
            (
                f"email:{rid}",
                subj,
                src_ds,
                ts,
                ts,
                (sample or "").lower(),
            )
            for (rid, src_ds, subj, ts, sample) in chunk
        ]
        work.executemany(
            """INSERT OR IGNORE INTO doc_refs
               (corpus, doc_id, filename, source_prefix, existing_category,
                date_earliest, date_latest, content_sample, file_ext)
               VALUES ('unified', ?, ?, ?, 'email', ?, ?, ?, 'eml')""",
            payload,
        )
        email_rows += len(payload)
        work.commit()
    src.close()
    log(work, "ingest", "unified", rows + email_rows,
        f"(docs={rows}, emails={email_rows})")


def ingest_epstein_20k(work: sqlite3.Connection) -> None:
    db_path = CORPUS_PATHS["epstein_20k"]
    if not db_path.exists():
        log(work, "ingest", "epstein_20k", 0, f"missing: {db_path}")
        return
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = src.execute(
        """SELECT house_oversight_id, filename, source_prefix,
                  char_count, SUBSTR(text, 1, 2048)
           FROM documents"""
    )
    rows = 0
    for chunk in batched(cur, 5000):
        payload = [
            (
                ho_id,
                fname,
                sp,
                cc,
                file_ext(fname),
                (sample or "").lower(),
            )
            for (ho_id, fname, sp, cc, sample) in chunk
        ]
        work.executemany(
            """INSERT OR IGNORE INTO doc_refs
               (corpus, doc_id, filename, source_prefix, char_count,
                file_ext, content_sample)
               VALUES ('epstein_20k', ?, ?, ?, ?, ?, ?)""",
            payload,
        )
        rows += len(payload)
        work.commit()
    src.close()
    log(work, "ingest", "epstein_20k", rows)


def ingest_doc_explorer(work: sqlite3.Connection) -> None:
    db_path = CORPUS_PATHS["doc_explorer"]
    if not db_path.exists():
        log(work, "ingest", "doc_explorer", 0, f"missing: {db_path}")
        return
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cur = src.execute(
        """SELECT doc_id, file_path, category, date_range_earliest,
                  date_range_latest, SUBSTR(full_text, 1, 2048)
           FROM documents"""
    )
    rows = 0
    for chunk in batched(cur, 2000):
        payload = [
            (
                doc_id,
                Path(fpath).name if fpath else None,
                fpath,
                cat,
                de,
                dl,
                file_ext(fpath),
                (sample or "").lower(),
            )
            for (doc_id, fpath, cat, de, dl, sample) in chunk
        ]
        work.executemany(
            """INSERT OR IGNORE INTO doc_refs
               (corpus, doc_id, filename, source_path, existing_category,
                date_earliest, date_latest, file_ext, content_sample)
               VALUES ('doc_explorer', ?, ?, ?, ?, ?, ?, ?, ?)""",
            payload,
        )
        rows += len(payload)
        work.commit()
    src.close()
    log(work, "ingest", "doc_explorer", rows)


def walk_loose_dirs(work: sqlite3.Connection) -> None:
    for group, root in LOOSE_DIRS.items():
        if not root.exists():
            log(work, "ingest", f"loose:{group}", 0, f"missing: {root}")
            continue
        count = 0
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    size = p.stat().st_size
                except OSError:
                    size = None
                work.execute(
                    """INSERT OR IGNORE INTO loose_files
                       (group_name, rel_path, file_ext, size_bytes)
                       VALUES (?, ?, ?, ?)""",
                    (group, str(p.relative_to(root)), file_ext(p.name), size),
                )
                count += 1
        work.commit()
        log(work, "ingest", f"loose:{group}", count)
    # Loose PDFs at datasets root
    root_pdf_count = 0
    for pdf in LOOSE_PDFS_AT_ROOT:
        if pdf.exists():
            work.execute(
                """INSERT OR IGNORE INTO loose_files
                   (group_name, rel_path, file_ext, size_bytes)
                   VALUES ('standalone_root_pdfs', ?, 'pdf', ?)""",
                (pdf.name, pdf.stat().st_size),
            )
            root_pdf_count += 1
    work.commit()
    log(work, "ingest", "loose:standalone_root_pdfs", root_pdf_count)


def cmd_ingest(args) -> None:
    workdir = Path(args.workdir).expanduser()
    work = open_work(workdir)
    ingest_doj_vol11(work)
    ingest_lmsband(work)
    ingest_unified(work)
    ingest_epstein_20k(work)
    ingest_doc_explorer(work)
    walk_loose_dirs(work)
    total = work.execute("SELECT COUNT(*) FROM doc_refs").fetchone()[0]
    loose = work.execute("SELECT COUNT(*) FROM loose_files").fetchone()[0]
    print(f"\nIngest complete. doc_refs={total}, loose_files={loose}")
    work.close()


# --- Stage 2: rule-based classification -----------------------------------


@dataclass
class Tag:
    axis1: str | None = None
    axis2: str | None = None
    axis3: str | None = None
    confidence: float = 0.0
    rule: str = ""


# Legacy category map — loaded from YAML
def load_legacy_map() -> dict[str, dict]:
    with open(TAXONOMY_PATH) as f:
        tax = yaml.safe_load(f)
    return tax.get("legacy_category_map", {})


# Rule family 4: filename regex → tags
FILENAME_REGEXES: list[tuple[re.Pattern, Tag]] = [
    (re.compile(r"\b302\b", re.I), Tag(axis2="fbi_302", axis3="fbi", confidence=0.75, rule="fn:302")),
    (re.compile(r"deposition", re.I), Tag(axis2="deposition_transcript", confidence=0.8, rule="fn:deposition")),
    (re.compile(r"flight[-_ ]?log|flight[-_ ]?manifest", re.I), Tag(axis2="flight_log", axis1="personal_records", confidence=0.85, rule="fn:flight")),
    (re.compile(r"subpoena", re.I), Tag(axis2="subpoena", confidence=0.85, rule="fn:subpoena")),
    (re.compile(r"indictment", re.I), Tag(axis2="indictment", confidence=0.9, rule="fn:indictment")),
    (re.compile(r"grand[-_ ]?jury", re.I), Tag(axis1="grand_jury", confidence=0.8, rule="fn:grand_jury")),
    (re.compile(r"complaint", re.I), Tag(axis2="complaint", confidence=0.7, rule="fn:complaint")),
    (re.compile(r"affidavit", re.I), Tag(axis2="affidavit", confidence=0.8, rule="fn:affidavit")),
    (re.compile(r"search[-_ ]?warrant|warrant", re.I), Tag(axis2="search_warrant", confidence=0.7, rule="fn:warrant")),
    (re.compile(r"wire[-_ ]?(transfer|record)", re.I), Tag(axis2="transaction_wire_record", confidence=0.8, rule="fn:wire")),
    (re.compile(r"bank[-_ ]?statement|account[-_ ]?statement", re.I), Tag(axis2="bank_statement", confidence=0.85, rule="fn:bank")),
    (re.compile(r"brokerage|position|portfolio", re.I), Tag(axis2="brokerage_statement", confidence=0.7, rule="fn:brokerage")),
    (re.compile(r"tax[-_ ]?return|form[-_ ]?990|k[-_ ]?1\b", re.I), Tag(axis2="tax_return_990", confidence=0.8, rule="fn:tax")),
    (re.compile(r"trust|will|probate|estate", re.I), Tag(axis2="trust_estate_document", confidence=0.7, rule="fn:trust")),
    (re.compile(r"contract|agreement|nda\b", re.I), Tag(axis2="contract_agreement", confidence=0.65, rule="fn:contract")),
    (re.compile(r"black[-_ ]?book|contact[-_ ]?list|address[-_ ]?book", re.I), Tag(axis2="contact_list", axis1="personal_records", confidence=0.85, rule="fn:contact_list")),
    (re.compile(r"calendar|schedule", re.I), Tag(axis2="calendar_schedule", confidence=0.75, rule="fn:calendar")),
    (re.compile(r"message[-_ ]?pad", re.I), Tag(axis2="message_pad", axis1="personal_records", confidence=0.85, rule="fn:msg_pad")),
    (re.compile(r"kyc|aml|forensic", re.I), Tag(axis2="forensic_kyc_report", confidence=0.7, rule="fn:kyc")),
]


# Rule family 5: source path directory segments
PATH_REGEXES: list[tuple[re.Pattern, Tag]] = [
    (re.compile(r"sdny|southern[-_ ]?district", re.I), Tag(axis1="federal_criminal_sdny", axis3="sdny_usao", confidence=0.6, rule="path:sdny")),
    (re.compile(r"usvi|virgin[-_ ]?islands", re.I), Tag(axis1="state_civil_usvi", axis3="usvi_ag", confidence=0.6, rule="path:usvi")),
    (re.compile(r"giuffre", re.I), Tag(axis1="civil_victim_litigation", confidence=0.75, rule="path:giuffre")),
    (re.compile(r"maxwell", re.I), Tag(axis1="federal_criminal_sdny", confidence=0.5, rule="path:maxwell")),
    (re.compile(r"jpmorgan|jpm[-_ ]|chase", re.I), Tag(axis1="civil_bank_litigation", axis3="jpmorgan", confidence=0.6, rule="path:jpm")),
    (re.compile(r"deutsche|db[-_]", re.I), Tag(axis1="civil_bank_litigation", axis3="deutsche_bank", confidence=0.6, rule="path:db")),
    (re.compile(r"house[-_ ]?oversight", re.I), Tag(axis1="congressional_house_oversight", axis3="house_oversight", confidence=0.8, rule="path:house_oversight")),
    (re.compile(r"palm[-_ ]?beach", re.I), Tag(axis1="state_criminal_fl_2006", axis3="pb_sheriff", confidence=0.6, rule="path:palm_beach")),
    (re.compile(r"\bfbi\b", re.I), Tag(axis3="fbi", confidence=0.7, rule="path:fbi")),
]


# Rule family 7: content keyword scan (first 2KB, lowercased)
CONTENT_KEYWORDS: list[tuple[str, Tag]] = [
    ("fd-302", Tag(axis2="fbi_302", axis3="fbi", confidence=0.85, rule="kw:fd-302")),
    ("form fd-302", Tag(axis2="fbi_302", axis3="fbi", confidence=0.9, rule="kw:form_fd-302")),
    ("federal bureau of investigation", Tag(axis3="fbi", confidence=0.5, rule="kw:fbi_mention")),
    ("grand jury", Tag(axis1="grand_jury", confidence=0.4, rule="kw:grand_jury")),
    ("deposition of", Tag(axis2="deposition_transcript", confidence=0.75, rule="kw:deposition_of")),
    ("non-prosecution agreement", Tag(axis1="state_criminal_fl_2008_npa", confidence=0.8, rule="kw:npa")),
    ("indictment", Tag(axis2="indictment", confidence=0.5, rule="kw:indictment")),
    ("motion to dismiss", Tag(axis2="motion", confidence=0.7, rule="kw:motion_dismiss")),
    ("subpoena duces tecum", Tag(axis2="subpoena", confidence=0.85, rule="kw:subpoena_dt")),
    ("wire transfer", Tag(axis2="transaction_wire_record", confidence=0.55, rule="kw:wire_transfer")),
    ("account statement", Tag(axis2="bank_statement", confidence=0.5, rule="kw:acct_stmt")),
    ("statement of account", Tag(axis2="bank_statement", confidence=0.55, rule="kw:stmt_of_acct")),
    ("form 990", Tag(axis2="tax_return_990", confidence=0.8, rule="kw:form_990")),
    ("flight log", Tag(axis2="flight_log", axis1="personal_records", confidence=0.7, rule="kw:flight_log")),
    ("while you were out", Tag(axis2="message_pad", axis1="personal_records", confidence=0.85, rule="kw:wyo")),
    # Email header scan: require both From: and To: (or Subject:) in the first 2KB.
    # A bare "from:" is too common (quoted text, letters, etc.) — this compound rule
    # is checked specially in classify_row rather than as a plain substring.
    ("last will and testament", Tag(axis2="trust_estate_document", confidence=0.9, rule="kw:will")),
    ("trust agreement", Tag(axis2="trust_estate_document", confidence=0.8, rule="kw:trust_agmt")),
    ("know your customer", Tag(axis2="forensic_kyc_report", confidence=0.75, rule="kw:kyc")),
]


def merge(t: Tag, add: Tag) -> Tag:
    """Merge add into t. Higher confidence wins per axis; stack rule names."""
    if add.axis1 and (not t.axis1 or add.confidence > t.confidence):
        t.axis1 = add.axis1
    if add.axis2 and (not t.axis2 or add.confidence > t.confidence):
        t.axis2 = add.axis2
    if add.axis3 and (not t.axis3 or add.confidence > t.confidence):
        t.axis3 = add.axis3
    t.confidence = max(t.confidence, add.confidence)
    t.rule = t.rule + "," + add.rule if t.rule else add.rule
    return t


def classify_row(row: sqlite3.Row, legacy_map: dict) -> Tag:
    t = Tag()

    # Rule 1: legacy category reuse
    cat = row["existing_category"]
    if cat:
        mapping = legacy_map.get(cat)
        if mapping:
            merge(t, Tag(
                axis1=mapping.get("axis1"),
                axis2=mapping.get("axis2"),
                axis3=mapping.get("axis3"),
                confidence=0.7 if row["corpus"] == "doc_explorer" else 0.55,
                rule=f"legacy:{cat}",
            ))

    # Rule 2: LMSBAND financial/travel subtype flag (stored in source_prefix)
    if row["corpus"] == "lmsband":
        sp = row["source_prefix"]
        if sp == "FIN":
            merge(t, Tag(axis2="transaction_wire_record", confidence=0.9, rule="lms:financial_subtable"))
        elif sp == "TRAVEL":
            merge(t, Tag(axis2="flight_log", axis1="personal_records", confidence=0.9, rule="lms:travel_subtable"))

    # Rule 3: ID prefix ranges
    did = row["doc_id"] or ""
    if did.startswith("HOUSE_OVERSIGHT"):
        merge(t, Tag(
            axis1="congressional_house_oversight",
            axis3="house_oversight",
            confidence=0.8,
            rule="id:house_oversight",
        ))
    elif did.startswith("EFTA") or (row["filename"] or "").startswith("EFTA"):
        # EFTA = DOJ / federal criminal SDNY + DOJ Main release
        merge(t, Tag(
            axis3="doj_main",
            confidence=0.4,
            rule="id:efta",
        ))

    # 20K source_prefix signals — IMAGES vs TEXT
    if row["corpus"] == "epstein_20k":
        sp = row["source_prefix"] or ""
        merge(t, Tag(
            axis1="congressional_house_oversight",
            axis3="house_oversight",
            confidence=0.8,
            rule="prefix:20k_ho",
        ))

    # Rule 4: filename regex
    fn = row["filename"] or ""
    for rx, add in FILENAME_REGEXES:
        if rx.search(fn):
            merge(t, add)

    # Rule 5: source path regex
    path = row["source_path"] or ""
    for rx, add in PATH_REGEXES:
        if rx.search(path):
            merge(t, add)

    # Rule 6: file extension fallback (only if axis2 still empty)
    ext = (row["file_ext"] or "").lower()
    if not t.axis2:
        if ext in ("eml", "msg"):
            merge(t, Tag(axis2="email", confidence=0.9, rule="ext:email"))
        elif ext in ("jpg", "jpeg", "png", "gif", "tiff", "tif", "mp4", "mov", "avi", "wav", "mp3"):
            merge(t, Tag(axis2="photograph_video", confidence=0.85, rule="ext:media"))
        elif ext in ("xlsx", "xls", "csv") and "transaction" in (row["content_sample"] or ""):
            merge(t, Tag(axis2="transaction_wire_record", confidence=0.75, rule="ext:spreadsheet+tx"))
        elif ext in ("xlsx", "xls", "csv"):
            merge(t, Tag(axis2="other", confidence=0.4, rule="ext:spreadsheet"))

    # Rule 7: content keyword scan (only if confidence still low)
    if t.confidence < 0.5:
        sample = row["content_sample"] or ""
        if sample:
            for kw, add in CONTENT_KEYWORDS:
                if kw in sample:
                    merge(t, add)
            # Compound email header detection: From: + (To: or Subject:) on line starts
            if re.search(r"(?:^|\n)from:\s", sample) and \
               re.search(r"(?:^|\n)(?:to|subject):\s", sample):
                merge(t, Tag(axis2="email", confidence=0.7, rule="kw:email_headers"))

    # Fallbacks — unified `email:*` doc_ids
    if row["corpus"] == "unified" and did.startswith("email:"):
        merge(t, Tag(axis2="email", confidence=0.95, rule="unified:email_table"))

    return t


def cmd_classify(args) -> None:
    workdir = Path(args.workdir).expanduser()
    work = sqlite3.connect(workdir / "catalog.db")
    work.row_factory = sqlite3.Row
    work.executescript(SCHEMA)
    legacy_map = load_legacy_map()

    # Clear previous classifications if --reset
    if args.reset:
        work.execute("DELETE FROM classifications")
        work.commit()

    total = work.execute("SELECT COUNT(*) FROM doc_refs").fetchone()[0]
    print(f"Classifying {total:,} doc_refs...")

    cur = work.execute(
        """SELECT * FROM doc_refs
           WHERE id NOT IN (SELECT doc_ref_id FROM classifications)"""
    )
    rows_written = 0
    insert_buf = []
    for row in cur:
        tag = classify_row(row, legacy_map)
        insert_buf.append(
            (
                row["id"],
                tag.axis1 or "unknown",
                tag.axis2 or "unknown",
                tag.axis3 or "unknown",
                tag.confidence,
                json.dumps([r for r in tag.rule.split(",") if r]),
            )
        )
        if len(insert_buf) >= 5000:
            work.executemany(
                """INSERT OR REPLACE INTO classifications
                   (doc_ref_id, axis1, axis2, axis3, confidence, rules_fired)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                insert_buf,
            )
            rows_written += len(insert_buf)
            insert_buf.clear()
            work.commit()
            if rows_written % 100000 == 0:
                print(f"  ... {rows_written:,} / {total:,}")
    if insert_buf:
        work.executemany(
            """INSERT OR REPLACE INTO classifications
               (doc_ref_id, axis1, axis2, axis3, confidence, rules_fired)
               VALUES (?, ?, ?, ?, ?, ?)""",
            insert_buf,
        )
        rows_written += len(insert_buf)
        work.commit()
    log(work, "classify", "all", rows_written)
    work.close()


# --- Stats ----------------------------------------------------------------


def cmd_stats(args) -> None:
    workdir = Path(args.workdir).expanduser()
    work = sqlite3.connect(workdir / "catalog.db")
    work.row_factory = sqlite3.Row

    print("\n=== doc_refs by corpus ===")
    for r in work.execute("SELECT corpus, COUNT(*) n FROM doc_refs GROUP BY corpus ORDER BY n DESC"):
        print(f"  {r['corpus']:20} {r['n']:>10,}")

    print("\n=== loose files by group ===")
    for r in work.execute(
        "SELECT group_name, COUNT(*) n, SUM(size_bytes) sz FROM loose_files GROUP BY group_name ORDER BY n DESC"
    ):
        sz = (r["sz"] or 0) / (1024 * 1024)
        print(f"  {r['group_name']:30} {r['n']:>8,}  ({sz:,.1f} MB)")

    try:
        print("\n=== axis2 (form) distribution ===")
        for r in work.execute(
            "SELECT axis2, COUNT(*) n FROM classifications GROUP BY axis2 ORDER BY n DESC"
        ):
            print(f"  {r['axis2']:30} {r['n']:>10,}")

        print("\n=== axis1 (origin) distribution ===")
        for r in work.execute(
            "SELECT axis1, COUNT(*) n FROM classifications GROUP BY axis1 ORDER BY n DESC"
        ):
            print(f"  {r['axis1']:30} {r['n']:>10,}")

        print("\n=== axis3 (custodian) distribution ===")
        for r in work.execute(
            "SELECT axis3, COUNT(*) n FROM classifications GROUP BY axis3 ORDER BY n DESC"
        ):
            print(f"  {r['axis3']:30} {r['n']:>10,}")

        print("\n=== confidence buckets ===")
        for r in work.execute(
            """SELECT CASE
                        WHEN confidence >= 0.8 THEN 'high (>=0.8)'
                        WHEN confidence >= 0.5 THEN 'medium'
                        WHEN confidence > 0    THEN 'low'
                        ELSE 'zero'
                      END bucket, COUNT(*) n
               FROM classifications
               GROUP BY bucket ORDER BY n DESC"""
        ):
            print(f"  {r['bucket']:20} {r['n']:>10,}")
    except sqlite3.OperationalError:
        print("  (classifications table empty — run `classify` first)")

    work.close()


# --- CLI ------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workdir", required=True,
                   help="Working directory for catalog.db (e.g., $WORKDIR)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ingest", help="Stage 1: pull metadata from all corpora").set_defaults(func=cmd_ingest)

    cp = sub.add_parser("classify", help="Stage 2: apply rule-based classification")
    cp.add_argument("--reset", action="store_true", help="Clear classifications table first")
    cp.set_defaults(func=cmd_classify)

    sub.add_parser("stats", help="Show counts").set_defaults(func=cmd_stats)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
