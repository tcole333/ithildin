from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_georgia_supreme_docket as ga_docket
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy, SourceSchemaError


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/georgia_supreme_docket"
)


def _fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


SEARCH_CASES = _fixture("search_cases.json")
SEARCH_ATTORNEY = _fixture("search_attorney.json")
DETAIL_CURRENT = _fixture("detail_current.json")
DETAIL_JUDGMENT = _fixture("detail_judgment.json")
SYSTEM_DATA = _fixture("system_data.json")


@dataclass
class FixtureResponse:
    body: Any
    status_code: int = 200
    url: str = ga_docket.SEARCH_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/json"}
    )

    @property
    def content(self) -> bytes:
        if isinstance(self.body, bytes):
            return self.body
        return json.dumps(self.body).encode("utf-8")

    @property
    def text(self) -> str:
        if isinstance(self.body, bytes):
            return self.body.decode("utf-8", errors="replace")
        return json.dumps(self.body)

    def json(self) -> Any:
        return self.body


class SequenceSession:
    def __init__(self, *responses: FixtureResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FixtureResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _client(
    *responses: FixtureResponse,
) -> tuple[ga_docket.GeorgiaSupremeDocketClient, SequenceSession]:
    session = SequenceSession(*responses)
    return (
        ga_docket.GeorgiaSupremeDocketClient(
            session=session,
            minimum_interval=0,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        session,
    )


def _parse(*values: str) -> argparse.Namespace:
    return ga_docket.build_parser().parse_args(list(values))


def _probe_search_row() -> dict[str, Any]:
    return {
        key: DETAIL_CURRENT[key]
        for key in (
            "docketDate",
            "caseType",
            "caseStyle",
            "caseNumber",
            "caseStatus",
            "lowerCourtCaseNumbers",
        )
    }


def test_manifest_preserves_scope_routes_and_official_complements() -> None:
    manifest = ga_docket.source_manifest()

    assert manifest["source_id"] == (
        "us-ga-supreme-court-public-docket"
    )
    assert manifest["scope"]["case_window"] == (
        "cases docketed in the last 5 years"
    )
    assert manifest["verified_endpoints"]["case_search"].endswith(
        "/api/public-docket/query"
    )
    assert set(manifest["search_modes"]) == set(ga_docket.SEARCH_FIELDS)
    assert manifest["pagination"] == {
        "native_api": "none",
        "response_shape": "complete JSON array",
        "portal_table": "client-side paginator with 20 rows",
        "adapter": "snapshot-bound local offset cursor",
    }
    complements = {
        item["name"]: item
        for item in manifest["adjacent_official_sources"]
    }
    assert complements["Supreme Court opinions and summaries"]["adds"] == (
        "opinion PDFs, decision and argument dates"
    )
    assert complements["Discretionary applications granted"]["gap"] == (
        "grants only"
    )
    assert manifest["document_access"]["api_file_urls"] is False
    assert manifest["document_access"]["handoff"][
        "request_submitted"
    ] is False


@pytest.mark.parametrize(
    ("field", "query", "county_id", "expected"),
    [
        (
            "case-number",
            "s26g",
            None,
            (("queryFilter", "CaseNumber STARTS_WITH S26G"),),
        ),
        (
            "case-style",
            "American,  Honda",
            None,
            (
                ("queryFilter", "CaseStyle CONTAINS American"),
                ("queryFilter", "CaseStyle CONTAINS Honda"),
            ),
        ),
        (
            "party",
            "Jonathan Christianson",
            None,
            (
                ("queryFilter", "Party CONTAINS Jonathan"),
                ("queryFilter", "Party CONTAINS Christianson"),
            ),
        ),
        (
            "lower-court-case-number",
            "2018CV02040",
            "31",
            (
                (
                    "queryFilter",
                    "LowerCaseNumbers CONTAINS 2018CV02040",
                ),
                ("queryFilter", "TrialCourtCounty EQUALS 31"),
            ),
        ),
        (
            "court-of-appeals-case-number",
            "a25a1237",
            None,
            (("queryFilter", "AssociatedCase EQUALS A25A1237"),),
        ),
        (
            "attorney",
            "Blackwell",
            None,
            (("lastName", "Blackwell"),),
        ),
    ],
)
def test_search_parameter_translation_matches_verified_portal_grammar(
    field: str,
    query: str,
    county_id: str | None,
    expected: tuple[tuple[str, str], ...],
) -> None:
    assert ga_docket.build_search_parameters(
        field,
        query,
        county_id=county_id,
    ) == expected


def test_lower_court_search_requires_county_without_restricting_other_queries() -> None:
    with pytest.raises(
        ga_docket.GeorgiaSupremeDocketSelectionError
    ) as raised:
        ga_docket.build_search_parameters(
            "lower-court-case-number",
            "2018CV02040",
        )
    assert raised.value.code == "county_required"

    with pytest.raises(
        ga_docket.GeorgiaSupremeDocketSelectionError
    ) as raised:
        ga_docket.build_search_parameters(
            "party",
            "Christianson",
            county_id="31",
        )
    assert raised.value.code == "county_not_used"


def test_search_parser_and_normalizer_preserve_native_case_pivots() -> None:
    parsed = ga_docket.parse_search_payload(
        SEARCH_CASES,
        source_url=ga_docket.SEARCH_URL,
    )
    record = ga_docket.normalize_search_record(
        parsed.records[0],
        field="case-number",
        query="S26G",
    )

    assert len(parsed.records) == 3
    assert len(parsed.schema_fingerprint) == 64
    assert record["case_number"] == "S26G0021"
    assert record["lower_court_case_numbers"] == [
        "24DP01828",
        "24DP01831",
    ]
    assert record["canonical_ref"].startswith("STATECOURT:")
    assert record["source_scope"] == {"docketed_within_last_years": 5}
    assert record["raw_source"] == SEARCH_CASES[0]
    assert record["adjacent_official_routes"][0]["url"].endswith(
        "/2026-opinions/"
    )


def test_search_parser_distinguishes_empty_results_from_schema_drift() -> None:
    empty = ga_docket.parse_search_payload(
        [],
        source_url=ga_docket.SEARCH_URL,
    )
    assert empty.records == ()

    changed = [dict(SEARCH_CASES[0])]
    del changed[0]["caseStatus"]
    with pytest.raises(SourceSchemaError) as raised:
        ga_docket.parse_search_payload(
            changed,
            source_url=ga_docket.SEARCH_URL,
        )
    assert "fields changed" in str(raised.value)


def test_local_cursor_is_bound_to_query_and_complete_source_snapshot() -> None:
    client, session = _client(
        FixtureResponse(SEARCH_CASES),
        FixtureResponse(SEARCH_CASES),
    )

    first = client.search("case-number", "S26G", limit=2)
    second = client.search(
        "case-number",
        "S26G",
        limit=2,
        cursor=first.next_cursor,
    )

    assert [item["caseNumber"] for item in first.records] == [
        "S26G0021",
        "S26G0149",
    ]
    assert [item["caseNumber"] for item in second.records] == [
        "S26G0456"
    ]
    assert first.source_total_count == 3
    assert first.next_cursor is not None
    assert second.next_cursor is None
    assert session.calls[0]["params"] == [
        ("queryFilter", "CaseNumber STARTS_WITH S26G")
    ]
    assert "page" not in dict(session.calls[0]["params"])


def test_local_cursor_fails_cleanly_when_upstream_array_changes() -> None:
    changed = json.loads(json.dumps(SEARCH_CASES))
    changed[0]["caseStatus"] = "Remittitur"
    client, _session = _client(
        FixtureResponse(SEARCH_CASES),
        FixtureResponse(changed),
    )

    first = client.search("case-number", "S26G", limit=1)
    with pytest.raises(
        ga_docket.GeorgiaSupremeDocketSelectionError
    ) as raised:
        client.search(
            "case-number",
            "S26G",
            limit=1,
            cursor=first.next_cursor,
        )
    assert raised.value.code == "cursor_snapshot_changed"


def test_detail_normalization_preserves_filings_orders_attorneys_and_handoff() -> None:
    parsed = ga_docket.parse_detail_payload(
        DETAIL_CURRENT,
        requested_case_number="S26G0537",
        source_url=(
            f"{ga_docket.CASE_DETAIL_ROOT}/S26G0537"
        ),
    )
    record = ga_docket.normalize_detail_record(parsed)

    assert record["case_number"] == "S26G0537"
    assert record["description"] == "Civil - Granted Certiorari"
    assert record["lower_court_case_numbers"] == ["2018CV02040"]
    assert record["calendar"] == {
        "is_calendar_case": True,
        "calendar": "November 2026",
        "argument_date": None,
        "argument_date_is_provisional": False,
    }
    first_filing = record["docket_entries"][0]
    assert first_filing["filing_type"].startswith("CERTIORARI")
    assert first_filing["order_type"] == "Certiorari granted"
    assert first_filing["document_url"] is None
    assert first_filing["document_access"] == "request_from_clerk"
    assert first_filing["event_id"].startswith(
        "ga-supreme-docket-event:"
    )
    assert record["attorneys"][0]["display_name"] == (
        "Keith Robert Blackwell"
    )
    inventory = record["document_inventory"]
    assert inventory["state"] == "metadata_only"
    assert inventory["public_document_urls"] == []
    assert inventory["request_handoff"]["phone"] == "+1-404-656-3470"
    assert inventory["request_handoff"]["request_submitted"] is False


def test_completed_case_detail_preserves_judgment_metadata() -> None:
    parsed = ga_docket.parse_detail_payload(
        DETAIL_JUDGMENT,
        requested_case_number="S24C0420",
        source_url=f"{ga_docket.CASE_DETAIL_ROOT}/S24C0420",
    )
    record = ga_docket.normalize_detail_record(parsed)

    assert record["case_status"] == "Remittitur"
    assert record["judgments"] == [
        {
            "sequence": 1,
            "judgment": "Certiorari - Writ denied",
            "judgment_line": "All the Justices concur.",
            "judgment_date": "2024-03-27",
            "raw_source": DETAIL_JUDGMENT["judgments"][0],
        }
    ]


def test_documents_command_returns_metadata_candidates_and_non_submitting_handoff() -> None:
    client, session = _client(
        FixtureResponse(
            DETAIL_CURRENT,
            url=f"{ga_docket.CASE_DETAIL_ROOT}/S26G0537",
        )
    )
    result = ga_docket.execute(
        _parse("documents", "S26G0537"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    record = result.to_dict()["records"][0]
    assert record["document_inventory_state"] == (
        "metadata_only_no_public_file_urls"
    )
    assert len(record["filing_candidates"]) == 2
    assert record["request_handoff"]["request_submitted"] is False
    assert record["request_handoff"]["fee_may_apply"] is True
    assert session.calls[0]["url"].endswith(
        "/api/public-docket/case/S26G0537"
    )


def test_detail_404_is_authoritative_no_result() -> None:
    client, _session = _client(
        FixtureResponse(
            b"",
            status_code=404,
            url=f"{ga_docket.CASE_DETAIL_ROOT}/S99A9999",
        )
    )
    result = ga_docket.execute(
        _parse("detail", "S99A9999"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_attorney_search_resolves_native_party_type_without_losing_id() -> None:
    client, session = _client(
        FixtureResponse(
            SEARCH_ATTORNEY,
            url=ga_docket.ATTORNEY_SEARCH_URL,
        ),
        FixtureResponse(
            SYSTEM_DATA,
            url=ga_docket.SYSTEM_DATA_URL,
        ),
    )
    result = ga_docket.execute(
        _parse(
            "search",
            "Blackwell",
            "--field",
            "attorney",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["attorney_search_match"] == {
        "first_name": "Keith",
        "last_name": "Blackwell",
        "party_type_native_id": "403",
        "party_type": "Appellant",
    }
    assert record["retrieval"]["source_total_count"] == 2
    assert result.next_cursor is not None
    assert session.calls[0]["url"] == ga_docket.ATTORNEY_SEARCH_URL
    assert session.calls[1]["url"] == ga_docket.SYSTEM_DATA_URL


def test_named_county_is_resolved_before_lower_court_search() -> None:
    client, session = _client(
        FixtureResponse(
            SYSTEM_DATA,
            url=ga_docket.SYSTEM_DATA_URL,
        ),
        FixtureResponse(
            [_probe_search_row()],
            url=ga_docket.SEARCH_URL,
        ),
    )
    result = ga_docket.execute(
        _parse(
            "search",
            "2018CV02040",
            "--field",
            "lower-court-case-number",
            "--county",
            "clayton",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert session.calls[1]["params"] == [
        (
            "queryFilter",
            "LowerCaseNumbers CONTAINS 2018CV02040",
        ),
        ("queryFilter", "TrialCourtCounty EQUALS 31"),
    ]
    assert ga_docket.SYSTEM_DATA_URL in result.raw_artifact_refs


def test_counties_command_exposes_native_id_and_county_code() -> None:
    client, _session = _client(
        FixtureResponse(
            SYSTEM_DATA,
            url=ga_docket.SYSTEM_DATA_URL,
        )
    )
    result = ga_docket.execute(
        _parse("counties"),
        client=client,
        log_results=False,
    )

    records = result.to_dict()["records"]
    assert [(item["name"], item["county_id"]) for item in records] == [
        ("Appling", "1"),
        ("Clayton", "31"),
    ]
    assert records[1]["county_code"] == "031"


def test_probe_is_bounded_to_exact_search_plus_detail() -> None:
    client, session = _client(
        FixtureResponse(
            [_probe_search_row()],
            url=ga_docket.SEARCH_URL,
        ),
        FixtureResponse(
            DETAIL_CURRENT,
            url=f"{ga_docket.CASE_DETAIL_ROOT}/S26G0537",
        ),
    )
    result = ga_docket.execute(
        _parse("probe", "--case-number", "S26G0537"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    probe = result.to_dict()["records"][0]
    assert probe["requests_made"] == 2
    assert probe["rolling_observation"]["case_number"] == "S26G0537"
    assert probe["rolling_observation"]["filing_metadata_count"] == 2
    assert len(session.calls) == 2


def test_parser_exposes_stable_standalone_operations() -> None:
    assert _parse("manifest", "--json").command == "manifest"
    search = _parse(
        "search",
        "Honda",
        "--field",
        "case-style",
        "--cursor",
        (
            "ga-supreme-docket:v1:query:0000000000000000:"
            "snapshot:1111111111111111:offset:20"
        ),
    )
    assert search.field == "case-style"
    assert search.limit == ga_docket.DEFAULT_LIMIT
    assert search.cursor.endswith("offset:20")
    assert _parse("documents", "S26G0537").case_number == "S26G0537"
    assert _parse("counties").command == "counties"
