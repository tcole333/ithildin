from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import query_bexar_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


FIXTURE_DIR = Path("tests/fixtures/public_records/bexar")
SUMMARY_PAGE_1 = json.loads(
    (FIXTURE_DIR / "arcgis_summary_page_1.json").read_text(encoding="utf-8")
)
GEOMETRY = json.loads(
    (FIXTURE_DIR / "arcgis_geometry.json").read_text(encoding="utf-8")
)
HGO_SEARCH_COUNT = json.loads(
    (FIXTURE_DIR / "hgo_search_count.json").read_text(encoding="utf-8")
)
HGO_SEARCH_RESULTS = json.loads(
    (FIXTURE_DIR / "hgo_search_results.json").read_text(encoding="utf-8")
)
HGO_DETAIL = json.loads(
    (FIXTURE_DIR / "hgo_property_detail.json").read_text(encoding="utf-8")
)
HGO_DEEDS = json.loads(
    (FIXTURE_DIR / "hgo_deed_history.json").read_text(encoding="utf-8")
)


def _args(command="owner", query="TAUREAN", **overrides):
    values = {
        "command": command,
        "query": query,
        "limit": 2,
        "cursor": None,
        "geometry": False,
        "year": None,
        "page_size": 1000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0,
        "catalog_db": "unused-catalog.db",
        "catalog_config": "unused-sources.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


class FakeArcGISClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class FakeHGOClient:
    def __init__(self, *, detail=None, deeds=(), detail_error=None, deed_error=None):
        self.detail_payload = detail
        self.deeds = deeds
        self.detail_error = detail_error
        self.deed_error = deed_error
        self.detail_calls = []
        self.deed_calls = []

    def detail(self, property_id, year):
        self.detail_calls.append((property_id, year))
        if self.detail_error is not None:
            raise self.detail_error
        return self.detail_payload

    def deed_history(self, property_id):
        self.deed_calls.append(property_id)
        if self.deed_error is not None:
            raise self.deed_error
        return self.deeds


@dataclass
class FixtureResponse:
    payload: Any
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""

    def json(self):
        return self.payload


class QueueTransport:
    def __init__(self, payloads):
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
            raise AssertionError("unexpected HGO request")
        return FixtureResponse(self.payloads.pop(0))


def _fetch(records, *, next_cursor=None, truncated=False, schema="schema123"):
    return PaginatedFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        schema={"kind": "fixture"},
        schema_fingerprint=schema,
        pages_fetched=1,
        requests_made=1,
        truncated_by_cap=truncated,
    )


def test_arcgis_summary_normalization_preserves_source_identity_and_values():
    record = query_bexar_property._normalize_summary(
        SUMMARY_PAGE_1["features"][0],
        schema_fingerprint_value="arcgis-schema",
    )

    assert record["canonical_ref"] == (
        "PROPERTY:us-tx-bexar-bcad-property/48029/parcel/358951"
    )
    assert record["native_parcel_id"] == "358951"
    assert record["alternate_parcel_ids"] == ["05936-004-0140"]
    assert record["jurisdiction"]["county_geoid"] == "48029"
    assert record["owners"][0]["raw_name"] == "TAUREAN GENERAL SERVICES"
    assert record["owners"][0]["ownership_percentage"] == 100.0
    assert record["business_name"] == "FETCH AND FRISKER"
    assert record["assessment"]["parcel_value"] == 2555970
    assert record["mailing_address"]["postal_code"] == "78006-6500"
    assert record["taxing_jurisdiction_codes"] == [
        "06",
        "08",
        "09",
        "10",
        "11",
        "CAD",
        "56",
        "100",
    ]
    assert record["schema_fingerprint"] == "arcgis-schema"


def test_source_contract_and_catalog_routes_match_verified_endpoints():
    query = query_bexar_property.build_query(
        "parcel",
        "358951",
        year=2026,
        limit=1,
        cursor="arcgis:offset:2",
        return_geometry=True,
    )
    config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    source = next(
        item
        for item in config["sources"]
        if item["source_id"] == query_bexar_property.SOURCE_ID
    )

    assert query.source.source_id == "us-tx-bexar-bcad-property"
    assert query.jurisdiction.county_fips == "48029"
    assert query.query.cursor == "arcgis:offset:2"
    assert query.query.parameters["return_geometry"] is True
    assert source["source_status"] == "active"
    assert source["authentication"] == "none"
    assert source["endpoints"]["arcgis_property_table"] == (
        query_bexar_property.TABLE_URL
    )
    assert source["endpoints"]["arcgis_parcel_layer"] == (
        query_bexar_property.PARCEL_LAYER_URL
    )
    assert source["endpoints"]["property_detail_api"] == (
        query_bexar_property.HGO_DETAIL_URL
    )
    assert source["endpoints"]["deed_history_api"] == (
        query_bexar_property.HGO_DEED_HISTORY_URL
    )
    assert source["access_review"]["limits"]["maximum_page_size"] == 20_000
    assert source["access_review"]["limits"]["pagination_order"] == (
        query_bexar_property.TABLE_ORDER_BY
    )
    assert {
        "search_owner",
        "search_address",
        "fetch_parcel",
        "fetch_geometry",
        "fetch_detail",
        "fetch_deed_history",
    }.issubset(source["capabilities"])


def test_hgo_search_normalization_includes_personal_property_missing_from_arcgis():
    record = query_bexar_property._normalize_hgo_search_record(
        HGO_SEARCH_RESULTS[0],
        schema_fingerprint_value="hgo-schema",
    )

    assert record["native_parcel_id"] == "1225837"
    assert record["property_type"] == {
        "code": "P",
        "description": "P (Personal)",
    }
    assert record["owners"][0]["raw_name"] == "TAUREAN GENERAL SERVICES INC"
    assert record["assessment"]["market_value"] == 33540
    assert record["assessment"]["assessed_value"] == 33540
    assert record["situs_address"]["raw"] == (
        "26545 W INTERSTATE 10 BOERNE, TX 78006"
    )


def test_hgo_detail_normalization_preserves_roll_history_and_deed_evidence():
    record = query_bexar_property._normalize_detail(HGO_DETAIL, HGO_DEEDS)

    assert record["native_parcel_id"] == "358951"
    assert record["owners"][0]["owner_id"] == 2931065
    assert record["assessment"] == {
        "land_value": 396510,
        "improvement_value": 2159460,
        "parcel_value": 2555970,
        "market_value": 2555970,
        "assessed_value": 2555970,
        "assessment_class": "RETAIL STORE",
        "currency": "USD",
    }
    assert [row["Year"] for row in record["roll_history"]] == [2025, 2026]
    assert record["improvements"][0]["ImprvDescription"] == "OFFICE"
    assert record["land"][0]["LandSegMktValue"] == 396510
    assert record["deed_history"][1] == {
        "sequence": 0,
        "deed_date": "11/17/2014",
        "deed_type_code": "GWD",
        "deed_type_description": "General Warranty Deed",
        "grantor": "LA SERENA PARTNERS L P",
        "grantee": "TAUREAN GENERAL SERVICES",
        "book": "16964",
        "page": "2303",
        "instrument_number": "20140198951",
        "raw": HGO_DEEDS[1],
    }
    assert record["source_links"]["record"].endswith(
        "/bexar/property/2026-358951"
    )
    assert len(record["schema_fingerprint"]) == 64


def test_hgo_search_paginates_with_skip_take_and_returns_cursor():
    transport = QueueTransport(
        [
            HGO_SEARCH_COUNT,
            [HGO_SEARCH_RESULTS[0]],
            [HGO_SEARCH_RESULTS[1]],
        ]
    )
    client = query_bexar_property.BCADHGOClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search(
        '"TAUREAN GENERAL SERVICES"',
        requested_limit=2,
        page_size=1,
    )

    assert [record["PropertyId"] for record in fetched.records] == [
        1225837,
        358951,
    ]
    assert fetched.next_cursor is None
    assert fetched.pages_fetched == 2
    assert fetched.requests_made == 3
    assert [call["params"].get("skip") for call in transport.calls[1:]] == [0, 1]
    assert all(call["params"]["take"] == 1 for call in transport.calls[1:])


def test_arcgis_execute_supplies_unique_order_and_authoritative_zero(monkeypatch):
    client = FakeArcGISClient(_fetch([]))
    logged = []
    monkeypatch.setattr(
        query_bexar_property,
        "_arcgis_client",
        lambda _args, _access, **_kwargs: client,
    )
    monkeypatch.setattr(
        query_bexar_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_bexar_property.execute(
        _args(query="NO SUCH OWNER"),
        access_decision={"allowed": True, "limits": {}},
    )

    assert result.status.value == "no_results"
    assert client.calls[0]["parameters"] == {
        "orderByFields": query_bexar_property.TABLE_ORDER_BY
    }
    assert client.calls[0]["where"] == (
        "(UPPER(owner_name) LIKE '%NO SUCH OWNER%' "
        "OR UPPER(dba_name) LIKE '%NO SUCH OWNER%')"
    )
    assert logged[0][1:] == (query_bexar_property.SOURCE_ID, 0)


def test_arcgis_failure_is_unavailable_and_never_logged_as_zero(monkeypatch):
    client = FakeArcGISClient(
        error=TransportError(
            "network unavailable",
            url=query_bexar_property.TABLE_URL,
        )
    )
    logged = []
    monkeypatch.setattr(
        query_bexar_property,
        "_arcgis_client",
        lambda _args, _access, **_kwargs: client,
    )
    monkeypatch.setattr(
        query_bexar_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_bexar_property.execute(
        _args(),
        access_decision={"allowed": True, "limits": {}},
    )

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert logged[0][1:] == (query_bexar_property.SOURCE_ID, None)


def test_catalog_denial_does_not_construct_clients_or_log_zero(monkeypatch):
    decision = {
        "source_id": query_bexar_property.SOURCE_ID,
        "allowed": False,
        "reason": "review is unavailable",
        "reason_code": "access_review_required",
    }
    monkeypatch.setattr(
        query_bexar_property,
        "_access_contract",
        lambda _args: (_ for _ in ()).throw(
            AcquisitionUnavailableError(decision)
        ),
    )
    monkeypatch.setattr(
        query_bexar_property,
        "_arcgis_client",
        lambda *_args, **_kwargs: pytest.fail(
            "ArcGIS client was constructed after catalog denial"
        ),
    )
    logged = []
    monkeypatch.setattr(
        query_bexar_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_bexar_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"
    assert logged[0][1:] == (query_bexar_property.SOURCE_ID, None)


def test_detail_keeps_property_when_deed_enrichment_fails(monkeypatch):
    hgo = FakeHGOClient(
        detail=HGO_DETAIL,
        deed_error=TransportError(
            "deed endpoint unavailable",
            url=query_bexar_property.HGO_DEED_HISTORY_URL,
        ),
    )
    monkeypatch.setattr(
        query_bexar_property,
        "_hgo_client",
        lambda _args, _access: hgo,
    )
    monkeypatch.setattr(query_bexar_property, "log_search", lambda *args: None)

    result = query_bexar_property.execute(
        _args(command="detail", query="358951", year=2026, limit=1),
        access_decision={"allowed": True, "limits": {}},
    )

    assert result.status.value == "partial"
    assert result.records[0]["native_parcel_id"] == "358951"
    assert not result.records[0]["deed_history"]
    assert result.errors[0].code == "transport_error"
    assert hgo.detail_calls == [(358951, 2026)]
    assert hgo.deed_calls == [358951]


def test_geometry_lookup_batches_ids_and_requests_wgs84(monkeypatch):
    client = FakeArcGISClient(_fetch(GEOMETRY["features"]))
    constructed = []

    def fake_client(_args, _access, *, layer_url=query_bexar_property.TABLE_URL):
        constructed.append(layer_url)
        return client

    monkeypatch.setattr(query_bexar_property, "_arcgis_client", fake_client)

    geometries = query_bexar_property._fetch_geometry(
        _args(command="parcel", query="358951", geometry=True),
        {"allowed": True, "limits": {}},
        ["358951"],
    )

    assert constructed == [query_bexar_property.PARCEL_LAYER_URL]
    assert geometries["358951"]["rings"]
    assert client.calls[0]["where"] == (
        f"{query_bexar_property.GEOMETRY_PROPERTY_FIELD} IN (358951)"
    )
    assert client.calls[0]["parameters"] == {
        "orderByFields": query_bexar_property.GEOMETRY_ORDER_BY,
        "outSR": 4326,
    }
    assert client.calls[0]["return_geometry"] is True


def test_direct_cli_help_uses_repository_tool_pattern():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/query_bexar_property.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Bexar County" in result.stdout
    assert "detail" in result.stdout
