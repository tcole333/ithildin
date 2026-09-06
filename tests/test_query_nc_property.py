import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_nc_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


@pytest.fixture(autouse=True)
def _reviewed_access_contract(monkeypatch):
    monkeypatch.setattr(
        query_nc_property,
        "_access_contract",
        lambda args: {
            "allowed": True,
            "limits": {
                "maximum_page_size": 5000,
                "minimum_interval_seconds": 0.25,
            },
        },
    )


def _args(command="owner", query="SMITH", **overrides):
    values = {
        "command": command,
        "query": query,
        "county_fips": "005",
        "limit": 2,
        "cursor": None,
        "geometry": False,
        "page_size": 1000,
        "max_records": 5000,
        "timeout": 30.0,
        "minimum_interval": 0,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _feature(**attributes):
    base = {
        "objectid": 6061042,
        "parno": "3013467134",
        "ownname": "SMITH, THOMAS &",
        "ownname2": None,
        "siteadd": "ROUND HOUSE RD",
        "stfips": "37",
        "cntyfips": "005",
        "stcntyfips": "37005",
        "cntyname": "Alleghany",
        "parval": 1900.0,
        "saledate": 1_735_689_600_000,
    }
    base.update(attributes)
    return {"attributes": base}


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


def test_client_uses_caller_and_catalog_page_sizes_without_hidden_ceiling():
    client = query_nc_property._client(
        _args(page_size=7000, max_records=None),
        {
            "allowed": True,
            "limits": {
                "maximum_page_size": 8000,
                "minimum_interval_seconds": 0,
            },
        },
    )

    assert client.page_size == 7000
    assert client.max_records is None


def test_owner_query_is_county_scoped_and_normalized(monkeypatch):
    client = FakeClient(
        PaginatedFetch(
            records=[_feature()],
            next_cursor=None,
            schema={"kind": "test"},
            schema_fingerprint="schema123",
            pages_fetched=1,
            requests_made=1,
        )
    )
    logged = []
    monkeypatch.setattr(query_nc_property, "_client", lambda args, access: client)
    monkeypatch.setattr(
        query_nc_property, "log_search", lambda *args: logged.append(args)
    )

    result = query_nc_property.execute(_args())

    assert result.status.value == "ok"
    assert result.query.jurisdiction.jurisdiction_id == "37005"
    assert result.query.fingerprint
    assert client.calls[0]["where"] == (
        "(UPPER(ownname) LIKE '%SMITH%' OR UPPER(ownname2) LIKE '%SMITH%') "
        "AND stcntyfips='37005'"
    )
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-nc-onemap-parcels/37005/parcel/3013467134"
    )
    assert record["owners"][0]["assertion_type"] == "assessment_roll"
    assert record["owners"][0]["confidence"] == "high"
    assert record["last_sale"]["sale_date"] == "2025-01-01"
    assert record["schema_fingerprint"] == "schema123"
    assert logged[0][1:] == (query_nc_property.SOURCE_ID, 1)
    assert json.loads(logged[0][0])["fingerprint"] == result.query.fingerprint


def test_source_failure_is_never_logged_as_zero(monkeypatch):
    client = FakeClient(
        error=TransportError(
            "network unavailable",
            url=query_nc_property.LAYER_URL,
        )
    )
    logged = []
    monkeypatch.setattr(query_nc_property, "_client", lambda args, access: client)
    monkeypatch.setattr(
        query_nc_property, "log_search", lambda *args: logged.append(args)
    )

    result = query_nc_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert result.errors[0].code == "transport_error"
    assert logged[0][2] is None


def test_no_results_is_authoritative_zero(monkeypatch):
    client = FakeClient(
        PaginatedFetch(
            records=[],
            next_cursor=None,
            schema={"kind": "test"},
            schema_fingerprint="schema123",
            pages_fetched=1,
            requests_made=1,
        )
    )
    logged = []
    monkeypatch.setattr(query_nc_property, "_client", lambda args, access: client)
    monkeypatch.setattr(
        query_nc_property, "log_search", lambda *args: logged.append(args)
    )

    result = query_nc_property.execute(_args(query="NO SUCH OWNER"))

    assert result.status.value == "no_results"
    assert logged[0][2] == 0


def test_unavailable_catalog_route_is_not_queried_or_reported_as_zero(monkeypatch):
    decision = {
        "source_id": query_nc_property.SOURCE_ID,
        "allowed": False,
        "reason": "no reviewed access decision exists",
        "reason_code": "access_review_required",
    }
    monkeypatch.setattr(
        query_nc_property,
        "_access_contract",
        lambda args: (_ for _ in ()).throw(AcquisitionUnavailableError(decision)),
    )
    monkeypatch.setattr(
        query_nc_property,
        "_client",
        lambda *args: pytest.fail("network client was unexpectedly constructed"),
    )
    logged = []
    monkeypatch.setattr(
        query_nc_property, "log_search", lambda *args: logged.append(args)
    )

    result = query_nc_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"
    assert logged[0][2] is None


def test_partial_result_preserves_cursor_and_caveats(monkeypatch):
    client = FakeClient(
        PaginatedFetch(
            records=[_feature()],
            next_cursor="arcgis:offset:1",
            schema={"kind": "test"},
            schema_fingerprint="schema123",
            pages_fetched=1,
            requests_made=1,
            truncated_by_cap=True,
            warnings=("configured cap reached",),
        )
    )
    monkeypatch.setattr(query_nc_property, "_client", lambda args, access: client)
    monkeypatch.setattr(query_nc_property, "log_search", lambda *args: None)

    result = query_nc_property.execute(_args(limit=1))

    assert result.status.value == "partial"
    assert result.next_cursor == "arcgis:offset:1"
    assert "configured cap reached" in result.warnings
    assert "not proof of legal title" in result.warnings[0]


def test_geometry_is_opt_in(monkeypatch):
    client = FakeClient(
        PaginatedFetch(
            records=[{**_feature(), "geometry": {"x": 1, "y": 2}}],
            next_cursor=None,
            schema={"kind": "test"},
            schema_fingerprint="schema123",
            pages_fetched=1,
            requests_made=1,
        )
    )
    monkeypatch.setattr(query_nc_property, "_client", lambda args, access: client)
    monkeypatch.setattr(query_nc_property, "log_search", lambda *args: None)

    result = query_nc_property.execute(_args(geometry=True))

    assert result.records[0]["geometry"] == {"x": 1, "y": 2}
    assert client.calls[0]["return_geometry"] is True


def test_sql_literals_escape_quotes_and_validate_county():
    assert query_nc_property._sql_literal("O'NEIL") == "O''NEIL"
    assert query_nc_property._county_geoid("037") == "37037"
    assert query_nc_property._arcgis_date(None, "02-08-2024") == "2024-02-08"


def test_direct_cli_import_path_supports_repository_tool_pattern():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/query_nc_property.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "North Carolina OneMap" in result.stdout
