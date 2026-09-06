#!/usr/bin/env python3
"""Query Maryland's statewide Circuit Court Judgment and Liens index.

The Maryland Judiciary publishes an anonymous index for judgments and liens
recorded by every Maryland circuit court.  Search is a stateful JSF workflow:
the component prefix, action URL, and view-state token are discovered from each
response instead of being treated as stable endpoint parameters.

Examples:
    uv run python tools/query_md_judgment_liens.py person Dalton \
        --first-name David --all-results --output /tmp/md-judgments.json
    uv run python tools/query_md_judgment_liens.py company \
        "Cobblestone Homeowners Assn Inc" --output /tmp/md-company-liens.json
    uv run python tools/query_md_judgment_liens.py detail 03-L-12-005195 \
        --output /tmp/md-judgment-detail.json
    uv run python tools/query_md_judgment_liens.py routes --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup, Tag

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
        sha256_fingerprint,
        utc_now_iso,
    )
    from tools.public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )
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
        sha256_fingerprint,
        utc_now_iso,
    )
    from public_records_http import (
        MinimumIntervalRateLimiter,
        RetryPolicy,
        system_trust_session,
    )


SOURCE_ID = "us-md-judgment-liens"
STATE_CODE = "MD"
STATE_GEOID = "24"

SEARCH_URL = "https://jportal.mdcourts.gov/judgment/judgementSearch.jsf"
RESULTS_URL = "https://jportal.mdcourts.gov/judgment/judgementResults.jsf"
DETAIL_URL = "https://jportal.mdcourts.gov/judgment/details.jsf"
FAQ_URL = "https://www.mdcourts.gov/casesearch2/faq"
CASE_SEARCH_URL = "https://casesearch.mdcourts.gov/casesearch/"
MDEC_PUBLIC_CASES_URL = "https://www.mdcourts.gov/mdec/publiccases"
COURT_RECORDS_URL = "https://www.mdcourts.gov/courts/courtrecords"
JUDICIAL_RECORDS_URL = "https://www.mdcourts.gov/judicialrecords/recordsrequests"
CIRCUIT_COURTS_URL = "https://www.mdcourts.gov/circuit"
LAND_RECORDS_GUIDE_URL = "https://www.mdcourts.gov/legalhelp/landrecords"
MDLANDREC_URL = "https://mdlandrec.net/"
SDAT_PROPERTY_URL = (
    "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
)
SDAT_OPEN_DATA_URL = (
    "https://opendata.maryland.gov/Business-and-Economy/"
    "Maryland-Real-Property-Assessments_Hidden-Property/ed4q-f8tm"
)
ESTATE_SEARCH_URL = "https://registers.maryland.gov/main/search.html"

OUTPUT_SCHEMA_VERSION = "maryland-judgment-liens/1.0"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_LIMIT = 100
DEFAULT_MAX_PAGE_BYTES = 4 * 1024 * 1024
NATIVE_PAGE_SIZE = 25
SOURCE_RESULT_CEILING = 500
CURSOR_RE = re.compile(
    r"^md-judgments:v1:(?P<key>[0-9a-f]{16}):"
    r"total:(?P<total>\d+):offset:(?P<offset>\d+)$"
)
RESULT_BANNER_RE = re.compile(
    r"(?P<total>[\d,]+)\s+items?\s+found,\s+displaying\s+"
    r"(?P<start>[\d,]+)\s+to\s+(?P<end>[\d,]+)\.?",
    re.IGNORECASE,
)
EXPECTED_RESULT_HEADERS = (
    "Case Number",
    "Name For",
    "Name Against",
    "Court",
    "Case Status",
    "Judgment Amount",
    "Book Page",
    "Entry Date",
)
DETAIL_SECTION_TITLES = {
    "Original Judgment": "original_judgment",
    "Judgment Modification": "judgment_modification",
}
PROBE_PERSON = {
    "last_name": "Dalton",
    "first_name": "David",
}
PROBE_CASE_NUMBER = "03-L-12-005195"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)


SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Maryland Judiciary Judgment and Liens Search",
    source_role="statewide_circuit_court_judgment_and_lien_index",
    base_url=SEARCH_URL,
    dataset_id="maryland-judgment-and-liens-index",
    metadata={
        "authority": "Maryland Judiciary",
        "coverage": "all Maryland circuit courts",
        "district_court_records": "not currently included",
        "retention": "records remain indefinitely",
        "native_page_size": NATIVE_PAGE_SIZE,
        "source_result_ceiling": SOURCE_RESULT_CEILING,
        "stable_join_keys": [
            "case_number",
            "party_name",
            "court_or_county",
            "entry_date",
            "judgment_amount",
            "book_page",
        ],
    },
)

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Maryland",
    state_code=STATE_CODE,
)

SOURCE_WARNINGS = (
    "The index covers Maryland circuit-court judgments and liens; the "
    "Judiciary states that District Court judgments are not currently included.",
    "A search returning 500 rows is at the source's published result boundary "
    "and may omit additional matches; narrower name, county, or filing-date "
    "criteria can retrieve a different bounded result set.",
    "Index rows and detail events are leads to the underlying court and land "
    "records; the clerk's file or recorded instrument supplies the authoritative "
    "document when one is needed.",
)


class MarylandJudgmentError(RuntimeError):
    """Source error with explicit public-record result semantics."""

    status = ResultStatus.UNAVAILABLE
    category = "source"
    retryable = False
    code = "maryland_judgment_error"

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        details = dict(self.details)
        if self.url:
            details["url"] = _stable_url(self.url)
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=details,
        )


class MarylandSelectionError(MarylandJudgmentError):
    """Caller selection cannot be represented by the source form."""

    category = "query"
    code = "invalid_selection"


class MarylandTransportError(MarylandJudgmentError):
    """The official source could not be reached."""

    category = "transport"
    retryable = True
    code = "transport_error"


class MarylandRestrictedError(MarylandJudgmentError):
    """The official source declined the current request."""

    status = ResultStatus.RESTRICTED
    category = "access"
    code = "access_restricted"


class MarylandRateLimitedError(MarylandJudgmentError):
    """The official source asked the client to slow down."""

    status = ResultStatus.RATE_LIMITED
    category = "rate_limit"
    retryable = True
    code = "rate_limited"


class MarylandSourceChangedError(MarylandJudgmentError):
    """The official representation no longer matches the verified contract."""

    status = ResultStatus.SOURCE_CHANGED
    category = "schema"
    code = "source_changed"


class MarylandSourceResponseError(MarylandJudgmentError):
    """The site rendered an explicit application error page."""

    category = "source"
    retryable = True
    code = "source_error_response"


@dataclass(frozen=True)
class SearchFormState:
    """Discovered state needed to submit one JSF search form."""

    mode: str
    form_name: str
    action_url: str
    view_state: str
    field_names: Mapping[str, str]
    county_values: Mapping[str, str]
    search_button_value: str
    schema_fingerprint: str


@dataclass(frozen=True)
class SearchCriteria:
    """Source-native person or company search criteria."""

    mode: str
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    company_name: str | None = None
    exact_last_name: bool = False
    county: str | None = None
    filed_from: str | None = None
    filed_to: str | None = None
    filing_date: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"person", "company"}:
            raise MarylandSelectionError(
                "Search mode must be person or company"
            )
        if self.mode == "person":
            if not _clean(self.last_name):
                raise MarylandSelectionError(
                    "Person search requires a last name"
                )
            if _clean(self.company_name):
                raise MarylandSelectionError(
                    "Company name belongs to a company search"
                )
        else:
            if not _clean(self.company_name):
                raise MarylandSelectionError(
                    "Company search requires a company name"
                )
            if any(
                _clean(value)
                for value in (
                    self.last_name,
                    self.first_name,
                    self.middle_name,
                )
            ):
                raise MarylandSelectionError(
                    "Person-name fields belong to a person search"
                )
            if self.exact_last_name:
                raise MarylandSelectionError(
                    "Exact-last-name applies only to person searches"
                )
        if self.filing_date and (self.filed_from or self.filed_to):
            raise MarylandSelectionError(
                "Use an exact filing date or a filing-date range, not both"
            )
        parsed = {
            label: _iso_date(value, label)
            for label, value in (
                ("filed_from", self.filed_from),
                ("filed_to", self.filed_to),
                ("filing_date", self.filing_date),
            )
            if value
        }
        if (
            parsed.get("filed_from")
            and parsed.get("filed_to")
            and parsed["filed_from"] > parsed["filed_to"]
        ):
            raise MarylandSelectionError(
                "Filing-date range starts after it ends"
            )

    def to_parameters(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "last_name": _clean(self.last_name) or None,
            "first_name": _clean(self.first_name) or None,
            "middle_name": _clean(self.middle_name) or None,
            "company_name": _clean(self.company_name) or None,
            "exact_last_name": self.exact_last_name,
            "county": _clean(self.county) or None,
            "filed_from": _iso_date(self.filed_from, "filed_from"),
            "filed_to": _iso_date(self.filed_to, "filed_to"),
            "filing_date": _iso_date(self.filing_date, "filing_date"),
        }

    def form_data(self, form: SearchFormState) -> dict[str, str]:
        """Materialize criteria against fields discovered from the live form."""

        if form.mode != self.mode:
            raise MarylandSourceChangedError(
                "Search form mode did not match the requested query",
                url=form.action_url,
                details={"requested_mode": self.mode, "form_mode": form.mode},
            )
        county = _county_value(self.county, form.county_values)
        data = {
            form.form_name: form.form_name,
            form.field_names["company_indicator"]: (
                "Y" if self.mode == "company" else "N"
            ),
            form.field_names["county"]: county,
            form.field_names["filing_start_date"]: _source_date(
                self.filed_from
            ),
            form.field_names["filing_end_date"]: _source_date(self.filed_to),
            form.field_names["exact_filing_date"]: _source_date(
                self.filing_date
            ),
            form.field_names["search_button"]: form.search_button_value,
            "javax.faces.ViewState": form.view_state,
        }
        if self.mode == "person":
            data.update(
                {
                    form.field_names["last_name"]: _clean(self.last_name),
                    form.field_names["first_name"]: _clean(self.first_name),
                    form.field_names["middle_name"]: _clean(self.middle_name),
                }
            )
            if self.exact_last_name:
                data[form.field_names["exact_last_name"]] = "on"
        else:
            data[form.field_names["company_name"]] = _clean(
                self.company_name
            )
        return data


@dataclass(frozen=True)
class ResultsPage:
    """One parsed native result page plus its continuation state."""

    records: tuple[dict[str, Any], ...]
    total_count: int
    display_start: int
    display_end: int
    form_name: str
    action_url: str
    view_state: str
    scroll_field: str | None
    source_url: str


@dataclass(frozen=True)
class SearchCollection:
    """All rows materialized from one native search."""

    records: tuple[dict[str, Any], ...]
    total_count: int
    pages_fetched: int
    transport_page_size: int
    source_ceiling_reached: bool
    raw_artifact_refs: tuple[str, ...]
    form_schema_fingerprint: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _soup(html: str) -> BeautifulSoup:
    without_declaration = re.sub(
        r"^\s*<\?xml[^>]*\?>",
        "",
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    return BeautifulSoup(without_declaration, "html.parser")


def _stable_url(url: str) -> str:
    parsed = urlsplit(url)
    path = re.sub(
        r";jsessionid=[^/?;]+",
        "",
        parsed.path,
        flags=re.IGNORECASE,
    )
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )


def _iso_date(value: str | None, label: str = "date") -> str | None:
    if not value:
        return None
    candidate = _clean(value)
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(candidate, date_format).date().isoformat()
        except ValueError:
            continue
    raise MarylandSelectionError(
        f"{label} must use YYYY-MM-DD or MM/DD/YYYY",
        details={label: candidate},
    )


def _source_date(value: str | None) -> str:
    normalized = _iso_date(value)
    if normalized is None:
        return ""
    return date.fromisoformat(normalized).strftime("%m/%d/%Y")


def _field_by_suffix(
    form: Tag,
    suffix: str,
    *,
    required: bool = True,
) -> str | None:
    for element in form.find_all(["input", "select", "button"]):
        name = _clean(element.get("name"))
        if name.endswith(f":{suffix}") or name == suffix:
            return name
    if required:
        raise MarylandSourceChangedError(
            f"Search form no longer exposes the {suffix} field"
        )
    return None


def _application_error(soup: BeautifulSoup) -> str | None:
    messages = [
        _clean(node.get_text(" ", strip=True))
        for node in soup.select(".error, .errors, .validationerrorsbox")
    ]
    messages.extend(
        _clean(text)
        for text in soup.stripped_strings
        if "unexpected error" in str(text).casefold()
    )
    return next((message for message in messages if message), None)


def parse_search_form(
    html: str,
    *,
    page_url: str = SEARCH_URL,
) -> SearchFormState:
    """Parse a person- or company-mode search form and its JSF state."""

    soup = _soup(html)
    error = _application_error(soup)
    if error:
        raise MarylandSourceResponseError(error, url=page_url)
    form = soup.find(
        "form",
        id=lambda value: bool(value)
        and str(value).casefold().endswith("searchform"),
    )
    if form is None:
        form = soup.find(
            "form",
            attrs={"name": lambda value: bool(value) and "search" in str(value).casefold()},
        )
    if not isinstance(form, Tag):
        raise MarylandSourceChangedError(
            "Judgment search page does not contain its search form",
            url=page_url,
        )
    form_name = _clean(form.get("name") or form.get("id"))
    view_state_node = form.find(
        "input", attrs={"name": "javax.faces.ViewState"}
    )
    view_state = (
        _clean(view_state_node.get("value"))
        if isinstance(view_state_node, Tag)
        else ""
    )
    if not form_name or not view_state:
        raise MarylandSourceChangedError(
            "Judgment search form lacks its JSF form identity or view state",
            url=page_url,
        )
    company_name = _field_by_suffix(
        form,
        "companyName",
        required=False,
    )
    last_name = _field_by_suffix(form, "lastName", required=False)
    if company_name and not last_name:
        mode = "company"
    elif last_name and not company_name:
        mode = "person"
    else:
        raise MarylandSourceChangedError(
            "Judgment search form mode could not be identified",
            url=page_url,
        )
    fields: dict[str, str] = {
        "company_indicator": str(
            _field_by_suffix(form, "companyIndicatorRadio")
        ),
        "county": str(_field_by_suffix(form, "county")),
        "filing_start_date": str(
            _field_by_suffix(form, "filingStartDate")
        ),
        "filing_end_date": str(_field_by_suffix(form, "filingEndDate")),
        "exact_filing_date": str(
            _field_by_suffix(form, "exactFilingDate")
        ),
        "search_button": str(_field_by_suffix(form, "caseSearchGet")),
    }
    if mode == "person":
        fields.update(
            {
                "last_name": str(last_name),
                "first_name": str(_field_by_suffix(form, "firstName")),
                "middle_name": str(_field_by_suffix(form, "middleName")),
                "exact_last_name": str(
                    _field_by_suffix(form, "wantsExactMatch")
                ),
            }
        )
    else:
        fields["company_name"] = str(company_name)
    county_node = form.find(attrs={"name": fields["county"]})
    county_values: dict[str, str] = {}
    if isinstance(county_node, Tag):
        for option in county_node.find_all("option"):
            value = _clean(option.get("value"))
            if value:
                county_values[value] = _clean(option.get_text(" ", strip=True))
    if not county_values:
        raise MarylandSourceChangedError(
            "Judgment search form contains no county choices",
            url=page_url,
        )
    search_node = form.find(attrs={"name": fields["search_button"]})
    search_value = (
        _clean(search_node.get("value"))
        if isinstance(search_node, Tag)
        else ""
    )
    if not search_value:
        search_value = "Search"
    action_url = urljoin(page_url, str(form.get("action") or ""))
    if not action_url:
        raise MarylandSourceChangedError(
            "Judgment search form lacks a submission action",
            url=page_url,
        )
    fingerprint = sha256_fingerprint(
        {
            "mode": mode,
            "form_name": form_name,
            "field_suffixes": sorted(
                name.rsplit(":", 1)[-1] for name in fields.values()
            ),
            "county_values": county_values,
        }
    )
    return SearchFormState(
        mode=mode,
        form_name=form_name,
        action_url=action_url,
        view_state=view_state,
        field_names=fields,
        county_values=county_values,
        search_button_value=search_value,
        schema_fingerprint=fingerprint,
    )


def _county_value(
    requested: str | None,
    county_values: Mapping[str, str],
) -> str:
    if not _clean(requested):
        return ""
    wanted = _clean(requested).casefold()
    for value, label in county_values.items():
        if wanted in {_clean(value).casefold(), _clean(label).casefold()}:
            return value
    raise MarylandSelectionError(
        "County is not one of the choices currently published by the source",
        details={
            "county": _clean(requested),
            "available_counties": sorted(county_values.values()),
        },
    )


def _money(raw: str) -> tuple[str | None, int | None]:
    value = _clean(raw)
    if not value:
        return None, None
    negative = value.startswith("(") and value.endswith(")")
    candidate = value.strip("()").replace("$", "").replace(",", "").strip()
    try:
        amount = Decimal(candidate)
    except InvalidOperation as exc:
        raise MarylandSourceChangedError(
            "Judgment result contains an unrecognized amount",
            details={"amount_raw": value},
        ) from exc
    if negative:
        amount = -amount
    amount = amount.quantize(Decimal("0.01"))
    return format(amount, ".2f"), int(amount * 100)


def _book_page(raw: str) -> tuple[str | None, str | None]:
    value = _clean(raw)
    if value.count("/") != 1:
        return None, None
    book, page = (_clean(part) for part in value.split("/", 1))
    return book or None, page or None


def _names(cell: Tag) -> list[str]:
    values = [
        _clean(node.get_text(" ", strip=True))
        for node in cell.select("span.Value")
    ]
    values = [value for value in values if value]
    if values:
        return values
    text = _clean(cell.get_text(" ", strip=True))
    return [text] if text else []


def _case_number_from_link(link: Tag, source_url: str) -> tuple[str, str]:
    href = urljoin(source_url, str(link.get("href") or ""))
    parsed = urlsplit(href)
    case_ids = parse_qs(parsed.query).get("selectedCaseId", [])
    case_number = _clean(case_ids[0] if case_ids else link.get_text(" ", strip=True))
    if not case_number:
        raise MarylandSourceChangedError(
            "Judgment result lacks its case identifier",
            url=source_url,
        )
    detail_url = f"{DETAIL_URL}?{urlencode({'selectedCaseId': case_number})}"
    return case_number, detail_url


def _event_ref(material: Mapping[str, Any]) -> str:
    case_number = _clean(material.get("case_number")).upper()
    digest = sha256_fingerprint(material)[:20]
    return f"MDJUDGMENT:INDEX:{case_number}:{digest}"


def _parse_result_row(
    row: Tag,
    *,
    source_url: str,
) -> dict[str, Any]:
    cells = row.find_all("td", recursive=False)
    if len(cells) != len(EXPECTED_RESULT_HEADERS):
        raise MarylandSourceChangedError(
            "Judgment result row no longer has eight top-level cells",
            url=source_url,
            details={"cell_count": len(cells)},
        )
    link = cells[0].find("a", href=True)
    if not isinstance(link, Tag):
        raise MarylandSourceChangedError(
            "Judgment result row lacks its case-detail link",
            url=source_url,
        )
    case_number, detail_url = _case_number_from_link(link, source_url)
    names_for = _names(cells[1])
    names_against = _names(cells[2])
    court = _clean(cells[3].get_text(" ", strip=True))
    status = _clean(cells[4].get_text(" ", strip=True))
    amount_raw = _clean(cells[5].get_text(" ", strip=True))
    amount, amount_minor_units = _money(amount_raw)
    book_page_raw = _clean(cells[6].get_text(" ", strip=True))
    book, page = _book_page(book_page_raw)
    entry_date_raw = _clean(cells[7].get_text(" ", strip=True))
    entry_date = _iso_date(entry_date_raw, "entry_date")
    identity = {
        "case_number": case_number,
        "names_for": names_for,
        "names_against": names_against,
        "court": court,
        "case_status": status,
        "judgment_amount": amount,
        "book_page": book_page_raw,
        "entry_date": entry_date,
    }
    return {
        "canonical_ref": _event_ref(identity),
        "canonical_case_ref": (
            f"MDJUDGMENT:CASE:{case_number.upper()}"
        ),
        "source_id": SOURCE_ID,
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "record_kind": "judgment_lien_index_event",
        "case_number": case_number,
        "names_for": names_for,
        "names_against": names_against,
        "court": court,
        "county": court,
        "case_status": status or None,
        "judgment_amount": amount,
        "judgment_amount_minor_units": amount_minor_units,
        "judgment_amount_currency": "USD" if amount is not None else None,
        "judgment_amount_raw": amount_raw or None,
        "book_page": book_page_raw or None,
        "book": book,
        "page": page,
        "entry_date": entry_date,
        "entry_date_raw": entry_date_raw,
        "detail_url": detail_url,
        "source_result_url": _stable_url(source_url),
        "join_keys": {
            "case_number": case_number,
            "party_names": [*names_for, *names_against],
            "court_or_county": court,
            "entry_date": entry_date,
            "judgment_amount": amount,
            "book_page": book_page_raw or None,
        },
        "raw": {
            "case_number": _clean(cells[0].get_text(" ", strip=True)),
            "names_for": names_for,
            "names_against": names_against,
            "court": court,
            "case_status": status,
            "judgment_amount": amount_raw,
            "book_page": book_page_raw,
            "entry_date": entry_date_raw,
        },
    }


def _result_form_state(
    soup: BeautifulSoup,
    *,
    page_url: str,
) -> tuple[str, str, str, str | None]:
    form = soup.find("form")
    if not isinstance(form, Tag):
        raise MarylandSourceChangedError(
            "Judgment results page lacks its JSF form",
            url=page_url,
        )
    form_name = _clean(form.get("name") or form.get("id"))
    view_state_node = form.find(
        "input", attrs={"name": "javax.faces.ViewState"}
    )
    view_state = (
        _clean(view_state_node.get("value"))
        if isinstance(view_state_node, Tag)
        else ""
    )
    if not form_name or not view_state:
        raise MarylandSourceChangedError(
            "Judgment results page lacks its JSF continuation state",
            url=page_url,
        )
    action_url = urljoin(page_url, str(form.get("action") or ""))
    scroll_field: str | None = None
    for anchor in form.find_all("a", onclick=True):
        match = re.search(
            r"\[\['(?P<field>[^']+)',\s*'idx\d+'\]\]",
            str(anchor.get("onclick")),
        )
        if match:
            scroll_field = match.group("field")
            if "bottomscroll" not in scroll_field:
                break
    return form_name, action_url, view_state, scroll_field


def parse_results_page(
    html: str,
    *,
    page_url: str = RESULTS_URL,
) -> ResultsPage:
    """Parse one native result page without flattening nested party rows."""

    soup = _soup(html)
    error = _application_error(soup)
    if error:
        raise MarylandSourceResponseError(error, url=page_url)
    result_table = soup.select_one("table.results")
    if not isinstance(result_table, Tag):
        raise MarylandSourceChangedError(
            "Judgment results page lacks its result table",
            url=page_url,
        )
    headers = tuple(
        _clean(header.get_text(" ", strip=True))
        for header in result_table.select("thead th")
    )
    if headers != EXPECTED_RESULT_HEADERS:
        raise MarylandSourceChangedError(
            "Judgment result columns changed",
            url=page_url,
            details={
                "expected_headers": list(EXPECTED_RESULT_HEADERS),
                "observed_headers": list(headers),
            },
        )
    banner_match = None
    for text in soup.stripped_strings:
        banner_match = RESULT_BANNER_RE.fullmatch(_clean(text))
        if banner_match:
            break
    if banner_match is None:
        raise MarylandSourceChangedError(
            "Judgment results page lacks its result-count banner",
            url=page_url,
        )
    total = int(banner_match.group("total").replace(",", ""))
    display_start = int(banner_match.group("start").replace(",", ""))
    display_end = int(banner_match.group("end").replace(",", ""))
    # MyFaces emits an outer tbody on the first page, but the live continuation
    # response currently places result rows directly under the table.  Nested
    # party-name tables have their own tbodies, so only direct children are
    # eligible result-row containers.
    rows = result_table.find_all("tr", recursive=False)
    if not rows:
        rows = [
            row
            for body in result_table.find_all("tbody", recursive=False)
            for row in body.find_all("tr", recursive=False)
        ]
    records = tuple(
        _parse_result_row(row, source_url=page_url) for row in rows
    )
    expected_rows = (
        0 if total == 0 else display_end - display_start + 1
    )
    if expected_rows != len(records):
        raise MarylandSourceChangedError(
            "Judgment result count does not match the displayed range",
            url=page_url,
            details={
                "total_count": total,
                "display_start": display_start,
                "display_end": display_end,
                "parsed_rows": len(records),
            },
        )
    if total == 0 and (display_start, display_end) != (0, 0):
        raise MarylandSourceChangedError(
            "Empty judgment results use an unexpected displayed range",
            url=page_url,
        )
    form_name, action_url, view_state, scroll_field = _result_form_state(
        soup,
        page_url=page_url,
    )
    if total > len(records) and not scroll_field:
        raise MarylandSourceChangedError(
            "Multi-page judgment results lack a continuation field",
            url=page_url,
        )
    return ResultsPage(
        records=records,
        total_count=total,
        display_start=display_start,
        display_end=display_end,
        form_name=form_name,
        action_url=action_url,
        view_state=view_state,
        scroll_field=scroll_field,
        source_url=_stable_url(page_url),
    )


def _detail_values(section: Tag) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for prompt in section.select("td.FirstColumnPrompt"):
        label = _clean(prompt.get_text(" ", strip=True)).rstrip(":").strip()
        value_cell = prompt.find_next_sibling("td")
        if not label or not isinstance(value_cell, Tag):
            continue
        spans = [
            _clean(node.get_text(" ", strip=True))
            for node in value_cell.select("span.Value")
        ]
        spans = [value for value in spans if value]
        if not spans:
            text = _clean(value_cell.get_text(" ", strip=True))
            spans = [text] if text else []
        values[label] = spans
    return values


def _first(values: Mapping[str, Sequence[str]], key: str) -> str | None:
    items = values.get(key, ())
    return _clean(items[0]) or None if items else None


def parse_detail_page(
    html: str,
    *,
    page_url: str = DETAIL_URL,
    expected_case_number: str | None = None,
) -> list[dict[str, Any]]:
    """Parse each original/modification block as a distinct judgment event."""

    soup = _soup(html)
    error = _application_error(soup)
    if error:
        raise MarylandSourceResponseError(error, url=page_url)
    sections: list[tuple[str, Tag]] = []
    seen_tables: set[int] = set()
    for node in soup.find_all(["span", "td"]):
        title = _clean(node.get_text(" ", strip=True))
        if title not in DETAIL_SECTION_TITLES:
            continue
        section = node.find_parent("table")
        if not isinstance(section, Tag) or id(section) in seen_tables:
            continue
        seen_tables.add(id(section))
        sections.append((title, section))
    if not sections:
        text = _clean(soup.get_text(" ", strip=True)).casefold()
        if (
            "no electronic record exists" in text
            or "no judgment information" in text
        ):
            return []
        raise MarylandSourceChangedError(
            "Judgment detail page contains no event sections",
            url=page_url,
        )

    parsed: list[tuple[str, dict[str, list[str]], Tag]] = []
    for title, section in sections:
        values = _detail_values(section)
        if not _first(values, "Case Number"):
            raise MarylandSourceChangedError(
                "Judgment detail event lacks its case number",
                url=page_url,
                details={"section": title},
            )
        parsed.append((title, values, section))
    case_numbers = {
        str(_first(values, "Case Number"))
        for _title, values, _section in parsed
    }
    if len(case_numbers) != 1:
        raise MarylandSourceChangedError(
            "Judgment detail page mixes multiple case numbers",
            url=page_url,
            details={"case_numbers": sorted(case_numbers)},
        )
    case_number = case_numbers.pop()
    if (
        expected_case_number
        and case_number.casefold() != _clean(expected_case_number).casefold()
    ):
        raise MarylandSourceChangedError(
            "Judgment detail page returned a different case",
            url=page_url,
            details={
                "requested_case_number": _clean(expected_case_number),
                "returned_case_number": case_number,
            },
        )
    county = next(
        (
            value
            for _title, values, _section in parsed
            if (value := _first(values, "County"))
        ),
        None,
    )
    case_search_url: str | None = None
    for _title, _values, section in parsed:
        link = section.find(
            "a",
            href=lambda value: bool(value)
            and "case-detail-page" in str(value),
        )
        if isinstance(link, Tag):
            case_search_url = _stable_url(
                urljoin(page_url, str(link.get("href")))
            )
            break
    detail_url = f"{DETAIL_URL}?{urlencode({'selectedCaseId': case_number})}"
    records: list[dict[str, Any]] = []
    for sequence, (title, values, _section) in enumerate(parsed, start=1):
        amount_raw = _first(values, "Amount") or ""
        amount, amount_minor_units = _money(amount_raw)
        book_page_raw = _first(values, "Book Page") or ""
        book, page = _book_page(book_page_raw)
        entered_raw = _first(values, "Judgment Entered Date")
        status_date_raw = _first(values, "Status Date")
        entered_date = (
            _iso_date(entered_raw, "judgment_entered_date")
            if entered_raw
            else None
        )
        status_date = (
            _iso_date(status_date_raw, "status_date")
            if status_date_raw
            else None
        )
        event_kind = DETAIL_SECTION_TITLES[title]
        status = _first(values, "Status")
        names_for = list(values.get("For", ()))
        names_against = list(values.get("Against", ()))
        material = {
            "case_number": case_number,
            "event_kind": event_kind,
            "sequence": sequence,
            "judgment_event_type": _first(
                values, "Judgment Event Type"
            ),
            "judgment_entered_date": entered_date,
            "status": status,
            "status_date": status_date,
            "amount": amount,
            "book_page": book_page_raw,
            "names_for": names_for,
            "names_against": names_against,
        }
        digest = sha256_fingerprint(material)[:20]
        records.append(
            {
                "canonical_ref": (
                    f"MDJUDGMENT:DETAIL:{case_number.upper()}:"
                    f"{sequence}:{digest}"
                ),
                "canonical_case_ref": (
                    f"MDJUDGMENT:CASE:{case_number.upper()}"
                ),
                "source_id": SOURCE_ID,
                "schema_version": OUTPUT_SCHEMA_VERSION,
                "record_kind": "judgment_lien_detail_event",
                "event_kind": event_kind,
                "event_sequence": sequence,
                "case_number": case_number,
                "county": county,
                "court": county,
                "judgment_event_type": _first(
                    values, "Judgment Event Type"
                ),
                "judgment_entered_date": entered_date,
                "judgment_entered_date_raw": entered_raw,
                "status": status,
                "status_date": status_date,
                "status_date_raw": status_date_raw,
                "event_date": status_date or entered_date,
                "judgment_amount": amount,
                "judgment_amount_minor_units": amount_minor_units,
                "judgment_amount_currency": (
                    "USD" if amount is not None else None
                ),
                "judgment_amount_raw": amount_raw or None,
                "book_page": book_page_raw or None,
                "book": book,
                "page": page,
                "names_for": names_for,
                "names_against": names_against,
                "status_comments": _first(
                    values, "Judgment Status Comments"
                ),
                "detail_url": detail_url,
                "case_search_url": case_search_url,
                "join_keys": {
                    "case_number": case_number,
                    "party_names": [*names_for, *names_against],
                    "court_or_county": county,
                    "event_date": status_date or entered_date,
                    "judgment_amount": amount,
                    "book_page": book_page_raw or None,
                },
                "raw": {
                    key: list(items) for key, items in values.items()
                },
            }
        )
    return records


class MarylandJudgmentClient:
    """Bounded stateful client for search, native paging, and details."""

    def __init__(
        self,
        *,
        session: requests.Session | Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        retry_policy: RetryPolicy | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self._owns_session = session is None
        self.session = session or system_trust_session()
        if hasattr(self.session, "headers"):
            self.session.headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        self.timeout = timeout
        self.rate_limiter = MinimumIntervalRateLimiter(minimum_interval)
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_session and hasattr(self.session, "close"):
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self.rate_limiter.wait()
            try:
                if hasattr(self.session, "request"):
                    response = self.session.request(
                        method,
                        url,
                        data=dict(data or {}) if data is not None else None,
                        timeout=self.timeout,
                    )
                elif method == "GET":
                    response = self.session.get(url, timeout=self.timeout)
                else:
                    response = self.session.post(
                        url,
                        data=dict(data or {}),
                        timeout=self.timeout,
                    )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            status_code = int(response.status_code)
            if status_code in self.retry_policy.retry_statuses:
                last_error = MarylandTransportError(
                    f"HTTP {status_code} from Maryland judgment source",
                    url=url,
                    details={"status_code": status_code},
                )
                if attempt == self.retry_policy.max_attempts:
                    break
                self.sleeper(self.retry_policy.delay(attempt))
                continue
            if status_code == 429:
                raise MarylandRateLimitedError(
                    "Maryland judgment source returned HTTP 429",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code in {401, 403}:
                raise MarylandRestrictedError(
                    f"HTTP {status_code} from Maryland judgment source",
                    url=url,
                    details={"status_code": status_code},
                )
            if status_code >= 400:
                raise MarylandTransportError(
                    f"HTTP {status_code} from Maryland judgment source",
                    url=url,
                    details={"status_code": status_code},
                )
            content = getattr(response, "content", None)
            if content is None:
                content = str(getattr(response, "text", "")).encode()
            if len(content) > DEFAULT_MAX_PAGE_BYTES:
                raise MarylandSourceChangedError(
                    "Maryland judgment response exceeded the page-size bound",
                    url=url,
                    details={
                        "size_bytes": len(content),
                        "max_bytes": DEFAULT_MAX_PAGE_BYTES,
                    },
                )
            return response
        if isinstance(last_error, MarylandJudgmentError):
            raise last_error
        raise MarylandTransportError(
            "Could not reach the Maryland judgment source",
            url=url,
            details={"reason": str(last_error or "request failed")},
        ) from last_error

    @staticmethod
    def _text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text is not None:
            return str(text)
        return bytes(response.content).decode("utf-8", errors="replace")

    @staticmethod
    def _url(response: Any, fallback: str) -> str:
        return str(getattr(response, "url", None) or fallback)

    def search_form(self, *, company: bool = False) -> SearchFormState:
        response = self._request("GET", SEARCH_URL)
        response_url = self._url(response, SEARCH_URL)
        form = parse_search_form(
            self._text(response),
            page_url=response_url,
        )
        requested_mode = "company" if company else "person"
        if form.mode == requested_mode:
            return form
        toggle = {
            form.form_name: form.form_name,
            form.field_names["company_indicator"]: (
                "Y" if company else "N"
            ),
            "javax.faces.ViewState": form.view_state,
        }
        response = self._request("POST", form.action_url, data=toggle)
        toggled_form = parse_search_form(
            self._text(response),
            page_url=self._url(response, form.action_url),
        )
        if toggled_form.mode != requested_mode:
            raise MarylandSourceChangedError(
                "Search-mode toggle did not render the requested form",
                url=toggled_form.action_url,
                details={
                    "requested_mode": requested_mode,
                    "rendered_mode": toggled_form.mode,
                },
            )
        return toggled_form

    def search(self, criteria: SearchCriteria) -> SearchCollection:
        form = self.search_form(company=criteria.mode == "company")
        response = self._request(
            "POST",
            form.action_url,
            data=criteria.form_data(form),
        )
        page_url = self._url(response, RESULTS_URL)
        first = parse_results_page(
            self._text(response),
            page_url=page_url,
        )
        records = list(first.records)
        artifacts = [_stable_url(SEARCH_URL), first.source_url]
        if first.total_count == 0:
            return SearchCollection(
                records=(),
                total_count=0,
                pages_fetched=1,
                transport_page_size=NATIVE_PAGE_SIZE,
                source_ceiling_reached=False,
                raw_artifact_refs=tuple(dict.fromkeys(artifacts)),
                form_schema_fingerprint=form.schema_fingerprint,
            )
        transport_size = len(first.records)
        if first.total_count > transport_size:
            if transport_size != NATIVE_PAGE_SIZE:
                raise MarylandSourceChangedError(
                    "First judgment result page uses an unexpected page size",
                    url=first.source_url,
                    details={
                        "expected_page_size": NATIVE_PAGE_SIZE,
                        "observed_page_size": transport_size,
                    },
                )
        page_count = math.ceil(first.total_count / transport_size)
        current = first
        for page_number in range(2, page_count + 1):
            if not current.scroll_field:
                raise MarylandSourceChangedError(
                    "Judgment pagination state ended before the final page",
                    url=current.source_url,
                    details={"next_page": page_number},
                )
            payload = {
                current.form_name: current.form_name,
                current.scroll_field: f"idx{page_number}",
                "javax.faces.ViewState": current.view_state,
            }
            response = self._request(
                "POST",
                current.action_url,
                data=payload,
            )
            current = parse_results_page(
                self._text(response),
                page_url=self._url(response, current.action_url),
            )
            expected_start = ((page_number - 1) * transport_size) + 1
            if (
                current.total_count != first.total_count
                or current.display_start != expected_start
            ):
                raise MarylandSourceChangedError(
                    "Judgment pagination did not advance to the expected range",
                    url=current.source_url,
                    details={
                        "page_number": page_number,
                        "expected_start": expected_start,
                        "observed_start": current.display_start,
                        "initial_total": first.total_count,
                        "observed_total": current.total_count,
                    },
                )
            records.extend(current.records)
            artifacts.append(current.source_url)
        if len(records) != first.total_count:
            raise MarylandSourceChangedError(
                "Judgment pagination completed with a row-count mismatch",
                url=current.source_url,
                details={
                    "source_total": first.total_count,
                    "materialized_rows": len(records),
                },
            )
        return SearchCollection(
            records=tuple(records),
            total_count=first.total_count,
            pages_fetched=page_count,
            transport_page_size=transport_size,
            source_ceiling_reached=(
                first.total_count >= SOURCE_RESULT_CEILING
            ),
            raw_artifact_refs=tuple(dict.fromkeys(artifacts)),
            form_schema_fingerprint=form.schema_fingerprint,
        )

    def detail(self, case_number: str) -> tuple[list[dict[str, Any]], str]:
        wanted = _clean(case_number)
        if not wanted:
            raise MarylandSelectionError("Case number must not be empty")
        url = f"{DETAIL_URL}?{urlencode({'selectedCaseId': wanted})}"
        response = self._request("GET", url)
        response_url = self._url(response, url)
        records = parse_detail_page(
            self._text(response),
            page_url=response_url,
            expected_case_number=wanted,
        )
        return records, _stable_url(response_url)


def related_source_routes() -> list[dict[str, Any]]:
    """Map adjacent records by role and practical join keys."""

    return [
        {
            "source_id": "us-md-case-search",
            "name": "Maryland Judiciary Case Search",
            "url": CASE_SEARCH_URL,
            "record_role": "case_parties_status_events_and_case_detail",
            "adds": (
                "case-level parties, status, event history, charges, and "
                "disposition beyond this judgment index"
            ),
            "access_observation": (
                "interactive agreement and native CAPTCHA on the current route"
            ),
            "join_keys": ["case_number", "party_name", "court_or_county"],
        },
        {
            "source_id": "us-md-mdec-public-cases",
            "name": "Maryland MDEC Public Cases Created by Courts",
            "url": MDEC_PUBLIC_CASES_URL,
            "record_role": "recent_public_case_filing_discovery",
            "adds": (
                "rolling public case creations, captions, case types, party "
                "names, and published party addresses"
            ),
            "join_keys": [
                "case_number",
                "party_name",
                "court_or_county",
                "filing_date",
            ],
        },
        {
            "source_id": "us-md-circuit-clerk-records",
            "name": "Maryland Circuit Court Clerk Records",
            "url": COURT_RECORDS_URL,
            "directory_url": CIRCUIT_COURTS_URL,
            "record_role": "underlying_case_file_and_certified_copies",
            "adds": (
                "filed judgments, releases, lien instruments, certifications, "
                "and records not represented in an online index"
            ),
            "join_keys": ["case_number", "court_or_county", "party_name"],
        },
        {
            "source_id": "us-md-land-records",
            "name": "Maryland Land Records / MDLandRec",
            "url": MDLANDREC_URL,
            "information_url": LAND_RECORDS_GUIDE_URL,
            "record_role": "recorded_real_property_instruments_and_some_liens",
            "adds": (
                "deeds, mortgages, releases, and recorded lien instruments "
                "affecting a parcel"
            ),
            "access_observation": "free Maryland State Archives account",
            "join_keys": [
                "party_name",
                "court_or_county",
                "book_page",
                "liber_folio",
                "property_address",
            ],
        },
        {
            "source_id": "us-md-sdat-real-property",
            "name": "Maryland SDAT Real Property",
            "url": SDAT_PROPERTY_URL,
            "bulk_dataset_url": SDAT_OPEN_DATA_URL,
            "record_role": "parcel_assessment_situs_and_deed_reference",
            "adds": (
                "parcel/account identity, situs, assessment, owner display, "
                "and deed liber/folio for property pivots"
            ),
            "join_keys": [
                "property_address",
                "court_or_county",
                "property_account_id",
                "liber_folio",
            ],
        },
        {
            "source_id": "us-md-local-finance-tax-liens",
            "name": "Maryland County and Baltimore City Finance Offices",
            "url": LAND_RECORDS_GUIDE_URL,
            "record_role": "property_tax_and_municipal_lien_status",
            "adds": (
                "unpaid property tax and municipal liens that the Judiciary's "
                "general land-records guidance routes to local finance offices"
            ),
            "join_keys": [
                "property_account_id",
                "property_address",
                "court_or_county",
                "owner_name",
            ],
        },
        {
            "source_id": "us-md-estate-search",
            "name": "Maryland Register of Wills Estate Search",
            "url": ESTATE_SEARCH_URL,
            "record_role": "estate_parties_status_and_docket",
            "adds": (
                "estate number, decedent, personal representative, attorney, "
                "status, and docket history for deceased judgment parties"
            ),
            "join_keys": [
                "party_name",
                "court_or_county",
                "estate_number",
            ],
        },
        {
            "source_id": "us-md-aoc-court-data",
            "name": "Maryland Judicial Records Requests",
            "url": JUDICIAL_RECORDS_URL,
            "record_role": "administrative_data_and_record_request_route",
            "adds": (
                "AOC or custodian request path when indexed web fields do not "
                "contain the needed record representation"
            ),
            "join_keys": [
                "case_number",
                "court_or_county",
                "record_type",
            ],
        },
    ]


def source_records() -> list[dict[str, Any]]:
    """Describe the implemented source and distinct adjacent representations."""

    records: list[dict[str, Any]] = [
        {
            "source_id": SOURCE_ID,
            "record_kind": "source_manifest",
            "name": SOURCE_METADATA.name,
            "url": SEARCH_URL,
            "information_url": FAQ_URL,
            "implemented_operations": [
                "person",
                "company",
                "detail",
                "probe",
                "routes",
            ],
            "coverage": {
                "courts": "all Maryland circuit courts",
                "records": "judgment and lien index entries",
                "retention": "indefinite",
                "district_court": "not currently included",
                "fields": list(EXPECTED_RESULT_HEADERS),
            },
            "bounds": {
                "native_page_size": NATIVE_PAGE_SIZE,
                "source_result_ceiling": SOURCE_RESULT_CEILING,
                "caller_limit": (
                    "local result-envelope pagination; --all-results returns "
                    "every row exposed by the native query"
                ),
            },
            "identity": {
                "case": ["case_number"],
                "index_event": [
                    "case_number",
                    "entry_date",
                    "case_status",
                    "judgment_amount",
                    "book_page",
                    "names_for",
                    "names_against",
                ],
                "detail_event": [
                    "case_number",
                    "event_kind",
                    "event_sequence",
                    "status_date",
                    "judgment_entered_date",
                ],
            },
        }
    ]
    records.extend(
        {"record_kind": "complementary_source", **route}
        for route in related_source_routes()
    )
    return records


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    cursor: str | None = None,
    requested_limit: int | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            cursor=cursor,
            requested_limit=requested_limit,
            metadata=metadata or {},
        ),
    )


def _cursor_key(criteria: SearchCriteria) -> str:
    return hashlib.sha256(
        canonical_json(criteria.to_parameters()).encode()
    ).hexdigest()[:16]


def _page_records(
    records: Sequence[Mapping[str, Any]],
    *,
    criteria: SearchCriteria,
    total_count: int,
    cursor: str | None,
    limit: int | None,
) -> tuple[list[Mapping[str, Any]], str | None]:
    offset = 0
    key = _cursor_key(criteria)
    if cursor:
        match = CURSOR_RE.fullmatch(cursor)
        if match is None:
            raise MarylandSelectionError("Cursor format is invalid")
        if match.group("key") != key:
            raise MarylandSelectionError(
                "Cursor belongs to a different Maryland judgment query"
            )
        cursor_total = int(match.group("total"))
        if cursor_total != total_count:
            raise MarylandSelectionError(
                "Judgment result count changed since this cursor was issued",
                details={
                    "cursor_total": cursor_total,
                    "current_total": total_count,
                },
            )
        offset = int(match.group("offset"))
        if offset >= len(records):
            raise MarylandSelectionError(
                "Cursor starts beyond the current result set",
                details={"offset": offset, "result_count": len(records)},
            )
    if limit is None:
        return list(records[offset:]), None
    page = list(records[offset : offset + limit])
    next_offset = offset + len(page)
    next_cursor = (
        f"md-judgments:v1:{key}:total:{total_count}:offset:{next_offset}"
        if next_offset < len(records)
        else None
    )
    return page, next_cursor


def _failure(
    query: PublicRecordsQuery,
    error: MarylandJudgmentError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        error.status,
        [error.to_contract_error()],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    client: MarylandJudgmentClient | Any | None = None,
    log_results: bool = True,
    retrieved_at: str | None = None,
) -> PublicRecordsResult:
    """Execute one source operation and return the shared result envelope."""

    own_client = client is None
    source_client = client or MarylandJudgmentClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        retry_policy=RetryPolicy(
            max_attempts=args.max_attempts,
            backoff_initial=args.retry_backoff,
        ),
    )
    retrieved_at = retrieved_at or utc_now_iso()
    query = _query(args.command, {})
    try:
        if args.command == "routes":
            query = _query("routes", {})
            result = PublicRecordsResult.success(
                query,
                source_records(),
                retrieved_at=retrieved_at,
                raw_artifact_refs=[SEARCH_URL, FAQ_URL],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command in {"person", "company"}:
            criteria = SearchCriteria(
                mode=args.command,
                last_name=(
                    args.last_name if args.command == "person" else None
                ),
                first_name=getattr(args, "first_name", None),
                middle_name=getattr(args, "middle_name", None),
                company_name=(
                    args.company_name if args.command == "company" else None
                ),
                exact_last_name=getattr(args, "exact_last_name", False),
                county=args.county,
                filed_from=args.filed_from,
                filed_to=args.filed_to,
                filing_date=args.filing_date,
            )
            limit = None if args.all_results else args.limit
            collection = source_client.search(criteria)
            page, next_cursor = _page_records(
                collection.records,
                criteria=criteria,
                total_count=collection.total_count,
                cursor=args.cursor,
                limit=limit,
            )
            query = _query(
                args.command,
                criteria.to_parameters(),
                cursor=args.cursor,
                requested_limit=limit,
                metadata={
                    "coverage": {
                        "source_total": collection.total_count,
                        "pages_fetched": collection.pages_fetched,
                        "transport_page_size": (
                            collection.transport_page_size
                        ),
                        "source_result_ceiling_reached": (
                            collection.source_ceiling_reached
                        ),
                    },
                    "form_schema_fingerprint": (
                        collection.form_schema_fingerprint
                    ),
                },
            )
            if collection.source_ceiling_reached:
                result = PublicRecordsResult.failure(
                    query,
                    ResultStatus.PARTIAL,
                    [
                        PublicRecordsError(
                            code="source_result_ceiling_reached",
                            message=(
                                "The query reached the source's 500-row result "
                                "boundary; returned rows are usable but may not "
                                "represent every match."
                            ),
                            category="coverage",
                            retryable=False,
                            details={
                                "source_total": collection.total_count,
                                "source_result_ceiling": (
                                    SOURCE_RESULT_CEILING
                                ),
                                "refinement_fields": [
                                    "name",
                                    "county",
                                    "filing_date",
                                ],
                            },
                        )
                    ],
                    records=page,
                    next_cursor=next_cursor,
                    retrieved_at=retrieved_at,
                    raw_artifact_refs=collection.raw_artifact_refs,
                    warnings=SOURCE_WARNINGS,
                )
            else:
                result = PublicRecordsResult.success(
                    query,
                    page,
                    next_cursor=next_cursor,
                    retrieved_at=retrieved_at,
                    raw_artifact_refs=collection.raw_artifact_refs,
                    warnings=SOURCE_WARNINGS,
                )
        elif args.command == "detail":
            wanted = _clean(args.case_number)
            query = _query("detail", {"case_number": wanted})
            records, source_url = source_client.detail(wanted)
            result = PublicRecordsResult.success(
                query,
                records,
                retrieved_at=retrieved_at,
                raw_artifact_refs=[source_url],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            person_form = source_client.search_form(company=False)
            company_form = source_client.search_form(company=True)
            criteria = SearchCriteria(mode="person", **PROBE_PERSON)
            collection = source_client.search(criteria)
            detail_records, detail_url = source_client.detail(
                PROBE_CASE_NUMBER
            )
            query = _query(
                "probe",
                {
                    "person_sentinel": criteria.to_parameters(),
                    "detail_sentinel": PROBE_CASE_NUMBER,
                },
            )
            probe = {
                "canonical_ref": (
                    "MDJUDGMENT:PROBE:"
                    + sha256_fingerprint(
                        {
                            "person_form": (
                                person_form.schema_fingerprint
                            ),
                            "company_form": (
                                company_form.schema_fingerprint
                            ),
                            "search_total": collection.total_count,
                            "detail_events": len(detail_records),
                        }
                    )
                ),
                "source_id": SOURCE_ID,
                "record_kind": "source_probe",
                "status": "ok",
                "operation_states": {
                    "person_form": "available",
                    "company_form_toggle": "available",
                    "stateful_search": "available",
                    "native_pagination": (
                        "available"
                        if collection.pages_fetched > 1
                        else "not_needed_for_sentinel"
                    ),
                    "case_detail": "available",
                },
                "person_form_schema_fingerprint": (
                    person_form.schema_fingerprint
                ),
                "company_form_schema_fingerprint": (
                    company_form.schema_fingerprint
                ),
                "search_sentinel_total": collection.total_count,
                "search_sentinel_pages": collection.pages_fetched,
                "detail_sentinel_event_count": len(detail_records),
                "source_result_ceiling": SOURCE_RESULT_CEILING,
            }
            result = PublicRecordsResult.success(
                query,
                [probe],
                retrieved_at=retrieved_at,
                raw_artifact_refs=[
                    *collection.raw_artifact_refs,
                    detail_url,
                ],
                warnings=SOURCE_WARNINGS,
            )
        else:
            raise MarylandSelectionError(
                f"Unsupported operation: {args.command}"
            )
    except MarylandJudgmentError as error:
        result = _failure(query, error)
    finally:
        if own_client:
            source_client.close()
    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            SOURCE_ID,
            result_count,
        )
    return result


def _add_runtime_and_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=0.5)
    add_output_args(parser)


def _add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--county", help="Source-published county label or value")
    parser.add_argument("--filed-from", help="Filing-date start (YYYY-MM-DD)")
    parser.add_argument("--filed-to", help="Filing-date end (YYYY-MM-DD)")
    parser.add_argument("--filing-date", help="Exact filing date (YYYY-MM-DD)")
    parser.add_argument("--cursor")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument(
        "--all-results",
        action="store_true",
        help="Return every row exposed by the native query",
    )
    _add_runtime_and_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Maryland Judiciary judgments and liens"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    routes = subparsers.add_parser(
        "routes",
        help="Show source coverage and complementary record routes",
    )
    _add_runtime_and_output(routes)

    person = subparsers.add_parser(
        "person",
        help="Search the judgment index by person name",
    )
    person.add_argument("last_name")
    person.add_argument("--first-name")
    person.add_argument("--middle-name")
    person.add_argument(
        "--exact-last-name",
        action="store_true",
        help="Select the source's exact-last-name checkbox",
    )
    _add_search_args(person)

    company = subparsers.add_parser(
        "company",
        help="Search the judgment index in company mode",
    )
    company.add_argument("company_name")
    _add_search_args(company)

    detail = subparsers.add_parser(
        "detail",
        help="Fetch original and modification events for a case",
    )
    detail.add_argument("case_number")
    _add_runtime_and_output(detail)

    probe = subparsers.add_parser(
        "probe",
        help="Verify both form modes, search, paging state, and case detail",
    )
    _add_runtime_and_output(probe)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.minimum_interval < 0:
        raise SystemExit("--minimum-interval must not be negative")
    if args.max_attempts <= 0:
        raise SystemExit("--max-attempts must be positive")
    if args.retry_backoff < 0:
        raise SystemExit("--retry-backoff must not be negative")
    if hasattr(args, "limit") and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    for field in ("filed_from", "filed_to", "filing_date"):
        value = getattr(args, field, None)
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                option = field.replace("_", "-")
                raise SystemExit(
                    f"--{option} must use YYYY-MM-DD"
                ) from exc
    if getattr(args, "filing_date", None) and (
        getattr(args, "filed_from", None)
        or getattr(args, "filed_to", None)
    ):
        raise SystemExit(
            "Use --filing-date or --filed-from/--filed-to, not both"
        )
    if (
        getattr(args, "filed_from", None)
        and getattr(args, "filed_to", None)
        and args.filed_from > args.filed_to
    ):
        raise SystemExit("--filed-from must not be after --filed-to")


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Maryland judgment/liens {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Maryland judgment/liens {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('case_number') or record.get('source_id') or '?'}"
            f" | {record.get('case_status') or record.get('event_kind') or '?'}"
            f" | {record.get('court') or record.get('name') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> int:
    args = build_parser().parse_args()
    _validate_args(args)
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
