from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from tools import query_dc_court_directory_data as dc_directory
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "dc_court_directory_data"
)


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _artifact(
    name: str,
    url: str,
    *,
    media_type: str = "text/html",
) -> dc_directory.Artifact:
    return dc_directory.Artifact(
        content=_fixture(name),
        source_url=url,
        media_type=media_type,
        headers={"content-type": media_type},
    )


class QueueClient:
    def __init__(
        self,
        responses: list[dc_directory.Artifact],
    ) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> dc_directory.Artifact:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected D.C. Courts request: {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def _args(*values: str) -> argparse.Namespace:
    return dc_directory.build_parser().parse_args(list(values))


def test_sources_and_manifest_keep_four_component_identities() -> None:
    sources = dc_directory.execute(
        _args("sources"),
        client=QueueClient([]),
        log_results=False,
    )
    manifest = dc_directory.execute(
        _args("manifest"),
        client=QueueClient([]),
        log_results=False,
    )

    validate_envelope(sources.to_dict())
    validate_envelope(manifest.to_dict())
    assert sources.status is ResultStatus.OK
    assert {
        record["source_id"] for record in sources.records
    } == set(dc_directory.COMPONENTS)
    assert len(dc_directory.COMPONENTS) == 4
    assert manifest.records[0]["operation_access_model"] == {
        "judicial_directories_and_contacts": (
            "open_server_rendered_html"
        ),
        "assignment_and_report_artifacts": "open_pdf",
        "aggregate_and_case_level_extracts": (
            "published_request_process"
        ),
    }
    assert (
        "us-dc-court-of-appeals-case-search"
        in manifest.records[0]["complementary_source_ids"]
    )


def test_superior_parser_exposes_role_fields_and_pager_contract() -> None:
    page = dc_directory.parse_directory_page(
        _artifact(
            "superior_page_1.html",
            dc_directory.SUPERIOR_DIRECTORY_URL,
        ),
        court="superior",
    )

    assert len(page.records) == 5
    assert page.advertised_totals == {
        "chief": 1,
        "associate": 3,
        "magistrate": 1,
        "senior": 1,
    }
    assert page.page_counts == {
        "chief": 1,
        "associate": 2,
        "magistrate": 1,
        "senior": 1,
    }
    becker = next(
        record
        for record in page.records
        if record["published_name"] == "Becker, Julie"
    )
    assert becker["court_id"] == dc_directory.SUPERIOR_COURT_ID
    assert becker["calendar"] == "Civil 2"
    assert becker["courtroom"] == "415"
    assert becker["remote_hearing_url"].endswith("/meet/ctb415")
    assert becker["projection"]["projectable_as_case"] is False


def test_combined_superior_pager_reconciles_every_advertised_role() -> None:
    client = QueueClient(
        [
            _artifact(
                "superior_page_1.html",
                dc_directory.SUPERIOR_DIRECTORY_URL,
            ),
            _artifact(
                "superior_page_2.html",
                (
                    f"{dc_directory.SUPERIOR_DIRECTORY_URL}"
                    "?page=0%2C1%2C0%2C0"
                ),
            ),
        ]
    )

    records = dc_directory.collect_directory(
        client,
        court="superior",
    )

    assert len(records) == 6
    assert [record["published_name"] for record in records].count(
        "Cordero, Laura A."
    ) == 1
    query = parse_qs(urlsplit(client.calls[1]["url"]).query)
    assert query["page"] == ["0,1,0,0"]


def test_appellate_directory_and_both_contact_blocks_parse() -> None:
    appeals_artifact = _artifact(
        "appeals.html",
        dc_directory.APPEALS_DIRECTORY_URL,
    )
    page = dc_directory.parse_directory_page(
        appeals_artifact,
        court="appeals",
    )
    appeals_contact = dc_directory.parse_contact_record(
        appeals_artifact,
        court="appeals",
    )
    superior_contact = dc_directory.parse_contact_record(
        _artifact(
            "superior_page_1.html",
            dc_directory.SUPERIOR_DIRECTORY_URL,
        ),
        court="superior",
    )

    assert len(page.records) == 3
    assert page.advertised_totals == {
        "chief": 1,
        "associate": 1,
        "senior": 1,
    }
    assert appeals_contact["leadership"][1] == {
        "title": "Clerk of the Court",
        "name": "Julio Castillo",
    }
    assert appeals_contact["locations"][0]["name"] == (
        "Historic Courthouse"
    )
    assert appeals_contact["hours"][0]["office"] == (
        "Public Office (Room 115)"
    )
    assert superior_contact["contacts"][0]["values"][0] == {
        "type": "phone",
        "value": "202-879-1010",
    }


def test_assignment_routes_remain_directory_publications() -> None:
    records = dc_directory.parse_assignment_publications(
        _artifact(
            "superior_page_1.html",
            dc_directory.SUPERIOR_DIRECTORY_URL,
        )
    )

    assert len(records) == 3
    assert records[0]["title"] == "2026 Judicial Assignments"
    assert records[0]["publication_year"] == 2026
    assert records[0]["source_id"] == (
        dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID
    )
    assert records[2]["artifact_url"].endswith(
        "/Pairing-of-Judges_12172025.pdf"
    )


def test_data_request_program_preserves_forms_and_contact_variants() -> None:
    record = dc_directory.parse_data_request_program(
        _artifact(
            "data_requests.html",
            dc_directory.DATA_REQUEST_URL,
        )
    )

    assert len(record["sections"]) == 5
    assert {
        artifact["artifact_kind"]
        for artifact in record["artifacts"]
    } == {
        "faq_and_instructions",
        "public_request_form",
        "government_or_court_partner_form",
    }
    assert record["published_email_variants"] == [
        "smddata@dccsystem.gov",
        "smddata@dcsc.gov",
    ]
    assert record["published_phone_variants"] == ["202-879-2886"]
    assert record["catalog_observations"][0]["kind"] == (
        "inconsistent_published_contact"
    )
    assert record["delivery_model"] == (
        "submitted_request_review_and_fulfillment"
    )


def test_report_catalog_keeps_duplicate_occurrences_and_label_anomaly() -> None:
    records = dc_directory.parse_report_catalog(
        _artifact(
            "reports.html",
            dc_directory.REPORTS_URL,
        )
    )

    assert len(records) == 6
    assert len({record["canonical_ref"] for record in records}) == 6
    statistical = records[0]
    assert statistical["publication_year"] == 2025
    assert statistical["report_kind"] == "statistical_summary"
    narrative = [
        record
        for record in records
        if record["artifact_url"].endswith(
            "/Annual-Report-2024.pdf"
        )
    ]
    assert len(narrative) == 2
    assert {
        record["publication_year"] for record in narrative
    } == {2023, 2024}
    assert all(
        record["catalog_observations"][0]["kind"]
        == "same_artifact_url_multiple_labels"
        for record in narrative
    )
    duplicate_family = [
        record
        for record in records
        if record["artifact_url"].endswith(
            "/2022-FC-Annual-Report.pdf"
        )
    ]
    assert all(
        record["catalog_observations"][0]["kind"]
        == "duplicate_catalog_occurrence"
        for record in duplicate_family
    )


def test_directory_and_report_filters_use_complete_source_snapshot() -> None:
    directory_client = QueueClient(
        [
            _artifact(
                "superior_page_1.html",
                dc_directory.SUPERIOR_DIRECTORY_URL,
            ),
            _artifact(
                "superior_page_2.html",
                (
                    f"{dc_directory.SUPERIOR_DIRECTORY_URL}"
                    "?page=0%2C1%2C0%2C0"
                ),
            ),
        ]
    )
    directory = dc_directory.execute(
        _args(
            "directory",
            "--court",
            "superior",
            "--query",
            "Julie Becker",
        ),
        client=directory_client,
        log_results=False,
    )
    reports = dc_directory.execute(
        _args(
            "reports",
            "--section",
            "annual-reports",
            "--year",
            "2025",
        ),
        client=QueueClient(
            [
                _artifact(
                    "reports.html",
                    dc_directory.REPORTS_URL,
                )
            ]
        ),
        log_results=False,
    )

    assert directory.status is ResultStatus.OK
    assert [record["published_name"] for record in directory.records] == [
        "Becker, Julie"
    ]
    assert reports.status is ResultStatus.OK
    assert [record["title"] for record in reports.records] == [
        "2025 Annual Report - Statistical Summary"
    ]
    assert directory.query.source.source_id == (
        dc_directory.SUPERIOR_DIRECTORY_SOURCE_ID
    )
    assert reports.query.source.source_id == dc_directory.REPORTS_SOURCE_ID


def test_report_download_resolves_live_title_validates_and_hashes(
    tmp_path: Path,
) -> None:
    pdf = b"%PDF-1.7\nfixture D.C. statistical report\n%%EOF\n"
    client = QueueClient(
        [
            _artifact(
                "reports.html",
                dc_directory.REPORTS_URL,
            ),
            dc_directory.Artifact(
                content=pdf,
                source_url=(
                    f"{dc_directory.BASE_URL}"
                    "/sites/default/files/CY2025-Statistical-Summary.pdf"
                ),
                media_type="application/pdf",
                headers={"content-type": "application/pdf"},
            ),
        ]
    )
    destination = tmp_path / "dc-2025.pdf"

    result = dc_directory.execute(
        _args(
            "download",
            "--collection",
            "reports",
            "2025 Annual Report - Statistical Summary",
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == pdf
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    assert result.records[0]["sha256"] == (
        dc_directory.hashlib.sha256(pdf).hexdigest()
    )
    assert result.records[0]["catalog_occurrences"][0]["publication_year"] == 2025
    assert client.calls[1]["maximum_bytes"] == (
        dc_directory.MAXIMUM_PDF_BYTES
    )


def test_source_drift_and_interactive_challenge_are_not_empty_results() -> None:
    with pytest.raises(dc_directory.SourceChangedError) as changed:
        dc_directory.parse_directory_page(
            _artifact(
                "source_changed.html",
                dc_directory.SUPERIOR_DIRECTORY_URL,
            ),
            court="superior",
        )
    assert changed.value.code == "judge_views_missing"

    challenge = dc_directory.Artifact(
        content=(
            b"<html><h1>Superior Court Judges</h1>"
            b"Enable JavaScript and cookies to continue</html>"
        ),
        source_url=dc_directory.SUPERIOR_DIRECTORY_URL,
        media_type="text/html",
        headers={},
    )
    with pytest.raises(
        dc_directory.DCCourtDirectoryDataError
    ) as blocked:
        dc_directory.parse_directory_page(
            challenge,
            court="superior",
        )
    assert blocked.value.code == "human_verification"
    assert blocked.value.status is ResultStatus.HUMAN_REQUIRED
