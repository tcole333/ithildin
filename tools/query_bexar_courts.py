#!/usr/bin/env python3
"""Query Bexar County District Clerk historical case files.

The official District Clerk page links to a Kofile/GovOS Neumo PublicSearch
tenant containing historical case-file indexes, OCR excerpts, parties, and
page images. This adapter intentionally models that archive separately from
the current Tyler Justice Information Portal.

Usage:
    uv run python tools/query_bexar_courts.py search SMITH
    uv run python tools/query_bexar_courts.py search "jury verdict" --ocr
    uv run python tools/query_bexar_courts.py search \
        --date-from 1919-01-01 --date-to 1919-12-31
    uv run python tools/query_bexar_courts.py case 229791650
    uv run python tools/query_bexar_courts.py page 229791650 1 /tmp/page.png
    uv run python tools/query_bexar_courts.py probe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urljoin

try:
    from tools.kofile_publicsearch import (
        KofileAccessError,
        KofileNotFoundError,
        KofilePageImage,
        KofilePublicSearchClient,
        KofilePublicSearchError,
        KofileRateLimitError,
        KofileSearchPage,
        KofileSourceChangedError,
    )
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
    from tools.public_records_http import inferred_schema, schema_fingerprint
    from tools.public_records_store import canonical_court_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from kofile_publicsearch import (
        KofileAccessError,
        KofileNotFoundError,
        KofilePageImage,
        KofilePublicSearchClient,
        KofilePublicSearchError,
        KofileRateLimitError,
        KofileSearchPage,
        KofileSourceChangedError,
    )
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
    from public_records_http import inferred_schema, schema_fingerprint
    from public_records_store import canonical_court_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-tx-bexar-district-historical-cases"
COUNTY_GEOID = "48029"
STATE_CODE = "TX"
DEPARTMENT = "HC"
COURT_ID = "tx-bexar-district-clerk-historical-cases"
COURT_NAME = "Bexar County District Clerk Historical Cases"
OFFICIAL_LINKING_PAGE = "https://www.bexar.org/DC"
BASE_URL = "https://bexardistrict.tx.publicsearch.us"
WEBSOCKET_URL = "wss://bexardistrict.tx.publicsearch.us/ws"
RESULTS_URL = f"{BASE_URL}/results"
DETAIL_URL_TEMPLATE = f"{BASE_URL}/doc/{{doc_id}}?department={DEPARTMENT}"
PROBE_DATE_FROM = "1919-01-01"
PROBE_DATE_TO = "1919-12-31"
UNKNOWN_DATE_SENTINEL = "1/1/1800"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Bexar County District Clerk Historical Cases",
    source_role="historical_case_index_ocr_page_images",
    base_url=BASE_URL,
    dataset_id=DEPARTMENT,
    metadata={
        "authority": "Bexar County District Clerk",
        "operator": "GovOS/Kofile",
        "platform_family": "kofile_neumo_publicsearch_ws",
        "coverage": "Bexar County historical case files",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
    },
)

SOURCE_WARNINGS = (
    "This source is a historical case-file index, not a modern docket.",
    "Portal page images are uncertified and are not a substitute for an official clerk copy.",
    "A raw file date of 1/1/1800 is retained as an unknown-date sentinel and is not asserted as the filing date.",
)


class BexarCourtSelectionError(ValueError):
    """A caller supplied an unsupported or ambiguous source selection."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Bexar historical case lacks {field_name}")
    return value.strip()


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Bexar historical case has invalid {field_name}")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Bexar historical case lacks numeric {field_name}"
        ) from error
    if result <= 0:
        raise ValueError(f"Bexar historical case has invalid {field_name}")
    return result


def _optional_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _compact_date(value: str, field_name: str) -> str:
    raw = value.strip()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as error:
        raise BexarCourtSelectionError(
            "invalid_date_filter",
            f"{field_name} must be an ISO calendar date",
            details={"field": field_name, "value": value},
        ) from error
    return parsed.strftime("%Y%m%d")


def _recorded_date(value: Any) -> tuple[str | None, str | None, str | None]:
    raw = _text(value)
    if raw is None:
        return None, None, "not_provided"
    if raw == UNKNOWN_DATE_SENTINEL:
        return raw, None, "unknown_date_sentinel"
    try:
        normalized = datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"Bexar historical case has unparseable file date {raw!r}"
        ) from error
    return raw, normalized, "source_file_date"


def _absolute_source_path(value: str | None) -> str | None:
    return urljoin(f"{BASE_URL}/", value) if value else None


def _court_payload() -> dict[str, Any]:
    return {
        "court_id": COURT_ID,
        "native_court_id": DEPARTMENT,
        "name": COURT_NAME,
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "court_level": "district",
        "division": "Historical Cases",
        "official_url": OFFICIAL_LINKING_PAGE,
    }


def _parties(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("Bexar historical case lacks a party list")
    parties: list[dict[str, Any]] = []
    for party in value:
        if not isinstance(party, Mapping):
            raise ValueError("Bexar historical case party must be an object")
        raw_name = _text(party.get("name"))
        if raw_name is None:
            continue
        party_type_code = _text(party.get("partyTypeCode"))
        native_type = _text(party.get("type"))
        is_direct = party.get("isDirect")
        if party_type_code == "DT" or native_type == "direct" or is_direct is True:
            role = "Plaintiff"
        elif (
            party_type_code == "IT"
            or native_type == "indirect"
            or is_direct is False
        ):
            role = "Defendant"
        else:
            role = native_type or party_type_code or "Unknown"
        parties.append(
            {
                "sequence_no": len(parties) + 1,
                "role": role,
                "raw_name": raw_name,
                "native_role": native_type,
                "party_type_code": party_type_code,
                "is_direct": is_direct if isinstance(is_direct, bool) else None,
                "access_state": "public",
            }
        )
    return parties


def _page_manifest(
    row: Mapping[str, Any],
    *,
    doc_id: int,
    image_id: int | None,
    page_count: int | None,
) -> dict[str, Any]:
    urls = row.get("urls")
    thumbnails = row.get("thumbnails")
    url_list = urls if isinstance(urls, list) else []
    thumbnail_list = thumbnails if isinstance(thumbnails, list) else []
    pages = []
    for index in range(max(len(url_list), len(thumbnail_list))):
        image_path = (
            url_list[index]
            if index < len(url_list) and isinstance(url_list[index], str)
            else None
        )
        thumbnail_path = (
            thumbnail_list[index]
            if index < len(thumbnail_list)
            and isinstance(thumbnail_list[index], str)
            else None
        )
        pages.append(
            {
                "page_number": index + 1,
                "signed_image_url": _absolute_source_path(image_path),
                "signed_thumbnail_url": _absolute_source_path(thumbnail_path),
            }
        )
    image_groups = row.get("images")
    return {
        "doc_id": doc_id,
        "image_id": image_id,
        "page_count": page_count,
        "signed_urls_are_ephemeral": True,
        "same_anonymous_session_cookie_required": True,
        "pages": pages,
        "image_groups": (
            [dict(value) for value in image_groups if isinstance(value, Mapping)]
            if isinstance(image_groups, list)
            else []
        ),
    }


def _document_artifact(
    *,
    doc_id: int,
    image_id: int | None,
    case_type: str | None,
    filing_date: str | None,
    page_count: int | None,
    access_state: str,
    ocr_excerpt: str | None,
) -> dict[str, Any]:
    native_document_id = (
        f"{doc_id}:{image_id}" if image_id is not None else str(doc_id)
    )
    return {
        "native_document_id": native_document_id,
        "document_type": case_type or "historical_case_file",
        "filed_date": filing_date,
        "source_url": DETAIL_URL_TEMPLATE.format(doc_id=doc_id),
        "mime_type": "image/png",
        "page_count": page_count,
        "ocr_status": (
            "excerpt_available" if ocr_excerpt else "not_returned"
        ),
        "certification_status": "uncertified",
        "access_state": access_state,
        "native_access_state": (
            "isSecured:true" if access_state == "restricted" else "isSecured:false"
        ),
    }


def normalize_case(
    row: Mapping[str, Any],
    *,
    schema: str,
    search_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize one native case-file result without synthesizing a docket."""

    doc_id = _positive_int(row.get("id", row.get("docId")), "docId")
    raw_case_number = _required_text(
        row.get("docNumber", row.get("documentNumber")),
        "case number",
    )
    rs_id = _required_text(row.get("rsId"), "rsId")
    image_id = _optional_int(row.get("imageId"))
    if image_id is None:
        images = row.get("images")
        if isinstance(images, list) and images and isinstance(images[0], Mapping):
            image_id = _optional_int(images[0].get("id"))
    page_count = _optional_int(
        row.get("pageCount", row.get("totalPages"))
    )
    raw_file_date, filing_date, date_quality = _recorded_date(
        row.get("recordedDate")
    )
    case_type = _text(row.get("docType"))
    access_state = "restricted" if row.get("isSecured") is True else "public"
    ocr_excerpt = _text(row.get("ocrText"))
    source_url = DETAIL_URL_TEMPLATE.format(
        doc_id=quote(str(doc_id), safe="")
    )
    record = {
        "canonical_ref": canonical_court_ref(
            SOURCE_ID,
            COURT_ID,
            raw_case_number,
            native_id=str(doc_id),
        ),
        "source_id": SOURCE_ID,
        "record_kind": "case",
        "court": _court_payload(),
        "raw_case_number": raw_case_number,
        "display_case_number": raw_case_number,
        "source_internal_id": str(doc_id),
        "doc_id": doc_id,
        "rs_id": rs_id,
        "image_id": image_id,
        "instrument_number": _text(row.get("instrumentNumber")),
        "case_type": case_type,
        "filing_date": filing_date,
        "source_file_date_raw": raw_file_date,
        "source_file_date_quality": date_quality,
        "status": None,
        "access_state": access_state,
        "native_access_state": (
            "isSecured:true" if access_state == "restricted" else "isSecured:false"
        ),
        "certified_record": False,
        "source_url": source_url,
        "parties": _parties(row.get("parties")),
        "documents": [
            _document_artifact(
                doc_id=doc_id,
                image_id=image_id,
                case_type=case_type,
                filing_date=filing_date,
                page_count=page_count,
                access_state=access_state,
                ocr_excerpt=ocr_excerpt,
            )
        ],
        "ocr_excerpt": ocr_excerpt,
        "page_manifest": _page_manifest(
            row,
            doc_id=doc_id,
            image_id=image_id,
            page_count=page_count,
        ),
        "source_versions": {
            "metadata_version": row.get("metadataVersion"),
            "document_version": row.get("docVersion", row.get("version")),
            "created_at": row.get("createdAt"),
            "updated_at": row.get("updatedAt"),
            "content_modified_at": row.get("contentModifiedAt"),
        },
        "schema_fingerprint": schema,
        "raw": dict(row),
    }
    if search_metadata is not None:
        record["search_metadata"] = dict(search_metadata)
    return record


def _access_contract(args: argparse.Namespace) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        SOURCE_ID,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(args, "catalog_config", str(DEFAULT_CATALOG_CONFIG_PATH))
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(SOURCE_ID)


def _make_client(args: argparse.Namespace) -> KofilePublicSearchClient:
    return KofilePublicSearchClient(
        BASE_URL,
        websocket_url=WEBSOCKET_URL,
        timeout=args.timeout,
    )


def _search_selection(args: argparse.Namespace) -> tuple[str | None, str | None]:
    query_text = _text(getattr(args, "query", None))
    date_from = _text(getattr(args, "date_from", None))
    date_to = _text(getattr(args, "date_to", None))
    if bool(date_from) != bool(date_to):
        raise BexarCourtSelectionError(
            "incomplete_date_range",
            "--date-from and --date-to must be supplied together",
        )
    if query_text is None and date_from is None:
        raise BexarCourtSelectionError(
            "search_selector_required",
            "search requires text or a complete date range",
        )
    if date_from and query_text and not getattr(args, "ocr", False):
        raise BexarCourtSelectionError(
            "date_range_text_requires_ocr",
            "text combined with a date range requires --ocr",
        )
    date_range = None
    if date_from and date_to:
        compact_from = _compact_date(date_from, "--date-from")
        compact_to = _compact_date(date_to, "--date-to")
        if compact_from > compact_to:
            raise BexarCourtSelectionError(
                "invalid_date_range",
                "--date-from must not be later than --date-to",
            )
        date_range = f"{compact_from},{compact_to}"
    return query_text, date_range


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {"department": DEPARTMENT}
    requested_limit: int | None = None
    cursor: str | None = None
    if args.command == "search":
        parameters.update(
            query=getattr(args, "query", None),
            ocr=getattr(args, "ocr", False),
            date_from=getattr(args, "date_from", None),
            date_to=getattr(args, "date_to", None),
            offset=getattr(args, "offset", 0),
        )
        requested_limit = args.limit
        cursor = f"kofile:offset:{args.offset}"
    elif args.command in {"case", "page"}:
        parameters["doc_id"] = args.doc_id
        if args.command == "page":
            parameters.update(
                page_number=args.page_number,
                destination=(
                    str(args.destination) if args.destination else None
                ),
            )
    elif args.command == "probe":
        parameters.update(
            date_from=PROBE_DATE_FROM,
            date_to=PROBE_DATE_TO,
        )
        requested_limit = 1
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Bexar County, Texas",
            state_code=STATE_CODE,
            county_fips=COUNTY_GEOID,
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=cursor,
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
            warnings=SOURCE_WARNINGS,
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
        warnings=SOURCE_WARNINGS,
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus(acquisition_result_status(decision)),
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code")
                    or "acquisition_route_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "Catalogued acquisition route is unavailable"
                ),
                category="access",
                retryable=False,
                details=decision,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _selection_failure(
    query: PublicRecordsQuery,
    error: BexarCourtSelectionError,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category="query_selection",
                retryable=False,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _source_failure(
    query: PublicRecordsQuery,
    error: KofilePublicSearchError,
) -> PublicRecordsResult:
    if isinstance(error, KofileAccessError):
        status = ResultStatus.RESTRICTED
        category = "access"
    elif isinstance(error, KofileRateLimitError):
        status = ResultStatus.RATE_LIMITED
        category = "rate_limit"
    elif isinstance(error, KofileSourceChangedError):
        status = ResultStatus.SOURCE_CHANGED
        category = "source_schema"
    else:
        status = ResultStatus.UNAVAILABLE
        category = "transport"
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=error.code,
                message=str(error),
                category=category,
                retryable=error.retryable,
                details=error.details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    page: KofileSearchPage,
) -> PublicRecordsResult:
    observed_schema = schema_fingerprint(inferred_schema(page.records))
    search_metadata = {
        "source_total_count": page.total_count,
        "offset": page.offset,
        "limit": page.limit,
        "statistics": dict(page.statistics),
        "response_type": page.response_type,
    }
    records = [
        normalize_case(
            row,
            schema=observed_schema,
            search_metadata=search_metadata,
        )
        for row in page.records
    ]
    next_cursor = (
        f"kofile:offset:{page.next_offset}"
        if page.next_offset is not None
        else None
    )
    return PublicRecordsResult.success(
        query,
        records,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _page_record(
    page: KofilePageImage,
    *,
    destination: Path | None,
) -> tuple[dict[str, Any], str | None]:
    observed_schema = schema_fingerprint(inferred_schema([page.document]))
    record = normalize_case(page.document, schema=observed_schema)
    digest = hashlib.sha256(page.content).hexdigest()
    storage_path = str(destination.resolve()) if destination else None
    page_artifact = {
        "native_document_id": (
            f"{record['doc_id']}:{record.get('image_id')}:"
            f"page:{page.page_number}"
        ),
        "document_type": "historical_case_file_page",
        "filed_date": record.get("filing_date"),
        "source_url": page.source_url,
        "sha256": digest,
        "mime_type": page.media_type,
        "page_count": 1,
        "storage_path": storage_path,
        "ocr_status": "not_run",
        "certification_status": "uncertified",
        "access_state": "public",
        "native_access_state": "anonymous_signed_page_image",
    }
    record["documents"] = [page_artifact]
    record["page_download"] = {
        "page_number": page.page_number,
        "size": len(page.content),
        "sha256": digest,
        "mime_type": page.media_type,
        "etag": page.etag,
        "storage_path": storage_path,
        "signed_source_url": page.source_url,
    }
    return record, storage_path


def _execute_command(
    args: argparse.Namespace,
    client: KofilePublicSearchClient | Any,
    query: PublicRecordsQuery,
) -> PublicRecordsResult:
    if args.command == "search":
        search_text, date_range = _search_selection(args)
        page = client.search(
            department=DEPARTMENT,
            limit=args.limit,
            offset=args.offset,
            search_value=search_text,
            search_ocr_text=args.ocr,
            recorded_date_range=date_range,
            workspace_id=args.workspace_id,
        )
        return _search_result(query, page)

    if args.command == "case":
        payload = client.fetch_document(args.doc_id)
        observed_schema = schema_fingerprint(inferred_schema([payload]))
        return PublicRecordsResult.success(
            query,
            [normalize_case(payload, schema=observed_schema)],
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "page":
        page = client.fetch_page_image(args.doc_id, args.page_number)
        destination = (
            Path(args.destination).expanduser()
            if args.destination is not None
            else None
        )
        if destination is not None:
            if destination.exists() and not args.overwrite:
                raise OSError(
                    f"destination exists; pass --overwrite: {destination}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(page.content)
        record, storage_path = _page_record(
            page,
            destination=destination,
        )
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[storage_path] if storage_path else (),
            warnings=SOURCE_WARNINGS,
        )

    if args.command == "probe":
        bootstrap = client.bootstrap()
        if DEPARTMENT not in bootstrap.department_codes:
            raise KofileSourceChangedError(
                f"PublicSearch tenant no longer exposes {DEPARTMENT}",
                code="historical_department_missing",
                retryable=False,
                details={"departments": list(bootstrap.department_codes)},
            )
        date_range = (
            f"{_compact_date(PROBE_DATE_FROM, 'probe start')},"
            f"{_compact_date(PROBE_DATE_TO, 'probe end')}"
        )
        page = client.search(
            department=DEPARTMENT,
            limit=1,
            offset=0,
            recorded_date_range=date_range,
            workspace_id="ithildin-bexar-historical-probe",
        )
        if not page.records:
            raise KofileSourceChangedError(
                "Bexar historical probe record is no longer returned",
                code="probe_record_missing",
                retryable=False,
            )
        doc_id = _positive_int(
            page.records[0].get("id", page.records[0].get("docId")),
            "probe docId",
        )
        payload = client.fetch_document(doc_id)
        observed_schema = schema_fingerprint(inferred_schema([payload]))
        record = normalize_case(payload, schema=observed_schema)
        record["probe"] = {
            "tenant_id": bootstrap.tenant_id,
            "department_codes": list(bootstrap.department_codes),
            "department_date_ranges": dict(
                bootstrap.department_date_ranges
            ),
            "source_total_count_in_probe_range": page.total_count,
            "statistics": dict(page.statistics),
            "search_response_type": page.response_type,
        }
        return PublicRecordsResult.success(
            query,
            [record],
            warnings=SOURCE_WARNINGS,
        )

    raise ValueError(f"unsupported Bexar court command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: KofilePublicSearchClient | Any | None = None,
) -> PublicRecordsResult:
    """Execute one Bexar historical-court operation."""

    query = build_query(args)
    try:
        decision = (
            dict(access_decision)
            if access_decision is not None
            else _access_contract(args)
        )
    except (AcquisitionUnavailableError, CatalogError, OSError, ValueError) as error:
        result = _access_failure(query, error)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result
    if not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    source_client = client or _make_client(args)
    owns_client = client is None
    try:
        result = _execute_command(args, source_client, query)
    except BexarCourtSelectionError as error:
        result = _selection_failure(query, error)
    except KofileNotFoundError:
        result = PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    except KofilePublicSearchError as error:
        result = _source_failure(query, error)
    except OSError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="page_write_failed",
                    message=str(error),
                    category="local_io",
                    retryable=False,
                )
            ],
            warnings=SOURCE_WARNINGS,
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
            warnings=SOURCE_WARNINGS,
        )
    finally:
        if owns_client:
            source_client.close()

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


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Bexar historical courts {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Bexar historical courts {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            f"  {record.get('raw_case_number') or '?'} | "
            f"doc {record.get('doc_id') or '?'} | "
            f"{record.get('case_type') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_catalog_and_output(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--timeout", type=float, default=30.0)
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query the official Bexar County District Clerk historical "
            "case-file archive"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser(
        "search",
        help="Search case index text, OCR, or a file-date range",
    )
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--ocr",
        action="store_true",
        help="Search document OCR rather than only indexed fields",
    )
    search.add_argument("--date-from", help="File date on/after YYYY-MM-DD")
    search.add_argument("--date-to", help="File date on/before YYYY-MM-DD")
    search.add_argument("--limit", type=int, default=50)
    search.add_argument("--offset", type=int, default=0)
    search.add_argument(
        "--workspace-id",
        help="Optional caller-stable source workspace identifier",
    )
    _add_catalog_and_output(search)

    case = sub.add_parser(
        "case",
        help="Fetch exact case-file detail by native document ID",
    )
    case.add_argument("doc_id", type=int)
    _add_catalog_and_output(case)

    page = sub.add_parser(
        "page",
        help="Fetch one page image after refreshing its signed URL",
    )
    page.add_argument("doc_id", type=int)
    page.add_argument("page_number", type=int)
    page.add_argument("destination", nargs="?")
    page.add_argument("--overwrite", action="store_true")
    _add_catalog_and_output(page)

    probe = sub.add_parser(
        "probe",
        help="Run a bounded tenant, search, and detail health check",
    )
    _add_catalog_and_output(probe)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "limit", 1) <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "offset", 0) < 0:
        parser.error("--offset must not be negative")
    if getattr(args, "doc_id", 1) <= 0:
        parser.error("doc_id must be positive")
    if getattr(args, "page_number", 1) <= 0:
        parser.error("page_number must be positive")
    try:
        result = execute(args)
    except BexarCourtSelectionError as error:
        parser.error(str(error))
        return
    _emit(result, args)


if __name__ == "__main__":
    main()
