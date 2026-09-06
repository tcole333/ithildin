#!/usr/bin/env python3
"""Inspect and prepare official Licking County Common Pleas record routes.

Licking County's current remote case portal is a re:SearchOH tenant.  Its
anonymous app/tenant configuration is machine-readable, while targeted case
search currently transitions through human verification and sign-in.  This
adapter monitors the verified anonymous contract and creates structured
handoffs for targeted browser search, bulk distribution, current copies, and
the county historical archive.

Examples:
    uv run python tools/query_ohio_licking_common_pleas.py source --json
    uv run python tools/query_ohio_licking_common_pleas.py probe --json
    uv run python tools/query_ohio_licking_common_pleas.py \
        targeted-browser-handoff --party-name "Jane Smith" --json
    uv run python tools/query_ohio_licking_common_pleas.py \
        bulk-request-handoff --scope "civil party index and docket events" --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

import requests

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        sha256_fingerprint,
    )
    from tools.public_records_http import system_trust_session
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        sha256_fingerprint,
    )
    from public_records_http import system_trust_session


SOURCE_ID = "us-oh-licking-common-pleas-remote-records"
COURT_ID = "oh-licking-common-pleas"
COURT_NAME = "Licking County Court of Common Pleas"
STATE_CODE = "OH"
COUNTY_FIPS = "39089"
OFFICIAL_LANDING_URL = (
    "https://lickingcounty.gov/depts/clerk/records_search.htm"
)
PORTAL_URL = (
    "https://researchoh.tylerhost.net/CourtRecordsSearch/ui/county/"
    "LickingCaseSearch"
)
APP_CONFIGURATION_URL = (
    "https://researchoh.tylerhost.net/CourtRecordsSearch//configuration/"
    "appConfiguration"
)
CLAIMS_URL = (
    "https://researchoh.tylerhost.net/CourtRecordsSearch/api/auth/claims"
)
SUBSCRIPTION_CONFIGURATION_URL = (
    "https://researchoh.tylerhost.net/CourtRecordsSearch//config/"
    "premiumAndProSubscription?getAdditionalDetails=false"
)
COUNTY_CONFIGURATION_URL = (
    "https://researchoh.tylerhost.net/CourtRecordsSearch/CountySite/"
    "GetCountySite/LickingCaseSearch"
)
ARCHIVES_URL = (
    "https://lickingcounty.gov/depts/records_n_archives/"
    "list_of_holdings_by_department/clerk_of_courts.htm"
)
DEFAULT_TIMEOUT = 30.0
PROBE_REQUEST_COUNT = 6
ADAPTER_FAMILY = "tyler_research"
OBSERVED_AT = "2026-08-03"
GENERAL_CIVIL_CRIMINAL_PHONE = "740-670-5791"
DOMESTIC_RELATIONS_PHONE = "740-670-5392"
CLERK_ADDRESS = "1 Courthouse Square, Newark, OH 43055"

SOURCE_WARNINGS = (
    "The remote portal describes its copies as unofficial; the Clerk of Courts "
    "is the official records custodian.",
    "The county landing page excludes domestic-violence civil protection "
    "orders and criminal protection orders from remote access.",
    "Current anonymous configuration does not establish the post-sign-in "
    "feature or document entitlement of any particular account.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Licking County Common Pleas remote records",
    source_role="county_common_pleas_remote_portal_and_official_record_actions",
    base_url=OFFICIAL_LANDING_URL,
    dataset_id=SOURCE_ID,
    metadata={
        "authority": "Licking County Clerk of Courts",
        "court_id": COURT_ID,
        "state_code": STATE_CODE,
        "county_fips": COUNTY_FIPS,
        "platform_family": ADAPTER_FAMILY,
        "portal_url": PORTAL_URL,
        "access": "human_verification_and_sign_in_for_targeted_search",
        "anonymous_probe_endpoints": [
            APP_CONFIGURATION_URL,
            CLAIMS_URL,
            SUBSCRIPTION_CONFIGURATION_URL,
            COUNTY_CONFIGURATION_URL,
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-oh-licking-county",
    name="Licking County, Ohio",
    state_code=STATE_CODE,
    county_fips=COUNTY_FIPS,
    locality="Licking County",
    metadata={"court_id": COURT_ID},
)

SOURCE_CATALOG_METADATA = {
    SOURCE_ID: {
        "source_id": SOURCE_ID,
        "record_identity_source_id": SOURCE_ID,
        "name": "Licking County Common Pleas remote records",
        "authority": "Licking County Clerk of Courts",
        "domain": "court",
        "court_id": COURT_ID,
        "state_code": STATE_CODE,
        "county_fips": COUNTY_FIPS,
        "url": OFFICIAL_LANDING_URL,
        "portal_url": PORTAL_URL,
        "platform_family": ADAPTER_FAMILY,
        "adapter": "tools/query_ohio_licking_common_pleas.py",
        "operations": [
            "source",
            "probe",
            "targeted_browser_handoff",
            "bulk_request_handoff",
            "record_request_handoff",
            "archives_handoff",
        ],
        "roles": [
            "party_name_search_handoff",
            "exact_case_search_handoff",
            "case_docket_and_pleading_handoff",
            "bulk_distribution_request",
            "official_copy_request",
            "historical_court_archive",
        ],
        "access": {
            "anonymous_probe": "available",
            "targeted_portal": "human_verification_and_sign_in",
            "bulk_and_copy": "official_clerk_request",
            "historical": "county_records_and_archives",
        },
        "monitor": {
            "request_budget": PROBE_REQUEST_COUNT,
            "sequence": [
                "official_landing",
                "tenant_shell",
                "app_configuration",
                "anonymous_claims",
                "subscription_configuration",
                "county_configuration",
            ],
            "waf_state": "human_required",
        },
        "remote_scope": [
            "common_pleas_general_civil",
            "common_pleas_general_criminal",
            "domestic_relations_excluding_juvenile",
            "fifth_district_appeals_filed_in_licking_county",
        ],
        "remote_exclusions": [
            "domestic_violence_civil_protection_orders",
            "criminal_protection_orders",
        ],
        "complementary_sources": [
            {
                "kind": "county_clerk_bulk_distribution",
                "url": OFFICIAL_LANDING_URL,
                "join_keys": ["case_number", "party_name", "filing_date"],
            },
            {
                "kind": "county_historical_archive",
                "url": ARCHIVES_URL,
                "join_keys": ["case_number", "party_name", "year"],
            },
            {
                "source_id": "us-oh-licking-sheriff-realauction",
                "kind": "foreclosure_and_sheriff_sale_context",
                "join_keys": ["case_number", "parcel_id", "address"],
            },
            {
                "source_id": "us-oh-licking-sheriff-foreclosure-archive",
                "kind": "historical_foreclosure_sale_context",
                "join_keys": ["case_number", "parcel_id", "address"],
            },
            {
                "source_id": "us-oh-licking-county-recorder-pax",
                "kind": "recorded_instrument_detail_and_image",
                "join_keys": ["instrument_number", "party_name", "address"],
            },
            {
                "source_id": "us-oh-licking-county-auditor-gis",
                "kind": "parcel_owner_and_transfer_context",
                "join_keys": ["parcel_id", "owner_name", "address"],
            },
        ],
        "observed_at": OBSERVED_AT,
    }
}


class LickingCourtError(RuntimeError):
    """Structured source or query error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        category: str = "source",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.category = category
        self.retryable = retryable
        self.details = dict(details or {})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _find_key(value: Any, *names: str) -> Any:
    wanted = {name.casefold() for name in names}
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in wanted:
                return item
        for item in value.values():
            found = _find_key(item, *names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_key(item, *names)
            if found is not None:
                return found
    return None


def _required_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LickingCourtError(
            "probe_packet_invalid",
            f"Licking source probe lacks {field}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return value


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "court_level": "common_pleas",
        "official_url": OFFICIAL_LANDING_URL,
    }


class LickingProbeClient:
    """Fetch the official landing and four verified anonymous JSON routes."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = session or system_trust_session()
        self.timeout = timeout
        self._owns_session = session is None
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        )

    def _get(
        self,
        url: str,
        *,
        json_response: bool,
        referer: str | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if referer:
            headers["Referer"] = referer
        if json_response:
            headers["Accept"] = "application/json, text/plain, */*"
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers=headers or None,
            )
        except requests.RequestException as error:
            raise LickingCourtError(
                "probe_transport_failed",
                f"Licking source request failed: {error}",
                category="transport",
                retryable=True,
                details={"url": url},
            ) from error
        if response.status_code == 403 and "researchoh.tylerhost.net" in url:
            raise LickingCourtError(
                "interactive_verification_required",
                "The Licking re:SearchOH route presented its verification layer",
                status=ResultStatus.HUMAN_REQUIRED,
                category="access",
                details={
                    "url": url,
                    "status_code": response.status_code,
                    "portal_url": PORTAL_URL,
                },
            )
        if response.status_code != 200:
            raise LickingCourtError(
                "probe_http_error",
                f"Licking source returned HTTP {response.status_code}",
                category="transport",
                retryable=response.status_code >= 500,
                details={"url": url, "status_code": response.status_code},
            )
        if json_response:
            try:
                payload = response.json()
            except ValueError as error:
                raise LickingCourtError(
                    "probe_non_json",
                    "Verified Licking JSON route returned non-JSON content",
                    status=ResultStatus.SOURCE_CHANGED,
                    category="source_schema",
                    details={"url": url},
                ) from error
            if not isinstance(payload, (dict, list)):
                raise LickingCourtError(
                    "probe_json_shape_changed",
                    "Verified Licking JSON route returned a scalar",
                    status=ResultStatus.SOURCE_CHANGED,
                    category="source_schema",
                    details={"url": url},
                )
            return {
                "url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "payload": payload,
            }
        body = response.text
        return {
            "url": url,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "title_matches": bool(
                re.search(r"Licking County.*Common Pleas.*Case Records", body, re.I | re.S)
            ),
            "mentions_docket": "docket" in body.casefold(),
            "mentions_pleadings": "pleading" in body.casefold(),
            "mentions_bulk": "bulk" in body.casefold(),
        }

    def probe(self) -> dict[str, Any]:
        requests_made = [
            self._get(OFFICIAL_LANDING_URL, json_response=False),
            self._get(
                PORTAL_URL,
                json_response=False,
                referer=OFFICIAL_LANDING_URL,
            ),
            self._get(
                APP_CONFIGURATION_URL,
                json_response=True,
                referer=PORTAL_URL,
            ),
            self._get(CLAIMS_URL, json_response=True, referer=PORTAL_URL),
            self._get(
                SUBSCRIPTION_CONFIGURATION_URL,
                json_response=True,
                referer=PORTAL_URL,
            ),
            self._get(
                COUNTY_CONFIGURATION_URL,
                json_response=True,
                referer=PORTAL_URL,
            ),
        ]
        if len(requests_made) != PROBE_REQUEST_COUNT:
            raise LickingCourtError(
                "probe_request_budget_changed",
                "Licking Common Pleas probe request budget changed",
                status=ResultStatus.SOURCE_CHANGED,
                category="monitor_contract",
            )
        return {
            "status": "ok",
            "source_url": OFFICIAL_LANDING_URL,
            "landing": requests_made[0],
            "portal_shell": requests_made[1],
            "app_configuration": requests_made[2],
            "claims": requests_made[3],
            "subscription_configuration": requests_made[4],
            "county_configuration": requests_made[5],
            "request_count": len(requests_made),
        }

    def close(self) -> None:
        if self._owns_session:
            self.session.close()


def _load_packet(file_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LickingCourtError(
            "input_packet_invalid",
            f"could not read probe packet: {error}",
            category="input",
        ) from error
    if not isinstance(payload, dict):
        raise LickingCourtError(
            "input_packet_invalid",
            "probe packet must be a JSON object",
            category="input",
        )
    return payload


def _payload(packet: Mapping[str, Any], name: str) -> Any:
    wrapper = _required_mapping(packet.get(name), name)
    if wrapper.get("status_code") != 200:
        raise LickingCourtError(
            "probe_packet_invalid",
            f"{name} packet is not an HTTP 200 observation",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return wrapper.get("payload")


def normalize_probe(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("status") != "ok":
        raise LickingCourtError(
            "probe_packet_invalid",
            "Licking source probe did not complete",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    landing = _required_mapping(packet.get("landing"), "landing")
    portal_shell = _required_mapping(packet.get("portal_shell"), "portal_shell")
    if portal_shell.get("status_code") != 200:
        raise LickingCourtError(
            "probe_packet_invalid",
            "Licking portal shell packet is not an HTTP 200 observation",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    app = _payload(packet, "app_configuration")
    claims = _payload(packet, "claims")
    subscription = _payload(packet, "subscription_configuration")
    county = _payload(packet, "county_configuration")
    if not isinstance(app, Mapping) or not isinstance(claims, Mapping):
        raise LickingCourtError(
            "probe_json_shape_changed",
            "Licking application or claims contract is no longer an object",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )

    version = _text(_find_key(app, "version", "applicationVersion", "appVersion"))
    name = _text(_find_key(app, "name", "applicationName", "appName"))
    max_export = _find_key(app, "maxExportSearchResultsSize")
    county_id = _find_key(county, "countyId")
    external_source = _text(_find_key(county, "externalSource"))
    county_site = _text(
        _find_key(county, "site", "siteName", "countySiteName", "countySite")
    )
    jwt = _find_key(claims, "jwt")
    user_profile = _find_key(claims, "userProfile")
    basic_security = _find_key(claims, "basicUserSecurity")
    authenticated = any(value not in (None, {}, [], "") for value in (jwt, user_profile))

    stable_contract = {
        "platform_family": ADAPTER_FAMILY,
        "portal_route": "/CourtRecordsSearch/ui/county/LickingCaseSearch",
        "portal_shell_available": True,
        "anonymous_routes": [
            "/CourtRecordsSearch//configuration/appConfiguration",
            "/CourtRecordsSearch/api/auth/claims",
            "/CourtRecordsSearch//config/premiumAndProSubscription",
            "/CourtRecordsSearch/CountySite/GetCountySite/LickingCaseSearch",
        ],
        "landing_fields": {
            "title_matches": bool(landing.get("title_matches")),
            "mentions_docket": bool(landing.get("mentions_docket")),
            "mentions_pleadings": bool(landing.get("mentions_pleadings")),
            "mentions_bulk": bool(landing.get("mentions_bulk")),
        },
        "claims_fields": sorted(str(key) for key in claims),
        "app_name": name,
        "county_id": county_id,
        "external_source": external_source,
        "county_site": county_site,
    }
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "source_probe",
        "canonical_ref": f"SOURCEPROBE:{SOURCE_ID}",
        "source_url": OFFICIAL_LANDING_URL,
        "portal_url": PORTAL_URL,
        "platform_family": ADAPTER_FAMILY,
        "anonymous_probe_state": "available",
        "targeted_search_access_state": (
            "signed_in_session_observed"
            if authenticated
            else "human_verification_and_sign_in_required"
        ),
        "authenticated_claims_observed": authenticated,
        "application_name": name,
        "application_version": version,
        "county_id": county_id,
        "external_source": external_source,
        "county_site": county_site,
        "max_export_search_results_size": max_export,
        "max_export_is_search_page_ceiling": False,
        "request_count": packet.get("request_count"),
        "schema_fingerprint": sha256_fingerprint(stable_contract),
        "contract": stable_contract,
        "rolling_observations": {
            "application_version": version,
            "anonymous_jwt_present": jwt not in (None, ""),
            "anonymous_user_profile_present": user_profile not in (None, {}, ""),
            "anonymous_basic_security_present": basic_security not in (None, {}, ""),
            "subscription_configuration_fingerprint": sha256_fingerprint(subscription),
        },
    }


def _source_record() -> dict[str, Any]:
    metadata = SOURCE_CATALOG_METADATA[SOURCE_ID]
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "source_manifest",
        "canonical_ref": f"SOURCE:{SOURCE_ID}",
        "name": metadata["name"],
        "authority": metadata["authority"],
        "source_url": OFFICIAL_LANDING_URL,
        "portal_url": PORTAL_URL,
        "platform_family": ADAPTER_FAMILY,
        "operations": list(metadata["operations"]),
        "roles": list(metadata["roles"]),
        "access": dict(metadata["access"]),
        "monitor": dict(metadata["monitor"]),
        "remote_scope": list(metadata["remote_scope"]),
        "remote_exclusions": list(metadata["remote_exclusions"]),
        "complementary_sources": list(metadata["complementary_sources"]),
        "update_note": "The county describes portal updates as approximately every 15 minutes.",
        "copy_status": "Portal copies are unofficial; official copies come from the Clerk.",
        "observed_at": OBSERVED_AT,
    }


def _handoff_ref(kind: str, parameters: Mapping[str, Any]) -> str:
    return f"ACTION:{SOURCE_ID}:{kind}:{sha256_fingerprint(parameters)[:20]}"


def targeted_browser_handoff(args: argparse.Namespace) -> dict[str, Any]:
    selectors = {
        "party_name": _text(args.party_name),
        "case_number": _text(args.case_number),
        "filed_from": args.filed_from,
        "filed_to": args.filed_to,
    }
    if not selectors["party_name"] and not selectors["case_number"]:
        raise LickingCourtError(
            "target_selector_missing",
            "targeted browser handoff needs a party name or case number",
            category="query_selection",
        )
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "source_action",
        "action_kind": "targeted_browser_search",
        "canonical_ref": _handoff_ref("targeted_browser_search", selectors),
        "source_url": PORTAL_URL,
        "selectors": selectors,
        "access_state": "human_verification_and_sign_in_required",
        "handoff": {
            "entry_url": PORTAL_URL,
            "steps": [
                "Open the official Licking County tenant.",
                "Choose Sign in and complete the displayed human verification.",
                "Sign in or register, then apply the supplied selectors in the portal.",
                "Capture displayed case IDs, case numbers, docket fields, filing IDs, and document states.",
            ],
            "capture_fields": [
                "caseDataID",
                "displayed_case_number",
                "party_occurrences",
                "docket_or_event_rows",
                "filingId",
                "document_access_state",
            ],
        },
    }


def bulk_request_handoff(args: argparse.Namespace) -> dict[str, Any]:
    parameters = {
        "scope": _text(args.scope),
        "party_name": _text(args.party_name),
        "case_number": _text(args.case_number),
        "filed_from": args.filed_from,
        "filed_to": args.filed_to,
        "division": _text(args.division),
    }
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "source_action",
        "action_kind": "bulk_distribution_request",
        "canonical_ref": _handoff_ref("bulk_distribution_request", parameters),
        "source_url": OFFICIAL_LANDING_URL,
        "requested_scope": parameters,
        "access_state": "official_clerk_request",
        "handoff": {
            "authority": "Licking County Clerk of Courts",
            "address": CLERK_ADDRESS,
            "general_civil_criminal_phone": GENERAL_CIVIL_CRIMINAL_PHONE,
            "domestic_relations_phone": DOMESTIC_RELATIONS_PHONE,
            "request_note": "The official landing directs bulk distribution inquiries to the Clerk.",
        },
    }


def record_request_handoff(args: argparse.Namespace) -> dict[str, Any]:
    parameters = {
        "case_number": _text(args.case_number),
        "document_description": _text(args.document_description),
        "copy_type": args.copy_type,
    }
    if not parameters["case_number"]:
        raise LickingCourtError(
            "case_number_missing",
            "record request handoff needs a case number",
            category="query_selection",
        )
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "source_action",
        "action_kind": "current_record_or_copy_request",
        "canonical_ref": _handoff_ref("current_record_or_copy_request", parameters),
        "source_url": OFFICIAL_LANDING_URL,
        "request": parameters,
        "access_state": "official_clerk_request",
        "handoff": {
            "authority": "Licking County Clerk of Courts",
            "address": CLERK_ADDRESS,
            "general_civil_criminal_phone": GENERAL_CIVIL_CRIMINAL_PHONE,
            "domestic_relations_phone": DOMESTIC_RELATIONS_PHONE,
            "official_copy": args.copy_type in {"official", "certified"},
        },
    }


def archives_handoff(args: argparse.Namespace) -> dict[str, Any]:
    parameters = {
        "party_name": _text(args.party_name),
        "case_number": _text(args.case_number),
        "year": args.year,
        "record_series": _text(args.record_series),
    }
    if not any(parameters.values()):
        raise LickingCourtError(
            "archive_selector_missing",
            "archives handoff needs a party, case, year, or record series",
            category="query_selection",
        )
    return {
        "source_id": SOURCE_ID,
        "court_id": COURT_ID,
        "native_court_id": COURT_ID,
        "court": _court_payload(),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_FIPS,
        "record_kind": "source_action",
        "action_kind": "historical_archive_lookup",
        "canonical_ref": _handoff_ref("historical_archive_lookup", parameters),
        "source_url": ARCHIVES_URL,
        "selectors": parameters,
        "access_state": "county_records_and_archives",
        "coverage_note": (
            "The official holdings page lists Clerk of Courts indexes and files "
            "beginning in the 1810s, with many series through 1992 and some through 1994."
        ),
        "current_record_route": OFFICIAL_LANDING_URL,
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "party_name",
        "case_number",
        "filed_from",
        "filed_to",
        "scope",
        "division",
        "document_description",
        "copy_type",
        "year",
        "record_series",
    ):
        if hasattr(args, name):
            value = getattr(args, name)
            parameters[name] = str(value) if isinstance(value, Path) else value
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command.replace("-", "_"),
            parameters=parameters,
            metadata={"court_id": COURT_ID, "adapter_family": ADAPTER_FAMILY},
        ),
    )


def _failure(query: PublicRecordsQuery, error: LickingCourtError) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=error.category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: LickingProbeClient | Any | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    raw_refs: tuple[str, ...] = ()
    source_client = client
    owns_client = False
    try:
        if args.command == "source":
            records = [_source_record()]
        elif args.command == "probe":
            if args.input:
                resolved = Path(args.input).resolve()
                packet = _load_packet(resolved)
                raw_refs = (str(resolved),)
            else:
                source_client = source_client or LickingProbeClient(timeout=args.timeout)
                owns_client = client is None
                packet = source_client.probe()
            records = [normalize_probe(packet)]
        elif args.command == "targeted-browser-handoff":
            records = [targeted_browser_handoff(args)]
        elif args.command == "bulk-request-handoff":
            records = [bulk_request_handoff(args)]
        elif args.command == "record-request-handoff":
            records = [record_request_handoff(args)]
        elif args.command == "archives-handoff":
            records = [archives_handoff(args)]
        else:
            raise LickingCourtError(
                "unsupported_command",
                f"unsupported command: {args.command}",
                category="query_selection",
            )
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=raw_refs,
            warnings=SOURCE_WARNINGS,
        )
    except LickingCourtError as error:
        return _failure(query, error)
    except (TypeError, ValueError, KeyError) as error:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="normalization",
                )
            ],
            raw_artifact_refs=raw_refs,
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client and source_client is not None:
            source_client.close()


def _date_arg(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD")
    return value


def _runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    add_output_args(parser)


def _selector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--party-name")
    parser.add_argument("--case-number")
    parser.add_argument("--filed-from", type=_date_arg)
    parser.add_argument("--filed-to", type=_date_arg)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser("source", help="Show verified source routes")
    add_output_args(source)

    probe = subparsers.add_parser(
        "probe", help="Fetch the official landing and anonymous tenant contract"
    )
    probe.add_argument("--input", type=Path, help="Normalize a saved probe packet")
    _runtime_args(probe)

    targeted = subparsers.add_parser(
        "targeted-browser-handoff",
        help="Prepare a signed-in browser search action",
    )
    _selector_args(targeted)
    add_output_args(targeted)

    bulk = subparsers.add_parser(
        "bulk-request-handoff", help="Prepare an official bulk distribution request"
    )
    bulk.add_argument("--scope", required=True)
    _selector_args(bulk)
    bulk.add_argument(
        "--division",
        choices=["general-civil", "general-criminal", "domestic-relations", "appeals"],
    )
    add_output_args(bulk)

    record = subparsers.add_parser(
        "record-request-handoff", help="Prepare a current case record or copy request"
    )
    record.add_argument("case_number")
    record.add_argument("--document-description")
    record.add_argument(
        "--copy-type",
        choices=["informational", "official", "certified"],
        default="informational",
    )
    add_output_args(record)

    archives = subparsers.add_parser(
        "archives-handoff", help="Prepare a historical Records and Archives lookup"
    )
    archives.add_argument("--party-name")
    archives.add_argument("--case-number")
    archives.add_argument("--year", type=int)
    archives.add_argument("--record-series")
    add_output_args(archives)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Licking County Common Pleas {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Licking County Common Pleas {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
