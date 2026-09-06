#!/usr/bin/env python3
"""Search and parse Broward County Official Records.

The county's AcclaimWeb portal is useful for historical discovery and public
document PDFs.  Broward also publishes a rolling set of quality-assured daily
index files (DOC/NME/LNK/LGL) and public TIFF images.  This adapter gives those
interfaces distinct commands while normalizing both to the same instrument
identity.

Examples:
    uv run python tools/query_broward_official_records.py routes --json
    uv run python tools/query_broward_official_records.py probe --json
    uv run python tools/query_broward_official_records.py name \
        "EPSTEIN, JEFFREY" --from-date 1977-01-01 --json
    uv run python tools/query_broward_official_records.py parcel \
        514223CB0580 --from-date 1977-01-01 --json
    uv run python tools/query_broward_official_records.py instrument \
        114957232 --output /tmp/broward-instrument.json
    uv run python tools/query_broward_official_records.py detail \
        114957232 --output /tmp/broward-detail.json
    uv run python tools/query_broward_official_records.py download \
        114957232 /tmp/114957232.pdf --json
    uv run python tools/query_broward_official_records.py bulk \
        07-26-2026doc-ver.txt --names 07-26-2026nme-ver.txt \
        --links 07-26-2026lnk-ver.txt --legals 07-26-2026lgl-ver.txt \
        --range-file 07-26-2026doc-ver-rng.txt --output /tmp/broward-daily.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence

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
    )
    from tools.public_records_store import canonical_property_ref
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
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-fl-broward-official-records"
COUNTY_GEOID = "12011"
STATE_CODE = "FL"
BASE_URL = "https://officialrecords.broward.org/AcclaimWeb"
SEARCH_URL = f"{BASE_URL}/"
BULK_INFORMATION_URL = (
    "https://www.broward.org/RecordsTaxesTreasury/Records/Pages/"
    "IndexFiles-Completed.aspx"
)
BULK_LAYOUT_URL = (
    "https://www.broward.org/RecordsTaxesTreasury/Records/Documents/"
    "ExportFilesLayout.pdf"
)
DOCUMENT_TYPES_URL = (
    "https://www.broward.org/RecordsTaxesTreasury/Records/Documents/"
    "DocumentTypeDescriptions.pdf"
)
SEARCH_COPY_URL = (
    "https://www.broward.org/RecordsTaxesTreasury/Records/Pages/"
    "SearchCopySectionServices.aspx"
)
ONLINE_ORDERS_URL = f"{BASE_URL}/OnlineOrders/Cart"
PROPERTY_APPRAISER_URL = "https://web.bcpa.net/BcpaClient/#/Record-Search"
PROPERTY_MAP_URL = "https://gisweb-adapters.bcpa.net/bcpawebmap_ex/bcpawebmap.aspx"
TAX_COLLECTOR_URL = "https://broward.county-taxes.com/public/"
COURT_SEARCH_URL = "https://www.browardclerk.org/Web2"
TAX_DEED_INFORMATION_URL = (
    "https://www.broward.org/RecordsTaxesTreasury/RecordingClerk/Pages/"
    "TaxDeeds.aspx"
)
TAX_DEED_AUCTION_URL = "https://broward.realtaxdeed.com/"
FL_DOR_URL = (
    "https://floridarevenue.com/property/Pages/"
    "DataPortal_RequestAssessmentRollGISData.aspx"
)
HELPER_PATH = Path(__file__).with_name(
    "_broward_official_records_browser_helper.js"
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Broward County Official Records",
    source_role=(
        "county_recorder_instrument_index_cross_references_and_public_images"
    ),
    base_url=SEARCH_URL,
    dataset_id="acclaimweb-and-daily-index-extracts",
    metadata={
        "authority": (
            "Broward County Records, Taxes and Treasury Division, "
            "Recording Section"
        ),
        "state_code": STATE_CODE,
        "county_geoid": COUNTY_GEOID,
        "platform_family": "harris_recording_solutions_acclaimweb",
        "record_identity_key": "instrument_number",
        "interactive_search_page_size": 100,
        "bulk_layout_url": BULK_LAYOUT_URL,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name="Broward County, Florida",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality="Broward County",
)

SOURCE_WARNINGS = (
    (
        "Search-grid rows are index observations. A downloaded PDF or daily "
        "TIFF is a separate source artifact."
    ),
    (
        "The instrument-number form returns a forward result window; this "
        "adapter exact-filters that window before returning an exact result."
    ),
    (
        "The free official bulk endpoint is a rolling daily-release channel, "
        "while the interactive portal supplies historical discovery."
    ),
)

PORTAL_SEARCH_PATHS: Mapping[str, str] = {
    "party_name": "/search/SearchTypeName",
    "book_page": "/search/SearchTypeBookPage",
    "document_type": "/search/SearchTypeDocType",
    "instrument_number": "/search/SearchTypeInstrumentNumber",
    "case_number": "/search/SearchTypeCaseNumber",
    "consideration": "/search/SearchTypeConsideration",
    "record_date": "/search/SearchTypeRecordDate",
    "simple_search": "/search/SearchTypeSimpleSearch",
    "parcel_id": "/search/SearchTypeParcel",
}

DOCUMENT_TYPE_DESCRIPTIONS: Mapping[str, str] = {
    "ADP": "Adoption",
    "AFF": "Affidavit",
    "AGD": "Agreement for Deed",
    "AGR": "Agreement",
    "AST": "Assignment",
    "CDO": "Condominium Documents",
    "CER": "Certificate",
    "CET": "Certificate of Title",
    "CFJ": "Certified Final Judgment",
    "CJF": "Certified Judgment - Foreign",
    "CMV": "Certificate of Compliance Re Sale Motor Vehicle",
    "COP": "Certificate of Payment to Contractor",
    "CP": "Court Paper",
    "D": "Deed Transfers of Real Property",
    "DC": "Death Certificate",
    "DPR": "Domestic Partnership",
    "EAS": "Easement Related",
    "FJ": "Final Judgment",
    "FS UCC": "UCC Financing Statement Related",
    "GOV": "Gov Orders Ordinances Petitions & Resolutions",
    "LIE": "Lien",
    "LIEN CORP": "Corporate Lien Warrant Exempt",
    "LNP": "Land Patent",
    "LP": "Lis Pendens",
    "M": "Mortgage/ Modifications & Assumptions",
    "M EXEMPT": "Mortgage Tax Exempt",
    "M INTG EXEMPT": "Mortgage Tax Exempt",
    "MAP": "Miscellaneous Maps",
    "MIL": "Military Discharge",
    "MOD": "Modification",
    "NCL": "Notice of Contest of Lien",
    "NCP": "Notice of Contest of Payment",
    "NIP": "Notice of Interest in Property",
    "NOB": "Notice of Bond",
    "NOC": "Notice of Commencement",
    "NOH": "Notice of Homestead/Homestead Affidavit",
    "NOP": "Notice of Permit",
    "NOT": "Notice",
    "NPD": "Notice of Preservation of Declaration",
    "PCS": "Public Construction Security",
    "PLAT": "Plat",
    "PLAT REL": "Plat Related",
    "PR": "Partial Release",
    "PRO": "Probate",
    "REL CORP": "Release Corp Lien Warrant Exempt",
    "RES": "Restrictions & Related Docs",
    "RST": "Release/Revoke/Satisfy or Terminate",
    "RW MAP": "Right of Way Maps",
    "TBLIE": "Transfer Lien to Bond",
    "TCLIE": "Transfer Lien to Cash Deposit",
}

DOC_FIELDS = (
    "instrument_number",
    "record_date_compact",
    "record_date_display",
    "record_time",
    "document_type_code",
    "consideration",
    "book_number",
    "page_number",
    "book_type",
    "legal_description",
    "parcel_id",
    "documentary_tax",
    "intangible_tax",
    "number_of_names",
    "confidentiality_code",
    "status_code",
    "rerecord_flag",
    "source_code",
    "case_number",
)
NAME_FIELDS = (
    "instrument_number",
    "party_name",
    "party_type",
    "name_sequence",
)
LINK_FIELDS = (
    "instrument_number",
    "book_number",
    "page_number",
    "book_type",
    "document_type_code",
    "prior_instrument_number",
    "prior_book_number",
    "prior_page_number",
    "prior_book_type",
    "prior_document_type_code",
    "keypunch",
)
LEGAL_FIELDS = (
    "instrument_number",
    "legal_description",
    "parcel_id",
)

HelperRunner = Callable[[Sequence[str], float], Mapping[str, Any]]


class BrowardRecorderError(RuntimeError):
    """Structured Broward source or local-parser failure."""


class BrowardSourceChanged(BrowardRecorderError):
    """The returned source schema no longer matches the verified layout."""


class BrowardBrowserError(BrowardRecorderError):
    """The browser-session helper could not complete an operation."""

    def __init__(self, message: str, *, error_type: str = "Error") -> None:
        super().__init__(message)
        self.error_type = error_type


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _unique(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = _text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    normalized = _text(value)
    if not normalized:
        return None
    candidate = re.sub(r"[^0-9.\-]", "", normalized)
    if not candidate:
        return None
    try:
        return float(candidate)
    except ValueError:
        return None


def _integer(value: Any) -> int | None:
    normalized = _text(value)
    if not normalized or not re.fullmatch(r"-?\d+", normalized):
        return None
    return int(normalized)


def _iso_date(value: Any) -> str | None:
    normalized = _text(value)
    if not normalized:
        return None
    epoch_match = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d+)?\)/", normalized)
    if epoch_match:
        timestamp = int(epoch_match.group(1)) / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
    for date_format in (
        "%Y%m%d",
        "%m/%d/%Y",
        "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _instrument(value: Any) -> str | None:
    normalized = _text(value)
    if not normalized:
        return None
    digits = re.sub(r"\D", "", normalized)
    return digits or None


def _parcel_key(value: Any) -> str | None:
    normalized = _text(value)
    if not normalized:
        return None
    key = re.sub(r"[^0-9A-Za-z]", "", normalized).upper()
    return key or None


def _book_page(value: Any) -> tuple[str | None, str | None]:
    normalized = _text(value)
    if not normalized:
        return None, None
    match = re.fullmatch(r"\s*([^/\s]+)\s*/\s*([^/\s]+)\s*", normalized)
    return (match.group(1), match.group(2)) if match else (None, None)


def _party_role(value: Any) -> tuple[str, str]:
    normalized = (_text(value) or "").casefold()
    if normalized in {"from", "direct", "d"}:
        return "grantor", "direct"
    if normalized in {"to", "reverse", "indirect", "r"}:
        return "grantee", "reverse"
    return "indexed_party", normalized or "unresolved"


def _instrument_ref(instrument_number: str) -> str:
    return canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "instrument",
        instrument_number,
    )


def _grid_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise BrowardSourceChanged("portal grid payload has no data array")
    if not isinstance(payload.get("total"), (int, float)):
        raise BrowardSourceChanged("portal grid payload has no numeric total")
    for row in rows:
        if not isinstance(row, Mapping):
            raise BrowardSourceChanged("portal grid contains a non-object row")
    return list(rows)


def normalize_grid(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Group Acclaim party/result rows by stable instrument number."""

    rows = _grid_rows(payload)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        instrument_number = _instrument(row.get("InstrumentNumber"))
        if not instrument_number:
            raise BrowardSourceChanged(
                "portal grid row has no numeric instrument number"
            )
        grouped[instrument_number].append(row)

    records: list[dict[str, Any]] = []
    for instrument_number, instrument_rows in grouped.items():
        representative = instrument_rows[0]
        parties: list[dict[str, Any]] = []
        seen_parties: set[tuple[str, str]] = set()
        related_names: list[dict[str, str]] = []
        source_item_ids: list[str] = []
        source_guids: list[str] = []
        for row in instrument_rows:
            name = _text(row.get("Name"))
            native_role = _text(row.get("Party"))
            role, direction = _party_role(native_role)
            if name and (name.casefold(), role) not in seen_parties:
                parties.append(
                    {
                        "name": name,
                        "role": role,
                        "native_role": native_role,
                        "index_direction": direction,
                    }
                )
                seen_parties.add((name.casefold(), role))
            related = _text(row.get("CrossPartyName"))
            if related:
                inverse_role = (
                    "grantee"
                    if role == "grantor"
                    else "grantor"
                    if role == "grantee"
                    else "related_party"
                )
                related_names.append(
                    {
                        "name": related,
                        "relationship": "cross_party_name",
                        "suggested_role": inverse_role,
                    }
                )
                if (related.casefold(), inverse_role) not in seen_parties:
                    parties.append(
                        {
                            "name": related,
                            "role": inverse_role,
                            "native_role": "CrossPartyName",
                            "index_direction": (
                                "reverse"
                                if inverse_role == "grantee"
                                else "direct"
                                if inverse_role == "grantor"
                                else "unresolved"
                            ),
                        }
                    )
                    seen_parties.add((related.casefold(), inverse_role))
            item_id = _text(row.get("TransactionItemId"))
            if item_id:
                source_item_ids.append(item_id)
            guid = _text(row.get("GUID"))
            if guid:
                source_guids.append(guid)

        book, page = _book_page(representative.get("BookPage"))
        legal_descriptions = _unique(
            row.get("DocLegalDescription") for row in instrument_rows
        )
        legal_descriptions = [
            value
            for value in legal_descriptions
            if "no legal data available" not in value.casefold()
        ]
        parcel_ids = _unique(row.get("ParcelNumber") for row in instrument_rows)
        case_numbers = _unique(row.get("CaseNumber") for row in instrument_rows)
        ref = _instrument_ref(instrument_number)
        record = {
            "source_id": SOURCE_ID,
            "record_kind": "recorded_instrument",
            "record_scope": "portal_index_metadata",
            "canonical_ref": ref,
            "evidence_ref": ref,
            "native_document_id": instrument_number,
            "instrument_number": instrument_number,
            "document_number": instrument_number,
            "recording_date": _iso_date(representative.get("RecordDate")),
            "recording_date_raw": _text(representative.get("RecordDate")),
            "document_type": _text(representative.get("DocTypeDescription")),
            "book_type": _text(representative.get("BookType")),
            "book": book,
            "page": page,
            "book_page_raw": _text(representative.get("BookPage")),
            "consideration": _number(representative.get("Consideration")),
            "case_number": case_numbers[0] if len(case_numbers) == 1 else None,
            "case_numbers": case_numbers,
            "parcel_ids": parcel_ids,
            "legal_descriptions": legal_descriptions,
            "parties": parties,
            "related_names": related_names,
            "indexed_direct_name_count": _integer(
                representative.get("NumberOfDirectNames")
            ),
            "indexed_reverse_name_count": _integer(
                representative.get("NumberOfReverseNames")
            ),
            "comments": _unique(row.get("Comments") for row in instrument_rows),
            "source_locator": {
                "transaction_id": _text(representative.get("TransactionId")),
                "transaction_item_ids": _unique(source_item_ids),
                "guids": _unique(source_guids),
                "locator_role": "session_result_row",
            },
            "source_query_observation_count": len(instrument_rows),
            "source_url": SEARCH_URL,
            "jurisdiction": {
                "geoid": COUNTY_GEOID,
                "name": "Broward County, Florida",
                "state_code": STATE_CODE,
            },
            "raw": {
                "grid_rows": [dict(row) for row in instrument_rows],
                "search_kind": payload.get("search_kind"),
            },
        }
        records.append(record)
    return records


def _field_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (_text(value) or "").casefold()).strip("_")


def _field_values(
    fields: Mapping[str, Sequence[str]],
    *aliases: str,
) -> list[str]:
    normalized = {
        _field_key(key): _unique(values)
        for key, values in fields.items()
    }
    for alias in aliases:
        values = normalized.get(_field_key(alias))
        if values:
            return values
    return []


def _detail_fields(
    html: str | None,
    rendered: Mapping[str, Any],
) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}

    rendered_fields = rendered.get("fields")
    if isinstance(rendered_fields, Mapping):
        for key, values in rendered_fields.items():
            if isinstance(values, (list, tuple)):
                fields[str(key)] = _unique(values)
            elif _text(values):
                fields[str(key)] = [_text(values) or ""]

    table_rows = rendered.get("table_rows")
    if isinstance(table_rows, list):
        for row in table_rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            first = row[0]
            key = _text(first[0] if isinstance(first, list) and first else first)
            if not key or len(key) > 80:
                continue
            values: list[Any] = []
            for cell in row[1:]:
                values.extend(cell if isinstance(cell, list) else [cell])
            if _unique(values):
                fields.setdefault(key.rstrip(":"), _unique(values))

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            label = row.find("label")
            if len(cells) < 2:
                continue
            key = _text(
                label.get_text(" ", strip=True)
                if isinstance(label, Tag)
                else cells[0].get_text(" ", strip=True)
            )
            if not key or len(key) > 80:
                continue
            value_cell = cells[-1]
            values = _unique(
                value_cell.get_text("\n", strip=True).splitlines()
            )
            if values:
                fields[key.rstrip(":")] = values
    return fields


def normalize_detail(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Merge one exact grid hit with its public document-detail state."""

    if payload.get("found") is False:
        return None
    search = payload.get("search")
    if not isinstance(search, Mapping):
        raise BrowardSourceChanged("detail payload has no search object")
    grid_records = normalize_grid(search)
    expected = _instrument(payload.get("instrument_number"))
    exact = [
        record
        for record in grid_records
        if record["instrument_number"] == expected
    ]
    if not exact:
        raise BrowardSourceChanged(
            "detail payload has no exact instrument grid record"
        )
    record = exact[0]

    detail = payload.get("detail")
    detail = detail if isinstance(detail, Mapping) else {}
    rendered = detail.get("rendered")
    rendered = rendered if isinstance(rendered, Mapping) else {}
    html = detail.get("details_html")
    html = str(html) if html else None
    fields = _detail_fields(html, rendered)

    instrument_values = _field_values(
        fields,
        "Instrument Number",
        "Instrument #",
        "Instrument",
    )
    if instrument_values:
        detail_instrument = _instrument(instrument_values[0])
        if detail_instrument and detail_instrument != expected:
            raise BrowardSourceChanged(
                "detail instrument does not match the exact search hit"
            )

    grantors = _field_values(
        fields,
        "Grantor",
        "Direct Names",
        "From",
    )
    grantees = _field_values(
        fields,
        "Grantee",
        "Reverse Names",
        "To",
    )
    parties = [
        {
            "name": name,
            "role": "grantor",
            "native_role": "Grantor",
            "index_direction": "direct",
        }
        for name in grantors
    ]
    parties.extend(
        {
            "name": name,
            "role": "grantee",
            "native_role": "Grantee",
            "index_direction": "reverse",
        }
        for name in grantees
    )
    if parties:
        record["parties"] = parties

    doc_type_values = _field_values(
        fields,
        "Document Type",
        "Doc Type",
        "Document Code",
    )
    if doc_type_values:
        doc_type_raw = doc_type_values[0]
        match = re.match(r"^([A-Z][A-Z ]{0,14})\s*[-–]\s*(.+)$", doc_type_raw)
        if match:
            record["document_type_code"] = match.group(1).strip()
            record["document_type"] = match.group(2).strip()
        else:
            record["document_type"] = doc_type_raw

    record_date_values = _field_values(
        fields,
        "Record Date",
        "Recorded",
        "Recording Date",
    )
    if record_date_values:
        record["recording_date_raw"] = record_date_values[0]
        record["recording_date"] = (
            _iso_date(record_date_values[0]) or record["recording_date"]
        )
    page_count_values = _field_values(
        fields,
        "Number of Pages",
        "Page Count",
    )
    if page_count_values:
        record["page_count"] = _integer(page_count_values[0])
    consideration_values = _field_values(
        fields,
        "Consideration",
        "Consideration Amount",
    )
    if consideration_values:
        record["consideration_raw"] = consideration_values[0]
        record["consideration"] = _number(consideration_values[0])
    assumption_values = _field_values(
        fields,
        "Mortgage Assumption Amount",
        "Mortgage Assumption",
    )
    if assumption_values:
        record["mortgage_assumption_raw"] = assumption_values[0]
        record["mortgage_assumption"] = _number(assumption_values[0])
    case_numbers = _field_values(fields, "Case Number", "Case #")
    if case_numbers:
        record["case_numbers"] = case_numbers
        record["case_number"] = case_numbers[0]
    legal_descriptions = _field_values(
        fields,
        "Legal Description",
        "Legal",
        "Doc Legal Description",
    )
    if legal_descriptions:
        record["legal_descriptions"] = legal_descriptions
    parcel_ids = _field_values(
        fields,
        "Parcel Number",
        "Parcel ID",
        "PCN",
        "Property ID",
    )
    parcel_ids = [
        value
        for value in parcel_ids
        if re.fullmatch(r"[0-9A-Za-z-]{8,32}", value)
    ]
    if parcel_ids:
        record["parcel_ids"] = parcel_ids

    anchors = rendered.get("anchors")
    property_links: dict[str, str] = {}
    if isinstance(anchors, list):
        for anchor in anchors:
            if not isinstance(anchor, Mapping):
                continue
            href = _text(anchor.get("href"))
            label = " ".join(
                value
                for value in (
                    _text(anchor.get("text")),
                    _text(anchor.get("title")),
                    href,
                )
                if value
            ).casefold()
            if not href:
                continue
            if "map" in label:
                property_links["property_map"] = href
            elif "bcpa" in label or "property appraiser" in label:
                property_links["property_appraiser"] = href
            elif "tax" in label:
                property_links["tax_collector"] = href
    record["property_links"] = property_links

    image = payload.get("image")
    image = image if isinstance(image, Mapping) else {}
    pdf_url = _text(image.get("pdf_url"))
    record["image_access"] = {
        "status": (
            "available_online"
            if image.get("available")
            else _text(image.get("state")) or "unavailable_online"
        ),
        "page_count": _integer(image.get("page_count"))
        or record.get("page_count"),
        "mime_type": "application/pdf" if image.get("available") else None,
        "retrieval_url": pdf_url,
        "retrieval_url_ephemeral": bool(pdf_url),
        "viewer_url": _text(image.get("viewer_url")),
    }
    record["record_scope"] = "portal_detail_metadata_and_image_state"
    record["source_url"] = _text(detail.get("source_url")) or SEARCH_URL
    record["detail_source_url"] = _text(detail.get("details_url"))
    record["source_fields"] = fields
    record["detail_schema_fingerprint"] = _fingerprint(
        {
            "field_names": sorted(fields),
            "has_retrieval_token": bool(rendered.get("retrieval_token")),
        }
    )
    record["raw"].pop("details_html", None)
    return record


def _decode_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BrowardSourceChanged(f"could not decode bulk file: {path}")


def _pipe_rows(
    path: Path,
    fields: Sequence[str],
    *,
    file_kind: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(_decode_file(path).splitlines(), start=1):
        if not line.strip():
            continue
        values = line.rstrip("\r\n").split("|")
        if values and values[-1] == "":
            values.pop()
        if len(values) != len(fields):
            raise BrowardSourceChanged(
                f"{file_kind} line {line_number} has {len(values)} fields; "
                f"the official layout defines {len(fields)}"
            )
        rows.append(dict(zip(fields, values, strict=True)))
    return rows


def _bulk_status(value: str) -> str:
    return {
        "R": "recorded_not_fully_indexed",
        "I": "indexed",
        "H": "verified",
        "V": "verified_and_released",
    }.get(value, "unknown")


def _confidentiality(value: str) -> tuple[str, str]:
    return {
        "0": ("public", "public"),
        "1": ("confidential", "restricted"),
        "2": ("sealed", "restricted"),
        "3": ("expunged", "restricted"),
        "4": ("void", "unavailable"),
    }.get(value, ("unknown", "unknown"))


def _bulk_record(row: Mapping[str, str], source_file: Path) -> dict[str, Any]:
    instrument_number = _instrument(row["instrument_number"])
    if not instrument_number:
        raise BrowardSourceChanged(
            f"DOC row has invalid instrument number: {row['instrument_number']!r}"
        )
    confidentiality, access_state = _confidentiality(
        row["confidentiality_code"]
    )
    ref = _instrument_ref(instrument_number)
    legal = _text(row["legal_description"])
    parcel = _text(row["parcel_id"])
    return {
        "source_id": SOURCE_ID,
        "record_kind": "recorded_instrument",
        "record_scope": "quality_assured_daily_index_release",
        "canonical_ref": ref,
        "evidence_ref": ref,
        "native_document_id": instrument_number,
        "instrument_number": instrument_number,
        "document_number": instrument_number,
        "recording_date": (
            _iso_date(row["record_date_compact"])
            or _iso_date(row["record_date_display"])
        ),
        "recording_date_raw": row["record_date_display"],
        "record_time_raw": _text(row["record_time"]),
        "document_type_code": _text(row["document_type_code"]),
        "document_type": DOCUMENT_TYPE_DESCRIPTIONS.get(
            row["document_type_code"],
            row["document_type_code"],
        ),
        "consideration": _number(row["consideration"]),
        "book_type": _text(row["book_type"]),
        "book": (
            _text(row["book_number"])
            if row["book_number"] not in {"", "0"}
            else None
        ),
        "page": (
            _text(row["page_number"])
            if row["page_number"] not in {"", "0"}
            else None
        ),
        "legal_descriptions": (
            [{"description": legal, "parcel_id": parcel, "source_file": "DOC"}]
            if legal
            else []
        ),
        "parcel_ids": [parcel] if parcel else [],
        "documentary_tax": _number(row["documentary_tax"]),
        "intangible_tax": _number(row["intangible_tax"]),
        "indexed_name_count": _integer(row["number_of_names"]),
        "confidentiality": confidentiality,
        "confidentiality_code": row["confidentiality_code"],
        "access_state": access_state,
        "index_status": _bulk_status(row["status_code"]),
        "index_status_code": row["status_code"],
        "rerecord_flag": _text(row["rerecord_flag"]),
        "electronic_source": (
            True
            if row["source_code"] == "E"
            else False
            if row["source_code"]
            else None
        ),
        "case_number": _text(row["case_number"]),
        "case_numbers": (
            [_text(row["case_number"])]
            if _text(row["case_number"])
            else []
        ),
        "parties": [],
        "linked_instruments": [],
        "source_url": BULK_INFORMATION_URL,
        "source_artifact": str(source_file),
        "bulk_release_date": _release_date_from_name(source_file.name),
        "jurisdiction": {
            "geoid": COUNTY_GEOID,
            "name": "Broward County, Florida",
            "state_code": STATE_CODE,
        },
        "raw": {"document": dict(row)},
    }


def _release_date_from_name(file_name: str) -> str | None:
    match = re.search(
        r"(?<!\d)(\d{2})-(\d{2})-(\d{4})(?:doc|nme|lnk|lgl|img)",
        file_name,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _iso_date(f"{match.group(1)}/{match.group(2)}/{match.group(3)}")


def _bulk_party(row: Mapping[str, str]) -> dict[str, Any]:
    role, direction = _party_role(row["party_type"])
    sequence = _integer(row["name_sequence"])
    return {
        "native_party_id": (
            f"BROWARD-OR:{row['instrument_number']}:party:"
            f"{row['party_type']}:{row['name_sequence']}"
        ),
        "name": _text(row["party_name"]),
        "role": role,
        "native_role": row["party_type"],
        "index_direction": direction,
        "sequence": sequence,
        "raw": dict(row),
    }


def _bulk_link(row: Mapping[str, str], sequence: int) -> dict[str, Any]:
    prior_instrument = _instrument(row["prior_instrument_number"])
    return {
        "native_link_id": (
            f"BROWARD-OR:{row['instrument_number']}:link:{sequence}"
        ),
        "relationship": "source_cross_reference",
        "prior_instrument_number": prior_instrument,
        "prior_canonical_ref": (
            _instrument_ref(prior_instrument) if prior_instrument else None
        ),
        "prior_book": _text(row["prior_book_number"]),
        "prior_page": _text(row["prior_page_number"]),
        "prior_book_type": _text(row["prior_book_type"]),
        "prior_document_type_code": _text(
            row["prior_document_type_code"]
        ),
        "keypunch": _text(row["keypunch"]),
        "keyed_reference_resolved": bool(prior_instrument),
        "raw": dict(row),
    }


def _range_values(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    values = [
        _instrument(line)
        for line in _decode_file(path).splitlines()
        if _text(line)
    ]
    if len(values) != 2 or any(value is None for value in values):
        raise BrowardSourceChanged(
            "RNG file must contain beginning and ending instrument numbers"
        )
    return {
        "begin_instrument": values[0],
        "end_instrument": values[1],
        "source_file": str(path),
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_image_zip(path: Path) -> dict[str, Any]:
    """Inventory official TIFF members without extracting the daily ZIP."""

    images: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unrecognized_members: list[str] = []
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as error:
        raise BrowardSourceChanged(
            f"could not open official image ZIP {path}: {error}"
        ) from error
    with archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = PurePosixPath(member.filename)
            match = re.fullmatch(
                r"(?P<instrument>\d+)\.(?P<page>\d+)\.tiff?",
                member_path.name,
                flags=re.IGNORECASE,
            )
            if match is None:
                unrecognized_members.append(member.filename)
                continue
            instrument_number = match.group("instrument")
            page_number = int(match.group("page"))
            images[instrument_number].append(
                {
                    "native_artifact_id": (
                        f"BROWARD-OR:{instrument_number}:page:{page_number}"
                    ),
                    "instrument_number": instrument_number,
                    "page_number": page_number,
                    "member_name": member.filename,
                    "mime_type": "image/tiff",
                    "uncompressed_byte_count": member.file_size,
                    "compressed_byte_count": member.compress_size,
                    "crc32": f"{member.CRC:08x}",
                }
            )
    for members in images.values():
        members.sort(key=lambda item: item["page_number"])
    return {
        "source_file": str(path),
        "sha256": _file_sha256(path),
        "release_date": _release_date_from_name(path.name),
        "images": dict(images),
        "unrecognized_members": unrecognized_members,
    }


def parse_bulk_release(
    document_path: Path,
    *,
    names_path: Path | None = None,
    links_path: Path | None = None,
    legals_path: Path | None = None,
    range_path: Path | None = None,
    images_path: Path | None = None,
) -> dict[str, Any]:
    """Join one official daily DOC/NME/LNK/LGL release by instrument."""

    documents = _pipe_rows(document_path, DOC_FIELDS, file_kind="DOC")
    records = {
        record["instrument_number"]: record
        for record in (
            _bulk_record(row, document_path)
            for row in documents
        )
    }
    orphan_rows: dict[str, list[dict[str, str]]] = defaultdict(list)

    if names_path is not None:
        for row in _pipe_rows(names_path, NAME_FIELDS, file_kind="NME"):
            instrument_number = _instrument(row["instrument_number"])
            if instrument_number not in records:
                orphan_rows["NME"].append(row)
                continue
            records[instrument_number]["parties"].append(_bulk_party(row))
            records[instrument_number]["raw"].setdefault("names", []).append(row)

    if links_path is not None:
        link_counts: dict[str, int] = defaultdict(int)
        for row in _pipe_rows(links_path, LINK_FIELDS, file_kind="LNK"):
            instrument_number = _instrument(row["instrument_number"])
            if instrument_number not in records:
                orphan_rows["LNK"].append(row)
                continue
            link_counts[instrument_number] += 1
            link = _bulk_link(row, link_counts[instrument_number])
            records[instrument_number]["linked_instruments"].append(link)
            records[instrument_number]["raw"].setdefault("links", []).append(row)

    if legals_path is not None:
        for row in _pipe_rows(legals_path, LEGAL_FIELDS, file_kind="LGL"):
            instrument_number = _instrument(row["instrument_number"])
            if instrument_number not in records:
                orphan_rows["LGL"].append(row)
                continue
            legal = _text(row["legal_description"])
            parcel = _text(row["parcel_id"])
            observation = {
                "description": legal,
                "parcel_id": parcel,
                "source_file": "LGL",
            }
            existing = records[instrument_number]["legal_descriptions"]
            if not any(
                item["description"] == legal and item["parcel_id"] == parcel
                for item in existing
            ):
                existing.append(observation)
            if parcel and parcel not in records[instrument_number]["parcel_ids"]:
                records[instrument_number]["parcel_ids"].append(parcel)
            records[instrument_number]["raw"].setdefault("legals", []).append(row)

    image_manifest = parse_image_zip(images_path) if images_path else None
    if image_manifest is not None:
        image_rows = image_manifest["images"]
        for instrument_number, record in records.items():
            members = image_rows.get(instrument_number, [])
            record["image_access"] = {
                "status": (
                    "available_in_official_daily_zip"
                    if members
                    else "not_present_in_supplied_daily_zip"
                ),
                "media_type": "image/tiff" if members else None,
                "page_count": len(members),
                "container_path": str(images_path),
                "container_sha256": image_manifest["sha256"],
                "members": members,
            }

    files = {
        "document": str(document_path),
        "names": str(names_path) if names_path else None,
        "links": str(links_path) if links_path else None,
        "legals": str(legals_path) if legals_path else None,
        "range": str(range_path) if range_path else None,
        "images": str(images_path) if images_path else None,
    }
    return {
        "records": list(records.values()),
        "instrument_range": _range_values(range_path),
        "source_files": files,
        "orphan_rows": dict(orphan_rows),
        "image_manifest": (
            {
                key: value
                for key, value in image_manifest.items()
                if key != "images"
            }
            if image_manifest
            else None
        ),
        "schema_fingerprint": _fingerprint(
            {
                "DOC": DOC_FIELDS,
                "NME": NAME_FIELDS,
                "LNK": LINK_FIELDS,
                "LGL": LEGAL_FIELDS,
            }
        ),
    }


def source_routes() -> dict[str, Any]:
    """Describe source roles, exact coverage statements, and join routes."""

    return {
        "source_id": SOURCE_ID,
        "record_kind": "source_access_routes",
        "native_document_id": "verified-routes-2026-07-30",
        "as_observed": "2026-07-30",
        "official_record_portal": {
            "url": SEARCH_URL,
            "search_selectors": list(PORTAL_SEARCH_PATHS),
            "coverage_statements": {
                "plats_and_maps": "all record dates",
                "fully_searchable_other_records": (
                    "from 1977-07-07 13:47 forward"
                ),
                "limited_locator_search": (
                    "1972-03-09 11:28 through 1977-07-07 13:46"
                ),
                "not_available_on_portal": "before 1972-03-09 11:28",
            },
            "limited_period_selectors": [
                "instrument_number",
                "book_type",
                "book_page_range",
                "record_date",
            ],
            "instrument_search_behavior": (
                "returns a forward 100-row window; adapter exact-filters"
            ),
            "public_image_route": "session-scoped all-pages PDF",
            "certified_copy_route": ONLINE_ORDERS_URL,
            "search_boundaries": {
                "property_address": (
                    "use the Property Appraiser or Florida DOR roll"
                ),
                "legal_description": (
                    "returned as index metadata but not an address-style "
                    "recorder search selector"
                ),
            },
        },
        "official_daily_release": {
            "url": BULK_INFORMATION_URL,
            "layout_url": BULK_LAYOUT_URL,
            "document_types_url": DOCUMENT_TYPES_URL,
            "rolling_availability": "10 continuous days",
            "quality_state": "quality-assured fully verified released business day",
            "files": {
                "DOC": "one record per instrument",
                "NME": "one record per indexed party",
                "LNK": "one record per source cross-reference",
                "LGL": "one record per legal-description and parcel pair",
                "RNG": "begin and end instrument numbers",
                "IMG": "ZIP of public single-page TIFF images",
            },
            "join_key": "instrument_number",
            "image_name": "instrument_number.page_sequence.tif",
        },
        "complementary_routes": [
            {
                "kind": "broward_property_appraiser",
                "url": PROPERTY_APPRAISER_URL,
                "relationship": "parcel_owner_sales_value_and_map_context",
                "join_keys": ["parcel_id", "owner_name", "property_address"],
            },
            {
                "kind": "broward_property_map",
                "url": PROPERTY_MAP_URL,
                "relationship": "parcel_geometry_and_location_context",
                "join_keys": ["parcel_id"],
            },
            {
                "kind": "florida_dor_property_bulk",
                "source_id": "us-fl-dor-property-roll",
                "tool": "tools/query_fl_dor_property.py",
                "url": FL_DOR_URL,
                "relationship": "state_bulk_roll_sales_and_geometry_context",
                "join_keys": ["parcel_id", "owner_name", "sale_date"],
            },
            {
                "kind": "broward_tax_collector",
                "url": TAX_COLLECTOR_URL,
                "relationship": "property_tax_and_delinquency_context",
                "join_keys": ["parcel_id", "property_address"],
            },
            {
                "kind": "broward_clerk_case_search",
                "url": COURT_SEARCH_URL,
                "relationship": "underlying_local_case_and_docket_context",
                "join_keys": ["case_number", "party_name", "filing_date"],
                "observed_result_ceiling": 200,
            },
            {
                "kind": "broward_tax_deed",
                "url": TAX_DEED_INFORMATION_URL,
                "current_auction_url": TAX_DEED_AUCTION_URL,
                "relationship": (
                    "tax_deed_application_auction_file_and_title_context"
                ),
                "join_keys": [
                    "parcel_id",
                    "tax_deed_number",
                    "assessed_owner",
                    "legal_description",
                ],
            },
            {
                "kind": "online_certified_copy_order",
                "url": ONLINE_ORDERS_URL,
                "relationship": (
                    "instrument_or_book_page_copy_and_certification_order"
                ),
                "join_keys": ["instrument_number", "book_page"],
            },
            {
                "kind": "search_copy_and_archive_service",
                "url": SEARCH_COPY_URL,
                "relationship": (
                    "older_record_copy_certification_and_written_search"
                ),
                "join_keys": [
                    "instrument_number",
                    "book_page",
                    "party_name",
                    "recording_period",
                ],
            },
        ],
    }


def _parse_helper_error(stderr: str) -> BrowardBrowserError:
    lines = [line for line in stderr.splitlines() if line.strip()]
    if lines:
        try:
            payload = json.loads(lines[-1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, Mapping):
            error = payload.get("error")
            if isinstance(error, Mapping):
                return BrowardBrowserError(
                    str(error.get("message") or "browser helper failed"),
                    error_type=str(error.get("type") or "Error"),
                )
    return BrowardBrowserError(
        stderr.strip() or "browser helper failed without an error payload"
    )


def run_browser_helper(
    arguments: Sequence[str],
    timeout: float,
) -> Mapping[str, Any]:
    """Run the local browser helper and decode its JSON response."""

    node = shutil.which("node")
    if node is None:
        raise BrowardBrowserError(
            "Node.js is required to run the Broward browser helper",
            error_type="RuntimeDependencyError",
        )
    try:
        process = subprocess.run(
            [node, str(HELPER_PATH), *map(str, arguments)],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise BrowardBrowserError(
            f"Broward browser helper exceeded {timeout:g} seconds",
            error_type="TimeoutError",
        ) from error
    if process.returncode:
        raise _parse_helper_error(process.stderr)
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise BrowardBrowserError(
            "Broward browser helper returned invalid JSON",
            error_type="SourcePayloadError",
        ) from error
    if not isinstance(payload, Mapping):
        raise BrowardBrowserError(
            "Broward browser helper returned a non-object payload",
            error_type="SourcePayloadError",
        )
    return payload


def _native_date(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _text(value)
    if not normalized:
        return None
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(normalized, date_format).strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise ValueError("dates must use YYYY-MM-DD or MM/DD/YYYY")


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    requested_limit: int | None = getattr(args, "limit", None)
    if args.command == "name":
        parameters = {
            "name": args.name,
            "direction": args.direction,
            "from_date": args.from_date,
            "to_date": args.to_date,
            "max_pages": args.max_pages,
        }
    elif args.command == "parcel":
        parameters = {
            "parcel_id": args.parcel_id,
            "from_date": args.from_date,
            "to_date": args.to_date,
            "max_pages": args.max_pages,
            "exact_filter": True,
        }
    elif args.command in {"instrument", "detail", "download"}:
        parameters = {"instrument_number": args.instrument_number}
        if args.command == "download":
            parameters.update(
                {
                    "destination": str(args.destination),
                    "overwrite": args.overwrite,
                }
            )
    elif args.command == "bulk":
        parameters = {
            "document": str(args.document),
            "names": str(args.names) if args.names else None,
            "links": str(args.links) if args.links else None,
            "legals": str(args.legals) if args.legals else None,
            "range_file": (
                str(args.range_file) if args.range_file else None
            ),
            "images": str(args.images) if args.images else None,
        }
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
        ),
    )


def _browser_failure(
    query: PublicRecordsQuery,
    error: BrowardBrowserError,
) -> PublicRecordsResult:
    if error.error_type == "RecordNotFoundError":
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )
    if error.error_type == "DocumentUnavailableError":
        status = ResultStatus.UNAVAILABLE
        category = "document_access"
    elif error.error_type == "SourceChangedError":
        status = ResultStatus.SOURCE_CHANGED
        category = "source_schema"
    elif error.error_type == "RuntimeDependencyError":
        status = ResultStatus.UNAVAILABLE
        category = "runtime"
    else:
        status = ResultStatus.UNAVAILABLE
        category = "browser"
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=re.sub(
                    r"(?<!^)(?=[A-Z])",
                    "_",
                    error.error_type,
                ).casefold(),
                message=str(error),
                category=category,
                retryable=error.error_type in {"TimeoutError", "Error"},
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _grid_result(
    query: PublicRecordsQuery,
    payload: Mapping[str, Any],
    *,
    limit: int | None,
    exact_parcel_id: str | None = None,
) -> PublicRecordsResult:
    records = normalize_grid(payload)
    if exact_parcel_id is not None:
        expected = _parcel_key(exact_parcel_id)
        records = [
            record
            for record in records
            if expected
            and any(
                _parcel_key(parcel_id) == expected
                for parcel_id in record.get("parcel_ids", [])
            )
        ]
    returned = records[:limit] if limit else records
    source_total = int(payload["total"])
    truncated = bool(payload.get("truncated"))
    if truncated:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="source_pages_remaining",
                    message=(
                        f"Retrieved {len(payload.get('data', []))} of "
                        f"{source_total} source rows"
                    ),
                    category="pagination",
                    retryable=True,
                    details={
                        "source_total_rows": source_total,
                        "pages_retrieved": payload.get("pages_retrieved"),
                    },
                )
            ],
            records=returned,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        returned,
        warnings=SOURCE_WARNINGS,
    )


def _download_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    instrument_number = _instrument(payload.get("instrument_number"))
    if not instrument_number:
        raise BrowardSourceChanged(
            "download receipt has no instrument number"
        )
    sha256 = _text(payload.get("sha256"))
    artifact_ref = (
        f"BROWARD-OR-PDF:{sha256}"
        if sha256
        else f"BROWARD-OR:{instrument_number}:PDF"
    )
    return {
        "source_id": SOURCE_ID,
        "record_kind": "recorded_document_artifact",
        "canonical_ref": _instrument_ref(instrument_number),
        "evidence_ref": artifact_ref,
        "native_document_id": instrument_number,
        "instrument_number": instrument_number,
        "storage_path": _text(payload.get("destination")),
        "mime_type": _text(payload.get("mime_type")) or "application/pdf",
        "byte_count": _integer(payload.get("byte_count")),
        "sha256": sha256,
        "page_count": _integer(payload.get("page_count")),
        "source_url": _text(payload.get("source_url")) or SEARCH_URL,
        "retrieval_url_ephemeral": True,
        "certification_status": "public_online_copy",
    }


def _execute(
    args: argparse.Namespace,
    query: PublicRecordsQuery,
    runner: HelperRunner,
) -> PublicRecordsResult:
    if args.command == "routes":
        return PublicRecordsResult.success(
            query,
            [source_routes()],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "runtime-check":
        payload = runner(["runtime-check"], args.timeout)
        return PublicRecordsResult.success(
            query,
            [
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "runtime_check",
                    **dict(payload),
                }
            ],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "probe":
        payload = runner(["probe"], args.timeout)
        return PublicRecordsResult.success(
            query,
            [
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_probe",
                    "schema_fingerprint": _fingerprint(payload),
                    **dict(payload),
                }
            ],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "name":
        helper_args = [
            "name",
            args.name,
            "--direction",
            args.direction,
            "--max-pages",
            str(args.max_pages),
        ]
        if args.from_date:
            helper_args.extend(["--from", _native_date(args.from_date) or ""])
        if args.to_date:
            helper_args.extend(["--to", _native_date(args.to_date) or ""])
        return _grid_result(
            query,
            runner(helper_args, args.timeout),
            limit=args.limit,
        )
    if args.command == "parcel":
        helper_args = [
            "parcel",
            args.parcel_id,
            "--max-pages",
            str(args.max_pages),
        ]
        if args.from_date:
            helper_args.extend(["--from", _native_date(args.from_date) or ""])
        if args.to_date:
            helper_args.extend(["--to", _native_date(args.to_date) or ""])
        return _grid_result(
            query,
            runner(helper_args, args.timeout),
            limit=args.limit,
            exact_parcel_id=args.parcel_id,
        )
    if args.command == "instrument":
        payload = runner(
            ["instrument", args.instrument_number],
            args.timeout,
        )
        return _grid_result(query, payload, limit=1)
    if args.command == "detail":
        payload = runner(
            ["detail", args.instrument_number],
            args.timeout,
        )
        record = normalize_detail(payload)
        return PublicRecordsResult.success(
            query,
            [record] if record else [],
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "download":
        helper_args = [
            "download",
            args.instrument_number,
            str(args.destination),
        ]
        if args.overwrite:
            helper_args.append("--overwrite")
        payload = runner(helper_args, args.timeout)
        record = _download_record(payload)
        artifact = _text(payload.get("destination"))
        return PublicRecordsResult.success(
            query,
            [record],
            raw_artifact_refs=[artifact] if artifact else (),
            warnings=SOURCE_WARNINGS,
        )
    if args.command == "bulk":
        payload = parse_bulk_release(
            args.document,
            names_path=args.names,
            links_path=args.links,
            legals_path=args.legals,
            range_path=args.range_file,
            images_path=args.images,
        )
        records = payload["records"]
        if args.limit:
            records = records[: args.limit]
        orphan_rows = payload["orphan_rows"]
        raw_refs = [
            path
            for path in payload["source_files"].values()
            if path is not None
        ]
        if orphan_rows:
            return PublicRecordsResult.failure(
                query,
                ResultStatus.PARTIAL,
                [
                    PublicRecordsError(
                        code="bulk_join_orphans",
                        message=(
                            "Some companion rows referenced instruments absent "
                            "from the supplied DOC file"
                        ),
                        category="bulk_join",
                        retryable=False,
                        details={
                            kind: len(rows)
                            for kind, rows in orphan_rows.items()
                        },
                    )
                ],
                records=records,
                raw_artifact_refs=raw_refs,
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.success(
            query,
            records,
            raw_artifact_refs=raw_refs,
            warnings=SOURCE_WARNINGS,
        )
    raise ValueError(f"unsupported command: {args.command}")


def execute(
    args: argparse.Namespace,
    *,
    helper_runner: HelperRunner | None = None,
) -> PublicRecordsResult:
    """Execute one Broward portal or bulk-file operation."""

    query = build_query(args)
    runner = helper_runner or run_browser_helper
    try:
        result = _execute(args, query, runner)
    except BrowardBrowserError as error:
        result = _browser_failure(query, error)
    except (BrowardSourceChanged, OSError, TypeError, ValueError) as error:
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
    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Maximum browser-helper runtime in seconds",
    )
    add_output_args(parser)


def _add_search_bounds(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum source grid pages to retrieve",
    )
    parser.add_argument("--limit", type=int)
    _add_common(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Broward County Official Records"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("routes", "Show verified source roles and complementary joins"),
        ("runtime-check", "Check Node, Playwright, and browser availability"),
        ("probe", "Validate portal coverage and search routes"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        _add_common(command_parser)

    name = sub.add_parser("name", help="Search the party-name index")
    name.add_argument("name")
    name.add_argument(
        "--direction",
        choices=("all", "grantor", "grantee"),
        default="all",
    )
    name.add_argument("--from-date")
    name.add_argument("--to-date")
    _add_search_bounds(name)

    parcel = sub.add_parser(
        "parcel",
        help="Search the recorder index for one exact parcel identifier",
    )
    parcel.add_argument("parcel_id")
    parcel.add_argument("--from-date")
    parcel.add_argument("--to-date")
    _add_search_bounds(parcel)

    instrument = sub.add_parser(
        "instrument",
        help="Find one exact instrument in the source's forward window",
    )
    instrument.add_argument("instrument_number")
    _add_common(instrument)

    detail = sub.add_parser(
        "detail",
        help="Retrieve exact instrument detail and public image state",
    )
    detail.add_argument("instrument_number")
    _add_common(detail)

    download = sub.add_parser(
        "download",
        help="Download the public all-pages PDF for one exact instrument",
    )
    download.add_argument("instrument_number")
    download.add_argument("destination", type=Path)
    download.add_argument("--overwrite", action="store_true")
    _add_common(download)

    bulk = sub.add_parser(
        "bulk",
        help="Join a downloaded official daily DOC/NME/LNK/LGL release",
    )
    bulk.add_argument("document", type=Path)
    bulk.add_argument("--names", type=Path)
    bulk.add_argument("--links", type=Path)
    bulk.add_argument("--legals", type=Path)
    bulk.add_argument("--range-file", type=Path)
    bulk.add_argument(
        "--images",
        type=Path,
        help="Official daily img.ZIP to inventory and join by instrument",
    )
    bulk.add_argument("--limit", type=int)
    _add_common(bulk)
    return parser


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Broward Official Records {args.command} "
            f"({result.status.value})"
        ),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"{result.status.value}: {len(result.records)} record(s)")
    for error in result.errors:
        print(f"{error.code}: {error.message}", file=sys.stderr)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if getattr(args, "max_pages", 1) <= 0:
        parser.error("--max-pages must be positive")
    if getattr(args, "limit", None) is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if hasattr(args, "instrument_number") and not re.fullmatch(
        r"\d+",
        args.instrument_number,
    ):
        parser.error("instrument_number must contain digits only")
    result = execute(args)
    _emit(result, args)


if __name__ == "__main__":
    main()
