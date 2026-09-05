from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import (
    ingest_state_court_records as ingest,
    query_dc_court_directory_data as dc_directory,
    query_state_courts,
)
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "dc_court_directory_data"
)


def _artifact(name: str, url: str) -> dc_directory.Artifact:
    return dc_directory.Artifact(
        content=(FIXTURES / name).read_bytes(),
        source_url=url,
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(
    source_id: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=dc_directory.SOURCE_METADATA[source_id],
        jurisdiction=dc_directory.JURISDICTION,
        query=QueryMetadata(
            operation="directory",
            parameters={},
        ),
    )
    return PublicRecordsResult.success(query, records).to_dict()


def test_shared_routes_select_each_court_and_role_without_merging_sources() -> None:
    superior_route = query_state_courts.LIVE_ROUTES[
        dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID
    ]["search"]
    appeals_route = query_state_courts.LIVE_ROUTES[
        dc_directory.APPEALS_DIRECTORY_SOURCE_ID
    ]["search"]

    superior = superior_route.translate(
        _shared_args(
            "search",
            "Becker",
            "--source",
            dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID,
            "--jurisdiction",
            "DC",
            "--court-id",
            dc_directory.SUPERIOR_COURT_ID,
            "--search-field",
            "associate",
            "--first-name",
            "Julie",
            "--max-records",
            "7",
        ),
        superior_route.adapter_command,
    )
    appeals = appeals_route.translate(
        _shared_args(
            "search",
            "*",
            "--source",
            dc_directory.APPEALS_DIRECTORY_SOURCE_ID,
            "--search-field",
            "senior",
        ),
        appeals_route.adapter_command,
    )

    assert superior.command == "directory"
    assert superior.court == "superior"
    assert superior.role == "associate"
    assert superior.query == "Julie Becker"
    assert superior.limit == 7
    assert appeals.command == "directory"
    assert appeals.court == "appeals"
    assert appeals.role == "senior"
    assert appeals.query is None
    assert appeals.limit is None


def test_shared_directory_rejects_a_conflicting_court_identity() -> None:
    route = query_state_courts.LIVE_ROUTES[
        dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID
    ]["search"]

    with pytest.raises(ValueError, match=dc_directory.SUPERIOR_COURT_ID):
        route.translate(
            _shared_args(
                "search",
                "Becker",
                "--source",
                dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID,
                "--court-id",
                dc_directory.APPEALS_COURT_ID,
            ),
            route.adapter_command,
        )


def test_directory_people_are_snapshot_only_for_both_courts(
    tmp_path: Path,
) -> None:
    superior = [
        dict(record)
        for record in dc_directory.parse_directory_page(
            _artifact(
                "superior_page_1.html",
                dc_directory.SUPERIOR_DIRECTORY_URL,
            ),
            court="superior",
        ).records
    ]
    appeals = [
        dict(record)
        for record in dc_directory.parse_directory_page(
            _artifact(
                "appeals.html",
                dc_directory.APPEALS_DIRECTORY_URL,
            ),
            court="appeals",
        ).records
    ]
    court_db = tmp_path / "courts.db"

    superior_report = ingest_envelope(
        _envelope(
            dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID,
            superior,
        ),
        court_db=court_db,
    )
    appeals_report = ingest_envelope(
        _envelope(
            dc_directory.APPEALS_DIRECTORY_SOURCE_ID,
            appeals,
        ),
        court_db=court_db,
    )

    assert superior_report["projected"]["cases"] == 0
    assert superior_report["snapshot_only"] == {
        "record_count": 5,
        "record_kinds": {"court_directory_judge": 5},
    }
    assert appeals_report["projected"]["cases"] == 0
    assert appeals_report["snapshot_only"] == {
        "record_count": 3,
        "record_kinds": {"court_directory_judge": 3},
    }
    assert dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID in (
        ingest.DC_COURT_DIRECTORY_SOURCE_IDS
    )


def test_request_program_and_aggregate_reports_do_not_claim_case_routes() -> None:
    assert dc_directory.DATA_REQUEST_SOURCE_ID not in (
        query_state_courts.LIVE_ROUTES
    )
    assert dc_directory.REPORTS_SOURCE_ID not in (
        query_state_courts.LIVE_ROUTES
    )
