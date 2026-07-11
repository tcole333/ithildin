#!/usr/bin/env python3
"""Selector-pivot orchestrator.

Take one OSINT *selector* (email, username, phone, domain, IP, name/company) and
fan it out across the platform's existing lookup tools, harvesting linked
selectors and candidate entities into a single graph. Discovered entities are
resolved into the entities table and noteworthy pivots are queued as
`pending_triage` leads for human review.

Design:
  * Thin orchestrator. Each data source is a small *adapter* that shells out to
    an existing `query_*.py` tool and normalizes its output into a PivotRecord.
  * AGGREGATORS-ONLY posture: we query index layers, never download raw dumps.
  * Provenance is per-adapter. Legitimate sources (OpenSanctions, GLEIF, ICIJ)
    carry their own source name. Breach/leak aggregators (Dehashed, IntelX) set
    `leak_class=True`, which stamps `leak_aggregator` provenance and caps any
    derived finding at `medium` confidence (corroborate before promotion).
  * Selectors live in the FtM `--output` artifact (Email/UserAccount/Phone/...).
    Genuine entity<->entity relationships are what belong in `connections`
    (phase 2); v1 emits entities + pending_triage leads + the graph artifact.

Usage:
    uv run python tools/selector_pivot.py run "jane@example.com" --output $WORKDIR/pivot.json
    uv run python tools/selector_pivot.py run "Gazprom" --type company --depth 1 --output $WORKDIR/p.json
    uv run python tools/selector_pivot.py run "acmecorp.com" --output $WORKDIR/p.json --dry-run
    uv run python tools/selector_pivot.py run "Vladimir Putin" --enable-paid --output $WORKDIR/p.json
    uv run python tools/selector_pivot.py adapters          # list adapters + availability
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

try:
    from tools.output_util import add_output_args, write_output
    from tools.lead_tracker import get_db, check_searched, log_search
    from tools.entity_resolution import resolve_or_create_entity
    from tools.auto_leads import create_lead, lead_exists, LeadLimitReached
    from tools import investigation_context
    from tools.env_loader import load_env_file
except ImportError:
    from output_util import add_output_args, write_output
    from lead_tracker import get_db, check_searched, log_search
    from entity_resolution import resolve_or_create_entity
    from auto_leads import create_lead, lead_exists, LeadLimitReached
    import investigation_context
    from env_loader import load_env_file

# Load DEHASHED_API_KEY / INTELX_API_KEY from .env so adapter availability checks see them.
load_env_file()

SEARCH_SOURCE = "selector_pivot"


# --------------------------------------------------------------------------- #
# Selector typing
# --------------------------------------------------------------------------- #

SELECTOR_TYPES = ("email", "username", "phone", "domain", "ip", "name", "company", "eth", "sol")

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RE_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_RE_IPV6 = re.compile(r"^[0-9a-fA-F:]+:[0-9a-fA-F:]+$")
_RE_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9-]{1,63}\.)+[a-zA-Z]{2,}$")
_RE_PHONE = re.compile(r"^\+?[0-9][0-9\s().-]{6,}$")
_RE_ETH = re.compile(r"^0x[0-9a-fA-F]{40}$")
_RE_SOL = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_RE_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{2,40}$")


def detect_selector_type(value):
    """Best-effort selector classification. Use --type to override ambiguous cases."""
    v = value.strip()
    if _RE_EMAIL.match(v):
        return "email"
    if _RE_IPV4.match(v) or _RE_IPV6.match(v):
        return "ip"
    if _RE_ETH.match(v):
        return "eth"
    if _RE_DOMAIN.match(v):
        return "domain"
    if _RE_PHONE.match(v) and sum(c.isdigit() for c in v) >= 7:
        return "phone"
    # A multi-word string is almost certainly a person/org name, not a username.
    if " " in v:
        return "name"
    if _RE_SOL.match(v):
        return "sol"
    if _RE_USERNAME.match(v):
        return "username"
    return "name"


# --------------------------------------------------------------------------- #
# Core records
# --------------------------------------------------------------------------- #

@dataclass
class CandidateEntity:
    name: str
    entity_type: str = "unknown"
    jurisdiction: str = None
    ext_id: str = None          # the source's own id (ICIJ id, LEI, OpenSanctions id)
    score: float = None
    tags: list = field(default_factory=list)   # e.g. sanction/pep topics


@dataclass
class PivotRecord:
    """Normalized output of one adapter run against one selector."""
    source: str                                  # adapter name, e.g. 'opensanctions'
    input_selector: str
    input_type: str
    linked_selectors: list = field(default_factory=list)   # [(value, type), ...]
    entities: list = field(default_factory=list)           # [CandidateEntity, ...]
    leak_class: bool = False
    raw_count: int = 0
    error: str = None


# --------------------------------------------------------------------------- #
# Subprocess helper
# --------------------------------------------------------------------------- #

def _run_tool(argv, workdir, timeout=150):
    """Run an existing query_*.py tool, returning parsed JSON from its --output file.

    Uses the current interpreter (already inside the uv venv) for speed; the
    tools' dual-mode imports work when launched as a file from PROJECT_ROOT.
    """
    out_path = Path(workdir) / f"_pivot_{abs(hash((tuple(argv), os.urandom(4))))}.json"
    cmd = [sys.executable, str(PROJECT_ROOT / "tools" / argv[0]), *argv[1:],
           "--output", str(out_path)]
    try:
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    if not out_path.exists():
        err = (proc.stderr or proc.stdout or "no output").strip().splitlines()
        return None, (err[-1] if err else "no output file")
    try:
        with open(out_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return None, f"bad json: {e}"
    finally:
        try:
            out_path.unlink()
        except OSError:
            pass
    return data, None


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #

@dataclass
class Adapter:
    name: str
    selector_types: set
    runner: object                       # callable(selector, stype, workdir) -> PivotRecord
    paid: bool = False
    leak_class: bool = False
    available_check: object = None       # callable() -> (bool, reason)

    def available(self):
        if self.available_check is None:
            return True, "ok"
        return self.available_check()


def _env_present(var):
    def check():
        return (bool(os.environ.get(var)), f"set {var}" if not os.environ.get(var) else "ok")
    return check


# ---- normalizers (one per tool, against verified output shapes) ----------- #

def _norm_opensanctions(selector, stype, workdir):
    data, err = _run_tool(["query_opensanctions.py", "search", selector, "--limit", "5"], workdir)
    rec = PivotRecord("opensanctions", selector, stype)
    if err:
        rec.error = err
        return rec
    rows = data if isinstance(data, list) else data.get("results", [])
    rec.raw_count = len(rows)
    for r in rows:
        rec.entities.append(CandidateEntity(
            name=r.get("caption") or r.get("id"),
            entity_type=(r.get("schema") or "unknown").lower(),
            jurisdiction=(r.get("countries") or [None])[0],
            ext_id=r.get("id"),
            tags=r.get("topics") or [],
        ))
    return rec


def _norm_gleif(selector, stype, workdir):
    data, err = _run_tool(["query_gleif.py", "search", selector], workdir)
    rec = PivotRecord("gleif", selector, stype)
    if err:
        rec.error = err
        return rec
    rows = data if isinstance(data, list) else data.get("data", [])
    rec.raw_count = len(rows)
    for r in rows[:5]:
        attrs = r.get("attributes", {}) or {}
        ent = (attrs.get("entity") or {})
        legal = (ent.get("legalName") or {})
        rec.entities.append(CandidateEntity(
            name=legal.get("name") or r.get("id"),
            entity_type="company",
            jurisdiction=ent.get("jurisdiction"),
            ext_id=attrs.get("lei") or r.get("id"),
        ))
    return rec


def _norm_icij(selector, stype, workdir):
    data, err = _run_tool(["query_icij.py", "reconcile", selector, "--limit", "5"], workdir)
    rec = PivotRecord("icij", selector, stype)
    if err:
        rec.error = err
        return rec
    rows = data if isinstance(data, list) else data.get("results", [])
    rec.raw_count = len(rows)
    for r in rows:
        types = r.get("type") or []
        rec.entities.append(CandidateEntity(
            name=r.get("name"),
            entity_type=(types[0] if types else "offshore_entity"),
            ext_id=str(r.get("id")),
            score=r.get("score"),
            tags=["offshore"],
        ))
    return rec


def _norm_littlesis(selector, stype, workdir):
    data, err = _run_tool(["query_littlesis.py", "search", selector], workdir)
    rec = PivotRecord("littlesis", selector, stype)
    if err:
        rec.error = err
        return rec
    rows = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    rec.raw_count = len(rows)
    for r in rows[:5]:
        attrs = r.get("attributes", {}) if isinstance(r, dict) else {}
        rec.entities.append(CandidateEntity(
            name=attrs.get("name") or r.get("name"),
            entity_type=(attrs.get("primary_ext") or "unknown").lower(),
            ext_id=str(r.get("id")) if isinstance(r, dict) else None,
        ))
    return rec


def _norm_crtsh(selector, stype, workdir):
    data, err = _run_tool(["query_crtsh.py", "subdomains", selector], workdir)
    rec = PivotRecord("crtsh", selector, stype)
    if err:
        rec.error = err
        return rec
    subs = data.get("subdomains", []) if isinstance(data, dict) else []
    rec.raw_count = len(subs)
    for s in subs:
        if s and s != selector:
            rec.linked_selectors.append((s, "domain"))
    return rec


def _norm_maigret(selector, stype, workdir):
    data, err = _run_tool(["query_maigret.py", "search", selector, "--top", "50"], workdir)
    rec = PivotRecord("maigret", selector, stype)
    if err:
        rec.error = err
        return rec
    results = data.get("results", []) if isinstance(data, dict) else []
    found = [r for r in results if (r.get("status") or "").lower() in ("found", "claimed")]
    rec.raw_count = len(found)
    for r in found:
        if r.get("url"):
            rec.linked_selectors.append((r["url"], "url"))
    return rec


# ---- deferred / gated adapters -------------------------------------------- #

def _norm_dehashed(selector, stype, workdir):
    rec = PivotRecord("dehashed", selector, stype, leak_class=True)
    if not os.environ.get("DEHASHED_API_KEY"):
        rec.error = "no DEHASHED_API_KEY"
        return rec
    field = {"email": "email", "username": "username", "phone": "phone",
             "name": "name", "ip": "ip-address", "domain": "domain"}.get(stype)
    if not field:
        rec.error = f"unsupported selector type {stype}"
        return rec
    data, err = _run_tool(["query_dehashed.py", "search", f"--{field}", selector, "--size", "100"], workdir)
    if err:
        rec.error = err
        return rec
    entries = data.get("entries", []) if isinstance(data, dict) else []
    rec.raw_count = len(entries)
    seen = set()

    def _vals(entry, k):
        v = entry.get(k)
        if not v or v == "null":
            return []
        return [x for x in (v if isinstance(v, list) else [v]) if x and x != "null"]

    for e in entries:
        # Each record's OTHER selectors become linked-selector edges to pivot on.
        for fkey, ftype in (("email", "email"), ("username", "username"),
                            ("phone", "phone"), ("ip_address", "ip"), ("domain", "domain")):
            for v in _vals(e, fkey):
                k = (v.lower(), ftype)
                if k in seen or v.lower() == selector.lower():
                    continue
                seen.add(k)
                rec.linked_selectors.append((v, ftype))
        # A name -> candidate person entity, tagged with the breach source.
        for nm in _vals(e, "name"):
            db = e.get("database_name")
            rec.entities.append(CandidateEntity(name=nm, entity_type="person",
                                                tags=[db] if db else []))
    return rec


def _norm_intelx(selector, stype, workdir):
    rec = PivotRecord("intelx", selector, stype, leak_class=True)
    if not os.environ.get("INTELX_API_KEY"):
        rec.error = "no INTELX_API_KEY (free tier lacks phonebook; gated)"
        return rec
    data, err = _run_tool(["query_intelx.py", "search", selector], workdir)
    if err:
        rec.error = err
        return rec
    # Normalization wired when a key exists for live verification.
    rec.raw_count = len(data) if isinstance(data, list) else 0
    return rec


ADAPTERS = [
    Adapter("opensanctions", {"name", "company"}, _norm_opensanctions),
    Adapter("gleif", {"company", "name"}, _norm_gleif),
    Adapter("icij", {"name", "company"}, _norm_icij),
    Adapter("littlesis", {"name", "company"}, _norm_littlesis),
    Adapter("crtsh", {"domain"}, _norm_crtsh),
    Adapter("maigret", {"username"}, _norm_maigret),
    # Paid / leak aggregators — gated behind --enable-paid; Dehashed deferred.
    Adapter("intelx", {"email", "domain", "ip", "phone"}, _norm_intelx,
            paid=True, leak_class=True, available_check=_env_present("INTELX_API_KEY")),
    Adapter("dehashed", {"email", "username", "phone", "name", "ip", "domain"}, _norm_dehashed,
            paid=True, leak_class=True, available_check=_env_present("DEHASHED_API_KEY")),
]


def select_adapters(stype, enable_paid):
    out = []
    for a in ADAPTERS:
        if stype not in a.selector_types:
            continue
        if a.paid and not enable_paid:
            continue
        out.append(a)
    return out


# --------------------------------------------------------------------------- #
# Fan-out engine
# --------------------------------------------------------------------------- #

def pivot(seed, seed_type, depth, enable_paid, workdir, per_source_cap=25):
    """BFS fan-out. Returns (records, nodes, edges)."""
    records = []
    nodes = {}   # selector value -> {type, sources:set}
    edges = []   # {src, dst, rel, source}
    visited = set()
    frontier = [(seed, seed_type, 0)]
    nodes[seed] = {"type": seed_type, "sources": set(["seed"])}

    while frontier:
        value, stype, d = frontier.pop(0)
        key = (value.lower(), stype)
        if key in visited:
            continue
        visited.add(value.lower())
        # Paid/leak adapters fire only on the seed (d==0) to bound credit cost.
        adapters = select_adapters(stype, enable_paid and d == 0)
        for adapter in adapters:
            ok, reason = adapter.available()
            if not ok:
                records.append(PivotRecord(adapter.name, value, stype,
                                           leak_class=adapter.leak_class,
                                           error=f"unavailable: {reason}"))
                continue
            rec = adapter.runner(value, stype, workdir)
            rec.leak_class = adapter.leak_class
            records.append(rec)
            # entities -> nodes/edges
            for ent in rec.entities[:per_source_cap]:
                if not ent.name:
                    continue
                nid = f"entity::{ent.name}"
                nodes.setdefault(nid, {"type": ent.entity_type, "sources": set()})["sources"].add(rec.source)
                edges.append({"src": value, "dst": nid, "rel": "mentions", "source": rec.source})
            # linked selectors -> nodes/edges, enqueue for next depth
            for (lv, lt) in rec.linked_selectors[:per_source_cap]:
                nodes.setdefault(lv, {"type": lt, "sources": set()})["sources"].add(rec.source)
                edges.append({"src": value, "dst": lv, "rel": "linked", "source": rec.source})
                if d + 1 <= depth and lt in ("domain", "email", "username", "ip", "phone"):
                    frontier.append((lv, lt, d + 1))
    return records, nodes, edges


# --------------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------------- #

def emit(records, profile_id, dry_run):
    """Resolve candidate entities and queue pending_triage leads. Returns a summary."""
    created_entities, created_leads, skipped = [], [], 0
    if dry_run:
        for rec in records:
            for ent in rec.entities:
                created_entities.append({"name": ent.name, "type": ent.entity_type,
                                         "source": rec.source, "action": "DRY_RUN"})
        return {"entities": created_entities, "leads": [], "dry_run": True}

    db = get_db()
    try:
        for rec in records:
            if rec.error or not rec.entities:
                continue
            src_label = ("leak_aggregator:" + rec.source) if rec.leak_class else ("pivot:" + rec.source)
            for ent in rec.entities:
                if not ent.name:
                    continue
                res = resolve_or_create_entity(
                    db, ent.name,
                    entity_type=ent.entity_type if ent.entity_type in ("person", "company", "organization") else "unknown",
                    jurisdiction=ent.jurisdiction,
                    source=src_label,
                    notes=f"selector_pivot: {rec.input_type} '{rec.input_selector}' -> {rec.source}"
                          + (f" (id={ent.ext_id})" if ent.ext_id else ""),
                )
                created_entities.append({"name": ent.name, "entity_id": res.entity_id,
                                         "action": res.action, "source": rec.source})
                # Queue a triage lead for the strongest signals (sanctioned/offshore/scored).
                noteworthy = bool(ent.tags) or (ent.score or 0) >= 70 or rec.source in ("icij", "opensanctions")
                if not noteworthy:
                    continue
                title = f"Pivot: {rec.input_type} '{rec.input_selector}' -> {ent.name} ({rec.source})"
                if lead_exists(db, title[:60]):
                    skipped += 1
                    continue
                try:
                    lead_id = create_lead(
                        db, title=title, category="selector_pivot",
                        priority="medium", source=f"agent:{SEARCH_SOURCE}",
                        target=ent.name, profile_id=profile_id,
                        notes=f"Auto-discovered via selector pivot. Source={rec.source}, "
                              f"tags={ent.tags}, ext_id={ent.ext_id}. "
                              f"{'LEAK-AGGREGATOR: corroborate against a primary record before promotion.' if rec.leak_class else 'Verify the link before promotion.'}",
                    )
                    created_leads.append({"lead_id": lead_id, "title": title})
                except LeadLimitReached:
                    break
        db.commit()
    finally:
        db.close()
    return {"entities": created_entities, "leads": created_leads, "skipped_dupes": skipped}


def _serialize_nodes(nodes):
    return [{"id": k, "type": v["type"], "sources": sorted(v["sources"])} for k, v in nodes.items()]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def cmd_run(args):
    selector = args.selector.strip()
    stype = args.type or detect_selector_type(selector)
    if stype not in SELECTOR_TYPES:
        print(f"ERROR: unknown selector type '{stype}'. Choose from {SELECTOR_TYPES}.", file=sys.stderr)
        sys.exit(1)

    if not args.no_dedup and check_searched(selector, SEARCH_SOURCE):
        print(f"Already pivoted '{selector}' (source={SEARCH_SOURCE}). Use --no-dedup to force.")
        return

    profile_id = investigation_context.get_active_profile_id()
    workdir = args.workdir or tempfile.mkdtemp(prefix="selpivot-")

    records, nodes, edges = pivot(selector, stype, args.depth, args.enable_paid, workdir)
    emission = emit(records, profile_id, args.dry_run)

    if not args.no_dedup and not args.dry_run:
        log_search(selector, SEARCH_SOURCE, len(nodes))

    sources_run = sorted({r.source for r in records if not r.error})
    errors = [{"source": r.source, "selector": r.input_selector, "error": r.error}
              for r in records if r.error]
    result = {
        "seed": selector, "seed_type": stype, "depth": args.depth,
        "profile_id": profile_id,
        "adapters_run": sources_run,
        "node_count": len(nodes), "edge_count": len(edges),
        "nodes": _serialize_nodes(nodes), "edges": edges,
        "emission": emission,
        "errors": errors,
    }
    summary = (f"pivot '{selector}' [{stype}] -> {len(nodes)} nodes, "
               f"{len(emission.get('entities', []))} entities, "
               f"{len(emission.get('leads', []))} leads"
               + (" (dry-run)" if args.dry_run else ""))
    if write_output(result, args, summary=summary):
        return
    print(summary)
    if errors:
        print(f"  ({len(errors)} adapter error(s); pass --output to inspect)")


def cmd_adapters(args):
    stype = args.type
    rows = []
    for a in ADAPTERS:
        ok, reason = a.available()
        rows.append({
            "adapter": a.name,
            "selector_types": sorted(a.selector_types),
            "paid": a.paid, "leak_class": a.leak_class,
            "available": ok, "note": reason,
            "routed": (stype in a.selector_types) if stype else None,
        })
    if write_output(rows, args, summary=f"{len(rows)} adapters"):
        return
    for r in rows:
        flags = []
        if r["paid"]:
            flags.append("PAID")
        if r["leak_class"]:
            flags.append("LEAK")
        flag = f" [{','.join(flags)}]" if flags else ""
        status = "ok" if r["available"] else f"unavailable ({r['note']})"
        print(f"  {r['adapter']:<14}{flag:<14} types={','.join(r['selector_types']):<28} {status}")


def main():
    parser = argparse.ArgumentParser(description="Selector-pivot orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Pivot a selector across data sources")
    p_run.add_argument("selector", help="The selector to pivot (email/username/domain/ip/phone/name)")
    p_run.add_argument("--type", choices=SELECTOR_TYPES, help="Override auto-detected selector type")
    p_run.add_argument("--depth", type=int, default=1, help="Fan-out depth for re-pivotable selectors (default 1)")
    p_run.add_argument("--enable-paid", action="store_true", help="Include paid/leak aggregators (Dehashed/IntelX)")
    p_run.add_argument("--dry-run", action="store_true", help="Discover only; do not write entities/leads")
    p_run.add_argument("--no-dedup", action="store_true", help="Ignore search_log dedup")
    p_run.add_argument("--workdir", help="Scratch dir for adapter output (default: a temp dir)")
    add_output_args(p_run)
    p_run.set_defaults(func=cmd_run)

    p_ad = sub.add_parser("adapters", help="List adapters and availability")
    p_ad.add_argument("--type", choices=SELECTOR_TYPES, help="Show routing for this selector type")
    add_output_args(p_ad)
    p_ad.set_defaults(func=cmd_adapters)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
