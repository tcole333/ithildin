from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_edva_bankruptcy
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/edva_bankruptcy")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(
        self,
        payload: Any,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.payload = payload
        self.url = url
        self.status_code = status_code
        self.headers = dict(headers or {"Content-Type": "application/json"})

    def json(self) -> Any:
        return self.payload


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


def _client(
    responses: list[FakeResponse],
    *,
    retry_policy: RetryPolicy | None = None,
) -> tuple[query_edva_bankruptcy.EDVABankruptcyClient, FakeSession]:
    session = FakeSession(responses)
    client = query_edva_bankruptcy.EDVABankruptcyClient(
        token="test-token",
        session=session,
        minimum_interval=0,
        retry_policy=retry_policy or RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )
    return client, session


def _parse(*values: str) -> Any:
    return query_edva_bankruptcy.build_parser().parse_args(list(values))


def test_entries_exhaust_every_cursor_page_when_limit_is_omitted() -> None:
    first_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?docket=49921079"
    )
    second_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?cursor=second"
    )
    client, session = _client(
        [
            FakeResponse(_fixture("entries_page_1.json"), url=first_url),
            FakeResponse(_fixture("entries_page_2.json"), url=second_url),
        ]
    )

    collection = client.get_entries(49921079)

    assert [row["id"] for row in collection.records] == [7001, 7002, 7003]
    assert collection.pages_fetched == 2
    assert collection.next_cursor is None
    assert collection.incomplete_error is None
    assert session.calls[0]["params"] == {"docket": 49921079}
    assert session.calls[1]["url"] == second_url
    assert session.calls[1]["params"] is None


def test_caller_limit_emits_resumable_cursor_without_dropping_page_rows() -> None:
    first_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?docket=49921079"
    )
    second_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?cursor=second"
    )
    first_client, _session = _client(
        [FakeResponse(_fixture("entries_page_1.json"), url=first_url)]
    )

    first = first_client.get_entries(49921079, limit=1)

    assert [row["id"] for row in first.records] == [7001]
    assert first.next_cursor is not None

    resumed_client, resumed_session = _client(
        [
            FakeResponse(_fixture("entries_page_1.json"), url=first_url),
            FakeResponse(_fixture("entries_page_2.json"), url=second_url),
        ]
    )
    resumed = resumed_client.get_entries(
        49921079,
        cursor=first.next_cursor,
    )

    assert [row["id"] for row in resumed.records] == [7002, 7003]
    assert resumed.next_cursor is None
    assert resumed_session.calls[0]["url"] == first_url
    assert resumed_session.calls[0]["params"] is None


def test_cursor_rejects_mutation_and_cross_docket_replay() -> None:
    first_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?docket=49921079"
    )
    first_client, _session = _client(
        [FakeResponse(_fixture("entries_page_1.json"), url=first_url)]
    )
    first = first_client.get_entries(49921079, limit=1)
    assert first.next_cursor is not None

    encoded = first.next_cursor[len(query_edva_bankruptcy.CURSOR_PREFIX) :]
    padding = "=" * (-len(encoded) % 4)
    payload = json.loads(
        base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    )
    payload["offset"] = int(payload["offset"]) + 1
    mutated = query_edva_bankruptcy.CURSOR_PREFIX + (
        base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        .decode("ascii")
        .rstrip("=")
    )

    mutated_client, mutated_session = _client([])
    with pytest.raises(
        query_edva_bankruptcy.EDVABankruptcyError,
        match="not match this CourtListener query",
    ) as mutation_error:
        mutated_client.get_entries(49921079, cursor=mutated)
    assert mutation_error.value.code == "invalid_cursor"
    assert mutated_session.calls == []

    replay_client, replay_session = _client([])
    with pytest.raises(
        query_edva_bankruptcy.EDVABankruptcyError,
        match="not match this CourtListener query",
    ) as replay_error:
        replay_client.get_entries(33467987, cursor=first.next_cursor)
    assert replay_error.value.code == "invalid_cursor"
    assert replay_session.calls == []


def test_cursor_rejects_changed_intra_page_snapshot() -> None:
    first_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?docket=49921079"
    )
    first_client, _session = _client(
        [FakeResponse(_fixture("entries_page_1.json"), url=first_url)]
    )
    first = first_client.get_entries(49921079, limit=1)
    assert first.next_cursor is not None

    changed_page = _fixture("entries_page_1.json")
    changed_page["results"][0]["id"] = 999999
    resumed_client, resumed_session = _client(
        [FakeResponse(changed_page, url=first_url)]
    )
    with pytest.raises(
        query_edva_bankruptcy.SourceChangedError,
        match="changed before cursor resumption",
    ) as drift_error:
        resumed_client.get_entries(49921079, cursor=first.next_cursor)
    assert drift_error.value.code == "cursor_page_changed"
    assert resumed_session.calls[0]["url"] == first_url


def test_later_cursor_failure_preserves_rows_as_partial_collection() -> None:
    first_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?docket=49921079"
    )
    second_url = (
        f"{query_edva_bankruptcy.DOCKET_ENTRIES_URL}?cursor=second"
    )
    client, _session = _client(
        [
            FakeResponse(_fixture("entries_page_1.json"), url=first_url),
            FakeResponse({}, url=second_url, status_code=503),
        ],
        retry_policy=RetryPolicy(max_attempts=1),
    )

    collection = client.get_entries(49921079)

    assert [row["id"] for row in collection.records] == [7001, 7002]
    assert collection.incomplete_error is not None
    assert collection.incomplete_error.code == "http_status"
    assert collection.next_cursor is not None


def test_exact_blocked_case_is_recorded_as_access_gap_not_empty_docket() -> None:
    client, _session = _client(
        [
            FakeResponse(
                _fixture("dockets_exact.json"),
                url=query_edva_bankruptcy.DOCKETS_URL,
            ),
            FakeResponse(
                _fixture("entries_empty.json"),
                url=query_edva_bankruptcy.DOCKET_ENTRIES_URL,
            ),
        ]
    )

    result = query_edva_bankruptcy.execute(
        _parse("case", "05-39367"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    docket = result.to_dict()["records"][0]
    assert docket["docket_number"] == "05-39367"
    assert docket["pacer_case_id"] == "425734"
    assert docket["date_blocked"] == "2021-01-28"
    assert docket["entries"] == []
    assert docket["coverage"]["document_access_gap"] is True
    assert docket["coverage"]["gap_reason"] == "courtlistener_docket_blocked"
    assert docket["coverage"]["source_pagination_complete"] is True


def test_exact_case_no_match_is_authoritative_no_results() -> None:
    empty = {"count": None, "next": None, "previous": None, "results": []}
    client, _session = _client(
        [FakeResponse(empty, url=query_edva_bankruptcy.DOCKETS_URL)]
    )

    result = query_edva_bankruptcy.execute(
        _parse("case", "00-00000"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()


def test_fetch_docket_posts_exact_supported_payload_and_scrubs_credentials(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("PACER_USERNAME", "test-pacer-user")
    monkeypatch.setenv("PACER_PASSWORD", "test-pacer-password")
    monkeypatch.setenv("PACER_CLIENT_CODE", "research")
    client, session = _client(
        [
            FakeResponse(
                _fixture("fetch_created.json"),
                url=query_edva_bankruptcy.RECAP_FETCH_URL,
            )
        ]
    )

    result = query_edva_bankruptcy.execute(
        _parse("fetch-docket", "--docket-id", "49921079"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    payload = session.calls[0]["json"]
    assert payload == {
        "request_type": 1,
        "court": "vaeb",
        "docket": 49921079,
        "pacer_username": "test-pacer-user",
        "pacer_password": "test-pacer-password",
        "client_code": "research",
    }
    serialized = canonical = json.dumps(result.to_dict(), sort_keys=True)
    assert "test-pacer-password" not in serialized
    assert "should-not-escape" not in serialized
    assert canonical
    record = result.to_dict()["records"][0]
    assert record["status"] == 1
    assert record["status_label"] == "queued"
    assert record["request_id"] == 91001


def test_fetch_document_without_credentials_is_human_required(
    monkeypatch: Any,
) -> None:
    monkeypatch.delenv("PACER_USERNAME", raising=False)
    monkeypatch.delenv("PACER_PASSWORD", raising=False)
    client, session = _client([])

    result = query_edva_bankruptcy.execute(
        _parse("fetch-document", "8001"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "credentials_required"
    assert session.calls == []


def test_fetch_status_normalizes_terminal_state() -> None:
    client, session = _client(
        [
            FakeResponse(
                _fixture("fetch_success.json"),
                url=f"{query_edva_bankruptcy.RECAP_FETCH_URL}91001/",
            )
        ]
    )

    result = query_edva_bankruptcy.execute(
        _parse("fetch-status", "91001"),
        client=client,
        log_results=False,
    )

    assert session.calls[0]["method"] == "GET"
    record = result.to_dict()["records"][0]
    assert record["status"] == 2
    assert record["status_label"] == "successful"
    assert record["date_completed"] == "2026-07-30T12:01:20Z"


def test_prayer_is_an_explicit_post_with_document_identifier() -> None:
    client, session = _client(
        [
            FakeResponse(
                _fixture("prayer_created.json"),
                url=query_edva_bankruptcy.PRAYERS_URL,
            )
        ]
    )

    result = query_edva_bankruptcy.execute(
        _parse("pray", "8001"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["json"] == {"recap_document": 8001}
    assert result.to_dict()["records"][0]["recap_document"] == "8001"


def test_sources_inventory_keeps_alternatives_and_roles_distinct() -> None:
    result = query_edva_bankruptcy.execute(
        _parse("sources"),
        client=_client([])[0],
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    routes = result.to_dict()["records"][0]["routes"]
    by_id = {route["route_id"]: route for route in routes}
    assert by_id["courtlistener_recap"]["role"].startswith(
        "free_docket_metadata"
    )
    assert by_id["pacer_case_locator"]["role"] == (
        "official_exact_case_metadata_lookup"
    )
    assert by_id["edva_clerk_copy_request"]["role"] == (
        "official_copy_request_for_electronic_or_paper_files"
    )
    assert "edva_public_access_terminal" in by_id
    assert "federal_records_archive" in by_id


def test_probe_is_bounded_and_checks_both_sentinels_and_post_contract() -> None:
    client, session = _client(
        [
            FakeResponse(
                _fixture("docket_33467987.json"),
                url=f"{query_edva_bankruptcy.DOCKETS_URL}33467987/",
            ),
            FakeResponse(
                _fixture("entries_empty.json"),
                url=query_edva_bankruptcy.DOCKET_ENTRIES_URL,
            ),
            FakeResponse(
                _fixture("docket_49921079.json"),
                url=f"{query_edva_bankruptcy.DOCKETS_URL}49921079/",
            ),
            FakeResponse(
                _fixture("entries_empty.json"),
                url=query_edva_bankruptcy.DOCKET_ENTRIES_URL,
            ),
            FakeResponse(
                _fixture("options_recap_fetch.json"),
                url=query_edva_bankruptcy.RECAP_FETCH_URL,
            ),
        ]
    )

    result = query_edva_bankruptcy.execute(
        _parse("probe"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["probe_scope"] == {
        "bounded": True,
        "docket_entry_pages_per_target": 1,
        "coverage_inference": False,
    }
    assert len(record["sentinel_observations"]) == 2
    assert all(
        row["matches_sentinel"] for row in record["sentinel_observations"]
    )
    assert record["recap_fetch_contract_present"] is True
    assert record["healthy"] is True
    entry_calls = [
        call
        for call in session.calls
        if call["url"] == query_edva_bankruptcy.DOCKET_ENTRIES_URL
    ]
    assert len(entry_calls) == 2


def test_case_query_records_caller_bound_separately_from_transport_pages() -> None:
    client, _session = _client(
        [
            FakeResponse(
                _fixture("dockets_exact.json"),
                url=query_edva_bankruptcy.DOCKETS_URL,
            ),
            FakeResponse(
                _fixture("entries_page_1.json"),
                url=query_edva_bankruptcy.DOCKET_ENTRIES_URL,
            ),
        ]
    )

    result = query_edva_bankruptcy.execute(
        _parse("case", "05-39367", "--entry-limit", "1"),
        client=client,
        log_results=False,
    )

    docket = result.to_dict()["records"][0]
    coverage = docket["coverage"]
    assert coverage["entries_returned"] == 1
    assert coverage["caller_limit"] == 1
    assert coverage["caller_bound_reached"] is True
    assert coverage["transport_pages_fetched"] == 1
    assert result.next_cursor is not None
