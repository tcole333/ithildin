from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_arlington_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


def _args(
    command: str = "parcel",
    query: str | None = "03-001-009",
    **overrides,
) -> Namespace:
    values = {
        "command": command,
        "query": query,
        "limit": None,
        "cursor": None,
        "geometry": False,
        "page_size": 2_000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "catalog_db": "unused.db",
        "catalog_config": "unused.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _feature(**overrides):
    attributes = {
        "OBJECTID": 1,
        "RPCMSTR": "03001009",
        "PARCEL_ID": "03001009",
        "LRSN": 4234,
        "ZONING": "R-20",
        "OWN_STREET": "3905 44TH ST N",
        "OWN_CITY": "MCLEAN",
        "OWN_STATE": "VA",
        "OWN_ZIP": "22101",
        "PROPERTY_CLASS_DESC": "510-Res - Vacant(SF & Twnhse)",
        "NEIGHBORHOOD": 503014,
        "MAP_PAGE": "002-15",
        "LOTSIZE": 30104,
        "LEGAL_DESC": "LT 2 B RESUB LT 2 THETFORD SUBD 30104 SQ FT      ",
        "CHANGE_REASON_TYPE": "01- Annual",
        "ASSESSMENT_DATE": 1_767_225_600_000,
        "IMPROVEMENT": 0,
        "LAND": 2_920_100,
        "TOTAL": 2_920_100,
        "GeoSyncDate": 1_785_303_189_000,
        "SHAPE.STArea()": 30023.807607959119,
        "SHAPE.STLength()": 1033.6441524580064,
        "tax_exemption_type_dsc": None,
    }
    attributes.update(overrides)
    return {"attributes": attributes}


def _fetch(records, **overrides) -> PaginatedFetch:
    values = {
        "records": records,
        "next_cursor": None,
        "schema": {"kind": "test"},
        "schema_fingerprint": "arlington-schema",
        "pages_fetched": 1,
        "requests_made": 1,
    }
    values.update(overrides)
    return PaginatedFetch(**values)


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        query_arlington_property,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_parcel_query_normalizes_rich_property_observation_and_gaps():
    client = FakeClient(_fetch([_feature()]))

    result = query_arlington_property.execute(
        _args(),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    assert result.query.jurisdiction.jurisdiction_id == "51013"
    assert client.calls[0]["where"] == (
        "RPCMSTR='03001009' OR PARCEL_ID='03001009'"
    )
    assert client.calls[0]["parameters"] == {
        "orderByFields": "OBJECTID"
    }
    assert client.calls[0]["requested_limit"] is None
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-va-arlington-property-map/51013/"
        "parcel/03001009"
    )
    assert record["rpc_number"] == "03001009"
    assert record["parcel_id"] == "03001009"
    assert record["legal_description_raw"] == (
        "LT 2 B RESUB LT 2 THETFORD SUBD 30104 SQ FT"
    )
    assert record["classification"] == {
        "property_class_description": "510-Res - Vacant(SF & Twnhse)",
        "zoning": "R-20",
        "neighborhood_code": 503014,
        "map_page": "002-15",
        "tax_exemption_type": None,
    }
    assert record["assessment"] == {
        "tax_year": "2026",
        "assessment_date": "2026-01-01",
        "change_reason": "01- Annual",
        "land_value": 2_920_100,
        "improvement_value": 0,
        "parcel_value": 2_920_100,
        "assessed_value": 2_920_100,
        "assessment_class": "510-Res - Vacant(SF & Twnhse)",
        "total_value": 2_920_100,
        "currency": "USD",
    }
    assert record["lot"]["lot_size_square_feet"] == 30104
    assert record["source_sync_datetime"].startswith(
        "2026-07-29T"
    )
    assert record["owners"] == ()
    assert record["owner_visibility"]["state"] == (
        "not_exposed_by_source_layer"
    )
    assert record["sales_history"] == ()
    assert record["sales_visibility"]["state"] == (
        "not_exposed_by_source_layer"
    )
    assert record["situs_address"] is None
    assert "no owner name" in result.warnings[0]


def test_query_modes_use_verified_fields_and_normalize_rpc():
    assert query_arlington_property._where(
        "parcel", "03-001-009"
    ) == (
        "RPCMSTR='03001009' OR PARCEL_ID='03001009'"
    )
    assert query_arlington_property._where(
        "rpc", "03 001 009"
    ) == "RPCMSTR='03001009'"
    assert query_arlington_property._where(
        "address", "3905 44th St N"
    ) == "UPPER(OWN_STREET) LIKE '%3905 44TH ST N%'"
    assert query_arlington_property._where(
        "address", "3905 44th St N, McLean, VA 22101"
    ) == (
        "UPPER(OWN_STREET) LIKE '%3905 44TH ST N%' "
        "AND UPPER(OWN_CITY) LIKE '%MCLEAN%' "
        "AND UPPER(OWN_STATE)='VA' "
        "AND OWN_ZIP LIKE '22101%'"
    )
    assert query_arlington_property._where(
        "objectid", "0001"
    ) == "OBJECTID=1"
    with pytest.raises(ValueError, match="eight digits"):
        query_arlington_property._where("parcel", "123")
    with pytest.raises(ValueError, match="numeric"):
        query_arlington_property._where("objectid", "not-a-number")


def test_probe_uses_stable_rpc_sentinel_and_one_record():
    client = FakeClient(_fetch([_feature()]))

    result = query_arlington_property.execute(
        _args(command="probe", query=None, limit=None),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    assert client.calls[0]["where"] == (
        f"RPCMSTR='{query_arlington_property.PROBE_RPC_NUMBER}'"
    )
    assert client.calls[0]["requested_limit"] == 2
    assert result.query.query.requested_limit == 1


def test_probe_treats_missing_or_nonunique_sentinel_as_source_change():
    missing = query_arlington_property.execute(
        _args(command="probe", query=None),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([])),
    )
    duplicate = query_arlington_property.execute(
        _args(command="probe", query=None),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([_feature(), _feature(OBJECTID=2)])),
    )

    assert missing.status.value == "source_changed"
    assert duplicate.status.value == "source_changed"
    assert "expected exactly one" in missing.errors[0].message


def test_client_uses_native_page_size_without_hidden_record_cap():
    client = query_arlington_property._client(
        _args(page_size=50_000, max_records=None),
        {
            "allowed": True,
            "limits": {
                "maximum_page_size": 10_000,
                "minimum_interval_seconds": 0,
            },
        },
    )

    assert client.page_size == 2_000
    assert client.max_records is None


def test_caller_limit_and_max_records_are_passed_without_adapter_cap():
    unlimited_client = FakeClient(_fetch([_feature()]))
    unlimited = query_arlington_property.execute(
        _args(limit=None, max_records=None),
        access_decision={"allowed": True},
        client=unlimited_client,
    )

    assert unlimited.status.value == "ok"
    assert unlimited_client.calls[0]["requested_limit"] is None

    capped_client = FakeClient(
        _fetch(
            [_feature()],
            next_cursor="arcgis:offset:1",
            truncated_by_cap=True,
            warnings=("configured cap reached",),
        )
    )
    capped = query_arlington_property.execute(
        _args(limit=10, max_records=1),
        access_decision={"allowed": True},
        client=capped_client,
    )

    assert capped.status.value == "partial"
    assert capped.next_cursor == "arcgis:offset:1"
    assert "configured cap reached" in capped.warnings


def test_geometry_is_opt_in_and_identifies_source_crs():
    feature = {
        **_feature(),
        "geometry": {
            "rings": [
                [
                    [-8580000.0, 4700000.0],
                    [-8579999.0, 4700000.0],
                    [-8580000.0, 4700000.0],
                ]
            ]
        },
    }
    client = FakeClient(_fetch([feature]))

    result = query_arlington_property.execute(
        _args(geometry=True),
        access_decision={"allowed": True},
        client=client,
    )

    assert client.calls[0]["return_geometry"] is True
    record = result.records[0]
    assert result.to_dict()["records"][0]["geometry"] == feature["geometry"]
    assert record["geometry_format"] == "esri_json"
    assert record["geometry_crs"] == "EPSG:3857"


def test_authoritative_empty_and_transport_failure_are_distinct(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_arlington_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    empty = query_arlington_property.execute(
        _args(query="99-999-999"),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([])),
    )
    assert empty.status.value == "no_results"
    assert logged[-1][2] == 0

    unavailable = query_arlington_property.execute(
        _args(),
        access_decision={"allowed": True},
        client=FakeClient(
            error=TransportError(
                "network unavailable",
                url=query_arlington_property.LAYER_URL,
            )
        ),
    )
    assert unavailable.status.value == "unavailable"
    assert unavailable.errors[0].code == "transport_error"
    assert logged[-1][2] is None


def test_unavailable_access_decision_prevents_client_construction(monkeypatch):
    decision = {
        "source_id": query_arlington_property.SOURCE_ID,
        "allowed": False,
        "reason": "review missing",
        "reason_code": "access_review_required",
    }
    monkeypatch.setattr(
        query_arlington_property,
        "_access_contract",
        lambda args: (_ for _ in ()).throw(
            AcquisitionUnavailableError(decision)
        ),
    )
    monkeypatch.setattr(
        query_arlington_property,
        "_client",
        lambda *args: pytest.fail("network client was unexpectedly built"),
    )

    result = query_arlington_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"


def test_search_log_uses_query_fingerprint(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_arlington_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_arlington_property.execute(
        _args(),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([_feature()])),
    )

    logged_query = json.loads(logged[0][0])
    assert logged_query["fingerprint"] == result.query.fingerprint
    assert logged[0][1:] == (query_arlington_property.SOURCE_ID, 1)


def test_direct_script_help_and_cli_surface():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "tools/query_arlington_property.py"),
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Arlington County" in result.stdout
    parser = query_arlington_property.build_parser()
    parsed = parser.parse_args(
        [
            "rpc",
            "03-001-009",
            "--geometry",
            "--limit",
            "2500",
        ]
    )
    assert parsed.command == "rpc"
    assert parsed.geometry is True
    assert parsed.limit == 2500
    assert "owner" not in parser._subparsers._group_actions[0].choices
