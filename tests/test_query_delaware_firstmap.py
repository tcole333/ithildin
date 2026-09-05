import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from tools import query_delaware_firstmap
from tools.public_records_http import PaginatedFetch, TransportError


def _args(command="pin", **overrides):
    values = {
        "command": command,
        "pin": "1001300033",
        "term": None,
        "county": None,
        "objectid": None,
        "layer": query_delaware_firstmap.POLYGON_LAYER,
        "cursor": None,
        "geometry": False,
        "out_sr": 4326,
        "page_size": 2000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "max_attempts": 3,
        "catalog_db": "unused.db",
        "catalog_config": "unused.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _polygon(
    *,
    objectid=18356825,
    pin="1001300033",
    county="New Castle",
    geometry=None,
):
    feature = {
        "attributes": {
            "OBJECTID": objectid,
            "PIN": pin,
            "ACRES": 14.13674485,
            "COUNTY": county,
            "UPDATED": 1_784_073_600_000,
            "Shape__Area": 57_209.0,
            "Shape__Length": 1_100.0,
        }
    }
    if geometry is not None:
        feature["geometry"] = geometry
    return feature


def _centroid(
    *,
    objectid=95052,
    pin="1001300033",
    county="New Castle",
    geometry=None,
):
    feature = {
        "attributes": {
            "OBJECTID": objectid,
            "PIN": pin,
            "SUM_ACRES": 14.13674485,
            "ORIG_FID": None,
            "SENATE_DISTRICT": 13,
            "REPRESENTATIVE_DISTRICT": 17,
            "HUC_12": "020402050301",
            "SCHOOL_DISTRICT": "COLONIAL",
            "COUNTY": county,
            "TOWN": None,
            "EDRD": None,
            "CENSUSBLOCK": "100030150001028",
            "WASTEWATERCPCN": None,
            "WATERCPCN": None,
            "ERPA": None,
            "COMMUNITYNAME": None,
            "Z": 0,
            "X": 0,
            "Y": 0,
            "LONGITUDE": -75.61409778,
            "LATITUDE": 39.68600253,
            "LAST_UPDATED": 1_784_246_400_000,
            "ZIP_CODE": "19720",
        }
    }
    if geometry is not None:
        feature["geometry"] = geometry
    return feature


def _fetch(
    records=(),
    *,
    fingerprint="schema123",
    next_cursor=None,
    truncated=False,
    warnings=(),
):
    return PaginatedFetch(
        records=list(records),
        next_cursor=next_cursor,
        schema={"kind": "test"},
        schema_fingerprint=fingerprint,
        pages_fetched=1,
        requests_made=1,
        truncated_by_cap=truncated,
        warnings=warnings,
    )


class FakeClient:
    def __init__(self, *results, error=None):
        self.results = list(results)
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if not self.results:
            raise AssertionError("unexpected FirstMap client query")
        return self.results.pop(0)


def _client_map(polygon_client=None, centroid_client=None):
    return {
        query_delaware_firstmap.POLYGON_LAYER: polygon_client or FakeClient(),
        query_delaware_firstmap.CENTROID_LAYER: centroid_client or FakeClient(),
    }


def test_exact_pin_joins_polygon_and_centroid_by_county_and_pin(monkeypatch):
    polygon_client = FakeClient(_fetch([_polygon()], fingerprint="polygon-schema"))
    centroid_client = FakeClient(
        _fetch([_centroid()], fingerprint="centroid-schema")
    )
    logged = []
    monkeypatch.setattr(
        query_delaware_firstmap,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_delaware_firstmap.execute(
        _args(county="New Castle"),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, centroid_client),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-de-firstmap-parcels/10003/parcel/1001300033"
    )
    assert record["identity"] == {
        "basis": "county_and_pin",
        "county": "New Castle",
        "pin": "1001300033",
        "joinable": True,
    }
    assert len(record["polygon_features"]) == 1
    assert len(record["centroid_features"]) == 1
    assert record["centroid"]["zip_code"] == "19720"
    expected_where = "(PIN='1001300033') AND COUNTY='New Castle'"
    assert polygon_client.calls[0]["where"] == expected_where
    assert centroid_client.calls[0]["where"] == expected_where
    assert polygon_client.calls[0]["requested_limit"] is None
    assert logged[0][1:] == (query_delaware_firstmap.SOURCE_ID, 1)
    assert json.loads(logged[0][0])["fingerprint"] == result.query.fingerprint


def test_same_pin_in_different_counties_is_not_cross_joined():
    records = query_delaware_firstmap._normalize_features(
        {
            query_delaware_firstmap.POLYGON_LAYER: [
                _polygon(objectid=1, pin="SHARED", county="Kent")
            ],
            query_delaware_firstmap.CENTROID_LAYER: [
                _centroid(objectid=2, pin="SHARED", county="Sussex")
            ],
        },
        schema_fingerprints={
            query_delaware_firstmap.POLYGON_LAYER: "p",
            query_delaware_firstmap.CENTROID_LAYER: "c",
        },
        geometry_spatial_reference=4326,
    )

    assert len(records) == 2
    assert {record["jurisdiction"]["county_name"] for record in records} == {
        "Kent",
        "Sussex",
    }
    assert sorted(
        (
            len(record["polygon_features"]),
            len(record["centroid_features"]),
        )
        for record in records
    ) == [(0, 1), (1, 0)]


def test_duplicate_source_parts_are_preserved_under_one_parcel_identity():
    records = query_delaware_firstmap._normalize_features(
        {
            query_delaware_firstmap.POLYGON_LAYER: [
                _polygon(objectid=10, pin="P-1", county="Kent"),
                _polygon(objectid=11, pin="P-1", county="Kent"),
            ],
            query_delaware_firstmap.CENTROID_LAYER: [],
        },
        schema_fingerprints={
            query_delaware_firstmap.POLYGON_LAYER: "p",
        },
        geometry_spatial_reference=4326,
    )

    assert len(records) == 1
    assert [
        feature["object_id"] for feature in records[0]["polygon_features"]
    ] == [10, 11]


def test_blank_pin_feature_uses_explicit_objectid_fallback(monkeypatch):
    polygon_client = FakeClient(
        _fetch([_polygon(objectid=18522938, pin=" ", county="Kent")])
    )
    monkeypatch.setattr(query_delaware_firstmap, "log_search", lambda *args: None)

    result = query_delaware_firstmap.execute(
        _args(command="list", county="Kent"),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, FakeClient()),
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["native_parcel_id"] is None
    assert record["identity"]["basis"] == "source_object_id_fallback"
    assert record["identity"]["object_id"] == 18522938
    assert record["identity"]["joinable"] is False
    assert "parcel_feature" in record["canonical_ref"]
    assert "not asserted to be a canonical parcel identity" in (
        record["identity_caveat"]
    )
    assert query_delaware_firstmap.BLANK_PIN_CAVEAT in result.warnings


def test_county_search_uses_selected_layer_and_preserves_partial_cursor(
    monkeypatch,
):
    centroid_client = FakeClient(
        _fetch(
            [_centroid()],
            next_cursor="arcgis:offset:1",
            truncated=True,
            warnings=("caller ceiling reached",),
        )
    )
    monkeypatch.setattr(query_delaware_firstmap, "log_search", lambda *args: None)

    result = query_delaware_firstmap.execute(
        _args(
            command="search",
            term="013",
            county="new-castle",
            layer=query_delaware_firstmap.CENTROID_LAYER,
            cursor="arcgis:offset:0",
            max_records=1,
        ),
        access_decision={"allowed": True},
        clients=_client_map(FakeClient(), centroid_client),
    )

    assert result.status.value == "partial"
    assert result.next_cursor == "arcgis:offset:1"
    call = centroid_client.calls[0]
    assert call["where"] == "COUNTY='New Castle' AND PIN LIKE '%013%'"
    assert call["cursor"] == "arcgis:offset:0"
    assert "caller ceiling reached" in result.warnings


def test_objectid_joins_complement_by_source_key_not_objectid(monkeypatch):
    polygon_client = FakeClient(
        _fetch(
            [
                _polygon(
                    objectid=18507702,
                    pin="1-00-00100-01-0100-00001",
                    county="Kent",
                )
            ]
        )
    )
    centroid_client = FakeClient(
        _fetch(
            [
                _centroid(
                    objectid=12345,
                    pin="1-00-00100-01-0100-00001",
                    county="Kent",
                )
            ]
        )
    )
    monkeypatch.setattr(query_delaware_firstmap, "log_search", lambda *args: None)

    result = query_delaware_firstmap.execute(
        _args(command="objectid", objectid=18507702),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, centroid_client),
    )

    assert result.status.value == "ok"
    assert polygon_client.calls[0]["where"] == "OBJECTID=18507702"
    assert centroid_client.calls[0]["where"] == (
        "(PIN='1-00-00100-01-0100-00001') AND COUNTY='Kent'"
    )
    assert result.records[0]["source_feature_ids"] == (
        "centroid:OBJECTID:12345",
        "polygon:OBJECTID:18507702",
    )


def test_blank_pin_objectid_does_not_query_other_layer(monkeypatch):
    polygon_client = FakeClient(
        _fetch([_polygon(objectid=18522938, pin="", county="Kent")])
    )
    centroid_client = FakeClient()
    monkeypatch.setattr(query_delaware_firstmap, "log_search", lambda *args: None)

    result = query_delaware_firstmap.execute(
        _args(command="objectid", objectid=18522938),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, centroid_client),
    )

    assert result.status.value == "ok"
    assert centroid_client.calls == []
    assert result.records[0]["identity"]["basis"] == "source_object_id_fallback"


def test_geometry_is_opt_in_and_uses_caller_output_spatial_reference(monkeypatch):
    polygon_client = FakeClient(
        _fetch([_polygon(geometry={"rings": [[[1, 2], [3, 4]]]})])
    )
    centroid_client = FakeClient(
        _fetch([_centroid(geometry={"x": -75.6, "y": 39.6})])
    )
    monkeypatch.setattr(query_delaware_firstmap, "log_search", lambda *args: None)

    result = query_delaware_firstmap.execute(
        _args(geometry=True, out_sr=3857),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, centroid_client),
    )

    assert result.records[0]["polygon_features"][0]["geometry"]["rings"]
    assert (
        result.records[0]["centroid_features"][0][
            "geometry_spatial_reference"
        ]
        == 3857
    )
    for client in (polygon_client, centroid_client):
        assert client.calls[0]["return_geometry"] is True
        assert client.calls[0]["parameters"]["outSR"] == 3857


def test_probe_verifies_both_layers_and_schema_fields(monkeypatch):
    polygon_client = FakeClient(_fetch([_polygon()], fingerprint="polygon-schema"))
    centroid_client = FakeClient(
        _fetch([_centroid()], fingerprint="centroid-schema")
    )
    monkeypatch.setattr(query_delaware_firstmap, "log_search", lambda *args: None)

    result = query_delaware_firstmap.execute(
        _args(command="probe"),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, centroid_client),
    )

    assert result.status.value == "ok"
    assert result.records[0]["probe"] == {
        "sentinel": {
            "county": "New Castle",
            "pin": "1001300033",
        },
        "polygon_feature_count": 1,
        "centroid_feature_count": 1,
        "schema_fingerprints": {
            "polygon": "polygon-schema",
            "centroid": "centroid-schema",
        },
    }


def test_probe_reports_nonunique_sentinel_as_source_changed(monkeypatch):
    polygon_client = FakeClient(
        _fetch([_polygon(objectid=1), _polygon(objectid=2)])
    )
    centroid_client = FakeClient(_fetch([_centroid()]))
    logged = []
    monkeypatch.setattr(
        query_delaware_firstmap,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_delaware_firstmap.execute(
        _args(command="probe"),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, centroid_client),
    )

    assert result.status.value == "source_changed"
    assert "non-unique" in result.errors[0].message
    assert logged[0][2] is None


def test_no_hidden_adapter_cap_in_arcgis_clients():
    clients = query_delaware_firstmap._clients(
        _args(page_size=5000, max_records=None),
        {"allowed": True},
    )

    assert clients["polygon"].page_size == 5000
    assert clients["centroid"].page_size == 5000
    assert clients["polygon"].max_records is None
    assert clients["centroid"].max_records is None


def test_source_failure_is_not_logged_as_zero(monkeypatch):
    polygon_client = FakeClient(
        error=TransportError(
            "network unavailable",
            url=query_delaware_firstmap.POLYGON_LAYER_URL,
        )
    )
    logged = []
    monkeypatch.setattr(
        query_delaware_firstmap,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_delaware_firstmap.execute(
        _args(command="list", county="Kent"),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, FakeClient()),
    )

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert logged[0][2] is None


def test_no_results_is_authoritative_zero(monkeypatch):
    polygon_client = FakeClient(_fetch([]))
    logged = []
    monkeypatch.setattr(
        query_delaware_firstmap,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_delaware_firstmap.execute(
        _args(command="list", county="Sussex"),
        access_decision={"allowed": True},
        clients=_client_map(polygon_client, FakeClient()),
    )

    assert result.status.value == "no_results"
    assert logged[0][2] == 0


def test_sql_literals_escape_quotes_and_county_aliases_are_normalized():
    assert query_delaware_firstmap._sql_literal("O'NEIL", "PIN") == "O''NEIL"
    assert query_delaware_firstmap._county("new-castle") == "New Castle"
    assert query_delaware_firstmap._county("NEW CASTLE") == "New Castle"


def test_direct_cli_import_path_supports_repository_tool_pattern():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/query_delaware_firstmap.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Delaware FirstMap" in result.stdout
