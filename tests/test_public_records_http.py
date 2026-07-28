"""Offline tests for reusable Socrata and ArcGIS public-record clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    QueryMetadata,
    ResultStatus,
    SourceMetadata,
)
from tools.public_records_http import (
    ArcGISRESTClient,
    HTTPStatusError,
    MinimumIntervalRateLimiter,
    PaginationError,
    RateLimitedHTTPError,
    RestrictedHTTPError,
    RetryPolicy,
    SocrataSODAClient,
    SourceResponseError,
    SourceSchemaError,
    TermsBlockedHTTPError,
    TransportError,
    failure_result,
)


@dataclass
class FakeResponse:
    payload: Any
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""

    def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class QueueTransport:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def request(self, method, url, *, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.outcomes:
            raise AssertionError("unexpected HTTP request")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def _query() -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SourceMetadata(
            source_id="test-source",
            name="Test Source",
            source_role="assessor",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="US-TEST",
            name="Test Jurisdiction",
        ),
        query=QueryMetadata(operation="search", parameters={"owner": "EXAMPLE"}),
    )


def test_socrata_paginates_to_requested_limit_with_injected_session():
    transport = QueueTransport(
        [
            FakeResponse([{"id": "1", "owner": "A"}, {"id": "2", "owner": "B"}]),
            FakeResponse([{"owner": "C", "id": "3"}, {"owner": "D", "id": "4"}]),
            FakeResponse([{"id": "5", "owner": "E"}]),
        ]
    )
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        app_token="token",
        page_size=2,
        session=transport,
        minimum_interval=0,
    )

    result = client.query(
        {"$where": "owner is not null", "$order": "id"},
        requested_limit=10,
    )

    assert [record["id"] for record in result.records] == ["1", "2", "3", "4", "5"]
    assert result.pages_fetched == 3
    assert result.requests_made == 3
    assert result.next_cursor is None
    assert not result.truncated_by_cap
    assert len(result.schema_fingerprint) == 64
    assert [call["params"]["$offset"] for call in transport.calls] == [0, 2, 4]
    assert [call["params"]["$limit"] for call in transport.calls] == [2, 2, 2]
    assert all(call["headers"]["X-App-Token"] == "token" for call in transport.calls)


def test_socrata_returns_continuation_and_partial_when_safety_cap_wins():
    transport = QueueTransport(
        [
            FakeResponse([{"id": 1}, {"id": 2}]),
            FakeResponse([{"id": 3}]),
        ]
    )
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        page_size=2,
        max_records=3,
        transport=transport,
        minimum_interval=0,
    )

    fetch = client.query(requested_limit=10)
    envelope = fetch.to_result(_query())

    assert len(fetch.records) == 3
    assert fetch.next_cursor == "socrata:offset:3"
    assert fetch.truncated_by_cap
    assert "configured cap is 3" in fetch.warnings[0]
    assert envelope.status == ResultStatus.PARTIAL
    assert envelope.next_cursor == "socrata:offset:3"


def test_rate_limiter_enforces_minimum_interval_between_pages():
    fake_time = FakeTime()
    transport = QueueTransport(
        [
            FakeResponse([{"id": 1}]),
            FakeResponse([]),
        ]
    )
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        page_size=1,
        transport=transport,
        minimum_interval=1.25,
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    result = client.query(requested_limit=5)

    assert len(result.records) == 1
    assert fake_time.sleeps == [1.25]


def test_minimum_interval_rate_limiter_rejects_negative_interval():
    with pytest.raises(ValueError, match="must not be negative"):
        MinimumIntervalRateLimiter(-0.01)


def test_transport_retry_is_bounded_and_maps_to_unavailable_not_no_results():
    fake_time = FakeTime()
    transport = QueueTransport(
        [TimeoutError("one"), TimeoutError("two"), TimeoutError("three")]
    )
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        transport=transport,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=3,
            backoff_initial=0.5,
            backoff_multiplier=2,
            max_backoff=5,
        ),
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    with pytest.raises(TransportError) as exc_info:
        client.query(requested_limit=1)

    assert len(transport.calls) == 3
    assert fake_time.sleeps == [0.5, 1.0]
    envelope = failure_result(_query(), exc_info.value)
    assert envelope.status == ResultStatus.UNAVAILABLE
    assert envelope.status != ResultStatus.NO_RESULTS
    assert envelope.errors[0].retryable
    assert envelope.errors[0].details["attempts"] == 3


def test_rate_limit_retries_and_retry_after_are_bounded():
    fake_time = FakeTime()
    transport = QueueTransport(
        [
            FakeResponse({}, status_code=429, headers={"Retry-After": "60"}),
            FakeResponse({}, status_code=429, headers={"Retry-After": "60"}),
            FakeResponse({}, status_code=429, headers={"Retry-After": "60"}),
        ]
    )
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        transport=transport,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=3, max_backoff=2),
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    with pytest.raises(RateLimitedHTTPError) as exc_info:
        client.query(requested_limit=1)

    assert len(transport.calls) == 3
    assert fake_time.sleeps == [2, 2]
    assert failure_result(_query(), exc_info.value).status == ResultStatus.RATE_LIMITED


def test_server_error_retries_are_bounded_and_remain_retryable():
    fake_time = FakeTime()
    transport = QueueTransport(
        [
            FakeResponse("upstream", status_code=503, text="upstream"),
            FakeResponse("upstream", status_code=503, text="upstream"),
            FakeResponse("upstream", status_code=503, text="upstream"),
        ]
    )
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        transport=transport,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=3),
        clock=fake_time.monotonic,
        sleeper=fake_time.sleep,
    )

    with pytest.raises(HTTPStatusError) as exc_info:
        client.query(requested_limit=1)

    assert len(transport.calls) == 3
    assert fake_time.sleeps == [0.25, 0.5]
    assert exc_info.value.retryable


@pytest.mark.parametrize(
    ("status_code", "error_type", "result_status"),
    [
        (403, RestrictedHTTPError, ResultStatus.RESTRICTED),
        (451, TermsBlockedHTTPError, ResultStatus.TERMS_BLOCKED),
    ],
)
def test_access_failures_are_explicit_and_not_retried(
    status_code, error_type, result_status
):
    transport = QueueTransport([FakeResponse({}, status_code=status_code)])
    client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        transport=transport,
        minimum_interval=0,
    )

    with pytest.raises(error_type) as exc_info:
        client.query(requested_limit=1)

    assert len(transport.calls) == 1
    assert failure_result(_query(), exc_info.value).status == result_status


def test_socrata_source_error_and_schema_change_are_not_empty_results():
    source_error_client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        transport=QueueTransport(
            [FakeResponse({"error": True, "message": "invalid SoQL"})]
        ),
        minimum_interval=0,
    )
    with pytest.raises(SourceResponseError) as source_error:
        source_error_client.query(requested_limit=1)
    assert (
        failure_result(_query(), source_error.value).status == ResultStatus.UNAVAILABLE
    )

    schema_client = SocrataSODAClient(
        "https://example.test/resource",
        "abcd-1234",
        transport=QueueTransport([FakeResponse({"records": []})]),
        minimum_interval=0,
    )
    with pytest.raises(SourceSchemaError) as schema_error:
        schema_client.query(requested_limit=1)
    assert (
        failure_result(_query(), schema_error.value).status
        == ResultStatus.SOURCE_CHANGED
    )


def test_arcgis_paginates_on_transfer_limit_and_uses_declared_schema():
    fields = [
        {"name": "OWNER", "type": "esriFieldTypeString", "length": 120},
        {"name": "OBJECTID", "type": "esriFieldTypeOID"},
    ]
    transport = QueueTransport(
        [
            FakeResponse(
                {
                    "fields": fields,
                    "features": [
                        {"attributes": {"OBJECTID": 1, "OWNER": "A"}},
                        {"attributes": {"OBJECTID": 2, "OWNER": "B"}},
                    ],
                    "exceededTransferLimit": True,
                }
            ),
            FakeResponse(
                {
                    "fields": list(reversed(fields)),
                    "features": [
                        {"attributes": {"OBJECTID": 3, "OWNER": "C"}},
                    ],
                    "exceededTransferLimit": False,
                }
            ),
        ]
    )
    client = ArcGISRESTClient(
        "https://example.test/FeatureServer/0",
        page_size=2,
        transport=transport,
        minimum_interval=0,
    )

    result = client.query(
        where="OWNER IS NOT NULL",
        out_fields=["OBJECTID", "OWNER"],
        requested_limit=10,
    )

    assert [feature["attributes"]["OBJECTID"] for feature in result.records] == [
        1,
        2,
        3,
    ]
    assert result.pages_fetched == 2
    assert result.next_cursor is None
    assert result.schema["kind"] == "arcgis_declared"
    assert [field["name"] for field in result.schema["fields"]] == [
        "OBJECTID",
        "OWNER",
    ]
    assert len(result.schema_fingerprint) == 64
    assert [call["params"]["resultOffset"] for call in transport.calls] == [0, 2]
    assert all(
        call["params"]["outFields"] == "OBJECTID,OWNER" for call in transport.calls
    )


def test_arcgis_safety_cap_returns_cursor_without_overfetching():
    transport = QueueTransport(
        [
            FakeResponse(
                {
                    "features": [
                        {"attributes": {"OBJECTID": 1}},
                        {"attributes": {"OBJECTID": 2}},
                    ],
                    "exceededTransferLimit": True,
                }
            ),
            FakeResponse(
                {
                    "features": [{"attributes": {"OBJECTID": 3}}],
                    "exceededTransferLimit": True,
                }
            ),
        ]
    )
    client = ArcGISRESTClient(
        "https://example.test/FeatureServer/0",
        page_size=2,
        max_records=3,
        transport=transport,
        minimum_interval=0,
    )

    result = client.query(requested_limit=100)

    assert len(result.records) == 3
    assert result.next_cursor == "arcgis:offset:3"
    assert result.truncated_by_cap
    assert [call["params"]["resultRecordCount"] for call in transport.calls] == [
        2,
        1,
    ]


def test_arcgis_repeated_page_fails_instead_of_looping():
    page = {
        "features": [{"attributes": {"OBJECTID": 1}}],
        "exceededTransferLimit": True,
    }
    transport = QueueTransport([FakeResponse(page), FakeResponse(page)])
    client = ArcGISRESTClient(
        "https://example.test/FeatureServer/0",
        page_size=1,
        transport=transport,
        minimum_interval=0,
    )

    with pytest.raises(PaginationError):
        client.query(requested_limit=5)

    assert len(transport.calls) == 2


def test_arcgis_error_payload_is_an_explicit_source_failure():
    transport = QueueTransport(
        [
            FakeResponse(
                {
                    "error": {
                        "code": 400,
                        "message": "Unable to complete operation",
                    }
                }
            )
        ]
    )
    client = ArcGISRESTClient(
        "https://example.test/FeatureServer/0",
        transport=transport,
        minimum_interval=0,
    )

    with pytest.raises(SourceResponseError) as exc_info:
        client.query(requested_limit=1)

    envelope = failure_result(_query(), exc_info.value)
    assert envelope.status == ResultStatus.UNAVAILABLE
    assert envelope.status != ResultStatus.NO_RESULTS
