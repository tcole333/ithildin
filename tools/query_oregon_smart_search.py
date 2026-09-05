#!/usr/bin/env python3
"""Inspect and prepare searches for Oregon Judicial Department Smart Search.

Smart Search is a free statewide trial-court search page whose selector
contract is assembled in a rendered browser.  This adapter makes that contract
machine-readable, exposes live option sets, and produces browser-ready search
handoffs without conflating them with returned case records.

Examples:
    uv run python tools/query_oregon_smart_search.py sources --json
    uv run python tools/query_oregon_smart_search.py probe --json
    uv run python tools/query_oregon_smart_search.py options SearchBy --json
    uv run python tools/query_oregon_smart_search.py prepare "ACME LLC" \
        --search-by BusinessName --location Multnomah --json
    uv run python tools/query_oregon_smart_search.py prepare \
        --last-name Smith --first-name Jane --file-date-start 2025-01-01 \
        --file-date-end 2025-12-31 --json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

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


SOURCE_ID = "us-or-ojd-smart-search"
STATE_CODE = "OR"
STATE_GEOID = "41"
SOURCE_URL = "https://webportal.courts.oregon.gov/portal/Home/Dashboard/29"
FORM_ACTION_URL = (
    "https://webportal.courts.oregon.gov/portal/SmartSearch/SmartSearch/SmartSearch"
)
FORM_ACTION_PATH = "/portal/SmartSearch/SmartSearch/SmartSearch"
HELPER_PATH = Path(__file__).with_name("_oregon_smart_search_browser_helper.js")
DEFAULT_BROWSER_TIMEOUT = 120.0
OBSERVED_AT = "2026-07-29"
ADAPTER_FAMILY = "oregon_ojd_smart_search"

OJCIN_URL = "https://www.courts.oregon.gov/services/online/Pages/ojcin.aspx"
OJCIN_SIGNUP_URL = (
    "https://www.courts.oregon.gov/services/online/Pages/ojcin-signup.aspx"
)
OJCIN_FEE_SCHEDULE_URL = (
    "https://www.courts.oregon.gov/forms/Documents/OJCINFeeSchedule.pdf"
)
STATEWIDE_RECORDS_REQUEST_URL = (
    "https://www.courts.oregon.gov/about/Pages/records-request.aspx"
)
CASE_RECORDS_REQUEST_URL = (
    "https://www.courts.oregon.gov/forms/Pages/records-request.aspx"
)

SEARCH_BY_OPTIONS = (
    ("Smart Search", "SmartSearch"),
    ("Attorney Bar Number", "AttorneyBarNumber"),
    ("Attorney Name", "AttorneyName"),
    ("Business Name", "BusinessName"),
    ("Case Cross-Reference Number", "CaseCrossReferenceNumber"),
    ("Case Number", "CaseNumber"),
    ("Citation Number", "CitationNumber"),
    ("Judicial Officer", "JudicialOfficer"),
    ("Nickname", "Nickname"),
    ("Party Name", "PartyName"),
    ("Warrant Number", "WarrantNumber"),
)
SEARCH_BY_VALUES = frozenset(value for _, value in SEARCH_BY_OPTIONS)

LOCATION_OPTIONS = (
    ("All Locations", "All Locations"),
    ("Baker", "Baker"),
    ("Benton", "Benton"),
    ("Clackamas", "Clackamas"),
    ("Clatsop", "Clatsop"),
    ("Columbia", "Columbia"),
    ("Coos", "Coos"),
    ("Crook", "Crook"),
    ("Curry", "Curry"),
    ("Deschutes", "Deschutes"),
    ("Douglas", "Douglas"),
    ("Gilliam", "Gilliam"),
    ("Grant", "Grant"),
    ("Harney", "Harney"),
    ("Hood River", "Hood River "),
    ("Jackson", "Jackson"),
    ("Jefferson", "Jefferson"),
    ("Josephine", "Josephine"),
    ("Klamath", "Klamath"),
    ("Lake", "Lake"),
    ("Lane", "Lane"),
    ("Lincoln", "Lincoln"),
    ("Linn", "Linn"),
    ("Malheur", "Malheur"),
    ("Marion", "Marion"),
    ("Morrow", "Morrow"),
    ("Multnomah", "Multnomah"),
    ("Polk", "Polk"),
    ("Sherman", "Sherman "),
    ("Tax Court", "Tax Court"),
    ("Tillamook", "Tillamook"),
    ("Umatilla", "Umatilla "),
    ("Union", "Union"),
    ("Wallowa", "Wallowa"),
    ("Wasco", "Wasco"),
    ("Washington", "Washington"),
    ("Wheeler", "Wheeler"),
    ("Yamhill", "Yamhill"),
)

CASE_TYPE_OPTIONS = (
    ("All Case Types", "All Case Types "),
    ("Civil", "Civil"),
    ("Criminal", "Criminal "),
    ("Family", "Family "),
    ("Probate", "Probate"),
)

OPTION_FIELDS = (
    "JudicialOfficerSearchBy",
    "NameSuffix",
    "CourtLocation",
    "SearchBy",
    "CaseType",
    "CaseStatus",
    "JudicialOfficer",
    "JudgmentType",
    "WarrantType",
    "WarrantStatus",
)

ROLLING_OPTION_FIELDS = frozenset(
    {
        "JudicialOfficerSearchBy",
        "JudicialOfficer",
    }
)

EXPECTED_OPTION_COUNTS = {
    "CourtLocation": 38,
    "SearchBy": 11,
    "CaseType": 5,
    "CaseStatus": 46,
    "WarrantType": 13,
    "WarrantStatus": 12,
}

COMPLEMENTARY_SOURCES = (
    {
        "source_id": "us-or-ojcin-oeci-subscription",
        "name": "OJCIN OECI subscription",
        "url": OJCIN_URL,
        "access": "subscription",
        "adds": (
            "Register of Actions and judgment records across Oregon circuit "
            "courts and Tax Court."
        ),
        "join_keys": ["case_number", "court", "party_name"],
    },
    {
        "source_id": "us-or-ojcin-acms-subscription",
        "name": "OJCIN ACMS subscription",
        "url": OJCIN_URL,
        "access": "subscription",
        "adds": (
            "Appellate case registers and events maintained separately from "
            "the circuit and Tax Court OECI product."
        ),
        "join_keys": ["appellate_case_number", "court", "party_name"],
    },
    {
        "source_id": "us-or-ojcin-standard-report-package",
        "name": "OJCIN standard daily report package",
        "url": OJCIN_SIGNUP_URL,
        "access": "published_paid_products",
        "adds": (
            "Recurring New Case Index and Judgment Index reports for "
            "repeatable statewide coverage."
        ),
        "join_keys": ["case_number", "court", "party_name", "judgment_number"],
    },
    {
        "source_id": "us-or-ojcin-bulk-data-transfer",
        "name": "OJCIN bulk data transfer",
        "url": OJCIN_FEE_SCHEDULE_URL,
        "access": "published_paid_product",
        "adds": (
            "Recurring bulk delivery for approved OJCIN data-product subscribers."
        ),
        "join_keys": ["case_number", "court", "party_name", "judgment_number"],
    },
    {
        "source_id": "us-or-osca-statewide-court-data-request",
        "name": "Oregon State Court Administrator statewide data request",
        "url": STATEWIDE_RECORDS_REQUEST_URL,
        "access": "official_request",
        "adds": (
            "Statewide or complex court data not exposed by the free search interface."
        ),
        "join_keys": ["case_number", "court", "date_range", "data_definition"],
    },
    {
        "source_id": "us-or-ojd-case-record-request",
        "name": "Oregon court case record and copy request",
        "url": CASE_RECORDS_REQUEST_URL,
        "access": "official_request",
        "adds": (
            "Case documents, copies, and hearing-specific records requested "
            "from the court that holds the record."
        ),
        "join_keys": ["case_number", "court", "document_name", "hearing_date"],
    },
)

COMPLEMENT_CATALOG_METADATA = {
    item["source_id"]: dict(item) for item in COMPLEMENTARY_SOURCES
}

SOURCE_CATALOG_METADATA = {
    SOURCE_ID: {
        "source_id": SOURCE_ID,
        "record_identity_source_id": SOURCE_ID,
        "complementary_source_ids": [
            item["source_id"] for item in COMPLEMENTARY_SOURCES
        ],
        "name": "Oregon Judicial Department Smart Search",
        "domain": "court",
        "roles": [
            "trial_case_search",
            "party_and_business_search",
            "judgment_search",
            "warrant_search",
        ],
        "authority": "Oregon Judicial Department",
        "operator": "Oregon Judicial Department",
        "jurisdiction_geoids": [STATE_GEOID],
        "official_url": SOURCE_URL,
        "platform_family": "tyler_odyssey_portal_smart_search",
        "authentication": "none",
        "fees": "none_for_smart_search",
        "adapter_family": ADAPTER_FAMILY,
        "adapter_version": 1,
        "adapter_tool": Path(__file__).name,
        "adapter_commands": [
            "sources",
            "runtime-check",
            "probe",
            "options",
            "prepare",
        ],
        "endpoints": {
            "dashboard": SOURCE_URL,
            "rendered_form_action": FORM_ACTION_URL,
        },
        "probe_evidence": {
            "rendered_page_http_status": 200,
            "form_method": "post",
            "form_action_path": FORM_ACTION_PATH,
            "captcha_enabled_for_anonymous_search": True,
            "captcha_disabled_for_authenticated": False,
            "location_count": 38,
            "search_by_count": 11,
            "case_status_count": 46,
            "observed_at": OBSERVED_AT,
        },
    }
}

# Stable aliases for catalog integration code.
CATALOG_METADATA = SOURCE_CATALOG_METADATA
CATALOG_COMPLEMENTS = COMPLEMENT_CATALOG_METADATA

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Oregon Judicial Department Smart Search",
    source_role=("statewide_circuit_and_tax_court_case_judgment_warrant_search"),
    base_url=SOURCE_URL,
    dataset_id="oregon-ojd-smart-search-dashboard-29",
    metadata={
        "authority": "Oregon Judicial Department",
        "state_code": STATE_CODE,
        "platform_family": "tyler_odyssey_portal_smart_search",
        "authentication": "none",
        "search_execution": "rendered_browser_form",
        "form_action_url": FORM_ACTION_URL,
        "covered_locations": 38,
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-or-state-courts",
    name="Oregon Circuit Courts and Tax Court",
    state_code=STATE_CODE,
    metadata={
        "state_geoid": STATE_GEOID,
        "court_scope": "all_36_circuit_courts_and_tax_court",
    },
)

WARNINGS = (
    "Prepared handoffs describe search inputs, not returned case records.",
    "The live anonymous form currently adds a reCAPTCHA step when a search is "
    "submitted.",
    "OJCIN, official data deliveries, calendars, and court record requests "
    "provide complementary depth or acquisition routes.",
)


class SmartSearchError(RuntimeError):
    """A source, browser-runtime, contract, or query-selection error."""

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

    def to_public_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


def _runtime_node_path(environment: Mapping[str, str]) -> str | None:
    candidates: list[str] = []
    configured = environment.get("NODE_PATH")
    if configured:
        candidates.extend(value for value in configured.split(os.pathsep) if value)
    repository_modules = Path(__file__).resolve().parents[1] / "node_modules"
    if repository_modules.is_dir():
        candidates.append(str(repository_modules))
    bundled_modules = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "node_modules"
    )
    if bundled_modules.is_dir():
        candidates.append(str(bundled_modules))
    unique = list(dict.fromkeys(candidates))
    return os.pathsep.join(unique) if unique else None


def _helper_error(stderr: str, returncode: int) -> SmartSearchError:
    lines = [line for line in stderr.splitlines() if line.strip()]
    payload: Any = None
    if lines:
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            payload = None
    error = payload.get("error") if isinstance(payload, Mapping) else None
    error_type = (
        str(error.get("type"))
        if isinstance(error, Mapping) and error.get("type")
        else "BrowserHelperError"
    )
    message = (
        str(error.get("message"))
        if isinstance(error, Mapping) and error.get("message")
        else (lines[-1] if lines else f"browser helper exited {returncode}")
    )
    if error_type == "RuntimeDependencyError":
        return SmartSearchError(
            "browser_runtime_unavailable",
            message,
            category="runtime",
            details={"helper_error_type": error_type},
        )
    if error_type == "SourceContractError":
        return SmartSearchError(
            "source_contract_changed",
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"helper_error_type": error_type},
        )
    return SmartSearchError(
        "browser_probe_failed",
        message,
        category="browser",
        retryable=True,
        details={
            "helper_error_type": error_type,
            "returncode": returncode,
        },
    )


def run_browser_helper(
    command: str,
    *,
    field: str | None = None,
    timeout: float = DEFAULT_BROWSER_TIMEOUT,
) -> dict[str, Any]:
    """Run the short-lived rendered-page helper and parse its JSON packet."""

    node = os.environ.get("OREGON_SMART_SEARCH_NODE") or shutil.which("node")
    if not node:
        raise SmartSearchError(
            "node_runtime_unavailable",
            "Node.js was not found for the Smart Search browser helper",
            category="runtime",
        )
    argv = [node, str(HELPER_PATH), command]
    if field is not None:
        argv.append(field)
    environment = dict(os.environ)
    node_path = _runtime_node_path(environment)
    if node_path:
        environment["NODE_PATH"] = node_path
    try:
        completed = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise SmartSearchError(
            "browser_probe_timeout",
            f"Smart Search browser helper exceeded {timeout:g} seconds",
            category="browser",
            retryable=True,
        ) from error
    if completed.returncode != 0:
        raise _helper_error(completed.stderr, completed.returncode)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SmartSearchError(
            "browser_helper_invalid_json",
            "Smart Search browser helper returned invalid JSON",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        ) from error
    if not isinstance(payload, dict):
        raise SmartSearchError(
            "browser_helper_invalid_payload",
            "Smart Search browser helper returned a non-object payload",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return payload


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SmartSearchError(
            "probe_payload_invalid",
            f"Smart Search probe has no {label} object",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return value


def _compact_option_set(
    option_sets: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    payload = _require_mapping(option_sets.get(name), f"{name} option set")
    count = payload.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise SmartSearchError(
            "probe_option_set_empty",
            f"Smart Search {name} option set is empty or malformed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    values = payload.get("values")
    if values is not None and not isinstance(values, list):
        raise SmartSearchError(
            "probe_option_values_invalid",
            f"Smart Search {name} option values are malformed",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    normalized = {
        "count": count,
        "first": list(payload.get("first") or []),
        "last": list(payload.get("last") or []),
    }
    if values is not None:
        normalized["values"] = values
        normalized["values_fingerprint"] = sha256_fingerprint(values)
    return normalized


def normalize_probe(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a compact rendered Smart Search probe."""

    if payload.get("http_status") != 200:
        raise SmartSearchError(
            "probe_http_status_changed",
            f"Smart Search probe returned HTTP {payload.get('http_status')}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_route",
        )
    form = _require_mapping(payload.get("form"), "form")
    action = str(form.get("action") or "")
    if urlsplit(action).path != FORM_ACTION_PATH:
        raise SmartSearchError(
            "probe_form_action_changed",
            f"Smart Search form action changed to {action or '(missing)'}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    if str(form.get("method") or "").casefold() != "post":
        raise SmartSearchError(
            "probe_form_method_changed",
            "Smart Search form method is no longer POST",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    settings = _require_mapping(payload.get("settings"), "settings")
    option_sets = _require_mapping(payload.get("option_sets"), "option_sets")
    normalized_options = {
        name: _compact_option_set(option_sets, name) for name in OPTION_FIELDS
    }
    controls = form.get("named_controls")
    if not isinstance(controls, list):
        raise SmartSearchError(
            "probe_controls_invalid",
            "Smart Search named controls are missing",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    stable_controls = sorted(
        {
            (
                str(control.get("name")),
                str(control.get("type") or ""),
            )
            for control in controls
            if isinstance(control, Mapping)
            and (
                str(control.get("name") or "").startswith("caseCriteria.")
                or str(control.get("name") or "").startswith("Settings.")
                or control.get("name") in {"Search", "Clear", "g-recaptcha-response"}
            )
        }
    )
    schema = {
        "form_action_path": FORM_ACTION_PATH,
        "form_method": "post",
        "stable_controls": stable_controls,
        "settings": {
            key: settings[key] for key in sorted(settings) if key != "parse_error"
        },
        "option_counts": {
            name: value["count"]
            for name, value in sorted(normalized_options.items())
            if name not in ROLLING_OPTION_FIELDS
        },
    }
    count_matches = {
        name: normalized_options[name]["count"] == expected
        for name, expected in EXPECTED_OPTION_COUNTS.items()
    }
    captcha = dict(_require_mapping(payload.get("captcha"), "captcha"))
    return {
        "canonical_ref": "ORCOURT_SOURCE:SMART_SEARCH",
        "source_id": SOURCE_ID,
        "record_kind": "court_search_source_probe",
        "source_url": str(payload.get("source_url") or SOURCE_URL),
        "final_url": str(payload.get("final_url") or SOURCE_URL),
        "http_status": 200,
        "title": payload.get("title"),
        "form": {
            "action": action,
            "method": "post",
            "stable_controls": [
                {"name": name, "type": control_type}
                for name, control_type in stable_controls
            ],
            "rendered_named_control_count": len(controls),
        },
        "settings": dict(settings),
        "captcha": captcha,
        "option_sets": normalized_options,
        "expected_option_count_matches": count_matches,
        "schema": schema,
        "schema_fingerprint": sha256_fingerprint(schema),
        "rolling_observations": {
            "option_counts": {
                name: normalized_options[name]["count"]
                for name in sorted(ROLLING_OPTION_FIELDS)
            }
        },
        "panels": list(payload.get("panels") or []),
        "runtime": dict(payload.get("runtime") or {}),
        "observed_at": OBSERVED_AT,
    }


def normalize_options(
    payload: Mapping[str, Any],
    *,
    expected_field: str,
) -> dict[str, Any]:
    """Normalize one full rendered Kendo option set."""

    if payload.get("http_status") != 200:
        raise SmartSearchError(
            "options_http_status_changed",
            f"Smart Search options returned HTTP {payload.get('http_status')}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_route",
        )
    field = str(payload.get("field") or "")
    if field != expected_field:
        raise SmartSearchError(
            "options_field_mismatch",
            f"Smart Search returned options for {field or '(missing)'}",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details={"expected_field": expected_field},
        )
    options = payload.get("options")
    if not isinstance(options, list):
        raise SmartSearchError(
            "options_payload_invalid",
            "Smart Search option payload is not a list",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    normalized: list[dict[str, str]] = []
    for index, option in enumerate(options):
        if not isinstance(option, Mapping):
            raise SmartSearchError(
                "option_row_invalid",
                f"Smart Search option row {index} is malformed",
                status=ResultStatus.SOURCE_CHANGED,
                category="source_schema",
            )
        normalized.append(
            {
                "text": str(option.get("text") or ""),
                "value": str(option.get("value") or ""),
            }
        )
    if payload.get("option_count") != len(normalized):
        raise SmartSearchError(
            "option_count_mismatch",
            "Smart Search option count does not match returned options",
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
        )
    return {
        "canonical_ref": f"ORCOURT_SOURCE:SMART_SEARCH:OPTIONS:{field}",
        "source_id": SOURCE_ID,
        "record_kind": "court_search_option_set",
        "field": field,
        "options": normalized,
        "option_count": len(normalized),
        "options_fingerprint": sha256_fingerprint(normalized),
        "source_url": str(payload.get("source_url") or SOURCE_URL),
        "final_url": str(payload.get("final_url") or SOURCE_URL),
        "runtime": dict(payload.get("runtime") or {}),
    }


def _option_value(
    value: str,
    options: Sequence[tuple[str, str]],
    *,
    label: str,
) -> tuple[str, str]:
    candidate = value.strip().casefold()
    for text, native in options:
        if candidate in {text.strip().casefold(), native.strip().casefold()}:
            return text, native
    choices = ", ".join(text for text, _ in options)
    raise SmartSearchError(
        f"{label}_invalid",
        f"unknown {label.replace('_', ' ')} {value!r}; choose {choices}",
        category="query_selection",
    )


def _source_date(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed: date | None = None
    for format_string in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            parsed = datetime.strptime(candidate, format_string).date()
            break
        except ValueError:
            continue
    if parsed is None:
        raise SmartSearchError(
            "date_invalid",
            f"{label} must be YYYY-MM-DD or MM/DD/YYYY",
            category="query_selection",
            details={"field": label, "value": value},
        )
    return f"{parsed.month:02d}/{parsed.day:02d}/{parsed.year:04d}"


def _date_order(
    start: str | None,
    end: str | None,
    *,
    label: str,
) -> None:
    if start and end:
        start_date = datetime.strptime(start, "%m/%d/%Y").date()
        end_date = datetime.strptime(end, "%m/%d/%Y").date()
        if start_date > end_date:
            raise SmartSearchError(
                "date_range_invalid",
                f"{label} start date is after end date",
                category="query_selection",
            )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def prepare_search(
    args: argparse.Namespace, query: PublicRecordsQuery
) -> dict[str, Any]:
    """Build a validated, browser-prefillable Smart Search handoff."""

    search_by = str(args.search_by)
    if search_by not in SEARCH_BY_VALUES:
        raise SmartSearchError(
            "search_by_invalid",
            f"unknown Smart Search mode: {search_by}",
            category="query_selection",
        )
    location_text, location_value = _option_value(
        args.location,
        LOCATION_OPTIONS,
        label="location",
    )
    case_type_text, case_type_value = _option_value(
        args.case_type,
        CASE_TYPE_OPTIONS,
        label="case_type",
    )
    file_start = _source_date(args.file_date_start, "file_date_start")
    file_end = _source_date(args.file_date_end, "file_date_end")
    judgment_start = _source_date(
        args.judgment_date_from,
        "judgment_date_from",
    )
    judgment_end = _source_date(args.judgment_date_to, "judgment_date_to")
    warrant_start = _source_date(
        args.warrant_date_issued_from,
        "warrant_date_issued_from",
    )
    warrant_end = _source_date(
        args.warrant_date_issued_to,
        "warrant_date_issued_to",
    )
    _date_order(file_start, file_end, label="file date")
    _date_order(judgment_start, judgment_end, label="judgment date")
    _date_order(warrant_start, warrant_end, label="warrant issue date")

    strings = {
        "caseCriteria.SearchCriteria": _text(args.query_text),
        "caseCriteria.NameLast": _text(args.last_name),
        "caseCriteria.NameFirst": _text(args.first_name),
        "caseCriteria.NameMiddle": _text(args.middle_name),
        "caseCriteria.NameSuffix": _text(args.suffix),
        "caseCriteria.PhoneNumber": _text(args.phone_number),
        "caseCriteria.FBINumber": _text(args.fbi_number),
        "caseCriteria.SONumber": _text(args.so_number),
        "caseCriteria.BookingNumber": _text(args.booking_number),
        "caseCriteria.CourtLocation": location_value,
        "caseCriteria.SearchBy": search_by,
        "caseCriteria.CaseType": case_type_value,
        "caseCriteria.CaseStatus": _text(args.case_status),
        "caseCriteria.FileDateStart": file_start,
        "caseCriteria.FileDateEnd": file_end,
        "caseCriteria.JudicialOfficer": _text(args.judicial_officer),
        "caseCriteria.JudgmentType": _text(args.judgment_type),
        "caseCriteria.JudgmentDateFrom": judgment_start,
        "caseCriteria.JudgmentDateTo": judgment_end,
        "caseCriteria.WarrantType": _text(args.warrant_type),
        "caseCriteria.WarrantStatus": _text(args.warrant_status),
        "caseCriteria.WarrantDateIssuedFrom": warrant_start,
        "caseCriteria.WarrantDateIssuedTo": warrant_end,
    }
    strings = {key: value for key, value in strings.items() if value is not None}
    search_inputs = {
        key: value
        for key, value in strings.items()
        if key
        not in {
            "caseCriteria.CourtLocation",
            "caseCriteria.SearchBy",
            "caseCriteria.CaseType",
        }
    }
    if not search_inputs:
        raise SmartSearchError(
            "search_selector_missing",
            "provide a search term, name, identifier, or advanced filter",
            category="query_selection",
        )

    booleans = {
        "caseCriteria.AdvancedSearchOptionsOpen": bool(
            len(search_inputs) > 1
            or any(
                value
                for key, value in search_inputs.items()
                if key != "caseCriteria.SearchCriteria"
            )
        ),
        "caseCriteria.SearchCases": args.search_cases,
        "caseCriteria.SearchJudgments": args.search_judgments,
        "caseCriteria.SearchWarrants": args.search_warrants,
        "caseCriteria.SearchByPartyName": (
            args.party_name and search_by != "BusinessName"
        ),
        "caseCriteria.SearchByNickName": (args.nickname or search_by == "Nickname"),
        "caseCriteria.SearchByBusinessName": (
            args.business_name or search_by == "BusinessName"
        ),
        "caseCriteria.UseSoundex": args.soundex,
    }
    if not any(
        booleans[name]
        for name in (
            "caseCriteria.SearchCases",
            "caseCriteria.SearchJudgments",
            "caseCriteria.SearchWarrants",
        )
    ):
        raise SmartSearchError(
            "search_component_missing",
            "select at least one of cases, judgments, or warrants",
            category="query_selection",
        )

    search_by_text = dict((native, text) for text, native in SEARCH_BY_OPTIONS)[
        search_by
    ]
    handoff_schema = {
        "source_id": SOURCE_ID,
        "form_action": FORM_ACTION_URL,
        "string_fields": sorted(strings),
        "boolean_fields": sorted(booleans),
    }
    return {
        "canonical_ref": (f"ORCOURT_SEARCH_HANDOFF:{query.fingerprint[:24].upper()}"),
        "source_id": SOURCE_ID,
        "record_kind": "interactive_court_search_handoff",
        "query_fingerprint": query.fingerprint,
        "source_url": SOURCE_URL,
        "form_action_url": FORM_ACTION_URL,
        "form_method": "post",
        "coverage": {
            "locations": "all_36_circuit_courts_and_tax_court",
            "selected_location": location_text,
            "selected_location_native_value": location_value,
        },
        "search_mode": {
            "text": search_by_text,
            "value": search_by,
        },
        "selected_case_type": {
            "text": case_type_text,
            "value": case_type_value,
        },
        "form_values": {
            "strings": strings,
            "booleans": booleans,
        },
        "execution_handoff": {
            "open_url": SOURCE_URL,
            "prefill_by_name": strings,
            "checkbox_state_by_name": booleans,
            "submit_control": {"name": "Search", "value": "Submit"},
            "session_fields_added_by_page": [
                "g-recaptcha-response",
                "source-generated challenge control",
            ],
        },
        "requested_components": [
            component
            for component, selected in (
                ("cases", args.search_cases),
                ("judgments", args.search_judgments),
                ("warrants", args.search_warrants),
            )
            if selected
        ],
        "complementary_sources": list(COMPLEMENTARY_SOURCES),
        "prepared_search_is_case_result": False,
        "schema": handoff_schema,
        "schema_fingerprint": sha256_fingerprint(handoff_schema),
    }


def _catalog_records() -> list[dict[str, Any]]:
    source_record = {
        "canonical_ref": "ORCOURT_SOURCE:SMART_SEARCH",
        "record_kind": "court_search_source",
        **SOURCE_CATALOG_METADATA[SOURCE_ID],
        "search_by_options": [
            {"text": text, "value": value} for text, value in SEARCH_BY_OPTIONS
        ],
        "location_options": [
            {"text": text, "value": value} for text, value in LOCATION_OPTIONS
        ],
        "case_type_options": [
            {"text": text, "value": value} for text, value in CASE_TYPE_OPTIONS
        ],
    }
    complement_records = [
        {
            "canonical_ref": (f"ORCOURT_COMPLEMENT:{item['source_id'].upper()}"),
            "record_kind": "court_source_complement",
            **item,
        }
        for item in COMPLEMENTARY_SOURCES
    ]
    return [source_record, *complement_records]


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    if args.command == "prepare":
        parameters = {
            "query_text": args.query_text,
            "search_by": args.search_by,
            "location": args.location,
            "last_name": args.last_name,
            "first_name": args.first_name,
            "middle_name": args.middle_name,
            "suffix": args.suffix,
            "phone_number": args.phone_number,
            "fbi_number": args.fbi_number,
            "so_number": args.so_number,
            "booking_number": args.booking_number,
            "case_type": args.case_type,
            "case_status": args.case_status,
            "file_date_start": args.file_date_start,
            "file_date_end": args.file_date_end,
            "judicial_officer": args.judicial_officer,
            "judgment_type": args.judgment_type,
            "judgment_date_from": args.judgment_date_from,
            "judgment_date_to": args.judgment_date_to,
            "warrant_type": args.warrant_type,
            "warrant_status": args.warrant_status,
            "warrant_date_issued_from": args.warrant_date_issued_from,
            "warrant_date_issued_to": args.warrant_date_issued_to,
            "search_cases": args.search_cases,
            "search_judgments": args.search_judgments,
            "search_warrants": args.search_warrants,
            "party_name": args.party_name,
            "nickname": args.nickname,
            "business_name": args.business_name,
            "soundex": args.soundex,
        }
    elif args.command == "options":
        parameters = {"field": args.field}
    elif args.command == "probe":
        parameters = {
            "input": str(args.input) if args.input else None,
            "rendered_browser": args.input is None,
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
        ),
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SmartSearchError(
            "probe_input_unreadable",
            f"could not read Smart Search probe input: {path}",
            category="input",
            details={"path": str(path), "error": str(error)},
        ) from error
    except json.JSONDecodeError as error:
        raise SmartSearchError(
            "probe_input_invalid_json",
            f"Smart Search probe input is not valid JSON: {path}",
            category="input",
            details={"path": str(path), "error": str(error)},
        ) from error
    if not isinstance(payload, dict):
        raise SmartSearchError(
            "probe_input_invalid",
            "Smart Search probe input must contain a JSON object",
            category="input",
        )
    return payload


HelperRunner = Callable[..., dict[str, Any]]


def execute(
    args: argparse.Namespace,
    *,
    helper_runner: HelperRunner = run_browser_helper,
) -> PublicRecordsResult:
    """Execute one Smart Search metadata, probe, option, or prepare command."""

    query = build_query(args)
    try:
        if args.command == "sources":
            return PublicRecordsResult.success(
                query,
                _catalog_records(),
                warnings=WARNINGS,
            )
        if args.command == "runtime-check":
            runtime = helper_runner(
                "runtime-check",
                timeout=args.browser_timeout,
            )
            record = {
                "canonical_ref": "ORCOURT_SOURCE:SMART_SEARCH:RUNTIME",
                "source_id": SOURCE_ID,
                "record_kind": "browser_runtime_probe",
                **runtime,
            }
            return PublicRecordsResult.success(query, [record], warnings=WARNINGS)
        if args.command == "probe":
            payload = (
                _load_json(args.input)
                if args.input is not None
                else helper_runner("probe", timeout=args.browser_timeout)
            )
            return PublicRecordsResult.success(
                query,
                [normalize_probe(payload)],
                raw_artifact_refs=(
                    [str(args.input.resolve())] if args.input is not None else []
                ),
                warnings=WARNINGS,
            )
        if args.command == "options":
            payload = helper_runner(
                "options",
                field=args.field,
                timeout=args.browser_timeout,
            )
            return PublicRecordsResult.success(
                query,
                [normalize_options(payload, expected_field=args.field)],
                warnings=WARNINGS,
            )
        if args.command == "prepare":
            return PublicRecordsResult.success(
                query,
                [prepare_search(args, query)],
                warnings=WARNINGS,
            )
        raise SmartSearchError(
            "command_invalid",
            f"unsupported Smart Search command: {args.command}",
            category="query_selection",
        )
    except SmartSearchError as error:
        return PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_public_error()],
            warnings=WARNINGS,
        )


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _add_browser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--browser-timeout",
        type=_positive_float,
        default=DEFAULT_BROWSER_TIMEOUT,
        help="Maximum seconds for the rendered-page helper",
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Inspect and prepare Oregon Circuit and Tax Court Smart Search")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="List Smart Search and its official complementary routes",
    )
    add_output_args(sources)

    runtime = subparsers.add_parser(
        "runtime-check",
        help="Inspect browser-helper runtime availability",
    )
    _add_browser_args(runtime)

    probe = subparsers.add_parser(
        "probe",
        help="Render and inspect the live Smart Search form contract",
    )
    probe.add_argument(
        "--input",
        type=Path,
        help="Normalize a previously captured browser-helper JSON packet",
    )
    _add_browser_args(probe)

    options = subparsers.add_parser(
        "options",
        help="Return one complete live Smart Search option set",
    )
    options.add_argument("field", choices=OPTION_FIELDS)
    _add_browser_args(options)

    prepare = subparsers.add_parser(
        "prepare",
        help="Build a validated browser-ready Smart Search handoff",
    )
    prepare.add_argument("query_text", nargs="?")
    prepare.add_argument(
        "--search-by",
        choices=sorted(SEARCH_BY_VALUES),
        default="SmartSearch",
    )
    prepare.add_argument("--location", default="All Locations")
    prepare.add_argument("--last-name")
    prepare.add_argument("--first-name")
    prepare.add_argument("--middle-name")
    prepare.add_argument("--suffix")
    prepare.add_argument("--phone-number")
    prepare.add_argument("--fbi-number")
    prepare.add_argument("--so-number")
    prepare.add_argument("--booking-number")
    prepare.add_argument("--case-type", default="All Case Types")
    prepare.add_argument("--case-status")
    prepare.add_argument("--file-date-start")
    prepare.add_argument("--file-date-end")
    prepare.add_argument("--judicial-officer")
    prepare.add_argument("--judgment-type")
    prepare.add_argument("--judgment-date-from")
    prepare.add_argument("--judgment-date-to")
    prepare.add_argument("--warrant-type")
    prepare.add_argument("--warrant-status")
    prepare.add_argument("--warrant-date-issued-from")
    prepare.add_argument("--warrant-date-issued-to")
    prepare.add_argument(
        "--search-cases",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    prepare.add_argument(
        "--search-judgments",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    prepare.add_argument(
        "--search-warrants",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    prepare.add_argument(
        "--party-name",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    prepare.add_argument(
        "--nickname",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    prepare.add_argument(
        "--business-name",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    prepare.add_argument(
        "--soundex",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    add_output_args(prepare)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Oregon Smart Search {args.command}",
        result_count=len(result.records),
    ):
        return
    if getattr(args, "json_out", False):
        return
    print(
        f"Oregon Smart Search {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        print(f"  {record.get('record_kind')} | {record.get('canonical_ref')}")
    for error in result.errors:
        print(f"  {error.code}: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
