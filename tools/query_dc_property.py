#!/usr/bin/env python3
"""Query District of Columbia assessment, tax, geometry, sale, and survey data.

The official DCGIS ``Property and Land`` MapServer publishes several linked
components:

* ITSPE table 53: the full public assessment and tax-account extract.
* Common Ownership layer 40: daily land geometry with a denormalized ITSPE view.
* CAMA sales table 57: property-sale observations keyed by SSL.
* Surveyor Document System table 69: survey books and document-viewer links.

The components retain separate source identities and join through the District's
Square/Suffix/Lot (SSL) identifier.  The ITSPE table covers more tax accounts
than there are physical common-ownership polygons, so the adapter does not
assume a one-to-one account-to-geometry relationship.

Examples:
    uv run python tools/query_dc_property.py sources
    uv run python tools/query_dc_property.py assessment "PAR 01300036" --field ssl
    uv run python tools/query_dc_property.py geometry "931 BRENTWOOD" --field address
    uv run python tools/query_dc_property.py point -76.9927 38.9176 --geometry
    uv run python tools/query_dc_property.py sales "PAR 01300036"
    uv run python tools/query_dc_property.py surveys 9B59CB35-62CB-C473-B297-59097C200000 \
        --field document
    uv run python tools/query_dc_property.py count assessment
    uv run python tools/query_dc_property.py metadata geometry
    uv run python tools/query_dc_property.py probe geometry
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
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
        sha256_fingerprint,
    )
    from tools.public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
        schema_fingerprint,
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
        sha256_fingerprint,
    )
    from public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
        SourceResponseError,
        SourceSchemaError,
        failure_result,
        schema_fingerprint,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


STATE_CODE = "DC"
STATE_FIPS = "11"
JURISDICTION_GEOID = "11"
LINEAGE_ID = "us-dc-itspe-property-lineage"

ITSPE_SOURCE_ID = "us-dc-itspe-public-extract"
OWNER_POLYGON_SOURCE_ID = "us-dc-common-ownership-polygons"
SALES_SOURCE_ID = "us-dc-cama-property-sales"
SURVEY_SOURCE_ID = "us-dc-surveyor-document-system"
RECORDER_SOURCE_ID = "us-dc-recorder-of-deeds-public-records"

SERVICE_URL = (
    "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/"
    "Property_and_Land/MapServer"
)
ITSPE_LAYER_ID = 53
OWNER_POLYGON_LAYER_ID = 40
SALES_LAYER_ID = 57
SURVEY_LAYER_ID = 69

SOURCE_MAX_PAGE_SIZE = 1_000
DEFAULT_PAGE_SIZE = 100
SOURCE_NATIVE_CRS = "EPSG:2248"
DEFAULT_OUTPUT_CRS = 4326

PROBE_SSL = "PAR 01300036"
PROBE_SURVEY_GUID = "9B59CB35-62CB-C473-B297-59097C200000"

MYTAX_URL = "https://mytax.dc.gov/"
RECORDER_URL = "https://otr.cfo.dc.gov/node/1791291"
RECORDER_IMAGES_URL = "https://dc.gov/service/recorder-deeds-document-images"

TAX_PERIOD_PREFIXES = (
    "CY1",
    "CY2",
    "PY1",
    "PY2",
    "PY3",
    "PY4",
    "PY5",
    "PY6",
    "PY7",
    "PY8",
    "PY9",
    "PY10",
)
TAX_PERIOD_SUFFIXES = (
    "YEAR",
    "TXSALE",
    "TAX",
    "PEN",
    "INT",
    "FEE",
    "TOTDUE",
    "COLL",
    "BAL",
    "CR",
)


@dataclass(frozen=True)
class Component:
    key: str
    source_id: str
    name: str
    layer_id: int
    role: str
    record_kind: str
    has_geometry: bool
    stable_keys: tuple[str, ...]

    @property
    def layer_url(self) -> str:
        return f"{SERVICE_URL}/{self.layer_id}"

    def source_metadata(self) -> SourceMetadata:
        common = {
            "authority": "Government of the District of Columbia",
            "operator": "DC GIS",
            "coverage": "District of Columbia",
            "layer_id": self.layer_id,
            "lineage_id": LINEAGE_ID,
            "stable_keys": list(self.stable_keys),
            "ssl_join": True,
        }
        if self.key in {"assessment", "geometry"}:
            common.update(
                {
                    "lineage_relationship": (
                        "same_itspe_assessment_and_tax_lineage"
                    ),
                    "mytax_complement": MYTAX_URL,
                    "recorder_complement": RECORDER_URL,
                }
            )
        elif self.key == "sales":
            common["lineage_relationship"] = "cama_sale_observation"
        else:
            common["lineage_relationship"] = "surveyor_document_index"
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.role,
            base_url=self.layer_url,
            dataset_id=f"Property_and_Land/MapServer/{self.layer_id}",
            metadata=common,
        )


ITSPE = Component(
    key="assessment",
    source_id=ITSPE_SOURCE_ID,
    name="District of Columbia ITSPE Public Extract",
    layer_id=ITSPE_LAYER_ID,
    role="official_assessment_tax_account_extract",
    record_kind="assessment_tax_account",
    has_geometry=False,
    stable_keys=("SSL", "OBJECTID"),
)
OWNER_POLYGONS = Component(
    key="geometry",
    source_id=OWNER_POLYGON_SOURCE_ID,
    name="District of Columbia Common Ownership Polygons",
    layer_id=OWNER_POLYGON_LAYER_ID,
    role="official_property_geometry_assessment_tax_view",
    record_kind="common_ownership_polygon",
    has_geometry=True,
    stable_keys=("SSL", "GLOBALID", "OBJECTID"),
)
SALES = Component(
    key="sales",
    source_id=SALES_SOURCE_ID,
    name="District of Columbia CAMA Property Sales",
    layer_id=SALES_LAYER_ID,
    role="official_assessor_sale_history",
    record_kind="property_sale_observation",
    has_geometry=False,
    stable_keys=("SSL", "ROW_NUMBER", "OBJECTID"),
)
SURVEYS = Component(
    key="surveys",
    source_id=SURVEY_SOURCE_ID,
    name="District of Columbia Surveyor Document System",
    layer_id=SURVEY_LAYER_ID,
    role="official_survey_document_index",
    record_kind="surveyor_document",
    has_geometry=False,
    stable_keys=("DOCGUID", "OBJECTID"),
)

COMPONENTS = {
    component.key: component
    for component in (ITSPE, OWNER_POLYGONS, SALES, SURVEYS)
}
SOURCE_METADATA = {
    key: component.source_metadata() for key, component in COMPONENTS.items()
}
SOURCES_BY_ID = {
    metadata.source_id: metadata for metadata in SOURCE_METADATA.values()
}

JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=JURISDICTION_GEOID,
    name="District of Columbia",
    state_code=STATE_CODE,
    locality="Washington",
    metadata={"state_fips": STATE_FIPS},
)

ASSESSMENT_WARNINGS = (
    "ITSPE assessment-owner, sale, and tax fields are source observations tied to the published extract date.",
    "A recorded instrument should be retrieved from the separately sourced Recorder of Deeds route when document-level evidence is needed.",
)
GEOMETRY_WARNINGS = (
    "The common-ownership layer is regenerated from current vector-property mapping and ITSPE inputs; overlapping ITSPE values are the same data lineage.",
    "Tax accounts and physical land polygons are not assumed to have a one-to-one relationship.",
)
SALES_WARNINGS = (
    "CAMA sale rows are assessor-system observations and retain their source qualification and sale codes.",
)
SURVEY_WARNINGS = (
    "Surveyor documents are a survey and mapping complement, not the Recorder of Deeds instrument index.",
)
WARNINGS_BY_COMPONENT = {
    "assessment": ASSESSMENT_WARNINGS,
    "geometry": GEOMETRY_WARNINGS,
    "sales": SALES_WARNINGS,
    "surveys": SURVEY_WARNINGS,
}

ASSESSMENT_BASE_FIELDS = (
    "OBJECTID",
    "INTERNALID",
    "SSL",
    "SQUARE",
    "SUFFIX",
    "LOT",
    "ARN",
    "ASRNAME",
    "PROPTYPE",
    "TRIGROUP",
    "USECODE",
    "LANDAREA",
    "PREMISEADD",
    "NBHD",
    "SUBNBHD",
    "NBHDNAME",
    "PRMS_WARD",
    "UNITNUMBER",
    "OWNERNAME",
    "OWNNAME2",
    "CAREOFNAME",
    "ADDRESS1",
    "ADDRESS2",
    "CITYSTZIP",
    "OLDLAND",
    "OLDIMPR",
    "OLDTOTAL",
    "NEWLAND",
    "NEWIMPR",
    "NEWTOTAL",
    "PHASELAND",
    "PHASEBUILD",
    "PARTPART",
    "VACLNDUSE",
    "DELCODE",
    "HSTDCODE",
    "CLASSTYPE",
    "TAXRATE",
    "MIXEDUSE",
    "OWNOCCT",
    "COOPUNITS",
    "PCHILDCODE",
    "ABTLOTCODE",
    "SALEPRICE",
    "SALEDATE",
    "ACCEPTCODE",
    "SALETYPE",
    "DEEDDATE",
    "ASSESSMENT",
    "ANNUALTAX",
    "DUEDATE1",
    "AMTDUE1",
    "DUEDATE2",
    "AMTDUE2",
    "DUEDATE3",
    "AMTDUE3",
    "TOTDUEAMT",
    "TOTCOLAMT",
    "TOTBALAMT",
    "EXTRACTDAT",
    "CAPCURR",
    "CAPPROP",
    "REASONCD",
    "INST_NO",
    "MORTGAGECO",
    "PRESSL",
    "PIPARENTLOT",
    "BIDNAME",
    "BIDTOTALDUE",
    "BIDCOLLECTED",
    "BIDBALANCE",
    "SEWSTOTALDUE",
    "SEWSCOLLECTED",
    "SEWSBALANCE",
    "PACETOTALDUE",
    "PACECOLLECTED",
    "PACEBALANCE",
    "SWWSADTOTALDUE",
    "SWWSADCOLLECTED",
    "SWWSADBALANCE",
    "LASTPAYDT",
)
TAX_PERIOD_FIELDS = tuple(
    f"{prefix}{suffix}"
    for prefix in TAX_PERIOD_PREFIXES
    for suffix in TAX_PERIOD_SUFFIXES
)
ASSESSMENT_OUT_FIELDS = (*ASSESSMENT_BASE_FIELDS, *TAX_PERIOD_FIELDS)

OWNER_POLYGON_BASE_FIELDS = (
    "OBJECTID",
    "GLOBALID",
    "MAR_ID",
    "SSL",
    "SQUARE",
    "SUFFIX",
    "RES",
    "PAR",
    "LOT",
    "LOT_TYPE",
    "OF_LOT_SEQ",
    "BOOK_NUM",
    "PAGE_NUM",
    "UNDERLIES_CONDO",
    "CONDO_BOOK_NUM",
    "CONDO_PAGE_NUM",
    "EFFECTIVETAXYEAR",
    "QUADRANT",
    "COL",
    "ARN",
    "ASRNAME",
    "PROPTYPE",
    "TRIGROUP",
    "USECODE",
    "LANDAREA",
    "PRMSWARD",
    "PREMISEADD",
    "NBHD",
    "NBHDNAME",
    "SUBNBHD",
    "UNITNUMBER",
    "OWNERNAME",
    "OWNNAME2",
    "CAREOFNAME",
    "ADDRESS1",
    "ADDRESS2",
    "CITYSTZIP",
    "OLDLAND",
    "OLDIMPR",
    "OLDTOTAL",
    "NEWLAND",
    "NEWIMPR",
    "NEWTOTAL",
    "PHASELAND",
    "PHASEBUILD",
    "PARTPART",
    "VACLNDUSE",
    "DELCODE",
    "HSTDCODE",
    "CLASSTYPE",
    "TAXRATE",
    "MIXEDUSE",
    "OWNOCCT",
    "COOPUNITS",
    "PCHILDCODE",
    "ABTLOTCODE",
    "SALEPRICE",
    "SALEDATE",
    "INSTNO",
    "ACCEPTCODE",
    "SALETYPE",
    "MORTGAGECO",
    "ASSESSMENT",
    "ANNUALTAX",
    "EXTRACTDAT",
    "CAPCURR",
    "CAPPROP",
    "DEEDS",
    "CONDOLOT",
    "CONDO_REGIME_NUM",
    "RECORDATION_DT",
    "STATEDAREA",
    "STATEDAREAUNIT",
    "CALCULATEDAREA",
    "CREATED_DATE",
    "LAST_EDITED_DATE",
    "ISHISTORIC",
    "RECORD",
    "RETIRING_RECORD",
    "SHAPE.AREA",
    "SHAPE.LEN",
)
OWNER_POLYGON_OUT_FIELDS = (*OWNER_POLYGON_BASE_FIELDS, *TAX_PERIOD_FIELDS)
SALES_OUT_FIELDS = (
    "OBJECTID",
    "ROW_NUMBER",
    "SSL",
    "SALE_DATE",
    "SALE_PRICE",
    "QUALIFIED",
    "SALE_CODE",
    "SALE_CURR_OWNER",
    "GIS_LAST_MOD_DTTM",
)
SURVEY_OUT_FIELDS = (
    "DOCGUID",
    "SSL",
    "SQUARE",
    "SUFFIX",
    "LOT",
    "DOCUMENTTYPE",
    "SUBDOCUMENTTYPE",
    "FILENETLINK",
    "ISACTIVE",
    "BOOKNUMBER",
    "PAGENUMBER",
    "BOOKNAME",
    "OBJECTID",
    "GIS_LAST_MOD_DTTM",
)
OUT_FIELDS_BY_COMPONENT = {
    "assessment": ASSESSMENT_OUT_FIELDS,
    "geometry": OWNER_POLYGON_OUT_FIELDS,
    "sales": SALES_OUT_FIELDS,
    "surveys": SURVEY_OUT_FIELDS,
}

ADAPTER_SCHEMA_FINGERPRINTS = {
    key: sha256_fingerprint(
        {
            "source_id": component.source_id,
            "layer_id": component.layer_id,
            "normalization_version": 1,
            "fields": OUT_FIELDS_BY_COMPONENT[key],
        }
    )
    for key, component in COMPONENTS.items()
}


class DCArcGISClient(ArcGISRESTClient):
    """ArcGIS client with metadata and count operations for one component."""

    def fetch_metadata(self) -> Mapping[str, Any]:
        payload = self._request_json(self.layer_url, params={"f": "json"})
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "DCGIS metadata response must be an object",
                url=self.layer_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "DCGIS returned an error response",
                url=self.layer_url,
                details={"response": payload["error"]},
            )
        return payload

    def fetch_count(
        self,
        *,
        where: str = "1=1",
        parameters: Mapping[str, Any] | None = None,
    ) -> int:
        payload = self._request_json(
            self.query_url,
            params={
                **dict(parameters or {}),
                "where": where,
                "returnCountOnly": "true",
                "f": "json",
            },
        )
        if not isinstance(payload, Mapping):
            raise SourceSchemaError(
                "DCGIS count response must be an object",
                url=self.query_url,
            )
        if "error" in payload:
            raise SourceResponseError(
                "DCGIS returned an error response",
                url=self.query_url,
                details={"response": payload["error"]},
            )
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise SourceSchemaError(
                "DCGIS count response lacks a nonnegative integer count",
                url=self.query_url,
            )
        return count


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return parsed


def _component(value: str | Component) -> Component:
    if isinstance(value, Component):
        return value
    try:
        return COMPONENTS[str(value)]
    except KeyError as error:
        raise ValueError(
            f"component must be one of: {', '.join(sorted(COMPONENTS))}"
        ) from error


def _sql_text(value: Any, label: str) -> str:
    cleaned = " ".join(str(value or "").replace("\x00", "").split()).strip()
    if not cleaned:
        raise ValueError(f"{label} must not be blank")
    return cleaned.replace("'", "''")


def _raw_sql_text(value: Any, label: str) -> str:
    cleaned = str(value or "").replace("\x00", "").strip()
    if not cleaned:
        raise ValueError(f"{label} must not be blank")
    return cleaned.replace("'", "''")


def _date_literal(value: str, label: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} must be YYYY-MM-DD") from error
    return parsed.isoformat()


def _arcgis_datetime(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return (
                datetime.fromtimestamp(value / 1000, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (OSError, OverflowError, ValueError):
            pass
    return str(value).strip() or None


def _string(value: Any) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text or None


def _raw_address(*values: Any) -> str | None:
    parts = [_string(value) for value in values]
    return ", ".join(value for value in parts if value) or None


def _canonical_ssl(attributes: Mapping[str, Any]) -> tuple[str | None, str | None]:
    raw = str(attributes.get("SSL") or "").strip() or None
    normalized = _string(raw)
    if normalized:
        return normalized, raw
    square = _string(attributes.get("SQUARE"))
    suffix = _string(attributes.get("SUFFIX"))
    lot = _string(attributes.get("LOT"))
    values = [value for value in (square, suffix, lot) if value]
    return (" ".join(values) or None), raw


def _ssl_parts(value: Any) -> tuple[str, str | None, str] | None:
    normalized = _string(value)
    if not normalized:
        return None
    upper = normalized.upper()
    parcel_match = re.fullmatch(r"PAR\s+(\d{4})(\d{4})", upper)
    if parcel_match:
        return "PAR", parcel_match.group(1), parcel_match.group(2)
    standard_match = re.fullmatch(
        r"(\d{4})([A-Z]{1,4})?\s+(\d{4})",
        upper,
    )
    if standard_match:
        return (
            standard_match.group(1),
            standard_match.group(2),
            standard_match.group(3),
        )
    compact_match = re.fullmatch(r"(\d{4})([A-Z]{1,4})(\d{4})", upper)
    if compact_match:
        return (
            compact_match.group(1),
            compact_match.group(2),
            compact_match.group(3),
        )
    return None


def _ssl_where(value: Any, *, component_fields: bool) -> str:
    raw = _raw_sql_text(value, "SSL")
    exact = f"SSL='{raw}'"
    if not component_fields:
        return exact
    parts = _ssl_parts(value)
    if parts is None:
        return exact
    square, suffix, lot = parts
    suffix_condition = (
        f"SUFFIX='{suffix}'"
        if suffix
        else "(SUFFIX IS NULL OR SUFFIX='')"
    )
    return (
        f"({exact} OR (SQUARE='{square}' AND "
        f"{suffix_condition} AND LOT='{lot}'))"
    )


def _stable_native_id(
    component: Component,
    attributes: Mapping[str, Any],
) -> str:
    ssl, _ = _canonical_ssl(attributes)
    if component.key in {"assessment", "geometry"} and ssl:
        return ssl
    if component.key == "sales":
        row_number = _string(attributes.get("ROW_NUMBER"))
        if row_number:
            return row_number
        parts = (
            ssl,
            _arcgis_datetime(attributes.get("SALE_DATE")),
            _string(attributes.get("SALE_PRICE")),
        )
        natural = "|".join(part or "" for part in parts)
        if natural.strip("|"):
            return sha256_fingerprint(natural)[:24]
    if component.key == "surveys":
        guid = _string(attributes.get("DOCGUID"))
        if guid:
            return guid
    global_id = _string(attributes.get("GLOBALID"))
    if global_id:
        return global_id.strip("{}")
    object_id = attributes.get("OBJECTID")
    if object_id not in (None, ""):
        return str(object_id)
    raise ValueError(f"{component.name} record lacks a stable source identifier")


def _owners(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    for field_name, role in (
        ("OWNERNAME", "primary_assessment_owner"),
        ("OWNNAME2", "secondary_billing_owner"),
    ):
        name = _string(attributes.get(field_name))
        if name and name.casefold() not in {
            owner["raw_name"].casefold() for owner in owners
        }:
            owners.append(
                {
                    "raw_name": name,
                    "role": role,
                    "assertion_type": "assessment_roll",
                    "source_field": field_name,
                }
            )
    return owners


def _tax_periods(attributes: Mapping[str, Any]) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    for prefix in TAX_PERIOD_PREFIXES:
        values = {
            "source_prefix": prefix,
            "year_label": _string(attributes.get(f"{prefix}YEAR")),
            "tax_sale_flag": _string(attributes.get(f"{prefix}TXSALE")),
            "tax": attributes.get(f"{prefix}TAX"),
            "penalty": attributes.get(f"{prefix}PEN"),
            "interest": attributes.get(f"{prefix}INT"),
            "fee": attributes.get(f"{prefix}FEE"),
            "total_due": attributes.get(f"{prefix}TOTDUE"),
            "collected": attributes.get(f"{prefix}COLL"),
            "balance": attributes.get(f"{prefix}BAL"),
            "credits": attributes.get(f"{prefix}CR"),
            "currency": "USD",
        }
        if any(
            value not in (None, "", 0, 0.0)
            for key, value in values.items()
            if key not in {"source_prefix", "currency"}
        ) or values["year_label"]:
            periods.append(values)
    return periods


def _assessment_record(
    component: Component,
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
    geometry_crs: int,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError(f"{component.name} feature lacks attributes")
    attributes = dict(attributes_value)
    ssl, raw_ssl = _canonical_ssl(attributes)
    native_id = _stable_native_id(component, attributes)
    instrument_number = _string(
        attributes.get("INST_NO") or attributes.get("INSTNO")
    )
    geometry = feature.get("geometry")

    record: dict[str, Any] = {
        "record_type": component.record_kind,
        "canonical_ref": canonical_property_ref(
            component.source_id,
            JURISDICTION_GEOID,
            "property_account"
            if component.key == "assessment"
            else "property_geometry",
            native_id,
        ),
        "source_id": component.source_id,
        "dataset_id": SOURCE_METADATA[component.key].dataset_id,
        "lineage_id": LINEAGE_ID,
        "component": component.key,
        "jurisdiction": {
            "state_code": STATE_CODE,
            "jurisdiction_geoid": JURISDICTION_GEOID,
            "locality": "District of Columbia",
        },
        "native_id": native_id,
        "native_parcel_id": ssl,
        "ssl": {
            "normalized": ssl,
            "raw": raw_ssl,
            "square": _string(attributes.get("SQUARE")),
            "suffix": _string(attributes.get("SUFFIX")),
            "lot": _string(attributes.get("LOT")),
            "parcel": _string(attributes.get("PAR")),
            "reservation": _string(attributes.get("RES")),
        },
        "object_id": attributes.get("OBJECTID"),
        "global_id": _string(attributes.get("GLOBALID")),
        "owners": _owners(attributes),
        "situs_address": {
            "raw": _string(attributes.get("PREMISEADD")),
            "unit": _string(attributes.get("UNITNUMBER")),
            "ward": _string(
                attributes.get("PRMS_WARD")
                or attributes.get("PRMSWARD")
            ),
        },
        "mailing_address": {
            "raw": _raw_address(
                attributes.get("ADDRESS1"),
                attributes.get("ADDRESS2"),
                attributes.get("CITYSTZIP"),
            ),
            "line1": _string(attributes.get("ADDRESS1")),
            "line2": _string(attributes.get("ADDRESS2")),
            "city_state_postal_raw": _string(attributes.get("CITYSTZIP")),
            "care_of": _string(attributes.get("CAREOFNAME")),
        },
        "classification": {
            "property_type": _string(attributes.get("PROPTYPE")),
            "use_code": _string(attributes.get("USECODE")),
            "tax_class": _string(attributes.get("CLASSTYPE")),
            "tax_rate": attributes.get("TAXRATE"),
            "homestead_code": _string(attributes.get("HSTDCODE")),
            "mixed_use": _string(attributes.get("MIXEDUSE")),
            "vacant_land_use": _string(attributes.get("VACLNDUSE")),
            "neighborhood_code": _string(attributes.get("NBHD")),
            "neighborhood_name": _string(attributes.get("NBHDNAME")),
            "sub_neighborhood": _string(attributes.get("SUBNBHD")),
        },
        "assessment": {
            "current_total": attributes.get("ASSESSMENT"),
            "current_land": attributes.get("PHASELAND"),
            "current_improvement": attributes.get("PHASEBUILD"),
            "prior_land": attributes.get("OLDLAND"),
            "prior_improvement": attributes.get("OLDIMPR"),
            "prior_total": attributes.get("OLDTOTAL"),
            "proposed_land": attributes.get("NEWLAND"),
            "proposed_improvement": attributes.get("NEWIMPR"),
            "proposed_total": attributes.get("NEWTOTAL"),
            "current_cap": attributes.get("CAPCURR"),
            "proposed_cap": attributes.get("CAPPROP"),
            "currency": "USD",
        },
        "tax": {
            "annual_tax": attributes.get("ANNUALTAX"),
            "total_due": attributes.get("TOTDUEAMT"),
            "total_collected": attributes.get("TOTCOLAMT"),
            "total_balance": attributes.get("TOTBALAMT"),
            "installments": [
                {
                    "due_date_raw": _string(attributes.get(f"DUEDATE{index}")),
                    "amount_due": attributes.get(f"AMTDUE{index}"),
                    "currency": "USD",
                }
                for index in (1, 2, 3)
                if attributes.get(f"DUEDATE{index}") not in (None, "")
                or attributes.get(f"AMTDUE{index}") not in (None, "")
            ],
            "periods": _tax_periods(attributes),
            "last_payment_date": _arcgis_datetime(
                attributes.get("LASTPAYDT")
            ),
            "currency": "USD",
        },
        "last_sale": {
            "sale_date": _arcgis_datetime(attributes.get("SALEDATE")),
            "deed_date": _arcgis_datetime(attributes.get("DEEDDATE")),
            "consideration": attributes.get("SALEPRICE"),
            "acceptance_code": _string(attributes.get("ACCEPTCODE")),
            "sale_type": _string(attributes.get("SALETYPE")),
            "instrument_number": instrument_number,
            "currency": "USD",
        },
        "recorder_join": (
            {
                "source_id": RECORDER_SOURCE_ID,
                "instrument_number": instrument_number,
                "official_url": RECORDER_URL,
                "images_information_url": RECORDER_IMAGES_URL,
            }
            if instrument_number
            else None
        ),
        "property_lineage": {
            "parent_ssl": _string(
                attributes.get("PRESSL")
                or attributes.get("PIPARENTLOT")
            ),
            "abutting_ssl": _string(attributes.get("ABTLOTCODE")),
            "common_ownership": _string(attributes.get("COL")),
            "recordation_date": _arcgis_datetime(
                attributes.get("RECORDATION_DT")
            ),
            "created_date": _arcgis_datetime(
                attributes.get("CREATED_DATE")
            ),
            "last_edited_date": _arcgis_datetime(
                attributes.get("LAST_EDITED_DATE")
            ),
            "historic_flag": attributes.get("ISHISTORIC"),
            "record": _string(attributes.get("RECORD")),
            "retiring_record": _string(
                attributes.get("RETIRING_RECORD")
            ),
        },
        "physical": {
            "land_area": attributes.get("LANDAREA"),
            "stated_area": attributes.get("STATEDAREA"),
            "stated_area_unit": attributes.get("STATEDAREAUNIT"),
            "calculated_area": attributes.get("CALCULATEDAREA"),
            "shape_area": attributes.get("SHAPE.AREA"),
            "shape_length": attributes.get("SHAPE.LEN"),
        },
        "source_extract_date": _arcgis_datetime(
            attributes.get("EXTRACTDAT")
        ),
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINTS[
            component.key
        ],
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }
    if geometry is not None:
        record.update(
            {
                "geometry": geometry,
                "geometry_format": "esri_json",
                "geometry_crs": f"EPSG:{geometry_crs}",
                "source_geometry_crs": SOURCE_NATIVE_CRS,
            }
        )
    return record


def _sale_record(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError("CAMA sale feature lacks attributes")
    attributes = dict(attributes_value)
    ssl, raw_ssl = _canonical_ssl(attributes)
    native_id = _stable_native_id(SALES, attributes)
    return {
        "record_type": SALES.record_kind,
        "canonical_ref": canonical_property_ref(
            SALES.source_id,
            JURISDICTION_GEOID,
            "sale",
            native_id,
        ),
        "source_id": SALES.source_id,
        "dataset_id": SOURCE_METADATA["sales"].dataset_id,
        "component": "sales",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "jurisdiction_geoid": JURISDICTION_GEOID,
            "locality": "District of Columbia",
        },
        "native_id": native_id,
        "native_parcel_id": ssl,
        "ssl": {"normalized": ssl, "raw": raw_ssl},
        "object_id": attributes.get("OBJECTID"),
        "row_number": attributes.get("ROW_NUMBER"),
        "sale": {
            "sale_date": _arcgis_datetime(attributes.get("SALE_DATE")),
            "consideration": attributes.get("SALE_PRICE"),
            "qualified": _string(attributes.get("QUALIFIED")),
            "sale_code": _string(attributes.get("SALE_CODE")),
            "current_owner_flag": _string(
                attributes.get("SALE_CURR_OWNER")
            ),
            "currency": "USD",
        },
        "source_last_modified": _arcgis_datetime(
            attributes.get("GIS_LAST_MOD_DTTM")
        ),
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINTS["sales"],
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }


def _survey_record(
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
) -> dict[str, Any]:
    attributes_value = feature.get("attributes")
    if not isinstance(attributes_value, Mapping):
        raise ValueError("Surveyor document feature lacks attributes")
    attributes = dict(attributes_value)
    ssl, raw_ssl = _canonical_ssl(attributes)
    native_id = _stable_native_id(SURVEYS, attributes)
    document_url = _string(attributes.get("FILENETLINK"))
    return {
        "record_type": SURVEYS.record_kind,
        "canonical_ref": canonical_property_ref(
            SURVEYS.source_id,
            JURISDICTION_GEOID,
            "survey_document",
            native_id,
        ),
        "source_id": SURVEYS.source_id,
        "dataset_id": SOURCE_METADATA["surveys"].dataset_id,
        "component": "surveys",
        "jurisdiction": {
            "state_code": STATE_CODE,
            "jurisdiction_geoid": JURISDICTION_GEOID,
            "locality": "District of Columbia",
        },
        "native_id": native_id,
        "native_parcel_id": ssl,
        "ssl": {
            "normalized": ssl,
            "raw": raw_ssl,
            "square": _string(attributes.get("SQUARE")),
            "suffix": _string(attributes.get("SUFFIX")),
            "lot": _string(attributes.get("LOT")),
        },
        "object_id": attributes.get("OBJECTID"),
        "document": {
            "document_guid": _string(attributes.get("DOCGUID")),
            "document_type": _string(attributes.get("DOCUMENTTYPE")),
            "subdocument_type": _string(
                attributes.get("SUBDOCUMENTTYPE")
            ),
            "book_number": _string(attributes.get("BOOKNUMBER")),
            "page_number": _string(attributes.get("PAGENUMBER")),
            "book_name": _string(attributes.get("BOOKNAME")),
            "active_state": _string(attributes.get("ISACTIVE")),
            "viewer_url": document_url,
        },
        "representations": (
            [
                {
                    "kind": "official_document_viewer",
                    "source_id": SURVEYS.source_id,
                    "url": document_url,
                    "document_guid": native_id,
                }
            ]
            if document_url
            else []
        ),
        "source_last_modified": _arcgis_datetime(
            attributes.get("GIS_LAST_MOD_DTTM")
        ),
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINTS[
            "surveys"
        ],
        "response_schema_fingerprint": response_schema_fingerprint,
        "raw_attributes": attributes,
    }


def _normalize_feature(
    component: Component,
    feature: Mapping[str, Any],
    *,
    response_schema_fingerprint: str,
    geometry_crs: int,
) -> dict[str, Any]:
    if component.key in {"assessment", "geometry"}:
        return _assessment_record(
            component,
            feature,
            response_schema_fingerprint=response_schema_fingerprint,
            geometry_crs=geometry_crs,
        )
    if component.key == "sales":
        return _sale_record(
            feature,
            response_schema_fingerprint=response_schema_fingerprint,
        )
    return _survey_record(
        feature,
        response_schema_fingerprint=response_schema_fingerprint,
    )


def _where_assessment(field: str, selector: str) -> str:
    if field == "ssl":
        return _ssl_where(selector, component_fields=True)
    cleaned = _sql_text(selector, field)
    if field == "owner":
        return (
            f"(OWNERNAME LIKE '%{cleaned}%' OR "
            f"OWNNAME2 LIKE '%{cleaned}%')"
        )
    if field == "address":
        return (
            f"(PREMISEADD LIKE '%{cleaned}%' OR "
            f"ADDRESS1 LIKE '%{cleaned}%' OR "
            f"ADDRESS2 LIKE '%{cleaned}%' OR "
            f"CITYSTZIP LIKE '%{cleaned}%')"
        )
    if field == "instrument":
        return f"INST_NO LIKE '%{cleaned}%'"
    raise ValueError("assessment field must be ssl, owner, address, or instrument")


def _where_geometry(field: str, selector: str) -> str:
    if field == "ssl":
        return _ssl_where(selector, component_fields=True)
    cleaned = _sql_text(selector, field)
    if field == "owner":
        return (
            f"(OWNERNAME LIKE '%{cleaned}%' OR "
            f"OWNNAME2 LIKE '%{cleaned}%')"
        )
    if field == "address":
        return (
            f"(PREMISEADD LIKE '%{cleaned}%' OR "
            f"ADDRESS1 LIKE '%{cleaned}%' OR "
            f"ADDRESS2 LIKE '%{cleaned}%' OR "
            f"CITYSTZIP LIKE '%{cleaned}%')"
        )
    if field == "instrument":
        return f"INSTNO LIKE '%{cleaned}%'"
    if field == "objectid":
        try:
            object_id = int(selector)
        except ValueError as error:
            raise ValueError("OBJECTID must be an integer") from error
        if object_id <= 0:
            raise ValueError("OBJECTID must be positive")
        return f"OBJECTID={object_id}"
    raise ValueError(
        "geometry field must be ssl, owner, address, instrument, or objectid"
    )


def _where_sales(
    selector: str,
    *,
    start_date: str | None,
    end_date: str | None,
) -> str:
    conditions = [_ssl_where(selector, component_fields=False)]
    if start_date:
        conditions.append(
            f"SALE_DATE >= DATE '{_date_literal(start_date, 'start date')}'"
        )
    if end_date:
        conditions.append(
            f"SALE_DATE <= DATE '{_date_literal(end_date, 'end date')}'"
        )
    return " AND ".join(conditions)


def _where_surveys(field: str, selector: str) -> str:
    if field == "ssl":
        return _ssl_where(selector, component_fields=True)
    cleaned = _sql_text(selector, field)
    if field == "document":
        return f"DOCGUID='{cleaned}'"
    if field == "type":
        return (
            f"(DOCUMENTTYPE LIKE '%{cleaned}%' OR "
            f"SUBDOCUMENTTYPE LIKE '%{cleaned}%')"
        )
    if field == "book":
        return (
            f"(BOOKNUMBER LIKE '%{cleaned}%' OR "
            f"BOOKNAME LIKE '%{cleaned}%')"
        )
    raise ValueError("survey field must be ssl, document, type, or book")


def _spatial_parameters(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "point":
        geometry = f"{args.longitude},{args.latitude}"
        geometry_type = "esriGeometryPoint"
    elif args.command == "bbox":
        if args.xmin >= args.xmax or args.ymin >= args.ymax:
            raise ValueError("bbox minimums must be less than maximums")
        geometry = f"{args.xmin},{args.ymin},{args.xmax},{args.ymax}"
        geometry_type = "esriGeometryEnvelope"
    else:
        return {}
    return {
        "geometry": geometry,
        "geometryType": geometry_type,
        "inSR": DEFAULT_OUTPUT_CRS,
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": args.out_sr,
    }


def _selection(
    args: argparse.Namespace,
) -> tuple[Component, str, dict[str, Any], bool]:
    command = args.command
    if command == "assessment":
        return ITSPE, _where_assessment(args.field, args.query), {}, False
    if command == "geometry":
        return (
            OWNER_POLYGONS,
            _where_geometry(args.field, args.query),
            {"outSR": args.out_sr},
            args.geometry,
        )
    if command == "sales":
        return (
            SALES,
            _where_sales(
                args.ssl,
                start_date=args.start_date,
                end_date=args.end_date,
            ),
            {},
            False,
        )
    if command == "surveys":
        return SURVEYS, _where_surveys(args.field, args.query), {}, False
    if command in {"point", "bbox"}:
        return OWNER_POLYGONS, "1=1", _spatial_parameters(args), True
    if command == "probe":
        component = _component(args.component)
        if component.key == "surveys":
            return (
                component,
                f"DOCGUID='{PROBE_SURVEY_GUID}'",
                {},
                False,
            )
        return (
            component,
            f"SSL='{PROBE_SSL}'",
            {"outSR": args.out_sr} if component.has_geometry else {},
            component.has_geometry,
        )
    raise ValueError(f"unsupported command: {command}")


def _access_contract(
    args: argparse.Namespace,
    component: Component,
) -> dict[str, Any]:
    catalog = ensure_catalog_source(
        component.source_id,
        db_path=Path(
            getattr(args, "catalog_db", str(DEFAULT_CATALOG_DB_PATH))
        ).expanduser(),
        config_path=Path(
            getattr(
                args,
                "catalog_config",
                str(DEFAULT_CATALOG_CONFIG_PATH),
            )
        ).expanduser(),
    )
    return catalog.require_machine_acquisition(component.source_id)


def _client(
    args: argparse.Namespace,
    component: Component,
    access_contract: Mapping[str, Any],
) -> DCArcGISClient:
    limits = access_contract.get("limits") or {}
    page_size = min(args.page_size, SOURCE_MAX_PAGE_SIZE)
    reviewed_page_size = limits.get("maximum_page_size")
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    return DCArcGISClient(
        component.layer_url,
        page_size=page_size,
        max_records=args.max_records,
        timeout=args.timeout,
        minimum_interval=minimum_interval,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )


def _build_query(
    component: Component,
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA[component.key],
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=dict(parameters),
            requested_limit=limit,
            cursor=cursor,
        ),
    )


def _access_failure(
    query: PublicRecordsQuery,
    error: Exception,
    *,
    warnings: Sequence[str],
) -> PublicRecordsResult:
    if isinstance(error, AcquisitionUnavailableError):
        decision = error.decision
        status = ResultStatus(acquisition_result_status(decision))
        public_error = PublicRecordsError(
            code=str(
                decision.get("reason_code")
                or "acquisition_route_unavailable"
            ),
            message=str(decision.get("reason") or error),
            category="access",
            retryable=False,
            details=decision,
        )
    else:
        status = ResultStatus.UNAVAILABLE
        public_error = PublicRecordsError(
            code="catalog_unavailable",
            message=str(error),
            category="catalog",
            retryable=False,
        )
    return PublicRecordsResult.failure(
        query,
        status,
        [public_error],
        warnings=warnings,
    )


def _metadata_record(
    component: Component,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    fields = payload.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(field, Mapping) for field in fields
    ):
        raise SourceSchemaError(
            "DCGIS metadata is missing its field definitions",
            url=component.layer_url,
        )
    declared = [
        {
            "name": field.get("name"),
            "alias": field.get("alias"),
            "type": field.get("type"),
        }
        for field in fields
    ]
    return {
        "record_type": "source_metadata",
        "source_id": component.source_id,
        "component": component.key,
        "layer_id": component.layer_id,
        "name": payload.get("name"),
        "type": payload.get("type"),
        "description": payload.get("description"),
        "geometry_type": payload.get("geometryType"),
        "capabilities": payload.get("capabilities"),
        "max_record_count": payload.get("maxRecordCount"),
        "supported_query_formats": payload.get("supportedQueryFormats"),
        "supports_statistics": payload.get("supportsStatistics"),
        "advanced_query_capabilities": payload.get(
            "advancedQueryCapabilities"
        ),
        "source_spatial_reference": payload.get(
            "sourceSpatialReference"
        ),
        "extent": payload.get("extent"),
        "fields": declared,
        "field_names": [
            str(field["name"]) for field in declared if field.get("name")
        ],
        "schema_fingerprint": schema_fingerprint(
            {"kind": "arcgis_declared", "fields": declared}
        ),
        "relationships": payload.get("relationships") or [],
    }


def _execute_metadata_or_count(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None,
    client: DCArcGISClient | None,
) -> PublicRecordsResult:
    component = _component(args.component)
    operation = args.command
    query = _build_query(
        component,
        operation,
        {"component": component.key},
        limit=1,
        cursor=None,
    )
    warnings = WARNINGS_BY_COMPONENT[component.key]
    try:
        access = (
            access_decision
            if access_decision is not None
            else _access_contract(args, component)
        )
        source_client = client or _client(args, component, access)
        if operation == "metadata":
            record = _metadata_record(
                component, source_client.fetch_metadata()
            )
        else:
            record = {
                "record_type": "source_count",
                "source_id": component.source_id,
                "component": component.key,
                "where": "1=1",
                "count": source_client.fetch_count(),
            }
        result = PublicRecordsResult.success(query, [record], warnings=warnings)
    except (AcquisitionUnavailableError, CatalogError, OSError) as error:
        result = _access_failure(query, error, warnings=warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
    except (TypeError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="metadata_normalization_failed",
                    message=str(error),
                    category="source_schema",
                    retryable=False,
                )
            ],
            warnings=warnings,
        )
    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), component.source_id, result_count)
    return result


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    client: DCArcGISClient | None = None,
) -> PublicRecordsResult:
    if args.command in {"metadata", "count"}:
        return _execute_metadata_or_count(
            args,
            access_decision=access_decision,
            client=client,
        )
    component, where, parameters, return_geometry = _selection(args)
    limit = 1 if args.command == "probe" else args.limit
    if args.max_records is not None:
        limit = (
            min(limit, args.max_records)
            if limit is not None
            else args.max_records
        )
    query_parameters = {
        "component": component.key,
        "where": where,
        "return_geometry": return_geometry,
        "out_sr": args.out_sr if component.has_geometry else None,
    }
    query = _build_query(
        component,
        args.command,
        query_parameters,
        limit=limit,
        cursor=args.cursor,
    )
    warnings = WARNINGS_BY_COMPONENT[component.key]
    try:
        access = (
            access_decision
            if access_decision is not None
            else _access_contract(args, component)
        )
        source_client = client or _client(args, component, access)
        order = (
            "SALE_DATE DESC,OBJECTID ASC"
            if component.key == "sales"
            else "OBJECTID ASC"
        )
        query_parameters_arcgis = {
            **parameters,
            "orderByFields": order,
        }
        fetched = source_client.query(
            where=where,
            out_fields=OUT_FIELDS_BY_COMPONENT[component.key],
            parameters=query_parameters_arcgis,
            requested_limit=limit,
            cursor=args.cursor,
            return_geometry=return_geometry,
        )
        records = [
            _normalize_feature(
                component,
                feature,
                response_schema_fingerprint=fetched.schema_fingerprint,
                geometry_crs=args.out_sr,
            )
            for feature in fetched.records
        ]
        combined_warnings = (*warnings, *fetched.warnings)
        if fetched.truncated_by_cap:
            result = PublicRecordsResult(
                query=query,
                status=ResultStatus.PARTIAL,
                records=records,
                next_cursor=fetched.next_cursor,
                warnings=combined_warnings,
            )
        else:
            result = PublicRecordsResult.success(
                query,
                records,
                next_cursor=fetched.next_cursor,
                warnings=combined_warnings,
            )
    except (AcquisitionUnavailableError, CatalogError, OSError) as error:
        result = _access_failure(query, error, warnings=warnings)
    except PublicRecordsHTTPError as error:
        result = failure_result(query, error, warnings=warnings)
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
            warnings=warnings,
        )

    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(canonical_json(query.to_dict()), component.source_id, result_count)
    return result


def _source_rows() -> list[dict[str, Any]]:
    return [
        {
            "component": component.key,
            "source": SOURCE_METADATA[component.key].to_dict(),
            "layer_url": component.layer_url,
            "record_kind": component.record_kind,
            "has_geometry": component.has_geometry,
            "stable_keys": list(component.stable_keys),
            "warnings": list(WARNINGS_BY_COMPONENT[component.key]),
        }
        for component in COMPONENTS.values()
    ]


def _emit_sources(args: argparse.Namespace) -> None:
    rows = _source_rows()
    if write_output(rows, args, summary=f"DC property sources: {len(rows)}"):
        return
    if args.json_out:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    for row in rows:
        source = row["source"]
        print(
            f"{row['component']}: {source['source_id']} | "
            f"{row['layer_url']}"
        )


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"DC property {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"DC property {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if record.get("record_type") == "source_count":
            print(f"  {record['component']}: {record['count']}")
            continue
        if record.get("record_type") == "source_metadata":
            print(
                f"  {record['component']}: {record.get('name')} | "
                f"{len(record.get('fields') or [])} fields"
            )
            continue
        print(
            f"  {record.get('source_id')} | "
            f"{record.get('native_parcel_id') or record.get('native_id')}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    geometry: bool = False,
) -> None:
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--cursor")
    if geometry:
        parser.add_argument(
            "--geometry",
            action="store_true",
            help="Return source geometry",
        )
    parser.add_argument(
        "--out-sr",
        type=_positive_int,
        default=DEFAULT_OUTPUT_CRS,
        help="ArcGIS output spatial reference",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=DEFAULT_PAGE_SIZE,
    )
    parser.add_argument("--max-records", type=_positive_int)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=0.0,
    )
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
    parser.add_argument(
        "--catalog-db",
        default=str(DEFAULT_CATALOG_DB_PATH),
    )
    parser.add_argument(
        "--catalog-config",
        default=str(DEFAULT_CATALOG_CONFIG_PATH),
    )
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query official District of Columbia assessment, tax, parcel "
            "geometry, property-sale, and survey-document components"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser("sources", help="List source components")
    add_output_args(sources)

    for command in ("metadata", "count"):
        command_parser = subparsers.add_parser(
            command,
            help=f"Fetch component {command}",
        )
        command_parser.add_argument("component", choices=sorted(COMPONENTS))
        _add_runtime_arguments(command_parser)

    assessment = subparsers.add_parser(
        "assessment",
        help="Search the full ITSPE assessment and tax extract",
    )
    assessment.add_argument("query")
    assessment.add_argument(
        "--field",
        choices=("ssl", "owner", "address", "instrument"),
        default="ssl",
    )
    _add_runtime_arguments(assessment)

    geometry = subparsers.add_parser(
        "geometry",
        help="Search common-ownership geometry and its daily ITSPE view",
    )
    geometry.add_argument("query")
    geometry.add_argument(
        "--field",
        choices=("ssl", "owner", "address", "instrument", "objectid"),
        default="ssl",
    )
    _add_runtime_arguments(geometry, geometry=True)

    point = subparsers.add_parser(
        "point",
        help="Find common-ownership polygons intersecting a longitude/latitude",
    )
    point.add_argument("longitude", type=float)
    point.add_argument("latitude", type=float)
    _add_runtime_arguments(point, geometry=True)

    bbox = subparsers.add_parser(
        "bbox",
        help="Find common-ownership polygons intersecting a WGS84 bounding box",
    )
    bbox.add_argument("xmin", type=float)
    bbox.add_argument("ymin", type=float)
    bbox.add_argument("xmax", type=float)
    bbox.add_argument("ymax", type=float)
    _add_runtime_arguments(bbox, geometry=True)

    sales = subparsers.add_parser(
        "sales",
        help="Fetch CAMA property-sale observations for an SSL",
    )
    sales.add_argument("ssl")
    sales.add_argument("--start-date")
    sales.add_argument("--end-date")
    _add_runtime_arguments(sales)

    surveys = subparsers.add_parser(
        "surveys",
        help="Search the Surveyor Document System",
    )
    surveys.add_argument("query")
    surveys.add_argument(
        "--field",
        choices=("ssl", "document", "type", "book"),
        default="ssl",
    )
    _add_runtime_arguments(surveys)

    probe = subparsers.add_parser(
        "probe",
        help="Run one bounded component sentinel query",
    )
    probe.add_argument("component", choices=sorted(COMPONENTS))
    _add_runtime_arguments(probe, geometry=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "sources":
        _emit_sources(args)
        return 0
    if args.timeout <= 0:
        raise SystemExit("timeout must be positive")
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
