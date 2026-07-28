#!/usr/bin/env python3
"""Recompute and inspect nationwide public-record census priorities.

The tool preserves three independent planning dimensions:

* benefit reflects demand visible in the active investigation;
* feasibility reflects the strongest cataloged capability path; and
* risk reflects uncertainty and operational friction on that same path.

Each score is stored separately on ``source_census_targets``. The complete
component calculation is stored in ``priority_basis_json`` and every
recomputation appends a ``priority_recomputed`` census event.

Usage:
    uv run python tools/public_records_priority.py recompute --by analyst
    uv run python tools/public_records_priority.py metrics --json
    uv run python tools/public_records_priority.py explain 17 --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
        PublicRecordsCatalog,
        normalize_timestamp,
        utc_now,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH,
        PublicRecordsCatalog,
        normalize_timestamp,
        utc_now,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVESTIGATION_DB = PROJECT_ROOT / "investigation.db"
DEFAULT_INVESTIGATIONS_DIR = PROJECT_ROOT / "investigations"

ACTIVE_INFRA_STATUSES = frozenset({"open", "evaluating", "in_progress", "blocked"})
OPEN_LEAD_STATUSES = frozenset({"open"})

ADDRESS_POINTS = {"property": 10.0, "court": 5.0}
ADDRESS_CAP = 40.0
LEAD_POINTS = {
    "critical": 16.0,
    "high": 12.0,
    "medium": 8.0,
    "low": 4.0,
}
LEAD_CAP = 40.0
INFRA_POINTS = {
    "critical": 20.0,
    "high": 15.0,
    "medium": 10.0,
    "low": 5.0,
}
INFRA_CAP = 20.0

SOURCE_STATUS_FEASIBILITY = {
    "active": 20.0,
    "candidate": 10.0,
    "inactive": 3.0,
    "retired": 0.0,
}
ACCESS_FEASIBILITY = {
    "allowed": 20.0,
    "allowed_with_limits": 15.0,
    "unclear": 5.0,
    "prohibited": 0.0,
    "not_applicable": 0.0,
}
PROBE_FEASIBILITY = {
    "ok": 10.0,
    "no_results": 7.0,
    "partial": 6.0,
    "rate_limited": 4.0,
    "human_required": 2.0,
    "restricted": 2.0,
    "unavailable": 0.0,
    "terms_blocked": 0.0,
    "source_changed": 0.0,
    "error": 0.0,
}

SOURCE_STATUS_RISK = {
    "active": 0.0,
    "candidate": 5.0,
    "inactive": 10.0,
    "retired": 20.0,
}
ACCESS_CLASS_RISK = {
    "A": 2.0,
    "B": 5.0,
    "C": 20.0,
    "D": 10.0,
    "E": 15.0,
    "X": 25.0,
}
ACCESS_DISPOSITION_RISK = {
    "allowed": 0.0,
    "allowed_with_limits": 4.0,
    "unclear": 15.0,
    "prohibited": 20.0,
    "not_applicable": 10.0,
}
PROBE_RISK = {
    "ok": 0.0,
    "no_results": 2.0,
    "partial": 5.0,
    "rate_limited": 6.0,
    "human_required": 8.0,
    "restricted": 8.0,
    "source_changed": 10.0,
    "unavailable": 12.0,
    "error": 12.0,
    "terms_blocked": 15.0,
}

ROLE_ALIASES: dict[tuple[str, str], dict[str, frozenset[str]]] = {
    ("property", "assessment_roll"): {
        "roles": frozenset({"assessment", "appraisal", "assessment_roll", "sales"}),
        "capabilities": frozenset(
            {"search_owner", "search_address", "fetch_parcel", "search_sales"}
        ),
    },
    ("property", "parcel_geometry"): {
        "roles": frozenset({"parcel_geometry", "gis", "parcels"}),
        "capabilities": frozenset({"fetch_geometry", "search_parcels"}),
    },
    ("property", "tax_collection"): {
        "roles": frozenset({"tax_collection", "tax_status", "tax_sale"}),
        "capabilities": frozenset(
            {"search_tax_default", "search_tax_sale", "fetch_tax_status"}
        ),
    },
    ("property", "land_records_index"): {
        "roles": frozenset(
            {"land_records_index", "recorder", "instrument_index", "land_records"}
        ),
        "capabilities": frozenset(
            {"search_parties", "search_parcels", "fetch_instrument"}
        ),
    },
    ("court", "court_directory"): {
        "roles": frozenset({"court_directory", "court", "clerk", "court_administration"}),
        "capabilities": frozenset({"list_courts", "search_courts"}),
    },
    ("court", "trial_case_index"): {
        "roles": frozenset(
            {
                "trial_case_index",
                "case_metadata",
                "document_portal",
                "court",
            }
        ),
        "capabilities": frozenset(
            {"search_cases", "list_docket_entries", "fetch_document"}
        ),
    },
    ("court", "appellate_opinions"): {
        "roles": frozenset(
            {"appellate_opinions", "opinion_archive", "legal_aggregator"}
        ),
        "capabilities": frozenset({"search_opinions", "fetch_opinion"}),
    },
    ("court", "bulk_data_program"): {
        "roles": frozenset(
            {
                "bulk_data_program",
                "court_administration",
                "case_metadata",
            }
        ),
        "capabilities": frozenset({"sync", "bulk_download", "apply_deletions"}),
    },
}

PROPERTY_KEYWORDS = frozenset(
    {
        "assessor",
        "assessment",
        "deed",
        "foreclosure",
        "gis",
        "land record",
        "lien",
        "mortgage",
        "parcel",
        "property",
        "recorder",
        "tax sale",
        "title",
    }
)
COURT_KEYWORDS = frozenset(
    {
        "appeal",
        "appellate",
        "case",
        "clerk",
        "court",
        "docket",
        "filing",
        "judgment",
        "lawsuit",
        "litigation",
        "opinion",
    }
)
ROLE_KEYWORDS: dict[str, frozenset[str]] = {
    "assessment_roll": frozenset({"assessment", "assessor", "appraisal", "valuation"}),
    "parcel_geometry": frozenset({"gis", "geometry", "map", "parcel boundary"}),
    "tax_collection": frozenset(
        {"delinquent tax", "tax collection", "tax lien", "tax sale"}
    ),
    "land_records_index": frozenset(
        {"deed", "instrument", "land record", "mortgage", "recorder", "title"}
    ),
    "court_directory": frozenset({"clerk directory", "court directory"}),
    "trial_case_index": frozenset(
        {"case", "docket", "filing", "judgment", "lawsuit", "litigation"}
    ),
    "appellate_opinions": frozenset({"appeal", "appellate", "opinion"}),
    "bulk_data_program": frozenset(
        {"api", "bulk data", "bulk download", "data feed", "subscription"}
    ),
}


class PriorityError(RuntimeError):
    """Raised when priority inputs or catalog state cannot be evaluated."""


@dataclass(frozen=True)
class DemandInputs:
    profile_name: str
    primary_subject: str
    known_addresses: tuple[dict[str, Any], ...]
    open_leads: tuple[dict[str, Any], ...]
    active_infra_requests: tuple[dict[str, Any], ...]
    unmatched_addresses: tuple[str, ...]
    input_fingerprint: str


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(db, table):
        return set()
    return {str(row["name"]) for row in db.execute(f"PRAGMA table_info({table})")}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.casefold()
    for keyword in keywords:
        escaped = re.escape(keyword.casefold()).replace(r"\ ", r"\s+")
        if re.search(rf"(?<!\w){escaped}(?!\w)", lowered):
            return True
    return False


def _scope_for_text(
    text: str,
    *,
    category: str | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    lowered = text.casefold()
    domains: set[str] = set()
    if category == "legal" or _contains_any(lowered, COURT_KEYWORDS):
        domains.add("court")
    if _contains_any(lowered, PROPERTY_KEYWORDS):
        domains.add("property")
    if not domains:
        domains.update({"property", "court"})

    roles = {
        role
        for role, keywords in ROLE_KEYWORDS.items()
        if _contains_any(lowered, keywords)
    }
    return frozenset(domains), frozenset(roles)


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return round(float(ordered[index]), 2)


def _dimension_summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "p25": 0.0,
            "p75": 0.0,
            "zero_count": 0,
        }
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "mean": round(statistics.fmean(values), 2),
        "median": round(statistics.median(values), 2),
        "p25": _percentile(values, 0.25),
        "p75": _percentile(values, 0.75),
        "zero_count": sum(value == 0 for value in values),
    }


class PublicRecordsPriority:
    """Demand-aware scoring and metrics over the nationwide census."""

    def __init__(
        self,
        catalog_db: str | Path = DEFAULT_DB_PATH,
        *,
        investigation_db: str | Path = DEFAULT_INVESTIGATION_DB,
        investigations_dir: str | Path = DEFAULT_INVESTIGATIONS_DIR,
    ):
        self.catalog_db = Path(catalog_db)
        self.investigation_db = Path(investigation_db)
        self.investigations_dir = Path(investigations_dir)
        PublicRecordsCatalog(self.catalog_db)

    def _catalog_connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.catalog_db), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _investigation_connect(self) -> sqlite3.Connection:
        if not self.investigation_db.exists():
            raise PriorityError(
                f"investigation database not found: {self.investigation_db}"
            )
        db = sqlite3.connect(str(self.investigation_db), timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _active_profile_name(self, requested: str | None) -> str:
        if requested:
            return requested
        db = self._investigation_connect()
        try:
            if not _table_exists(db, "investigation_config"):
                raise PriorityError(
                    "active profile is unavailable; pass --profile explicitly"
                )
            row = db.execute(
                "SELECT value FROM investigation_config WHERE key='active_profile'"
            ).fetchone()
        finally:
            db.close()
        if row is None or not str(row["value"]).strip():
            raise PriorityError(
                "active profile is unavailable; pass --profile explicitly"
            )
        return str(row["value"]).strip()

    def _profile_data(self, profile_name: str) -> dict[str, Any]:
        path = self.investigations_dir / profile_name / "config.yaml"
        if not path.exists():
            raise PriorityError(f"profile config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise PriorityError(f"profile config must be a mapping: {path}")
        return dict(data)

    @staticmethod
    def _jurisdiction_patterns(
        jurisdictions: Sequence[sqlite3.Row],
    ) -> dict[str, tuple[re.Pattern[str], ...]]:
        patterns: dict[str, tuple[re.Pattern[str], ...]] = {}
        for row in jurisdictions:
            state = str(row["subdivision_code"] or "").upper()
            name = str(row["jurisdiction_name"])
            if not state:
                continue
            patterns[state] = (
                re.compile(rf"(?<![A-Za-z]){re.escape(state)}(?![A-Za-z])"),
                re.compile(
                    rf",\s*{re.escape(state.casefold())}(?![a-z])",
                    re.IGNORECASE,
                ),
                re.compile(
                    rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])",
                    re.IGNORECASE,
                ),
            )
        return patterns

    @staticmethod
    def _mentioned_states(
        text: str,
        patterns: Mapping[str, Sequence[re.Pattern[str]]],
    ) -> frozenset[str]:
        states: set[str] = set()
        for state, state_patterns in patterns.items():
            if any(pattern.search(text) for pattern in state_patterns):
                states.add(state)
        return frozenset(states)

    def _load_demand_inputs(
        self,
        *,
        profile_name: str,
        jurisdictions: Sequence[sqlite3.Row],
    ) -> DemandInputs:
        profile = self._profile_data(profile_name)
        patterns = self._jurisdiction_patterns(jurisdictions)
        raw_addresses = profile.get("known_addresses") or {}
        if isinstance(raw_addresses, Mapping):
            address_items = list(raw_addresses.items())
        elif isinstance(raw_addresses, list):
            address_items = [(item, "") for item in raw_addresses]
        else:
            raise PriorityError("profile known_addresses must be a mapping or list")

        addresses: list[dict[str, Any]] = []
        unmatched: list[str] = []
        for address, description in address_items:
            address_text = str(address)
            description_text = str(description or "")
            states = sorted(
                self._mentioned_states(
                    f"{address_text}\n{description_text}",
                    patterns,
                )
            )
            item = {
                "address": address_text,
                "description": description_text,
                "states": states,
            }
            addresses.append(item)
            if not states:
                unmatched.append(address_text)

        db = self._investigation_connect()
        try:
            lead_columns = _columns(db, "leads")
            leads: list[dict[str, Any]] = []
            if lead_columns:
                select_columns = [
                    name
                    for name in (
                        "id",
                        "title",
                        "description",
                        "category",
                        "priority",
                        "source",
                        "target_name",
                        "findings",
                        "profile_id",
                        "status",
                    )
                    if name in lead_columns
                ]
                clauses = ["status IN ({})".format(",".join("?" for _ in OPEN_LEAD_STATUSES))]
                params: list[Any] = list(sorted(OPEN_LEAD_STATUSES))
                if "profile_id" in lead_columns:
                    clauses.append("profile_id=?")
                    params.append(profile_name)
                rows = db.execute(
                    f"""
                    SELECT {", ".join(select_columns)}
                    FROM leads
                    WHERE {" AND ".join(clauses)}
                    ORDER BY id
                    """,
                    params,
                ).fetchall()
                for row in rows:
                    item = dict(row)
                    text = "\n".join(
                        str(item.get(field) or "")
                        for field in (
                            "title",
                            "description",
                            "source",
                            "target_name",
                            "findings",
                        )
                    )
                    domains, roles = _scope_for_text(
                        text,
                        category=str(item.get("category") or ""),
                    )
                    item["states"] = sorted(self._mentioned_states(text, patterns))
                    item["domains"] = sorted(domains)
                    item["roles"] = sorted(roles)
                    leads.append(item)

            infra_columns = _columns(db, "infra_requests")
            infra: list[dict[str, Any]] = []
            if infra_columns:
                select_columns = [
                    name
                    for name in (
                        "id",
                        "title",
                        "description",
                        "priority",
                        "status",
                        "source_name",
                        "source_url",
                        "data_type",
                        "access_method",
                        "estimated_coverage",
                        "related_lead_id",
                    )
                    if name in infra_columns
                ]
                rows = db.execute(
                    f"""
                    SELECT {", ".join(select_columns)}
                    FROM infra_requests
                    WHERE status IN (
                        {",".join("?" for _ in ACTIVE_INFRA_STATUSES)}
                    )
                    ORDER BY id
                    """,
                    sorted(ACTIVE_INFRA_STATUSES),
                ).fetchall()
                for row in rows:
                    item = dict(row)
                    text = "\n".join(
                        str(item.get(field) or "")
                        for field in (
                            "title",
                            "description",
                            "source_name",
                            "source_url",
                            "data_type",
                            "estimated_coverage",
                        )
                    )
                    domains, roles = _scope_for_text(text)
                    item["states"] = sorted(self._mentioned_states(text, patterns))
                    item["domains"] = sorted(domains)
                    item["roles"] = sorted(roles)
                    infra.append(item)
        finally:
            db.close()

        fingerprint_payload = {
            "profile_name": profile_name,
            "primary_subject": str(profile.get("primary_subject") or ""),
            "known_addresses": addresses,
            "open_leads": leads,
            "active_infra_requests": infra,
        }
        fingerprint = hashlib.sha256(
            _json_dump(fingerprint_payload).encode("utf-8")
        ).hexdigest()
        return DemandInputs(
            profile_name=profile_name,
            primary_subject=str(profile.get("primary_subject") or ""),
            known_addresses=tuple(addresses),
            open_leads=tuple(leads),
            active_infra_requests=tuple(infra),
            unmatched_addresses=tuple(unmatched),
            input_fingerprint=fingerprint,
        )

    @staticmethod
    def _signal_applies(
        signal: Mapping[str, Any],
        *,
        state: str,
        domain: str,
        role: str,
    ) -> bool:
        if state not in signal.get("states", ()):
            return False
        domains = set(signal.get("domains", ()))
        if domains and domain not in domains:
            return False
        roles = set(signal.get("roles", ()))
        return not roles or role in roles

    @staticmethod
    def _benefit_basis(
        target: Mapping[str, Any],
        demand: DemandInputs,
    ) -> tuple[float, dict[str, Any]]:
        state = str(target["subdivision_code"])
        domain = str(target["domain"])
        role = str(target["role"])

        address_matches: list[dict[str, Any]] = []
        if domain == "property" or role in {"court_directory", "trial_case_index"}:
            for item in demand.known_addresses:
                if state in item["states"]:
                    address_matches.append(
                        {
                            "address": item["address"],
                            "points": ADDRESS_POINTS[domain],
                        }
                    )
        address_raw = sum(item["points"] for item in address_matches)
        address_score = min(ADDRESS_CAP, address_raw)

        lead_matches: list[dict[str, Any]] = []
        for item in demand.open_leads:
            if not PublicRecordsPriority._signal_applies(
                item,
                state=state,
                domain=domain,
                role=role,
            ):
                continue
            priority = str(item.get("priority") or "medium").lower()
            points = LEAD_POINTS.get(priority, LEAD_POINTS["medium"])
            lead_matches.append(
                {
                    "lead_id": item.get("id"),
                    "priority": priority,
                    "title": str(item.get("title") or ""),
                    "points": points,
                    "domains": item.get("domains", []),
                    "roles": item.get("roles", []),
                }
            )
        lead_raw = sum(item["points"] for item in lead_matches)
        lead_score = min(LEAD_CAP, lead_raw)

        infra_matches: list[dict[str, Any]] = []
        for item in demand.active_infra_requests:
            if not PublicRecordsPriority._signal_applies(
                item,
                state=state,
                domain=domain,
                role=role,
            ):
                continue
            priority = str(item.get("priority") or "medium").lower()
            points = INFRA_POINTS.get(priority, INFRA_POINTS["medium"])
            infra_matches.append(
                {
                    "infra_request_id": item.get("id"),
                    "priority": priority,
                    "status": item.get("status"),
                    "title": str(item.get("title") or ""),
                    "points": points,
                    "domains": item.get("domains", []),
                    "roles": item.get("roles", []),
                }
            )
        infra_raw = sum(item["points"] for item in infra_matches)
        infra_score = min(INFRA_CAP, infra_raw)

        score = min(100.0, address_score + lead_score + infra_score)
        return score, {
            "score": score,
            "components": {
                "known_addresses": {
                    "score": address_score,
                    "raw_points": address_raw,
                    "cap": ADDRESS_CAP,
                    "points_per_match": ADDRESS_POINTS[domain],
                    "matches": address_matches,
                },
                "open_leads": {
                    "score": lead_score,
                    "raw_points": lead_raw,
                    "cap": LEAD_CAP,
                    "points_by_priority": LEAD_POINTS,
                    "matches": lead_matches,
                },
                "active_infra_requests": {
                    "score": infra_score,
                    "raw_points": infra_raw,
                    "cap": INFRA_CAP,
                    "points_by_priority": INFRA_POINTS,
                    "matches": infra_matches,
                },
            },
        }

    @staticmethod
    def _source_inventory(db: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        sources: dict[str, dict[str, Any]] = {}
        for row in db.execute("SELECT * FROM sources ORDER BY source_id"):
            item = dict(row)
            item["roles"] = set()
            item["capabilities"] = set()
            item["jurisdictions"] = []
            item["access_review"] = None
            item["probe"] = None
            sources[str(row["source_id"])] = item

        for row in db.execute("SELECT source_id, role FROM source_roles"):
            if row["source_id"] in sources:
                sources[row["source_id"]]["roles"].add(str(row["role"]))
        for row in db.execute(
            "SELECT source_id, capability FROM capabilities WHERE supported=1"
        ):
            if row["source_id"] in sources:
                sources[row["source_id"]]["capabilities"].add(
                    str(row["capability"])
                )
        for row in db.execute(
            """
            SELECT sj.source_id, j.jurisdiction_id, j.country_code, j.geoid,
                   j.kind, j.subdivision_code
            FROM source_jurisdictions sj
            JOIN jurisdictions j USING(jurisdiction_id)
            """
        ):
            if row["source_id"] in sources:
                sources[row["source_id"]]["jurisdictions"].append(dict(row))

        for row in db.execute(
            """
            SELECT ar.*
            FROM access_reviews ar
            WHERE ar.access_review_id = (
                SELECT MAX(ar2.access_review_id)
                FROM access_reviews ar2
                WHERE ar2.source_id=ar.source_id
            )
            """
        ):
            if row["source_id"] in sources:
                sources[row["source_id"]]["access_review"] = dict(row)
        for row in db.execute(
            """
            SELECT p.*
            FROM probes p
            WHERE p.probe_id = (
                SELECT MAX(p2.probe_id)
                FROM probes p2
                WHERE p2.source_id=p.source_id
            )
            """
        ):
            if row["source_id"] in sources:
                sources[row["source_id"]]["probe"] = dict(row)
        return sources

    @staticmethod
    def _coverage_kind(
        source: Mapping[str, Any],
        target: Mapping[str, Any],
    ) -> str | None:
        target_geoid = str(target.get("geoid") or "")
        for jurisdiction in source["jurisdictions"]:
            if jurisdiction["jurisdiction_id"] == target["jurisdiction_id"]:
                return "jurisdiction"
            source_geoid = str(jurisdiction.get("geoid") or "")
            if (
                len(target_geoid) == 2
                and len(source_geoid) > 2
                and source_geoid.startswith(target_geoid)
            ):
                return "subjurisdiction"
            if (
                jurisdiction["country_code"] == "US"
                and (
                    jurisdiction["geoid"] == "US"
                    or jurisdiction["kind"] == "country"
                )
            ):
                return "nationwide"
        return None

    @staticmethod
    def _role_evidence(
        source: Mapping[str, Any],
        *,
        domain: str,
        role: str,
        directly_linked: bool,
        coverage_kind: str,
    ) -> tuple[float, dict[str, Any]] | None:
        source_roles = set(source["roles"])
        capabilities = set(source["capabilities"])
        aliases = ROLE_ALIASES.get((domain, role), {"roles": set(), "capabilities": set()})
        exact_roles = sorted(source_roles & {role})
        alias_roles = sorted(source_roles & set(aliases["roles"]))
        capability_matches = sorted(capabilities & set(aliases["capabilities"]))
        capability_establishes_coverage = coverage_kind != "nationwide"
        if directly_linked or exact_roles:
            points = 20.0
        elif alias_roles or (
            capability_establishes_coverage and capability_matches
        ):
            points = 15.0
        else:
            return None
        return points, {
            "direct_target_link": directly_linked,
            "exact_roles": exact_roles,
            "alias_roles": alias_roles,
            "capabilities": capability_matches,
            "capability_establishes_coverage": capability_establishes_coverage,
        }

    @staticmethod
    def _verification_risk(
        source: Mapping[str, Any],
        *,
        as_of: datetime,
    ) -> tuple[float, dict[str, Any]]:
        probe = source["probe"]
        timestamps = [
            parsed
            for parsed in (
                _parse_time(source.get("last_verified_at")),
                _parse_time(probe.get("probed_at") if probe else None),
            )
            if parsed is not None
        ]
        if not timestamps:
            return 8.0, {"latest_verification": None, "age_days": None}
        latest = max(timestamps)
        age_days = max(0, (as_of - latest).days)
        if age_days <= 90:
            points = 0.0
        elif age_days <= 365:
            points = 4.0
        else:
            points = 8.0
        return points, {
            "latest_verification": latest.isoformat().replace("+00:00", "Z"),
            "age_days": age_days,
        }

    @classmethod
    def _assess_source(
        cls,
        source: Mapping[str, Any],
        target: Mapping[str, Any],
        *,
        coverage_kind: str,
        role_points: float,
        role_evidence: Mapping[str, Any],
        as_of: datetime,
    ) -> dict[str, Any]:
        source_status = str(source["source_status"])
        status_feasibility = SOURCE_STATUS_FEASIBILITY.get(source_status, 0.0)
        adapter_feasibility = (
            15.0
            if source.get("adapter_family") and source.get("adapter_version")
            else 10.0
            if source.get("adapter_family")
            else 0.0
        )
        review = source["access_review"]
        disposition = (
            str(review["automation_disposition"]) if review is not None else None
        )
        review_valid_until = (
            _parse_time(review.get("valid_until")) if review is not None else None
        )
        review_expired = bool(review_valid_until and review_valid_until < as_of)
        access_feasibility = (
            ACCESS_FEASIBILITY.get(disposition, 0.0)
            if disposition is not None and not review_expired
            else 0.0
        )
        probe = source["probe"]
        probe_status = str(probe["status"]) if probe is not None else None
        probe_feasibility = (
            PROBE_FEASIBILITY.get(probe_status, 0.0)
            if probe_status is not None
            else 0.0
        )
        feasibility_components = {
            "jurisdiction_coverage": {
                "score": 15.0,
                "kind": coverage_kind,
            },
            "role_capability_evidence": {
                "score": role_points,
                **dict(role_evidence),
            },
            "source_status": {
                "score": status_feasibility,
                "value": source_status,
            },
            "adapter": {
                "score": adapter_feasibility,
                "family": source.get("adapter_family"),
                "version": source.get("adapter_version"),
            },
            "access_review": {
                "score": access_feasibility,
                "access_class": (
                    str(review["access_class"]) if review is not None else None
                ),
                "automation_disposition": disposition,
                "review_id": (
                    int(review["access_review_id"]) if review is not None else None
                ),
                "valid_until": (
                    review_valid_until.isoformat().replace("+00:00", "Z")
                    if review_valid_until is not None
                    else None
                ),
                "expired": review_expired,
            },
            "latest_probe": {
                "score": probe_feasibility,
                "status": probe_status,
                "probe_id": int(probe["probe_id"]) if probe is not None else None,
            },
        }
        feasibility = min(
            100.0,
            sum(component["score"] for component in feasibility_components.values()),
        )

        source_status_risk = SOURCE_STATUS_RISK.get(source_status, 10.0)
        if review is None:
            access_class_risk = 30.0
            disposition_risk = 0.0
            contract_risk = 0.0
            access_class = None
        else:
            access_class = str(review["access_class"])
            access_class_risk = ACCESS_CLASS_RISK.get(access_class, 20.0)
            disposition_risk = ACCESS_DISPOSITION_RISK.get(disposition, 15.0)
            contract_risk = (
                10.0
                if access_class == "D" and not bool(review["contract_verified"])
                else 0.0
            )
        review_validity_risk = 10.0 if review_expired else 0.0
        probe_risk = (
            PROBE_RISK.get(probe_status, 10.0) if probe_status is not None else 8.0
        )
        verification_risk, verification_details = cls._verification_risk(
            source,
            as_of=as_of,
        )
        risk_components = {
            "source_status": {
                "score": source_status_risk,
                "value": source_status,
            },
            "access_class_or_review_gap": {
                "score": access_class_risk,
                "access_class": access_class,
                "review_id": (
                    int(review["access_review_id"]) if review is not None else None
                ),
            },
            "access_disposition": {
                "score": disposition_risk,
                "value": disposition,
            },
            "contract_state": {
                "score": contract_risk,
                "verified": (
                    bool(review["contract_verified"]) if review is not None else None
                ),
            },
            "review_validity": {
                "score": review_validity_risk,
                "valid_until": (
                    review_valid_until.isoformat().replace("+00:00", "Z")
                    if review_valid_until is not None
                    else None
                ),
                "expired": review_expired,
            },
            "latest_probe": {
                "score": probe_risk,
                "status": probe_status,
                "probe_id": int(probe["probe_id"]) if probe is not None else None,
            },
            "verification_age": {
                "score": verification_risk,
                **verification_details,
            },
        }
        risk = min(
            100.0,
            sum(component["score"] for component in risk_components.values()),
        )
        return {
            "source_id": source["source_id"],
            "source_name": source["name"],
            "target_domain": target["domain"],
            "target_role": target["role"],
            "feasibility_score": feasibility,
            "risk_score": risk,
            "feasibility_components": feasibility_components,
            "risk_components": risk_components,
        }

    @classmethod
    def _source_basis(
        cls,
        target: Mapping[str, Any],
        sources: Mapping[str, Mapping[str, Any]],
        *,
        as_of: datetime,
    ) -> tuple[float, float, dict[str, Any], dict[str, Any]]:
        assessments: list[dict[str, Any]] = []
        direct_source_ids = {
            str(source_id)
            for source_id in target.get("source_ids", [])
            if source_id
        }
        if target.get("source_id"):
            direct_source_ids.add(str(target["source_id"]))
        for source_id, source in sources.items():
            if source["domain"] not in {target["domain"], "mixed"}:
                continue
            coverage_kind = cls._coverage_kind(source, target)
            directly_linked = source_id in direct_source_ids
            if coverage_kind is None and not directly_linked:
                continue
            role_match = cls._role_evidence(
                source,
                domain=str(target["domain"]),
                role=str(target["role"]),
                directly_linked=directly_linked,
                coverage_kind=coverage_kind or "direct_target_link",
            )
            if role_match is None:
                continue
            role_points, evidence = role_match
            assessments.append(
                cls._assess_source(
                    source,
                    target,
                    coverage_kind=coverage_kind or "direct_target_link",
                    role_points=role_points,
                    role_evidence=evidence,
                    as_of=as_of,
                )
            )

        assessments.sort(
            key=lambda item: (
                -item["feasibility_score"],
                item["risk_score"],
                item["source_id"],
            )
        )
        if not assessments:
            feasibility_basis = {
                "score": 0.0,
                "selected_source_id": None,
                "selection_order": [
                    "feasibility_desc",
                    "risk_asc",
                    "source_id_asc",
                ],
                "candidate_sources": [],
                "components": {
                    "catalog_capability_path": {
                        "score": 0.0,
                        "evidence": "none_cataloged",
                    }
                },
            }
            risk_basis = {
                "score": 25.0,
                "selected_source_id": None,
                "components": {
                    "catalog_evidence_gap": {
                        "score": 25.0,
                        "evidence": "no_matching_source_capability",
                    }
                },
            }
            return 0.0, 25.0, feasibility_basis, risk_basis

        selected = assessments[0]
        feasibility = float(selected["feasibility_score"])
        risk = float(selected["risk_score"])
        candidate_summary = [
            {
                "source_id": item["source_id"],
                "feasibility_score": item["feasibility_score"],
                "risk_score": item["risk_score"],
            }
            for item in assessments
        ]
        feasibility_basis = {
            "score": feasibility,
            "selected_source_id": selected["source_id"],
            "selection_order": [
                "feasibility_desc",
                "risk_asc",
                "source_id_asc",
            ],
            "candidate_sources": candidate_summary,
            "components": selected["feasibility_components"],
        }
        risk_basis = {
            "score": risk,
            "selected_source_id": selected["source_id"],
            "components": selected["risk_components"],
        }
        return feasibility, risk, feasibility_basis, risk_basis

    def recompute(
        self,
        *,
        actor: str,
        profile_name: str | None = None,
        dry_run: bool = False,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Recompute every census target and optionally persist the result."""
        if not actor.strip():
            raise PriorityError("actor must not be blank")
        normalized_as_of = normalize_timestamp(as_of or utc_now(), "as_of")
        as_of_dt = _parse_time(normalized_as_of)
        assert as_of_dt is not None
        profile_name = self._active_profile_name(profile_name)

        db = self._catalog_connect()
        try:
            targets = db.execute(
                """
                SELECT t.*, j.name AS jurisdiction_name, j.geoid,
                       j.subdivision_code
                FROM source_census_targets t
                JOIN jurisdictions j USING(jurisdiction_id)
                ORDER BY t.census_target_id
                """
            ).fetchall()
            if not targets:
                raise PriorityError(
                    "source census is empty; seed it before recomputing priorities"
                )
            jurisdictions = db.execute(
                """
                SELECT jurisdiction_id, name AS jurisdiction_name,
                       subdivision_code, geoid
                FROM jurisdictions
                WHERE country_code='US'
                  AND kind='state_equivalent'
                ORDER BY subdivision_code
                """
            ).fetchall()
            sources = self._source_inventory(db)
            target_source_rows = db.execute(
                """
                SELECT census_target_id, source_id
                FROM source_census_target_sources
                ORDER BY census_target_id, source_id
                """
            ).fetchall()
        finally:
            db.close()

        target_sources: dict[int, list[str]] = {}
        for association in target_source_rows:
            target_sources.setdefault(
                int(association["census_target_id"]),
                [],
            ).append(str(association["source_id"]))

        demand = self._load_demand_inputs(
            profile_name=profile_name,
            jurisdictions=jurisdictions,
        )
        run_material = {
            "as_of": normalized_as_of,
            "profile": profile_name,
            "input_fingerprint": demand.input_fingerprint,
            "catalog_sources": sorted(sources),
            "target_source_associations": [
                [target_id, source_id]
                for target_id, source_ids in sorted(target_sources.items())
                for source_id in source_ids
            ],
        }
        run_id = "priority-" + hashlib.sha256(
            _json_dump(run_material).encode("utf-8")
        ).hexdigest()[:16]

        calculations: list[dict[str, Any]] = []
        for row in targets:
            target = dict(row)
            target["source_ids"] = target_sources.get(
                int(target["census_target_id"]),
                [],
            )
            benefit, benefit_basis = self._benefit_basis(target, demand)
            (
                feasibility,
                risk,
                feasibility_basis,
                risk_basis,
            ) = self._source_basis(target, sources, as_of=as_of_dt)
            basis = {
                "schema_version": 1,
                "run_id": run_id,
                "as_of": normalized_as_of,
                "profile": {
                    "name": demand.profile_name,
                    "primary_subject": demand.primary_subject,
                },
                "input_fingerprint": demand.input_fingerprint,
                "dimensions": {
                    "benefit": benefit_basis,
                    "feasibility": feasibility_basis,
                    "risk": risk_basis,
                },
            }
            old_basis = json.loads(target["priority_basis_json"] or "{}")
            changed = (
                float(target["benefit_score"]) != benefit
                or float(target["feasibility_score"]) != feasibility
                or float(target["risk_score"]) != risk
                or old_basis != basis
            )
            calculations.append(
                {
                    "census_target_id": int(target["census_target_id"]),
                    "state": target["subdivision_code"],
                    "domain": target["domain"],
                    "role": target["role"],
                    "status": target["status"],
                    "benefit_score": benefit,
                    "feasibility_score": feasibility,
                    "risk_score": risk,
                    "priority_basis": basis,
                    "changed": changed,
                    "old_scores": {
                        "benefit": float(target["benefit_score"]),
                        "feasibility": float(target["feasibility_score"]),
                        "risk": float(target["risk_score"]),
                    },
                }
            )

        if not dry_run:
            recorded_at = utc_now()
            db = self._catalog_connect()
            try:
                db.execute("BEGIN IMMEDIATE")
                for item in calculations:
                    target_id = item["census_target_id"]
                    db.execute(
                        """
                        UPDATE source_census_targets
                        SET benefit_score=?, feasibility_score=?, risk_score=?,
                            priority_basis_json=?, updated_at=?
                        WHERE census_target_id=?
                        """,
                        (
                            item["benefit_score"],
                            item["feasibility_score"],
                            item["risk_score"],
                            _json_dump(item["priority_basis"]),
                            recorded_at,
                            target_id,
                        ),
                    )
                    db.execute(
                        """
                        INSERT INTO source_census_events(
                            census_target_id, event_type, actor, from_status,
                            to_status, details_json, recorded_at
                        ) VALUES(?,?,?,?,?,?,?)
                        """,
                        (
                            target_id,
                            "priority_recomputed",
                            actor.strip(),
                            item["status"],
                            item["status"],
                            _json_dump(
                                {
                                    "run_id": run_id,
                                    "as_of": normalized_as_of,
                                    "profile_name": profile_name,
                                    "input_fingerprint": demand.input_fingerprint,
                                    "changed": item["changed"],
                                    "old_scores": item["old_scores"],
                                    "new_scores": {
                                        "benefit": item["benefit_score"],
                                        "feasibility": item["feasibility_score"],
                                        "risk": item["risk_score"],
                                    },
                                }
                            ),
                            recorded_at,
                        ),
                    )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        return {
            "run_id": run_id,
            "as_of": normalized_as_of,
            "profile_name": profile_name,
            "dry_run": dry_run,
            "targets_evaluated": len(calculations),
            "targets_changed": sum(item["changed"] for item in calculations),
            "demand_inputs": {
                "known_addresses": len(demand.known_addresses),
                "known_addresses_with_state": (
                    len(demand.known_addresses) - len(demand.unmatched_addresses)
                ),
                "unmatched_addresses": list(demand.unmatched_addresses),
                "open_leads": len(demand.open_leads),
                "active_infra_requests": len(demand.active_infra_requests),
                "input_fingerprint": demand.input_fingerprint,
            },
            "score_dimensions": {
                "benefit": _dimension_summary(
                    [item["benefit_score"] for item in calculations]
                ),
                "feasibility": _dimension_summary(
                    [item["feasibility_score"] for item in calculations]
                ),
                "risk": _dimension_summary(
                    [item["risk_score"] for item in calculations]
                ),
            },
        }

    @staticmethod
    def _pareto_frontier(rows: Sequence[Mapping[str, Any]]) -> list[int]:
        frontier: list[int] = []
        for candidate in rows:
            dominated = False
            for other in rows:
                if other["census_target_id"] == candidate["census_target_id"]:
                    continue
                at_least_as_good = (
                    other["benefit_score"] >= candidate["benefit_score"]
                    and other["feasibility_score"] >= candidate["feasibility_score"]
                    and other["risk_score"] <= candidate["risk_score"]
                )
                strictly_better = (
                    other["benefit_score"] > candidate["benefit_score"]
                    or other["feasibility_score"] > candidate["feasibility_score"]
                    or other["risk_score"] < candidate["risk_score"]
                )
                if at_least_as_good and strictly_better:
                    dominated = True
                    break
            if not dominated:
                frontier.append(int(candidate["census_target_id"]))
        return frontier

    def metrics(self) -> dict[str, Any]:
        """Return score distributions and a non-aggregated Pareto frontier."""
        db = self._catalog_connect()
        try:
            rows = [
                dict(row)
                for row in db.execute(
                    """
                    SELECT t.census_target_id, t.domain, t.role, t.status,
                           t.benefit_score, t.feasibility_score, t.risk_score,
                           t.priority_basis_json, j.subdivision_code AS state
                    FROM source_census_targets t
                    JOIN jurisdictions j USING(jurisdiction_id)
                    ORDER BY t.census_target_id
                    """
                )
            ]
            source_status_counts = {
                str(row["source_status"]): int(row["count"])
                for row in db.execute(
                    """
                    SELECT source_status, COUNT(*) AS count
                    FROM sources GROUP BY source_status ORDER BY source_status
                    """
                )
            }
            access_rows = db.execute(
                """
                SELECT ar.access_class, ar.automation_disposition
                FROM access_reviews ar
                WHERE ar.access_review_id = (
                    SELECT MAX(ar2.access_review_id)
                    FROM access_reviews ar2
                    WHERE ar2.source_id=ar.source_id
                )
                """
            ).fetchall()
            probe_rows = db.execute(
                """
                SELECT p.status
                FROM probes p
                WHERE p.probe_id = (
                    SELECT MAX(p2.probe_id)
                    FROM probes p2
                    WHERE p2.source_id=p.source_id
                )
                """
            ).fetchall()
        finally:
            db.close()

        by_domain: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: {"benefit": [], "feasibility": [], "risk": []}
        )
        by_capability: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "targets": 0,
                "with_catalog_capability_path": 0,
                "with_demand_signal": 0,
                "benefit": [],
                "feasibility": [],
                "risk": [],
            }
        )
        by_status: dict[str, int] = defaultdict(int)
        demand_signal_counts = {
            "known_addresses": 0,
            "open_leads": 0,
            "active_infra_requests": 0,
        }
        targets_with_source_path = 0
        recomputed_targets = 0
        for row in rows:
            by_status[str(row["status"])] += 1
            for dimension in ("benefit", "feasibility", "risk"):
                by_domain[str(row["domain"])][dimension].append(
                    float(row[f"{dimension}_score"])
                )
            capability_key = f"{row['domain']}.{row['role']}"
            capability = by_capability[capability_key]
            capability["targets"] += 1
            for dimension in ("benefit", "feasibility", "risk"):
                capability[dimension].append(float(row[f"{dimension}_score"]))
            try:
                basis = json.loads(row["priority_basis_json"] or "{}")
            except json.JSONDecodeError:
                basis = {}
            dimensions = basis.get("dimensions", {})
            if dimensions:
                recomputed_targets += 1
            benefit = dimensions.get("benefit", {}).get("components", {})
            has_demand_signal = False
            for signal in demand_signal_counts:
                if benefit.get(signal, {}).get("matches"):
                    demand_signal_counts[signal] += 1
                    has_demand_signal = True
            if has_demand_signal:
                capability["with_demand_signal"] += 1
            if (
                dimensions.get("feasibility", {}).get("selected_source_id")
                is not None
            ):
                targets_with_source_path += 1
                capability["with_catalog_capability_path"] += 1

        frontier_ids = self._pareto_frontier(rows)
        frontier_set = set(frontier_ids)
        frontier = [
            {
                key: row[key]
                for key in (
                    "census_target_id",
                    "state",
                    "domain",
                    "role",
                    "status",
                    "benefit_score",
                    "feasibility_score",
                    "risk_score",
                )
            }
            for row in rows
            if row["census_target_id"] in frontier_set
        ]
        return {
            "targets": len(rows),
            "targets_with_recomputed_basis": recomputed_targets,
            "targets_with_catalog_capability_path": targets_with_source_path,
            "targets_with_demand_signal": demand_signal_counts,
            "by_status": dict(sorted(by_status.items())),
            "score_dimensions": {
                dimension: _dimension_summary(
                    [float(row[f"{dimension}_score"]) for row in rows]
                )
                for dimension in ("benefit", "feasibility", "risk")
            },
            "by_domain": {
                domain: {
                    dimension: _dimension_summary(values)
                    for dimension, values in dimensions.items()
                }
                for domain, dimensions in sorted(by_domain.items())
            },
            "by_capability": {
                capability_name: {
                    "targets": values["targets"],
                    "with_catalog_capability_path": values[
                        "with_catalog_capability_path"
                    ],
                    "with_demand_signal": values["with_demand_signal"],
                    "score_dimensions": {
                        dimension: _dimension_summary(values[dimension])
                        for dimension in ("benefit", "feasibility", "risk")
                    },
                }
                for capability_name, values in sorted(by_capability.items())
            },
            "catalog_state": {
                "sources": sum(source_status_counts.values()),
                "by_source_status": source_status_counts,
                "sources_with_access_review": len(access_rows),
                "latest_access_class": dict(
                    sorted(
                        {
                            value: sum(
                                str(row["access_class"]) == value
                                for row in access_rows
                            )
                            for value in {
                                str(row["access_class"]) for row in access_rows
                            }
                        }.items()
                    )
                ),
                "latest_automation_disposition": dict(
                    sorted(
                        {
                            value: sum(
                                str(row["automation_disposition"]) == value
                                for row in access_rows
                            )
                            for value in {
                                str(row["automation_disposition"])
                                for row in access_rows
                            }
                        }.items()
                    )
                ),
                "sources_with_probe": len(probe_rows),
                "latest_probe_status": dict(
                    sorted(
                        {
                            value: sum(
                                str(row["status"]) == value for row in probe_rows
                            )
                            for value in {
                                str(row["status"]) for row in probe_rows
                            }
                        }.items()
                    )
                ),
            },
            "comparison_model": {
                "dimensions": [
                    {"name": "benefit", "direction": "higher"},
                    {"name": "feasibility", "direction": "higher"},
                    {"name": "risk", "direction": "lower"},
                ],
                "pareto_frontier": frontier,
            },
        }

    def explain(self, target_id: int) -> dict[str, Any]:
        """Return a target's complete score basis and priority audit events."""
        db = self._catalog_connect()
        try:
            row = db.execute(
                """
                SELECT t.*, j.name AS jurisdiction_name,
                       j.subdivision_code AS state, j.geoid
                FROM source_census_targets t
                JOIN jurisdictions j USING(jurisdiction_id)
                WHERE t.census_target_id=?
                """,
                (target_id,),
            ).fetchone()
            if row is None:
                raise PriorityError(f"unknown census target: {target_id}")
            target = dict(row)
            target["source_ids"] = [
                str(source_row["source_id"])
                for source_row in db.execute(
                    """
                    SELECT source_id
                    FROM source_census_target_sources
                    WHERE census_target_id=?
                    ORDER BY added_at, rowid
                    """,
                    (target_id,),
                )
            ]
            try:
                target["priority_basis"] = json.loads(
                    target.pop("priority_basis_json")
                )
            except json.JSONDecodeError as error:
                raise PriorityError(
                    f"target {target_id} has invalid priority basis JSON"
                ) from error
            events = []
            for event in db.execute(
                """
                SELECT census_event_id, event_type, actor, from_status,
                       to_status, details_json, recorded_at
                FROM source_census_events
                WHERE census_target_id=?
                  AND event_type IN ('scored', 'priority_recomputed')
                ORDER BY census_event_id
                """,
                (target_id,),
            ):
                item = dict(event)
                item["details"] = json.loads(item.pop("details_json"))
                events.append(item)
        finally:
            db.close()
        target["priority_events"] = events
        return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute and inspect separate benefit, feasibility, and risk "
            "dimensions for the public-record source census"
        )
    )
    parser.add_argument("--catalog-db", default=str(DEFAULT_DB_PATH))
    parser.add_argument(
        "--investigation-db",
        default=str(DEFAULT_INVESTIGATION_DB),
    )
    parser.add_argument(
        "--investigations-dir",
        default=str(DEFAULT_INVESTIGATIONS_DIR),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    recompute_parser = sub.add_parser("recompute")
    recompute_parser.add_argument("--by", required=True)
    recompute_parser.add_argument("--profile")
    recompute_parser.add_argument("--as-of")
    recompute_parser.add_argument("--dry-run", action="store_true")
    add_output_args(recompute_parser)

    metrics_parser = sub.add_parser("metrics")
    add_output_args(metrics_parser)

    explain_parser = sub.add_parser("explain")
    explain_parser.add_argument("target_id", type=int)
    add_output_args(explain_parser)
    return parser


def _emit(value: Any, args: argparse.Namespace) -> None:
    if write_output(
        value,
        args,
        summary=f"Public-record census priority {args.command}",
    ):
        return
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    args = build_parser().parse_args()
    priority = PublicRecordsPriority(
        args.catalog_db,
        investigation_db=args.investigation_db,
        investigations_dir=args.investigations_dir,
    )
    try:
        if args.command == "recompute":
            value = priority.recompute(
                actor=args.by,
                profile_name=args.profile,
                dry_run=args.dry_run,
                as_of=args.as_of,
            )
        elif args.command == "metrics":
            value = priority.metrics()
        else:
            value = priority.explain(args.target_id)
    except (PriorityError, OSError, sqlite3.Error, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    _emit(value, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
