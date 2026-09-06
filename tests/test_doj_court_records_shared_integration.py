from __future__ import annotations

from typing import Any

import pytest

from tools import query_doj_court_records as doj_courts
from tools import query_state_courts
from tools.public_records_contract import PublicRecordsResult


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_shared_routes_preserve_release_corpus_semantics_and_omitted_limit() -> None:
    routes = query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID]

    assert set(routes) == {"search", "documents", "discovery", "probe"}
    assert "case" not in routes
    assert "docket" not in routes

    search = routes["search"].translate(
        _shared_args(
            "search",
            "United States v. Epstein",
            "--source",
            doj_courts.SOURCE_ID,
        ),
        routes["search"].adapter_command,
    )
    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            doj_courts.SENTINEL_CASE_URL,
            "--source",
            doj_courts.SOURCE_ID,
        ),
        routes["documents"].adapter_command,
    )

    assert search.command == "index"
    assert search.query == "United States v. Epstein"
    assert search.limit is None
    assert search.minimum_interval == doj_courts.DEFAULT_MINIMUM_INTERVAL
    assert documents.command == "case"
    assert documents.case_url == doj_courts.SENTINEL_CASE_URL
    assert documents.limit is None
    assert documents.cursor is None
    assert documents.minimum_interval == doj_courts.DEFAULT_MINIMUM_INTERVAL


def test_shared_caller_limits_and_document_cursor_are_forwarded() -> None:
    routes = query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID]
    cursor = doj_courts._encode_cursor(
        doj_courts.SENTINEL_CASE_URL,
        criteria_fingerprint=doj_courts._cursor_criteria_fingerprint(
            doj_courts.SENTINEL_CASE_URL
        ),
    )

    search = routes["search"].translate(
        _shared_args(
            "search",
            "Epstein",
            "--source",
            doj_courts.SOURCE_ID,
            "--limit",
            "9",
        ),
        routes["search"].adapter_command,
    )
    documents = routes["documents"].translate(
        _shared_args(
            "documents",
            doj_courts.SENTINEL_CASE_URL,
            "--source",
            doj_courts.SOURCE_ID,
            "--max-records",
            "17",
            "--cursor",
            cursor,
        ),
        routes["documents"].adapter_command,
    )

    assert search.limit == 9
    assert documents.limit == 17
    assert documents.cursor == cursor


def test_discovery_and_probe_do_not_acquire_or_normalize_rows() -> None:
    routes = query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID]

    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "coverage",
            "--source",
            doj_courts.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "probe",
            "--source",
            doj_courts.SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )

    assert discovery.command == "sources"
    assert probe.command == "probe"


@pytest.mark.parametrize(
    ("operation", "selector", "options", "message"),
    [
        (
            "search",
            "Epstein",
            ("--jurisdiction", "US-NY"),
            "multiple underlying courts",
        ),
        (
            "search",
            "Epstein",
            ("--court-id", "nysd"),
            "not source-native court",
        ),
        (
            "search",
            "Epstein",
            ("--after", "2019-01-01"),
            "not source-native court",
        ),
        (
            "search",
            "Example Holdings",
            ("--entity-kind", "organization"),
            "not source-native court",
        ),
        (
            "search",
            "Epstein",
            ("--ingest",),
            "not normalized as complete court cases",
        ),
        (
            "probe",
            "probe",
            ("--limit", "1"),
            "without row filters",
        ),
    ],
)
def test_shared_routes_reject_misleading_case_semantics(
    operation: str,
    selector: str,
    options: tuple[str, ...],
    message: str,
) -> None:
    route = query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID][operation]
    args = _shared_args(
        operation,
        selector,
        "--source",
        doj_courts.SOURCE_ID,
        *options,
    )

    with pytest.raises(ValueError, match=message):
        route.translate(args, route.adapter_command)


@pytest.mark.parametrize(
    ("selector", "error_code"),
    [
        ("19-cr-00490", "invalid_case_url"),
        ("https://example.org/court-records/example", "unofficial_url"),
    ],
)
def test_invalid_document_selector_preserves_source_error_without_acquisition(
    monkeypatch: pytest.MonkeyPatch,
    selector: str,
    error_code: str,
) -> None:
    class FakeCatalog:
        def __init__(self, _path):
            pass

        def show_source(self, source_id):
            assert source_id == doj_courts.SOURCE_ID
            return {"source_id": source_id}

        def machine_acquisition_decision(self, _source_id):
            return {"allowed": True, "limits": {}}

    class NoNetworkSession:
        closed = False

        def request(self, *_args, **_kwargs):
            pytest.fail("an invalid selector must fail before any HTTP request")

        def close(self):
            self.closed = True

    session = NoNetworkSession()
    monkeypatch.setattr(query_state_courts, "PublicRecordsCatalog", FakeCatalog)
    monkeypatch.setattr(doj_courts, "system_trust_session", lambda: session)
    monkeypatch.setattr(doj_courts, "log_search", lambda *_args: None)

    payload = query_state_courts.execute(
        _shared_args("documents", selector, "--source", doj_courts.SOURCE_ID)
    )

    assert payload["status"] == "unavailable"
    assert payload["records"] == []
    assert len(payload["errors"]) == 1
    error = payload["errors"][0]
    assert error["code"] == error_code
    assert error["category"] == "query_selection"
    assert error["retryable"] is False
    assert selector in error["details"]["url"]
    assert session.closed is True


def test_shared_adapter_applies_transport_settings_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[Any] = []
    calls: list[Any] = []

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

    def fake_execute(
        args: Any,
        *,
        client: Any,
    ) -> PublicRecordsResult:
        calls.append((args, client))
        return PublicRecordsResult.success(doj_courts._query("index"), [])

    monkeypatch.setattr(doj_courts, "DOJCourtRecordsClient", DummyClient)
    monkeypatch.setattr(doj_courts, "execute", fake_execute)
    route = query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID]["search"]
    translated = route.translate(
        _shared_args(
            "search",
            "Epstein",
            "--source",
            doj_courts.SOURCE_ID,
            "--timeout",
            "12",
            "--minimum-interval",
            "1.75",
        ),
        route.adapter_command,
    )

    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )

    assert result.records == ()
    assert len(calls) == len(clients) == 1
    assert calls[0][1] is clients[0]
    assert clients[0].kwargs == {
        "timeout": 12.0,
        "minimum_interval": 1.75,
    }
    assert clients[0].closed is True


def test_shared_probe_uses_the_caller_timeout_for_pdf_magic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[Any] = []
    pdf_calls: list[tuple[str, float]] = []

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

    def fake_pdf_probe(
        url: str,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        pdf_calls.append((url, timeout))
        return {"magic": "%PDF-"}

    def fake_execute(
        args: Any,
        *,
        client: Any,
        pdf_probe: Any,
    ) -> PublicRecordsResult:
        del args
        assert client is clients[0]
        assert pdf_probe(doj_courts.SENTINEL_PDF_URL) == {
            "magic": "%PDF-"
        }
        return PublicRecordsResult.success(
            doj_courts._query("probe"),
            [],
        )

    monkeypatch.setattr(doj_courts, "DOJCourtRecordsClient", DummyClient)
    monkeypatch.setattr(doj_courts, "probe_pdf_magic", fake_pdf_probe)
    monkeypatch.setattr(doj_courts, "execute", fake_execute)
    route = query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID]["probe"]
    translated = route.translate(
        _shared_args(
            "probe",
            "probe",
            "--source",
            doj_courts.SOURCE_ID,
            "--timeout",
            "7",
        ),
        route.adapter_command,
    )

    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )

    assert result.records == ()
    assert clients[0].kwargs == {
        "timeout": 7.0,
        "minimum_interval": 0.0,
    }
    assert clients[0].closed is True
    assert pdf_calls == [(doj_courts.SENTINEL_PDF_URL, 7.0)]


def test_router_guidance_separates_release_corpus_and_docket_sources() -> None:
    guidance = query_state_courts._source_guidance(doj_courts.SOURCE_ID)

    assert guidance["mode"] == "unified_live_official_release_corpus"
    assert guidance["record_grain"] == [
        "doj_release_case_group",
        "doj_released_court_document",
    ]
    assert set(guidance["complementary_routes"]) == {
        "pacer_cm_ecf",
        "courtlistener_recap",
        "named_court_clerk",
        "local_efta_corpus",
    }
    assert "not complete dockets" in guidance["note"]
    assert "not projected" in guidance["note"]
