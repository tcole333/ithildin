#!/usr/bin/env python3
"""Automated quality checks for curated dossiers.

Subcommands:
    check <slug>       Run all checks on one dossier (records to DB)
    batch [--top N]    Check all (or top N) curated dossiers (records to DB)
    fix <slug>         Auto-fix deterministic issues
    summary            Aggregate report table
    gate               Publish gate — exits non-zero if any FAIL verdict
    status             Show review status from DB
"""

import argparse
import json
import re
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DOSSIER_DIR = ROOT_DIR / "content" / "dossiers"
INDEX_PATH = DOSSIER_DIR / "_index.json"
DB_PATH = ROOT_DIR / "investigation.db"

# --- Banned phrases (from curate-dossier editorial standards) ---

# BLOCKING in titles/system_role
BANNED_TITLE_PHRASES = [
    "machine", "apparatus", "operative", "dark money", "pipeline",
]

# SHOULD_FIX in body text (unattributed usage)
BANNED_BODY_PATTERNS = [
    r"\braises?\s+questions?\b",
    r"\braises?\s+concerns?\b",
    r"\bstriking\b",
    r"\bextraordinary\b",
    r"\bremarkable\b",
    r"\bunprecedented\b",
    r"\bmost\s+significant\b",
    r"\bmost\s+consequential\b",
    r"\bmost\s+important\b",
]

# Valid viz values
VALID_VIZ = {None, "ego_network", "timeline"}

# Citation token patterns — match both bracket [EFTA...] and inline EFTA... formats
CITATION_RE = re.compile(
    r"(?:"
    r"EFTA\d{5,11}"
    r"|Finding\s*#\d+"
    r"|SEC[:\-]\S+"
    r"|EDGAR[:\-]\S+"
    r"|990[:\-]\d+"
    r"|ACRIS[:\-]\S+"
    r"|CL[:\-]\d+"
    r"|FEC[:\-]\S+"
    r"|FARA[:\-]\d+"
    r"|REG[:\-]\w{2}[:\-]\S+"
    r"|HOUSE_OVERSIGHT_\d+"
    r"|LMSBAND[:\-]\S+"
    r"|DOJ[:\-]\S+"
    r")"
)

# Attribution language patterns (for inference/synthesis)
ATTRIBUTION_RE = re.compile(
    r"(?:analysis\s+(?:of|indicates|suggests)|"
    r"cross-?reference\s+of|"
    r"(?:grant|fund|financial)\s+flow\s+analysis|"
    r"review\s+of\s+(?:the\s+)?(?:records?|filings?|documents?)|"
    r"examination\s+of|"
    r"according\s+to|"
    r"records?\s+(?:show|indicate|reveal)|"
    r"hypothesis\s+#?\d+\s+proposes?)",
    re.IGNORECASE,
)


# --- HTML helpers ---


class TextExtractor(HTMLParser):
    """Extract plain text and track linked names from HTML."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.links: dict[str, str] = {}  # slug -> anchor text
        self._in_link = False
        self._link_slug = ""
        self._link_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            m = re.match(r"/dossiers/([\w-]+)", href)
            if m:
                self._in_link = True
                self._link_slug = m.group(1)
                self._link_text = ""

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self.links[self._link_slug] = self._link_text.strip()
            self._in_link = False

    def handle_data(self, data):
        self.text_parts.append(data)
        if self._in_link:
            self._link_text += data

    @property
    def text(self):
        return "".join(self.text_parts)


def parse_html(html: str) -> TextExtractor:
    ext = TextExtractor()
    ext.feed(html or "")
    return ext


def extract_sentences(text: str) -> list[str]:
    """Split text into approximate sentences."""
    # Split on period/question/exclamation followed by space or end
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw if s.strip() and len(s.strip()) > 10]


# --- Check implementations ---


def load_index() -> dict[str, str]:
    """Return {name: slug} from _index.json."""
    entries = json.loads(INDEX_PATH.read_text())
    result = {}
    for e in entries:
        result[e["name"]] = e["slug"]
        # Also add any aliases if present in the dossier file
    return result


def load_dossier(slug: str) -> dict:
    path = DOSSIER_DIR / f"{slug}.json"
    if not path.exists():
        print(f"Error: dossier not found: {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def check_crosslinks(dossier: dict, name_to_slug: dict) -> list[dict]:
    """Check 1: Names in text that have dossiers but aren't linked."""
    issues = []
    slug = dossier["slug"]
    curation = dossier.get("curation", {})

    # Collect all HTML content blocks: lead + sections
    blocks = []
    if curation.get("lead"):
        blocks.append(("lead", curation["lead"]))
    for sec in curation.get("sections", []):
        blocks.append((f"section '{sec.get('title', sec.get('id', '?'))}'", sec.get("content", "")))

    for block_name, html in blocks:
        parsed = parse_html(html)
        linked_slugs = set(parsed.links.keys())
        text = parsed.text

        for name, target_slug in name_to_slug.items():
            if target_slug == slug:
                continue  # Skip self
            if target_slug in linked_slugs:
                continue  # Already linked

            # Word boundary match, handle possessives
            pattern = re.compile(r"\b" + re.escape(name) + r"(?:'s?)?\b")
            if pattern.search(text):
                # Verify it's not a substring false positive by checking
                # the match is the full name (not part of a longer name)
                issues.append({
                    "check": "crosslinks",
                    "severity": "SHOULD_FIX",
                    "detail": f"{name} mentioned but not linked in {block_name}",
                    "fixable": True,
                    "fix_data": {"name": name, "slug": target_slug, "block": block_name},
                })

    return issues


def check_banned_phrases(dossier: dict) -> list[dict]:
    """Check 2: Banned phrase scan."""
    issues = []
    curation = dossier.get("curation", {})

    # Check titles and system_role (BLOCKING)
    title_texts = []
    if curation.get("system_role"):
        title_texts.append(("system_role", curation["system_role"]))
    for sec in curation.get("sections", []):
        title_texts.append((f"section title '{sec.get('title', '')}'", sec.get("title", "")))

    for label, text in title_texts:
        lower = text.lower()
        for phrase in BANNED_TITLE_PHRASES:
            if phrase in lower:
                issues.append({
                    "check": "banned_phrases",
                    "severity": "BLOCKING",
                    "detail": f"Banned phrase '{phrase}' in {label}",
                    "fixable": label.startswith("section title"),
                })

    # Check body text (SHOULD_FIX)
    body_blocks = []
    if curation.get("lead"):
        body_blocks.append(("lead", curation["lead"]))
    for sec in curation.get("sections", []):
        body_blocks.append((f"section '{sec.get('title', sec.get('id'))}'", sec.get("content", "")))
    if curation.get("system_role"):
        body_blocks.append(("system_role", curation["system_role"]))

    for label, html in body_blocks:
        text = parse_html(html).text
        for pattern in BANNED_BODY_PATTERNS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for m in matches:
                # Get surrounding context
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 30)
                context = text[start:end].replace("\n", " ")
                issues.append({
                    "check": "banned_phrases",
                    "severity": "SHOULD_FIX",
                    "detail": f"Banned pattern '{m.group()}' in {label}: ...{context}...",
                    "fixable": False,
                })

    return issues


def check_structure(dossier: dict) -> list[dict]:
    """Check 3: Structure validation."""
    issues = []
    curation = dossier.get("curation", {})

    if not curation.get("lead"):
        issues.append({
            "check": "structure",
            "severity": "BLOCKING",
            "detail": "Missing lead",
            "fixable": False,
        })

    if not curation.get("sections"):
        issues.append({
            "check": "structure",
            "severity": "BLOCKING",
            "detail": "No sections defined",
            "fixable": False,
        })

    for sec in curation.get("sections", []):
        content = sec.get("content", "")
        title = sec.get("title", sec.get("id", "unknown"))

        # Check for HTML lists (should be prose)
        if re.search(r"<(?:ul|ol)\b", content):
            issues.append({
                "check": "structure",
                "severity": "SHOULD_FIX",
                "detail": f"Section '{title}' contains <ul>/<ol> — should be prose",
                "fixable": False,
            })

        # Check viz values
        viz = sec.get("viz")
        if viz not in VALID_VIZ:
            issues.append({
                "check": "structure",
                "severity": "BLOCKING",
                "detail": f"Section '{title}' has invalid viz value: {viz!r}",
                "fixable": False,
            })

    return issues


def check_citations(dossier: dict) -> list[dict]:
    """Check 4: Citation coverage — % of factual sentences with inline citations."""
    issues = []
    curation = dossier.get("curation", {})
    total_sentences = 0
    cited_sentences = 0
    orphan_citations = []

    # Collect all finding IDs for orphan check
    finding_ids = {f["id"] for f in dossier.get("findings", [])}

    blocks = []
    if curation.get("lead"):
        blocks.append(("lead", curation["lead"]))
    for sec in curation.get("sections", []):
        blocks.append((sec.get("title", sec.get("id")), sec.get("content", "")))

    for label, html in blocks:
        if not html:
            continue
        # Work with raw HTML to preserve citation tokens
        text = parse_html(html).text
        sentences = extract_sentences(text)

        for sent in sentences:
            total_sentences += 1
            if CITATION_RE.search(sent):
                cited_sentences += 1

        # Check for orphan Finding citations (bracket or inline)
        for m in re.finditer(r"Finding\s*#(\d+)", html):
            fid = int(m.group(1))
            if fid not in finding_ids:
                orphan_citations.append(f"Finding #{fid} in {label}")

    coverage = (cited_sentences / total_sentences * 100) if total_sentences > 0 else 0

    if coverage < 50:
        issues.append({
            "check": "citations",
            "severity": "BLOCKING",
            "detail": f"Citation coverage {coverage:.1f}% (< 50% threshold, {cited_sentences}/{total_sentences} sentences)",
            "fixable": False,
        })
    elif coverage < 80:
        issues.append({
            "check": "citations",
            "severity": "SHOULD_FIX",
            "detail": f"Citation coverage {coverage:.1f}% (< 80% target, {cited_sentences}/{total_sentences} sentences)",
            "fixable": False,
        })

    for orphan in orphan_citations:
        issues.append({
            "check": "citations",
            "severity": "SHOULD_FIX",
            "detail": f"Orphan citation: {orphan} — not in dossier findings",
            "fixable": False,
        })

    return issues, {"supported_pct": round(coverage, 1), "orphan_citations": len(orphan_citations)}


def check_claim_compliance(dossier: dict) -> list[dict]:
    """Check 5: Inference/synthesis findings cited without attribution language."""
    issues = []
    curation = dossier.get("curation", {})

    # Build map of finding_id -> claim_type
    claim_map = {}
    for f in dossier.get("findings", []):
        claim_map[f["id"]] = f.get("claim_type", "")

    blocks = []
    if curation.get("lead"):
        blocks.append(("lead", curation["lead"]))
    for sec in curation.get("sections", []):
        blocks.append((sec.get("title", sec.get("id")), sec.get("content", "")))

    for label, html in blocks:
        if not html:
            continue
        text = parse_html(html).text
        sentences = extract_sentences(text)

        for sent in sentences:
            # Find Finding references in this sentence (bracket or inline)
            finding_refs = re.findall(r"Finding\s*#(\d+)", sent)
            for ref in finding_refs:
                fid = int(ref)
                claim_type = claim_map.get(fid, "")
                if claim_type in ("inference", "synthesis"):
                    # Check if sentence has attribution language
                    if not ATTRIBUTION_RE.search(sent):
                        issues.append({
                            "check": "claim_compliance",
                            "severity": "SHOULD_FIX",
                            "detail": f"{claim_type} Finding #{fid} cited without attribution language in {label}",
                            "fixable": False,
                        })

    return issues


def check_outbound_links(dossier: dict) -> list[dict]:
    """Check 6: Flag if < 5 outbound cross-links."""
    issues = []
    curation = dossier.get("curation", {})
    all_linked_slugs = set()

    blocks = []
    if curation.get("lead"):
        blocks.append(curation["lead"])
    for sec in curation.get("sections", []):
        blocks.append(sec.get("content", ""))

    for html in blocks:
        parsed = parse_html(html)
        all_linked_slugs.update(parsed.links.keys())

    count = len(all_linked_slugs)
    if count < 5:
        issues.append({
            "check": "outbound_links",
            "severity": "SUGGESTION",
            "detail": f"Only {count} outbound cross-links (recommend >= 5)",
            "fixable": False,
        })

    return issues, count


# --- Fix implementation ---


def fix_crosslinks(dossier: dict, name_to_slug: dict) -> tuple[dict, int]:
    """Insert missing cross-links on first mention per section."""
    slug = dossier["slug"]
    curation = dossier.get("curation", {})
    fix_count = 0

    def add_links_to_html(html: str, skip_slugs: set | None = None) -> tuple[str, set]:
        """Add dossier links to first unlinked mention of each name."""
        nonlocal fix_count
        if not html:
            return html, set()

        parsed = parse_html(html)
        already_linked = set(parsed.links.keys())
        if skip_slugs:
            already_linked |= skip_slugs

        linked_this_block = set()

        for name, target_slug in sorted(name_to_slug.items(), key=lambda x: -len(x[0])):
            if target_slug == slug:
                continue
            if target_slug in already_linked or target_slug in linked_this_block:
                continue

            # Only replace if the name appears outside of existing <a> tags
            # Use a pattern that matches the name at a word boundary, not inside a tag
            pattern = re.compile(
                r"(?<![/>\"=])\b(" + re.escape(name) + r")\b(?![^<]*</a>)",
            )

            # Only replace first occurrence
            new_html, n = pattern.subn(
                f'<a href="/dossiers/{target_slug}">\\1</a>',
                html,
                count=1,
            )
            if n > 0:
                # Verify we didn't insert inside an existing tag attribute
                # Quick sanity: make sure the replacement isn't inside an href/src
                if f'"{name}"' not in new_html.split(f"/dossiers/{target_slug}")[0][-50:]:
                    html = new_html
                    linked_this_block.add(target_slug)
                    fix_count += 1

        return html, linked_this_block

    # Fix lead
    if curation.get("lead"):
        curation["lead"], _ = add_links_to_html(curation["lead"])

    # Fix each section independently (first mention per section)
    for sec in curation.get("sections", []):
        if sec.get("content"):
            sec["content"], _ = add_links_to_html(sec["content"])

    dossier["curation"] = curation
    return dossier, fix_count


def fix_banned_titles(dossier: dict) -> tuple[dict, int]:
    """Remove banned phrases from section titles and system_role."""
    curation = dossier.get("curation", {})
    fix_count = 0

    # Fix system_role
    if curation.get("system_role"):
        sr = curation["system_role"]
        for phrase in BANNED_TITLE_PHRASES:
            if phrase in sr.lower():
                # Can't safely auto-replace in system_role — flag only
                pass

    # Fix section titles
    for sec in curation.get("sections", []):
        title = sec.get("title", "")
        lower = title.lower()
        for phrase in BANNED_TITLE_PHRASES:
            if phrase in lower:
                # Remove the banned word (context-dependent, so conservative)
                new_title = re.sub(
                    r"\b" + re.escape(phrase) + r"\b",
                    "",
                    title,
                    flags=re.IGNORECASE,
                )
                # Clean up double spaces and leading/trailing
                new_title = re.sub(r"\s+", " ", new_title).strip()
                if new_title and new_title != title:
                    sec["title"] = new_title
                    fix_count += 1

    dossier["curation"] = curation
    return dossier, fix_count


# --- Main check orchestrator ---


def run_checks(slug: str, name_to_slug: dict | None = None) -> dict:
    """Run all checks on a dossier and return structured result."""
    dossier = load_dossier(slug)
    curation = dossier.get("curation", {})

    if not curation.get("lead"):
        return {
            "slug": slug,
            "name": dossier.get("name", slug),
            "verdict": "SKIP",
            "detail": "Not curated",
            "blocking": [],
            "should_fix": [],
            "suggestions": [],
            "metrics": {},
        }

    if name_to_slug is None:
        name_to_slug = load_index()

    all_issues = []

    # Check 1: Cross-links
    all_issues.extend(check_crosslinks(dossier, name_to_slug))

    # Check 2: Banned phrases
    all_issues.extend(check_banned_phrases(dossier))

    # Check 3: Structure
    all_issues.extend(check_structure(dossier))

    # Check 4: Citations
    citation_issues, citation_metrics = check_citations(dossier)
    all_issues.extend(citation_issues)

    # Check 5: Claim compliance
    all_issues.extend(check_claim_compliance(dossier))

    # Check 6: Outbound links
    link_issues, outbound_count = check_outbound_links(dossier)
    all_issues.extend(link_issues)

    # Categorize
    blocking = [i for i in all_issues if i["severity"] == "BLOCKING"]
    should_fix = [i for i in all_issues if i["severity"] == "SHOULD_FIX"]
    suggestions = [i for i in all_issues if i["severity"] == "SUGGESTION"]

    # Verdict
    if blocking:
        verdict = "FAIL"
    elif should_fix:
        verdict = "NEEDS_FIXES"
    else:
        verdict = "PASS"

    missing_crosslinks = sum(1 for i in all_issues if i["check"] == "crosslinks")
    banned_count = sum(1 for i in all_issues if i["check"] == "banned_phrases")

    return {
        "slug": slug,
        "name": dossier.get("name", slug),
        "verdict": verdict,
        "blocking": blocking,
        "should_fix": should_fix,
        "suggestions": suggestions,
        "metrics": {
            "supported_pct": citation_metrics.get("supported_pct", 0),
            "outbound_links": outbound_count,
            "orphan_citations": citation_metrics.get("orphan_citations", 0),
            "banned_phrases": banned_count,
            "missing_crosslinks": missing_crosslinks,
        },
    }


def get_curated_slugs(top_n: int | None = None) -> list[str]:
    """Return slugs of curated dossiers, sorted by finding count desc."""
    index = json.loads(INDEX_PATH.read_text())
    curated = []
    for entry in index:
        slug = entry["slug"]
        path = DOSSIER_DIR / f"{slug}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text())
        if d.get("curation", {}).get("lead"):
            total = entry.get("stats", {}).get("total_findings", 0)
            curated.append((slug, total))

    curated.sort(key=lambda x: -x[1])
    slugs = [s for s, _ in curated]
    if top_n:
        slugs = slugs[:top_n]
    return slugs


# --- DB tracking ---


def ensure_review_schema(db: sqlite3.Connection) -> None:
    """Create dossier_reviews table if it doesn't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS dossier_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            verdict TEXT NOT NULL CHECK(verdict IN ('PASS','NEEDS_FIXES','FAIL','SKIP')),
            blocking_count INTEGER NOT NULL DEFAULT 0,
            should_fix_count INTEGER NOT NULL DEFAULT 0,
            suggestion_count INTEGER NOT NULL DEFAULT 0,
            supported_pct REAL,
            outbound_links INTEGER,
            issues_json TEXT,
            metrics_json TEXT,
            reviewer TEXT DEFAULT 'automated',
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_dossier_reviews_slug
            ON dossier_reviews(slug, reviewed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_dossier_reviews_verdict
            ON dossier_reviews(verdict);
    """)


def get_review_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    ensure_review_schema(db)
    return db


def record_review(result: dict, reviewer: str = "automated") -> None:
    """Write a review result to the dossier_reviews table."""
    db = get_review_db()
    db.execute(
        """INSERT INTO dossier_reviews
           (slug, name, verdict, blocking_count, should_fix_count, suggestion_count,
            supported_pct, outbound_links, issues_json, metrics_json, reviewer)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            result["slug"],
            result["name"],
            result["verdict"],
            len(result.get("blocking", [])),
            len(result.get("should_fix", [])),
            len(result.get("suggestions", [])),
            result.get("metrics", {}).get("supported_pct"),
            result.get("metrics", {}).get("outbound_links"),
            json.dumps(result.get("blocking", []) + result.get("should_fix", []) + result.get("suggestions", [])),
            json.dumps(result.get("metrics", {})),
            reviewer,
        ),
    )
    db.commit()
    db.close()


def get_latest_verdict(slug: str) -> dict | None:
    """Get the most recent review for a slug."""
    db = get_review_db()
    row = db.execute(
        "SELECT * FROM dossier_reviews WHERE slug = ? ORDER BY reviewed_at DESC LIMIT 1",
        (slug,),
    ).fetchone()
    db.close()
    return dict(row) if row else None


def check_publish_gate(slugs: list[str] | None = None) -> tuple[bool, list[dict]]:
    """Check if all curated dossiers pass review. Returns (ok, failures)."""
    db = get_review_db()

    if slugs is None:
        slugs = get_curated_slugs()

    failures = []
    for slug in slugs:
        row = db.execute(
            "SELECT slug, name, verdict, reviewed_at FROM dossier_reviews "
            "WHERE slug = ? ORDER BY reviewed_at DESC LIMIT 1",
            (slug,),
        ).fetchone()

        if row is None:
            failures.append({"slug": slug, "reason": "never reviewed"})
        elif row["verdict"] == "FAIL":
            failures.append({"slug": slug, "reason": f"verdict={row['verdict']}", "reviewed_at": row["reviewed_at"]})

    db.close()
    return len(failures) == 0, failures


# --- CLI ---


def cmd_check(args):
    result = run_checks(args.slug)
    if not args.no_record and result["verdict"] != "SKIP":
        record_review(result)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(result, indent=2))


def cmd_batch(args):
    slugs = get_curated_slugs(args.top)
    name_to_slug = load_index()
    results = []
    for slug in slugs:
        result = run_checks(slug, name_to_slug)
        if not args.no_record and result["verdict"] != "SKIP":
            record_review(result)
        results.append(result)

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2))
        print(f"Checked {len(results)} dossiers → {args.output}")
    else:
        print(json.dumps(results, indent=2))

    # Print summary table to stderr
    print_summary_table(results, file=sys.stderr)


def cmd_fix(args):
    name_to_slug = load_index()
    dossier = load_dossier(args.slug)

    if not dossier.get("curation", {}).get("lead"):
        print(f"Skipping {args.slug} — not curated", file=sys.stderr)
        return

    total_fixes = 0

    # Fix cross-links
    dossier, n = fix_crosslinks(dossier, name_to_slug)
    if n:
        print(f"  Cross-links inserted: {n}")
    total_fixes += n

    # Fix banned titles
    dossier, n = fix_banned_titles(dossier)
    if n:
        print(f"  Banned title phrases fixed: {n}")
    total_fixes += n

    if total_fixes > 0:
        path = DOSSIER_DIR / f"{args.slug}.json"
        path.write_text(json.dumps(dossier, indent=2, default=str))
        print(f"Fixed {total_fixes} issues in {args.slug}")

        # Re-run checks
        print("\nPost-fix check:")
        result = run_checks(args.slug, name_to_slug)
        print(f"  Verdict: {result['verdict']}")
        print(f"  Remaining: {len(result['blocking'])} blocking, {len(result['should_fix'])} should_fix, {len(result['suggestions'])} suggestions")
    else:
        print(f"No auto-fixable issues found in {args.slug}")


def cmd_summary(args):
    slugs = get_curated_slugs()
    name_to_slug = load_index()
    results = []
    for slug in slugs:
        result = run_checks(slug, name_to_slug)
        results.append(result)

    print_summary_table(results)


def print_summary_table(results: list[dict], file=None):
    if file is None:
        file = sys.stdout

    pass_count = sum(1 for r in results if r["verdict"] == "PASS")
    needs_fix = sum(1 for r in results if r["verdict"] == "NEEDS_FIXES")
    fail_count = sum(1 for r in results if r["verdict"] == "FAIL")
    skip_count = sum(1 for r in results if r["verdict"] == "SKIP")

    active = [r for r in results if r["verdict"] != "SKIP"]

    avg_coverage = (
        sum(r["metrics"].get("supported_pct", 0) for r in active) / len(active)
        if active else 0
    )
    avg_links = (
        sum(r["metrics"].get("outbound_links", 0) for r in active) / len(active)
        if active else 0
    )

    print(f"\n{'='*70}", file=file)
    print(f"Dossier Review Summary: {len(active)} curated dossiers", file=file)
    print(f"{'='*70}", file=file)
    print(f"PASS: {pass_count}  |  NEEDS_FIXES: {needs_fix}  |  FAIL: {fail_count}  |  SKIP: {skip_count}", file=file)
    print(f"Avg citation coverage: {avg_coverage:.1f}%  |  Avg outbound links: {avg_links:.1f}", file=file)
    print(f"{'='*70}", file=file)

    # Table
    print(f"\n{'Name':<35} {'Verdict':<13} {'Block':>5} {'Fix':>5} {'Cov%':>6} {'Links':>5}", file=file)
    print(f"{'-'*35} {'-'*13} {'-'*5} {'-'*5} {'-'*6} {'-'*5}", file=file)

    for r in sorted(active, key=lambda x: ({"FAIL": 0, "NEEDS_FIXES": 1, "PASS": 2}.get(x["verdict"], 3), x["name"])):
        name = r["name"][:34]
        verdict = r["verdict"]
        blocking = len(r.get("blocking", []))
        should_fix = len(r.get("should_fix", []))
        cov = r["metrics"].get("supported_pct", 0)
        links = r["metrics"].get("outbound_links", 0)
        print(f"{name:<35} {verdict:<13} {blocking:>5} {should_fix:>5} {cov:>5.1f}% {links:>5}", file=file)


def cmd_gate(args):
    """Publish gate — exits non-zero if any curated dossier has FAIL verdict."""
    ok, failures = check_publish_gate()

    result = {
        "gate": "dossier-review",
        "status": "passed" if ok else "failed",
        "failures": failures,
        "checked_at": __import__("datetime").datetime.now().isoformat(),
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if ok:
            print(f"Dossier review gate: PASSED (all curated dossiers reviewed)")
        else:
            print(f"Dossier review gate: FAILED ({len(failures)} issues)")
            for f in failures:
                print(f"  {f['slug']}: {f['reason']}")

    sys.exit(0 if ok else 1)


def cmd_status(args):
    """Show review status of all curated dossiers from DB."""
    db = get_review_db()
    slugs = get_curated_slugs()

    print(f"\n{'Name':<35} {'Verdict':<13} {'Reviewed At':<20}")
    print(f"{'-'*35} {'-'*13} {'-'*20}")

    reviewed = 0
    for slug in slugs:
        row = db.execute(
            "SELECT name, verdict, reviewed_at FROM dossier_reviews "
            "WHERE slug = ? ORDER BY reviewed_at DESC LIMIT 1",
            (slug,),
        ).fetchone()
        if row:
            reviewed += 1
            print(f"{row['name'][:34]:<35} {row['verdict']:<13} {row['reviewed_at']:<20}")
        else:
            # Get name from index
            dossier = load_dossier(slug)
            print(f"{dossier.get('name', slug)[:34]:<35} {'NOT REVIEWED':<13} {'':<20}")

    db.close()
    print(f"\n{reviewed}/{len(slugs)} curated dossiers have been reviewed")


def main():
    parser = argparse.ArgumentParser(description="Automated dossier quality checks")
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="Check a single dossier")
    p_check.add_argument("slug", help="Dossier slug")
    p_check.add_argument("--output", "-o", help="Output JSON file")
    p_check.add_argument("--no-record", action="store_true", help="Skip writing to DB")

    p_batch = sub.add_parser("batch", help="Check all curated dossiers")
    p_batch.add_argument("--top", type=int, help="Only check top N by finding count")
    p_batch.add_argument("--output", "-o", help="Output JSON file")
    p_batch.add_argument("--no-record", action="store_true", help="Skip writing to DB")

    p_fix = sub.add_parser("fix", help="Auto-fix deterministic issues")
    p_fix.add_argument("slug", help="Dossier slug")

    sub.add_parser("summary", help="Print aggregate summary table")

    p_gate = sub.add_parser("gate", help="Publish gate — fail if any dossier has FAIL verdict")
    p_gate.add_argument("--json", action="store_true", help="Output JSON")

    sub.add_parser("status", help="Show review status from DB")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "fix":
        cmd_fix(args)
    elif args.command == "summary":
        cmd_summary(args)
    elif args.command == "gate":
        cmd_gate(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
