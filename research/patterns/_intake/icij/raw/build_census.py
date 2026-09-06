#!/usr/bin/env python3
"""Build reproducible ICIJ census tables from saved sitemap and page pulls."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


RAW_DIR = Path(__file__).resolve().parent

CLUSTERS = {
    "C1": {
        "label": "Offshore finance, tax and hidden assets",
        "rule": (
            "Projects whose primary object is an offshore structure, tax-minimization "
            "system, private-bank secrecy, or hidden cross-border asset ownership."
        ),
        "slugs": [
            "offshore",
            "zhong-guo-chi-jin-rong-jie-mi",
            "luxembourg-leaks",
            "swiss-leaks",
            "mauritius-leaks",
            "panama-papers",
            "paradise-papers",
            "west-africa-leaks",
            "luanda-leaks",
            "pandora-papers",
            "cyprus-confidential",
            "hidden-treasures",
        ],
    },
    "C2": {
        "label": "Dirty money, corruption, kleptocracy and enablers",
        "rule": (
            "Projects centered on laundering, bribery, sanctions evasion, state capture, "
            "or professional/corporate enablers, rather than offshore ownership itself."
        ),
        "slugs": [
            "coin-laundry",
            "fincen-files",
            "bribery-division",
            "ericsson-list",
            "russia-archive",
            "swazi-secrets",
            "caspian-cabals",
            "shadow-diplomats",
        ],
    },
    "C3": {
        "label": "Corporate lobbying and regulatory capture",
        "rule": (
            "Projects centered on corporate influence over law, regulation, public-health "
            "policy, pricing, or market access."
        ),
        "slugs": [
            "big-tobacco-smuggling",
            "tobacco-underground",
            "smoke-screen",
            "cancer-calculus",
            "uber-files",
        ],
    },
    "C4": {
        "label": "Natural resources, extractives and environment",
        "rule": (
            "Projects centered on mining, fishing, forests, water, climate, or trade in "
            "natural resources and their ecological consequences."
        ),
        "slugs": [
            "fatal-extraction",
            "waterbarons",
            "global-climate-change-lobby",
            "looting-the-seas",
            "looting-the-seas-ii",
            "looting-seas-iii",
            "coltan",
            "deforestation-inc",
        ],
    },
    "C5": {
        "label": "Conflict, repression and transnational rights",
        "rule": (
            "Projects centered on war commerce, political violence, detention, surveillance, "
            "or cross-border state repression."
        ),
        "slugs": [
            "makingkilling",
            "interpols-red-flag",
            "daniel-pearl",
            "china-targets",
            "damascus-dossier",
            "china-cables",
            "solitary-voices",
        ],
    },
    "C6": {
        "label": "Health, labor and human exploitation",
        "rule": (
            "Projects centered on unsafe medical products, occupational disease, tissue "
            "supply chains, or exploitation of workers and trafficking victims."
        ),
        "slugs": [
            "dangers-dust",
            "island-widows",
            "tissue",
            "implant-files",
            "trafficking-inc",
        ],
    },
    "C7": {
        "label": "Aid, development finance and public contracting",
        "rule": (
            "Projects centered on aid programs, multilateral development finance, military "
            "assistance, privatized public services, or wartime procurement."
        ),
        "slugs": [
            "world-bank",
            "divine-intervention",
            "us-aid-latin-america",
            "collateraldamage",
            "windfalls-war",
        ],
    },
}

FAMOUS_CANON = {
    "offshore",
    "panama-papers",
    "paradise-papers",
    "pandora-papers",
    "fincen-files",
    "implant-files",
    "luanda-leaks",
}

# ICIJ launch pages recovered through the web index where the archived project
# landing page omitted its first pagination batch.
START_YEAR_OVERRIDES = {
    "paradise-papers": {
        "year": 2017,
        "source": "https://www.icij.org/investigations/paradise-papers/about-the-investigation-2/",
    },
    "implant-files": {
        "year": 2018,
        "source": "https://www.icij.org/investigations/implant-files/icij-publishes-new-investigation-the-implant-files/",
    },
    "fincen-files": {
        "year": 2020,
        "source": "https://www.icij.org/investigations/fincen-files/mining-sars-data/",
    },
}


def read_json(name: str) -> object:
    return json.loads((RAW_DIR / name).read_text(encoding="utf-8"))


def write_json(name: str, value: object) -> None:
    (RAW_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def project_slug(url: str, valid_slugs: set[str]) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "investigations" and parts[1] in valid_slugs:
        return parts[1]
    return None


def main() -> None:
    content_name = (
        "content-urls-complete.json"
        if (RAW_DIR / "content-urls-complete.json").exists()
        else "content-urls-recovered.json"
    )
    content = read_json(content_name)
    page_rows = read_json("project-page-story-dates.json")
    unclassified = read_json("projects-unclassified.json")
    awards = read_json("awards-census.json")
    assert isinstance(content, list)
    assert isinstance(page_rows, list)
    assert isinstance(unclassified, list)
    assert isinstance(awards, dict)

    page_by_slug = {str(row["slug"]): row for row in page_rows}
    top_tags_by_slug = {
        str(row["slug"]): row.get("top_story_tags", []) for row in unclassified
    }
    cluster_by_slug = {
        slug: cluster_id
        for cluster_id, cluster in CLUSTERS.items()
        for slug in cluster["slugs"]
    }
    valid_slugs = set(cluster_by_slug)
    if valid_slugs != set(page_by_slug):
        raise RuntimeError(
            f"Classification mismatch: missing={set(page_by_slug) - valid_slugs}; "
            f"extra={valid_slugs - set(page_by_slug)}"
        )

    content_by_slug: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in content:
        slug = project_slug(str(row["url"]), valid_slugs)
        if slug:
            content_by_slug[slug].append(row)

    award_entries = {
        str(row["project_slug"]): int(row["award_list_entries"])
        for row in awards["entries"]
        if row["project_slug"]
    }
    projects = []
    for slug, page in page_by_slug.items():
        rows = content_by_slug[slug]
        dated_years = {
            int(row["publication_year"])
            for row in rows
            if isinstance(row.get("publication_year"), int)
        }
        for story_date in page.get("story_dates", {}).values():
            dated_years.add(int(str(story_date)[:4]))
        override = START_YEAR_OVERRIDES.get(slug)
        if override:
            dated_years.add(int(override["year"]))
        projects.append(
            {
                "name": page["name"],
                "slug": slug,
                "url": page["url"],
                "subject": page["subject"],
                "subject_source": "ICIJ project landing page",
                "cluster": cluster_by_slug[slug],
                "distinct_project_path_items": len(rows),
                "dated_project_path_items": sum(
                    isinstance(row.get("publication_year"), int) for row in rows
                ),
                "first_year": min(dated_years) if dated_years else None,
                "last_year": max(dated_years) if dated_years else None,
                "span_start_override_source": override["source"] if override else None,
                "award_page_list_entries": award_entries.get(slug, 0),
                "famous_canon": slug in FAMOUS_CANON,
                "top_story_tags": top_tags_by_slug.get(slug, []),
            }
        )
    projects.sort(key=lambda row: (str(row["cluster"]), int(row["first_year"] or 9999), str(row["name"])))
    write_json("projects.json", projects)
    write_json("classification.json", cluster_by_slug)

    project_by_slug = {str(row["slug"]): row for row in projects}
    cluster_rows = []
    for cluster_id, cluster in CLUSTERS.items():
        rows = [project_by_slug[slug] for slug in cluster["slugs"]]
        first_years = [int(row["first_year"]) for row in rows if row["first_year"]]
        last_years = [int(row["last_year"]) for row in rows if row["last_year"]]
        cluster_rows.append(
            {
                "cluster": cluster_id,
                "label": cluster["label"],
                "rule": cluster["rule"],
                "project_count": len(rows),
                "distinct_project_path_items": sum(
                    int(row["distinct_project_path_items"]) for row in rows
                ),
                "first_year": min(first_years),
                "last_year": max(last_years),
                "project_slugs": cluster["slugs"],
            }
        )
    write_json("clusters.json", cluster_rows)

    dated_counts = Counter(
        int(row["publication_year"])
        for row in content
        if isinstance(row.get("publication_year"), int)
    )
    sources = Counter(row.get("publication_year_source") or "unresolved" for row in content)
    write_json(
        "annual-counts.json",
        {
            "counted_from": (
                "distinct URLs in ICIJ post-sitemap1..9 and article-sitemap1..5; "
                "publication years from ICIJ URL dates or ICIJ page metadata, including "
                "archived copies of the same ICIJ pages"
            ),
            "input": content_name,
            "distinct_editorial_urls": len(content),
            "dated_distinct_urls": sum(dated_counts.values()),
            "undated_distinct_urls": len(content) - sum(dated_counts.values()),
            "publication_year_sources": dict(sources),
            "per_year": {str(year): count for year, count in sorted(dated_counts.items())},
        },
    )

    canon_rows = [row for row in projects if row["famous_canon"]]
    project_items = sum(int(row["distinct_project_path_items"]) for row in projects)
    canon_items = sum(int(row["distinct_project_path_items"]) for row in canon_rows)
    all_editorial = len(content)
    write_json(
        "canon-coverage.json",
        {
            "definition": (
                "Offshore Leaks, Panama Papers, Paradise Papers, Pandora Papers, "
                "FinCEN Files, Implant Files and Luanda Leaks"
            ),
            "project_count": len(canon_rows),
            "all_named_projects": len(projects),
            "project_share_percent": round(100 * len(canon_rows) / len(projects), 1),
            "canon_distinct_project_path_items": canon_items,
            "all_distinct_project_path_items": project_items,
            "project_path_item_share_percent": round(100 * canon_items / project_items, 1),
            "project_path_item_miss_percent": round(
                100 * (project_items - canon_items) / project_items, 1
            ),
            "all_distinct_editorial_urls": all_editorial,
            "all_editorial_url_share_percent": round(100 * canon_items / all_editorial, 1),
            "all_editorial_url_miss_percent": round(
                100 * (all_editorial - canon_items) / all_editorial, 1
            ),
            "project_slugs": sorted(FAMOUS_CANON),
        },
    )

    print(
        json.dumps(
            {
                "input": content_name,
                "projects": len(projects),
                "project_items": project_items,
                "editorial_urls": all_editorial,
                "dated": sum(dated_counts.values()),
                "clusters": len(cluster_rows),
                "canon_items": canon_items,
            }
        )
    )


if __name__ == "__main__":
    main()
