#!/usr/bin/env python3
"""Recover ICIJ project-page story dates from Internet Archive snapshots.

The URL backbone remains ICIJ's current sitemaps. Wayback is used only as a
transport fallback after ICIJ's CloudFront rate-limited the bulk metadata pass.
"""

from __future__ import annotations

import asyncio
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


RAW_DIR = Path(__file__).resolve().parent
CDX = "https://web.archive.org/cdx/search/cdx"


def read_json(name: str) -> object:
    return json.loads((RAW_DIR / name).read_text(encoding="utf-8"))


def write_json(name: str, value: object) -> None:
    (RAW_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_url(url: str) -> str:
    parsed = urlparse(html.unescape(url))
    path = re.sub(r"/+", "/", parsed.path)
    if path != "/" and not path.endswith("/"):
        path += "/"
    return f"https://www.icij.org{path}"


async def get_json(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    params: list[tuple[str, str]],
) -> object:
    async with semaphore:
        for attempt in range(4):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                if attempt == 3:
                    raise RuntimeError(f"JSON request failed: {response.url}: {exc}") from exc
                await asyncio.sleep(0.6 * (attempt + 1))
    raise AssertionError("unreachable")


async def get_text(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> str:
    async with semaphore:
        for attempt in range(4):
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                if attempt == 3:
                    raise RuntimeError(f"HTML request failed: {url}: {exc}") from exc
                await asyncio.sleep(0.7 * (attempt + 1))
    raise AssertionError("unreachable")


def extract_project_page(
    project_url: str,
    text: str,
) -> dict[str, object]:
    soup = BeautifulSoup(text, "lxml")
    h1 = soup.find("h1")
    name = h1.get_text(" ", strip=True) if h1 else None
    description = None
    if h1:
        for sibling in h1.find_all_next(limit=5):
            if sibling.name == "p" and sibling.get_text(" ", strip=True):
                description = sibling.get_text(" ", strip=True)
                break
    if not description:
        meta = soup.find("meta", property="og:description")
        description = meta.get("content", "").strip() if meta else None

    base = normalize_url(project_url)
    story_dates: dict[str, str] = {}
    for time_node in soup.find_all("time"):
        date_value = (time_node.get("datetime") or time_node.get_text(" ", strip=True)).strip()
        if not date_value:
            continue
        current = time_node
        candidate = None
        for _ in range(8):
            current = current.parent
            if current is None:
                break
            for anchor in current.find_all("a", href=True):
                href = normalize_url(anchor["href"])
                if href.startswith(base) and href != base:
                    candidate = href
                    break
            if candidate:
                break
        if candidate and candidate not in story_dates:
            try:
                parsed = datetime.strptime(date_value, "%b %d, %Y")
                story_dates[candidate] = parsed.date().isoformat()
            except ValueError:
                match = re.match(r"(\d{4}-\d{2}-\d{2})", date_value)
                if match:
                    story_dates[candidate] = match.group(1)

    return {
        "name": name,
        "subject": description,
        "story_dates": story_dates,
    }


async def main() -> None:
    projects = read_json("projects-unclassified.json")
    assert isinstance(projects, list)
    headers = {
        "User-Agent": "Ithildin empirical corpus census (public archival research)",
        "Accept-Encoding": "gzip, deflate",
    }
    timeout = httpx.Timeout(45.0, connect=20.0)
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=6)
    semaphore = asyncio.Semaphore(6)
    async with httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        cdx_tasks = []
        for project in projects:
            cdx_tasks.append(
                get_json(
                    client,
                    semaphore,
                    CDX,
                    [
                        ("url", str(project["url"])),
                        ("output", "json"),
                        ("filter", "statuscode:200"),
                        ("filter", "mimetype:text/html"),
                        ("fl", "timestamp,original,digest"),
                        ("limit", "-1"),
                    ],
                )
            )
        cdx_results = await asyncio.gather(*cdx_tasks, return_exceptions=True)
        captures = []
        for project, result in zip(projects, cdx_results, strict=True):
            if isinstance(result, Exception) or not isinstance(result, list) or len(result) < 2:
                captures.append(
                    {
                        "slug": project["slug"],
                        "url": project["url"],
                        "timestamp": None,
                        "capture_url": None,
                        "error": str(result) if isinstance(result, Exception) else "no capture",
                    }
                )
                continue
            rows = result[1:]
            latest = max(rows, key=lambda row: row[0])
            timestamp, original, digest = latest
            capture_url = f"https://web.archive.org/web/{timestamp}id_/{project['url']}"
            captures.append(
                {
                    "slug": project["slug"],
                    "url": project["url"],
                    "timestamp": timestamp,
                    "original": original,
                    "digest": digest,
                    "capture_url": capture_url,
                }
            )
        write_json("project-page-captures.json", captures)

        html_tasks = [
            get_text(client, semaphore, str(capture["capture_url"]))
            for capture in captures
            if capture.get("capture_url")
        ]
        html_results = await asyncio.gather(*html_tasks, return_exceptions=True)

    result_iter = iter(html_results)
    page_results = []
    date_by_url: dict[str, dict[str, str]] = defaultdict(dict)
    for capture in captures:
        if not capture.get("capture_url"):
            page_results.append({**capture, "name": None, "subject": None, "story_dates": {}})
            continue
        result = next(result_iter)
        if isinstance(result, Exception):
            page_results.append(
                {
                    **capture,
                    "name": None,
                    "subject": None,
                    "story_dates": {},
                    "fetch_error": str(result),
                }
            )
            continue
        extracted = extract_project_page(str(capture["url"]), result)
        page_results.append({**capture, **extracted})
        for url, date_value in extracted["story_dates"].items():
            date_by_url[url][str(capture["slug"])] = date_value

    write_json("project-page-story-dates.json", page_results)

    content = read_json("content-urls.json")
    assert isinstance(content, list)
    by_url: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in content:
        by_url[normalize_url(str(row["url"]))].append(row)
    duplicates = [
        {
            "url": url,
            "occurrences": len(rows),
            "sitemaps": [row["sitemap"] for row in rows],
            "content_types": [row["content_type"] for row in rows],
        }
        for url, rows in sorted(by_url.items())
        if len(rows) > 1
    ]
    write_json("duplicate-sitemap-urls.json", duplicates)

    unique_rows = []
    for url, rows in sorted(by_url.items()):
        row = dict(rows[0])
        row["sitemap_memberships"] = [item["sitemap"] for item in rows]
        row["content_type_memberships"] = sorted(
            {str(item["content_type"]) for item in rows}
        )
        year = row.get("publication_year")
        source = "direct_page_metadata" if year else None
        if not year:
            match = re.search(r"/(?:inside-icij|news)/(\d{4})/\d{2}/", url)
            if match:
                year = int(match.group(1))
                source = "icij_url_year_month"
        if not year:
            match = re.search(r"/investigations/(\d{4})/\d{2}/", url)
            if match:
                year = int(match.group(1))
                source = "icij_url_year_month"
        project_dates = date_by_url.get(url, {})
        if not year and project_dates:
            date_value = sorted(project_dates.values())[0]
            year = int(date_value[:4])
            source = "icij_project_page_date_via_wayback"
            row["published"] = date_value
        if not year:
            match = re.search(r"/(\d{8})[-_/]", url)
            if match:
                year = int(match.group(1)[:4])
                source = "icij_dated_slug"
        row["publication_year"] = year
        row["publication_year_source"] = source
        row["project_page_dates"] = project_dates
        unique_rows.append(row)

    source_counts = Counter(row["publication_year_source"] or "unresolved" for row in unique_rows)
    year_counts = Counter(
        int(row["publication_year"])
        for row in unique_rows
        if isinstance(row.get("publication_year"), int)
    )
    write_json("content-urls-recovered.json", unique_rows)
    write_json(
        "year-counts-recovered.json",
        {
            "counted_from": (
                "distinct URLs in ICIJ post/article sitemaps; publication years from direct "
                "ICIJ page metadata, explicit ICIJ URL years, or dated ICIJ project cards "
                "retrieved via Internet Archive"
            ),
            "sitemap_entries": len(content),
            "distinct_editorial_urls": len(unique_rows),
            "duplicate_entries_removed": len(content) - len(unique_rows),
            "dated_distinct_urls": sum(year_counts.values()),
            "undated_distinct_urls": len(unique_rows) - sum(year_counts.values()),
            "source_counts": dict(source_counts),
            "per_year": {str(year): count for year, count in sorted(year_counts.items())},
        },
    )
    print(
        json.dumps(
            {
                "project_pages": len(page_results),
                "project_pages_with_stories": sum(
                    bool(row["story_dates"]) for row in page_results
                ),
                "dated_distinct_urls": sum(year_counts.values()),
                "undated_distinct_urls": len(unique_rows) - sum(year_counts.values()),
                "source_counts": source_counts,
            },
            default=dict,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
