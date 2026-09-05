#!/usr/bin/env python3
"""Discover and search official New York Law Reporting Bureau decisions.

Verified official routes (2026-07-29):
    Selected trial courts RSS:
        https://www.nycourts.gov/reporter/RSS/misc.xml
    Commercial Division RSS:
        https://www.nycourts.gov/reporter/RSS/ComDiv.xml
    Selected trial courts current index:
        https://www.nycourts.gov/reporter/current/index/miscolo.shtml
    Selected trial courts archive index:
        https://www.nycourts.gov/reporter/current/index/other-courts-archive.shtml
    Commercial Division current index:
        https://www.nycourts.gov/reporter/current/index/com_div_idxtable.shtml
    Commercial Division archive index:
        https://www.nycourts.gov/reporter/current/index/com-div-decisions-archive.shtml

The source paginates its indexes by current month and one archive page per
month. Commands return every source row by default; ``--limit`` is optional and
has no adapter-defined maximum.
"""

from __future__ import annotations

import argparse
import calendar
import html as html_lib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output


BASE_URL = "https://www.nycourts.gov"
SOURCE_ID = "us-ny-law-reporting-bureau"
SOURCE = SOURCE_ID
USER_AGENT = "IthildinOSINT/1.0 (public-record research)"
TIMEOUT = 30
MAX_RETRIES = 2
REQUEST_DELAY = 0.25
MAX_TEXT_BYTES = 25_000_000
ALLOWED_HOSTS = frozenset({
    "nycourts.gov",
    "www.nycourts.gov",
    "www.courts.state.ny.us",
})

COLLECTIONS = {
    "other": {
        "label": "Selected Trial and Other Courts",
        "rss_url": f"{BASE_URL}/reporter/RSS/misc.xml",
        "current_index_url": (
            f"{BASE_URL}/reporter/current/index/miscolo.shtml"
        ),
        "archive_index_url": (
            f"{BASE_URL}/reporter/current/index/other-courts-archive.shtml"
        ),
    },
    "commercial": {
        "label": "Supreme Court, Commercial Division",
        "rss_url": f"{BASE_URL}/reporter/RSS/ComDiv.xml",
        "current_index_url": (
            f"{BASE_URL}/reporter/current/index/com_div_idxtable.shtml"
        ),
        "archive_index_url": (
            f"{BASE_URL}/reporter/current/index/com-div-decisions-archive.shtml"
        ),
    },
}

SENTINEL_OPINION_URL = (
    f"{BASE_URL}/reporter/current/3dseries/2026/2026_26113.shtml"
)
SENTINEL_CAPTION = "Fifty Nine Realty LLC v Gottesman"
SENTINEL_CITATION = "2026 NY Slip Op 26113"
SENTINEL_BODY_MARKER = "NYSCEF Doc Nos: 9-26"

_last_request_at = 0.0


class NyLawReportsError(RuntimeError):
    """Base error for official Law Reporting Bureau requests and parsing."""


class NyLawReportsAccessChallenge(NyLawReportsError):
    """The official host returned a browser/security challenge."""


@dataclass(frozen=True)
class TextResponse:
    url: str
    text: str
    content_type: str
    status_code: int


def _clean_text(node_or_text: Any) -> str:
    if node_or_text is None:
        return ""
    if hasattr(node_or_text, "get_text"):
        value = node_or_text.get_text(" ", strip=True)
    else:
        value = str(node_or_text)
    value = html_lib.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", value)


def _decode_entities(value: str) -> str:
    previous = value
    for _ in range(3):
        decoded = html_lib.unescape(previous)
        if decoded == previous:
            break
        previous = decoded
    return _clean_text(previous)


def _official_url(value: str, *, base: str = BASE_URL) -> str:
    candidate = urljoin(base, value.strip())
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_HOSTS:
        raise NyLawReportsError(
            "URL must be an official nycourts.gov Law Reporting Bureau URL"
        )
    if not parsed.path.lower().startswith("/reporter/"):
        raise NyLawReportsError(
            "URL must be within the official /reporter/ source tree"
        )
    return urlunparse((
        "https",
        "www.nycourts.gov",
        parsed.path,
        "",
        parsed.query,
        "",
    ))


def _evidence_ref(url: str) -> str:
    path = urlparse(_official_url(url)).path
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if re.fullmatch(r"\d{4}_\d{5}", stem):
        return f"NY_LAW_REPORTS:{stem}"
    return f"NY_LAW_REPORTS:{path.removeprefix('/reporter/')}"


def _document_format(url: str) -> str:
    return "pdf" if urlparse(url).path.lower().endswith(".pdf") else "html"


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,application/rss+xml,"
            "application/xml,text/xml;q=0.9"
        ),
        "Accept-Language": "en-US,en;q=0.8",
    })
    return session


def _challenge_body(text: str) -> bool:
    lowered = text.lower()
    return (
        "performing security verification" in lowered
        or "challenges.cloudflare.com" in lowered
        or "enable javascript and cookies to continue" in lowered
    )


def _decode_body(body: bytes, content_type: str) -> str:
    """Decode source text without Requests' ISO-8859-1 fallback for text/html."""
    if body.startswith(b"\xef\xbb\xbf"):
        return body.decode("utf-8-sig", errors="replace")

    encoding_match = re.search(
        r"\bcharset\s*=\s*[\"']?([a-z0-9._-]+)",
        content_type,
        flags=re.I,
    )
    encoding = encoding_match.group(1) if encoding_match else None
    if encoding is None:
        prefix = body[:4096]
        byte_match = re.search(
            br"""(?:<meta\b[^>]*\bcharset\s*=\s*["']?\s*|"""
            br"""<\?xml\b[^>]*\bencoding\s*=\s*["']\s*)"""
            br"""([a-z0-9._-]+)""",
            prefix,
            flags=re.I,
        )
        encoding = byte_match.group(1).decode("ascii") if byte_match else "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError as exc:
        raise NyLawReportsError(
            f"official source declared an unknown character encoding: {encoding}"
        ) from exc


def _request_text(session: requests.Session, url: str) -> TextResponse:
    """Fetch one official HTML/XML page and identify source-wide challenges."""
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
                timeout=TIMEOUT,
                allow_redirects=True,
                stream=True,
            )
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * (2**attempt))
                continue
            raise NyLawReportsError(f"official source request failed: {exc}") from exc

        final_url = _official_url(response.url)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < MAX_RETRIES:
                response.close()
                time.sleep(0.5 * (2**attempt))
                continue

        content_type = response.headers.get("Content-Type", "").lower()
        body = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                body.extend(chunk)
                if len(body) > MAX_TEXT_BYTES:
                    raise NyLawReportsError(
                        f"source page exceeds {MAX_TEXT_BYTES} bytes: {final_url}"
                    )
        finally:
            response.close()

        text = _decode_body(bytes(body), content_type)
        if response.status_code == 403 and _challenge_body(text):
            raise NyLawReportsAccessChallenge(
                f"official host returned a security challenge for {final_url}"
            )
        if response.status_code != 200:
            raise NyLawReportsError(
                f"official source returned HTTP {response.status_code} for {final_url}"
            )

        if _challenge_body(text):
            raise NyLawReportsAccessChallenge(
                f"official host returned a security challenge for {final_url}"
            )
        return TextResponse(
            url=final_url,
            text=text,
            content_type=content_type,
            status_code=response.status_code,
        )

    raise NyLawReportsError("official source request exhausted retries")


def _date_iso(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"^(?:Decided on|Decided)\s+", "", value, flags=re.I).strip()
    for pattern in ("%B %d, %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _rss_description_fields(description_html: str) -> tuple[str | None, str | None, str | None]:
    soup = BeautifulSoup(html_lib.unescape(description_html), "html.parser")
    cells = soup.select("td")
    values: list[str] = []
    if len(cells) >= 2:
        values = [_clean_text(value) for value in cells[-1].stripped_strings]
    if len(values) < 3:
        lines = [
            _clean_text(value)
            for value in soup.stripped_strings
            if _clean_text(value).lower() not in {"court", "decided", "slip"}
        ]
        values = lines[-3:]
    if len(values) < 3:
        return None, None, None
    return values[0], values[1], values[2]


def parse_rss(xml_text: str, source_url: str, collection: str) -> dict:
    """Parse one official RSS feed and its source-provided result window."""
    try:
        root = ET.fromstring(xml_text.lstrip("\ufeff"))
    except ET.ParseError as exc:
        raise NyLawReportsError(f"invalid Law Reporting RSS XML: {exc}") from exc
    channel = root.find("channel")
    if channel is None:
        raise NyLawReportsError("Law Reporting RSS feed has no channel")

    results: list[dict] = []
    for item in channel.findall("item"):
        raw_title = item.findtext("title") or ""
        raw_link = item.findtext("link") or item.findtext("guid") or ""
        if not raw_link:
            continue
        link = _official_url(raw_link, base=source_url)
        description = item.findtext("description") or ""
        court, decision_date, citation = _rss_description_fields(description)
        caption = re.sub(r"\s+\(PDF\)$", "", _decode_entities(raw_title), flags=re.I)
        results.append({
            "source": SOURCE,
            "collection": collection,
            "discovery_method": "rss",
            "caption": caption,
            "court": court,
            "decision_date": decision_date,
            "decision_date_iso": _date_iso(decision_date),
            "citation": citation,
            "judge": None,
            "source_url": link,
            "document_format": _document_format(link),
            "evidence_ref": _evidence_ref(link),
            "raw_metadata": {
                "rss_title": raw_title,
                "description_html": description.strip(),
                "guid": item.findtext("guid"),
            },
        })

    feed_link = channel.findtext("link")
    return {
        "source": SOURCE,
        "collection": collection,
        "feed": {
            "title": _decode_entities(channel.findtext("title") or ""),
            "description": _clean_text(channel.findtext("description") or ""),
            "last_build_date": channel.findtext("lastBuildDate"),
            "link": _official_url(feed_link, base=source_url) if feed_link else None,
        },
        "source_url": _official_url(source_url),
        "coverage": {
            "kind": "source_feed_window",
            "description": "all entries present in the source-provided RSS response",
            "item_count": len(results),
        },
        "pagination": {
            "kind": "rss_feed_window",
            "source_has_numbered_pages": False,
            "returned_all_source_rows": True,
        },
        "results": results,
    }


def parse_archive_index(html_text: str, source_url: str, collection: str) -> dict:
    """Parse source-native year/month links from an archive landing page."""
    soup = BeautifulSoup(html_text, "html.parser")
    periods: list[dict] = []
    seen: set[tuple[int, int]] = set()
    month_lookup = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}

    for link in soup.select("a[href]"):
        href = link.get("href", "")
        match = re.search(
            r"_(?P<year>20\d{2})_(?P<month>[a-z]+)\.shtml(?:$|[?#])",
            href,
            flags=re.I,
        )
        if not match:
            continue
        year = int(match.group("year"))
        month_name = match.group("month").lower()
        month = month_lookup.get(month_name)
        if not month or (year, month) in seen:
            continue
        seen.add((year, month))
        periods.append({
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "period": f"{year:04d}-{month:02d}",
            "source_url": _official_url(href, base=source_url),
        })

    periods.sort(key=lambda row: (row["year"], row["month"]))
    if not periods:
        raise NyLawReportsError("archive index contained no source month links")
    return {
        "source": SOURCE,
        "collection": collection,
        "source_url": _official_url(source_url),
        "coverage": {
            "kind": "source_month_index",
            "first_period": periods[0]["period"],
            "last_period": periods[-1]["period"],
            "period_count": len(periods),
        },
        "pagination": {
            "kind": "one_source_page_per_month",
            "source_has_numbered_pages": False,
            "returned_all_source_rows": True,
        },
        "results": periods,
    }


def parse_decision_index(
    html_text: str,
    source_url: str,
    collection: str,
    *,
    period: str,
) -> dict:
    """Parse all decision rows on a current or archived monthly index."""
    soup = BeautifulSoup(html_text, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()

    for table in soup.select("table"):
        caption = _clean_text(table.select_one("caption"))
        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 4:
                continue
            link = cells[0].select_one("a[href]")
            if not link:
                continue
            try:
                document_url = _official_url(link.get("href", ""), base=source_url)
            except NyLawReportsError:
                continue
            if document_url in seen:
                continue
            seen.add(document_url)
            raw_caption = _clean_text(link)
            results.append({
                "source": SOURCE,
                "collection": collection,
                "discovery_method": "monthly_index",
                "caption": re.sub(r"\s+\(PDF\)$", "", raw_caption, flags=re.I),
                "court": _clean_text(cells[1]) or None,
                "decision_date": _clean_text(cells[2]) or None,
                "decision_date_iso": _date_iso(_clean_text(cells[2])),
                "citation": _clean_text(cells[3]) or None,
                "judge": None,
                "source_url": document_url,
                "document_format": _document_format(document_url),
                "evidence_ref": _evidence_ref(document_url),
                "raw_metadata": {
                    "index_caption": raw_caption,
                    "posted_group": caption or None,
                },
            })

    if not results:
        raise NyLawReportsError("decision index contained no recognizable decision rows")
    return {
        "source": SOURCE,
        "collection": collection,
        "period": period,
        "source_url": _official_url(source_url),
        "coverage": {
            "kind": "source_month_page",
            "period": period,
            "row_count": len(results),
        },
        "pagination": {
            "kind": "one_source_page_per_month",
            "source_has_numbered_pages": False,
            "returned_all_source_rows": True,
        },
        "results": results,
    }


def _first_matching(lines: list[str], pattern: str) -> str | None:
    regex = re.compile(pattern, re.I)
    return next((line for line in lines if regex.search(line)), None)


def _body_blocks(container) -> str:
    blocks: list[str] = []
    for node in container.select("h1, h2, h3, p, li, span.page"):
        if node.find_parent(["h1", "h2", "h3", "p", "li"]):
            continue
        text = _clean_text(node)
        if text and (not blocks or text != blocks[-1]):
            blocks.append(text)
    return "\n\n".join(blocks)


def parse_opinion(html_text: str, source_url: str) -> dict:
    """Parse one full official HTML opinion, including body text."""
    soup = BeautifulSoup(html_text.lstrip("\ufeff"), "html.parser")
    if _challenge_body(html_text):
        raise NyLawReportsAccessChallenge(
            f"official host returned a security challenge for {_official_url(source_url)}"
        )
    container = soup.select_one(".current-legal-document")
    modern = container is not None
    if container is None:
        container = soup.select_one("main.decision") or soup.body
    if container is None:
        raise NyLawReportsError("opinion page has no document body")

    case_info = container.select_one(".case-info")
    info_lines = (
        [_clean_text(node) for node in case_info.select("h1, p")]
        if case_info
        else []
    )
    page_title = _clean_text(soup.title)
    heading = (
        _clean_text(case_info.select_one("h1"))
        if case_info
        else _clean_text(container.select_one("h1"))
    )
    caption = heading or re.split(r"\s+-\s+\d{4}\s+NY\s+Slip\s+Op", page_title)[0]

    all_text = _clean_text(container)
    citation_match = re.search(
        r"\b\d{4}\s+NY\s+Slip\s+Op\s+\d{5}(?:\(U\))?\b",
        " ".join(info_lines) or all_text,
        flags=re.I,
    )
    citation = citation_match.group(0) if citation_match else None

    date_value = next(
        (
            line
            for line in info_lines
            if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", line)
        ),
        None,
    )
    if date_value is None:
        decided = re.search(
            r"\bDecided on ([A-Z][a-z]+ \d{1,2}, \d{4})\b",
            all_text,
        )
        date_value = decided.group(1) if decided else None

    court = info_lines[3] if len(info_lines) >= 4 else None
    if not court or "court" not in court.lower():
        court = _first_matching(
            info_lines + [_clean_text(node) for node in container.select("p")[:15]],
            r"\b(?:court|appellate division|appellate term)\b",
        )
    judge = info_lines[4] if len(info_lines) >= 5 else None
    if not judge or not re.search(r"\bJ(?:\.|,|$)|JJ\.", judge):
        judge = _clean_text(container.select_one(".current-judge-name")) or None

    digest = _clean_text(container.select_one(".digest")) or None
    parties = [
        _clean_text(node)
        for node in container.select(".parties p")
        if _clean_text(node)
    ]
    counsel = [
        _clean_text(node)
        for node in container.select(".current-counsel-block p")
        if _clean_text(node)
    ]
    index_number_line = next(
        (
            _clean_text(node)
            for node in container.select(".current-legal-small-center")
            if re.search(r"\bIndex No\.", _clean_text(node), flags=re.I)
        ),
        None,
    )
    index_number_match = re.search(
        r"\bIndex No\.\s*(.+)$",
        index_number_line or "",
        flags=re.I,
    )

    body_soup = BeautifulSoup(str(container), "html.parser")
    body_container = body_soup.select_one(".current-legal-document") or body_soup
    for selector in (
        ".case-info",
        ".digest",
        ".parties",
        ".current-legal-small-center",
        ".current-counsel-block",
        ".current-judge-name",
    ):
        for node in body_container.select(selector):
            node.decompose()
    body_text = _body_blocks(body_container)
    if not body_text:
        raise NyLawReportsError("opinion page did not yield body text")

    canonical_url = _official_url(source_url)
    return {
        "source": SOURCE,
        "caption": caption or None,
        "court": court,
        "decision_date": date_value,
        "decision_date_iso": _date_iso(date_value),
        "citation": citation,
        "judge": judge,
        "index_number": index_number_match.group(1).strip() if index_number_match else None,
        "source_url": canonical_url,
        "document_format": "html",
        "evidence_ref": _evidence_ref(canonical_url),
        "body_text": body_text,
        "raw_metadata": {
            "html_format": "current" if modern else "legacy",
            "page_title": page_title or None,
            "case_info": info_lines,
            "digest": digest,
            "parties": parties,
            "counsel": counsel,
        },
    }


def _collection_names(value: str) -> list[str]:
    return list(COLLECTIONS) if value == "all" else [value]


def _validate_limit(value: int | None) -> None:
    if value is not None and value < 1:
        raise NyLawReportsError("--limit must be a positive integer")


def _validate_period(year: int | None, month: int | None) -> None:
    if (year is None) != (month is None):
        raise NyLawReportsError("--year and --month must be provided together")
    if month is not None and not 1 <= month <= 12:
        raise NyLawReportsError("--month must be between 1 and 12")


def _archive_payload(session: requests.Session, collection: str) -> dict:
    url = COLLECTIONS[collection]["archive_index_url"]
    response = _request_text(session, url)
    return parse_archive_index(response.text, response.url, collection)


def _period_index_url(
    session: requests.Session,
    collection: str,
    year: int,
    month: int,
) -> str:
    archive = _archive_payload(session, collection)
    for row in archive["results"]:
        if row["year"] == year and row["month"] == month:
            return row["source_url"]
    raise NyLawReportsError(
        f"{collection} archive does not list {year:04d}-{month:02d}; "
        f"reported coverage is {archive['coverage']['first_period']} through "
        f"{archive['coverage']['last_period']}"
    )


def _index_payload(
    session: requests.Session,
    collection: str,
    year: int | None,
    month: int | None,
) -> dict:
    if year is None:
        url = COLLECTIONS[collection]["current_index_url"]
        period = "current"
    else:
        url = _period_index_url(session, collection, year, month or 1)
        period = f"{year:04d}-{month:02d}"
    response = _request_text(session, url)
    return parse_decision_index(
        response.text,
        response.url,
        collection,
        period=period,
    )


def _log(query: str, count: int) -> None:
    try:
        log_search(query, SOURCE, count)
    except Exception as exc:
        print(f"Warning: could not log search: {exc}", file=sys.stderr)


def _emit(payload: dict, args: argparse.Namespace, summary: str) -> None:
    if write_output(payload, args, summary=summary):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2))
        return
    if "results" in payload:
        print(f"{len(payload['results'])} results")
        for row in payload["results"]:
            title = row.get("caption") or row.get("period") or row.get("source_url")
            print(f"- {title}")
            if row.get("citation"):
                print(f"  {row['citation']}")
            if row.get("source_url"):
                print(f"  {row['source_url']}")
    else:
        print(payload.get("caption") or payload.get("status") or SOURCE)
        if payload.get("citation"):
            print(payload["citation"])
        if payload.get("source_url"):
            print(payload["source_url"])
        if payload.get("body_text"):
            print(f"\n{payload['body_text']}")


def cmd_rss(args: argparse.Namespace) -> int:
    _validate_limit(args.limit)
    session = _session()
    feeds = []
    combined: list[dict] = []
    for collection in _collection_names(args.collection):
        url = COLLECTIONS[collection]["rss_url"]
        response = _request_text(session, url)
        payload = parse_rss(response.text, response.url, collection)
        rows = payload["results"]
        if args.limit is not None:
            rows = rows[: args.limit]
            payload["results"] = rows
            payload["pagination"]["returned_all_source_rows"] = (
                len(rows) == payload["coverage"]["item_count"]
            )
        feeds.append(payload)
        combined.extend(rows)
    result = {
        "source": SOURCE,
        "collection": args.collection,
        "feeds": feeds,
        "results": combined,
    }
    _log(f"rss:{args.collection}", len(combined))
    _emit(result, args, f"NY Law Reports RSS {args.collection}")
    return 0


def cmd_archives(args: argparse.Namespace) -> int:
    session = _session()
    archives = []
    combined: list[dict] = []
    for collection in _collection_names(args.collection):
        payload = _archive_payload(session, collection)
        rows = payload["results"]
        if args.year is not None:
            rows = [row for row in rows if row["year"] == args.year]
            payload["results"] = rows
        archives.append(payload)
        combined.extend({**row, "collection": collection} for row in rows)
    result = {
        "source": SOURCE,
        "collection": args.collection,
        "year": args.year,
        "archives": archives,
        "results": combined,
    }
    _log(
        f"archives:{args.collection}:{args.year or 'all'}",
        len(combined),
    )
    _emit(result, args, f"NY Law Reports archive periods {args.collection}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    _validate_period(args.year, args.month)
    _validate_limit(args.limit)
    payload = _index_payload(
        _session(),
        args.collection,
        args.year,
        args.month,
    )
    source_count = len(payload["results"])
    if args.limit is not None:
        payload["results"] = payload["results"][: args.limit]
        payload["pagination"]["returned_all_source_rows"] = (
            len(payload["results"]) == source_count
        )
    _log(
        f"index:{args.collection}:{payload['period']}",
        len(payload["results"]),
    )
    _emit(
        payload,
        args,
        f"NY Law Reports {args.collection} index {payload['period']}",
    )
    return 0


def _opinion_url(value: str) -> str:
    if re.fullmatch(r"\d{4}_\d{5}", value.strip()):
        year = value[:4]
        return (
            f"{BASE_URL}/reporter/current/3dseries/{year}/{value.strip()}.shtml"
        )
    url = _official_url(value)
    if _document_format(url) != "html":
        raise NyLawReportsError("opinion command currently accepts official HTML opinions")
    return url


def cmd_opinion(args: argparse.Namespace) -> int:
    url = _opinion_url(args.opinion)
    response = _request_text(_session(), url)
    payload = parse_opinion(response.text, response.url)
    _log(f"opinion:{payload['evidence_ref']}", 1)
    _emit(payload, args, f"NY Law Reports opinion {payload.get('citation') or url}")
    return 0


def _match_field(value: str | None, query: str, mode: str) -> bool:
    if not value:
        return False
    haystack = value.casefold()
    if mode == "phrase":
        return query.casefold() in haystack
    terms = [term.casefold() for term in re.findall(r"\w+", query) if term]
    if not terms:
        return False
    checks = (term in haystack for term in terms)
    return all(checks) if mode == "all" else any(checks)


def _snippet(text: str, query: str, mode: str, radius: int = 220) -> str | None:
    lowered = text.casefold()
    needles = [query.casefold()]
    if mode != "phrase":
        needles = [term.casefold() for term in re.findall(r"\w+", query) if term]
    positions = [lowered.find(needle) for needle in needles if needle]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return None
    position = min(positions)
    start = max(0, position - radius)
    end = min(len(text), position + radius)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    return ("…" if start else "") + snippet + ("…" if end < len(text) else "")


def cmd_search(args: argparse.Namespace) -> int:
    if not args.query.strip():
        raise NyLawReportsError("search query cannot be empty")
    _validate_period(args.year, args.month)
    _validate_limit(args.limit)
    session = _session()

    if args.feed:
        if args.year is not None:
            raise NyLawReportsError("--feed cannot be combined with --year/--month")
        response = _request_text(session, COLLECTIONS[args.collection]["rss_url"])
        discovery = parse_rss(
            response.text,
            response.url,
            args.collection,
        )
        scope = "rss"
    else:
        discovery = _index_payload(
            session,
            args.collection,
            args.year,
            args.month,
        )
        scope = discovery["period"]

    candidates = discovery["results"]
    html_candidates = [
        row for row in candidates if row["document_format"] == "html"
    ]
    results: list[dict] = []
    failures: list[dict] = []
    fetched = 0
    truncated = False

    for candidate in html_candidates:
        if args.limit is not None and len(results) >= args.limit:
            truncated = True
            break
        try:
            response = _request_text(session, candidate["source_url"])
            opinion = parse_opinion(response.text, response.url)
        except NyLawReportsAccessChallenge:
            raise
        except NyLawReportsError as exc:
            failures.append({
                "source_url": candidate["source_url"],
                "error": str(exc),
            })
            continue
        fetched += 1
        fields = {
            "caption": opinion.get("caption"),
            "court": opinion.get("court"),
            "citation": opinion.get("citation"),
            "judge": opinion.get("judge"),
            "body_text": opinion.get("body_text"),
        }
        matched_fields = [
            field
            for field, value in fields.items()
            if _match_field(value, args.query, args.match_mode)
        ]
        if not matched_fields:
            continue
        opinion["matched_fields"] = matched_fields
        opinion["match_snippet"] = _snippet(
            opinion["body_text"],
            args.query,
            args.match_mode,
        )
        opinion["discovery"] = candidate
        results.append(opinion)

    payload = {
        "source": SOURCE,
        "query": args.query,
        "match_mode": args.match_mode,
        "collection": args.collection,
        "scope": scope,
        "source_url": discovery["source_url"],
        "coverage": discovery["coverage"],
        "pagination": discovery["pagination"],
        "documents_discovered": len(candidates),
        "html_documents_discovered": len(html_candidates),
        "pdf_documents_skipped": len(candidates) - len(html_candidates),
        "documents_fetched": fetched,
        "failed_documents": failures,
        "limit_requested": args.limit,
        "truncated": truncated,
        "results": results,
    }
    _log(args.query, len(results))
    _emit(payload, args, f"NY Law Reports body search {args.query!r}")
    return 0


def run_sentinel(session: requests.Session | None = None) -> dict:
    """Probe RSS, current-index, and exact-opinion contracts with known facts."""
    session = session or _session()
    checks: list[dict] = []

    def check(name: str, url: str, parse) -> None:
        try:
            response = _request_text(session, url)
            details = parse(response)
            checks.append({
                "name": name,
                "status": "ok",
                "source_url": response.url,
                **details,
            })
        except NyLawReportsAccessChallenge as exc:
            checks.append({
                "name": name,
                "status": "access_challenge",
                "source_url": _official_url(url),
                "error": str(exc),
            })
        except NyLawReportsError as exc:
            checks.append({
                "name": name,
                "status": "error",
                "source_url": _official_url(url),
                "error": str(exc),
            })

    check(
        "other_rss",
        COLLECTIONS["other"]["rss_url"],
        lambda response: {
            "record_count": len(
                parse_rss(response.text, response.url, "other")["results"]
            )
        },
    )
    check(
        "commercial_rss",
        COLLECTIONS["commercial"]["rss_url"],
        lambda response: {
            "record_count": len(
                parse_rss(response.text, response.url, "commercial")["results"]
            )
        },
    )
    check(
        "other_current_index",
        COLLECTIONS["other"]["current_index_url"],
        lambda response: {
            "record_count": len(
                parse_decision_index(
                    response.text,
                    response.url,
                    "other",
                    period="current",
                )["results"]
            )
        },
    )
    check(
        "commercial_current_index",
        COLLECTIONS["commercial"]["current_index_url"],
        lambda response: {
            "record_count": len(
                parse_decision_index(
                    response.text,
                    response.url,
                    "commercial",
                    period="current",
                )["results"]
            )
        },
    )
    check(
        "other_archive_index",
        COLLECTIONS["other"]["archive_index_url"],
        lambda response: {
            "period_count": len(
                parse_archive_index(
                    response.text,
                    response.url,
                    "other",
                )["results"]
            )
        },
    )
    check(
        "commercial_archive_index",
        COLLECTIONS["commercial"]["archive_index_url"],
        lambda response: {
            "period_count": len(
                parse_archive_index(
                    response.text,
                    response.url,
                    "commercial",
                )["results"]
            )
        },
    )

    def sentinel_opinion(response: TextResponse) -> dict:
        opinion = parse_opinion(response.text, response.url)
        if opinion["caption"] != SENTINEL_CAPTION:
            raise NyLawReportsError(
                f"sentinel caption changed: {opinion['caption']!r}"
            )
        if opinion["citation"] != SENTINEL_CITATION:
            raise NyLawReportsError(
                f"sentinel citation changed: {opinion['citation']!r}"
            )
        if SENTINEL_BODY_MARKER not in opinion["body_text"]:
            raise NyLawReportsError("sentinel body marker is missing")
        return {
            "caption": opinion["caption"],
            "citation": opinion["citation"],
            "body_marker": SENTINEL_BODY_MARKER,
        }

    check("exact_opinion", SENTINEL_OPINION_URL, sentinel_opinion)
    ok = all(row["status"] == "ok" for row in checks)
    return {
        "source": SOURCE,
        "status": "ok" if ok else "unavailable",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "exact_urls": {
            "other_rss": COLLECTIONS["other"]["rss_url"],
            "commercial_rss": COLLECTIONS["commercial"]["rss_url"],
            "other_current_index": COLLECTIONS["other"]["current_index_url"],
            "commercial_current_index": (
                COLLECTIONS["commercial"]["current_index_url"]
            ),
            "other_archive_index": COLLECTIONS["other"]["archive_index_url"],
            "commercial_archive_index": (
                COLLECTIONS["commercial"]["archive_index_url"]
            ),
            "opinion": SENTINEL_OPINION_URL,
        },
    }


def cmd_sentinel(args: argparse.Namespace) -> int:
    payload = run_sentinel()
    _emit(payload, args, "NY Law Reports live sentinel")
    return 0 if payload["status"] == "ok" else 1


def _add_collection(parser: argparse.ArgumentParser, *, allow_all: bool = False) -> None:
    choices = [*COLLECTIONS]
    if allow_all:
        choices.append("all")
    parser.add_argument(
        "--collection",
        choices=choices,
        default="other",
        help="Official source collection (default: other)",
    )


def _add_period(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int, help="Archive year; requires --month")
    parser.add_argument("--month", type=int, help="Archive month 1-12; requires --year")


def _add_optional_limit(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional user-requested result limit; default returns all source rows",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and search official New York Law Reporting Bureau decisions"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rss = sub.add_parser("rss", help="Read official current-decision RSS feeds")
    _add_collection(rss, allow_all=True)
    _add_optional_limit(rss)
    add_output_args(rss)
    rss.set_defaults(func=cmd_rss)

    archives = sub.add_parser(
        "archives",
        help="List source-native monthly archive pages",
    )
    _add_collection(archives, allow_all=True)
    archives.add_argument("--year", type=int, help="Optionally filter archive periods")
    add_output_args(archives)
    archives.set_defaults(func=cmd_archives)

    index = sub.add_parser(
        "index",
        help="List all decisions on the current or one archived month page",
    )
    _add_collection(index)
    _add_period(index)
    _add_optional_limit(index)
    add_output_args(index)
    index.set_defaults(func=cmd_index)

    opinion = sub.add_parser(
        "opinion",
        help="Retrieve and parse one official full HTML opinion",
    )
    opinion.add_argument(
        "opinion",
        help="Official opinion URL or native identifier such as 2026_26113",
    )
    add_output_args(opinion)
    opinion.set_defaults(func=cmd_opinion)

    search = sub.add_parser(
        "search",
        help="Search full HTML opinion bodies discovered from one source window",
    )
    search.add_argument("query", help="Case-insensitive body/metadata search terms")
    _add_collection(search)
    _add_period(search)
    search.add_argument(
        "--feed",
        action="store_true",
        help="Search the collection's current RSS window instead of an index page",
    )
    search.add_argument(
        "--match-mode",
        choices=("phrase", "all", "any"),
        default="phrase",
        help="Text matching behavior (default: phrase)",
    )
    _add_optional_limit(search)
    add_output_args(search)
    search.set_defaults(func=cmd_search)

    sentinel = sub.add_parser(
        "sentinel",
        help="Run live RSS, index, and exact-opinion contract checks",
    )
    add_output_args(sentinel)
    sentinel.set_defaults(func=cmd_sentinel)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except NyLawReportsError as exc:
        payload = {
            "status": "error",
            "source": SOURCE,
            "error": str(exc),
            "results": [],
        }
        if getattr(args, "output", None):
            write_output(payload, args, summary="NY Law Reports request failed")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
