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
import hashlib
import json
import os
import re
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = Path(os.environ.get("ITHILDIN_CONTENT_DIR") or ROOT_DIR / "content")
DOSSIER_DIR = CONTENT_DIR / "dossiers"
INDEX_PATH = DOSSIER_DIR / "_index.json"
DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH") or ROOT_DIR / "investigation.db")
RECEIPT_PATH = CONTENT_DIR / "dossier-review-receipts.json"

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

# Internal investigation-process references that must NOT appear in outward-facing
# dossier prose. These leak the agent pipeline (waves/rounds/analysis-runs/skills)
# into reader-facing text. High-precision: require a digit or process noun so legit
# uses ("funding round", "waves of formation", "this analysis") don't match.
INTERNAL_REF_PATTERNS = [
    r"\banalysis[ _-]run(?:-\d+)?\b",                     # analysis-run, analysis_run, analysis-run-52
    r"\bcross-lens\b",
    r"\bmeta-synthesis\b",
    r"\b(?:Round|Wave)[ -]?\d+\s+(?:[A-Z][A-Za-z]+ )?"   # "Round 6 synthesis", "Wave 3 systemic report"
    r"(?:analytical |systemic |meta-)?(?:synthes|cross-lens|analysis|finding|evidence|record|"
    r"report|claim|hypothes|framework|correction|prediction|takeaway|cycle|priorit|window|"
    r"integration|docket|review|study|grid)",
    r"\b(?:per|from|in|according to|noted in|identified in|documented in|established in|"
    r"compiled in|reviewed in|confirmed in|flagged in|combined with the|cross-referenced with the)"
    r"\s+(?:the\s+|a\s+|an\s+)?(?:same\s+)?(?:Round|Wave)[ -]?\d+\b",
    r"\bAgents?\s+[A-G]\s*[-–]\s*[A-G]\b",                # Agents A-G
    r"\bROUND[ -]?\d+\b",                                  # all-caps ROUND-6 headers
    r"\b(?:discover-frameworks|systemic-analysis|deep-investigate|pursue-lead|triage-leads|"
    r"generate-hunches|search-all-sources|timeline-analysis)\b",
    r"\bpublication-readiness\b",
    r"\binvestigation\s+(?:DB|database)\b",
    r"\bthis analysis run\b",
    r"\bhyp-\d+\b",
    r"\bhypothesis\s+#\d+\b",
    r"\bHUNCH\s*\(hypothesis",
]

# Valid viz values
VALID_VIZ = {None, "ego_network", "timeline"}

# Citation token patterns — mirror `normalizeCitationPatterns` in web/src/lib/citations.ts.
# Matches bare tokens; renderer accepts [Token], (Token), and bare forms all equivalently.
# `Finding` allows an optional `#` since many legacy dossiers use `(Finding 2866)` without it.
CITATION_RE = re.compile(
    r"(?:"
    r"EFTA\d{5,11}"
    r"|Finding\s*#?\s*\d+"
    r"|SEC[:\-]\S+"
    r"|EDGAR[:\-]\S+"
    r"|990[:\-]\d+"
    r"|ACRIS[:\-]\S+"
    r"|CL[:\-]\d+"
    r"|NYSCEF_CASE[:\-]\S+"
    r"|FEC[:\-]\S+"
    r"|FARA[:\-]\d+"
    r"|REG[:\-]\w{2}[:\-]\S+"
    r"|USVI[:\-]\S+"
    r"|HOUSE_OVERSIGHT_\d+"
    r"|LMSBAND[:\-]\S+"
    r"|DOJ[:\-]\S+"
    r")"
)

# Loose match for Finding references (bracket, paren, or bare) — used by claim-type
# compliance and orphan detection. Keep separate so we don't conflate with other tokens.
FINDING_REF_RE = re.compile(r"Finding\s*#?\s*(\d+)", re.IGNORECASE)

# Attribution language patterns (for inference/synthesis)
ATTRIBUTION_RE = re.compile(
    r"(?:analysis\s+(?:of|indicates|suggests)|"
    r"cross-?reference\s+of|"
    r"cross-?reference\s+(?:shows|documents|indicates|found)|"
    r"(?:review|comparison)\s+(?:found|shows|documents|indicates|identifies)|"
    r"(?:grant|fund|financial)\s+flow\s+analysis|"
    r"review\s+of\s+(?:the\s+)?(?:records?|filings?|documents?)|"
    r"examination\s+of|"
    r"according\s+to|"
    r"(?:records?|documents?|sources?|evidence|filings?|agreement|petition|docket|"
    r"biography|report|messages?|correspondence|invoice|memoranda?)\s+"
    r"(?:(?:do|does|did|can|could)\s+not\s+)?"
    r"(?:show|indicate|reveal|document|establish|prove|identify|name|list|state|"
    r"contain|support|resolve|trace|attribute|place)|"
    r"(?:released|reviewed|located|public|federal|archived|contemporaneous|cited)\s+"
    r"(?:records?|documents?|messages?|emails?|filings?|docket|agreement|petition|"
    r"invoice|report|biography|materials?|files?|roster)|"
    r"(?:records?|documents?|sources?|evidence|filings?|agreement|petition|docket|"
    r"biography|report|messages?|correspondence|invoice|memoranda?|files?|response|"
    r"export|sequence|exchange|entry|appearance|matter)\b.{0,120}?\b"
    r"(?:show|shows|indicate|indicates|reveal|reveals|document|documents|establish|"
    r"establishes|prove|proves|identify|identifies|name|names|list|lists|state|states|"
    r"contain|contains|include|includes|support|supports|resolve|resolves|trace|traces|"
    r"attribute|attributes|place|places|appear|appears|reach|reaches|reached|label|"
    r"labels|involve|involves|leave|leaves|connect|connects|connected|accept|accepts|"
    r"accepted|date|dates|dated|is|are|was|were)\b|"
    r"\b(?:appear|appears)\s+in\s+(?:a|the)\s+(?:separate\s+)?(?:filing|record|docket)\b|"
    r"\bon\s+(?:the\s+)?cited\s+pages\b|"
    r"\b(?:wrote|told|asked|replied|answered|said|stated|reported|forwarded|sent|"
    r"listed|named|recorded|identified|described|billed|retained|relayed)\b|"
    r"\b(?:it|they|this|that|these|those)\s+(?:do|does|did|can|could)\s+not\s+"
    r"(?:show|establish|prove|identify|document|support|resolve|trace|name)|"
    r"\b(?:supported|bounded)\s+(?:conclusion|identity\s+match)\b|"
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
        if tag in {"p", "li", "div", "section", "h1", "h2", "h3", "br"}:
            self.text_parts.append(" ")

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


def dossier_content_sha256(slug: str) -> str:
    """Bind semantic review to the exact checked-in dossier, including evidence."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", slug):
        raise ValueError(f"Invalid dossier slug: {slug!r}")
    return hashlib.sha256((DOSSIER_DIR / f"{slug}.json").read_bytes()).hexdigest()


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


def check_internal_refs(dossier: dict) -> list[dict]:
    """Check 7: Internal investigation-process references in outward-facing prose.

    Flags wave/round/analysis-run/skill-name leakage (the agent pipeline showing
    through into reader-facing text). BLOCKING in system_role/section-titles,
    SHOULD_FIX in lead/section bodies and finding summaries/details.
    """
    issues = []
    curation = dossier.get("curation", {})

    # (label, raw_text, is_html, blocking)
    blocks = []
    if curation.get("system_role"):
        blocks.append(("system_role", curation["system_role"], False, True))
    for sec in curation.get("sections", []):
        blocks.append((f"section title '{sec.get('title', '')}'", sec.get("title", ""), False, True))
        blocks.append((f"section '{sec.get('title', sec.get('id'))}'", sec.get("content", ""), True, False))
    if curation.get("lead"):
        blocks.append(("lead", curation["lead"], True, False))
    for i, q in enumerate(curation.get("open_questions", []) or []):
        blocks.append((f"open_question[{i}]", q or "", False, False))
    for f in dossier.get("findings", []):
        for field in ("summary", "detail"):
            if f.get(field):
                blocks.append((f"finding #{f.get('id', '?')} {field}", f[field], False, False))

    for label, raw, is_html, blocking in blocks:
        if not isinstance(raw, str) or not raw:
            continue
        text = parse_html(raw).text if is_html else raw
        for pattern in INTERNAL_REF_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 30)
                context = text[start:end].replace("\n", " ")
                issues.append({
                    "check": "internal_refs",
                    "severity": "BLOCKING" if blocking else "SHOULD_FIX",
                    "detail": f"Internal-process reference '{m.group()}' in {label}: ...{context}...",
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

    applicable_models = curation.get("applicable_models", [])
    if not isinstance(applicable_models, list) or any(
        not isinstance(model_id, str) for model_id in applicable_models
    ):
        issues.append({
            "check": "structure",
            "severity": "BLOCKING",
            "detail": "curation.applicable_models must be an array of string model IDs",
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


def load_global_finding_statuses(db_path: Path = DB_PATH) -> dict[int, str]:
    """Return canonical verification states for globally citable findings."""
    if not db_path.exists():
        return {}
    try:
        with sqlite3.connect(str(db_path)) as db:
            return {
                int(row[0]): str(row[1] or "unverified")
                for row in db.execute("SELECT id, verification_status FROM findings")
            }
    except sqlite3.Error:
        return {}


def load_global_finding_ids(db_path: Path = DB_PATH) -> set[int]:
    """Return finding IDs available to the website's global citation catalog."""
    return set(load_global_finding_statuses(db_path))


def check_citations(
    dossier: dict,
    global_finding_ids: set[int] | None = None,
    global_finding_statuses: dict[int, str] | None = None,
) -> tuple[list[dict], dict]:
    """Check 4: Citation coverage — % of factual sentences with inline citations."""
    issues = []
    curation = dossier.get("curation", {})
    total_sentences = 0
    cited_sentences = 0
    orphan_citations = []
    non_verified_citations = []

    # Dossier pages merge their local catalog with the global finding catalog,
    # including the investigation.db fallback. A cross-target finding citation is
    # therefore valid even when that finding is not embedded in this dossier JSON.
    dossier_finding_records = [
        *dossier.get("findings", []),
        *dossier.get("citation_findings", []),
    ]
    finding_ids = {f["id"] for f in dossier_finding_records}
    if global_finding_ids is not None:
        finding_ids.update(global_finding_ids)

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

        # Check for orphan Finding citations (bracket, paren, or bare form)
        for m in FINDING_REF_RE.finditer(html):
            fid = int(m.group(1))
            if fid not in finding_ids:
                orphan_citations.append(f"Finding #{fid} in {label}")
            elif global_finding_statuses is not None:
                status = global_finding_statuses.get(fid)
                if status is None:
                    status = next(
                        (
                            str(f.get("verification_status") or "unverified")
                            for f in dossier_finding_records
                            if f.get("id") == fid
                        ),
                        "unverified",
                    )
                if status != "verified":
                    non_verified_citations.append(
                        f"Finding #{fid} in {label} has status {status}"
                    )

    coverage = (cited_sentences / total_sentences * 100) if total_sentences > 0 else 0

    # Citation coverage is a rough heuristic (inline ID string detection),
    # not a real support-coverage metric. Use npm run report:support-coverage
    # for authoritative numbers. Keep these as advisory only.
    if coverage < 50:
        issues.append({
            "check": "citations",
            "severity": "SHOULD_FIX",
            "detail": f"Citation coverage ~{coverage:.1f}% ({cited_sentences}/{total_sentences} sentences with inline refs)",
            "fixable": False,
        })
    elif coverage < 80:
        issues.append({
            "check": "citations",
            "severity": "SUGGESTION",
            "detail": f"Citation coverage ~{coverage:.1f}% ({cited_sentences}/{total_sentences} sentences with inline refs)",
            "fixable": False,
        })

    for orphan in orphan_citations:
        issues.append({
            "check": "citations",
            "severity": "SHOULD_FIX",
            "detail": f"Orphan citation: {orphan} — not in dossier findings",
            "fixable": False,
        })

    for citation in sorted(set(non_verified_citations)):
        issues.append({
            "check": "citations",
            "severity": "BLOCKING",
            "detail": f"Non-verified citation: {citation}",
            "fixable": False,
        })

    return issues, {
        "supported_pct": round(coverage, 1),
        "orphan_citations": len(orphan_citations),
        "non_verified_citations": len(set(non_verified_citations)),
    }


def check_claim_compliance(dossier: dict) -> list[dict]:
    """Check 5: Inference/synthesis findings cited without attribution language."""
    issues = []
    curation = dossier.get("curation", {})

    # Build map of finding_id -> claim_type
    claim_map = {}
    for f in [
        *dossier.get("findings", []),
        *dossier.get("citation_findings", []),
    ]:
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
            # Find Finding references in this sentence (bracket, paren, or bare form)
            for m in FINDING_REF_RE.finditer(sent):
                fid = int(m.group(1))
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


def run_checks(
    slug: str, name_to_slug: dict | None = None, *, static_only: bool = False,
) -> dict:
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
    # Portable release checks must resolve citations from the exported dossier,
    # including citation_findings. A developer's private DB cannot bless a build.
    global_finding_statuses = {} if static_only else load_global_finding_statuses()
    citation_issues, citation_metrics = check_citations(
        dossier,
        global_finding_ids=set(global_finding_statuses),
        global_finding_statuses=global_finding_statuses,
    )
    all_issues.extend(citation_issues)

    # Check 5: Claim compliance
    all_issues.extend(check_claim_compliance(dossier))

    # Check 6: Outbound links
    link_issues, outbound_count = check_outbound_links(dossier)
    all_issues.extend(link_issues)

    # Check 7: Internal-process references
    all_issues.extend(check_internal_refs(dossier))

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
    internal_ref_count = sum(1 for i in all_issues if i["check"] == "internal_refs")

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
            "non_verified_citations": citation_metrics.get(
                "non_verified_citations", 0
            ),
            "banned_phrases": banned_count,
            "internal_refs": internal_ref_count,
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
    """Create dossier_reviews and dossier_llm_reviews tables if they don't exist."""
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

        CREATE TABLE IF NOT EXISTS dossier_llm_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            blocking_count INTEGER NOT NULL DEFAULT 0,
            should_fix_count INTEGER NOT NULL DEFAULT 0,
            suggestion_count INTEGER NOT NULL DEFAULT 0,
            issues_json TEXT NOT NULL,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_dossier_llm_reviews_slug
            ON dossier_llm_reviews(slug, reviewed_at DESC);
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(dossier_llm_reviews)")}
    for name in ("content_sha256", "reviewer", "verdict"):
        if name not in columns:
            db.execute(f"ALTER TABLE dossier_llm_reviews ADD COLUMN {name} TEXT")


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


def check_publish_gate(
    slugs: list[str] | None = None, *, receipt_file: Path | None = None,
) -> tuple[bool, list[dict]]:
    """Require current semantic receipts and static checks without opening a DB."""
    result = validate_receipts(receipt_file or RECEIPT_PATH, slugs=slugs)
    return result["status"] == "passed", result["failures"]


# --- CLI ---


def cmd_check(args):
    result = run_checks(args.slug)
    result["content_sha256"] = dossier_content_sha256(args.slug)
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
        result["content_sha256"] = dossier_content_sha256(slug)
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
    """Publish gate for exact-content semantic receipts and static checks."""
    ok, failures = check_publish_gate(receipt_file=Path(args.receipt_file))

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
            print("Dossier review gate: PASSED (all curated dossiers reviewed)")
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


def extract_llm_issues(review: dict) -> list[dict]:
    """Extract issues from various LLM review JSON formats."""
    # Format 1: llm_issues array (canonical)
    if review.get("llm_issues"):
        return review["llm_issues"]

    # Format 2: issues array
    if review.get("issues") and isinstance(review["issues"], list):
        return review["issues"]

    # Format 3: checklist dict with nested issues arrays
    all_issues = []
    checklist = review.get("checklist", {})
    for category, data in checklist.items():
        if isinstance(data, dict) and "issues" in data:
            for issue in data["issues"]:
                if isinstance(issue, dict):
                    # Normalize severity
                    sev = issue.get("severity", "SUGGESTION").upper()
                    if sev in ("MINOR", "NOTE", "POSITIVE"):
                        sev = "SUGGESTION"
                    all_issues.append({
                        "severity": sev,
                        "category": category,
                        "detail": issue.get("detail", ""),
                        "location": issue.get("location", ""),
                    })

    # Also grab additional_findings, automated_issues_confirmed
    for key in ("additional_findings", "automated_issues_confirmed"):
        items = review.get(key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    sev = item.get("severity", "SHOULD_FIX").upper()
                    if sev in ("MINOR", "NOTE", "POSITIVE"):
                        sev = "SUGGESTION"
                    all_issues.append({
                        "severity": sev,
                        "category": item.get("category", key),
                        "detail": item.get("detail", str(item)),
                        "location": item.get("location", ""),
                    })
                elif isinstance(item, str):
                    all_issues.append({
                        "severity": "SHOULD_FIX",
                        "category": key,
                        "detail": item,
                        "location": "",
                    })

    return all_issues


def validate_semantic_review(review: dict, *, require_pass: bool = False) -> dict:
    """Validate an actual review's shape and exact content binding, not its truth.

    This accepts no implicit PASS from missing fields or legacy DB records.
    Semantic judgment remains the reviewer's responsibility.
    """
    if not isinstance(review, dict):
        raise ValueError("semantic review must be an object")
    slug = review.get("slug")
    if not isinstance(slug, str) or not slug:
        raise ValueError("semantic review needs a slug")
    if review.get("content_sha256") != dossier_content_sha256(slug):
        raise ValueError("missing or stale content_sha256; review this dossier version")
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("semantic review needs an identified reviewer")
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("semantic review needs an ISO reviewed_at timestamp with timezone") from exc
    if reviewed_at.tzinfo is None or reviewed_at > datetime.now(timezone.utc):
        raise ValueError("reviewed_at must have a timezone and cannot be in the future")
    issues = review.get("llm_issues")
    if not isinstance(issues, list) or any(
        not isinstance(issue, dict)
        or issue.get("severity") not in {"BLOCKING", "SHOULD_FIX", "SUGGESTION"}
        or not isinstance(issue.get("detail"), str)
        or not issue["detail"].strip()
        for issue in issues
    ):
        raise ValueError("llm_issues must explicitly list issues with valid severity and detail")
    verdict = (
        "FAIL" if any(i["severity"] == "BLOCKING" for i in issues)
        else "NEEDS_FIXES" if any(i["severity"] == "SHOULD_FIX" for i in issues)
        else "PASS"
    )
    if review.get("verdict") != verdict:
        raise ValueError("semantic verdict must be explicit and agree with llm_issues")
    if require_pass and verdict != "PASS":
        raise ValueError(f"semantic verdict={verdict}")
    return {
        "slug": slug, "content_sha256": review["content_sha256"],
        "reviewer": reviewer, "reviewed_at": review["reviewed_at"],
        "verdict": verdict, "llm_issues": issues,
    }


def _load_receipts(receipt_file: Path) -> dict[str, dict]:
    payload = json.loads(receipt_file.read_text())
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("receipt file must have schema_version=1")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("receipt file needs a reviews array")
    result = {}
    for review in reviews:
        if not isinstance(review, dict) or not isinstance(review.get("slug"), str):
            raise ValueError("each receipt needs a slug")
        slug = review["slug"]
        if slug in result:
            raise ValueError(f"duplicate receipt for {slug}")
        result[slug] = review
    return result


def validate_receipts(receipt_file: Path, *, slugs: list[str] | None = None) -> dict:
    """DB-free release validation. Old unbound reviews are review debt."""
    failures = []
    try:
        receipts = _load_receipts(Path(receipt_file))
        if slugs is None:
            # Include every published curated file, even if the index is stale.
            slugs = [
                path.stem for path in sorted(DOSSIER_DIR.glob("*.json"))
                if not path.name.startswith("_")
                and json.loads(path.read_text()).get("curation", {}).get("lead")
            ]
        name_to_slug = load_index()
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return {"gate": "dossier-review", "status": "failed", "checked": 0,
                "failures": [{"slug": "*", "reason": str(exc)}]}
    for slug in slugs:
        try:
            review = receipts.get(slug)
            if review is None:
                raise ValueError("no exact-content semantic review receipt")
            validated = validate_semantic_review(review, require_pass=True)
            automated = run_checks(slug, name_to_slug, static_only=True)
            if automated["verdict"] in {"FAIL", "SKIP"}:
                raise ValueError(f"static verdict={automated['verdict']}: {automated['blocking']}")
            if validated["content_sha256"] != dossier_content_sha256(slug):
                raise ValueError("dossier changed during validation")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            failures.append({"slug": slug, "reason": str(exc)})
    return {"gate": "dossier-review", "status": "failed" if failures else "passed",
            "checked": len(slugs), "failures": failures}


def store_receipt(review: dict, receipt_file: Path) -> dict:
    """Store a supplied actual review, including failed reviews; never infer one."""
    validated = validate_semantic_review(review)
    receipt_file = Path(receipt_file)
    receipts = _load_receipts(receipt_file) if receipt_file.exists() else {}
    receipts[validated["slug"]] = validated
    payload = {"schema_version": 1, "reviews": [receipts[k] for k in sorted(receipts)]}
    # Serialize receipt writes in the parent after all reviewers finish.
    temporary = receipt_file.with_name(f".{receipt_file.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n")
        temporary.replace(receipt_file)
    finally:
        temporary.unlink(missing_ok=True)
    return validated


def record_llm_review(review: dict) -> None:
    """Write an LLM review result to the dossier_llm_reviews table."""
    review = validate_semantic_review(review)
    db = get_review_db()
    issues = review["llm_issues"]
    blocking = sum(1 for i in issues if i.get("severity") == "BLOCKING")
    should_fix = sum(1 for i in issues if i.get("severity") == "SHOULD_FIX")
    suggestion = sum(1 for i in issues if i.get("severity") == "SUGGESTION")

    db.execute(
        """INSERT INTO dossier_llm_reviews
           (slug, blocking_count, should_fix_count, suggestion_count, issues_json,
            content_sha256, reviewer, verdict, reviewed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (review["slug"], blocking, should_fix, suggestion, json.dumps(issues),
         review["content_sha256"], review["reviewer"], review["verdict"], review["reviewed_at"]),
    )
    db.commit()
    db.close()


def cmd_ingest_llm(args):
    """Ingest LLM review JSON files into dossier_llm_reviews table."""
    import glob as globmod

    pattern = args.pattern or f"{args.dir}/review-*.json"
    files = sorted(globmod.glob(pattern))
    if not files:
        print(f"No files matching {pattern}", file=sys.stderr)
        sys.exit(1)

    ingested = 0
    failed = 0
    for f in files:
        try:
            review = json.loads(Path(f).read_text())
            if "slug" not in review:
                print(f"  Skipping {f} — no slug field", file=sys.stderr)
                continue
            record_llm_review(review)
            issues = extract_llm_issues(review)
            b = sum(1 for i in issues if i.get("severity") == "BLOCKING")
            s = sum(1 for i in issues if i.get("severity") == "SHOULD_FIX")
            print(f"  {review['slug']}: {b} blocking, {s} should_fix, {len(issues)-b-s} suggestions")
            ingested += 1
        except (ValueError, KeyError, OSError) as e:
            print(f"  Error in {f}: {e}", file=sys.stderr)
            failed += 1

    print(f"\nIngested {ingested} LLM reviews")
    if failed or not ingested:
        raise SystemExit(1)


def cmd_llm_status(args):
    """Show LLM review status of all curated dossiers."""
    db = get_review_db()
    slugs = get_curated_slugs()

    reviewed = 0
    blocking_total = 0

    print(f"\n{'Slug':<40} {'Block':>5} {'Fix':>5} {'Suggest':>7} {'Current':<8} {'Reviewed At':<20}")
    print(f"{'-'*40} {'-'*5} {'-'*5} {'-'*7} {'-'*20}")

    for slug in slugs:
        row = db.execute(
            "SELECT slug, blocking_count, should_fix_count, suggestion_count, reviewed_at, "
            "content_sha256 FROM dossier_llm_reviews WHERE slug = ? "
            "ORDER BY reviewed_at DESC, id DESC LIMIT 1",
            (slug,),
        ).fetchone()
        if row:
            current = row["content_sha256"] == dossier_content_sha256(slug)
            reviewed += int(current)
            if current:
                blocking_total += row["blocking_count"]
            print(f"{row['slug']:<40} {row['blocking_count']:>5} {row['should_fix_count']:>5} {row['suggestion_count']:>7} {str(current):<8} {row['reviewed_at']:<20}")

    db.close()
    print(f"\n{reviewed}/{len(slugs)} curated dossiers have current content-bound LLM reviews")
    if blocking_total:
        print(f"Total blocking issues: {blocking_total}")


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

    p_gate = sub.add_parser("gate", help="Require exact-content semantic receipts and static checks")
    p_gate.add_argument("--json", action="store_true", help="Output JSON")
    p_gate.add_argument("--receipt-file", type=Path, default=RECEIPT_PATH)

    p_receipt = sub.add_parser("receipt", help="Store an actual content-bound semantic review")
    p_receipt.add_argument("--review-file", type=Path, required=True)
    p_receipt.add_argument("--receipt-file", type=Path, default=RECEIPT_PATH)

    p_validate = sub.add_parser("validate-receipts", help="Check portable semantic receipts without a DB")
    p_validate.add_argument("--receipt-file", type=Path, default=RECEIPT_PATH)
    p_validate.add_argument("--slug", action="append", help="Check selected dossier (repeatable)")
    p_validate.add_argument("--json", action="store_true")
    p_validate.add_argument("--output", type=Path)

    sub.add_parser("status", help="Show review status from DB")

    p_ingest = sub.add_parser("ingest-llm", help="Ingest LLM review JSON files into DB")
    p_ingest.add_argument("--dir", default="/tmp", help="Directory containing review-*.json files")
    p_ingest.add_argument("--pattern", help="Glob pattern override (default: <dir>/review-*.json)")

    sub.add_parser("llm-status", help="Show LLM review status from DB")

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
    elif args.command == "ingest-llm":
        cmd_ingest_llm(args)
    elif args.command == "llm-status":
        cmd_llm_status(args)
    elif args.command == "receipt":
        try:
            receipt = store_receipt(json.loads(args.review_file.read_text()), args.receipt_file)
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))
        print(f"Stored {receipt['verdict']} review of {receipt['slug']} in {args.receipt_file}")
    elif args.command == "validate-receipts":
        result = validate_receipts(args.receipt_file, slugs=args.slug)
        if args.output:
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Dossier receipts: {result['status']} ({len(result['failures'])} issues)")
            for failure in result["failures"]:
                print(f"  {failure['slug']}: {failure['reason']}")
        raise SystemExit(0 if result["status"] == "passed" else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
