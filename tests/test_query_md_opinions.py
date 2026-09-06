from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_md_opinions as md
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/md_opinions")
REPORTED_LANDING = (FIXTURE_DIR / "reported_landing.html").read_text()
REPORTED_RESULTS = (FIXTURE_DIR / "reported_results.html").read_text()
REPORTED_CHANGED = (FIXTURE_DIR / "reported_source_changed.html").read_text()
UNREPORTED_DIRECTORY = (FIXTURE_DIR / "unreported_directory.html").read_text()
UNREPORTED_MONTH = (FIXTURE_DIR / "unreported_month.html").read_text()
UNREPORTED_METADATA_ONLY = (FIXTURE_DIR / "unreported_metadata_only.html").read_text()
UNREPORTED_CHANGED = (FIXTURE_DIR / "unreported_source_changed.html").read_text()
PDF_BYTES = b"%PDF-1.7\nfixture Maryland opinion\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    content: bytes = b""
    url: str = md.REPORTED_INDEX_URL
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
        reported: md.MarylandOpinionIndex | None = None,
        directory: md.MarylandUnreportedDirectory | None = None,
        months: Mapping[str, md.MarylandOpinionIndex] | None = None,
        landing: md.MarylandReportedLanding | None = None,
        pdf: md.MarylandOpinionPDF | None = None,
    ) -> None:
        self.reported = reported
        self.directory = directory
        self.months = dict(months or {})
        self.landing = landing
        self.pdf = pdf
        self.reported_calls: list[dict[str, str]] = []
        self.month_calls: list[str] = []
        self.closed = False

    def fetch_reported_landing(self) -> md.MarylandReportedLanding:
        if self.landing is None:
            raise AssertionError("unexpected reported landing request")
        return self.landing

    def fetch_unreported_directory(self) -> md.MarylandUnreportedDirectory:
        if self.directory is None:
            raise AssertionError("unexpected unreported directory request")
        return self.directory

    def fetch_reported(
        self,
        *,
        native_court: str,
        year: str,
        native_order: str,
    ) -> md.MarylandOpinionIndex:
        self.reported_calls.append(
            {
                "native_court": native_court,
                "year": year,
                "native_order": native_order,
            }
        )
        if self.reported is None:
            raise AssertionError("unexpected reported index request")
        return self.reported

    def fetch_unreported_month(self, month: str) -> md.MarylandOpinionIndex:
        self.month_calls.append(month)
        return self.months[month]

    def fetch_pdf(self, source_url: str) -> md.MarylandOpinionPDF:
        if self.pdf is None:
            raise AssertionError("unexpected PDF request")
        return self.pdf

    def close(self) -> None:
        self.closed = True


def _parse(*values: str) -> argparse.Namespace:
    return md.build_parser().parse_args(list(values))


def _reported_index() -> md.MarylandOpinionIndex:
    return md.parse_reported_results(
        REPORTED_RESULTS,
        source_url=(f"{md.REPORTED_RESULTS_URL}?court=both&year=2026&order=bydate"),
        native_court_filter="both",
    )


def _directory() -> md.MarylandUnreportedDirectory:
    return md.parse_unreported_directory(UNREPORTED_DIRECTORY)


def _unreported_index() -> md.MarylandOpinionIndex:
    return md.parse_unreported_month(
        UNREPORTED_MONTH,
        month="202607",
        source_url=f"{md.UNREPORTED_MONTH_PREFIX}/202607",
    )


def _pdf(url: str | None = None) -> md.MarylandOpinionPDF:
    source_url = url or (
        f"{md.BASE_URL}/sites/default/files/unreported-opinions/1539s24.pdf"
    )
    return md.MarylandOpinionPDF(
        source_url=source_url,
        content=PDF_BYTES,
        media_type="application/pdf",
        sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
    )


def _older_index() -> md.MarylandOpinionIndex:
    record = dict(_unreported_index().records[0])
    record.update(
        {
            "canonical_ref": "STATECOURT:older-record",
            "evidence_ref": "STATECOURT:older-record",
            "decision_date": "2026-06-18",
            "filed_date": "2026-06-18",
            "source_month": "2026-06",
        }
    )
    return md.MarylandOpinionIndex(
        records=(record,),
        source_url=f"{md.UNREPORTED_MONTH_PREFIX}/202606",
        schema_fingerprint="b" * 64,
        collection="unreported",
        native_count=1,
    )


def test_source_identity_matches_documented_maryland_route() -> None:
    assert md.SOURCE_ID == "us-md-appellate-opinions"
    assert md.SOURCE_METADATA.source_id == md.SOURCE_ID
    assert md.REPORTED_RESULTS_URL.endswith("/cgi-bin/indexlist.pl")
    assert md.UNREPORTED_MONTH_PREFIX.endswith("/appellate/unreportedopinions/list")


def test_route_parsers_preserve_distinct_year_and_month_coverage() -> None:
    landing = md.parse_reported_landing(REPORTED_LANDING)
    directory = _directory()

    assert landing.years == (2026, 2025, 1995)
    assert landing.native_courts == ("both", "coa", "cosa")
    assert landing.native_orders == (
        "bycase",
        "bycite",
        "bydate",
        "byjudge",
        "bytitle",
    )
    assert directory.months == (
        "202607",
        "202606",
        "201505",
        "201504",
        "200102",
    )
    assert len(landing.schema_fingerprint) == 64
    assert len(directory.schema_fingerprint) == 64


def test_reported_parser_handles_legacy_unclosed_cells_and_corrections() -> None:
    index = _reported_index()

    assert index.native_count == 3
    first = index.records[0]
    assert first["display_case_number"] == "42/25"
    assert first["decision_date"] == "2026-07-27"
    assert first["correction_dates"] == ["2026-07-21"]
    assert first["filing_note"] == "corrected 2026-07-21"
    assert first["citation_status"] == "slip_opinion"
    assert first["court"]["court_key"] == "supreme"
    assert first["court"]["name_at_filing"] == "Supreme Court of Maryland"
    assert first["native_document_id"] == "coa/2026/42a25.pdf"
    assert first["document"]["document_type"] == "appellate_opinion"
    assert first["provenance"]["native_line_number"] == 1


def test_reported_parser_distinguishes_orders_and_historical_names() -> None:
    records = _reported_index().records
    order = records[1]
    historical = records[2]

    assert order["publication_kind"] == "appellate_order"
    assert order["document"]["document_type"] == "appellate_order"
    assert historical["citation_status"] == "reported_citation"
    assert historical["court"]["name_at_filing"] == (
        "Court of Special Appeals of Maryland"
    )
    assert historical["electronic_text_status"] == (
        "online_reported_copy_bound_reporter_controls"
    )


def test_reported_identity_survives_citation_and_correction_updates() -> None:
    original = _reported_index().records[0]
    changed = md.parse_reported_results(
        REPORTED_RESULTS.replace(
            "slip.op<td><font>2026-07-27 corrected 2026-07-21",
            "500 Md. 1<td><font>2026-07-27 corrected 2026-07-29",
            1,
        ),
        source_url=md.REPORTED_RESULTS_URL,
        native_court_filter="both",
    ).records[0]

    assert changed["citation"] == "500 Md. 1"
    assert changed["correction_dates"] == ["2026-07-29"]
    assert changed["canonical_ref"] == original["canonical_ref"]
    assert changed["native_document_id"] == original["native_document_id"]


def test_reported_schema_and_completeness_changes_are_explicit() -> None:
    with pytest.raises(md.MarylandOpinionsSourceChangedError) as headers:
        md.parse_reported_results(
            REPORTED_CHANGED,
            source_url=md.REPORTED_RESULTS_URL,
            native_court_filter="both",
        )
    assert headers.value.code == "reported_headers_changed"

    with pytest.raises(md.MarylandOpinionsSourceChangedError) as sequence:
        md.parse_reported_results(
            REPORTED_RESULTS.replace("<font>3\n", "<font>4\n"),
            source_url=md.REPORTED_RESULTS_URL,
            native_court_filter="both",
        )
    assert sequence.value.code == "reported_line_sequence_changed"


def test_unreported_parser_preserves_parties_pdf_and_case_identity() -> None:
    index = _unreported_index()
    first, second = index.records

    assert index.native_count == 2
    assert first["display_case_number"] == "1539/24"
    assert first["caption"] == "Brunson, Shawn Lee v. State"
    assert [party["role"] for party in first["parties"]] == [
        "appellant_or_first_party",
        "appellee_or_second_party",
    ]
    assert first["full_text_status"] == "available"
    assert first["pdf_url"].endswith("/1539s24.pdf")
    assert first["court"]["court_key"] == "appellate"
    assert second["court"]["court_key"] == "supreme"
    assert first["case_canonical_ref"] != first["canonical_ref"]


def test_unreported_pre_may_2015_rows_remain_searchable_metadata() -> None:
    index = md.parse_unreported_month(
        UNREPORTED_METADATA_ONLY,
        month="201504",
        source_url=f"{md.UNREPORTED_MONTH_PREFIX}/201504",
    )
    record = index.records[0]

    assert record["display_case_number"] == "1002/14"
    assert record["full_text_status"] == "metadata_only"
    assert record["pdf_url"] is None
    assert record["document"] is None
    assert record["court"]["name_at_filing"] == "Court of Special Appeals"
    assert record["court"]["name"] == "Appellate Court of Maryland"


def test_unreported_header_and_month_mismatch_are_explicit() -> None:
    with pytest.raises(md.MarylandOpinionsSourceChangedError) as headers:
        md.parse_unreported_month(
            UNREPORTED_CHANGED,
            month="202607",
            source_url=f"{md.UNREPORTED_MONTH_PREFIX}/202607",
        )
    assert headers.value.code == "unreported_headers_changed"

    with pytest.raises(md.MarylandOpinionsSourceChangedError) as month:
        md.parse_unreported_month(
            UNREPORTED_MONTH,
            month="202606",
            source_url=f"{md.UNREPORTED_MONTH_PREFIX}/202606",
        )
    assert month.value.code == "unreported_month_mismatch"


def test_client_uses_exact_native_cgi_parameters_and_month_route() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=REPORTED_RESULTS,
                url=md.REPORTED_RESULTS_URL,
            ),
            FakeResponse(
                text=UNREPORTED_MONTH,
                url=f"{md.UNREPORTED_MONTH_PREFIX}/202607",
            ),
        ]
    )
    client = md.MarylandOpinionsClient(
        session=session,
        minimum_interval=0,
    )

    client.fetch_reported(
        native_court="both",
        year="2026",
        native_order="bycase",
    )
    client.fetch_unreported_month("202607")

    reported_url, reported_kwargs = session.calls[0]
    assert reported_url == md.REPORTED_RESULTS_URL
    assert reported_kwargs["params"] == {
        "court": "both",
        "year": "2026",
        "order": "bycase",
        "submit": "Submit",
    }
    assert session.calls[1][0].endswith("/list/202607")
    assert "Mozilla/5.0" in session.headers["User-Agent"]


def test_pdf_validation_accepts_source_files_and_rejects_other_hosts() -> None:
    session = FakeSession(
        [
            FakeResponse(
                content=PDF_BYTES,
                url=(
                    f"{md.BASE_URL}/sites/default/files/unreported-opinions/1539s24.pdf"
                ),
                headers={"Content-Type": "application/pdf"},
            )
        ]
    )
    client = md.MarylandOpinionsClient(
        session=session,
        minimum_interval=0,
    )

    pdf = client.fetch_pdf(
        f"{md.BASE_URL}/sites/default/files/unreported-opinions/1539s24.pdf"
    )
    assert pdf.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()

    with pytest.raises(md.MarylandOpinionsSelectionError):
        md._official_pdf_url("https://example.com/opinion.pdf")


def test_reported_cursor_is_query_bound_and_anchor_based() -> None:
    index = _reported_index()
    selection = {
        "collection": "reported",
        "court": "both",
        "native_court": "both",
        "year": "2026",
        "order": "date",
        "native_order": "bydate",
        "query": None,
    }
    fingerprint = md._selection_fingerprint("reported", selection)
    first, token = md._page_reported_records(
        index,
        selection=selection,
        cursor=None,
        limit=1,
        selection_fingerprint=fingerprint,
    )
    assert len(first) == 1
    assert token is not None

    cursor = md._decode_cursor(
        token,
        operation="reported",
        selection_fingerprint=fingerprint,
    )
    second, second_token = md._page_reported_records(
        index,
        selection=selection,
        cursor=cursor,
        limit=1,
        selection_fingerprint=fingerprint,
    )
    assert second[0]["canonical_ref"] == index.records[1]["canonical_ref"]
    assert second_token is not None

    with pytest.raises(md.MarylandOpinionsSelectionError) as mismatch:
        md._decode_cursor(
            token,
            operation="reported",
            selection_fingerprint="different",
        )
    assert mismatch.value.code == "cursor_query_mismatch"


def test_unreported_cursor_continues_across_complete_month_indexes() -> None:
    months = ("202607", "202606")
    client = FakeClient(
        months={
            "202607": _unreported_index(),
            "202606": _older_index(),
        }
    )
    selection = {
        "collection": "unreported",
        "court": "both",
        "months": list(months),
        "date_from": None,
        "date_to": None,
        "query": None,
    }
    fingerprint = md._selection_fingerprint("unreported", selection)
    records, token, urls, schemas = md._collect_unreported(
        client,
        months=months,
        selection=selection,
        cursor=None,
        limit=2,
        selection_fingerprint=fingerprint,
    )
    assert len(records) == 2
    assert token is not None
    assert len(urls) == 1
    assert len(schemas) == 1

    cursor = md._decode_cursor(
        token,
        operation="unreported",
        selection_fingerprint=fingerprint,
    )
    remaining, final_token, _, _ = md._collect_unreported(
        client,
        months=months,
        selection=selection,
        cursor=cursor,
        limit=2,
        selection_fingerprint=fingerprint,
    )
    assert [record["canonical_ref"] for record in remaining] == [
        "STATECOURT:older-record"
    ]
    assert final_token is None


def test_execute_reported_filters_metadata_and_emits_valid_envelope() -> None:
    client = FakeClient(reported=_reported_index())
    result = md.execute(
        _parse(
            "reported",
            "--year",
            "2026",
            "--query",
            "Harbor Properties",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    assert result.records[0]["display_case_number"] == "0123/16"
    assert client.reported_calls == [
        {
            "native_court": "both",
            "year": "2026",
            "native_order": "bydate",
        }
    ]
    lineage = validate_envelope(result.to_dict())
    assert lineage["source_id"] == md.SOURCE_ID


def test_case_number_matching_does_not_search_pdf_path_fragments() -> None:
    records = _reported_index().records

    assert md._record_matches(
        records[0],
        query_text="42/25",
        court="both",
        match_mode="case_number",
    )
    assert not md._record_matches(
        records[0],
        query_text="26/42",
        court="both",
        match_mode="case_number",
    )


def test_execute_unreported_defaults_to_latest_discovered_month() -> None:
    directory = _directory()
    client = FakeClient(
        directory=directory,
        months={"202607": _unreported_index()},
    )
    result = md.execute(
        _parse("unreported"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 2
    assert client.month_calls == ["202607"]
    assert result.query.query.parameters["months"] == ("202607",)


def test_manifest_maps_accessible_complements_without_conflating_roles() -> None:
    result = md.execute(
        _parse("manifest"),
        client=FakeClient(),
        log_results=False,
    )
    manifest = result.records[0]
    routes = {route["source_id"]: route for route in manifest["related_source_routes"]}

    assert result.status is ResultStatus.OK
    assert routes["us-md-case-search"]["operation_state"] == ("interactive_captcha")
    assert routes["us-md-mdec-public-cases"]["role"] == (
        "rolling_recent_case_creation_feed"
    )
    assert manifest["identity"]["reported_document"] == ("court/year/PDF filename")


def test_probe_checks_both_collections_and_one_pdf() -> None:
    reported = _reported_index()
    unreported = _unreported_index()
    landing = md.parse_reported_landing(REPORTED_LANDING)
    directory = _directory()
    pdf_url = str(unreported.records[0]["pdf_url"])
    client = FakeClient(
        reported=reported,
        directory=directory,
        months={"202607": unreported},
        landing=landing,
        pdf=_pdf(pdf_url),
    )

    result = md.execute(
        _parse("probe"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["reported_sample_count"] == 3
    assert probe["unreported_sample_count"] == 2
    assert probe["pdf_size_bytes"] == len(PDF_BYTES)
    assert probe["pdf_media_type"] == "application/pdf"
