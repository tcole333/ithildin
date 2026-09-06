from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tools import query_virginia_parcels as va
from tools.public_records_http import SourceResponseError, SourceSchemaError


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "virginia_parcels"
)


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


def _item(*, layer_url=va.DEFAULT_LAYER_URL, modified=1782934213000):
    item = _load("item.json")
    item["modified"] = modified
    service_url = layer_url.removesuffix("/0")
    item["description"] = (
        f'<a href="{service_url}">REST Endpoint</a>'
    )
    return item


def _layer(*, missing=()):
    layer = _load("layer.json")
    layer["fields"] = [
        field
        for field in layer["fields"]
        if field["name"] not in set(missing)
    ]
    return layer


def _statistics(*, row_count=3, maximum=3, latest=1767916800000):
    return {
        "min_object_id": 1 if row_count else None,
        "max_object_id": maximum if row_count else None,
        "row_count": row_count,
        "earliest_update": 1767916800000 if row_count else None,
        "latest_update": latest if row_count else None,
    }


def _snapshot(
    *,
    row_count=3,
    maximum=3,
    latest=1767916800000,
    layer_url=va.DEFAULT_LAYER_URL,
    modified=1782934213000,
):
    statistics = _statistics(
        row_count=row_count,
        maximum=maximum,
        latest=latest,
    )
    return va._compatible_snapshot(
        _item(layer_url=layer_url, modified=modified),
        _layer(),
        layer_url,
        statistics,
    )


class FakeClient:
    def __init__(
        self,
        features=(),
        *,
        page_size=2,
        snapshots=None,
        full_counts=None,
        locality_rows=(),
        identity_audit=None,
    ):
        self.features = copy.deepcopy(list(features))
        self.page_size = page_size
        self.snapshots = list(
            snapshots
            or [_snapshot(row_count=len(self.features), maximum=len(self.features))]
        )
        self.full_counts = list(full_counts or [])
        self.locality_rows = copy.deepcopy(list(locality_rows))
        self.identity_audit = identity_audit or {
            "vgin_qpid_null_count": 0,
            "vgin_qpid_duplicate_group_examples": [],
            "vgin_qpid_unique_and_complete_in_observed_release": True,
            "blank_or_null_parcel_id_count": 136861,
        }
        self.snapshot_calls = 0
        self.full_count_calls = 0
        self.count_calls = []
        self.page_calls = []

    def fetch_snapshot(self):
        index = min(self.snapshot_calls, len(self.snapshots) - 1)
        self.snapshot_calls += 1
        return self.snapshots[index]

    def fetch_count(self, where, spatial_parameters=None):
        self.count_calls.append(
            {
                "where": where,
                "spatial_parameters": dict(spatial_parameters or {}),
            }
        )
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        if match:
            threshold = int(match.group(1))
            return sum(
                feature["attributes"]["OBJECTID"] > threshold
                for feature in self.features
            )
        if self.full_counts:
            index = min(self.full_count_calls, len(self.full_counts) - 1)
            count = self.full_counts[index]
            self.full_count_calls += 1
            return count
        self.full_count_calls += 1
        return len(self.features)

    def fetch_page(
        self,
        *,
        where,
        record_count,
        return_geometry,
        spatial_parameters=None,
    ):
        self.page_calls.append(
            {
                "where": where,
                "record_count": record_count,
                "return_geometry": return_geometry,
                "spatial_parameters": dict(spatial_parameters or {}),
            }
        )
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        threshold = int(match.group(1)) if match else -1
        return tuple(
            feature
            for feature in self.features
            if feature["attributes"]["OBJECTID"] > threshold
        )[:record_count]

    def fetch_locality_statistics(self, *, page_size):
        assert page_size > 0
        return tuple(self.locality_rows)

    def fetch_identity_audit(self):
        return dict(self.identity_audit)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(va, "log_search", lambda *_args, **_kwargs: None)


@pytest.fixture
def features():
    return _load("features.json")


def test_official_item_resolves_current_feature_service():
    item = _load("item.json")

    layer_url = va._extract_layer_url(item)

    assert layer_url == va.DEFAULT_LAYER_URL


def test_item_resolver_accepts_an_official_arcgis_host_migration():
    item = _item(
        layer_url=(
            "https://services9.arcgis.com/example/arcgis/rest/services/"
            "Virginia_Parcels/FeatureServer/0"
        )
    )

    assert va._extract_layer_url(item).startswith(
        "https://services9.arcgis.com/"
    )


def test_item_resolver_rejects_non_official_endpoint_host():
    item = _load("item.json")
    item["description"] = (
        '<a href="https://example.test/VA_Parcels/FeatureServer">'
        "REST Endpoint</a>"
    )

    with pytest.raises(SourceSchemaError):
        va._extract_layer_url(item)


def test_snapshot_validates_contract_and_tracks_release_state():
    snapshot = va._compatible_snapshot(
        _load("item.json"),
        _load("layer.json"),
        va.DEFAULT_LAYER_URL,
        _load("dataset_statistics.json"),
    )

    assert snapshot.native_page_size == 2000
    assert snapshot.item_modified == 1782934213000
    assert snapshot.dataset_statistics["row_count"] == 4170691
    assert re.fullmatch(r"[0-9a-f]{64}", snapshot.schema_fingerprint)
    assert re.fullmatch(r"[0-9a-f]{64}", snapshot.data_fingerprint)


def test_snapshot_rejects_missing_identity_field():
    with pytest.raises(SourceSchemaError) as error:
        va._compatible_snapshot(
            _load("item.json"),
            _layer(missing={"VGIN_QPID"}),
            va.DEFAULT_LAYER_URL,
            _load("dataset_statistics.json"),
        )

    assert error.value.details["missing_fields"] == ["VGIN_QPID"]


def test_client_resolves_item_layer_and_dataset_statistics(monkeypatch):
    replacement = (
        "https://services9.arcgis.com/example/arcgis/rest/services/"
        "Virginia_Parcels/FeatureServer/0"
    )
    item = _item(layer_url=replacement)
    layer = _layer()
    calls = []
    client = va.VirginiaParcelClient(minimum_interval=0)

    def fake_request(url, *, params):
        calls.append((url, params))
        if url == va.ITEM_API_URL:
            return item
        if url == replacement:
            return layer
        if url == f"{replacement}/query":
            return {
                "features": [
                    {"attributes": _statistics(row_count=3, maximum=3)}
                ]
            }
        raise AssertionError(url)

    monkeypatch.setattr(client, "_request_json", fake_request)

    snapshot = client.fetch_snapshot()

    assert snapshot.layer_url == replacement
    assert client.layer_url == replacement
    assert [call[0] for call in calls] == [
        va.ITEM_API_URL,
        replacement,
        f"{replacement}/query",
    ]


def test_exact_parcel_selector_escapes_text_and_scopes_locality():
    args = va.build_parser().parse_args(
        [
            "parcel",
            "O'NEIL-7",
            "--field",
            "parcel-id",
            "--fips",
            "51087",
        ]
    )

    selection = va._selection_from_args(args)

    assert "PARCELID='O''NEIL-7'" in selection.where
    assert "FIPS='51087'" in selection.where
    assert "PTM_ID" not in selection.where


def test_auto_numeric_selector_includes_all_exact_identifier_fields():
    args = va.build_parser().parse_args(
        ["parcel", va.PROBE_VGIN_QPID]
    )

    where = va._selection_from_args(args).where

    assert f"VGIN_QPID={va.PROBE_VGIN_QPID}" in where
    assert f"PARCELID='{va.PROBE_VGIN_QPID}'" in where
    assert f"PTM_ID='{va.PROBE_VGIN_QPID}'" in where


def test_point_selection_uses_wgs84_intersection():
    args = va.build_parser().parse_args(
        ["point", "-77.6104", "37.7099", "--fips", "51087"]
    )

    selection = va._selection_from_args(args)

    assert selection.where == "(FIPS='51087')"
    assert selection.spatial_parameters == {
        "geometry": "-77.6104,37.7099",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }


def test_updated_before_is_exclusive_utc_date_boundary():
    args = va.build_parser().parse_args(
        ["search", "--locality", "Henrico County", "--updated-before", "2026-02-01"]
    )

    where = va._selection_from_args(args).where

    assert "LOCALITY='Henrico County'" in where
    assert "LASTUPDATE < 1769904000000" in where


def test_omitted_limit_exhausts_matches_and_normalizes_identity(features):
    client = FakeClient(features)
    args = va.build_parser().parse_args(["search", "--all", "--geometry"])

    result = va.execute(args, client=client)

    assert result.status.value == "ok"
    assert [record["object_id"] for record in result.records] == [1, 2, 3]
    assert result.next_cursor is None
    assert [call["record_count"] for call in client.page_calls] == [2, 1]
    first = result.records[0]
    assert first["source_record_id"] == "VGIN_QPID:5108700000001"
    assert first["canonical_ref"] == (
        "PROPERTY:us-va-vgin-parcels/51087/parcel/5108700000001"
    )
    assert first["identity"]["local_join_fields"] == {
        "fips": "51087",
        "parcel_id": "740-783-1825",
        "parcel_tax_map_id": "740-783-1825",
    }
    assert first["source_dates"]["last_update"] == "2026-01-09"
    assert first["geometry_crs"] == "EPSG:4326"
    assert first["related_routes"]["recorded_land_instruments"][
        "source_id"
    ] == "us-va-secure-remote-access-land-records"


def test_bounded_query_returns_and_resumes_keyset_cursor(features):
    first = va.execute(
        va.build_parser().parse_args(
            ["search", "--all", "--limit", "2"]
        ),
        client=FakeClient(features),
    )

    assert [record["object_id"] for record in first.records] == [1, 2]
    assert first.next_cursor

    second_client = FakeClient(features)
    second = va.execute(
        va.build_parser().parse_args(
            [
                "search",
                "--all",
                "--limit",
                "2",
                "--cursor",
                first.next_cursor,
            ]
        ),
        client=second_client,
    )

    assert second.status.value == "ok"
    assert [record["object_id"] for record in second.records] == [3]
    assert second.next_cursor is None
    assert "OBJECTID > 2" in second_client.page_calls[0]["where"]


def test_cursor_rejects_different_query(features):
    first = va.execute(
        va.build_parser().parse_args(
            ["search", "--fips", "51087", "--limit", "1"]
        ),
        client=FakeClient(features),
    )

    result = va.execute(
        va.build_parser().parse_args(
            [
                "search",
                "--fips",
                "51013",
                "--limit",
                "1",
                "--cursor",
                first.next_cursor,
            ]
        ),
        client=FakeClient(features),
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "cursor_query_mismatch"


def test_cursor_rejects_release_refresh(features):
    first = va.execute(
        va.build_parser().parse_args(
            ["search", "--all", "--limit", "1"]
        ),
        client=FakeClient(features),
    )
    changed = _snapshot(
        row_count=3,
        maximum=3,
        latest=1768003200000,
    )

    result = va.execute(
        va.build_parser().parse_args(
            [
                "search",
                "--all",
                "--limit",
                "1",
                "--cursor",
                first.next_cursor,
            ]
        ),
        client=FakeClient(features, snapshots=[changed]),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "cursor_snapshot_changed"


def test_authoritative_empty_query_is_no_results():
    args = va.build_parser().parse_args(
        ["parcel", "DOES-NOT-EXIST", "--field", "parcel-id"]
    )

    result = va.execute(args, client=FakeClient())

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_locality_coverage_separates_release_from_local_freshness():
    observed = sorted(
        va.EXPECTED_COUNTY_EQUIVALENT_GEOIDS - {"51157"}
    )
    rows = [
        {
            "FIPS": geoid,
            "LOCALITY": f"Locality {geoid}",
            "parcel_count": 1,
            "earliest_update": 1770000000000,
            "latest_update": 1770000000000,
        }
        for geoid in observed
    ]
    rows.extend(
        [
            {
                "FIPS": code,
                "LOCALITY": name,
                "parcel_count": 1,
                "earliest_update": update,
                "latest_update": update,
            }
            for code, name, update in (
                ("5105544", "Bedford Town", 1778025600000),
                ("5118400", "Colonial Beach Town", 1778025600000),
                ("5120752", "Culpeper Town", 1778025600000),
                ("5127440", "Farmville Town", 1757548800000),
            )
        ]
    )
    snapshot = _snapshot(row_count=len(rows), maximum=len(rows))

    record = va._locality_coverage_record(rows, snapshot)

    assert record["source_locality_group_count"] == 136
    assert record["observed_county_equivalent_count"] == 132
    assert record["missing_county_equivalent_geoids"] == ["51157"]
    assert record["incorporated_town_code_count"] == 4
    assert record["oldest_locality_latest_update"]["locality_name"] == (
        "Farmville Town"
    )


def test_fixture_locality_rows_preserve_stale_and_town_observations():
    rows = _load("locality_statistics.json")
    snapshot = _snapshot(
        row_count=sum(row["parcel_count"] for row in rows),
        maximum=sum(row["parcel_count"] for row in rows),
    )

    record = va._locality_coverage_record(rows, snapshot)

    martinsville = next(
        row
        for row in record["localities"]
        if row["locality_name"] == "Martinsville City"
    )
    bedford = next(
        row
        for row in record["localities"]
        if row["locality_name"] == "Bedford Town"
    )
    assert martinsville["latest_update"] == "2017-02-22"
    assert bedford["geography_type"] == "incorporated_town_place"


def test_identity_audit_and_log_suppression(features, monkeypatch):
    logged = []
    monkeypatch.setattr(va, "log_search", lambda *args: logged.append(args))
    args = va.build_parser().parse_args(["identity-audit"])

    result = va.execute(
        args,
        client=FakeClient(features),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0][
        "vgin_qpid_unique_and_complete_in_observed_release"
    ] is True
    assert logged == []


def test_alternatives_include_bulk_assessment_and_recorded_instruments():
    result = va.execute(
        va.build_parser().parse_args(["alternatives"]),
        log_results=False,
    )

    route_ids = {record["route_id"] for record in result.records}
    assert {
        "official-bulk-downloads",
        "local-assessor-commissioner-gis-or-treasurer",
        "circuit-court-land-records",
        "arlington-rich-assessment-example",
        "arlington-recorded-instruments-example",
    } <= route_ids


def test_arcgis_error_fixture_is_not_an_empty_result():
    with pytest.raises(SourceResponseError):
        va._feature_tuple(
            _load("arcgis_error.json"),
            url=va.DEFAULT_LAYER_URL,
            description="test response",
        )


def test_parser_has_no_implicit_result_limit():
    args = va.build_parser().parse_args(
        ["parcel", "740-783-1825", "--fips", "51087"]
    )

    assert args.limit is None
    assert args.page_size == 2000


def test_alternatives_cli_outputs_contract_json():
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(va.__file__)),
            "alternatives",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["status"] == "ok"
    assert payload["query"]["source"]["source_id"] == va.SOURCE_ID
    assert any(
        record["route_id"] == "circuit-court-land-records"
        for record in payload["records"]
    )
