from __future__ import annotations

import subprocess
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import query_orleans_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


SAMPLE_ATTRIBUTES = {
    "OBJECTID": 106289096,
    "LOWPARCELID": None,
    "PARCELID": "41050755",
    "BUILDING": None,
    "UNIT": None,
    "CVTTXCD": "1",
    "CVTTXDSCRP": "ORLEANS",
    "SCHLTXCD": "1",
    "SCHLDSCRP": "ORLEANS",
    "USEDSCRP": "EXEMPT",
    "NGHBRHDCD": "A01",
    "CLASSCD": "R",
    "CLASSDSCRP": "RESIDENTIAL",
    "SITEADDRESS": "1771 NASHVILLE AVE, LA, 70115",
    "CNVYNAME": None,
    "OWNERNME1": "CITY OF NEW ORLEANS",
    "OWNERNME2": None,
    "PSTLADDRESS": "1300 PERDIDO ST, ROOM 5W06",
    "PSTLCITY": "NEW ORLEANS",
    "PSTLSTATE": "LA",
    "PSTLZIP5": "70112",
    "PSTLZIP4": "0000",
    "RESFLRAREA": 2500.0,
    "RESYRBLT": 1924.0,
    "RESSTRTYP": "SINGLE FAMILY",
    "STRCLASS": "A",
    "CLASSMOD": "1",
    "LNDVALUE": 225000.0,
    "PRVASSDVAL": 170000.0,
    "CNTASSDVAL": 180700.0,
    "ASSDVALYRCG": 10700.0,
    "ASSDPCNTCG": 6.294,
    "PRVTXBLVAL": 160000.0,
    "CNTTXBLVAL": 170000.0,
    "TXBLVALYRCHG": 10000.0,
    "TXBLPCNTCHG": 6.25,
    "PRVWNTTXOD": 100.0,
    "PRVSMRTXOD": 50.0,
    "TOTPRVTXTOD": 150.0,
    "CNTWNTTXOD": 120.0,
    "CNTSMRTXOD": 60.0,
    "TOTCNTTXOD": 180.0,
    "TXODYRCHG": 30.0,
    "TXODPCNTCHG": 20.0,
    "WATERSERV": "SWBNO",
    "SEWERSERV": "SWBNO",
    "LASTUPDATE": 1781531741000,
    "Shape_Length": 1000.25,
    "Shape_Area": 94087.0,
    "SITEADDR": "1771 NASHVILLE AVE",
    "SITECITY": "NEW ORLEANS",
    "SITESTATE": "LA",
    "SITEZIP": "70115",
    "SITUS_NUM": "1771",
    "SITUS_DIR": None,
    "SITUS_STREET": "NASHVILLE",
    "SITUS_TYPE": "AVE",
    "USECD": "1",
    "PRPRTYDSCRP": "PT SQS 69 70 HOME FOR CHILDREN",
    "TAXBILLID": "615199817",
    "LOT": None,
    "SQUARE": None,
    "BLOCK": "69",
    "PARID": "1771-NASHVILLEAV",
    "ASS_SQFT": "94087",
    "ASS_DIMS": "189x190x457x436",
}
SAMPLE_FEATURE = {
    "attributes": SAMPLE_ATTRIBUTES,
    "geometry": {
        "rings": [
            [
                [-90.1146, 29.9323],
                [-90.1148, 29.9324],
                [-90.1146, 29.9323],
            ]
        ]
    },
}
SECOND_FEATURE = {
    "attributes": {
        **SAMPLE_ATTRIBUTES,
        "OBJECTID": 106289097,
        "TAXBILLID": "615199818",
        "UNIT": "2",
    }
}
LOCATOR_CANDIDATE = {
    "address": "615199817",
    "location": {"x": -10031536.679728802, "y": 3494899.2532103313},
    "score": 100,
    "attributes": {
        "User_fld": "1771 NASHVILLE AVE",
        "Loc_name": "ParcelTaxbillL",
    },
}


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(query_orleans_property, "log_search", lambda *_args: None)


def _args(command="parcel", query="41050755", **overrides):
    values = {
        "command": command,
        "query": query,
        "limit": 2,
        "cursor": None,
        "geometry": False,
        "tax_year": None,
        "page_size": 1000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0,
        "catalog_db": "unused-catalog.db",
        "catalog_config": "unused-sources.yaml",
        "output": None,
        "json_out": False,
        "id_type": "auto",
    }
    values.update(overrides)
    return Namespace(**values)


def test_cli_uses_source_appropriate_default_timeout():
    args = query_orleans_property.build_parser().parse_args(
        ["parcel", "Y2A21C4"]
    )

    assert args.timeout == 60.0


def _fetch(
    records,
    *,
    next_cursor=None,
    truncated=False,
    schema="orleans-schema",
    warnings=(),
):
    return PaginatedFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        schema={"kind": "fixture"},
        schema_fingerprint=schema,
        pages_fetched=1,
        requests_made=1,
        truncated_by_cap=truncated,
        warnings=tuple(warnings),
    )


class FakeLayerClient:
    def __init__(self, *results, error=None):
        self.results = list(results)
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if not self.results:
            raise AssertionError("unexpected ArcGIS query")
        return self.results.pop(0)


class FakeLocatorClient:
    def __init__(self, candidates):
        self.candidate_records = tuple(candidates)
        self.calls = []

    def candidates(self, query, *, max_locations):
        self.calls.append((query, max_locations))
        return self.candidate_records[:max_locations]


@dataclass
class FixtureResponse:
    payload: Any
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""

    def json(self):
        return self.payload


class QueueTransport:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def request(self, method, url, *, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.payloads:
            raise AssertionError("unexpected HTTP request")
        return FixtureResponse(self.payloads.pop(0))


def test_normalization_preserves_account_parcel_and_assessment_identity():
    record = query_orleans_property._normalize_feature(
        SAMPLE_FEATURE,
        schema_fingerprint_value="schema123",
        include_geometry=True,
    )

    assert record["native_parcel_id"] == "TAXBILLID:615199817"
    assert record["canonical_ref"] == (
        "PROPERTY:us-la-orleans-property-viewer/22071/account/"
        "TAXBILLID%3A615199817"
    )
    assert record["tax_bill_id"] == "615199817"
    assert record["geopin"] == "41050755"
    assert record["parid"] == "1771-NASHVILLEAV"
    assert record["alternate_parcel_ids"] == [
        "615199817",
        "41050755",
        "1771-NASHVILLEAV",
    ]
    assert record["owners"][0]["raw_name"] == "CITY OF NEW ORLEANS"
    assert record["assessment"]["land_value"] == 225000
    assert record["assessment"]["assessed_value"] == 180700
    assert record["assessment"]["assessment_class"] == "RESIDENTIAL"
    assert record["taxes_owed"]["current_total"] == 180
    assert record["structure"]["residential_year_built"] == 1924
    assert record["source_last_updated"] == "2026-06-15T13:55:41Z"
    assert record["mailing_address"]["postal_code"] == "70112"
    assert record["source_links"]["record"].endswith("?geopin=41050755")
    assert record["source_links"]["assessor_record"].endswith(
        "KeyValue=1771-NASHVILLEAV"
    )
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["schema_fingerprint"] == "schema123"


def test_account_record_key_is_collision_tolerant_and_keeps_alphanumeric_ids():
    attributes = {
        "TAXBILLID": "39W747514",
        "PARCELID": "41135830",
        "PARID": "UNIT-101",
    }

    assert query_orleans_property._record_key(attributes) == (
        "TAXBILLID:39W747514"
    )
    assert query_orleans_property._record_key(
        {"PARCELID": "41208602", "PARID": "Y2A21C4"}
    ) == "PARID:Y2A21C4"
    assert query_orleans_property._record_key(
        {"OBJECTID": 106289096, "PARCELID": "41050755"}
    ) == "PARCELID:41050755|OBJECTID:106289096"


def test_assessment_class_falls_back_to_class_code():
    feature = {
        "attributes": {
            **SAMPLE_ATTRIBUTES,
            "CLASSDSCRP": " ",
            "CLASSCD": "R",
        }
    }

    record = query_orleans_property._normalize_feature(
        feature,
        schema_fingerprint_value="schema123",
        include_geometry=False,
    )

    assert record["assessment"]["assessment_class"] == "R"


def test_direct_predicates_use_indexed_owner_and_geopin_routes():
    assert query_orleans_property._where("owner", "O'Brien") == (
        "OWNERNME1 LIKE 'O''BRIEN%'"
    )
    assert query_orleans_property._where("parcel", "41135830") == (
        "PARCELID='41135830'"
    )
    assert query_orleans_property._where(
        "parcel", "1771-NASHVILLEAV"
    ) == "PARID='1771-NASHVILLEAV'"
    assert query_orleans_property._where(
        "parcel", "Y2A21C4"
    ) == "PARID='Y2A21C4'"
    assert query_orleans_property._where(
        "parcel",
        "Y2A21C4",
        id_type="geopin",
    ) == "PARCELID='Y2A21C4'"
    assert query_orleans_property._where(
        "parcel",
        "41135830",
        id_type="parid",
    ) == "PARID='41135830'"
    assert query_orleans_property._where("probe", None) == (
        "PARCELID='41026779'"
    )


def test_owner_search_queries_each_index_separately_and_excludes_duplicates():
    owner_two_feature = {
        "attributes": {
            **SAMPLE_ATTRIBUTES,
            "OBJECTID": 106289098,
            "TAXBILLID": "615199819",
            "OWNERNME1": "OTHER OWNER",
            "OWNERNME2": "CITY OF NEW ORLEANS",
        }
    }
    layer = FakeLayerClient(
        _fetch([SAMPLE_FEATURE]),
        _fetch([owner_two_feature]),
    )

    result = query_orleans_property.execute(
        _args(
            command="owner",
            query="CITY OF NEW ORLEANS",
            limit=2,
        ),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
    )

    assert result.status.value == "ok"
    assert [record["tax_bill_id"] for record in result.records] == [
        "615199817",
        "615199819",
    ]
    assert layer.calls[0]["where"] == (
        "OWNERNME1 LIKE 'CITY OF NEW ORLEANS%'"
    )
    assert layer.calls[1]["where"] == (
        "(OWNERNME2 LIKE 'CITY OF NEW ORLEANS%' AND "
        "(OWNERNME1 IS NULL OR OWNERNME1 NOT LIKE 'CITY OF NEW ORLEANS%'))"
    )


def test_owner_cursor_wraps_arcgis_offset_and_resumes_same_index():
    first_layer = FakeLayerClient(
        _fetch([SAMPLE_FEATURE, SECOND_FEATURE])
    )
    first = query_orleans_property.execute(
        _args(command="owner", query="CITY", limit=1),
        access_decision={"allowed": True, "limits": {}},
        layer_client=first_layer,
    )

    assert first.next_cursor == "orleans:owner:0:1"

    second_layer = FakeLayerClient(_fetch([SECOND_FEATURE]))
    second = query_orleans_property.execute(
        _args(
            command="owner",
            query="CITY",
            limit=1,
            cursor=first.next_cursor,
        ),
        access_decision={"allowed": True, "limits": {}},
        layer_client=second_layer,
    )

    assert second.records[0]["tax_bill_id"] == "615199818"
    assert second_layer.calls[0]["cursor"] == "arcgis:offset:1"
    assert second.next_cursor == "orleans:owner:1:0"


def test_locator_client_uses_official_composite_service_and_native_spatial_ref():
    transport = QueueTransport({"candidates": [LOCATOR_CANDIDATE]})
    client = query_orleans_property.OrleansPropertyLocatorClient(
        transport=transport,
        minimum_interval=0,
    )

    candidates = client.candidates("615199817", max_locations=7)

    assert candidates == (LOCATOR_CANDIDATE,)
    call = transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == (
        f"{query_orleans_property.LOCATOR_URL}/findAddressCandidates"
    )
    assert call["params"]["SingleLine"] == "615199817"
    assert call["params"]["outSR"] == 102100
    assert call["params"]["maxLocations"] == 7
    assert "User_fld" in call["params"]["outFields"]


def test_locator_client_rejects_schema_drift():
    client = query_orleans_property.OrleansPropertyLocatorClient(
        transport=QueueTransport({"results": []}),
        minimum_interval=0,
    )

    with pytest.raises(
        query_orleans_property.SourceSchemaError,
        match="candidates array",
    ):
        client.candidates("1771 NASHVILLE", max_locations=2)


def test_direct_parcel_execute_preserves_arcgis_pagination_and_geometry():
    layer = FakeLayerClient(
        _fetch([SAMPLE_FEATURE, SECOND_FEATURE])
    )

    result = query_orleans_property.execute(
        _args(geometry=True, cursor="arcgis:offset:0", limit=1),
        access_decision={"allowed": True, "limits": {"maximum_page_size": 1000}},
        layer_client=layer,
    )

    assert result.status.value == "ok"
    assert result.next_cursor == "arcgis:offset:1"
    assert len(result.records) == 1
    call = layer.calls[0]
    assert call["where"] == "PARCELID='41050755'"
    assert call["parameters"]["orderByFields"] == "OBJECTID ASC"
    assert call["parameters"]["outSR"] == 4326
    assert call["cursor"] == "arcgis:offset:0"
    assert call["return_geometry"] is True
    assert call["requested_limit"] == 2


def test_exact_single_parcel_does_not_emit_a_speculative_cursor():
    layer = FakeLayerClient(_fetch([SAMPLE_FEATURE]))

    result = query_orleans_property.execute(
        _args(limit=1),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.next_cursor is None


def test_caller_ceiling_is_partial_only_when_direct_source_has_more():
    layer = FakeLayerClient(
        _fetch([SAMPLE_FEATURE, SECOND_FEATURE])
    )

    result = query_orleans_property.execute(
        _args(limit=10, max_records=1),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
    )

    assert result.status.value == "partial"
    assert result.next_cursor == "arcgis:offset:1"
    assert "caller-selected ceiling" in result.warnings[-1]


def test_account_uses_locator_point_query_and_filters_intersecting_rows():
    wrong = {
        "attributes": {
            **SAMPLE_ATTRIBUTES,
            "OBJECTID": 106289095,
            "TAXBILLID": "OTHER",
        }
    }
    layer = FakeLayerClient(_fetch([wrong, SAMPLE_FEATURE]))
    locator = FakeLocatorClient([LOCATOR_CANDIDATE])

    result = query_orleans_property.execute(
        _args(command="account", query="615199817", limit=5),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
        locator_client=locator,
    )

    assert result.status.value == "ok"
    assert [record["tax_bill_id"] for record in result.records] == [
        "615199817"
    ]
    assert locator.calls == [
        ("615199817", query_orleans_property.LOCATOR_MAX_CANDIDATES)
    ]
    assert layer.calls[0]["where"] == "TAXBILLID='615199817'"
    params = layer.calls[0]["parameters"]
    assert params["geometryType"] == "esriGeometryPoint"
    assert params["inSR"] == 102100
    assert params["spatialRel"] == "esriSpatialRelIntersects"
    assert '"x":-10031536.679728802' in params["geometry"]
    assert result.records[0]["source_match"]["score"] == 100


def test_generic_search_owner_locator_filters_co_located_accounts():
    owner_candidate = {
        **LOCATOR_CANDIDATE,
        "address": "KWASKE ILIANNA",
        "attributes": {
            "Loc_name": "ParcelOwnerLoc",
            "Match_addr": "KWASKE ILIANNA",
            "User_fld": "920 POEYFARRE ST",
        },
    }
    unrelated = {
        "attributes": {
            **SAMPLE_ATTRIBUTES,
            "OBJECTID": 106289094,
            "TAXBILLID": "OTHER",
            "OWNERNME1": "UNRELATED OWNER",
            "OWNERNME2": None,
        }
    }
    matched = {
        "attributes": {
            **SAMPLE_ATTRIBUTES,
            "OBJECTID": 106289095,
            "TAXBILLID": "103106317",
            "OWNERNME1": "OTHER OWNER",
            "OWNERNME2": "KWASKE ILIANNA",
        }
    }
    layer = FakeLayerClient(_fetch([unrelated, matched]))

    result = query_orleans_property.execute(
        _args(command="search", query="KWASKE ILIANNA", limit=5),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
        locator_client=FakeLocatorClient([owner_candidate]),
    )

    assert [record["tax_bill_id"] for record in result.records] == [
        "103106317"
    ]
    assert layer.calls[0]["where"] == (
        "(OWNERNME1='KWASKE ILIANNA' OR OWNERNME2='KWASKE ILIANNA')"
    )


def test_generic_search_taxbill_locator_requires_exact_account():
    wrong = {
        "attributes": {
            **SAMPLE_ATTRIBUTES,
            "OBJECTID": 106289095,
            "TAXBILLID": "6151998170",
        }
    }
    layer = FakeLayerClient(_fetch([wrong, SAMPLE_FEATURE]))

    result = query_orleans_property.execute(
        _args(command="search", query="615199817", limit=5),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
        locator_client=FakeLocatorClient([LOCATOR_CANDIDATE]),
    )

    assert [record["tax_bill_id"] for record in result.records] == [
        "615199817"
    ]
    assert layer.calls[0]["where"] == "TAXBILLID='615199817'"


def test_address_locator_cursor_resumes_inside_multi_account_parcel():
    locator = FakeLocatorClient(
        [
            {
                **LOCATOR_CANDIDATE,
                "address": "1771 NASHVILLE AVENUE, NEW ORLEANS",
            }
        ]
    )
    first_layer = FakeLayerClient(_fetch([SAMPLE_FEATURE, SECOND_FEATURE]))

    first = query_orleans_property.execute(
        _args(command="address", query="1771 NASHVILLE AVE", limit=1),
        access_decision={"allowed": True, "limits": {}},
        layer_client=first_layer,
        locator_client=locator,
    )

    assert first.status.value == "ok"
    assert first.records[0]["tax_bill_id"] == "615199817"
    assert first.next_cursor is not None
    candidate_offset, feature_offset, seen = (
        query_orleans_property._locator_cursor(first.next_cursor)
    )
    assert (candidate_offset, feature_offset) == (0, 1)
    assert seen == {"106289096"}

    second_layer = FakeLayerClient(_fetch([SECOND_FEATURE]))
    second = query_orleans_property.execute(
        _args(
            command="address",
            query="1771 NASHVILLE AVE",
            limit=1,
            cursor=first.next_cursor,
        ),
        access_decision={"allowed": True, "limits": {}},
        layer_client=second_layer,
        locator_client=locator,
    )

    assert second.records[0]["tax_bill_id"] == "615199818"
    assert second.next_cursor is None
    assert second_layer.calls[0]["cursor"] == "arcgis:offset:1"


def test_locator_cursor_deduplicates_features_across_candidates():
    second_candidate = {
        **LOCATOR_CANDIDATE,
        "address": "1771 NASHVILLE AVENUE, NEW ORLEANS",
    }
    locator = FakeLocatorClient([LOCATOR_CANDIDATE, second_candidate])
    first = query_orleans_property.execute(
        _args(command="address", query="1771 NASHVILLE AVE", limit=1),
        access_decision={"allowed": True, "limits": {}},
        layer_client=FakeLayerClient(_fetch([SAMPLE_FEATURE])),
        locator_client=locator,
    )

    assert first.next_cursor is not None
    candidate_offset, feature_offset, seen = (
        query_orleans_property._locator_cursor(first.next_cursor)
    )
    assert (candidate_offset, feature_offset) == (1, 0)
    assert seen == {"106289096"}

    second = query_orleans_property.execute(
        _args(
            command="address",
            query="1771 NASHVILLE AVE",
            limit=1,
            cursor=first.next_cursor,
        ),
        access_decision={"allowed": True, "limits": {}},
        layer_client=FakeLayerClient(
            _fetch([SAMPLE_FEATURE, SECOND_FEATURE])
        ),
        locator_client=locator,
    )

    assert [record["tax_bill_id"] for record in second.records] == [
        "615199818"
    ]


def test_uncapped_limit_is_forwarded_without_an_implicit_record_ceiling():
    layer = FakeLayerClient(_fetch([SAMPLE_FEATURE]))

    result = query_orleans_property.execute(
        _args(limit=5_000),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
    )

    assert result.status.value == "ok"
    assert layer.calls[0]["requested_limit"] == 5_001


def test_tax_year_is_explicitly_unavailable_without_constructing_clients():
    result = query_orleans_property.execute(
        _args(tax_year=2025),
        access_decision={"allowed": True, "limits": {}},
        layer_client=pytest.fail,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "tax_year_filter_not_published"
    assert "does not expose a tax-year field" in result.errors[0].message


def test_transport_error_is_not_reported_as_no_results():
    layer = FakeLayerClient(
        error=TransportError(
            "source timed out",
            url=query_orleans_property.LAYER_URL,
        )
    )

    result = query_orleans_property.execute(
        _args(),
        access_decision={"allowed": True, "limits": {}},
        layer_client=layer,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "transport_error"
    assert result.records == ()


def test_catalog_denial_prevents_client_construction(monkeypatch):
    decision = {
        "source_id": query_orleans_property.SOURCE_ID,
        "allowed": False,
        "reason": "review unavailable",
        "reason_code": "access_review_required",
    }
    monkeypatch.setattr(
        query_orleans_property,
        "_access_contract",
        lambda _args: (_ for _ in ()).throw(
            AcquisitionUnavailableError(decision)
        ),
    )
    monkeypatch.setattr(
        query_orleans_property,
        "_new_layer_client",
        lambda *_args: pytest.fail("client constructed after denial"),
    )

    result = query_orleans_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"


def test_source_contract_matches_catalog_endpoints_and_verified_limits():
    query = query_orleans_property.build_query(
        "parcel",
        "41050755",
        tax_year=None,
        limit=50,
        cursor="arcgis:offset:1000",
        return_geometry=True,
    )
    config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    source = next(
        item
        for item in config["sources"]
        if item["source_id"] == query_orleans_property.SOURCE_ID
    )

    assert query.source.base_url == query_orleans_property.LAYER_URL
    assert query.jurisdiction.county_fips == "22071"
    assert query.query.cursor == "arcgis:offset:1000"
    assert source["official_url"] == query_orleans_property.VIEWER_URL
    assert source["endpoints"]["parcel_layer"] == (
        query_orleans_property.LAYER_URL
    )
    assert source["endpoints"]["viewer_parcel_layer"] == (
        query_orleans_property.VIEWER_LAYER_URL
    )
    assert source["endpoints"]["composite_locator"] == (
        query_orleans_property.LOCATOR_URL
    )
    assert source["access_review"]["limits"]["maximum_page_size"] == 1000
    assert {
        "search_owner",
        "search_address",
        "fetch_account",
        "fetch_parcel",
        "fetch_geometry",
        "assessment_value",
        "source_update",
    }.issubset(
        {
            capability["name"]
            for capability in source["capabilities"]
        }
    )


def test_cli_help_lists_all_supported_routes():
    completed = subprocess.run(
        [
            sys.executable,
            "tools/query_orleans_property.py",
            "--help",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    for command in ("owner", "address", "account", "parcel", "search", "probe"):
        assert command in completed.stdout

    parcel_help = subprocess.run(
        [
            sys.executable,
            "tools/query_orleans_property.py",
            "parcel",
            "--help",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert parcel_help.returncode == 0
    assert "--id-type {auto,geopin,parid}" in parcel_help.stdout
