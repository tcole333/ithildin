import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_cook_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


@pytest.fixture(autouse=True)
def _reviewed_access_contract(monkeypatch):
    monkeypatch.setattr(
        query_cook_property,
        "_access_contract",
        lambda args: {
            "allowed": True,
            "limits": {
                "maximum_page_size": 50_000,
                "require_complete_pagination": True,
            },
        },
    )


def _args(command="parcel", query="01-01-106-009-1001", **overrides):
    values = {
        "command": command,
        "query": query,
        "tax_year": None,
        "limit": 2,
        "cursor": None,
        "page_size": 1000,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _row(**overrides):
    row = {
        "pin": "01011060091001",
        "pin10": "0101106009",
        "year": "2026.0",
        "class": "599",
        "triad_name": "North",
        "triad_code": "2",
        "township_name": "Barrington",
        "township_code": "10",
        "nbhd_code": "10012",
        "tax_code": "10148",
        "zip_code": "60010",
        "lon": "-88.1331071142",
        "lat": "42.1526952977",
        "row_id": "010110600910012026",
    }
    row.update(overrides)
    return row


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def query(self, parameters, **kwargs):
        self.calls.append((parameters, kwargs))
        if self.error:
            raise self.error
        return self.result


def _fetch(records, **overrides):
    values = {
        "records": records,
        "next_cursor": None,
        "schema": {"kind": "test"},
        "schema_fingerprint": "cook-schema",
        "pages_fetched": 1,
        "requests_made": 1,
    }
    values.update(overrides)
    return PaginatedFetch(**values)


def test_parcel_query_normalizes_historic_snapshot(monkeypatch):
    client = FakeClient(_fetch([_row()], next_cursor="socrata:offset:1"))
    logged = []
    monkeypatch.setattr(
        query_cook_property, "_client", lambda args, access: client
    )
    monkeypatch.setattr(
        query_cook_property, "log_search", lambda *args: logged.append(args)
    )

    result = query_cook_property.execute(_args(tax_year=2026))

    assert result.status.value == "ok"
    parameters, call = client.calls[0]
    assert parameters["$where"] == (
        "(pin='01011060091001') AND year=2026"
    )
    assert parameters["$order"] == "year DESC,row_id"
    assert call["requested_limit"] == 2
    assert result.next_cursor == "socrata:offset:1"
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-il-cook-parcel-universe/17031/"
        "parcel_snapshot/010110600910012026"
    )
    assert record["tax_year"] == "2026"
    assert record["owner_observation"]["state"] == (
        "not_present_in_dataset_schema"
    )
    assert record["owner_observation"]["names"] == ()
    assert record["situs_location"]["street_address_state"] == (
        "not_present_in_dataset_schema"
    )
    assert record["situs_location"]["centroid"]["longitude"] == pytest.approx(
        -88.1331071142
    )
    assert record["response_schema_fingerprint"] == "cook-schema"
    assert record["adapter_schema_fingerprint"] == (
        query_cook_property.ADAPTER_SCHEMA_FINGERPRINT
    )
    assert json.loads(logged[0][0])["fingerprint"] == result.query.fingerprint
    assert logged[0][1:] == (query_cook_property.SOURCE_ID, 1)


def test_ten_digit_pin_uses_pin10_and_probe_is_bounded(monkeypatch):
    assert query_cook_property._where("parcel", "101106009", None) == (
        "pin10='0101106009'"
    )
    client = FakeClient(_fetch([_row()]))
    monkeypatch.setattr(
        query_cook_property, "_client", lambda args, access: client
    )
    monkeypatch.setattr(query_cook_property, "log_search", lambda *args: None)
    result = query_cook_property.execute(
        _args(command="probe", query=None, limit=500)
    )
    assert result.status.value == "ok"
    assert client.calls[0][1]["requested_limit"] == 1
    assert client.calls[0][0]["$where"] == "1=1"


def test_true_zero_and_transport_failure_remain_distinct(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_cook_property, "log_search", lambda *args: logged.append(args)
    )
    monkeypatch.setattr(
        query_cook_property,
        "_client",
        lambda args, access: FakeClient(_fetch([])),
    )
    empty = query_cook_property.execute(_args())
    assert empty.status.value == "no_results"
    assert logged[-1][2] == 0

    monkeypatch.setattr(
        query_cook_property,
        "_client",
        lambda args, access: FakeClient(
            error=TransportError(
                "network unavailable",
                url=f"{query_cook_property.BASE_URL}/{query_cook_property.DATASET_ID}.json",
            )
        ),
    )
    failure = query_cook_property.execute(_args())
    assert failure.status.value == "unavailable"
    assert failure.errors[0].code == "transport_error"
    assert logged[-1][2] is None


def test_client_uses_explicit_requested_limit_without_hidden_ceiling():
    client = query_cook_property._client(
        _args(limit=12_345, page_size=2_000),
        {
            "limits": {
                "maximum_page_size": 50_000,
            },
        },
    )

    assert client.max_records == 12_345
    assert client.page_size == 2_000


def test_access_denial_prevents_network(monkeypatch):
    decision = {
        "source_id": query_cook_property.SOURCE_ID,
        "allowed": False,
        "reason_code": "access_review_required",
        "reason": "review missing",
    }
    monkeypatch.setattr(
        query_cook_property,
        "_access_contract",
        lambda args: (_ for _ in ()).throw(AcquisitionUnavailableError(decision)),
    )
    monkeypatch.setattr(
        query_cook_property,
        "_client",
        lambda *args: pytest.fail("network was unexpectedly called"),
    )
    monkeypatch.setattr(query_cook_property, "log_search", lambda *args: None)

    result = query_cook_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"


def test_direct_script_import_and_capability_surface():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project_root / "tools/query_cook_property.py"), "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Cook County Assessor Parcel Universe" in result.stdout
    parser = query_cook_property.build_parser()
    assert parser.parse_args(["parcel", "01011060091001"]).command == "parcel"
    with pytest.raises(SystemExit):
        parser.parse_args(["owner", "EXAMPLE"])
