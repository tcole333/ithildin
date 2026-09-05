from __future__ import annotations

import json
from argparse import Namespace
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_nyc_pip as pip
from tools.public_records_contract import ResultStatus
from tools.public_records_http import PaginatedFetch, TransportError


FIXTURE_DIR = Path("tests/fixtures/public_records/nyc_pip")


def fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text())


def metadata_for(key: str) -> dict[str, Any]:
    metadata = fixture("source_contract.json")["layers"][key]
    metadata["fields"] = [
        {
            "name": field_name,
            "type": (
                "esriFieldTypeOID"
                if field_name == "OBJECTID"
                else "esriFieldTypeString"
            ),
            "nullable": field_name != "OBJECTID",
        }
        for field_name in pip.LAYER_SPECS[key].required_fields
    ]
    return metadata


def sentinel_features(key: str) -> list[dict[str, Any]]:
    bundle = fixture("sentinel_bundle.json")
    value = bundle[key]
    return deepcopy(value if isinstance(value, list) else [value])


def args(
    command: str = "owner",
    query: str | None = "BOLT 1 L.P.",
    **overrides: Any,
) -> Namespace:
    values: dict[str, Any] = {
        "command": command,
        "query": query,
        "borough": "Manhattan",
        "block": "1386",
        "lot": "10",
        "mode": "layers",
        "layer": None,
        "match": "contains",
        "limit": None,
        "cursor": None,
        "page_size": 1_000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


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
        key: str,
        records: list[dict[str, Any]] | None = None,
        *,
        metadata: dict[str, Any] | None = None,
        error: Exception | None = None,
        fetch_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.key = key
        self.records = (
            records if records is not None else sentinel_features(key)
        )
        self.metadata_value = metadata or metadata_for(key)
        self.error = error
        self.fetch_overrides = fetch_overrides or {}
        self.calls: list[dict[str, Any]] = []
        self.metadata_calls = 0
        self.page_size = 1_000

    def metadata(self) -> dict[str, Any]:
        self.metadata_calls += 1
        if self.error is not None:
            raise self.error
        return self.metadata_value

    def query(self, **kwargs: Any) -> PaginatedFetch:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return fetch(self.records, **self.fetch_overrides)


def sentinel_clients(
    **overrides: FakeClient,
) -> dict[str, FakeClient]:
    return {
        key: overrides.get(key, FakeClient(key))
        for key in pip.BUNDLE_LAYER_KEYS
    }


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
    monkeypatch.setattr(pip, "log_search", lambda *_args, **_kwargs: None)


def test_bbl_and_borough_block_lot_normalization() -> None:
    assert pip.normalize_bbl("1-01386-0010") == "1013860010"
    assert pip.bbl_from_parts("New York County", 1386, 10) == "1013860010"
    assert pip.bbl_from_parts("Staten Island", 1, 7) == "5000010007"
    assert pip.bbl_parts("1013860010")["county_geoid"] == "36061"

    with pytest.raises(ValueError, match="ten digits"):
        pip.normalize_bbl("1386-10")
    with pytest.raises(ValueError, match="1 through 5"):
        pip.normalize_bbl("6013860010")
    with pytest.raises(ValueError, match="borough"):
        pip.bbl_from_parts("Nassau", 1386, 10)


def test_detail_preserves_parcel_and_occurrence_identity_without_title_claim() -> None:
    record = pip.normalize_feature(
        sentinel_features("detail")[0],
        pip.LAYER_SPECS["detail"],
        response_schema_fingerprint="response",
        layer_schema_fingerprint="layer",
    )

    assert record["bbl"] == "1013860010"
    assert record["same_record_key"] == "US-NYC:BBL:1013860010"
    assert record["identity"]["parcel"]["durable"]
    assert not record["identity"]["layer_occurrence"]["durable"]
    assert record["native_feature_id"] == "124750"
    assert record["owners"] == [
        {
            "raw_name": "BOLT 1 L.P.",
            "role": "dof_tax_roll_owner",
            "assertion_type": "assessment_roll_observation",
            "title_assertion": False,
        }
    ]
    assert record["situs_address"]["raw"] == (
        "9 EAST 71 STREET, NEW YORK, NY, 10021"
    )
    assert record["building"]["gross_square_feet"] == 18814
    assert record["land"]["zoning"] == "R8B"
    assert record["recording_lineage"]["pip_acris_relationship"] == (
        "same_acris_record_representation"
    )


def test_tax_lot_geometry_is_a_distinct_layer_occurrence() -> None:
    record = pip.normalize_feature(
        sentinel_features("tax_lot")[0],
        pip.LAYER_SPECS["tax_lot"],
        response_schema_fingerprint="response",
        layer_schema_fingerprint="layer",
    )

    assert record["parcel_canonical_ref"].endswith(
        "/parcel/1013860010"
    )
    assert record["canonical_ref"].endswith(
        "/tax_lot_occurrence/tax_lot%3A1013860010%3A1775"
    )
    assert record["tax_lot"]["shape_area"] == 867.37109375
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry_role"] == "cadastral_tax_lot"


def test_current_and_history_remain_distinct_but_join_on_assessment_key() -> None:
    audit = fixture("assessment_identity_audit.json")
    assert audit["current_assessment"][
        "maximum_observed_group_count"
    ] == 1
    assert audit["assessment_history"][
        "maximum_observed_group_count"
    ] == 1
    current = pip.normalize_feature(
        sentinel_features("current_assessment")[0],
        pip.LAYER_SPECS["current_assessment"],
        response_schema_fingerprint="response",
        layer_schema_fingerprint="current-layer",
    )
    history = pip.normalize_feature(
        sentinel_features("assessment_history")[0],
        pip.LAYER_SPECS["assessment_history"],
        response_schema_fingerprint="response",
        layer_schema_fingerprint="history-layer",
    )

    assert current["canonical_ref"] != history["canonical_ref"]
    assert current["native_feature_id"] == "139025"
    assert history["native_feature_id"] == "12796579"
    assert current["same_assessment_key"] == history[
        "same_assessment_key"
    ]
    assert current["assessment_identity"]["key_role"] == (
        "cross_representation_join"
    )
    assert current["assessment_identity"]["occurrence_key"] != history[
        "assessment_identity"
    ]["occurrence_key"]
    assert current["assessment"]["representation"] == (
        "current_assessment"
    )
    assert history["assessment"]["representation"] == (
        "assessment_history"
    )
    assert current["assessment"]["values"]["market_value"] == 66836000


def test_exemption_identity_includes_original_parcel_grain() -> None:
    audit = fixture("exemption_duplicate_audit.json")
    assert audit["largest_parcel_level_group"]["row_count"] == 324
    assert audit["largest_refined_child_group"]["row_count"] == 1

    client = FakeClient(
        "exemptions",
        records=audit["sample_features"],
    )
    result = pip.execute(
        args(
            command="exemptions",
            query="3801190032",
        ),
        clients={"exemptions": client},
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    first, second = result.records
    assert first["canonical_ref"] != second["canonical_ref"]
    assert first["exemption_identity"]["key"] != second[
        "exemption_identity"
    ]["key"]
    assert first["same_exemption_tuple_key"] != second[
        "same_exemption_tuple_key"
    ]
    assert first["exemption_identity"]["published_tuple"][
        "original_parid"
    ] == "3801190032 E219"
    assert first["exemption_identity"][
        "published_tuple_observed_unique"
    ]
    assert "duplicate_ordinal" not in first["exemption_identity"]
    assert first["exemption"]["original_parid"] == "3801190032 E219"


def test_truly_identical_exemption_tuples_receive_duplicate_ordinals() -> None:
    features = fixture("exemption_duplicate_audit.json")[
        "sample_features"
    ]
    features[1]["attributes"]["PARID_ORG"] = features[0]["attributes"][
        "PARID_ORG"
    ]
    client = FakeClient("exemptions", records=features)

    result = pip.execute(
        args(command="exemptions", query="3801190032"),
        clients={"exemptions": client},
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    first, second = result.records
    assert first["canonical_ref"] != second["canonical_ref"]
    assert first["same_exemption_tuple_key"] == second[
        "same_exemption_tuple_key"
    ]
    assert {
        first["exemption_identity"]["duplicate_ordinal"],
        second["exemption_identity"]["duplicate_ordinal"],
    } == {1, 2}
    assert first["exemption_identity"]["duplicate_count_in_response"] == 2
    assert first["exemption_identity"]["duplicate_ordinal_scope"] == (
        "complete_exact_bbl_result"
    )
    assert not first["exemption_identity"][
        "published_tuple_observed_unique"
    ]


def test_query_builders_use_verified_fields_and_escape_literals() -> None:
    detail = pip.LAYER_SPECS["detail"]
    history = pip.LAYER_SPECS["assessment_history"]

    assert pip._where(
        "owner",
        selector="O'Neil",
        spec=detail,
        match="contains",
    ) == "UPPER(OWNER) LIKE '%O''NEIL%'"
    address = pip._where(
        "address",
        selector="9 E 71st St, New York, NY 10021",
        spec=detail,
    )
    assert "UPPER(HOUSENUM)='9'" in address
    assert "LIKE '%EAST%'" in address
    assert "LIKE '%71%'" in address
    assert "LIKE '%STREET%'" in address
    assert "NEW" not in address
    assert pip._where(
        "assessment-history",
        selector="1013860010",
        spec=history,
    ) == "PARID='1013860010'"


def test_layer_metadata_contract_is_validated_for_all_five_layers() -> None:
    for key, spec in pip.LAYER_SPECS.items():
        validated = pip.validate_layer_metadata(
            metadata_for(key),
            spec,
        )
        assert validated["schema_fingerprint"]
        assert validated["native_page_size"] in {1_000, 2_000}

    renamed = metadata_for("detail")
    renamed["name"] = "RENAMED"
    with pytest.raises(pip.SourceSchemaError, match="identity changed"):
        pip.validate_layer_metadata(renamed, pip.LAYER_SPECS["detail"])

    missing = metadata_for("detail")
    missing["fields"] = [
        item
        for item in missing["fields"]
        if item["name"] != "OWNER"
    ]
    with pytest.raises(pip.SourceSchemaError, match="missing required"):
        pip.validate_layer_metadata(missing, pip.LAYER_SPECS["detail"])

    no_paging = metadata_for("assessment_history")
    no_paging["advancedQueryCapabilities"]["supportsPagination"] = False
    with pytest.raises(pip.SourceSchemaError, match="pagination contract"):
        pip.validate_layer_metadata(
            no_paging,
            pip.LAYER_SPECS["assessment_history"],
        )


def test_omitted_limit_exhausts_native_arcgis_pages() -> None:
    features = sentinel_features("detail")
    second = deepcopy(features[0])
    second["attributes"]["OBJECTID"] = 124751
    third = deepcopy(features[0])
    third["attributes"]["OBJECTID"] = 124752
    response_fields = metadata_for("detail")["fields"]
    transport = QueueTransport(
        [
            FakeResponse(metadata_for("detail")),
            FakeResponse(
                {
                    "fields": response_fields,
                    "features": [features[0], second],
                    "exceededTransferLimit": True,
                }
            ),
            FakeResponse(
                {
                    "fields": response_fields,
                    "features": [third],
                    "exceededTransferLimit": False,
                }
            ),
        ]
    )
    client = pip.PIPArcGISClient(
        pip.LAYER_SPECS["detail"],
        page_size=2,
        transport=transport,
        minimum_interval=0,
    )

    result = pip.execute(
        args(limit=None, max_records=None, page_size=2),
        clients={"detail": client},
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.query.query.requested_limit is None
    assert [call["params"]["resultOffset"] for call in transport.calls[1:]] == [
        0,
        2,
    ]
    assert [
        call["params"]["resultRecordCount"]
        for call in transport.calls[1:]
    ] == [2, 2]
    assert result.next_cursor is None


def test_explicit_caller_window_preserves_continuation() -> None:
    client = FakeClient(
        "detail",
        fetch_overrides={
            "next_cursor": "arcgis:offset:25",
            "truncated_by_cap": True,
        },
    )

    result = pip.execute(
        args(limit=25, cursor="arcgis:offset:0"),
        clients={"detail": client},
        log_results=False,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.next_cursor == "arcgis:offset:25"
    assert client.calls[0]["requested_limit"] == 25
    assert client.calls[0]["cursor"] == "arcgis:offset:0"


def test_exact_bbl_bundle_exhausts_all_components_and_accepts_no_exemptions() -> None:
    clients = sentinel_clients()

    result = pip.execute(
        args(command="bbl", query="1013860010"),
        clients=clients,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 6
    anchor = result.records[0]
    assert anchor["record_kind"] == "nyc_dof_property_information_bundle"
    assert anchor["component_counts"] == {
        "detail": 1,
        "tax_lot": 1,
        "current_assessment": 1,
        "assessment_history": 2,
        "exemptions": 0,
    }
    assert anchor["recording_routes"][
        "pip_recent_acris_display_relationship"
    ] == "same_acris_record_representation"
    for key, client in clients.items():
        assert client.calls[0]["requested_limit"] is None
        assert client.calls[0]["max_records"] is None
        expected_field = pip.LAYER_SPECS[key].identity_field
        assert client.calls[0]["where"] == (
            f"{expected_field}='1013860010'"
        )


def test_lot_command_builds_the_same_exact_bundle() -> None:
    result = pip.execute(
        args(
            command="lot",
            query=None,
            borough="Manhattan",
            block="1386",
            lot="10",
        ),
        clients=sentinel_clients(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.query.query.parameters["selector"] == "1013860010"
    assert result.records[0]["bbl"] == "1013860010"


def test_probe_checks_stable_identity_but_not_rolling_owner_or_value() -> None:
    detail = sentinel_features("detail")
    detail[0]["attributes"]["OWNER"] = "A NEW TAX-ROLL OWNER"
    current = sentinel_features("current_assessment")
    current[0]["attributes"]["MARKET_VALUE"] = 70000000
    clients = sentinel_clients(
        detail=FakeClient("detail", records=detail),
        current_assessment=FakeClient(
            "current_assessment",
            records=current,
        ),
    )

    result = pip.execute(
        args(command="probe", query=None),
        clients=clients,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    detail_record = next(
        record
        for record in result.records
        if record.get("record_kind")
        == "nyc_dof_parcel_detail_observation"
    )
    assert detail_record["owners"][0]["raw_name"] == (
        "A NEW TAX-ROLL OWNER"
    )


def test_probe_detects_stable_address_drift() -> None:
    detail = sentinel_features("detail")
    detail[0]["attributes"]["STREET_NAME"] = "CHANGED STREET"
    clients = sentinel_clients(
        detail=FakeClient("detail", records=detail),
    )

    result = pip.execute(
        args(command="probe", query=None),
        clients=clients,
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


def test_probe_detects_missing_tax_lot_geometry() -> None:
    tax_lot = sentinel_features("tax_lot")
    tax_lot[0].pop("geometry")
    clients = sentinel_clients(
        tax_lot=FakeClient("tax_lot", records=tax_lot),
    )

    result = pip.execute(
        args(command="probe", query=None),
        clients=clients,
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


def test_discovery_reports_layers_live_metadata_and_recorder_lineage() -> None:
    layers = pip.execute(
        args(command="discovery", query=None, mode="layers"),
        log_results=False,
    )
    routes = pip.execute(
        args(command="discovery", query=None, mode="routes"),
        log_results=False,
    )
    metadata = pip.execute(
        args(command="discovery", query=None, mode="metadata"),
        clients=sentinel_clients(),
        log_results=False,
    )

    assert layers.status == ResultStatus.OK
    assert len(layers.records) == 5
    assert routes.records[0]["recording_routes"][0][
        "relationship_to_pip_recent_display"
    ] == "same_acris_record_representation"
    assert len(metadata.records) == 5
    assert {
        record["layer_key"] for record in metadata.records
    } == set(pip.LAYER_SPECS)


def test_invalid_query_no_results_and_transport_failure_are_distinct() -> None:
    invalid = pip.execute(
        args(command="address", query="NY 10021"),
        clients={"detail": FakeClient("detail")},
        log_results=False,
    )
    empty = pip.execute(
        args(command="detail", query="1013860010"),
        clients={"detail": FakeClient("detail", records=[])},
        log_results=False,
    )
    unavailable = pip.execute(
        args(),
        clients={
            "detail": FakeClient(
                "detail",
                error=TransportError(
                    "offline",
                    url=pip.LAYER_SPECS["detail"].url,
                ),
            )
        },
        log_results=False,
    )

    assert invalid.status == ResultStatus.UNAVAILABLE
    assert invalid.errors[0].code == "invalid_query"
    assert empty.status == ResultStatus.NO_RESULTS
    assert unavailable.status == ResultStatus.UNAVAILABLE
    assert unavailable.errors[0].code == "transport_error"


def test_parser_has_no_implicit_result_ceiling() -> None:
    parsed = pip.build_parser().parse_args(["owner", "BOLT 1 L.P."])

    assert parsed.limit is None
    assert parsed.max_records is None
    assert parsed.page_size == 1_000
