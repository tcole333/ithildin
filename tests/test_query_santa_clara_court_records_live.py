from __future__ import annotations

import os

import pytest

from tools import query_santa_clara_court_records as santa_clara
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_SANTA_CLARA_COURT") != "1",
    reason="set RUN_LIVE_SANTA_CLARA_COURT=1 for official live probes",
)


def parse_args(*values: str):
    return santa_clara.build_parser().parse_args(list(values))


def test_live_probe_verifies_open_alternatives() -> None:
    result = santa_clara.execute(
        parse_args(
            "probe",
            "--minimum-interval",
            "0.1",
            "--max-attempts",
            "2",
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["department_count"] == 10
    assert set(probe["departments"]) == santa_clara.EXPECTED_DEPARTMENTS
    assert probe["ruling_artifact_count"] >= 1
    assert probe["ruling_pdf"]["size_bytes"] > 100
    assert {product["product_kind"] for product in probe["products"]} == {
        "civil",
        "criminal",
    }


def test_live_products_expose_distinct_case_index_fields() -> None:
    result = santa_clara.execute(
        parse_args(
            "products",
            "--minimum-interval",
            "0.1",
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 2
    civil = next(
        record
        for record in result.records
        if record["product_kind"] == "civil"
    )
    criminal = next(
        record
        for record in result.records
        if record["product_kind"] == "criminal"
    )
    assert "scheduled_event_information" in civil["included_fields"]
    assert criminal["included_fields"] == (
        "case_number",
        "filing_date",
        "party_name",
    )
