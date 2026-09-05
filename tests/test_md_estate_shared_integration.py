from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_md_estate_search as md
from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import seed_catalog


FIXTURE_DIR = Path("tests/fixtures/public_records/md_estate_search")
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _index_record() -> dict[str, Any]:
    page = md.parse_results_page(fixture("results_page_1.html"))
    return md.normalize_search_row(
        page.rows[0],
        criteria=md.SearchCriteria(
            operation="estate",
            estate_number=md.PROBE_ESTATE_NUMBER,
            county=md.PROBE_COUNTY,
        ),
        refresh=page.refresh,
        schema_fingerprint=page.schema_fingerprint,
    )


def _detail_records() -> tuple[dict[str, Any], ...]:
    detail = md.parse_detail_page(
        fixture("detail.html"),
        f"{md.DETAIL_URL}?src=row&RecordId=1868548158",
    )
    return tuple(dict(record) for record in detail.records)


def test_unified_router_translates_names_counties_and_estate_numbers() -> None:
    route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["search"]
    args = query_state_courts.build_parser().parse_args(
        [
            "search",
            "Cynthia Novak",
            "--source",
            md.SOURCE_ID,
            "--jurisdiction",
            "24005",
            "--search-field",
            "representative",
        ]
    )
    translated = route.translate(args, route.adapter_command)
    assert translated.command == "representative"
    assert translated.last_name == "Novak"
    assert translated.first_name == "Cynthia"
    assert translated.county == "Baltimore County"
    assert translated.limit is None

    case_route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["case"]
    case_args = query_state_courts.build_parser().parse_args(
        [
            "case",
            "238438",
            "--source",
            md.SOURCE_ID,
            "--jurisdiction",
            "24510",
        ]
    )
    case_translated = case_route.translate(
        case_args,
        case_route.adapter_command,
    )
    assert case_translated.command == "resolve-estate"
    assert case_translated.estate_number == "238438"
    assert case_translated.county == "Baltimore City"


def test_unified_exact_case_resolves_record_id_and_fetches_full_docket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_execute(
        args: Any,
        *,
        access_decision: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> PublicRecordsResult:
        assert access_decision == {"allowed": True}
        calls.append(args.command)
        if args.command == "estate":
            return PublicRecordsResult.success(
                md._query(
                    "estate",
                    {
                        "operation": "estate",
                        "estate_number": "238438",
                        "county": "Baltimore County",
                    },
                ),
                [_index_record()],
                retrieved_at=RETRIEVED_AT,
                raw_artifact_refs=[md.SEARCH_URL],
            )
        assert args.command == "detail"
        assert args.record_id == "1868548158"
        return PublicRecordsResult.success(
            md._query("detail", {"record_id": args.record_id}),
            _detail_records(),
            retrieved_at=RETRIEVED_AT,
            raw_artifact_refs=[md.DETAIL_URL],
        )

    monkeypatch.setattr(md, "execute", fake_execute)
    route = query_state_courts.LIVE_ROUTES[md.SOURCE_ID]["docket"]
    shared_args = query_state_courts.build_parser().parse_args(
        [
            "docket",
            "238438",
            "--source",
            md.SOURCE_ID,
            "--county",
            "Baltimore County",
        ]
    )
    translated = route.translate(shared_args, route.adapter_command)
    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )
    assert calls == ["estate", "detail"]
    assert result.status.value == "ok"
    assert [record["record_kind"] for record in result.records] == [
        "estate_case_detail",
        "estate_docket_event",
        "estate_docket_event",
        "estate_docket_event",
    ]
    assert result.raw_artifact_refs == (md.SEARCH_URL, md.DETAIL_URL)


def test_estate_detail_projects_one_case_parties_attorney_events_and_docket(
    tmp_path: Path,
) -> None:
    result = PublicRecordsResult.success(
        md._query("detail", {"record_id": "1868548158"}),
        _detail_records(),
        retrieved_at=RETRIEVED_AT,
        raw_artifact_refs=[
            f"{md.DETAIL_URL}?src=row&RecordId=1868548158"
        ],
    )
    court_db = tmp_path / "courts.db"
    report = ingest_envelope(result.to_dict(), court_db=court_db)
    assert report["projected"]["docket_entries"] == 3
    assert report["projected"]["parties"] == 5
    assert report["projected"]["attorneys"] == 1

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = db.execute(
            """
            SELECT raw_case_number, source_internal_id, caption, case_type,
                   filing_date, status
            FROM case_record
            """
        ).fetchone()
        assert dict(case) == {
            "raw_case_number": "238438",
            "source_internal_id": None,
            "caption": "Estate of PATRICIA A. NOVAK",
            "case_type": "Regular Estate",
            "filing_date": "2026-04-29",
            "status": "OPEN",
        }
        court = db.execute(
            "SELECT county_geoid, court_level FROM court"
        ).fetchone()
        assert dict(court) == {
            "county_geoid": "24005",
            "court_level": "probate",
        }
        parties = {
            (row["role"], row["raw_name"])
            for row in db.execute(
                "SELECT role, raw_name FROM case_party"
            )
        }
        assert ("decedent", "PATRICIA A. NOVAK") in parties
        assert (
            "personal_representative",
            "CYNTHIA L. NOVAK",
        ) in parties
        assert ("decedent_alias", "PATRICIA ANN NOVAK") in parties
        assert db.execute("SELECT COUNT(*) FROM attorney").fetchone()[0] == 1
        assert (
            db.execute("SELECT COUNT(*) FROM docket_entry").fetchone()[0]
            == 3
        )
        assert db.execute("SELECT COUNT(*) FROM case_event").fetchone()[0] >= 3
    finally:
        db.close()


def test_estate_monitor_separates_stable_contract_from_daily_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {"stamp": "07/29/2026 4:00:00 PM"}

    def fake_execute(
        _args: Any,
        *,
        access_decision: dict[str, Any],
        log_results: bool,
    ) -> PublicRecordsResult:
        assert access_decision["allowed"] is True
        assert log_results is False
        record = {
            "source_id": md.SOURCE_ID,
            "record_kind": "source_probe",
            "status": "ok",
            "operation_states": {
                "agreement_navigation": "available",
                "search_form": "available",
                "estate_number_search": "available",
                "dynamic_native_pagination": "not_needed_for_sentinel",
                "estate_detail": "available",
                "docket_history": "available",
            },
            "source_latest_data_raw": rolling["stamp"],
            "source_latest_data_at": "2026-07-29T20:00:00Z",
            "application_instance": "rownetwebalt",
            "search_result_count": 1,
            "sentinel_record_id": "1868548158",
            "sentinel_estate_number": md.PROBE_ESTATE_NUMBER,
            "sentinel_county": md.PROBE_COUNTY,
            "sentinel_docket_event_count": 10,
            "result_schema_fingerprint": "a" * 64,
            "detail_schema_fingerprint": "b" * 64,
        }
        return PublicRecordsResult.success(
            md._query("probe", {}),
            [record],
            retrieved_at=RETRIEVED_AT,
        )

    monkeypatch.setattr(md, "execute", fake_execute)
    context = ProbeContext(
        source_id=md.SOURCE_ID,
        catalog_decision={
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = public_records_monitor.probe_maryland_estates(context)
    rolling["stamp"] = "07/30/2026 4:00:00 PM"
    second = public_records_monitor.probe_maryland_estates(context)
    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]["source_latest_data_raw"]
        != second.details["rolling_observation"]["source_latest_data_raw"]
    )


def test_estate_catalog_planner_and_census_use_verified_capabilities(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.require_machine_acquisition(md.SOURCE_ID)["allowed"] is True
    detail = catalog.show_source(md.SOURCE_ID)
    capabilities = {
        capability["name"] for capability in detail["capabilities"]
    }
    assert {
        "search_decedent_estates",
        "search_representative_estates",
        "search_estate_number",
        "fetch_estate_detail",
        "list_estate_docket",
        "probe_source",
    } == capabilities

    plan = build_search_plan(
        "Patricia Novak",
        jurisdictions=["24"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    sources = {row["source_id"]: row for row in plan["sources"]}
    assert sources[md.SOURCE_ID]["access"]["mode"] == "allowed_with_limits"
    tasks = {
        task["capability"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == md.SOURCE_ID
    }
    assert tasks == {
        "search_decedent_estates",
        "search_representative_estates",
        "search_estate_number",
        "fetch_estate_detail",
        "list_estate_docket",
    }
    route_groups = {
        group["primary_source_id"]: group
        for group in plan["complementary_routes"]
    }
    complements = {
        value["source_id"]
        for value in route_groups[md.SOURCE_ID]["complements"]
    }
    assert {
        "us-md-register-of-wills-offices",
        "us-md-estate-legal-notices",
        "us-md-estate-claims",
        "us-md-land-records",
        "us-md-sdat-real-property",
    } <= complements
