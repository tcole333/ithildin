from __future__ import annotations

import os

import pytest

from tools.query_va_general_district import VAGeneralDistrictClient


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 to exercise the official live source",
)


def test_live_court_component_list() -> None:
    client = VAGeneralDistrictClient(minimum_interval=0.5)
    try:
        records = client.courts()
    finally:
        client.close()
    assert len(records) >= 130
    by_code = {record["court_source_code"]: record for record in records}
    assert by_code["013"]["court_name"] == ("Arlington General District Court")


def test_live_bounded_probe() -> None:
    client = VAGeneralDistrictClient(minimum_interval=0.5)
    try:
        record = client.probe("013")[0]
    finally:
        client.close()
    assert record["status"] == "ok"
    assert record["court_component_count"] >= 130
    assert len(record["selected_court_route_labels"]) >= 8
    assert record["civil_case_form_present"] is True
    assert record["traffic_criminal_case_form_present"] is True
    hearing_codes = {option["code"] for option in record["source_native_hearing_types"]}
    assert {"MO", "PR", "ST"}.issubset(hearing_codes)
