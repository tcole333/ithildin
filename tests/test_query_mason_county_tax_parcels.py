from __future__ import annotations

import base64
import copy
import json
from typing import Any

import pytest

from tools import query_mason_county_tax_parcels as mason
from tools.public_records_http import RetryPolicy, SourceSchemaError
from tools.public_records_store import canonical_property_ref


OFFICIAL_FIELDS = tuple(
    dict.fromkeys(
        (
            "FID",
            "Shape",
            "PIN",
            "Taxlot",
            "Map_number",
            "Township",
            "Towndir",
            "Range",
            "Rangedir",
            "Section",
            "QTR",
            "QTRQTR",
            "AFN",
            "WhoCreated",
            "MapAccurac",
            "SEG_NUMBER",
            "TERRA_PIN",
            "Shape_area",
            "Shape_len",
            "District",
            "City",
            "State",
            "Zip",
            "Assessment",
            "IsExempt",
            "TotalMarke",
            "TotalAsses",
            "MarketLand",
            "MarketBuil",
            "AssessedLa",
            "AssessedBu",
            "ResultingT",
            "Department",
            "SecondaryL",
            "TotalAcres",
            "LastName",
            "FirstName",
            "Address1",
            "Address2",
            "Situs",
            "AssembledL",
            "SubName",
            "Assessed_1",
        )
    )
)


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.text = json.dumps(payload)

    def json(self) -> Any:
        return self.payload


def _field(name: str) -> dict[str, Any]:
    if name == "FID":
        field_type = "esriFieldTypeOID"
    elif name == "Shape":
        field_type = "esriFieldTypeGeometry"
    elif name in {
        "TotalMarke",
        "TotalAsses",
        "MarketLand",
        "MarketBuil",
        "AssessedLa",
        "AssessedBu",
        "ResultingT",
        "TotalAcres",
        "Assessed_1",
    }:
        field_type = "esriFieldTypeDouble"
    else:
        field_type = "esriFieldTypeString"
    return {"name": name, "alias": name, "type": field_type}


def _metadata(*, maximum: int = 2) -> dict[str, Any]:
    return {
        "id": 0,
        "name": mason.LAYER_NAME,
        "type": "Feature Layer",
        "displayField": "PIN",
        "objectIdField": "FID",
        "geometryType": mason.GEOMETRY_TYPE,
        "capabilities": "Map,Query,Data",
        "maxRecordCount": maximum,
        "supportsAdvancedQueries": False,
        "supportsStatistics": False,
        "advancedQueryCapabilities": {
            "supportsPagination": False,
            "supportsOrderBy": False,
            "supportsStatistics": False,
            "supportsDistinct": False,
        },
        "extent": {
            "xmin": 900_000,
            "ymin": 600_000,
            "xmax": 1_300_000,
            "ymax": 1_000_000,
            "spatialReference": {"wkid": 102749, "latestWkid": 2286},
        },
        "fields": [_field(name) for name in OFFICIAL_FIELDS],
    }


def _feature(
    fid: int,
    *,
    pin: str | None = "219010090013",
    terra_pin: str | None = "21901-00-90013",
    taxlot: str | None = "0090013",
) -> dict[str, Any]:
    return {
        "attributes": {
            "FID": fid,
            "PIN": pin,
            "TERRA_PIN": terra_pin,
            "Taxlot": taxlot,
            "Map_number": "219010",
            "SEG_NUMBER": "01",
            "Assessment": "REAL PROPERTY",
            "IsExempt": "N",
            "TotalMarke": 425_000.0 + fid,
            "TotalAsses": 410_000.0 + fid,
            "MarketLand": 150_000.0,
            "MarketBuil": 275_000.0,
            "AssessedLa": 145_000.0,
            "AssessedBu": 265_000.0,
            "ResultingT": 4_200.5,
            "TotalAcres": 1.25,
            "LastName": "EXAMPLE",
            "FirstName": "OWNER",
            "Address1": "PO BOX 10",
            "Address2": "",
            "City": "SHELTON",
            "State": "WA",
            "Zip": "98584",
            "Situs": "100 TEST RD",
            "AssembledL": "LOT 13 TEST PLAT",
            "SubName": "TEST PLAT",
            "Township": 19,
            "Towndir": "N",
            "Range": 1,
            "Rangedir": "W",
            "Section": 9,
            "QTR": "NE",
            "QTRQTR": "SE",
        },
        "geometry": {
            "rings": [
                [
                    [-123.1, 47.2],
                    [-123.0, 47.2],
                    [-123.1, 47.2],
                ]
            ]
        },
    }


class ArcGISTransport:
    def __init__(
        self,
        *,
        object_ids: list[int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.object_ids = list(object_ids if object_ids is not None else [2, 0, 1])
        self.metadata = copy.deepcopy(metadata or _metadata())
        self.features = {
            object_id: _feature(object_id) for object_id in self.object_ids
        }
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        parameters = dict(params or {})
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": parameters,
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        assert method == "GET"
        if url == mason.LAYER_URL:
            assert parameters == {"f": "json"}
            return FakeResponse(copy.deepcopy(self.metadata))
        if url != mason.QUERY_URL:
            raise AssertionError(f"unexpected request URL: {url}")
        assert "resultOffset" not in parameters
        assert "resultRecordCount" not in parameters
        assert "orderByFields" not in parameters
        if parameters.get("returnIdsOnly") == "true":
            return FakeResponse(
                {
                    "objectIdFieldName": "FID",
                    "objectIds": list(self.object_ids),
                }
            )
        requested = [int(value) for value in parameters["objectIds"].split(",")]
        rows = [
            copy.deepcopy(self.features[object_id]) for object_id in reversed(requested)
        ]
        if parameters.get("returnGeometry") != "true":
            for row in rows:
                row.pop("geometry", None)
        return FakeResponse(
            {
                "objectIdFieldName": "FID",
                "features": rows,
                "exceededTransferLimit": False,
            }
        )


def _client(transport: ArcGISTransport) -> mason.MasonCountyTaxParcelsClient:
    return mason.MasonCountyTaxParcelsClient(
        transport=transport,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )


def _args(*values: str):
    return mason.build_parser().parse_args(list(values))


def test_non_pageable_traversal_snapshots_sorts_and_batches_exact_fids() -> None:
    transport = ArcGISTransport()
    batch = mason.fetch_feature_batch(
        _client(transport),
        operation="list",
        spec=mason.QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=None,
        cursor=None,
    )

    assert batch.matching_object_ids == (0, 1, 2)
    assert [row["attributes"]["FID"] for row in batch.features] == [0, 1, 2]
    assert batch.next_cursor is None
    assert batch.requests_made == 4
    feature_calls = [call for call in transport.calls if "objectIds" in call["params"]]
    assert [call["params"]["objectIds"] for call in feature_calls] == [
        "0,1",
        "2",
    ]
    assert all(
        call["params"]["returnGeometry"] == "false" and "outSR" not in call["params"]
        for call in feature_calls
    )


def test_cursor_accepts_fid_zero_and_detects_population_change() -> None:
    transport = ArcGISTransport()
    first = mason.fetch_feature_batch(
        _client(transport),
        operation="list",
        spec=mason.QuerySpec("1=1", {}, False),
        limit=1,
        cursor=None,
    )

    assert first.next_cursor
    decoded = mason._decode_cursor(first.next_cursor)
    assert decoded is not None
    assert decoded.last_object_id == 0
    second = mason.fetch_feature_batch(
        _client(transport),
        operation="list",
        spec=mason.QuerySpec("1=1", {}, False),
        limit=1,
        cursor=first.next_cursor,
    )
    assert [row["attributes"]["FID"] for row in second.features] == [1]

    transport.object_ids.append(3)
    transport.features[3] = _feature(3)
    with pytest.raises(
        mason.MasonParcelSelectionError,
        match="changed after the cursor",
    ) as raised:
        mason.fetch_feature_batch(
            _client(transport),
            operation="list",
            spec=mason.QuerySpec("1=1", {}, False),
            limit=1,
            cursor=first.next_cursor,
        )
    assert raised.value.code == "cursor_snapshot_changed"
    assert raised.value.status.value == "source_changed"


def test_cursor_rejects_boolean_numeric_fields() -> None:
    payload = {
        "version": mason.CURSOR_VERSION,
        "criteria": "a" * 64,
        "schema": "b" * 64,
        "ids": "c" * 64,
        "offset": True,
        "last": 0,
        "total": 3,
    }
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )

    with pytest.raises(
        mason.MasonParcelSelectionError,
        match="lacks required continuation fields",
    ):
        mason._decode_cursor(f"{mason.CURSOR_PREFIX}{encoded}")


def test_metadata_contract_rejects_traversal_and_schema_drift() -> None:
    contract = mason.metadata_contract(_metadata())
    assert contract.object_id_field == "FID"
    assert contract.max_record_count == 2
    assert contract.supports_pagination is False
    assert contract.supports_order_by is False
    assert contract.spatial_reference == {
        "wkid": 102749,
        "latestWkid": 2286,
    }

    pageable = _metadata()
    pageable["advancedQueryCapabilities"]["supportsPagination"] = True
    with pytest.raises(SourceSchemaError, match="support flags changed"):
        mason.metadata_contract(pageable)

    missing = _metadata()
    missing["fields"] = [field for field in missing["fields"] if field["name"] != "PIN"]
    with pytest.raises(SourceSchemaError, match="missing required fields"):
        mason.metadata_contract(missing)


def test_normalization_separates_occurrence_join_and_source_semantics() -> None:
    contract = mason.metadata_contract(_metadata())
    record = mason.normalize_feature(
        _feature(0),
        contract=contract,
        geometry_requested=True,
    )

    assert record["source_occurrence_id"] == "FID:0"
    assert record["feature_occurrence"] == {
        "object_id_field": "FID",
        "object_id": 0,
        "feature_ref": canonical_property_ref(
            mason.SOURCE_ID,
            mason.COUNTY_GEOID,
            "parcel_feature",
            "FID:0",
        ),
    }
    assert record["native_parcel_id"] == "219010090013"
    assert record["parcel_join_key"] == {
        "county_geoid": "53045",
        "field": "pin",
        "value": "219010090013",
        "identity_role": "candidate_parcel_join",
        "uniqueness_in_layer": "not_assumed",
    }
    assert record["owners"][0]["raw_name"] == "EXAMPLE, OWNER"
    assert record["owners"][0]["role"] == "assessment_snapshot_name"
    assert record["assessment"]["market_value"] == 425_000.0
    assert record["assessment"]["published_resulting_tax"] == 4_200.5
    assert record["source_semantics"]["recorder_instruments"] is False
    assert record["source_semantics"]["treasury_balances_or_payment_history"] is False
    assert record["source_semantics"]["recorded_title_or_beneficial_ownership"] is False
    assert record["geometry_crs"] == "EPSG:4326"

    unlinked = mason.normalize_feature(
        _feature(7, pin=None, terra_pin=None, taxlot=None),
        contract=contract,
        geometry_requested=False,
    )
    assert unlinked["native_parcel_id"] is None
    assert unlinked["parcel_join_key"] is None
    assert unlinked["canonical_ref"] == unlinked["feature_ref"]
    assert "geometry" not in unlinked


def test_parser_and_spatial_query_keep_caller_bounds_optional() -> None:
    exhaustive = _args("list")
    sentinel = _args("objectid", "0", "--limit", "1")
    point = mason._query_spec(_args("point", "-123.1", "47.2"))

    assert exhaustive.limit is None
    assert exhaustive.minimum_interval == 0
    assert sentinel.objectid == 0
    assert point.return_geometry is True
    assert point.geometry_parameters["geometryType"] == "esriGeometryPoint"
    assert json.loads(point.geometry_parameters["geometry"]) == {
        "x": -123.1,
        "y": 47.2,
        "spatialReference": {"wkid": 4326},
    }


def test_execute_exact_verified_sentinel_with_geometry() -> None:
    transport = ArcGISTransport(object_ids=[0])
    result = mason.execute(
        _args("objectid", "0", "--limit", "1", "--geometry"),
        access_contract={"allowed": True, "limits": {}},
        client=_client(transport),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["source_occurrence_id"] == "FID:0"
    assert result.records[0]["parcel_identifiers"] == {
        "pin": "219010090013",
        "terra_pin": "21901-00-90013",
        "taxlot": "0090013",
        "map_number": "219010",
        "segment_number": "01",
    }
    feature_call = transport.calls[-1]["params"]
    assert feature_call["objectIds"] == "0"
    assert feature_call["returnGeometry"] == "true"
    assert feature_call["outSR"] == 4326
