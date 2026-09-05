from __future__ import annotations

import copy
import json
import os
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_jackson_douglas_assessors as adapter
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import (
    TransportError,
    arcgis_declared_schema,
    schema_fingerprint,
)


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_jackson_douglas_assessors"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


def _packet(config: adapter.SourceConfig) -> dict[str, Any]:
    county = "jackson" if config.source_id == adapter.JACKSON_SOURCE_ID else "douglas"
    return _fixture(f"{county}_probe_packet")


def _args(
    command: str = "search",
    *,
    source: str = adapter.JACKSON_SOURCE_ID,
    query: str | None = "GOEBEL",
    **overrides: Any,
) -> Namespace:
    values = {
        "command": command,
        "source": source,
        "query": query,
        "field": "owner" if command == "search" else command,
        "limit": 100,
        "cursor": None,
        "geometry": False,
        "page_size": 2,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "retry_attempts": 1,
        "all_sources": False,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


class FakeClient:
    def __init__(
        self,
        config: adapter.SourceConfig,
        features: list[dict[str, Any]],
        *,
        metadata: Mapping[str, Any] | Exception | None = None,
        item_metadata: Mapping[str, Any] | Exception | None = None,
        count_script: list[int | Exception] | None = None,
        page_size: int = 2,
    ) -> None:
        packet = _packet(config)
        self.config = config
        self.features = sorted(
            copy.deepcopy(features),
            key=lambda feature: feature["attributes"][config.object_id_field],
        )
        self.metadata = (
            copy.deepcopy(packet["metadata"]) if metadata is None else metadata
        )
        self.item_metadata = (
            copy.deepcopy(packet["item_metadata"])
            if item_metadata is None
            else item_metadata
        )
        self.count_script = list(count_script or [])
        self.page_size = page_size
        self.calls: list[tuple[str, Any]] = []

    def fetch_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("metadata", None))
        if isinstance(self.metadata, Exception):
            raise self.metadata
        return self.metadata

    def fetch_item_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("item_metadata", None))
        if isinstance(self.item_metadata, Exception):
            raise self.item_metadata
        return self.item_metadata

    def fetch_count(self, where: str) -> int:
        self.calls.append(("count", where))
        if self.count_script:
            value = self.count_script.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return len(self.features)

    def fetch_page(
        self,
        *,
        where: str,
        offset: int,
        record_count: int,
        out_fields: str = "*",
        return_geometry: bool,
    ) -> tuple[Mapping[str, Any], ...]:
        self.calls.append(
            (
                "page",
                {
                    "where": where,
                    "offset": offset,
                    "record_count": record_count,
                    "out_fields": out_fields,
                    "return_geometry": return_geometry,
                },
            )
        )
        return tuple(copy.deepcopy(self.features[offset : offset + record_count]))


@pytest.fixture(autouse=True)
def _disable_search_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "log_search", lambda *_args, **_kwargs: None)


@pytest.mark.parametrize("config", (adapter.JACKSON, adapter.DOUGLAS))
def test_probe_fixtures_reproduce_verified_arcgis_contract(
    config: adapter.SourceConfig,
) -> None:
    packet = _packet(config)
    contract = adapter._metadata_schema(config, packet["metadata"])

    assert packet["source_id"] == config.source_id
    assert packet["count"] == config.baseline_count
    assert packet["observed_at"] == config.baseline_observed_at
    assert contract.object_id_field == "OBJECTID"
    assert contract.source_wkid == config.source_wkid
    assert contract.server_page_size == config.max_page_size
    assert contract.schema_fingerprint == packet["schema_fingerprint"]
    assert contract.schema_fingerprint == config.expected_schema_fingerprint
    assert schema_fingerprint(
        arcgis_declared_schema(packet["metadata"]["fields"])
    ) == config.expected_schema_fingerprint
    item = adapter._item_identity(config, packet["item_metadata"])
    assert item["item_id"] == config.service_item_id
    assert item["created"] == config.baseline_item_created
    assert item["modified"] == config.baseline_item_modified
    assert item["access"] == "public"


def test_jackson_normalization_preserves_owner_addresses_values_and_taxlot_keys() -> None:
    feature = _fixture("jackson_rich_feature")
    feature["geometry"] = _packet(adapter.JACKSON)["representative_feature"][
        "geometry"
    ]

    record = adapter._normalize_feature(
        adapter.JACKSON,
        feature,
        schema_value=adapter.JACKSON.expected_schema_fingerprint,
        geometry_requested=True,
    )

    assert record["native_parcel_id"] == "30-3E-100"
    assert record["alternate_parcel_ids"] == ["303E100", "303E", "100"]
    assert record["map_taxlot"] == {
        "combined": "30-3E-100",
        "compact": "303E100",
        "map_number": "303E",
        "alternate_map_number": "303E",
        "taxlot": "100",
    }
    assert record["assessment_account_ids"] == ["10507550"]
    assert record["owners"][0]["raw_name"] == "GOEBEL CHARLES A JR TRUSTEE"
    assert record["owners"][0]["role"] == "fee_owner"
    assert record["care_of"] == "RICHARD GOEBEL TRUSTEE"
    assert record["mailing_address"] == {
        "raw": "38 PACHECO AVE",
        "address_lines": ["38 PACHECO AVE"],
        "city_state_zip_raw": None,
        "city": "FAIRFAX",
        "state": "CA",
        "postal_code": "94930",
        "country": "US",
    }
    assert record["situs_address"]["raw"] == "57815 HWY 230"
    assert record["parcel_acres"] == 0
    assert record["assessment"] == {
        "market_land": 0,
        "market_improvements": 104680,
        "market_total": 104680,
        "assessed_land": 0,
        "assessed_improvements": 36710,
        "assessed_total": 36710,
        "currency": "USD",
    }
    assert record["physical_characteristics"]["year_built"] == 1930
    assert record["classification"]["tax_code"] == "5901"
    assert record["source_geometry_crs"] == "EPSG:6827"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["raw_attributes"]["ACCOUNT"] == 10507550


def test_douglas_normalization_preserves_legal_sale_value_and_account_context() -> None:
    feature = _fixture("douglas_rich_feature")
    feature["geometry"] = _packet(adapter.DOUGLAS)["representative_feature"][
        "geometry"
    ]

    record = adapter._normalize_feature(
        adapter.DOUGLAS,
        feature,
        schema_value=adapter.DOUGLAS.expected_schema_fingerprint,
        geometry_requested=True,
    )

    assert record["native_parcel_id"] == "19080000101"
    assert record["assessment_account_ids"] == ["R10015"]
    assert record["owners"][0]["raw_name"] == "Cg Fcsf II Seed Asset 2 L.L.C."
    assert record["mailing_address"]["raw"] == (
        "8809 Lenox Pointe Dr Ste B, Charlotte, NC 28273"
    )
    assert record["situs_address"]["raw"] == (
        "0 Us Highway 101, Westlake, OR 97493"
    )
    assert record["parcel_acres"] == 113.7
    assert record["parcel_acre_observations"] == {
        "account_acreage": 113.7,
        "map_taxlot_acreage": 113.7,
        "total_acreage": 121.722,
    }
    assert record["assessment"] == {
        "assessed_value": 68436,
        "market_land": 125068,
        "market_improvements": 0,
        "market_total": 125068,
        "currency": "USD",
    }
    assert record["legal_description"] == (
        "TRACT LOTS 1, 2 & 3 IN SEC 7, ACRES 113.70"
    )
    assert record["published_instrument_and_sale_reference"] == {
        "instrument_number": "2025-11606",
        "sale_date": "2025-09-25",
        "scope": "published_on_current_parcel_row",
    }
    assert record["classification"]["tax_code_area"] == "00150"
    assert record["source_geometry_crs"] == "EPSG:2270"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["raw_attributes"]["PROP_ID"] == "R10015"


def test_sources_expose_catalog_constants_and_distinct_complements() -> None:
    payload = adapter.execute(_args(command="sources", query=None))

    assert isinstance(payload, dict)
    assert adapter.CATALOG_METADATA is adapter.SOURCE_CATALOG_METADATA
    assert set(adapter.CATALOG_METADATA) == set(adapter.SOURCES)
    assert {source["source_id"] for source in payload["sources"]} == set(
        adapter.SOURCES
    )
    jackson = next(
        source
        for source in payload["sources"]
        if source["source_id"] == adapter.JACKSON_SOURCE_ID
    )
    assert set(jackson["search_fields"]) == {
        "account",
        "address",
        "owner",
        "parcel",
    }
    assert {
        item["source_id"] for item in jackson["complementary_sources"]
    } >= {
        adapter.JACKSON_DATA_REQUEST_SOURCE_ID,
        adapter.JACKSON_MAPS_SOURCE_ID,
        adapter.JACKSON_RECORDER_SOURCE_ID,
    }
    douglas = next(
        source
        for source in payload["sources"]
        if source["source_id"] == adapter.DOUGLAS_SOURCE_ID
    )
    bulk = douglas["complementary_sources"][0]
    assert bulk["source_id"] == adapter.DOUGLAS_BULK_SOURCE_ID
    assert bulk["url"] == adapter.DOUGLAS_BULK_URL
    assert "Certified All Property values and Present Owner CSV" in bulk[
        "published_products"
    ]
    assert len(payload["process_learnings"]) == 3


def test_source_specific_where_clauses_handle_text_numeric_and_quotes() -> None:
    assert adapter._where(
        adapter.JACKSON,
        operation="account",
        selector="10507550",
        search_field="account",
    ) == "ACCOUNT = 10507550"
    assert adapter._where(
        adapter.DOUGLAS,
        operation="parcel",
        selector="19080000101",
        search_field="parcel",
    ) == "UPPER(TAXID) = '19080000101'"
    assert adapter._where(
        adapter.DOUGLAS,
        operation="owner",
        selector="O'Neil",
        search_field="owner",
    ) == "UPPER(NAME) LIKE '%O''NEIL%'"
    assert adapter._where(
        adapter.DOUGLAS,
        operation="search",
        selector="2025-11606",
        search_field="instrument",
    ) == "UPPER(INST_NO) LIKE '%2025-11606%'"

    with pytest.raises(adapter.SourceSelectionError, match="not compatible"):
        adapter._where(
            adapter.JACKSON,
            operation="account",
            selector="R10015",
            search_field="account",
        )
    with pytest.raises(
        adapter.SourceSelectionError,
        match="does not publish a searchable instrument",
    ):
        adapter._where(
            adapter.JACKSON,
            operation="search",
            selector="2025-11606",
            search_field="instrument",
        )


@pytest.mark.parametrize(
    ("command", "query", "field", "where_fragment"),
    (
        ("search", "GOEBEL", "owner", "UPPER(FEEOWNER) LIKE '%GOEBEL%'"),
        ("owner", "GOEBEL", "owner", "UPPER(FEEOWNER) LIKE '%GOEBEL%'"),
        ("address", "HWY 230", "address", "UPPER(SITEADD) LIKE '%HWY 230%'"),
        ("parcel", "30-3E-100", "parcel", "UPPER(TM_MAPLOT) = '30-3E-100'"),
        ("account", "10507550", "account", "ACCOUNT = 10507550"),
    ),
)
def test_required_record_commands_execute_source_specific_queries(
    command: str,
    query: str,
    field: str,
    where_fragment: str,
) -> None:
    client = FakeClient(
        adapter.JACKSON,
        [_fixture("jackson_rich_feature")],
    )

    result = adapter.execute(
        _args(command=command, query=query, field=field),
        client=client,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok"
    assert result.query.query.operation == command
    assert result.records[0]["native_parcel_id"] == "30-3E-100"
    first_count_where = next(
        where for call, where in client.calls if call == "count"
    )
    assert where_fragment in first_count_where


def _jackson_features(count: int) -> list[dict[str, Any]]:
    base = _fixture("jackson_rich_feature")
    features: list[dict[str, Any]] = []
    for index in range(count):
        feature = copy.deepcopy(base)
        feature["attributes"]["OBJECTID"] = 2 + index
        feature["attributes"]["TM_MAPLOT"] = f"30-3E-{100 + index}"
        feature["attributes"]["MAPLOT"] = f"303E{100 + index}"
        features.append(feature)
    return features


def test_count_snapshot_pagination_cursor_round_trips_with_oid_anchor() -> None:
    client = FakeClient(
        adapter.JACKSON,
        _jackson_features(3),
        page_size=1,
    )
    first = adapter.execute(
        _args(command="owner", limit=2, page_size=1),
        client=client,
    )

    assert isinstance(first, PublicRecordsResult)
    assert first.status.value == "ok"
    assert len(first.records) == 2
    assert first.next_cursor
    assert first.records[0]["retrieval_snapshot"] == {
        "total_matching_records": 3,
        "window_start_offset": 0,
        "window_returned_records": 2,
        "window_complete": False,
        "continuation_available": True,
        "pages_fetched": 2,
        "schema_fingerprint": adapter.JACKSON.expected_schema_fingerprint,
        "service_data_last_edit": None,
    }

    second = adapter.execute(
        _args(
            command="owner",
            limit=2,
            cursor=first.next_cursor,
            page_size=1,
        ),
        client=client,
    )

    assert isinstance(second, PublicRecordsResult)
    assert second.status.value == "ok"
    assert [record["object_id"] for record in second.records] == [4]
    assert second.next_cursor is None
    boundary_calls = [
        details
        for call, details in client.calls
        if call == "page" and details["out_fields"] == "OBJECTID"
    ]
    assert boundary_calls == [
        {
            "where": (
                "(UPPER(FEEOWNER) LIKE '%GOEBEL%' OR "
                "UPPER(CONTRACT) LIKE '%GOEBEL%')"
            ),
            "offset": 1,
            "record_count": 1,
            "out_fields": "OBJECTID",
            "return_geometry": False,
        }
    ]


def test_cursor_is_bound_to_source_operation_filter_and_geometry() -> None:
    client = FakeClient(adapter.JACKSON, _jackson_features(3))
    first = adapter.execute(
        _args(command="owner", limit=1),
        client=client,
    )
    assert isinstance(first, PublicRecordsResult)
    assert first.next_cursor

    changed_query = adapter.execute(
        _args(
            command="owner",
            query="TRUSTEE",
            limit=1,
            cursor=first.next_cursor,
        ),
        client=client,
    )
    assert isinstance(changed_query, PublicRecordsResult)
    assert changed_query.status.value == "unavailable"
    assert changed_query.errors[0].code == "cursor_query_mismatch"

    changed_geometry = adapter.execute(
        _args(
            command="owner",
            limit=1,
            cursor=first.next_cursor,
            geometry=True,
        ),
        client=client,
    )
    assert isinstance(changed_geometry, PublicRecordsResult)
    assert changed_geometry.status.value == "unavailable"
    assert changed_geometry.errors[0].code == "cursor_query_mismatch"


def test_count_change_after_cursor_is_partial_and_not_resumable() -> None:
    first_client = FakeClient(
        adapter.JACKSON,
        _jackson_features(4),
        count_script=[3, 3],
    )
    first = adapter.execute(
        _args(command="owner", limit=2),
        client=first_client,
    )
    assert isinstance(first, PublicRecordsResult)
    assert first.next_cursor

    second_client = FakeClient(
        adapter.JACKSON,
        _jackson_features(4),
        count_script=[4, 4],
    )
    second = adapter.execute(
        _args(command="owner", limit=2, cursor=first.next_cursor),
        client=second_client,
    )

    assert isinstance(second, PublicRecordsResult)
    assert second.status.value == "partial"
    assert len(second.records) == 2
    assert second.next_cursor is None
    assert [error.code for error in second.errors] == [
        "count_changed_since_cursor"
    ]


def test_schema_drift_and_transport_failure_are_not_empty_results() -> None:
    packet = _packet(adapter.DOUGLAS)
    metadata = copy.deepcopy(packet["metadata"])
    metadata["fields"] = [
        field for field in metadata["fields"] if field["name"] != "LEGAL"
    ]
    drift = adapter.execute(
        _args(
            command="parcel",
            source=adapter.DOUGLAS_SOURCE_ID,
            query="19080000101",
        ),
        client=FakeClient(
            adapter.DOUGLAS,
            [_fixture("douglas_rich_feature")],
            metadata=metadata,
        ),
    )

    assert isinstance(drift, PublicRecordsResult)
    assert drift.status.value == "source_changed"
    assert drift.records == ()
    assert drift.errors[0].code == "source_schema_changed"
    assert drift.errors[0].details["missing_fields"] == ("LEGAL",)

    unavailable = adapter.execute(
        _args(command="owner"),
        client=FakeClient(
            adapter.JACKSON,
            [],
            metadata=TransportError(
                "network failed",
                url=adapter.JACKSON_LAYER_URL,
            ),
        ),
    )
    assert isinstance(unavailable, PublicRecordsResult)
    assert unavailable.status.value == "unavailable"
    assert unavailable.records == ()
    assert unavailable.errors[0].code == "transport_error"


def test_authoritative_zero_count_is_no_results() -> None:
    result = adapter.execute(
        _args(command="owner"),
        client=FakeClient(adapter.JACKSON, []),
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


@pytest.mark.parametrize("config", (adapter.JACKSON, adapter.DOUGLAS))
def test_probe_reports_standard_packet_and_representative_row(
    config: adapter.SourceConfig,
) -> None:
    packet = _packet(config)
    result = adapter.execute(
        _args(
            command="probe",
            source=config.source_id,
            query=None,
        ),
        client=FakeClient(
            config,
            [packet["representative_feature"]],
            count_script=[packet["count"], 1],
        ),
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["service_identity"]["service_item_id"] == config.service_item_id
    assert probe["layer_identity"] == {
        "layer_url": config.layer_url,
        "layer_id": config.layer_id,
        "layer_name": config.expected_layer_name,
        "object_id_field": config.object_id_field,
        "geometry_type": "esriGeometryPolygon",
    }
    assert probe["item_identity"]["modified"] == config.baseline_item_modified
    assert probe["component_total_count"] == config.baseline_count
    assert probe["maximum_page_size"] == config.max_page_size
    assert probe["source_crs"] == config.original_crs
    assert probe["schema_fingerprint"] == config.expected_schema_fingerprint
    assert probe["schema_baseline"]["matches"] is True
    assert probe["update_metadata"]["layer_editing_info"] is None
    assert probe["sentinel_count"] == 1
    assert probe["representative_row"]["geometry_crs"] == "EPSG:4326"
    assert probe["representative_row"]["raw_attributes"]
    assert probe["complementary_sources"]


def test_parser_supports_required_source_commands() -> None:
    parser = adapter.build_parser()
    source_args = [
        "--source",
        adapter.JACKSON_SOURCE_ID,
        "--limit",
        "5",
        "--output",
        "/tmp/result.json",
    ]

    for command in ("search", "owner", "address", "parcel", "account"):
        parsed = parser.parse_args([command, "example", *source_args])
        assert parsed.command == command
        assert parsed.source == adapter.JACKSON_SOURCE_ID
        assert parsed.limit == 5

    sources = parser.parse_args(["sources", "--json"])
    assert sources.command == "sources"
    assert sources.json_out is True
    probe = parser.parse_args(["probe", "--all", "--json"])
    assert probe.command == "probe"
    assert probe.all_sources is True


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_JACKSON_DOUGLAS") != "1",
    reason="set RUN_LIVE_OR_JACKSON_DOUGLAS=1 for official ArcGIS probes",
)
@pytest.mark.parametrize("source_id", sorted(adapter.SOURCES))
def test_live_official_component_probe(source_id: str) -> None:
    result = adapter.execute(
        _args(
            command="probe",
            source=source_id,
            query=None,
            timeout=45.0,
            minimum_interval=0.1,
            retry_attempts=3,
        ),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok", result.to_dict()
    probe = result.records[0]
    assert probe["component_total_count"] > 0
    assert probe["sentinel_count"] > 0
    assert probe["schema_baseline"]["matches"] is True
