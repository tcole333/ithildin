#!/usr/bin/env python3
"""
Git repository analysis tool for OSINT investigations.

Clones git repos, extracts structured commit metadata via PyDriller, stores in
SQLite, and classifies commits by subsystem. Supports temporal correlation with
investigation event timelines.

Usage:
    python tools/analyze_git_repo.py clone https://github.com/nginx/nginx.git --name nginx
    python tools/analyze_git_repo.py ingest --repo nginx
    python tools/analyze_git_repo.py contributors --repo nginx
    python tools/analyze_git_repo.py contributors --repo nginx --subsystem tls_ssl
    python tools/analyze_git_repo.py timeline --repo nginx --subsystem tls_ssl --start 2019-01 --end 2020-01
    python tools/analyze_git_repo.py activity --repo nginx --author "dounin"
    python tools/analyze_git_repo.py hotspots --repo nginx --start 2019-12-01 --end 2019-12-31
    python tools/analyze_git_repo.py subsystem-authors --repo nginx --subsystem tls_ssl
    python tools/analyze_git_repo.py correlate --repo nginx --days 14
    python tools/analyze_git_repo.py stats --repo nginx
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from output_util import add_output_args, write_output

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "git_analysis.db"
REPOS_DIR = PROJECT_ROOT / "datasets" / "git_repos"
INVESTIGATION_DB = PROJECT_ROOT / "investigation.db"

# ── Subsystem classification ──────────────────────────────────────────
# Each rule: (subsystem_name, security_level, [path_patterns])
# Ordered by specificity — first match wins.

SUBSYSTEM_RULES = [
    ("tls_ssl", "CRITICAL", [
        r"src/event/ngx_event_openssl",
        r"src/http/modules/ngx_http_ssl",
        r"src/http/v[23]/ngx_http_v[23]",
        r"src/stream/ngx_stream_ssl",
        r"src/mail/ngx_mail_ssl",
    ]),
    ("auth", "CRITICAL", [
        r"src/http/modules/ngx_http_auth",
    ]),
    ("crypto", "CRITICAL", [
        r".*rand.*",
        r".*entropy.*",
        r".*prng.*",
    ]),
    ("connection", "HIGH", [
        r"src/event/ngx_event",
        r"src/os/unix/ngx_process",
        r"src/os/unix/ngx_socket",
        r"src/os/unix/ngx_channel",
    ]),
    ("http_core", "HIGH", [
        r"src/http/ngx_http(?!.*modules)",
        r"src/http/ngx_http_(?:request|header|parse|core|upstream|script|variables)",
    ]),
    ("logging", "MEDIUM", [
        r"src/core/ngx_log",
        r"src/http/modules/ngx_http_log",
    ]),
    ("mail", "MEDIUM", [
        r"src/mail/",
    ]),
    ("stream", "MEDIUM", [
        r"src/stream/",
    ]),
    ("modules", "MEDIUM", [
        r"src/http/modules/",
    ]),
    ("core", "MEDIUM", [
        r"src/core/",
        r"src/os/",
    ]),
    ("build", "LOW", [
        r"auto/",
        r"configure",
        r"Makefile",
        r"misc/",
    ]),
    ("docs", "LOW", [
        r"docs/",
        r"CHANGES",
        r"README",
        r"LICENSE",
    ]),
    ("tests", "LOW", [
        r"test",
        r"t/",
    ]),
]

# Compiled patterns for performance
_COMPILED_RULES = [
    (name, level, [re.compile(p, re.IGNORECASE) for p in patterns])
    for name, level, patterns in SUBSYSTEM_RULES
]


def classify_file(filepath):
    """Classify a file path into a subsystem. Returns (subsystem, security_level)."""
    for name, level, patterns in _COMPILED_RULES:
        for pat in patterns:
            if pat.search(filepath):
                return name, level
    return "other", "LOW"


def classify_commit_subsystems(file_paths):
    """Classify a commit into subsystems based on all files touched.
    Returns list of unique subsystem names."""
    subsystems = set()
    for fp in file_paths:
        sub, _ = classify_file(fp)
        subsystems.add(sub)
    return sorted(subsystems)


def security_level_for_subsystem(subsystem):
    """Get security level for a subsystem name."""
    for name, level, _ in SUBSYSTEM_RULES:
        if name == subsystem:
            return level
    return "LOW"


# ── Database ──────────────────────────────────────────────────────────

def get_db():
    """Open or create the git analysis database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA synchronous=NORMAL")
    _ensure_schema(db)
    return db


def _ensure_schema(db):
    """Create tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS git_repos (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT,
            local_path TEXT NOT NULL,
            profile_id TEXT,
            total_commits INTEGER DEFAULT 0,
            total_contributors INTEGER DEFAULT 0,
            first_commit_date TEXT,
            last_commit_date TEXT,
            ingested_at TEXT,
            UNIQUE(name)
        );

        CREATE TABLE IF NOT EXISTS git_commits (
            id INTEGER PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES git_repos(id),
            hash TEXT NOT NULL,
            author_name TEXT,
            author_email TEXT,
            author_date TEXT,
            author_timezone INTEGER,
            committer_name TEXT,
            committer_email TEXT,
            commit_date TEXT,
            subject TEXT,
            body TEXT,
            merge INTEGER DEFAULT 0,
            files_changed INTEGER DEFAULT 0,
            insertions INTEGER DEFAULT 0,
            deletions INTEGER DEFAULT 0,
            subsystems TEXT,
            UNIQUE(repo_id, hash)
        );

        CREATE TABLE IF NOT EXISTS git_contributors (
            id INTEGER PRIMARY KEY,
            repo_id INTEGER NOT NULL REFERENCES git_repos(id),
            name TEXT,
            email TEXT,
            entity_id INTEGER,
            first_commit_date TEXT,
            last_commit_date TEXT,
            commit_count INTEGER DEFAULT 0,
            primary_subsystems TEXT,
            UNIQUE(repo_id, email)
        );

        CREATE TABLE IF NOT EXISTS git_file_changes (
            id INTEGER PRIMARY KEY,
            commit_id INTEGER NOT NULL REFERENCES git_commits(id),
            file_path TEXT,
            change_type TEXT,
            insertions INTEGER DEFAULT 0,
            deletions INTEGER DEFAULT 0,
            subsystem TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_gc_repo ON git_commits(repo_id);
        CREATE INDEX IF NOT EXISTS idx_gc_author_date ON git_commits(author_date);
        CREATE INDEX IF NOT EXISTS idx_gc_author_email ON git_commits(author_email);
        CREATE INDEX IF NOT EXISTS idx_gc_hash ON git_commits(hash);
        CREATE INDEX IF NOT EXISTS idx_gfc_commit ON git_file_changes(commit_id);
        CREATE INDEX IF NOT EXISTS idx_gfc_subsystem ON git_file_changes(subsystem);
        CREATE INDEX IF NOT EXISTS idx_gcn_repo ON git_contributors(repo_id);
    """)
    db.commit()


# ── Commands ──────────────────────────────────────────────────────────

def cmd_clone(args):
    """Clone a git repository for analysis."""
    url = args.url
    name = args.name or url.rstrip("/").split("/")[-1].replace(".git", "")

    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    repo_path = REPOS_DIR / name

    if repo_path.exists():
        print(f"Repository already exists at {repo_path}")
        print("  Use 'ingest' to re-parse commits, or delete the directory to re-clone.")
        return

    print(f"Cloning {url} -> {repo_path}")
    result = subprocess.run(
        ["git", "clone", "--bare", url, str(repo_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: git clone failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"  Cloned successfully: {repo_path}")

    # Register in DB
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO git_repos (name, url, local_path, profile_id) VALUES (?, ?, ?, ?)",
        (name, url, str(repo_path), _get_active_profile()),
    )
    db.commit()
    db.close()
    print(f"  Registered as repo '{name}'")


def cmd_ingest(args):
    """Parse all commits from a cloned repo into the database."""
    from pydriller import Repository

    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]
    repo_path = repo_row["local_path"]

    if not Path(repo_path).exists():
        print(f"ERROR: Repo path {repo_path} not found. Re-clone with 'clone' command.")
        sys.exit(1)

    # Clear existing data for re-ingest
    if not args.append:
        db.execute("DELETE FROM git_file_changes WHERE commit_id IN (SELECT id FROM git_commits WHERE repo_id = ?)", (repo_id,))
        db.execute("DELETE FROM git_commits WHERE repo_id = ?", (repo_id,))
        db.execute("DELETE FROM git_contributors WHERE repo_id = ?", (repo_id,))
        db.commit()
        print("  Cleared existing commit data (use --append to add incrementally)")

    print(f"Ingesting commits from {repo_path}...")

    commit_count = 0
    contributor_stats = defaultdict(lambda: {
        "name": "", "first": None, "last": None, "count": 0,
        "subsystems": Counter(),
    })

    commit_batch = []
    file_batch = []
    batch_size = 500
    start = datetime.now()

    for commit in Repository(repo_path).traverse_commits():
        author_date = commit.author_date.isoformat() if commit.author_date else None
        commit_date = commit.committer_date.isoformat() if commit.committer_date else None
        author_tz = int(commit.author_date.utcoffset().total_seconds()) if commit.author_date and commit.author_date.utcoffset() else None

        file_paths = []
        total_ins = 0
        total_del = 0
        file_records = []

        for mod in commit.modified_files:
            fp = mod.new_path or mod.old_path or ""
            file_paths.append(fp)
            ins = mod.added_lines or 0
            dels = mod.deleted_lines or 0
            total_ins += ins
            total_del += dels
            subsystem, _ = classify_file(fp)
            change_type = mod.change_type.name if mod.change_type else "UNKNOWN"
            file_records.append((fp, change_type, ins, dels, subsystem))

        subsystems = classify_commit_subsystems(file_paths)
        subsystems_json = json.dumps(subsystems)

        commit_batch.append((
            repo_id, commit.hash, commit.author.name, commit.author.email,
            author_date, author_tz,
            commit.committer.name, commit.committer.email, commit_date,
            commit.msg.split("\n")[0] if commit.msg else "",
            commit.msg if commit.msg else "",
            1 if commit.merge else 0,
            len(file_paths), total_ins, total_del, subsystems_json,
            file_records,  # stashed for file_changes insert
        ))

        # Track contributor stats
        email = commit.author.email or "unknown"
        cs = contributor_stats[email]
        cs["name"] = commit.author.name or ""
        cs["count"] += 1
        if author_date:
            if cs["first"] is None or author_date < cs["first"]:
                cs["first"] = author_date
            if cs["last"] is None or author_date > cs["last"]:
                cs["last"] = author_date
        for sub in subsystems:
            cs["subsystems"][sub] += 1

        commit_count += 1
        if len(commit_batch) >= batch_size:
            _flush_commits(db, commit_batch, file_batch)
            commit_batch.clear()
            elapsed = (datetime.now() - start).total_seconds()
            rate = commit_count / elapsed if elapsed > 0 else 0
            print(f"  {commit_count} commits ({rate:.0f}/sec)...", end="\r")

    # Final flush
    if commit_batch:
        _flush_commits(db, commit_batch, file_batch)

    # Insert contributors
    for email, cs in contributor_stats.items():
        top_subs = [s for s, _ in cs["subsystems"].most_common(5)]
        db.execute("""
            INSERT OR REPLACE INTO git_contributors
            (repo_id, name, email, first_commit_date, last_commit_date, commit_count, primary_subsystems)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (repo_id, cs["name"], email, cs["first"], cs["last"], cs["count"], json.dumps(top_subs)))

    # Update repo metadata
    dates = db.execute(
        "SELECT MIN(author_date) as first, MAX(author_date) as last FROM git_commits WHERE repo_id = ?",
        (repo_id,),
    ).fetchone()
    db.execute("""
        UPDATE git_repos SET total_commits = ?, total_contributors = ?,
        first_commit_date = ?, last_commit_date = ?, ingested_at = ?
        WHERE id = ?
    """, (commit_count, len(contributor_stats), dates["first"], dates["last"],
          datetime.now().isoformat(), repo_id))

    db.commit()
    db.close()

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\nIngested {commit_count} commits from {len(contributor_stats)} contributors in {elapsed:.1f}s")


def _flush_commits(db, commit_batch, file_batch):
    """Insert a batch of commits and their file changes."""
    for row in commit_batch:
        file_records = row[-1]  # pop stashed file records
        commit_data = row[:-1]
        try:
            cursor = db.execute("""
                INSERT OR IGNORE INTO git_commits
                (repo_id, hash, author_name, author_email, author_date, author_timezone,
                 committer_name, committer_email, commit_date, subject, body,
                 merge, files_changed, insertions, deletions, subsystems)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, commit_data)
            commit_id = cursor.lastrowid
            if commit_id and file_records:
                for fp, ct, ins, dels, sub in file_records:
                    db.execute("""
                        INSERT INTO git_file_changes (commit_id, file_path, change_type, insertions, deletions, subsystem)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (commit_id, fp, ct, ins, dels, sub))
        except sqlite3.IntegrityError:
            pass  # duplicate commit hash, skip
    db.commit()


def cmd_contributors(args):
    """List contributors with commit counts and subsystem focus."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]

    if args.subsystem:
        # Filter to contributors who touched a specific subsystem
        rows = db.execute("""
            SELECT gc.author_email, gc.author_name,
                   COUNT(DISTINCT gc.id) as commit_count,
                   MIN(gc.author_date) as first_commit,
                   MAX(gc.author_date) as last_commit,
                   SUM(gfc.insertions) as total_ins,
                   SUM(gfc.deletions) as total_del
            FROM git_commits gc
            JOIN git_file_changes gfc ON gfc.commit_id = gc.id
            WHERE gc.repo_id = ? AND gfc.subsystem = ?
            GROUP BY gc.author_email
            ORDER BY commit_count DESC
        """, (repo_id, args.subsystem)).fetchall()
    else:
        rows = db.execute("""
            SELECT email, name, commit_count, first_commit_date, last_commit_date, primary_subsystems
            FROM git_contributors WHERE repo_id = ?
            ORDER BY commit_count DESC
        """, (repo_id,)).fetchall()

    if args.limit:
        rows = rows[:args.limit]

    results = []
    for r in rows:
        entry = dict(r)
        # Parse timezone from commits if available
        if not args.subsystem:
            tz_row = db.execute("""
                SELECT author_timezone, COUNT(*) as cnt FROM git_commits
                WHERE repo_id = ? AND author_email = ? AND author_timezone IS NOT NULL
                GROUP BY author_timezone ORDER BY cnt DESC LIMIT 1
            """, (repo_id, r["email"])).fetchone()
            if tz_row:
                offset_hrs = tz_row["author_timezone"] / 3600
                entry["primary_timezone"] = f"UTC{offset_hrs:+.0f}"
        results.append(entry)

    if write_output(results, args, summary=f"contributors for {args.repo}"):
        return

    sub_label = f" [{args.subsystem}]" if args.subsystem else ""
    print(f"\nContributors for {args.repo}{sub_label} ({len(results)} total):\n")
    for r in results:
        name = r.get("name") or r.get("author_name", "?")
        email = r.get("email") or r.get("author_email", "?")
        count = r.get("commit_count", 0)
        first = (r.get("first_commit_date") or r.get("first_commit", "?"))[:10]
        last = (r.get("last_commit_date") or r.get("last_commit", "?"))[:10]
        tz = r.get("primary_timezone", "")
        subs = ""
        if "primary_subsystems" in r and r["primary_subsystems"]:
            try:
                subs = ", ".join(json.loads(r["primary_subsystems"])[:3])
            except (json.JSONDecodeError, TypeError):
                pass
        tz_str = f"  {tz}" if tz else ""
        sub_str = f"  [{subs}]" if subs else ""
        print(f"  {count:>5}  {name} <{email}>  ({first} -> {last}){tz_str}{sub_str}")

    db.close()


def cmd_timeline(args):
    """Show commit activity over time for a subsystem or author."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]
    conditions = ["gc.repo_id = ?"]
    params = [repo_id]

    if args.subsystem:
        conditions.append("gfc.subsystem = ?")
        params.append(args.subsystem)
    if args.author:
        conditions.append("(gc.author_name LIKE ? OR gc.author_email LIKE ?)")
        params.extend([f"%{args.author}%", f"%{args.author}%"])
    if args.start:
        conditions.append("gc.author_date >= ?")
        params.append(args.start)
    if args.end:
        conditions.append("gc.author_date <= ?")
        params.append(args.end)

    where = " AND ".join(conditions)

    if args.subsystem:
        query = f"""
            SELECT strftime('%Y-%m', gc.author_date) as month,
                   COUNT(DISTINCT gc.id) as commits,
                   COUNT(DISTINCT gc.author_email) as authors,
                   SUM(gfc.insertions) as ins,
                   SUM(gfc.deletions) as del_lines
            FROM git_commits gc
            JOIN git_file_changes gfc ON gfc.commit_id = gc.id
            WHERE {where}
            GROUP BY month ORDER BY month
        """
    else:
        query = f"""
            SELECT strftime('%Y-%m', author_date) as month,
                   COUNT(*) as commits,
                   COUNT(DISTINCT author_email) as authors,
                   SUM(insertions) as ins,
                   SUM(deletions) as del_lines
            FROM git_commits gc
            WHERE {where}
            GROUP BY month ORDER BY month
        """

    rows = db.execute(query, params).fetchall()
    results = [dict(r) for r in rows]

    if write_output(results, args, summary=f"timeline for {args.repo}"):
        return

    filters = []
    if args.subsystem:
        filters.append(f"subsystem={args.subsystem}")
    if args.author:
        filters.append(f"author={args.author}")
    filter_str = f" ({', '.join(filters)})" if filters else ""

    print(f"\nCommit timeline for {args.repo}{filter_str}:\n")
    print(f"  {'Month':<10} {'Commits':>8} {'Authors':>8} {'Lines+':>8} {'Lines-':>8}")
    print(f"  {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}")
    for r in results:
        print(f"  {r['month']:<10} {r['commits']:>8} {r['authors']:>8} {r['ins'] or 0:>8} {r['del_lines'] or 0:>8}")

    db.close()


def cmd_activity(args):
    """Show a specific author's commit activity over time."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]

    rows = db.execute("""
        SELECT strftime('%Y-%m', author_date) as month,
               COUNT(*) as commits,
               SUM(insertions) as ins,
               SUM(deletions) as del_lines,
               GROUP_CONCAT(DISTINCT json_each.value) as subsystems
        FROM git_commits, json_each(subsystems)
        WHERE repo_id = ? AND (author_name LIKE ? OR author_email LIKE ?)
        GROUP BY month ORDER BY month
    """, (repo_id, f"%{args.author}%", f"%{args.author}%")).fetchall()

    results = [dict(r) for r in rows]

    if write_output(results, args, summary=f"activity for {args.author}"):
        return

    print(f"\nActivity for '{args.author}' in {args.repo}:\n")
    print(f"  {'Month':<10} {'Commits':>8} {'Lines+':>8} {'Lines-':>8}  Subsystems")
    print(f"  {'─' * 10} {'─' * 8} {'─' * 8} {'─' * 8}  {'─' * 30}")
    for r in results:
        subs = r["subsystems"] or ""
        # Deduplicate subsystem list
        unique_subs = sorted(set(subs.split(","))) if subs else []
        print(f"  {r['month']:<10} {r['commits']:>8} {r['ins'] or 0:>8} {r['del_lines'] or 0:>8}  {', '.join(unique_subs)}")

    db.close()


def cmd_hotspots(args):
    """Find anomalous commit activity windows — bursts of security-sensitive changes."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]
    conditions = ["gc.repo_id = ?"]
    params = [repo_id]

    if args.start:
        conditions.append("gc.author_date >= ?")
        params.append(args.start)
    if args.end:
        conditions.append("gc.author_date <= ?")
        params.append(args.end)
    if args.security_only:
        conditions.append("gfc.subsystem IN ('tls_ssl', 'auth', 'crypto', 'connection')")

    where = " AND ".join(conditions)

    rows = db.execute(f"""
        SELECT gc.hash, gc.author_name, gc.author_email, gc.author_date,
               gc.author_timezone, gc.subject,
               gc.insertions, gc.deletions, gc.subsystems,
               GROUP_CONCAT(DISTINCT gfc.subsystem) as touched_subsystems
        FROM git_commits gc
        JOIN git_file_changes gfc ON gfc.commit_id = gc.id
        WHERE {where}
        GROUP BY gc.id
        ORDER BY gc.author_date
    """, params).fetchall()

    results = [dict(r) for r in rows]

    if write_output(results, args, summary=f"hotspots for {args.repo}"):
        return

    # Group by day for display
    by_day = defaultdict(list)
    for r in results:
        day = r["author_date"][:10] if r["author_date"] else "unknown"
        by_day[day].append(r)

    sec_flag = " [security-sensitive only]" if args.security_only else ""
    date_range = ""
    if args.start or args.end:
        date_range = f" ({args.start or '...'} to {args.end or '...'})"
    print(f"\nCommit hotspots for {args.repo}{date_range}{sec_flag}:\n")

    for day, commits in sorted(by_day.items()):
        subsystems = set()
        for c in commits:
            if c["touched_subsystems"]:
                subsystems.update(c["touched_subsystems"].split(","))
        security_subs = subsystems & {"tls_ssl", "auth", "crypto", "connection"}
        flag = " *** SECURITY-SENSITIVE ***" if security_subs else ""
        print(f"  {day}  ({len(commits)} commits){flag}")
        for c in commits:
            tz = ""
            if c["author_timezone"]:
                offset_hrs = c["author_timezone"] / 3600
                tz = f" [UTC{offset_hrs:+.0f}]"
            print(f"    {c['hash'][:8]}  {c['author_name']}{tz}  {c['subject'][:70]}")
            if c["touched_subsystems"]:
                print(f"             subsystems: {c['touched_subsystems']}")

    db.close()


def cmd_subsystem_authors(args):
    """Show who has touched a specific subsystem — ranked by commit count."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]
    rows = db.execute("""
        SELECT gc.author_name, gc.author_email, gc.author_timezone,
               COUNT(DISTINCT gc.id) as commits,
               SUM(gfc.insertions) as ins,
               SUM(gfc.deletions) as del_lines,
               MIN(gc.author_date) as first_touch,
               MAX(gc.author_date) as last_touch
        FROM git_commits gc
        JOIN git_file_changes gfc ON gfc.commit_id = gc.id
        WHERE gc.repo_id = ? AND gfc.subsystem = ?
        GROUP BY gc.author_email
        ORDER BY commits DESC
    """, (repo_id, args.subsystem)).fetchall()

    results = [dict(r) for r in rows]

    if write_output(results, args, summary=f"{args.subsystem} authors for {args.repo}"):
        return

    level = security_level_for_subsystem(args.subsystem)
    print(f"\nAuthors touching '{args.subsystem}' [{level}] in {args.repo} ({len(results)} contributors):\n")
    print(f"  {'Commits':>8} {'Lines+':>8} {'Lines-':>8}  {'First':>10}  {'Last':>10}  Author")
    print(f"  {'─' * 8} {'─' * 8} {'─' * 8}  {'─' * 10}  {'─' * 10}  {'─' * 30}")
    for r in results:
        tz = ""
        if r["author_timezone"]:
            offset_hrs = r["author_timezone"] / 3600
            tz = f" [UTC{offset_hrs:+.0f}]"
        first = r["first_touch"][:10] if r["first_touch"] else "?"
        last = r["last_touch"][:10] if r["last_touch"] else "?"
        print(f"  {r['commits']:>8} {r['ins'] or 0:>8} {r['del_lines'] or 0:>8}  {first:>10}  {last:>10}  {r['author_name']}{tz}")

    db.close()


def cmd_correlate(args):
    """Correlate commit activity with investigation event timeline."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]
    days = args.days or 14

    # Load events from investigation.db
    if not INVESTIGATION_DB.exists():
        print("ERROR: investigation.db not found. Seed events first.")
        sys.exit(1)

    inv_db = sqlite3.connect(str(INVESTIGATION_DB))
    inv_db.row_factory = sqlite3.Row

    profile = _get_active_profile()
    if profile:
        events = inv_db.execute(
            "SELECT event_date as date, event_name as name, category FROM event_timeline WHERE profile_id = ? ORDER BY event_date",
            (profile,),
        ).fetchall()
    else:
        events = inv_db.execute(
            "SELECT event_date as date, event_name as name, category FROM event_timeline ORDER BY event_date"
        ).fetchall()
    inv_db.close()

    if not events:
        print("No events in timeline. Run 'event_timeline.py seed' first.")
        return

    results = []
    for event in events:
        event_date = event["date"]
        window_start = (datetime.fromisoformat(event_date) - timedelta(days=days)).isoformat()
        window_end = (datetime.fromisoformat(event_date) + timedelta(days=days)).isoformat()

        commits = db.execute("""
            SELECT COUNT(*) as total_commits,
                   COUNT(DISTINCT author_email) as unique_authors,
                   SUM(insertions) as total_ins,
                   SUM(deletions) as total_del
            FROM git_commits
            WHERE repo_id = ? AND author_date BETWEEN ? AND ?
        """, (repo_id, window_start, window_end)).fetchone()

        security_commits = db.execute("""
            SELECT COUNT(DISTINCT gc.id) as sec_commits
            FROM git_commits gc
            JOIN git_file_changes gfc ON gfc.commit_id = gc.id
            WHERE gc.repo_id = ? AND gc.author_date BETWEEN ? AND ?
              AND gfc.subsystem IN ('tls_ssl', 'auth', 'crypto', 'connection')
        """, (repo_id, window_start, window_end)).fetchone()

        results.append({
            "event_date": event_date,
            "event_name": event["name"],
            "event_category": event["category"],
            "window_days": days,
            "total_commits": commits["total_commits"],
            "unique_authors": commits["unique_authors"],
            "total_insertions": commits["total_ins"],
            "total_deletions": commits["total_del"],
            "security_commits": security_commits["sec_commits"],
        })

    if write_output(results, args, summary=f"correlations for {args.repo}"):
        return

    print(f"\nEvent-commit correlation for {args.repo} (window: +/- {days} days):\n")
    print(f"  {'Date':<12} {'Commits':>8} {'SecCmts':>8} {'Authors':>8}  Event")
    print(f"  {'─' * 12} {'─' * 8} {'─' * 8} {'─' * 8}  {'─' * 50}")
    for r in results:
        flag = " ***" if r["security_commits"] > 0 else ""
        print(f"  {r['event_date']:<12} {r['total_commits']:>8} {r['security_commits']:>8} {r['unique_authors']:>8}  {r['event_name'][:50]}{flag}")

    db.close()


def cmd_stats(args):
    """Show repository statistics."""
    db = get_db()
    repo_row = _get_repo(db, args.repo)
    if not repo_row:
        return

    repo_id = repo_row["id"]

    total = db.execute("SELECT COUNT(*) as n FROM git_commits WHERE repo_id = ?", (repo_id,)).fetchone()["n"]
    contributors = db.execute("SELECT COUNT(*) as n FROM git_contributors WHERE repo_id = ?", (repo_id,)).fetchone()["n"]
    merges = db.execute("SELECT COUNT(*) as n FROM git_commits WHERE repo_id = ? AND merge = 1", (repo_id,)).fetchone()["n"]

    subsystem_counts = db.execute("""
        SELECT gfc.subsystem, COUNT(DISTINCT gc.id) as commits
        FROM git_commits gc
        JOIN git_file_changes gfc ON gfc.commit_id = gc.id
        WHERE gc.repo_id = ?
        GROUP BY gfc.subsystem ORDER BY commits DESC
    """, (repo_id,)).fetchall()

    # Timezone distribution
    tz_dist = db.execute("""
        SELECT author_timezone, COUNT(*) as cnt FROM git_commits
        WHERE repo_id = ? AND author_timezone IS NOT NULL
        GROUP BY author_timezone ORDER BY cnt DESC LIMIT 10
    """, (repo_id,)).fetchall()

    stats = {
        "repo": args.repo,
        "total_commits": total,
        "total_contributors": contributors,
        "merge_commits": merges,
        "first_commit": repo_row["first_commit_date"],
        "last_commit": repo_row["last_commit_date"],
        "subsystems": {r["subsystem"]: r["commits"] for r in subsystem_counts},
        "timezone_distribution": {
            f"UTC{r['author_timezone']/3600:+.0f}": r["cnt"] for r in tz_dist
        },
    }

    if write_output(stats, args, summary=f"stats for {args.repo}"):
        return

    print(f"\nRepository: {args.repo}")
    print(f"  Commits: {total} ({merges} merges)")
    print(f"  Contributors: {contributors}")
    print(f"  Date range: {repo_row['first_commit_date'][:10] if repo_row['first_commit_date'] else '?'} -> {repo_row['last_commit_date'][:10] if repo_row['last_commit_date'] else '?'}")
    print(f"\n  Subsystem commit counts:")
    for r in subsystem_counts:
        level = security_level_for_subsystem(r["subsystem"])
        flag = f" [{level}]" if level in ("CRITICAL", "HIGH") else ""
        print(f"    {r['subsystem']:<20} {r['commits']:>6}{flag}")
    print(f"\n  Timezone distribution:")
    for r in tz_dist:
        offset_hrs = r["author_timezone"] / 3600
        print(f"    UTC{offset_hrs:+.0f}: {r['cnt']} commits")

    db.close()


# ── Helpers ───────────────────────────────────────────────────────────

def _get_repo(db, name):
    """Look up a repo by name. Print error and return None if not found."""
    row = db.execute("SELECT * FROM git_repos WHERE name = ?", (name,)).fetchone()
    if not row:
        repos = db.execute("SELECT name FROM git_repos").fetchall()
        print(f"ERROR: Repo '{name}' not found.", file=sys.stderr)
        if repos:
            print(f"  Available repos: {', '.join(r['name'] for r in repos)}")
        else:
            print("  No repos registered. Use 'clone' to add one.")
        sys.exit(1)
    return row


def _get_active_profile():
    """Get the active investigation profile name from investigation.db."""
    if not INVESTIGATION_DB.exists():
        return None
    try:
        inv_db = sqlite3.connect(str(INVESTIGATION_DB))
        row = inv_db.execute(
            "SELECT value FROM investigation_config WHERE key = 'active_profile'"
        ).fetchone()
        inv_db.close()
        return row[0] if row else None
    except Exception:
        return None


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Git repository analysis for OSINT investigations",
    )
    sub = parser.add_subparsers(dest="command")

    # clone
    p_clone = sub.add_parser("clone", help="Clone a git repository")
    p_clone.add_argument("url", help="Git repository URL")
    p_clone.add_argument("--name", help="Short name for the repo (default: derived from URL)")

    # ingest
    p_ingest = sub.add_parser("ingest", help="Parse commits into database")
    p_ingest.add_argument("--repo", required=True, help="Repo name")
    p_ingest.add_argument("--append", action="store_true", help="Append instead of replacing")

    # contributors
    p_contrib = sub.add_parser("contributors", help="List contributors")
    p_contrib.add_argument("--repo", required=True)
    p_contrib.add_argument("--subsystem", help="Filter by subsystem")
    p_contrib.add_argument("--limit", type=int, help="Max results")
    add_output_args(p_contrib)

    # timeline
    p_timeline = sub.add_parser("timeline", help="Commit activity over time")
    p_timeline.add_argument("--repo", required=True)
    p_timeline.add_argument("--subsystem", help="Filter by subsystem")
    p_timeline.add_argument("--author", help="Filter by author name/email")
    p_timeline.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_timeline.add_argument("--end", help="End date (YYYY-MM-DD)")
    add_output_args(p_timeline)

    # activity
    p_activity = sub.add_parser("activity", help="Author activity over time")
    p_activity.add_argument("--repo", required=True)
    p_activity.add_argument("--author", required=True, help="Author name or email substring")
    add_output_args(p_activity)

    # hotspots
    p_hotspots = sub.add_parser("hotspots", help="Find anomalous commit windows")
    p_hotspots.add_argument("--repo", required=True)
    p_hotspots.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_hotspots.add_argument("--end", help="End date (YYYY-MM-DD)")
    p_hotspots.add_argument("--security-only", action="store_true", help="Only security-sensitive subsystems")
    add_output_args(p_hotspots)

    # subsystem-authors
    p_sub_auth = sub.add_parser("subsystem-authors", help="Who touches a subsystem")
    p_sub_auth.add_argument("--repo", required=True)
    p_sub_auth.add_argument("--subsystem", required=True)
    add_output_args(p_sub_auth)

    # correlate
    p_corr = sub.add_parser("correlate", help="Correlate commits with event timeline")
    p_corr.add_argument("--repo", required=True)
    p_corr.add_argument("--days", type=int, default=14, help="Window size in days (default: 14)")
    add_output_args(p_corr)

    # stats
    p_stats = sub.add_parser("stats", help="Repository statistics")
    p_stats.add_argument("--repo", required=True)
    add_output_args(p_stats)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "clone": cmd_clone,
        "ingest": cmd_ingest,
        "contributors": cmd_contributors,
        "timeline": cmd_timeline,
        "activity": cmd_activity,
        "hotspots": cmd_hotspots,
        "subsystem-authors": cmd_subsystem_authors,
        "correlate": cmd_correlate,
        "stats": cmd_stats,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
