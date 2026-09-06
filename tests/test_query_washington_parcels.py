from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_washington_parcels as washington


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "washington_parcels"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


class FakeClient:
    def __init__(
        self,
        metadata: Mapping[str, Any],
        features: list[Mapping[str, Any]],
        *,
        total_count: int | None = None,
        page_size: int = 2,
        layer_url: str = "https://example.test/FeatureServer/0",
        synthetic_boundaries: bool = False,
    ) -> None:
        self.metadata = copy.deepcopy(dict(metadata))
        self.features = copy.deepcopy(features)
        self.total_count = len(features) if total_count is None else total_count
        self.page_size = page_size
        self.layer_url = layer_url
        self.synthetic_boundaries = synthetic_boundaries
        self.calls: list[tuple[str, Any]] = []

    def fetch_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("metadata", None))
        return copy.deepcopy(self.metadata)

    def _matching(self, where: str) -> list[Mapping[str, Any]]:
        rows = copy.deepcopy(self.features)
        if where == "1=1":
            return rows
        if washington.SENTINEL_PARCEL_ID in where:
            return [
                feature
                for feature in rows
                if washington.SENTINEL_PARCEL_ID
                == feature["attributes"].get("PARCEL_ID_NR")
            ]
        for field_name in ("COUNTY_NM", "CODE"):
            marker = f"{field_name}='"
            if marker in where:
                value = where.split(marker, 1)[1].split("'", 1)[0]
                rows = [
                    feature
                    for feature in rows
                    if str(feature["attributes"].get(field_name)) == value
                ]
        return rows

    def fetch_count(
        self,
        where: str,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> int:
        self.calls.append(
            ("count", {"where": where, "parameters": dict(parameters or {})})
        )
        if where == "1=1":
            return self.total_count
        return len(self._matching(where))

    def fetch_page(
        self,
        *,
        where: str,
        offset: int,
        record_count: int,
        out_fields: str = "*",
        return_geometry: bool,
        parameters: Mapping[str, Any] | None = None,
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
                    "parameters": dict(parameters or {}),
                },
            )
        )
        if self.synthetic_boundaries and offset >= 900 and out_fields == "OBJECTID":
            return ({"attributes": {"OBJECTID": offset + 1}},)
        rows = self._matching(where)
        return tuple(rows[offset : offset + record_count])


def _metadata(name: str) -> dict[str, Any]:
    return _fixture(f"{name}_metadata")


def _sentinel(name: str) -> dict[str, Any]:
    return _fixture("sentinels")[name]


def _table_client(
    name: str,
    *,
    total_count: int | None = None,
    features: list[Mapping[str, Any]] | None = None,
) -> FakeClient:
    fixture = _fixture(name)
    return FakeClient(
        fixture,
        features if features is not None else fixture["features"],
        total_count=total_count,
        page_size=2_000,
        layer_url=f"https://example.test/{name}",
    )


def _clients(
    *,
    ecology_features: list[Mapping[str, Any]] | None = None,
    dnr_features: list[Mapping[str, Any]] | None = None,
    wisaard_features: list[Mapping[str, Any]] | None = None,
    ecology_count: int | None = None,
    dnr_count: int | None = None,
    wisaard_count: int | None = None,
    freshness_features: list[Mapping[str, Any]] | None = None,
    freshness_count: int | None = None,
    land_use_features: list[Mapping[str, Any]] | None = None,
    land_use_count: int | None = None,
    synthetic_boundaries: bool = False,
) -> dict[str, FakeClient]:
    ecology_rows = ecology_features or [_sentinel("ecology")]
    dnr_rows = dnr_features or [_sentinel("dnr")]
    wisaard_rows = wisaard_features or [_sentinel("wisaard")]
    return {
        "ecology": FakeClient(
            _metadata("ecology"),
            ecology_rows,
            total_count=ecology_count,
            page_size=2_000,
            synthetic_boundaries=synthetic_boundaries,
        ),
        "dnr": FakeClient(
            _metadata("dnr"),
            dnr_rows,
            total_count=dnr_count,
            page_size=1_000,
            synthetic_boundaries=synthetic_boundaries,
        ),
        "wisaard": FakeClient(
            _metadata("wisaard"),
            wisaard_rows,
            total_count=wisaard_count,
            page_size=2_000,
            synthetic_boundaries=synthetic_boundaries,
        ),
        "freshness": _table_client(
            "county_freshness",
            total_count=freshness_count,
            features=freshness_features,
        ),
        "landuse": _table_client(
            "county_land_use",
            total_count=land_use_count,
            features=land_use_features,
        ),
    }


def _args(*values: str):
    return washington.build_parser().parse_args(list(values))


@pytest.mark.parametrize(
    ("representation", "fixture_name", "maximum", "original_land_use"),
    [
        (washington.ECOLOGY, "ecology", 2_000, True),
        (washington.DNR, "dnr", 1_000, True),
        (washington.WISAARD, "wisaard", 2_000, False),
    ],
)
def test_live_schema_fixtures_are_owner_free(
    representation: washington.Representation,
    fixture_name: str,
    maximum: int,
    original_land_use: bool,
) -> None:
    contract = washington._metadata_contract(
        representation,
        _metadata(fixture_name),
    )

    assert contract["owner_fields_detected"] == []
    assert (
        contract["owner_name_state"]
        == "not_published_by_normalized_statewide_layer"
    )
    assert contract["max_record_count"] == maximum
    assert ("ORIG_LANDUSE_CD" in contract["field_names"]) is original_land_use


def test_new_live_owner_fields_are_observed_and_surfaced() -> None:
    metadata = _metadata("ecology")
    metadata["fields"].extend(
        [
            {
                "name": "OWNER_NAME",
                "alias": "OWNER_NAME",
                "type": "esriFieldTypeString",
            },
            {
                "name": "MAIL_ADDRESS",
                "alias": "MAIL_ADDRESS",
                "type": "esriFieldTypeString",
            },
        ]
    )
    feature = copy.deepcopy(_sentinel("ecology"))
    feature["attributes"]["OWNER_NAME"] = "EXAMPLE HOLDINGS LLC"
    feature["attributes"]["MAIL_ADDRESS"] = "PO BOX 1"
    contract = washington._metadata_contract(washington.ECOLOGY, metadata)

    record = washington._normalize_feature(
        washington.ECOLOGY,
        feature,
        schema_fingerprint_value=contract["schema_fingerprint"],
        owner_fields_detected=contract["owner_fields_detected"],
        dor_land_use={83: "83 - Agricultural current use"},
        freshness={"1": "2026-01-09T00:00:00Z"},
        county_land_use={},
        geometry_requested=False,
    )

    assert contract["owner_fields_detected"] == [
        "MAIL_ADDRESS",
        "OWNER_NAME",
    ]
    assert record["owner_visibility"]["state"] == "published_in_live_schema"
    assert record["owner_visibility"]["published_owner_fields"] == [
        "MAIL_ADDRESS",
        "OWNER_NAME",
    ]
    assert record["owners"] == [
        {
            "raw_name": "EXAMPLE HOLDINGS LLC",
            "source_field": "OWNER_NAME",
        }
    ]
    assert record["owner_related_attributes"] == {
        "MAIL_ADDRESS": "PO BOX 1",
        "OWNER_NAME": "EXAMPLE HOLDINGS LLC",
    }


def test_county_selectors_follow_representation_native_values() -> None:
    ecology = washington._query_spec(
        _args(
            "search",
            "King",
            "--field",
            "county",
            "--no-enrich",
        ),
        washington.ECOLOGY,
    )
    wisaard = washington._query_spec(
        _args(
            "search",
            "King",
            "--field",
            "county",
            "--representation",
            "wisaard",
            "--no-enrich",
        ),
        washington.WISAARD,
    )

    assert "COUNTY_NM='33'" in ecology.where
    assert "COUNTY_NM='King'" in wisaard.where
    assert ecology.county == washington.CountyInfo("King", "033")
    assert washington._resolve_county("53033").name == "King"


@pytest.mark.parametrize(
    ("field", "query", "expected"),
    [
        (
            "parcel",
            "2038010000001",
            "ORIG_PARCEL_ID='2038010000001'",
        ),
        (
            "parcel-id",
            "001-2038010000001",
            "PARCEL_ID_NR='001-2038010000001'",
        ),
        ("situs", "Main St", "SITUS_ADDRESS LIKE '%Main St%'"),
        ("land-use", "83", "LANDUSE_CD=83"),
        (
            "original-land-use",
            "11-10",
            "ORIG_LANDUSE_CD='11-10'",
        ),
    ],
)
def test_search_fields_build_source_queries(
    field: str,
    query: str,
    expected: str,
) -> None:
    spec = washington._query_spec(
        _args(
            "search",
            query,
            "--field",
            field,
            "--no-enrich",
        ),
        washington.ECOLOGY,
    )
    assert expected in spec.where


def test_wisaard_reports_missing_original_land_use_field() -> None:
    spec_args = _args(
        "search",
        "11-10",
        "--field",
        "original-land-use",
        "--representation",
        "wisaard",
        "--no-enrich",
    )
    with pytest.raises(
        washington.WashingtonParcelSelectionError,
        match="does not publish ORIG_LANDUSE_CD",
    ):
        washington._query_spec(spec_args, washington.WISAARD)


def test_point_and_bbox_build_wgs84_spatial_queries() -> None:
    point = washington._query_spec(
        _args("point", "-117.97", "47.255", "--no-enrich"),
        washington.ECOLOGY,
    )
    bbox = washington._query_spec(
        _args(
            "bbox",
            "-117.983",
            "47.250",
            "-117.960",
            "47.261",
            "--no-enrich",
        ),
        washington.ECOLOGY,
    )

    assert point.return_geometry is True
    assert point.geometry_parameters["geometryType"] == "esriGeometryPoint"
    assert json.loads(point.geometry_parameters["geometry"])["x"] == -117.97
    assert bbox.geometry_parameters["geometryType"] == "esriGeometryEnvelope"
    assert json.loads(bbox.geometry_parameters["geometry"])["xmax"] == -117.96


def test_normalization_preserves_data_link_and_county_land_use_join() -> None:
    feature = _fixture("pagination_features")["features"][0]
    contract = washington._metadata_contract(
        washington.ECOLOGY,
        _metadata("ecology"),
    )
    record = washington._normalize_feature(
        washington.ECOLOGY,
        feature,
        schema_fingerprint_value=contract["schema_fingerprint"],
        owner_fields_detected=contract["owner_fields_detected"],
        dor_land_use={11: "11 - Household, single family units"},
        freshness={"11": "2026-02-17T00:00:00Z"},
        county_land_use={
            ("11", "11-10"): "10 - HOUSING UNITS, SINGLE FAMILY"
        },
        geometry_requested=False,
    )

    assert record["canonical_ref"].startswith(
        "PROPERTY:us-wa-state-parcels-normalized/53011/parcel/"
    )
    assert record["jurisdiction"]["county_name"] == "Clark"
    assert record["assessment"] == {
        "land_value": 100000,
        "building_value": 200000,
        "total_value": 300000,
    }
    assert record["land_use"]["county_original_description"] == (
        "10 - HOUSING UNITS, SINGLE FAMILY"
    )
    assert record["data_link"] == feature["attributes"]["DATA_LINK"]
    assert record["county_assessor_route"]["host"] == "gis.clark.wa.gov"
    assert (
        record["county_assessor_route"]["vendor_family"]
        == "county_specific"
    )
    assert record["owner_visibility"]["published_owner_fields"] == []


def test_mirror_records_share_canonical_identity_but_keep_representation() -> None:
    freshness = {"1": "2026-01-09T00:00:00Z"}
    records = []
    for representation in (
        washington.ECOLOGY,
        washington.DNR,
        washington.WISAARD,
    ):
        contract = washington._metadata_contract(
            representation,
            _metadata(representation.key),
        )
        records.append(
            washington._normalize_feature(
                representation,
                _sentinel(representation.key),
                schema_fingerprint_value=contract["schema_fingerprint"],
                owner_fields_detected=contract["owner_fields_detected"],
                dor_land_use={83: "83 - Agricultural current use"},
                freshness=freshness,
                county_land_use={},
                geometry_requested=False,
            )
        )

    assert len({record["canonical_ref"] for record in records}) == 1
    assert {record["source_id"] for record in records} == {
        washington.ECOLOGY_SOURCE_ID,
        washington.DNR_SOURCE_ID,
        washington.WISAARD_SOURCE_ID,
    }
    assert all(
        record["source_lineage"]["mirror_comparison_is_corroboration"] is False
        for record in records
    )
    assert records[0]["county_assessor_route"]["vendor_family"] == (
        "taxsifter_publicaccessnow"
    )
    assert records[2]["source_file_date"] == "2021-02-24T00:00:00Z"


def test_deterministic_pagination_crosses_page_boundary() -> None:
    features = _fixture("pagination_features")["features"]
    client = FakeClient(
        _metadata("ecology"),
        features,
        total_count=4,
        page_size=2,
    )
    spec = washington.QuerySpec(
        where="1=1",
        geometry_parameters={},
        return_geometry=False,
    )

    batch = washington._fetch_batch(
        client,
        washington.ECOLOGY,
        operation="export",
        spec=spec,
        limit=4,
        cursor=None,
    )

    assert [washington._object_id(row) for row in batch.features] == [
        1999,
        2000,
        2001,
        2002,
    ]
    page_calls = [details for name, details in client.calls if name == "page"]
    assert [details["offset"] for details in page_calls] == [0, 2]
    assert [details["record_count"] for details in page_calls] == [2, 2]
    assert batch.pages_fetched == 2
    assert batch.next_cursor is None


def test_cursor_validates_boundary_and_resumes_without_overlap() -> None:
    features = _fixture("pagination_features")["features"]
    spec = washington.QuerySpec(
        where="1=1",
        geometry_parameters={},
        return_geometry=False,
    )
    first_client = FakeClient(
        _metadata("ecology"),
        features,
        total_count=4,
        page_size=2,
    )
    first = washington._fetch_batch(
        first_client,
        washington.ECOLOGY,
        operation="export",
        spec=spec,
        limit=2,
        cursor=None,
    )
    assert first.next_cursor

    second_client = FakeClient(
        _metadata("ecology"),
        features,
        total_count=4,
        page_size=2,
    )
    second = washington._fetch_batch(
        second_client,
        washington.ECOLOGY,
        operation="export",
        spec=spec,
        limit=2,
        cursor=first.next_cursor,
    )

    assert [washington._object_id(row) for row in second.features] == [2001, 2002]
    page_calls = [
        details for name, details in second_client.calls if name == "page"
    ]
    assert page_calls[0]["offset"] == 1
    assert page_calls[0]["out_fields"] == "OBJECTID"
    assert page_calls[1]["offset"] == 2
    assert second.next_cursor is None


def test_cursor_is_bound_to_query_criteria() -> None:
    features = _fixture("pagination_features")["features"]
    client = FakeClient(
        _metadata("ecology"),
        features,
        total_count=4,
        page_size=2,
    )
    first = washington._fetch_batch(
        client,
        washington.ECOLOGY,
        operation="export",
        spec=washington.QuerySpec("1=1", {}, False),
        limit=2,
        cursor=None,
    )

    with pytest.raises(
        washington.WashingtonParcelSelectionError,
        match="different Washington parcel query",
    ):
        washington._fetch_batch(
            FakeClient(
                _metadata("ecology"),
                features,
                total_count=4,
                page_size=2,
            ),
            washington.ECOLOGY,
            operation="export",
            spec=washington.QuerySpec("FIPS_NR='011'", {}, False),
            limit=2,
            cursor=first.next_cursor,
        )


def test_search_execute_enriches_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    logged = []
    monkeypatch.setattr(
        washington,
        "log_search",
        lambda *values: logged.append(values),
    )
    clients = _clients()
    result = washington.execute(
        _args(
            "search",
            washington.SENTINEL_ORIGINAL_ID,
            "--field",
            "parcel",
        ),
        clients=clients,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["normalized_parcel_id"] == washington.SENTINEL_PARCEL_ID
    assert record["source_file_date"] == "2026-01-09T08:00:00Z"
    assert record["data_link"].startswith("https://adamswa-taxsifter")
    assert record["owner_visibility"]["state"] == (
        "not_published_by_normalized_statewide_layer"
    )
    assert logged[0][1:] == (washington.ECOLOGY_SOURCE_ID, 1)


def test_count_operation_preserves_filter_contract() -> None:
    clients = _clients(ecology_count=3_321_859)
    result = washington.execute(
        _args("count", "--county", "Adams"),
        clients=clients,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0]["representation"] == "ecology"
    assert result.records[0]["where"] == "(COUNTY_NM='1')"
    count_call = [
        details
        for name, details in clients["ecology"].calls
        if name == "count"
    ][0]
    assert count_call["where"] == "(COUNTY_NM='1')"


def test_county_freshness_and_land_use_commands_normalize_join_keys() -> None:
    clients = _clients()
    freshness = washington.execute(
        _args("county-freshness", "--county", "Clark"),
        clients=clients,
        log_results=False,
    )
    land_use = washington.execute(
        _args(
            "land-use-codes",
            "--county",
            "Clark",
            "--code",
            "11-10",
        ),
        clients=clients,
        log_results=False,
    )

    assert freshness.status.value == "ok"
    assert freshness.records[0]["county_geoid"] == "53011"
    assert freshness.records[0]["file_date"] == "2026-02-17T08:00:00Z"
    assert land_use.status.value == "ok"
    assert land_use.records[0]["join_key"] == {
        "county_native_code": "11",
        "code": "11-10",
    }


def test_parity_is_health_comparison_not_corroboration() -> None:
    clients = _clients(
        ecology_count=3_321_859,
        dnr_count=3_321_859,
        wisaard_count=3_192_327,
    )
    result = washington.execute(
        _args("parity", "--include-wisaard"),
        clients=clients,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["interpretation"] == "mirror_health_not_corroboration"
    comparisons = {
        comparison["candidate"]: comparison
        for comparison in record["comparisons"]
    }
    assert comparisons["dnr"]["health"] == "aligned"
    assert comparisons["dnr"]["identity_equal"] is True
    assert comparisons["wisaard"]["health"] == "lagging"
    assert comparisons["wisaard"]["differences"]["total_count"] == {
        "baseline": 3_321_859,
        "candidate": 3_192_327,
    }


def _all_freshness_rows() -> list[dict[str, Any]]:
    rows = []
    for object_id, county in enumerate(
        washington.COUNTIES_BY_FIPS.values(),
        start=1,
    ):
        rows.append(
            {
                "attributes": {
                    "OBJECTID": object_id,
                    "COUNTY_NM": county.coded_value,
                    "FILE_DATE": 1767945600000,
                    "GlobalID": f"freshness-{object_id}",
                }
            }
        )
    return rows


def test_operation_level_probe_covers_components_and_boundary() -> None:
    clients = _clients(
        ecology_count=3_321_859,
        dnr_count=3_321_859,
        wisaard_count=3_192_327,
        freshness_features=_all_freshness_rows(),
        freshness_count=39,
        land_use_count=1_931,
        synthetic_boundaries=True,
    )
    result = washington.execute(
        _args(
            "probe",
            "--operation",
            "all",
            "--representation",
            "ecology",
            "--include-wisaard",
        ),
        clients=clients,
        log_results=False,
    )

    assert result.status.value == "ok"
    by_kind = {record["record_kind"]: record for record in result.records}
    assert by_kind["companion_table_probe"]["freshness"]["count"] == 39
    assert by_kind["companion_table_probe"]["county_land_use"]["count"] == 1_931
    assert by_kind["parcel_representation_parity"]["comparisons"][0][
        "health"
    ] == "aligned"
    ecology_probe = by_kind["source_probe"]
    assert not ecology_probe["operations"]["metadata"]["owner_fields_detected"]
    assert ecology_probe["operations"]["count"]["count"] == 3_321_859
    assert ecology_probe["operations"]["sentinel"]["parcel_id"] == (
        washington.SENTINEL_PARCEL_ID
    )
    assert ecology_probe["operations"]["pagination"]["boundary_offset"] == 2_000


def test_explicit_wisaard_probe_does_not_require_all_source_opt_in() -> None:
    clients = _clients(
        wisaard_count=3_192_327,
        freshness_features=_all_freshness_rows(),
        freshness_count=39,
    )
    result = washington.execute(
        _args(
            "probe",
            "--operation",
            "metadata",
            "--representation",
            "wisaard",
        ),
        clients=clients,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["representation"] == "wisaard"
    assert not result.records[0]["operations"]["metadata"][
        "owner_fields_detected"
    ]


def test_emit_honors_output_file(tmp_path: Path) -> None:
    args = _args("metadata", "--output", str(tmp_path / "result.json"))
    result = washington.execute(
        args,
        clients=_clients(),
        log_results=False,
    )

    washington._emit(result, args)

    payload = json.loads((tmp_path / "result.json").read_text())
    assert payload["status"] == "ok"
    assert payload["records"][0]["representation"] == "ecology"
