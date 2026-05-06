#!/usr/bin/env python3
"""
Git contributor network analysis for OSINT investigations.

Builds contributor relationship graphs from shared file edits, analyzes email
domain clustering, tracks contributor on/offboarding, and computes influence
metrics. Works with data ingested by analyze_git_repo.py.

Usage:
    python tools/git_contributor_network.py coauthors --repo nginx
    python tools/git_contributor_network.py file-overlap --repo nginx --subsystem tls_ssl
    python tools/git_contributor_network.py domain-analysis --repo nginx
    python tools/git_contributor_network.py influence --repo nginx
    python tools/git_contributor_network.py transitions --repo nginx
    python tools/git_contributor_network.py transitions --repo nginx --start 2019-01 --end 2020-01
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from output_util import add_output_args, write_output

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "git_analysis.db"


def get_db():
    """Open the git analysis database (read-only)."""
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run analyze_git_repo.py first.", file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    return db


def _get_repo_id(db, name):
    """Look up repo by name, return id or exit."""
    row = db.execute("SELECT id FROM git_repos WHERE name = ?", (name,)).fetchone()
    if not row:
        repos = db.execute("SELECT name FROM git_repos").fetchall()
        print(f"ERROR: Repo '{name}' not found.", file=sys.stderr)
        if repos:
            print(f"  Available: {', '.join(r['name'] for r in repos)}")
        sys.exit(1)
    return row["id"]


# ── Commands ──────────────────────────────────────────────────────────

def cmd_coauthors(args):
    """Build co-authorship network: contributors who edited the same files."""
    db = get_db()
    repo_id = _get_repo_id(db, args.repo)
    min_shared = args.min_shared or 3

    # Find pairs of contributors who edited the same files
    rows = db.execute("""
        SELECT a.author_email as email_a, b.author_email as email_b,
               COUNT(DISTINCT fa.file_path) as shared_files,
               GROUP_CONCAT(DISTINCT fa.subsystem) as shared_subsystems
        FROM git_file_changes fa
        JOIN git_commits ca ON ca.id = fa.commit_id AND ca.repo_id = ?
        JOIN git_file_changes fb ON fb.file_path = fa.file_path AND fb.commit_id != fa.commit_id
        JOIN git_commits cb ON cb.id = fb.commit_id AND cb.repo_id = ?
        WHERE a.author_email < b.author_email
          AND ca.author_email != cb.author_email
        GROUP BY a.author_email, b.author_email
        HAVING shared_files >= ?
        ORDER BY shared_files DESC
    """, (repo_id, repo_id, min_shared)).fetchall()

    # The above query is too slow for large repos. Use a simpler approach:
    # Build file -> authors mapping, then compute pairwise overlaps.
    file_authors = defaultdict(set)
    file_subsystems = {}

    rows_raw = db.execute("""
        SELECT gfc.file_path, gfc.subsystem, gc.author_email
        FROM git_file_changes gfc
        JOIN git_commits gc ON gc.id = gfc.commit_id
        WHERE gc.repo_id = ?
    """, (repo_id,)).fetchall()

    for r in rows_raw:
        file_authors[r["file_path"]].add(r["author_email"])
        file_subsystems[r["file_path"]] = r["subsystem"]

    # Compute pairwise shared file counts
    pair_files = Counter()
    pair_subsystems = defaultdict(set)
    for fp, authors in file_authors.items():
        authors = sorted(authors)
        sub = file_subsystems.get(fp, "other")
        for i, a in enumerate(authors):
            for b in authors[i + 1:]:
                pair_files[(a, b)] += 1
                pair_subsystems[(a, b)].add(sub)

    results = []
    for (a, b), count in pair_files.most_common():
        if count < min_shared:
            break
        subs = sorted(pair_subsystems[(a, b)])
        results.append({
            "contributor_a": a,
            "contributor_b": b,
            "shared_files": count,
            "shared_subsystems": subs,
        })

    if args.limit:
        results = results[:args.limit]

    if write_output(results, args, summary=f"coauthor pairs for {args.repo}"):
        return

    print(f"\nCo-authorship network for {args.repo} (min {min_shared} shared files):\n")
    print(f"  {'Shared':>7}  Contributor A  <->  Contributor B  [Subsystems]")
    print(f"  {'─' * 7}  {'─' * 60}")
    for r in results[:50]:
        subs = ", ".join(r["shared_subsystems"][:3])
        print(f"  {r['shared_files']:>7}  {r['contributor_a']:<30}  {r['contributor_b']:<25}  [{subs}]")

    db.close()


def cmd_file_overlap(args):
    """Show which contributors edit the same files in a subsystem."""
    db = get_db()
    repo_id = _get_repo_id(db, args.repo)

    conditions = ["gc.repo_id = ?"]
    params = [repo_id]
    if args.subsystem:
        conditions.append("gfc.subsystem = ?")
        params.append(args.subsystem)

    where = " AND ".join(conditions)

    rows = db.execute(f"""
        SELECT gfc.file_path, gfc.subsystem,
               GROUP_CONCAT(DISTINCT gc.author_email) as authors,
               COUNT(DISTINCT gc.id) as total_commits,
               COUNT(DISTINCT gc.author_email) as author_count
        FROM git_file_changes gfc
        JOIN git_commits gc ON gc.id = gfc.commit_id
        WHERE {where}
        GROUP BY gfc.file_path
        HAVING author_count >= 2
        ORDER BY author_count DESC, total_commits DESC
    """, params).fetchall()

    results = [dict(r) for r in rows]
    if args.limit:
        results = results[:args.limit]

    if write_output(results, args, summary=f"file overlap for {args.repo}"):
        return

    sub_label = f" [{args.subsystem}]" if args.subsystem else ""
    print(f"\nMulti-author files for {args.repo}{sub_label} ({len(results)} files):\n")
    for r in results[:40]:
        authors = r["authors"].split(",")
        print(f"  {r['file_path']}")
        print(f"    {r['author_count']} authors, {r['total_commits']} commits  [{r['subsystem']}]")
        for a in authors[:5]:
            print(f"      - {a}")
        if len(authors) > 5:
            print(f"      ... and {len(authors) - 5} more")
        print()

    db.close()


def cmd_domain_analysis(args):
    """Analyze contributor email domains — institutional clustering."""
    db = get_db()
    repo_id = _get_repo_id(db, args.repo)

    rows = db.execute("""
        SELECT email, name, commit_count, first_commit_date, last_commit_date, primary_subsystems
        FROM git_contributors WHERE repo_id = ?
        ORDER BY commit_count DESC
    """, (repo_id,)).fetchall()

    # Group by email domain
    domain_groups = defaultdict(list)
    for r in rows:
        email = r["email"] or ""
        if "@" in email:
            domain = email.split("@")[1].lower()
        else:
            domain = "(no domain)"
        domain_groups[domain].append(dict(r))

    # Sort domains by total commits
    domain_stats = []
    for domain, contributors in domain_groups.items():
        total = sum(c["commit_count"] for c in contributors)
        # Collect subsystems across all contributors
        all_subs = Counter()
        for c in contributors:
            try:
                subs = json.loads(c["primary_subsystems"] or "[]")
                for s in subs:
                    all_subs[s] += 1
            except (json.JSONDecodeError, TypeError):
                pass
        domain_stats.append({
            "domain": domain,
            "contributors": len(contributors),
            "total_commits": total,
            "top_subsystems": [s for s, _ in all_subs.most_common(5)],
            "people": [{
                "name": c["name"],
                "email": c["email"],
                "commits": c["commit_count"],
                "active": f"{(c['first_commit_date'] or '?')[:10]} -> {(c['last_commit_date'] or '?')[:10]}",
            } for c in contributors],
        })

    domain_stats.sort(key=lambda x: x["total_commits"], reverse=True)

    if write_output(domain_stats, args, summary=f"domain analysis for {args.repo}"):
        return

    print(f"\nEmail domain analysis for {args.repo}:\n")
    for ds in domain_stats:
        subs = ", ".join(ds["top_subsystems"][:3])
        print(f"  @{ds['domain']}  ({ds['contributors']} people, {ds['total_commits']} commits)  [{subs}]")
        for p in ds["people"][:10]:
            print(f"    {p['commits']:>5}  {p['name']} <{p['email']}>  {p['active']}")
        if len(ds["people"]) > 10:
            print(f"    ... and {len(ds['people']) - 10} more")
        print()

    db.close()


def cmd_influence(args):
    """Compute influence metrics: who controls what code."""
    db = get_db()
    repo_id = _get_repo_id(db, args.repo)

    # For each contributor, compute:
    # - Total commits
    # - Subsystems touched (breadth)
    # - Security-sensitive commits (depth)
    # - Unique files touched (scope)
    # - Duration of activity (tenure)
    rows = db.execute("""
        SELECT gc.author_email, gc.author_name,
               COUNT(DISTINCT gc.id) as total_commits,
               COUNT(DISTINCT gfc.subsystem) as subsystem_breadth,
               COUNT(DISTINCT gfc.file_path) as unique_files,
               MIN(gc.author_date) as first_commit,
               MAX(gc.author_date) as last_commit
        FROM git_commits gc
        JOIN git_file_changes gfc ON gfc.commit_id = gc.id
        WHERE gc.repo_id = ?
        GROUP BY gc.author_email
    """, (repo_id,)).fetchall()

    # Security-sensitive commits per contributor
    sec_counts = {}
    sec_rows = db.execute("""
        SELECT gc.author_email, COUNT(DISTINCT gc.id) as sec_commits
        FROM git_commits gc
        JOIN git_file_changes gfc ON gfc.commit_id = gc.id
        WHERE gc.repo_id = ? AND gfc.subsystem IN ('tls_ssl', 'auth', 'crypto', 'connection')
        GROUP BY gc.author_email
    """, (repo_id,)).fetchall()
    for sr in sec_rows:
        sec_counts[sr["author_email"]] = sr["sec_commits"]

    results = []
    for r in rows:
        email = r["author_email"]
        first = r["first_commit"]
        last = r["last_commit"]

        # Tenure in years
        try:
            from datetime import datetime
            f = datetime.fromisoformat(first.replace("Z", "+00:00")) if first else None
            l = datetime.fromisoformat(last.replace("Z", "+00:00")) if last else None
            tenure_years = (l - f).days / 365.25 if f and l else 0
        except Exception:
            tenure_years = 0

        sec = sec_counts.get(email, 0)
        total = r["total_commits"]

        # Composite influence score:
        # commits * breadth * (1 + security_ratio) * log(tenure + 1)
        import math
        security_ratio = sec / total if total > 0 else 0
        score = total * r["subsystem_breadth"] * (1 + security_ratio * 2) * math.log(tenure_years + 1.1)

        results.append({
            "email": email,
            "name": r["author_name"],
            "total_commits": total,
            "subsystem_breadth": r["subsystem_breadth"],
            "unique_files": r["unique_files"],
            "security_commits": sec,
            "security_ratio": round(security_ratio, 3),
            "tenure_years": round(tenure_years, 1),
            "influence_score": round(score, 1),
        })

    results.sort(key=lambda x: x["influence_score"], reverse=True)
    if args.limit:
        results = results[:args.limit]

    if write_output(results, args, summary=f"influence metrics for {args.repo}"):
        return

    print(f"\nInfluence metrics for {args.repo}:\n")
    print(f"  {'Score':>8} {'Commits':>8} {'SecCmts':>8} {'Breadth':>8} {'Files':>6} {'Tenure':>7}  Contributor")
    print(f"  {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 6} {'─' * 7}  {'─' * 40}")
    for r in results[:30]:
        print(f"  {r['influence_score']:>8.1f} {r['total_commits']:>8} {r['security_commits']:>8} {r['subsystem_breadth']:>8} {r['unique_files']:>6} {r['tenure_years']:>6.1f}y  {r['name']} <{r['email']}>")

    db.close()


def cmd_transitions(args):
    """Track contributor on/offboarding over time — who started/stopped contributing."""
    db = get_db()
    repo_id = _get_repo_id(db, args.repo)

    rows = db.execute("""
        SELECT email, name, first_commit_date, last_commit_date, commit_count, primary_subsystems
        FROM git_contributors WHERE repo_id = ?
        ORDER BY first_commit_date
    """, (repo_id,)).fetchall()

    # Group by year-quarter for onboarding/offboarding
    onboard = defaultdict(list)
    offboard = defaultdict(list)

    for r in rows:
        first = r["first_commit_date"]
        last = r["last_commit_date"]
        if first:
            q = first[:7]  # YYYY-MM
            onboard[q].append(dict(r))
        if last:
            q = last[:7]
            offboard[q].append(dict(r))

    # Build timeline
    all_months = sorted(set(list(onboard.keys()) + list(offboard.keys())))

    # Filter by date range if specified
    if args.start:
        all_months = [m for m in all_months if m >= args.start]
    if args.end:
        all_months = [m for m in all_months if m <= args.end]

    results = []
    for month in all_months:
        joined = onboard.get(month, [])
        left = offboard.get(month, [])
        results.append({
            "month": month,
            "joined": [{"name": c["name"], "email": c["email"], "commits": c["commit_count"]} for c in joined],
            "left": [{"name": c["name"], "email": c["email"], "commits": c["commit_count"]} for c in left],
        })

    if write_output(results, args, summary=f"transitions for {args.repo}"):
        return

    print(f"\nContributor transitions for {args.repo}:\n")
    for r in results:
        if not r["joined"] and not r["left"]:
            continue
        print(f"  {r['month']}:")
        for j in r["joined"]:
            print(f"    + JOINED  {j['name']} <{j['email']}>  ({j['commits']} total commits)")
        for l in r["left"]:
            print(f"    - LEFT    {l['name']} <{l['email']}>  ({l['commits']} total commits)")

    db.close()


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Git contributor network analysis",
    )
    sub = parser.add_subparsers(dest="command")

    # coauthors
    p_co = sub.add_parser("coauthors", help="Co-authorship network from shared file edits")
    p_co.add_argument("--repo", required=True)
    p_co.add_argument("--min-shared", type=int, default=3, help="Min shared files (default: 3)")
    p_co.add_argument("--limit", type=int)
    add_output_args(p_co)

    # file-overlap
    p_fo = sub.add_parser("file-overlap", help="Multi-author files by subsystem")
    p_fo.add_argument("--repo", required=True)
    p_fo.add_argument("--subsystem", help="Filter by subsystem")
    p_fo.add_argument("--limit", type=int)
    add_output_args(p_fo)

    # domain-analysis
    p_da = sub.add_parser("domain-analysis", help="Email domain clustering")
    p_da.add_argument("--repo", required=True)
    add_output_args(p_da)

    # influence
    p_inf = sub.add_parser("influence", help="Contributor influence metrics")
    p_inf.add_argument("--repo", required=True)
    p_inf.add_argument("--limit", type=int)
    add_output_args(p_inf)

    # transitions
    p_tr = sub.add_parser("transitions", help="Contributor on/offboarding timeline")
    p_tr.add_argument("--repo", required=True)
    p_tr.add_argument("--start", help="Start month (YYYY-MM)")
    p_tr.add_argument("--end", help="End month (YYYY-MM)")
    add_output_args(p_tr)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "coauthors": cmd_coauthors,
        "file-overlap": cmd_file_overlap,
        "domain-analysis": cmd_domain_analysis,
        "influence": cmd_influence,
        "transitions": cmd_transitions,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
