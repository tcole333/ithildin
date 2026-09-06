from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_dc_property as dc
from tools.public_records_http import (
    PaginatedFetch,
    SourceSchemaError,
    TransportError,
)


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "dc_property"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


def _args(*tokens: str):
    return dc.build_parser().parse_args(list(tokens))


def _fetch(
    records: list[Mapping[str, Any]],
    *,
    fingerprint: str = "response-schema",
    next_cursor: str | None = None,
    truncated: bool = False,
    warnings: tuple[str, ...] = (),
) -> PaginatedFetch:
    return PaginatedFetch(
        records=records,
        next_cursor=next_cursor,
        schema={"kind": "test"},
        schema_fingerprint=fingerprint,
        pages_fetched=1,
        requests_made=1,
        truncated_by_cap=truncated,
        warnings=warnings,
    )


class FakeClient:
    def __init__(
        self,
        *results: PaginatedFetch,
        metadata: Mapping[str, Any] | None = None,
        count: int = 0,
        error: Exception | None = None,
    ) -> None:
        self.results = list(results)
        self.metadata = dict(metadata or _fixture("metadata"))
        self.count = count
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, **kwargs: Any) -> PaginatedFetch:
        self.calls.append(("query", kwargs))
        if self.error is not None:
            raise self.error
        if not self.results:
            raise AssertionError("unexpected query")
        return self.results.pop(0)

    def fetch_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("metadata", {}))
        if self.error is not None:
            raise self.error
        return self.metadata

    def fetch_count(
        self,
        *,
        where: str = "1=1",
        parameters: Mapping[str, Any] | None = None,
    ) -> int:
        self.calls.append(
            (
                "count",
                {"where": where, "parameters": dict(parameters or {})},
            )
        )
        if self.error is not None:
            raise self.error
        return self.count


@pytest.fixture(autouse=True)
def _disable_search_logging(monkeypatch):
    monkeypatch.setattr(dc, "log_search", lambda *_args, **_kwargs: None)


def test_components_keep_account_geometry_sales_and_surveys_attributable():
    assert set(dc.COMPONENTS) == {
        "assessment",
        "geometry",
        "sales",
        "surveys",
    }
    assert len({item.source_id for item in dc.COMPONENTS.values()}) == 4
    assert (
        dc.SOURCE_METADATA["assessment"].metadata["lineage_id"]
        == dc.LINEAGE_ID
    )
    assert (
        dc.SOURCE_METADATA["geometry"].metadata["lineage_id"]
        == dc.LINEAGE_ID
    )
    assert (
        dc.SOURCE_METADATA["assessment"].metadata["lineage_relationship"]
        == "same_itspe_assessment_and_tax_lineage"
    )
    assert dc.SOURCE_METADATA["sales"].metadata["lineage_relationship"] == (
        "cama_sale_observation"
    )


def test_assessment_normalization_preserves_tax_history_and_recorder_join():
    record = dc._normalize_feature(
        dc.ITSPE,
        _fixture("assessment"),
        response_schema_fingerprint="live-schema",
        geometry_crs=4326,
    )

    assert record["record_type"] == "assessment_tax_account"
    assert record["source_id"] == dc.ITSPE_SOURCE_ID
    assert record["native_parcel_id"] == "PAR 01300036"
    assert [owner["raw_name"] for owner in record["owners"]] == [
        "931 BRENTWOOD ROAD LLC",
        "SECOND OWNER LLC",
    ]
    assert record["situs_address"]["ward"] == "5"
    assert (
        record["mailing_address"]["raw"]
        == "2202 18TH ST NW STE 380, WASHINGTON DC 20009-1813"
    )
    assert record["assessment"] == {
        "current_total": 1520370,
        "current_land": 1031850,
        "current_improvement": 488520,
        "prior_land": 1031850,
        "prior_improvement": 382660,
        "prior_total": 1414510,
        "proposed_land": 1031850,
        "proposed_improvement": 495840,
        "proposed_total": 1527690,
        "current_cap": 1520370,
        "proposed_cap": 1527690,
        "currency": "USD",
    }
    assert record["tax"]["total_balance"] == 12543.05
    assert [period["source_prefix"] for period in record["tax"]["periods"]] == [
        "CY1",
        "CY2",
        "PY1",
    ]
    assert record["tax"]["periods"][1]["balance"] == 12543.05
    assert record["last_sale"]["instrument_number"] == "2023000123"
    assert record["recorder_join"] == {
        "source_id": dc.RECORDER_SOURCE_ID,
        "instrument_number": "2023000123",
        "official_url": dc.RECORDER_URL,
        "images_information_url": dc.RECORDER_IMAGES_URL,
    }
    assert record["property_lineage"]["parent_ssl"] == "0130 0035"
    assert record["response_schema_fingerprint"] == "live-schema"
    assert "geometry" not in record


def test_common_owner_polygon_retains_geometry_and_same_lineage():
    record = dc._normalize_feature(
        dc.OWNER_POLYGONS,
        _fixture("owner_polygon"),
        response_schema_fingerprint="polygon-schema",
        geometry_crs=4326,
    )

    assert record["record_type"] == "common_ownership_polygon"
    assert record["source_id"] == dc.OWNER_POLYGON_SOURCE_ID
    assert record["lineage_id"] == dc.LINEAGE_ID
    assert record["native_parcel_id"] == "PAR 01300036"
    assert record["geometry"]["spatialReference"]["wkid"] == 4326
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["source_geometry_crs"] == dc.SOURCE_NATIVE_CRS
    assert record["physical"]["calculated_area"] == 16692
    assert record["property_lineage"]["common_ownership"] == "Y"
    assert record["tax"]["periods"][0]["year_label"] == "2026"


def test_cama_sale_normalization_preserves_qualification_and_currency():
    record = dc._normalize_feature(
        dc.SALES,
        _fixture("sale"),
        response_schema_fingerprint="sales-schema",
        geometry_crs=4326,
    )

    assert record["record_type"] == "property_sale_observation"
    assert record["source_id"] == dc.SALES_SOURCE_ID
    assert record["native_id"] == "420252"
    assert record["native_parcel_id"] == "PAR 01300036"
    assert record["sale"]["consideration"] == 498360
    assert record["sale"]["qualified"] == "Q"
    assert record["sale"]["sale_code"] == "01"
    assert record["sale"]["current_owner_flag"] == "1"
    assert record["sale"]["currency"] == "USD"


def test_survey_normalization_preserves_guid_viewer_and_raw_ssl():
    record = dc._normalize_feature(
        dc.SURVEYS,
        _fixture("survey"),
        response_schema_fingerprint="survey-schema",
        geometry_crs=4326,
    )

    assert record["record_type"] == "surveyor_document"
    assert record["native_id"] == dc.PROBE_SURVEY_GUID
    assert record["native_parcel_id"] == "1653E 0024"
    assert record["ssl"]["raw"] == "1653E   0024"
    assert record["document"]["subdocument_type"] == "Subdivision Books"
    assert record["document"]["book_name"] == "SUBDIVISIONS_BOOK_0105"
    assert record["representations"][0]["document_guid"] == (
        dc.PROBE_SURVEY_GUID
    )
    assert record["representations"][0]["url"].startswith(
        "https://doberecords.dc.gov/"
    )


@pytest.mark.parametrize(
    ("field", "selector", "expected"),
    [
        ("ssl", "PAR 01300036", "SSL='PAR 01300036'"),
        (
            "owner",
            "O'BRIEN",
            "(OWNERNAME LIKE '%O''BRIEN%' OR OWNNAME2 LIKE '%O''BRIEN%')",
        ),
        (
            "address",
            "18TH ST",
            "PREMISEADD LIKE '%18TH ST%'",
        ),
        ("instrument", "2023", "INST_NO LIKE '%2023%'"),
    ],
)
def test_assessment_where_clauses(field, selector, expected):
    assert expected in dc._where_assessment(field, selector)


def test_geometry_and_survey_where_clauses_are_component_specific():
    assert dc._where_geometry("instrument", "ABC") == (
        "INSTNO LIKE '%ABC%'"
    )
    assert dc._where_geometry("objectid", "42") == "OBJECTID=42"
    assert dc._where_surveys("document", dc.PROBE_SURVEY_GUID) == (
        f"DOCGUID='{dc.PROBE_SURVEY_GUID}'"
    )
    assert "SUBDOCUMENTTYPE" in dc._where_surveys("type", "Subdivision")
    assert "BOOKNAME" in dc._where_surveys("book", "0105")


@pytest.mark.parametrize(
    ("selector", "parts"),
    [
        ("PAR 01300036", ("PAR", "0130", "0036")),
        ("1653E 0024", ("1653", "E", "0024")),
        ("5605 0838", ("5605", None, "0838")),
        ("1653E0024", ("1653", "E", "0024")),
    ],
)
def test_ssl_component_parsing_handles_district_source_formats(
    selector,
    parts,
):
    assert dc._ssl_parts(selector) == parts


def test_collapsed_survey_ssl_adds_structured_component_match():
    where = dc._where_surveys("ssl", "1653E 0024")
    assert where == (
        "(SSL='1653E 0024' OR "
        "(SQUARE='1653' AND SUFFIX='E' AND LOT='0024'))"
    )
    no_suffix = dc._where_surveys("ssl", "5605 0838")
    assert "(SUFFIX IS NULL OR SUFFIX='')" in no_suffix


def test_sales_date_bounds_are_validated_and_retained():
    where = dc._where_sales(
        "PAR 01300036",
        start_date="2020-01-01",
        end_date="2026-07-30",
    )
    assert where == (
        "SSL='PAR 01300036' AND "
        "SALE_DATE >= DATE '2020-01-01' AND "
        "SALE_DATE <= DATE '2026-07-30'"
    )
    with pytest.raises(ValueError, match="start date must be YYYY-MM-DD"):
        dc._where_sales(
            "PAR 01300036",
            start_date="01/01/2020",
            end_date=None,
        )


def test_execute_assessment_uses_deterministic_paging_and_logs(monkeypatch):
    logged = []
    monkeypatch.setattr(
        dc, "log_search", lambda *values: logged.append(values)
    )
    client = FakeClient(
        _fetch(
            [_fixture("assessment")],
            next_cursor="arcgis:offset:1",
            truncated=True,
            warnings=("configured cap applied",),
        )
    )
    result = dc.execute(
        _args(
            "assessment",
            "PAR 01300036",
            "--field",
            "ssl",
            "--limit",
            "1",
        ),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "partial"
    assert result.next_cursor == "arcgis:offset:1"
    assert result.records[0]["native_parcel_id"] == "PAR 01300036"
    assert "configured cap applied" in result.warnings
    method, call = client.calls[0]
    assert method == "query"
    assert call["where"] == (
        "(SSL='PAR 01300036' OR "
        "(SQUARE='PAR' AND SUFFIX='0130' AND LOT='0036'))"
    )
    assert call["parameters"]["orderByFields"] == "OBJECTID ASC"
    assert call["requested_limit"] == 1
    assert call["return_geometry"] is False
    assert "CY1TAX" in call["out_fields"]
    logged_query = json.loads(logged[0][0])
    assert logged_query["source"]["source_id"] == dc.ITSPE_SOURCE_ID
    assert logged[0][1:] == (dc.ITSPE_SOURCE_ID, 1)


def test_geometry_point_uses_wgs84_intersection_and_returns_geometry():
    client = FakeClient(_fetch([_fixture("owner_polygon")]))
    result = dc.execute(
        _args(
            "point",
            "-76.9927",
            "38.9176",
            "--out-sr",
            "4326",
        ),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    _, call = client.calls[0]
    assert call["where"] == "1=1"
    assert call["return_geometry"] is True
    assert call["parameters"] == {
        "geometry": "-76.9927,38.9176",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": 4326,
        "orderByFields": "OBJECTID ASC",
    }
    assert result.records[0]["geometry_crs"] == "EPSG:4326"


def test_bbox_rejects_reversed_extent_before_request():
    with pytest.raises(ValueError, match="minimums"):
        dc._selection(
            _args("bbox", "-76.9", "39.0", "-77.0", "38.9")
        )


def test_sales_execute_orders_newest_first_and_keeps_date_bounds():
    client = FakeClient(_fetch([_fixture("sale")]))
    result = dc.execute(
        _args(
            "sales",
            "PAR 01300036",
            "--start-date",
            "2000-01-01",
            "--end-date",
            "2026-12-31",
        ),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    _, call = client.calls[0]
    assert call["where"].startswith("SSL='PAR 01300036'")
    assert "SALE_DATE >= DATE '2000-01-01'" in call["where"]
    assert call["parameters"]["orderByFields"] == (
        "SALE_DATE DESC,OBJECTID ASC"
    )


@pytest.mark.parametrize(
    ("component", "expected_where", "returns_geometry"),
    [
        ("assessment", "SSL='PAR 01300036'", False),
        ("geometry", "SSL='PAR 01300036'", True),
        ("sales", "SSL='PAR 01300036'", False),
        (
            "surveys",
            f"DOCGUID='{dc.PROBE_SURVEY_GUID}'",
            False,
        ),
    ],
)
def test_probe_is_bounded_per_component(
    component,
    expected_where,
    returns_geometry,
):
    fixture = {
        "assessment": "assessment",
        "geometry": "owner_polygon",
        "sales": "sale",
        "surveys": "survey",
    }[component]
    client = FakeClient(_fetch([_fixture(fixture)]))
    result = dc.execute(
        _args("probe", component),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    _, call = client.calls[0]
    assert call["where"] == expected_where
    assert call["requested_limit"] == 1
    assert call["return_geometry"] is returns_geometry
    assert result.query.source.source_id == dc.COMPONENTS[component].source_id


def test_metadata_normalizes_declared_contract_and_relationships():
    client = FakeClient(metadata=_fixture("metadata"))
    result = dc.execute(
        _args("metadata", "geometry"),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["record_type"] == "source_metadata"
    assert record["source_id"] == dc.OWNER_POLYGON_SOURCE_ID
    assert record["geometry_type"] == "esriGeometryPolygon"
    assert record["max_record_count"] == 1000
    assert record["advanced_query_capabilities"]["supportsPagination"] is True
    assert record["field_names"] == (
        "OBJECTID",
        "SSL",
        "OWNERNAME",
        "SHAPE",
    )
    assert record["relationships"][0]["relatedTableId"] == 69
    assert len(record["schema_fingerprint"]) == 64
    assert client.calls == [("metadata", {})]


def test_count_preserves_component_identity():
    client = FakeClient(count=221400)
    result = dc.execute(
        _args("count", "assessment"),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    assert result.records == (
        {
            "record_type": "source_count",
            "source_id": dc.ITSPE_SOURCE_ID,
            "component": "assessment",
            "where": "1=1",
            "count": 221400,
        },
    )
    assert client.calls == [
        ("count", {"where": "1=1", "parameters": {}})
    ]


def test_empty_authoritative_query_is_no_results():
    result = dc.execute(
        _args("sales", "0000 0000"),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([])),
    )
    assert result.status.value == "no_results"
    assert result.records == ()


def test_transport_error_maps_to_unavailable():
    result = dc.execute(
        _args("assessment", "PAR 01300036"),
        access_decision={"allowed": True},
        client=FakeClient(
            error=TransportError(
                "network unavailable",
                url=dc.ITSPE.layer_url,
            )
        ),
    )
    assert result.status.value == "unavailable"
    assert result.errors[0].category == "transport"


def test_malformed_feature_is_explicit_source_change():
    result = dc.execute(
        _args("assessment", "PAR 01300036"),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([{"not_attributes": {}}])),
    )
    assert result.status.value == "source_changed"
    assert result.errors[0].code == "normalization_failed"


def test_metadata_missing_fields_is_explicit_source_change():
    result = dc.execute(
        _args("metadata", "geometry"),
        access_decision={"allowed": True},
        client=FakeClient(metadata={"name": "changed"}),
    )
    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"


def test_sources_command_is_catalog_independent_json():
    completed = subprocess.run(
        [
            sys.executable,
            "tools/query_dc_property.py",
            "sources",
            "--json",
        ],
        cwd=Path(__file__).parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    rows = json.loads(completed.stdout)
    assert {row["component"] for row in rows} == set(dc.COMPONENTS)
    assert {row["source"]["source_id"] for row in rows} == {
        dc.ITSPE_SOURCE_ID,
        dc.OWNER_POLYGON_SOURCE_ID,
        dc.SALES_SOURCE_ID,
        dc.SURVEY_SOURCE_ID,
    }


def test_client_metadata_and_count_validate_source_shapes(monkeypatch):
    client = dc.DCArcGISClient("https://example.test/MapServer/40")
    responses = iter(
        [
            {"name": "Owner Polygons", "fields": []},
            {"count": 137400},
        ]
    )
    monkeypatch.setattr(
        client, "_request_json", lambda *_args, **_kwargs: next(responses)
    )
    assert client.fetch_metadata()["name"] == "Owner Polygons"
    assert client.fetch_count() == 137400


def test_client_rejects_malformed_count(monkeypatch):
    client = dc.DCArcGISClient("https://example.test/MapServer/40")
    monkeypatch.setattr(
        client,
        "_request_json",
        lambda *_args, **_kwargs: {"count": "137400"},
    )
    with pytest.raises(
        SourceSchemaError,
        match="nonnegative integer count",
    ):
        client.fetch_count()


def test_cli_rejects_nonpositive_runtime_values():
    with pytest.raises(SystemExit):
        _args("assessment", "x", "--page-size", "0")
    with pytest.raises(SystemExit):
        _args("geometry", "x", "--minimum-interval", "-1")
