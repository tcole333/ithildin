"""Tests for the shared public-record query and result contract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsError,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    ResultStatus,
    SourceMetadata,
    canonical_json,
)


def _query(parameters=None) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SourceMetadata(
            source_id="nyc-acris-master",
            name="NYC ACRIS Real Property Master",
            source_role="recorder_index",
            base_url="https://data.cityofnewyork.us/resource",
            dataset_id="bnx9-e6tj",
            metadata={"operator": "NYC Department of Finance"},
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="US-NY-NYC",
            name="New York City",
            state_code="ny",
            county_fips="36061",
            metadata={"borough": "Manhattan"},
        ),
        query=QueryMetadata(
            operation="party_search",
            parameters=parameters or {"$where": "name='EXAMPLE LLC'", "active": True},
            requested_limit=25,
            metadata={"purpose": "property research"},
        ),
    )


def test_query_fingerprint_uses_canonical_json_and_all_context():
    first = _query({"z": [2, 1], "a": {"last": False, "first": "Å"}})
    second = _query({"a": {"first": "Å", "last": False}, "z": [2, 1]})

    assert first.fingerprint == second.fingerprint
    assert first.to_json() == second.to_json()

    payload_json = canonical_json(first.fingerprint_payload())
    expected = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    assert first.fingerprint == expected
    assert len(first.fingerprint) == 64

    other_jurisdiction = PublicRecordsQuery(
        source=first.source,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="US-NY-QUEENS",
            name="Queens County",
            state_code="NY",
            county_fips="36081",
        ),
        query=first.query,
    )
    assert other_jurisdiction.fingerprint != first.fingerprint


def test_query_detaches_and_freezes_mutable_metadata():
    parameters = {"where": {"owner": "EXAMPLE LLC"}}
    query = _query(parameters)
    fingerprint = query.fingerprint

    parameters["where"]["owner"] = "CHANGED LLC"

    assert query.fingerprint == fingerprint
    assert query.query.parameters["where"]["owner"] == "EXAMPLE LLC"
    with pytest.raises(TypeError):
        query.query.parameters["new"] = "value"


def test_canonical_json_rejects_ambiguous_or_nonstandard_values():
    with pytest.raises(TypeError, match="non-string mapping key"):
        canonical_json({1: "not a JSON object key"})
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"value": float("nan")})
    with pytest.raises(TypeError, match="unsupported JSON value"):
        canonical_json({"value": {1, 2}})


def test_result_serialization_is_deterministic_and_complete():
    query = _query()
    result = PublicRecordsResult.success(
        query,
        [{"document_id": "20260001", "amount": 1_000_000}],
        retrieved_at=datetime(2026, 7, 28, 16, 30, tzinfo=timezone.utc),
        next_cursor="socrata:offset:25",
        raw_artifact_refs=["sha256:abc"],
        warnings=["Index records are not proof of current title."],
    )

    assert result.status == ResultStatus.OK
    assert result.to_json() == result.to_json()
    decoded = json.loads(result.to_json())
    assert decoded == {
        "errors": [],
        "next_cursor": "socrata:offset:25",
        "query": query.to_dict(),
        "raw_artifact_refs": ["sha256:abc"],
        "records": [{"amount": 1_000_000, "document_id": "20260001"}],
        "retrieved_at": "2026-07-28T16:30:00Z",
        "schema_version": "public-records-result/1.0",
        "status": "ok",
        "warnings": ["Index records are not proof of current title."],
    }


def test_success_distinguishes_authoritative_empty_results():
    result = PublicRecordsResult.success(
        _query(),
        [],
        retrieved_at="2026-07-28T12:00:00-04:00",
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.retrieved_at == "2026-07-28T16:00:00Z"


def test_failures_cannot_be_collapsed_into_no_results():
    error = PublicRecordsError(
        code="transport_error",
        message="connection timed out",
        category="transport",
        retryable=True,
        details={"attempts": 3},
    )
    result = PublicRecordsResult.failure(
        _query(),
        ResultStatus.UNAVAILABLE,
        [error],
        retrieved_at="2026-07-28T16:30:00Z",
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.records == ()
    assert result.errors == (error,)

    with pytest.raises(ValueError, match="no_results cannot contain errors"):
        PublicRecordsResult(
            query=_query(),
            status=ResultStatus.NO_RESULTS,
            retrieved_at="2026-07-28T16:30:00Z",
            errors=[error],
        )
    with pytest.raises(ValueError, match="must contain an explicit error"):
        PublicRecordsResult(
            query=_query(),
            status=ResultStatus.RATE_LIMITED,
            retrieved_at="2026-07-28T16:30:00Z",
        )


def test_status_vocabulary_is_exact():
    assert {status.value for status in ResultStatus} == {
        "ok",
        "no_results",
        "partial",
        "unavailable",
        "restricted",
        "human_required",
        "rate_limited",
        "terms_blocked",
        "source_changed",
    }
