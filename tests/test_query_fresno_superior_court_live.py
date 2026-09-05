from __future__ import annotations

import os

import pytest

from tools import query_fresno_superior_court as fresno
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_FRESNO_SUPERIOR_COURT") != "1",
    reason=(
        "set RUN_LIVE_FRESNO_SUPERIOR_COURT=1 for official live probes"
    ),
)


def parse_args(*values: str):
    return fresno.build_parser().parse_args(list(values))


def test_live_probe_verifies_all_anonymous_operations() -> None:
    result = fresno.execute(
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
    assert probe["portal"]["anonymous_case_search_control_present"] is False
    assert probe["calendar"]["index_artifact_count"] >= 1
    assert probe["calendar"]["parsed_record_count"] >= 1
    assert set(probe["tentative_rulings"]["departments"]) == {
        403,
        501,
        502,
        503,
    }
    assert probe["tentative_rulings"]["index_artifact_count"] >= 4
    assert probe["probate_examiner_notes"]["case_number"] == "19CEPR00967"
    assert (
        probe["probate_examiner_notes"]["case_style"]
        == "Celestino Perales (Estate)"
    )
    assert probe["probate_examiner_notes"]["parsed_record_count"] >= 52


def test_live_known_ruling_document_preserves_case_metadata() -> None:
    result = fresno.execute(
        parse_args(
            "rulings",
            "--url",
            (
                "https://www.fresno.courts.ca.gov/system/files/"
                "tentative-rulings/07-30-26-dept-501-gsf.pdf"
            ),
            "--minimum-interval",
            "0.1",
            "--max-attempts",
            "2",
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert {record["case_number"] for record in result.records} >= {
        "25CECG03846",
        "25CECG01657",
        "25CECG05256",
    }
    yang = next(
        record
        for record in result.records
        if record["case_number"] == "25CECG05256"
    )
    assert yang["matter_number"] == 41
    assert yang["issued_date"] == "2026-07-28"
    assert "vehicle pursuit" in yang["explanation"]
