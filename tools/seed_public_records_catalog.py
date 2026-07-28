#!/usr/bin/env python3
"""Bootstrap the public-records catalog from tracked manifests and reviews.

The bootstrap keeps candidate manifests and current access reviews distinct so
adapters can read one central, auditable description of each supported route.

Usage:
    uv run python tools/seed_public_records_catalog.py
    uv run python tools/seed_public_records_catalog.py --db /tmp/catalog.db --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
        PublicRecordsCatalog,
        utc_now,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_catalog import DEFAULT_DB_PATH, PublicRecordsCatalog, utc_now

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "public_records_sources.yaml"


def _load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("public-record source config must be a mapping")
    if data.get("schema_version") != 1:
        raise ValueError("unsupported public-record source config schema")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("public-record source config requires a non-empty sources list")
    return dict(data)


def _same_review(latest: Mapping[str, Any] | None, review: Mapping[str, Any]) -> bool:
    if not latest:
        return False
    latest_limits = latest.get("limits", {})
    return (
        latest.get("access_class") == str(review["access_class"]).upper()
        and latest.get("automation_disposition")
        == review["automation_disposition"]
        and latest.get("review_basis") == review["review_basis"]
        and latest_limits == review.get("limits", {})
    )


def ensure_catalog_source(
    source_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> PublicRecordsCatalog:
    """Return a catalog containing ``source_id`` without rewriting current state.

    Query adapters use this lightweight bootstrap path.  An already registered
    source is left untouched, including any access review recorded after the
    tracked configuration was written.  The explicit ``seed_catalog`` command
    remains the synchronization path for the complete tracked catalog.
    """
    catalog = PublicRecordsCatalog(db_path)
    if source_id in {row["source_id"] for row in catalog.list_sources()}:
        return catalog

    config = _load_config(Path(config_path))
    source_entry = next(
        (
            entry
            for entry in config["sources"]
            if isinstance(entry, Mapping) and entry.get("source_id") == source_id
        ),
        None,
    )
    if source_entry is None:
        raise ValueError(
            f"source {source_id!r} is not present in {Path(config_path)}"
        )

    manifest = dict(source_entry)
    review = manifest.pop("access_review", None)
    submitted_by = str(config.get("submitted_by") or "public-records-bootstrap")
    catalog.register_manifest(
        manifest,
        submitted_by=submitted_by,
        submitted_at=utc_now(),
    )
    if review is not None:
        if not isinstance(review, Mapping):
            raise ValueError(f"{source_id} access_review must be a mapping")
        catalog.evaluate_access(
            source_id,
            access_class=str(review["access_class"]),
            automation_disposition=str(review["automation_disposition"]),
            reviewed_by=str(review["reviewed_by"]),
            review_basis=str(review["review_basis"]),
            limits=review.get("limits", {}),
            notes=review.get("notes"),
        )
    return catalog


def seed_catalog(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    config_path: Path | str = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    """Register manifests and reviewed access decisions idempotently."""
    config = _load_config(Path(config_path))
    catalog = PublicRecordsCatalog(db_path)
    submitted_by = str(config.get("submitted_by") or "public-records-bootstrap")
    counts = {
        "sources_seen": 0,
        "manifests_registered": 0,
        "manifests_unchanged": 0,
        "access_reviews_recorded": 0,
        "access_reviews_unchanged": 0,
    }

    for source_entry in config["sources"]:
        if not isinstance(source_entry, Mapping):
            raise ValueError("each source config entry must be a mapping")
        manifest = dict(source_entry)
        review = manifest.pop("access_review", None)
        counts["sources_seen"] += 1

        before = {row["source_id"] for row in catalog.list_sources()}
        registration = catalog.register_manifest(
            manifest,
            submitted_by=submitted_by,
            submitted_at=utc_now(),
        )
        if registration["source_id"] in before:
            counts["manifests_unchanged"] += 1
        else:
            counts["manifests_registered"] += 1

        if review is None:
            continue
        if not isinstance(review, Mapping):
            raise ValueError(
                f"{registration['source_id']} access_review must be a mapping"
            )
        detail = catalog.show_source(registration["source_id"])
        latest = detail.get("latest_access_review")
        if _same_review(latest, review):
            counts["access_reviews_unchanged"] += 1
            continue
        catalog.evaluate_access(
            registration["source_id"],
            access_class=str(review["access_class"]),
            automation_disposition=str(review["automation_disposition"]),
            reviewed_by=str(review["reviewed_by"]),
            review_basis=str(review["review_basis"]),
            limits=review.get("limits", {}),
            notes=review.get("notes"),
        )
        counts["access_reviews_recorded"] += 1

    counts["db_path"] = str(Path(db_path))
    counts["config_path"] = str(Path(config_path))
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the public-record source catalog")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    add_output_args(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = seed_catalog(db_path=args.db, config_path=args.config)
    if write_output(result, args, summary=f"catalog seed: {result['sources_seen']} sources"):
        return
    if args.json_out:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Catalog seed: {result['sources_seen']} sources; "
            f"{result['manifests_registered']} new manifests; "
            f"{result['access_reviews_recorded']} new access reviews"
        )


if __name__ == "__main__":
    main()
