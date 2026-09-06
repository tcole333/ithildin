from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

from tools import query_wisconsin_parcels as wisconsin


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "wisconsin_parcels"
)


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


class FakeParcelClient:
    def __init__(
        self,
        metadata,
        features,
        *,
        page_size=2,
        full_counts=None,
        metadata_versions=None,
        metadata_names=None,
    ):
        self.metadata = copy.deepcopy(metadata)
        self.features = copy.deepcopy(features)
        self.page_size = page_size
        self.full_counts = list(full_counts or [])
        self.metadata_versions = list(metadata_versions or [])
        self.metadata_names = list(metadata_names or [])
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
        if self.metadata_names:
            index = min(
                self.metadata_calls, len(self.metadata_names) - 1
            )
            payload["name"] = self.metadata_names[index]
        self.metadata_calls += 1
        return payload

    def fetch_count(self, where):
        self.count_calls.append(where)
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        if match:
            threshold = int(match.group(1))
            return sum(
                feature["attributes"]["OBJECTID"] > threshold
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
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        threshold = int(match.group(1)) if match else -1
        return tuple(
            feature
            for feature in self.features
            if feature["attributes"]["OBJECTID"] > threshold
        )[:record_count]


class FakeCoverageClient:
    def __init__(self, metadata):
        self.metadata = copy.deepcopy(metadata)
        self.page_size = 2000
        self.metadata_calls = 0
        self.group_calls = []

    def fetch_metadata(self):
        self.metadata_calls += 1
        return copy.deepcopy(self.metadata)

    def fetch_count(self, where):
        assert where == "1=1"
        return 4

    def fetch_grouped_counts(self, where):
        self.group_calls.append(where)
        if where == "1=1":
            rows = [
                {
                    "PARCELSRC": "ADAMS",
                    "PARCELFIPS": "001",
                    "record_count": 2,
                },
                {
                    "PARCELSRC": "KENOSHA",
                    "PARCELFIPS": "059",
                    "record_count": 1,
                },
                {
                    "PARCELSRC": "SCO",
                    "PARCELFIPS": "999",
                    "record_count": 1,
                },
            ]
        elif "NOT AVAILABLE" in where:
            if "IS NOT NULL" in where:
                rows = []
            else:
                rows = [
                    {
                        "PARCELSRC": "KENOSHA",
                        "PARCELFIPS": "059",
                        "record_count": 1,
                    }
                ]
        elif "IS NULL" in where:
            rows = [
                {
                    "PARCELSRC": "ADAMS",
                    "PARCELFIPS": "001",
                    "record_count": 1,
                },
                {
                    "PARCELSRC": "SCO",
                    "PARCELFIPS": "999",
                    "record_count": 1,
                },
            ]
        else:
            rows = [
                {
                    "PARCELSRC": "ADAMS",
                    "PARCELFIPS": "001",
                    "record_count": 1,
                }
            ]
        return tuple(rows)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        wisconsin,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


@pytest.fixture
def metadata():
    return _load("metadata.json")


@pytest.fixture
def features():
    return _load("features.json")


def test_omitted_limit_exhausts_every_match(metadata, features):
    client = FakeParcelClient(metadata, features, page_size=2)
    args = wisconsin.build_parser().parse_args(["owner", "EPSTEIN"])

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "ok"
    assert result.query.query.requested_limit is None
    assert [record["object_id"] for record in result.records] == [1, 2, 28]
    assert [call["record_count"] for call in client.page_calls] == [2, 1]
    assert "OBJECTID > 2" in client.page_calls[1]["where"]
    assert result.next_cursor is None
    snapshot = result.records[0]["source_snapshot"]
    assert snapshot["reported_total_matches"] == 3
    assert snapshot["pages_fetched"] == 2


def test_bounded_query_returns_resumable_keyset_cursor(metadata, features):
    first_client = FakeParcelClient(metadata, features, page_size=2)
    first_args = wisconsin.build_parser().parse_args(
        ["owner", "EPSTEIN", "--limit", "2"]
    )

    first = wisconsin.execute(first_args, client=first_client)

    assert [record["object_id"] for record in first.records] == [1, 2]
    assert first.next_cursor

    second_client = FakeParcelClient(metadata, features, page_size=2)
    second_args = wisconsin.build_parser().parse_args(
        [
            "owner",
            "EPSTEIN",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = wisconsin.execute(second_args, client=second_client)

    assert second.status.value == "ok"
    assert [record["object_id"] for record in second.records] == [28]
    assert second.next_cursor is None
    assert "OBJECTID > 2" in second_client.page_calls[0]["where"]


def test_source_count_change_during_traversal_is_partial(
    metadata, features
):
    client = FakeParcelClient(
        metadata,
        features,
        full_counts=[3, 4],
    )
    args = wisconsin.build_parser().parse_args(["owner", "EPSTEIN"])

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "partial"
    assert len(result.records) == 3
    assert result.errors[0].code == "source_changed_during_traversal"


def test_cursor_detects_annual_release_change(metadata, features):
    first_client = FakeParcelClient(metadata, features)
    first_args = wisconsin.build_parser().parse_args(
        ["owner", "EPSTEIN", "--limit", "1"]
    )
    first = wisconsin.execute(first_args, client=first_client)

    refreshed_client = FakeParcelClient(
        metadata,
        features,
        metadata_names=["V1300_WisconsinParcels_2027"],
    )
    second_args = wisconsin.build_parser().parse_args(
        [
            "owner",
            "EPSTEIN",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = wisconsin.execute(second_args, client=refreshed_client)

    assert second.status.value == "source_changed"
    assert second.errors[0].code == "cursor_release_changed"


def test_compatible_future_release_is_accepted(metadata, features):
    client = FakeParcelClient(
        metadata,
        features[:1],
        metadata_names=["V1300_WisconsinParcels_2027"],
    )
    args = wisconsin.build_parser().parse_args(["probe"])

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "ok"
    snapshot = result.records[0]["source_snapshot"]
    assert snapshot["dataset_release"] == "V1300_WisconsinParcels_2027"
    assert snapshot["release_version"] == 13
    assert snapshot["release_year"] == 2027


def test_missing_required_field_is_reported_as_source_change(
    metadata, features
):
    metadata["fields"] = [
        field
        for field in metadata["fields"]
        if field["name"] != "STATEID"
    ]
    client = FakeParcelClient(metadata, features)
    args = wisconsin.build_parser().parse_args(["probe"])

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "source_changed"
    assert result.errors


def test_owner_withholding_marker_is_a_visibility_state(
    metadata, features
):
    client = FakeParcelClient(metadata, features[1:2])
    args = wisconsin.build_parser().parse_args(
        ["parcel", "01-122-01-103-013"]
    )

    result = wisconsin.execute(args, client=client)

    record = result.records[0]
    assert record["owners"] == ()
    assert record["owner_visibility"] == {
        "state": "withheld_by_source",
        "source_marker": "NOT AVAILABLE",
        "withheld_fields": ("OWNERNME1",),
    }
    assert record["raw_attributes"]["OWNERNME1"] == "NOT AVAILABLE"
    assert record["jurisdiction"]["county_geoid"] == "55059"


def test_known_non_parcel_label_is_preserved_and_classified(
    metadata, features
):
    client = FakeParcelClient(metadata, features[2:])
    args = wisconsin.build_parser().parse_args(
        ["parcel", "ROW", "--geometry"]
    )

    result = wisconsin.execute(args, client=client)

    record = result.records[0]
    assert record["record_type"] == (
        "statewide_annual_non_parcel_map_observation"
    )
    assert record["source_record_classification"]["kind"] == (
        "non_parcel_feature"
    )
    assert record["native_id"] == "001ROW:28"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry_role"] == (
        "aggregated_county_gis_parcel_polygon"
    )


def test_where_builds_source_native_county_and_escaped_queries():
    where = wisconsin._where("owner", "O'Neil", "55025")

    assert "O''NEIL" in where
    assert "PARCELFIPS='025'" in where

    named = wisconsin._where("address", "main st", "Dane")
    assert "UPPER(SITEADRESS)" in named
    assert "UPPER(PARCELSRC)='DANE'" in named


def test_coverage_reports_exact_grouped_visibility(metadata):
    client = FakeCoverageClient(metadata)
    args = wisconsin.build_parser().parse_args(["coverage"])

    result = wisconsin.execute(args, client=client)

    assert result.status.value == "ok"
    summary = result.records[0]
    assert summary["statewide_record_count"] == 4
    assert summary["county_contributor_count"] == 2
    assert summary["special_source_count"] == 1
    assert summary["owner_visibility"] == {
        "published": 1,
        "withheld_by_source": 1,
        "partially_withheld_by_source": 0,
        "not_present_in_dataset": 2,
    }
    assert summary["known_non_parcel_label_count"] == 1
    kenosha = next(
        row
        for row in summary["contributors"]
        if row["contributing_source"] == "KENOSHA"
    )
    assert kenosha["owner_visibility"]["withheld_by_source"] == 1
    assert len(client.group_calls) == 5
    assert client.metadata_calls == 2


def test_alternatives_include_bulk_local_and_transfer_routes():
    args = wisconsin.build_parser().parse_args(["alternatives"])

    result = wisconsin.execute(args)

    route_ids = {record["route_id"] for record in result.records}
    assert {
        "current-statewide-release-downloads",
        "county-gdb-and-shapefile-downloads",
        "historic-statewide-and-county-releases",
        "county-land-record-systems",
        "dor-retr-property-search",
        "dor-retr-historical-downloads",
        "dor-parcel-number-formats",
    } <= route_ids
    local = next(
        record
        for record in result.records
        if record["route_id"] == "county-land-record-systems"
    )
    assert "recorded instrument" in local["use"]


def test_parser_has_no_implicit_collection_limit():
    args = wisconsin.build_parser().parse_args(["owner", "EPSTEIN"])

    assert args.limit is None
    assert args.page_size == 2000


def test_client_page_uses_ordered_keyset_and_optional_geometry(monkeypatch):
    client = wisconsin.WisconsinParcelClient(
        page_size=25,
        minimum_interval=0,
    )
    captured = []

    def fake_request(_url, *, params):
        captured.append(params)
        return {"features": [{"attributes": {"OBJECTID": 9}}]}

    monkeypatch.setattr(client, "_request_json", fake_request)
    features = client.fetch_page(
        where="OBJECTID > 8",
        record_count=25,
        return_geometry=True,
    )

    assert features == ({"attributes": {"OBJECTID": 9}},)
    assert captured[0]["orderByFields"] == "OBJECTID ASC"
    assert captured[0]["resultRecordCount"] == 25
    assert captured[0]["outSR"] == 4326


def test_main_rejects_nonpositive_page_size(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_wisconsin_parcels.py",
            "probe",
            "--page-size",
            "0",
        ],
    )

    with pytest.raises(SystemExit) as error:
        wisconsin.main()

    assert error.value.code == 2
