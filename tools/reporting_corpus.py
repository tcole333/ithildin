#!/usr/bin/env python3
"""Build and query the Epstein reporting knowledge layer.

The corpus stores versioned reporting, attributed atomic claims, reporting
lineage, and links to primary evidence.  It does not treat secondary reporting
as established fact.  Use ``promote`` only after a claim has a reviewed primary
evidence link with a source quote.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import yaml

try:
    from tools.epstein_reporting import (
        CORE_DB_PATH,
        DEFAULT_DB_PATH,
        connect,
        domain_from_url,
        json_text,
        normalize_country,
        normalize_language,
        normalize_published_at,
        normalize_url,
        publication_date_from_url,
        refresh_claim_fts,
        refresh_item_fts,
        stable_hash,
    )
    from tools.output_util import add_output_args, write_output
except ImportError:
    from epstein_reporting import (
        CORE_DB_PATH,
        DEFAULT_DB_PATH,
        connect,
        domain_from_url,
        json_text,
        normalize_country,
        normalize_language,
        normalize_published_at,
        normalize_url,
        publication_date_from_url,
        refresh_claim_fts,
        refresh_item_fts,
        stable_hash,
    )
    from output_util import add_output_args, write_output


USER_AGENT = "Ithildin-OSINT/1.0 (research corpus; contact: osint-research@proton.me)"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_WEB_URL = "https://web.archive.org/web"
COMMONCRAWL_COLLECTIONS_URL = "https://index.commoncrawl.org/collinfo.json"

SOURCE_TYPE_ALIASES = {
    "document_publisher": "secondary_quality",
    "magazine": "secondary_quality",
    "aggregator": "unknown",
}


def normalize_source_type(value: str | None) -> str:
    source_type = (value or "unknown").strip().casefold()
    return SOURCE_TYPE_ALIASES.get(source_type, source_type)
COMMONCRAWL_DATA_URL = "https://data.commoncrawl.org"
DEFAULT_SOURCE_CONFIG = Path(__file__).resolve().parent.parent / "investigations" / "epstein" / "reporting_sources.yaml"
_COMMONCRAWL_COLLECTIONS_CACHE: list[dict] | None = None


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArticleHTMLParser(HTMLParser):
    """Extract conservative article metadata and readable page text."""

    SKIP = {"script", "style", "svg", "noscript", "template", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.canonical: str | None = None
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.article_text_parts: list[str] = []
        self.jsonld_parts: list[str] = []
        self.time_datetimes: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._in_jsonld = False
        self._article_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag in self.SKIP:
            self._skip_depth += 1
        if tag == "article":
            self._article_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "meta":
            key = values.get("property") or values.get("name") or values.get("itemprop")
            if key and values.get("content"):
                self.meta[key.lower()] = values["content"].strip()
        if tag == "time" and values.get("datetime"):
            self.time_datetimes.append(values["datetime"].strip())
        if tag == "link" and "canonical" in values.get("rel", "").lower():
            self.canonical = values.get("href") or self.canonical

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "article" and self._article_depth:
            self._article_depth -= 1
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
        elif tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self.jsonld_parts.append(data)
        elif self._in_title:
            self.title_parts.append(data)
        elif not self._skip_depth:
            clean = re.sub(r"\s+", " ", data).strip()
            if clean:
                self.text_parts.append(clean)
                if self._article_depth:
                    self.article_text_parts.append(clean)


class PageLinkParser(HTMLParser):
    """Collect anchor destinations and their visible text from a topic page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a" and self._href is None:
            self._href = dict(attrs).get("href")
            self._text = []
            self._depth = 1
        elif self._href is not None:
            self._depth += 1

    def handle_data(self, data: str) -> None:
        if self._href is not None and data.strip():
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if self._href is None:
            return
        self._depth -= 1
        if tag.lower() == "a" or self._depth <= 0:
            title = re.sub(r"\s+", " ", " ".join(self._text)).strip()
            self.links.append((self._href, title))
            self._href, self._text, self._depth = None, [], 0


def extract_page_links(raw: bytes, base_url: str) -> list[tuple[str, str]]:
    parser = PageLinkParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, title in parser.links:
        url = urljoin(base_url, html.unescape(href))
        if urlsplit(url).scheme not in {"http", "https"} or url in seen:
            continue
        seen.add(url)
        links.append((url, title))
    return links


def is_navigation_link(title: str | None) -> bool:
    value = re.sub(r"\s+", " ", title or "").strip().casefold().rstrip(" >»")
    date_navigation = re.fullmatch(
        r"\d{1,2} (?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december) \d{4}", value,
    )
    return bool(re.fullmatch(r"\d+", value) or date_navigation) or value in {
        "next", "next page", "previous", "previous page", "older", "newer",
        "suivant", "précédent", "siguiente", "anterior", "próxima", "próximo",
        "vis ældre", "vis nyere",
        "כתבות קודמות", "כתבות נוספות",
        "skip to main content",
    }


def is_topic_landing_page(url: str, title: str | None = None) -> bool:
    """Identify publisher indexes or structured reference pages that are not articles."""
    normalized = normalize_url(url)
    domain = domain_from_url(normalized)
    parts = urlsplit(normalized)
    path = unquote(parts.path).casefold().rstrip("/")
    segments = {segment for segment in path.split("/") if segment}
    query_keys = {key.casefold() for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
    if "pinnedentry" in query_keys:
        return True
    if domain == "wyborcza.pl" and "tag" in query_keys and re.fullmatch(r"/0,\d+\.html", path):
        return True
    if path in {
        "/subscription", "/subscriptions", "/subscribe", "/suscripcion",
        "/suscripciones", "/support", "/tamogatas",
    }:
        return True
    if domain == "tv.nu" and path.startswith("/program/"):
        return True
    if path.startswith("/userfeedback"):
        return True
    if segments & {
        "topic", "topics", "tag", "tags", "cimke", "eticheta", "argomenti",
        "assunto", "tudo-sobre", "noticias", "protagonisti", "folha-topicos",
        "theme", "hub",
    }:
        return True
    if (domain, path) in {
        ("lemonde.fr", "/affaire-epstein"),
        ("theguardian.com", "/us-news/ghislaine-maxwell"),
        ("theguardian.com", "/us-news/jeffrey-epstein"),
    }:
        return True
    if domain == "projects.propublica.org" and path.startswith("/nonprofits/organizations/"):
        return True
    value = re.sub(r"\s+", " ", title or "").casefold()
    return any(marker in value for marker in (
        "actualités, vidéos et infos en direct",
        "tutte le notizie",
        " en el país |",
    ))


def is_access_interstitial(url: str) -> bool:
    """Return true for consent/privacy redirects that are not article responses."""
    normalized = normalize_url(url)
    parts = urlsplit(normalized)
    domain = domain_from_url(normalized)
    path = unquote(parts.path).casefold()
    query_keys = {key.casefold() for key, _ in parse_qsl(parts.query, keep_blank_values=True)}
    if domain == "myprivacy.dpgmedia.nl" and path.startswith("/consent"):
        return True
    return bool(
        {"callbackurl", "redirecturi"} & query_keys
        and any(marker in path for marker in ("/consent", "/privacy-gate"))
    )


def candidate_display_title(candidate: dict) -> str:
    if candidate.get("title"):
        return candidate["title"]
    slug = unquote(urlsplit(candidate["url"]).path.rstrip("/").split("/")[-1])
    slug = re.sub(r"\.(?:html?|amp)$", "", slug, flags=re.I)
    words = [word for word in re.split(r"[-_]+", slug) if word]
    if len(words) >= 4 and not all(word.isdigit() for word in words):
        title = " ".join(words)
        return title[:1].upper() + title[1:]
    return candidate["url"]


def _flatten_jsonld(value: object) -> list[dict]:
    if isinstance(value, list):
        out: list[dict] = []
        for item in value:
            out.extend(_flatten_jsonld(item))
        return out
    if not isinstance(value, dict):
        return []
    out = [value]
    if "@graph" in value:
        out.extend(_flatten_jsonld(value["@graph"]))
    return out


def _jsonld_scalar(
    value: object,
    keys: tuple[str, ...] = ("name", "@value", "value", "@id", "url"),
) -> str | None:
    """Return a stable scalar from permissive schema.org JSON-LD shapes."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        for entry in value:
            scalar = _jsonld_scalar(entry, keys)
            if scalar:
                return scalar
        return None
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                scalar = _jsonld_scalar(value[key], keys)
                if scalar:
                    return scalar
    return None


def parse_article_html(raw: bytes, source_url: str) -> dict:
    text = raw.decode("utf-8", errors="replace")
    parser = ArticleHTMLParser()
    parser.feed(text)
    metadata: dict = {}
    comment_body = None
    comment_segments = re.findall(
        r"<!--\s*begintext\s*-->(.*?)<!--\s*endtext\s*-->", text, re.S | re.I,
    )
    if comment_segments:
        body_parser = ArticleHTMLParser()
        body_parser.feed("<article>" + "\n".join(comment_segments) + "</article>")
        extracted = "\n".join(body_parser.article_text_parts).strip()
        if len(extracted) >= 200:
            comment_body = extracted
            metadata["body_extraction"] = "html_comment_markers"
    joined_jsonld = "\n".join(parser.jsonld_parts).strip()
    if joined_jsonld:
        try:
            candidates = _flatten_jsonld(json.loads(joined_jsonld))
            article_types = {"article", "newsarticle", "reportagenewsarticle", "analysisnewsarticle"}
            record = next(
                (r for r in candidates if str(r.get("@type", "")).lower() in article_types),
                candidates[0] if candidates else {},
            )
            metadata["jsonld"] = record
        except json.JSONDecodeError:
            metadata["jsonld_parse_error"] = True
    record = metadata.get("jsonld", {})
    authors = record.get("author") or []
    if isinstance(authors, (str, dict)):
        authors = [authors]
    author_names = []
    for author in authors:
        name = _jsonld_scalar(author, ("name", "alternateName"))
        if name:
            author_names.append(name.strip())
    title = _jsonld_scalar(record.get("headline")) or (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title") or " ".join(parser.title_parts).strip()
    )
    canonical = (
        _jsonld_scalar(record.get("url"), ("url", "@id", "@value", "value"))
        or parser.canonical or parser.meta.get("og:url") or source_url
    )
    description = _jsonld_scalar(record.get("description"))
    alternative_headline = _jsonld_scalar(record.get("alternativeHeadline"))
    return {
        "title": html.unescape(str(title or "Untitled reporting item")).strip(),
        "dek": alternative_headline or parser.meta.get("description") or parser.meta.get("og:description"),
        "canonical_url": urljoin(source_url, canonical),
        "published_at": (
            _jsonld_scalar(record.get("datePublished"))
            or parser.meta.get("article:published_time")
            or parser.meta.get("datepublished")
            or parser.meta.get("date")
            or (parser.time_datetimes[0] if parser.time_datetimes else None)
        ),
        "updated_at": (
            _jsonld_scalar(record.get("dateModified"))
            or parser.meta.get("article:modified_time")
            or parser.meta.get("datemodified")
        ),
        "language": _jsonld_scalar(record.get("inLanguage")) or parser.meta.get("og:locale"),
        "authors": author_names,
        "publisher": _jsonld_scalar(
            record.get("publisher"), ("name", "legalName", "alternateName")
        ),
        "abstract": description or parser.meta.get("description"),
        "content_text": (
            _jsonld_scalar(record.get("articleBody"))
            or comment_body
            or ("\n".join(parser.article_text_parts) if len(" ".join(parser.article_text_parts)) >= 200 else None)
            or "\n".join(parser.text_parts)
        ),
        "metadata": metadata,
        "raw_hash": stable_hash(text),
    }


CORE_SUBJECT_ALIASES = (
    "epstein", "maxwell", "эпштейн", "אפשטיין", "إبستين",
    "エプスタイン", "엡스타인", "엡스틴", "爱泼斯坦", "愛潑斯坦", "艾普斯坦",
    "επσταϊν", "έπσταϊν", "επστάιν", "μάξγουελ", "μαξγουελ",
    "एपस्टीन", "앱스타인",
)


def core_subject_hits(value: str | None) -> int:
    folded = (value or "").casefold()
    return sum(folded.count(alias) for alias in CORE_SUBJECT_ALIASES)


def contains_core_subject(value: str | None) -> bool:
    return core_subject_hits(value) > 0


def is_direct_reporting(record: dict) -> bool:
    metadata_blob = " ".join(filter(None, [
        record.get("title"), record.get("dek"), record.get("abstract"),
        record.get("canonical_url"),
    ]))
    body_hits = core_subject_hits(record.get("content_text"))
    return contains_core_subject(metadata_blob) or body_hits >= 2


def fetch_url(url: str, timeout: int = 30) -> tuple[bytes, str, str]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get_content_type()
        return resp.read(), resp.geturl(), content_type


def candidate_url_variants(url: str, metadata: dict | None = None) -> list[str]:
    """Preserve discovery URLs and tolerate publishers requiring a www host."""
    variants: list[str] = []
    source_record = (metadata or {}).get("source_record") or {}
    for value in (
        source_record.get("canonical_url") if isinstance(source_record, dict) else None,
        source_record.get("url") if isinstance(source_record, dict) else None,
        url,
    ):
        if value and value not in variants:
            variants.append(value)
    for value in list(variants):
        parts = urlsplit(value)
        match = re.fullmatch(r"/v/article/([A-Z0-9]+)\.php", parts.path, re.I)
        if (parts.hostname or "").casefold() == "smart.asahi.com" and match:
            canonical = f"https://www.asahi.com/articles/{match.group(1)}.html"
            if canonical not in variants:
                variants.append(canonical)
    parts = urlsplit(url)
    if parts.hostname and not parts.hostname.startswith("www."):
        www_host = "www." + parts.hostname
        if parts.port:
            www_host += f":{parts.port}"
        www_variant = urlunsplit((parts.scheme, www_host, parts.path, parts.query, parts.fragment))
        if www_variant not in variants:
            variants.append(www_variant)
    return variants


def fetch_candidate_url(url: str, metadata: dict | None, timeout: int) -> tuple[bytes, str, str]:
    errors = []
    for variant in candidate_url_variants(url, metadata):
        try:
            return fetch_url(variant, timeout)
        except Exception as exc:
            errors.append(f"{variant}: {exc}")
    raise RuntimeError("; ".join(errors))


def _fetch_bytes(url: str, timeout: int = 30, headers: dict | None = None, retries: int = 2) -> tuple[bytes, str, str]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request_headers.update(headers or {})
    req = Request(url, headers=request_headers)
    attempt = 0
    while True:
        try:
            with urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get_content_type()
                return resp.read(), resp.geturl(), content_type
        except HTTPError as exc:
            if attempt >= retries or exc.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = float(retry_after) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
        except (URLError, TimeoutError):
            if attempt >= retries:
                raise
            delay = 2 ** attempt
        time.sleep(min(max(delay, 0.5), 10.0))
        attempt += 1


def parse_wayback_cdx(raw: bytes) -> list[dict]:
    rows = json.loads(raw.decode("utf-8", errors="replace"))
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


def wayback_captures(url: str, timeout: int = 30, limit: int = 10) -> list[dict]:
    params = {
        "url": url,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest,length",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "digest",
        "limit": limit,
    }
    raw, _, _ = _fetch_bytes(
        f"{WAYBACK_CDX_URL}?{urlencode(params, doseq=True)}", timeout, retries=0,
    )
    return parse_wayback_cdx(raw)


def wayback_domain_urls(
    domain: str, url_pattern: str = "epstein", timeout: int = 15,
    limit: int = 250, from_date: str | None = None, to_date: str | None = None,
) -> list[dict]:
    """Discover archived URLs on a domain using a confirmed CDX urlkey filter."""
    safe_pattern = re.sub(r"[^a-z0-9_-]+", "", url_pattern.casefold())
    if not safe_pattern:
        raise ValueError("URL pattern must contain letters or numbers")
    params: dict[str, object] = {
        "url": domain,
        "matchType": "domain",
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": ["statuscode:200", "mimetype:text/html", f"urlkey:.*{safe_pattern}.*"],
        "collapse": "urlkey",
        "limit": limit,
    }
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    # Domain scans are broad and independently resumable. Do not multiply an
    # archive outage into several minutes of retries for every publisher.
    raw, _, _ = _fetch_bytes(
        f"{WAYBACK_CDX_URL}?{urlencode(params, doseq=True)}", timeout, retries=0,
    )
    return parse_wayback_cdx(raw)


def fetch_wayback_capture(record: dict, timeout: int = 30) -> tuple[bytes, str, dict]:
    archive_url = f"{WAYBACK_WEB_URL}/{record['timestamp']}id_/{record['original']}"
    raw, final_url, _ = _fetch_bytes(archive_url, timeout, {"Accept": "text/html,application/xhtml+xml"})
    metadata = {
        "archive_provider": "wayback",
        "archive_timestamp": record.get("timestamp"),
        "archive_digest": record.get("digest"),
        "archive_original": record.get("original"),
    }
    return raw, final_url, metadata


def parse_commoncrawl_index(raw: bytes) -> list[dict]:
    records = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def archive_url_variants(url: str) -> list[str]:
    """Return bounded exact variants commonly retained by web archives."""
    parsed = urlsplit(url)
    hosts = [parsed.netloc]
    if parsed.netloc.startswith("www."):
        hosts.append(parsed.netloc[4:])
    elif parsed.netloc:
        hosts.append("www." + parsed.netloc)
    paths = [parsed.path or "/"]
    if parsed.path and parsed.path != "/":
        paths.append(parsed.path.rstrip("/") if parsed.path.endswith("/") else parsed.path + "/")
    variants = []
    for host in hosts:
        for path in paths:
            candidate = urlunsplit((parsed.scheme or "https", host, path, parsed.query, ""))
            if candidate not in variants:
                variants.append(candidate)
    return variants


def commoncrawl_capture(url: str, timeout: int = 30, indexes: int = 3) -> dict | None:
    global _COMMONCRAWL_COLLECTIONS_CACHE
    if _COMMONCRAWL_COLLECTIONS_CACHE is None:
        collections_raw, _, _ = _fetch_bytes(
            COMMONCRAWL_COLLECTIONS_URL, timeout, retries=0,
        )
        _COMMONCRAWL_COLLECTIONS_CACHE = json.loads(collections_raw.decode("utf-8", errors="replace"))
    collections = _COMMONCRAWL_COLLECTIONS_CACHE
    matches = []
    for collection in collections[:indexes]:
        query = urlencode({"url": url, "output": "json", "filter": "status:200"})
        try:
            raw, _, _ = _fetch_bytes(
                f"{collection['cdx-api']}?{query}", timeout, retries=0,
            )
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        for record in parse_commoncrawl_index(raw):
            if record.get("mime") == "text/html" or record.get("mime-detected") == "text/html":
                record["collection"] = collection.get("id")
                matches.append(record)
        if matches:
            break
    return max(matches, key=lambda row: row.get("timestamp", "")) if matches else None


def extract_warc_http_payload(raw: bytes) -> tuple[bytes, dict[str, str]]:
    """Extract the HTTP entity from one decompressed Common Crawl WARC record."""
    _, separator, http_record = raw.partition(b"\r\n\r\n")
    if not separator:
        raise ValueError("WARC headers are incomplete")
    header_blob, separator, body = http_record.partition(b"\r\n\r\n")
    if not separator:
        raise ValueError("Embedded HTTP headers are incomplete")
    lines = header_blob.decode("iso-8859-1", errors="replace").splitlines()
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    if headers.get("content-encoding", "").lower() == "gzip":
        body = gzip.decompress(body)
    return body, headers


def fetch_commoncrawl_capture(record: dict, timeout: int = 30) -> tuple[bytes, str, dict]:
    offset = int(record["offset"])
    length = int(record["length"])
    data_url = f"{COMMONCRAWL_DATA_URL}/{record['filename']}"
    blob, _, _ = _fetch_bytes(data_url, timeout, {"Range": f"bytes={offset}-{offset + length - 1}"})
    body, response_headers = extract_warc_http_payload(gzip.decompress(blob))
    archive_url = f"{data_url}#offset={offset}&length={length}"
    metadata = {
        "archive_provider": "commoncrawl",
        "archive_timestamp": record.get("timestamp"),
        "archive_digest": record.get("digest"),
        "archive_original": record.get("url"),
        "commoncrawl_collection": record.get("collection"),
        "commoncrawl_response_headers": response_headers,
    }
    return body, archive_url, metadata


def validate_archived_html(raw: bytes) -> None:
    prefix = raw[:4096].lower()
    if len(raw) < 500 or (b"<html" not in prefix and b"<!doctype html" not in prefix):
        raise ValueError(f"archive replay is not substantive HTML ({len(raw)} bytes)")


def fetch_json_with_429_retry(req: Request, timeout: int, retries: int = 3) -> dict:
    """Fetch JSON with bounded exponential retries for public-API rate limiting."""
    attempt = 0
    while True:
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            if exc.code != 429 or attempt >= retries:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = max(6.0, float(retry_after)) if retry_after else 8.0 * (2 ** attempt)
            except ValueError:
                delay = 8.0 * (2 ** attempt)
            time.sleep(min(delay, 30.0))
            attempt += 1


def ensure_publisher(
    db: sqlite3.Connection, name: str | None, domain: str, *,
    country: str | None = None, default_language: str | None = None,
    source_type: str | None = None,
) -> int:
    existing = db.execute("SELECT id,name FROM publisher WHERE domain=?", (domain,)).fetchone()
    if existing:
        stable_name = existing["name"]
        if name and (not stable_name or stable_name.casefold() == domain.casefold()):
            stable_name = name
        db.execute(
            """UPDATE publisher SET name=?,country=COALESCE(country,?),
               default_language=COALESCE(default_language,?),updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (
                stable_name, normalize_country(country), normalize_language(default_language),
                existing["id"],
            ),
        )
        return existing["id"]
    cursor = db.execute(
        """INSERT INTO publisher(name,domain,country,default_language,source_type)
           VALUES(?,?,?,?,?)""",
        (
            name or domain, domain, normalize_country(country), normalize_language(default_language),
            normalize_source_type(source_type),
        ),
    )
    return int(cursor.lastrowid)


def ensure_authors(db: sqlite3.Connection, item_id: int, authors: list[str] | None) -> None:
    for position, raw_name in enumerate(authors or []):
        name = re.sub(r"\s+", " ", raw_name).strip()
        if not name:
            continue
        db.execute("INSERT OR IGNORE INTO author(canonical_name) VALUES(?)", (name,))
        author_id = db.execute("SELECT id FROM author WHERE canonical_name=?", (name,)).fetchone()[0]
        db.execute(
            "INSERT OR REPLACE INTO item_author(item_id,author_id,position) VALUES(?,?,?)",
            (item_id, author_id, position),
        )


def infer_item_type(record: dict, canonical_url: str) -> str:
    """Infer a supported corpus type when discovery did not supply one."""
    if record.get("item_type"):
        return str(record["item_type"])
    segments = {part.casefold() for part in urlsplit(canonical_url).path.split("/") if part}
    if "video" in segments or "videos" in segments:
        return "broadcast_transcript"
    return "article"


def ingest_record(db: sqlite3.Connection, record: dict, *, discovery_method: str) -> tuple[int, bool, bool]:
    source_url = record.get("canonical_url") or record.get("url")
    canonical_url = normalize_url(source_url)
    item_type = infer_item_type(record, canonical_url)
    domain = domain_from_url(canonical_url)
    publisher_id = ensure_publisher(
        db, record.get("publisher"), domain,
        country=record.get("publisher_country"),
        default_language=record.get("publisher_default_language") or record.get("language"),
        source_type=record.get("publisher_source_type"),
    )
    title = re.sub(r"\s+", " ", str(record.get("title") or "Untitled reporting item")).strip()
    published_at = normalize_published_at(record.get("published_at")) or publication_date_from_url(canonical_url)
    publisher_language = db.execute(
        "SELECT default_language FROM publisher WHERE id=?", (publisher_id,)
    ).fetchone()[0]
    item_language = normalize_language(record.get("language")) or normalize_language(publisher_language)
    existing = db.execute("SELECT * FROM reporting_item WHERE canonical_url=?", (canonical_url,)).fetchone()
    created = existing is None
    if created:
        cursor = db.execute(
            """
            INSERT INTO reporting_item(
                item_type,title,dek,canonical_url,publisher_id,published_at,updated_at,
                language,access_status,rights_status,abstract,source_native_id,
                discovery_method,independence_group,notes,scope_class
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                item_type, title, record.get("dek"), canonical_url,
                publisher_id, published_at,
                normalize_published_at(record.get("updated_at")),
                item_language, record.get("access_status", "unknown"),
                record.get("rights_status", "metadata_only"), record.get("abstract"),
                record.get("source_native_id"), discovery_method,
                record.get("independence_group") or f"outlet:{domain}", record.get("notes"),
                record.get("scope_class", "direct"),
            ),
        )
        item_id = int(cursor.lastrowid)
    else:
        item_id = int(existing["id"])
        db.execute(
            """
            UPDATE reporting_item SET title=?, dek=COALESCE(?,dek), publisher_id=?,
                item_type=CASE WHEN item_type='article' AND ?<>'article' THEN ? ELSE item_type END,
                published_at=COALESCE(?,published_at), updated_at=COALESCE(?,updated_at),
                language=COALESCE(?,language), abstract=COALESCE(?,abstract),
                source_native_id=COALESCE(source_native_id,?), notes=COALESCE(notes,?),
                access_status=CASE WHEN ?='unknown' THEN access_status ELSE ? END,
                rights_status=CASE WHEN ?='metadata_only' THEN rights_status ELSE ? END,
                last_seen_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                title, record.get("dek"), publisher_id, item_type, item_type,
                published_at,
                normalize_published_at(record.get("updated_at")),
                item_language, record.get("abstract"),
                record.get("source_native_id"), record.get("notes"),
                record.get("access_status", "unknown"), record.get("access_status", "unknown"),
                record.get("rights_status", "metadata_only"), record.get("rights_status", "metadata_only"),
                item_id,
            ),
        )
    ensure_authors(db, item_id, record.get("authors"))

    content_text = record.get("content_text")
    version_hash = record.get("content_hash") or stable_hash(
        title, record.get("dek"), record.get("abstract"), content_text, record.get("updated_at")
    )
    version = db.execute(
        "SELECT id FROM item_version WHERE item_id=? AND content_hash=?", (item_id, version_hash)
    ).fetchone()
    version_created = version is None
    current_version = db.execute(
        "SELECT * FROM item_version WHERE id=(SELECT current_version_id FROM reporting_item WHERE id=?)",
        (item_id,),
    ).fetchone()
    # Bibliographic imports often arrive after a live full-text capture. Enrich that
    # capture's provenance instead of replacing the searchable current version with
    # an empty metadata-only version.
    if (
        not created and content_text in (None, "") and current_version
        and current_version["content_text"] not in (None, "")
    ):
        old_metadata = json.loads(current_version["metadata_json"] or "{}")
        incoming_metadata = record.get("metadata") or {}
        old_metadata.update({key: value for key, value in incoming_metadata.items() if value is not None})
        db.execute(
            """UPDATE item_version SET metadata_json=?,archive_url=COALESCE(archive_url,?)
               WHERE id=?""",
            (json_text(old_metadata), record.get("archive_url"), current_version["id"]),
        )
        version_created = False
    elif not version_created and version and record.get("metadata"):
        matched_version = db.execute(
            "SELECT metadata_json FROM item_version WHERE id=?", (version["id"],)
        ).fetchone()
        merged_metadata = json.loads(matched_version["metadata_json"] or "{}")
        merged_metadata.update({
            key: value for key, value in record["metadata"].items() if value is not None
        })
        db.execute(
            """UPDATE item_version SET metadata_json=?,archive_url=COALESCE(archive_url,?)
               WHERE id=?""",
            (json_text(merged_metadata), record.get("archive_url"), version["id"]),
        )
    if version_created:
        db.execute(
            "UPDATE item_version SET version_status='superseded' WHERE item_id=? AND version_status='current'",
            (item_id,),
        )
        cursor = db.execute(
            """
            INSERT INTO item_version(
                item_id,source_url,archive_url,content_text,content_hash,metadata_json,
                version_status,change_summary
            ) VALUES(?,?,?,?,?,?,'current',?)
            """,
            (
                item_id, source_url, record.get("archive_url"), content_text, version_hash,
                json_text(record.get("metadata", {})),
                "initial capture" if created else "content or metadata changed",
            ),
        )
        version_id = int(cursor.lastrowid)
        db.execute("UPDATE reporting_item SET current_version_id=? WHERE id=?", (version_id, item_id))
    refresh_item_fts(db, item_id)
    db.execute(
        "UPDATE discovery_candidate SET status='ingested',processed_at=CURRENT_TIMESTAMP WHERE url IN (?,?)",
        (source_url, canonical_url),
    )
    db.commit()
    return item_id, created, version_created


def add_candidate(
    db: sqlite3.Connection, *, url: str, method: str, run_id: int | None = None,
    title: str | None = None, published_at: str | None = None, language: str | None = None,
    query: str | None = None, metadata: dict | None = None, scope_class: str = "candidate",
) -> bool:
    try:
        normalized = normalize_url(url)
    except ValueError:
        return False
    previous = db.execute("SELECT status FROM discovery_candidate WHERE url=?", (normalized,)).fetchone()
    cursor = db.execute(
        """
        INSERT INTO discovery_candidate(
            url,title,publisher_domain,published_at,language,discovery_run_id,
            discovery_method,query,metadata_json,scope_class
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(url) DO UPDATE SET
            title=COALESCE(discovery_candidate.title,excluded.title),
            published_at=COALESCE(discovery_candidate.published_at,excluded.published_at),
            language=COALESCE(discovery_candidate.language,excluded.language),
            metadata_json=excluded.metadata_json,
            scope_class=excluded.scope_class,
            discovery_run_id=CASE WHEN discovery_candidate.status='excluded'
                THEN excluded.discovery_run_id ELSE discovery_candidate.discovery_run_id END,
            discovery_method=CASE WHEN discovery_candidate.status='excluded'
                THEN excluded.discovery_method ELSE discovery_candidate.discovery_method END,
            query=CASE WHEN discovery_candidate.status='excluded'
                THEN excluded.query ELSE discovery_candidate.query END,
            status=CASE WHEN discovery_candidate.status='excluded' THEN 'pending' ELSE discovery_candidate.status END,
            status_note=CASE WHEN discovery_candidate.status='excluded' THEN NULL ELSE discovery_candidate.status_note END
        """,
        (
            normalized, title, domain_from_url(normalized), normalize_published_at(published_at),
            normalize_language(language),
            run_id, method, query, json_text(metadata or {}), scope_class,
        ),
    )
    return previous is None or previous["status"] == "excluded"


def begin_run(db: sqlite3.Connection, method: str, query: str | None, source: str, params: dict) -> int:
    cursor = db.execute(
        "INSERT INTO discovery_run(method,query,source_name,parameters_json) VALUES(?,?,?,?)",
        (method, query, source, json_text(params)),
    )
    db.commit()
    return int(cursor.lastrowid)


def finish_run(db: sqlite3.Connection, run_id: int, result_count: int, imported_count: int, error: str | None = None) -> None:
    db.execute(
        """UPDATE discovery_run SET completed_at=CURRENT_TIMESTAMP,result_count=?,imported_count=?,error=? WHERE id=?""",
        (result_count, imported_count, error, run_id),
    )
    db.commit()


def cmd_init(args: argparse.Namespace) -> None:
    db = connect(args.db)
    version = db.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
    print(f"Initialized {args.db} (schema {version})")


def cmd_ingest_url(args: argparse.Namespace) -> None:
    raw, final_url, content_type = fetch_url(args.url, args.timeout)
    if content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError(f"Expected HTML, received {content_type}")
    record = parse_article_html(raw, final_url)
    record.update({
        "title": args.title or record["title"],
        "publisher": args.publisher or record.get("publisher"),
        "published_at": args.published_at or record.get("published_at"),
        "language": args.language or record.get("language"),
        "access_status": args.access_status,
        "rights_status": args.rights_status,
        "item_type": args.item_type,
    })
    if not args.store_text:
        record["content_text"] = None
    record["metadata"]["http_final_url"] = final_url
    record["metadata"]["raw_response_hash"] = record.pop("raw_hash")
    db = connect(args.db)
    item_id, created, version_created = ingest_record(db, record, discovery_method="direct_url")
    print(f"Item #{item_id}: {'created' if created else 'updated'}; version {'created' if version_created else 'unchanged'}")


def _records_from_jsonl(path: Path) -> list[dict]:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc
    return records


def _records_from_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _records_from_ris(path: Path) -> list[dict]:
    records: list[dict] = []
    current: dict[str, list[str]] = {}
    last_tag: str | None = None
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        match = re.match(r"^([A-Z0-9]{2})  - ?(.*)$", line)
        if match:
            tag, value = match.groups()
            if tag == "ER":
                if current:
                    records.append(current)
                current, last_tag = {}, None
                continue
            current.setdefault(tag, []).append(value.strip())
            last_tag = tag
        elif last_tag and line.strip():
            current[last_tag][-1] += " " + line.strip()
    if current:
        records.append(current)

    converted = []
    for ris in records:
        first = lambda *tags: next((ris[t][0] for t in tags if ris.get(t)), None)
        url = first("UR", "L1", "L2")
        if not url:
            continue
        converted.append({
            "title": first("TI", "T1", "CT") or "Untitled reporting item",
            "canonical_url": url,
            "authors": ris.get("AU") or ris.get("A1") or [],
            "published_at": first("DA", "Y1", "PY"),
            "publisher": first("JO", "JF", "T2", "PB"),
            "abstract": first("AB", "N2"),
            "language": first("LA"),
            "source_native_id": first("AN", "ID"),
            "access_status": "licensed",
            "rights_status": "metadata_only",
            "metadata": {"ris": ris},
        })
    return converted


def _records_from_file(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        return _records_from_jsonl(path)
    if suffix == ".csv":
        return _records_from_csv(path)
    if suffix == ".ris":
        return _records_from_ris(path)
    raise ValueError("Supported imports: .jsonl, .ndjson, .csv, .ris")


FIELD_ALIASES = {
    "url": ("url", "canonical_url", "URL", "DocumentURL", "Full Text URL"),
    "title": ("title", "Title", "TI"),
    "publisher": ("publisher", "publication", "Publication", "Source title", "Journal"),
    "published_at": ("published_at", "date", "Date", "Publication date"),
    "abstract": ("abstract", "Abstract", "summary"),
    "language": ("language", "Language"),
    "content_text": ("content_text", "full_text", "Full text", "Text"),
}


def normalize_import_record(raw: dict) -> dict:
    record = dict(raw)
    for target, aliases in FIELD_ALIASES.items():
        if record.get(target) not in (None, ""):
            continue
        value = next((raw.get(alias) for alias in aliases if raw.get(alias) not in (None, "")), None)
        if value is not None:
            record[target] = value
    if not record.get("canonical_url"):
        record["canonical_url"] = record.get("url")
    authors = record.get("authors") or record.get("author") or record.get("Author")
    if isinstance(authors, str):
        authors = [part.strip() for part in re.split(r"\s*;\s*|\s+and\s+", authors) if part.strip()]
    record["authors"] = authors or []
    return record


def cmd_import_file(args: argparse.Namespace) -> None:
    path = Path(args.path)
    suffix = path.suffix.lower()
    records = _records_from_file(path)
    db = connect(args.db)
    run_id = begin_run(db, "file_import", str(path), args.source, {"path": str(path), "format": suffix})
    imported = 0
    errors = []
    for index, raw in enumerate(records, 1):
        try:
            record = normalize_import_record(raw)
            if not record.get("canonical_url"):
                raise ValueError("missing URL")
            if record.get("content_text") and args.rights_status == "metadata_only":
                record["content_text"] = None
            record.setdefault("access_status", args.access_status)
            record.setdefault("rights_status", args.rights_status)
            metadata = dict(record.get("metadata") or {"import_record": raw})
            candidate = db.execute(
                "SELECT id FROM discovery_candidate WHERE url=?",
                (normalize_url(record["canonical_url"]),),
            ).fetchone()
            if candidate:
                metadata.setdefault("source_candidate_id", int(candidate["id"]))
                fetched = db.execute(
                    """SELECT i.canonical_url,v.metadata_json
                       FROM reporting_item i
                       JOIN item_version v ON v.id=i.current_version_id
                       WHERE CAST(json_extract(v.metadata_json,'$.discovery_candidate_id') AS INTEGER)=?
                       LIMIT 1""",
                    (int(candidate["id"]),),
                ).fetchone()
                if fetched:
                    original_url = normalize_url(record["canonical_url"])
                    fetched_metadata = json.loads(fetched["metadata_json"] or "{}")
                    aliases = list(fetched_metadata.get("canonical_aliases") or [])
                    if original_url != fetched["canonical_url"] and original_url not in aliases:
                        aliases.append(original_url)
                    if aliases:
                        metadata["canonical_aliases"] = aliases
                    record["canonical_url"] = fetched["canonical_url"]
            record["metadata"] = metadata
            ingest_record(db, record, discovery_method=f"import:{args.source}")
            imported += 1
        except Exception as exc:
            errors.append(f"record {index}: {exc}")
    finish_run(db, run_id, len(records), imported, "\n".join(errors[:20]) or None)
    print(f"Imported {imported}/{len(records)} reporting items from {path}")
    if errors:
        print(f"{len(errors)} records failed; first error: {errors[0]}", file=sys.stderr)


def cmd_discover_file(args: argparse.Namespace) -> None:
    """Add URLs from a reproducible bibliographic file to the fetch queue."""
    path = Path(args.path)
    records = _records_from_file(path)
    db = connect(args.db)
    run_id = begin_run(
        db, "file_discovery", str(path), args.source,
        {"path": str(path), "format": path.suffix.lower()},
    )
    imported = 0
    errors = []
    for index, raw in enumerate(records, 1):
        try:
            record = normalize_import_record(raw)
            url = record.get("canonical_url")
            if not url:
                raise ValueError("missing URL")
            metadata = dict(record.get("metadata") or {})
            metadata.update({
                "publisher": record.get("publisher"),
                "access_status": record.get("access_status"),
                "source_record": raw,
            })
            imported += int(add_candidate(
                db, url=url, title=record.get("title"),
                published_at=record.get("published_at"),
                language=record.get("language"), method=f"file:{args.source}",
                run_id=run_id, query=str(path), metadata=metadata,
                scope_class=record.get("scope_class") or "candidate",
            ))
        except Exception as exc:
            errors.append(f"record {index}: {exc}")
    finish_run(db, run_id, len(records), imported, "\n".join(errors[:20]) or None)
    print(f"Discovered {len(records)} file records; added {imported} new candidates from {path}")
    if errors:
        print(f"{len(errors)} records failed; first error: {errors[0]}", file=sys.stderr)


def cmd_discover_gdelt(args: argparse.Namespace) -> None:
    params = {
        "query": args.query, "mode": "artlist", "maxrecords": args.limit,
        "format": "json", "timespan": args.timespan,
    }
    run_db = connect(args.db)
    run_id = begin_run(run_db, "gdelt", args.query, "GDELT DOC 2.0", params)
    try:
        req = Request(f"{GDELT_DOC_URL}?{urlencode(params)}", headers={"User-Agent": USER_AGENT})
        payload = fetch_json_with_429_retry(req, args.timeout)
        articles = payload.get("articles", [])
        imported = 0
        for article in articles:
            imported += int(add_candidate(
                run_db, url=article.get("url", ""), title=article.get("title"),
                published_at=article.get("seendate"), language=article.get("language"),
                method="gdelt", run_id=run_id, query=args.query, metadata=article,
            ))
        finish_run(run_db, run_id, len(articles), imported)
        print(f"Discovered {len(articles)} GDELT results; added {imported} new candidates")
    except Exception as exc:
        finish_run(run_db, run_id, 0, 0, str(exc))
        raise


def cmd_discover_feed(args: argparse.Namespace) -> None:
    raw, final_url, _ = fetch_url(args.url, args.timeout)
    root = ET.fromstring(raw)
    entries = root.findall(".//item")
    if not entries:
        entries = root.findall(".//{*}entry")
    db = connect(args.db)
    run_id = begin_run(db, "feed", args.query, final_url, {"url": args.url})
    imported = 0
    for entry in entries:
        def find_text(names: list[str]) -> str | None:
            for name in names:
                node = entry.find(name) or entry.find(f"{{*}}{name}")
                if node is not None and node.text:
                    return node.text.strip()
            return None
        link = find_text(["link"])
        if not link:
            node = entry.find("{*}link")
            link = node.attrib.get("href") if node is not None else None
        if link and (not args.query or args.query.casefold() in " ".join(entry.itertext()).casefold()):
            imported += int(add_candidate(
                db, url=urljoin(final_url, link), title=find_text(["title"]),
                published_at=find_text(["pubDate", "published", "updated"]),
                method="feed", run_id=run_id, query=args.query,
                metadata={"feed_url": final_url},
            ))
    finish_run(db, run_id, len(entries), imported)
    print(f"Scanned {len(entries)} feed entries; added {imported} new candidates")


def cmd_discover_page(args: argparse.Namespace) -> None:
    raw, final_url, content_type = fetch_url(args.url, args.timeout)
    if content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError(f"Expected HTML, received {content_type}")
    links = extract_page_links(raw, final_url)
    source_domain = domain_from_url(normalize_url(final_url))
    terms = [term.casefold() for term in (args.query or ["epstein", "maxwell"])]
    link_pattern = re.compile(args.link_regex) if args.link_regex else None
    db = connect(args.db)
    run_id = begin_run(db, "publisher_page", " OR ".join(terms), final_url, {
        "url": args.url, "same_domain": args.same_domain,
        "language": args.language, "publisher": args.publisher,
        "link_regex": args.link_regex,
    })
    imported = matched = 0
    errors = []
    for url, title in links:
        try:
            if normalize_url(url) == normalize_url(final_url):
                continue
            if is_navigation_link(title) or is_topic_landing_page(url, title):
                continue
            if args.same_domain:
                link_domain = domain_from_url(normalize_url(url))
                if link_domain != source_domain and not link_domain.endswith("." + source_domain):
                    continue
            term_match = any(term in f"{url} {title}".casefold() for term in terms)
            empty_card_match = bool(link_pattern and not title and link_pattern.search(url))
            if not term_match and not empty_card_match:
                continue
            matched += 1
            imported += int(add_candidate(
                db, url=url, title=title or None, language=args.language,
                method="publisher_page", run_id=run_id, query=" OR ".join(terms),
                metadata={"source_page": final_url, "publisher": args.publisher},
                scope_class="direct" if empty_card_match else "candidate",
            ))
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    finish_run(db, run_id, matched, imported, "\n".join(errors[:20]) or None)
    print(f"Scanned {len(links)} page links; matched {matched}; added {imported} candidates")


def _load_source_config(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("version") != 1:
        raise ValueError(f"Unsupported reporting source config version: {data.get('version')}")
    return data


def _unwrap_archive_url(url: str) -> str:
    match = re.match(r"https?://web\.archive\.org/web/[^/]+/(https?://.+)$", url)
    return match.group(1) if match else url


def cmd_discover_repository(args: argparse.Namespace) -> None:
    config = _load_source_config(args.config)
    publishers = config.get("publishers", [])
    allowed = {entry["domain"].lower(): entry for entry in publishers}
    db = connect(args.db)
    for domain, entry in allowed.items():
        publisher_id = ensure_publisher(db, entry.get("name"), domain)
        db.execute(
            """
            UPDATE publisher SET source_type=?,reliability_notes=?,epstein_connection=?,
                   country=?,default_language=?,updated_at=CURRENT_TIMESTAMP WHERE id=?
            """,
            (
                normalize_source_type(entry.get("source_type")), entry.get("reliability_notes"),
                entry.get("epstein_connection"), entry.get("country"),
                entry.get("language"), publisher_id,
            ),
        )
    paths = args.path or config.get("repository_seed_paths", [])
    discovery_pages = {
        normalize_url(entry["url"]) for entry in config.get("discovery_pages", [])
        if entry.get("url")
    }
    contextual_roots = set(config.get("contextual_seed_paths", []))
    run_id = begin_run(db, "repository_references", None, str(args.config), {"paths": paths})
    db.execute(
        """UPDATE discovery_candidate SET status='excluded',status_note='Not present in latest relevance-scoped repository seed'
           WHERE discovery_method='repository_reference' AND status='pending'"""
    )
    total_urls = 0
    imported = 0
    files_scanned = 0
    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        try:
            configured_rel = str(path.relative_to(Path(__file__).resolve().parent.parent))
        except ValueError:
            configured_rel = str(path)
        files = [path] if path.is_file() else list(path.rglob("*")) if path.is_dir() else []
        for file_path in files:
            if file_path.suffix.lower() not in {".md", ".mdx", ".json", ".yaml", ".yml"}:
                continue
            files_scanned += 1
            try:
                file_rel = str(file_path.relative_to(Path(__file__).resolve().parent.parent))
            except ValueError:
                file_rel = str(file_path)
            file_is_contextual = any(
                file_rel == root or file_rel.startswith(root.rstrip("/") + "/")
                for root in contextual_roots
            )
            content = file_path.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"https?://[^\s<>\"'`]+", content):
                url = match.group(0).rstrip(".,;:!?]}")
                while url.endswith(")") and url.count(")") > url.count("("):
                    url = url[:-1]
                url = _unwrap_archive_url(url)
                total_urls += 1
                context = content[max(0, match.start() - 1500):match.end() + 1500]
                direct = bool(re.search(r"\b(?:jeffrey\s+)?epstein\b|\bghislaine\s+maxwell\b", context, re.I))
                if not direct and not file_is_contextual:
                    continue
                scope_class = "contextual" if file_is_contextual else "candidate"
                try:
                    normalized_url = normalize_url(url)
                    domain = domain_from_url(normalized_url)
                except ValueError:
                    continue
                if normalized_url in discovery_pages or is_topic_landing_page(normalized_url):
                    continue
                source = next((entry for key, entry in allowed.items() if domain == key or domain.endswith("." + key)), None)
                if not source:
                    continue
                prefix = content[max(0, match.start() - 300):match.start()]
                label_match = re.search(r"\[([^\]\n]{2,250})\]\($", prefix)
                imported += int(add_candidate(
                    db, url=url, title=label_match.group(1).strip() if label_match else None,
                    method="repository_reference", run_id=run_id, scope_class=scope_class,
                    metadata={"file": str(file_path.relative_to(Path(__file__).resolve().parent.parent)),
                              "publisher": source.get("name"), "scope_class": scope_class},
                ))
    finish_run(db, run_id, total_urls, imported)
    db.commit()
    print(f"Scanned {files_scanned} files and {total_urls} URLs; added {imported} reporting candidates")


def cmd_discover_wayback(args: argparse.Namespace) -> None:
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    publisher_map = {
        entry["domain"]: entry for entry in config.get("publishers", []) if entry.get("domain")
    }
    domains = args.domain or list(publisher_map)
    if args.max_domains:
        domains = domains[:args.max_domains]
    patterns = args.url_pattern or ["epstein"]
    db = connect(args.db)
    run_id = begin_run(db, "wayback_domain", " OR ".join(patterns), "Wayback CDX", {
        "domains": domains, "patterns": patterns, "limit_per_domain": args.limit_per_domain,
        "from": args.from_date, "to": args.to_date,
        "max_consecutive_errors": args.max_consecutive_errors,
    })
    seen = imported = 0
    errors = []
    consecutive_errors = 0
    stopped_early = False
    for domain in domains:
        for pattern in patterns:
            try:
                records = wayback_domain_urls(
                    domain, pattern, args.timeout, args.limit_per_domain,
                    args.from_date, args.to_date,
                )
                seen += len(records)
                for record in records:
                    original = html.unescape(record.get("original") or "")
                    if not original:
                        continue
                    imported += int(add_candidate(
                        db, url=original, method="wayback_cdx", run_id=run_id,
                        language=publisher_map.get(domain, {}).get("language"),
                        query=f"{domain}:urlkey:{pattern}",
                        metadata={
                            "archive_provider": "wayback",
                            "archive_timestamp": record.get("timestamp"),
                            "archive_digest": record.get("digest"),
                            "publisher": publisher_map.get(domain, {}).get("name"),
                        },
                    ))
                db.commit()
                consecutive_errors = 0
            except Exception as exc:
                errors.append(f"{domain}/{pattern}: {exc}")
                consecutive_errors += 1
                if args.max_consecutive_errors and consecutive_errors >= args.max_consecutive_errors:
                    errors.append(
                        f"Stopped after {consecutive_errors} consecutive archive errors; rerun is resumable"
                    )
                    stopped_early = True
            if args.delay:
                time.sleep(args.delay)
            if stopped_early:
                break
        if stopped_early:
            break
    finish_run(db, run_id, seen, imported, "\n".join(errors[:30]) or None)
    print(f"Wayback URL discovery: {seen} captures processed; {imported} new candidates")
    if errors:
        print(f"{len(errors)} domain queries failed; first: {errors[0]}", file=sys.stderr)


def _fetch_candidate(candidate: dict, args: argparse.Namespace) -> dict:
    try:
        candidate_metadata = json.loads(candidate["metadata_json"] or "{}")
        raw, final_url, content_type = fetch_candidate_url(
            candidate["url"], candidate_metadata, args.timeout,
        )
        if is_access_interstitial(final_url):
            raise ValueError(f"publisher access interstitial, not article ({final_url})")
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"not HTML ({content_type})")
        record = parse_article_html(raw, final_url)
        record["language"] = record.get("language") or candidate["language"]
        record["published_at"] = record.get("published_at") or candidate["published_at"]
        candidate_domain = domain_from_url(candidate["url"])
        final_domain = domain_from_url(final_url)
        candidate_publisher = (
            candidate_metadata.get("publisher") if candidate_domain == final_domain else None
        )
        record["publisher"] = record.get("publisher") or candidate_publisher
        record["publisher_country"] = candidate_metadata.get("sourcecountry")
        record["publisher_default_language"] = candidate["language"]
        record["publisher_source_type"] = "unknown"
        record["access_status"] = args.access_status
        record["rights_status"] = args.rights_status
        is_direct = is_direct_reporting(record)
        if candidate["scope_class"] == "candidate" and not is_direct:
            return {"status": "excluded", "note": "Fetched item lacks direct Epstein/Maxwell reporting"}
        record["scope_class"] = "direct" if is_direct else candidate["scope_class"]
        if not args.store_text or len((record.get("content_text") or "").strip()) < 200:
            record["content_text"] = None
            record["rights_status"] = "metadata_only"
        record["metadata"]["discovery_candidate_id"] = candidate["id"]
        return {"status": "ingested", "record": record}
    except Exception as exc:
        return {"status": "failed", "note": str(exc)[:1000]}
    finally:
        if args.delay:
            time.sleep(args.delay)


def align_candidate_canonical(db: sqlite3.Connection, candidate_url: str, record_url: str) -> None:
    candidate_url = normalize_url(candidate_url)
    record_url = normalize_url(record_url)
    if candidate_url == record_url:
        return
    old_item = db.execute(
        "SELECT id FROM reporting_item WHERE canonical_url=?", (candidate_url,)
    ).fetchone()
    final_item = db.execute(
        "SELECT id FROM reporting_item WHERE canonical_url=?", (record_url,)
    ).fetchone()
    if old_item and not final_item:
        db.execute(
            "UPDATE reporting_item SET canonical_url=? WHERE id=?",
            (record_url, old_item["id"]),
        )
        db.commit()


def cmd_ingest_candidates(args: argparse.Namespace) -> None:
    db = connect(args.db)
    candidates = [dict(row) for row in db.execute(
        "SELECT * FROM discovery_candidate WHERE status='pending' ORDER BY discovered_at LIMIT ?",
        (args.limit,),
    ).fetchall()]
    ingested = 0
    worker_count = max(1, args.workers)
    if worker_count == 1:
        results = map(lambda candidate: _fetch_candidate(candidate, args), candidates)
        executor = None
    else:
        executor = ThreadPoolExecutor(max_workers=worker_count)
        results = executor.map(lambda candidate: _fetch_candidate(candidate, args), candidates)
    try:
        for candidate, result in zip(candidates, results):
            if result["status"] == "ingested":
                align_candidate_canonical(
                    db, candidate["url"], result["record"]["canonical_url"],
                )
                ingest_record(db, result["record"], discovery_method=candidate["discovery_method"])
                db.execute(
                    """UPDATE discovery_candidate SET status='ingested',status_note=NULL,
                       processed_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (candidate["id"],),
                )
                db.commit()
                ingested += 1
            else:
                already_present = db.execute(
                    "SELECT 1 FROM reporting_item WHERE canonical_url=? LIMIT 1",
                    (candidate["url"],),
                ).fetchone()
                if already_present:
                    db.execute(
                        """UPDATE discovery_candidate SET status='ingested',
                           status_note='Canonical reporting item already present',
                           processed_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (candidate["id"],),
                    )
                else:
                    db.execute(
                        """UPDATE discovery_candidate SET status=?,status_note=?,processed_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (result["status"], result.get("note"), candidate["id"]),
                    )
                db.commit()
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    print(f"Ingested {ingested}/{len(candidates)} pending candidates")


def cmd_materialize_candidates(args: argparse.Namespace) -> None:
    """Create metadata-only items without removing candidates from the fetch queue."""
    db = connect(args.db)
    statuses = args.status or ["pending", "failed"]
    placeholders = ",".join("?" for _ in statuses)
    params: list[object] = list(statuses)
    where = [f"status IN ({placeholders})"]
    if args.method:
        where.append("discovery_method=?")
        params.append(args.method)
    if getattr(args, "run_id", None) is not None:
        where.append("discovery_run_id=?")
        params.append(args.run_id)
    params.append(args.limit)
    candidates = db.execute(
        f"SELECT * FROM discovery_candidate WHERE {' AND '.join(where)} ORDER BY discovered_at LIMIT ?",
        params,
    ).fetchall()
    materialized = skipped = 0
    for candidate in candidates:
        metadata = json.loads(candidate["metadata_json"] or "{}")
        if is_navigation_link(candidate["title"]) or is_topic_landing_page(
            candidate["url"], candidate["title"]
        ):
            skipped += 1
            continue
        if args.require_direct and candidate["scope_class"] != "direct" and not contains_core_subject(
            f"{candidate['title'] or ''} {candidate['url']}"
        ):
            skipped += 1
            continue
        record = {
            "title": candidate_display_title(dict(candidate)),
            "canonical_url": candidate["url"],
            "publisher": metadata.get("publisher") or candidate["publisher_domain"],
            "published_at": candidate["published_at"] or publication_date_from_url(candidate["url"]),
            "language": candidate["language"],
            "access_status": args.access_status,
            "rights_status": "metadata_only",
            "scope_class": "direct",
            "metadata": {
                # Deliberately not the ingest_record control key
                # ``discovery_candidate_id``: metadata materialization must not
                # remove the URL from the full-text fetch queue.
                "source_candidate_id": candidate["id"],
                "metadata_only_materialization": True,
                "candidate_metadata": metadata,
            },
        }
        ingest_record(db, record, discovery_method=f"metadata:{candidate['discovery_method']}")
        db.execute(
            "UPDATE discovery_candidate SET status=?,processed_at=NULL WHERE id=?",
            (candidate["status"], candidate["id"]),
        )
        db.commit()
        materialized += 1
    print(f"Materialized {materialized}/{len(candidates)} candidates; skipped {skipped} without direct title/URL evidence")


def cmd_cleanup_navigation(args: argparse.Namespace) -> None:
    """Remove publisher-page pagination controls accidentally queued as articles."""
    db = connect(args.db)
    candidates = db.execute(
        "SELECT * FROM discovery_candidate WHERE discovery_method='publisher_page'"
    ).fetchall()
    removed_items = excluded = skipped_claimed = 0
    for candidate in candidates:
        pagination = is_navigation_link(candidate["title"])
        landing_page = is_topic_landing_page(candidate["url"], candidate["title"])
        if not pagination and not landing_page:
            continue
        items = db.execute(
            """SELECT DISTINCT i.id FROM reporting_item i
               LEFT JOIN item_version v ON v.id=i.current_version_id
               WHERE i.canonical_url=?
                  OR json_extract(v.metadata_json,'$.discovery_candidate_id')=?""",
            (candidate["url"], candidate["id"]),
        ).fetchall()
        claimed_item = False
        for item in items:
            claimed = db.execute(
                "SELECT 1 FROM reporting_claim WHERE item_id=? LIMIT 1", (item["id"],)
            ).fetchone()
            if claimed:
                skipped_claimed += 1
                claimed_item = True
                continue
            db.execute("DELETE FROM reporting_fts WHERE item_id=?", (item["id"],))
            db.execute("DELETE FROM reporting_item WHERE id=?", (item["id"],))
            removed_items += 1
        if claimed_item:
            continue
        if candidate["status"] != "excluded":
            note = (
                "Publisher pagination control, not a reporting item"
                if pagination
                else "Publisher topic/index page, not a reporting item"
            )
            db.execute(
                """UPDATE discovery_candidate SET status='excluded',
                   status_note=?, processed_at=CURRENT_TIMESTAMP WHERE id=?""",
                (note, candidate["id"]),
            )
            excluded += 1
    for item in db.execute(
        "SELECT id,title,canonical_url,item_type FROM reporting_item WHERE item_type='article'"
    ).fetchall():
        if not is_topic_landing_page(item["canonical_url"], item["title"]):
            continue
        if db.execute(
            "SELECT 1 FROM reporting_claim WHERE item_id=? LIMIT 1", (item["id"],)
        ).fetchone():
            skipped_claimed += 1
            continue
        db.execute("DELETE FROM reporting_fts WHERE item_id=?", (item["id"],))
        db.execute("DELETE FROM reporting_item WHERE id=?", (item["id"],))
        db.execute(
            """UPDATE discovery_candidate SET status='excluded',
               status_note='Publisher topic/index page, not a reporting item',
               processed_at=CURRENT_TIMESTAMP WHERE url=?""",
            (item["canonical_url"],),
        )
        removed_items += 1
        excluded += 1
    db.commit()
    print(f"Excluded {excluded} navigation candidates; removed {removed_items} items; skipped {skipped_claimed} claimed items")


def cmd_cleanup_canonical_aliases(args: argparse.Namespace) -> None:
    """Remove metadata aliases proven to map to a fetched item by candidate ID."""
    db = connect(args.db)
    metadata_items: dict[int, int] = {}
    fetched_items: dict[int, int] = {}
    for row in db.execute("SELECT item_id,metadata_json FROM item_version WHERE metadata_json IS NOT NULL"):
        metadata = json.loads(row["metadata_json"] or "{}")
        if metadata.get("source_candidate_id") is not None:
            metadata_items[int(metadata["source_candidate_id"])] = int(row["item_id"])
        if metadata.get("discovery_candidate_id") is not None:
            fetched_items[int(metadata["discovery_candidate_id"])] = int(row["item_id"])
    removed = skipped_claimed = 0
    for candidate_id in metadata_items.keys() & fetched_items.keys():
        old_item_id = metadata_items[candidate_id]
        fetched_item_id = fetched_items[candidate_id]
        if old_item_id == fetched_item_id:
            continue
        if db.execute(
            "SELECT 1 FROM reporting_claim WHERE item_id=? LIMIT 1", (old_item_id,)
        ).fetchone():
            skipped_claimed += 1
            continue
        old_item = db.execute(
            "SELECT * FROM reporting_item WHERE id=?", (old_item_id,)
        ).fetchone()
        fetched_item = db.execute(
            "SELECT * FROM reporting_item WHERE id=?", (fetched_item_id,)
        ).fetchone()
        old_version = db.execute(
            "SELECT * FROM item_version WHERE id=?", (old_item["current_version_id"],)
        ).fetchone() if old_item else None
        fetched_version = db.execute(
            "SELECT * FROM item_version WHERE id=?", (fetched_item["current_version_id"],)
        ).fetchone() if fetched_item else None
        if old_item and fetched_item:
            db.execute(
                """UPDATE reporting_item SET
                       source_native_id=COALESCE(source_native_id,?),
                       notes=COALESCE(notes,?),
                       scope_class=CASE WHEN ?='direct' THEN 'direct' ELSE scope_class END,
                       last_seen_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (old_item["source_native_id"], old_item["notes"], old_item["scope_class"], fetched_item_id),
            )
        if old_version and fetched_version:
            merged_metadata = json.loads(fetched_version["metadata_json"] or "{}")
            old_metadata = json.loads(old_version["metadata_json"] or "{}")
            for key, value in old_metadata.items():
                if value is not None:
                    merged_metadata.setdefault(key, value)
            aliases = list(merged_metadata.get("canonical_aliases") or [])
            if old_item["canonical_url"] not in aliases:
                aliases.append(old_item["canonical_url"])
            merged_metadata["canonical_aliases"] = aliases
            db.execute(
                """UPDATE item_version SET metadata_json=?,
                       archive_url=COALESCE(archive_url,?) WHERE id=?""",
                (json_text(merged_metadata), old_version["archive_url"], fetched_version["id"]),
            )
            if old_version["content_text"] not in (None, ""):
                transferred = db.execute(
                    "SELECT id FROM item_version WHERE item_id=? AND content_hash=?",
                    (fetched_item_id, old_version["content_hash"]),
                ).fetchone()
                prefer_old = len(old_version["content_text"]) > len(fetched_version["content_text"] or "")
                if transferred:
                    transferred_id = int(transferred["id"])
                else:
                    if prefer_old:
                        db.execute(
                            "UPDATE item_version SET version_status='superseded' WHERE item_id=? AND version_status='current'",
                            (fetched_item_id,),
                        )
                    cursor = db.execute(
                        """INSERT INTO item_version(
                               item_id,source_url,archive_url,content_text,content_hash,
                               metadata_json,version_status,change_summary
                           ) VALUES(?,?,?,?,?,?,?,?)""",
                        (
                            fetched_item_id, old_version["source_url"], old_version["archive_url"],
                            old_version["content_text"], old_version["content_hash"],
                            json_text(merged_metadata), "current" if prefer_old else "superseded",
                            "preserved from canonical alias",
                        ),
                    )
                    transferred_id = int(cursor.lastrowid)
                if prefer_old:
                    db.execute(
                        "UPDATE item_version SET version_status='current',metadata_json=? WHERE id=?",
                        (json_text(merged_metadata), transferred_id),
                    )
                    db.execute(
                        "UPDATE reporting_item SET current_version_id=? WHERE id=?",
                        (transferred_id, fetched_item_id),
                    )
        db.execute("DELETE FROM reporting_fts WHERE item_id=?", (old_item_id,))
        db.execute("DELETE FROM reporting_item WHERE id=?", (old_item_id,))
        refresh_item_fts(db, fetched_item_id)
        removed += 1
    db.commit()
    print(f"Removed {removed} candidate-proven canonical aliases; skipped {skipped_claimed} claimed items")


def recover_archived_html(url: str, provider: str, timeout: int) -> tuple[bytes, str, dict] | None:
    if provider in {"auto", "wayback"}:
        captures = []
        for variant in archive_url_variants(url):
            try:
                captures.extend(wayback_captures(variant, timeout=timeout, limit=10))
            except (HTTPError, URLError, TimeoutError):
                if provider == "wayback":
                    continue
        for capture in sorted(captures, key=lambda row: row.get("timestamp", ""), reverse=True):
            try:
                result = fetch_wayback_capture(capture, timeout)
                validate_archived_html(result[0])
                return result
            except (HTTPError, URLError, TimeoutError, ValueError):
                continue
        if provider == "wayback":
            return None
    if provider in {"auto", "commoncrawl"}:
        captures = [
            capture for variant in archive_url_variants(url)
            if (capture := commoncrawl_capture(variant, timeout=timeout))
        ]
        if captures:
            result = fetch_commoncrawl_capture(
                max(captures, key=lambda row: row.get("timestamp", "")), timeout
            )
            validate_archived_html(result[0])
            return result
    return None


def _existing_item_context(db: sqlite3.Connection, canonical_url: str) -> dict:
    row = db.execute(
        """SELECT r.*,p.name publisher_name FROM reporting_item r
           LEFT JOIN publisher p ON p.id=r.publisher_id WHERE r.canonical_url=?""",
        (normalize_url(canonical_url),),
    ).fetchone()
    return dict(row) if row else {}


def _archive_ingest_record(
    db: sqlite3.Connection, original_url: str, raw: bytes, archive_url: str,
    archive_metadata: dict, *, store_text: bool, context: dict | None = None,
    discovery_method: str,
) -> tuple[int, bool, bool]:
    context = context or _existing_item_context(db, original_url)
    validate_archived_html(raw)
    parsed = parse_article_html(raw, archive_url)
    context_title = context.get("title")
    if context_title == "Untitled reporting item" or (
        context_title and re.match(r"^https?://", context_title, re.I)
    ):
        context_title = None
    if store_text and len(parsed.get("content_text") or "") < 200:
        raise ValueError("archive replay did not yield substantive article text")
    prior_access = context.get("access_status")
    archive_access = (
        "archive_only" if prior_access in {None, "unknown", "unavailable"}
        else prior_access
    )
    parsed.update({
        "canonical_url": original_url,
        "archive_url": archive_url,
        "title": context_title or parsed.get("title"),
        "publisher": context.get("publisher_name") or parsed.get("publisher") or domain_from_url(original_url),
        "published_at": context.get("published_at") or parsed.get("published_at"),
        "language": context.get("language") or parsed.get("language"),
        "scope_class": "direct" if is_direct_reporting(parsed) else (context.get("scope_class") or "direct"),
        "access_status": archive_access,
        "rights_status": "local_research" if store_text else "metadata_only",
        "independence_group": context.get("independence_group") or f"outlet:{domain_from_url(original_url)}",
    })
    if not store_text:
        parsed["content_text"] = None
    if context.get("scope_class") == "candidate" and parsed["scope_class"] != "direct":
        raise ValueError("archived item lacks direct Epstein/Maxwell reporting")
    parsed.setdefault("metadata", {}).update(archive_metadata)
    parsed["metadata"]["raw_response_hash"] = parsed.pop("raw_hash")
    return ingest_record(db, parsed, discovery_method=discovery_method)


def reconcile_candidate_statuses(db: sqlite3.Connection) -> int:
    """Mark candidates ingested when a fetched canonical item already exists.

    Metadata-only materialization deliberately leaves a candidate in the fetch
    queue, including for a later archive-recovery pass.
    """
    cursor = db.execute(
        """UPDATE discovery_candidate SET status='ingested',
               status_note='Canonical reporting item already present',
               processed_at=COALESCE(processed_at,CURRENT_TIMESTAMP)
           WHERE status<>'ingested' AND EXISTS (
               SELECT 1 FROM reporting_item i
               LEFT JOIN item_version v ON v.id=i.current_version_id
               WHERE i.canonical_url=discovery_candidate.url
                 AND COALESCE(json_extract(
                     v.metadata_json,'$.metadata_only_materialization'
                 ),0)<>1
           )"""
    )
    db.commit()
    return int(cursor.rowcount)


def cmd_reconcile_candidates(args: argparse.Namespace) -> None:
    db = connect(args.db)
    changed = reconcile_candidate_statuses(db)
    print(f"Reconciled {changed} candidate statuses to ingested")


def cmd_recover_archives(args: argparse.Namespace) -> None:
    db = connect(args.db)
    reconcile_candidate_statuses(db)
    targets: list[tuple[str, dict]] = []
    for item_id in args.item_id or []:
        row = db.execute(
            """SELECT r.*,p.name publisher_name FROM reporting_item r
               LEFT JOIN publisher p ON p.id=r.publisher_id WHERE r.id=?""",
            (item_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Reporting item #{item_id} not found")
        targets.append((row["canonical_url"], dict(row)))
    for url in args.url or []:
        targets.append((url, _existing_item_context(db, url)))
    if args.access_status:
        placeholders = ",".join("?" for _ in args.access_status)
        rows = db.execute(
            f"""SELECT r.*,p.name publisher_name FROM reporting_item r
                LEFT JOIN publisher p ON p.id=r.publisher_id
                WHERE r.access_status IN ({placeholders}) ORDER BY r.published_at DESC,r.id LIMIT ?""",
            (*args.access_status, args.limit),
        ).fetchall()
        targets.extend((row["canonical_url"], dict(row)) for row in rows)
    if args.failed_candidates:
        rows = db.execute(
            """SELECT * FROM discovery_candidate WHERE status='failed'
               ORDER BY discovered_at LIMIT ?""",
            (args.limit,),
        ).fetchall()
        targets.extend((row["url"], dict(row)) for row in rows)
    deduped: list[tuple[str, dict]] = []
    seen_urls = set()
    for url, context in targets:
        normalized = normalize_url(url)
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            deduped.append((normalized, context))
    if not deduped:
        raise ValueError("Provide --url, --item-id, --access-status, or --failed-candidates")
    deduped = deduped[:args.limit]
    run_id = begin_run(db, "archive_recovery", None, args.provider, {
        "provider": args.provider, "targets": len(deduped), "store_text": args.store_text,
        "max_consecutive_errors": args.max_consecutive_errors,
    })
    recovered = 0
    errors = []
    consecutive_errors = 0
    for url, context in deduped:
        try:
            result = recover_archived_html(url, args.provider, args.timeout)
            consecutive_errors = 0
            if not result:
                errors.append(f"{url}: no capture")
                continue
            raw, archive_url, metadata = result
            provider = metadata["archive_provider"]
            _archive_ingest_record(
                db, url, raw, archive_url, metadata, store_text=args.store_text,
                context=context, discovery_method=f"archive:{provider}",
            )
            recovered += 1
        except Exception as exc:
            if context.get("status") == "failed" and "lacks direct Epstein/Maxwell" in str(exc):
                db.execute(
                    """UPDATE discovery_candidate SET status='excluded',status_note=?,
                       processed_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (str(exc), context["id"]),
                )
                db.commit()
                continue
            errors.append(f"{url}: {exc}")
            consecutive_errors += 1
            if args.max_consecutive_errors and consecutive_errors >= args.max_consecutive_errors:
                errors.append(
                    f"Stopped after {consecutive_errors} consecutive archive-provider errors; rerun is resumable"
                )
                break
        if args.delay:
            time.sleep(args.delay)
    finish_run(db, run_id, len(deduped), recovered, "\n".join(errors[:20]) or None)
    print(f"Recovered {recovered}/{len(deduped)} reporting URLs from public archives")
    if errors:
        print(f"{len(errors)} archive lookups failed; first: {errors[0]}", file=sys.stderr)


def cmd_ingest_archive_url(args: argparse.Namespace) -> None:
    raw, final_url, _ = _fetch_bytes(
        args.archive_url, args.timeout, {"Accept": "text/html,application/xhtml+xml"}
    )
    provider = domain_from_url(final_url)
    metadata = {
        "archive_provider": provider,
        "archive_original": args.original_url,
        "manually_supplied_archive_url": args.archive_url,
    }
    db = connect(args.db)
    item_id, created, version_created = _archive_ingest_record(
        db, args.original_url, raw, final_url, metadata, store_text=args.store_text,
        discovery_method=f"archive:{provider}",
    )
    print(f"Item #{item_id}: {'created' if created else 'updated'}; archive version {'created' if version_created else 'unchanged'}")


def _item_query(db: sqlite3.Connection, where: str = "", params: tuple = (), limit: int = 50) -> list[dict]:
    sql = """
        SELECT i.*,p.name publisher,p.domain,
               GROUP_CONCAT(a.canonical_name, '; ') authors
        FROM reporting_item i
        LEFT JOIN publisher p ON p.id=i.publisher_id
        LEFT JOIN item_author ia ON ia.item_id=i.id
        LEFT JOIN author a ON a.id=ia.author_id
    """
    if where:
        sql += " WHERE " + where
    sql += " GROUP BY i.id ORDER BY COALESCE(i.published_at,i.first_seen_at) DESC LIMIT ?"
    return [dict(row) for row in db.execute(sql, params + (limit,)).fetchall()]


def cmd_search(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    try:
        rows = db.execute(
            """
            SELECT i.id,i.title,i.canonical_url,i.published_at,p.name publisher,
                   snippet(reporting_fts,4,'>>>','<<<','…',48) snippet
            FROM reporting_fts
            JOIN reporting_item i ON i.id=reporting_fts.item_id
            LEFT JOIN publisher p ON p.id=i.publisher_id
            WHERE reporting_fts MATCH ? AND (? OR i.scope_class!='background')
            ORDER BY rank LIMIT ?
            """,
            (args.query, int(args.include_background), args.limit),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    data = [dict(row) for row in rows]
    if len(data) < args.limit:
        existing_ids = {row["id"] for row in data}
        pattern = f"%{args.query}%"
        fallback = db.execute(
            """
            SELECT i.id,i.title,i.canonical_url,i.published_at,p.name publisher,
                   substr(COALESCE(v.content_text,i.abstract,i.dek,i.title),1,360) snippet
            FROM reporting_item i
            LEFT JOIN publisher p ON p.id=i.publisher_id
            LEFT JOIN item_version v ON v.id=i.current_version_id
            WHERE (? OR i.scope_class!='background') AND (
                i.title LIKE ? OR COALESCE(i.dek,'') LIKE ? OR
                COALESCE(i.abstract,'') LIKE ? OR COALESCE(v.content_text,'') LIKE ?
            )
            ORDER BY i.published_at DESC,i.id DESC LIMIT ?
            """,
            (int(args.include_background), pattern, pattern, pattern, pattern, args.limit * 2),
        ).fetchall()
        data.extend(dict(row) for row in fallback if row["id"] not in existing_ids)
        data = data[:args.limit]
    if write_output(data, args, summary=f"reporting search '{args.query}'"):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, default=str))
        return
    for row in data:
        print(f"#{row['id']} {row['published_at'] or '?'} — {row['title']} [{row['publisher'] or '?'}]")
        print(f"  {row['canonical_url']}\n  {row['snippet'] or ''}")


def cmd_latest(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    rows = _item_query(db, "" if args.include_background else "i.scope_class!='background'", (), args.limit)
    if write_output(rows, args, summary="latest reporting"):
        return
    if args.json_out:
        print(json.dumps(rows, indent=2, default=str))
        return
    for row in rows:
        print(f"#{row['id']} {row['published_at'] or '?'} — {row['title']} [{row['publisher'] or '?'}]")


def cmd_show(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    rows = _item_query(db, "i.id=?", (args.id,), 1)
    if not rows:
        raise ValueError(f"Reporting item #{args.id} not found")
    item = rows[0]
    item["versions"] = [dict(r) for r in db.execute(
        "SELECT id,retrieved_at,source_url,archive_url,content_hash,version_status,change_summary FROM item_version WHERE item_id=? ORDER BY retrieved_at",
        (args.id,),
    )]
    item["claims"] = [dict(r) for r in db.execute(
        "SELECT * FROM reporting_claim WHERE item_id=? ORDER BY id", (args.id,)
    )]
    if write_output(item, args, summary=f"reporting item #{args.id}"):
        return
    print(json.dumps(item, indent=2, default=str))


def cmd_add_claim(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    item = db.execute("SELECT current_version_id FROM reporting_item WHERE id=?", (args.item_id,)).fetchone()
    if not item:
        raise ValueError(f"Reporting item #{args.item_id} not found")
    cursor = db.execute(
        """
        INSERT INTO reporting_claim(
            item_id,version_id,claim_text,subject_text,predicate,object_text,event_date_raw,
            amount_raw,attribution,claim_kind,source_excerpt,source_locator,extracted_by,
            claim_fingerprint
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            args.item_id, item["current_version_id"], args.claim, args.subject, args.predicate,
            args.object, args.date, args.amount, args.attribution, args.kind, args.excerpt,
            args.locator, args.by,
            stable_hash(re.sub(r"\s+", " ", args.claim).strip().casefold()),
        ),
    )
    claim_id = int(cursor.lastrowid)
    refresh_claim_fts(db, claim_id)
    db.commit()
    print(f"Created reported-only claim #{claim_id}")


def cmd_import_claims(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    records = _records_from_jsonl(Path(args.path))
    imported = 0
    duplicates = 0
    errors = []
    for index, record in enumerate(records, 1):
        try:
            item_id = record.get("item_id")
            if not item_id and record.get("item_url"):
                normalized = normalize_url(record["item_url"])
                row = db.execute("SELECT id FROM reporting_item WHERE canonical_url=?", (normalized,)).fetchone()
                item_id = row["id"] if row else None
            if not item_id:
                raise ValueError("item_id or known item_url is required")
            item = db.execute("SELECT current_version_id FROM reporting_item WHERE id=?", (item_id,)).fetchone()
            if not item:
                raise ValueError(f"unknown item_id {item_id}")
            claim_text = record.get("claim_text") or record.get("claim")
            if not claim_text:
                raise ValueError("claim_text is required")
            fingerprint = stable_hash(re.sub(r"\s+", " ", claim_text).strip().casefold())
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO reporting_claim(
                    item_id,version_id,claim_text,subject_text,predicate,object_text,
                    event_date_raw,amount_raw,attribution,claim_kind,source_excerpt,
                    source_locator,extracted_by,claim_fingerprint
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id, item["current_version_id"], claim_text, record.get("subject_text"),
                    record.get("predicate"), record.get("object_text"), record.get("event_date_raw"),
                    record.get("amount_raw"), record.get("attribution"),
                    record.get("claim_kind", "paraphrase"), record.get("source_excerpt"),
                    record.get("source_locator"), record.get("extracted_by") or args.by, fingerprint,
                ),
            )
            if cursor.rowcount:
                claim_id = int(cursor.lastrowid)
                refresh_claim_fts(db, claim_id)
                imported += 1
            else:
                duplicates += 1
        except Exception as exc:
            errors.append(f"record {index}: {exc}")
    db.commit()
    print(f"Imported {imported} claims; skipped {duplicates} duplicates; {len(errors)} errors")
    if errors:
        print(errors[0], file=sys.stderr)


def cmd_review_queue(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    text_col = ",v.content_text" if args.include_text else ""
    rows = db.execute(
        f"""
        SELECT i.id item_id,i.title,i.canonical_url,i.published_at,i.scope_class,
               p.name publisher,p.domain,i.abstract{text_col}
        FROM reporting_item i LEFT JOIN publisher p ON p.id=i.publisher_id
        LEFT JOIN item_version v ON v.id=i.current_version_id
        WHERE NOT EXISTS(SELECT 1 FROM reporting_claim c WHERE c.item_id=i.id)
          AND (? OR i.scope_class!='background')
        ORDER BY CASE i.scope_class WHEN 'direct' THEN 0 WHEN 'contextual' THEN 1 ELSE 2 END,
                 COALESCE(i.published_at,i.first_seen_at) DESC LIMIT ?
        """,
        (int(args.include_background), args.limit),
    ).fetchall()
    data = [dict(row) for row in rows]
    if write_output(data, args, summary="reporting claim-extraction review queue"):
        return
    print(json.dumps(data, indent=2, default=str))


def cmd_detect_duplicates(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    rows = db.execute(
        """
        SELECT a.item_id from_id,b.item_id to_id,a.content_hash
        FROM item_version a JOIN item_version b
          ON a.content_hash=b.content_hash AND a.item_id<b.item_id
        WHERE a.content_text IS NOT NULL AND length(a.content_text)>=?
        """,
        (args.min_chars,),
    ).fetchall()
    inserted = 0
    for row in rows:
        cursor = db.execute(
            """INSERT OR IGNORE INTO item_relation(from_item_id,to_item_id,relation_type,assessment)
               VALUES(?,?,'duplicates','Exact stored-content hash; automated')""",
            (row["from_id"], row["to_id"]),
        )
        inserted += cursor.rowcount
        group = f"content:{row['content_hash']}"
        db.execute("UPDATE reporting_item SET independence_group=? WHERE id IN (?,?)", (group, row["from_id"], row["to_id"]))
    db.commit()
    print(f"Recorded {inserted} exact-content duplicate relations from {len(rows)} matching pairs")


def cmd_coverage(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    data = {
        "items_by_publisher": [dict(row) for row in db.execute(
            """SELECT p.name,p.domain,COUNT(i.id) items,MIN(i.published_at) earliest,MAX(i.published_at) latest
               FROM publisher p LEFT JOIN reporting_item i ON i.publisher_id=p.id
               GROUP BY p.id ORDER BY items DESC,p.name"""
        )],
        "items_by_language": [dict(row) for row in db.execute(
            "SELECT COALESCE(language,'unknown') language,COUNT(*) items FROM reporting_item GROUP BY language ORDER BY items DESC"
        )],
        "items_by_scope": [dict(row) for row in db.execute(
            "SELECT scope_class,COUNT(*) items FROM reporting_item GROUP BY scope_class"
        )],
        "failed_candidates_by_domain": [dict(row) for row in db.execute(
            """SELECT publisher_domain,COUNT(*) failed FROM discovery_candidate
               WHERE status='failed' GROUP BY publisher_domain ORDER BY failed DESC"""
        )],
        "discovery_runs": [dict(row) for row in db.execute(
            "SELECT * FROM discovery_run ORDER BY started_at DESC LIMIT ?", (args.runs,)
        )],
    }
    if write_output(data, args, summary="reporting corpus coverage"):
        return
    print(json.dumps(data, indent=2, default=str))


def cmd_audit_relevance(args: argparse.Namespace) -> None:
    """Conservatively demote uncurated items without direct subject evidence."""
    db = connect(args.db, create=False)
    rows = db.execute(
        """SELECT i.id,i.title,i.dek,i.abstract,i.scope_class,i.canonical_url,
                  i.discovery_method,v.content_text
           FROM reporting_item i LEFT JOIN item_version v ON v.id=i.current_version_id
           WHERE i.scope_class='direct'"""
    ).fetchall()
    demoted = 0
    for row in rows:
        if is_direct_reporting(dict(row)):
            continue
        if (row["discovery_method"] or "").startswith(("import:", "file:")):
            continue
        db.execute("UPDATE reporting_item SET scope_class='background' WHERE id=?", (row["id"],))
        db.execute(
            """UPDATE discovery_candidate SET status='excluded',
               status_note='Post-ingest relevance audit: no direct multilingual title/body evidence'
               WHERE url=?""",
            (row["canonical_url"],),
        )
        demoted += 1
    db.commit()
    print(f"Demoted {demoted}/{len(rows)} direct items to background; use --include-background to query them")


def cmd_link_evidence(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    if not db.execute("SELECT 1 FROM reporting_claim WHERE id=?", (args.claim_id,)).fetchone():
        raise ValueError(f"Claim #{args.claim_id} not found")
    db.execute(
        """
        INSERT OR REPLACE INTO claim_source(
            claim_id,source_type,source_ref,source_description,source_quote,source_page,
            independence_group,assessment,is_primary
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            args.claim_id, args.source_type, args.ref, args.description, args.quote, args.page,
            args.independence_group, args.assessment, int(args.primary),
        ),
    )
    db.commit()
    print(f"Linked {args.ref} to claim #{args.claim_id}")


def cmd_link_release(args: argparse.Namespace) -> None:
    """Link a reporting claim to a release from the primary-government sidecar."""
    try:
        from tools.government_releases import DEFAULT_DB_PATH as GOV_DB_PATH, connect as connect_government
    except ImportError:
        from government_releases import DEFAULT_DB_PATH as GOV_DB_PATH, connect as connect_government
    gov_db = connect_government(args.releases_db or GOV_DB_PATH, create=False)
    release = gov_db.execute(
        """SELECT * FROM government_release
           WHERE CAST(id AS TEXT)=? OR source_ref=? OR release_number=?""",
        (args.identifier, args.identifier, args.identifier),
    ).fetchone()
    if not release:
        raise ValueError(f"Government release not found: {args.identifier}")
    db = connect(args.db, create=False)
    if not db.execute("SELECT 1 FROM reporting_claim WHERE id=?", (args.claim_id,)).fetchone():
        raise ValueError(f"Claim #{args.claim_id} not found")
    db.execute(
        """INSERT OR REPLACE INTO claim_source(
           claim_id,source_type,source_ref,source_description,source_quote,source_page,
           independence_group,assessment,is_primary)
           VALUES(?,'primary_document',?,?,?,?,?,?,1)""",
        (args.claim_id, release["canonical_url"],
         f"{release['source_ref']} | {release['title']}", args.quote, args.page,
         release["source_ref"], args.assessment),
    )
    db.commit()
    print(f"Linked {release['source_ref']} ({release['canonical_url']}) to claim #{args.claim_id}")


def cmd_verify_claim(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    if not db.execute(
        "SELECT 1 FROM reporting_claim WHERE id=?", (args.claim_id,)
    ).fetchone():
        raise ValueError(f"Claim #{args.claim_id} not found")
    if args.status in {"primary_supported", "independently_corroborated"}:
        primary = db.execute(
            "SELECT 1 FROM claim_source WHERE claim_id=? AND is_primary=1 AND source_quote IS NOT NULL",
            (args.claim_id,),
        ).fetchone()
        if not primary:
            raise ValueError("Supported status requires a primary evidence link with --quote")
    db.execute(
        """UPDATE reporting_claim SET verification_status=?,confidence=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=?""",
        (args.status, args.confidence, args.by, utcnow(), utcnow(), args.claim_id),
    )
    db.commit()
    print(f"Claim #{args.claim_id} marked {args.status}")


def cmd_relate(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    table = "claim_relation" if args.kind == "claim" else "item_relation"
    from_col = "from_claim_id" if args.kind == "claim" else "from_item_id"
    to_col = "to_claim_id" if args.kind == "claim" else "to_item_id"
    db.execute(
        f"INSERT OR REPLACE INTO {table}({from_col},{to_col},relation_type,assessment) VALUES(?,?,?,?)",
        (args.from_id, args.to_id, args.relation, args.assessment),
    )
    db.commit()
    print(f"Recorded {args.kind} #{args.from_id} {args.relation} #{args.to_id}")


def cmd_claims(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    params: list = []
    where = []
    if args.status:
        where.append("c.verification_status=?")
        params.append(args.status)
    if args.query:
        sql = """
            SELECT c.*,i.title,i.canonical_url,p.name publisher
            FROM claim_fts
            JOIN reporting_claim c ON c.id=claim_fts.claim_id
            JOIN reporting_item i ON i.id=c.item_id
            LEFT JOIN publisher p ON p.id=i.publisher_id
            WHERE claim_fts MATCH ?
        """
        params = [args.query] + params
        if where:
            sql += " AND " + " AND ".join(where)
        sql += " ORDER BY rank LIMIT ?"
    else:
        sql = """
            SELECT c.*,i.title,i.canonical_url,p.name publisher
            FROM reporting_claim c JOIN reporting_item i ON i.id=c.item_id
            LEFT JOIN publisher p ON p.id=i.publisher_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY c.created_at DESC LIMIT ?"
    params.append(args.limit)
    data = [dict(row) for row in db.execute(sql, params).fetchall()]
    if write_output(data, args, summary="reporting claims"):
        return
    print(json.dumps(data, indent=2, default=str))


def cmd_primary_gaps(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    rows = db.execute(
        """
        SELECT c.id,c.claim_text,c.subject_text,c.attribution,c.verification_status,
               i.title,i.canonical_url,p.name publisher
        FROM reporting_claim c JOIN reporting_item i ON i.id=c.item_id
        LEFT JOIN publisher p ON p.id=i.publisher_id
        WHERE c.verification_status IN ('reported_only','unresolved','partially_supported')
          AND NOT EXISTS(SELECT 1 FROM claim_source s WHERE s.claim_id=c.id AND s.is_primary=1)
        ORDER BY c.created_at DESC LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    data = [dict(row) for row in rows]
    if write_output(data, args, summary="claims lacking primary evidence"):
        return
    print(json.dumps(data, indent=2, default=str))


def cmd_conflicts(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    rows = db.execute(
        """
        SELECT r.*,a.claim_text from_claim,b.claim_text to_claim
        FROM claim_relation r
        JOIN reporting_claim a ON a.id=r.from_claim_id
        JOIN reporting_claim b ON b.id=r.to_claim_id
        WHERE r.relation_type='contradicts' ORDER BY r.created_at DESC LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    data = [dict(row) for row in rows]
    if write_output(data, args, summary="reporting claim conflicts"):
        return
    print(json.dumps(data, indent=2, default=str))


def cmd_lineage(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    if args.kind == "claim":
        rows = db.execute(
            """
            SELECT r.*,a.claim_text from_text,b.claim_text to_text
            FROM claim_relation r JOIN reporting_claim a ON a.id=r.from_claim_id
            JOIN reporting_claim b ON b.id=r.to_claim_id
            WHERE r.from_claim_id=? OR r.to_claim_id=? ORDER BY r.created_at
            """,
            (args.id, args.id),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT r.*,a.title from_title,b.title to_title
            FROM item_relation r JOIN reporting_item a ON a.id=r.from_item_id
            JOIN reporting_item b ON b.id=r.to_item_id
            WHERE r.from_item_id=? OR r.to_item_id=? ORDER BY r.created_at
            """,
            (args.id, args.id),
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], indent=2, default=str))


def cmd_resolve_entities(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    core_path = Path(args.core_db)
    if not core_path.exists():
        raise FileNotFoundError(core_path)
    core = sqlite3.connect(str(core_path))
    core.row_factory = sqlite3.Row
    entities = core.execute(
        """
        SELECT e.id,e.name,COUNT(fe.finding_id) finding_count
        FROM entities e LEFT JOIN finding_entities fe ON fe.entity_id=e.id
        GROUP BY e.id ORDER BY finding_count DESC,e.id LIMIT ?
        """,
        (args.max_entities,),
    ).fetchall()
    aliases: dict[int, list[str]] = {row["id"]: [row["name"]] for row in entities}
    ids = list(aliases)
    for start in range(0, len(ids), 900):
        chunk = ids[start:start + 900]
        marks = ",".join("?" for _ in chunk)
        for row in core.execute(f"SELECT entity_id,alias FROM name_aliases WHERE entity_id IN ({marks})", chunk):
            aliases[row["entity_id"]].append(row["alias"])
    items = db.execute(
        """
        SELECT i.id,i.title,i.dek,i.abstract,v.content_text FROM reporting_item i
        LEFT JOIN item_version v ON v.id=i.current_version_id
        ORDER BY i.id LIMIT ?
        """,
        (args.limit,),
    ).fetchall()
    inserted = 0
    for item in items:
        haystack = " ".join(filter(None, [item["title"], item["dek"], item["abstract"], item["content_text"]])).casefold()
        for entity in entities:
            for name in aliases[entity["id"]]:
                if len(name) < 5:
                    continue
                if re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", haystack):
                    cursor = db.execute(
                        """INSERT OR IGNORE INTO item_entity(item_id,entity_id,mention_text,match_method,confidence,status) VALUES(?,?,?,'exact_alias',0.95,'candidate')""",
                        (item["id"], entity["id"], name),
                    )
                    inserted += cursor.rowcount
                    break
    db.commit()
    print(f"Added {inserted} candidate links to canonical entities; no entities were created")


def cmd_promote(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    claim = db.execute("SELECT * FROM reporting_claim WHERE id=?", (args.claim_id,)).fetchone()
    if not claim:
        raise ValueError(f"Claim #{args.claim_id} not found")
    if claim["verification_status"] not in {"primary_supported", "independently_corroborated"}:
        raise ValueError("Only primary-supported or independently-corroborated claims may be promoted")
    if not claim["reviewed_by"]:
        raise ValueError("Claim must be reviewed before promotion")
    if not claim["subject_text"]:
        raise ValueError("Claim needs subject_text before promotion")
    sources = db.execute(
        "SELECT * FROM claim_source WHERE claim_id=? AND is_primary=1", (args.claim_id,)
    ).fetchall()
    if not sources or any(not row["source_quote"] for row in sources):
        raise ValueError("Every primary evidence link needs a source quote before promotion")
    try:
        from tools.findings_tracker import add_finding
    except ImportError:
        from findings_tracker import add_finding
    refs = [row["source_ref"] for row in sources]
    source_quotes = {
        row["source_ref"]: {
            "quote": row["source_quote"], "page": row["source_page"],
            "assessment": row["assessment"],
        }
        for row in sources
    }
    source_datasets = ["reporting"]
    if any(
        "justice.gov/" in row["source_ref"] or "sec.gov/" in row["source_ref"]
        or (row["source_description"] or "").startswith(("DOJ-PR:", "SEC-PR:"))
        for row in sources
    ):
        source_datasets.append("government_releases")
    finding_id = add_finding(
        target_name=claim["subject_text"], summary=claim["claim_text"],
        finding_type=args.finding_type,
        detail=f"Promoted from attributed reporting claim #{args.claim_id}. Attribution: {claim['attribution'] or 'unspecified'}",
        evidence_ids=refs, source_datasets=source_datasets, confidence=args.confidence,
        date_of_event=claim["event_date_raw"], claim_type="paraphrase",
        source_quotes=source_quotes, profile_id="epstein",
    )
    db.execute(
        "INSERT INTO claim_promotion(claim_id,finding_id,promoted_by,primary_evidence_refs_json) VALUES(?,?,?,?)",
        (args.claim_id, finding_id, args.by, json_text(refs)),
    )
    db.commit()
    print(f"Promoted reporting claim #{args.claim_id} to finding #{finding_id}")


def cmd_stats(args: argparse.Namespace) -> None:
    db = connect(args.db, create=False)
    tables = ["reporting_item", "item_version", "reporting_claim", "claim_source", "discovery_candidate", "publisher", "author"]
    data = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    data["claim_statuses"] = {
        row[0]: row[1] for row in db.execute("SELECT verification_status,COUNT(*) FROM reporting_claim GROUP BY verification_status")
    }
    data["candidate_statuses"] = {
        row[0]: row[1] for row in db.execute("SELECT status,COUNT(*) FROM discovery_candidate GROUP BY status")
    }
    if write_output(data, args, summary="reporting corpus statistics"):
        return
    print(json.dumps(data, indent=2))


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help=f"Reporting DB (default: {DEFAULT_DB_PATH})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Epstein reporting knowledge layer")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Initialize the reporting sidecar")
    add_common(p); p.set_defaults(func=cmd_init)

    p = sub.add_parser("ingest-url", help="Fetch and ingest one public article URL")
    p.add_argument("url"); p.add_argument("--title"); p.add_argument("--publisher")
    p.add_argument("--published-at"); p.add_argument("--language"); p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--store-text", action="store_true", help="Store extracted text when rights permit")
    p.add_argument("--access-status", choices=["open","paywalled","licensed","archive_only","unavailable","unknown"], default="unknown")
    p.add_argument("--rights-status", choices=["metadata_only","local_research","redistributable","unknown"], default="metadata_only")
    p.add_argument("--item-type", choices=["article","investigation_series","newsletter","book_chapter","podcast","broadcast_transcript","blog_post","other"], default="article")
    add_common(p); p.set_defaults(func=cmd_ingest_url)

    p = sub.add_parser("import-file", help="Import JSONL, CSV, or RIS exports")
    p.add_argument("path"); p.add_argument("--source", required=True)
    p.add_argument("--access-status", choices=["open","paywalled","licensed","archive_only","unavailable","unknown"], default="licensed")
    p.add_argument("--rights-status", choices=["metadata_only","local_research","redistributable","unknown"], default="metadata_only")
    add_common(p); p.set_defaults(func=cmd_import_file)

    p = sub.add_parser("discover-file", help="Seed fetch candidates from JSONL, CSV, or RIS")
    p.add_argument("path"); p.add_argument("--source", required=True)
    add_common(p); p.set_defaults(func=cmd_discover_file)

    p = sub.add_parser("discover-gdelt", help="Discover recent URLs through verified GDELT DOC 2.0 API")
    p.add_argument("query"); p.add_argument("--limit", type=int, default=250); p.add_argument("--timespan", default="3m"); p.add_argument("--timeout", type=int, default=60)
    add_common(p); p.set_defaults(func=cmd_discover_gdelt)

    p = sub.add_parser("discover-feed", help="Discover URLs from an RSS or Atom feed")
    p.add_argument("url"); p.add_argument("--query"); p.add_argument("--timeout", type=int, default=30)
    add_common(p); p.set_defaults(func=cmd_discover_feed)

    p = sub.add_parser("discover-page", help="Discover relevant links from a verified publisher topic or series page")
    p.add_argument("url"); p.add_argument("--query", action="append")
    p.add_argument("--publisher"); p.add_argument("--language")
    p.add_argument("--link-regex", help="Accept empty-title topic cards whose URL matches this pattern")
    p.add_argument("--same-domain", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--timeout", type=int, default=30)
    add_common(p); p.set_defaults(func=cmd_discover_page)

    p = sub.add_parser("discover-repository", help="Seed candidates from reporting URLs already cited in the repository")
    p.add_argument("--config", type=Path, default=DEFAULT_SOURCE_CONFIG)
    p.add_argument("--path", action="append", help="File or directory to scan (repeatable; defaults from config)")
    add_common(p); p.set_defaults(func=cmd_discover_repository)

    p = sub.add_parser("discover-wayback", help="Discover publisher URLs through Wayback CDX urlkey filters")
    p.add_argument("--config", type=Path, default=DEFAULT_SOURCE_CONFIG)
    p.add_argument("--domain", action="append", help="Publisher domain (repeatable; defaults to configured publishers)")
    p.add_argument("--url-pattern", action="append", help="URL-slug term such as epstein or maxwell (repeatable)")
    p.add_argument("--from", dest="from_date"); p.add_argument("--to", dest="to_date")
    p.add_argument("--limit-per-domain", type=int, default=250); p.add_argument("--max-domains", type=int, default=0)
    p.add_argument("--timeout", type=int, default=15); p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--max-consecutive-errors", type=int, default=5,
                   help="Stop an unavailable archive from stalling every domain; 0 disables")
    add_common(p); p.set_defaults(func=cmd_discover_wayback)

    p = sub.add_parser("ingest-candidates", help="Fetch pending discovery candidates")
    p.add_argument("--limit", type=int, default=50); p.add_argument("--timeout", type=int, default=30); p.add_argument("--delay", type=float, default=0.5); p.add_argument("--store-text", action="store_true")
    p.add_argument("--workers", type=int, default=1, help="Concurrent network fetches; database writes remain serialized")
    p.add_argument("--access-status", choices=["open","paywalled","licensed","archive_only","unavailable","unknown"], default="unknown")
    p.add_argument("--rights-status", choices=["metadata_only","local_research","redistributable","unknown"], default="metadata_only")
    add_common(p); p.set_defaults(func=cmd_ingest_candidates)

    p = sub.add_parser("materialize-candidates", help="Create metadata-only items while retaining the fetch queue")
    p.add_argument("--status", action="append", choices=["pending","failed","ingested","excluded"])
    p.add_argument("--method"); p.add_argument("--run-id", type=int)
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--access-status", choices=["open","paywalled","licensed","archive_only","unavailable","unknown"], default="unknown")
    p.add_argument("--require-direct", action=argparse.BooleanOptionalAction, default=True)
    add_common(p); p.set_defaults(func=cmd_materialize_candidates)

    p = sub.add_parser("cleanup-navigation", help="Remove publisher pagination controls misclassified as articles")
    add_common(p); p.set_defaults(func=cmd_cleanup_navigation)

    p = sub.add_parser("cleanup-canonical-aliases", help="Remove metadata aliases proven by a shared candidate ID")
    add_common(p); p.set_defaults(func=cmd_cleanup_canonical_aliases)

    p = sub.add_parser("reconcile-candidates", help="Mark candidates ingested when their canonical item exists")
    add_common(p); p.set_defaults(func=cmd_reconcile_candidates)

    p = sub.add_parser("recover-archives", help="Recover known reporting URLs from Wayback or Common Crawl")
    p.add_argument("--url", action="append", help="Original publisher URL (repeatable)")
    p.add_argument("--item-id", action="append", type=int, help="Reporting item ID (repeatable)")
    p.add_argument("--access-status", action="append", choices=["open","paywalled","licensed","archive_only","unavailable","unknown"], help="Recover matching reporting items")
    p.add_argument("--failed-candidates", action="store_true", help="Recover candidates whose direct fetch failed")
    p.add_argument("--provider", choices=["auto","wayback","commoncrawl"], default="auto")
    p.add_argument("--limit", type=int, default=50); p.add_argument("--timeout", type=int, default=30)
    p.add_argument("--delay", type=float, default=1.0); p.add_argument("--store-text", action="store_true")
    p.add_argument("--max-consecutive-errors", type=int, default=5,
                   help="Stop an unavailable archive from stalling every URL; 0 disables")
    add_common(p); p.set_defaults(func=cmd_recover_archives)

    p = sub.add_parser("ingest-archive-url", help="Ingest a manually supplied archive.is/Wayback snapshot")
    p.add_argument("original_url", help="Canonical publisher URL")
    p.add_argument("archive_url", help="Public snapshot URL")
    p.add_argument("--timeout", type=int, default=30); p.add_argument("--store-text", action="store_true")
    add_common(p); p.set_defaults(func=cmd_ingest_archive_url)

    p = sub.add_parser("search"); p.add_argument("query"); p.add_argument("--limit", type=int, default=50); p.add_argument("--include-background", action="store_true"); add_output_args(p); add_common(p); p.set_defaults(func=cmd_search)
    p = sub.add_parser("latest"); p.add_argument("--limit", type=int, default=50); p.add_argument("--include-background", action="store_true"); add_output_args(p); add_common(p); p.set_defaults(func=cmd_latest)
    p = sub.add_parser("show"); p.add_argument("id", type=int); add_output_args(p); add_common(p); p.set_defaults(func=cmd_show)

    p = sub.add_parser("add-claim", help="Add an attributed, reported-only atomic claim")
    p.add_argument("item_id", type=int); p.add_argument("--claim", required=True); p.add_argument("--subject"); p.add_argument("--predicate"); p.add_argument("--object")
    p.add_argument("--date"); p.add_argument("--amount"); p.add_argument("--attribution"); p.add_argument("--excerpt"); p.add_argument("--locator"); p.add_argument("--by", required=True)
    p.add_argument("--kind", choices=["direct_quote","paraphrase","inference","synthesis"], default="paraphrase")
    add_common(p); p.set_defaults(func=cmd_add_claim)

    p = sub.add_parser("import-claims", help="Idempotently import atomic claims from JSONL")
    p.add_argument("path"); p.add_argument("--by", required=True); add_common(p); p.set_defaults(func=cmd_import_claims)

    p = sub.add_parser("review-queue", help="Export items that have no extracted claims")
    p.add_argument("--limit", type=int, default=100); p.add_argument("--include-text", action="store_true"); p.add_argument("--include-background", action="store_true"); add_output_args(p); add_common(p); p.set_defaults(func=cmd_review_queue)

    p = sub.add_parser("link-evidence", help="Link a claim to its source basis or primary evidence")
    p.add_argument("claim_id", type=int); p.add_argument("--ref", required=True); p.add_argument("--source-type", choices=["primary_document","named_interview","anonymous_source","other_reporting","personal_observation","analysis","unspecified"], required=True)
    p.add_argument("--description"); p.add_argument("--quote"); p.add_argument("--page"); p.add_argument("--independence-group"); p.add_argument("--assessment"); p.add_argument("--primary", action="store_true")
    add_common(p); p.set_defaults(func=cmd_link_evidence)

    p = sub.add_parser("link-release", help="Link a claim to a DOJ/SEC primary release")
    p.add_argument("claim_id", type=int); p.add_argument("identifier", help="Corpus id, source ref, or release number")
    p.add_argument("--releases-db", type=Path); p.add_argument("--quote", required=True); p.add_argument("--page")
    p.add_argument("--assessment"); add_common(p); p.set_defaults(func=cmd_link_release)

    p = sub.add_parser("verify-claim")
    p.add_argument("claim_id", type=int); p.add_argument("--status", choices=["reported_only","primary_supported","independently_corroborated","partially_supported","contradicted","superseded","retracted","unresolved"], required=True)
    p.add_argument("--confidence", choices=["unverified","low","medium","high","confirmed"], required=True); p.add_argument("--by", required=True)
    add_common(p); p.set_defaults(func=cmd_verify_claim)

    p = sub.add_parser("claims"); p.add_argument("query", nargs="?"); p.add_argument("--status"); p.add_argument("--limit", type=int, default=50); add_output_args(p); add_common(p); p.set_defaults(func=cmd_claims)
    p = sub.add_parser("primary-gaps"); p.add_argument("--limit", type=int, default=100); add_output_args(p); add_common(p); p.set_defaults(func=cmd_primary_gaps)
    p = sub.add_parser("conflicts"); p.add_argument("--limit", type=int, default=100); add_output_args(p); add_common(p); p.set_defaults(func=cmd_conflicts)

    p = sub.add_parser("relate"); p.add_argument("kind", choices=["item","claim"]); p.add_argument("from_id", type=int); p.add_argument("to_id", type=int); p.add_argument("relation"); p.add_argument("--assessment"); add_common(p); p.set_defaults(func=cmd_relate)
    p = sub.add_parser("lineage"); p.add_argument("kind", choices=["item","claim"]); p.add_argument("id", type=int); add_common(p); p.set_defaults(func=cmd_lineage)
    p = sub.add_parser("detect-duplicates", help="Record exact full-text duplicates as one independence group")
    p.add_argument("--min-chars", type=int, default=500); add_common(p); p.set_defaults(func=cmd_detect_duplicates)

    p = sub.add_parser("resolve-entities"); p.add_argument("--core-db", type=Path, default=CORE_DB_PATH); p.add_argument("--limit", type=int, default=10000); p.add_argument("--max-entities", type=int, default=5000); add_common(p); p.set_defaults(func=cmd_resolve_entities)

    p = sub.add_parser("promote", help="Promote a reviewed primary-supported claim to a finding")
    p.add_argument("claim_id", type=int); p.add_argument("--by", required=True); p.add_argument("--finding-type", default="document"); p.add_argument("--confidence", choices=["low","medium","high"], default="high"); add_common(p); p.set_defaults(func=cmd_promote)

    p = sub.add_parser("stats"); add_output_args(p); add_common(p); p.set_defaults(func=cmd_stats)
    p = sub.add_parser("coverage"); p.add_argument("--runs", type=int, default=50); add_output_args(p); add_common(p); p.set_defaults(func=cmd_coverage)
    p = sub.add_parser("audit-relevance", help="Demote direct items whose metadata does not name Epstein/Maxwell")
    add_common(p); p.set_defaults(func=cmd_audit_relevance)

    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
