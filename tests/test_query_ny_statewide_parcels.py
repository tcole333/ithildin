from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from tools import query_ny_statewide_parcels as ny
from tools.public_records_http import SourceResponseError


FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "public_records" / "ny_statewide_parcels"
)


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


def _metadata(component_key: str):
    fixture = _load("metadata.json")
    component = fixture["components"][component_key]
    fields = (
        fixture["footprint_fields"]
        if component_key == "public-footprint"
        else (fixture["common_fields"] + fixture["extra_normalization_fields"])
    )
    return {
        "layer": {
            "id": component["id"],
            "name": component["name"],
            "type": "Feature Layer",
            "objectIdField": "OBJECTID",
            "geometryType": component["geometry_type"],
            "maxRecordCount": component["max_record_count"],
            "advancedQueryCapabilities": {
                "supportsPagination": True,
                "supportsOrderBy": True,
                "supportsStatistics": True,
            },
            "fields": fields,
        },
        "item": {
            "title": component["title"],
            "type": "Map Service",
            "description": (
                "Publication Date: May 2026. Updated annually. "
                "Official NYS parcel source."
            ),
        },
    }


class FakeParcelClient:
    def __init__(
        self,
        component_key: str,
        features,
        *,
        page_size: int = 2,
        metadata_sequence=None,
        reported_total: int | None = None,
        fail_count: bool = False,
        fail_page_number: int | None = None,
    ):
        self.component_key = component_key
        self.features = copy.deepcopy(features)
        self.page_size = page_size
        self.metadata_sequence = [
            copy.deepcopy(item)
            for item in (metadata_sequence or [_metadata(component_key)])
        ]
        self.reported_total = reported_total
        self.fail_count = fail_count
        self.fail_page_number = fail_page_number
        self.metadata_calls = 0
        self.count_calls = []
        self.page_calls = []

    def fetch_source_metadata(self):
        index = min(
            self.metadata_calls,
            len(self.metadata_sequence) - 1,
        )
        self.metadata_calls += 1
        return copy.deepcopy(self.metadata_sequence[index])

    def _matching(self, where):
        matches = list(self.features)
        thresholds = [
            int(value) for value in re.findall(r"OBJECTID\s*>\s*([0-9]+)", where)
        ]
        if thresholds:
            threshold = max(thresholds)
            matches = [
                feature
                for feature in matches
                if feature["attributes"]["OBJECTID"] > threshold
            ]
        exact = re.search(r"OBJECTID\s*=\s*([0-9]+)", where)
        if exact:
            object_id = int(exact.group(1))
            matches = [
                feature
                for feature in matches
                if feature["attributes"]["OBJECTID"] == object_id
            ]
        return matches

    def fetch_count(self, where, *, spatial_parameters=None):
        self.count_calls.append(
            {
                "where": where,
                "spatial_parameters": dict(spatial_parameters or {}),
            }
        )
        if self.fail_count:
            raise SourceResponseError(
                "fixture count failure",
                url="https://example.invalid/query",
            )
        if self.reported_total is not None and "OBJECTID >" not in where:
            return self.reported_total
        return len(self._matching(where))

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
        if (
            self.fail_page_number is not None
            and len(self.page_calls) == self.fail_page_number
        ):
            raise SourceResponseError(
                "fixture page failure",
                url="https://example.invalid/query",
            )
        return tuple(self._matching(where)[:record_count])


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        ny,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


@pytest.fixture
def features():
    return _load("features.json")


def test_omitted_limit_exhausts_matches_with_objectid_keyset(features):
    client = FakeParcelClient(
        "centroids",
        features["centroids"],
        page_size=2,
    )
    args = ny.build_parser().parse_args(["owner", "STATE"])

    result = ny.execute(args, client=client)

    assert result.status.value == "ok"
    assert result.query.query.requested_limit is None
    assert [record["object_id"] for record in result.records] == [1, 2, 7]
    assert [call["record_count"] for call in client.page_calls] == [2, 1]
    assert "OBJECTID > 2" in client.page_calls[1]["where"]
    assert result.next_cursor is None
    snapshot = result.records[0]["source_snapshot"]
    assert snapshot["reported_total_matches"] == 3
    assert snapshot["pages_fetched"] == 2


def test_bounded_query_returns_and_resumes_keyset_cursor(features):
    first_client = FakeParcelClient(
        "centroids",
        features["centroids"],
        page_size=2,
    )
    first_args = ny.build_parser().parse_args(["owner", "STATE", "--limit", "2"])

    first = ny.execute(first_args, client=first_client)

    assert [record["object_id"] for record in first.records] == [1, 2]
    assert first.next_cursor

    second_client = FakeParcelClient(
        "centroids",
        features["centroids"],
        page_size=2,
    )
    second_args = ny.build_parser().parse_args(
        [
            "owner",
            "STATE",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = ny.execute(second_args, client=second_client)

    assert second.status.value == "ok"
    assert [record["object_id"] for record in second.records] == [7]
    assert second.next_cursor is None
    assert "OBJECTID > 2" in second_client.page_calls[0]["where"]


def test_cursor_is_bound_to_component_and_query_criteria(features):
    first = ny.execute(
        ny.build_parser().parse_args(["owner", "STATE", "--limit", "1"]),
        client=FakeParcelClient("centroids", features["centroids"]),
    )
    assert first.next_cursor

    wrong_component = ny.execute(
        ny.build_parser().parse_args(
            [
                "owner",
                "STATE",
                "--collection",
                "public-parcels",
                "--cursor",
                first.next_cursor,
            ]
        ),
        client=FakeParcelClient(
            "public-parcels",
            features["public-parcels"],
        ),
    )
    assert wrong_component.status.value == "source_changed"
    assert wrong_component.errors[0].code == "stale_cursor"

    changed_query = ny.execute(
        ny.build_parser().parse_args(
            ["address", "STATE", "--cursor", first.next_cursor]
        ),
        client=FakeParcelClient("centroids", features["centroids"]),
    )
    assert changed_query.status.value == "source_changed"
    assert changed_query.errors[0].code == "stale_cursor"


def test_owner_and_location_filters_escape_and_normalize():
    args = ny.build_parser().parse_args(
        [
            "owner",
            "O'Brien",
            "--county",
            "36089",
            "--municipality",
            "Potsdam",
            "--swis",
            "406089",
            "--roll-year",
            "2025",
        ]
    )

    where = ny._where("owner", args)

    assert "O''BRIEN" in where
    assert "ST LAWRENCE" in where
    assert "POTSDAM" in where
    assert "SWIS='406089'" in where
    assert "ROLL_YR=2025" in where


def test_county_borough_aliases_and_invalid_swis():
    assert len(ny.COUNTIES) == 62
    assert len(set(ny.COUNTIES.values())) == 62
    assert ny._county_identity("Brooklyn") == ("36047", "Kings")
    assert ny._county_identity("Staten Island") == ("36085", "Richmond")
    assert ny._county_identity("027") == ("36027", "Dutchess")

    args = ny.build_parser().parse_args(["owner", "TEST", "--swis", "123"])
    result = ny.execute(
        args,
        client=FakeParcelClient("centroids", []),
    )
    assert result.status.value == "unavailable"
    assert result.errors[0].code == "invalid_swis"


def test_native_where_preserves_expression_and_adds_location_filter():
    args = ny.build_parser().parse_args(
        [
            "native",
            "FULL_MARKET_VAL > 1000000",
            "--county",
            "Albany",
        ]
    )

    where = ny._where("native", args)

    assert "FULL_MARKET_VAL > 1000000" in where
    assert "UPPER(COUNTY_NAME)='ALBANY'" in where


def test_deed_query_uses_numeric_book_and_page():
    args = ny.build_parser().parse_args(["deed", "3085", "788", "--county", "Albany"])

    where = ny._where("deed", args)

    assert "(BOOK=3085 AND PAGE=788)" in where
    assert "UPPER(COUNTY_NAME)='ALBANY'" in where


def test_parcel_id_auto_detection_binds_indexable_join_field():
    swis_sbl = ny.build_parser().parse_args(["parcel", "01010004100000021270000000"])
    swis_print = ny.build_parser().parse_args(["parcel", "01010041.00-2-127"])
    explicit_municipal = ny.build_parser().parse_args(
        ["parcel", "01010031094", "--id-type", "municipal"]
    )
    all_fields = ny.build_parser().parse_args(
        ["parcel", "41.00-2-127", "--id-type", "all"]
    )

    assert ny._selector_clause("parcel", swis_sbl) == (
        "SWIS_SBL_ID='01010004100000021270000000'"
    )
    assert ny._selector_clause("parcel", swis_print) == (
        "SWIS_PRINT_KEY_ID='01010041.00-2-127'"
    )
    assert ny._selector_clause("parcel", explicit_municipal) == (
        "MUNI_PARCEL_ID='01010031094'"
    )
    assert "SWIS_SBL_ID='41.00-2-127'" in ny._selector_clause(
        "parcel",
        all_fields,
    )


def test_agency_search_defaults_to_state_owned_component():
    args = ny.build_parser().parse_args(["agency", "DEC"])

    assert args.collection == "state-owned"
    assert ny.build_query(args).query.parameters["component"] == "state-owned"


def test_normalization_preserves_join_keys_ownership_and_geometry(features):
    client = FakeParcelClient(
        "centroids",
        [features["centroids"][2]],
    )
    args = ny.build_parser().parse_args(["objectid", "7", "--geometry"])

    result = ny.execute(args, client=client)

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["canonical_ref"].startswith(
        "PROPERTY:us-ny-statewide-parcels/36027/parcel/"
    )
    assert record["parcel_identifiers"]["swis_sbl_id"] == ("1313006161011234560000")
    assert [owner["role"] for owner in record["owners"]] == [
        "primary_owner",
        "additional_owner",
    ]
    assert record["owner_type"]["description"] == "private"
    assert record["assessment"]["full_market_value"] == 310000.0
    assert record["deed_reference"] == {
        "book": 2024,
        "page": 17,
        "source_scope": "recent-sale window in annual parcel product",
    }
    assert record["geometry_flags"]["duplicate_geometry"] is True
    assert record["geometry"]["x"] == pytest.approx(-73.929)
    assert record["geometry_crs"] == "EPSG:4326"


def test_same_parcel_joins_across_all_three_components(features):
    records = []
    for component_key in ("centroids", "public-parcels", "state-owned"):
        result = ny.execute(
            ny.build_parser().parse_args(
                [
                    "parcel",
                    "01010004100000021270000000",
                    "--collection",
                    component_key,
                    "--geometry",
                ]
            ),
            client=FakeParcelClient(
                component_key,
                [features[component_key][0]],
            ),
        )
        assert result.status.value == "ok"
        records.append(result.records[0])

    assert {record["parcel_identifiers"]["swis_sbl_id"] for record in records} == {
        "01010004100000021270000000"
    }
    assert {record["component"] for record in records} == {
        "centroids",
        "public-parcels",
        "state-owned",
    }
    assert records[0]["geometry_role"].endswith("point_within_parcel")
    assert records[1]["geometry_role"].endswith("public_parcel_polygon")
    assert records[2]["state_ownership"]["agency_name"] == ("New York State- DEC")


def test_point_query_forwards_spatial_intersection_parameters(features):
    client = FakeParcelClient(
        "public-parcels",
        features["public-parcels"],
    )
    args = ny.build_parser().parse_args(["point", "-73.868", "42.721", "--geometry"])

    result = ny.execute(args, client=client)

    assert result.status.value == "ok"
    assert result.query.query.parameters["component"] == "public-parcels"
    spatial = client.page_calls[0]["spatial_parameters"]
    assert spatial == {
        "geometry": "-73.868,42.721",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }
    assert client.page_calls[0]["return_geometry"] is True


def test_authoritative_empty_is_distinct_from_source_failure():
    args = ny.build_parser().parse_args(["owner", "NO SUCH OWNER"])

    empty = ny.execute(
        args,
        client=FakeParcelClient("centroids", []),
    )
    failed = ny.execute(
        args,
        client=FakeParcelClient(
            "centroids",
            [],
            fail_count=True,
        ),
    )

    assert empty.status.value == "no_results"
    assert not empty.errors
    assert failed.status.value == "unavailable"
    assert failed.errors[0].code == "source_error_response"


def test_missing_required_field_is_source_changed(features):
    metadata = _metadata("centroids")
    metadata["layer"]["fields"] = [
        field for field in metadata["layer"]["fields"] if field["name"] != "SWIS_SBL_ID"
    ]
    client = FakeParcelClient(
        "centroids",
        features["centroids"],
        metadata_sequence=[metadata],
    )

    result = ny.execute(
        ny.build_parser().parse_args(["probe"]),
        client=client,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert "SWIS_SBL_ID" in result.errors[0].details["missing_fields"]


def test_annual_release_change_after_records_is_partial(features):
    before = _metadata("centroids")
    after = _metadata("centroids")
    after["item"]["title"] = "NYS 2026 Tax Parcel Centroid Points"
    after["item"]["description"] = "Publication Date: May 2027."
    client = FakeParcelClient(
        "centroids",
        features["centroids"],
        metadata_sequence=[before, after],
    )

    result = ny.execute(
        ny.build_parser().parse_args(["owner", "STATE"]),
        client=client,
    )

    assert result.status.value == "partial"
    assert len(result.records) == 3
    assert result.errors[0].code == "source_schema_changed"


def test_page_failure_after_first_batch_is_partial_and_resumable(features):
    client = FakeParcelClient(
        "centroids",
        features["centroids"],
        page_size=1,
        fail_page_number=2,
    )

    result = ny.execute(
        ny.build_parser().parse_args(["owner", "STATE"]),
        client=client,
    )

    assert result.status.value == "partial"
    assert [record["object_id"] for record in result.records] == [1]
    assert result.next_cursor
    assert result.errors[0].code == "source_error_response"


def test_routes_map_record_roles_and_join_keys():
    result = ny.execute(ny.build_parser().parse_args(["alternatives"]))

    assert result.status.value == "ok"
    routes = {record["route_id"]: record for record in result.records}
    assert routes["centroid-feature-service"]["coverage"] == ("all 62 counties")
    assert "SWIS_SBL_ID" in routes["public-polygon-feature-service"]["join_keys"]
    assert "ten years" in routes["orpts-sales-web"]["record_role"]
    assert "document" in routes["nyc-acris"]["record_role"]
    assert (
        "blank assessment output fields"
        in routes["assessment-coordinate-lookup"]["observed_status"]
    )
    assert routes["service-migration-status"]["url"] == ny.MIGRATION_URL


def test_coverage_reconciles_components_and_footprint(features):
    reported = {
        "centroids": 5_510_061,
        "public-parcels": 3_827_530,
        "state-owned": 35_892,
    }

    def factory(component):
        component_features = features.get(component.key, [])
        return FakeParcelClient(
            component.key,
            component_features,
            reported_total=(
                None if component.key == "public-footprint" else reported[component.key]
            ),
        )

    result = ny.execute(
        ny.build_parser().parse_args(["coverage"]),
        client_factory=factory,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert {
        row["component"]: row["record_count"] for row in record["component_counts"]
    } == reported
    public = record["public_polygon_county_coverage"]
    assert public["county_count"] == 3
    assert [row["county_name"] for row in public["counties"]] == [
        "Albany",
        "Bronx",
        "Broome",
    ]
    assert list(record["cross_component_join_keys"]) == [
        "SWIS_SBL_ID",
        "SWIS_PRINT_KEY_ID",
        "MUNI_PARCEL_ID",
    ]


def test_client_page_binds_order_geometry_and_spatial_parameters(monkeypatch):
    client = ny.NYParcelClient(
        ny.COMPONENTS["public-parcels"],
        page_size=10,
        minimum_interval=0,
    )
    observed = {}

    def request_json(url, *, params=None, headers=None):
        observed.update(
            {
                "url": url,
                "params": dict(params or {}),
                "headers": headers,
            }
        )
        return {"features": [{"attributes": {"OBJECTID": 9}}]}

    monkeypatch.setattr(client, "_request_json", request_json)

    records = client.fetch_page(
        where="OBJECTID > 8",
        record_count=5,
        return_geometry=True,
        spatial_parameters={
            "geometry": "-73.8,42.7",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
        },
    )

    assert records[0]["attributes"]["OBJECTID"] == 9
    assert observed["url"].endswith("/FeatureServer/1/query")
    assert observed["params"]["orderByFields"] == "OBJECTID ASC"
    assert observed["params"]["resultRecordCount"] == 5
    assert observed["params"]["returnGeometry"] == "true"
    assert observed["params"]["outSR"] == 4326
    assert observed["params"]["geometry"] == "-73.8,42.7"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["point", "-181", "42"], "longitude"),
        (["point", "-73", "91"], "latitude"),
        (["owner", "TEST", "--limit", "0"], "positive"),
    ],
)
def test_parser_rejects_invalid_bounds(argv, message, capsys):
    with pytest.raises(SystemExit):
        ny.build_parser().parse_args(argv)
    assert message in capsys.readouterr().err
