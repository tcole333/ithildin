from __future__ import annotations

import copy
import json
import subprocess
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_miami_dade_property
from tools.public_records_http import PaginatedFetch, TransportError


FIXTURE_DIR = Path("tests/fixtures/public_records/miami_dade")
OWNER_PAGE_1 = json.loads(
    (FIXTURE_DIR / "owner_page_1.json").read_text(encoding="utf-8")
)
OWNER_PAGE_2 = json.loads(
    (FIXTURE_DIR / "owner_page_2.json").read_text(encoding="utf-8")
)
ADDRESS_RESULT = json.loads(
    (FIXTURE_DIR / "address_result.json").read_text(encoding="utf-8")
)
PROPERTY_DETAIL = json.loads(
    (FIXTURE_DIR / "property_detail.json").read_text(encoding="utf-8")
)
PARCEL_GEOMETRY = json.loads(
    (FIXTURE_DIR / "parcel_geometry.json").read_text(encoding="utf-8")
)


def _args(command="owner", query="MIAMI-DADE COUNTY", **overrides):
    values = {
        "command": command,
        "query": query,
        "unit": None,
        "limit": 2,
        "cursor": None,
        "geometry": False,
        "page_size": 200,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "catalog_db": "unused-catalog.db",
        "catalog_config": "unused-sources.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


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
            raise AssertionError("unexpected Miami-Dade source request")
        return FixtureResponse(self.payloads.pop(0))


class FakeProxyClient:
    def __init__(self, *, detail=None, search=None, error=None):
        self.detail_payload = detail
        self.search_payload = search
        self.error = error
        self.detail_calls = []
        self.search_calls = []

    def detail(self, folio):
        self.detail_calls.append(folio)
        if self.error is not None:
            raise self.error
        return self.detail_payload

    def search(self, operation, selector, **kwargs):
        self.search_calls.append((operation, selector, kwargs))
        if self.error is not None:
            raise self.error
        return self.search_payload


class FakeArcGISClient:
    def __init__(self, fetched):
        self.fetched = fetched
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return self.fetched


def _fetch(records, *, next_cursor=None, truncated=False, schema="fixture-schema"):
    return PaginatedFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        schema={"kind": "fixture"},
        schema_fingerprint=schema,
        pages_fetched=1,
        requests_made=1,
        truncated_by_cap=truncated,
    )


def test_proxy_search_uses_inclusive_nonoverlapping_ranges_and_cursor():
    transport = QueueTransport([OWNER_PAGE_1, OWNER_PAGE_2])
    client = query_miami_dade_property.MiamiDadePAClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search(
        "owner",
        "MIAMI-DADE COUNTY",
        requested_limit=4,
        page_size=2,
    )

    assert [row["Strap"] for row in fetched.records] == [
        "01-0100-000-0022",
        "01-0100-000-0125",
        "01-0100-000-0280",
        "01-0100-000-0292",
    ]
    assert [
        (call["params"]["from"], call["params"]["to"])
        for call in transport.calls
    ] == [(1, 2), (3, 4)]
    assert fetched.next_cursor == "miami-pa:owner:offset:4"
    assert fetched.pages_fetched == 2
    assert fetched.requests_made == 2


def test_proxy_cursor_is_operation_scoped():
    client = query_miami_dade_property.MiamiDadePAClient(
        transport=QueueTransport([]),
        minimum_interval=0,
    )

    with pytest.raises(ValueError, match="Miami-Dade owner cursor"):
        client.search(
            "owner",
            "MIAMI-DADE COUNTY",
            requested_limit=1,
            page_size=1,
            cursor="miami-pa:address:offset:2",
        )


def test_caller_ceiling_is_distinct_from_source_page_size():
    second_page = copy.deepcopy(OWNER_PAGE_2)
    second_page["MinimumPropertyInfos"] = second_page[
        "MinimumPropertyInfos"
    ][:1]
    transport = QueueTransport([OWNER_PAGE_1, second_page])
    client = query_miami_dade_property.MiamiDadePAClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search(
        "owner",
        "MIAMI-DADE COUNTY",
        requested_limit=5,
        page_size=2,
        max_records=3,
    )

    assert len(fetched.records) == 3
    assert fetched.truncated_by_cap is True
    assert fetched.next_cursor == "miami-pa:owner:offset:3"
    assert [
        (call["params"]["from"], call["params"]["to"])
        for call in transport.calls
    ] == [(1, 2), (3, 3)]
    assert "caller-selected ceiling is 3" in fetched.warnings[0]


def test_catalog_page_facts_and_caller_page_size_are_kept_distinct():
    args = _args(page_size=2_000)
    access = {
        "allowed": True,
        "limits": {
            "property_search_page_size": 200,
            "parcel_geometry_page_size": 1_000,
        },
    }

    assert query_miami_dade_property._proxy_page_size(args, access) == 200
    geometry_client = query_miami_dade_property._arcgis_client(
        args,
        access,
    )
    assert geometry_client.page_size == 1_000
    assert isinstance(
        geometry_client.transport.adapters["https://"],
        query_miami_dade_property._SystemTrustHTTPAdapter,
    )


def test_address_search_includes_unit_and_verified_proxy_operation():
    transport = QueueTransport([ADDRESS_RESULT])
    client = query_miami_dade_property.MiamiDadePAClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search(
        "address",
        "111 NW 1 ST",
        requested_limit=1,
        page_size=10,
        unit="12A",
    )

    assert fetched.next_cursor is None
    assert fetched.records[0]["Strap"] == "01-4137-023-0020"
    assert transport.calls[0]["params"] == {
        "Operation": "GetAddress",
        "clientAppName": "PropertySearch",
        "from": 1,
        "myAddress": "111 NW 1 ST",
        "myUnit": "12A",
        "to": 1,
    }


def test_search_normalization_preserves_folio_owner_and_situs_identity():
    record = query_miami_dade_property._normalize_search_record(
        ADDRESS_RESULT["MinimumPropertyInfos"][0],
        response_schema_fingerprint="search-schema",
    )

    assert record["canonical_ref"] == (
        "PROPERTY:us-fl-miami-dade-property-appraiser/12086/"
        "parcel/0141370230020"
    )
    assert record["native_parcel_id"] == "0141370230020"
    assert record["folio_number"] == "01-4137-023-0020"
    assert record["record_view"] == "search_summary"
    assert record["owners"] == []
    assert record["owner_display_lines"] == [
        "MIAMI-DADE COUNTY",
        "GSA R/E MGMT-DGC",
    ]
    assert record["owner_display_group"]["requires_detail_resolution"] is True
    assert [
        line["source_field"]
        for line in record["owner_display_group"]["lines"]
    ] == ["Owner1", "Owner2"]
    assert record["situs_address"]["raw"] == "111 NW 1 ST"
    assert record["response_schema_fingerprint"] == "search-schema"
    assert "tax_year" not in record


def test_search_owner_display_block_is_not_split_into_owner_assertions():
    source_row = copy.deepcopy(
        ADDRESS_RESULT["MinimumPropertyInfos"][0]
    )
    source_row.update(
        {
            "Owner1": "EXAMPLE LONG-NAME",
            "Owner2": "C/O EXAMPLE MANAGEMENT",
            "Owner3": "HOLDINGS LLC",
        }
    )

    record = query_miami_dade_property._normalize_search_record(
        source_row,
        response_schema_fingerprint="search-schema",
    )

    assert record["owners"] == []
    assert record["owner_display_lines"] == [
        "EXAMPLE LONG-NAME",
        "C/O EXAMPLE MANAGEMENT",
        "HOLDINGS LLC",
    ]
    assert record["owner_display_group"]["lines"][2] == {
        "source_field": "Owner3",
        "position": 3,
        "raw_text": "HOLDINGS LLC",
        "classification": "display_line",
    }
    assert record["owner_contacts"] == [
        {
            "raw_name": "C/O EXAMPLE MANAGEMENT",
            "role": "care_of_contact",
            "assertion_type": "source_contact_line",
            "confidence": "high",
            "source_field": "Owner2",
        }
    ]


def test_detail_normalization_preserves_assessment_and_sale_history_contract():
    record = query_miami_dade_property._normalize_detail(PROPERTY_DETAIL)

    assert record["canonical_ref"] == (
        "PROPERTY:us-fl-miami-dade-property-appraiser/12086/"
        "parcel/0101060501010"
    )
    assert record["record_view"] == "property_detail"
    assert [owner["raw_name"] for owner in record["owners"]] == [
        "NW MIAMI OWNER LLC"
    ]
    assert record["owner_display_lines"] == [
        "NW MIAMI OWNER LLC",
        "C/O THE JOHN BUCK COMPANY",
    ]
    assert record["owner_contacts"][0]["raw_name"] == (
        "C/O THE JOHN BUCK COMPANY"
    )
    assert record["owner_contacts"][0]["role"] == "care_of_contact"
    assert record["tax_year"] == 2026
    assert record["assessment"]["land_value"] == 10433000
    assert record["assessment"]["improvement_value"] == 0
    assert record["assessment"]["parcel_value"] == 10433000
    assert record["assessment"]["assessed_value"] == 8033410
    assert [
        item["tax_year"] for item in record["assessment_history"]
    ] == [2026, 2025, 2024]
    assert {
        "tax_year",
        "land_value",
        "improvement_value",
        "parcel_value",
        "assessed_value",
        "currency",
        "assessment_class",
        "raw",
    }.issubset(record["assessment_history"][0])

    sale = record["sale_history"][0]
    assert sale["source_document_ref"] == "OR:33574:1907"
    assert sale["sale_date"] == "2023-02-06"
    assert sale["sale_date_raw"] == "2/6/2023"
    assert sale["date_precision"] == "day"
    assert sale["consideration"] == 39500000
    assert sale["instrument_type"] == "WDE"
    assert sale["book"] == "33574"
    assert sale["page"] == "1907"
    assert sale["grantors"] == ["BH 18 INVESTMENTS LLC"]
    assert sale["grantees"] == ["NW MIAMI OWNER LLC"]
    assert sale["qualified_flag"] == "Q"
    assert sale["reason_code"] == "05"
    assert sale["source_document_url"].startswith(
        query_miami_dade_property.CLERK_RECORD_URL
    )
    assert len(record["response_schema_fingerprint"]) == 64


def test_placeholder_record_book_and_page_fall_back_to_source_sale_id():
    history = query_miami_dade_property._sale_history(
        {
            "SalesInfos": [
                {
                    "SaleId": 6,
                    "DateOfSale": "7/1/1976",
                    "OfficialRecordBook": "00000",
                    "OfficialRecordPage": "00000",
                }
            ]
        }
    )

    assert history[0]["source_document_ref"] == "SALE:6"
    assert history[0]["book"] == "00000"
    assert history[0]["page"] == "00000"
    assert history[0]["sale_date"] == "1976-07-01"


def test_geometry_normalization_and_query_preserve_epsg_4326(monkeypatch):
    feature = PARCEL_GEOMETRY["features"][0]
    normalized = query_miami_dade_property._normalize_geometry(
        feature,
        response_schema_fingerprint="geometry-schema",
    )

    assert normalized["record_view"] == "parcel_geometry"
    assert normalized["native_parcel_id"] == "0101060501010"
    assert normalized["source_object_id"] == 373
    assert normalized["geometry_format"] == "esri_json"
    assert normalized["geometry_crs"] == "EPSG:4326"
    assert normalized["geometry"]["rings"][0][0] == [
        -80.19722730589267,
        25.779342403039013,
    ]
    assert "tax_year" not in normalized

    client = FakeArcGISClient(_fetch([feature], schema="geometry-schema"))
    monkeypatch.setattr(
        query_miami_dade_property,
        "_arcgis_client",
        lambda args, access: client,
    )
    records, fetched = query_miami_dade_property._fetch_geometry(
        _args(command="geometry", query="0101060501010"),
        {"allowed": True, "limits": {}},
        ["01-0106-050-1010"],
        requested_limit=1,
    )

    assert records[0]["geometry_crs"] == "EPSG:4326"
    assert fetched is not None
    assert client.calls[0]["where"] == "FOLIO IN ('0101060501010')"
    assert client.calls[0]["parameters"]["outSR"] == 4326
    assert client.calls[0]["requested_limit"] == 1
    assert client.calls[0]["return_geometry"] is True


def test_detail_execution_can_attach_geometry_without_changing_property_view(
    monkeypatch,
):
    proxy = FakeProxyClient(detail=PROPERTY_DETAIL)
    geometry = query_miami_dade_property._normalize_geometry(
        PARCEL_GEOMETRY["features"][0],
        response_schema_fingerprint="geometry-schema",
    )
    logged = []
    monkeypatch.setattr(
        query_miami_dade_property,
        "_proxy_client",
        lambda args, access: proxy,
    )
    monkeypatch.setattr(
        query_miami_dade_property,
        "_fetch_geometry",
        lambda *args, **kwargs: ([geometry], None),
    )
    monkeypatch.setattr(
        query_miami_dade_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_miami_dade_property.execute(
        _args(
            command="detail",
            query="01-0106-050-1010",
            geometry=True,
        ),
        access_decision={"allowed": True, "limits": {}},
    )

    assert result.status.value == "ok"
    assert proxy.detail_calls == ["0101060501010"]
    assert result.records[0]["record_view"] == "property_detail"
    assert result.records[0]["geometry_format"] == "esri_json"
    assert result.records[0]["geometry_crs"] == "EPSG:4326"
    assert result.records[0]["geometry"]["rings"][0][0] == tuple(
        geometry["geometry"]["rings"][0][0]
    )
    assert logged[0][1:] == (query_miami_dade_property.SOURCE_ID, 1)


def test_transport_failure_is_not_logged_as_a_true_zero(monkeypatch):
    proxy = FakeProxyClient(
        error=TransportError(
            "network unavailable",
            url=query_miami_dade_property.PROXY_URL,
        )
    )
    logged = []
    monkeypatch.setattr(
        query_miami_dade_property,
        "_proxy_client",
        lambda args, access: proxy,
    )
    monkeypatch.setattr(
        query_miami_dade_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_miami_dade_property.execute(
        _args(),
        access_decision={"allowed": True, "limits": {}},
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "transport_error"
    assert logged[0][1:] == (query_miami_dade_property.SOURCE_ID, None)


def test_direct_script_import_and_capability_surface():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "tools/query_miami_dade_property.py"),
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Miami-Dade Property Appraiser" in result.stdout
    parser = query_miami_dade_property.build_parser()
    assert parser.parse_args(["owner", "MIAMI-DADE COUNTY"]).command == "owner"
    assert parser.parse_args(["history", "0101060501010"]).command == "history"
    assert parser.parse_args(["geometry", "0101060501010"]).command == "geometry"
