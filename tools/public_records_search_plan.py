#!/usr/bin/env python3
"""Build a reproducible cross-domain property and court search plan.

This tool performs no remote acquisition. It combines user-supplied selectors
with locally available investigation context, inventories every property and
court source in the public-records catalog, and emits adapter-neutral query
templates with explicit dependencies.

Usage:
    uv run python tools/public_records_search_plan.py "Example Holdings LLC" \
        --alias "Example Holdings" --jurisdiction 36 --json
    uv run python tools/public_records_search_plan.py "Jane Example" \
        --address "100 Main St, Albany, NY" --output /tmp/records-plan.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - repository runtime includes PyYAML
    yaml = None

try:
    from tools.output_util import add_output_args
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        PublicRecordsCatalog,
    )
except ImportError:
    from output_util import add_output_args
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB,
        PublicRecordsCatalog,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVESTIGATION_DB = PROJECT_ROOT / "investigation.db"
DEFAULT_PROFILES_DIR = PROJECT_ROOT / "investigations"
SCHEMA_VERSION = 1

PROPERTY_DISCOVERY_CAPABILITIES = frozenset(
    {
        "search_owner",
        "search_address",
        "search_assessment_records",
        "search_tax_accounts",
        "enrich_census_geography",
        "sync",
    }
)
PROPERTY_DETAIL_CAPABILITIES = frozenset(
    {
        "fetch_account",
        "fetch_parcel",
        "fetch_geometry",
        "search_parcels",
        "search_sales",
        "search_recent_deed_reference",
        "search_tax_default",
        "fetch_tax_status",
        "fetch_bills",
        "fetch_payment_history",
        "fetch_auction_event",
        "fetch_foreclosure_case",
        "list_releases",
        "download_bulk",
        "list_operator_history",
        "resolve_operator",
        "resolve_well",
        "route_to_county_source",
        "route_to_county_recorder",
    }
)
RECORDER_INDEX_CAPABILITIES = frozenset(
    {
        "search_folio",
        "search_document_text",
        "search_instruments",
        "search_parcels",
        "search_parties",
    }
)
RECORDER_ENRICHMENT_CAPABILITIES = frozenset(
    {
        "search_cfn",
        "search_book_page",
        "hydrate_search_results",
        "fetch_instrument",
        "fetch_parties",
        "fetch_financial_detail",
        "fetch_document",
        "request_bulk_files",
        "request_bulk_images",
        "request_deed_of_trust",
        "request_instrument_copy",
        "request_oil_gas_record",
    }
)
RECORDER_ROLES = frozenset({"recorder", "instrument_index"})
PROPERTY_ROLES = frozenset(
    {
        "assessment",
        "ownership",
        "parcel_geometry",
        "parcel_geography",
        "parcel_index",
        "situs_address",
        "tax_status",
        "sales",
        "deed_history",
        "deeds",
        "improvements",
        "exemptions",
        "hearings",
        "oil_gas_operator_history",
        "oil_gas_organizations",
        "oil_gas_wells",
        "lease_index",
        "well_index",
        "regulatory_records",
        "entity_resolution",
    }
)
COURT_SEARCH_CAPABILITIES = frozenset(
    {
        "search_cases",
        "search_documents",
        "search_hearings",
        "search_judgments",
        "search_opinions",
        "search_parties",
        "search_publications",
        "search_owner",
        "search_address",
        "search_judges",
        "lookup_case",
        "list_excess_proceeds",
    }
)
COURT_SETUP_CAPABILITIES = frozenset(
    {
        "list_case_reports",
        "list_courts",
        "list_judges",
        "list_court_offices",
        "list_prothonotaries",
        "list_clerks_of_courts",
        "list_registers_of_wills",
        "list_district_court_administrators",
        "list_calendars",
        "list_current_releases",
        "query_magisterial_district_geometry",
        "route_address_to_magisterial_district",
    }
)
COURT_DETAIL_CAPABILITIES = frozenset(
    {
        "fetch_case",
        "fetch_document",
        "fetch_parties",
        "fetch_publication",
        "fetch_legacy_document",
        "list_case_events",
        "list_charges",
        "list_docket_entries",
        "list_document_index",
        "list_docket_documents",
        "list_estate_docket",
        "list_probate_notes",
        "list_probate_claims",
        "request_bulk_files",
        "request_case_copy",
        "request_case_report",
        "request_certified_copy",
        "request_court_data",
        "request_docket_range",
        "fetch_calendar_document",
        "fetch_opinion",
        "fetch_opinion_pdf",
        "fetch_release_document",
        "export",
    }
)


def _court_capability_groups(
    supported: set[str],
    *,
    adapter_capabilities: set[str],
) -> tuple[set[str], set[str], set[str]]:
    """Classify shared names plus executable adapter-specific variants."""

    setup = set(supported & COURT_SETUP_CAPABILITIES)
    search = set(supported & COURT_SEARCH_CAPABILITIES)
    search.update(
        capability
        for capability in adapter_capabilities
        if capability.startswith(("search_", "lookup_"))
    )
    detail = set(supported & COURT_DETAIL_CAPABILITIES)
    detail.update(
        capability
        for capability in adapter_capabilities
        if capability.startswith(
            (
                "fetch_",
                "request_",
                "parse_",
                "download_",
                "export_",
            )
        )
    )
    search.difference_update(setup)
    detail.difference_update(setup | search)
    return setup, search, detail


def _property_capability_groups(
    supported: set[str],
    *,
    adapter_capabilities: set[str],
) -> tuple[set[str], set[str]]:
    """Classify shared names plus executable property-specific variants."""

    discovery = set(supported & PROPERTY_DISCOVERY_CAPABILITIES)
    detail = set(supported & PROPERTY_DETAIL_CAPABILITIES)
    discovery.update(
        capability
        for capability in adapter_capabilities
        if capability.startswith(("search_", "lookup_"))
    )
    detail.update(
        capability
        for capability in adapter_capabilities
        if capability.startswith(
            (
                "fetch_",
                "request_",
                "parse_",
                "download_",
                "export_",
            )
        )
    )
    discovery.difference_update(detail)
    return discovery, detail


class SearchPlanError(ValueError):
    """Raised when a requested plan cannot be represented consistently."""


def canonical_json(value: Any) -> str:
    """Return the stable JSON representation used for plan fingerprints."""
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _clean(value: str) -> str:
    return " ".join(value.split())


def _key(value: str) -> str:
    return _clean(value).casefold()


def _sorted_unique(values: Iterable[str]) -> list[str]:
    by_key: dict[str, str] = {}
    for raw in values:
        if not isinstance(raw, str):
            continue
        value = _clean(raw)
        if value:
            by_key.setdefault(value.casefold(), value)
    return [by_key[key] for key in sorted(by_key)]


def _merge_value(
    target: dict[str, dict[str, Any]],
    value: str,
    provenance: str,
    **metadata: Any,
) -> None:
    cleaned = _clean(value)
    if not cleaned:
        return
    key = cleaned.casefold()
    row = target.setdefault(
        key,
        {"value": cleaned, "provenance": set(), "metadata": {}},
    )
    row["provenance"].add(provenance)
    for metadata_key, metadata_value in metadata.items():
        if metadata_value is not None and metadata_value != "":
            row["metadata"].setdefault(metadata_key, metadata_value)


def _materialize_values(
    values: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    materialized = []
    for key in sorted(values):
        row = values[key]
        item = {
            "value": row["value"],
            "provenance": sorted(row["provenance"]),
        }
        if row["metadata"]:
            item["metadata"] = dict(sorted(row["metadata"].items()))
        materialized.append(item)
    return materialized


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def _open_readonly(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _alias_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(db, "name_aliases"):
        return []
    columns = {row["name"] for row in db.execute("PRAGMA table_info(name_aliases)")}
    selected = ["canonical_name", "alias"]
    for optional in ("alias_type", "entity_id"):
        if optional in columns:
            selected.append(optional)
    rows = db.execute(
        f"SELECT {', '.join(selected)} FROM name_aliases "
        "ORDER BY lower(canonical_name), lower(alias)"
    ).fetchall()
    return [dict(row) for row in rows]


def _resolve_canonical_name(
    subject: str,
    explicit_aliases: Sequence[str],
    alias_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, list[Mapping[str, Any]], list[str]]:
    subject_key = _key(subject)
    selector_keys = {subject_key, *(_key(value) for value in explicit_aliases)}
    matching = [
        row
        for row in alias_rows
        if _key(str(row["canonical_name"])) in selector_keys
        or _key(str(row["alias"])) in selector_keys
    ]
    direct_alias_matches = sorted(
        {
            _clean(str(row["canonical_name"]))
            for row in matching
            if _key(str(row["alias"])) == subject_key
        },
        key=str.casefold,
    )
    direct_canonical_matches = sorted(
        {
            _clean(str(row["canonical_name"]))
            for row in matching
            if _key(str(row["canonical_name"])) == subject_key
        },
        key=str.casefold,
    )
    candidates = (
        direct_alias_matches
        or direct_canonical_matches
        or sorted(
            {_clean(str(row["canonical_name"])) for row in matching},
            key=str.casefold,
        )
    )
    canonical = candidates[0] if candidates else _clean(subject)
    canonical_rows = [
        row for row in alias_rows if _key(str(row["canonical_name"])) == _key(canonical)
    ]
    return canonical, canonical_rows, candidates


def _matching_entities(
    db: sqlite3.Connection,
    names: Sequence[str],
    entity_ids: Sequence[int],
) -> list[dict[str, Any]]:
    if not _table_exists(db, "entities"):
        return []
    columns = {row["name"] for row in db.execute("PRAGMA table_info(entities)")}
    selected = [
        column
        for column in ("id", "name", "entity_type", "jurisdiction", "address")
        if column in columns
    ]
    if not selected or "id" not in selected or "name" not in selected:
        return []

    name_keys = {_key(value) for value in names}
    entity_id_set = {int(value) for value in entity_ids if value is not None}
    rows = db.execute(
        f"SELECT {', '.join(selected)} FROM entities ORDER BY id"
    ).fetchall()
    return [
        dict(row)
        for row in rows
        if int(row["id"]) in entity_id_set or _key(str(row["name"])) in name_keys
    ]


def _profile_name_from_db(db: sqlite3.Connection) -> str | None:
    if not _table_exists(db, "investigation_config"):
        return None
    row = db.execute(
        "SELECT value FROM investigation_config WHERE key='active_profile'"
    ).fetchone()
    if row is None:
        return None
    value = _clean(str(row["value"]))
    return value or None


def _read_profile(
    profile_name: str | None,
    profiles_dir: Path,
) -> tuple[dict[str, Any] | None, str | None]:
    if not profile_name:
        return None, None
    path = profiles_dir / profile_name / "config.yaml"
    if not path.exists():
        return None, f"profile config not found: {path}"
    try:
        text = path.read_text()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            if yaml is None:
                return None, "PyYAML is unavailable and profile is not JSON"
            data = yaml.safe_load(text)
    except (OSError, ValueError) as error:
        return None, f"could not read profile {profile_name}: {error}"
    if not isinstance(data, Mapping):
        return None, f"profile {profile_name} does not contain a mapping"
    return dict(data), None


def _profile_address_rows(profile: Mapping[str, Any]) -> list[tuple[str, str]]:
    raw = profile.get("known_addresses", {})
    if isinstance(raw, Mapping):
        return sorted(
            (
                (_clean(str(address)), _clean(str(description)))
                for address, description in raw.items()
                if _clean(str(address))
            ),
            key=lambda item: item[0].casefold(),
        )
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return sorted(
            ((_clean(str(address)), "") for address in raw if _clean(str(address))),
            key=lambda item: item[0].casefold(),
        )
    return []


def _text_mentions_any(text: str, selectors: Sequence[str]) -> bool:
    haystack = _key(text)
    return any(
        len(selector) >= 3 and _key(selector) in haystack for selector in selectors
    )


def _load_identity_context(
    *,
    subject: str,
    explicit_aliases: Sequence[str],
    explicit_addresses: Sequence[str],
    explicit_related_entities: Sequence[str],
    explicit_jurisdictions: Sequence[str],
    investigation_db: Path,
    profile_name: str | None,
    profiles_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    names: dict[str, dict[str, Any]] = {}
    addresses: dict[str, dict[str, Any]] = {}
    jurisdictions: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    database_context = {
        "path": str(investigation_db),
        "available": investigation_db.exists(),
        "alias_rows_matched": 0,
        "entities_matched": 0,
    }

    _merge_value(names, subject, "input:subject")
    for alias in explicit_aliases:
        _merge_value(names, alias, "input:alias")
    for address in explicit_addresses:
        _merge_value(addresses, address, "input:address")
    for jurisdiction in explicit_jurisdictions:
        _merge_value(jurisdictions, jurisdiction, "input:jurisdiction")

    alias_rows: list[dict[str, Any]] = []
    canonical_name = _clean(subject)
    canonical_rows: list[Mapping[str, Any]] = []
    related_rows: list[dict[str, Any]] = []
    db: sqlite3.Connection | None = None
    selected_profile = profile_name
    try:
        if investigation_db.exists():
            db = _open_readonly(investigation_db)
            alias_rows = _alias_rows(db)
            canonical_name, canonical_rows, candidates = _resolve_canonical_name(
                subject, explicit_aliases, alias_rows
            )
            if len(candidates) > 1:
                unresolved.append(
                    {
                        "code": "ambiguous_canonical_name",
                        "note": (
                            "Multiple canonical names match the supplied subject "
                            "or aliases."
                        ),
                        "values": candidates,
                    }
                )
            _merge_value(names, canonical_name, "investigation_db:canonical_name")
            for row in canonical_rows:
                _merge_value(
                    names,
                    str(row["alias"]),
                    "investigation_db:name_aliases",
                    alias_type=row.get("alias_type"),
                )
            database_context["alias_rows_matched"] = len(canonical_rows)

            subject_entity_ids = [
                int(row["entity_id"])
                for row in canonical_rows
                if row.get("entity_id") is not None
            ]
            subject_entities = _matching_entities(
                db,
                [canonical_name, subject, *explicit_aliases],
                subject_entity_ids,
            )
            database_context["entities_matched"] += len(subject_entities)
            for entity in subject_entities:
                if entity.get("address"):
                    _merge_value(
                        addresses,
                        str(entity["address"]),
                        "investigation_db:entities",
                        entity_id=entity["id"],
                    )
                if entity.get("jurisdiction"):
                    _merge_value(
                        jurisdictions,
                        str(entity["jurisdiction"]),
                        "investigation_db:entities",
                        entity_id=entity["id"],
                    )

            for related_input in _sorted_unique(explicit_related_entities):
                related_canonical, aliases_for_related, _ = _resolve_canonical_name(
                    related_input, [], alias_rows
                )
                related_entity_ids = [
                    int(row["entity_id"])
                    for row in aliases_for_related
                    if row.get("entity_id") is not None
                ]
                entity_rows = _matching_entities(
                    db,
                    [related_input, related_canonical],
                    related_entity_ids,
                )
                database_context["entities_matched"] += len(entity_rows)
                related_names = _sorted_unique(
                    [
                        related_input,
                        related_canonical,
                        *[str(row["alias"]) for row in aliases_for_related],
                        *[str(row["name"]) for row in entity_rows],
                    ]
                )
                related_addresses = _sorted_unique(
                    [str(row["address"]) for row in entity_rows if row.get("address")]
                )
                related_jurisdictions = _sorted_unique(
                    [
                        str(row["jurisdiction"])
                        for row in entity_rows
                        if row.get("jurisdiction")
                    ]
                )
                for address in related_addresses:
                    _merge_value(
                        addresses,
                        address,
                        "investigation_db:related_entity",
                        related_entity=related_canonical,
                    )
                for jurisdiction in related_jurisdictions:
                    _merge_value(
                        jurisdictions,
                        jurisdiction,
                        "investigation_db:related_entity",
                        related_entity=related_canonical,
                    )
                related_rows.append(
                    {
                        "input": related_input,
                        "canonical_name": related_canonical,
                        "names": related_names,
                        "addresses": related_addresses,
                        "jurisdictions": related_jurisdictions,
                    }
                )
            if selected_profile is None:
                selected_profile = _profile_name_from_db(db)
    except sqlite3.Error as error:
        database_context["error"] = str(error)
        unresolved.append(
            {
                "code": "investigation_database_unreadable",
                "note": "Local investigation context could not be read.",
                "detail": str(error),
            }
        )
    finally:
        if db is not None:
            db.close()

    if not related_rows:
        related_rows = [
            {
                "input": value,
                "canonical_name": value,
                "names": [value],
                "addresses": [],
                "jurisdictions": [],
            }
            for value in _sorted_unique(explicit_related_entities)
        ]
    related_rows.sort(key=lambda row: _key(row["canonical_name"]))

    profile, profile_error = _read_profile(selected_profile, profiles_dir)
    profile_context: dict[str, Any] = {
        "name": selected_profile,
        "available": profile is not None,
        "primary_subject_match": False,
        "key_person_match": False,
        "known_addresses_available": 0,
        "known_addresses_matched": 0,
    }
    if profile_error:
        profile_context["error"] = profile_error
        unresolved.append(
            {
                "code": "profile_context_unavailable",
                "note": profile_error,
            }
        )
    if profile is not None:
        primary_subject = _clean(str(profile.get("primary_subject", "")))
        profile_context["primary_subject"] = primary_subject or None
        profile_context["primary_subject_match"] = bool(primary_subject) and _key(
            primary_subject
        ) == _key(canonical_name)
        key_people = _sorted_unique(
            str(value) for value in profile.get("key_persons", [])
        )
        matching_key_people = [
            value
            for value in key_people
            if _key(value)
            in {
                _key(canonical_name),
                _key(subject),
                *(_key(value) for value in explicit_aliases),
            }
        ]
        profile_context["key_person_match"] = bool(matching_key_people)
        for value in matching_key_people:
            _merge_value(names, value, f"profile:{selected_profile}:key_person")

        known_addresses = _profile_address_rows(profile)
        profile_context["known_addresses_available"] = len(known_addresses)
        selectors = [
            canonical_name,
            subject,
            *explicit_aliases,
            *[name for related in related_rows for name in related.get("names", [])],
        ]
        matching_addresses = [
            (address, description)
            for address, description in known_addresses
            if profile_context["primary_subject_match"]
            or _text_mentions_any(
                f"{address} {description}",
                selectors,
            )
        ]
        profile_context["known_addresses_matched"] = len(matching_addresses)
        for address, description in matching_addresses:
            _merge_value(
                addresses,
                address,
                f"profile:{selected_profile}:known_addresses",
                description=description,
            )

    identity = {
        "input_subject": _clean(subject),
        "canonical_name": canonical_name,
        "names": _materialize_values(names),
        "addresses": _materialize_values(addresses),
        "related_entities": related_rows,
        "jurisdictions": _materialize_values(jurisdictions),
    }
    context = {
        "investigation_database": database_context,
        "profile": profile_context,
    }
    return identity, context, unresolved


def _parse_date(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    cleaned = _clean(value)
    try:
        return date.fromisoformat(cleaned).isoformat()
    except ValueError as error:
        raise SearchPlanError(f"{field} must be an ISO date (YYYY-MM-DD)") from error


def _jurisdiction_match(
    requested: Sequence[str],
    source_jurisdictions: Sequence[Mapping[str, Any]],
    *,
    numeric_hierarchy: bool = True,
) -> dict[str, Any]:
    requested_values = _sorted_unique(requested)
    if not requested_values:
        return {
            "status": "not_scoped",
            "requested": [],
            "matched": [],
            "unmatched": [],
        }

    matched: list[str] = []
    for request in requested_values:
        request_key = _key(request)
        request_digits = re.sub(r"\D", "", request)
        for jurisdiction in source_jurisdictions:
            identifiers = {
                _key(str(jurisdiction.get(field, "")))
                for field in (
                    "jurisdiction_id",
                    "geoid",
                    "name",
                    "subdivision_code",
                )
                if jurisdiction.get(field)
            }
            geoid = str(jurisdiction.get("geoid") or "")
            country_code = str(jurisdiction.get("country_code") or "")
            numeric_hierarchy_match = (
                numeric_hierarchy
                and bool(request_digits)
                and geoid.isdigit()
                and (
                    request_digits.startswith(geoid) or geoid.startswith(request_digits)
                )
            )
            nationwide_match = geoid.upper() in {"US", "USA"} and (
                country_code.upper() == "US"
            )
            if (
                request_key in identifiers
                or numeric_hierarchy_match
                or nationwide_match
            ):
                matched.append(request)
                break
    matched = _sorted_unique(matched)
    unmatched = [
        value
        for value in requested_values
        if _key(value) not in {_key(v) for v in matched}
    ]
    return {
        "status": (
            "matched" if not unmatched else "partial" if matched else "no_catalog_match"
        ),
        "requested": requested_values,
        "matched": matched,
        "unmatched": unmatched,
    }


def _catalog_access(detail: Mapping[str, Any]) -> dict[str, Any]:
    source = detail["source"]
    review = detail.get("latest_access_review")
    if review is None:
        return {
            "review_state": "unreviewed",
            "mode": "unreviewed",
            "latest_review": None,
            "manifest_proposal": {
                "access_class": source["proposed_access_class"],
                "automation_disposition": source["proposed_automation_disposition"],
            },
        }
    return {
        "review_state": "reviewed",
        "mode": review["automation_disposition"],
        "latest_review": {
            key: review.get(key)
            for key in (
                "access_review_id",
                "access_class",
                "automation_disposition",
                "limits",
                "review_basis",
                "notes",
                "terms_snapshot_id",
                "contract_verified",
                "contract_reference",
                "reviewed_by",
                "reviewed_at",
                "valid_until",
            )
        },
        "manifest_proposal": {
            "access_class": source["proposed_access_class"],
            "automation_disposition": source["proposed_automation_disposition"],
        },
    }


def _load_catalog_sources(
    catalog_db: Path,
    requested_jurisdictions: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not catalog_db.exists():
        return [], [
            {
                "code": "catalog_unavailable",
                "note": f"Public-records catalog not found: {catalog_db}",
            }
        ]
    sources: list[dict[str, Any]] = []
    try:
        catalog = PublicRecordsCatalog(catalog_db, initialize=False)
        for row in catalog.list_sources():
            if row["domain"] not in {"property", "court", "mixed"}:
                continue
            detail = catalog.show_source(row["source_id"])
            source = detail["source"]
            manifest = detail.get("current_manifest") or {}
            capabilities = [
                {
                    "name": capability["name"],
                    "supported": capability["supported"],
                    "details": capability["details"],
                }
                for capability in detail["capabilities"]
            ]
            jurisdictions = [
                {
                    key: jurisdiction.get(key)
                    for key in (
                        "jurisdiction_id",
                        "name",
                        "kind",
                        "country_code",
                        "subdivision_code",
                        "geoid",
                        "coverage",
                        "exclusions",
                    )
                }
                for jurisdiction in detail["jurisdictions"]
            ]
            sources.append(
                {
                    "source_id": source["source_id"],
                    "name": source["name"],
                    "domain": source["domain"],
                    "roles": list(detail["roles"]),
                    "authority": source["authority"],
                    "official_url": source["official_url"],
                    "platform_family": source["platform_family"],
                    "source_status": source["source_status"],
                    "coverage_start": source.get("coverage_start"),
                    "update_cadence": source.get("update_cadence"),
                    "adapter_family": source.get("adapter_family"),
                    "adapter_version": source.get("adapter_version"),
                    "record_identity_source_id": (
                        manifest.get("record_identity_source_id") or source["source_id"]
                    ),
                    "complementary_source_ids": list(
                        manifest.get("complementary_source_ids") or []
                    ),
                    "capabilities": capabilities,
                    "jurisdictions": jurisdictions,
                    "requested_jurisdiction_coverage": _jurisdiction_match(
                        requested_jurisdictions,
                        jurisdictions,
                        numeric_hierarchy=(
                            manifest.get("jurisdiction_match_mode") != "explicit"
                        ),
                    ),
                    "access": _catalog_access(detail),
                }
            )
    except (sqlite3.Error, KeyError, ValueError) as error:
        return [], [
            {
                "code": "catalog_unreadable",
                "note": "Public-records catalog could not be read.",
                "detail": str(error),
            }
        ]
    sources.sort(key=lambda source: source["source_id"])
    return sources, []


def _access_ref(source: Mapping[str, Any]) -> dict[str, Any]:
    review = source["access"]["latest_review"]
    return {
        "source_id": source["source_id"],
        "access_review_id": (
            review.get("access_review_id") if review is not None else None
        ),
        "mode": source["access"]["mode"],
    }


def _task(
    *,
    task_id: str,
    stage: str,
    source: Mapping[str, Any],
    capability: str,
    depends_on: Sequence[str],
    seed_parameters: Mapping[str, Any],
    runtime_inputs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    capability_details = next(
        (
            capability_row.get("details") or {}
            for capability_row in source["capabilities"]
            if capability_row["name"] == capability
        ),
        {},
    )
    return {
        "task_id": task_id,
        "stage": stage,
        "source_id": source["source_id"],
        "capability": capability,
        "capability_details": dict(capability_details),
        "depends_on": sorted(set(depends_on)),
        "seed_parameters": dict(seed_parameters),
        "runtime_inputs": list(runtime_inputs),
        "catalog_access": _access_ref(source),
    }


def _build_workflow(
    sources: Sequence[Mapping[str, Any]],
    identity: Mapping[str, Any],
    date_bounds: Mapping[str, str | None],
) -> dict[str, Any]:
    subject_names = [row["value"] for row in identity["names"]]
    related_names = _sorted_unique(
        name for related in identity["related_entities"] for name in related["names"]
    )
    party_names = _sorted_unique([*subject_names, *related_names])
    addresses = [row["value"] for row in identity["addresses"]]
    jurisdictions = [row["value"] for row in identity["jurisdictions"]]
    common_scope = {
        "jurisdictions": jurisdictions,
        "date_bounds": dict(date_bounds),
    }

    def source_scope(source: Mapping[str, Any]) -> dict[str, Any]:
        matched = source["requested_jurisdiction_coverage"]["matched"]
        return {
            **common_scope,
            "jurisdictions": list(matched) if jurisdictions else [],
        }

    workflow_sources = [
        source
        for source in sources
        if not jurisdictions or source["requested_jurisdiction_coverage"]["matched"]
    ]

    property_tasks: list[dict[str, Any]] = []
    property_seed_ids: list[str] = []
    property_detail_specs: list[tuple[Mapping[str, Any], str]] = []
    recorder_index_specs: list[tuple[Mapping[str, Any], str]] = []
    recorder_enrichment_specs: list[tuple[Mapping[str, Any], str]] = []
    court_sources: list[tuple[Mapping[str, Any], set[str], set[str], set[str]]] = []

    for source in workflow_sources:
        supported = {
            capability["name"]
            for capability in source["capabilities"]
            if capability["supported"]
        }
        roles = set(source["roles"])
        is_recorder = bool(RECORDER_ROLES.intersection(roles))
        is_parcel_source = bool(PROPERTY_ROLES.intersection(roles))
        if source["domain"] in {"property", "mixed"} and (
            is_parcel_source or not is_recorder
        ):
            adapter_capabilities = {
                capability["name"]
                for capability in source["capabilities"]
                if capability["supported"]
                and (
                    (capability.get("details") or {}).get("adapter_tool")
                    or (capability.get("details") or {}).get("adapter_command")
                    or (capability.get("details") or {}).get("adapter_commands")
                )
            }
            discovery, detail = _property_capability_groups(
                supported,
                adapter_capabilities=adapter_capabilities,
            )
            for capability in sorted(discovery):
                task_id = f"property.{source['source_id']}.{capability}"
                parameters: dict[str, Any] = source_scope(source)
                if capability == "search_owner":
                    parameters["names"] = party_names
                elif capability == "search_address":
                    parameters["addresses"] = addresses
                elif capability == "search_assessment_records":
                    parameters["queries"] = _sorted_unique([*party_names, *addresses])
                elif capability == "enrich_census_geography":
                    parameters["geographies"] = list(parameters["jurisdictions"])
                    parameters["addresses"] = addresses
                elif capability == "sync":
                    parameters["selectors"] = {
                        "names": party_names,
                        "addresses": addresses,
                    }
                else:
                    parameters["queries"] = _sorted_unique([*party_names, *addresses])
                property_tasks.append(
                    _task(
                        task_id=task_id,
                        stage="property_discovery",
                        source=source,
                        capability=capability,
                        depends_on=[],
                        seed_parameters=parameters,
                    )
                )
                property_seed_ids.append(task_id)
            for capability in sorted(detail):
                property_detail_specs.append((source, capability))
        if source["domain"] in {"property", "mixed"} and is_recorder:
            recorder_index_capabilities = supported & RECORDER_INDEX_CAPABILITIES
            if "search_parcels" in recorder_index_capabilities:
                recorder_index_capabilities.discard("search_folio")
            for capability in sorted(recorder_index_capabilities):
                recorder_index_specs.append((source, capability))
            for capability in sorted(supported & RECORDER_ENRICHMENT_CAPABILITIES):
                recorder_enrichment_specs.append((source, capability))
        if source["domain"] in {"court", "mixed"}:
            adapter_capabilities = {
                capability["name"]
                for capability in source["capabilities"]
                if capability["supported"]
                and (
                    (capability.get("details") or {}).get("adapter_tool")
                    or (capability.get("details") or {}).get("adapter_command")
                )
            }
            setup, search, detail = _court_capability_groups(
                supported,
                adapter_capabilities=adapter_capabilities,
            )
            court_sources.append((source, setup, search, detail))

    for source, capability in property_detail_specs:
        task_id = f"property.{source['source_id']}.{capability}"
        property_tasks.append(
            _task(
                task_id=task_id,
                stage="property_details",
                source=source,
                capability=capability,
                depends_on=property_seed_ids,
                seed_parameters={
                    **source_scope(source),
                    "names": party_names,
                    "addresses": addresses,
                },
                runtime_inputs=[
                    {
                        "name": "parcel_identifiers",
                        "from_tasks": sorted(property_seed_ids),
                        "fields": [
                            "tax_bill_id",
                            "parcel_id",
                            "parid",
                            "ain",
                            "apn",
                            "native_parcel_id",
                            "alternate_parcel_id",
                            "state_parcel_id",
                            "local_parcel_id",
                            "jurisdiction_geoid",
                        ],
                    }
                ],
            )
        )
    property_tasks.sort(key=lambda task: task["task_id"])
    property_ids = [task["task_id"] for task in property_tasks]

    recorder_tasks: list[dict[str, Any]] = []
    recorder_search_ids: list[str] = []
    for source, capability in recorder_index_specs:
        task_id = f"recorder.{source['source_id']}.{capability}"
        recorder_tasks.append(
            _task(
                task_id=task_id,
                stage="recorder_index",
                source=source,
                capability=capability,
                depends_on=property_ids,
                seed_parameters={
                    **source_scope(source),
                    "party_names": party_names,
                    "addresses": addresses,
                },
                runtime_inputs=[
                    {
                        "name": "property_identifiers",
                        "from_tasks": property_ids,
                        "fields": [
                            "ain",
                            "apn",
                            "native_parcel_id",
                            "alternate_parcel_id",
                            "state_parcel_id",
                            "local_parcel_id",
                            "situs_address",
                            "legal_description",
                            "owner_name",
                            "book",
                            "page",
                            "book_type",
                            "native_sale_id",
                        ],
                    }
                ],
            )
        )
        recorder_search_ids.append(task_id)
    for source, capability in recorder_enrichment_specs:
        task_id = f"recorder.{source['source_id']}.{capability}"
        recorder_tasks.append(
            _task(
                task_id=task_id,
                stage="recorder_instruments",
                source=source,
                capability=capability,
                depends_on=[*property_ids, *recorder_search_ids],
                seed_parameters=source_scope(source),
                runtime_inputs=[
                    {
                        "name": "instrument_and_route_identifiers",
                        "from_tasks": sorted({*property_ids, *recorder_search_ids}),
                        "fields": [
                            "native_document_id",
                            "instrument_id",
                            "clerk_file_number",
                            "cfn_master_id",
                            "cfn_master_ids",
                            "document_type",
                            "instrument_type",
                            "recording_date",
                            "recording_document_number",
                            "recording_locator",
                            "book",
                            "page",
                            "book_type",
                            "issued_search_token",
                        ],
                    }
                ],
            )
        )
    recorder_tasks.sort(key=lambda task: task["task_id"])
    recorder_ids = [task["task_id"] for task in recorder_tasks]

    court_tasks: list[dict[str, Any]] = []
    court_setup_ids_by_source: dict[str, list[str]] = {}
    court_search_ids_by_source: dict[str, list[str]] = {}
    upstream_ids = sorted([*property_ids, *recorder_ids])
    for source, setup_capabilities, search_capabilities, _detail in court_sources:
        source_setup_ids = []
        for capability in sorted(setup_capabilities):
            task_id = f"court.{source['source_id']}.{capability}"
            court_tasks.append(
                _task(
                    task_id=task_id,
                    stage="court_source_discovery",
                    source=source,
                    capability=capability,
                    depends_on=[],
                    seed_parameters=source_scope(source),
                )
            )
            source_setup_ids.append(task_id)
        court_setup_ids_by_source[source["source_id"]] = source_setup_ids

        source_search_ids = []
        for capability in sorted(search_capabilities):
            task_id = f"court.{source['source_id']}.{capability}"
            court_tasks.append(
                _task(
                    task_id=task_id,
                    stage="court_case_search",
                    source=source,
                    capability=capability,
                    depends_on=[
                        *upstream_ids,
                        *source_setup_ids,
                    ],
                    seed_parameters={
                        **source_scope(source),
                        "party_names": party_names,
                        "addresses": addresses,
                    },
                    runtime_inputs=[
                        {
                            "name": "property_and_instrument_context",
                            "from_tasks": upstream_ids,
                            "fields": [
                                "owner_name",
                                "party_name",
                                "situs_address",
                                "mailing_address",
                                "ain",
                                "apn",
                                "legal_description",
                                "native_parcel_id",
                                "native_document_id",
                                "instrument_id",
                                "recording_document_number",
                            ],
                        },
                        {
                            "name": "court_identifiers",
                            "from_tasks": sorted(source_setup_ids),
                            "fields": [
                                "court_id",
                                "court_resource_uuid",
                                "native_court_id",
                                "native_court_external_id",
                            ],
                        },
                    ],
                )
            )
            source_search_ids.append(task_id)
        court_search_ids_by_source[source["source_id"]] = source_search_ids

    court_search_ids_by_identity: dict[str, list[str]] = {}
    for source, _setup, _search, _detail in court_sources:
        identity_source_id = str(
            source.get("record_identity_source_id") or source["source_id"]
        )
        court_search_ids_by_identity.setdefault(
            identity_source_id,
            [],
        ).extend(court_search_ids_by_source[source["source_id"]])

    for source, _setup, _search, detail_capabilities in court_sources:
        source_setup_ids = court_setup_ids_by_source[source["source_id"]]
        identity_source_id = str(
            source.get("record_identity_source_id") or source["source_id"]
        )
        source_dependencies = sorted(
            set(court_search_ids_by_identity.get(identity_source_id, []))
        )
        for capability in sorted(detail_capabilities):
            task_id = f"court.{source['source_id']}.{capability}"
            capability_details = next(
                (
                    capability_row.get("details") or {}
                    for capability_row in source["capabilities"]
                    if capability_row["name"] == capability
                ),
                {},
            )
            declared_prior_selectors = capability_details.get(
                "requires_prior_selectors",
                capability_details.get("requires_prior_selector"),
            )
            if isinstance(declared_prior_selectors, str):
                prior_selector_fields = [declared_prior_selectors]
            elif isinstance(declared_prior_selectors, Sequence):
                prior_selector_fields = [
                    str(value)
                    for value in declared_prior_selectors
                    if str(value).strip()
                ]
            else:
                prior_selector_fields = []
            if (
                "raw_case_number" in prior_selector_fields
                and "case_number" not in prior_selector_fields
            ):
                prior_selector_fields.append("case_number")
            runtime_inputs = [
                {
                    "name": "case_or_document_identifiers",
                    "from_tasks": sorted(
                        {*source_setup_ids, *source_dependencies}
                    ),
                    "fields": [
                        "court_id",
                        "court_resource_uuid",
                        "native_court_id",
                        "native_court_external_id",
                        "raw_case_number",
                        "trial_case_number",
                        "appellate_case_number",
                        "docket_id",
                        "case_uuid",
                        "case_instance_uuid",
                        "source_internal_id",
                        "party_uuid",
                        "docket_entry_uuid",
                        "native_entry_id",
                        "claim_uuid",
                        "claim_sequence_no",
                        "document_uuid",
                        "document_link_uuid",
                        "native_document_id",
                        "legacy_item_id",
                        "doc_id",
                        "rs_id",
                        "image_id",
                        "publication_uuid",
                        "notice_refcode",
                        "calendar_item",
                    ],
                }
            ]
            if prior_selector_fields:
                runtime_inputs.append(
                    {
                        "name": "declared_prior_selectors",
                        "from_tasks": sorted(
                            {
                                *upstream_ids,
                                *source_setup_ids,
                                *source_dependencies,
                            }
                        ),
                        "fields": _sorted_unique(prior_selector_fields),
                        "declared_sources": list(
                            capability_details.get(
                                "prior_selector_sources",
                                (),
                            )
                        ),
                    }
                )
            court_tasks.append(
                _task(
                    task_id=task_id,
                    stage="court_dockets_and_documents",
                    source=source,
                    capability=capability,
                    depends_on=[
                        *upstream_ids,
                        *source_setup_ids,
                        *source_dependencies,
                    ],
                    seed_parameters=source_scope(source),
                    runtime_inputs=runtime_inputs,
                )
            )
    court_tasks.sort(key=lambda task: task["task_id"])

    stages = [
        {
            "stage_id": "property",
            "purpose": (
                "Resolve parcels, ownership observations, addresses, assessments, "
                "sales, and geometry."
            ),
            "tasks": property_tasks,
        },
        {
            "stage_id": "recorder",
            "purpose": (
                "Use names and parcel identifiers to resolve recorded instruments "
                "and parties."
            ),
            "tasks": recorder_tasks,
        },
        {
            "stage_id": "court",
            "purpose": (
                "Resolve source courts, search case, party, document, and "
                "publication indexes with the available context, then retrieve "
                "case details, docket entries, and selected public records."
            ),
            "tasks": court_tasks,
        },
    ]
    return {
        "dependency_order": ["property", "recorder", "court"],
        "stages": stages,
    }


def _supported_capability_names(
    source: Mapping[str, Any],
) -> set[str]:
    return {
        str(capability["name"])
        for capability in source["capabilities"]
        if capability["supported"]
    }


def _complementary_routes(
    sources: Sequence[Mapping[str, Any]],
    identity: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Expand catalog-declared complements into field-oriented route groups."""

    sources_by_id = {str(source["source_id"]): source for source in sources}
    requested_jurisdictions = {str(row["value"]) for row in identity["jurisdictions"]}
    groups: list[dict[str, Any]] = []
    for source in sources:
        complement_ids = source.get("complementary_source_ids") or []
        if not complement_ids:
            continue
        matched = set(source["requested_jurisdiction_coverage"]["matched"])
        if requested_jurisdictions and not matched:
            continue
        primary_roles = set(source["roles"])
        primary_capabilities = _supported_capability_names(source)
        complements: list[dict[str, Any]] = []
        for complement_id in complement_ids:
            complement = sources_by_id.get(str(complement_id))
            if complement is None:
                continue
            complement_roles = set(complement["roles"])
            complement_capabilities = _supported_capability_names(complement)
            complements.append(
                {
                    "source_id": complement["source_id"],
                    "name": complement["name"],
                    "domain": complement["domain"],
                    "official_url": complement["official_url"],
                    "source_status": complement["source_status"],
                    "adapter_family": complement["adapter_family"],
                    "roles": sorted(complement_roles),
                    "supported_capabilities": sorted(complement_capabilities),
                    "adds_roles": sorted(complement_roles - primary_roles),
                    "adds_capabilities": sorted(
                        complement_capabilities - primary_capabilities
                    ),
                    "access_mode": complement["access"]["mode"],
                    "coverage_start": complement["coverage_start"],
                    "update_cadence": complement["update_cadence"],
                    "requested_jurisdiction_match": list(
                        complement["requested_jurisdiction_coverage"]["matched"]
                    ),
                    "record_identity_relation": (
                        "shared"
                        if complement["record_identity_source_id"]
                        == source["record_identity_source_id"]
                        else "independent"
                    ),
                }
            )
        if complements:
            groups.append(
                {
                    "primary_source_id": source["source_id"],
                    "primary_name": source["name"],
                    "primary_official_url": source["official_url"],
                    "primary_source_status": source["source_status"],
                    "primary_adapter_family": source["adapter_family"],
                    "primary_access_mode": source["access"]["mode"],
                    "primary_coverage_start": source["coverage_start"],
                    "primary_update_cadence": source["update_cadence"],
                    "primary_roles": sorted(primary_roles),
                    "primary_supported_capabilities": sorted(primary_capabilities),
                    "relationship_basis": "catalog_declared",
                    "complements": sorted(
                        complements,
                        key=lambda row: row["source_id"],
                    ),
                }
            )
    return sorted(groups, key=lambda row: row["primary_source_id"])


def _coverage_summary(
    sources: Sequence[Mapping[str, Any]],
    identity: Mapping[str, Any],
    workflow: Mapping[str, Any],
    complementary_routes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    domain_counts = Counter(source["domain"] for source in sources)
    mode_counts = Counter(source["access"]["mode"] for source in sources)
    capability_counts = Counter(
        capability["name"]
        for source in sources
        for capability in source["capabilities"]
        if capability["supported"]
    )
    requested_jurisdictions = [row["value"] for row in identity["jurisdictions"]]
    jurisdiction_rows = []
    for jurisdiction in requested_jurisdictions:
        matching_sources = [
            source["source_id"]
            for source in sources
            if jurisdiction in source["requested_jurisdiction_coverage"]["matched"]
        ]
        jurisdiction_rows.append(
            {
                "jurisdiction": jurisdiction,
                "catalog_source_ids": sorted(matching_sources),
            }
        )
    return {
        "catalog_source_count": len(sources),
        "sources_by_domain": dict(sorted(domain_counts.items())),
        "sources_by_access_mode": dict(sorted(mode_counts.items())),
        "supported_capability_counts": dict(sorted(capability_counts.items())),
        "requested_jurisdictions": jurisdiction_rows,
        "identity_selector_counts": {
            "names": len(identity["names"]),
            "addresses": len(identity["addresses"]),
            "related_entities": len(identity["related_entities"]),
        },
        "query_template_counts": {
            stage["stage_id"]: len(stage["tasks"]) for stage in workflow["stages"]
        },
        "complementary_route_group_count": len(complementary_routes),
    }


def _append_unresolved_notes(
    unresolved: list[dict[str, Any]],
    *,
    sources: Sequence[Mapping[str, Any]],
    identity: Mapping[str, Any],
    workflow: Mapping[str, Any],
) -> None:
    if not identity["jurisdictions"]:
        unresolved.append(
            {
                "code": "jurisdiction_not_supplied",
                "note": (
                    "No jurisdiction selector is available; local source coverage "
                    "remains broad."
                ),
            }
        )
    if not identity["addresses"]:
        unresolved.append(
            {
                "code": "address_not_available",
                "note": (
                    "No address selector is available for parcel or venue pivots."
                ),
            }
        )
    property_sources = [
        source for source in sources if source["domain"] in {"property", "mixed"}
    ]
    court_sources = [
        source for source in sources if source["domain"] in {"court", "mixed"}
    ]
    if not property_sources:
        unresolved.append(
            {
                "code": "property_catalog_coverage_empty",
                "note": "The catalog contains no property source.",
            }
        )
    if not court_sources:
        unresolved.append(
            {
                "code": "court_catalog_coverage_empty",
                "note": "The catalog contains no court source.",
            }
        )
    recorder_tasks = next(
        stage["tasks"]
        for stage in workflow["stages"]
        if stage["stage_id"] == "recorder"
    )
    if not recorder_tasks:
        unresolved.append(
            {
                "code": "recorder_query_template_unavailable",
                "note": (
                    "No catalogued property source currently declares a recorder "
                    "query capability."
                ),
            }
        )
    unreviewed = [
        source["source_id"]
        for source in sources
        if source["access"]["review_state"] == "unreviewed"
    ]
    if unreviewed:
        unresolved.append(
            {
                "code": "catalog_access_review_pending",
                "note": (
                    "These sources have manifest proposals but no current catalog "
                    "access review."
                ),
                "source_ids": sorted(unreviewed),
            }
        )
    requested = [row["value"] for row in identity["jurisdictions"]]
    uncovered = [
        jurisdiction
        for jurisdiction in requested
        if not any(
            jurisdiction in source["requested_jurisdiction_coverage"]["matched"]
            for source in sources
        )
    ]
    if uncovered:
        unresolved.append(
            {
                "code": "jurisdiction_catalog_match_unresolved",
                "note": (
                    "No catalog source declares matching coverage for these "
                    "jurisdiction selectors."
                ),
                "jurisdictions": sorted(uncovered, key=str.casefold),
            }
        )
    if requested:
        complement_gaps = [
            {
                "source_id": source["source_id"],
                "access_mode": source["access"]["mode"],
            }
            for source in sources
            if source["requested_jurisdiction_coverage"]["matched"]
            and source["access"]["mode"] not in {"allowed", "allowed_with_limits"}
            and not source.get("complementary_source_ids")
        ]
        if complement_gaps:
            unresolved.append(
                {
                    "code": "complementary_route_not_cataloged",
                    "note": (
                        "These jurisdiction-matched sources do not yet "
                        "declare an adjacent source or acquisition route. "
                        "Review official indexes, publications, archives, "
                        "record custodians, and useful account or data "
                        "products for partial coverage."
                    ),
                    "sources": sorted(
                        complement_gaps,
                        key=lambda row: row["source_id"],
                    ),
                }
            )


def build_search_plan(
    subject: str,
    *,
    aliases: Sequence[str] = (),
    addresses: Sequence[str] = (),
    related_entities: Sequence[str] = (),
    jurisdictions: Sequence[str] = (),
    after: str | None = None,
    before: str | None = None,
    catalog_db: str | Path = DEFAULT_CATALOG_DB,
    investigation_db: str | Path = DEFAULT_INVESTIGATION_DB,
    profile: str | None = None,
    profiles_dir: str | Path = DEFAULT_PROFILES_DIR,
) -> dict[str, Any]:
    """Build a canonical local search plan without contacting any source."""
    subject = _clean(subject)
    if not subject:
        raise SearchPlanError("subject must not be blank")
    after_date = _parse_date(after, "after")
    before_date = _parse_date(before, "before")
    if after_date and before_date and after_date > before_date:
        raise SearchPlanError("after must not be later than before")

    identity, context, unresolved = _load_identity_context(
        subject=subject,
        explicit_aliases=_sorted_unique(aliases),
        explicit_addresses=_sorted_unique(addresses),
        explicit_related_entities=_sorted_unique(related_entities),
        explicit_jurisdictions=_sorted_unique(jurisdictions),
        investigation_db=Path(investigation_db),
        profile_name=_clean(profile) if profile else None,
        profiles_dir=Path(profiles_dir),
    )
    requested_jurisdictions = [row["value"] for row in identity["jurisdictions"]]
    sources, catalog_notes = _load_catalog_sources(
        Path(catalog_db),
        requested_jurisdictions,
    )
    unresolved.extend(catalog_notes)
    date_bounds = {"after": after_date, "before": before_date}
    workflow = _build_workflow(sources, identity, date_bounds)
    complementary_routes = _complementary_routes(sources, identity)
    _append_unresolved_notes(
        unresolved,
        sources=sources,
        identity=identity,
        workflow=workflow,
    )
    unresolved.sort(
        key=lambda note: (
            str(note.get("code", "")),
            canonical_json(note),
        )
    )

    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "plan_type": "public_records_cross_domain_search",
        "identity": identity,
        "scope": {
            "date_bounds": date_bounds,
            "profile": context["profile"]["name"],
        },
        "context": context,
        "sources": sources,
        "workflow": workflow,
        "complementary_routes": complementary_routes,
        "coverage": _coverage_summary(
            sources,
            identity,
            workflow,
            complementary_routes,
        ),
        "unresolved": unresolved,
    }
    plan["fingerprint"] = hashlib.sha256(
        canonical_json(plan).encode("utf-8")
    ).hexdigest()
    return plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local, reproducible property-to-recorder-to-court search plan"
        )
    )
    parser.add_argument("subject")
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--address", action="append", default=[])
    parser.add_argument("--related-entity", action="append", default=[])
    parser.add_argument("--jurisdiction", action="append", default=[])
    parser.add_argument("--after", help="Lower ISO date bound (YYYY-MM-DD)")
    parser.add_argument("--before", help="Upper ISO date bound (YYYY-MM-DD)")
    parser.add_argument("--catalog-db", default=str(DEFAULT_CATALOG_DB))
    parser.add_argument(
        "--investigation-db",
        default=str(DEFAULT_INVESTIGATION_DB),
    )
    parser.add_argument("--profile", help="Investigation profile name")
    parser.add_argument(
        "--profiles-dir",
        default=str(DEFAULT_PROFILES_DIR),
        help=argparse.SUPPRESS,
    )
    add_output_args(parser)
    return parser


def _emit(plan: Mapping[str, Any], args: argparse.Namespace) -> None:
    payload = canonical_json(plan)
    if args.output:
        Path(args.output).write_text(payload + "\n")
        print(f"Search plan {plan['fingerprint']} saved to {args.output}")
        return
    if args.json_out:
        print(payload)
        return
    coverage = plan["coverage"]
    print(f"Search plan: {plan['identity']['canonical_name']}")
    print(f"Fingerprint: {plan['fingerprint']}")
    print(f"Catalog sources: {coverage['catalog_source_count']}")
    print(
        "Query templates: "
        + ", ".join(
            f"{stage}={count}"
            for stage, count in coverage["query_template_counts"].items()
        )
    )
    print(f"Unresolved notes: {len(plan['unresolved'])}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        plan = build_search_plan(
            args.subject,
            aliases=args.alias,
            addresses=args.address,
            related_entities=args.related_entity,
            jurisdictions=args.jurisdiction,
            after=args.after,
            before=args.before,
            catalog_db=args.catalog_db,
            investigation_db=args.investigation_db,
            profile=args.profile,
            profiles_dir=args.profiles_dir,
        )
    except SearchPlanError as error:
        parser.error(str(error))
    _emit(plan, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
