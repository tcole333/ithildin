#!/usr/bin/env python3
"""Query Miami-Dade Clerk Official Records detail, image, and commercial APIs.

The Clerk exposes two independently cataloged acquisition surfaces:

* Public, sessionless hydration/detail/image routes for already-issued search
  tokens or known record identifiers.
* A credentialed commercial API for deterministic CFN, book/page, and folio
  lookups.

The public application issues search tokens through its interactive search
surface; this adapter can hydrate those tokens once issued.

Examples:
    uv run python tools/query_miami_dade_recorder.py document-types
    uv run python tools/query_miami_dade_recorder.py hydrate-qs '<issued-token>'
    uv run python tools/query_miami_dade_recorder.py parties 50126241
    uv run python tools/query_miami_dade_recorder.py financial 50126241 \
        --doc-type 'DEED - DEE' --recording-date 2026-01-27
    uv run python tools/query_miami_dade_recorder.py image 35134 800 \
        --book-type O --document-output /tmp/Document_35134_800.pdf
    uv run python tools/query_miami_dade_recorder.py cfn 2026 55844
    uv run python tools/query_miami_dade_recorder.py book-page 35134 800
    uv run python tools/query_miami_dade_recorder.py folio 01-4138-067-0370
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlencode

import requests

try:
    from tools.env_loader import load_env_file
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
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
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from env_loader import load_env_file
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
        CatalogError,
        acquisition_result_status,
    )
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
        HTTPStatusError,
        PublicRecordsHTTPError,
        RateLimitedHTTPError,
        RestrictedHTTPError,
        RetryPolicy,
        SourceChangedHTTPError,
        SourceResponseError,
        SourceSchemaError,
        TermsBlockedHTTPError,
        TransportError,
        _BaseJSONClient,
        failure_result,
        inferred_schema,
        schema_fingerprint,
    )
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


PUBLIC_SOURCE_ID = "us-fl-miami-dade-official-records-public"
CANONICAL_SOURCE_ID = "us-fl-miami-dade-official-records"
COUNTY_GEOID = "12086"
COMMERCIAL_AUTH_ENV = "MIAMI_DADE_CLERK_AUTH_KEY"

PUBLIC_APP_URL = (
    "https://onlineservices.miamidadeclerk.gov/officialrecords/"
)
PUBLIC_RESULTS_API = (
    f"{PUBLIC_APP_URL}api/SearchResults/getStandardRecords"
)
PUBLIC_PARTIES_API = f"{PUBLIC_APP_URL}api/Home/getparties"
PUBLIC_FINANCIAL_API = f"{PUBLIC_APP_URL}api/Home/financial-details"
PUBLIC_IMAGE_API = (
    f"{PUBLIC_APP_URL}api/DocumentImage/getdocumentimage"
)
PUBLIC_DOCUMENT_TYPES_API = f"{PUBLIC_APP_URL}api/home/documentTypes"
COMMERCIAL_API_URL = (
    "https://www2.miamidadeclerk.gov/Developers/api/OfficialRecords"
)
COMMERCIAL_HELP_URL = (
    "https://www2.miamidadeclerk.gov/Developers/Help/Api/"
    "GET-api-OfficialRecords_parameter1_parameter2_authKey"
)

ROUTE_ISSUED_RESULT_HYDRATION = "issued_result_hydration"
ROUTE_RECORD_DETAIL = "record_detail"
ROUTE_DOCUMENT_IMAGE = "document_image"
ROUTE_DOCUMENT_TYPES = "document_types"
ROUTE_COMMERCIAL_API = "official_records_api"

RECORD_KIND_INSTRUMENT = "recorded_instrument"
RECORD_KIND_DOCUMENT_TYPE = "document_type_reference"
RECORD_KIND_FINANCIAL_DETAIL = "financial_detail"
RECORD_KIND_DOCUMENT_ARTIFACT = "document_artifact"

# Codes from the Clerk's document-type vocabulary that record a transfer of
# real-property title. Agreement-for-deed (AFD) is not included because it is
# an executory contract rather than the instrument completing the conveyance.
CONVEYANCE_INSTRUMENT_CODES = frozenset(
    {
        "CTI",  # Certificate of title
        "DAM",  # Deed with assumption of mortgage
        "DEE",  # Deed
        "DM",  # Deed with mortgage
        "ODE",  # Old deed
        "PRO",  # Probate order of distribution
        "PT",  # Any property transfer
        "PTMOR",  # Any property transfer and mortgage
        "QCD",  # Quit claim deed
    }
)

PUBLIC_COMMAND_ROUTES = {
    "document-types": ROUTE_DOCUMENT_TYPES,
    "hydrate-qs": ROUTE_ISSUED_RESULT_HYDRATION,
    "parties": ROUTE_RECORD_DETAIL,
    "financial": ROUTE_RECORD_DETAIL,
    "image": ROUTE_DOCUMENT_IMAGE,
}
COMMERCIAL_COMMANDS = frozenset({"cfn", "book-page", "folio"})

PUBLIC_SOURCE_METADATA = SourceMetadata(
    source_id=PUBLIC_SOURCE_ID,
    name="Miami-Dade Clerk Official Records Public Detail and Images",
    source_role="recorder_instrument_detail",
    base_url=PUBLIC_APP_URL,
    dataset_id="officialrecords-public-detail",
    metadata={
        "authority": "Miami-Dade Clerk of the Court and Comptroller",
        "coverage": "Miami-Dade County, Florida",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
        "record_identity_source_id": CANONICAL_SOURCE_ID,
    },
)

CANONICAL_SOURCE_METADATA = SourceMetadata(
    source_id=CANONICAL_SOURCE_ID,
    name="Miami-Dade Clerk Official Records",
    source_role="recorder_instrument_index",
    base_url=COMMERCIAL_API_URL,
    dataset_id="OfficialRecords",
    metadata={
        "authority": "Miami-Dade Clerk of the Court and Comptroller",
        "coverage": "Miami-Dade County, Florida",
        "access_class": "D",
        "authentication": "registered_prepaid_account",
        "credential_env": COMMERCIAL_AUTH_ENV,
        "record_identity_source_id": CANONICAL_SOURCE_ID,
    },
)

PUBLIC_WARNINGS = (
    "Clerk index rows may repeat for each property group and indexed party; "
    "the normalized result preserves that hierarchy.",
    "Issued search tokens are source locators, not canonical document identifiers.",
)


@dataclass(frozen=True)
class DocumentDownload:
    """Validated PDF response returned by the public document-image route."""

    content: bytes
    media_type: str
    filename: str
    etag: str | None = None


def _header(headers: Mapping[str, Any], name: str) -> str | None:
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value)
    return None


def _response_text(response: Any) -> str:
    value = getattr(response, "text", "")
    return value if isinstance(value, str) else str(value)


class MiamiDadeRecorderClient(_BaseJSONClient):
    """Transport-injectable client for verified Clerk JSON and PDF routes."""

    def _request_response(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
            **dict(headers or {}),
        }
        transient_errors = (
            requests.RequestException,
            TimeoutError,
            ConnectionError,
        )
        last_error: BaseException | None = None

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._rate_limiter.wait()
            self.request_count += 1
            try:
                response = self.transport.request(
                    method,
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout,
                )
            except transient_errors as error:
                last_error = error
                if attempt >= self.retry_policy.max_attempts:
                    raise TransportError(
                        "Miami-Dade Clerk request failed after "
                        f"{attempt} attempts: {error}",
                        url=url,
                        details={"attempts": attempt},
                    ) from error
                self._sleeper(self.retry_policy.delay(attempt))
                continue

            status_code = int(
                getattr(response, "status_code", getattr(response, "status", 0))
            )
            if status_code in self.retry_policy.retry_statuses:
                retry_after_value = _header(
                    getattr(response, "headers", {}),
                    "Retry-After",
                )
                retry_after: float | None = None
                if retry_after_value is not None:
                    try:
                        retry_after = max(0.0, float(retry_after_value))
                    except ValueError:
                        retry_after = None
                if attempt < self.retry_policy.max_attempts:
                    self._sleeper(
                        self.retry_policy.delay(attempt, retry_after)
                    )
                    continue
                if status_code == 429:
                    raise RateLimitedHTTPError(
                        status_code,
                        url=url,
                        response_text=_response_text(response),
                    )
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {401, 403}:
                raise RestrictedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code == 451:
                raise TermsBlockedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code in {404, 410}:
                raise SourceChangedHTTPError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            if status_code < 200 or status_code >= 300:
                raise HTTPStatusError(
                    status_code,
                    url=url,
                    response_text=_response_text(response),
                )
            return response

        raise TransportError(
            f"Miami-Dade Clerk request failed: {last_error}",
            url=url,
            details={"attempts": self.retry_policy.max_attempts},
        )

    def _route_json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        response = self._request_response(
            method,
            url,
            params=params,
            headers=headers,
        )
        try:
            return response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise SourceSchemaError(
                "Miami-Dade Clerk returned invalid JSON",
                url=url,
                details={"response_text": _response_text(response)[:500]},
            ) from error

    def document_types(self) -> Sequence[str]:
        payload = self._route_json(
            "GET",
            PUBLIC_DOCUMENT_TYPES_API,
            params={},
        )
        if not isinstance(payload, list) or any(
            not isinstance(value, str) for value in payload
        ):
            raise SourceSchemaError(
                "Miami-Dade document-types response must be an array of strings",
                url=PUBLIC_DOCUMENT_TYPES_API,
            )
        if not payload:
            raise SourceSchemaError(
                "Miami-Dade document-types response was empty",
                url=PUBLIC_DOCUMENT_TYPES_API,
            )
        return tuple(payload)

    def hydrate_qs(self, issued_token: str) -> Mapping[str, Any]:
        payload = self._route_json(
            "GET",
            PUBLIC_RESULTS_API,
            params={"qs": issued_token},
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Miami-Dade search-result hydration must return an object",
                url=PUBLIC_RESULTS_API,
            )
        return payload

    def parties(self, cfn_master_id: int) -> Sequence[Mapping[str, Any]]:
        payload = self._route_json(
            "POST",
            PUBLIC_PARTIES_API,
            params={"cfnMasterID": cfn_master_id},
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": "0",
            },
        )
        if not isinstance(payload, list) or any(
            not isinstance(row, Mapping) for row in payload
        ):
            raise SourceSchemaError(
                "Miami-Dade parties response must be an array of objects",
                url=PUBLIC_PARTIES_API,
            )
        return tuple(payload)

    def financial(
        self,
        cfn_master_id: int,
        document_type: str,
        recording_date: str,
    ) -> Mapping[str, Any]:
        payload = self._route_json(
            "GET",
            PUBLIC_FINANCIAL_API,
            params={
                "cfnMasterID": cfn_master_id,
                "docType": document_type,
                "recDate": recording_date,
            },
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Miami-Dade financial response must be an object",
                url=PUBLIC_FINANCIAL_API,
            )
        return payload

    def document_image(
        self,
        *,
        book: str,
        page: str,
        book_type: str,
        cfn_master_id: int | None = None,
    ) -> DocumentDownload:
        params: dict[str, Any] = {
            "sBook": book,
            "sPage": page,
            "sBookType": book_type,
            "redact": "false",
        }
        if cfn_master_id is not None:
            params["cfnMasterId"] = cfn_master_id
        response = self._request_response(
            "GET",
            PUBLIC_IMAGE_API,
            params=params,
            headers={"Accept": "application/pdf"},
        )
        content = getattr(response, "content", None)
        if not isinstance(content, bytes):
            raise SourceSchemaError(
                "Miami-Dade document-image response did not expose binary content",
                url=PUBLIC_IMAGE_API,
            )
        media_type = (
            _header(getattr(response, "headers", {}), "Content-Type") or ""
        ).split(";", 1)[0].strip().lower()
        if media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise SourceSchemaError(
                "Miami-Dade document-image response was not a PDF",
                url=PUBLIC_IMAGE_API,
                details={
                    "content_type": media_type,
                    "signature_hex": content[:8].hex(),
                },
            )
        disposition = _header(
            getattr(response, "headers", {}),
            "Content-Disposition",
        )
        filename = f"Document_{book}_{page}.pdf"
        if disposition:
            match = re.search(r'filename="?([^";]+)', disposition)
            if match:
                filename = match.group(1).strip()
        return DocumentDownload(
            content=content,
            media_type=media_type,
            filename=filename,
            etag=_header(getattr(response, "headers", {}), "ETag"),
        )

    def commercial_lookup(
        self,
        *,
        parameter1: str,
        parameter2: str,
        auth_key: str,
    ) -> Mapping[str, Any]:
        payload = self._route_json(
            "GET",
            COMMERCIAL_API_URL,
            params={
                "parameter1": parameter1,
                "parameter2": parameter2,
                "authKey": auth_key,
            },
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Miami-Dade commercial API response must be an object",
                url=COMMERCIAL_API_URL,
            )
        return payload


def _field(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\x00", "").split()).strip()
    return normalized or None


def _integer(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"Miami-Dade record lacks {field_name}")
        return None
    if isinstance(value, bool):
        raise ValueError(f"Miami-Dade {field_name} is not an integer")
    try:
        integer = int(str(value).strip())
    except ValueError as error:
        raise ValueError(
            f"Miami-Dade {field_name} is not an integer"
        ) from error
    return integer


def _iso_date(value: Any, field_name: str) -> str | None:
    """Normalize Clerk date/date-time strings to an ISO calendar date."""
    raw = _text(value)
    if raw is None:
        return None
    iso_candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(iso_candidate)
    except ValueError:
        parsed = None
        for date_format in (
            "%m/%d/%Y %I:%M:%S %p",
            "%m/%d/%Y %I:%M %p",
            "%m/%d/%Y",
        ):
            try:
                parsed = datetime.strptime(raw, date_format)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError(
                f"Miami-Dade {field_name} has an unrecognized date format"
            )
    normalized = parsed.date().isoformat()
    # The live index uses this value as an empty document-date sentinel.
    return None if normalized == "1900-01-01" else normalized


def normalize_folio(value: Any) -> str | None:
    """Return the County's 13-character folio representation when possible."""
    raw = _text(value)
    if raw is None:
        return None
    compact = raw.replace("-", "").replace(" ", "")
    if not compact.isdigit():
        raise ValueError("Miami-Dade folio must contain digits and separators")
    if len(compact) > 13:
        raise ValueError("Miami-Dade folio exceeds 13 digits")
    return compact.zfill(13)


def _document_type(value: Any) -> dict[str, Any]:
    raw = _text(value)
    if raw is None:
        return {"code": None, "description": None, "raw": None}
    match = re.match(r"^(.*?)\s+-\s+([A-Za-z0-9_&-]+)$", raw)
    if match:
        return {
            "code": match.group(2).strip(),
            "description": match.group(1).strip(),
            "raw": raw,
        }
    return {"code": raw, "description": None, "raw": raw}


def _cfn(year: int, sequence: int) -> str:
    return f"{year}R{sequence}"


def _record_ref(source_id: str, year: int, sequence: int) -> str:
    return f"RECORDER:{source_id}/{COUNTY_GEOID}/cfn/{_cfn(year, sequence)}"


def _book_page_ref(
    source_id: str,
    book_type: str,
    book: str,
    page: str,
) -> str:
    return (
        f"RECORDER-DOCUMENT:{source_id}/{COUNTY_GEOID}/"
        f"{book_type}/{book}/{page}"
    )


def _party(row: Mapping[str, Any]) -> dict[str, Any]:
    raw_party_code = _field(row, "PARTY_CODE", "partY_CODE")
    raw_firm_individual = _field(row, "FIRM_INDIV", "firM_INDIV")
    party_code = _text(raw_party_code)
    role = {
        "D": "direct",
        "R": "reverse",
    }.get((party_code or "").upper())
    entity_kind = {
        "I": "person",
        "P": "person",
        "C": "organization",
        "O": "organization",
    }.get((_text(raw_firm_individual) or "").upper())
    sequence = _integer(
        _field(row, "PARTY_SEQUENCE", "ps"),
        "party sequence",
    )
    return {
        "name": _text(_field(row, "FIRST_PARTY", "firsT_PARTY")),
        "cross_party_name": _text(
            _field(row, "SECOND_PARTY", "seconD_PARTY")
        ),
        "sequence": sequence,
        "role": role,
        "raw_role_code": raw_party_code,
        "entity_kind": entity_kind,
        "raw_address": None,
        "party_code": party_code,
        "party_code_raw": raw_party_code,
        "firm_individual_code": _text(raw_firm_individual),
        "firm_individual_code_raw": raw_firm_individual,
        "party_sequence": sequence,
        "row_key": _field(row, "KEY", "key"),
        "record_row_id": _text(_field(row, "REC_ROWID", "reC_ROWID")),
        "raw": dict(row),
    }


def _sort_nullable(value: Any) -> tuple[int, str]:
    return (value is None, str(value or ""))


def _group_record(
    rows: Sequence[Mapping[str, Any]],
    group_id: int | None,
) -> dict[str, Any]:
    first = rows[0]
    folio_raw = _field(first, "FOLIO_NUMBER", "foliO_NUMBER")
    parties = [_party(row) for row in rows]
    parties.sort(
        key=lambda party: (
            _sort_nullable(party.get("party_sequence")),
            _sort_nullable(party.get("row_key")),
            _sort_nullable(party.get("name")),
        )
    )
    return {
        "group_id": group_id,
        "folio": normalize_folio(folio_raw),
        "folio_raw": folio_raw,
        "address": {
            "raw": _text(_field(first, "address", "ADDRESS")),
            "street": _text(
                _field(first, "addressnounit", "ADDRESSNOUNIT")
            ),
            "unit": _text(_field(first, "addressunit", "ADDRESSUNIT")),
        },
        "subdivision_name": _text(
            _field(first, "SUBDIV_NAME", "subdiV_NAME")
        ),
        "legal_description": _text(
            _field(first, "LEGAL_DESCRIPTION", "legaL_DESCRIPTION")
        ),
        "block": _text(_field(first, "BLOCK_NO", "blocK_NO")),
        "plat": {
            "book": _integer(
                _field(first, "PLAT_BOOK", "plaT_BOOK"),
                "plat book",
            ),
            "page": _integer(
                _field(first, "PLAT_PAGE", "plaT_PAGE"),
                "plat page",
            ),
        },
        "township": _text(_field(first, "TOWNSHIP", "township")),
        "section": _text(_field(first, "SECTION", "section")),
        "range": _text(_field(first, "RANGE", "range")),
        "case_number": _text(_field(first, "CASE_NUM", "casE_NUM")),
        "misc_reference": _text(
            _field(first, "ORIG_MISC_REF", "misC_REF")
        ),
        "parties": parties,
    }


def normalize_documents(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_id: str,
    route: str,
    search_criteria: Mapping[str, Any] | None = None,
    lookup_images: Sequence[Any] = (),
    commercial_status: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Normalize flat Clerk rows into CFN -> property group -> party records."""
    if any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("Miami-Dade record rows must be objects")
    row_values = [dict(row) for row in rows]
    if not row_values:
        return []
    fingerprint = schema_fingerprint(inferred_schema(row_values))
    by_document: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for row in row_values:
        year = _integer(
            _field(row, "CFN_YEAR", "cfN_YEAR"),
            "CFN year",
            required=True,
        )
        sequence = _integer(
            _field(row, "CFN_SEQ", "cfN_SEQ"),
            "CFN sequence",
            required=True,
        )
        assert year is not None and sequence is not None
        by_document.setdefault((year, sequence), []).append(row)

    normalized: list[dict[str, Any]] = []
    for (year, sequence), document_rows in sorted(by_document.items()):
        first = document_rows[0]
        grouped: dict[int | None, list[Mapping[str, Any]]] = {}
        for row in document_rows:
            group_id = _integer(
                _field(row, "GROUP_ID", "grouP_ID"),
                "group ID",
            )
            grouped.setdefault(group_id, []).append(row)
        groups = [
            _group_record(group_rows, group_id)
            for group_id, group_rows in sorted(
                grouped.items(),
                key=lambda item: _sort_nullable(item[0]),
            )
        ]

        book = _integer(
            _field(first, "REC_BOOK", "reC_BOOK"),
            "recording book",
        )
        page = _integer(
            _field(first, "REC_PAGE", "reC_PAGE"),
            "recording page",
        )
        raw_book_type = _field(first, "BOOK_TYPE", "booK_TYPE")
        book_type = _text(raw_book_type)
        master_ids = sorted(
            {
                value
                for row in document_rows
                if (
                    value := _integer(
                        _field(row, "CFN_MASTER_ID", "cfN_MASTER_ID"),
                        "CFN master ID",
                    )
                )
                is not None
            }
        )
        links: dict[str, str] = {
            "official_records": PUBLIC_APP_URL,
        }
        issued_token = _text(_field(first, "qs", "QS"))
        if issued_token:
            links["record_page"] = (
                f"{PUBLIC_APP_URL}recordpage?qs={quote(issued_token, safe='')}"
            )
        if book is not None and page is not None and book_type:
            links["document_image"] = (
                f"{PUBLIC_IMAGE_API}?"
                + urlencode(
                    {
                        "sBook": str(book),
                        "sPage": str(page),
                        "sBookType": book_type,
                        "redact": "false",
                    }
                )
            )

        parsed_document_type = _document_type(
            _field(first, "DOC_TYPE", "doC_TYPE")
        )
        recording_date_raw = _field(first, "REC_DATE", "reC_DATE")
        execution_date_raw = _field(first, "DOC_DATE", "doC_DATE")
        recording_date = _iso_date(recording_date_raw, "recording date")
        execution_date = _iso_date(execution_date_raw, "execution date")
        instrument_code = _text(parsed_document_type["code"])
        consideration = _field(
            first, "CONSIDERATION_1", "consideratioN_1"
        )
        flat_parties: list[dict[str, Any]] = []
        parcel_values: list[dict[str, Any]] = []
        seen_parcels: set[str] = set()
        legal_descriptions: list[str] = []
        for group in groups:
            group_id = group.get("group_id")
            for party_value in group["parties"]:
                party = dict(party_value)
                party["group_id"] = group_id
                flat_parties.append(party)
            folio = group.get("folio")
            legal_description = group.get("legal_description")
            if legal_description and legal_description not in legal_descriptions:
                legal_descriptions.append(legal_description)
            if folio and folio not in seen_parcels:
                seen_parcels.add(folio)
                parcel_values.append(
                    {
                        "native_parcel_id": folio,
                        "link_method": "source_index_folio",
                        "link_confidence": 1.0,
                        "legal_description_raw": legal_description,
                        "address": dict(group.get("address") or {}),
                        "group_id": group_id,
                    }
                )
        source_url = (
            links.get("record_page")
            or links.get("document_image")
            or links["official_records"]
        )
        record: dict[str, Any] = {
            "canonical_ref": _record_ref(source_id, year, sequence),
            "source_id": source_id,
            "record_identity_source_id": CANONICAL_SOURCE_ID,
            "source_route": route,
            "record_kind": RECORD_KIND_INSTRUMENT,
            "jurisdiction": {
                "state_code": "FL",
                "state_fips": "12",
                "county_name": "Miami-Dade",
                "county_geoid": COUNTY_GEOID,
            },
            "document_id": _cfn(year, sequence),
            "native_document_id": _cfn(year, sequence),
            "clerk_file_number": {
                "year": year,
                "sequence": sequence,
                "display": _text(
                    _field(first, "clerk_File", "CLERK_FILE")
                )
                or f"{year} R {sequence}",
            },
            "cfn_master_ids": master_ids,
            "document_type": parsed_document_type,
            "instrument_type": (
                parsed_document_type["code"]
                or parsed_document_type["raw"]
            ),
            "is_conveyance": (
                (instrument_code or "").upper()
                in CONVEYANCE_INSTRUMENT_CODES
            ),
            "book": book,
            "page": page,
            "book_type": book_type,
            "execution_date": execution_date,
            "execution_date_raw": execution_date_raw,
            "recording_date": recording_date,
            "recording_date_raw": recording_date_raw,
            "consideration": consideration,
            "legal_description_raw": (
                "\n".join(legal_descriptions) or None
            ),
            "source_url": source_url,
            "parties": flat_parties,
            "parcels": parcel_values,
            "recording": {
                "date": recording_date,
                "book": book,
                "page": page,
                "book_type": book_type,
                "book_type_raw": raw_book_type,
            },
            "document_date": execution_date,
            "original_document": {
                "cfn_year": _integer(
                    _field(first, "ORIG_CFN_YEAR", "oriG_CFN_YEAR"),
                    "original CFN year",
                ),
                "cfn_sequence": _integer(
                    _field(first, "ORIG_CFN_SEQ", "oriG_CFN_SEQ"),
                    "original CFN sequence",
                ),
                "recording_book": _integer(
                    _field(first, "ORIG_REC_BOOK", "oriG_REC_BOOK"),
                    "original recording book",
                ),
                "recording_page": _integer(
                    _field(first, "ORIG_REC_PAGE", "oriG_REC_PAGE"),
                    "original recording page",
                ),
                "linked_document_type": _text(
                    _field(first, "LINK_DOCTYPE", "linK_DOCTYPE")
                ),
            },
            "page_counts": {
                "document": _integer(
                    _field(first, "DOC_PAGES", "doC_PAGES"),
                    "document pages",
                ),
                "appended": _integer(
                    _field(first, "APPEND_PAGES", "appenD_PAGES"),
                    "appended pages",
                ),
            },
            "status": _text(_field(first, "STATUS", "status")),
            "rerecord_flag": _text(
                _field(first, "RERECORD_FLAG", "rerecorD_FLAG")
            ),
            "financial": {
                "consideration_1": consideration,
                "consideration_2": _field(
                    first, "CONSIDERATION_2", "consideratioN_2"
                ),
                "deed_documentary_tax": _field(
                    first, "DEED_DOC_TAX", "deeD_DOC_TAX"
                ),
                "single_family_code": _field(
                    first, "SINGLE_FAMILY", "singlE_FAMILY"
                ),
                "surtax": _field(first, "SURTAX", "surtax"),
                "intangible_tax": _field(
                    first, "INTANGIBLE", "intangible"
                ),
                "documentary_stamps": _field(
                    first, "DOCUMENTARY_STAMPS", "documentarY_STAMPS"
                ),
            },
            "groups": groups,
            "source_links": links,
            "schema_fingerprint": fingerprint,
            "raw_rows": document_rows,
        }
        if search_criteria is not None:
            record["search_criteria"] = dict(search_criteria)
        if issued_token is not None:
            record["issued_search_token"] = issued_token
        if lookup_images:
            record["commercial_lookup_images"] = list(lookup_images)
        if commercial_status is not None:
            record["commercial_response"] = dict(commercial_status)
        normalized.append(record)
    return normalized


def _document_type_records(labels: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": PUBLIC_SOURCE_ID,
            "record_identity_source_id": CANONICAL_SOURCE_ID,
            "source_route": ROUTE_DOCUMENT_TYPES,
            "record_kind": RECORD_KIND_DOCUMENT_TYPE,
            "label": label,
            **_document_type(label),
        }
        for label in labels
    ]


def _public_hydration_records(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = _field(payload, "recordingModels")
    if not isinstance(rows, list) or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise SourceSchemaError(
            "Miami-Dade hydrated result lacks recordingModels",
            url=PUBLIC_RESULTS_API,
        )
    criteria = _field(payload, "searchCritiriea", "searchCriteria")
    if criteria is not None and not isinstance(criteria, Mapping):
        raise SourceSchemaError(
            "Miami-Dade hydrated search criteria must be an object",
            url=PUBLIC_RESULTS_API,
        )
    return normalize_documents(
        rows,
        source_id=PUBLIC_SOURCE_ID,
        route=ROUTE_ISSUED_RESULT_HYDRATION,
        search_criteria=criteria,
    )


def _commercial_parts(
    payload: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], list[Any], dict[str, Any]]:
    container = _field(payload, "OfficialRecordList")
    rows: Any = None
    if isinstance(container, Mapping):
        rows = _field(container, "OfficialRecords")
    elif isinstance(container, list):
        rows = container
    if rows is None:
        rows = []
    elif isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list) or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise SourceSchemaError(
            "Miami-Dade commercial response has an invalid OfficialRecordList",
            url=COMMERCIAL_API_URL,
        )
    images = _field(payload, "RecordImages")
    if images is None:
        image_values: list[Any] = []
    elif isinstance(images, list):
        image_values = list(images)
    else:
        raise SourceSchemaError(
            "Miami-Dade commercial RecordImages must be an array",
            url=COMMERCIAL_API_URL,
        )
    status = {
        "status": _field(payload, "Status"),
        "description": _field(payload, "StatusDesc"),
        "units_balance": _field(payload, "UnitsBalance"),
    }
    status_text = " ".join(
        str(value or "")
        for value in (status["status"], status["description"])
    ).upper()
    if not rows and any(
        marker in status_text
        for marker in ("ERROR", "INVALID", "DENIED", "UNAUTHORIZED", "FAILED")
    ):
        raise SourceResponseError(
            "Miami-Dade commercial API returned an error response",
            url=COMMERCIAL_API_URL,
            details={
                "status": status["status"],
                "description": status["description"],
            },
        )
    return rows, image_values, status


def _commercial_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows, images, status = _commercial_parts(payload)
    return normalize_documents(
        rows,
        source_id=CANONICAL_SOURCE_ID,
        route=ROUTE_COMMERCIAL_API,
        lookup_images=images,
        commercial_status=status,
    )


def _financial_record(
    cfn_master_id: int,
    document_type: str,
    recording_date: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "canonical_ref": (
            f"RECORDER-DETAIL:{PUBLIC_SOURCE_ID}/{COUNTY_GEOID}/"
            f"master/{cfn_master_id}/financial"
        ),
        "source_id": PUBLIC_SOURCE_ID,
        "record_identity_source_id": CANONICAL_SOURCE_ID,
        "source_route": ROUTE_RECORD_DETAIL,
        "record_kind": RECORD_KIND_FINANCIAL_DETAIL,
        "cfn_master_id": cfn_master_id,
        "document_type": _document_type(document_type),
        "recording_date": recording_date,
        "mortgage_or_deed_amount": _field(
            payload, "mortgageDeedAmount"
        ),
        "consideration": _field(payload, "consideration"),
        "raw": dict(payload),
    }


def _access_contract(args: argparse.Namespace, source_id: str) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        source_id,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(source_id)


def _make_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> MiamiDadeRecorderClient:
    limits = access_contract.get("limits") or {}
    interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return MiamiDadeRecorderClient(
        session=requests.Session(),
        timeout=args.timeout,
        retry_policy=RetryPolicy(),
        minimum_interval=interval,
    )


def _positive_integer_text(value: str, label: str) -> str:
    cleaned = "".join(str(value).split())
    if not cleaned.isdigit() or int(cleaned) <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return str(int(cleaned))


def _folio_selector(value: str) -> str:
    normalized = normalize_folio(value)
    if normalized is None or int(normalized) <= 0:
        raise ValueError("folio must identify a positive numeric parcel")
    return normalized


def _commercial_selector(args: argparse.Namespace) -> tuple[str, str]:
    if args.command == "cfn":
        return (
            _positive_integer_text(args.year, "CFN year"),
            "R" + _positive_integer_text(args.sequence, "CFN sequence"),
        )
    if args.command == "book-page":
        return (
            _positive_integer_text(args.book, "recording book"),
            _positive_integer_text(args.page, "recording page"),
        )
    if args.command == "folio":
        return (_folio_selector(args.folio), "FN")
    raise ValueError(f"unsupported commercial command: {args.command}")


def _commercial_auth_key() -> str:
    load_env_file()
    value = os.environ.get(COMMERCIAL_AUTH_ENV, "").strip()
    if not value:
        raise LookupError(COMMERCIAL_AUTH_ENV)
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise ValueError(
            f"{COMMERCIAL_AUTH_ENV} must contain the Clerk-issued GUID"
        ) from error


def _source_for_command(command: str) -> SourceMetadata:
    if command in PUBLIC_COMMAND_ROUTES:
        return PUBLIC_SOURCE_METADATA
    if command in COMMERCIAL_COMMANDS:
        return CANONICAL_SOURCE_METADATA
    raise ValueError(f"unsupported command: {command}")


def _route_for_command(command: str) -> str:
    if command in PUBLIC_COMMAND_ROUTES:
        return PUBLIC_COMMAND_ROUTES[command]
    if command in COMMERCIAL_COMMANDS:
        return ROUTE_COMMERCIAL_API
    raise ValueError(f"unsupported command: {command}")


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    route = _route_for_command(args.command)
    parameters: dict[str, Any] = {"route": route}
    if args.command == "hydrate-qs":
        parameters["issued_token"] = args.issued_token
    elif args.command == "parties":
        parameters["cfn_master_id"] = args.cfn_master_id
    elif args.command == "financial":
        parameters.update(
            {
                "cfn_master_id": args.cfn_master_id,
                "document_type": args.doc_type,
                "recording_date": args.recording_date,
            }
        )
    elif args.command == "image":
        parameters.update(
            {
                "book": args.book,
                "page": args.page,
                "book_type": args.book_type,
                "cfn_master_id": args.cfn_master_id,
            }
        )
    elif args.command in COMMERCIAL_COMMANDS:
        parameter1, parameter2 = _commercial_selector(args)
        parameters.update(
            {
                "parameter1": parameter1,
                "parameter2": parameter2,
                "credential_env": COMMERCIAL_AUTH_ENV,
            }
        )
    return parameters


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source = _source_for_command(args.command)
    return PublicRecordsQuery(
        source=source,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Miami-Dade County, Florida",
            state_code="FL",
            county_fips=COUNTY_GEOID,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: AcquisitionUnavailableError | CatalogError | OSError | ValueError,
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        return PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "acquisition_route_unavailable"
                    ),
                    message=str(decision.get("reason") or error),
                    category="access",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=PUBLIC_WARNINGS,
        )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="acquisition_route_unavailable",
                message=str(error),
                category="access_control",
                retryable=False,
            )
        ],
        warnings=PUBLIC_WARNINGS,
    )


def _credential_failure(
    query: PublicRecordsQuery,
    *,
    invalid: bool,
) -> PublicRecordsResult:
    code = "commercial_credential_invalid" if invalid else "commercial_credential_missing"
    message = (
        f"{COMMERCIAL_AUTH_ENV} is not a valid Clerk-issued GUID"
        if invalid
        else f"{COMMERCIAL_AUTH_ENV} is not configured"
    )
    return PublicRecordsResult.failure(
        query,
        ResultStatus.RESTRICTED,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="authentication",
                retryable=False,
                details={
                    "credential_env": COMMERCIAL_AUTH_ENV,
                    "source_route": ROUTE_COMMERCIAL_API,
                },
            )
        ],
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: MiamiDadeRecorderClient | Any | None = None,
) -> PublicRecordsResult:
    query = build_query(args)
    source_id = query.source.source_id
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args, source_id)
        )
    except (AcquisitionUnavailableError, CatalogError, OSError, ValueError) as error:
        result = _access_failure(query, error)
        log_search(canonical_json(query.to_dict()), source_id, None)
        return result

    source_client = client or _make_client(args, access_contract)
    auth_key: str | None = None
    if args.command in COMMERCIAL_COMMANDS:
        try:
            auth_key = _commercial_auth_key()
        except LookupError:
            result = _credential_failure(query, invalid=False)
            log_search(canonical_json(query.to_dict()), source_id, None)
            return result
        except ValueError:
            result = _credential_failure(query, invalid=True)
            log_search(canonical_json(query.to_dict()), source_id, None)
            return result

    try:
        if args.command == "document-types":
            records = _document_type_records(source_client.document_types())
        elif args.command == "hydrate-qs":
            records = _public_hydration_records(
                source_client.hydrate_qs(args.issued_token)
            )
        elif args.command == "parties":
            records = normalize_documents(
                source_client.parties(args.cfn_master_id),
                source_id=PUBLIC_SOURCE_ID,
                route=ROUTE_RECORD_DETAIL,
            )
        elif args.command == "financial":
            records = [
                _financial_record(
                    args.cfn_master_id,
                    args.doc_type,
                    args.recording_date,
                    source_client.financial(
                        args.cfn_master_id,
                        args.doc_type,
                        args.recording_date,
                    ),
                )
            ]
        elif args.command == "image":
            download = source_client.document_image(
                book=args.book,
                page=args.page,
                book_type=args.book_type,
                cfn_master_id=args.cfn_master_id,
            )
            destination = Path(args.document_output).expanduser()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(download.content)
            image_url_params: dict[str, Any] = {
                "sBook": args.book,
                "sPage": args.page,
                "sBookType": args.book_type,
                "redact": "false",
            }
            if args.cfn_master_id is not None:
                image_url_params["cfnMasterId"] = args.cfn_master_id
            records = [
                {
                    "canonical_ref": _book_page_ref(
                        PUBLIC_SOURCE_ID,
                        args.book_type,
                        args.book,
                        args.page,
                    ),
                    "source_id": PUBLIC_SOURCE_ID,
                    "record_identity_source_id": CANONICAL_SOURCE_ID,
                    "source_route": ROUTE_DOCUMENT_IMAGE,
                    "record_kind": RECORD_KIND_DOCUMENT_ARTIFACT,
                    "recording": {
                        "book": int(args.book),
                        "page": int(args.page),
                        "book_type": args.book_type,
                    },
                    "cfn_master_id": args.cfn_master_id,
                    "document_path": str(destination),
                    "filename": download.filename,
                    "media_type": download.media_type,
                    "size": len(download.content),
                    "sha256": hashlib.sha256(download.content).hexdigest(),
                    "etag": download.etag,
                    "source_url": (
                        f"{PUBLIC_IMAGE_API}?{urlencode(image_url_params)}"
                    ),
                }
            ]
        elif args.command in COMMERCIAL_COMMANDS:
            parameter1, parameter2 = _commercial_selector(args)
            assert auth_key is not None
            records = _commercial_records(
                source_client.commercial_lookup(
                    parameter1=parameter1,
                    parameter2=parameter2,
                    auth_key=auth_key,
                )
            )
        else:
            raise ValueError(f"unsupported command: {args.command}")
        warnings = PUBLIC_WARNINGS if args.command in PUBLIC_COMMAND_ROUTES else ()
        result = PublicRecordsResult.success(
            query,
            records,
            warnings=warnings,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(
            query,
            error,
            warnings=(
                PUBLIC_WARNINGS
                if args.command in PUBLIC_COMMAND_ROUTES
                else ()
            ),
        )
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="document_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=PUBLIC_WARNINGS,
        )
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=(
                PUBLIC_WARNINGS
                if args.command in PUBLIC_COMMAND_ROUTES
                else ()
            ),
        )

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), source_id, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"Miami-Dade recorder {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Miami-Dade recorder {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    for record in result.records:
        identifier = (
            record.get("document_id")
            or record.get("document_type", {}).get("code")
            or record.get("canonical_ref")
        )
        print(f"  {identifier}")
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--minimum-interval", type=float, default=0.25)
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
        help="Public-record source and acquisition catalog",
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
        help="Tracked source manifests and reviewed access decisions",
    )
    add_output_args(parser)


def _positive_cli_int(value: str) -> int:
    try:
        integer = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if integer <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return integer


def _positive_cli_text(value: str) -> str:
    try:
        return _positive_integer_text(value, "value")
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _book_type(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise argparse.ArgumentTypeError("book type must not be empty")
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query verified Miami-Dade Clerk public detail/image routes and "
            "the credentialed Official Records API"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    document_types = sub.add_parser(
        "document-types",
        help="List current Clerk document-type labels and codes",
    )
    _add_shared_arguments(document_types)

    hydrate = sub.add_parser(
        "hydrate-qs",
        help="Hydrate an already-issued public search-result token",
    )
    hydrate.add_argument("issued_token")
    _add_shared_arguments(hydrate)

    parties = sub.add_parser(
        "parties",
        help="Fetch and normalize all indexed parties for a CFN master ID",
    )
    parties.add_argument("cfn_master_id", type=_positive_cli_int)
    _add_shared_arguments(parties)

    financial = sub.add_parser(
        "financial",
        help="Fetch supplemental financial fields for a CFN master ID",
    )
    financial.add_argument("cfn_master_id", type=_positive_cli_int)
    financial.add_argument("--doc-type", required=True)
    financial.add_argument("--recording-date", required=True)
    _add_shared_arguments(financial)

    image = sub.add_parser(
        "image",
        help="Download a public record PDF by recording book and page",
    )
    image.add_argument("book", type=_positive_cli_text)
    image.add_argument("page", type=_positive_cli_text)
    image.add_argument("--book-type", type=_book_type, default="O")
    image.add_argument("--cfn-master-id", type=_positive_cli_int)
    image.add_argument(
        "--document-output",
        required=True,
        help="Destination path for the downloaded PDF",
    )
    _add_shared_arguments(image)

    cfn = sub.add_parser(
        "cfn",
        help="Query the commercial API by Clerk File Number",
    )
    cfn.add_argument("year", type=_positive_cli_text)
    cfn.add_argument("sequence", type=_positive_cli_text)
    _add_shared_arguments(cfn)

    book_page = sub.add_parser(
        "book-page",
        help="Query the commercial API by recording book and page",
    )
    book_page.add_argument("book", type=_positive_cli_text)
    book_page.add_argument("page", type=_positive_cli_text)
    _add_shared_arguments(book_page)

    folio = sub.add_parser(
        "folio",
        help="Query the commercial API by Miami-Dade folio",
    )
    folio.add_argument("folio")
    _add_shared_arguments(folio)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0 or args.minimum_interval < 0:
        parser.error("--timeout must be positive and --minimum-interval non-negative")
    try:
        result = execute(args)
    except ValueError as error:
        parser.error(str(error))
    _emit(result, args)


if __name__ == "__main__":
    main()
