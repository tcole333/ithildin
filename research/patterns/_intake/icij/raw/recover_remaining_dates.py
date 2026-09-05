#!/usr/bin/env python3
"""Recover publication dates for ICIJ sitemap URLs still lacking a year."""

from __future__ import annotations

import asyncio
import html
import json
import re
from collections import Counter
from pathlib import Path

import httpx


RAW_DIR = Path(__file__).resolve().parent
AVAILABLE = "https://archive.org/wayback/available"
HEAD_END = re.compile(rb"</head\s*>", re.I)


def read_json(name: str) -> object:
    return json.loads((RAW_DIR / name).read_text(encoding="utf-8"))


def write_json(name: str, value: object) -> None:
    (RAW_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


async def cdx_lookup(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> dict[str, object]:
    params = {"url": url}
    async with semaphore:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = await client.get(AVAILABLE, params=params)
                response.raise_for_status()
                result = response.json()
                closest = result.get("archived_snapshots", {}).get("closest", {})
                if not closest.get("available") or closest.get("status") != "200":
                    return {"url": url, "timestamp": None, "capture_url": None}
                timestamp = closest["timestamp"]
                return {
                    "url": url,
                    "timestamp": timestamp,
                    "capture_url": f"https://web.archive.org/web/{timestamp}id_/{url}",
                }
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(0.7 * (attempt + 1))
        return {
            "url": url,
            "timestamp": None,
            "capture_url": None,
            "error": str(last_error),
        }


async def fetch_head(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    capture: dict[str, object],
) -> dict[str, object]:
    capture_url = capture.get("capture_url")
    if not capture_url:
        return {**capture, "published": None}
    async with semaphore:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                data = bytearray()
                async with client.stream("GET", str(capture_url)) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if HEAD_END.search(data) or len(data) >= 400_000:
                            break
                text = bytes(data).decode("utf-8", errors="replace")
                patterns = [
                    r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
                    r'"datePublished"\s*:\s*"([^"]+)"',
                ]
                published = None
                for pattern in patterns:
                    match = re.search(pattern, text, re.I)
                    if match:
                        published = html.unescape(match.group(1)).strip()
                        break
                return {**capture, "published": published, "status": response.status_code}
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(0.8 * (attempt + 1))
        return {**capture, "published": None, "fetch_error": str(last_error)}


async def main() -> None:
    rows = read_json("content-urls-recovered.json")
    assert isinstance(rows, list)
    unresolved = [row for row in rows if not row.get("publication_year")]
    headers = {
        "User-Agent": "Ithildin empirical corpus census (public archival research)",
        "Accept-Encoding": "gzip, deflate",
    }
    timeout = httpx.Timeout(45.0, connect=20.0)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=8)
    replay_semaphore = asyncio.Semaphore(8)
    async with httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        # Wayback's `2id_` selector redirects to the most recent raw capture.
        # This avoids a separate CDX/availability query for every URL.
        captures = [
            {
                "url": str(row["url"]),
                "timestamp": "latest",
                "capture_url": (
                    f"https://web.archive.org/web/2id_/{str(row['url'])}"
                ),
            }
            for row in unresolved
        ]
        write_json("unresolved-page-captures.json", captures)
        recovered = await asyncio.gather(
            *(fetch_head(client, replay_semaphore, capture) for capture in captures)
        )
    write_json("unresolved-page-metadata.json", recovered)

    recovered_by_url = {str(row["url"]): row for row in recovered}
    complete = []
    for row in rows:
        item = dict(row)
        if not item.get("publication_year"):
            archived = recovered_by_url.get(str(item["url"]), {})
            published = archived.get("published")
            if isinstance(published, str):
                match = re.match(r"(\d{4})", published)
                if match:
                    item["publication_year"] = int(match.group(1))
                    item["publication_year_source"] = "icij_page_metadata_via_wayback"
                    item["published"] = published
                    item["wayback_capture"] = archived.get("capture_url")
        complete.append(item)

    year_counts = Counter(
        int(row["publication_year"])
        for row in complete
        if isinstance(row.get("publication_year"), int)
    )
    source_counts = Counter(row.get("publication_year_source") or "unresolved" for row in complete)
    write_json("content-urls-complete.json", complete)
    write_json(
        "year-counts-complete.json",
        {
            "counted_from": (
                "distinct URLs in ICIJ's post/article sitemaps; year read from direct ICIJ "
                "metadata, explicit ICIJ URL year, ICIJ project-card dates, or archived "
                "copies of the same ICIJ page metadata"
            ),
            "distinct_editorial_urls": len(complete),
            "dated_distinct_urls": sum(year_counts.values()),
            "undated_distinct_urls": len(complete) - sum(year_counts.values()),
            "source_counts": dict(source_counts),
            "per_year": {str(year): count for year, count in sorted(year_counts.items())},
        },
    )
    print(
        json.dumps(
            {
                "attempted": len(unresolved),
                "captures": sum(bool(row.get("capture_url")) for row in recovered),
                "recovered": sum(bool(row.get("published")) for row in recovered),
                "undated": len(complete) - sum(year_counts.values()),
                "source_counts": source_counts,
            },
            default=dict,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
