#!/usr/bin/env python3
"""
DocumentCloud API wrapper for OSINT investigations.

Searches DocumentCloud's public document archive. No authentication needed
for public documents. Text and PDF access via S3 URLs.

Key project: Epstein Documents (ID 216915) — 6 docs, 6,613 pages
(Giuffre v. Maxwell unsealed docs + MCC records)

Usage:
    # Full-text search across all DocumentCloud
    python tools/query_documentcloud.py search "Jeffrey Epstein" --limit 20
    python tools/query_documentcloud.py search "Maxwell" --project 216915

    # List documents in Epstein project
    python tools/query_documentcloud.py project
    python tools/query_documentcloud.py project 216915

    # Get document detail + text preview
    python tools/query_documentcloud.py document 24466257
    python tools/query_documentcloud.py document 24466257 --full

    # Fetch full text or specific page text
    python tools/query_documentcloud.py text 24466257
    python tools/query_documentcloud.py text 24466257 --page 5
    python tools/query_documentcloud.py text 24466257 --output /tmp/doc.txt

    # Download PDF
    python tools/query_documentcloud.py download 24466257
    python tools/query_documentcloud.py download 24466257 --dir /tmp/pdfs
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

API_BASE = "https://api.www.documentcloud.org/api/"
S3_BASE = "https://s3.documentcloud.org/documents"
# DocumentCloud, MuckRock, and Squarelet share one SSO. A Squarelet JWT minted
# from the MuckRock account authenticates the DocumentCloud API and lifts the
# anonymous ">500 calls / 24h per IP" rate limit.
AUTH_BASE = "https://accounts.muckrock.com/api/"
USER_AGENT = "OSINT-Research/1.0"
DEFAULT_PROJECT = 216915  # Epstein Documents
RATE_LIMIT_DELAY = 0.5  # seconds between paginated requests

# Short-lived JWTs cached outside the repo (never committed). The access token
# lives ~5 min; DocumentCloud treats an expired bearer as anonymous (429), not as
# 401, so we check the exp claim before reuse and also refresh reactively.
_TOKEN_CACHE_PATH = os.path.join(
    os.path.expanduser("~"), ".cache", "ithildin", "documentcloud_tokens.json"
)
_ACCESS_TOKEN = None
_TOKEN_LOADED = False


def _post_json(url, payload):
    """POST a JSON body and return the decoded JSON response."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _read_token_cache():
    try:
        with open(_TOKEN_CACHE_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_token_cache(access, refresh):
    try:
        os.makedirs(os.path.dirname(_TOKEN_CACHE_PATH), exist_ok=True)
        with open(_TOKEN_CACHE_PATH, "w") as f:
            json.dump({"access": access, "refresh": refresh}, f)
        os.chmod(_TOKEN_CACHE_PATH, 0o600)
    except OSError:
        pass  # caching is best-effort; auth still works without it


def _env_creds():
    """Load MuckRock/Squarelet credentials from the repo-local .env."""
    try:
        from tools.env_loader import load_env_file
    except ImportError:
        from env_loader import load_env_file
    load_env_file()
    return os.environ.get("MUCKROCK_USERNAME"), os.environ.get("MUCKROCK_PASSWORD")


def _mint_tokens():
    """Obtain (access, refresh) tokens: refresh the cached pair, else use creds.

    Returns (None, None) when no credentials are configured, so the caller
    falls back to anonymous access transparently.
    """
    refresh = _read_token_cache().get("refresh")
    if refresh:
        try:
            j = _post_json(f"{AUTH_BASE}refresh/", {"refresh": refresh})
            _write_token_cache(j["access"], j["refresh"])
            return j["access"], j["refresh"]
        except (HTTPError, URLError, ValueError, KeyError):
            pass  # refresh expired/invalid — fall through to username/password
    user, password = _env_creds()
    if not (user and password):
        return None, None
    try:
        j = _post_json(f"{AUTH_BASE}token/", {"username": user, "password": password})
        _write_token_cache(j["access"], j["refresh"])
        return j["access"], j["refresh"]
    except (HTTPError, URLError, ValueError, KeyError) as e:
        print(f"  DocumentCloud auth failed ({e}); continuing anonymously",
              file=sys.stderr)
        return None, None


def _token_is_fresh(token, skew=60):
    """True if a JWT's exp claim is more than `skew` seconds in the future."""
    if not token:
        return False
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # restore base64 padding
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
    except (ValueError, IndexError, TypeError):
        return False
    return exp is not None and exp - time.time() > skew


def _access_token(force_refresh=False):
    """Return a usable (unexpired) access token, or None for anonymous."""
    global _ACCESS_TOKEN, _TOKEN_LOADED
    if force_refresh:
        _ACCESS_TOKEN, _ = _mint_tokens()
        _TOKEN_LOADED = True
        return _ACCESS_TOKEN
    if _TOKEN_LOADED:
        return _ACCESS_TOKEN
    # Reuse a cached access token only while it is still valid; a stale bearer is
    # silently downgraded to anonymous (429), never rejected with 401.
    cached = _read_token_cache().get("access")
    _ACCESS_TOKEN = cached if _token_is_fresh(cached) else _mint_tokens()[0]
    _TOKEN_LOADED = True
    return _ACCESS_TOKEN


def _request(url, _retries=2, _auth_retried=False):
    """GET the API with Bearer auth (when available) and transient-error retry."""
    token = _access_token()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        # A stale/expired bearer is rejected as 401 OR silently downgraded to
        # anonymous and rate-limited (429 with an "anonymous user" body). Either
        # way our token was not honored — mint a fresh one and retry once.
        token_rejected = e.code == 401 or (e.code == 429 and "anonymous" in body.lower())
        if token_rejected and token and not _auth_retried:
            if _access_token(force_refresh=True):
                return _request(url, _retries=_retries, _auth_retried=True)
        if e.code in (429, 500, 502, 503) and _retries > 0:
            wait = 3 if e.code == 429 else 2
            print(f"  HTTP {e.code}, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
            return _request(url, _retries=_retries - 1, _auth_retried=_auth_retried)
        print(f"ERROR: HTTP {e.code}: {body}", file=sys.stderr)
        return None
    except URLError as e:
        print(f"ERROR: Cannot reach DocumentCloud: {e.reason}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON response: {e}", file=sys.stderr)
        return None


def _fetch_text(url, _retries=2):
    """Fetch raw text from an S3 URL. Returns string or None.

    S3 asset serving is not behind the API rate limiter, but it can still throttle
    transiently under concurrent load, so retry 429/5xx and network errors.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 404:
            print("  Text not available (404)", file=sys.stderr)
            return None
        if e.code in (429, 500, 502, 503) and _retries > 0:
            time.sleep(2)
            return _fetch_text(url, _retries=_retries - 1)
        print(f"ERROR: HTTP {e.code} fetching text", file=sys.stderr)
        return None
    except URLError as e:
        if _retries > 0:
            time.sleep(2)
            return _fetch_text(url, _retries=_retries - 1)
        print(f"ERROR: Cannot fetch text: {e.reason}", file=sys.stderr)
        return None


def _fetch_binary(url, _retries=2):
    """Fetch binary content from a URL. Returns bytes or None.

    Retries transient S3 throttling/network errors, mirroring _fetch_text.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=120) as resp:
            return resp.read()
    except HTTPError as e:
        if e.code == 404:
            print("  File not available (404)", file=sys.stderr)
            return None
        if e.code in (429, 500, 502, 503) and _retries > 0:
            time.sleep(2)
            return _fetch_binary(url, _retries=_retries - 1)
        print(f"ERROR: HTTP {e.code} fetching file", file=sys.stderr)
        return None
    except URLError as e:
        if _retries > 0:
            time.sleep(2)
            return _fetch_binary(url, _retries=_retries - 1)
        print(f"ERROR: Cannot fetch file: {e.reason}", file=sys.stderr)
        return None


def _s3_text_url(doc_id, slug):
    """Full document text URL."""
    return f"{S3_BASE}/{doc_id}/{slug}.txt"


def _s3_page_text_url(doc_id, slug, page):
    """Single page text URL (1-indexed)."""
    return f"{S3_BASE}/{doc_id}/pages/{slug}-p{page}.txt"


def _s3_pdf_url(doc_id, slug):
    """PDF download URL."""
    return f"{S3_BASE}/{doc_id}/{slug}.pdf"


def _format_doc_row(doc):
    """Format a document dict for display."""
    doc_id = doc.get("id", "?")
    title = doc.get("title", "Untitled")
    pages = doc.get("page_count", 0)
    source = doc.get("source", "")
    org = doc.get("organization", "")
    if isinstance(org, dict):
        org = org.get("name", "")
    created = doc.get("created_at", "")[:10]
    return doc_id, title, pages, source, org, created


def _quoted_phrase(query):
    """Return the contents of a query made up of one quoted phrase."""
    match = re.fullmatch(r'\s*"([^"]+)"\s*', query)
    return match.group(1) if match else None


def _contains_exact_phrase(text, phrase):
    """Match adjacent phrase tokens with flexible whitespace and case."""
    tokens = re.findall(r"[^\W_]+", phrase.casefold())
    if not tokens:
        return False
    pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, tokens)) + r"(?!\w)"
    return re.search(pattern, text.casefold()) is not None


def _document_contains_exact_phrase(doc, phrase):
    """Verify a phrase against searchable metadata or the document text."""
    metadata = "\n".join(
        str(doc.get(field) or "") for field in ("title", "description")
    )
    if _contains_exact_phrase(metadata, phrase):
        return True

    doc_id = doc.get("id")
    slug = doc.get("slug")
    if not doc_id or not slug:
        return False
    text = _fetch_text(_s3_text_url(doc_id, slug))
    return bool(text and _contains_exact_phrase(text, phrase))


def _search_response_in_scope(data, query, project_id=None):
    """Verify the API actually executed a scoped full-text search."""
    results = data.get("results")
    if (
        not isinstance(results, list)
        or not isinstance(data.get("count"), int)
        or not isinstance(data.get("escaped"), bool)
    ):
        print(
            "ERROR: DocumentCloud returned a non-search response; refusing "
            "potentially unfiltered documents.",
            file=sys.stderr,
        )
        return False

    next_url = data.get("next")
    if next_url:
        parsed = urlparse(next_url)
        next_params = parse_qs(parsed.query)
        query_preserved = next_params.get("q") == [query]
        project_preserved = not project_id or (
            next_params.get("project") == [str(project_id)]
            or next_params.get("projects") == [str(project_id)]
        )
        if not parsed.path.endswith("/documents/search/") or not query_preserved or not project_preserved:
            print(
                "ERROR: DocumentCloud pagination dropped the search scope; "
                "refusing potentially unfiltered documents.",
                file=sys.stderr,
            )
            return False

    return True


# ── Commands ───────────────────────────────────────────────────────────


def cmd_search(args):
    """Full-text search across DocumentCloud documents."""
    query = args.query
    exact_phrase = _quoted_phrase(query)
    project_id = getattr(args, "project", None)
    limit = args.limit

    params = {"q": query, "per_page": min(limit, 100)}
    if project_id:
        params["project"] = project_id

    url = f"{API_BASE}documents/search/?{urlencode(params)}"

    all_results = []
    page_num = 0
    while url and len(all_results) < limit:
        page_num += 1
        if page_num > 1:
            time.sleep(RATE_LIMIT_DELAY)

        data = _request(url)
        if not data:
            break
        if not _search_response_in_scope(data, query, project_id):
            raise SystemExit(1)

        results = data.get("results", [])
        if not results:
            break

        all_results.extend(results)
        url = data.get("next")  # cursor-based pagination

    # Trim to limit
    all_results = all_results[:limit]
    if exact_phrase is not None:
        candidates = all_results
        all_results = [
            doc for doc in candidates
            if _document_contains_exact_phrase(doc, exact_phrase)
        ]
        for doc in all_results:
            doc["_search_match"] = "exact_phrase_verified"
        skipped = len(candidates) - len(all_results)
        if skipped:
            print(
                f"INFO: excluded {skipped} DocumentCloud token-cooccurrence "
                f"candidate(s) that did not contain the exact phrase "
                f"{query}.",
                file=sys.stderr,
            )

    # Output
    scope = f" in project {project_id}" if project_id else ""
    semantics = " (exact phrase verified)" if exact_phrase is not None else ""
    summary = f"DocumentCloud search '{query}'{scope}{semantics}"

    if write_output(all_results, args, summary=summary):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(all_results, indent=2, default=str))
        return

    if not all_results:
        print(f"No documents found for '{query}'{scope}")
        return

    print(f"Found {len(all_results)} documents for '{query}'{scope}")
    print()
    for doc in all_results:
        doc_id, title, pages, source, org, created = _format_doc_row(doc)
        print(f"  [{doc_id}] {title}")
        print(f"    Pages: {pages}  Source: {source or '-'}  Org: {org or '-'}  Created: {created}")
        desc = doc.get("description", "")
        if desc:
            desc_trunc = desc[:120] + "..." if len(desc) > 120 else desc
            print(f"    {desc_trunc}")
        print()


def cmd_project(args):
    """List documents in a project."""
    project_id = args.project_id or DEFAULT_PROJECT

    params = {"project": project_id, "per_page": 100}
    url = f"{API_BASE}documents/?{urlencode(params)}"

    all_docs = []
    page_num = 0
    while url:
        page_num += 1
        if page_num > 1:
            time.sleep(RATE_LIMIT_DELAY)

        data = _request(url)
        if not data:
            break

        results = data.get("results", [])
        if not results:
            break

        all_docs.extend(results)
        url = data.get("next")

    summary = f"DocumentCloud project {project_id}"

    if write_output(all_docs, args, summary=summary):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(all_docs, indent=2, default=str))
        return

    if not all_docs:
        print(f"No documents found in project {project_id}")
        return

    total_pages = sum(d.get("page_count", 0) for d in all_docs)
    print(f"Project {project_id}: {len(all_docs)} documents, {total_pages:,} total pages")
    print()
    for doc in all_docs:
        doc_id, title, pages, source, org, created = _format_doc_row(doc)
        print(f"  [{doc_id}] {title}")
        print(f"    Pages: {pages}  Source: {source or '-'}  Created: {created}")
        desc = doc.get("description", "")
        if desc:
            desc_trunc = desc[:120] + "..." if len(desc) > 120 else desc
            print(f"    {desc_trunc}")
        print()


def cmd_document(args):
    """Get document detail and text preview."""
    doc_id = args.doc_id
    show_full = args.full

    url = f"{API_BASE}documents/{doc_id}/"
    data = _request(url)
    if not data:
        print(f"Document {doc_id} not found", file=sys.stderr)
        return

    title = data.get("title", "Untitled")
    slug = data.get("slug", "")
    pages = data.get("page_count", 0)
    source = data.get("source", "")
    description = data.get("description", "")
    org = data.get("organization", "")
    if isinstance(org, dict):
        org = org.get("name", "")
    status = data.get("status", "")
    access = data.get("access", "")
    created = data.get("created_at", "")[:19]
    updated = data.get("updated_at", "")[:19]
    canonical = data.get("canonical_url", "")
    projects = data.get("projects", [])

    # Fetch text from S3
    text = None
    if slug:
        text_url = _s3_text_url(doc_id, slug)
        text = _fetch_text(text_url)

    result = {
        "id": doc_id,
        "title": title,
        "slug": slug,
        "page_count": pages,
        "source": source,
        "description": description,
        "organization": org,
        "status": status,
        "access": access,
        "created_at": created,
        "updated_at": updated,
        "canonical_url": canonical,
        "projects": projects,
        "text_preview": (text[:2000] if text and not show_full else text),
        "text_length": len(text) if text else 0,
    }

    if write_output(result, args, summary=f"DocumentCloud doc {doc_id}"):
        return

    if getattr(args, "json_out", False):
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"Document: {title}")
    print(f"ID: {doc_id}")
    print(f"Slug: {slug}")
    print(f"Pages: {pages}")
    print(f"Source: {source or '-'}")
    print(f"Organization: {org or '-'}")
    print(f"Status: {status}  Access: {access}")
    print(f"Created: {created}  Updated: {updated}")
    if description:
        print(f"Description: {description}")
    if canonical:
        print(f"URL: {canonical}")
    if projects:
        print(f"Projects: {projects}")
    print()

    if text:
        text_display = text if show_full else text[:2000]
        print(f"--- Text ({len(text):,} chars{'' if show_full else ', first 2000'}) ---")
        print(text_display)
        if not show_full and len(text) > 2000:
            print(f"\n... [{len(text) - 2000:,} more chars — use --full to see all]")
    else:
        print("  [Text not available]")


def cmd_text(args):
    """Fetch full text or specific page text from S3."""
    doc_id = args.doc_id
    page = getattr(args, "page", None)

    # Need slug to build S3 URL — fetch doc metadata first
    url = f"{API_BASE}documents/{doc_id}/"
    data = _request(url)
    if not data:
        print(f"Document {doc_id} not found", file=sys.stderr)
        return

    slug = data.get("slug", "")
    title = data.get("title", "Untitled")
    total_pages = data.get("page_count", 0)

    if not slug:
        print(f"ERROR: No slug for document {doc_id}", file=sys.stderr)
        return

    if page:
        if page < 1 or (total_pages and page > total_pages):
            print(f"ERROR: Page {page} out of range (1-{total_pages})", file=sys.stderr)
            return
        text_url = _s3_page_text_url(doc_id, slug, page)
        label = f"page {page}"
    else:
        text_url = _s3_text_url(doc_id, slug)
        label = "full text"

    text = _fetch_text(text_url)
    if text is None:
        print(f"Text not available for {label} of '{title}'", file=sys.stderr)
        return

    # --output writes text to file (not JSON)
    output_path = getattr(args, "output", None)
    if output_path:
        with open(output_path, "w") as f:
            f.write(text)
        print(f"{len(text):,} chars ({label} of '{title}') saved to {output_path}")
        return

    if getattr(args, "json_out", False):
        result = {
            "id": doc_id,
            "title": title,
            "slug": slug,
            "page": page,
            "text": text,
            "length": len(text),
        }
        print(json.dumps(result, indent=2, default=str))
        return

    page_label = f" (page {page}/{total_pages})" if page else f" ({total_pages} pages)"
    print(f"--- {title}{page_label} --- {len(text):,} chars ---")
    print(text)


def cmd_download(args):
    """Download PDF to local directory."""
    doc_id = args.doc_id
    out_dir = args.dir or "datasets/documentcloud"

    # Fetch metadata for slug and title
    url = f"{API_BASE}documents/{doc_id}/"
    data = _request(url)
    if not data:
        print(f"Document {doc_id} not found", file=sys.stderr)
        return

    slug = data.get("slug", "")
    title = data.get("title", "Untitled")
    pages = data.get("page_count", 0)

    if not slug:
        print(f"ERROR: No slug for document {doc_id}", file=sys.stderr)
        return

    os.makedirs(out_dir, exist_ok=True)
    filename = f"{doc_id}-{slug}.pdf"
    filepath = os.path.join(out_dir, filename)

    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"Already exists: {filepath} ({size:,} bytes)")
        return

    pdf_url = _s3_pdf_url(doc_id, slug)
    print(f"Downloading: {title} ({pages} pages)")
    print(f"  URL: {pdf_url}")

    content = _fetch_binary(pdf_url)
    if content is None:
        print(f"ERROR: Failed to download PDF for {doc_id}", file=sys.stderr)
        return

    with open(filepath, "wb") as f:
        f.write(content)

    print(f"  Saved: {filepath} ({len(content):,} bytes)")


# ── CLI ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Query DocumentCloud API for public documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    subparsers.required = True

    # search
    sp = subparsers.add_parser("search", help="Full-text search across DocumentCloud")
    sp.add_argument(
        "query",
        help=(
            "Search query; a query consisting of one quoted phrase is "
            "post-verified against document text"
        ),
    )
    sp.add_argument("--project", type=int, help="Scope search to project ID (e.g. 216915)")
    sp.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
    add_output_args(sp)
    sp.set_defaults(func=cmd_search)

    # project
    sp = subparsers.add_parser("project", help="List documents in a project")
    sp.add_argument("project_id", nargs="?", type=int, default=None,
                    help=f"Project ID (default: {DEFAULT_PROJECT} = Epstein Documents)")
    add_output_args(sp)
    sp.set_defaults(func=cmd_project)

    # document
    sp = subparsers.add_parser("document", help="Get document detail + text preview")
    sp.add_argument("doc_id", help="Document ID")
    sp.add_argument("--full", action="store_true", help="Show full text (not just first 2000 chars)")
    add_output_args(sp)
    sp.set_defaults(func=cmd_document)

    # text
    sp = subparsers.add_parser("text", help="Fetch document text from S3")
    sp.add_argument("doc_id", help="Document ID")
    sp.add_argument("--page", type=int, help="Specific page number (1-indexed)")
    add_output_args(sp)
    sp.set_defaults(func=cmd_text)

    # download
    sp = subparsers.add_parser("download", help="Download PDF")
    sp.add_argument("doc_id", help="Document ID")
    sp.add_argument("--dir", help="Output directory (default: datasets/documentcloud)")
    sp.set_defaults(func=cmd_download)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
