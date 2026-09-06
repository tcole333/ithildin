#!/usr/bin/env python3
"""Query Los Angeles Superior Court civil case summaries and tentative rulings.

The official court exposes two complementary anonymous civil-record flows:

* Case Summary accepts an exact case number and returns case metadata, future
  hearings, parties, a filed-document index, past proceedings, and register
  actions.
* Tentative Rulings publishes a changing list of location/department/date
  selections.  A selection can contain full rulings for multiple cases.

Examples:
    uv run python tools/query_los_angeles_court.py case 24NNCV00427 --json
    uv run python tools/query_los_angeles_court.py selections --json
    uv run python tools/query_los_angeles_court.py rulings \
        "ALH,3,07/30/2026" --output /tmp/la-rulings.json
    uv run python tools/query_los_angeles_court.py rulings all --json
    uv run python tools/query_los_angeles_court.py sources --json
    uv run python tools/query_los_angeles_court.py probe --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from tools.public_records_store import canonical_court_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        inferred_schema,
        schema_fingerprint,
        system_trust_session,
    )
    from public_records_store import canonical_court_ref


SOURCE_ID = "us-ca-los-angeles-superior-civil"
STATE_CODE = "CA"
COUNTY_GEOID = "06037"
COURT_ID = "ca-los-angeles-superior-court-civil"
COURT_NAME = (
    "Superior Court of California, County of Los Angeles, Civil Division"
)
BASE_URL = "https://www.lacourt.ca.gov"
COURT_LANDING_URL = f"{BASE_URL}/pages/lp/civil"
CASE_SEARCH_URL = f"{BASE_URL}/casesummary/v2web3/?casetype=civil"
CASE_RESULT_URL = f"{BASE_URL}/casesummary/v2web3/CaseSummary"
TENTATIVE_INDEX_URL = (
    f"{BASE_URL}/tentativeRulingNet/ui/main.aspx?casetype=civil"
)
TENTATIVE_RESULT_URL = (
    f"{BASE_URL}/tentativeRulingNet/ui/Result.aspx?Referer=Index"
)
TENTATIVE_SELECTOR_NAME = (
    "ctl00$ctl00$siteMasterHolder$basicBodyHolder$List2DeptDate"
)
NAME_INDEX_URL = f"{BASE_URL}/paos/v2web3/CivilIndex"
DOCUMENT_IMAGE_URL = f"{BASE_URL}/paos/v2web3/DocumentImages"
FEE_INFORMATION_URL = f"{BASE_URL}/paos/v2web3/FeeInformation"
FAMILY_CASE_SEARCH_URL = (
    f"{BASE_URL}/casesummary/v2web3/?casetype=familylaw"
)
SMALL_CLAIMS_CASE_SEARCH_URL = (
    f"{BASE_URL}/casesummary/v2web3/?casetype=smallclaims"
)
PROBATE_CASE_SEARCH_URL = (
    f"{BASE_URL}/casesummary/v2web3/?casetype=probate"
)
APPELLATE_TENTATIVE_URL = (
    f"{BASE_URL}/tentativeRulingNet/ui/main.aspx?casetype=appellate"
)
PROBE_CASE_NUMBER = "24NNCV00427"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)

SOURCE_WARNINGS = (
    "Case Summary states that it is not the official court record.",
    "Tentative rulings are provisional and may change before the hearing.",
    "Filed-document metadata is public in Case Summary; document-image delivery "
    "uses the court's separate paid service.",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Los Angeles Superior Court Civil Case Summary and Tentative Rulings",
    source_role="county_superior_civil_case_docket_and_tentative_ruling",
    base_url=COURT_LANDING_URL,
    dataset_id="lasc-civil-online-services",
    metadata={
        "authority": "Superior Court of California, County of Los Angeles",
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_id": COURT_ID,
        "authentication": "none",
        "case_summary_url": CASE_SEARCH_URL,
        "tentative_ruling_index_url": TENTATIVE_INDEX_URL,
        "tentative_ruling_selector": TENTATIVE_SELECTOR_NAME,
        "name_index_complement": NAME_INDEX_URL,
        "document_image_complement": DOCUMENT_IMAGE_URL,
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Los Angeles County, California",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
)


class LACourtError(RuntimeError):
    """Structured Los Angeles court source error."""

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

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class LASelectionError(LACourtError):
    """A requested source-native selector is unavailable."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            category="query_selection",
            details=details,
        )


class LASourceChangedError(LACourtError):
    """The source no longer matches the verified HTML contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code,
            message,
            status=ResultStatus.SOURCE_CHANGED,
            category="source_schema",
            details=details,
        )


@dataclass(frozen=True)
class CaseSearchPage:
    request_verification_token: str
    courthouse_options: Mapping[str, str]
    schema_fingerprint: str


@dataclass(frozen=True)
class PartyRow:
    name: str
    role: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "role": self.role}


@dataclass(frozen=True)
class HearingRow:
    hearing_date: str
    hearing_time: str
    department: str
    location: str
    hearing_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "hearing_date": self.hearing_date,
            "hearing_time": self.hearing_time,
            "department": self.department,
            "location": self.location,
            "hearing_type": self.hearing_type,
        }


@dataclass(frozen=True)
class DocumentRow:
    filed_date: str
    description: str
    filer: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "filed_date": self.filed_date,
            "description": self.description,
            "filer": self.filer,
        }


@dataclass(frozen=True)
class ProceedingRow:
    proceeding_datetime: str
    department: str
    proceeding_type: str
    disposition: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "proceeding_datetime": self.proceeding_datetime,
            "department": self.department,
            "proceeding_type": self.proceeding_type,
            "disposition": self.disposition,
        }


@dataclass(frozen=True)
class RegisterActionRow:
    action_date: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "action_date": self.action_date,
            "description": self.description,
        }


@dataclass(frozen=True)
class CaseSummaryPage:
    case_number: str
    case_title: str
    filing_courthouse: str
    filing_date: str
    case_type: str
    status: str
    document_image_url: str
    future_hearings: tuple[HearingRow, ...]
    parties: tuple[PartyRow, ...]
    documents: tuple[DocumentRow, ...]
    past_proceedings: tuple[ProceedingRow, ...]
    register_actions: tuple[RegisterActionRow, ...]
    source_url: str
    response_sha256: str
    schema_fingerprint: str


@dataclass(frozen=True)
class CaseLookup:
    page: CaseSummaryPage | None
    no_match_message: str | None = None
    native_courthouse_value: str | None = None


@dataclass(frozen=True)
class TentativeSelection:
    native_value: str
    label: str
    location_code: str
    department: str
    hearing_date: str
    hearing_date_iso: str

    def to_dict(self) -> dict[str, str]:
        return {
            "native_value": self.native_value,
            "label": self.label,
            "location_code": self.location_code,
            "department": self.department,
            "hearing_date": self.hearing_date,
            "hearing_date_iso": self.hearing_date_iso,
        }


@dataclass(frozen=True)
class TentativeIndexPage:
    hidden_fields: Mapping[str, str]
    selections: tuple[TentativeSelection, ...]
    source_url: str
    response_sha256: str
    schema_fingerprint: str


@dataclass(frozen=True)
class TentativeRuling:
    case_number: str
    hearing_date: str
    hearing_date_iso: str
    department: str
    full_text: str
    full_text_sha256: str
    duplicate_ordinal: int
    source_url: str
    response_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_number": self.case_number,
            "hearing_date": self.hearing_date,
            "hearing_date_iso": self.hearing_date_iso,
            "department": self.department,
            "full_text": self.full_text,
            "full_text_sha256": self.full_text_sha256,
            "duplicate_ordinal": self.duplicate_ordinal,
            "source_url": self.source_url,
            "response_sha256": self.response_sha256,
        }


@dataclass(frozen=True)
class TentativeResultPage:
    rulings: tuple[TentativeRuling, ...]
    message: str | None
    source_url: str
    response_sha256: str
    schema_fingerprint: str


@dataclass(frozen=True)
class TentativeCollection:
    records: tuple[Mapping[str, Any], ...]
    selection_count_snapshot: int
    selections_requested: int
    selections_fetched: int
    next_selection_offset: int | None
    incomplete_error: LACourtError | None = None


@dataclass(frozen=True)
class ProbeSnapshot:
    case_search: CaseSearchPage
    case_summary: CaseSummaryPage
    tentative_index: TentativeIndexPage
    tentative_selection: TentativeSelection | None
    tentative_result: TentativeResultPage | None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _required_text(value: Any, field_name: str) -> str:
    normalized = _text(value)
    if normalized is None:
        raise LASourceChangedError(
            "required_field_missing",
            f"Los Angeles civil response lacks {field_name}",
            details={"field": field_name},
        )
    return normalized


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(str(html).replace("\x00", ""), "html.parser")


def _table_rows(table: Tag) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        rows.append(
            [
                _text(cell.get_text(" ", strip=True)) or ""
                for cell in cells
            ]
        )
    return rows


def _source_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise LASourceChangedError(
            "source_date_changed",
            f"Los Angeles civil source date is unparseable: {value!r}",
            details={"value": value},
        ) from error


def _source_long_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%B %d, %Y").date().isoformat()
    except ValueError as error:
        raise LASourceChangedError(
            "source_date_changed",
            f"Los Angeles tentative-ruling date is unparseable: {value!r}",
            details={"value": value},
        ) from error


def _source_datetime(value: str) -> tuple[str, str]:
    for pattern in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.date().isoformat(), parsed.time().isoformat()
        except ValueError:
            continue
    raise LASourceChangedError(
        "source_datetime_changed",
        f"Los Angeles civil source date/time is unparseable: {value!r}",
        details={"value": value},
    )


def _source_time(value: str) -> str | None:
    for pattern in ("%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(value.upper(), pattern).time().isoformat()
        except ValueError:
            continue
    return None


def _identity_text(value: str | None) -> str:
    return (_text(value) or "").casefold()


def _native_id(prefix: str, basis: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        canonical_json(dict(basis)).encode("utf-8")
    ).hexdigest()
    return f"{prefix}:{digest}"


def _occurrence_numbers(
    values: Iterable[Any],
    key: Any,
) -> Iterable[tuple[Any, int]]:
    counts: defaultdict[str, int] = defaultdict(int)
    for value in values:
        identity_key = canonical_json(key(value))
        ordinal = counts[identity_key]
        counts[identity_key] += 1
        yield value, ordinal


def parse_case_search_html(html: str) -> CaseSearchPage:
    """Parse the civil exact-case form and native courthouse options."""

    soup = _soup(html)
    form = soup.find("form", id="caseSummaryForm")
    if not isinstance(form, Tag):
        raise LASourceChangedError(
            "case_search_form_missing",
            "Los Angeles civil case-search form is missing",
            details={"url": CASE_SEARCH_URL},
        )
    if str(form.get("method") or "").casefold() != "post":
        raise LASourceChangedError(
            "case_search_method_changed",
            "Los Angeles civil case-search method changed",
            details={"url": CASE_SEARCH_URL},
        )
    observed_fields = {
        str(field.get("name"))
        for field in form.find_all(["input", "select", "button"])
        if field.get("name")
    }
    required_fields = {
        "txtCaseNumber",
        "ddlCourthouse",
        "action",
        "__RequestVerificationToken",
    }
    missing = sorted(required_fields - observed_fields)
    if missing:
        raise LASourceChangedError(
            "case_search_fields_changed",
            "Los Angeles civil case-search fields changed",
            details={"missing_fields": missing},
        )
    token = form.find(
        "input",
        attrs={"name": "__RequestVerificationToken"},
    )
    token_value = _required_text(
        token.get("value") if isinstance(token, Tag) else None,
        "case-search verification token",
    )
    options: dict[str, str] = {}
    select = form.find("select", attrs={"name": "ddlCourthouse"})
    if isinstance(select, Tag):
        for option in select.find_all("option"):
            native_value = str(option.get("value") or "").strip()
            options[native_value] = (
                _text(option.get_text(" ", strip=True)) or ""
            )
    return CaseSearchPage(
        request_verification_token=token_value,
        courthouse_options=options,
        schema_fingerprint=schema_fingerprint(
            {
                "form_id": "caseSummaryForm",
                "method": "post",
                "fields": sorted(observed_fields),
                "courthouse_value_shape": "code_semicolon_label",
            }
        ),
    )


def _section_table(soup: BeautifulSoup, anchor_name: str) -> Tag:
    anchor = soup.find("a", attrs={"name": anchor_name})
    if not isinstance(anchor, Tag):
        raise LASourceChangedError(
            "case_section_missing",
            f"Los Angeles civil case section {anchor_name!r} is missing",
            details={"section": anchor_name, "url": CASE_RESULT_URL},
        )
    table = anchor.find_next("table", class_="dataTable")
    if not isinstance(table, Tag):
        raise LASourceChangedError(
            "case_section_table_missing",
            f"Los Angeles civil case section {anchor_name!r} lacks its table",
            details={"section": anchor_name, "url": CASE_RESULT_URL},
        )
    return table


def parse_case_lookup_html(
    html: str,
    *,
    expected_case_number: str | None = None,
    source_url: str = CASE_RESULT_URL,
) -> CaseLookup:
    """Parse a six-section civil Case Summary or its no-match response."""

    soup = _soup(html)
    messages = [
        message
        for node in soup.select(
            ".message, .validation-summary-errors, .field-validation-error"
        )
        if (message := _text(node.get_text(" ", strip=True))) is not None
    ]
    no_match = next(
        (
            message
            for message in messages
            if re.search(r"\bno match found for case number\b", message, re.I)
        ),
        None,
    )
    if no_match is not None:
        return CaseLookup(page=None, no_match_message=no_match)

    case_rows = _table_rows(_section_table(soup, "CaseInformation"))
    case_fields: dict[str, str] = {}
    for row in case_rows:
        if len(row) != 2:
            raise LASourceChangedError(
                "case_information_width_changed",
                "Los Angeles civil Case Information row width changed",
                details={"row": row},
            )
        case_fields[row[0].strip().rstrip(":").casefold()] = row[1]
    required_case_fields = (
        "case information",
        "case title",
        "filing courthouse",
        "filing date",
        "case type",
        "status",
    )
    missing = [
        field for field in required_case_fields if not case_fields.get(field)
    ]
    if missing:
        if messages:
            raise LASelectionError(
                "source_validation_error",
                "; ".join(messages),
                details={"messages": messages},
            )
        raise LASourceChangedError(
            "case_information_fields_changed",
            "Los Angeles civil Case Information fields changed",
            details={"missing_fields": missing},
        )
    case_number = case_fields["case information"]
    if (
        expected_case_number is not None
        and case_number.casefold() != expected_case_number.strip().casefold()
    ):
        raise LASourceChangedError(
            "case_number_mismatch",
            "Los Angeles civil result case number differs from the query",
            details={
                "expected": expected_case_number,
                "observed": case_number,
            },
        )

    image_link = soup.find(
        "a",
        href=lambda value: isinstance(value, str)
        and "/DocumentImages/SearchCaseNumber" in value,
    )
    if not isinstance(image_link, Tag):
        raise LASourceChangedError(
            "document_image_link_missing",
            "Los Angeles civil document-image complement link is missing",
            details={"url": source_url},
        )
    document_image_url = urljoin(source_url, str(image_link.get("href")))

    future_hearings: list[HearingRow] = []
    for index, row in enumerate(
        _table_rows(_section_table(soup, "FutureHearings"))
    ):
        if len(row) != 5:
            raise LASourceChangedError(
                "future_hearing_width_changed",
                "Los Angeles civil Future Hearings row width changed",
                details={"row_index": index, "row": row},
            )
        future_hearings.append(
            HearingRow(
                hearing_date=_required_text(row[0], "future hearing date"),
                hearing_time=_required_text(row[1], "future hearing time"),
                department=_required_text(row[2], "future hearing department"),
                location=_required_text(row[3], "future hearing location"),
                hearing_type=_required_text(row[4], "future hearing type"),
            )
        )

    parties: list[PartyRow] = []
    for index, row in enumerate(_table_rows(_section_table(soup, "Parties"))):
        if len(row) != 2:
            raise LASourceChangedError(
                "party_width_changed",
                "Los Angeles civil Party Information row width changed",
                details={"row_index": index, "row": row},
            )
        parties.append(
            PartyRow(
                name=_required_text(row[0], "party name"),
                role=_required_text(row[1], "party role"),
            )
        )

    documents: list[DocumentRow] = []
    for index, row in enumerate(
        _table_rows(_section_table(soup, "DocumentsFiled"))
    ):
        if len(row) != 3:
            raise LASourceChangedError(
                "document_width_changed",
                "Los Angeles civil Documents Filed row width changed",
                details={"row_index": index, "row": row},
            )
        documents.append(
            DocumentRow(
                filed_date=_required_text(row[0], "document filed date"),
                description=_required_text(row[1], "document description"),
                filer=_text(row[2]),
            )
        )

    past_proceedings: list[ProceedingRow] = []
    for index, row in enumerate(
        _table_rows(_section_table(soup, "PastProceedings"))
    ):
        if len(row) != 4:
            raise LASourceChangedError(
                "proceeding_width_changed",
                "Los Angeles civil Past Proceedings row width changed",
                details={"row_index": index, "row": row},
            )
        past_proceedings.append(
            ProceedingRow(
                proceeding_datetime=_required_text(
                    row[0], "past proceeding date and time"
                ),
                department=_required_text(
                    row[1], "past proceeding department"
                ),
                proceeding_type=_required_text(
                    row[2], "past proceeding type"
                ),
                disposition=_text(row[3]),
            )
        )

    register_actions: list[RegisterActionRow] = []
    for index, row in enumerate(
        _table_rows(_section_table(soup, "RegisterOfAction"))
    ):
        if len(row) != 2:
            raise LASourceChangedError(
                "register_action_width_changed",
                "Los Angeles civil Register Of Actions row width changed",
                details={"row_index": index, "row": row},
            )
        register_actions.append(
            RegisterActionRow(
                action_date=_required_text(row[0], "register action date"),
                description=_required_text(
                    row[1], "register action description"
                ),
            )
        )

    shape = {
        "case": {
            "case_number": case_number,
            "case_title": case_fields["case title"],
            "filing_courthouse": case_fields["filing courthouse"],
            "filing_date": case_fields["filing date"],
            "case_type": case_fields["case type"],
            "status": case_fields["status"],
        },
        "future_hearing": (
            future_hearings[0].to_dict() if future_hearings else None
        ),
        "party": parties[0].to_dict() if parties else None,
        "document": documents[0].to_dict() if documents else None,
        "past_proceeding": (
            past_proceedings[0].to_dict() if past_proceedings else None
        ),
        "register_action": (
            register_actions[0].to_dict() if register_actions else None
        ),
    }
    return CaseLookup(
        page=CaseSummaryPage(
            case_number=case_number,
            case_title=case_fields["case title"],
            filing_courthouse=case_fields["filing courthouse"],
            filing_date=case_fields["filing date"],
            case_type=case_fields["case type"],
            status=case_fields["status"],
            document_image_url=document_image_url,
            future_hearings=tuple(future_hearings),
            parties=tuple(parties),
            documents=tuple(documents),
            past_proceedings=tuple(past_proceedings),
            register_actions=tuple(register_actions),
            source_url=source_url,
            response_sha256=hashlib.sha256(
                html.encode("utf-8")
            ).hexdigest(),
            schema_fingerprint=schema_fingerprint(inferred_schema([shape])),
        )
    )


def parse_tentative_index_html(
    html: str,
    *,
    source_url: str = TENTATIVE_INDEX_URL,
) -> TentativeIndexPage:
    """Parse the complete current WebForms selection inventory."""

    soup = _soup(html)
    selector = soup.find(
        "select",
        attrs={"name": TENTATIVE_SELECTOR_NAME},
    )
    if not isinstance(selector, Tag):
        raise LASourceChangedError(
            "tentative_selector_missing",
            "Los Angeles civil tentative-ruling selector is missing",
            details={
                "selector": TENTATIVE_SELECTOR_NAME,
                "url": source_url,
            },
        )
    hidden_fields = {
        str(field.get("name")): str(field.get("value") or "")
        for field in soup.find_all("input", attrs={"type": "hidden"})
        if field.get("name")
    }
    missing_state = [
        field
        for field in ("__VIEWSTATE", "__EVENTVALIDATION")
        if field not in hidden_fields
    ]
    if missing_state:
        raise LASourceChangedError(
            "tentative_webforms_state_missing",
            "Los Angeles civil tentative-ruling WebForms state changed",
            details={"missing_fields": missing_state, "url": source_url},
        )

    selections: list[TentativeSelection] = []
    seen_values: set[str] = set()
    for index, option in enumerate(selector.find_all("option")):
        native_value = str(option.get("value") or "").strip()
        label = _text(option.get_text(" ", strip=True))
        if not native_value or label is None:
            raise LASourceChangedError(
                "tentative_selection_missing_value",
                "Los Angeles tentative-ruling selection is incomplete",
                details={"option_index": index},
            )
        if native_value in seen_values:
            raise LASourceChangedError(
                "tentative_selection_duplicate",
                "Los Angeles tentative-ruling selector contains a duplicate value",
                details={"native_value": native_value},
            )
        seen_values.add(native_value)
        parts = native_value.rsplit(",", 2)
        if len(parts) != 3:
            raise LASourceChangedError(
                "tentative_selection_shape_changed",
                "Los Angeles tentative-ruling selection value changed shape",
                details={"native_value": native_value},
            )
        location_code, department, hearing_date = parts
        selections.append(
            TentativeSelection(
                native_value=native_value,
                label=label,
                location_code=_required_text(
                    location_code, "tentative location code"
                ),
                department=_required_text(
                    department, "tentative department"
                ),
                hearing_date=_required_text(
                    hearing_date, "tentative hearing date"
                ),
                hearing_date_iso=_source_date(hearing_date.strip()),
            )
        )

    fingerprint = schema_fingerprint(
        {
            "selector_name": TENTATIVE_SELECTOR_NAME,
            "hidden_fields": sorted(hidden_fields),
            "selection_fields": inferred_schema(
                [
                    selections[0].to_dict()
                    if selections
                    else {
                        "native_value": "",
                        "label": "",
                        "location_code": "",
                        "department": "",
                        "hearing_date": "",
                        "hearing_date_iso": "",
                    }
                ]
            )["fields"],
        }
    )
    return TentativeIndexPage(
        hidden_fields=hidden_fields,
        selections=tuple(selections),
        source_url=source_url,
        response_sha256=hashlib.sha256(
            html.encode("utf-8")
        ).hexdigest(),
        schema_fingerprint=fingerprint,
    )


def _heading_key(tag: Tag) -> str:
    return (_text(tag.get_text(" ", strip=True)) or "").rstrip(":").casefold()


def _strings_between(start: Tag, end: Tag | None) -> list[str]:
    values: list[str] = []
    for node in start.next_elements:
        if node is end:
            break
        if isinstance(node, NavigableString):
            parent = node.parent
            inside_start = False
            while isinstance(parent, Tag):
                if parent is start:
                    inside_start = True
                    break
                parent = parent.parent
            if inside_start:
                continue
            value = _text(node)
            if value is not None:
                values.append(value)
    return values


def parse_tentative_result_html(
    html: str,
    *,
    source_url: str = TENTATIVE_RESULT_URL,
) -> TentativeResultPage:
    """Split one tentative result page into case-specific ruling occurrences."""

    soup = _soup(html)
    body = soup.find("div", id="speechSynthesis")
    page_text = _text(soup.get_text(" ", strip=True)) or ""
    if not isinstance(body, Tag):
        no_ruling = re.search(
            r"\bno (?:tentative )?rulings? (?:have|has) been published\b",
            page_text,
            flags=re.IGNORECASE,
        )
        if no_ruling:
            return TentativeResultPage(
                rulings=(),
                message=no_ruling.group(0),
                source_url=source_url,
                response_sha256=hashlib.sha256(
                    html.encode("utf-8")
                ).hexdigest(),
                schema_fingerprint=schema_fingerprint(
                    {
                        "result_container": None,
                        "message_kind": "no_rulings_published",
                    }
                ),
            )
        raise LASourceChangedError(
            "tentative_result_body_missing",
            "Los Angeles tentative-ruling result body is missing",
            details={"url": source_url},
        )

    case_markers = [
        tag
        for tag in body.find_all("b")
        if _heading_key(tag) == "case number"
    ]
    response_sha = hashlib.sha256(html.encode("utf-8")).hexdigest()
    parsed: list[dict[str, str]] = []
    for index, case_marker in enumerate(case_markers):
        hearing_marker = case_marker.find_next("b")
        department_marker = (
            hearing_marker.find_next("b")
            if isinstance(hearing_marker, Tag)
            else None
        )
        if (
            not isinstance(hearing_marker, Tag)
            or _heading_key(hearing_marker) != "hearing date"
            or not isinstance(department_marker, Tag)
            or _heading_key(department_marker) != "dept"
        ):
            raise LASourceChangedError(
                "tentative_occurrence_header_changed",
                "Los Angeles tentative-ruling occurrence header changed",
                details={"occurrence_index": index},
            )
        next_case = (
            case_markers[index + 1]
            if index + 1 < len(case_markers)
            else None
        )
        case_number = _required_text(
            " ".join(_strings_between(case_marker, hearing_marker)),
            "tentative case number",
        )
        hearing_date = _required_text(
            " ".join(_strings_between(hearing_marker, department_marker)),
            "tentative hearing date",
        )
        department_and_text = _strings_between(
            department_marker,
            next_case,
        )
        if len(department_and_text) < 2:
            raise LASourceChangedError(
                "tentative_ruling_text_missing",
                "Los Angeles tentative-ruling occurrence lacks full text",
                details={
                    "occurrence_index": index,
                    "case_number": case_number,
                },
            )
        department = _required_text(
            department_and_text[0],
            "tentative department",
        )
        full_text = _required_text(
            " ".join(department_and_text[1:]),
            "tentative ruling full text",
        )
        parsed.append(
            {
                "case_number": case_number,
                "hearing_date": hearing_date,
                "department": department,
                "full_text": full_text,
            }
        )

    if not parsed:
        body_message = _text(body.get_text(" ", strip=True))
        return TentativeResultPage(
            rulings=(),
            message=body_message,
            source_url=source_url,
            response_sha256=response_sha,
            schema_fingerprint=schema_fingerprint(
                {
                    "result_container": "speechSynthesis",
                    "occurrence": None,
                }
            ),
        )

    rulings: list[TentativeRuling] = []
    for row, ordinal in _occurrence_numbers(
        parsed,
        lambda value: {
            "case_number": value["case_number"].casefold(),
            "hearing_date": value["hearing_date"],
            "department": value["department"].casefold(),
            "full_text_sha256": hashlib.sha256(
                value["full_text"].encode("utf-8")
            ).hexdigest(),
        },
    ):
        full_text_sha = hashlib.sha256(
            row["full_text"].encode("utf-8")
        ).hexdigest()
        rulings.append(
            TentativeRuling(
                case_number=row["case_number"],
                hearing_date=row["hearing_date"],
                hearing_date_iso=_source_long_date(row["hearing_date"]),
                department=row["department"],
                full_text=row["full_text"],
                full_text_sha256=full_text_sha,
                duplicate_ordinal=ordinal,
                source_url=source_url,
                response_sha256=response_sha,
            )
        )
    shape = inferred_schema(
        [
            {
            "case_number": rulings[0].case_number,
            "hearing_date": rulings[0].hearing_date,
            "hearing_date_iso": rulings[0].hearing_date_iso,
            "department": rulings[0].department,
            "full_text": rulings[0].full_text,
            "full_text_sha256": rulings[0].full_text_sha256,
            }
        ]
    )
    return TentativeResultPage(
        rulings=tuple(rulings),
        message=None,
        source_url=source_url,
        response_sha256=response_sha,
        schema_fingerprint=schema_fingerprint(shape),
    )


def _resolve_courthouse_value(
    requested: str | None,
    offered: Mapping[str, str],
) -> str:
    selector = _text(requested) or ""
    if not selector:
        return ""
    if selector in offered:
        return selector
    casefold_matches = [
        value
        for value in offered
        if value.casefold() == selector.casefold()
    ]
    if len(casefold_matches) == 1:
        return casefold_matches[0]
    code_matches = [
        value
        for value in offered
        if value.partition(";")[0].casefold() == selector.casefold()
    ]
    if len(code_matches) == 1:
        return code_matches[0]
    raise LASelectionError(
        "unknown_courthouse",
        f"courthouse selector {selector!r} is not offered by the source",
        details={"available_courthouses": dict(offered)},
    )


def _resolve_tentative_selection(
    requested: str,
    offered: Sequence[TentativeSelection],
) -> TentativeSelection:
    matches = [
        selection
        for selection in offered
        if selection.native_value == requested
    ]
    if len(matches) == 1:
        return matches[0]
    raise LASelectionError(
        "unknown_tentative_selection",
        f"tentative-ruling selection {requested!r} is not currently offered",
        details={
            "requested": requested,
            "available_count": len(offered),
            "available_values": [
                selection.native_value for selection in offered
            ],
        },
    )


class LosAngelesCourtClient:
    """Paced same-session client for official civil HTML services."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.session = session or system_trust_session()
        self._owns_session = session is None
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper
        self.rate_limiter = MinimumIntervalRateLimiter(
            minimum_interval,
            sleeper=sleeper,
        )
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update(
                {
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
        referer: str | None = None,
    ) -> tuple[str, str]:
        headers = {"Referer": referer} if referer else None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                if method == "GET":
                    response = self.session.get(
                        url,
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=True,
                    )
                else:
                    response = self.session.post(
                        url,
                        data=dict(data or {}),
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=True,
                    )
            except requests.RequestException as error:
                if attempt >= self.retry_policy.max_attempts:
                    raise LACourtError(
                        "transport_error",
                        f"Los Angeles court request failed: {error}",
                        category="transport",
                        retryable=True,
                        details={"url": url, "method": method},
                    ) from error
                self.sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(getattr(response, "status_code", 0))
            if (
                status_code in self.retry_policy.retry_statuses
                and attempt < self.retry_policy.max_attempts
            ):
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise LACourtError(
                    "source_rate_limited",
                    "Los Angeles court rate-limited the request",
                    status=ResultStatus.RATE_LIMITED,
                    category="rate_limit",
                    retryable=True,
                    details={"url": url, "http_status": status_code},
                )
            if status_code in {401, 403}:
                raise LACourtError(
                    "source_access_restricted",
                    f"Los Angeles court returned HTTP {status_code}",
                    status=ResultStatus.RESTRICTED,
                    category="access",
                    details={"url": url, "http_status": status_code},
                )
            if status_code != 200:
                raise LACourtError(
                    "source_http_error",
                    f"Los Angeles court returned HTTP {status_code}",
                    category="http",
                    retryable=status_code >= 500,
                    details={"url": url, "http_status": status_code},
                )
            content_type = str(
                getattr(response, "headers", {}).get("Content-Type", "")
            ).casefold()
            if content_type and "html" not in content_type:
                raise LASourceChangedError(
                    "non_html_response",
                    "Los Angeles court returned a non-HTML response",
                    details={"url": url, "content_type": content_type},
                )
            final_url = str(getattr(response, "url", url))
            parsed = urlparse(final_url)
            if parsed.hostname and parsed.hostname != "www.lacourt.ca.gov":
                raise LASourceChangedError(
                    "unexpected_redirect",
                    "Los Angeles court redirected outside its official host",
                    details={"requested_url": url, "final_url": final_url},
                )
            return str(response.text), final_url
        raise AssertionError("retry loop exhausted")

    def bootstrap_case(self) -> CaseSearchPage:
        html, _source_url = self._request("GET", CASE_SEARCH_URL)
        return parse_case_search_html(html)

    def case(
        self,
        case_number: str,
        *,
        courthouse: str | None = None,
        bootstrap: CaseSearchPage | None = None,
    ) -> CaseLookup:
        normalized_case = _required_text(case_number, "case number")
        search_page = bootstrap or self.bootstrap_case()
        courthouse_value = _resolve_courthouse_value(
            courthouse,
            search_page.courthouse_options,
        )
        html, source_url = self._request(
            "POST",
            CASE_SEARCH_URL,
            data={
                "txtCaseNumber": normalized_case,
                "ddlCourthouse": courthouse_value,
                "action": "Search",
                "__RequestVerificationToken": (
                    search_page.request_verification_token
                ),
            },
            referer=CASE_SEARCH_URL,
        )
        lookup = parse_case_lookup_html(
            html,
            expected_case_number=normalized_case,
            source_url=source_url,
        )
        return CaseLookup(
            page=lookup.page,
            no_match_message=lookup.no_match_message,
            native_courthouse_value=courthouse_value,
        )

    def bootstrap_tentatives(self) -> TentativeIndexPage:
        html, source_url = self._request("GET", TENTATIVE_INDEX_URL)
        return parse_tentative_index_html(html, source_url=source_url)

    def tentative_rulings(
        self,
        selection_value: str,
        *,
        bootstrap: TentativeIndexPage | None = None,
    ) -> tuple[TentativeSelection, TentativeResultPage]:
        index = bootstrap or self.bootstrap_tentatives()
        selection = _resolve_tentative_selection(
            selection_value,
            index.selections,
        )
        payload = dict(index.hidden_fields)
        payload[TENTATIVE_SELECTOR_NAME] = selection.native_value
        payload["CaseNumber"] = ""
        html, source_url = self._request(
            "POST",
            TENTATIVE_INDEX_URL,
            data=payload,
            referer=TENTATIVE_INDEX_URL,
        )
        return selection, parse_tentative_result_html(
            html,
            source_url=source_url,
        )

    def all_tentative_rulings(
        self,
        *,
        selection_offset: int = 0,
        max_selections: int | None = None,
    ) -> TentativeCollection:
        initial = self.bootstrap_tentatives()
        available = initial.selections
        stop = (
            None
            if max_selections is None
            else selection_offset + max_selections
        )
        requested = available[selection_offset:stop]
        records: list[Mapping[str, Any]] = []
        fetched = 0
        incomplete_error: LACourtError | None = None
        for index, snapshot_selection in enumerate(requested):
            try:
                current = (
                    initial if index == 0 else self.bootstrap_tentatives()
                )
                selection, page = self.tentative_rulings(
                    snapshot_selection.native_value,
                    bootstrap=current,
                )
                records.extend(
                    normalize_tentative_ruling(ruling, selection=selection)
                    for ruling in page.rulings
                )
                fetched += 1
            except LACourtError as error:
                incomplete_error = error
                break
        consumed = selection_offset + fetched
        next_offset = (
            consumed if consumed < len(available) else None
        )
        return TentativeCollection(
            records=tuple(records),
            selection_count_snapshot=len(available),
            selections_requested=len(requested),
            selections_fetched=fetched,
            next_selection_offset=next_offset,
            incomplete_error=incomplete_error,
        )

    def probe(self) -> ProbeSnapshot:
        case_search = self.bootstrap_case()
        case_lookup = self.case(
            PROBE_CASE_NUMBER,
            bootstrap=case_search,
        )
        if case_lookup.page is None:
            raise LASourceChangedError(
                "probe_case_missing",
                "Los Angeles civil probe case stopped resolving",
                details={"case_number": PROBE_CASE_NUMBER},
            )
        tentative_index = self.bootstrap_tentatives()
        if tentative_index.selections:
            selection, result = self.tentative_rulings(
                tentative_index.selections[0].native_value,
                bootstrap=tentative_index,
            )
        else:
            selection = None
            result = None
        return ProbeSnapshot(
            case_search=case_search,
            case_summary=case_lookup.page,
            tentative_index=tentative_index,
            tentative_selection=selection,
            tentative_result=result,
        )


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": "los-angeles-superior-civil",
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "superior",
        "division": "civil",
        "official_url": COURT_LANDING_URL,
    }


def _base_case_record(
    case_number: str,
    *,
    caption: str | None,
    filing_date: str | None,
    case_type: str | None,
    status: str | None,
    source_url: str,
) -> dict[str, Any]:
    return {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            case_number,
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(),
        "raw_case_number": case_number,
        "display_case_number": case_number,
        "source_internal_id": None,
        "caption": caption,
        "case_type": case_type,
        "filing_date": filing_date,
        "status": status,
        "native_status": status,
        "access_state": "public",
        "certified_record": False,
        "source_url": source_url,
        "parties": [],
        "docket_entries": [],
        "documents": [],
    }


def _future_hearing_entry(
    case_number: str,
    row: HearingRow,
    ordinal: int,
) -> dict[str, Any]:
    event_date = _source_date(row.hearing_date)
    basis = {
        "case_number": case_number.upper(),
        "section": "future_hearings",
        "event_date": event_date,
        "source_time": row.hearing_time,
        "department": _identity_text(row.department),
        "location": _identity_text(row.location),
        "hearing_type": _identity_text(row.hearing_type),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("future-hearing", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "future_hearing",
        "event_code": None,
        "raw_text": row.hearing_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": _source_time(row.hearing_time),
        "source_event_time_raw": row.hearing_time,
        "department": row.department,
        "location": row.location,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def _past_proceeding_entry(
    case_number: str,
    row: ProceedingRow,
    ordinal: int,
) -> dict[str, Any]:
    event_date, event_time = _source_datetime(row.proceeding_datetime)
    basis = {
        "case_number": case_number.upper(),
        "section": "past_proceedings",
        "event_date": event_date,
        "event_time": event_time,
        "department": _identity_text(row.department),
        "proceeding_type": _identity_text(row.proceeding_type),
        "disposition": _identity_text(row.disposition),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("past-proceeding", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "past_proceeding",
        "event_code": None,
        "raw_text": row.proceeding_type,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "event_time": event_time,
        "department": row.department,
        "disposition": row.disposition,
        "document_available": False,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def _register_action_entry(
    case_number: str,
    row: RegisterActionRow,
    ordinal: int,
) -> dict[str, Any]:
    event_date = _source_date(row.action_date)
    basis = {
        "case_number": case_number.upper(),
        "section": "register_of_actions",
        "event_date": event_date,
        "description": _identity_text(row.description),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_entry_id": _native_id("register-action", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "event_type": "register_of_actions",
        "event_code": None,
        "raw_text": row.description,
        "filed_date": None,
        "entered_date": None,
        "event_date": event_date,
        "document_available": None,
        "access_state": "public",
        "documents": [],
        "raw": row.to_dict(),
    }


def _document_payload(
    case_number: str,
    image_url: str,
    row: DocumentRow,
    ordinal: int,
) -> dict[str, Any]:
    filed_date = _source_date(row.filed_date)
    basis = {
        "case_number": case_number.upper(),
        "section": "documents_filed",
        "filed_date": filed_date,
        "description": _identity_text(row.description),
        "filer": _identity_text(row.filer),
        "duplicate_ordinal": ordinal,
    }
    return {
        "native_document_id": _native_id("document-index-row", basis),
        "identity_kind": "source_fields_sha256_with_duplicate_ordinal",
        "identity_basis": basis,
        "document_type": row.description,
        "filed_date": filed_date,
        "source_url": image_url,
        "sha256": None,
        "mime_type": None,
        "page_count": None,
        "storage_path": None,
        "ocr_status": "not_acquired",
        "certification_status": "uncertified",
        "access_state": "public",
        "native_access_state": "public_index_separate_paid_delivery",
        "acquired_at": None,
        "filer_raw": row.filer,
        "raw": row.to_dict(),
    }


def _slice_values(
    values: Sequence[Any],
    *,
    limit: int | None,
    offset: int,
    cursor_prefix: str,
) -> tuple[list[Any], str | None]:
    selected = list(
        values[offset:] if limit is None else values[offset : offset + limit]
    )
    next_cursor = None
    if limit is not None and offset + limit < len(values):
        next_cursor = f"{cursor_prefix}:{offset + limit}"
    return selected, next_cursor


def normalize_case(
    page: CaseSummaryPage,
    *,
    entry_limit: int | None = None,
    entry_offset: int = 0,
) -> tuple[dict[str, Any], str | None]:
    """Normalize a complete six-section Case Summary."""

    entries: list[dict[str, Any]] = []
    for row, ordinal in _occurrence_numbers(
        page.future_hearings,
        lambda value: value.to_dict(),
    ):
        entries.append(_future_hearing_entry(page.case_number, row, ordinal))
    for row, ordinal in _occurrence_numbers(
        page.past_proceedings,
        lambda value: value.to_dict(),
    ):
        entries.append(_past_proceeding_entry(page.case_number, row, ordinal))
    for row, ordinal in _occurrence_numbers(
        page.register_actions,
        lambda value: value.to_dict(),
    ):
        entries.append(_register_action_entry(page.case_number, row, ordinal))
    selected_entries, next_cursor = _slice_values(
        entries,
        limit=entry_limit,
        offset=entry_offset,
        cursor_prefix="la-civil-case-entry",
    )
    documents = [
        _document_payload(page.case_number, page.document_image_url, row, ordinal)
        for row, ordinal in _occurrence_numbers(
            page.documents,
            lambda value: value.to_dict(),
        )
    ]
    record = _base_case_record(
        page.case_number,
        caption=page.case_title,
        filing_date=_source_date(page.filing_date),
        case_type=page.case_type,
        status=page.status,
        source_url=page.source_url,
    )
    record.update(
        {
            "filing_courthouse": page.filing_courthouse,
            "parties": [
                {
                    "sequence_no": index,
                    "raw_name": party.name,
                    "role": party.role,
                    "access_state": "public",
                    "raw": party.to_dict(),
                }
                for index, party in enumerate(page.parties, start=1)
            ],
            "docket_entries": selected_entries,
            "documents": documents,
            "document_image_url": page.document_image_url,
            "document_access": {
                "index_access_state": "public_anonymous",
                "image_delivery_access_state": "paid_guest_or_account",
                "service_url": page.document_image_url,
            },
            "source_scope": {
                "record_type": "civil_case_summary",
                "query_key": "exact_case_number",
                "sections": [
                    "case_information",
                    "future_hearings",
                    "parties",
                    "documents_filed",
                    "past_proceedings",
                    "register_of_actions",
                ],
                "name_discovery_service_url": NAME_INDEX_URL,
                "document_image_service_url": page.document_image_url,
            },
            "search_metadata": {
                "source_counts": {
                    "future_hearings": len(page.future_hearings),
                    "parties": len(page.parties),
                    "documents": len(page.documents),
                    "past_proceedings": len(page.past_proceedings),
                    "register_actions": len(page.register_actions),
                    "docket_entries_combined": len(entries),
                },
                "returned_docket_entries": len(selected_entries),
                "docket_entry_offset": entry_offset,
                "docket_entry_limit": entry_limit,
            },
            "provenance": {
                "source_component": "civil_case_summary",
                "search_url": CASE_SEARCH_URL,
                "result_url": page.source_url,
                "response_sha256": page.response_sha256,
            },
            "schema_fingerprint": page.schema_fingerprint,
            "raw": {
                "case_information": {
                    "case_number": page.case_number,
                    "case_title": page.case_title,
                    "filing_courthouse": page.filing_courthouse,
                    "filing_date": page.filing_date,
                    "case_type": page.case_type,
                    "status": page.status,
                },
                "future_hearings": [
                    row.to_dict() for row in page.future_hearings
                ],
                "parties": [row.to_dict() for row in page.parties],
                "documents": [row.to_dict() for row in page.documents],
                "past_proceedings": [
                    row.to_dict() for row in page.past_proceedings
                ],
                "register_actions": [
                    row.to_dict() for row in page.register_actions
                ],
            },
        }
    )
    return record, next_cursor


def normalize_tentative_ruling(
    ruling: TentativeRuling,
    *,
    selection: TentativeSelection,
) -> dict[str, Any]:
    """Normalize one case occurrence from a multi-case ruling page."""

    basis = {
        "selection": selection.native_value,
        "case_number": ruling.case_number.upper(),
        "hearing_date": ruling.hearing_date_iso,
        "department": _identity_text(ruling.department),
        "full_text_sha256": ruling.full_text_sha256,
        "duplicate_ordinal": ruling.duplicate_ordinal,
    }
    native_entry_id = _native_id("tentative-ruling", basis)
    record = _base_case_record(
        ruling.case_number,
        caption=None,
        filing_date=None,
        case_type="Civil",
        status=None,
        source_url=ruling.source_url,
    )
    record.update(
        {
            "occurrence_kind": "tentative_ruling",
            "occurrence_id": native_entry_id,
            "docket_entries": [
                {
                    "native_entry_id": native_entry_id,
                    "identity_kind": (
                        "source_fields_sha256_with_duplicate_ordinal"
                    ),
                    "identity_basis": basis,
                    "event_type": "tentative_ruling",
                    "event_code": "tentative_ruling",
                    "raw_text": ruling.full_text,
                    "filed_date": None,
                    "entered_date": None,
                    "event_date": ruling.hearing_date_iso,
                    "event_time": None,
                    "department": ruling.department,
                    "document_available": False,
                    "access_state": "public",
                    "documents": [],
                    "raw": ruling.to_dict(),
                }
            ],
            "tentative_ruling": {
                "case_number": ruling.case_number,
                "hearing_date": ruling.hearing_date,
                "hearing_date_iso": ruling.hearing_date_iso,
                "department": ruling.department,
                "full_text": ruling.full_text,
                "full_text_sha256": ruling.full_text_sha256,
            },
            "source_scope": {
                "record_type": "civil_tentative_ruling_occurrence",
                "publication_inventory": "current_source_selection_snapshot",
            },
            "provenance": {
                "source_component": "civil_tentative_rulings",
                "index_url": TENTATIVE_INDEX_URL,
                "result_url": ruling.source_url,
                "selection": selection.to_dict(),
                "response_sha256": ruling.response_sha256,
            },
            "schema_fingerprint": schema_fingerprint(
                inferred_schema(
                    [
                        {
                        "case_number": ruling.case_number,
                        "hearing_date": ruling.hearing_date,
                        "hearing_date_iso": ruling.hearing_date_iso,
                        "department": ruling.department,
                        "full_text": ruling.full_text,
                        }
                    ]
                )
            ),
            "raw": {
                "selection": selection.to_dict(),
                "ruling": ruling.to_dict(),
            },
        }
    )
    return record


def normalize_selection(
    selection: TentativeSelection,
    *,
    index: TentativeIndexPage,
) -> dict[str, Any]:
    basis = {"native_value": selection.native_value}
    return {
        "canonical_ref": _native_id("la-tentative-selection", basis),
        "source_id": SOURCE_ID,
        "record_kind": "source_selection",
        "source_component": "civil_tentative_rulings",
        "source_url": index.source_url,
        "access_state": "public",
        **selection.to_dict(),
        "inventory_response_sha256": index.response_sha256,
        "schema_fingerprint": index.schema_fingerprint,
    }


def source_manifest() -> dict[str, Any]:
    """Return verified primary components and useful official complements."""

    return {
        "source_id": SOURCE_ID,
        "primary_components": [
            {
                "component_id": "civil_case_summary",
                "url": CASE_SEARCH_URL,
                "access_state": "public",
                "native_access_state": "free_anonymous_exact_case_number",
                "representations": [
                    "case_metadata",
                    "future_hearings",
                    "parties",
                    "filed_document_index",
                    "past_proceedings",
                    "register_of_actions",
                ],
            },
            {
                "component_id": "civil_tentative_rulings",
                "url": TENTATIVE_INDEX_URL,
                "access_state": "public",
                "native_access_state": (
                    "free_anonymous_current_selection_full_text"
                ),
                "representations": [
                    "location_department_hearing_date_inventory",
                    "case_number",
                    "hearing_date",
                    "department",
                    "full_tentative_ruling_text",
                ],
            },
        ],
        "complementary_sources": [
            {
                "component_id": "civil_name_index",
                "url": NAME_INDEX_URL,
                "access_state": "paid",
                "native_access_state": "paid_guest_or_account_name_search",
                "relationship": "case_number_discovery_complement",
            },
            {
                "component_id": "civil_document_images",
                "url": DOCUMENT_IMAGE_URL,
                "access_state": "paid",
                "native_access_state": "paid_guest_or_account_image_delivery",
                "relationship": "case_summary_document_index_complement",
                "fee_information_url": FEE_INFORMATION_URL,
            },
            {
                "component_id": "family_law_case_summary",
                "url": FAMILY_CASE_SEARCH_URL,
                "access_state": "public",
                "native_access_state": "free_anonymous_exact_case_number",
                "relationship": "sibling_case_type",
            },
            {
                "component_id": "small_claims_case_summary",
                "url": SMALL_CLAIMS_CASE_SEARCH_URL,
                "access_state": "public",
                "native_access_state": "free_anonymous_exact_case_number",
                "relationship": "sibling_case_type",
            },
            {
                "component_id": "probate_case_summary",
                "url": PROBATE_CASE_SEARCH_URL,
                "access_state": "public",
                "native_access_state": "free_anonymous_exact_case_number",
                "relationship": "sibling_case_type",
            },
            {
                "component_id": "appellate_tentative_rulings",
                "url": APPELLATE_TENTATIVE_URL,
                "access_state": "public",
                "native_access_state": "free_anonymous_current_publication",
                "relationship": "appellate_division_complement",
            },
        ],
    }


def source_records() -> list[dict[str, Any]]:
    manifest = source_manifest()
    records: list[dict[str, Any]] = []
    for role in ("primary_components", "complementary_sources"):
        for component in manifest[role]:
            records.append(
                {
                    "canonical_ref": (
                        f"STATECOURT-SOURCE:{SOURCE_ID}/"
                        f"{component['component_id']}"
                    ),
                    "source_id": SOURCE_ID,
                    "record_kind": "source_component",
                    "component_role": (
                        "primary" if role == "primary_components" else "complement"
                    ),
                    **component,
                }
            )
    return records


def _probe_record(snapshot: ProbeSnapshot) -> dict[str, Any]:
    tentative_result = snapshot.tentative_result
    return {
        "canonical_ref": f"STATECOURT:{SOURCE_ID}/{COURT_ID}/probe",
        "source_id": SOURCE_ID,
        "record_kind": "probe",
        "source_url": COURT_LANDING_URL,
        "court": _court_payload(),
        "probe_case_number": snapshot.case_summary.case_number,
        "case_search_schema_fingerprint": (
            snapshot.case_search.schema_fingerprint
        ),
        "case_summary_schema_fingerprint": (
            snapshot.case_summary.schema_fingerprint
        ),
        "case_summary_response_sha256": (
            snapshot.case_summary.response_sha256
        ),
        "case_summary_counts": {
            "future_hearings": len(snapshot.case_summary.future_hearings),
            "parties": len(snapshot.case_summary.parties),
            "documents": len(snapshot.case_summary.documents),
            "past_proceedings": len(snapshot.case_summary.past_proceedings),
            "register_actions": len(snapshot.case_summary.register_actions),
        },
        "tentative_index_schema_fingerprint": (
            snapshot.tentative_index.schema_fingerprint
        ),
        "tentative_selection_count": len(
            snapshot.tentative_index.selections
        ),
        "tentative_probe_selection": (
            snapshot.tentative_selection.to_dict()
            if snapshot.tentative_selection
            else None
        ),
        "tentative_result_schema_fingerprint": (
            tentative_result.schema_fingerprint
            if tentative_result
            else None
        ),
        "tentative_ruling_count": (
            len(tentative_result.rulings) if tentative_result else 0
        ),
        "tentative_result_response_sha256": (
            tentative_result.response_sha256
            if tentative_result
            else None
        ),
    }


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any]
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "case":
        parameters = {
            "case_number": args.case_number,
            "courthouse": args.courthouse,
            "docket_entry_limit": args.limit,
            "docket_entry_offset": args.offset,
        }
        requested_limit = args.limit
        cursor = f"la-civil-case-entry:{args.offset}"
    elif args.command == "selections":
        parameters = {
            "limit": args.limit,
            "offset": args.offset,
        }
        requested_limit = args.limit
        cursor = f"la-tentative-selection:{args.offset}"
    elif args.command == "rulings":
        parameters = {
            "selection": args.selection,
            "max_selections": args.max_selections,
            "selection_offset": args.selection_offset,
        }
        requested_limit = args.max_selections
        cursor = f"la-tentative-selection:{args.selection_offset}"
    elif args.command == "probe":
        parameters = {"case_number": PROBE_CASE_NUMBER}
        requested_limit = 1
    else:
        parameters = {}
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
        ),
    )


def _execute_command(
    args: argparse.Namespace,
    client: LosAngelesCourtClient | Any | None,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "sources":
        return PublicRecordsResult.success(
            query,
            source_records(),
            warnings=SOURCE_WARNINGS,
        )
    if client is None:
        raise AssertionError("client is required for network commands")
    if args.command == "case":
        lookup = client.case(
            args.case_number,
            courthouse=args.courthouse,
        )
        if lookup.page is None:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        record, next_cursor = normalize_case(
            lookup.page,
            entry_limit=args.limit,
            entry_offset=args.offset,
        )
        record["search_metadata"]["native_courthouse_value"] = (
            lookup.native_courthouse_value
        )
        return PublicRecordsResult.success(
            query,
            [record],
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "selections":
        index = client.bootstrap_tentatives()
        selected, next_cursor = _slice_values(
            index.selections,
            limit=args.limit,
            offset=args.offset,
            cursor_prefix="la-tentative-selection",
        )
        return PublicRecordsResult.success(
            query,
            [
                normalize_selection(selection, index=index)
                for selection in selected
            ],
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "rulings":
        if args.selection == "all":
            collection = client.all_tentative_rulings(
                selection_offset=args.selection_offset,
                max_selections=args.max_selections,
            )
            next_cursor = (
                f"la-tentative-selection:"
                f"{collection.next_selection_offset}"
                if collection.next_selection_offset is not None
                else None
            )
            if collection.incomplete_error is not None:
                status = (
                    ResultStatus.PARTIAL
                    if collection.records
                    else collection.incomplete_error.status
                )
                return PublicRecordsResult.failure(
                    query,
                    status,
                    [collection.incomplete_error.to_contract_error()],
                    records=collection.records,
                    next_cursor=next_cursor,
                    warnings=SOURCE_WARNINGS,
                )
            return PublicRecordsResult.success(
                query,
                collection.records,
                next_cursor=next_cursor,
                warnings=SOURCE_WARNINGS,
            )
        if args.selection_offset or args.max_selections is not None:
            raise LASelectionError(
                "selection_bounds_require_all",
                "--selection-offset and --max-selections apply to 'rulings all'",
            )
        selection, page = client.tentative_rulings(args.selection)
        records = [
            normalize_tentative_ruling(ruling, selection=selection)
            for ruling in page.rulings
        ]
        return PublicRecordsResult.success(
            query,
            records,
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        return PublicRecordsResult.success(
            query,
            [_probe_record(client.probe())],
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported Los Angeles court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    client: LosAngelesCourtClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one Los Angeles civil court operation."""

    query = build_query(args)
    own_client = client is None and args.command != "sources"
    source_client = client
    if own_client:
        source_client = LosAngelesCourtClient(
            timeout=args.timeout,
            minimum_interval=args.minimum_interval,
            retry_policy=RetryPolicy(
                max_attempts=args.max_attempts,
                backoff_initial=args.retry_backoff,
            ),
        )
    try:
        result = _execute_command(args, source_client, query)
    except LACourtError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except (TypeError, ValueError) as error:
        source_error = LASourceChangedError(
            "normalization_failed",
            str(error),
        )
        result = PublicRecordsResult.failure(
            query,
            source_error.status,
            [source_error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if own_client and source_client is not None:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help="Minimum seconds between source requests",
    )
    parser.add_argument(
        "--max-attempts",
        type=_positive_int,
        default=3,
        help="Maximum attempts for transient request failures",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=0.5,
        help="Initial retry backoff in seconds",
    )
    add_output_args(parser)


def _add_optional_paging(
    parser: argparse.ArgumentParser,
    *,
    item_name: str,
) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help=f"Maximum {item_name} to return; omit to return every source row",
    )
    parser.add_argument(
        "--offset",
        type=_nonnegative_int,
        default=0,
        help=f"Number of {item_name} to skip",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official Los Angeles Superior Court civil case summaries "
            "and tentative rulings"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    case = subparsers.add_parser(
        "case",
        help="Fetch one civil Case Summary by exact case number",
    )
    case.add_argument("case_number")
    case.add_argument(
        "--courthouse",
        help="Native courthouse code or complete option value",
    )
    _add_optional_paging(case, item_name="combined docket entries")
    _add_runtime_and_output(case)

    selections = subparsers.add_parser(
        "selections",
        help="List every current tentative-ruling selection",
    )
    _add_optional_paging(
        selections,
        item_name="tentative-ruling selections",
    )
    _add_runtime_and_output(selections)

    rulings = subparsers.add_parser(
        "rulings",
        help="Fetch one selection or exhaustively traverse 'all'",
    )
    rulings.add_argument(
        "selection",
        help="Exact current native selection value, or 'all'",
    )
    rulings.add_argument(
        "--max-selections",
        type=_positive_int,
        help="Caller-selected bound for 'all'; omit for exhaustive traversal",
    )
    rulings.add_argument(
        "--selection-offset",
        type=_nonnegative_int,
        default=0,
        help="Number of current selections to skip for 'all'",
    )
    _add_runtime_and_output(rulings)

    sources = subparsers.add_parser(
        "sources",
        help="Describe primary components and complementary official sources",
    )
    _add_runtime_and_output(sources)

    probe = subparsers.add_parser(
        "probe",
        help="Verify the case-summary and tentative-ruling contracts",
    )
    _add_runtime_and_output(probe)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Los Angeles civil court {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Los Angeles civil court {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_kind") == "case":
            print(
                f"  {record.get('raw_case_number') or '?'} | "
                f"{len(record.get('docket_entries') or [])} entries | "
                f"{record.get('caption') or record.get('occurrence_kind') or '?'}"
            )
        elif record.get("record_kind") == "source_selection":
            print(
                f"  {record.get('native_value')} | {record.get('label')}"
            )
        else:
            print(
                f"  {record.get('component_id') or record.get('record_kind')}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
