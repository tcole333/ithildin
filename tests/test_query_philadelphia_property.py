from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

from tools import query_philadelphia_property as phila


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "philadelphia_property"
)


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


class FakeArcGISClient:
    def __init__(
        self,
        metadata,
        features,
        *,
        page_size=2,
        full_counts=None,
        metadata_versions=None,
    ):
        self.metadata = copy.deepcopy(metadata)
        self.features = copy.deepcopy(features)
        self.page_size = page_size
        self.full_counts = list(full_counts or [])
        self.metadata_versions = list(metadata_versions or [])
        self.full_count_calls = 0
        self.metadata_calls = 0
        self.page_calls = []
        self.count_calls = []

    def fetch_metadata(self):
        payload = copy.deepcopy(self.metadata)
        if self.metadata_versions:
            index = min(
                self.metadata_calls, len(self.metadata_versions) - 1
            )
            payload["editingInfo"]["dataLastEditDate"] = (
                self.metadata_versions[index]
            )
        self.metadata_calls += 1
        return payload

    def fetch_count(self, where):
        self.count_calls.append(where)
        match = re.search(r"objectid > ([0-9]+)", where)
        if match:
            threshold = int(match.group(1))
            return sum(
                feature["attributes"]["objectid"] > threshold
                for feature in self.features
            )
        if self.full_counts:
            index = min(
                self.full_count_calls, len(self.full_counts) - 1
            )
            count = self.full_counts[index]
            self.full_count_calls += 1
            return count
        self.full_count_calls += 1
        return len(self.features)

    def fetch_page(self, *, where, record_count, return_geometry):
        self.page_calls.append(
            {
                "where": where,
                "record_count": record_count,
                "return_geometry": return_geometry,
            }
        )
        match = re.search(r"objectid > ([0-9]+)", where)
        threshold = int(match.group(1)) if match else -1
        return tuple(
            feature
            for feature in self.features
            if feature["attributes"]["objectid"] > threshold
        )[:record_count]


class FakeHistoryClient:
    def __init__(
        self,
        schema,
        rows,
        *,
        page_size=2,
        full_counts=None,
    ):
        self.schema = copy.deepcopy(schema)
        self.rows = copy.deepcopy(rows)
        self.page_size = page_size
        self.full_counts = list(full_counts or [])
        self.full_count_calls = 0
        self.schema_calls = 0
        self.count_calls = []
        self.page_calls = []

    def fetch_schema(self):
        self.schema_calls += 1
        return copy.deepcopy(self.schema)

    def fetch_count(self, where):
        self.count_calls.append(where)
        match = re.search(r"objectid > ([0-9]+)", where)
        if match:
            threshold = int(match.group(1))
            return sum(row["objectid"] > threshold for row in self.rows)
        if self.full_counts:
            index = min(
                self.full_count_calls, len(self.full_counts) - 1
            )
            count = self.full_counts[index]
            self.full_count_calls += 1
            return count
        self.full_count_calls += 1
        return len(self.rows)

    def fetch_page(self, *, where, record_count):
        self.page_calls.append(
            {"where": where, "record_count": record_count}
        )
        match = re.search(r"objectid > ([0-9]+)", where)
        threshold = int(match.group(1)) if match else -1
        return tuple(
            row for row in self.rows if row["objectid"] > threshold
        )[:record_count]


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(phila, "log_search", lambda *_args, **_kwargs: None)


@pytest.fixture
def opa_metadata():
    return _load("opa_metadata.json")


@pytest.fixture
def opa_features():
    return _load("opa_features.json")


@pytest.fixture
def history_schema():
    return _load("history_schema.json")


@pytest.fixture
def history_rows():
    return _load("history_rows.json")


def test_omitted_limit_exhausts_current_matches(
    opa_metadata, opa_features
):
    client = FakeArcGISClient(opa_metadata, opa_features, page_size=2)
    args = phila.build_parser().parse_args(["owner", "PENA"])

    result = phila.execute(args, opa_client=client)

    assert result.status.value == "ok"
    assert result.query.query.requested_limit is None
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert [record["object_id"] for record in result.records] == [1, 2, 28]
    assert [call["record_count"] for call in client.page_calls] == [2, 1]
    assert "objectid > 2" in client.page_calls[1]["where"]
    assert result.records[0]["source_snapshot"]["pages_fetched"] == 2
    assert result.records[0]["source_snapshot"][
        "reported_total_matches"
    ] == 3


def test_bounded_current_query_returns_resumable_keyset_cursor(
    opa_metadata, opa_features
):
    first_client = FakeArcGISClient(opa_metadata, opa_features, page_size=2)
    first_args = phila.build_parser().parse_args(
        ["owner", "PENA", "--limit", "2"]
    )

    first = phila.execute(first_args, opa_client=first_client)

    assert first.status.value == "ok"
    assert [record["object_id"] for record in first.records] == [1, 2]
    assert first.next_cursor

    second_client = FakeArcGISClient(opa_metadata, opa_features, page_size=2)
    second_args = phila.build_parser().parse_args(
        [
            "owner",
            "PENA",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = phila.execute(second_args, opa_client=second_client)

    assert second.status.value == "ok"
    assert [record["object_id"] for record in second.records] == [28]
    assert second.next_cursor is None
    assert "objectid > 2" in second_client.page_calls[0]["where"]


def test_source_change_during_exhaustive_traversal_is_partial(
    opa_metadata, opa_features
):
    client = FakeArcGISClient(
        opa_metadata,
        opa_features,
        full_counts=[3, 4],
    )
    args = phila.build_parser().parse_args(["owner", "PENA"])

    result = phila.execute(args, opa_client=client)

    assert result.status.value == "partial"
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert result.errors[0].code == "source_changed_during_traversal"


def test_cursor_detects_nightly_snapshot_refresh(
    opa_metadata, opa_features
):
    first_client = FakeArcGISClient(
        opa_metadata,
        opa_features,
        metadata_versions=[100, 100],
    )
    first_args = phila.build_parser().parse_args(
        ["owner", "PENA", "--limit", "1"]
    )
    first = phila.execute(first_args, opa_client=first_client)

    refreshed_client = FakeArcGISClient(
        opa_metadata,
        opa_features,
        metadata_versions=[101, 101],
    )
    second_args = phila.build_parser().parse_args(
        [
            "owner",
            "PENA",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = phila.execute(second_args, opa_client=refreshed_client)

    assert second.status.value == "source_changed"
    assert second.errors[0].code == "cursor_snapshot_changed"
    assert refreshed_client.count_calls == []


def test_current_normalization_preserves_deed_joins_and_point_geometry(
    opa_metadata, opa_features
):
    client = FakeArcGISClient(opa_metadata, opa_features[:1])
    args = phila.build_parser().parse_args(
        ["parcel", "341086700", "--geometry"]
    )

    result = phila.execute(args, opa_client=client)

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-pa-philadelphia-opa-properties/42101/"
        "parcel/341086700"
    )
    assert record["owners"][0]["raw_name"] == "PENA ROSADO ELVIS"
    assert record["mailing_address"]["street"] == "700 PINE ST"
    assert record["mailing_address"]["source_state_code"] == "NJ"
    assert record["assessment"]["market_value"] == 199600
    assert record["last_sale"]["book_and_page_raw"] == "54561195"
    assert record["related_routes"]["dor_parcel_geometry"][
        "join_fields"
    ]["registry_number_to_mapreg"] == "062N200131"
    assert record["geometry_role"] == "opa_property_point"
    assert record["geometry_crs"] == "EPSG:4326"


def test_authoritative_empty_current_query_is_no_results(opa_metadata):
    client = FakeArcGISClient(opa_metadata, [])
    args = phila.build_parser().parse_args(["owner", "NO SUCH OWNER"])

    result = phila.execute(args, opa_client=client)

    assert result.status.value == "no_results"
    assert result.records == ()
    assert client.page_calls == []


def test_missing_required_current_field_is_source_changed(
    opa_metadata, opa_features
):
    opa_metadata["fields"] = [
        field
        for field in opa_metadata["fields"]
        if field["name"] != "owner_1"
    ]
    client = FakeArcGISClient(opa_metadata, opa_features)
    args = phila.build_parser().parse_args(["owner", "PENA"])

    result = phila.execute(args, opa_client=client)

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert "owner_1" in result.errors[0].details["missing_fields"]


def test_history_is_exhaustive_and_retains_source_year_labels(
    history_schema, history_rows
):
    client = FakeHistoryClient(history_schema, history_rows, page_size=2)
    args = phila.build_parser().parse_args(
        ["history", "341086700", "--from-year", "2023"]
    )

    result = phila.execute(args, history_client=client)

    assert result.status.value == "ok"
    assert len(result.records) == 3
    assert result.query.source.source_id == phila.HISTORY_SOURCE_ID
    assert result.query.query.requested_limit is None
    assert result.records[0]["assessment_year"] == "2023"
    assert result.records[1]["assessment_year"] == "2027"
    assert result.records[1]["assessment"]["market_value"] == 199600
    assert "year >= '2023'" in client.count_calls[0]
    assert [call["record_count"] for call in client.page_calls] == [2, 1]


def test_history_schema_drift_is_explicit(history_schema, history_rows):
    del history_schema["market_value"]
    client = FakeHistoryClient(history_schema, history_rows)
    args = phila.build_parser().parse_args(
        ["history", "341086700"]
    )

    result = phila.execute(args, history_client=client)

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert "market_value" in result.errors[0].details["missing_fields"]


def test_dor_route_normalizes_separate_parcel_polygon():
    metadata = _load("dor_metadata.json")
    feature = _load("dor_feature.json")
    client = FakeArcGISClient(metadata, [feature])
    args = phila.build_parser().parse_args(
        ["parcel-shape", "062N200131"]
    )

    result = phila.execute(args, dor_client=client)

    assert args.geometry is True
    assert result.status.value == "ok"
    assert result.query.source.source_id == phila.DOR_SOURCE_ID
    record = result.records[0]
    assert record["map_registry_number"] == "062N200131"
    assert record["pin"] == "1001666377"
    assert record["address"]["standardized"] == "430 N 60TH ST"
    assert record["geometry_role"] == (
        "dor_deed_description_parcel_polygon"
    )
    assert record["related_opa_source"]["join_fields"][
        "mapreg_to_registry_number"
    ] == "062N200131"


def test_native_query_modes_escape_literals_and_use_verified_fields():
    assert phila._where_current("owner", "O'NEIL") == (
        "(owner_1 LIKE '%O''NEIL%' OR owner_2 LIKE '%O''NEIL%')"
    )
    assert phila._where_current("parcel", "341086700") == (
        "parcel_number='341086700'"
    )
    assert phila._where_current("pin", "001001666377") == (
        "pin=1001666377"
    )
    assert phila._where_dor("062N200131", "registry") == (
        "(mapreg='062N200131' OR basereg='062N200131')"
    )
    assert phila._where_history(
        "341086700",
        from_year=2015,
        to_year=2027,
    ) == (
        "parcel_number='341086700' AND year >= '2015' "
        "AND year <= '2027'"
    )
    with pytest.raises(phila.PhiladelphiaPropertyError, match="numeric"):
        phila._where_current("objectid", "not-numeric")


def test_alternatives_inventory_has_complementary_official_routes():
    args = phila.build_parser().parse_args(["alternatives"])

    result = phila.execute(args)

    route_ids = {record["route_id"] for record in result.records}
    assert {
        "opa-nightly-current-csv",
        "opa-carto-current-mirror",
        "opa-nightly-history-csv",
        "dor-parcel-polygons",
        "atlas",
        "philadox",
        "department-of-records-and-city-archives",
        "property-application",
    } == route_ids
    carto = next(
        record
        for record in result.records
        if record["route_id"] == "opa-carto-current-mirror"
    )
    assert carto["relationship_to_primary"] == (
        "same OPA dataset; not corroboration"
    )


def test_carto_client_generates_ordered_keyset_sql(monkeypatch):
    client = phila.PhiladelphiaCartoClient(
        page_size=25,
        minimum_interval=0,
    )
    statements = []

    def fake_request(_url, *, params):
        statements.append(params["q"])
        return {"rows": [{"objectid": 9}]}

    monkeypatch.setattr(client, "_request_json", fake_request)
    rows = client.fetch_page(
        where="parcel_number='341086700' AND objectid > 8",
        record_count=25,
    )

    assert rows == ({"objectid": 9},)
    assert "ORDER BY objectid ASC LIMIT 25" in statements[0]
    assert "objectid > 8" in statements[0]


def test_main_rejects_reversed_history_years(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_philadelphia_property.py",
            "history",
            "341086700",
            "--from-year",
            "2027",
            "--to-year",
            "2015",
        ],
    )
    with pytest.raises(SystemExit) as error:
        phila.main()
    assert error.value.code == 2
