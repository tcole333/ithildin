#!/usr/bin/env python3
"""
CourtListener API wrapper for OSINT investigations.

Loads credentials from .env and provides investigation-friendly output.

Usage:
    python tools/query_courtlistener.py search "Jeffrey Epstein"
    python tools/query_courtlistener.py cases "Epstein" --court nysd
    python tools/query_courtlistener.py docket 16066603
    python tools/query_courtlistener.py party "Ghislaine Maxwell"
    python tools/query_courtlistener.py opinions "Epstein" --court ca2
    python tools/query_courtlistener.py judge "Preska"
    python tools/query_courtlistener.py disclosures --person-id 1234
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
    from tools.search_log_util import canonical_search_key
except ImportError:
    from output_util import add_output_args, write_output
    from search_log_util import canonical_search_key


COURTLISTENER_SOURCE = "courtlistener"


def _log(query, source, count):
    """Log search to prevent redundant queries."""
    try:
        from tools.lead_tracker import log_search
        log_search(query, source, count)
    except Exception:
        pass


def _record_search(mode, count, query=None, **filters):
    """Log one CourtListener operation with a stable mode/filter key."""
    _log(
        canonical_search_key(mode, query, **filters),
        COURTLISTENER_SOURCE,
        count,
    )


# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"'))

def _client():
    try:
        from tools.courtlistener_api_client import CourtListenerClient
    except ImportError:
        from courtlistener_api_client import CourtListenerClient

    token = os.environ.get("COURTLISTENER_TOKEN")
    if not token:
        print("ERROR: COURTLISTENER_TOKEN not set in .env", file=sys.stderr)
        sys.exit(1)
    return CourtListenerClient(token=token)


def _report_pagination(client, requested_limit):
    """Explain when an upstream result count is below the requested ceiling."""
    metadata = getattr(client, "last_pagination", None)
    if not metadata:
        return
    returned = metadata["returned"]
    upstream_count = metadata["upstream_count"]
    pages = metadata["pages"]
    if metadata["upstream_ended_early"]:
        print(
            "WARNING: CourtListener pagination ended without a next link after "
            f"{returned} of {upstream_count} reported results across {pages} page(s).",
            file=sys.stderr,
        )
    elif requested_limit and returned < requested_limit:
        reported = upstream_count if upstream_count is not None else returned
        print(
            "INFO: CourtListener pagination complete: returned "
            f"{returned} of {reported} upstream results across {pages} page(s); "
            f"--limit {requested_limit} is a ceiling, not a promised result count.",
            file=sys.stderr,
        )


def cmd_search(args):
    """Generic search with field operator support."""
    # Build query from positional + field operator flags
    parts = [args.query] if args.query else []
    if getattr(args, "party", None):
        parts.append(f'party:"{args.party}"')
    if getattr(args, "firm", None):
        parts.append(f'firm:"{args.firm}"')
    if getattr(args, "attorney", None):
        parts.append(f'attorney:"{args.attorney}"')
    if getattr(args, "assigned_to", None):
        parts.append(f'assignedTo:"{args.assigned_to}"')
    if getattr(args, "docket_number", None):
        parts.append(f'docketNumber:"{args.docket_number}"')
    query = " ".join(parts) if parts else "*"

    kwargs = {}
    if getattr(args, "semantic", False):
        kwargs["semantic"] = "true"
    if getattr(args, "highlight", False):
        kwargs["highlight"] = "on"
    if getattr(args, "after", None):
        kwargs["filed_after"] = args.after
    if getattr(args, "before", None):
        kwargs["filed_before"] = args.before

    client = _client()
    results = client.search(
        query,
        search_type=args.type,
        court=args.court,
        max_results=args.limit,
        **kwargs,
    )
    _report_pagination(client, args.limit)

    _record_search(
        "search",
        len(results),
        query,
        search_type=args.type,
        court=args.court,
        after=getattr(args, "after", None),
        before=getattr(args, "before", None),
        semantic=bool(getattr(args, "semantic", False)),
    )

    if write_output(results, args, summary=f"CourtListener search '{query}'"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    print(f"Found {len(results)} results for '{query}' (type={args.type})")
    print()
    for r in results:
        court = r.get("court", r.get("court_id", "?"))
        case_name = r.get("caseName", r.get("case_name", "?"))
        date = r.get("dateFiled", r.get("date_filed", ""))
        url = r.get("docket_absolute_url", r.get("absolute_url", ""))
        print(f"  [{court}] {case_name}")
        if date:
            print(f"    Filed: {date}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        # Show snippet if available
        snippet = r.get("snippet", r.get("text", ""))
        if snippet:
            clean = snippet.replace("<mark>", "**").replace("</mark>", "**")
            print(f"    Snippet: {clean[:200]}")
        print()


def cmd_cases(args):
    """Search RECAP dockets specifically."""
    client = _client()
    results = client.search_cases(
        args.query,
        court=args.court,
        date_filed_after=args.after,
        date_filed_before=args.before,
        max_results=args.limit,
    )
    _record_search(
        "cases",
        len(results),
        args.query,
        court=args.court,
        after=args.after,
        before=args.before,
    )

    if write_output(results, args, summary=f"CourtListener cases '{args.query}': {len(results)} results"):
        return

    print(f"Found {len(results)} cases for '{args.query}'")
    print()
    for r in results:
        court = r.get("court", "?")
        case_name = r.get("caseName", "?")
        date = r.get("dateFiled", "")
        docket_num = r.get("docketNumber", "")
        nos = r.get("suitNature", "")
        url = r.get("docket_absolute_url", "")
        print(f"  [{court}] {case_name}")
        if docket_num:
            print(f"    Docket #: {docket_num}")
        if date:
            print(f"    Filed: {date}")
        if nos:
            print(f"    Nature of suit: {nos}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        print()


def cmd_docket(args):
    """Get docket details by ID."""
    client = _client()
    docket = client.get_docket(args.docket_id)

    if write_output(docket, args, summary=f"CourtListener docket #{args.docket_id}"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(docket, indent=2, default=str))
        return

    print(f"=== Docket #{args.docket_id} ===")
    print(f"Case: {docket.get('case_name', '?')}")
    print(f"Court: {docket.get('court', '?')}")
    print(f"Docket #: {docket.get('docket_number', '?')}")
    print(f"Filed: {docket.get('date_filed', '?')}")
    print(f"Terminated: {docket.get('date_terminated', 'ongoing')}")
    print(f"Nature of suit: {docket.get('nature_of_suit', '?')}")
    print(f"Cause: {docket.get('cause', '?')}")
    judges = docket.get("assigned_to_str", "") or docket.get("referred_to_str", "")
    if judges:
        print(f"Judge: {judges}")
    print(f"URL: https://www.courtlistener.com{docket.get('absolute_url', '')}")
    print()


def cmd_party(args):
    """Search for cases by party name (uses search API field operators)."""
    client = _client()
    results = client.search_by_party(args.name, court=args.court, max_results=args.limit)
    _record_search(
        "party",
        len(results),
        args.name,
        court=args.court,
    )

    if write_output(results, args, summary=f"CourtListener party search '{args.name}': {len(results)} results"):
        return

    print(f"Found {len(results)} cases involving party '{args.name}'")
    print()
    for r in results:
        case_name = r.get("caseName", r.get("case_name", "?"))
        court = r.get("court", "?")
        date = r.get("dateFiled", "")
        docket_num = r.get("docketNumber", "")
        url = r.get("docket_absolute_url", "")
        parties = r.get("party", [])
        attorneys = r.get("attorney", [])
        firms = r.get("firm", [])
        print(f"  [{court}] {case_name}")
        if docket_num:
            print(f"    Docket #: {docket_num}")
        if date:
            print(f"    Filed: {date}")
        if parties:
            print(f"    Parties: {', '.join(str(p) for p in parties[:5])}")
        if attorneys:
            print(f"    Attorneys: {', '.join(str(a) for a in attorneys[:3])}")
        if firms:
            print(f"    Firms: {', '.join(str(f) for f in firms[:3])}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        print()


def cmd_opinions(args):
    """Search opinions."""
    client = _client()
    kwargs = {}
    if getattr(args, "semantic", False):
        kwargs["semantic"] = "true"
    results = client.search(
        args.query,
        search_type="o",
        court=args.court,
        max_results=args.limit,
        **kwargs,
    )
    _record_search(
        "opinions",
        len(results),
        args.query,
        court=args.court,
        semantic=bool(getattr(args, "semantic", False)),
    )

    if write_output(results, args, summary=f"CourtListener opinions '{args.query}': {len(results)} results"):
        return

    print(f"Found {len(results)} opinions for '{args.query}'")
    print()
    for r in results:
        case_name = r.get("caseName", "?")
        court = r.get("court", "?")
        date = r.get("dateFiled", "")
        cite = r.get("citation", [])
        url = r.get("absolute_url", "")
        print(f"  [{court}] {case_name}")
        if date:
            print(f"    Date: {date}")
        if cite:
            print(f"    Citations: {cite}")
        if url:
            print(f"    URL: https://www.courtlistener.com{url}")
        snippet = r.get("snippet", "")
        if snippet:
            clean = snippet.replace("<mark>", "**").replace("</mark>", "**")
            print(f"    Snippet: {clean[:200]}")
        print()


def cmd_judge(args):
    """Search judges."""
    client = _client()
    judges = client.search_judges(name=args.name, max_results=args.limit)
    _record_search("judge", len(judges), args.name)

    if write_output(judges, args, summary=f"CourtListener judges '{args.name}': {len(judges)} results"):
        return

    print(f"Found {len(judges)} judges matching '{args.name}'")
    for j in judges:
        name = j.get("name_full", "?")
        positions = j.get("positions", [])
        print(f"  {name} (ID: {j.get('id', '?')})")
        for pos in positions[:3]:
            court = pos.get("court", {}).get("short_name", "?")
            title = pos.get("position_type", "?")
            print(f"    {title} at {court}")
        print()


def cmd_disclosures(args):
    """Get financial disclosures for a judge."""
    client = _client()
    results = client.get_financial_disclosures(
        person_id=args.person_id,
        year=args.year,
        max_results=args.limit,
    )

    if write_output(results, args, summary="CourtListener disclosures"):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(results, indent=2, default=str))
        return

    print(f"Found {len(results)} disclosure records")
    for d in results:
        year = d.get("year", "?")
        person = d.get("person", "?")
        print(f"  Year {year} — Person ID: {person}")
        if d.get("has_been_extracted"):
            print("    Extracted: Yes")
        print()


def cmd_opinion(args):
    """Fetch full opinion text by opinion ID or cluster ID."""
    client = _client()
    id_type = getattr(args, "id_type", "auto")

    # Search results and citations normally expose cluster IDs. Numeric cluster
    # and opinion ID spaces overlap, so trying the opinion endpoint first can
    # silently return an unrelated case. Prefer clusters in auto mode; callers
    # with a known raw opinion ID can force the opinion endpoint.
    opinion = None
    if id_type in {"auto", "cluster"}:
        try:
            cluster = client.get_cluster(args.opinion_id)
            opinion_urls = cluster.get("sub_opinions", [])
            if opinion_urls:
                oid = opinion_urls[0].rstrip("/").split("/")[-1]
                opinion = client.get_opinion(int(oid))
        except Exception as exc:
            if id_type == "cluster":
                print(
                    f"ERROR: Could not fetch opinion cluster: {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(1)

    if opinion is None and id_type in {"auto", "opinion"}:
        try:
            opinion = client.get_opinion(args.opinion_id)
        except Exception as exc:
            print(f"ERROR: Could not fetch opinion: {exc}", file=sys.stderr)
            raise SystemExit(1)

    if opinion is None:
        print(
            f"ERROR: CourtListener cluster #{args.opinion_id} contains no opinions.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    _record_search(
        "opinion",
        1,
        str(args.opinion_id),
        id_type=id_type,
    )
    if write_output(opinion, args, summary=f"CourtListener opinion #{args.opinion_id}"):
        return

    # Extract text from available fields (priority order)
    text = ""
    for field in ["html_lawbox", "html_columbia", "html_with_citations", "html", "plain_text", "xml_harvard"]:
        content = opinion.get(field, "")
        if content and len(content) > 100:
            text = content
            print(f"─── Opinion (source: {field}, {len(text):,} chars) ───")
            break

    if not text:
        print("No opinion text available.", file=sys.stderr)
        return

    # Strip HTML if needed
    if text.startswith("<"):
        import html as html_mod
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<(?:br|p|div|tr|li|h[1-6])[^>]*/?>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = html_mod.unescape(text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

    lines = text.split("\n")
    for line in lines[:args.lines]:
        print(line)
    if len(lines) > args.lines:
        print(f"\n... ({len(lines) - args.lines} more lines)")

def cmd_recap_search(args):
    """Search RECAP documents for a case. Uses the search API (type=rd)."""
    client = _client()
    results = client.search(
        args.query,
        search_type="rd",
        court=args.court,
        max_results=args.limit,
    )
    _report_pagination(client, args.limit)

    _record_search(
        "recap_search",
        len(results),
        args.query,
        court=args.court,
    )
    if write_output(results, args, summary=f"RECAP doc search '{args.query}': {len(results)} results"):
        return

    print(f"Found {len(results)} RECAP documents for '{args.query}'")
    print()
    for r in results:
        desc = r.get("short_description") or r.get("description") or "?"
        entry_num = r.get("entry_number", "?")
        date = r.get("entry_date_filed", "?")
        pages = r.get("page_count", "?")
        filepath = r.get("filepath_local", "")
        is_available = r.get("is_available", False)
        docket_url = r.get("docket_absolute_url", "")

        print(f"  [{entry_num}] {date} | {desc[:80]}")
        print(f"       Pages: {pages} | Available: {is_available}")
        if filepath:
            print(f"       Download: https://storage.courtlistener.com/{filepath}")
        if docket_url:
            print(f"       Docket: https://www.courtlistener.com{docket_url}")
        print()

def _extract_pages_pymupdf(pdf_path):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    doc = fitz.open(pdf_path)
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def _extract_pages_pdftotext(pdf_path):
    executable = shutil.which("pdftotext")
    if not executable:
        raise FileNotFoundError("pdftotext is not installed or not on PATH")
    completed = subprocess.run(
        [executable, "-layout", str(pdf_path), "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit status {completed.returncode}"
        raise RuntimeError(f"pdftotext failed: {detail}")
    pages = completed.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages or [""]


def _extract_pdf_pages(pdf_path):
    """Extract PDF pages with PyMuPDF, then the installed Poppler fallback."""
    pymupdf_error = None
    try:
        return "pymupdf", _extract_pages_pymupdf(pdf_path), None
    except Exception as exc:
        pymupdf_error = exc

    try:
        return (
            "pdftotext",
            _extract_pages_pdftotext(pdf_path),
            str(pymupdf_error),
        )
    except Exception as pdftotext_error:
        raise RuntimeError(
            "PDF text extraction failed with both PyMuPDF "
            f"({pymupdf_error}) and pdftotext ({pdftotext_error})"
        ) from pdftotext_error


def _extraction_quality(pages):
    chars_per_page = [
        len(re.sub(r"\s+", "", page or ""))
        for page in pages
    ]
    page_count = len(chars_per_page)
    text_chars = sum(chars_per_page)
    substantive_pages = sum(chars >= 300 for chars in chars_per_page)
    needs_ocr = (
        text_chars < 100
        or (
            page_count >= 3
            and (
                text_chars / page_count < 200
                or substantive_pages / page_count < 0.25
            )
        )
    )
    return {
        "page_count": page_count,
        "text_chars": text_chars,
        "substantive_pages": substantive_pages,
        "needs_ocr": needs_ocr,
    }


def _write_extracted_text(text_path, pages):
    page_break = "\n--- PAGE BREAK ---\n"
    text = page_break.join((page or "").rstrip() for page in pages)
    Path(text_path).write_text(text.rstrip() + "\n", encoding="utf-8")


def cmd_download(args):
    """Download a RECAP document PDF from CourtListener storage."""
    import requests

    url = args.url
    if not url.startswith("http"):
        # Assume it's a filepath_local — prepend storage URL
        url = f"https://storage.courtlistener.com/{url}"

    print(f"Downloading: {url}", file=sys.stderr)
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        print(f"ERROR: HTTP {r.status_code}", file=sys.stderr)
        return

    outpath = args.output_file
    with open(outpath, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    size_kb = os.path.getsize(outpath) / 1024
    print(f"Downloaded {size_kb:.0f}KB to {outpath}")

    # If it's a PDF and the user wants text extraction, prefer PyMuPDF and
    # fall back to the installed Poppler command-line extractor.
    if outpath.casefold().endswith(".pdf") and args.extract_text:
        text_path = str(Path(outpath).with_suffix(".txt"))
        try:
            method, pages, fallback_reason = _extract_pdf_pages(outpath)
            _write_extracted_text(text_path, pages)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(1) from None

        quality = _extraction_quality(pages)
        if method == "pdftotext":
            print(
                "INFO: PyMuPDF unavailable or failed; used pdftotext fallback"
                + (f" ({fallback_reason})" if fallback_reason else ""),
                file=sys.stderr,
            )
        print(
            f"Extracted text via {method} "
            f"({quality['page_count']} pages, "
            f"{quality['text_chars']} non-whitespace chars) to {text_path}"
        )
        if quality["needs_ocr"]:
            print(
                "WARNING: Low-text PDF extraction "
                f"({quality['text_chars']} chars across "
                f"{quality['page_count']} pages; "
                f"{quality['substantive_pages']} substantive pages). "
                "The PDF likely needs OCR.",
                file=sys.stderr,
            )


def cmd_citations(args):
    """Show citation graph for an opinion cluster."""
    client = _client()
    citing = client.get_citing_opinions(args.cluster_id, max_results=args.limit)
    cited_by = client.get_cited_by_opinion(args.cluster_id, max_results=args.limit)
    result = {"cluster_id": args.cluster_id, "cites": citing, "cited_by": cited_by}
    _record_search(
        "citations",
        len(citing) + len(cited_by),
        str(args.cluster_id),
    )
    if write_output(result, args, summary=f"Citations for cluster #{args.cluster_id}: cites={len(citing)} cited_by={len(cited_by)}"):
        return
    print(f"=== Citation Graph for Cluster #{args.cluster_id} ===")
    print(f"\nThis opinion cites {len(citing)} opinions:")
    for c in citing[:20]:
        print(f"  -> {c.get('cited_opinion', '?')}")
    print(f"\nCited by {len(cited_by)} opinions:")
    for c in cited_by[:20]:
        print(f"  <- {c.get('citing_opinion', '?')}")


def cmd_resolve_cite(args):
    """Resolve citation text to CourtListener cluster IDs."""
    client = _client()
    result = client.resolve_citations(args.text)
    _record_search("resolve_cite", 1, args.text[:80])
    if write_output(result, args, summary="Citation resolution"):
        return
    print(json.dumps(result, indent=2, default=str))


def cmd_cluster(args):
    """Get opinion cluster details."""
    client = _client()
    cluster = client.get_cluster(args.cluster_id)
    _record_search("cluster", 1, str(args.cluster_id))
    if write_output(cluster, args, summary=f"Cluster #{args.cluster_id}"):
        return
    print(f"=== Cluster #{args.cluster_id} ===")
    print(f"Case: {cluster.get('case_name', '?')}")
    print(f"Date Filed: {cluster.get('date_filed', '?')}")
    print(f"Citation Count: {cluster.get('citation_count', 0)}")
    print(f"Precedential Status: {cluster.get('precedential_status', '?')}")
    sub_opinions = cluster.get("sub_opinions", [])
    if sub_opinions:
        print(f"Sub-opinions: {len(sub_opinions)}")
        for op in sub_opinions[:5]:
            print(f"  {op}")


def cmd_investments(args):
    """Search judge investment holdings by company/description."""
    client = _client()
    results = client.get_investments(
        person_id=getattr(args, "person_id", None),
        description=args.query,
        max_results=args.limit,
    )
    _record_search(
        "investments",
        len(results),
        args.query,
        person_id=getattr(args, "person_id", None),
    )
    if write_output(results, args, summary=f"Investment search '{args.query}': {len(results)} results"):
        return
    print(f"Found {len(results)} investment records matching '{args.query}'")
    for inv in results:
        desc = inv.get("description", "?")
        value = inv.get("gross_value_code", "?")
        income = inv.get("income_during_reporting_period_code", "?")
        print(f"  {desc}")
        print(f"    Value code: {value} | Income code: {income}")
        print(f"    Disclosure: {inv.get('financial_disclosure', '?')}")
        print()


def cmd_reimbursements(args):
    """Search judge travel reimbursements by source."""
    client = _client()
    results = client.get_reimbursements(
        person_id=getattr(args, "person_id", None),
        source=args.query,
        max_results=args.limit,
    )
    _record_search(
        "reimbursements",
        len(results),
        args.query,
        person_id=getattr(args, "person_id", None),
    )
    if write_output(results, args, summary=f"Reimbursement search '{args.query}': {len(results)} results"):
        return
    print(f"Found {len(results)} reimbursement records matching '{args.query}'")
    for r in results:
        source = r.get("source", "?")
        location = r.get("location", "?")
        purpose = r.get("purpose", "?")
        dates = r.get("dates_reimbursed", "?")
        print(f"  {source}")
        print(f"    Location: {location} | Purpose: {purpose} | Dates: {dates}")
        print()


def cmd_fjc(args):
    """Search the FJC Integrated Database (federal case metadata)."""
    try:
        from requests.exceptions import Timeout
    except ImportError:  # pragma: no cover - requests is a project dependency
        Timeout = TimeoutError

    client = _client()
    try:
        results = client.search_fjc(
            plaintiff=args.plaintiff,
            defendant=args.defendant,
            nature_of_suit=args.nos,
            date_filed_after=args.after,
            date_filed_before=args.before,
            max_results=args.limit,
        )
    except Timeout:
        print(
            "ERROR: CourtListener FJC search timed out after one bounded "
            "request; try a narrower name or date range.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    query_desc = args.plaintiff or args.defendant or "all"
    _record_search(
        "fjc",
        len(results),
        query_desc,
        plaintiff=args.plaintiff,
        defendant=args.defendant,
        nature_of_suit=args.nos,
        after=args.after,
        before=args.before,
    )
    if write_output(results, args, summary=f"FJC search: {len(results)} results"):
        return
    print(f"Found {len(results)} FJC records")
    for r in results:
        plaintiff = r.get("plaintiff", "?")
        defendant = r.get("defendant", "?")
        nos = r.get("nature_of_suit", "?")
        disposition = r.get("disposition", "?")
        print(f"  {plaintiff} v. {defendant}")
        print(f"    NOS: {nos} | Disposition: {disposition}")
        print()


def cmd_career(args):
    """Show full career timeline for a judge."""
    client = _client()
    judges = client.search_judges(name=args.name, max_results=5)
    if not judges:
        print(f"No judges found matching '{args.name}'")
        return

    # Use first result — search API returns different format than REST
    judge = judges[0]
    person_id = judge.get("id")
    if not person_id:
        print(f"Could not determine person ID for '{args.name}'")
        return

    person = client.get_person(person_id)
    positions = client.get_positions(person_id)
    educations = client.get_educations(person_id)
    affiliations = client.get_political_affiliations(person_id)

    result = {
        "person": person,
        "positions": positions,
        "education": educations,
        "political_affiliations": affiliations,
    }

    _record_search("career", len(positions), args.name)
    if write_output(result, args, summary=f"Career for {args.name}: {len(positions)} positions"):
        return

    name = person.get("name_full", args.name)
    print(f"=== Career: {name} (ID: {person_id}) ===")
    dob = person.get("date_dob", "")
    if dob:
        print(f"Born: {dob}")

    if educations:
        print(f"\nEducation ({len(educations)}):")
        for e in educations:
            school = e.get("school", {})
            school_name = school.get("name", "?") if isinstance(school, dict) else str(school)
            degree = e.get("degree_level", "?")
            year = e.get("degree_year", "?")
            print(f"  {school_name} — {degree} ({year})")

    if positions:
        print(f"\nPositions ({len(positions)}):")
        for p in positions:
            court = p.get("court", {})
            court_name = court.get("short_name", "?") if isinstance(court, dict) else str(court)
            pos_type = p.get("position_type", "?")
            start = p.get("date_start", "?")
            end = p.get("date_termination", "present")
            appointer = p.get("appointer", "")
            appointer_str = ""
            if appointer:
                if isinstance(appointer, dict):
                    appointer_str = f" (appointed by {appointer.get('name_full', '?')})"
                else:
                    appointer_str = f" (appointer: {appointer})"
            print(f"  {pos_type} at {court_name}, {start} - {end}{appointer_str}")

    if affiliations:
        print(f"\nPolitical Affiliations ({len(affiliations)}):")
        for a in affiliations:
            party = a.get("political_party", "?")
            source = a.get("source", "?")
            print(f"  {party} (source: {source})")


def main():
    parser = argparse.ArgumentParser(description="CourtListener API for OSINT investigation")
    sub = parser.add_subparsers(dest="command", required=True)

    # search — enhanced with field operators
    p = sub.add_parser("search", help="Search (supports field operators: --party, --firm, --attorney)")
    p.add_argument("query", nargs="?", default="", help="Search query (optional if using field operators)")
    p.add_argument("--type", default="r", help="o=opinions, r=recap/dockets, rd=recap docs, p=people, oa=oral args")
    p.add_argument("--court", help="Court filter (e.g., nysd, ca2, scotus, flsd)")
    p.add_argument("--party", help="Party name field operator")
    p.add_argument("--firm", help="Law firm field operator")
    p.add_argument("--attorney", help="Attorney name field operator")
    p.add_argument("--assigned-to", help="Assigned judge field operator")
    p.add_argument("--docket-number", help="Docket number field operator")
    p.add_argument("--semantic", action="store_true", help="Enable semantic search (opinions)")
    p.add_argument("--highlight", action="store_true", help="Enable result highlighting")
    p.add_argument("--after", help="Filed after (YYYY-MM-DD)")
    p.add_argument("--before", help="Filed before (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # cases
    p = sub.add_parser("cases", help="Search RECAP dockets")
    p.add_argument("query")
    p.add_argument("--court")
    p.add_argument("--after", help="Filed after (YYYY-MM-DD)")
    p.add_argument("--before", help="Filed before (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # docket
    p = sub.add_parser("docket", help="Get docket by ID")
    p.add_argument("docket_id", type=int)
    add_output_args(p)

    # party — uses search API with party:"Name" (not blocked /parties/ endpoint)
    p = sub.add_parser("party", help="Search cases by party name (via search API)")
    p.add_argument("name")
    p.add_argument("--court")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # opinions
    p = sub.add_parser("opinions", help="Search opinions")
    p.add_argument("query")
    p.add_argument("--court")
    p.add_argument("--semantic", action="store_true", help="Semantic search")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # judge
    p = sub.add_parser("judge", help="Search judges")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=10)
    add_output_args(p)

    # disclosures
    p = sub.add_parser("disclosures", help="Financial disclosures")
    p.add_argument("--person-id", type=int, help="Judge person ID")
    p.add_argument("--year", type=int)
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # opinion — full text by ID
    p = sub.add_parser("opinion", help="Fetch full opinion text by ID")
    p.add_argument("opinion_id", type=int, help="Opinion ID or cluster ID")
    p.add_argument(
        "--id-type",
        choices=["auto", "cluster", "opinion"],
        default="auto",
        help=(
            "Interpret the ID as a cluster or raw opinion ID. Auto (default) "
            "checks the cluster endpoint first because the numeric ID spaces overlap."
        ),
    )
    p.add_argument("--lines", type=int, default=500, help="Max lines to show")
    add_output_args(p)

    # recap-search
    p = sub.add_parser("recap-search", help="Search RECAP documents (type=rd)")
    p.add_argument("query", help="Search query")
    p.add_argument("--court", help="Court filter")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # download
    p = sub.add_parser("download", help="Download a RECAP document PDF")
    p.add_argument("url", help="Full URL or filepath_local from RECAP")
    p.add_argument("output_file", help="Local path to save the PDF")
    p.add_argument(
        "--extract-text",
        action="store_true",
        help="Extract text via PyMuPDF, falling back to pdftotext",
    )

    # citations — citation graph
    p = sub.add_parser("citations", help="Citation graph for an opinion cluster")
    p.add_argument("cluster_id", type=int)
    p.add_argument("--limit", type=int, default=50)
    add_output_args(p)

    # resolve-cite — resolve citation text
    p = sub.add_parser("resolve-cite", help="Resolve citation text to cluster IDs")
    p.add_argument("text", help="Citation text (e.g., '410 U.S. 113')")
    add_output_args(p)

    # cluster — opinion cluster detail
    p = sub.add_parser("cluster", help="Get opinion cluster details")
    p.add_argument("cluster_id", type=int)
    add_output_args(p)

    # investments — judge investment search
    p = sub.add_parser("investments", help="Search judge investment holdings by company")
    p.add_argument("query", help="Company/description to search")
    p.add_argument("--person-id", type=int, help="Filter to specific judge")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # reimbursements — judge travel reimbursements
    p = sub.add_parser("reimbursements", help="Search judge travel reimbursements by source")
    p.add_argument("query", help="Source to search (e.g., 'Federalist Society')")
    p.add_argument("--person-id", type=int, help="Filter to specific judge")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # fjc — FJC Integrated Database
    p = sub.add_parser("fjc", help="Search FJC Integrated Database (federal case metadata)")
    p.add_argument("--plaintiff", help="Plaintiff name")
    p.add_argument("--defendant", help="Defendant name")
    p.add_argument("--nos", help="Nature of suit code")
    p.add_argument("--after", help="Filed after (YYYY-MM-DD)")
    p.add_argument("--before", help="Filed before (YYYY-MM-DD)")
    p.add_argument("--limit", type=int, default=20)
    add_output_args(p)

    # career — judge career timeline
    p = sub.add_parser("career", help="Full career timeline for a judge")
    p.add_argument("name", help="Judge name")
    add_output_args(p)

    args = parser.parse_args()
    if not hasattr(args, "json_out"):
        args.json_out = False

    handlers = {
        "search": cmd_search,
        "cases": cmd_cases,
        "docket": cmd_docket,
        "party": cmd_party,
        "opinions": cmd_opinions,
        "judge": cmd_judge,
        "disclosures": cmd_disclosures,
        "opinion": cmd_opinion,
        "recap-search": cmd_recap_search,
        "download": cmd_download,
        "citations": cmd_citations,
        "resolve-cite": cmd_resolve_cite,
        "cluster": cmd_cluster,
        "investments": cmd_investments,
        "reimbursements": cmd_reimbursements,
        "fjc": cmd_fjc,
        "career": cmd_career,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
