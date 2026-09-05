#!/usr/bin/env python3
"""Collect the ICIJ-owned project and editorial sitemap census.

All network sources are public ICIJ pages. All writes stay beside this script.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


RAW_DIR = Path(__file__).resolve().parent
BASE = "https://www.icij.org"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
HEAD_RE = re.compile(rb"</head\s*>", re.I)


def write_text(name: str, text: str) -> None:
    (RAW_DIR / name).write_text(text, encoding="utf-8")


def write_json(name: str, value: object) -> None:
    (RAW_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sitemap_rows(xml_text: str) -> list[dict[str, str | None]]:
    root = ET.fromstring(xml_text)
    return [
        {
            "url": node.findtext("sm:loc", namespaces=SITEMAP_NS),
            "lastmod": node.findtext("sm:lastmod", namespaces=SITEMAP_NS),
        }
        for node in root.findall("sm:url", SITEMAP_NS)
    ]


def sitemap_children(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [
        node.findtext("sm:loc", namespaces=SITEMAP_NS)
        for node in root.findall("sm:sitemap", SITEMAP_NS)
        if node.findtext("sm:loc", namespaces=SITEMAP_NS)
    ]


def meta_value(text: str, key: str, *, attr: str = "property") -> str | None:
    patterns = [
        rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+{attr}=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    return None


def all_meta_values(text: str, key: str, *, attr: str = "property") -> list[str]:
    patterns = [
        rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+{attr}=["\']{re.escape(key)}["\']',
    ]
    values: list[str] = []
    for pattern in patterns:
        values.extend(html.unescape(item).strip() for item in re.findall(pattern, text, re.I))
    return list(dict.fromkeys(value for value in values if value))


async def fetch_text(client: httpx.AsyncClient, url: str, retries: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries + 1} attempts: {url}: {last_error}")


async def fetch_head(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
) -> dict[str, object]:
    last_error: Exception | None = None
    async with semaphore:
        for attempt in range(3):
            try:
                data = bytearray()
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if HEAD_RE.search(data) or len(data) >= 350_000:
                            break
                text = bytes(data).decode("utf-8", errors="replace")
                published = meta_value(text, "article:published_time")
                if not published:
                    match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', text)
                    published = html.unescape(match.group(1)) if match else None
                title = meta_value(text, "og:title")
                description = meta_value(text, "og:description")
                tags = all_meta_values(text, "article:tag")
                return {
                    "url": url,
                    "status": response.status_code,
                    "published": published,
                    "title": title,
                    "description": description,
                    "tags": tags,
                }
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.4 * (attempt + 1))
        return {
            "url": url,
            "status": None,
            "published": None,
            "title": None,
            "description": None,
            "tags": [],
            "error": str(last_error),
        }


def year_of(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"(\d{4})", value)
    return int(match.group(1)) if match else None


def project_slug(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "investigations":
        return parts[1]
    return None


async def main() -> None:
    headers = {
        "User-Agent": "Ithildin empirical corpus census (research; contact via repository owner)",
        "Accept": "text/html,application/xml,application/xhtml+xml",
    }
    timeout = httpx.Timeout(30.0, connect=15.0)
    limits = httpx.Limits(max_connections=24, max_keepalive_connections=18)
    async with httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        sitemap_index = await fetch_text(client, f"{BASE}/sitemap.xml")
        write_text("sitemap.xml", sitemap_index)
        child_urls = sitemap_children(sitemap_index)
        selected = [
            url
            for url in child_urls
            if re.search(r"/(?:post|article|project)-sitemap\d*\.xml$", url)
        ]
        child_texts = await asyncio.gather(*(fetch_text(client, url) for url in selected))
        sitemap_manifest = []
        editorial_rows: list[dict[str, object]] = []
        project_rows: list[dict[str, object]] = []
        for url, text in zip(selected, child_texts, strict=True):
            filename = urlparse(url).path.rsplit("/", 1)[-1]
            write_text(filename, text)
            rows = sitemap_rows(text)
            kind = filename.split("-sitemap", 1)[0]
            sitemap_manifest.append({"url": url, "file": filename, "kind": kind, "count": len(rows)})
            for row in rows:
                row["sitemap"] = filename
                row["content_type"] = kind
                if kind == "project":
                    project_rows.append(row)
                else:
                    editorial_rows.append(row)
        write_json("sitemap-manifest.json", sitemap_manifest)

        archive_urls = [f"{BASE}/investigations/"] + [
            f"{BASE}/category/investigations/page/{page}/" for page in range(2, 11)
        ]
        archive_texts = await asyncio.gather(*(fetch_text(client, url) for url in archive_urls))
        archive_pages = []
        for page_number, (url, text) in enumerate(
            zip(archive_urls, archive_texts, strict=True), start=1
        ):
            soup = BeautifulSoup(text, "lxml")
            main_node = soup.find("main")
            names = [
                node.get_text(" ", strip=True)
                for node in soup.select(".archive-project-list__item h2 a")
            ]
            project_links = [
                node.get("href") for node in soup.select(".archive-project-list__item h2 a")
            ]
            archive_pages.append(
                {
                    "page": page_number,
                    "url": url,
                    "canonical": (
                        soup.find("link", rel="canonical").get("href")
                        if soup.find("link", rel="canonical")
                        else None
                    ),
                    "prev": (
                        soup.find("link", rel="prev").get("href")
                        if soup.find("link", rel="prev")
                        else None
                    ),
                    "next": (
                        soup.find("link", rel="next").get("href")
                        if soup.find("link", rel="next")
                        else None
                    ),
                    "card_count": len(names),
                    "project_names": names,
                    "project_urls": project_links,
                    "main_sha256": hashlib.sha256(
                        str(main_node).encode("utf-8")
                    ).hexdigest(),
                }
            )
        write_json("archive-pagination.json", archive_pages)

        semaphore = asyncio.Semaphore(18)
        head_rows = await asyncio.gather(
            *(fetch_head(client, semaphore, str(row["url"])) for row in editorial_rows)
        )
        sitemap_by_url = {str(row["url"]): row for row in editorial_rows}
        content = []
        for item in head_rows:
            row = sitemap_by_url[str(item["url"])]
            content.append(
                {
                    **row,
                    **item,
                    "project_slug": project_slug(str(item["url"])),
                    "publication_year": year_of(item.get("published")),
                }
            )
        content.sort(key=lambda row: (str(row.get("published") or ""), str(row["url"])))
        write_json("content-urls.json", content)

        project_heads = await asyncio.gather(
            *(fetch_head(client, semaphore, str(row["url"])) for row in project_rows)
        )
        project_sitemap_by_url = {str(row["url"]): row for row in project_rows}
        content_by_project: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in content:
            if row["project_slug"]:
                content_by_project[str(row["project_slug"])].append(row)
        projects = []
        for head in project_heads:
            row = project_sitemap_by_url[str(head["url"])]
            slug = project_slug(str(head["url"]))
            stories = content_by_project.get(slug or "", [])
            dated = sorted(
                str(item["published"]) for item in stories if item.get("published")
            )
            tags = Counter(
                tag for item in stories for tag in item.get("tags", []) if isinstance(tag, str)
            )
            title = str(head.get("title") or "").removesuffix(" - ICIJ").strip()
            projects.append(
                {
                    **row,
                    **head,
                    "slug": slug,
                    "name": title,
                    "subject": head.get("description"),
                    "url_path_story_count": len(stories),
                    "first_story_date": dated[0] if dated else None,
                    "last_story_date": dated[-1] if dated else None,
                    "top_story_tags": [
                        {"tag": tag, "count": count} for tag, count in tags.most_common(12)
                    ],
                }
            )
        projects.sort(key=lambda row: str(row.get("published") or ""), reverse=True)
        write_json("projects-unclassified.json", projects)

        year_counts = Counter(
            int(row["publication_year"])
            for row in content
            if isinstance(row.get("publication_year"), int)
        )
        type_year_counts: dict[str, Counter[int]] = defaultdict(Counter)
        for row in content:
            if isinstance(row.get("publication_year"), int):
                type_year_counts[str(row["content_type"])][int(row["publication_year"])] += 1
        write_json(
            "year-counts.json",
            {
                "counted_from": "article- and post-sitemap URLs, publication year read from each page's article:published_time/datePublished metadata",
                "total_sitemap_entries": len(content),
                "dated_entries": sum(year_counts.values()),
                "undated_entries": len(content) - sum(year_counts.values()),
                "all_editorial_types": {str(year): count for year, count in sorted(year_counts.items())},
                "by_content_type": {
                    kind: {str(year): count for year, count in sorted(counts.items())}
                    for kind, counts in sorted(type_year_counts.items())
                },
            },
        )

        official_slugs = {str(row["slug"]) for row in projects}
        path_slugs = Counter(
            str(row["project_slug"]) for row in content if row.get("project_slug")
        )
        write_json(
            "investigation-path-slugs.json",
            {
                "official_project_slugs": sorted(official_slugs),
                "all_investigation_path_slugs": [
                    {"slug": slug, "count": count}
                    for slug, count in sorted(path_slugs.items())
                ],
                "path_slugs_without_project_sitemap_landing": [
                    {"slug": slug, "count": count}
                    for slug, count in sorted(path_slugs.items())
                    if slug not in official_slugs
                ],
                "official_projects_without_child_story_url": sorted(
                    official_slugs - path_slugs.keys()
                ),
            },
        )

        awards_html = await fetch_text(client, f"{BASE}/about/awards/")
        awards_soup = BeautifulSoup(awards_html, "lxml")
        awards_main = awards_soup.find("main") or awards_soup
        award_sections = []
        for heading in awards_main.find_all("h2"):
            name = heading.get_text(" ", strip=True)
            items = []
            node = heading.find_next_sibling()
            while node and getattr(node, "name", None) != "h2":
                if getattr(node, "name", None) in {"ul", "ol"}:
                    for li in node.find_all("li", recursive=False):
                        items.append(
                            {
                                "text": li.get_text(" ", strip=True),
                                "links": [
                                    {"text": a.get_text(" ", strip=True), "url": a.get("href")}
                                    for a in li.find_all("a")
                                ],
                            }
                        )
                node = node.find_next_sibling()
            if items:
                award_sections.append(
                    {"project": name, "award_count": len(items), "awards": items}
                )
        write_json("awards.json", award_sections)

        data_html = await fetch_text(client, f"{BASE}/category/category-data/")
        data_soup = BeautifulSoup(data_html, "lxml")
        data_items = [
            {"title": a.get_text(" ", strip=True), "url": a.get("href")}
            for a in data_soup.select("h2.article-title__title a")
        ]
        write_json("data-category.json", data_items)

    write_json(
        "collection-metadata.json",
        {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "base": BASE,
            "project_count": len(projects),
            "editorial_sitemap_entries": len(content),
            "archive_pages_probed": len(archive_pages),
            "award_project_sections": len(award_sections),
            "data_category_items": len(data_items),
        },
    )
    print(
        json.dumps(
            {
                "projects": len(projects),
                "editorial_entries": len(content),
                "dated": sum(1 for row in content if row.get("publication_year")),
                "failed": sum(1 for row in content if row.get("status") is None),
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
