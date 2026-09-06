from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from tools import query_doj_court_records as doj_courts
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/doj_court_records")


def _text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = dict(headers or {"Content-Type": "text/html"})


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected {method} request to {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class BinaryResponse:
    def __init__(
        self,
        body: bytes,
        content_type: str,
        *,
        url: str = doj_courts.SENTINEL_PDF_URL,
        status: int = 206,
    ) -> None:
        self._body = BytesIO(body)
        self.headers = {"Content-Type": content_type}
        self._url = url
        self.status = status

    def __enter__(self) -> BinaryResponse:
        return self

    def __exit__(self, *_args: Any) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def geturl(self) -> str:
        return self._url


def _client(
    responses: list[FakeResponse],
) -> tuple[doj_courts.DOJCourtRecordsClient, FakeSession]:
    session = FakeSession(responses)
    client = doj_courts.DOJCourtRecordsClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )
    return client, session


def _parse(*values: str) -> Any:
    return doj_courts.build_parser().parse_args(list(values))


def _page_url(page: int | None = None) -> str:
    if page is None:
        return doj_courts.SENTINEL_CASE_URL
    return f"{doj_courts.SENTINEL_CASE_URL}?page={page}"


def test_defaults_add_no_unpublished_pacing_or_result_cap() -> None:
    index = _parse("index")
    case = _parse("case", doj_courts.SENTINEL_CASE_URL)

    assert doj_courts.DEFAULT_MINIMUM_INTERVAL == 0
    assert index.limit is None
    assert case.limit is None


def test_index_parser_extracts_only_case_groups_and_dockets() -> None:
    records = doj_courts.parse_index_html(_text("index.html"))

    assert len(records) == 3
    assert records[0]["case_title"] == (
        "United States v. Epstein, No. 1:19-cr-00490 (S.D.N.Y. 2019)"
    )
    assert records[0]["docket_number"] == "1:19-cr-00490"
    assert records[0]["case_page_url"] == doj_courts.SENTINEL_CASE_URL
    assert records[0]["canonical_ref"].startswith("DOJ-COURT-CASE:")
    assert records[2]["docket_number"] == "50-2006-CF-009454-AXXX-MB"


def test_index_parser_canonicalizes_case_group_identity() -> None:
    html = (
        '<html><h1>DOJ Disclosures</h1><a href="'
        f"{doj_courts.SENTINEL_CASE_URL}?page=4#documents"
        '">Court Records: United States v. Epstein</a></html>'
    )

    records = doj_courts.parse_index_html(html)

    assert records[0]["case_page_url"] == doj_courts.SENTINEL_CASE_URL


def test_index_schema_change_is_explicit() -> None:
    with pytest.raises(
        doj_courts.SourceChangedError,
        match="no recognizable court-record",
    ):
        doj_courts.parse_index_html(_text("source_changed.html"))


def test_case_parser_preserves_indexed_url_efta_and_native_next_page() -> None:
    page = doj_courts.parse_case_html(
        _text("case_page_0.html"),
        source_url=doj_courts.SENTINEL_CASE_URL,
    )

    assert page.case_title.startswith("United States v. Epstein")
    assert [row["efta_id"] for row in page.documents] == [
        "EFTA02824136",
        "EFTA02824150",
    ]
    assert page.documents[0]["canonical_ref"] == "EFTA02824136"
    assert (
        page.documents[0]["indexed_source_url"]
        == doj_courts.SENTINEL_PDF_URL
    )
    assert page.documents[0]["native_page"] == 0
    assert page.next_url == _page_url(1)


def test_case_parser_separates_canonical_identity_from_transport_url() -> None:
    transport_url = (
        doj_courts.SENTINEL_CASE_URL.replace(
            "www.justice.gov",
            "justice.gov",
        )
        + "?page=0"
    )

    page = doj_courts.parse_case_html(
        _text("case_page_0.html"),
        source_url=transport_url,
    )

    assert (
        page.documents[0]["case_page_url"]
        == doj_courts.SENTINEL_CASE_URL
    )
    assert page.documents[0]["listing_page_url"] == transport_url


def test_case_client_exhausts_native_pages_without_default_cap() -> None:
    client, session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            ),
            FakeResponse(_text("case_page_1.html"), url=_page_url(1)),
        ]
    )

    collection = client.fetch_case(doj_courts.SENTINEL_CASE_URL)

    assert [row["efta_id"] for row in collection.documents] == [
        "EFTA02824136",
        "EFTA02824150",
        "EFTA02824473",
    ]
    assert collection.pages_fetched == 2
    assert collection.next_cursor is None
    assert collection.incomplete_error is None
    assert [call["url"] for call in session.calls] == [
        doj_courts.SENTINEL_CASE_URL,
        _page_url(1),
    ]


def test_case_selection_starts_at_canonical_first_page() -> None:
    client, session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )

    client.fetch_case(
        f"{doj_courts.SENTINEL_CASE_URL}?page=99",
        one_page=True,
    )

    assert session.calls[0]["url"] == doj_courts.SENTINEL_CASE_URL


def test_caller_limit_cursor_resumes_inside_transport_page_without_loss() -> None:
    first_client, _session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )
    first = first_client.fetch_case(
        doj_courts.SENTINEL_CASE_URL,
        limit=1,
    )

    assert [row["efta_id"] for row in first.documents] == ["EFTA02824136"]
    assert first.next_cursor is not None
    assert first.next_cursor.startswith(doj_courts.CURSOR_PREFIX)

    resumed_client, resumed_session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            ),
            FakeResponse(_text("case_page_1.html"), url=_page_url(1)),
        ]
    )
    resumed = resumed_client.fetch_case(
        doj_courts.SENTINEL_CASE_URL,
        cursor=first.next_cursor,
    )

    assert [row["efta_id"] for row in resumed.documents] == [
        "EFTA02824150",
        "EFTA02824473",
    ]
    assert resumed_session.calls[0]["url"] == doj_courts.SENTINEL_CASE_URL


def test_cursor_is_bound_to_the_selected_case() -> None:
    first_client, _session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )
    first = first_client.fetch_case(
        doj_courts.SENTINEL_CASE_URL,
        limit=1,
    )
    other_case_url = (
        "https://www.justice.gov/epstein/doj-disclosures/"
        "court-records-example-v-example-no-100-cv-00001"
    )
    resumed_client, resumed_session = _client([])

    with pytest.raises(
        doj_courts.DOJCourtRecordsError,
        match="does not match this DOJ court-record case",
    ):
        resumed_client.fetch_case(
            other_case_url,
            cursor=first.next_cursor,
        )

    assert resumed_session.calls == []


def test_cursor_rejects_mutation_with_a_stale_checksum() -> None:
    first_client, _session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )
    first = first_client.fetch_case(
        doj_courts.SENTINEL_CASE_URL,
        limit=1,
    )
    assert first.next_cursor is not None
    encoded = first.next_cursor[len(doj_courts.CURSOR_PREFIX) :]
    padding = "=" * (-len(encoded) % 4)
    payload = json.loads(
        base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    )
    payload["offset"] = 0
    mutated = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii").rstrip("=")
    resumed_client, resumed_session = _client([])

    with pytest.raises(
        doj_courts.DOJCourtRecordsError,
        match="does not match this DOJ court-record case",
    ):
        resumed_client.fetch_case(
            doj_courts.SENTINEL_CASE_URL,
            cursor=doj_courts.CURSOR_PREFIX + mutated,
        )

    assert resumed_session.calls == []


def test_cursor_rejects_changed_page_before_resuming_inside_it() -> None:
    first_client, _session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )
    first = first_client.fetch_case(
        doj_courts.SENTINEL_CASE_URL,
        limit=1,
    )
    changed_html = _text("case_page_0.html").replace(
        "EFTA02824150",
        "EFTA02824151",
    )
    resumed_client, _session = _client(
        [
            FakeResponse(
                changed_html,
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )

    with pytest.raises(
        doj_courts.SourceChangedError,
        match="contents changed before cursor resumption",
    ):
        resumed_client.fetch_case(
            doj_courts.SENTINEL_CASE_URL,
            cursor=first.next_cursor,
        )


def test_later_edge_denial_preserves_first_page_as_partial_with_cursor() -> None:
    client, _session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            ),
            FakeResponse(
                _text("dead_link.html"),
                url=_page_url(1),
                status_code=403,
            ),
        ]
    )

    result = doj_courts.execute(
        _parse("case", doj_courts.SENTINEL_CASE_URL),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 2
    assert result.next_cursor is not None
    assert result.errors[0].code == "edge_access_denied"
    retrieval = result.to_dict()["records"][0]["retrieval"]
    assert retrieval["transport_pages_fetched"] == 1
    assert retrieval["caller_limit"] is None
    assert retrieval["caller_bound_reached"] is False
    assert retrieval["source_pagination_complete"] is False
    assert retrieval["source_page_failure"] == "edge_access_denied"


def test_age_gate_html_is_not_misreported_as_empty_case() -> None:
    client, _session = _client(
        [
            FakeResponse(
                _text("age_gate.html"),
                url="https://www.justice.gov/age-verify?destination=/epstein",
            )
        ]
    )

    result = doj_courts.execute(
        _parse("case", doj_courts.SENTINEL_CASE_URL),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.HUMAN_REQUIRED
    assert result.records == ()
    assert result.errors[0].code == "age_gate_html"


def test_pdf_probe_sets_cookie_and_range_and_checks_magic() -> None:
    captured: dict[str, Any] = {}

    def opener(request: Any, timeout: float) -> BinaryResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return BinaryResponse(b"%PDF-more bytes", "application/pdf")

    result = doj_courts.probe_pdf_magic(
        doj_courts.SENTINEL_PDF_URL,
        opener=opener,
    )

    request = captured["request"]
    assert request.get_header("Cookie") == doj_courts.AGE_COOKIE
    assert request.get_header("Range") == "bytes=0-4"
    assert captured["timeout"] == doj_courts.DEFAULT_TIMEOUT
    assert result["magic"] == "%PDF-"
    assert result["bytes_read"] == 5


def test_pdf_probe_rejects_age_gate_fixture_by_magic() -> None:
    age_gate = _text("age_gate.html").encode()

    with pytest.raises(
        doj_courts.DOJCourtRecordsError,
        match="HTML or non-PDF",
    ):
        doj_courts.probe_pdf_magic(
            doj_courts.SENTINEL_PDF_URL,
            opener=lambda *_args, **_kwargs: BinaryResponse(
                age_gate,
                "text/html",
            ),
        )


def test_numeric_legacy_dead_link_returns_structured_gap_and_alternatives(
    tmp_path: Path,
) -> None:
    legacy_url = (
        "https://www.justice.gov/multimedia/Court%20Records/"
        "United%20States%20v.%20Epstein%2C%20No.%20119-cr-00490%20"
        "%28S.D.N.Y.%202019%29/061.pdf"
    )
    client, _session = _client(
        [
            FakeResponse(_text("index.html"), url=doj_courts.INDEX_URL),
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            ),
            FakeResponse(_text("case_page_1.html"), url=_page_url(1)),
        ]
    )

    def dead_download(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise HTTPError(legacy_url, 404, "not found", {}, None)

    result = doj_courts.execute(
        _parse("download", legacy_url, str(tmp_path / "061.pdf")),
        client=client,
        downloader=dead_download,
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "indexed_link_not_found"
    recovery = result.to_dict()["errors"][0]["details"]["recovery"]
    assert recovery["resolution"] == (
        "current_case_found_without_exact_document_mapping"
    )
    assert recovery["current_case_page_url"] == doj_courts.SENTINEL_CASE_URL
    assert recovery["case_documents_observed"] == 3
    routes = {
        route["route_id"] for route in recovery["alternatives"]
    }
    assert {"pacer_cm_ecf", "courtlistener_recap", "wayback_exact_url"} <= routes
    assert not (tmp_path / "061.pdf").exists()


def test_exact_efta_legacy_link_recovers_to_current_url(
    tmp_path: Path,
) -> None:
    legacy_url = (
        "https://www.justice.gov/multimedia/Court%20Records/"
        "United%20States%20v.%20Epstein%2C%20No.%20119-cr-00490%20"
        "%28S.D.N.Y.%202019%29/EFTA02824136.pdf"
    )
    client, _session = _client(
        [
            FakeResponse(_text("index.html"), url=doj_courts.INDEX_URL),
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            ),
            FakeResponse(
                _text("dead_link.html"),
                url=_page_url(1),
                status_code=403,
            ),
        ]
    )
    calls: list[str] = []

    def recovering_download(
        url: str,
        destination: Path,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        calls.append(url)
        if len(calls) == 1:
            raise HTTPError(url, 404, "not found", {}, None)
        destination.write_bytes((FIXTURE_DIR / "minimal.pdf").read_bytes())
        return {
            "source_url": url,
            "retrieved_url": url,
            "output": str(destination),
            "content_type": "application/pdf",
            "bytes": destination.stat().st_size,
            "sha256": "fixture",
        }

    output = tmp_path / "EFTA02824136.pdf"
    result = doj_courts.execute(
        _parse("download", legacy_url, str(output)),
        client=client,
        downloader=recovering_download,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert calls == [legacy_url, doj_courts.SENTINEL_PDF_URL]
    record = result.to_dict()["records"][0]
    assert record["requested_url"] == legacy_url
    assert record["indexed_source_url"] == doj_courts.SENTINEL_PDF_URL
    assert record["recovered_from"] == legacy_url
    assert output.read_bytes().startswith(b"%PDF-")


def test_sources_keep_release_docket_archive_and_local_roles_distinct() -> None:
    result = doj_courts.execute(
        _parse("sources"),
        client=_client([])[0],
        log_results=False,
    )

    record = result.to_dict()["records"][0]
    distinctions = record["coverage_distinctions"]
    assert distinctions["doj"].startswith("released copies")
    assert distinctions["pacer"].startswith("official federal docket")
    assert distinctions["recap"].startswith("free contributed")
    assert distinctions["local_efta_corpus"].startswith("local DOJ")


def test_probe_is_one_index_page_one_case_page_and_five_bytes() -> None:
    client, session = _client(
        [
            FakeResponse(_text("index.html"), url=doj_courts.INDEX_URL),
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            ),
        ]
    )

    result = doj_courts.execute(
        _parse("probe"),
        client=client,
        pdf_probe=lambda _url: {
            "source_url": doj_courts.SENTINEL_PDF_URL,
            "retrieved_url": doj_courts.SENTINEL_PDF_URL,
            "http_status": 206,
            "content_type": "application/pdf",
            "magic": "%PDF-",
            "bytes_read": 5,
        },
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["probe_scope"] == {
        "bounded": True,
        "index_pages": 1,
        "case_pages": 1,
        "pdf_bytes": 5,
        "coverage_inference": False,
    }
    assert record["case_count_on_index"] == 3
    assert record["sentinel_document_present"] is True
    assert record["sentinel_has_native_next_page"] is True
    assert record["requests_made"] == 3
    assert record["request_breakdown"] == {
        "release_index": 1,
        "sentinel_case_page": 1,
        "sentinel_pdf_range": 1,
    }
    assert record["healthy"] is True
    assert len(session.calls) == 2


@pytest.mark.parametrize(
    "values",
    [
        ("index", "--limit", "0"),
        ("case", doj_courts.SENTINEL_CASE_URL, "--limit", "-1"),
    ],
)
def test_nonpositive_limits_return_structured_selection_error(
    values: tuple[str, ...],
) -> None:
    client, session = _client([])

    result = doj_courts.execute(
        _parse(*values),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "invalid_limit"
    assert result.query.query.requested_limit is None
    assert session.calls == []


def test_index_filter_and_limit_are_caller_bounds() -> None:
    client, _session = _client(
        [FakeResponse(_text("index.html"), url=doj_courts.INDEX_URL)]
    )

    result = doj_courts.execute(
        _parse("index", "--query", "Epstein", "--limit", "1"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    query = result.to_dict()["query"]["query"]
    assert query["requested_limit"] == 1
    assert query["metadata"]["caller_bound"] is True
    assert any("caller-selected" in warning for warning in result.warnings)


def test_case_result_distinguishes_caller_limit_from_transport_pages() -> None:
    client, _session = _client(
        [
            FakeResponse(
                _text("case_page_0.html"),
                url=doj_courts.SENTINEL_CASE_URL,
            )
        ]
    )

    result = doj_courts.execute(
        _parse(
            "case",
            doj_courts.SENTINEL_CASE_URL,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    retrieval = result.to_dict()["records"][0]["retrieval"]
    assert retrieval == {
        "transport_pages_fetched": 1,
        "caller_limit": 1,
        "caller_bound_reached": True,
        "source_pagination_complete": False,
        "source_page_failure": None,
    }
    assert result.next_cursor is not None


def test_invalid_caller_size_bound_does_not_dispatch_download(
    tmp_path: Path,
) -> None:
    client, session = _client([])

    def never_download(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("download should not run")

    result = doj_courts.execute(
        _parse(
            "download",
            doj_courts.SENTINEL_PDF_URL,
            str(tmp_path / "record.pdf"),
            "--max-bytes",
            "0",
        ),
        client=client,
        downloader=never_download,
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "invalid_max_bytes"
    assert session.calls == []


def test_download_rejects_a_different_doj_epstein_corpus(
    tmp_path: Path,
) -> None:
    client, session = _client([])
    dataset_url = (
        "https://www.justice.gov/epstein/files/DataSet%2011/"
        "EFTA02504960.pdf"
    )

    def never_download(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("download should not run")

    result = doj_courts.execute(
        _parse(
            "download",
            dataset_url,
            str(tmp_path / "record.pdf"),
        ),
        client=client,
        downloader=never_download,
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "invalid_pdf_url"
    assert session.calls == []


def test_result_envelope_is_json_serializable() -> None:
    client, _session = _client(
        [FakeResponse(_text("index.html"), url=doj_courts.INDEX_URL)]
    )
    result = doj_courts.execute(
        _parse("index"),
        client=client,
        log_results=False,
    )

    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert doj_courts.SOURCE_ID in serialized
    assert "DOJ-COURT-CASE" in serialized
