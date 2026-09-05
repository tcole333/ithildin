from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_colorado_opinions
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/colorado_opinions")


def _json_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _text_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        *,
        payload: Any | None = None,
        text: str = "",
        content: bytes | None = None,
        url: str = query_colorado_opinions.SEARCH_URL,
        status_code: int = 200,
        content_type: str = "application/json; charset=utf-8",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.text = text
        self.content = (
            content if content is not None else text.encode("utf-8")
        )
        self.url = url
        self.status_code = status_code
        self.headers = {
            "Content-Type": content_type,
            **dict(headers or {}),
        }

    def json(self) -> Any:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected Colorado opinions request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _client(*responses: FakeResponse) -> query_colorado_opinions.ColoradoOpinionsClient:
    return query_colorado_opinions.ColoradoOpinionsClient(
        session=FakeSession(list(responses)),
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )


def _parse(*values: str) -> Any:
    return query_colorado_opinions.build_parser().parse_args(list(values))


def _selection(
    query_text: str = "People",
    court: str = "supreme",
) -> dict[str, str]:
    return query_colorado_opinions._search_selection(query_text, court)


def test_search_page_contract_accepts_short_page_before_exhaustion() -> None:
    page = query_colorado_opinions.parse_search_page(
        _json_fixture("search_page_1.json"),
        page_number=1,
    )

    assert page.count == 3
    assert len(page.results) == 2
    assert page.partial_results is False
    assert len(page.schema_fingerprint) == 64


def test_search_page_contract_distinguishes_source_change() -> None:
    with pytest.raises(
        query_colorado_opinions.ColoradoOpinionsSourceChangedError
    ) as error:
        query_colorado_opinions.parse_search_page(
            _json_fixture("search_source_changed.json"),
            page_number=1,
        )

    assert error.value.code == "search_fields_changed"


def test_client_uses_count_and_exhausts_short_native_pages_without_cap() -> None:
    session = FakeSession(
        [
            FakeResponse(
                payload=_json_fixture("count.json"),
                url=f"{query_colorado_opinions.COUNT_URL}?g=2",
            ),
            FakeResponse(
                payload=_json_fixture("search_page_1.json"),
                url=f"{query_colorado_opinions.SEARCH_URL}?page=1",
            ),
            FakeResponse(
                payload=_json_fixture("search_page_2_short.json"),
                url=f"{query_colorado_opinions.SEARCH_URL}?page=2",
            ),
        ]
    )
    client = query_colorado_opinions.ColoradoOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    batch = client.search(_selection())

    assert [item["id"] for item in batch.results] == [
        887202075,
        890715320,
        1041908406,
    ]
    assert batch.total_count == 3
    assert batch.pages_fetched == 2
    assert batch.next_cursor is None
    assert batch.incomplete_error is None
    assert session.calls[1][1]["params"]["page"] == "1"
    assert session.calls[2][1]["params"]["page"] == "2"


def test_limit_returns_query_bound_cursor_and_resume_finishes() -> None:
    selection = _selection()
    first = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
    )

    batch = first.search(selection, limit=1)

    assert [item["id"] for item in batch.results] == [887202075]
    assert batch.next_cursor is not None
    assert ":page:1:row:1:seen:0" in batch.next_cursor

    second = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
        FakeResponse(payload=_json_fixture("search_page_2_short.json")),
    )
    resumed = second.search(selection, cursor=batch.next_cursor)

    assert [item["id"] for item in resumed.results] == [
        890715320,
        1041908406,
    ]
    assert resumed.next_cursor is None


def test_cursor_cannot_be_reused_for_another_query() -> None:
    selection = _selection("People")
    cursor = query_colorado_opinions._search_cursor(
        parameters=selection,
        page=2,
        row=0,
        seen=2,
        anchor=890715320,
    )
    client = _client()

    with pytest.raises(
        query_colorado_opinions.ColoradoOpinionsSelectionError
    ) as error:
        client.search(_selection("Bankers"), cursor=cursor)

    assert error.value.code == "cursor_query_mismatch"


def test_authoritative_empty_count_and_page_become_no_results() -> None:
    client = _client(
        FakeResponse(payload=_json_fixture("count_zero.json")),
        FakeResponse(payload=_json_fixture("search_no_results.json")),
    )

    result = query_colorado_opinions.execute(
        _parse("search", "NoSuchColoradoCase", "--court", "supreme"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    validate_envelope(result.to_dict())


def test_normalization_preserves_docket_citations_identity_and_null_publication() -> None:
    page = query_colorado_opinions.parse_search_page(
        _json_fixture("search_page_1.json"),
        page_number=1,
    )

    record = query_colorado_opinions.normalize_search_results(
        page.results[:1],
        court_key="supreme",
        total_count=3,
    )[0]

    assert record["source_id"] == query_colorado_opinions.SOURCE_ID
    assert record["canonical_ref"].endswith("/supreme/887202075")
    assert record["title"] == "People v. Calvaresi"
    assert record["court"]["name"] == "Colorado Supreme Court"
    assert record["docket_number"] == "No. 25997"
    assert record["decision_date"] == "1975-04-21"
    assert record["citations"] == ["188 Colo. 277", "534 P.2d 316"]
    assert record["publication_status"] is None
    assert record["pdf_url"].endswith("/pdf/887202075")


def test_wrong_court_result_is_source_change_not_silent_leak() -> None:
    payload = _json_fixture("search_page_1.json")
    payload["results"][0]["parent"]["title"] = "Colorado Court of Appeals"
    page = query_colorado_opinions.parse_search_page(
        payload,
        page_number=1,
    )

    with pytest.raises(
        query_colorado_opinions.ColoradoOpinionsSourceChangedError
    ) as error:
        query_colorado_opinions.normalize_search_results(
            page.results,
            court_key="supreme",
            total_count=3,
        )

    assert error.value.code == "court_filter_leaked"


def test_restricted_or_partial_source_is_explicit_partial() -> None:
    client = _client(
        FakeResponse(payload=_json_fixture("count_restricted.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
    )

    result = query_colorado_opinions.execute(
        _parse(
            "search",
            "People",
            "--court",
            "supreme",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert result.errors[0].code == "source_returned_partial_results"
    assert len(result.records) == 1


def test_count_endpoint_disagreement_still_traverses_search_page_count() -> None:
    count_payload = {"count": 4, "restricted": False}
    client = _client(
        FakeResponse(payload=count_payload),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
        FakeResponse(payload=_json_fixture("search_page_2_short.json")),
    )

    result = query_colorado_opinions.execute(
        _parse("search", "People", "--court", "supreme"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 3
    assert result.errors[0].code == "native_pagination_incomplete"
    assert result.errors[0].details == {
        "count_endpoint": 4,
        "search_page_count": 3,
        "page": 1,
    }


def test_search_reports_rows_beyond_snapshot_count_as_partial() -> None:
    second_page = _json_fixture("search_page_1.json")
    second_page["results"][0]["id"] = 1041908406
    second_page["results"][1]["id"] = 1041908407
    client = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
        FakeResponse(payload=second_page),
    )

    result = query_colorado_opinions.execute(
        _parse("search", "People", "--court", "supreme"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 4
    assert result.errors[0].code == "native_pagination_incomplete"
    assert result.errors[0].details["snapshot_count"] == 3
    assert result.errors[0].details["rows_through_page"] == 4


def test_search_cursor_detects_reordered_boundary() -> None:
    selection = _selection()
    first = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
    )
    cursor = first.search(selection, limit=1).next_cursor
    changed_page = _json_fixture("search_page_1.json")
    changed_page["results"].reverse()
    resumed = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=changed_page),
    )

    with pytest.raises(
        query_colorado_opinions.ColoradoOpinionsSelectionError
    ) as error:
        resumed.search(selection, cursor=cursor)

    assert error.value.code == "cursor_snapshot_changed"


def test_page_boundary_cursor_detects_overlap_on_next_page() -> None:
    selection = _selection()
    first = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
    )
    cursor = first.search(selection, limit=2).next_cursor
    overlapping = _json_fixture("search_page_2_short.json")
    overlapping["results"][0]["id"] = 890715320
    resumed = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
        FakeResponse(payload=overlapping),
    )

    batch = resumed.search(selection, cursor=cursor)

    assert batch.results == ()
    assert batch.incomplete_error is not None
    assert batch.incomplete_error.code == "native_pagination_incomplete"
    assert batch.incomplete_error.details["document_id"] == 890715320


def test_search_does_not_chase_later_count_growth() -> None:
    growing_page = _json_fixture("search_page_2_short.json")
    growing_page["count"] = 4
    client = _client(
        FakeResponse(payload=_json_fixture("count.json")),
        FakeResponse(payload=_json_fixture("search_page_1.json")),
        FakeResponse(payload=growing_page),
    )

    batch = client.search(_selection())

    assert len(batch.results) == 3
    assert batch.total_count == 3
    assert batch.pages_fetched == 2
    assert batch.incomplete_error is not None
    assert batch.incomplete_error.details["snapshot_count"] == 3


def test_supreme_release_parser_emits_individual_current_opinions() -> None:
    page = query_colorado_opinions.parse_supreme_releases(
        _text_fixture("supreme_releases.html")
    )

    assert len(page.records) == 4
    first = page.records[0]
    assert first["source_id"] == query_colorado_opinions.RELEASE_SOURCE_ID
    assert first["record_kind"] == "current_supreme_opinion_release"
    assert first["native_release_id"] == "17158"
    assert first["docket_number"] == "23SC932"
    assert first["release_date"] == "2026-06-29"
    assert first["citation"] == "26 CO 55"
    assert first["publication_status"] == "published"
    assert first["publication_stage"] == "slip_opinion"
    assert first["download_source"].endswith("/node/17158")
    consolidated = [
        record
        for record in page.records
        if record["native_release_id"] == "17160"
    ]
    assert len(consolidated) == 2
    assert consolidated[0]["canonical_ref"] != consolidated[1]["canonical_ref"]


def test_appeals_release_parser_keeps_packet_distinct_from_opinion() -> None:
    page = query_colorado_opinions.parse_appeals_releases(
        _text_fixture("appeals_releases_page_1.html"),
        source_url=(
            f"{query_colorado_opinions.APPEALS_RELEASE_URL}?page=0"
        ),
    )

    assert len(page.records) == 1
    record = page.records[0]
    assert record["source_id"] == query_colorado_opinions.RELEASE_SOURCE_ID
    assert record["record_kind"] == "appellate_release_announcement_packet"
    assert record["is_opinion"] is False
    assert record["publication_scope"] == ["published", "unpublished"]
    assert record["release_date"] == "2026-07-23"
    assert record["pdf_url"].endswith("/2026-07/07-23-26.pdf")
    assert page.next_page_url == (
        f"{query_colorado_opinions.APPEALS_RELEASE_URL}?page=1"
    )


def test_appeals_release_valid_empty_is_distinct_from_source_change() -> None:
    empty = query_colorado_opinions.parse_appeals_releases(
        _text_fixture("appeals_releases_empty.html")
    )
    assert empty.records == ()

    with pytest.raises(
        query_colorado_opinions.ColoradoOpinionsSourceChangedError
    ) as error:
        query_colorado_opinions.parse_appeals_releases(
            _text_fixture("release_source_changed.html")
        )
    assert error.value.code == "appeals_release_container_changed"


def test_appeals_releases_exhaust_native_pages_and_preserve_filters() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=_text_fixture("appeals_releases_page_1.html"),
                content_type="text/html",
                url=(
                    f"{query_colorado_opinions.APPEALS_RELEASE_URL}?"
                    "page=0"
                ),
            ),
            FakeResponse(
                text=_text_fixture("appeals_releases_page_2.html"),
                content_type="text/html",
                url=(
                    f"{query_colorado_opinions.APPEALS_RELEASE_URL}?"
                    "page=1"
                ),
            ),
        ]
    )
    client = query_colorado_opinions.ColoradoOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    collection = client.fetch_releases(
        court_key="appeals",
        year=2026,
        query_text="People",
        limit=None,
        cursor=None,
    )

    assert len(collection.records) == 2
    assert collection.pages_fetched == 2
    assert collection.next_cursor is None
    for _url, kwargs in session.calls:
        assert kwargs["params"]["f[0]"] == (
            "case_announcement_coa_year:2026"
        )
        assert kwargs["params"]["search_api_fulltext"] == "People"
    assert session.calls[1][1]["params"]["page"] == "1"


def test_release_cursor_is_query_bound() -> None:
    parameters = {"court": "appeals", "year": "2026", "query": ""}
    cursor = query_colorado_opinions._release_cursor(
        parameters=parameters,
        offset=1,
        anchor="a" * 64,
    )

    assert query_colorado_opinions._release_cursor_offset(
        cursor,
        parameters=parameters,
    ) == (1, "a" * 64)
    with pytest.raises(
        query_colorado_opinions.ColoradoOpinionsSelectionError
    ) as error:
        query_colorado_opinions._release_cursor_offset(
            cursor,
            parameters={"court": "appeals", "year": "2025", "query": ""},
        )
    assert error.value.code == "cursor_query_mismatch"


def test_appeals_release_pagination_stops_on_repeated_content() -> None:
    repeated_html = _text_fixture("appeals_releases_page_1.html")
    client = query_colorado_opinions.ColoradoOpinionsClient(
        session=FakeSession(
            [
                FakeResponse(
                    text=repeated_html,
                    content_type="text/html",
                    url=f"{query_colorado_opinions.APPEALS_RELEASE_URL}?page=0",
                ),
                FakeResponse(
                    text=repeated_html,
                    content_type="text/html",
                    url=f"{query_colorado_opinions.APPEALS_RELEASE_URL}?page=1",
                ),
            ]
        ),
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    collection = client.fetch_releases(
        court_key="appeals",
        year=None,
        query_text=None,
        limit=None,
        cursor=None,
    )

    assert len(collection.records) == 1
    assert collection.pages_fetched == 2
    assert collection.incomplete_error is not None
    assert collection.incomplete_error.code == "native_pagination_incomplete"


def test_document_metadata_and_full_text_normalize_docket_and_citations() -> None:
    client = _client(
        FakeResponse(
            payload=_json_fixture("document.json"),
            url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "vid/887202075.json"
            ),
        ),
        FakeResponse(
            text=_text_fixture("document_content.html"),
            content_type="text/html; charset=utf-8",
            url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "vid/887202075/content"
            ),
        ),
    )

    document = client.fetch_document(887202075)
    record = query_colorado_opinions.normalize_document(document)

    assert record["record_kind"] == "appellate_opinion_document"
    assert record["docket_number"] == "25997"
    assert record["citations"] == ["534 P.2d 316", "188 Colo. 277"]
    assert record["decision_date"] == "1975-04-21"
    assert "fixture opinion paragraph" in record["full_text"]
    assert len(record["full_text_sha256"]) == 64


def test_pdf_fetch_validates_magic_and_component_identity() -> None:
    content = (FIXTURE_DIR / "sentinel.pdf").read_bytes()
    client = _client(
        FakeResponse(
            payload=_json_fixture("document.json"),
            url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "vid/887202075.json"
            ),
        ),
        FakeResponse(
            content=content,
            content_type="application/pdf",
            url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "pdf/887202075"
            ),
            headers={
                "Content-Disposition": (
                    'attachment; filename="people-v-calvaresi-colorado.pdf"'
                )
            },
        )
    )

    artifact = client.fetch_pdf("887202075")

    assert artifact.component_source_id == query_colorado_opinions.SOURCE_ID
    assert artifact.content.startswith(b"%PDF-")
    assert artifact.file_name == "people-v-calvaresi-colorado.pdf"
    assert len(artifact.sha256) == 64


def test_download_writes_pdf_and_emits_integrity_receipt(tmp_path: Path) -> None:
    content = (FIXTURE_DIR / "sentinel.pdf").read_bytes()
    client = _client(
        FakeResponse(
            payload=_json_fixture("document.json"),
            url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "vid/887202075.json"
            ),
        ),
        FakeResponse(
            content=content,
            content_type="application/pdf",
            url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "pdf/887202075"
            ),
        )
    )
    destination = tmp_path / "opinion.pdf"

    result = query_colorado_opinions.execute(
        _parse("download", "887202075", str(destination)),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == content
    assert result.records[0]["record_kind"] == (
        "appellate_opinion_pdf_artifact"
    )
    assert result.records[0]["sha256"] == result.records[0]["canonical_ref"].split(
        ":"
    )[-1]
    assert result.raw_artifact_refs == (str(destination),)


def test_download_rejects_unverified_pdf_route_before_request() -> None:
    client = _client()

    result = query_colorado_opinions.execute(
        _parse(
            "download",
            "https://example.com/opinion.pdf",
            "/tmp/not-written.pdf",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "pdf_source_unknown"


def test_injected_catalog_decision_must_match_source_component() -> None:
    result = query_colorado_opinions.execute(
        _parse("search", "People", "--court", "supreme"),
        access_decision={
            "source_id": query_colorado_opinions.RELEASE_SOURCE_ID,
            "allowed": True,
        },
        client=_client(),
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "catalog_decision_source_mismatch"


def test_download_rejects_unrelated_official_pdf_route_before_request() -> None:
    client = _client()

    result = query_colorado_opinions.execute(
        _parse(
            "download",
            (
                "https://www.coloradojudicial.gov/sites/default/files/"
                "2025-11/CJD05-01.pdf"
            ),
            "/tmp/not-written.pdf",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "pdf_source_unknown"


def test_supreme_release_node_resolves_and_downloads_exact_pdf(
    tmp_path: Path,
) -> None:
    content = (FIXTURE_DIR / "sentinel.pdf").read_bytes()
    node_url = "https://www.coloradojudicial.gov/node/17158"
    pdf_url = (
        "https://www.coloradojudicial.gov/system/files/"
        "opinions-2026-06/23SC932.pdf"
    )
    client = _client(
        FakeResponse(
            text=_text_fixture("supreme_release_node.html"),
            content_type="text/html",
            url=node_url,
        ),
        FakeResponse(
            content=content,
            content_type="application/pdf",
            url=pdf_url,
        ),
    )
    destination = tmp_path / "23SC932.pdf"

    result = query_colorado_opinions.execute(
        _parse("download", node_url, str(destination)),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert result.query.source.source_id == (
        query_colorado_opinions.RELEASE_SOURCE_ID
    )
    assert result.records[0]["source_url"] == pdf_url
    assert result.records[0]["component_source_id"] == (
        query_colorado_opinions.RELEASE_SOURCE_ID
    )
    assert destination.read_bytes() == content


def test_release_pdf_download_query_uses_release_component_identity() -> None:
    source_url = (
        "https://www.coloradojudicial.gov/sites/default/files/"
        "2026-07/07-23-26.pdf"
    )
    query = query_colorado_opinions.build_query(
        _parse("download", source_url, "/tmp/announcement.pdf")
    )

    assert (
        query.source.source_id
        == query_colorado_opinions.RELEASE_SOURCE_ID
    )


class ProbeClient:
    def __init__(self) -> None:
        search_page = query_colorado_opinions.parse_search_page(
            _json_fixture("search_page_1.json"),
            page_number=1,
        )
        self.count = query_colorado_opinions.parse_count(
            _json_fixture("count.json")
        )
        self.page = search_page
        metadata = _json_fixture("document.json")
        content = _text_fixture("document_content.html")
        self.document = query_colorado_opinions.CaseLawDocument(
            metadata=metadata,
            content_html=content,
            metadata_url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "vid/887202075.json"
            ),
            content_url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "vid/887202075/content"
            ),
            metadata_schema_fingerprint="a" * 64,
            content_sha256="b" * 64,
        )
        pdf_content = (FIXTURE_DIR / "sentinel.pdf").read_bytes()
        self.artifact = query_colorado_opinions.PDFArtifact(
            content=pdf_content,
            source_url=(
                f"{query_colorado_opinions.CASE_LAW_BASE_URL}/"
                "pdf/887202075"
            ),
            media_type="application/pdf",
            sha256="c" * 64,
            file_name="sentinel.pdf",
            component_source_id=query_colorado_opinions.SOURCE_ID,
        )
        self.supreme = query_colorado_opinions.parse_supreme_releases(
            _text_fixture("supreme_releases.html")
        )
        self.appeals = query_colorado_opinions.parse_appeals_releases(
            _text_fixture("appeals_releases_page_1.html")
        )
        self.calls: list[str] = []

    def fetch_count(self, _selection: Mapping[str, str]) -> Any:
        self.calls.append("count")
        return self.count

    def fetch_search_page(
        self,
        _selection: Mapping[str, str],
        *,
        page_number: int,
    ) -> Any:
        assert page_number == 1
        self.calls.append("search")
        return self.page

    def fetch_document(
        self,
        document_id: int,
        *,
        include_content: bool,
    ) -> Any:
        assert document_id == 887202075
        assert include_content is True
        self.calls.append("document")
        return self.document

    def fetch_pdf(self, source: str) -> Any:
        assert source == "887202075"
        self.calls.append("pdf")
        return self.artifact

    def fetch_supreme_release_page(self) -> Any:
        self.calls.append("supreme-release")
        return self.supreme

    def fetch_appeals_release_page(self, *, page_number: int) -> Any:
        assert page_number == 0
        self.calls.append("appeals-release")
        return self.appeals


def test_component_probes_have_source_matched_identity_and_dispatch() -> None:
    archive_client = ProbeClient()
    archive = query_colorado_opinions.execute(
        _parse("probe", "--component", "archive"),
        client=archive_client,
        log_results=False,
    )

    assert archive.status is ResultStatus.OK
    assert archive.query.source.source_id == query_colorado_opinions.SOURCE_ID
    assert archive.records[0]["source_id"] == query_colorado_opinions.SOURCE_ID
    assert archive.records[0]["record_kind"] == "source_health_check"
    assert archive.records[0]["probe_component"] == "archive"
    assert len(archive.records[0]["schema_fingerprint"]) == 64
    assert len(archive.records[0]["artifact_identity"]) == 64
    assert archive_client.calls == ["count", "search", "document", "pdf"]

    release_client = ProbeClient()
    releases = query_colorado_opinions.execute(
        _parse("probe", "--component", "releases"),
        client=release_client,
        log_results=False,
    )

    assert releases.status is ResultStatus.OK
    assert (
        releases.query.source.source_id
        == query_colorado_opinions.RELEASE_SOURCE_ID
    )
    assert (
        releases.records[0]["source_id"]
        == query_colorado_opinions.RELEASE_SOURCE_ID
    )
    assert releases.records[0]["record_kind"] == "source_health_check"
    assert releases.records[0]["probe_component"] == "releases"
    assert releases.records[0]["result_count"] == 5
    assert release_client.calls == ["supreme-release", "appeals-release"]


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORD_TESTS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORD_TESTS=1 for the official live sentinel",
)
def test_live_component_probes() -> None:
    for component in ("archive", "releases"):
        result = query_colorado_opinions.execute(
            _parse(
                "probe",
                "--component",
                component,
                "--minimum-interval",
                "0.1",
            ),
            log_results=False,
        )
        assert result.status is ResultStatus.OK
        assert result.records[0]["probe_component"] == component
