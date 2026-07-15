#!/usr/bin/env python3
"""Build a read-only, stratified claim-extraction queue.

Run from the repository root:

  .venv/bin/python /tmp/osint-nEX5pEev/build_claims_queue.py \
    --db datasets/epstein_reporting.db \
    --sql /tmp/osint-nEX5pEev/claims_queue.sql \
    --output /tmp/osint-nEX5pEev/claims-queue.csv

The SQL produces an intrinsic evidence/reporting score and exact-content leader
set.  This script adds deterministic topical, era, language, publisher, and
independence-group diversity so 2025-26 outlet volume cannot swamp the queue.
It never opens the database writable.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


TOPICS: tuple[tuple[str, str, int], ...] = (
    ("banks_trusts_usvi", "topic_banks", 32),
    ("wexner_black", "topic_wexner_black", 24),
    ("maxwell", "topic_maxwell", 28),
    ("political_intelligence", "topic_politics_intel", 30),
    ("science_philanthropy", "topic_science_philanthropy", 24),
    ("properties", "topic_properties", 22),
    ("staff_operations", "topic_staff_operations", 24),
)
TOPIC_QUOTAS = {name: quota for name, _field, quota in TOPICS}
OTHER_CORE_QUOTA = 16
NON_ENGLISH_TARGET = 60
BROADCAST_CAP = 70

TOPIC_TITLE_PATTERNS = {
    "banks_trusts_usvi": re.compile(
        r"j\.?p\.?\s*morgan|deutsche|fidelity|bank|trust|usvi|virgin islands|"
        r"financial|money|account|tax|estate|indyke|kahn",
        re.I,
    ),
    "wexner_black": re.compile(
        r"wexner|leon black|apollo|dechert|l brands|limited brands|victoria.?s secret",
        re.I,
    ),
    "maxwell": re.compile(r"ghislaine|maxwell", re.I),
    "political_intelligence": re.compile(
        r"trump|clinton|prince andrew|barak|bannon|acosta|dershowitz|mossad|"
        r"intelligence|carbyne|congress|parliament|politic|qatar|saudi|israel",
        re.I,
    ),
    "science_philanthropy": re.compile(
        r"scient|harvard|\bmit\b|university|academic|philanthrop|foundation|"
        r"donation|bill gates|summers|nikolic|professor|research",
        re.I,
    ),
    "properties": re.compile(
        r"island|mansion|ranch|property|properties|real estate|home|house|"
        r"residence|palm beach|little st\.? james|zorro|townhouse|apartment",
        re.I,
    ),
    "staff_operations": re.compile(
        r"staff|assistant|employee|pilot|butler|recruiter|scheduler|household|"
        r"indyke|kahn|groff|kellen|marcinkova|shuliak|galbraith|co-conspirator",
        re.I,
    ),
    "legal_accountability": re.compile(
        r"plea|prosecution|conviction|trial|lawsuit|settlement|victim|survivor|"
        r"sentence|non-prosecution",
        re.I,
    ),
}

# Desired composition, used as a decreasing bonus rather than a brittle hard
# quota.  Caps below are the safety rail against recent-volume domination.
ERA_TARGETS = {
    "pre_2015": 24,
    "2015_2018": 16,
    "2019": 40,
    "2020_2024": 55,
    "2025": 35,
    "2026_plus": 25,
    "undated": 5,
}
ERA_CAPS = dict(ERA_TARGETS)

INVESTIGATIVE_OUTLETS = {
    "Miami Herald",
    "Palm Beach Post",
    "ICIJ",
    "OCCRP",
    "ProPublica",
    "The Intercept",
    "Drop Site News",
    "The Smoking Gun",
}

STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "how", "in", "is",
    "it", "new", "of", "on", "or", "that", "the", "this", "to", "was", "were",
    "with", "jeffrey", "epstein", "ghislaine", "maxwell", "files", "documents",
}


@lru_cache(maxsize=4096)
def compile_regex(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I | re.S)


def sqlite_regexp(pattern: str | None, value: str | None) -> int:
    if pattern is None or value is None:
        return 0
    try:
        return int(compile_regex(pattern).search(value) is not None)
    except re.error as exc:
        raise sqlite3.OperationalError(f"invalid REGEXP {pattern!r}: {exc}") from exc


def title_signature(title: str) -> tuple[str, frozenset[str]]:
    folded = unicodedata.normalize("NFKD", title.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    tokens = [t for t in re.findall(r"[a-z0-9]{2,}", folded) if t not in STOPWORDS]
    return " ".join(tokens), frozenset(tokens)


def title_cluster_key(candidate: dict[str, Any]) -> tuple[str, tuple[str, ...]] | None:
    _norm, tokens = candidate["_title_signature"]
    if len(tokens) < 3:
        return None
    date = (candidate.get("published_at") or "")[:10]
    # Exact normalized token sets catch conspicuous same-headline rewrites in
    # O(1).  More aggressive semantic rewrite clustering belongs in lineage
    # review; doing pairwise fuzzy comparison here makes reruns quadratic.
    return date, tuple(sorted(tokens))


def topics_for(candidate: dict[str, Any]) -> list[str]:
    return [name for name, field, _quota in TOPICS if int(candidate[field] or 0)]


def publisher_cap(candidate: dict[str, Any]) -> int:
    if candidate["publisher"] in INVESTIGATIVE_OUTLETS:
        return 18
    kind = candidate["publisher_type"]
    if kind in {"secondary_compromised", "secondary_blog"}:
        return 3
    if kind == "wire_service":
        return 6
    if kind == "broadcast":
        return 6
    if kind in {"unknown"}:
        return 5
    return 12


def candidate_selection_score(
    candidate: dict[str, Any],
    topic_counts: Counter[str],
    era_counts: Counter[str],
    publisher_counts: Counter[str],
    group_counts: Counter[str],
    non_english_count: int,
) -> float:
    topic_names = candidate["_topics"]
    topic_need_values: list[float] = []
    for name, _field, quota in TOPICS:
        if name not in topic_names:
            continue
        need = max(0.0, (quota - topic_counts[name]) / quota)
        title_affinity = 1.0 if TOPIC_TITLE_PATTERNS[name].search(candidate["title"]) else 0.0
        topic_need_values.append(30.0 * need + 8.0 * title_affinity)
    if topic_need_values:
        topic_bonus = max(topic_need_values)
    else:
        other_need = max(
            0.0,
            (OTHER_CORE_QUOTA - topic_counts["other_core"]) / OTHER_CORE_QUOTA,
        )
        topic_bonus = 12.0 * other_need

    era = candidate["era_bucket"]
    era_target = ERA_TARGETS[era]
    era_need = max(0.0, (era_target - era_counts[era]) / max(era_target, 1))
    era_bonus = 18.0 * era_need

    language_bonus = (
        6.0
        if candidate["language"] != "en" and non_english_count < NON_ENGLISH_TARGET
        else 0.0
    )
    publisher_penalty = 4.0 * publisher_counts[candidate["publisher"]]
    group_seen = group_counts[candidate["independence_group"]]
    group_adjustment = 5.0 if group_seen == 0 else -3.0 * group_seen

    return (
        float(candidate["base_score"])
        + topic_bonus
        + era_bonus
        + language_bonus
        + group_adjustment
        - publisher_penalty
    )


def choose_primary_topic(candidate: dict[str, Any], counts: Counter[str]) -> str:
    possibilities: list[tuple[float, str]] = []
    for name in candidate["_topics"]:
        quota = TOPIC_QUOTAS[name]
        if counts[name] >= quota:
            continue
        remaining_ratio = (quota - counts[name]) / quota
        title_affinity = 0.20 if TOPIC_TITLE_PATTERNS[name].search(candidate["title"]) else 0.0
        possibilities.append((remaining_ratio + title_affinity, name))
    if not possibilities:
        return "other_core"
    possibilities.sort(key=lambda pair: (-pair[0], pair[1]))
    return possibilities[0][1]


def rationale_tags(
    candidate: dict[str, Any], primary_topic: str, group_was_new: bool
) -> str:
    tags = [f"base:{candidate['base_score']}", f"primary:{primary_topic}"]
    tags.extend(f"topic:{name}" for name in candidate["_topics"])
    if int(candidate.get("topic_legal_accountability") or 0):
        tags.append("topic:legal_accountability")
    tags.append(f"era:{candidate['era_bucket']}")
    chars = int(candidate["content_chars"])
    tags.append("fulltext:longform" if chars >= 8000 else "fulltext:substantive")
    if int(candidate["document_hits"]):
        tags.append(f"documents:{candidate['document_hits']}")
    if int(candidate["original_reporting_hits"]):
        tags.append(f"original-signals:{candidate['original_reporting_hits']}")
    if candidate.get("discovery_method") in {
        "import:early_reporting",
        "import:palm_beach_post_archive",
        "file:historical_released_reporting",
        "import:historical_released_reporting",
    }:
        tags.append("historical:curated")
    if int(candidate.get("full_name_mentions") or 0) < 2 and int(candidate["content_chars"]) >= 12000:
        tags.append("headline-body-risk")
    if candidate["publisher"] in INVESTIGATIVE_OUTLETS:
        tags.append("outlet:investigative")
    elif candidate["publisher_type"] in {"secondary_quality", "academic"}:
        tags.append("outlet:quality")
    elif candidate["publisher_type"] == "wire_service":
        tags.append("outlet:wire-origin")
    elif candidate["publisher_type"] in {"secondary_compromised", "secondary_blog"}:
        tags.append("outlet:caution")
    duplicate_count = int(candidate["exact_duplicate_count"])
    tags.append("hash:unique" if duplicate_count == 1 else f"hash:leader-of-{duplicate_count}")
    tags.append("independence:first-pass" if group_was_new else "independence:repeat-capped")
    if candidate["language"] != "en":
        tags.append("language:non-en")
    lowered_authors = candidate["authors"].casefold()
    if "landon thomas" in lowered_authors:
        tags.append("author-caveat:landon-thomas")
    if "michael wolff" in lowered_authors:
        tags.append("author-caveat:michael-wolff")
    return ";".join(tags)


def build_queue(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    topic_counts: Counter[str] = Counter()
    era_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    publisher_counts: Counter[str] = Counter()
    group_counts: Counter[str] = Counter()
    publisher_type_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []
    selected_title_clusters: set[tuple[str, tuple[str, ...]]] = set()
    used_ids: set[int] = set()
    non_english_count = 0
    for candidate in candidates:
        # The live item lacks an author row, but the profile-level source
        # override identifies item 1801 as Landon Thomas Jr.'s conflicted 2002
        # profile. Apply the author caveat even when ingest metadata omitted it.
        if int(candidate["item_id"]) == 1801 and "landon thomas" not in candidate["authors"].casefold():
            candidate["base_score"] = int(candidate["base_score"]) - 14
            candidate["authors"] = (candidate["authors"] + "; Landon Thomas Jr.").strip("; ")
        candidate["_topics"] = topics_for(candidate)
        candidate["_title_signature"] = title_signature(candidate["title"])
        candidate["_title_cluster_key"] = title_cluster_key(candidate)

    if limit != sum(ERA_TARGETS.values()):
        raise ValueError(f"This stratified queue is calibrated for {sum(ERA_TARGETS.values())} rows")

    # Fill scarce eras first so NBC/CBS/Guardian caps are reserved for the tiny
    # historical pool rather than consumed by 2025-26 volume.
    era_order = (
        "pre_2015", "2015_2018", "undated", "2019",
        "2020_2024", "2025", "2026_plus",
    )
    for target_era in era_order:
        strict_diversity = True
        while era_counts[target_era] < ERA_TARGETS[target_era]:
            ranked: list[tuple[float, int, dict[str, Any]]] = []
            for candidate in candidates:
                item_id = int(candidate["item_id"])
                if item_id in used_ids or candidate["era_bucket"] != target_era:
                    continue
                current_publisher_cap = publisher_cap(candidate) if strict_diversity else 24
                if publisher_counts[candidate["publisher"]] >= current_publisher_cap:
                    continue
                group = candidate["independence_group"]
                group_cap = current_publisher_cap if group.startswith("outlet:") else 3
                if group_counts[group] >= group_cap:
                    continue
                language = candidate["language"]
                if language == "en" and language_counts["en"] >= max(0, limit - NON_ENGLISH_TARGET):
                    continue
                if language != "en" and non_english_count >= NON_ENGLISH_TARGET:
                    continue
                per_language_cap = 6 if strict_diversity else 10
                if language != "en" and language_counts[language] >= per_language_cap:
                    continue
                if (
                    candidate["publisher_type"] == "broadcast"
                    and publisher_type_counts["broadcast"] >= BROADCAST_CAP
                ):
                    continue
                if (
                    candidate["publisher_type"] == "wire_service"
                    and publisher_type_counts["wire_service"] >= 10
                ):
                    continue
                cluster_key = candidate["_title_cluster_key"]
                if cluster_key is not None and cluster_key in selected_title_clusters:
                    continue
                score = candidate_selection_score(
                    candidate,
                    topic_counts,
                    era_counts,
                    publisher_counts,
                    group_counts,
                    non_english_count,
                )
                ranked.append((score, int(candidate["document_hits"]), candidate))

            if not ranked:
                if strict_diversity:
                    strict_diversity = False
                    continue
                raise RuntimeError(
                    f"Only selected {len(selected)} of {limit}; {target_era} quota exhausted "
                    f"under hard caps; eras={dict(era_counts)} topics={dict(topic_counts)} "
                    f"languages={dict(language_counts)} publisher_types={dict(publisher_type_counts)}"
                )
            ranked.sort(key=lambda triple: (-triple[0], -triple[1], int(triple[2]["item_id"])))
            score, _doc_hits, chosen = ranked[0]
            group_was_new = group_counts[chosen["independence_group"]] == 0
            primary_topic = choose_primary_topic(chosen, topic_counts)
            chosen["_selection_score"] = round(score, 1)
            chosen["_primary_topic"] = primary_topic
            chosen["_rationale_tags"] = rationale_tags(chosen, primary_topic, group_was_new)
            selected.append(chosen)
            if chosen["_title_cluster_key"] is not None:
                selected_title_clusters.add(chosen["_title_cluster_key"])
            used_ids.add(int(chosen["item_id"]))
            topic_counts[primary_topic] += 1
            era_counts[chosen["era_bucket"]] += 1
            language_counts[chosen["language"]] += 1
            publisher_counts[chosen["publisher"]] += 1
            group_counts[chosen["independence_group"]] += 1
            publisher_type_counts[chosen["publisher_type"]] += 1
            if chosen["language"] != "en":
                non_english_count += 1

    if len({row["content_hash"] for row in selected}) != len(selected):
        raise AssertionError("exact current-content duplicate escaped SQL leader selection")
    selected.sort(
        key=lambda row: (
            -float(row["_selection_score"]),
            -int(row["document_hits"]),
            int(row["item_id"]),
        )
    )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("datasets/epstein_reporting.db"))
    parser.add_argument("--sql", type=Path, default=Path(__file__).with_name("claims_queue.sql"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("claims-queue.csv"))
    parser.add_argument("--candidate-cache", type=Path)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    if args.candidate_cache and args.candidate_cache.exists():
        candidates = json.loads(args.candidate_cache.read_text(encoding="utf-8"))
    else:
        db_path = args.db.resolve()
        sql = args.sql.read_text(encoding="utf-8")
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.create_function("REGEXP", 2, sqlite_regexp, deterministic=True)
        db.execute("PRAGMA query_only = ON")
        candidates = [dict(row) for row in db.execute(sql)]
        db.close()
        if args.candidate_cache:
            args.candidate_cache.write_text(
                json.dumps(candidates, ensure_ascii=False), encoding="utf-8"
            )

    queue = build_queue(candidates, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "rank", "item_id", "published_at", "publisher", "language",
                "title", "score", "rationale_tags",
            ),
        )
        writer.writeheader()
        for rank, row in enumerate(queue, 1):
            writer.writerow(
                {
                    "rank": rank,
                    "item_id": row["item_id"],
                    "published_at": row["published_at"] or "",
                    "publisher": row["publisher"],
                    "language": row["language"],
                    "title": row["title"],
                    "score": f"{row['_selection_score']:.1f}",
                    "rationale_tags": row["_rationale_tags"],
                }
            )

    print(
        f"wrote {len(queue)} rows from {len(candidates)} eligible exact-content leaders "
        f"to {args.output}"
    )
    print("eras:", dict(Counter(row["era_bucket"] for row in queue)))
    print("primary topics:", dict(Counter(row["_primary_topic"] for row in queue)))
    print("languages:", dict(Counter(row["language"] for row in queue)))


if __name__ == "__main__":
    main()
