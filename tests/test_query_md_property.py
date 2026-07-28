import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_md_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


@pytest.fixture(autouse=True)
def _reviewed_access_contract(monkeypatch):
    monkeypatch.setattr(
        query_md_property,
        "_access_contract",
        lambda args: {
            "allowed": True,
            "limits": {
                "maximum_page_size": 50_000,
                "preserve_owner_visibility_state": "withheld_by_source",
            },
        },
    )


def _args(command="address", query="7 TRAYMORE RD", **overrides):
    values = {
        "command": command,
        "query": query,
        "county_code": "04",
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
    fields = query_md_property.FIELDS
    row = {
        fields["jurisdiction_code"]: "BACO",
        fields["county_name"]: "Baltimore County",
        fields["account_id"]: "04030311078580",
        fields["property_link"]: {
            "url": "https://sdat.dat.maryland.gov/RealProperty/example"
        },
        fields["finder_link"]: {
            "url": "https://apps.planning.maryland.gov/finderonline/example"
        },
        fields["longitude"]: "-76.7068417664",
        fields["latitude"]: "39.3733046671",
        fields["county_code"]: "04",
        fields["district"]: "03",
        fields["account_number"]: "0311078580",
        fields["owner_occupancy"]: "N",
        fields["address"]: "7 TRAYMORE RD ",
        fields["city"]: "PIKESVILLE",
        fields["postal_code"]: "21208",
        fields["legal_1"]: "0.2191 AC",
        fields["legal_2"]: "7 TRAYMORE RD",
        fields["legal_3"]: "MARLBOROUGH ESTATES",
        fields["deed_liber"]: "48094",
        fields["deed_folio"]: "0187",
        fields["base_land"]: "97100",
        fields["base_improvements"]: "0",
        fields["current_land"]: "97100",
        fields["current_improvements"]: "0",
        fields["current_total"]: "97100",
        fields["assessment_cycle_year"]: "2025",
        fields["source_updated"]: "20250703",
        (
            "sales_segment_1_grantor_name_mdp_field_grntnam1_sdat_field_80"
        ): "BALTIMORE HEBREW CONGREGATION",
        (
            "sales_segment_1_transfer_number_mdp_field_transno1_sdat_field_79"
        ): "000001",
        (
            "sales_segment_1_transfer_date_yyyy_mm_dd_mdp_field_tradate_sdat_field_89"
        ): "2023.05.31",
        (
            "sales_segment_1_consideration_mdp_field_considr1_sdat_field_90"
        ): "175000",
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
        "schema_fingerprint": "md-schema",
        "pages_fetched": 1,
        "requests_made": 1,
    }
    values.update(overrides)
    return PaginatedFetch(**values)


def test_address_query_preserves_withheld_owner_state(monkeypatch):
    client = FakeClient(_fetch([_row()], next_cursor="socrata:offset:1"))
    logged = []
    monkeypatch.setattr(query_md_property, "_client", lambda args, access: client)
    monkeypatch.setattr(
        query_md_property, "log_search", lambda *args: logged.append(args)
    )

    result = query_md_property.execute(_args())

    assert result.status.value == "ok"
    parameters, call = client.calls[0]
    assert parameters["$where"] == (
        "(UPPER(mdp_street_address_mdp_field_address) LIKE '%7 TRAYMORE RD%' "
        "OR UPPER(legal_description_line_2_mdp_field_legal2_sdat_field_18) "
        "LIKE '%7 TRAYMORE RD%') AND "
        "record_key_county_code_sdat_field_1='04'"
    )
    assert call["requested_limit"] == 2
    assert result.next_cursor == "socrata:offset:1"
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-md-sdat-property-hidden/24005/"
        "parcel/04030311078580"
    )
    assert record["owners"] == ()
    assert record["owner_visibility"] == {
        "state": "withheld_by_source",
        "dataset_name": query_md_property.DATASET_NAME,
        "current_owner_name_field_present": False,
    }
    assert record["situs_address"]["raw"] == "7 TRAYMORE RD"
    assert record["assessment"]["current_total_assessment"] == 97100
    assert record["source_record_updated"] == "2025-07-03"
    assert record["sales_history"][0]["party"] == {
        "raw_name": "BALTIMORE HEBREW CONGREGATION",
        "role": "historical_grantor",
    }
    assert all(
        owner.get("raw_name") != "BALTIMORE HEBREW CONGREGATION"
        for owner in record["owners"]
    )
    assert record["response_schema_fingerprint"] == "md-schema"
    assert logged[0][1:] == (query_md_property.SOURCE_ID, 1)
    assert json.loads(logged[0][0])["fingerprint"] == result.query.fingerprint


def test_parcel_query_and_county_mapping(monkeypatch):
    client = FakeClient(_fetch([_row()]))
    monkeypatch.setattr(query_md_property, "_client", lambda args, access: client)
    monkeypatch.setattr(query_md_property, "log_search", lambda *args: None)

    result = query_md_property.execute(
        _args(command="parcel", query="04-03-0311078580")
    )

    where = client.calls[0][0]["$where"]
    assert (
        "account_id_mdp_field_acctid='04030311078580'" in where
    )
    assert (
        "record_key_account_number_sdat_field_3='04030311078580'" in where
    )
    assert result.query.jurisdiction.jurisdiction_id == "24005"
    assert result.records[0]["jurisdiction"]["county_geoid"] == "24005"
    assert query_md_property._county_code("3") == "03"


def test_probe_uses_one_row_and_no_owner_capability(monkeypatch):
    client = FakeClient(_fetch([_row()]))
    monkeypatch.setattr(query_md_property, "_client", lambda args, access: client)
    monkeypatch.setattr(query_md_property, "log_search", lambda *args: None)

    result = query_md_property.execute(
        _args(command="probe", query=None, county_code=None, limit=500)
    )

    assert result.status.value == "ok"
    assert client.calls[0][1]["requested_limit"] == 1
    assert client.calls[0][0]["$where"] == "1=1"
    parser = query_md_property.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["owner", "EXAMPLE"])


def test_true_zero_and_transport_failure_remain_distinct(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_md_property, "log_search", lambda *args: logged.append(args)
    )
    monkeypatch.setattr(
        query_md_property,
        "_client",
        lambda args, access: FakeClient(_fetch([])),
    )
    empty = query_md_property.execute(_args())
    assert empty.status.value == "no_results"
    assert logged[-1][2] == 0

    monkeypatch.setattr(
        query_md_property,
        "_client",
        lambda args, access: FakeClient(
            error=TransportError(
                "network unavailable",
                url=f"{query_md_property.BASE_URL}/{query_md_property.DATASET_ID}.json",
            )
        ),
    )
    failure = query_md_property.execute(_args())
    assert failure.status.value == "unavailable"
    assert failure.errors[0].code == "transport_error"
    assert logged[-1][2] is None


def test_client_uses_explicit_requested_limit_without_hidden_ceiling():
    client = query_md_property._client(
        _args(limit=12_345, page_size=2_000),
        {
            "limits": {
                "maximum_page_size": 50_000,
            },
        },
    )

    assert client.max_records == 12_345
    assert client.page_size == 2_000
    client.transport.close()


def test_access_denial_prevents_network(monkeypatch):
    decision = {
        "source_id": query_md_property.SOURCE_ID,
        "allowed": False,
        "reason_code": "access_review_required",
        "reason": "review missing",
    }
    monkeypatch.setattr(
        query_md_property,
        "_access_contract",
        lambda args: (_ for _ in ()).throw(AcquisitionUnavailableError(decision)),
    )
    monkeypatch.setattr(
        query_md_property,
        "_client",
        lambda *args: pytest.fail("network was unexpectedly called"),
    )
    monkeypatch.setattr(query_md_property, "log_search", lambda *args: None)

    result = query_md_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"


def test_direct_script_import_path_support():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project_root / "tools/query_md_property.py"), "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Maryland statewide real-property assessments" in result.stdout
