from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_santa_fe_property as santa_fe
from tools.public_records_contract import ResultStatus
from tools.public_records_http import PaginatedFetch, TransportError


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/santa_fe_property"
)


def fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


def args(
    command: str = "owner",
    query: str | None = "SANTA FE COUNTY",
    **overrides,
) -> Namespace:
    values = {
        "command": command,
        "query": query,
        "limit": None,
        "cursor": None,
        "active_only": False,
        "geometry": False,
        "page_size": 2_000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def fetch(records, **overrides) -> PaginatedFetch:
    values = {
        "records": records,
        "next_cursor": None,
        "schema": {"kind": "test"},
        "schema_fingerprint": "response-schema",
        "pages_fetched": 1,
        "requests_made": 1,
    }
    values.update(overrides)
    return PaginatedFetch(**values)


class FakeClient:
    def __init__(
        self,
        records=None,
        *,
        metadata=None,
        error=None,
        fetch_overrides=None,
    ):
        self.metadata_value = metadata or fixture("layer_metadata.json")
        self.records = (
            records
            if records is not None
            else fixture("county_parcel.json")["features"]
        )
        self.error = error
        self.fetch_overrides = fetch_overrides or {}
        self.calls = []
        self.metadata_calls = 0
        self.page_size = 2_000

    def metadata(self):
        self.metadata_calls += 1
        if self.error:
            raise self.error
        return self.metadata_value

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return fetch(self.records, **self.fetch_overrides)


@pytest.fixture(autouse=True)
def disable_search_log(monkeypatch):
    monkeypatch.setattr(
        santa_fe,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_owner_query_normalizes_assessor_and_join_observations():
    client = FakeClient()

    result = santa_fe.execute(args(geometry=True), client=client)

    assert result.status == ResultStatus.OK
    assert client.metadata_calls == 1
    assert client.calls[0]["where"] == (
        "UPPER(owner_name) LIKE '%SANTA FE COUNTY%'"
    )
    assert client.calls[0]["requested_limit"] is None
    assert client.calls[0]["parameters"] == {
        "orderByFields": "OBJECTID",
        "outSR": 4326,
    }
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-nm-santa-fe-assessor-accounts/35049/"
        "parcel/1037057082517000000"
    )
    assert record["same_record_key"] == (
        "US-NM-SANTA-FE:PARCEL:1037057082517000000"
    )
    assert record["identity"] == {
        "basis": "upc",
        "tier": "durable_parcel_account",
        "durable_parcel_identity": True,
        "projection_eligible_as_parcel": True,
    }
    assert record["native_parcel_id"] == "1037057082517000000"
    assert record["native_feature_id"] == "249"
    assert record["owners"][0] == {
        "raw_name": "SANTA FE COUNTY",
        "role": "assessor_owner",
        "assertion_type": "assessment_account_observation",
    }
    assert record["situs_address"]["raw"] == (
        "18 DINKLE RD, EDGEWOOD, NM, 87015, UNITED STATES"
    )
    assert record["mailing_address"]["line1"] == "PO BOX 276"
    assert record["effective_from"] == "1980-01-01"
    assert record["assessment"]["current"]["source_fields"][
        "assessed_land"
    ] == 21250.0
    assert record["assessment"]["prior"]["source_fields"][
        "assessed_improvement"
    ] == 480000.0
    assert record["legal"]["acreage"] == 1
    assert record["recorder_index_hints"]["book_page_refs"] == (
        {"book": "175", "page": "10"},
        {"book": "173", "page": "37"},
    )
    assert record["recorder_index_hints"]["assessor_deed_note"] == {
        "raw": "2064666 REC 8/8/2025",
        "instrument_number": "2064666",
        "recording_date": "2025-08-08",
    }
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["response_schema_fingerprint"] == "response-schema"
    assert record["layer_schema_fingerprint"]


def test_objectid_only_row_is_a_feature_occurrence_not_a_parcel():
    feature = fixture("geometry_occurrence.json")["features"][0]

    record = santa_fe.normalize_feature(
        feature,
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint="layer-schema",
    )

    assert record["canonical_ref"] == (
        "PROPERTY:us-nm-santa-fe-assessor-accounts/35049/"
        "feature_occurrence/1"
    )
    assert record["same_record_key"] == "US-NM-SANTA-FE:FEATURE:1"
    assert record["record_kind"] == (
        "parcel_geometry_feature_occurrence"
    )
    assert record["identity"] == {
        "basis": "objectid",
        "tier": "layer_feature_occurrence",
        "durable_parcel_identity": False,
        "projection_eligible_as_parcel": False,
    }
    assert record["native_parcel_id"] is None
    assert record["native_feature_id"] == "1"
    assert record["same_authority_representations"] == []


def test_omitted_limit_has_no_adapter_record_ceiling():
    client = FakeClient()

    result = santa_fe.execute(
        args(limit=None, max_records=None),
        client=client,
    )

    assert result.query.query.requested_limit is None
    assert result.query.query.parameters["max_records"] is None
    assert client.calls[0]["requested_limit"] is None


def test_caller_window_preserves_continuation_and_partial_status():
    client = FakeClient(
        fetch_overrides={
            "next_cursor": "arcgis:25",
            "truncated_by_cap": True,
        }
    )

    result = santa_fe.execute(
        args(limit=25, cursor="arcgis:0"),
        client=client,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.next_cursor == "arcgis:25"
    assert client.calls[0]["requested_limit"] == 25
    assert client.calls[0]["cursor"] == "arcgis:0"


def test_query_modes_use_verified_fields_and_escape_literals():
    assert santa_fe._where("owner", "O'Neil") == (
        "UPPER(owner_name) LIKE '%O''NEIL%'"
    )
    assert santa_fe._where("address", "18 Dinkle Rd") == (
        "(UPPER(situs_line_1) LIKE '%18 DINKLE RD%' OR "
        "UPPER(situs_line_2) LIKE '%18 DINKLE RD%' OR "
        "UPPER(situs_line_3) LIKE '%18 DINKLE RD%')"
    )
    assert santa_fe._where("mailing", "PO Box 276") == (
        "(UPPER(owner_line_1) LIKE '%PO BOX 276%' OR "
        "UPPER(owner_line_2) LIKE '%PO BOX 276%' OR "
        "UPPER(owner_line_3) LIKE '%PO BOX 276%')"
    )
    assert santa_fe._where("parcel", "910002704") == (
        "UPC='910002704' OR parcel_number='910002704' "
        "OR alt_id='910002704'"
    )
    assert santa_fe._where("objectid", "000249") == "OBJECTID=249"
    assert santa_fe._where(
        "parcel",
        "910002704",
        active_only=True,
    ) == (
        "(UPC='910002704' OR parcel_number='910002704' "
        "OR alt_id='910002704') AND active_status='A'"
    )
    with pytest.raises(ValueError, match="numeric"):
        santa_fe._where("objectid", "not-a-number")


def test_probe_exhausts_the_exact_county_owned_sentinel():
    client = FakeClient()

    result = santa_fe.execute(
        args(command="probe", query=None, limit=900),
        client=client,
    )

    assert result.status == ResultStatus.OK
    assert result.query.query.requested_limit is None
    assert client.calls[0]["where"] == (
        f"UPC='{santa_fe.PROBE_UPC}'"
    )
    assert client.calls[0]["requested_limit"] is None


def test_probe_detects_sentinel_drift():
    record = fixture("county_parcel.json")["features"][0]
    record["attributes"]["parcel_number"] = "changed"

    result = santa_fe.execute(
        args(command="probe", query=None),
        client=FakeClient(records=[record]),
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


def test_probe_treats_assessment_owner_as_rolling_content():
    record = fixture("county_parcel.json")["features"][0]
    record["attributes"]["owner_name"] = "A NEW ASSESSMENT OWNER"

    result = santa_fe.execute(
        args(command="probe", query=None),
        client=FakeClient(records=[record]),
    )

    assert result.status == ResultStatus.OK
    assert [
        owner["raw_name"] for owner in result.records[0]["owners"]
    ] == ["A NEW ASSESSMENT OWNER"]


def test_metadata_validation_requires_identity_fields_and_pagination():
    metadata = fixture("layer_metadata.json")
    validated = santa_fe.validate_layer_metadata(metadata)

    assert validated["native_page_size"] == 2_000
    assert validated["schema_fingerprint"]

    missing = fixture("layer_metadata.json")
    missing["fields"] = [
        field
        for field in missing["fields"]
        if field["name"] != "owner_name"
    ]
    with pytest.raises(
        santa_fe.SourceSchemaError,
        match="missing required fields",
    ):
        santa_fe.validate_layer_metadata(missing)

    no_paging = fixture("layer_metadata.json")
    no_paging["advancedQueryCapabilities"]["supportsPagination"] = False
    with pytest.raises(
        santa_fe.SourceSchemaError,
        match="pagination contract",
    ):
        santa_fe.validate_layer_metadata(no_paging)


def test_source_map_classifies_representations_and_independent_records():
    routes = {
        route["route_id"]: route
        for route in santa_fe.route_map()["routes"]
    }

    assert routes[
        "us-nm-santa-fe-assessor-parcel-download"
    ]["relationship_to_primary"] == "same_record_snapshot"
    assert not routes[
        "us-nm-santa-fe-assessor-notices"
    ]["independent_evidence"]
    assert routes[
        "us-nm-santa-fe-clerktrack-index"
    ]["relationship_to_primary"] == "independent_recorded_instrument"
    assert routes[
        "us-nm-santa-fe-treasurer-paydici"
    ]["relationship_to_primary"] == "distinct_tax_record"


def test_transport_failure_is_not_an_empty_result():
    error = TransportError("offline", url=santa_fe.LAYER_URL)

    result = santa_fe.execute(
        args(),
        client=FakeClient(error=error),
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_search_log_failure_does_not_replace_source_result(
    monkeypatch,
    capsys,
):
    def fail_log(*_args, **_kwargs):
        raise RuntimeError("tracker unavailable")

    monkeypatch.setattr(santa_fe, "log_search", fail_log)

    result = santa_fe.execute(args(), client=FakeClient())

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    assert "search log was not updated" in capsys.readouterr().err


def test_parser_has_no_implicit_result_limit():
    parsed = santa_fe.build_parser().parse_args(
        ["owner", "SANTA FE COUNTY"]
    )

    assert parsed.limit is None
    assert parsed.max_records is None
    assert parsed.page_size == 2_000
