from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from tools import query_texas_supreme_publications as publications


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "texas_supreme_publications"
)
RELEASE_URL = (
    "https://www.txcourts.gov/supreme/orders-opinions/"
    "2026/may/may-29-2026/"
)


def _artifact(name: str, source_url: str) -> publications.Artifact:
    return publications.Artifact(
        content=(FIXTURE_DIR / name).read_bytes(),
        source_url=source_url,
        media_type=(
            "application/pdf" if name.endswith(".pdf") else "text/html"
        ),
        headers={},
    )


def _args(*values: str) -> Any:
    return publications.build_parser().parse_args(list(values))


class FixtureClient:
    def __init__(self) -> None:
        self.annual_calls: list[int] = []
        self.release_calls: list[str] = []
        self.document_calls: list[str] = []

    def landing(self) -> publications.Artifact:
        return _artifact("landing.html", publications.LANDING_URL)

    def annual(self, year: int) -> publications.Artifact:
        self.annual_calls.append(year)
        assert year == 2026
        return _artifact("annual-2026.html", publications.annual_url(year))

    def release(self, source_url: str) -> publications.Artifact:
        self.release_calls.append(source_url)
        return _artifact("release-2026-05-29.html", RELEASE_URL)

    def document(self, source_url: str) -> publications.Artifact:
        self.document_calls.append(source_url)
        return _artifact("sample.pdf", source_url)


def test_landing_keeps_annual_outage_and_legacy_contracts_distinct() -> None:
    records = publications.parse_landing(
        _artifact("landing.html", publications.LANDING_URL)
    )
    kinds = {record["record_kind"] for record in records}
    assert kinds == {
        "annual_release_index",
        "network_outage_document",
        "pre_2014_archive",
        "fiscal_year_aggregate",
    }

    outage = [
        record
        for record in records
        if record["record_kind"] == "network_outage_document"
    ]
    assert {
        record["document"]["document_type"] for record in outage
    } >= {
        "network_outage_print_orders",
        "network_outage_special_order",
        "network_outage_orders_on_causes",
        "network_outage_miscellaneous_orders",
        "network_outage_court_opinion",
        "network_outage_concurring_opinion",
        "network_outage_dissenting_opinion",
    }
    warner = [
        record for record in outage if record["case_number"] == "18-0068"
    ]
    assert [record["document"]["document_type"] for record in warner] == [
        "network_outage_court_opinion",
        "network_outage_dissenting_opinion",
    ]
    assert len(
        {
            record["document"]["native_document_id"]
            for record in warner
        }
    ) == 2

    aggregates = [
        record
        for record in records
        if record["record_kind"] == "fiscal_year_aggregate"
    ]
    assert {
        record["document"]["document_type"] for record in aggregates
    } == {
        "fiscal_year_orders_aggregate",
        "fiscal_year_opinions_aggregate",
    }


def test_annual_page_enumerates_every_source_reported_release_date() -> None:
    index = publications.parse_annual_index(
        _artifact("annual-2026.html", publications.annual_url(2026)),
        year=2026,
    )
    assert [record["release_date"] for record in index.releases] == [
        "2026-01-05",
        "2026-05-22",
        "2026-05-29",
    ]
    assert index.releases[-1]["source_url"] == RELEASE_URL
    assert len(index.schema_fingerprint) == 64


def test_release_parser_uses_structure_not_generated_css_classes() -> None:
    page = publications.parse_release_page(
        _artifact("release-2026-05-29.html", RELEASE_URL),
        expected_date="2026-05-29",
    )
    assert page.release_date == "2026-05-29"
    assert page.release_artifact["document_type"] == "print_order_release"
    assert [record["raw_case_number"] for record in page.records] == [
        "24-0205",
        "24-0286",
        "25-0706",
    ]

    huffman = page.records[0]
    assert huffman["section_heading_raw"] == "ORDERS ON CAUSES"
    assert huffman["raw_case_text"].startswith("HUFFMAN ASSET MANAGEMENT")
    assert huffman["originating_county_candidate"] == "Dallas County"
    assert huffman["lower_court_candidate"] == {
        "label": "5th Court of Appeals District",
        "case_number_candidates": ["05-22-00779-CV"],
        "raw_parenthetical": (
            "(05-22-00779-CV, 719 SW3d 308, 11-07-23)"
        ),
        "authoritative_assignment": False,
    }
    assert {
        document["document_type"]
        for document in huffman["case_documents"]
    } == {"court_opinion", "concurring_opinion"}
    assert huffman["release_documents"][0]["document_type"] == (
        "editorial_case_summary"
    )
    assert huffman["release_artifact"]["native_document_id"] != (
        huffman["release_documents"][0]["native_document_id"]
    )
    assert huffman["release_occurrence_id"] == (
        "TXSC-RELEASE:2026-05-29:24-0205:1"
    )

    denied = page.records[-1]
    assert denied["action_heading_raw"] == (
        "THE FOLLOWING PETITIONS FOR REVIEW ARE DENIED:"
    )
    assert denied["participation_text"] == [
        "(Justice Devine not participating)"
    ]
    assert "DENIED" in denied["disposition_text"]


def test_search_exhausts_selected_release_set_when_limit_is_omitted() -> None:
    client = FixtureClient()
    result = publications.execute(
        _args(
            "search",
            "*",
            "--year",
            "2026",
            "--date-from",
            "2026-05-29",
            "--date-to",
            "2026-05-29",
        ),
        client=client,
        log_results=False,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert client.annual_calls == [2026]
    assert client.release_calls == [RELEASE_URL]


def test_search_filters_exact_case_and_document_type() -> None:
    result = publications.execute(
        _args(
            "search",
            "*",
            "--year",
            "2026",
            "--date-from",
            "2026-05-29",
            "--date-to",
            "2026-05-29",
            "--case-number",
            "24-0286",
            "--document-type",
            "dissenting_opinion",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert [record["raw_case_number"] for record in result.records] == [
        "24-0286"
    ]


def test_limit_cursor_is_bound_to_the_selected_release_set() -> None:
    client = FixtureClient()
    first = publications.execute(
        _args(
            "search",
            "*",
            "--year",
            "2026",
            "--date-from",
            "2026-05-29",
            "--date-to",
            "2026-05-29",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    assert len(first.records) == 2
    assert first.next_cursor

    second = publications.execute(
        _args(
            "search",
            "*",
            "--year",
            "2026",
            "--date-from",
            "2026-05-29",
            "--date-to",
            "2026-05-29",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert [record["raw_case_number"] for record in second.records] == [
        "25-0706"
    ]
    assert second.next_cursor is None

    mismatched = publications.execute(
        _args(
            "search",
            "Huffman",
            "--year",
            "2026",
            "--date-from",
            "2026-05-29",
            "--date-to",
            "2026-05-29",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert mismatched.status.value == "unavailable"
    assert mismatched.errors[0].code == "invalid_selection"


def test_release_resolves_through_the_annual_index() -> None:
    client = FixtureClient()
    result = publications.execute(
        _args("release", "2026-05-29"),
        client=client,
        log_results=False,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 3
    assert client.annual_calls == [2026]
    assert client.release_calls == [RELEASE_URL]


def test_download_validates_and_hashes_the_exact_official_pdf(
    tmp_path: Path,
) -> None:
    client = FixtureClient()
    destination = tmp_path / "opinion.pdf"
    source_url = "https://www.txcourts.gov/media/1462796/240205.pdf"
    result = publications.execute(
        _args("download", source_url, str(destination)),
        client=client,
        log_results=False,
    )
    assert result.status.value == "ok"
    assert destination.read_bytes().startswith(b"%PDF-")
    assert result.records[0]["sha256"] == hashlib.sha256(
        destination.read_bytes()
    ).hexdigest()
    assert client.document_calls == [source_url]


def test_search_requires_an_explicit_annual_or_date_scope() -> None:
    result = publications.execute(
        _args("search", "Huffman"),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status.value == "unavailable"
    assert result.errors[0].code == "invalid_selection"


def test_probe_checks_landing_annual_release_and_pdf_contracts() -> None:
    result = publications.execute(
        _args("probe"),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.records[0]
    assert record["requests_made"] == 4
    assert record["probe_release_date"] == "2026-05-29"
    assert record["release_case_count"] == 3
    assert set(record["landing_record_kinds"]) == {
        "annual_release_index",
        "network_outage_document",
        "pre_2014_archive",
        "fiscal_year_aggregate",
    }
    assert record["rolling_observation"]["print_order_pdf_bytes"] > 0


@pytest.mark.parametrize(
    "url",
    [
        "http://www.txcourts.gov/media/1462796/240205.pdf",
        "https://example.com/media/1462796/240205.pdf",
        "https://www.txcourts.gov/supreme/orders-opinions/",
    ],
)
def test_download_rejects_non_official_pdf_routes(url: str) -> None:
    with pytest.raises(publications.SelectionError):
        publications._official_pdf_url(url)
