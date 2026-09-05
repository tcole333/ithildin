from __future__ import annotations

import os

import pytest

from tools import query_san_diego_court_index as san_diego
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_SAN_DIEGO_COURT_INDEX") != "1",
    reason=(
        "set RUN_LIVE_SAN_DIEGO_COURT_INDEX=1 for official live probes"
    ),
)


def parse_args(*values: str):
    return san_diego.build_parser().parse_args(list(values))


def test_live_bounded_probe_verifies_index_detail_and_static_filings() -> None:
    result = san_diego.execute(
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
    assert probe["bounded_probe"] is True
    assert probe["party_search"]["native_rows_observed"] >= 2
    assert "IC810023" in probe["party_search"]["case_numbers"]
    assert list(probe["case_search"]["case_numbers"]) == ["IC810023"]
    assert probe["case_detail"]["case_number"] == "IC810023"
    assert probe["case_detail"]["category_code"] == "A60301"
    filing_types = probe["new_filings"]["case_types"]
    assert set(filing_types) == set(san_diego.NEW_FILING_TYPE_CODES)
    assert filing_types["civil"]["case_count"] >= 1
    assert filing_types["civil"]["native_partitions_discovered"] == 25
    assert probe["transport"]["court_index"] == "headed_chromium"


def test_live_new_filings_exhausts_current_civil_partitions_before_limit() -> None:
    result = san_diego.execute(
        parse_args(
            "new-filings",
            "--case-type",
            "civil",
            "--limit",
            "3",
            "--minimum-interval",
            "0.05",
            "--max-attempts",
            "2",
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 3
    metadata = result.records[0]["search_metadata"]
    assert metadata["native_partitions_discovered"] == 25
    assert metadata["native_partitions_fetched"] == 25
    assert metadata["native_partitions_exhausted"] is True
    assert metadata[
        "caller_limit_applied_after_native_partition_collection"
    ] is True


def test_live_party_search_exhausts_multi_page_native_result() -> None:
    result = san_diego.execute(
        parse_args(
            "party-search",
            "--case-type",
            "civil",
            "--last-name",
            "Smith",
            "--begin-year",
            "2026",
            "--end-year",
            "2026",
            "--minimum-interval",
            "0.05",
            "--max-attempts",
            "2",
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    metadata = result.records[0]["search_metadata"]
    assert metadata["native_rows_observed"] > 50
    assert metadata["native_pages_discovered"] >= 2
    assert metadata["pages_fetched"] == metadata["native_pages_discovered"]
    assert metadata["native_pages_exhausted"] is True
    assert metadata["max_rows_on_page"] == 50
    assert metadata["caller_limit"] is None
    assert metadata["server_result_ceiling_value"] is None
