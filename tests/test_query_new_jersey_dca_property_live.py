from __future__ import annotations

import os

import pytest

from tools import query_new_jersey_dca_property as dca


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded NJ DCA probes",
)


def test_live_probe_returns_exact_building_and_property_registration():
    result = dca.execute(
        dca.build_parser().parse_args(
            ["probe", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["building_registration_number"] == (
        dca.PROBE_BUILDING_REGISTRATION
    )
    assert record["property_registration_number"] == (
        dca.PROBE_PROPERTY_REGISTRATION
    )
    assert record["property_interest_id"] == dca.PROBE_PROPERTY_INTEREST_ID
    assert record["parcel_coordinates"]["county"] == "ESSEX"
    assert record["parcel_coordinates"]["municipality"] == "NEWARK CITY"


def test_live_lookup_contract_keeps_statewide_counties_and_municipalities():
    result = dca.execute(
        dca.build_parser().parse_args(
            ["lookups", "--minimum-interval", "0"]
        ),
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["county_count"] == 21
    assert record["municipality_count"] >= 560
    assert any(
        municipality["name"] == "NEWARK CITY"
        and municipality["county_id"]
        == "fef3aaf2-63e4-e711-8125-1458d054d020"
        for municipality in record["municipalities"]
    )
