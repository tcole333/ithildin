import argparse

import pytest

from tools import (
    query_florida_court_directory_data,
    query_state_courts,
)
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    SourceMetadata,
)


def _parse(*values: str) -> argparse.Namespace:
    return query_state_courts.build_parser().parse_args(list(values))


class _AllowedCatalog:
    def __init__(self, _path: str | None = None) -> None:
        pass

    @staticmethod
    def show_source(source_id: str) -> dict[str, object]:
        return {
            "source": {
                "source_id": source_id,
                "name": source_id,
                "official_url": "https://www.flcourts.gov/",
                "license_or_terms_url": None,
            },
            "capabilities": [{"name": "search_cases", "supported": False}],
            "latest_access_review": {"access_class": "A"},
        }

    @staticmethod
    def machine_acquisition_decision(source_id: str) -> dict[str, object]:
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "A",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed",
        }


@pytest.mark.parametrize(
    ("source_id", "adapter_command", "selector", "record"),
    [
        (
            query_florida_court_directory_data.LOCATION_SOURCE_ID,
            "locations",
            "Charlotte",
            {
                "record_kind": "county_courthouse_location",
                "source_id": query_florida_court_directory_data.LOCATION_SOURCE_ID,
                "canonical_ref": "FL-COURTS:LOCATION:101",
                "name": "Charlotte",
                "county": "Charlotte",
                "appellate_map_category": {"identifier": "6dca"},
                "published_region": {"identifier": "2dca"},
                "published_region_matches_map_category": False,
            },
        ),
        (
            query_florida_court_directory_data.VIRTUAL_SOURCE_ID,
            "virtual",
            "George",
            {
                "record_kind": "virtual_courtroom_directory_entry",
                "source_id": query_florida_court_directory_data.VIRTUAL_SOURCE_ID,
                "canonical_ref": "FL-COURTS:VCD:7",
                "name": "Judge George",
            },
        ),
        (
            query_florida_court_directory_data.PUBLIC_RECORDS_SOURCE_ID,
            "data-request",
            "OSCA",
            {
                "record_kind": "public_records_request_program",
                "source_id": (
                    query_florida_court_directory_data.PUBLIC_RECORDS_SOURCE_ID
                ),
                "canonical_ref": "FL-COURTS:PUBLIC-RECORDS:OSCA",
                "name": "OSCA Public Records Request Program",
            },
        ),
        (
            query_florida_court_directory_data.STATISTICS_SOURCE_ID,
            "statistics",
            "Statistics",
            {
                "record_kind": "trial_court_statistical_publication",
                "source_id": (
                    query_florida_court_directory_data.STATISTICS_SOURCE_ID
                ),
                "canonical_ref": "FL-COURTS:STATISTICS:2472276",
                "title": "Overall Statistics",
            },
        ),
    ],
)
def test_shared_search_preserves_component_identity_and_source_records(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    adapter_command: str,
    selector: str,
    record: dict[str, object],
) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        _AllowedCatalog,
    )
    calls: list[argparse.Namespace] = []

    def fake_execute(adapter_args: argparse.Namespace) -> PublicRecordsResult:
        calls.append(adapter_args)
        query = PublicRecordsQuery(
            source=query_florida_court_directory_data.SOURCE_METADATA[source_id],
            jurisdiction=query_florida_court_directory_data.JURISDICTION,
            query=QueryMetadata(
                operation=adapter_args.command,
                parameters={"query": getattr(adapter_args, "query", None)},
            ),
        )
        return PublicRecordsResult.success(query, [record])

    monkeypatch.setattr(
        query_florida_court_directory_data,
        "execute",
        fake_execute,
    )

    payload = query_state_courts.execute(
        _parse("search", selector, "--source", source_id)
    )

    assert payload["status"] == "ok"
    assert payload["query"]["source"]["source_id"] == source_id
    assert payload["records"] == [record]
    assert calls[0].command == adapter_command


def test_location_translation_retains_published_county_and_region_semantics() -> None:
    route = query_state_courts.LIVE_ROUTES[
        query_florida_court_directory_data.LOCATION_SOURCE_ID
    ]["search"]
    adapter_args = route.translate(
        _parse(
            "search",
            "Miami",
            "--source",
            query_florida_court_directory_data.LOCATION_SOURCE_ID,
            "--county",
            "Miami-Dade County",
            "--search-field",
            "county",
            "--limit",
            "7",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "locations"
    assert adapter_args.query == "Miami-Dade"
    assert adapter_args.kind == "county"
    assert adapter_args.district is None
    assert adapter_args.limit == 7


def test_virtual_and_statistics_routes_keep_native_selectors() -> None:
    virtual_route = query_state_courts.LIVE_ROUTES[
        query_florida_court_directory_data.VIRTUAL_SOURCE_ID
    ]["search"]
    virtual_args = virtual_route.translate(
        _parse(
            "search",
            "George",
            "--source",
            query_florida_court_directory_data.VIRTUAL_SOURCE_ID,
            "--search-field",
            "judge",
            "--first-name",
            "Susan",
        ),
        virtual_route.adapter_command,
    )
    assert virtual_args.command == "virtual"
    assert virtual_args.judge == "Susan George"
    assert virtual_args.county is None
    assert virtual_args.query is None

    statistics_route = query_state_courts.LIVE_ROUTES[
        query_florida_court_directory_data.STATISTICS_SOURCE_ID
    ]["search"]
    statistics_args = statistics_route.translate(
        _parse(
            "search",
            "2024-25",
            "--source",
            query_florida_court_directory_data.STATISTICS_SOURCE_ID,
            "--search-field",
            "fiscal-year",
            "--max-records",
            "8",
        ),
        statistics_route.adapter_command,
    )
    assert statistics_args.command == "statistics"
    assert statistics_args.fiscal_year == "2024-25"
    assert statistics_args.section is None
    assert statistics_args.query is None
    assert statistics_args.limit == 8


def test_public_request_keyword_filter_is_truthful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_id = query_florida_court_directory_data.PUBLIC_RECORDS_SOURCE_ID
    query = PublicRecordsQuery(
        source=query_florida_court_directory_data.SOURCE_METADATA[source_id],
        jurisdiction=query_florida_court_directory_data.JURISDICTION,
        query=QueryMetadata(operation="data-request"),
    )
    monkeypatch.setattr(
        query_florida_court_directory_data,
        "execute",
        lambda _args: PublicRecordsResult.success(
            query,
            [
                {
                    "record_kind": "public_records_request_program",
                    "source_id": source_id,
                    "name": "OSCA Public Records Request Program",
                }
            ],
        ),
    )
    route = query_state_courts.LIVE_ROUTES[source_id]["search"]
    adapter_args = route.translate(
        _parse("search", "unmatched phrase", "--source", source_id),
        route.adapter_command,
    )

    result = route.adapter.execute(adapter_args)

    assert result.status.value == "no_results"
    assert result.records == ()


def test_shared_routes_do_not_misrepresent_exact_statistics_download() -> None:
    for source_id in query_state_courts.FLORIDA_COURT_DIRECTORY_DATA_SOURCE_IDS:
        assert set(query_state_courts.LIVE_ROUTES[source_id]) == {"search"}
        assert query_state_courts._source_guidance(source_id)[
            "unified_operations"
        ] == ["search"]

    guidance = query_state_courts._source_guidance(
        query_florida_court_directory_data.STATISTICS_SOURCE_ID
    )
    assert "download SELECTOR DESTINATION" in guidance["exact_download_tool"]
    assert "download" not in guidance["unified_operations"]


@pytest.mark.parametrize(
    ("source_id", "record_kind"),
    [
        (
            query_florida_court_directory_data.LOCATION_SOURCE_ID,
            "county_courthouse_location",
        ),
        (
            query_florida_court_directory_data.LOCATION_SOURCE_ID,
            "district_court_of_appeal_location",
        ),
        (
            query_florida_court_directory_data.LOCATION_SOURCE_ID,
            "state_supreme_court_location",
        ),
        (
            query_florida_court_directory_data.VIRTUAL_SOURCE_ID,
            "virtual_courtroom_directory_entry",
        ),
        (
            query_florida_court_directory_data.PUBLIC_RECORDS_SOURCE_ID,
            "public_records_request_program",
        ),
        (
            query_florida_court_directory_data.STATISTICS_SOURCE_ID,
            "trial_court_statistical_publication",
        ),
        (
            query_florida_court_directory_data.STATISTICS_SOURCE_ID,
            "trial_court_statistical_pdf_artifact",
        ),
    ],
)
def test_florida_directory_data_records_are_explicit_snapshot_only(
    tmp_path,
    source_id: str,
    record_kind: str,
) -> None:
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=source_id,
            name=source_id,
            source_role="official_court_snapshot",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="12",
            name="Florida",
            state_code="FL",
        ),
        query=QueryMetadata(operation="search"),
    )
    record = {
        "record_kind": record_kind,
        "source_id": source_id,
        "canonical_ref": f"FL-SNAPSHOT:{record_kind}",
        # Incidental case-like fields must not turn a directory/catalog row
        # into a normalized case.
        "raw_case_number": "NOT-A-CASE",
        "court": {
            "court_id": "fl-test-court",
            "name": "Florida Test Court",
        },
    }

    report = ingest_envelope(
        PublicRecordsResult.success(query, [record]).to_dict(),
        court_db=tmp_path / "florida-snapshots.db",
    )

    assert report["projected"]["cases"] == 0
    assert report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {record_kind: 1},
    }
