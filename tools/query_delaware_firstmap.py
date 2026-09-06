#!/usr/bin/env python3
"""Query Delaware FirstMap's statewide parcel polygons and centroids.

FirstMap publishes two complementary layers in one official FeatureServer:

- layer 0: one statewide parcel-polygon feature per usable county/PIN key;
- layer 1: parcel centroids with geographic routing attributes.

The polygon layer has no owner or address fields. The centroid layer is a
useful enrichment, but it is not a complete one-to-one copy of the polygon
layer. Records are therefore joined only on a nonblank county plus PIN. Source
features without a usable PIN are preserved under an explicit OBJECTID-based
feature identity rather than being assigned a parcel identifier.

Usage:
    uv run python tools/query_delaware_firstmap.py pin 1001300033
    uv run python tools/query_delaware_firstmap.py search 013 --county "New Castle"
    uv run python tools/query_delaware_firstmap.py list --county Kent --max-records 5000
    uv run python tools/query_delaware_firstmap.py objectid 18356825 --layer polygon
    uv run python tools/query_delaware_firstmap.py probe --output /tmp/firstmap.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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
        RetryPolicy,
        failure_result,
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
        RetryPolicy,
        failure_result,
    )
    from public_records_store import canonical_property_ref
    from seed_public_records_catalog import (
        DEFAULT_CONFIG_PATH as DEFAULT_CATALOG_CONFIG_PATH,
        ensure_catalog_source,
    )


SOURCE_ID = "us-de-firstmap-parcels"
SERVICE_URL = (
    "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/"
    "PlanningCadastre/DE_StateParcels/FeatureServer"
)
POLYGON_LAYER_URL = f"{SERVICE_URL}/0"
CENTROID_LAYER_URL = f"{SERVICE_URL}/1"

POLYGON_LAYER = "polygon"
CENTROID_LAYER = "centroid"
LAYER_URLS = {
    POLYGON_LAYER: POLYGON_LAYER_URL,
    CENTROID_LAYER: CENTROID_LAYER_URL,
}
POLYGON_FIELDS = (
    "OBJECTID",
    "PIN",
    "ACRES",
    "COUNTY",
    "UPDATED",
    "Shape__Area",
    "Shape__Length",
)
CENTROID_FIELDS = (
    "OBJECTID",
    "PIN",
    "SUM_ACRES",
    "ORIG_FID",
    "SENATE_DISTRICT",
    "REPRESENTATIVE_DISTRICT",
    "HUC_12",
    "SCHOOL_DISTRICT",
    "COUNTY",
    "TOWN",
    "EDRD",
    "CENSUSBLOCK",
    "WASTEWATERCPCN",
    "WATERCPCN",
    "ERPA",
    "COMMUNITYNAME",
    "Z",
    "X",
    "Y",
    "LONGITUDE",
    "LATITUDE",
    "LAST_UPDATED",
    "ZIP_CODE",
)
LAYER_FIELDS = {
    POLYGON_LAYER: POLYGON_FIELDS,
    CENTROID_LAYER: CENTROID_FIELDS,
}

COUNTIES = {
    "kent": ("Kent", "10001"),
    "newcastle": ("New Castle", "10003"),
    "sussex": ("Sussex", "10005"),
}
COUNTY_GEOIDS = {
    county_name.casefold(): county_geoid
    for county_name, county_geoid in COUNTIES.values()
}

PROBE_COUNTY = "New Castle"
PROBE_PIN = "1001300033"

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Delaware FirstMap Statewide Parcels",
    source_role="parcel_discovery_geometry_routing",
    base_url=SERVICE_URL,
    dataset_id="PlanningCadastre/DE_StateParcels",
    metadata={
        "authority": "State of Delaware",
        "operator": "Delaware FirstMap",
        "coverage": "Statewide current parcel geometry",
        "polygon_layer": POLYGON_LAYER_URL,
        "centroid_layer": CENTROID_LAYER_URL,
    },
)

SOURCE_WARNINGS = (
    "FirstMap is a current parcel-geometry source and does not publish owner, situs-address, assessment, or recorded-title fields in these layers.",
    "The centroid layer is an enrichment layer and is not a complete one-to-one copy of the parcel-polygon layer.",
)
BLANK_PIN_CAVEAT = (
    "This source feature has no usable PIN. It is preserved by its layer and "
    "OBJECTID only and is not asserted to be a canonical parcel identity."
)


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


def _county_key(value: str) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _county(value: str | None, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError("county is required")
        return None
    cleaned = _county_key(value)
    try:
        return COUNTIES[cleaned][0]
    except KeyError as error:
        names = ", ".join(item[0] for item in COUNTIES.values())
        raise ValueError(f"Delaware county must be one of: {names}") from error


def _county_geoid(county_name: str | None) -> str | None:
    if county_name is None:
        return None
    return COUNTY_GEOIDS.get(county_name.casefold())


def _sql_literal(value: str, field_name: str) -> str:
    cleaned = " ".join(str(value).replace("\x00", "").split()).strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be blank")
    return cleaned.replace("'", "''")


def _object_id(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("OBJECTID must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("OBJECTID must be a positive integer") from error
    if parsed <= 0:
        raise ValueError("OBJECTID must be a positive integer")
    return parsed


def _arcgis_timestamp(value: Any) -> str | None:
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


def _where_pin(pin: str, county_name: str | None = None) -> str:
    expression = f"PIN='{_sql_literal(pin, 'PIN')}'"
    if county_name:
        expression = (
            f"({expression}) AND COUNTY='{_sql_literal(county_name, 'county')}'"
        )
    return expression


def _where_search(term: str, county_name: str) -> str:
    return (
        f"COUNTY='{_sql_literal(county_name, 'county')}' AND "
        f"PIN LIKE '%{_sql_literal(term, 'search term')}%'"
    )


def _where_list(county_name: str) -> str:
    return f"COUNTY='{_sql_literal(county_name, 'county')}'"


def _where_objectid(value: Any) -> str:
    return f"OBJECTID={_object_id(value)}"


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


def _clients(
    args: argparse.Namespace,
    access_contract: Mapping[str, Any],
) -> dict[str, ArcGISRESTClient]:
    limits = access_contract.get("limits") or {}
    page_size = args.page_size
    reviewed_page_size = limits.get("maximum_page_size")
    if reviewed_page_size is not None:
        page_size = min(page_size, int(reviewed_page_size))
    minimum_interval = max(
        args.minimum_interval,
        float(limits.get("minimum_interval_seconds") or 0),
    )
    retry_policy = RetryPolicy(max_attempts=args.max_attempts)
    common = {
        "page_size": page_size,
        "max_records": args.max_records,
        "timeout": args.timeout,
        "minimum_interval": minimum_interval,
        "retry_policy": retry_policy,
    }
    return {
        layer: ArcGISRESTClient(layer_url, **common)
        for layer, layer_url in LAYER_URLS.items()
    }


def _attributes(feature: Mapping[str, Any]) -> dict[str, Any]:
    raw = feature.get("attributes")
    if not isinstance(raw, Mapping):
        raise ValueError("FirstMap feature is missing an attributes object")
    return dict(raw)


def _canonical_county(raw_county: Any) -> str | None:
    text = " ".join(str(raw_county or "").split()).strip()
    if not text:
        return None
    known = COUNTIES.get(_county_key(text))
    return known[0] if known else text


def _feature_identity(
    feature: Mapping[str, Any],
    *,
    layer: str,
    schema_fingerprint: str,
    geometry_spatial_reference: int,
) -> dict[str, Any]:
    attributes = _attributes(feature)
    object_id = _object_id(attributes.get("OBJECTID"))
    pin = str(attributes.get("PIN") or "").strip() or None
    county_name = _canonical_county(attributes.get("COUNTY"))
    normalized: dict[str, Any] = {
        "layer": layer,
        "object_id": object_id,
        "source_feature_id": f"{layer}:OBJECTID:{object_id}",
        "source_url": LAYER_URLS[layer],
        "county": county_name,
        "pin": pin,
        "schema_fingerprint": schema_fingerprint,
        "raw_attributes": attributes,
    }
    if layer == POLYGON_LAYER:
        normalized.update(
            {
                "acres": attributes.get("ACRES"),
                "shape_area": attributes.get("Shape__Area"),
                "shape_length": attributes.get("Shape__Length"),
                "source_updated_at": _arcgis_timestamp(attributes.get("UPDATED")),
            }
        )
    else:
        normalized.update(
            {
                "sum_acres": attributes.get("SUM_ACRES"),
                "origin_feature_id": attributes.get("ORIG_FID"),
                "longitude": attributes.get("LONGITUDE"),
                "latitude": attributes.get("LATITUDE"),
                "zip_code": attributes.get("ZIP_CODE"),
                "census_block": attributes.get("CENSUSBLOCK"),
                "town": attributes.get("TOWN"),
                "community_name": attributes.get("COMMUNITYNAME"),
                "senate_district": attributes.get("SENATE_DISTRICT"),
                "representative_district": attributes.get(
                    "REPRESENTATIVE_DISTRICT"
                ),
                "school_district": attributes.get("SCHOOL_DISTRICT"),
                "huc_12": attributes.get("HUC_12"),
                "source_updated_at": _arcgis_timestamp(
                    attributes.get("LAST_UPDATED")
                ),
            }
        )
    if "geometry" in feature:
        normalized["geometry"] = feature.get("geometry")
        normalized["geometry_spatial_reference"] = geometry_spatial_reference
    return normalized


def _join_key(feature: Mapping[str, Any]) -> tuple[str, str] | None:
    county_name = str(feature.get("county") or "").strip()
    pin = str(feature.get("pin") or "").strip()
    if not county_name or not pin:
        return None
    return county_name.casefold(), pin


def _canonical_record(
    polygon_features: Sequence[Mapping[str, Any]],
    centroid_features: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_features = [*polygon_features, *centroid_features]
    if not source_features:
        raise ValueError("cannot normalize an empty FirstMap feature group")
    first = source_features[0]
    county_name = str(first.get("county") or "").strip() or None
    pin = str(first.get("pin") or "").strip() or None
    county_geoid = _county_geoid(county_name)

    if pin and county_name:
        canonical_native_id = (
            pin if county_geoid else f"{county_name}:{pin}"
        )
        canonical_ref = canonical_property_ref(
            SOURCE_ID,
            county_geoid or "10",
            "parcel",
            canonical_native_id,
        )
        identity = {
            "basis": "county_and_pin",
            "county": county_name,
            "pin": pin,
            "joinable": True,
        }
        identity_caveat = None
    else:
        if len(source_features) != 1:
            raise ValueError("unjoinable FirstMap features were grouped together")
        layer = str(first["layer"])
        object_id = _object_id(first["object_id"])
        canonical_ref = canonical_property_ref(
            SOURCE_ID,
            county_geoid or "10",
            "parcel_feature",
            f"{layer}:OBJECTID:{object_id}",
        )
        identity = {
            "basis": "source_object_id_fallback",
            "county": county_name,
            "pin": None,
            "layer": layer,
            "object_id": object_id,
            "joinable": False,
        }
        identity_caveat = BLANK_PIN_CAVEAT

    polygon_values = sorted(
        (dict(value) for value in polygon_features),
        key=lambda value: value["object_id"],
    )
    centroid_values = sorted(
        (dict(value) for value in centroid_features),
        key=lambda value: value["object_id"],
    )
    record: dict[str, Any] = {
        "canonical_ref": canonical_ref,
        "source_id": SOURCE_ID,
        "jurisdiction": {
            "state_code": "DE",
            "state_fips": "10",
            "county_name": county_name,
            "county_geoid": county_geoid,
        },
        "native_parcel_id": pin,
        "identity": identity,
        "identity_caveat": identity_caveat,
        "polygon_features": polygon_values,
        "centroid_features": centroid_values,
        "source_feature_ids": [
            value["source_feature_id"]
            for value in sorted(
                source_features,
                key=lambda value: (value["layer"], value["object_id"]),
            )
        ],
        "schema_fingerprints": {
            layer: sorted(
                {
                    str(value["schema_fingerprint"])
                    for value in source_features
                    if value["layer"] == layer
                }
            )
            for layer in (POLYGON_LAYER, CENTROID_LAYER)
            if any(value["layer"] == layer for value in source_features)
        },
    }
    if polygon_values:
        record["acres"] = polygon_values[0].get("acres")
    if centroid_values:
        centroid = centroid_values[0]
        record["centroid"] = {
            key: centroid.get(key)
            for key in (
                "longitude",
                "latitude",
                "zip_code",
                "census_block",
                "town",
                "community_name",
            )
        }
        record["routing"] = {
            key: centroid.get(key)
            for key in (
                "senate_district",
                "representative_district",
                "school_district",
                "huc_12",
            )
        }
    return record


def _normalize_features(
    features_by_layer: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    schema_fingerprints: Mapping[str, str],
    geometry_spatial_reference: int,
) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[str, ...],
        dict[str, list[dict[str, Any]]],
    ] = {}
    for layer in (POLYGON_LAYER, CENTROID_LAYER):
        for raw_feature in features_by_layer.get(layer, ()):
            feature = _feature_identity(
                raw_feature,
                layer=layer,
                schema_fingerprint=schema_fingerprints[layer],
                geometry_spatial_reference=geometry_spatial_reference,
            )
            join_key = _join_key(feature)
            if join_key is None:
                group_key = (
                    "feature",
                    layer,
                    str(feature["object_id"]),
                )
            else:
                group_key = ("parcel", *join_key)
            bucket = grouped.setdefault(
                group_key,
                {POLYGON_LAYER: [], CENTROID_LAYER: []},
            )
            bucket[layer].append(feature)

    records = [
        _canonical_record(
            bucket[POLYGON_LAYER],
            bucket[CENTROID_LAYER],
        )
        for bucket in grouped.values()
    ]
    return sorted(
        records,
        key=lambda record: (
            str(record["jurisdiction"].get("county_name") or ""),
            str(record.get("native_parcel_id") or ""),
            record["canonical_ref"],
        ),
    )


def _query_layer(
    args: argparse.Namespace,
    clients: Mapping[str, ArcGISRESTClient],
    *,
    layer: str,
    where: str,
    cursor: str | None = None,
) -> PaginatedFetch:
    parameters: dict[str, Any] = {"orderByFields": "OBJECTID ASC"}
    if args.geometry:
        parameters["outSR"] = args.out_sr
    return clients[layer].query(
        where=where,
        out_fields=LAYER_FIELDS[layer],
        parameters=parameters,
        requested_limit=None,
        cursor=cursor,
        return_geometry=args.geometry,
    )


def _fetch_records(
    args: argparse.Namespace,
    clients: Mapping[str, ArcGISRESTClient],
) -> tuple[list[dict[str, Any]], list[PaginatedFetch], str | None]:
    command = args.command
    fetches: list[PaginatedFetch] = []
    features_by_layer: dict[str, list[Mapping[str, Any]]] = {
        POLYGON_LAYER: [],
        CENTROID_LAYER: [],
    }
    fingerprints: dict[str, str] = {}
    next_cursor: str | None = None

    if command in {"pin", "probe"}:
        pin = PROBE_PIN if command == "probe" else args.pin
        county_name = PROBE_COUNTY if command == "probe" else _county(args.county)
        where = _where_pin(pin, county_name)
        for layer in (POLYGON_LAYER, CENTROID_LAYER):
            fetched = _query_layer(
                args,
                clients,
                layer=layer,
                where=where,
            )
            fetches.append(fetched)
            features_by_layer[layer].extend(fetched.records)
            fingerprints[layer] = fetched.schema_fingerprint
    elif command in {"search", "list"}:
        layer = args.layer
        county_name = _county(args.county, required=True)
        where = (
            _where_search(args.term, county_name)
            if command == "search"
            else _where_list(county_name)
        )
        fetched = _query_layer(
            args,
            clients,
            layer=layer,
            where=where,
            cursor=args.cursor,
        )
        fetches.append(fetched)
        features_by_layer[layer].extend(fetched.records)
        fingerprints[layer] = fetched.schema_fingerprint
        next_cursor = fetched.next_cursor
    elif command == "objectid":
        layer = args.layer
        complement = (
            CENTROID_LAYER if layer == POLYGON_LAYER else POLYGON_LAYER
        )
        fetched = _query_layer(
            args,
            clients,
            layer=layer,
            where=_where_objectid(args.objectid),
        )
        fetches.append(fetched)
        features_by_layer[layer].extend(fetched.records)
        fingerprints[layer] = fetched.schema_fingerprint

        join_keys: set[tuple[str, str]] = set()
        for raw_feature in fetched.records:
            feature = _feature_identity(
                raw_feature,
                layer=layer,
                schema_fingerprint=fetched.schema_fingerprint,
                geometry_spatial_reference=args.out_sr,
            )
            join_key = _join_key(feature)
            if join_key is not None:
                join_keys.add(join_key)
        for county_key, pin in sorted(join_keys):
            county_name = _canonical_county(county_key)
            complement_fetch = _query_layer(
                args,
                clients,
                layer=complement,
                where=_where_pin(pin, county_name),
            )
            fetches.append(complement_fetch)
            features_by_layer[complement].extend(complement_fetch.records)
            fingerprints[complement] = complement_fetch.schema_fingerprint
    else:
        raise ValueError(f"unsupported FirstMap operation: {command}")

    records = _normalize_features(
        features_by_layer,
        schema_fingerprints=fingerprints,
        geometry_spatial_reference=args.out_sr,
    )
    if command == "probe":
        _validate_probe(records, features_by_layer)
        records[0]["probe"] = {
            "sentinel": {
                "county": PROBE_COUNTY,
                "pin": PROBE_PIN,
            },
            "polygon_feature_count": 1,
            "centroid_feature_count": 1,
            "schema_fingerprints": dict(fingerprints),
        }
    return records, fetches, next_cursor


def _validate_probe(
    records: Sequence[Mapping[str, Any]],
    features_by_layer: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    if len(features_by_layer[POLYGON_LAYER]) != 1:
        raise ValueError("FirstMap polygon sentinel is missing or non-unique")
    if len(features_by_layer[CENTROID_LAYER]) != 1:
        raise ValueError("FirstMap centroid sentinel is missing or non-unique")
    if len(records) != 1:
        raise ValueError("FirstMap sentinel layers did not join to one parcel")
    record = records[0]
    if (
        record.get("native_parcel_id") != PROBE_PIN
        or record.get("jurisdiction", {}).get("county_name") != PROBE_COUNTY
    ):
        raise ValueError("FirstMap sentinel identity changed")
    polygon = record["polygon_features"][0]["raw_attributes"]
    centroid = record["centroid_features"][0]["raw_attributes"]
    for field_name in ("OBJECTID", "PIN", "ACRES", "COUNTY", "UPDATED"):
        if field_name not in polygon:
            raise ValueError(f"FirstMap polygon sentinel lacks {field_name}")
    for field_name in (
        "OBJECTID",
        "PIN",
        "COUNTY",
        "LONGITUDE",
        "LATITUDE",
        "LAST_UPDATED",
        "ZIP_CODE",
        "CENSUSBLOCK",
    ):
        if field_name not in centroid:
            raise ValueError(f"FirstMap centroid sentinel lacks {field_name}")
    if not isinstance(centroid.get("LONGITUDE"), (int, float)) or not isinstance(
        centroid.get("LATITUDE"), (int, float)
    ):
        raise ValueError("FirstMap centroid sentinel coordinates changed type")


def _query_parameters(args: argparse.Namespace) -> dict[str, Any]:
    values: dict[str, Any] = {
        "geometry": args.geometry,
        "out_sr": args.out_sr if args.geometry else None,
        "max_records": args.max_records,
        "page_size": args.page_size,
    }
    for name in ("pin", "term", "county", "objectid", "layer"):
        value = getattr(args, name, None)
        if value is not None:
            values[name] = value
    if getattr(args, "cursor", None) is not None:
        values["cursor"] = args.cursor
    if args.command == "probe":
        values["sentinel_county"] = PROBE_COUNTY
        values["sentinel_pin"] = PROBE_PIN
    return values


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    county_name = _county(getattr(args, "county", None))
    county_geoid = _county_geoid(county_name)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=county_geoid or "10",
            name=county_name or "Delaware",
            state_code="DE",
            county_fips=county_geoid,
            metadata={"state_fips": "10"},
        ),
        query=QueryMetadata(
            operation=args.command,
            parameters=_query_parameters(args),
            requested_limit=args.max_records,
            cursor=getattr(args, "cursor", None),
        ),
    )


def _unique_warnings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    clients: Mapping[str, ArcGISRESTClient] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    query = build_query(args)
    try:
        access_contract = (
            access_decision
            if access_decision is not None
            else _access_contract(args)
        )
        source_clients = clients or _clients(args, access_contract)
        records, fetches, next_cursor = _fetch_records(args, source_clients)
        truncated = any(fetched.truncated_by_cap for fetched in fetches)
        warnings = _unique_warnings(
            (
                *SOURCE_WARNINGS,
                *(warning for fetched in fetches for warning in fetched.warnings),
                *(
                    ("The caller-selected max-records ceiling was reached.",)
                    if truncated
                    else ()
                ),
                *(
                    BLANK_PIN_CAVEAT
                    for record in records
                    if record.get("identity_caveat")
                ),
            )
        )
        if truncated:
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
    if log_results:
        log_search(canonical_json(query.to_dict()), SOURCE_ID, count)
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    data = result.to_dict()
    if write_output(
        data,
        args,
        summary=f"Delaware FirstMap {args.command} ({result.status.value})",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print(
        f"Delaware FirstMap {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        identity = record["identity"]
        if identity["basis"] == "county_and_pin":
            label = f"{identity['county']} | {identity['pin']}"
        else:
            label = (
                f"{identity.get('county') or 'Delaware'} | "
                f"{identity['layer']} OBJECTID {identity['object_id']}"
            )
        print(
            f"  {label} | polygons={len(record['polygon_features'])} "
            f"centroids={len(record['centroid_features'])}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    *,
    cursor: bool = False,
) -> None:
    if cursor:
        parser.add_argument(
            "--cursor",
            help="Continuation cursor from a previous result",
        )
    parser.add_argument(
        "--geometry",
        action="store_true",
        help="Return source geometry",
    )
    parser.add_argument(
        "--out-sr",
        type=_positive_int,
        default=4326,
        help="ArcGIS output spatial reference used with --geometry",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=2_000,
        help="Requested ArcGIS page size; the service enforces its native limit",
    )
    parser.add_argument(
        "--max-records",
        type=_positive_int,
        help="Optional caller-selected record ceiling",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--minimum-interval",
        type=_nonnegative_float,
        default=0.0,
        help="Optional minimum seconds between source requests",
    )
    parser.add_argument("--max-attempts", type=_positive_int, default=3)
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
        description=(
            "Query official Delaware FirstMap statewide parcel polygons "
            "and centroid routing data"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pin_parser = subparsers.add_parser(
        "pin",
        help="Look up an exact PIN and join polygon and centroid records",
    )
    pin_parser.add_argument("pin")
    pin_parser.add_argument("--county", help="Kent, New Castle, or Sussex")
    _add_runtime_arguments(pin_parser)

    search_parser = subparsers.add_parser(
        "search",
        help="Search PIN text within one county and one source layer",
    )
    search_parser.add_argument("term")
    search_parser.add_argument(
        "--county",
        required=True,
        help="Kent, New Castle, or Sussex",
    )
    search_parser.add_argument(
        "--layer",
        choices=(POLYGON_LAYER, CENTROID_LAYER),
        default=POLYGON_LAYER,
    )
    _add_runtime_arguments(search_parser, cursor=True)

    list_parser = subparsers.add_parser(
        "list",
        help="List one county from one source layer",
    )
    list_parser.add_argument(
        "--county",
        required=True,
        help="Kent, New Castle, or Sussex",
    )
    list_parser.add_argument(
        "--layer",
        choices=(POLYGON_LAYER, CENTROID_LAYER),
        default=POLYGON_LAYER,
    )
    _add_runtime_arguments(list_parser, cursor=True)

    objectid_parser = subparsers.add_parser(
        "objectid",
        help="Look up one layer OBJECTID and join its complement by county/PIN",
    )
    objectid_parser.add_argument("objectid", type=_positive_int)
    objectid_parser.add_argument(
        "--layer",
        choices=(POLYGON_LAYER, CENTROID_LAYER),
        default=POLYGON_LAYER,
    )
    _add_runtime_arguments(objectid_parser)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Verify a stable public-property sentinel across both layers",
    )
    _add_runtime_arguments(probe_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
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
