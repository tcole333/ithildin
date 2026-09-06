from __future__ import annotations

import argparse

import pytest

from tools import query_state_courts
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


def _parse(*values: str) -> argparse.Namespace:
    return query_state_courts.build_parser().parse_args(list(values))


def _empty_la_envelope(operation: str) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=query_state_courts.query_los_angeles_probate.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="06037",
            name="Los Angeles County, California",
            state_code="CA",
            county_fips="06037",
        ),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, [])


class _LosAngelesCatalog:
    def show_source(self, source_id: str) -> dict[str, object]:
        assert source_id == (
            query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
        )
        return {
            "source": {
                "source_id": source_id,
                "name": "Los Angeles Superior Court Probate Online Services",
                "official_url": (
                    "https://www.lacourt.ca.gov/pages/lp/probate"
                ),
                "authority": (
                    "Superior Court of California, County of Los Angeles"
                ),
                "platform_family": "lasc_aspnet_public_online_services",
            },
            "roles": [
                "superior_court_probate",
                "docket_entries",
                "filed_document_index",
                "probate_notes",
                "hearing_calendar",
            ],
            "capabilities": [
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "list_document_index", "supported": True},
                {"name": "list_probate_notes", "supported": True},
                {"name": "search_hearings", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, object]:
        assert source_id == (
            query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
        )
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits anonymous exact-case acquisition",
            "reason_code": "allowed",
            "limits": {
                "probate_notes_source_window": (
                    "typically_two_weeks_before_through_60_days_after_hearing"
                )
            },
        }


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _LosAngelesCatalog(),
    )


@pytest.mark.parametrize(
    ("router_command", "adapter_command"),
    [
        ("case", "case"),
        ("documents", "case"),
        ("notes", "notes"),
        ("calendar", "calendar"),
    ],
)
def test_los_angeles_router_maps_case_scoped_operations_without_default_cap(
    monkeypatch: pytest.MonkeyPatch,
    router_command: str,
    adapter_command: str,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
    ][router_command]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_la_envelope(adapter_command)
        ),
    )

    payload = query_state_courts.execute(
        _parse(
            router_command,
            "26STPB00601",
            "--source",
            query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID,
        )
    )

    assert payload["status"] == "no_results"
    adapter_args = calls[0]
    assert adapter_args.command == adapter_command
    assert adapter_args.case_number == "26STPB00601"
    assert adapter_args.limit is None
    assert adapter_args.offset == 0
    if router_command == "notes":
        assert adapter_args.view == "all"


def test_los_angeles_router_preserves_caller_paging_and_courthouse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
    ]["docket"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_la_envelope("case")
        ),
    )

    query_state_courts.execute(
        _parse(
            "docket",
            "26STPB00601",
            "--source",
            query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID,
            "--courthouse",
            "LA",
            "--limit",
            "25",
            "--max-records",
            "7",
            "--cursor",
            "la-probate:offset:4",
        )
    )

    adapter_args = calls[0]
    assert adapter_args.command == "case"
    assert adapter_args.courthouse == "LA"
    assert adapter_args.limit == 7
    assert adapter_args.offset == 4


def test_los_angeles_router_keeps_nonanonymous_routes_out_of_live_dispatch():
    assert {
        "case",
        "docket",
        "documents",
        "notes",
        "calendar",
    } == set(
        query_state_courts.LIVE_ROUTES[
            query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
        ]
    )
    for source_id in (
        "us-ca-los-angeles-superior-probate-name-index",
        "us-ca-los-angeles-superior-probate-document-images",
        "us-ca-los-angeles-superior-probate-records",
    ):
        assert source_id not in query_state_courts.LIVE_ROUTES


def test_los_angeles_source_guidance_lists_machine_and_action_surfaces():
    guidance = query_state_courts._source_guidance(
        query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
    )

    assert guidance["unified_operations"] == [
        "calendar",
        "case",
        "docket",
        "documents",
        "notes",
    ]
    assert "query_los_angeles_probate.py" in guidance["direct_tool"]
    assert "Name-index discovery" in guidance["note"]
    assert "separate catalog actions" in guidance["note"]


def test_los_angeles_unified_notes_envelope_can_be_ingested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
    ]["notes"]
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda _args, **_kwargs: _empty_la_envelope("notes"),
    )
    ingested = []
    monkeypatch.setattr(
        query_state_courts,
        "ingest_envelope",
        lambda envelope, **kwargs: ingested.append((envelope, kwargs))
        or {"status": "ingested", "projected": {"cases": 0}},
    )
    court_db = tmp_path / "courts.db"

    payload = query_state_courts.execute(
        _parse(
            "notes",
            "26STPB00601",
            "--source",
            query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID,
            "--court-db",
            str(court_db),
            "--ingest",
        )
    )

    assert payload["ingest"]["status"] == "ingested"
    assert ingested[0][0]["query"]["source"]["source_id"] == (
        query_state_courts.LOS_ANGELES_PROBATE_SOURCE_ID
    )
    assert ingested[0][1] == {"court_db": str(court_db)}
