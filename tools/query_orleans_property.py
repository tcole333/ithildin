#!/usr/bin/env python3
"""Query official Orleans Parish property and assessment records.

The City of New Orleans publishes two complementary services:

- ``TaxParcelPublishing`` is the full current assessor/account layer.
- ``PropertyViewerCompositeLocator`` resolves address, owner, and tax-bill
  searches to parcel locations without scanning unindexed layer fields.

Usage:
    uv run python tools/query_orleans_property.py owner "CITY OF NEW ORLEANS"
    uv run python tools/query_orleans_property.py address "1771 NASHVILLE AVE"
    uv run python tools/query_orleans_property.py account 615199817
    uv run python tools/query_orleans_property.py parcel 41050755 --geometry
    uv run python tools/query_orleans_property.py search "PALMER ROSEMARY C"
    uv run python tools/query_orleans_property.py probe --output /tmp/orleans.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
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
        ArcGISRESTClient,
        PaginatedFetch,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
        system_trust_session,
    )
    from tools.public_records_store import canonical_property_ref
    from tools.seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_catalog import (
        DEFAULT_DB_PATH as DEFAULT_CATALOG_DB_PATH,
        AcquisitionUnavailableError,
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
        ArcGISRESTClient,
        PaginatedFetch,
        PublicRecordsHTTPError,
        SourceResponseError,
        SourceSchemaError,
        _BaseJSONClient,
        failure_result,
        system_trust_session,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-la-orleans-property-viewer"
COUNTY_GEOID = "22071"
VIEWER_URL = "https://property.nola.gov/"
MAP_SERVICE_URL = (
    "https://gis.nola.gov/arcgis/rest/services/"
    "LGIM/TaxParcelQuery/MapServer"
)
LAYER_URL = f"{MAP_SERVICE_URL}/0"
VIEWER_LAYER_URL = (
    "https://gis.nola.gov/arcgis/rest/services/"
    "apps/property3/MapServer/15"
)
LOCATOR_URL = (
    "https://gis.nola.gov/arcgis/rest/services/"
    "Locators/PropertyViewerCompositeLocator/GeocodeServer"
)
ASSESSOR_RECORD_URL = (
    "https://beacon.schneidercorp.com/Application.aspx"
    "?AppID=979&LayerID=19792&PageTypeID=4&PageID=8663"
    "&Q=1886938444&KeyValue="
)
ORDER_BY = "OBJECTID ASC"
SOURCE_MAX_PAGE_SIZE = 1_000
LOCATOR_MAX_CANDIDATES = 1_000
NATIVE_SPATIAL_REFERENCE = 102100
OUTPUT_SPATIAL_REFERENCE = 4326
PROBE_GEOPIN = "41026779"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="City of New Orleans Property Viewer and Tax Parcel Publishing",
    source_role="current_assessment_account_and_parcel_gis",
    base_url=LAYER_URL,
    dataset_id="LGIM/TaxParcelQuery/MapServer/0",
    metadata={
        "authority": "Orleans Parish Assessor",
        "operator": "City of New Orleans",
        "coverage": "Orleans Parish, Louisiana",
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
        "published_update_cadence": "weekly",
    },
)

SOURCE_WARNINGS = (
    "Owner names are current assessor-account observations, not a title chain.",
    "Parcel geometry is public GIS mapping and is not a surveyed legal boundary.",
    "The source publishes a current weekly snapshot; historical rolls and transfer records are separate sources.",
)

_LOCATOR_CURSOR_PREFIX = "orleans:locator:"
_OWNER_CURSOR_PREFIX = "orleans:owner:"


class OrleansPropertyLocatorClient(_BaseJSONClient):
    """Client for the composite locator used by the official Property Viewer."""

    def candidates(
        self,
        query: str,
        *,
        max_locations: int,
    ) -> tuple[Mapping[str, Any], ...]:
        payload = self._request_json(
            f"{LOCATOR_URL}/findAddressCandidates",
            params={
                "SingleLine": _query_text(query),
                "outSR": NATIVE_SPATIAL_REFERENCE,
                "outFields": "Address,User_fld,Loc_name,Match_addr",
                "maxLocations": max_locations,
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "Orleans locator response must be a JSON object",
                url=LOCATOR_URL,
                details={"response_type": type(payload).__name__},
            )
        if "error" in payload:
            raise SourceResponseError(
                "Orleans locator returned an error response",
                url=LOCATOR_URL,
                details={"response": payload["error"]},
            )
        candidates = payload.get("candidates")
        if not isinstance(candidates, list) or any(
            not isinstance(candidate, Mapping) for candidate in candidates
        ):
            raise SourceSchemaError(
                "Orleans locator response lacks a candidates array",
                url=LOCATOR_URL,
            )
        return tuple(candidates)


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


def _reviewed_limits(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> tuple[int, float]:
    limits = access_contract.get("limits") or {}
    page_size = min(
        int(getattr(args, "page_size", SOURCE_MAX_PAGE_SIZE)),
        int(limits.get("maximum_page_size") or SOURCE_MAX_PAGE_SIZE),
        SOURCE_MAX_PAGE_SIZE,
    )
    interval = max(
        float(getattr(args, "minimum_interval", 0.25)),
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return page_size, interval


def _new_layer_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> ArcGISRESTClient:
    page_size, interval = _reviewed_limits(args, access_contract)
    return ArcGISRESTClient(
        LAYER_URL,
        page_size=page_size,
        session=system_trust_session(),
        timeout=float(getattr(args, "timeout", 30.0)),
        minimum_interval=interval,
    )


def _new_locator_client(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> OrleansPropertyLocatorClient:
    _page_size, interval = _reviewed_limits(args, access_contract)
    return OrleansPropertyLocatorClient(
        session=system_trust_session(),
        timeout=float(getattr(args, "timeout", 30.0)),
        minimum_interval=interval,
    )


def _query_text(value: Any) -> str:
    cleaned = " ".join(str(value or "").replace("\x00", "").split()).strip()
    if not cleaned:
        raise ValueError("query value must not be blank")
    return cleaned


def _sql_literal(value: Any) -> str:
    return _query_text(value).replace("'", "''")


def _like_prefix(value: Any) -> str:
    escaped = _sql_literal(value).upper()
    escaped = escaped.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped


def _owner_like(field: str, selector: str, *, negate: bool = False) -> str:
    raw = _sql_literal(selector).upper()
    needs_escape = any(character in raw for character in ("\\", "%", "_"))
    value = _like_prefix(raw) if needs_escape else raw
    operator = "NOT LIKE" if negate else "LIKE"
    escape = " ESCAPE '\\'" if needs_escape else ""
    return f"{field} {operator} '{value}%'{escape}"


def _owner_where(selector: str, phase: int) -> str:
    if phase == 0:
        return _owner_like("OWNERNME1", selector)
    if phase == 1:
        owner_two = _owner_like("OWNERNME2", selector)
        owner_one_exclusion = _owner_like(
            "OWNERNME1",
            selector,
            negate=True,
        )
        return (
            f"({owner_two} AND "
            f"(OWNERNME1 IS NULL OR {owner_one_exclusion}))"
        )
    raise ValueError("Orleans owner cursor phase must be 0 or 1")


def _parcel_selector(
    value: Any,
    id_type: str = "auto",
) -> tuple[str, str]:
    cleaned = _query_text(value)
    normalized_type = str(id_type or "auto").strip().lower()
    if normalized_type not in {"auto", "geopin", "parid"}:
        raise ValueError("Orleans parcel id type must be auto, geopin, or parid")
    if normalized_type == "geopin":
        return "PARCELID", cleaned
    if normalized_type == "parid":
        return "PARID", cleaned
    if re.fullmatch(r"\d{8}", cleaned):
        return "PARCELID", cleaned
    return "PARID", cleaned


def _where(
    operation: str,
    selector: str | None,
    *,
    id_type: str = "auto",
) -> str:
    if operation == "probe":
        return f"PARCELID='{PROBE_GEOPIN}'"
    if operation == "owner":
        return _owner_where(_query_text(selector), 0)
    if operation == "parcel":
        field, value = _parcel_selector(selector, id_type)
        return f"{field}='{_sql_literal(value)}'"
    raise ValueError(f"unsupported direct Orleans operation: {operation}")


def _locator_cursor(cursor: str | None) -> tuple[int, int, set[str]]:
    if cursor is None:
        return 0, 0, set()
    if not cursor.startswith(_LOCATOR_CURSOR_PREFIX):
        raise ValueError("invalid Orleans locator cursor")
    suffix = cursor[len(_LOCATOR_CURSOR_PREFIX) :]
    if suffix.startswith("v2:"):
        encoded = suffix.removeprefix("v2:")
        try:
            padding = "=" * (-len(encoded) % 4)
            decoded = base64.b64decode(
                encoded + padding,
                altchars=b"-_",
                validate=True,
            )
            payload = json.loads(decoded)
        except (
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            raise ValueError("invalid Orleans locator cursor") from error
        if not isinstance(payload, Mapping) or payload.get("v") != 2:
            raise ValueError("invalid Orleans locator cursor")
        candidate_offset = payload.get("candidate")
        feature_offset = payload.get("feature")
        seen = payload.get("seen")
        if (
            isinstance(candidate_offset, bool)
            or not isinstance(candidate_offset, int)
            or candidate_offset < 0
            or isinstance(feature_offset, bool)
            or not isinstance(feature_offset, int)
            or feature_offset < 0
            or not isinstance(seen, list)
            or any(not isinstance(value, str) for value in seen)
        ):
            raise ValueError("invalid Orleans locator cursor")
        return candidate_offset, feature_offset, set(seen)
    parts = suffix.split(":")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ValueError("invalid Orleans locator cursor")
    candidate_offset, feature_offset = (int(part) for part in parts)
    return candidate_offset, feature_offset, set()


def _make_locator_cursor(
    candidate_offset: int,
    feature_offset: int,
    seen_features: set[str],
) -> str:
    payload = canonical_json(
        {
            "candidate": candidate_offset,
            "feature": feature_offset,
            "seen": sorted(seen_features),
            "v": 2,
        }
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{_LOCATOR_CURSOR_PREFIX}v2:{encoded}"


def _owner_cursor(cursor: str | None) -> tuple[int, int]:
    if cursor is None:
        return 0, 0
    if not cursor.startswith(_OWNER_CURSOR_PREFIX):
        raise ValueError("invalid Orleans owner cursor")
    parts = cursor[len(_OWNER_CURSOR_PREFIX) :].split(":")
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ValueError("invalid Orleans owner cursor")
    phase, offset = (int(part) for part in parts)
    if phase not in {0, 1}:
        raise ValueError("invalid Orleans owner cursor")
    return phase, offset


def _make_owner_cursor(phase: int, offset: int) -> str:
    return f"{_OWNER_CURSOR_PREFIX}{phase}:{offset}"


def _arcgis_offset(cursor: str) -> int:
    prefix = "arcgis:offset:"
    if not cursor.startswith(prefix) or not cursor[len(prefix) :].isdigit():
        raise ValueError("invalid ArcGIS cursor returned by Orleans source")
    return int(cursor[len(prefix) :])


def _effective_limit(args: argparse.Namespace) -> tuple[int, bool, list[str]]:
    requested = int(getattr(args, "limit", 50))
    if requested <= 0:
        raise ValueError("limit must be positive")
    max_records = getattr(args, "max_records", None)
    if max_records is None:
        return requested, False, []
    max_records = int(max_records)
    if max_records <= 0:
        raise ValueError("max_records must be positive when supplied")
    if requested <= max_records:
        return requested, False, []
    return (
        max_records,
        True,
        [f"Requested {requested} records but the caller-selected ceiling is {max_records}."],
    )


def _text(value: Any) -> str | None:
    cleaned = str(value or "").replace("\x00", "").strip()
    return cleaned or None


def _number(value: Any) -> int | float | str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    cleaned = str(value).strip().replace(",", "").replace("$", "")
    try:
        number = float(cleaned)
    except ValueError:
        return str(value).strip()
    return int(number) if number.is_integer() else number


def _epoch_millis(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid Orleans LASTUPDATE value: {value!r}") from error
    return (
        datetime.fromtimestamp(milliseconds / 1_000, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _postal_code(zip5: Any, zip4: Any) -> str | None:
    first = _text(zip5)
    plus4 = _text(zip4)
    if first and plus4 and plus4 != "0000":
        return f"{first}-{plus4}"
    return first


def _record_key(attributes: Mapping[str, Any]) -> str:
    """Return the most stable published identity for a current account row."""

    tax_bill_id = _text(attributes.get("TAXBILLID"))
    if tax_bill_id:
        return f"TAXBILLID:{tax_bill_id}"
    parid = _text(attributes.get("PARID"))
    if parid:
        return f"PARID:{parid}"
    parcel_id = _text(attributes.get("PARCELID"))
    object_id = _text(attributes.get("OBJECTID"))
    if parcel_id and object_id:
        return f"PARCELID:{parcel_id}|OBJECTID:{object_id}"
    if parcel_id:
        return f"PARCELID:{parcel_id}"
    if object_id:
        return f"OBJECTID:{object_id}"
    raise ValueError("Orleans property row lacks all source identifiers")


def _alternate_ids(attributes: Mapping[str, Any]) -> list[str]:
    values = (
        attributes.get("TAXBILLID"),
        attributes.get("PARCELID"),
        attributes.get("LOWPARCELID"),
        attributes.get("PARID"),
    )
    result: list[str] = []
    for value in values:
        cleaned = _text(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _owners(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for field, role in (
        ("OWNERNME1", "primary_assessor_owner"),
        ("OWNERNME2", "secondary_assessor_owner"),
    ):
        name = _text(attributes.get(field))
        if not name:
            continue
        result.append(
            {
                "raw_name": name,
                "role": role,
                "assertion_type": "assessment_roll",
                "confidence": "high",
                "title_caveat": "not_a_title_chain",
            }
        )
    return result


def _source_links(attributes: Mapping[str, Any]) -> dict[str, str]:
    links = {
        "property_viewer": VIEWER_URL,
        "tax_parcel_layer": LAYER_URL,
        "viewer_parcel_layer": VIEWER_LAYER_URL,
    }
    geopin = _text(attributes.get("PARCELID"))
    if geopin:
        links["record"] = f"{VIEWER_URL}?geopin={quote(geopin, safe='')}"
    parid = _text(attributes.get("PARID"))
    if parid:
        links["assessor_record"] = f"{ASSESSOR_RECORD_URL}{quote(parid, safe='')}"
    return links


def _normalize_feature(
    feature: Mapping[str, Any],
    *,
    schema_fingerprint_value: str,
    include_geometry: bool,
    locator_candidate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError("Orleans ArcGIS feature attributes must be an object")
    attributes = dict(attributes_value)
    native_id = _record_key(attributes)
    last_update = _epoch_millis(attributes.get("LASTUPDATE"))
    tax_bill_id = _text(attributes.get("TAXBILLID"))
    geopin = _text(attributes.get("PARCELID"))
    parid = _text(attributes.get("PARID"))

    record: dict[str, Any] = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "account",
            native_id,
        ),
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "LA",
            "state_fips": "22",
            "county_name": "Orleans Parish",
            "county_geoid": COUNTY_GEOID,
        },
        "native_parcel_id": native_id,
        "native_account_id": tax_bill_id,
        "tax_bill_id": tax_bill_id,
        "parcel_id": geopin,
        "geopin": geopin,
        "lowest_parcel_id": _text(attributes.get("LOWPARCELID")),
        "parid": parid,
        "alternate_parcel_ids": _alternate_ids(attributes),
        "object_id": attributes.get("OBJECTID"),
        "record_scope": "current_weekly_snapshot",
        "snapshot_complete": True,
        "source_last_updated": last_update,
        "owners": _owners(attributes),
        "situs_address": {
            "raw": _text(attributes.get("SITEADDRESS")),
            "street": _text(attributes.get("SITEADDR")),
            "building_number": _text(
                attributes.get("BUILDING") or attributes.get("SITUS_NUM")
            ),
            "unit": _text(attributes.get("UNIT")),
            "street_direction": _text(attributes.get("SITUS_DIR")),
            "street_name": _text(attributes.get("SITUS_STREET")),
            "street_type": _text(attributes.get("SITUS_TYPE")),
            "city": _text(attributes.get("SITECITY")),
            "state": _text(attributes.get("SITESTATE")) or "LA",
            "postal_code": _text(attributes.get("SITEZIP")),
        },
        "mailing_address": {
            "raw": _text(attributes.get("PSTLADDRESS")),
            "city": _text(attributes.get("PSTLCITY")),
            "state": _text(attributes.get("PSTLSTATE")),
            "postal_code": _postal_code(
                attributes.get("PSTLZIP5"),
                attributes.get("PSTLZIP4"),
            ),
        },
        "property_type": {
            "use_code": _text(attributes.get("USECD")),
            "use_description": _text(attributes.get("USEDSCRP")),
            "class_code": _text(attributes.get("CLASSCD")),
            "class_description": _text(attributes.get("CLASSDSCRP")),
            "neighborhood_code": _text(attributes.get("NGHBRHDCD")),
        },
        "assessment": {
            "land_value": _number(attributes.get("LNDVALUE")),
            "previous_assessed_value": _number(attributes.get("PRVASSDVAL")),
            "assessed_value": _number(attributes.get("CNTASSDVAL")),
            "assessed_value_change": _number(attributes.get("ASSDVALYRCG")),
            "assessed_value_percent_change": _number(
                attributes.get("ASSDPCNTCG")
            ),
            "previous_taxable_value": _number(attributes.get("PRVTXBLVAL")),
            "taxable_value": _number(attributes.get("CNTTXBLVAL")),
            "taxable_value_change": _number(attributes.get("TXBLVALYRCHG")),
            "taxable_value_percent_change": _number(
                attributes.get("TXBLPCNTCHG")
            ),
            "assessment_class": (
                _text(attributes.get("CLASSDSCRP"))
                or _text(attributes.get("CLASSCD"))
            ),
            "value_type": "current_assessor_snapshot",
            "currency": "USD",
            "source_last_updated": last_update,
        },
        "taxes_owed": {
            "previous_winter": _number(attributes.get("PRVWNTTXOD")),
            "previous_summer": _number(attributes.get("PRVSMRTXOD")),
            "previous_total": _number(attributes.get("TOTPRVTXTOD")),
            "current_winter": _number(attributes.get("CNTWNTTXOD")),
            "current_summer": _number(attributes.get("CNTSMRTXOD")),
            "current_total": _number(attributes.get("TOTCNTTXOD")),
            "year_over_year_change": _number(attributes.get("TXODYRCHG")),
            "percent_change": _number(attributes.get("TXODPCNTCHG")),
            "currency": "USD",
        },
        "tax_district": {
            "code": _text(attributes.get("CVTTXCD")),
            "description": _text(attributes.get("CVTTXDSCRP")),
        },
        "school_district": {
            "code": _text(attributes.get("SCHLTXCD")),
            "description": _text(attributes.get("SCHLDSCRP")),
        },
        "structure": {
            "residential_floor_area": _number(attributes.get("RESFLRAREA")),
            "residential_year_built": _number(attributes.get("RESYRBLT")),
            "residential_structure_type": _text(attributes.get("RESSTRTYP")),
            "structure_class": _text(attributes.get("STRCLASS")),
            "class_modifier": _text(attributes.get("CLASSMOD")),
        },
        "services": {
            "water": _text(attributes.get("WATERSERV")),
            "sewer": _text(attributes.get("SEWERSERV")),
        },
        "legal_description_raw": _text(attributes.get("PRPRTYDSCRP")),
        "subdivision_or_condo_name": _text(attributes.get("CNVYNAME")),
        "lot": _text(attributes.get("LOT")),
        "square": _text(attributes.get("SQUARE")),
        "block": _text(attributes.get("BLOCK")),
        "parcel_area_sq_ft": _number(attributes.get("ASS_SQFT")),
        "parcel_dimensions_raw": _text(attributes.get("ASS_DIMS")),
        "source_geometry_area": _number(attributes.get("Shape_Area")),
        "source_geometry_length": _number(attributes.get("Shape_Length")),
        "source_links": _source_links(attributes),
        "schema_fingerprint": schema_fingerprint_value,
        "raw_attributes": attributes,
    }
    if locator_candidate is not None:
        candidate_attributes = locator_candidate.get("attributes")
        record["source_match"] = {
            "address": locator_candidate.get("address"),
            "score": locator_candidate.get("score"),
            "location": locator_candidate.get("location"),
            "attributes": (
                dict(candidate_attributes)
                if isinstance(candidate_attributes, Mapping)
                else {}
            ),
        }
    geometry = feature.get("geometry")
    if include_geometry and isinstance(geometry, Mapping):
        record["geometry"] = dict(geometry)
        record["geometry_format"] = "esri_json"
        record["geometry_crs"] = f"EPSG:{OUTPUT_SPATIAL_REFERENCE}"
        record["geometry_disclaimer"] = SOURCE_WARNINGS[1]
    return record


def _candidate_point(candidate: Mapping[str, Any]) -> dict[str, Any]:
    location = candidate.get("location")
    if not isinstance(location, Mapping):
        raise ValueError("Orleans locator candidate lacks a location")
    x = location.get("x")
    y = location.get("y")
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        raise ValueError("Orleans locator candidate has an invalid x coordinate")
    if not isinstance(y, (int, float)) or isinstance(y, bool):
        raise ValueError("Orleans locator candidate has an invalid y coordinate")
    return {
        "x": x,
        "y": y,
        "spatialReference": {"wkid": NATIVE_SPATIAL_REFERENCE},
    }


def _matches_locator_request(
    operation: str,
    selector: str,
    feature: Mapping[str, Any],
    candidate: Mapping[str, Any] | None = None,
) -> bool:
    attributes = feature.get("attributes")
    if not isinstance(attributes, Mapping):
        return False
    requested = _query_text(selector).casefold()
    if operation == "account":
        return (_text(attributes.get("TAXBILLID")) or "").casefold() == requested
    if operation != "search":
        return True
    locator_name = _locator_name(candidate)
    target = _locator_target(candidate, selector).casefold()
    if locator_name == "parcelownerloc":
        return target in {
            (_text(attributes.get("OWNERNME1")) or "").casefold(),
            (_text(attributes.get("OWNERNME2")) or "").casefold(),
        }
    if locator_name == "parceltaxbilll":
        return (_text(attributes.get("TAXBILLID")) or "").casefold() == target
    return True


def _locator_attributes(
    candidate: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if not isinstance(candidate, Mapping):
        return {}
    attributes = candidate.get("attributes")
    return attributes if isinstance(attributes, Mapping) else {}


def _locator_name(candidate: Mapping[str, Any] | None) -> str:
    return (
        _text(_locator_attributes(candidate).get("Loc_name")) or ""
    ).casefold()


def _locator_target(
    candidate: Mapping[str, Any] | None,
    selector: str,
) -> str:
    attributes = _locator_attributes(candidate)
    values = (
        candidate.get("address") if isinstance(candidate, Mapping) else None,
        attributes.get("Match_addr"),
        attributes.get("Address"),
    )
    for value in values:
        cleaned = _text(value)
        if cleaned:
            return cleaned
    return _query_text(selector)


def _locator_where(
    operation: str,
    selector: str,
    candidate: Mapping[str, Any],
) -> str:
    if operation == "account":
        return f"TAXBILLID='{_sql_literal(selector)}'"
    if operation != "search":
        return "1=1"
    locator_name = _locator_name(candidate)
    target = _locator_target(candidate, selector)
    if locator_name == "parcelownerloc":
        escaped = _sql_literal(target)
        return f"(OWNERNME1='{escaped}' OR OWNERNME2='{escaped}')"
    if locator_name == "parceltaxbilll":
        return f"TAXBILLID='{_sql_literal(target)}'"
    return "1=1"


def _direct_fetch(
    args: argparse.Namespace,
    *,
    operation: str,
    limit: int,
    layer_client: ArcGISRESTClient,
) -> PaginatedFetch:
    return layer_client.query(
        where=_where(
            operation,
            getattr(args, "query", None),
            id_type=getattr(args, "id_type", "auto"),
        ),
        out_fields="*",
        parameters={
            "orderByFields": ORDER_BY,
            "outSR": OUTPUT_SPATIAL_REFERENCE,
        },
        requested_limit=limit + 1,
        cursor=getattr(args, "cursor", None),
        return_geometry=bool(getattr(args, "geometry", False)),
    )


def _owner_fetch(
    args: argparse.Namespace,
    *,
    selector: str,
    limit: int,
    layer_client: ArcGISRESTClient,
) -> tuple[list[dict[str, Any]], str | None, list[str]]:
    phase, offset = _owner_cursor(getattr(args, "cursor", None))
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    include_geometry = bool(getattr(args, "geometry", False))

    for current_phase in range(phase, 2):
        remaining = limit - len(records)
        if remaining <= 0:
            return records, _make_owner_cursor(current_phase, offset), warnings
        fetched = layer_client.query(
            where=_owner_where(selector, current_phase),
            out_fields="*",
            parameters={
                "orderByFields": ORDER_BY,
                "outSR": OUTPUT_SPATIAL_REFERENCE,
            },
            requested_limit=remaining + 1,
            cursor=(
                f"arcgis:offset:{offset}"
                if current_phase == phase and offset
                else None
            ),
            return_geometry=include_geometry,
        )
        source_records = list(fetched.records)
        selected_records = source_records[:remaining]
        records.extend(
            _normalize_feature(
                feature,
                schema_fingerprint_value=fetched.schema_fingerprint,
                include_geometry=include_geometry,
            )
            for feature in selected_records
        )
        warnings.extend(fetched.warnings)
        if len(source_records) > remaining:
            return (
                records,
                _make_owner_cursor(
                    current_phase,
                    offset + remaining,
                ),
                warnings,
            )
        offset = 0
        if len(records) >= limit:
            next_cursor = (
                _make_owner_cursor(1, 0)
                if current_phase == 0
                else None
            )
            return records, next_cursor, warnings
    return records, None, warnings


def _locator_fetch(
    args: argparse.Namespace,
    *,
    operation: str,
    selector: str,
    limit: int,
    layer_client: ArcGISRESTClient,
    locator_client: OrleansPropertyLocatorClient,
) -> tuple[list[dict[str, Any]], str | None, list[str], bool]:
    candidate_offset, feature_offset, seen_features = _locator_cursor(
        getattr(args, "cursor", None)
    )
    requested_candidates = LOCATOR_MAX_CANDIDATES
    candidates = locator_client.candidates(
        selector,
        max_locations=requested_candidates,
    )
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    include_geometry = bool(getattr(args, "geometry", False))
    if len(candidates) == LOCATOR_MAX_CANDIDATES:
        warnings.append(
            "The official locator returned its maximum candidate batch, "
            "so additional locator matches may exist."
        )

    for candidate_index in range(candidate_offset, len(candidates)):
        candidate = candidates[candidate_index]
        point = _candidate_point(candidate)
        source_offset = (
            feature_offset if candidate_index == candidate_offset else 0
        )
        while len(records) < limit:
            remaining = limit - len(records)
            fetched = layer_client.query(
                where=_locator_where(operation, selector, candidate),
                out_fields="*",
                parameters={
                    "geometry": canonical_json(point),
                    "geometryType": "esriGeometryPoint",
                    "inSR": NATIVE_SPATIAL_REFERENCE,
                    "spatialRel": "esriSpatialRelIntersects",
                    "orderByFields": ORDER_BY,
                    "outSR": OUTPUT_SPATIAL_REFERENCE,
                },
                requested_limit=remaining + 1,
                cursor=(
                    f"arcgis:offset:{source_offset}"
                    if source_offset
                    else None
                ),
                return_geometry=include_geometry,
            )
            warnings.extend(fetched.warnings)
            source_records = list(fetched.records)
            consumed = 0
            for feature in source_records:
                consumed += 1
                if not _matches_locator_request(
                    operation,
                    selector,
                    feature,
                    candidate,
                ):
                    continue
                attributes = feature.get("attributes")
                object_id = (
                    _text(attributes.get("OBJECTID"))
                    if isinstance(attributes, Mapping)
                    else None
                )
                identity = object_id or canonical_json(feature)
                if identity in seen_features:
                    continue
                seen_features.add(identity)
                records.append(
                    _normalize_feature(
                        feature,
                        schema_fingerprint_value=fetched.schema_fingerprint,
                        include_geometry=include_geometry,
                        locator_candidate=candidate,
                    )
                )
                if len(records) >= limit:
                    next_source_offset = source_offset + consumed
                    if (
                        consumed < len(source_records)
                        or fetched.next_cursor is not None
                    ):
                        next_cursor = _make_locator_cursor(
                            candidate_index,
                            next_source_offset,
                            seen_features,
                        )
                    elif candidate_index + 1 < len(candidates):
                        next_cursor = _make_locator_cursor(
                            candidate_index + 1,
                            0,
                            seen_features,
                        )
                    else:
                        next_cursor = None
                    return (
                        records,
                        next_cursor,
                        warnings,
                        next_cursor is not None,
                    )
            source_offset += len(source_records)
            if fetched.next_cursor is None:
                break
            if not source_records:
                raise ValueError(
                    "Orleans layer returned a continuation without records"
                )
        feature_offset = 0

    return records, None, warnings, False


def build_query(
    operation: str,
    selector: str | None,
    *,
    tax_year: int | None,
    limit: int,
    cursor: str | None,
    return_geometry: bool,
    id_type: str = "auto",
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=COUNTY_GEOID,
            name="Orleans Parish, Louisiana",
            state_code="LA",
            county_fips=COUNTY_GEOID,
            locality="New Orleans",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={
                "selector": selector,
                "tax_year": tax_year,
                "return_geometry": return_geometry,
                "parcel_id_type": id_type if operation == "parcel" else None,
            },
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _unsupported_tax_year(
    query: PublicRecordsQuery,
    tax_year: int,
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="tax_year_filter_not_published",
                message=(
                    "The current TaxParcelPublishing layer does not expose a tax-year "
                    f"field, so it cannot apply tax year {tax_year}."
                ),
                category="query",
                retryable=False,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    layer_client: ArcGISRESTClient | None = None,
    locator_client: OrleansPropertyLocatorClient | None = None,
) -> PublicRecordsResult:
    operation = str(args.command)
    selector = (
        PROBE_GEOPIN
        if operation == "probe"
        else getattr(args, "query", None)
    )
    requested_limit = 1 if operation == "probe" else int(args.limit)
    tax_year = getattr(args, "tax_year", None)
    query = build_query(
        operation,
        selector,
        tax_year=tax_year,
        limit=requested_limit,
        cursor=getattr(args, "cursor", None),
        return_geometry=bool(getattr(args, "geometry", False)),
        id_type=getattr(args, "id_type", "auto"),
    )

    if tax_year is not None:
        result = _unsupported_tax_year(query, int(tax_year))
        log_search(canonical_json(query.to_dict()), SOURCE_ID, None)
        return result

    try:
        limit, capped, cap_warnings = _effective_limit(args)
        if operation == "probe":
            limit = 1
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        layer = layer_client or _new_layer_client(args, access_contract)
        warnings = [*SOURCE_WARNINGS, *cap_warnings]

        if operation == "owner":
            records, next_cursor, owner_warnings = _owner_fetch(
                args,
                selector=_query_text(selector),
                limit=limit,
                layer_client=layer,
            )
            warnings.extend(owner_warnings)
            partial = capped and next_cursor is not None
        elif operation in {"parcel", "probe"}:
            fetched = _direct_fetch(
                args,
                operation=operation,
                limit=limit,
                layer_client=layer,
            )
            source_records = list(fetched.records)
            selected_records = source_records[:limit]
            records = [
                _normalize_feature(
                    feature,
                    schema_fingerprint_value=fetched.schema_fingerprint,
                    include_geometry=bool(getattr(args, "geometry", False)),
                )
                for feature in selected_records
            ]
            warnings.extend(fetched.warnings)
            source_has_more = len(source_records) > limit
            start_offset = (
                _arcgis_offset(args.cursor)
                if getattr(args, "cursor", None)
                else 0
            )
            next_cursor = (
                f"arcgis:offset:{start_offset + limit}"
                if source_has_more
                else None
            )
            partial = capped and source_has_more
        elif operation in {"address", "account", "search"}:
            locator = locator_client or _new_locator_client(
                args,
                access_contract,
            )
            records, next_cursor, locator_warnings, source_has_more = (
                _locator_fetch(
                    args,
                    operation=operation,
                    selector=_query_text(selector),
                    limit=limit,
                    layer_client=layer,
                    locator_client=locator,
                )
            )
            warnings.extend(locator_warnings)
            partial = capped and source_has_more
        else:
            raise ValueError(f"unsupported Orleans operation: {operation}")

        if partial:
            result = PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=next_cursor,
                warnings=warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                warnings=warnings,
            )
    except AcquisitionUnavailableError as error:
        decision = error.decision
        result = PublicRecordsResult.failure(
            query,
            ResultStatus(acquisition_result_status(decision)),
            [
                PublicRecordsError(
                    code=str(
                        decision.get("reason_code")
                        or "machine_acquisition_denied"
                    ),
                    message=str(error),
                    category="access_policy",
                    retryable=False,
                    details=decision,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=SOURCE_WARNINGS)
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

    count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"Orleans property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Orleans property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        owners = ", ".join(
            str(owner.get("raw_name") or "")
            for owner in record.get("owners", [])
        )
        print(
            f"  {record.get('tax_bill_id') or record['native_parcel_id']} | "
            f"GeoPIN {record.get('geopin') or '?'} | "
            f"{record.get('situs_address', {}).get('raw') or '?'} | "
            f"{owners or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--cursor", help="Continuation cursor from a previous result")
    parser.add_argument("--geometry", action="store_true", help="Return parcel geometry")
    parser.add_argument(
        "--tax-year",
        type=int,
        help="Tax-year filter when a source publishes one",
    )
    parser.add_argument("--page-size", type=int, default=SOURCE_MAX_PAGE_SIZE)
    parser.add_argument(
        "--max-records",
        type=int,
        help="Optional caller-selected record ceiling",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query official Orleans Parish property and assessment records"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("owner", "Search owner-one and owner-two fields by name prefix"),
        ("address", "Resolve a situs address through the official locator"),
        ("account", "Fetch a tax assessment account by Tax Bill ID"),
        ("parcel", "Fetch all accounts for a GeoPIN or PARID"),
        ("search", "Search address, owner, or Tax Bill ID through the official locator"),
    ):
        command_parser = sub.add_parser(command, help=help_text)
        command_parser.add_argument("query")
        if command == "parcel":
            command_parser.add_argument(
                "--id-type",
                choices=("auto", "geopin", "parid"),
                default="auto",
                help=(
                    "Interpret the identifier automatically, as a GeoPIN, "
                    "or as a PARID"
                ),
            )
        _add_shared_arguments(command_parser)
    probe_parser = sub.add_parser("probe", help="Run one bounded source-health query")
    _add_shared_arguments(probe_parser)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if (
        args.limit <= 0
        or args.page_size <= 0
        or (args.max_records is not None and args.max_records <= 0)
    ):
        parser.error("limit and page-size must be positive; max-records is optional")
    if args.tax_year is not None and args.tax_year <= 0:
        parser.error("--tax-year must be positive")
    _emit(execute(args), args)


if __name__ == "__main__":
    main()
