from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_wy_dor_parcels as wy
from tools.public_records_contract import ResultStatus
from tools.public_records_http import PaginatedFetch, TransportError


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "wy_dor_parcels"
)


def fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text())


def metadata() -> dict[str, Any]:
    return fixture("source_contract.json")["layer"]


def sentinel() -> dict[str, Any]:
    return fixture("sentinel_feature.json")


def app_item() -> dict[str, Any]:
    return {
        "id": wy.ROOT_APP_ITEM_ID,
        "type": "Web Mapping Application",
        "owner": "dave.chapman@wyo.gov",
        "access": "public",
    }


def app_data() -> dict[str, Any]:
    return {
        "appItemId": wy.ROOT_APP_ITEM_ID,
        "title": "Wyoming Statewide Parcel  and Tax District Viewer",
        "subtitle": wy.ROOT_APP_DATA_SUBTITLE,
        "map": {"itemId": "982879668f2847c79211d6d91de9418a"},
        "widgetPool": {
            "widgets": [
                {
                    "id": "_7",
                    "label": "Query Parcels, Counties and Tax Districts",
                    "uri": "widgets/Query/Widget",
                    "config": {
                        "queries": [
                            {
                                "url": wy.LAYER_URL,
                                "name": (
                                    "2026 Wyoming Parcels by Account Number "
                                    "or Parcel Number"
                                ),
                                "filter": {
                                    "parts": [
                                        {"fieldObj": {"name": "accountno"}},
                                        {"fieldObj": {"name": "parcelnb"}},
                                    ]
                                },
                            }
                        ]
                    },
                }
            ]
        },
    }


def fetch(
    records: list[dict[str, Any]],
    **overrides: Any,
) -> PaginatedFetch:
    values: dict[str, Any] = {
        "records": records,
        "next_cursor": None,
        "schema": {"kind": "test"},
        "schema_fingerprint": "response-schema",
        "pages_fetched": 1,
        "requests_made": 1,
    }
    values.update(overrides)
    return PaginatedFetch(**values)


class FakeClient:
    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        *,
        metadata_value: dict[str, Any] | None = None,
        error: Exception | None = None,
        fetch_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.records = records if records is not None else [sentinel()]
        self.metadata_value = metadata_value or metadata()
        self.error = error
        self.fetch_overrides = fetch_overrides or {}
        self.metadata_calls = 0
        self.app_item_calls = 0
        self.app_data_calls = 0
        self.count_calls = 0
        self.calls: list[dict[str, Any]] = []
        self.page_size = 2_000

    def metadata(self) -> dict[str, Any]:
        self.metadata_calls += 1
        if self.error is not None:
            raise self.error
        return self.metadata_value

    def app_item(self) -> dict[str, Any]:
        self.app_item_calls += 1
        return app_item()

    def app_data(self) -> dict[str, Any]:
        self.app_data_calls += 1
        return app_data()

    def count(self) -> int:
        self.count_calls += 1
        return 373_666

    def query(self, **kwargs: Any) -> PaginatedFetch:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return fetch(self.records, **self.fetch_overrides)


@dataclass
class FakeResponse:
    payload: Any
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""

    def json(self) -> Any:
        return self.payload


class QueueTransport:
    def __init__(self, outcomes: list[FakeResponse]) -> None:
        self.outcomes = list(outcomes)
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
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.outcomes:
            raise AssertionError("unexpected HTTP request")
        return self.outcomes.pop(0)


@pytest.fixture(autouse=True)
def disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wy, "log_search", lambda *_args, **_kwargs: None)


def parse(*tokens: str):
    return wy.build_parser().parse_args(list(tokens))


def normalized(feature: dict[str, Any]) -> dict[str, Any]:
    return wy.normalize_feature(
        feature,
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint="layer-schema",
        source_version={
            "data_last_edit": "2026-06-10T00:00:00Z",
            "schema_last_edit": "2026-06-10T00:00:00Z",
        },
    )


def test_layer_metadata_contract_locks_item_schema_and_paging() -> None:
    validated = wy.validate_layer_metadata(metadata())

    assert validated["native_page_size"] == 2_000
    assert validated["schema_fingerprint"]
    assert validated["schema"]["identity"]["service_item_id"] == wy.ITEM_ID

    renamed = metadata()
    renamed["serviceItemId"] = "another-item"
    with pytest.raises(wy.SourceSchemaError, match="identity changed"):
        wy.validate_layer_metadata(renamed)

    missing = metadata()
    missing["fields"] = [
        field for field in missing["fields"] if field["name"] != "accountno"
    ]
    with pytest.raises(wy.SourceSchemaError, match="missing required"):
        wy.validate_layer_metadata(missing)

    no_paging = metadata()
    no_paging["advancedQueryCapabilities"]["supportsPagination"] = False
    with pytest.raises(wy.SourceSchemaError, match="pagination contract"):
        wy.validate_layer_metadata(no_paging)


def test_root_application_contract_points_query_widget_to_current_layer() -> None:
    agreement = wy.validate_app_agreement(app_item(), app_data())

    assert agreement["app_identity"]["id"] == wy.ROOT_APP_ITEM_ID
    assert agreement["app_data"]["title"] == wy.ROOT_APP_DATA_TITLE
    assert agreement["parcel_query_routes"][0]["url"] == wy.LAYER_URL
    assert agreement["parcel_query_routes"][0]["fields"] == [
        "accountno",
        "parcelnb",
    ]
    future_release = app_data()
    future_release["subtitle"] = "Current as of January 1, 2027"
    assert wy.validate_app_agreement(app_item(), future_release)["app_data"][
        "release_year"
    ] == "2027"

    stale = app_data()
    stale["widgetPool"]["widgets"][0]["config"]["queries"][0]["url"] = (
        wy.LAYER_URL.replace("2026", "2025")
    )
    with pytest.raises(wy.SourceSchemaError, match="no longer points"):
        wy.validate_app_agreement(app_item(), stale)


def test_county_normalization_and_inventory_cover_all_23_jurisdictions() -> None:
    assert wy.normalize_jurisdiction("Campbell County") == "CAMPBELL"
    assert wy.normalize_jurisdiction("Big Horn") == "BIGHORN"
    assert wy.normalize_jurisdiction("HOTSPRINGS") == "HOTSPRINGS"
    assert len(wy.COUNTIES) == 23
    assert sum(value["count"] for value in wy.COUNTIES.values()) == 373_666

    with pytest.raises(ValueError, match="23 counties"):
        wy.normalize_jurisdiction("Yellowstone")


def test_sentinel_normalization_preserves_tax_roll_and_occurrence_grains() -> None:
    record = normalized(sentinel())

    assert record["record_kind"] == "wy_dor_annual_parcel_geometry_occurrence"
    assert record["tax_year"] == "2026"
    assert record["jurisdiction_code"] == "CAMPBELL"
    assert record["county_geoid"] == "56005"
    assert record["parcel_number"] == "49720332401200"
    assert record["account_number"] == "R0059774"
    assert record["native_feature_id"] == "30558"
    assert record["annual_parcel_canonical_ref"]
    assert record["canonical_ref"] != record["annual_parcel_canonical_ref"]
    assert record["identity"]["annual_parcel_join"]["basis"] == (
        "tax_year_jurisdiction_parcel_account"
    )
    assert record["identity"]["release_occurrence"] == {
        "basis": "arcgis_fid",
        "fid": 30558,
        "canonical_ref": record["canonical_ref"],
        "durable_across_annual_releases": False,
    }
    assert record["owners"][0] == {
        "raw_name": "STATE OF WYOMING",
        "role": "primary_annual_tax_roll_owner",
        "assertion_type": "annual_tax_roll_observation",
        "title_assertion": False,
    }
    assert record["mailing_address"]["postal_code"] == "82009-3338"
    assert record["situs_address"]["raw"] == "16 KETTLESON XING"
    assert record["assessment"]["actual_value"] == 424342
    assert record["land"]["gross_acres"] == 0.1935
    assert record["geometry_crs"] == "EPSG:4326"


def test_multipart_tuple_is_one_annual_join_with_every_fid_retained() -> None:
    audit = fixture("identity_audit.json")
    assert audit["largest_grouped_tuples"][1]["row_count"] == 84
    records = [normalized(feature) for feature in fixture("multipart_features.json")]

    assert len(records) == 3
    assert len({record["canonical_ref"] for record in records}) == 3
    assert {record["native_feature_id"] for record in records} == {
        "195144",
        "195145",
        "195146",
    }
    assert len({record["same_annual_record_key"] for record in records}) == 1
    assert len(
        {record["annual_parcel_canonical_ref"] for record in records}
    ) == 1
    assert {
        record["land"]["source_shape_area_square_meters"]
        for record in records
    } == {614.8046875, 786.24609375, 22194.09375}


def test_blank_parcel_and_account_stays_occurrence_only_and_preserves_zero() -> None:
    audit = fixture("identity_audit.json")
    assert audit["blank_string_counts"]["both_single_space"] == 1_214
    record = normalized(fixture("blank_feature.json"))

    assert record["record_kind"] == "wy_dor_unresolved_geometry_occurrence"
    assert record["annual_parcel_canonical_ref"] is None
    assert record["same_annual_record_key"] is None
    assert record["parcel_number"] is None
    assert record["account_number"] is None
    assert record["identity"]["annual_parcel_join"]["reason"] == (
        "blank_parcel_and_account"
    )
    assert not record["identity"]["annual_parcel_join"][
        "projection_eligible_as_annual_parcel"
    ]
    assert record["assessment"]["actual_value"] == 0
    assert record["land"]["gross_acres"] == 0


def test_non_specific_parcel_without_account_is_not_a_durable_join() -> None:
    feature = fixture("blank_feature.json")
    feature["attributes"]["parcelnb"] = "BLM"
    record = normalized(feature)

    identity = record["identity"]["annual_parcel_join"]
    assert identity["parcel_identifier_quality"] == "non_specific_label"
    assert identity["reason"] == "non_specific_parcel_identifier_without_account"
    assert not identity["projection_eligible_as_annual_parcel"]
    assert record["parcel_number"] == "BLM"


def test_specific_parcel_only_fallback_is_an_observed_annual_join() -> None:
    audit = fixture("identity_audit.json")
    assert audit["normalized_identity_basis_counts"][
        "tax_year_jurisdiction_parcel"
    ] == 37_474
    record = normalized(fixture("parcel_only_feature.json"))

    identity = record["identity"]["annual_parcel_join"]
    assert identity["basis"] == "tax_year_jurisdiction_parcel"
    assert identity["projection_eligible_as_annual_parcel"]
    assert record["parcel_number"] == "22160120050000"
    assert record["account_number"] is None
    assert record["annual_parcel_canonical_ref"]


def test_account_only_fallback_is_supported_but_absent_in_2026_audit() -> None:
    audit = fixture("identity_audit.json")
    assert audit["normalized_identity_basis_counts"][
        "tax_year_jurisdiction_account"
    ] == 0
    feature = fixture("blank_feature.json")
    feature["attributes"]["accountno"] = "R-FUTURE-EXAMPLE"
    record = normalized(feature)

    identity = record["identity"]["annual_parcel_join"]
    assert identity["basis"] == "tax_year_jurisdiction_account"
    assert identity["projection_eligible_as_annual_parcel"]
    assert record["parcel_number"] is None
    assert record["account_number"] == "R-FUTURE-EXAMPLE"


def test_owner_search_is_an_unresolved_candidate_not_a_title_claim() -> None:
    client = FakeClient()
    result = wy.execute(
        parse("owner", "WYOMING", "--jurisdiction", "Campbell"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert client.calls[0]["where"] == (
        "((UPPER(ownername1) LIKE '%WYOMING%' OR "
        "UPPER(ownername2) LIKE '%WYOMING%')) AND "
        "jurisdicti='CAMPBELL'"
    )
    assert client.calls[0]["requested_limit"] is None
    assert result.records[0]["query_match"]["resolution_status"] == (
        "unresolved_candidate"
    )
    assert not result.records[0]["owners"][0]["title_assertion"]


def test_text_and_identifier_query_builders_use_verified_fields() -> None:
    assert wy._where(
        "parcel",
        selector="49'720",
        match="exact",
    ) == "UPPER(parcelnb)='49''720'"
    assert wy._where(
        "account",
        selector="R0059774",
        match="starts",
    ) == "UPPER(accountno) LIKE 'R0059774%'"
    assert wy._where(
        "situs",
        selector="KETTLESON",
        match="contains",
    ) == "UPPER(locationad) LIKE '%KETTLESON%'"
    assert "mailaddres" in wy._where(
        "mailing",
        selector="BISHOP",
        match="contains",
    )
    assert wy._where(
        "legal",
        selector="LEGACY RIDGE",
        match="contains",
        tax_year="2026",
    ) == "UPPER(legal) LIKE '%LEGACY RIDGE%' AND taxyear='2026'"
    assert wy._where("fid", selector="030558") == "FID=30558"
    assert wy._where("county", selector="Hot Springs County") == (
        "jurisdicti='HOTSPRINGS'"
    )


def test_omitted_limit_exhausts_ordered_native_pages() -> None:
    first = sentinel()
    second = deepcopy(first)
    second["attributes"]["FID"] = 30559
    third = deepcopy(first)
    third["attributes"]["FID"] = 30560
    fields = metadata()["fields"]
    transport = QueueTransport(
        [
            FakeResponse(metadata()),
            FakeResponse(
                {
                    "fields": fields,
                    "features": [first, second],
                    "exceededTransferLimit": True,
                }
            ),
            FakeResponse(
                {
                    "fields": fields,
                    "features": [third],
                    "exceededTransferLimit": False,
                }
            ),
        ]
    )
    client = wy.WyomingDORClient(
        page_size=2,
        transport=transport,
        minimum_interval=0,
    )

    result = wy.execute(
        parse("owner", "STATE", "--page-size", "2"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.query.query.requested_limit is None
    assert [call["params"]["resultOffset"] for call in transport.calls[1:]] == [
        0,
        2,
    ]
    assert all(
        call["params"]["orderByFields"] == "FID ASC"
        for call in transport.calls[1:]
    )
    assert result.next_cursor is None


def test_explicit_caller_window_preserves_continuation() -> None:
    client = FakeClient(
        fetch_overrides={
            "next_cursor": "arcgis:offset:25",
            "truncated_by_cap": True,
        }
    )

    result = wy.execute(
        parse(
            "owner",
            "STATE",
            "--limit",
            "25",
            "--cursor",
            "arcgis:offset:0",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.next_cursor == "arcgis:offset:25"
    assert client.calls[0]["requested_limit"] == 25
    assert client.calls[0]["cursor"] == "arcgis:offset:0"


def test_point_and_bbox_build_wgs84_spatial_queries() -> None:
    point_client = FakeClient()
    bbox_client = FakeClient()

    point = wy.execute(
        parse("point", "-105.5013", "44.2526"),
        client=point_client,
        log_results=False,
    )
    bbox = wy.execute(
        parse("bbox", "-105.51", "44.24", "-105.49", "44.27"),
        client=bbox_client,
        log_results=False,
    )

    assert point.status == ResultStatus.OK
    assert point_client.calls[0]["parameters"] == {
        "orderByFields": "FID ASC",
        "geometry": "-105.5013,44.2526",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }
    assert bbox_client.calls[0]["parameters"]["geometry"] == (
        "-105.51,44.24,-105.49,44.27"
    )
    assert bbox_client.calls[0]["parameters"]["geometryType"] == (
        "esriGeometryEnvelope"
    )
    assert bbox.query.query.parameters["selector"] == {
        "xmin": -105.51,
        "ymin": 44.24,
        "xmax": -105.49,
        "ymax": 44.27,
    }


def test_geometry_command_forces_wgs84_feature_geometry() -> None:
    client = FakeClient()

    result = wy.execute(
        parse("geometry", "30558"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert client.calls[0]["where"] == "FID=30558"
    assert client.calls[0]["return_geometry"] is True
    assert client.calls[0]["parameters"] == {
        "orderByFields": "FID ASC",
        "outSR": 4326,
    }


def test_probe_is_exact_and_ignores_rolling_owner_and_values() -> None:
    from tools.public_records_monitor import HANDLER_REGISTRY

    feature = sentinel()
    feature["attributes"]["ownername1"] = "A NEW TAX ROLL OWNER"
    feature["attributes"]["actualvalu"] = 999999
    client = FakeClient(records=[feature])

    result = wy.execute(
        parse("probe"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert client.calls[0]["where"] == (
        "taxyear='2026' AND jurisdicti='CAMPBELL' AND "
        "parcelnb='49720332401200' AND accountno='R0059774'"
    )
    assert client.calls[0]["requested_limit"] is None
    assert client.calls[0]["return_geometry"] is True
    assert result.records[0]["owners"][0]["raw_name"] == (
        "A NEW TAX ROLL OWNER"
    )
    assert result.records[0]["source_probe"]["root_application_agreement"][
        "app_identity"
    ]["id"] == wy.ROOT_APP_ITEM_ID
    assert result.records[0]["source_probe"]["statewide_occurrence_count"] == (
        373_666
    )
    assert client.app_item_calls == 1
    assert client.app_data_calls == 1
    assert client.count_calls == 1
    assert client.metadata_calls == 1
    assert len(client.calls) == 1
    total_requests = (
        client.app_item_calls
        + client.app_data_calls
        + client.count_calls
        + client.metadata_calls
        + len(client.calls)
    )
    assert total_requests == HANDLER_REGISTRY[wy.SOURCE_ID].expected_requests == 5


def test_probe_detects_stable_situs_or_geometry_drift() -> None:
    changed_situs = sentinel()
    changed_situs["attributes"]["locationad"] = "CHANGED ADDRESS"
    situs_result = wy.execute(
        parse("probe"),
        client=FakeClient(records=[changed_situs]),
        log_results=False,
    )
    no_geometry = sentinel()
    no_geometry.pop("geometry")
    geometry_result = wy.execute(
        parse("probe"),
        client=FakeClient(records=[no_geometry]),
        log_results=False,
    )

    assert situs_result.status == ResultStatus.SOURCE_CHANGED
    assert situs_result.errors[0].code == "source_schema_changed"
    assert geometry_result.status == ResultStatus.SOURCE_CHANGED


def test_discovery_exposes_source_counties_identity_routes_and_metadata() -> None:
    source = wy.execute(parse("discovery", "source"), log_results=False)
    counties = wy.execute(parse("discovery", "counties"), log_results=False)
    identity = wy.execute(parse("discovery", "identity"), log_results=False)
    routes = wy.execute(parse("discovery", "routes"), log_results=False)
    agreement = wy.execute(
        parse("discovery", "agreement"),
        client=FakeClient(),
        log_results=False,
    )
    live_metadata = wy.execute(
        parse("discovery", "metadata"),
        client=FakeClient(),
        log_results=False,
    )

    assert source.records[0]["item_id"] == wy.ITEM_ID
    assert source.records[0]["root_app_item_id"] == wy.ROOT_APP_ITEM_ID
    assert len(counties.records) == 23
    assert identity.records[0]["largest_usable_tuple_occurrence_count"] == 84
    assert routes.records[0]["same_publisher_lineage"][0][
        "relationship"
    ] == "same_annual_feature_service_release"
    assert {
        route["role"]
        for route in routes.records[0]["field_matched_county_complements"]
    } == {"county_assessor", "county_treasurer", "county_clerk"}
    assert live_metadata.records[0]["native_page_size"] == 2_000
    assert agreement.records[0]["implemented_layer_url"] == wy.LAYER_URL


def test_invalid_query_no_results_and_transport_failure_are_distinct() -> None:
    invalid_county = wy.execute(
        parse("county", "Yellowstone"),
        client=FakeClient(),
        log_results=False,
    )
    invalid_bbox = wy.execute(
        parse("bbox", "-105", "45", "-106", "44"),
        client=FakeClient(),
        log_results=False,
    )
    empty = wy.execute(
        parse("parcel", "DOES-NOT-EXIST"),
        client=FakeClient(records=[]),
        log_results=False,
    )
    unavailable = wy.execute(
        parse("owner", "STATE"),
        client=FakeClient(
            error=TransportError("offline", url=wy.LAYER_URL)
        ),
        log_results=False,
    )

    assert invalid_county.status == ResultStatus.UNAVAILABLE
    assert invalid_county.errors[0].code == "invalid_query"
    assert invalid_bbox.status == ResultStatus.UNAVAILABLE
    assert empty.status == ResultStatus.NO_RESULTS
    assert unavailable.status == ResultStatus.UNAVAILABLE
    assert unavailable.errors[0].code == "transport_error"


def test_parser_has_no_implicit_result_ceiling() -> None:
    args = parse("owner", "STATE OF WYOMING")

    assert args.limit is None
    assert args.max_records is None
    assert args.page_size == 2_000
