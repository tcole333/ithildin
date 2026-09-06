#!/usr/bin/env python3
"""
Query and build the local Ehud Barak emails corpus.

Source: DDoSecrets "Ehud Barak emails" (published 2025-08-27), a 4.6 GiB solid
7z archive containing 100,000+ emails and attachments (2007-2016) from two
mailboxes -- ``ehbarak1@gmail.com`` and ``ehud.barak@hyperion-eb.com``. Leaked
by the Handala hacking group. DDoSecrets flags this Cyberwar-category dataset
for elevated risk of malware and altered/implanted data; handle attachments as
inert bytes only.

Database: datasets/barak_emails.db

The corpus is stored as three message representations:
  - ``.meta``  JSON header records (sender/subject/date/folder + body preview)
  - ``.html``  saved-webpage message bodies (subject + body text, inline headers)
  - ``.eml``   raw RFC822 messages

Parsing is strictly offline and text-only: HTML is tag-stripped, remote
resources (tracking pixels, linked images) are never fetched, and attachments
are never opened or executed -- only cataloged by name/size/hash/type with a
danger classification.

Usage:
    python tools/query_barak.py ingest [--force] [--limit N]
    python tools/query_barak.py folders                     # shard units + counts
    python tools/query_barak.py list --folder Inbox --offset 0 --limit 100
    python tools/query_barak.py search "epstein" --limit 20
    python tools/query_barak.py show <message_id> [--full]
    python tools/query_barak.py attachments [--danger] [--ext pdf]
    python tools/query_barak.py stats
"""

import argparse
import email
import email.policy
import hashlib
import html as html_mod
import json
import mimetypes
import re
import sqlite3
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
    from tools.fts_query import literal_fts_query
except ImportError:
    from output_util import add_output_args, write_output
    from fts_query import literal_fts_query

REPO = Path(__file__).parent.parent
DB_PATH = REPO / "datasets" / "barak_emails.db"
EXTRACT_DIR = REPO / "datasets" / "barak_emails" / "_quarantine" / "extracted"

# Attachment danger classification by extension.
_EXEC = {"exe", "dll", "scr", "com", "bat", "cmd", "msi", "app", "pkg", "dmg",
         "jar", "lnk", "iso", "vbs", "vbe", "wsf", "hta", "cpl", "msc"}
_SCRIPT = {"js", "jse", "ps1", "psm1", "sh", "bash", "py", "pl", "rb", "php"}
_MACRO_OFFICE = {"doc", "xls", "ppt", "docm", "xlsm", "pptm", "dotm", "xltm",
                 "potm", "xlsb"}
_ARCHIVE = {"zip", "7z", "rar", "gz", "tar", "tgz", "cab", "z", "arj"}


def classify_danger(ext: str) -> str:
    e = (ext or "").lower().lstrip(".")
    if e in _EXEC:
        return "executable"
    if e in _SCRIPT:
        return "script"
    if e in _MACRO_OFFICE:
        return "macro-office"
    if e in _ARCHIVE:
        return "archive"
    if e in {"pdf"}:
        return "pdf"
    if e in {"p7s", "p7m", "dat", "bin", ""}:
        return "opaque-binary"
    return ""


# ── HTML → text (offline; never fetches remote resources) ──────────────

class _TextExtractor(HTMLParser):
    """Collect visible text; drop script/style; note inline headers."""

    _SKIP = {"script", "style", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts = []
        self.title = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in ("br", "p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title and self.title is None:
            self.title = data.strip()
        if data.strip():
            self.parts.append(data)


def html_to_text(raw: str) -> tuple[str, str | None]:
    p = _TextExtractor()
    try:
        p.feed(raw)
    except Exception:
        # Fall back to a blunt tag strip if the parser chokes.
        txt = re.sub(r"<[^>]+>", " ", raw)
        return _collapse(html_mod.unescape(txt)), None
    text = _collapse("".join(p.parts))
    return text, p.title


def _collapse(s: str) -> str:
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


_HDR_RE = {
    "from": re.compile(r"(?:^|\n)\s*(?:from|מאת)\s*:\s*(.+)", re.I),
    "to": re.compile(r"(?:^|\n)\s*(?:to|אל)\s*:\s*(.+)", re.I),
    "cc": re.compile(r"(?:^|\n)\s*cc\s*:\s*(.+)", re.I),
    "date": re.compile(r"(?:^|\n)\s*(?:sent|date|נשלח)\s*:\s*(.+)", re.I),
    "subject": re.compile(r"(?:^|\n)\s*(?:subject|נושא)\s*:\s*(.+)", re.I),
}


def sniff_inline_headers(text: str) -> dict:
    """Best-effort pull of From/To/Date/Subject from a forwarded-mail body."""
    head = text[:1500]
    out = {}
    for key, rx in _HDR_RE.items():
        m = rx.search(head)
        if m:
            out[key] = m.group(1).strip()[:500]
    return out


# ── .meta bencode body preview ─────────────────────────────────────────

def bdecode_dict_field(blob: str, field: str) -> str | None:
    """Extract one string value from a flat bencoded dict like
    ``d1:f149:<text>1:p4:Re: 1:s39:<sender>1:vi10ee``. Length-prefixed so the
    value can safely contain ':' and digits."""
    key = f"1:{field}"
    i = blob.find(key)
    if i < 0:
        return None
    j = i + len(key)
    m = re.match(r"(\d+):", blob[j:])
    if not m:
        return None
    length = int(m.group(1))
    start = j + m.end()
    return blob[start:start + length]


# ── date normalization ─────────────────────────────────────────────────

def epoch_to_iso(val) -> str | None:
    try:
        return datetime.fromtimestamp(int(val), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


# ── DB ─────────────────────────────────────────────────────────────────

def get_db(create=False):
    if not DB_PATH.exists() and not create:
        print(f"ERROR: Barak email database not found at {DB_PATH}. Run: "
              f"python tools/query_barak.py ingest")
        sys.exit(1)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db(db):
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            source_path TEXT UNIQUE,
            mailbox TEXT,
            folder TEXT,
            scheme TEXT,
            imap_id INTEGER,
            from_addr TEXT,
            to_addr TEXT,
            cc_addr TEXT,
            subject TEXT,
            date_raw TEXT,
            date_iso TEXT,
            body_text TEXT,
            body_chars INTEGER,
            has_attach INTEGER DEFAULT 0,
            content_hash TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_msg_date ON messages(date_iso);
        CREATE INDEX IF NOT EXISTS ix_msg_hash ON messages(content_hash);
        CREATE INDEX IF NOT EXISTS ix_msg_scheme ON messages(scheme);

        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY,
            source_path TEXT UNIQUE,
            mailbox TEXT,
            folder TEXT,
            filename TEXT,
            ext TEXT,
            size INTEGER,
            sha256 TEXT,
            mime_guess TEXT,
            danger TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_att_danger ON attachments(danger);
        CREATE INDEX IF NOT EXISTS ix_att_ext ON attachments(ext);
        CREATE INDEX IF NOT EXISTS ix_att_sha ON attachments(sha256);

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            subject, body_text, from_addr, to_addr,
            content='messages', content_rowid='id'
        );
        """
    )
    db.commit()


# Message-body file schemes we ingest. Everything else is an attachment.
_BODY_EXT = {"html", "htm", "eml", "meta"}
# Inline saved-webpage resource dirs; treated as attachments if binary.
_RESOURCE_DIR = re.compile(r"_files(/|$)")


def rel_parts(path: Path):
    rel = path.relative_to(EXTRACT_DIR)
    parts = rel.parts
    mailbox = parts[0] if parts else ""
    folder = "/".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) == 2 else "")
    return str(rel), mailbox, folder


def parse_meta(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    body = ""
    meta_blob = data.get("metadata")
    if isinstance(meta_blob, str):
        body = bdecode_dict_field(meta_blob, "f") or ""
    subject = data.get("subject") or ""
    sender = data.get("sender") or ""
    date_raw = str(data.get("date") or "")
    return {
        "scheme": "meta",
        "imap_id": data.get("imap_id"),
        "from_addr": sender,
        "to_addr": "",
        "cc_addr": "",
        "subject": subject,
        "date_raw": date_raw,
        "date_iso": epoch_to_iso(data.get("date")),
        "body_text": body,
        "folder_override": (data.get("Path") or "").strip("/") or None,
    }


def parse_html(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    text, title = html_to_text(raw)
    hdr = sniff_inline_headers(text)
    subject = hdr.get("subject") or (title or "")
    return {
        "scheme": "html",
        "imap_id": None,
        "from_addr": hdr.get("from", ""),
        "to_addr": hdr.get("to", ""),
        "cc_addr": hdr.get("cc", ""),
        "subject": subject,
        "date_raw": hdr.get("date", ""),
        "date_iso": None,
        "body_text": text,
        "folder_override": None,
    }


def parse_eml(path: Path) -> dict | None:
    try:
        with path.open("rb") as fh:
            msg = email.message_from_binary_file(fh, policy=email.policy.default)
    except Exception:
        return None
    body = ""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is not None:
            payload = part.get_content()
            if part.get_content_subtype() == "html":
                body, _ = html_to_text(payload)
            else:
                body = _collapse(payload)
    except Exception:
        body = ""
    date_raw = msg.get("Date", "")
    date_iso = None
    try:
        dt = email.utils.parsedate_to_datetime(date_raw) if date_raw else None
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            date_iso = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return {
        "scheme": "eml",
        "imap_id": None,
        "from_addr": str(msg.get("From", "")),
        "to_addr": str(msg.get("To", "")),
        "cc_addr": str(msg.get("Cc", "")),
        "subject": str(msg.get("Subject", "")),
        "date_raw": date_raw,
        "date_iso": date_iso,
        "body_text": body,
        "folder_override": None,
    }


def content_hash(rec: dict) -> str:
    h = hashlib.sha256()
    h.update((rec.get("from_addr") or "").lower().encode("utf-8", "replace"))
    h.update(b"\x00")
    h.update((rec.get("subject") or "").lower().encode("utf-8", "replace"))
    h.update(b"\x00")
    h.update((rec.get("date_raw") or "").encode("utf-8", "replace"))
    h.update(b"\x00")
    h.update((rec.get("body_text") or "")[:4000].encode("utf-8", "replace"))
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_ingest(args):
    if not EXTRACT_DIR.exists():
        print(f"ERROR: extracted corpus not found at {EXTRACT_DIR}")
        sys.exit(1)
    db = get_db(create=True)
    if args.force:
        db.executescript("DROP TABLE IF EXISTS messages; DROP TABLE IF EXISTS attachments; "
                         "DROP TABLE IF EXISTS messages_fts;")
        db.commit()
    init_db(db)

    n_msg = n_att = n_dupe = n_skip = 0
    seen_hashes = set()
    for row in db.execute("SELECT content_hash FROM messages"):
        if row[0]:
            seen_hashes.add(row[0])
    have_paths = {r[0] for r in db.execute("SELECT source_path FROM messages")}
    have_att = {r[0] for r in db.execute("SELECT source_path FROM attachments")}

    files = (p for p in EXTRACT_DIR.rglob("*") if p.is_file())
    for i, path in enumerate(files):
        if args.limit and (n_msg + n_att) >= args.limit:
            break
        try:
            rel, mailbox, folder = rel_parts(path)
        except Exception:
            continue
        name = path.name
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

        if ext in _BODY_EXT and not _RESOURCE_DIR.search(rel):
            if rel in have_paths:
                continue
            if ext == "meta":
                rec = parse_meta(path)
            elif ext in ("html", "htm"):
                rec = parse_html(path)
            else:
                rec = parse_eml(path)
            if not rec or not (rec["body_text"] or rec["subject"]):
                n_skip += 1
                continue
            ch = content_hash(rec)
            is_dupe = ch in seen_hashes
            if is_dupe:
                n_dupe += 1
            seen_hashes.add(ch)
            fld = rec.get("folder_override") or folder
            db.execute(
                """INSERT OR IGNORE INTO messages
                   (source_path, mailbox, folder, scheme, imap_id, from_addr,
                    to_addr, cc_addr, subject, date_raw, date_iso, body_text,
                    body_chars, has_attach, content_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rel, mailbox, fld, rec["scheme"], rec["imap_id"],
                 rec["from_addr"], rec["to_addr"], rec["cc_addr"], rec["subject"],
                 rec["date_raw"], rec["date_iso"], rec["body_text"],
                 len(rec["body_text"] or ""), 0, ch),
            )
            n_msg += 1
        else:
            # Attachment / inline resource: catalog only, never open/execute.
            if rel in have_att:
                continue
            try:
                size = path.stat().st_size
                sha = sha256_file(path) if size <= (64 << 20) else None
            except Exception:
                size, sha = None, None
            mime = mimetypes.guess_type(name)[0]
            db.execute(
                """INSERT OR IGNORE INTO attachments
                   (source_path, mailbox, folder, filename, ext, size, sha256,
                    mime_guess, danger)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (rel, mailbox, folder, name, ext, size, sha, mime, classify_danger(ext)),
            )
            n_att += 1

        if (n_msg + n_att) % 5000 == 0 and (n_msg + n_att) > 0:
            db.commit()
            print(f"  ...{n_msg} messages, {n_att} attachments", file=sys.stderr)

    # Rebuild FTS from content table.
    db.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
    db.commit()
    print(f"Ingest complete: {n_msg} messages ({n_dupe} content-dupes flagged), "
          f"{n_att} attachments cataloged, {n_skip} empty skipped.")
    print(f"DB: {DB_PATH}")


def cmd_search(args):
    db = get_db()
    q = literal_fts_query(args.query)
    rows = db.execute(
        """SELECT m.id, m.mailbox, m.folder, m.scheme, m.from_addr, m.subject,
                  m.date_iso, m.body_chars,
                  snippet(messages_fts, 1, '[', ']', ' … ', 12) AS snip
           FROM messages_fts JOIN messages m ON m.id = messages_fts.rowid
           WHERE messages_fts MATCH ?
           ORDER BY rank LIMIT ?""",
        (q, args.limit),
    ).fetchall()
    results = [dict(r) for r in rows]
    if write_output(results, args, summary=f"Barak email search '{args.query}': {len(results)} hits"):
        return
    if not results:
        print(f"No matches for '{args.query}'.")
        return
    for r in results:
        print(f"\n[{r['id']}] {r['date_iso'] or '?'}  ({r['scheme']})  {r['folder']}")
        print(f"    From: {r['from_addr'][:80]}")
        print(f"    Subj: {r['subject'][:90]}")
        print(f"    {r['snip'][:200]}")


def cmd_show(args):
    db = get_db()
    r = db.execute("SELECT * FROM messages WHERE id=?", (args.message_id,)).fetchone()
    if not r:
        print(f"No message {args.message_id}")
        return
    r = dict(r)
    if write_output(r, args, summary=f"Barak message {args.message_id}"):
        return
    print(f"id={r['id']}  scheme={r['scheme']}  mailbox={r['mailbox']}  folder={r['folder']}")
    print(f"From: {r['from_addr']}")
    print(f"To:   {r['to_addr']}")
    print(f"Cc:   {r['cc_addr']}")
    print(f"Date: {r['date_iso'] or r['date_raw']}")
    print(f"Subject: {r['subject']}")
    print(f"Path: {r['source_path']}")
    print("-" * 60)
    body = r["body_text"] or ""
    print(body if args.full else body[:args.chars])


def cmd_folders(args):
    """Enumerate folders with message counts -- the unit of work for sharding."""
    db = get_db()
    rows = db.execute(
        """SELECT mailbox, folder, COUNT(*) AS n,
                  SUM(CASE WHEN body_chars > 0 THEN 1 ELSE 0 END) AS with_body,
                  MIN(date_iso) AS min_date, MAX(date_iso) AS max_date
           FROM messages GROUP BY mailbox, folder ORDER BY n DESC"""
    ).fetchall()
    results = [dict(r) for r in rows]
    if write_output(results, args, summary=f"{len(results)} folders"):
        return
    print(f"{'n':>7}  {'body':>6}  mailbox / folder")
    for r in results:
        print(f"{r['n']:>7}  {r['with_body']:>6}  {r['mailbox']} / {r['folder']}")


def cmd_list(args):
    """Page through messages for systematic coverage (triage before `show`)."""
    db = get_db()
    where, params = [], []
    if args.mailbox:
        where.append("mailbox = ?")
        params.append(args.mailbox)
    if args.folder:
        where.append("folder = ?" if not args.folder_like else "folder LIKE ?")
        params.append(args.folder)
    if args.scheme:
        where.append("scheme = ?")
        params.append(args.scheme)
    if args.min_chars:
        where.append("body_chars >= ?")
        params.append(args.min_chars)
    if args.since:
        where.append("date_iso >= ?")
        params.append(args.since)
    if args.until:
        where.append("date_iso <= ?")
        params.append(args.until)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.execute(
        f"""SELECT id, mailbox, folder, scheme, date_iso, date_raw, from_addr,
                   to_addr, subject, body_chars, substr(body_text,1,?) AS preview
            FROM messages {clause}
            ORDER BY id LIMIT ? OFFSET ?""",
        (args.preview, *params, args.limit, args.offset),
    ).fetchall()
    results = [dict(r) for r in rows]
    if write_output(results, args, summary=f"list: {len(results)} messages"):
        return
    for r in results:
        print(f"\n[{r['id']}] {r['date_iso'] or r['date_raw'] or '?'}  ({r['scheme']})  "
              f"{r['mailbox']}/{r['folder']}  {r['body_chars']}c")
        print(f"    From: {(r['from_addr'] or '')[:80]}")
        if r['to_addr']:
            print(f"    To:   {r['to_addr'][:80]}")
        print(f"    Subj: {(r['subject'] or '')[:100]}")
        if r['preview']:
            print(f"    {r['preview'].strip()[:220]}")


def cmd_attachments(args):
    db = get_db()
    where, params = [], []
    if args.danger:
        where.append("danger != ''")
    if args.ext:
        where.append("ext = ?")
        params.append(args.ext.lower().lstrip("."))
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.execute(
        f"""SELECT danger, ext, COUNT(*) n, SUM(size) bytes
            FROM attachments {clause}
            GROUP BY danger, ext ORDER BY n DESC""", params).fetchall()
    summary = [dict(r) for r in rows]
    if write_output(summary, args, summary="Barak attachment inventory"):
        return
    print(f"{'danger':16} {'ext':8} {'count':>7} {'MB':>10}")
    for r in rows:
        print(f"{(r['danger'] or '-'):16} {(r['ext'] or '-'):8} {r['n']:>7} "
              f"{(r['bytes'] or 0)/1e6:>10.1f}")


def cmd_stats(args):
    db = get_db()
    out = {}
    out["messages"] = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    out["by_scheme"] = {r[0]: r[1] for r in db.execute(
        "SELECT scheme, COUNT(*) FROM messages GROUP BY scheme")}
    out["by_mailbox"] = {r[0]: r[1] for r in db.execute(
        "SELECT mailbox, COUNT(*) FROM messages GROUP BY mailbox")}
    dr = db.execute("SELECT MIN(date_iso), MAX(date_iso) FROM messages WHERE date_iso IS NOT NULL").fetchone()
    out["date_range"] = {"min": dr[0], "max": dr[1]}
    out["content_dupes"] = db.execute(
        "SELECT COUNT(*)-COUNT(DISTINCT content_hash) FROM messages").fetchone()[0]
    out["attachments"] = db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0]
    out["attach_dangerous"] = db.execute(
        "SELECT COUNT(*) FROM attachments WHERE danger NOT IN ('','pdf')").fetchone()[0]
    out["attach_by_danger"] = {r[0] or "(clean)": r[1] for r in db.execute(
        "SELECT danger, COUNT(*) FROM attachments GROUP BY danger ORDER BY 2 DESC")}
    if write_output(out, args, summary="Barak corpus stats"):
        return
    print(json.dumps(out, indent=2, default=str))


def main():
    ap = argparse.ArgumentParser(description="Ehud Barak emails corpus (DDoSecrets/Handala leak)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest", help="Build barak_emails.db from the extracted quarantine tree")
    p.add_argument("--force", action="store_true", help="Drop and rebuild")
    p.add_argument("--limit", type=int, default=0, help="Stop after N files (debug)")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("search", help="FTS5 search over subject/body/from/to")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("show", help="Show one message")
    p.add_argument("message_id", type=int)
    p.add_argument("--full", action="store_true")
    p.add_argument("--chars", type=int, default=3000)
    add_output_args(p)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("folders", help="Enumerate folders + counts (sharding unit)")
    add_output_args(p)
    p.set_defaults(func=cmd_folders)

    p = sub.add_parser("list", help="Page messages for systematic coverage")
    p.add_argument("--mailbox", help="Exact mailbox (ehbarak1@gmail.com | ehud.barak@hyperion-eb.com)")
    p.add_argument("--folder", help="Exact folder name (or use --folder-like)")
    p.add_argument("--folder-like", action="store_true", help="Treat --folder as a LIKE pattern")
    p.add_argument("--scheme", choices=["html", "meta", "eml"], help="Filter by representation")
    p.add_argument("--min-chars", type=int, default=0, help="Minimum body length")
    p.add_argument("--since", help="date_iso >= (YYYY-MM-DD); only dated msgs")
    p.add_argument("--until", help="date_iso <= (YYYY-MM-DD); only dated msgs")
    p.add_argument("--preview", type=int, default=200, help="Body preview chars (default 200)")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)
    add_output_args(p)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("attachments", help="Attachment inventory / danger triage")
    p.add_argument("--danger", action="store_true", help="Only flagged (non-clean) types")
    p.add_argument("--ext", help="Filter by extension")
    add_output_args(p)
    p.set_defaults(func=cmd_attachments)

    p = sub.add_parser("stats", help="Corpus statistics")
    add_output_args(p)
    p.set_defaults(func=cmd_stats)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
