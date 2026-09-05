from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_wisconsin_opinions as wi
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/wisconsin_opinions"
)
APPEALS_HTML = (FIXTURE_DIR / "metadata-appeals.html").read_text(
    encoding="utf-8"
)
ORDERS_HTML = (FIXTURE_DIR / "metadata-orders.html").read_text(
    encoding="utf-8"
)
EMPTY_HTML = (FIXTURE_DIR / "metadata-empty.html").read_text(
    encoding="utf-8"
)
KEYWORD_HTML = (FIXTURE_DIR / "keyword-supreme.html").read_text(
    encoding="utf-8"
)
KEYWORD_EMPTY_HTML = (FIXTURE_DIR / "keyword-empty.html").read_text(
    encoding="utf-8"
)
FEED_XML = (FIXTURE_DIR / "feed-appeals.xml").read_bytes()
TAXONOMY_HTML = (FIXTURE_DIR / "taxonomy-appeals.html").read_text(
    encoding="utf-8"
)
PDF_BYTES = b"%PDF-1.7\nWisconsin opinion fixture\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    content: bytes = b""
    url: str = wi.BASE_URL
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
            raise AssertionError("unexpected Wisconsin Court System request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class TaxonomyClient:
    def fetch_taxonomy(
        self,
        collection: str,
    ) -> tuple[list[dict[str, Any]], str]:
        return (
            wi.parse_taxonomy(
                TAXONOMY_HTML,
                collection=collection,
                source_url=wi.COLLECTIONS[collection].form_url,
            ),
            wi.COLLECTIONS[collection].form_url,
        )


def _parse(*values: str) -> argparse.Namespace:
    return wi.build_parser().parse_args(list(values))


def test_source_exposes_distinct_official_record_roles() -> None:
    assert wi.SOURCE_METADATA.source_id == "us-wi-court-opinions"
    assert set(wi.COLLECTIONS) == {
        "supreme-opinions",
        "supreme-orders",
        "appeals-opinions",
        "appeals-summary",
    }
    assert set(wi.FULLTEXT_COLLECTIONS) == {"supreme", "appeals"}
    assert wi.FEED_URLS["appeals"].endswith("/rss/caopin.jsp")


def test_appeals_parser_preserves_pagination_annotations_and_join_keys() -> None:
    page = wi.parse_metadata_page(
        APPEALS_HTML,
        collection="appeals-opinions",
        source_url=(
            f"{wi.COLLECTIONS['appeals-opinions'].endpoint}"
            "?party_name=Alliance&page=1"
        ),
        requested_page=1,
    )

    assert page.total_pages == 2
    assert page.next_page == 2
    assert len(page.records) == 2
    recommended, withdrawn = page.records
    assert recommended["raw_case_number"] == "2024AP002484"
    assert recommended["publication_status"] == "recommended_for_publication"
    assert recommended["source_annotations"] == [
        "Recommended for Publication"
    ]
    assert recommended["district"] == "4"
    assert recommended["county"] == "Dane"
    assert recommended["join_keys"] == {
        "appellate_case_number": "2024AP002484",
        "native_document_id": "1149000",
        "native_document_id_type": "seq_no",
    }
    assert recommended["canonical_ref"].startswith("STATECOURT:")
    assert withdrawn["raw_case_number"] == "2024AP001000-CR"
    assert (
        withdrawn["normalized_appellate_case_number"]
        == "2024AP001000"
    )
    assert withdrawn["publication_status"] == "withdrawn"
    assert withdrawn["withdrawn_date"] == "2026-06-18"
    assert len(page.schema_fingerprint) == 64


def test_supreme_order_parser_uses_doc_id_and_order_type() -> None:
    page = wi.parse_metadata_page(
        ORDERS_HTML,
        collection="supreme-orders",
        source_url=wi.COLLECTIONS["supreme-orders"].endpoint,
        requested_page=1,
    )

    assert page.next_page is None
    assert len(page.records) == 1
    record = page.records[0]
    assert record["record_kind"] == "appellate_order_index"
    assert record["document"]["document_type"] == "supreme_court_order"
    assert record["document"]["native_document_id"] == "1144136"
    assert record["document"]["native_document_id_type"] == "doc_id"
    assert record["court"]["court_id"] == wi.SUPREME_COURT_ID


def test_explicit_empty_state_is_not_a_transport_failure() -> None:
    page = wi.parse_metadata_page(
        EMPTY_HTML,
        collection="appeals-opinions",
        source_url=wi.COLLECTIONS["appeals-opinions"].endpoint,
        requested_page=1,
    )

    assert page.records == ()
    assert page.total_pages == 0
    assert page.next_page is None


def test_header_change_is_reported_as_source_changed() -> None:
    changed = APPEALS_HTML.replace(
        "<th>County</th>",
        "<th>Originating county</th>",
    )

    with pytest.raises(wi.WisconsinOpinionsSourceChangedError) as raised:
        wi.parse_metadata_page(
            changed,
            collection="appeals-opinions",
            source_url=wi.COLLECTIONS["appeals-opinions"].endpoint,
            requested_page=1,
        )

    assert raised.value.code == "table_headers_changed"
    assert raised.value.status is ResultStatus.SOURCE_CHANGED


def test_fulltext_parser_preserves_highlights_formats_and_native_offset() -> None:
    page = wi.parse_fulltext_page(
        KEYWORD_HTML,
        court="supreme",
        query_text='"Wisconsin Voter Alliance"',
        source_url=(
            f"{wi.SEARCH_URL}?q=Wisconsin+Voter+Alliance"
            "&fq=%2Bid%3A*%2Fsc%2Fopinion%2F*"
        ),
        requested_page=1,
    )

    assert page.total_items == 12
    assert page.total_pages == 2
    assert page.next_offset == 10
    assert len(page.records) == 2
    pdf_hit, html_hit = page.records
    assert "WISCONSIN VOTER ALLIANCE" in pdf_hit["snippet"]
    assert pdf_hit["native_document_id"] == "903123"
    assert pdf_hit["indexed_date"] == "2025-03-04"
    assert pdf_hit["mime_type"] == "application/pdf"
    assert html_hit["native_document_id"] == "51544"
    assert html_hit["mime_type"] == "text/html"
    assert pdf_hit["canonical_ref"] != html_hit["canonical_ref"]


def test_fulltext_explicit_empty_state_is_authoritative() -> None:
    page = wi.parse_fulltext_page(
        KEYWORD_EMPTY_HTML,
        court="supreme",
        query_text='"not present"',
        source_url=f"{wi.SEARCH_URL}?q=not+present",
        requested_page=1,
    )

    assert page.records == ()
    assert page.total_items == 0
    assert page.total_pages == 0
    assert page.next_offset is None


def test_feed_identity_comes_from_route_while_native_author_is_preserved() -> None:
    records = wi.parse_feed(
        FEED_XML,
        court="appeals",
        source_url=wi.FEED_URLS["appeals"],
    )

    assert len(records) == 1
    record = records[0]
    assert record["native_author"] == "Wisconsin Supreme Court"
    assert record["court"]["court_id"] == wi.APPEALS_COURT_ID
    assert record["court_identity_basis"] == "feed_route"
    assert record["raw_case_number"] == "2024AP002484"
    assert record["publication_status"] == "recommended_for_publication"
    assert record["index_url"].startswith("https://www.wicourts.gov/")


def test_taxonomy_resolves_labels_and_native_values_without_static_table() -> None:
    records = wi.parse_taxonomy(
        TAXONOMY_HTML,
        collection="appeals-opinions",
        source_url=wi.COLLECTIONS["appeals-opinions"].form_url,
    )

    assert (
        wi._taxonomy_value(
            records,
            field_name="trial_county",
            requested="Dane",
        )
        == "13"
    )
    assert (
        wi._taxonomy_value(
            records,
            field_name="disp_code",
            requested="AFFD",
        )
        == "AFFD"
    )
    args = _parse(
        "search",
        "--collection",
        "appeals-opinions",
        "--county",
        "Dane",
        "--disposition",
        "Affirmed",
        "--date-from",
        "2026-07-01",
        "--date-to",
        "07/31/2026",
    )
    selection, artifacts = wi._metadata_selection(
        args,
        client=TaxonomyClient(),
    )
    assert selection["trial_county"] == "13"
    assert selection["disp_code"] == "AFFD"
    assert selection["begin_date"] == "07/01/2026"
    assert selection["end_date"] == "07/31/2026"
    assert artifacts == (
        wi.COLLECTIONS["appeals-opinions"].form_url,
    )


def test_collection_specific_filter_error_is_explicit() -> None:
    args = _parse(
        "search",
        "--collection",
        "appeals-summary",
        "--county",
        "Dane",
    )

    with pytest.raises(wi.WisconsinOpinionsSelectionError) as raised:
        wi._metadata_selection(args, client=TaxonomyClient())

    assert raised.value.code == "unsupported_collection_filter"


def test_metadata_client_uses_one_page_parameter_and_summary_discriminator() -> None:
    response = FakeResponse(
        text=APPEALS_HTML,
        content=APPEALS_HTML.encode(),
        url=(
            f"{wi.COLLECTIONS['appeals-summary'].endpoint}"
            "?noticeTypeCode=SMD&page=1"
        ),
    )
    session = FakeSession([response])
    client = wi.WisconsinOpinionsClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    page = client.fetch_metadata_page(
        "appeals-summary",
        {},
        page_number=1,
    )

    assert page.page_number == 1
    params = session.calls[0][1]["params"]
    assert params["noticeTypeCode"] == "SMD"
    assert params["page"] == 1


def test_pdf_download_validates_signature_hash_and_official_identity() -> None:
    response = FakeResponse(
        content=PDF_BYTES,
        url=wi.PROBE_APPEALS_PDF_URL,
        headers={"Content-Type": "application/pdf"},
    )
    session = FakeSession([response])
    client = wi.WisconsinOpinionsClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    pdf = client.fetch_pdf(wi.PROBE_APPEALS_PDF_URL)

    assert pdf.native_document_id == wi.PROBE_APPEALS_DOCUMENT_ID
    assert pdf.native_document_id_type == "seq_no"
    assert pdf.sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    with pytest.raises(wi.WisconsinOpinionsSelectionError):
        wi._official_pdf_url("https://example.com/opinion.pdf")


def test_routes_map_record_roles_and_case_join_keys() -> None:
    routes = wi.source_routes("2025AP000482")
    by_id = {record["source_id"]: record for record in routes}

    assert by_id[wi.SOURCE_ID]["relationship"] == "authoritative_primary"
    assert by_id["us-wi-wscca-public"]["case_url"].endswith(
        "/case/2025AP000482"
    )
    assert "linked_circuit_case_number_from_wscca" in by_id[
        "us-wi-wcca-public"
    ]["join_keys"]
    assert by_id["us-courtlistener-api"]["relationship"] == "searchable_mirror"
    assert "not independent corroboration" in by_id["us-courtlistener-api"][
        "evidence_note"
    ]


def test_routes_execute_emits_valid_public_records_envelope() -> None:
    result = wi.execute(
        _parse("routes", "--case-number", "2025AP000482"),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    lineage = validate_envelope(result.to_dict())
    assert lineage["status"] == "ok"
    assert lineage["source_id"] == wi.SOURCE_ID
    assert len(result.records) == 7
