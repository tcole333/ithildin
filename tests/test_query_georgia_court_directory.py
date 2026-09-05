from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_georgia_court_directory as directory
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_ROOT = Path(
    "tests/fixtures/public_records/georgia_court_directory"
)


def _fixture(name: str) -> Any:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _Response:
    def __init__(
        self,
        payload: Any,
        *,
        status_code: int = 200,
        url: str = directory.SEARCH_API_URL,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.url = url
        self.headers = dict(headers or {"content-type": "application/json"})
        self.text = json.dumps(payload)

    def json(self) -> Any:
        return copy.deepcopy(self._payload)


class _QueueSession:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> _Response:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params),
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("fixture session has no response left")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _args(*values: str):
    return directory.build_parser().parse_args(list(values))


def _client(session: _QueueSession) -> directory.GeorgiaCourtDirectoryClient:
    return directory.GeorgiaCourtDirectoryClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )


def test_manifest_keeps_views_classifications_and_complements_distinct() -> None:
    manifest = directory.source_manifest()

    assert manifest["source_id"] == (
        "us-ga-aoc-court-personnel-directory"
    )
    assert manifest["operations"]["search"]["view_id"] == "view_5"
    assert manifest["operations"]["detail"]["view_id"] == "view_6"
    fields = {
        item["name"]: item for item in manifest["search_fields"]
    }
    assert fields["city"]["field"] == "field_79"
    assert fields["city"]["result_field"] == "field_8"
    assert "municipal-judge city" in fields["city"]["input_scope"]
    assert fields["court_class"]["field"] == "field_18"
    assert fields["directory_section"]["field"] == "field_19"
    anomalies = manifest["observed_source_anomalies"]
    assert any(item.get("field") == "field_3" for item in anomalies)
    assert (
        manifest["classifications"]["court_class"]["options"]
        != manifest["classifications"]["directory_section"]["options"]
    )
    complements = {item["name"]: item for item in manifest["complements"]}
    gsccca = complements[
        "Georgia Superior Court Clerks' Cooperative Authority"
    ]
    assert "separate statewide indices" in gsccca["role"]
    assert complements["Official local court and county sites"][
        "authority"
    ] == "the relevant court or county"


def test_build_filters_uses_verified_fields_and_operators() -> None:
    filters = directory.build_filters(
        {
            "first": " Marla ",
            "county": "Fulton",
            "court_class": "Superior",
            "directory_section": "Superior Court Clerks",
        }
    )

    assert filters == (
        {"field": "field_1", "operator": "contains", "value": "Marla"},
        {
            "field": "field_15",
            "operator": "contains",
            "value": "Fulton",
        },
        {"field": "field_18", "operator": "is", "value": "Superior"},
        {
            "field": "field_19",
            "operator": "is",
            "value": "Superior Court Clerks",
        },
    )


def test_search_view_request_has_public_headers_and_native_filter_json() -> None:
    session = _QueueSession([_Response(_fixture("search-page-1.json"))])
    client = _client(session)
    filters = directory.build_filters(
        {"directory_section": "Superior Court Clerks"}
    )

    page = client.search_page(filters, page=1, page_size=2)

    assert page.total_records == 4
    assert len(page.records) == 2
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == directory.SEARCH_API_URL
    assert call["params"]["page"] == 1
    assert call["params"]["rows_per_page"] == 2
    assert json.loads(call["params"]["filters"]) == list(filters)
    assert call["headers"]["X-Knack-Application-Id"] == directory.APP_ID
    assert call["headers"]["X-Knack-REST-API-Key"] == "knack"


def test_search_cursor_resumes_inside_a_native_page_and_binds_filters() -> None:
    filters = directory.build_filters({"county": "Fulton"})
    first_session = _QueueSession(
        [
            _Response(_fixture("search-page-1.json")),
            _Response(_fixture("search-page-2.json")),
        ]
    )
    first = _client(first_session).search(
        filters,
        limit=3,
        page_size=2,
    )

    assert [row["id"] for row in first.records] == [
        "58af01d3ce9168f520c4cec9",
        "58af01d3ce9168f520c4ceca",
        "58af01d3ce9168f520c4cecb",
    ]
    assert first.pages_fetched == 2
    assert first.next_cursor is not None
    assert first.next_cursor.endswith(":size:2:page:2:row:1")

    second_session = _QueueSession(
        [_Response(_fixture("search-page-2.json"))]
    )
    second = _client(second_session).search(
        filters,
        limit=3,
        cursor=first.next_cursor,
        page_size=2,
    )
    assert [row["id"] for row in second.records] == [
        "58af01d3ce9168f520c4cecc"
    ]
    assert second.next_cursor is None
    assert second_session.calls[0]["params"]["page"] == 2

    with pytest.raises(
        directory.GeorgiaDirectorySelectionError,
        match="different Georgia directory filters",
    ):
        _client(_QueueSession([])).search(
            directory.build_filters({"county": "DeKalb"}),
            limit=1,
            cursor=first.next_cursor,
            page_size=2,
        )


def test_no_results_shape_is_authoritative_empty_not_a_failure() -> None:
    session = _QueueSession([_Response(_fixture("no-results.json"))])
    result = directory.execute(
        _args(
            "search",
            "--last",
            "zzzz-no-such-person",
            "--page-size",
            "2",
        ),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_detail_normalization_preserves_raw_and_separate_classifications() -> None:
    payload = _fixture("detail-superior-clerk.json")
    detail = directory.parse_detail(
        payload,
        requested_record_id=payload["id"],
        source_url=f"{directory.DETAIL_API_URL}/{payload['id']}",
    )
    record = directory.normalize_detail_record(detail)

    assert record["person"]["display_name"] == (
        "Chief Deputy Clerk Marla Robinson"
    )
    assert record["person"]["prefix_or_title"] == "Chief Deputy Clerk"
    assert record["classifications"]["court_classes"] == []
    assert record["classifications"]["directory_sections"] == [
        "Superior Court Clerks"
    ]
    assert record["classifications"]["chief_magistrate_indicator"] == "no"
    assert record["contact"] == {
        "phone": "(404) 555-0100",
        "fax": "(404) 555-0101",
        "email": "marla.robinson@example.gov",
        "email_visibility": "published",
        "source_display_email": True,
    }
    assert record["raw_fields"]["detail"]["field_19_raw"] == [
        "Superior Court Clerks"
    ]

    hidden_payload = copy.deepcopy(payload)
    hidden_payload["field_13_raw"] = "nobody@fake-email.com"
    hidden_payload["field_99_raw"] = False
    hidden = directory.normalize_detail_record(
        directory.parse_detail(
            hidden_payload,
            requested_record_id=payload["id"],
            source_url="https://example.test/detail",
        )
    )
    assert hidden["contact"]["email"] is None
    assert hidden["contact"]["email_visibility"] == "source_placeholder"
    assert hidden["raw_fields"]["detail"]["field_13_raw"] == (
        "nobody@fake-email.com"
    )


def test_search_details_hydrates_exact_view_and_keeps_selection_context() -> None:
    search_payload = copy.deepcopy(_fixture("search-page-1.json"))
    search_payload["total_records"] = 2
    search_payload["total_pages"] = 1
    detail_payload = _fixture("detail-superior-clerk.json")
    session = _QueueSession(
        [
            _Response(search_payload),
            _Response(
                detail_payload,
                url=f"{directory.DETAIL_API_URL}/{detail_payload['id']}",
            ),
        ]
    )
    result = directory.execute(
        _args(
            "search",
            "--directory-section",
            "Superior Court Clerks",
            "--limit",
            "1",
            "--page-size",
            "2",
            "--details",
        ),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    record = result.records[0]
    assert record["snapshot_state"] == "detail"
    assert record["selection_context"] == {
        "directory_section": "Superior Court Clerks"
    }
    assert record["classifications"]["directory_sections"] == (
        "Superior Court Clerks",
    )
    assert record["query_observation"] == {
        "source_total_count": 2,
        "source_total_pages": 1,
        "native_pages_fetched": 1,
        "search_requests_made": 1,
    }
    assert set(record["raw_fields"]) == {"search", "detail"}
    assert result.next_cursor is not None
    assert len(session.calls) == 2
    assert session.calls[1]["url"].endswith(detail_payload["id"])


def test_exact_detail_404_is_an_authoritative_no_result() -> None:
    record_id = "does-not-exist"
    session = _QueueSession(
        [
            _Response(
                {"error": "Record not found"},
                status_code=404,
                url=f"{directory.DETAIL_API_URL}/{record_id}",
            )
        ]
    )
    result = directory.execute(
        _args("detail", record_id),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_probe_is_two_requests_and_checks_filter_against_detail() -> None:
    search_payload = copy.deepcopy(_fixture("search-page-1.json"))
    search_payload["records"] = [search_payload["records"][0]]
    search_payload["total_records"] = 154
    search_payload["total_pages"] = 154
    detail_payload = _fixture("detail-superior-clerk.json")
    session = _QueueSession(
        [
            _Response(search_payload),
            _Response(
                detail_payload,
                url=f"{directory.DETAIL_API_URL}/{detail_payload['id']}",
            ),
        ]
    )
    result = directory.execute(
        _args("probe"),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["record_kind"] == "source_probe"
    assert probe["requests_made"] == 2
    assert probe["rolling_observation"]["matching_total_records"] == 154
    assert probe["rolling_observation"]["sample_directory_sections"] == (
        "Superior Court Clerks",
    )
    assert len(session.calls) == 2
    assert json.loads(session.calls[0]["params"]["filters"]) == [
        {
            "field": "field_19",
            "operator": "is",
            "value": "Superior Court Clerks",
        }
    ]


def test_missing_search_view_field_is_reported_as_source_changed() -> None:
    payload = copy.deepcopy(_fixture("search-page-1.json"))
    payload["records"][0].pop("field_15")
    session = _QueueSession([_Response(payload)])
    result = directory.execute(
        _args("search", "--page-size", "2"),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["missing_fields"] == ("field_15",)


def test_retry_is_bounded_and_reuses_published_view_headers() -> None:
    session = _QueueSession(
        [
            _Response({"error": "temporary"}, status_code=503),
            _Response(_fixture("search-page-1.json")),
        ]
    )
    client = directory.GeorgiaCourtDirectoryClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0,
        ),
        sleeper=lambda _seconds: None,
    )

    page = client.search_page([], page=1, page_size=2)

    assert page.total_records == 4
    assert client.request_count == 2
    assert len(session.calls) == 2
    assert all(
        call["headers"]["X-Knack-REST-API-Key"] == "knack"
        for call in session.calls
    )
