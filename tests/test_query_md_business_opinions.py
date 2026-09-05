from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_md_business_opinions as md
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/md_business_opinions")
ARCHIVE_DIRECTORY = (FIXTURE_DIR / "archive_directory.html").read_text()
CURRENT = (FIXTURE_DIR / "current.html").read_text()
ARCHIVE_2008 = (FIXTURE_DIR / "archive2008.html").read_text()
ARCHIVE_2003 = (FIXTURE_DIR / "archive2003.html").read_text()
ARCHIVE_IRREGULAR = (FIXTURE_DIR / "archive_irregular.html").read_text()
ARCHIVE_2007_SWAPPED = (FIXTURE_DIR / "archive2007_swapped.html").read_text()
SOURCE_CHANGED = (FIXTURE_DIR / "source_changed.html").read_text()
PDF_BYTES = b"%PDF-1.7\nfixture Maryland business opinion\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    content: bytes = b""
    url: str = md.CURRENT_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=UTF-8"}
    )


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected Maryland Judiciary request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(
        self,
        *,
        current: md.MarylandBusinessOpinionIndex | None = None,
        routes: md.MarylandBusinessRoutes | None = None,
        archives: Mapping[int, md.MarylandBusinessOpinionIndex] | None = None,
        document: md.MarylandBusinessDocument | None = None,
    ) -> None:
        self.current = current
        self.routes = routes
        self.archives = dict(archives or {})
        self.document = document
        self.archive_calls: list[tuple[int, str | None]] = []
        self.closed = False

    def fetch_current(self) -> md.MarylandBusinessOpinionIndex:
        if self.current is None:
            raise AssertionError("unexpected current-index request")
        return self.current

    def fetch_archive_directory(self) -> md.MarylandBusinessRoutes:
        if self.routes is None:
            raise AssertionError("unexpected archive-directory request")
        return self.routes

    def fetch_archive_year(
        self,
        year: int,
        *,
        source_url: str | None = None,
    ) -> md.MarylandBusinessOpinionIndex:
        self.archive_calls.append((year, source_url))
        return self.archives[year]

    def fetch_document(self, source_url: str) -> md.MarylandBusinessDocument:
        if self.document is None:
            raise AssertionError("unexpected publication-document request")
        return self.document

    def close(self) -> None:
        self.closed = True


def _parse(*values: str) -> argparse.Namespace:
    return md.build_parser().parse_args(list(values))


def _routes() -> md.MarylandBusinessRoutes:
    return md.parse_archive_directory(ARCHIVE_DIRECTORY)


def _current() -> md.MarylandBusinessOpinionIndex:
    return md.parse_opinion_page(CURRENT, source_url=md.CURRENT_URL)


def _archive_2008() -> md.MarylandBusinessOpinionIndex:
    return md.parse_opinion_page(
        ARCHIVE_2008,
        source_url=f"{md.ARCHIVE_INDEX_URL}2008",
        expected_publication_year=2008,
    )


def _archive_2003() -> md.MarylandBusinessOpinionIndex:
    return md.parse_opinion_page(
        ARCHIVE_2003,
        source_url=f"{md.ARCHIVE_INDEX_URL}2003",
        expected_publication_year=2003,
    )


def _document() -> md.MarylandBusinessDocument:
    url = (
        f"{md.BASE_URL}/sites/default/files/import/businesstech/"
        "opinions/2025/mdbt3-25.pdf"
    )
    return md.MarylandBusinessDocument(
        source_url=url,
        content=PDF_BYTES,
        media_type="application/pdf",
        sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
    )


def test_source_identity_and_coverage_match_verified_routes() -> None:
    assert md.SOURCE_ID == "us-md-business-technology-opinions"
    assert md.SOURCE_METADATA.source_id == md.SOURCE_ID
    assert md.CURRENT_URL.endswith("/businesstech/opinions")
    assert md.ARCHIVE_INDEX_URL.endswith("/businesstech/opinions_archive")


def test_archive_directory_discovers_source_published_routes() -> None:
    routes = _routes()

    assert routes.archive_years == (2008, 2007, 2006, 2005, 2004, 2003)
    assert routes.archive_urls[2003].endswith("/opinions_archive2003")
    assert len(routes.schema_fingerprint) == 64


def test_current_parser_preserves_duplicate_and_mismatched_source_links() -> None:
    page = _current()

    assert page.native_count == 6
    records = {record["publication_designation"]: record for record in page.records}
    shared_url = records["2025 MDBT-3"]["documents"][0]["source_url"]
    assert shared_url == records["2025 MDBT-5"]["documents"][0]["source_url"]
    assert {
        anomaly["code"] for anomaly in records["2025 MDBT-5"]["source_link_anomalies"]
    } == {
        "attachment_designation_mismatch_at_source",
        "attachment_url_shared_by_source_rows",
    }
    assert {
        anomaly["code"] for anomaly in records["2025 MDBT-3"]["source_link_anomalies"]
    } == {"attachment_url_shared_by_source_rows"}


def test_current_parser_keeps_source_omissions_and_path_states() -> None:
    records = {
        record["publication_designation"]: record for record in _current().records
    }

    assert records["2015 MDBT-3"]["filed_date"] is None
    assert records["2015 MDBT-3"]["source_omissions"] == ["filed_date"]
    assert records["2009 MDBT-4"]["case_number"] is None
    assert records["2009 MDBT-4"]["case_canonical_ref"] is None
    assert "case_number" in records["2009 MDBT-4"]["source_omissions"]
    path_codes = {
        anomaly["code"] for anomaly in records["2018 MDBT-2"]["source_link_anomalies"]
    }
    assert path_codes == {"duplicated_path_segment_at_source"}


def test_missing_publication_number_is_not_inferred_from_filename() -> None:
    record = next(
        record
        for record in _current().records
        if record["publication_designation"] == "2016 MDBT"
    )

    assert record["publication_number"] is None
    assert record["publication_designation_at_source"] == "2016 MDBT"
    assert {anomaly["code"] for anomaly in record["source_link_anomalies"]} == {
        "publication_number_omitted_at_source"
    }


@pytest.mark.parametrize(
    ("url", "publication_year", "publication_number", "expected_codes"),
    [
        (
            "/sites/default/files/import/businesstech/pdfs/mdbt201402.pdf",
            2014,
            2,
            set(),
        ),
        (
            "/sites/default/files/import/businesstech/pdfs/mdbt2013-9.pdf",
            2013,
            9,
            set(),
        ),
        (
            "/sites/default/files/import/businesstech/pdfs/mdbt3-25.pdf",
            2025,
            5,
            {"attachment_designation_mismatch_at_source"},
        ),
    ],
)
def test_attachment_filename_grammars_avoid_false_mismatch_flags(
    url: str,
    publication_year: int,
    publication_number: int,
    expected_codes: set[str],
) -> None:
    anomalies = md._attachment_anomalies(
        md._official_attachment_url(url),
        publication_year=publication_year,
        publication_number=publication_number,
    )

    assert {anomaly["code"] for anomaly in anomalies} == expected_codes


def test_archive_parser_retains_multiple_document_roles_and_formats() -> None:
    records = {
        record["publication_designation"]: record for record in _archive_2008().records
    }
    record = records["2008 MDBT-4"]

    assert record["document_types"] == ["opinion", "order"]
    assert [document["file_format"] for document in record["documents"]] == [
        "wpd",
        "pdf",
        "wpd",
        "pdf",
    ]
    assert records["2008 MDBT-5"]["filed_date"] is None


def test_old_archive_parser_preserves_counsel_and_nonmatching_filing_year() -> None:
    records = {
        record["publication_designation"]: record for record in _archive_2003().records
    }
    dotson = records["2003 MDBT-11"]
    tomran = records["2003 MDBT-3"]

    assert dotson["court"]["name"] == "Circuit Court for Prince George's County"
    assert dotson["counsel"] == "F. Paul Bland, Jr.; Bruce J. Marcus"
    assert dotson["document_types"] == ["opinion", "synopsis"]
    assert tomran["publication_year"] == 2003
    assert tomran["filed_date"] == "2002-12-30"
    assert tomran["date_precision"] == "day"
    assert tomran["source_notes"] == ["aff'd, 159 Md.App. 706, 862 A.2d 453 (2004)"]


def test_archive_context_supplies_omitted_publication_year_and_month_date() -> None:
    page = md.parse_opinion_page(
        ARCHIVE_IRREGULAR,
        source_url=f"{md.ARCHIVE_INDEX_URL}2004",
        expected_publication_year=2004,
    )
    record = page.records[0]

    assert record["publication_designation_at_source"] == "MDBT10"
    assert record["publication_designation"] == "2004 MDBT-10"
    assert record["case_number"] == "24-C-03-001111"
    assert record["case_numbers_at_source"] == [
        "24-C-03-001111",
        "24-C-03-001112",
    ]
    assert record["filed_date_at_source"] == "4/04"
    assert record["filed_date"] == "2004-04"
    assert record["date_precision"] == "month"


def test_left_cell_classifier_handles_judge_before_case_number() -> None:
    page = md.parse_opinion_page(
        ARCHIVE_2007_SWAPPED,
        source_url=f"{md.ARCHIVE_INDEX_URL}2007",
        expected_publication_year=2007,
    )
    record = page.records[0]

    assert record["judge"] == "J. Sweeney"
    assert record["case_number"] == "13-C-06-067710"
    assert record["filed_date"] == "2007-06-26"


def test_search_date_bounds_overlap_month_precision_and_exclude_missing_dates() -> None:
    selection = {
        "year": None,
        "all_pages": True,
        "query": None,
        "case_number": None,
        "county": None,
        "judge": None,
        "document_type": None,
        "filed_from": "2004-04-15",
        "filed_to": "2004-04-20",
    }
    record = md.parse_opinion_page(
        ARCHIVE_IRREGULAR,
        source_url=f"{md.ARCHIVE_INDEX_URL}2004",
        expected_publication_year=2004,
    ).records[0]
    missing_date = next(
        value
        for value in _current().records
        if value["publication_designation"] == "2015 MDBT-3"
    )

    assert md._record_matches(record, selection=selection)
    assert not md._record_matches(missing_date, selection=selection)


def test_county_filter_compares_normalized_source_and_router_tokens() -> None:
    record = _archive_2003().records[0]
    selection = {
        "year": None,
        "all_pages": True,
        "query": None,
        "case_number": None,
        "county": "prince george s",
        "judge": None,
        "document_type": None,
        "filed_from": None,
        "filed_to": None,
    }

    assert record["court"]["county"] == "Prince George's"
    assert md._record_matches(record, selection=selection)


def test_table_header_drift_is_explicit_source_changed_error() -> None:
    with pytest.raises(
        md.MarylandBusinessOpinionsSourceChangedError,
        match="table headers changed",
    ):
        md.parse_opinion_page(SOURCE_CHANGED, source_url=md.CURRENT_URL)


def test_official_attachment_validator_keeps_exact_paths_and_rejects_other_hosts() -> (
    None
):
    doubled = (
        "/sites/default/files/files/import/businesstech/opinions/2018/mdbt2-18.pdf"
    )
    assert "/files/files/" in md._official_attachment_url(doubled)

    with pytest.raises(md.MarylandBusinessOpinionsSelectionError):
        md._official_attachment_url(
            "https://example.org/sites/default/files/import/businesstech/a.pdf"
        )


def test_client_validates_pdf_signature_and_classifies_429() -> None:
    document_url = (
        f"{md.BASE_URL}/sites/default/files/import/businesstech/"
        "opinions/2025/mdbt3-25.pdf"
    )
    session = FakeSession(
        [
            FakeResponse(
                content=PDF_BYTES,
                url=document_url,
                headers={"Content-Type": "application/pdf"},
            ),
            FakeResponse(status_code=429, url=md.CURRENT_URL),
        ]
    )
    client = md.MarylandBusinessOpinionsClient(
        session=session,
        minimum_interval=0,
        retry_policy=md.RetryPolicy(max_attempts=1),
    )

    document = client.fetch_document(document_url)
    assert document.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    with pytest.raises(md.MarylandBusinessOpinionsError) as caught:
        client.fetch_current()
    assert caught.value.status is ResultStatus.RATE_LIMITED


def test_manifest_records_complementary_routes_and_operation_states() -> None:
    result = md.execute(_parse("manifest"), log_results=False)
    manifest = result.records[0]
    related = {route["source_id"]: route for route in manifest["related_source_routes"]}

    assert result.status is ResultStatus.OK
    assert related["us-md-case-search"]["operation_state"] == "interactive_captcha"
    assert related["us-md-appellate-opinions"]["operation_state"] == "integrated"
    assert (
        related["us-md-circuit-clerk-records"]["operation_state"]
        == "court_specific_request_route"
    )


def test_search_filters_one_discovered_archive_year() -> None:
    client = FakeClient(
        routes=_routes(),
        archives={2008: _archive_2008()},
    )
    result = md.execute(
        _parse(
            "search",
            "--year",
            "2008",
            "--document-type",
            "order",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert [record["publication_designation"] for record in result.records] == [
        "2008 MDBT-4"
    ]
    assert client.archive_calls == [(2008, f"{md.ARCHIVE_INDEX_URL}2008")]


def test_all_page_search_uses_stable_anchor_cursor_without_deduping_cases() -> None:
    client = FakeClient(
        current=_current(),
        routes=_routes(),
        archives={
            2008: _archive_2008(),
            2007: md.parse_opinion_page(
                ARCHIVE_2007_SWAPPED,
                source_url=f"{md.ARCHIVE_INDEX_URL}2007",
                expected_publication_year=2007,
            ),
            2006: _archive_2008(),
            2005: _archive_2008(),
            2004: md.parse_opinion_page(
                ARCHIVE_IRREGULAR,
                source_url=f"{md.ARCHIVE_INDEX_URL}2004",
                expected_publication_year=2004,
            ),
            2003: _archive_2003(),
        },
    )
    first = md.execute(
        _parse("search", "--all-pages", "--limit", "3"),
        client=client,
        log_results=False,
    )
    second = md.execute(
        _parse(
            "search",
            "--all-pages",
            "--limit",
            "3",
            "--cursor",
            str(first.next_cursor),
        ),
        client=client,
        log_results=False,
    )

    assert first.next_cursor is not None
    assert first.records[-1]["publication_designation"] == "2018 MDBT-2"
    assert second.records[0]["publication_designation"] == "2016 MDBT"
    combined_refs = [
        record["canonical_ref"] for record in (*first.records, *second.records)
    ]
    assert len(combined_refs) == len(set(combined_refs))


def test_cursor_is_bound_to_filters() -> None:
    selection = {
        "year": None,
        "all_pages": False,
        "query": None,
        "case_number": None,
        "county": None,
        "judge": None,
        "document_type": None,
    }
    cursor = md._encode_cursor(
        selection_fingerprint=md._selection_fingerprint(selection),
        anchor="STATECOURT:fixture",
    )
    changed = {**selection, "county": "Montgomery"}

    with pytest.raises(
        md.MarylandBusinessOpinionsSelectionError,
        match="different publication search",
    ):
        md._decode_cursor(
            cursor,
            selection_fingerprint=md._selection_fingerprint(changed),
        )


def test_routes_and_probe_use_shared_public_records_envelope() -> None:
    client = FakeClient(
        current=_current(),
        routes=_routes(),
        archives={2003: _archive_2003()},
        document=_document(),
    )
    routes_result = md.execute(
        _parse("routes"),
        client=client,
        log_results=False,
    )
    probe_result = md.execute(
        _parse("probe"),
        client=client,
        log_results=False,
    )

    validate_envelope(routes_result.to_dict())
    validate_envelope(probe_result.to_dict())
    probe = probe_result.records[0]
    assert probe["archive_years"] == (2008, 2007, 2006, 2005, 2004, 2003)
    assert probe["current_publication_count"] == 6
    assert probe["archive_sample_year"] == 2003
    assert probe["pdf_size_bytes"] == len(PDF_BYTES)


def test_source_changed_result_is_not_reported_as_no_results() -> None:
    class ChangedClient:
        def fetch_current(self) -> md.MarylandBusinessOpinionIndex:
            raise md.MarylandBusinessOpinionsSourceChangedError(
                "fixture_schema_changed",
                "fixture schema changed",
            )

    result = md.execute(
        _parse("search"),
        client=ChangedClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.records == ()
    assert result.errors[0].code == "fixture_schema_changed"
