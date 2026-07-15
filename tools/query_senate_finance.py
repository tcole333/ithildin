#!/usr/bin/env python3
"""Search and read the U.S. Senate Finance Committee public archive.

The committee's own site exposes an unauthenticated HTML search interface and
stable detail pages with primary-source attachments.  This tool keeps requests
bounded and returns the detail-page text plus the attachment URLs needed for
auditable follow-up.

Endpoint probe (2026-07-14):
    Search: https://www.finance.senate.gov/search/?q=...&page=...
    Detail: https://www.finance.senate.gov/<section>/<slug>
    Files:  https://www.finance.senate.gov/download/<slug>

Usage:
    uv run python tools/query_senate_finance.py search \
        "media-based ministries" --limit 20 --output "$WORKDIR/sfc-search.json"
    uv run python tools/query_senate_finance.py item \
        /ranking-members-news/grassley-releases-review-of-tax-issues-raised-by-media-based-ministries \
        --output "$WORKDIR/sfc-item.json"
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output


BASE_URL = "https://www.finance.senate.gov"
SEARCH_URL = f"{BASE_URL}/search/"
SOURCE = "senate_finance"
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
REQUEST_DELAY = 0.5
MAX_RESULTS = 100
MAX_RETRIES = 2
MAX_HTML_BYTES = 5_000_000
TIMEOUT = 30
ALLOWED_HOSTS = frozenset({"finance.senate.gov", "www.finance.senate.gov"})

_last_request_at = 0.0


class SenateFinanceError(RuntimeError):
    """Raised when the official committee archive cannot be queried safely."""


@dataclass(frozen=True)
class HtmlResponse:
    url: str
    text: str


def _official_url(value: str) -> str:
    """Resolve a path/URL and reject redirects or inputs outside senate.gov."""
    url = urljoin(f"{BASE_URL}/", value.strip())
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise SenateFinanceError(
            "item URL must use https://www.finance.senate.gov"
        )
    return url


def _reference_for_url(value: str) -> str:
    path = urlparse(_official_url(value)).path.lstrip("/")
    # Some indexed download results append this switch inside the URL path.
    # The base /download/<slug> page is stable and refreshes to the same PDF;
    # omitting the switch also keeps evidence references shell/Markdown-safe.
    path = re.sub(r"&download=1$", "", path, flags=re.I)
    return f"SENATE_FINANCE:{path}"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })
    return session


def _request_html(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, object] | None = None,
) -> HtmlResponse:
    """Fetch one official HTML page with rate limiting and bounded retries."""
    global _last_request_at

    safe_url = _official_url(url)
    for attempt in range(MAX_RETRIES + 1):
        elapsed = time.monotonic() - _last_request_at
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        try:
            _last_request_at = time.monotonic()
            response = session.get(
                safe_url,
                params=params,
                timeout=TIMEOUT,
                allow_redirects=True,
                stream=True,
            )
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                time.sleep(0.75 * (2**attempt))
                continue
            raise SenateFinanceError(f"Senate Finance request failed: {exc}") from exc

        # A compromised or changed route must not silently carry the query to a
        # non-Senate host.
        try:
            final_url = _official_url(response.url)
        except Exception:
            response.close()
            raise
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait = (
                        min(float(retry_after), 10.0)
                        if retry_after
                        else 0.75 * (2**attempt)
                    )
                except ValueError:
                    wait = 0.75 * (2**attempt)
                response.close()
                time.sleep(wait)
                continue

        if response.status_code != 200:
            response.close()
            raise SenateFinanceError(
                f"Senate Finance returned HTTP {response.status_code} for {final_url}"
            )

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type:
            response.close()
            raise SenateFinanceError(
                f"expected an HTML archive page, received {content_type or 'unknown content type'}"
            )
        content_length = response.headers.get("Content-Length")
        try:
            declared_bytes = int(content_length) if content_length else None
        except ValueError:
            declared_bytes = None
        if declared_bytes is not None and declared_bytes > MAX_HTML_BYTES:
            response.close()
            raise SenateFinanceError(
                f"archive page exceeds the {MAX_HTML_BYTES}-byte response limit"
            )

        body = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                body.extend(chunk)
                if len(body) > MAX_HTML_BYTES:
                    raise SenateFinanceError(
                        f"archive page exceeds the {MAX_HTML_BYTES}-byte response limit"
                    )
        finally:
            response.close()

        encoding = response.encoding or "utf-8"
        return HtmlResponse(
            url=final_url,
            text=bytes(body).decode(encoding, errors="replace"),
        )

    raise SenateFinanceError("Senate Finance request exhausted retries")


def _clean_text(node) -> str:
    text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([,;:!?])(?=\S)", r"\1 ", text)
    return re.sub(r"(?<=\w)\s*-\s*(?=\w)", "-", text)


def parse_search_page(html: str, source_url: str) -> tuple[int, list[dict]]:
    """Parse one committee search-results page."""
    soup = BeautifulSoup(html, "html.parser")
    summary = soup.select_one(".sr-results-summary")
    total = 0
    if summary:
        match = re.search(r"([\d,]+)\s+results?\s+found", _clean_text(summary), re.I)
        if match:
            total = int(match.group(1).replace(",", ""))

    results: list[dict] = []
    for row in soup.select("#sr-listing > li"):
        link = row.select_one("a.sr-title[href]")
        if not link:
            continue
        url = _official_url(urljoin(source_url, link.get("href", "")))
        date_node = row.select_one(".sr-date")
        summary_node = row.select_one(".sr-summary")
        results.append({
            "title": _clean_text(link),
            "date": _clean_text(date_node) if date_node else None,
            "summary": _clean_text(summary_node) if summary_node else None,
            "url": url,
            "evidence_ref": _reference_for_url(url),
        })

    return total, results


def parse_item_page(html: str, source_url: str) -> dict:
    """Parse a committee release/detail page and its related files."""
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"][href]')
    canonical_url = _official_url(
        canonical.get("href", source_url) if canonical else source_url
    )

    main = soup.select_one("#newscontent") or soup.select_one("#main_column")
    if not main:
        raise SenateFinanceError("could not locate the article body on this archive page")

    title_node = main.select_one("h1.main_page_title") or main.select_one("h1")
    if not title_node:
        raise SenateFinanceError("could not locate the article title on this archive page")

    date_node = main.select_one("span.date") or main.select_one("time")
    body_node = main.select_one("#pressrelease") or main.select_one("article") or main
    paragraphs = [
        _clean_text(node)
        for node in body_node.select("p")
        if _clean_text(node)
    ]

    related_files: list[dict] = []
    seen_urls: set[str] = set()
    for aside in soup.select("aside"):
        heading = aside.select_one("h1, h2, h3")
        if not heading or "related files" not in _clean_text(heading).lower():
            continue
        for link in aside.select("a[href]"):
            url = _official_url(urljoin(canonical_url, link.get("href", "")))
            if url in seen_urls:
                continue
            seen_urls.add(url)
            title = re.sub(
                r"^(?:acrobat|document|spreadsheet)\s+",
                "",
                _clean_text(link),
                flags=re.I,
            )
            related_files.append({
                "title": title,
                "url": url,
                "evidence_ref": _reference_for_url(url),
            })

    return {
        "source": SOURCE,
        "title": _clean_text(title_node),
        "date": _clean_text(date_node) if date_node else None,
        "url": canonical_url,
        "evidence_ref": _reference_for_url(canonical_url),
        "paragraphs": paragraphs,
        "text": "\n\n".join(paragraphs),
        "related_files": related_files,
    }


def _log(query: str, count: int) -> None:
    try:
        log_search(query, SOURCE, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit(payload, args: argparse.Namespace, summary: str) -> None:
    if write_output(payload, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return

    if isinstance(payload, dict) and "results" in payload:
        print(f"{payload['total']} archive matches; showing {len(payload['results'])}")
        for item in payload["results"]:
            date = f" ({item['date']})" if item.get("date") else ""
            print(f"- {item['title']}{date}\n  {item['url']}")
    else:
        print(f"{payload['title']} ({payload.get('date') or 'date unavailable'})")
        print(payload["url"])
        if payload.get("text"):
            print(f"\n{payload['text']}")
        if payload.get("related_files"):
            print("\nRelated files:")
            for item in payload["related_files"]:
                print(f"- {item['title']}: {item['url']}")


def cmd_search(args: argparse.Namespace) -> None:
    if not args.query.strip():
        raise SenateFinanceError("search query cannot be empty")
    if not 1 <= args.limit <= MAX_RESULTS:
        raise SenateFinanceError(f"--limit must be between 1 and {MAX_RESULTS}")
    if args.page < 1:
        raise SenateFinanceError("--page must be at least 1")

    session = _session()
    pages_needed = math.ceil(args.limit / 10)
    all_results: list[dict] = []
    total = 0
    pages_fetched = 0
    for page in range(args.page, args.page + pages_needed):
        response = _request_html(
            session,
            SEARCH_URL,
            params={"q": args.query, "page": page},
        )
        page_total, results = parse_search_page(response.text, response.url)
        total = max(total, page_total)
        pages_fetched += 1
        all_results.extend(results)
        if len(all_results) >= args.limit or not results:
            break

    all_results = all_results[: args.limit]
    payload = {
        "source": SOURCE,
        "query": args.query,
        "total": total,
        "page_start": args.page,
        "pages_fetched": pages_fetched,
        "results": all_results,
        "source_url": SEARCH_URL,
    }
    _log(args.query, len(all_results))
    _emit(payload, args, f"Senate Finance search {args.query!r}")


def cmd_item(args: argparse.Namespace) -> None:
    url = _official_url(args.url)
    response = _request_html(_session(), url)
    payload = parse_item_page(response.text, response.url)
    _log(f"item:{urlparse(payload['url']).path}", 1)
    _emit(payload, args, f"Senate Finance item {payload['title']!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search and read the U.S. Senate Finance Committee archive"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search committee pages and attached documents")
    search.add_argument("query", help="Archive search terms")
    search.add_argument("--limit", type=int, default=10, help="Results to return (1-100; default: 10)")
    search.add_argument("--page", type=int, default=1, help="First result page (default: 1)")
    add_output_args(search)
    search.set_defaults(func=cmd_search)

    item = sub.add_parser("item", help="Read one official committee detail page")
    item.add_argument("url", help="Official finance.senate.gov detail URL or path")
    add_output_args(item)
    item.set_defaults(func=cmd_item)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except SenateFinanceError as exc:
        payload = {
            "status": "error",
            "source": SOURCE,
            "error": str(exc),
            "results": [],
        }
        if getattr(args, "output", None):
            write_output(payload, args, summary="Senate Finance request failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
