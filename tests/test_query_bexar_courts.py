from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import query_bexar_courts
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.kofile_publicsearch import (
    KofileBootstrap,
    KofilePageImage,
    KofileSearchPage,
    KofileSourceChangedError,
    SEARCH_SUCCESS_TYPE,
)
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/bexar_courts")
SEARCH_RESPONSE = json.loads(
    (FIXTURE_DIR / "search_response.json").read_text(encoding="utf-8")
)
DETAIL_RESPONSE = json.loads(
    (FIXTURE_DIR / "detail_response.json").read_text(encoding="utf-8")
)
SEARCH_ROWS = tuple(
    SEARCH_RESPONSE["payload"]["data"]["byHash"][str(identifier)]
    for identifier in SEARCH_RESPONSE["payload"]["data"]["byOrder"]
)
DETAIL_ROW = DETAIL_RESPONSE["payload"]
ALLOWED = {
    "allowed": True,
    "access_class": "B",
    "reason_code": "allowed_with_limits",
    "limits": {},
}


class FakeBexarClient:
    def __init__(
        self,
        *,
        search_page: KofileSearchPage | None = None,
        search_error: Exception | None = None,
        page_content: bytes = b"\x89PNG\r\nfixture-page",
    ) -> None:
        self.search_page = search_page or KofileSearchPage(
            records=SEARCH_ROWS,
            total_count=3,
            statistics={"recorded-years": [{"label": "1919", "hits": 2}]},
            offset=0,
            limit=2,
            next_offset=2,
            response_type=SEARCH_SUCCESS_TYPE,
        )
        self.search_error = search_error
        self.page_content = page_content
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def bootstrap(self) -> KofileBootstrap:
        self.calls.append(("bootstrap", {}))
        return KofileBootstrap(
            state={},
            auth_token="anonymous-token-1",
            ip="203.0.113.4",
            tenant_id="48029dc",
            department_codes=("HC", "NR"),
            department_date_ranges={
                "HC": {"min": "18000101", "max": "19190917"}
            },
        )

    def search(self, **kwargs: Any) -> KofileSearchPage:
        self.calls.append(("search", dict(kwargs)))
        if self.search_error is not None:
            raise self.search_error
        return self.search_page

    def fetch_document(self, doc_id: int) -> dict[str, Any]:
        self.calls.append(("fetch_document", {"doc_id": doc_id}))
        if doc_id == 102:
            return dict(DETAIL_ROW)
        if doc_id == 101:
            return dict(SEARCH_ROWS[0])
        raise AssertionError(f"unexpected fixture document {doc_id}")

    def fetch_page_image(
        self,
        doc_id: int,
        page_number: int,
    ) -> KofilePageImage:
        self.calls.append(
            (
                "fetch_page_image",
                {"doc_id": doc_id, "page_number": page_number},
            )
        )
        return KofilePageImage(
            document=dict(DETAIL_ROW),
            page_number=page_number,
            source_url=DETAIL_ROW["urls"][page_number - 1],
            media_type="image/png",
            content=self.page_content,
            etag='"fixture-etag"',
        )


def _parse(*values: str):
    return query_bexar_courts.build_parser().parse_args(list(values))


def _execute(args, monkeypatch, *, client=None, decision=ALLOWED):
    monkeypatch.setattr(query_bexar_courts, "log_search", lambda *args: None)
    return query_bexar_courts.execute(
        args,
        access_decision=decision,
        client=client or FakeBexarClient(),
    )


def test_parser_exposes_search_case_page_and_probe_commands():
    search = _parse(
        "search",
        "jury verdict",
        "--ocr",
        "--date-from",
        "1919-01-01",
        "--date-to",
        "1919-12-31",
        "--limit",
        "7",
        "--offset",
        "14",
        "--workspace-id",
        "review-run",
        "--output",
        "results.json",
    )
    case = _parse("case", "102", "--json")
    page = _parse("page", "102", "2", "page.png", "--overwrite")
    probe = _parse("probe", "--timeout", "4")

    assert search.command == "search"
    assert search.query == "jury verdict"
    assert search.ocr is True
    assert (search.limit, search.offset) == (7, 14)
    assert search.workspace_id == "review-run"
    assert search.output == "results.json"
    assert case.doc_id == 102
    assert case.json_out is True
    assert (page.doc_id, page.page_number, page.destination) == (
        102,
        2,
        "page.png",
    )
    assert page.overwrite is True
    assert probe.timeout == 4


def test_search_normalizes_native_identity_sentinel_parties_and_pagination(
    monkeypatch,
):
    client = FakeBexarClient()

    result = _execute(
        _parse("search", "6707", "--limit", "2"),
        monkeypatch,
        client=client,
    )
    payload = result.to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert payload["next_cursor"] == "kofile:offset:2"
    assert len(payload["records"]) == 2
    first, second = payload["records"]
    assert first["raw_case_number"] == second["raw_case_number"] == "6707"
    assert (first["source_internal_id"], second["source_internal_id"]) == (
        "101",
        "102",
    )
    assert first["canonical_ref"] != second["canonical_ref"]
    assert first["rs_id"] == "BexarTXCivilCaseFiles-005548"
    assert first["source_file_date_raw"] == "1/1/1800"
    assert first["source_file_date_quality"] == "unknown_date_sentinel"
    assert first["filing_date"] is None
    assert second["filing_date"] == "1919-09-17"
    assert [party["role"] for party in first["parties"]] == [
        "Plaintiff",
        "Defendant",
    ]
    assert first["ocr_excerpt"] == "divorce petition excerpt"
    assert first["source_versions"]["metadata_version"] == 2
    assert first["page_manifest"]["image_id"] == 501
    assert "docket_entries" not in first
    search_call = client.calls[0]
    assert search_call == (
        "search",
        {
            "department": "HC",
            "limit": 2,
            "offset": 0,
            "search_value": "6707",
            "search_ocr_text": False,
            "recorded_date_range": None,
            "workspace_id": None,
        },
    )


def test_date_range_and_ocr_are_forwarded_without_an_adapter_total_cap(
    monkeypatch,
):
    client = FakeBexarClient()

    _execute(
        _parse(
            "search",
            "jury verdict",
            "--ocr",
            "--date-from",
            "1919-01-01",
            "--date-to",
            "1919-12-31",
            "--limit",
            "137",
            "--offset",
            "274",
        ),
        monkeypatch,
        client=client,
    )

    assert client.calls[0][1]["limit"] == 137
    assert client.calls[0][1]["offset"] == 274
    assert client.calls[0][1]["search_value"] == "jury verdict"
    assert client.calls[0][1]["search_ocr_text"] is True
    assert (
        client.calls[0][1]["recorded_date_range"]
        == "19190101,19191231"
    )


def test_authoritative_empty_search_remains_no_results(monkeypatch):
    client = FakeBexarClient(
        search_page=KofileSearchPage(
            records=(),
            total_count=0,
            statistics={},
            offset=0,
            limit=50,
            next_offset=None,
            response_type=SEARCH_SUCCESS_TYPE,
        )
    )

    result = _execute(
        _parse("search", "NO SUCH PARTY"),
        monkeypatch,
        client=client,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_case_fetches_exact_doc_id_and_preserves_ephemeral_page_manifest(
    monkeypatch,
):
    client = FakeBexarClient()

    result = _execute(
        _parse("case", "102"),
        monkeypatch,
        client=client,
    )
    payload = result.to_dict()
    validate_envelope(payload)
    record = payload["records"][0]

    assert client.calls == [("fetch_document", {"doc_id": 102})]
    assert record["doc_id"] == 102
    assert record["source_internal_id"] == "102"
    assert record["source_url"].endswith("/doc/102?department=HC")
    assert record["source_versions"]["document_version"] == 5
    assert record["page_manifest"]["signed_urls_are_ephemeral"] is True
    assert record["page_manifest"]["same_anonymous_session_cookie_required"] is True
    assert len(record["page_manifest"]["pages"]) == 2


def test_envelope_projects_without_synthetic_docket_entries(
    tmp_path,
    monkeypatch,
):
    client = FakeBexarClient(
        search_page=KofileSearchPage(
            records=SEARCH_ROWS[:1],
            total_count=1,
            statistics={},
            offset=0,
            limit=1,
            next_offset=None,
            response_type=SEARCH_SUCCESS_TYPE,
        )
    )
    result = _execute(
        _parse("search", "6707", "--limit", "1"),
        monkeypatch,
        client=client,
    )

    ingested = ingest_envelope(
        result.to_dict(),
        court_db=tmp_path / "courts.db",
    )

    assert ingested["status"] == "ingested"
    assert ingested["projected"]["cases"] == 1
    assert ingested["projected"]["parties"] == 2
    assert ingested["projected"]["documents"] == 1
    assert ingested["projected"]["docket_entries"] == 0


def test_page_download_writes_only_selected_image_and_records_sha(
    tmp_path,
    monkeypatch,
):
    client = FakeBexarClient()
    destination = tmp_path / "selected-page.png"

    result = _execute(
        _parse("page", "102", "2", str(destination)),
        monkeypatch,
        client=client,
    )
    payload = result.to_dict()
    validate_envelope(payload)
    record = payload["records"][0]

    assert destination.read_bytes() == client.page_content
    assert payload["raw_artifact_refs"] == [str(destination.resolve())]
    assert record["page_download"]["page_number"] == 2
    assert record["page_download"]["storage_path"] == str(
        destination.resolve()
    )
    assert len(record["page_download"]["sha256"]) == 64
    assert record["documents"][0]["document_type"] == (
        "historical_case_file_page"
    )


def test_probe_checks_tenant_search_and_exact_detail(monkeypatch):
    client = FakeBexarClient()

    result = _execute(_parse("probe"), monkeypatch, client=client)
    payload = result.to_dict()
    record = payload["records"][0]

    assert [name for name, _kwargs in client.calls] == [
        "bootstrap",
        "search",
        "fetch_document",
    ]
    assert client.calls[1][1]["recorded_date_range"] == "19190101,19191231"
    assert record["doc_id"] == 101
    assert record["source_file_date_raw"] == "1/1/1800"
    assert record["probe"]["tenant_id"] == "48029dc"
    assert record["probe"]["department_codes"] == ["HC", "NR"]


def test_catalog_denial_stops_before_source_dispatch(monkeypatch):
    calls = []
    monkeypatch.setattr(
        query_bexar_courts,
        "log_search",
        lambda *args: calls.append(args),
    )

    result = query_bexar_courts.execute(
        _parse("case", "102"),
        access_decision={
            "allowed": False,
            "access_class": "C",
            "reason_code": "interactive_route",
            "reason": "review requires another route",
        },
    )

    assert result.status is ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "interactive_route"
    assert len(calls) == 1


def test_protocol_change_is_not_reported_as_no_results(monkeypatch):
    client = FakeBexarClient(
        search_error=KofileSourceChangedError(
            "observed v7",
            code="search_protocol_version_changed",
            retryable=False,
        )
    )

    result = _execute(
        _parse("search", "6707"),
        monkeypatch,
        client=client,
    )

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "search_protocol_version_changed"
