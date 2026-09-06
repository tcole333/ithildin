from __future__ import annotations

import pytest

from tools import query_ny_attorneys as ny_attorneys
from tools import query_state_courts
from tools.public_records_contract import PublicRecordsResult, ResultStatus


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_shared_routes_are_registration_specific_and_preserve_company_name() -> None:
    routes = query_state_courts.LIVE_ROUTES[ny_attorneys.SOURCE_ID]

    assert set(routes) == {"search", "detail", "discovery", "probe"}
    assert "case" not in routes
    assert "docket" not in routes
    assert "documents" not in routes

    search = routes["search"].translate(
        _shared_args(
            "search",
            "ACME HOLDINGS, LLC",
            "--source",
            ny_attorneys.SOURCE_ID,
            "--jurisdiction",
            "US-NY",
            "--entity-kind",
            "organization",
            "--limit",
            "7",
            "--minimum-interval",
            "0",
        ),
        routes["search"].adapter_command,
    )

    assert search.command == "search"
    assert search.query == "ACME HOLDINGS, LLC"
    assert search.field == "company"
    assert search.limit == 7
    assert search.minimum_interval == 0
    assert (
        "upper(company_name) LIKE '%ACME HOLDINGS, LLC%'"
        in ny_attorneys._search_where(search)
    )


def test_shared_search_preserves_snapshot_cursor_and_name_filters() -> None:
    routes = query_state_courts.LIVE_ROUTES[ny_attorneys.SOURCE_ID]
    cursor = ny_attorneys._cursor_encode(
        {
            "version": ny_attorneys.CURSOR_VERSION,
            "criteria": "a" * 64,
            "schema": "b" * 64,
            "rows_updated_at": 1_785_387_837,
            "total": 432_566,
            "offset": 25,
        }
    )
    search = routes["search"].translate(
        _shared_args(
            "search",
            "Karp",
            "--source",
            ny_attorneys.SOURCE_ID,
            "--first-name",
            "Brad",
            "--county",
            "New York",
            "--cursor",
            cursor,
            "--max-records",
            "25",
        ),
        routes["search"].adapter_command,
    )

    assert search.query == "Karp"
    assert search.field == "last-name"
    assert search.first == "Brad"
    assert search.county == "New York"
    assert search.cursor == cursor
    assert search.limit == 25
    assert cursor.startswith("ny-oca-attorneys:v2:")


def test_detail_discovery_and_probe_translate_without_case_semantics() -> None:
    routes = query_state_courts.LIVE_ROUTES[ny_attorneys.SOURCE_ID]

    detail = routes["detail"].translate(
        _shared_args(
            "detail",
            "2064509",
            "--source",
            ny_attorneys.SOURCE_ID,
            "--jurisdiction",
            "New York",
        ),
        routes["detail"].adapter_command,
    )
    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "routes",
            "--source",
            ny_attorneys.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "probe",
            "--source",
            ny_attorneys.SOURCE_ID,
            "--jurisdiction",
            "36",
        ),
        routes["probe"].adapter_command,
    )

    assert detail.command == "registration"
    assert detail.registration_number == "2064509"
    assert discovery.command == "sources"
    assert probe.command == "probe"


@pytest.mark.parametrize(
    ("operation", "selector", "options", "message"),
    [
        (
            "search",
            "Karp",
            ("--jurisdiction", "NJ"),
            "statewide New York",
        ),
        (
            "search",
            "Karp",
            ("--case-type", "civil"),
            "do not expose case",
        ),
        (
            "search",
            "Karp",
            ("--after", "2026-01-01"),
            "filing-date",
        ),
        (
            "search",
            "Karp",
            ("--court-id", "ny-supreme"),
            "court selectors",
        ),
        (
            "search",
            "2064509",
            ("--search-field", "registration-number"),
            "shared detail",
        ),
        (
            "detail",
            "not-a-registration",
            (),
            "digits only",
        ),
    ],
)
def test_shared_routes_reject_misleading_selectors(
    operation: str,
    selector: str,
    options: tuple[str, ...],
    message: str,
) -> None:
    route = query_state_courts.LIVE_ROUTES[ny_attorneys.SOURCE_ID][operation]
    args = _shared_args(
        operation,
        selector,
        "--source",
        ny_attorneys.SOURCE_ID,
        *options,
    )

    with pytest.raises(ValueError, match=message):
        route.translate(args, route.adapter_command)


def test_discovery_envelope_keeps_official_routes_distinct() -> None:
    route = query_state_courts.LIVE_ROUTES[ny_attorneys.SOURCE_ID][
        "discovery"
    ]
    translated = route.translate(
        _shared_args(
            "discovery",
            "--source",
            ny_attorneys.SOURCE_ID,
        ),
        route.adapter_command,
    )
    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True, "reason_code": "open"},
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status is ResultStatus.OK
    assert result.query.query.operation == "discovery"
    manifest = result.to_dict()["records"][0]
    assert manifest["record_kind"] == "source_manifest"
    assert manifest["projection"]["projectable_as_case_record"] is False
    capabilities = {item["name"] for item in manifest["capabilities"]}
    assert capabilities == {
        "NY Open Data Socrata API",
        "Unified Court System interactive directory",
        "22 NYCRR 118.2 written request",
        "Appellate Division discipline sources",
        "NYSCEF case filings",
    }
    assert manifest["field_gaps"]["socrata_dataset"] == [
        "discipline decision text",
        "case appearances",
        "registration history between quarterly snapshots",
    ]


def test_router_guidance_describes_snapshot_identity_and_complements() -> None:
    guidance = query_state_courts._source_guidance(ny_attorneys.SOURCE_ID)

    assert guidance["unified_operations"] == [
        "detail",
        "discovery",
        "probe",
        "search",
    ]
    assert guidance["record_grain"] == (
        "quarterly_attorney_registration_snapshot"
    )
    assert guidance["identity_model"] == "OCA registration_number"
    assert set(guidance["complementary_routes"]) == {
        "interactive_directory",
        "written_request_data",
        "public_discipline_decisions",
        "nyscef_case_filings",
    }
    assert "quarterly snapshot timestamp" in guidance["note"]
    assert "cases, dockets, or filings" in guidance["note"]
