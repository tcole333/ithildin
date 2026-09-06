from __future__ import annotations

import copy
import json
import os
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_lane_marion_parcels as adapter
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import TransportError


FIXTURE_ROOT = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_lane_marion"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


def _args(
    command: str = "search",
    *,
    source: str = adapter.LANE_PARCELS_SOURCE_ID,
    query: str = "BLM",
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


def _metadata(
    config: adapter.SourceConfig,
    *,
    missing: str | None = None,
    maximum: int = 2_000,
) -> dict[str, Any]:
    fields = []
    for name in config.required_fields:
        if name == missing:
            continue
        fields.append(
            {
                "name": name,
                "alias": name,
                "type": (
                    "esriFieldTypeOID"
                    if name == config.object_id_field
                    else "esriFieldTypeString"
                ),
                "nullable": name != config.object_id_field,
            }
        )
    return {
        "name": config.expected_layer_name,
        "serviceItemId": config.service_item_id,
        "maxRecordCount": maximum,
        "fields": fields,
        "advancedQueryCapabilities": {
            "supportsPagination": True,
            "supportsOrderBy": True,
        },
        "editingInfo": {"dataLastEditDate": 1_757_969_144_628},
    }


class FakeClient:
    def __init__(
        self,
        config: adapter.SourceConfig,
        features: list[dict[str, Any]],
        *,
        metadata: Mapping[str, Any] | Exception | None = None,
        count_script: list[int | Exception] | None = None,
        page_size: int = 2,
    ) -> None:
        self.config = config
        self.features = sorted(
            copy.deepcopy(features),
            key=lambda feature: feature["attributes"][config.object_id_field],
        )
        self.metadata = _metadata(config) if metadata is None else metadata
        self.count_script = list(count_script or [])
        self.page_size = page_size
        self.calls: list[tuple[str, Any]] = []

    def fetch_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("metadata", None))
        if isinstance(self.metadata, Exception):
            raise self.metadata
        return self.metadata

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


def test_lane_parcel_normalization_preserves_owner_join_keys_and_geometry() -> None:
    record = adapter._normalize_feature(
        adapter.LANE_PARCELS,
        _fixture("lane_parcel"),
        schema_value="lane-schema",
        geometry_requested=True,
    )

    assert record["record_kind"] == "parcel"
    assert record["native_parcel_id"] == "1501000000100"
    assert record["assessment_account_ids"] == ["0000016"]
    assert record["snapshot_complete"] is True
    assert record["owners"][0]["raw_name"] == "US Dept of Interior BLM"
    assert record["mailing_address"]["address_lines"] == ["PO Box 10226"]
    assert record["parcel_acres"] == 54.11808539
    assert record["parcel_acre_observations"] == {
        "map_acres": 54.11808539,
        "assessor_acres_raw": "54.39",
    }
    assert record["zoning_and_plan"]["plan_description"] == "Forest"
    assert record["related_components"][0]["source_id"] == (
        adapter.LANE_SALES_SOURCE_ID
    )
    assert record["related_components"][0]["join_keys"]["map_taxlot"] == (
        "1501000000100"
    )
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry_lineage"]["source_crs"] == "EPSG:2914"
    assert record["raw_attributes"]["OWNNAME"] == "US Dept of Interior BLM"


def test_lane_sale_is_distinct_record_with_semantic_identity_and_join_keys() -> None:
    record = adapter._normalize_feature(
        adapter.LANE_SALES,
        _fixture("lane_sale"),
        schema_value="sale-schema",
        geometry_requested=False,
    )

    assert record["record_kind"] == "sale_reference"
    assert len(record["native_sale_id"]) == 64
    assert record["join_keys"] == {
        "assessment_account_id": "0057313",
        "map_taxlot": "1605070001100",
        "related_source_id": adapter.LANE_PARCELS_SOURCE_ID,
    }
    assert record["instrument_reference"] == {
        "instrument_number": "2024-019914",
        "instrument_type": "WD",
        "recording_date": "2024-07-10",
        "source_kind": "assessor_sale_analysis_reference",
    }
    assert record["sale"]["consideration"] == 556000
    assert record["sale"]["reject_code"] == "Y - Tried to Confirm Sale"
    assert record["coverage_period"]["source_label"] == "last 3 years"
    assert record["source_geometry_crs"] == "EPSG:2914"
    assert "geometry" not in record


def test_marion_normalization_preserves_values_latest_sale_links_and_crs() -> None:
    record = adapter._normalize_feature(
        adapter.MARION_PARCELS,
        _fixture("marion_parcel"),
        schema_value="marion-schema",
        geometry_requested=True,
    )

    assert record["native_parcel_id"] == "032W290000400"
    assert record["alternate_parcel_ids"] == ["032W29 00400"]
    assert record["assessment_account_ids"] == [
        "510174",
        "R10174",
        "510175",
        "510177",
    ]
    assert record["snapshot_complete"] is True
    assert record["parcel_acres"] == 166.6
    assert record["parcel_acre_observations"] == {
        "published_acres": 166.6,
    }
    assert record["owners"][0]["raw_name"] == "KCK PARTNERS LLC"
    assert record["legal_and_plat"] == {
        "plat_name": "SAMPLE FARM PLAT",
        "block": "2",
        "lot": "4",
    }
    assert record["latest_verified_sale_reference"]["scope"] == (
        "latest_transfer_coded_as_verified_sale"
    )
    assert record["latest_verified_sale_reference"]["instrument_number"] == ("35450047")
    assert record["assessment"]["real_market_total"] == 1833580
    assert record["assessment"]["assessed_value"] == 276968
    assert record["official_links"]["property_record"].startswith(
        "https://mcasr.co.marion.or.us/"
    )
    assert record["source_centroid"]["crs"] == "EPSG:2913"
    assert record["geometry_crs"] == "EPSG:4326"


@pytest.mark.parametrize(
    ("config", "fixture_name", "identity_fields"),
    (
        (
            adapter.LANE_PARCELS,
            "lane_parcel",
            ("MAPTAXLOT", "RLID"),
        ),
        (
            adapter.MARION_PARCELS,
            "marion_parcel",
            ("TAXLOT", "ALT_TAXLOT"),
        ),
    ),
)
def test_parcel_identity_falls_back_consistently_to_source_object_id(
    config: adapter.SourceConfig,
    fixture_name: str,
    identity_fields: tuple[str, ...],
) -> None:
    feature = _fixture(fixture_name)
    for field_name in identity_fields:
        feature["attributes"][field_name] = None

    record = adapter._normalize_feature(
        config,
        feature,
        schema_value="schema",
        geometry_requested=False,
    )

    assert record["native_parcel_id"] == record["source_record_id"]
    assert record["parcel_identity_basis"] == "source_object_id_fallback"
    assert record["canonical_ref"].endswith(
        f"/{record['record_kind']}/{record['source_record_id']}"
    )


def test_source_listing_exposes_component_scope_complements_and_learnings() -> None:
    payload = adapter.execute(_args(command="sources"))

    assert isinstance(payload, dict)
    assert {source["source_id"] for source in payload["sources"]} == set(
        adapter.SOURCES
    )
    lane_sales = next(
        source
        for source in payload["sources"]
        if source["source_id"] == adapter.LANE_SALES_SOURCE_ID
    )
    assert lane_sales["metadata"]["record_kind"] == "sale_reference"
    assert "instrument" in lane_sales["search_fields"]
    assert lane_sales["complementary_sources"][0]["access"] == (
        "public_library_or_copy_request"
    )
    marion = next(
        source
        for source in payload["sources"]
        if source["source_id"] == adapter.MARION_PARCELS_SOURCE_ID
    )
    assert {item["access"] for item in marion["complementary_sources"]} == {
        "public_interactive",
        "public_download",
        "paid_request",
    }
    assert len(payload["process_learnings"]) == 3


def _lane_features(count: int) -> list[dict[str, Any]]:
    base = _fixture("lane_parcel")
    features = []
    for index in range(count):
        feature = copy.deepcopy(base)
        feature["attributes"]["OBJECTID"] = 2 + index
        feature["attributes"]["MAPTAXLOT"] = f"15010000001{index:02d}"
        feature["attributes"]["RLID"] = f"15010000001{index:02d}"
        features.append(feature)
    return features


def test_count_driven_pagination_cursor_round_trips_with_oid_anchor() -> None:
    client = FakeClient(adapter.LANE_PARCELS, _lane_features(3), page_size=1)
    first = adapter.execute(
        _args(limit=2, page_size=1, geometry=True),
        client=client,
    )

    assert isinstance(first, PublicRecordsResult)
    assert first.status.value == "ok"
    assert len(first.records) == 2
    assert first.next_cursor is not None
    assert first.records[0]["retrieval_snapshot"] == {
        "total_matching_records": 3,
        "window_start_offset": 0,
        "window_returned_records": 2,
        "window_complete": False,
        "continuation_available": True,
        "pages_fetched": 2,
        "schema_fingerprint": first.records[0]["response_schema_fingerprint"],
        "service_data_last_edit": "2025-09-15",
    }

    second = adapter.execute(
        _args(limit=2, cursor=first.next_cursor, page_size=1, geometry=True),
        client=client,
    )

    assert isinstance(second, PublicRecordsResult)
    assert second.status.value == "ok"
    assert len(second.records) == 1
    assert second.next_cursor is None
    assert second.records[0]["object_id"] == 4
    boundary_calls = [
        details
        for call, details in client.calls
        if call == "page" and details["out_fields"] == "OBJECTID"
    ]
    assert boundary_calls == [
        {
            "where": "UPPER(OWNNAME) LIKE '%BLM%'",
            "offset": 1,
            "record_count": 1,
            "out_fields": "OBJECTID",
            "return_geometry": False,
        }
    ]


def test_cursor_is_bound_to_source_operation_filter_and_geometry() -> None:
    client = FakeClient(adapter.LANE_PARCELS, _lane_features(3))
    first = adapter.execute(_args(limit=1), client=client)
    assert isinstance(first, PublicRecordsResult)
    assert first.next_cursor

    changed = adapter.execute(
        _args(query="INTERIOR", limit=1, cursor=first.next_cursor),
        client=client,
    )
    assert isinstance(changed, PublicRecordsResult)
    assert changed.status.value == "unavailable"
    assert changed.errors[0].code == "cursor_query_mismatch"

    changed_geometry = adapter.execute(
        _args(limit=1, cursor=first.next_cursor, geometry=True),
        client=client,
    )
    assert isinstance(changed_geometry, PublicRecordsResult)
    assert changed_geometry.status.value == "unavailable"
    assert changed_geometry.errors[0].code == "cursor_query_mismatch"


def test_count_change_after_cursor_is_partial_and_not_resumable() -> None:
    first_client = FakeClient(
        adapter.LANE_PARCELS,
        _lane_features(4),
        count_script=[3, 3],
    )
    first = adapter.execute(_args(limit=2), client=first_client)
    assert isinstance(first, PublicRecordsResult)
    assert first.next_cursor

    second_client = FakeClient(
        adapter.LANE_PARCELS,
        _lane_features(4),
        count_script=[4, 4],
    )
    second = adapter.execute(
        _args(limit=2, cursor=first.next_cursor),
        client=second_client,
    )

    assert isinstance(second, PublicRecordsResult)
    assert second.status.value == "partial"
    assert len(second.records) == 2
    assert second.next_cursor is None
    assert [error.code for error in second.errors] == ["count_changed_since_cursor"]


def test_schema_drift_is_source_changed_not_empty() -> None:
    client = FakeClient(
        adapter.MARION_PARCELS,
        [_fixture("marion_parcel")],
        metadata=_metadata(
            adapter.MARION_PARCELS,
            missing="INSTNUM",
        ),
    )
    result = adapter.execute(
        _args(
            command="parcel",
            source=adapter.MARION_PARCELS_SOURCE_ID,
            query="032W290000400",
        ),
        client=client,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "source_changed"
    assert result.records == ()
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["missing_fields"] == ("INSTNUM",)


def test_transport_failure_is_unavailable_not_no_results() -> None:
    client = FakeClient(
        adapter.LANE_PARCELS,
        [],
        metadata=TransportError(
            "network failed",
            url=adapter.LANE_PARCELS.layer_url,
        ),
    )
    result = adapter.execute(_args(), client=client)

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "unavailable"
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_authoritative_zero_count_is_no_results() -> None:
    client = FakeClient(adapter.LANE_PARCELS, [])
    result = adapter.execute(_args(), client=client)

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_probe_reports_census_schema_freshness_and_complements() -> None:
    client = FakeClient(
        adapter.MARION_PARCELS,
        [_fixture("marion_parcel")],
    )
    result = adapter.execute(
        _args(
            command="probe",
            source=adapter.MARION_PARCELS_SOURCE_ID,
            query=None,
        ),
        client=client,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["component_total_count"] == 1
    assert probe["sentinel_count"] == 1
    assert probe["service_data_last_edit"] == "2025-09-15"
    assert probe["source_crs"] == "EPSG:2913"
    assert probe["sentinel_strategy"] == "configured_exact_identifier"
    assert len(probe["schema_fingerprint"]) == 64
    assert len(probe["complementary_sources"]) == 4


def test_rolling_sales_probe_uses_current_structural_sentinel() -> None:
    client = FakeClient(
        adapter.LANE_SALES,
        [_fixture("lane_sale")],
    )
    result = adapter.execute(
        _args(
            command="probe",
            source=adapter.LANE_SALES_SOURCE_ID,
            query=None,
        ),
        client=client,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["sentinel_strategy"] == "first_ordered_current_row"
    assert probe["sentinel_count"] == 1
    count_calls = [call for call in client.calls if call[0] == "count"]
    assert count_calls == [("count", "1=1")]
    page_call = next(call for call in client.calls if call[0] == "page")
    assert page_call[1]["where"] == "1=1"


@pytest.mark.parametrize("command", ("search", "probe"))
def test_query_and_probe_preserve_upstream_access_decision(
    command: str,
) -> None:
    decision = {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
        "limits": {"max_records": 250},
    }
    result = adapter.execute(
        _args(
            command=command,
            source=adapter.LANE_PARCELS_SOURCE_ID,
            query="BLM" if command == "search" else None,
        ),
        client=FakeClient(
            adapter.LANE_PARCELS,
            [_fixture("lane_parcel")],
        ),
        access_decision=decision,
    )

    assert isinstance(result, PublicRecordsResult)
    assert dict(result.query.query.metadata["access_decision"]) == decision


def test_source_specific_where_clauses_preserve_exact_and_contains_semantics() -> None:
    assert adapter._where(
        adapter.LANE_PARCELS,
        operation="parcel",
        selector="1501000000100",
        search_field="parcel",
    ) == (
        "(UPPER(MAPTAXLOT) = '1501000000100' OR "
        "UPPER(RLID) = '1501000000100' OR "
        "UPPER(MAPNUMBER) = '1501000000100' OR "
        "UPPER(TAXLOT) = '1501000000100')"
    )
    assert (
        adapter._where(
            adapter.MARION_PARCELS,
            operation="search",
            selector="O'Neil",
            search_field="owner",
        )
        == "UPPER(OWNERNAME) LIKE '%O''NEIL%'"
    )
    assert adapter._where(
        adapter.LANE_SALES,
        operation="sale",
        selector="2024-019914",
        search_field="instrument",
    ) == (
        "UPPER(SalesLayerCityJoin_SalesforGISLayerAll_deed_transfer_no) = '2024-019914'"
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LANE_MARION") != "1",
    reason="set RUN_LIVE_OR_LANE_MARION=1 for official ArcGIS probes",
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
        )
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok", result.to_dict()
    assert result.records[0]["component_total_count"] > 0
    assert result.records[0]["sentinel_count"] > 0
