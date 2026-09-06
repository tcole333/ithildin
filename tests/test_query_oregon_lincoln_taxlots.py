from __future__ import annotations

import copy
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_lincoln_taxlots as adapter
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import SourceResponseError, TransportError


FIXTURE_ROOT = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_lincoln_taxlots"
)


def _text_fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text()


def test_python_options_and_cli_namespace_produce_same_source_query(monkeypatch):
    namespace = adapter.build_parser().parse_args([
        "search", "R452940", "--field", "property", "--limit", "2",
    ])
    options = adapter.QueryOptions(
        command="search", query="R452940", field="property", limit=2,
    )
    monkeypatch.setattr(adapter, "build_parser", lambda: pytest.fail("internal CLI parsing"))
    direct = adapter.execute(options, client=FakeClient(), log_results=False).to_dict()
    legacy = adapter.execute(namespace, client=FakeClient(), log_results=False).to_dict()
    assert direct["query"] == legacy["query"]
    assert direct["records"] == legacy["records"]
    assert direct["status"] == legacy["status"] == "ok"


def test_shared_property_route_uses_validated_python_options(monkeypatch):
    from tools import query_property

    args = query_property.build_parser().parse_args([
        "map", "07-11-03-DC-05800-00", "--source", adapter.SOURCE_ID,
        "--jurisdiction", "41041", "--limit", "2",
    ])
    monkeypatch.setattr(adapter, "build_parser", lambda: pytest.fail("internal CLI parsing"))
    route = query_property.LIVE_ROUTES[adapter.SOURCE_ID]["map"]
    options = route.translate(args, route.adapter_command)
    assert isinstance(options, adapter.QueryOptions)
    assert options.field == "parcel"
    assert options.geometry
    assert options.limit == 2
    result = adapter.execute(options, client=FakeClient(), log_results=False)
    assert result.status == "ok"
    assert result.records[0]["native_identity"]["propertyid"] == "R452940"


@pytest.mark.parametrize("values", [
    {"page_size": 0}, {"limit": 0}, {"timeout": float("inf")},
    {"minimum_interval": -1}, {"field": "unknown"}, {"match": "unknown"},
])
def test_python_options_validate_before_acquiring_source(values):
    with pytest.raises(ValueError):
        adapter.QueryOptions(command="search", query="R452940", **values)


def _json_fixture(name: str) -> dict[str, Any]:
    return json.loads(_text_fixture(name))


def _comparison_values(filter_xml: str) -> list[tuple[str, str, str]]:
    root = ET.fromstring(filter_xml)
    values: list[tuple[str, str, str]] = []
    for comparison in root.iter():
        local = comparison.tag.rsplit("}", 1)[-1]
        if local not in {"PropertyIsEqualTo", "PropertyIsLike"}:
            continue
        field = None
        literal = None
        for child in comparison:
            child_local = child.tag.rsplit("}", 1)[-1]
            if child_local == "ValueReference":
                field = child.text
            elif child_local == "Literal":
                literal = child.text
        assert field is not None
        assert literal is not None
        values.append((local, field, literal))
    return values


def _unescape_like(pattern: str) -> str:
    assert pattern.startswith("*") and pattern.endswith("*")
    inner = pattern[1:-1]
    decoded: list[str] = []
    index = 0
    while index < len(inner):
        if inner[index] == "!" and index + 1 < len(inner):
            index += 1
        decoded.append(inner[index])
        index += 1
    return "".join(decoded)


class FakeClient:
    def __init__(
        self,
        *,
        features: list[Mapping[str, Any]] | None = None,
        page_size: int = 2,
    ) -> None:
        source = features or _json_fixture("search_features.json")["features"]
        self.features = copy.deepcopy(source)
        self.page_size = page_size
        self.calls: list[tuple[str, Any]] = []

    def fetch_capabilities(self) -> str:
        self.calls.append(("capabilities", None))
        return _text_fixture("capabilities.xml")

    def describe_schema(self) -> str:
        self.calls.append(("schema", None))
        return _text_fixture("schema.xsd")

    def _matching(self, filter_xml: str | None) -> list[Mapping[str, Any]]:
        if filter_xml is None:
            records = self.features
        else:
            comparisons = _comparison_values(filter_xml)
            records = []
            for feature in self.features:
                properties = feature["properties"]
                matched = False
                for comparison, field, literal in comparisons:
                    observed = str(properties.get(field, ""))
                    if comparison == "PropertyIsEqualTo":
                        matched = observed.casefold() == literal.casefold()
                    else:
                        matched = (
                            _unescape_like(literal).casefold() in observed.casefold()
                        )
                    if matched:
                        break
                if matched:
                    records.append(feature)
        return sorted(
            records,
            key=lambda feature: (
                feature["properties"]["propertyid"],
                feature["properties"]["ogc_fid"],
            ),
        )

    def fetch_count(self, filter_xml: str | None) -> adapter.CountResult:
        self.calls.append(("count", filter_xml))
        return adapter.CountResult(
            number_matched=len(self._matching(filter_xml)),
            number_returned=0,
            timestamp="2026-07-29T19:47:50",
        )

    def fetch_page(
        self,
        filter_xml: str | None,
        *,
        start_index: int,
        count: int,
    ) -> Mapping[str, Any]:
        self.calls.append(
            (
                "page",
                {
                    "filter": filter_xml,
                    "start_index": start_index,
                    "count": count,
                },
            )
        )
        rows = copy.deepcopy(
            self._matching(filter_xml)[start_index : start_index + count]
        )
        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": adapter.EXPECTED_RETURNED_CRS},
            },
            "features": rows,
        }


class BrokenClient(FakeClient):
    def fetch_capabilities(self) -> str:
        raise TransportError(
            "offline fixture transport failed",
            url=adapter.MAPSERVER_URL,
        )


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "log_search", lambda *_args, **_kwargs: None)


def _search_args(*values: str) -> Any:
    return adapter.build_parser().parse_args(["search", *values])


def _probe_args() -> Any:
    return adapter.build_parser().parse_args(
        [
            "probe",
            "--minimum-interval",
            "0",
            "--retry-attempts",
            "1",
        ]
    )


def test_verified_capabilities_preserve_wfs_2_paging_and_crs_lineage() -> None:
    contract = adapter.parse_capabilities(_text_fixture("capabilities.xml"))

    assert contract.service_title == "Parcel Maps"
    assert contract.version == "2.0.0"
    assert contract.result_paging is True
    assert contract.sorting is True
    assert contract.feature_name == "ms:Taxlots_selection"
    assert contract.default_crs == "urn:ogc:def:crs:EPSG::26915"
    assert "urn:ogc:def:crs:EPSG::4326" in contract.other_crs
    assert contract.wgs84_bounds == adapter.EXPECTED_WGS84_BOUNDS
    assert "application/json" in contract.output_formats


def test_declared_schema_retains_native_fields_and_stable_fingerprint() -> None:
    schema = adapter.parse_schema(_text_fixture("schema.xsd"))

    assert schema.field_names == adapter.DECLARED_FIELDS
    assert schema.schema_fingerprint == adapter.EXPECTED_SCHEMA_FINGERPRINT
    assert schema.target_namespace == "http://mapserver.gis.umn.edu/mapserver"
    assert schema.schema["kind"] == "wfs_xsd_declared"


def test_hits_parser_retains_count_and_source_timestamp() -> None:
    all_records = adapter.parse_hits(_text_fixture("all_hits.xml"))
    sentinel = adapter.parse_hits(_text_fixture("sentinel_hits.xml"))

    assert all_records.number_matched == 44_966
    assert all_records.number_returned == 0
    assert all_records.timestamp == "2026-07-29T19:47:50"
    assert sentinel.number_matched == 1


def test_fes_exact_filter_is_xml_safe_and_preserves_literal_characters() -> None:
    selector = "R<&>*?!"
    filter_xml = adapter.build_filter(selector, "property", "exact")
    comparisons = _comparison_values(filter_xml)

    assert "&lt;" in filter_xml
    assert "&amp;" in filter_xml
    assert comparisons == [("PropertyIsEqualTo", "propertyid", selector)]


def test_fes_contains_filter_escapes_wildcards_for_every_address_field() -> None:
    selector = "A&B <TRUST> *?!"
    filter_xml = adapter.build_filter(selector, "address", "contains")
    comparisons = _comparison_values(filter_xml)

    assert len(comparisons) == len(adapter.SEARCH_FIELDS["address"])
    assert {field for _kind, field, _literal in comparisons} == set(
        adapter.SEARCH_FIELDS["address"]
    )
    for kind, _field, literal in comparisons:
        assert kind == "PropertyIsLike"
        assert _unescape_like(literal) == selector


def test_live_client_uses_verified_wfs_2_getfeature_parameters() -> None:
    class Response:
        status_code = 200
        headers: Mapping[str, str] = {}
        text = _text_fixture("sentinel.json")

    class Transport:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def request(self, method: str, url: str, **kwargs: Any) -> Response:
            self.calls.append({"method": method, "url": url, **kwargs})
            return Response()

    transport = Transport()
    client = adapter.LincolnWFSClient(
        page_size=10,
        minimum_interval=0,
        retry_attempts=1,
        transport=transport,
    )
    filter_xml = adapter.build_filter("R452940", "property", "exact")
    payload = client.fetch_page(filter_xml, start_index=3, count=7)

    assert payload["features"][0]["properties"]["propertyid"] == "R452940"
    request = transport.calls[0]
    assert request["method"] == "GET"
    assert request["url"] == adapter.MAPSERVER_URL
    params = request["params"]
    assert params["map"] == adapter.MAPFILE
    assert params["VERSION"] == "2.0.0"
    assert params["TYPENAMES"] == "ms:Taxlots_selection"
    assert params["SRSNAME"] == "urn:ogc:def:crs:EPSG::4326"
    assert params["COUNT"] == 7
    assert params["STARTINDEX"] == 3
    assert params["SORTBY"] == adapter.SORT_BY
    assert params["FILTER"] == filter_xml
    assert request["stream"] is True


def test_exact_property_search_normalizes_join_keys_without_geometry() -> None:
    result = adapter.execute(
        _search_args(
            "R452940",
            "--field",
            "property",
            "--match",
            "exact",
            "--minimum-interval",
            "0",
        ),
        client=FakeClient(),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    payload = result.to_dict()
    assert payload["status"] == "ok"
    assert payload["next_cursor"] is None
    record = payload["records"][0]
    assert record["native_identity"] == {
        "propertyid": "R452940",
        "parcelid": "07-11-03-DC-05800-00",
        "ogc_fid": "42750936",
        "imagekey": "07 11 03 DC",
    }
    assert record["native_id"] == "42750936"
    assert record["native_id_basis"] == "ogc_fid"
    assert record["source_record_id"] == "42750936"
    assert record["evidence_ref"] == record["canonical_ref"]
    assert record["access_state"] == "public_anonymous"
    assert record["jurisdiction"]["county_geoid"] == adapter.COUNTY_GEOID
    assert record["owners"][0]["raw_name"].endswith("SCRUTTON LLC")
    assert record["join_keys"]["propertyweb_property_quick_ref_id"] == "R452940"
    assert (
        record["join_candidates"][adapter.PROPERTYWEB_SOURCE_ID]["property_quick_ref"]
        == "R452940"
    )
    assert record["official_links"]["assessor_map"].startswith("https://ormap.net/")
    assert record["official_links"]["interactive_map"] == (
        adapter.APP_URL
        + "?service=search-Taxlots&field:parcelid=07-11-03-DC-05800-00"
    )
    assert adapter.INTERACTIVE_MAP_SOURCE_ID == adapter.SOURCE_ID
    assert adapter.ORMAP_SOURCE_ID == "us-or-ormap-cadastral-routing"
    assert record["geometry_available"] is True
    assert "geometry" not in record
    assert record["geometry_lineage"] == {
        "source_default_crs": adapter.SOURCE_DEFAULT_CRS,
        "wfs_requested_srs": adapter.REQUESTED_CRS,
        "geojson_reported_crs": adapter.EXPECTED_RETURNED_CRS,
        "coordinate_order": "longitude_latitude",
        "transformation_performed_by": "Lincoln County MapServer WFS",
    }
    complements = {item["source_id"] for item in record["complementary_sources"]}
    assert {
        adapter.PROPERTYWEB_SOURCE_ID,
        adapter.ORMAP_SOURCE_ID,
        adapter.RECORDER_SOURCE_ID,
        adapter.STATEWIDE_TAXLOT_SOURCE_ID,
    } <= complements


def test_geometry_is_included_only_when_requested() -> None:
    result = adapter.execute(
        _search_args(
            "R452940",
            "--field",
            "property",
            "--geometry",
            "--minimum-interval",
            "0",
        ),
        client=FakeClient(),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    record = result.to_dict()["records"][0]
    assert record["geometry"]["type"] == "Polygon"
    assert record["geometry_crs"] == adapter.EXPECTED_RETURNED_CRS
    assert record["geometry"]["coordinates"][0][0] == [-124.01336, 44.9883]


def test_query_bound_cursor_resumes_after_verified_boundary() -> None:
    client = FakeClient(page_size=1)
    first_args = _search_args(
        "R",
        "--field",
        "property",
        "--match",
        "contains",
        "--limit",
        "2",
        "--minimum-interval",
        "0",
    )
    first = adapter.execute(first_args, client=client, log_results=False)

    assert isinstance(first, PublicRecordsResult)
    first_payload = first.to_dict()
    assert [
        record["native_identity"]["propertyid"] for record in first_payload["records"]
    ] == [
        "R000001",
        "R000002",
    ]
    cursor = first_payload["next_cursor"]
    assert cursor

    second_args = _search_args(
        "R",
        "--field",
        "property",
        "--match",
        "contains",
        "--limit",
        "2",
        "--cursor",
        cursor,
        "--minimum-interval",
        "0",
    )
    second = adapter.execute(second_args, client=client, log_results=False)

    assert isinstance(second, PublicRecordsResult)
    second_payload = second.to_dict()
    assert [
        record["native_identity"]["propertyid"] for record in second_payload["records"]
    ] == [
        "R000003",
        "R452940",
    ]
    assert second_payload["next_cursor"] is None
    page_calls = [details for kind, details in client.calls if kind == "page"]
    assert {"start_index": 1, "count": 1} == {
        key: page_calls[-3][key] for key in ("start_index", "count")
    }
    assert page_calls[-2]["start_index"] == 2
    assert page_calls[-1]["start_index"] == 3


def test_composite_cursor_preserves_duplicate_property_account_features() -> None:
    base = _json_fixture("search_features.json")["features"][0]
    features: list[Mapping[str, Any]] = []
    for ogc_fid in ("42710001", "42710002", "42710003"):
        feature = copy.deepcopy(base)
        feature["properties"]["propertyid"] = "R73753"
        feature["properties"]["parcelid"] = "08-11-11-AA-00100-00"
        feature["properties"]["ogc_fid"] = ogc_fid
        features.append(feature)
    client = FakeClient(features=features, page_size=1)

    first = adapter.execute(
        _search_args(
            "R73753",
            "--field",
            "property",
            "--match",
            "exact",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    assert isinstance(first, PublicRecordsResult)
    first_payload = first.to_dict()
    assert first_payload["status"] == "ok"
    assert [record["source_record_id"] for record in first_payload["records"]] == [
        "42710001",
        "42710002",
    ]
    assert len({record["canonical_ref"] for record in first_payload["records"]}) == 2
    assert first_payload["next_cursor"]

    second = adapter.execute(
        _search_args(
            "R73753",
            "--field",
            "property",
            "--match",
            "exact",
            "--limit",
            "2",
            "--cursor",
            first_payload["next_cursor"],
        ),
        client=client,
        log_results=False,
    )
    assert isinstance(second, PublicRecordsResult)
    second_payload = second.to_dict()
    assert [record["source_record_id"] for record in second_payload["records"]] == [
        "42710003"
    ]
    assert second_payload["next_cursor"] is None


def test_composite_order_guard_rejects_decreasing_fid_within_property() -> None:
    base = _json_fixture("search_features.json")["features"][0]
    features = []
    for ogc_fid in ("42710002", "42710001"):
        feature = copy.deepcopy(base)
        feature["properties"]["propertyid"] = "R73753"
        feature["properties"]["ogc_fid"] = ogc_fid
        features.append(feature)

    class MisorderedClient(FakeClient):
        def _matching(self, filter_xml: str | None) -> list[Mapping[str, Any]]:
            return list(self.features)

    result = adapter.execute(
        _search_args(
            "R73753",
            "--field",
            "property",
            "--match",
            "exact",
            "--limit",
            "2",
        ),
        client=MisorderedClient(features=features),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    payload = result.to_dict()
    assert payload["status"] == "source_changed"
    assert payload["errors"][0]["code"] == "pagination_stalled"


def test_cursor_rejects_query_and_snapshot_changes() -> None:
    client = FakeClient(page_size=2)
    first = adapter.execute(
        _search_args(
            "R",
            "--field",
            "property",
            "--match",
            "contains",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    assert isinstance(first, PublicRecordsResult)
    cursor = first.to_dict()["next_cursor"]
    assert cursor

    mismatch = adapter.execute(
        _search_args(
            "R0",
            "--field",
            "property",
            "--match",
            "contains",
            "--limit",
            "2",
            "--cursor",
            cursor,
        ),
        client=client,
        log_results=False,
    )
    assert isinstance(mismatch, PublicRecordsResult)
    assert mismatch.to_dict()["errors"][0]["code"] == "cursor_query_mismatch"

    extra = copy.deepcopy(client.features[-1])
    extra["properties"]["propertyid"] = "R999999"
    extra["properties"]["ogc_fid"] = "999999"
    client.features.append(extra)
    changed = adapter.execute(
        _search_args(
            "R",
            "--field",
            "property",
            "--match",
            "contains",
            "--limit",
            "2",
            "--cursor",
            cursor,
        ),
        client=client,
        log_results=False,
    )
    assert isinstance(changed, PublicRecordsResult)
    assert changed.to_dict()["errors"][0]["code"] == "cursor_snapshot_changed"


def test_cursor_boundary_guard_detects_same_count_row_replacement() -> None:
    client = FakeClient(page_size=2)
    first = adapter.execute(
        _search_args(
            "R",
            "--field",
            "property",
            "--match",
            "contains",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    assert isinstance(first, PublicRecordsResult)
    cursor = first.to_dict()["next_cursor"]
    client.features[1]["properties"]["ogc_fid"] = "replacement"

    resumed = adapter.execute(
        _search_args(
            "R",
            "--field",
            "property",
            "--match",
            "contains",
            "--limit",
            "2",
            "--cursor",
            cursor,
        ),
        client=client,
        log_results=False,
    )

    assert isinstance(resumed, PublicRecordsResult)
    assert resumed.to_dict()["errors"][0]["code"] == "cursor_boundary_changed"


def test_transport_failure_is_not_reported_as_no_results() -> None:
    result = adapter.execute(
        _search_args(
            "R452940",
            "--field",
            "property",
            "--match",
            "exact",
        ),
        client=BrokenClient(),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    payload = result.to_dict()
    assert payload["status"] == "unavailable"
    assert payload["records"] == []
    assert payload["errors"][0]["code"] == "transport_error"


@pytest.mark.parametrize(
    ("headers", "chunks"),
    [
        ({"Content-Length": "6"}, [b"ignored"]),
        ({}, [b"123", b"456"]),
    ],
)
def test_wfs_response_byte_bound_applies_to_declared_and_streamed_sizes(
    headers: Mapping[str, str],
    chunks: list[bytes],
) -> None:
    class Response:
        status_code = 200
        encoding = "utf-8"

        def __init__(self) -> None:
            self.headers = headers
            self.closed = False

        def iter_content(self, _chunk_size: int) -> Any:
            yield from chunks

        def close(self) -> None:
            self.closed = True

    class Transport:
        def __init__(self) -> None:
            self.response = Response()

        def request(self, *_args: Any, **_kwargs: Any) -> Response:
            return self.response

    transport = Transport()
    client = adapter.LincolnWFSClient(
        max_response_bytes=5,
        minimum_interval=0,
        retry_attempts=1,
        transport=transport,
    )

    with pytest.raises(SourceResponseError, match="byte bound"):
        client.fetch_capabilities()
    assert transport.response.closed is True


def test_page_size_and_geojson_crs_contracts_are_enforced() -> None:
    with pytest.raises(ValueError, match=str(adapter.MAX_PAGE_SIZE)):
        adapter.LincolnWFSClient(page_size=adapter.MAX_PAGE_SIZE + 1)

    class WrongCRSClient(FakeClient):
        def fetch_page(
            self,
            filter_xml: str | None,
            *,
            start_index: int,
            count: int,
        ) -> Mapping[str, Any]:
            payload = dict(
                super().fetch_page(
                    filter_xml,
                    start_index=start_index,
                    count=count,
                )
            )
            payload["crs"] = {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
            }
            return payload

    result = adapter.execute(
        _search_args("R452940", "--field", "property"),
        client=WrongCRSClient(),
        log_results=False,
    )
    assert isinstance(result, PublicRecordsResult)
    assert result.to_dict()["status"] == "source_changed"
    assert result.to_dict()["errors"][0]["code"] == "source_schema_changed"


def test_probe_packet_preserves_schema_count_sentinel_and_update_signal() -> None:
    result = adapter.execute(
        _probe_args(),
        client=FakeClient(),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    payload = result.to_dict()
    assert payload["status"] == "ok"
    probe = payload["records"][0]
    assert probe["protocol_contract"]["result_paging"] is True
    assert probe["protocol_contract"]["ordering"] == adapter.SORT_BY
    assert probe["schema_baseline"]["matches"] is True
    assert probe["count_baseline"]["current_count"] == 4
    assert probe["sentinel_count"] == 1
    assert probe["representative_row"]["native_identity"]["parcelid"] == (
        adapter.SENTINEL_PARCEL_ID
    )
    assert probe["crs_lineage"]["source_default_crs"] == ("urn:ogc:def:crs:EPSG::26915")
    assert "updated nightly" in probe["update_observation"]["mapbook_statement"]


def test_sources_exposes_distinct_components_and_process_learnings() -> None:
    args = adapter.build_parser().parse_args(["sources"])
    payload = adapter.execute(args, log_results=False)

    assert isinstance(payload, dict)
    source = payload["sources"][0]
    assert source["source_id"] == adapter.SOURCE_ID
    assert source["catalog_metadata"]["access_method"] == "wfs"
    assert source["geometry"]["opt_in"] is True
    assert source["search_fields"]["owner"] == ["ownname"]
    assert source["search_fields"]["property"] == ["propertyid"]
    assert {learning["scope"] for learning in payload["process_learnings"]} == {
        "protocol_discovery",
        "crs_lineage",
        "identity_and_paging",
        "complementary_records",
    }


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_TAXLOTS") != "1",
    reason="set RUN_LIVE_OR_LINCOLN_TAXLOTS=1 for official WFS probes",
)
def test_live_official_probe() -> None:
    result = adapter.execute(_probe_args(), log_results=False)

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok", result.to_dict()
    probe = result.to_dict()["records"][0]
    assert probe["count_baseline"]["current_count"] > 40_000
    assert probe["schema_baseline"]["matches"] is True
    assert probe["sentinel_count"] == 1
    assert probe["representative_row"]["native_identity"]["propertyid"] == (
        adapter.SENTINEL_PROPERTY_ID
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_TAXLOTS") != "1",
    reason="set RUN_LIVE_OR_LINCOLN_TAXLOTS=1 for official WFS probes",
)
def test_live_exact_search_with_geometry() -> None:
    result = adapter.execute(
        _search_args(
            adapter.SENTINEL_PROPERTY_ID,
            "--field",
            "property",
            "--match",
            "exact",
            "--geometry",
            "--minimum-interval",
            "0.1",
        ),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok", result.to_dict()
    record = result.to_dict()["records"][0]
    assert record["native_identity"]["parcelid"] == adapter.SENTINEL_PARCEL_ID
    assert record["geometry"]["type"] == "Polygon"
    assert record["geometry_crs"] == adapter.EXPECTED_RETURNED_CRS


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_TAXLOTS") != "1",
    reason="set RUN_LIVE_OR_LINCOLN_TAXLOTS=1 for official WFS probes",
)
@pytest.mark.parametrize(
    ("selector", "field", "match", "expected_property_id"),
    [
        ("SCRUTTON", "owner", "contains", None),
        ("3205 NW INLET", "address", "contains", adapter.SENTINEL_PROPERTY_ID),
        (
            adapter.SENTINEL_PARCEL_ID,
            "parcel",
            "exact",
            adapter.SENTINEL_PROPERTY_ID,
        ),
        ("452940", "property", "contains", adapter.SENTINEL_PROPERTY_ID),
    ],
)
def test_live_search_modes_return_matching_rows(
    selector: str,
    field: str,
    match: str,
    expected_property_id: str | None,
) -> None:
    result = adapter.execute(
        _search_args(
            selector,
            "--field",
            field,
            "--match",
            match,
            "--limit",
            "5",
            "--minimum-interval",
            "0.1",
        ),
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status.value == "ok", result.to_dict()
    records = result.to_dict()["records"]
    if expected_property_id:
        assert expected_property_id in {
            record["native_identity"]["propertyid"] for record in records
        }
    else:
        assert records
        assert all(
            selector.casefold() in record["source_native"]["ownname"].casefold()
            for record in records
        )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_TAXLOTS") != "1",
    reason="set RUN_LIVE_OR_LINCOLN_TAXLOTS=1 for official WFS probes",
)
def test_live_owner_cursor_resumes_on_next_sorted_feature() -> None:
    first_args = _search_args(
        "SMITH",
        "--field",
        "owner",
        "--match",
        "contains",
        "--limit",
        "1",
        "--page-size",
        "1",
        "--minimum-interval",
        "0.1",
    )
    first = adapter.execute(first_args, log_results=False)

    assert isinstance(first, PublicRecordsResult)
    assert first.status.value == "ok", first.to_dict()
    first_payload = first.to_dict()
    assert first_payload["next_cursor"]

    second_args = _search_args(
        "SMITH",
        "--field",
        "owner",
        "--match",
        "contains",
        "--limit",
        "1",
        "--page-size",
        "1",
        "--cursor",
        first_payload["next_cursor"],
        "--minimum-interval",
        "0.1",
    )
    second = adapter.execute(second_args, log_results=False)

    assert isinstance(second, PublicRecordsResult)
    assert second.status.value == "ok", second.to_dict()
    assert (
        second.to_dict()["records"][0]["source_record_id"]
        != (first_payload["records"][0]["source_record_id"])
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_TAXLOTS") != "1",
    reason="set RUN_LIVE_OR_LINCOLN_TAXLOTS=1 for official WFS probes",
)
def test_live_duplicate_propertyid_cursor_uses_ogc_fid_tiebreaker() -> None:
    first = adapter.execute(
        _search_args(
            "R73753",
            "--field",
            "property",
            "--match",
            "exact",
            "--limit",
            "1",
            "--page-size",
            "1",
            "--minimum-interval",
            "0.1",
        ),
        log_results=False,
    )
    assert isinstance(first, PublicRecordsResult)
    first_payload = first.to_dict()
    assert first_payload["status"] == "ok", first_payload
    assert first_payload["next_cursor"]

    second = adapter.execute(
        _search_args(
            "R73753",
            "--field",
            "property",
            "--match",
            "exact",
            "--limit",
            "1",
            "--page-size",
            "1",
            "--cursor",
            first_payload["next_cursor"],
            "--minimum-interval",
            "0.1",
        ),
        log_results=False,
    )
    assert isinstance(second, PublicRecordsResult)
    second_payload = second.to_dict()
    assert second_payload["status"] == "ok", second_payload
    first_record = first_payload["records"][0]
    second_record = second_payload["records"][0]
    assert first_record["native_identity"]["propertyid"] == "R73753"
    assert second_record["native_identity"]["propertyid"] == "R73753"
    assert (
        first_record["native_identity"]["ogc_fid"]
        < second_record["native_identity"]["ogc_fid"]
    )
    assert first_record["canonical_ref"] != second_record["canonical_ref"]
