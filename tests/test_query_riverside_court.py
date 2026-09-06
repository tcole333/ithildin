from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools import query_riverside_court as riverside


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "riverside_court"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def fixture_json(name: str) -> dict:
    return json.loads(fixture(name))


class FixtureClient:
    def __init__(
        self,
        *,
        calendar_payload: dict | None = None,
        ruling_html: str | None = None,
        artifact_bytes: bytes = b"%PDF-1.7\nfixture\n%%EOF\n",
    ) -> None:
        self.calendar_payload = calendar_payload or fixture_json(
            "calendar_payload.json"
        )
        self.ruling_html = ruling_html or fixture("ruling_index.html")
        self.artifact_bytes = artifact_bytes
        self.calls: list[dict] = []

    def run(self, selection: dict) -> dict:
        self.calls.append(copy.deepcopy(selection))
        if selection["operation"] == "calendar":
            return copy.deepcopy(self.calendar_payload)
        if selection["operation"] == "ruling_index":
            return {
                "ok": True,
                "url": riverside.RULING_INDEX_URL,
                "html": self.ruling_html,
            }
        if selection["operation"] == "ruling_pdf":
            department = riverside._normalized_department(
                selection["department"]
            )
            index = riverside.parse_ruling_directory(
                self.ruling_html,
                retrieved_at=RETRIEVED_AT,
            )
            match = next(
                row for row in index if row["department"] == department
            )
            return {
                "ok": True,
                "index_url": riverside.RULING_INDEX_URL,
                "index_html": self.ruling_html,
                "artifact": {
                    "label": match["label"],
                    "url": match["artifact_url"],
                    "status": 200,
                    "content_type": "application/pdf",
                    "etag": '"fixture"',
                    "last_modified": "Thu, 30 Jul 2026 07:00:00 GMT",
                    "base64": base64.b64encode(
                        self.artifact_bytes
                    ).decode(),
                },
            }
        if selection["operation"] == "probe":
            probe_calendar = copy.deepcopy(self.calendar_payload)
            probe_calendar["selected_combinations"] = 1
            probe_calendar["records"] = [
                row
                for row in probe_calendar["records"]
                if row["source_department"] == "Department 8"
            ]
            return {
                "ok": True,
                "calendar": probe_calendar,
                "ruling_index": {
                    "ok": True,
                    "url": riverside.RULING_INDEX_URL,
                    "html": self.ruling_html,
                },
            }
        raise AssertionError(f"unexpected operation: {selection}")

    def close(self) -> None:
        return None


def test_source_manifest_separates_implemented_and_complementary_routes() -> None:
    records = riverside.source_records()
    assert records[0]["source_id"] == riverside.SOURCE_FAMILY_ID
    assert records[0]["record_kind"] == "source_manifest"
    implemented = {
        row["source_id"]
        for row in records
        if row["record_kind"] == "implemented_source"
    }
    assert implemented == {
        riverside.CALENDAR_SOURCE_ID,
        riverside.RULING_SOURCE_ID,
    }
    complements = [
        row for row in records if row["record_kind"] == "complementary_source"
    ]
    assert {row["source_id"] for row in complements} == set(
        riverside.COMPLEMENT_SOURCE_IDS_BY_URL.values()
    )
    assert len({row["source_id"] for row in records}) == len(records)
    assert any(
        row["url"] == riverside.PUBLIC_ACCESS_URL for row in complements
    )
    assert any(
        row["url"] == riverside.PURCHASE_INDEXES_URL for row in complements
    )
    assert any(
        row["url"] == riverside.PROBATE_INFORMATION_URL
        for row in complements
    )
    assert any(
        row["url"] == riverside.FOURTH_DISTRICT_SEARCH_URL
        for row in complements
    )


def test_calendar_omitted_limit_returns_every_source_row() -> None:
    client = FixtureClient()
    result = riverside.calendar_search(
        courthouse="Historic Court House",
        department="Department 8",
        area_of_law="probate",
        anchor_date="2026-07-30",
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 4
    assert result.next_cursor is None
    assert client.calls[0] == {
        "operation": "calendar",
        "anchor_date": "2026-07-30",
        "courthouse": "Historic Court House",
        "department": "8",
        "area_of_law": "Probate",
        "start_date": None,
        "end_date": None,
    }
    bounds = result.query.query.metadata["bounds"]
    assert bounds["caller_limit"] is None
    assert bounds["transport_response_paging"] is None
    assert bounds["visible_grid_paging"] == "client_side_only"
    assert list(bounds["source_window"]) == [
        "2026-07-30",
        "2026-07-31",
        "2026-08-03",
        "2026-08-04",
    ]


def test_calendar_normalizes_multi_hearing_and_attorney_fields() -> None:
    result = riverside.calendar_search(
        anchor_date="2026-07-30",
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
    )
    first = result.records[0]
    assert first["case_number"] == "PRRI2601001"
    assert list(first["hearing"]["names"]) == [
        "Hearing on Petition for Probate",
        "Status Conference",
    ]
    assert list(first["attorneys"]) == ["Alex Counsel", "Blair Counsel"]
    assert first["department"] == "8"
    assert first["courthouse"]["address"] == (
        "4050 Main Street, Riverside, CA, 92501"
    )
    assert first["judicial_officer"] == "Christopher B. Harmon"
    assert first["canonical_ref"].startswith("RIVERSIDE-CALENDAR:")


def test_explicit_limit_issues_snapshot_cursor_and_resumes() -> None:
    client = FixtureClient()
    first = riverside.calendar_search(
        limit=2,
        anchor_date="2026-07-30",
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert len(first.records) == 2
    assert first.next_cursor
    second = riverside.calendar_search(
        limit=2,
        cursor=first.next_cursor,
        anchor_date="2026-07-30",
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert len(second.records) == 2
    assert second.next_cursor is None
    assert {
        row["canonical_ref"] for row in first.records
    }.isdisjoint({row["canonical_ref"] for row in second.records})


def test_cursor_rejects_changed_query() -> None:
    client = FixtureClient()
    initial = riverside.calendar_search(
        limit=1,
        anchor_date="2026-07-30",
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    with pytest.raises(riverside.RiversideSelectionError) as raised:
        riverside.calendar_search(
            courthouse="Historic Court House",
            limit=1,
            cursor=initial.next_cursor,
            anchor_date="2026-07-30",
            client=client,
            retrieved_at=RETRIEVED_AT,
        )
    assert raised.value.code == "cursor_query_mismatch"


def test_cursor_rejects_changed_source_snapshot() -> None:
    stable_client = FixtureClient()
    initial = riverside.calendar_search(
        limit=1,
        anchor_date="2026-07-30",
        client=stable_client,
        retrieved_at=RETRIEVED_AT,
    )
    changed = fixture_json("calendar_payload.json")
    changed["records"][0]["event_name"] = "Changed Hearing"
    with pytest.raises(riverside.RiversideSelectionError) as raised:
        riverside.calendar_search(
            limit=1,
            cursor=initial.next_cursor,
            anchor_date="2026-07-30",
            client=FixtureClient(calendar_payload=changed),
            retrieved_at=RETRIEVED_AT,
        )
    assert raised.value.code == "cursor_snapshot_changed"


def test_calendar_empty_payload_is_authoritative_no_results() -> None:
    result = riverside.calendar_search(
        anchor_date="2026-07-30",
        client=FixtureClient(
            calendar_payload=fixture_json("calendar_empty.json")
        ),
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_calendar_schema_drift_is_not_reported_as_no_results() -> None:
    changed = fixture_json("calendar_payload.json")
    del changed["records"][0]["case_number"]
    with pytest.raises(riverside.RiversideSourceChangedError) as raised:
        riverside.calendar_search(
            anchor_date="2026-07-30",
            client=FixtureClient(calendar_payload=changed),
            retrieved_at=RETRIEVED_AT,
        )
    assert raised.value.code == "calendar_record_schema_changed"


def test_parse_ruling_directory_preserves_path_dates_and_placeholders() -> None:
    records = riverside.parse_ruling_directory(
        fixture("ruling_index.html"),
        retrieved_at=RETRIEVED_AT,
    )
    assert len(records) == 4
    by_department = {row["department"]: row for row in records}
    assert by_department["PS1"]["region"] == "Desert Region"
    assert by_department["PS1"]["courthouse"] == "Palm Springs Court"
    assert by_department["PS1"]["judicial_officer"] == "Arthur Hester III"
    assert by_department["PS1"]["artifact_path_month"] == "2026-07"
    assert by_department["PS1"]["artifact_filename_date_candidates"] == [
        "2026-07-30"
    ]
    assert by_department["PS4"]["filename_indicates_no_tentatives"] is True
    assert by_department["M205"]["artifact_path_month"] == "2024-07"
    assert by_department["02"]["artifact_path_month"] == "2023-10"


def test_ruling_directory_identity_drift_is_explicit() -> None:
    with pytest.raises(riverside.RiversideSourceChangedError) as raised:
        riverside.parse_ruling_directory(
            fixture("ruling_source_changed.html"),
            retrieved_at=RETRIEVED_AT,
        )
    assert raised.value.code == "ruling_directory_identity_changed"


def test_ruling_index_filters_department_without_default_cap() -> None:
    result = riverside.ruling_index(
        department="PS4",
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["department"] == "PS4"
    bounds = result.query.query.metadata["bounds"]
    assert bounds["caller_limit"] is None
    coverage = result.query.query.metadata["coverage"]
    assert coverage["directory_artifacts_before_filter"] == 4


def test_parse_ruling_text_retains_full_text_and_case_numbers() -> None:
    parsed = riverside.parse_ruling_text(fixture("ruling_text.txt"))
    assert parsed["hearing_date"] == "2026-07-30"
    assert parsed["department"] == "PS1"
    assert parsed["case_numbers"] == [
        "CVPS2407937",
        "CVPS2501303",
        "CVPS2605423",
    ]
    assert parsed["matter_numbers"] == [1, 2]
    assert parsed["matter_count"] == 2
    assert parsed["no_tentative_rulings"] is False
    assert "Motion GRANTED" in parsed["text"]
    assert len(parsed["text_sha256"]) == 64


def test_document_placeholder_flag_does_not_match_one_matter_disposition() -> None:
    mixed = (
        "Tentative Rulings for July 30, 2026\n"
        "Department PS1\n\n"
        "1.\nCASE # CASE NAME HEARING NAME\n"
        "CVPS2501702 CARRERA VS GONZALEZ MOTION\n"
        "Tentative Ruling: No tentative ruling. Hearing continued.\n"
    )
    parsed = riverside.parse_ruling_text(mixed)
    assert parsed["case_numbers"] == ["CVPS2501702"]
    assert parsed["matter_count"] == 1
    assert parsed["no_tentative_rulings"] is False

    placeholder = (
        "No Tentative Rulings for\n"
        "Department 260\n"
        "Riverside Superior Court\n"
    )
    assert (
        riverside.parse_ruling_text(placeholder)["no_tentative_rulings"]
        is True
    )


def test_ruling_document_validates_pdf_and_preserves_artifact(
    tmp_path: Path,
) -> None:
    pdf_bytes = b"%PDF-1.7\nRiverside fixture\n%%EOF\n"
    destination = tmp_path / "ps1.pdf"
    result = riverside.ruling_document(
        "Department PS1",
        client=FixtureClient(artifact_bytes=pdf_bytes),
        retrieved_at=RETRIEVED_AT,
        download_path=destination,
        text_extractor=lambda _: fixture("ruling_text.txt"),
    )
    assert result.status.value == "ok"
    record = result.records[0]
    assert record["department"] == "PS1"
    assert record["matter_count"] == 2
    assert list(record["case_numbers"]) == [
        "CVPS2407937",
        "CVPS2501303",
        "CVPS2605423",
    ]
    assert record["artifact"]["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert record["artifact"]["bytes"] == len(pdf_bytes)
    assert destination.read_bytes() == pdf_bytes
    assert any(
        route["url"] == riverside.PROBATE_INFORMATION_URL
        for route in record["complementary_routes"]
    )


def test_ruling_document_rejects_non_pdf_representation() -> None:
    with pytest.raises(riverside.RiversideSourceChangedError) as raised:
        riverside.ruling_document(
            "PS1",
            client=FixtureClient(artifact_bytes=b"<html>challenge</html>"),
            retrieved_at=RETRIEVED_AT,
            include_text=False,
        )
    assert raised.value.code == "ruling_artifact_not_pdf"


def test_probe_is_bounded_and_reports_full_selector_shape() -> None:
    result = riverside.probe_sources(
        client=FixtureClient(),
        anchor_date="2026-07-30",
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    record = result.records[0]
    assert record["ecalendar"]["courthouse_count"] == 2
    assert record["ecalendar"]["department_count"] == 2
    assert record["ecalendar"]["department_area_combinations"] == 3
    assert record["ecalendar"]["probe_rows"] == 2
    assert record["tentative_rulings"]["directory_artifact_count"] == 4
    assert record["probe_bounds"][
        "calendar_department_area_combinations_queried"
    ] == 1
    assert record["probe_bounds"]["ruling_artifacts_downloaded"] == 0


def test_execute_converts_selection_failure_to_explicit_envelope() -> None:
    args = riverside.build_parser().parse_args(
        ["calendar", "--limit", "0", "--json"]
    )
    result = riverside.execute(
        args,
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status.value == "unavailable"
    assert result.records == ()
    assert result.errors[0].code == "invalid_limit"


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official endpoint probes",
)
def test_live_probe_confirms_calendar_and_ruling_contracts() -> None:
    result = riverside.probe_sources()
    assert result.status.value == "ok"
    record = result.records[0]
    assert len(record["ecalendar"]["business_days"]) == 4
    assert record["ecalendar"]["courthouse_count"] >= 9
    assert record["ecalendar"]["department_count"] >= 60
    assert record["ecalendar"]["department_area_combinations"] >= 60
    assert record["tentative_rulings"]["directory_artifact_count"] > 0
    assert record["probe_bounds"]["ruling_artifacts_downloaded"] == 0
