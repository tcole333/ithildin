from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_md_estate_notices_claims as md
from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import (
    DEFAULT_CONFIG_PATH,
    seed_catalog,
)


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/md_estate_notices_claims"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _notice_record() -> dict[str, Any]:
    page = md.parse_notice_results_page(fixture("notice_results.html"))
    return md.normalize_notice_row(page.rows[0], page=page)


def _claim_record() -> dict[str, Any]:
    criteria = md.ClaimCriteria(role="decedent", last_name="Smith")
    page = md.parse_claim_results_page(
        fixture("claim_results.html"),
        effective_parameters=criteria.parameters(),
    )
    detail = md.parse_claim_detail(
        fixture("claim_detail.html"),
        page.rows[0].detail_url,
    )
    return md.normalize_claim_row(
        page.rows[0],
        criteria=criteria,
        page=page,
        detail=detail,
    )


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_unified_router_preserves_notice_and_claim_occurrence_semantics() -> None:
    notice_routes = query_state_courts.LIVE_ROUTES[md.NOTICE_SOURCE_ID]
    assert set(notice_routes) == {"search", "probe"}
    notice = notice_routes["search"].translate(
        _shared_args(
            "search",
            "Patrick Taylor",
            "--source",
            md.NOTICE_SOURCE_ID,
            "--jurisdiction",
            "24031",
            "--search-field",
            "representative",
            "--after",
            "2026-07-01",
            "--before",
            "2026-07-30",
        ),
        notice_routes["search"].adapter_command,
    )
    assert notice.command == "notices"
    assert notice.party_type == "representative"
    assert notice.last_name == "Taylor"
    assert notice.first_name == "Patrick"
    assert notice.county == "Montgomery County"
    assert notice.published_from == "2026-07-01"
    assert notice.published_to == "2026-07-30"
    assert notice.limit is None

    claim_routes = query_state_courts.LIVE_ROUTES[md.CLAIM_SOURCE_ID]
    assert set(claim_routes) == {"search", "claims", "detail", "probe"}
    corporation = claim_routes["search"].translate(
        _shared_args(
            "search",
            "University of Maryland Medical System",
            "--source",
            md.CLAIM_SOURCE_ID,
            "--entity-kind",
            "organization",
            "--case-type",
            "DEBT",
            "--after",
            "2026-07-28",
            "--before",
            "2026-07-28",
            "--limit",
            "25",
        ),
        claim_routes["search"].adapter_command,
    )
    assert corporation.command == "claims"
    assert corporation.role == "claimant"
    assert corporation.corporation == (
        "University of Maryland Medical System"
    )
    assert corporation.claim_type == "DEBT"
    assert corporation.filed_date == "2026-07-28"
    assert corporation.limit == 25

    by_estate = claim_routes["claims"].translate(
        _shared_args(
            "claims",
            "W127316",
            "--source",
            md.CLAIM_SOURCE_ID,
        ),
        claim_routes["claims"].adapter_command,
    )
    assert by_estate.estate_number == "W127316"

    detail = claim_routes["detail"].translate(
        _shared_args(
            "detail",
            "270350434",
            "--source",
            md.CLAIM_SOURCE_ID,
        ),
        claim_routes["detail"].adapter_command,
    )
    assert detail.command == "claim-detail"
    assert detail.record_id == "270350434"
    assert detail.source_partition == "row"
    partitioned_detail = claim_routes["detail"].translate(
        _shared_args(
            "detail",
            "archive:270350434",
            "--source",
            md.CLAIM_SOURCE_ID,
        ),
        claim_routes["detail"].adapter_command,
    )
    assert partitioned_detail.record_id == "270350434"
    assert partitioned_detail.source_partition == "archive"

    with pytest.raises(ValueError, match="exact filed-date"):
        claim_routes["search"].translate(
            _shared_args(
                "search",
                "Smith",
                "--source",
                md.CLAIM_SOURCE_ID,
                "--after",
                "2026-07-01",
                "--before",
                "2026-07-30",
            ),
            claim_routes["search"].adapter_command,
        )


def test_manifests_catalog_census_and_planner_use_live_capabilities(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    notices = sources[md.NOTICE_SOURCE_ID]
    claims = sources[md.CLAIM_SOURCE_ID]
    assert notices["source_status"] == "active"
    assert claims["source_status"] == "active"
    assert notices["automation_disposition"] == "allowed"
    assert claims["automation_disposition"] == "allowed"
    assert notices["stable_keys"] == ["notice_id"]
    assert claims["stable_keys"] == ["source_partition", "record_id"]
    assert notices["probe_evidence"]["live_default_page_two_postback_verified"]
    assert claims["probe_evidence"]["live_exact_detail_verified"]
    assert notices["census_associations"][0]["role"] == (
        "estate_legal_notices"
    )
    assert claims["census_associations"][0]["role"] == "estate_claim_index"

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    assert catalog.require_machine_acquisition(md.NOTICE_SOURCE_ID)[
        "allowed"
    ] is True
    assert catalog.require_machine_acquisition(md.CLAIM_SOURCE_ID)[
        "allowed"
    ] is True
    notice_capabilities = {
        capability["name"]
        for capability in catalog.show_source(md.NOTICE_SOURCE_ID)[
            "capabilities"
        ]
    }
    claim_capabilities = {
        capability["name"]
        for capability in catalog.show_source(md.CLAIM_SOURCE_ID)[
            "capabilities"
        ]
    }
    assert notice_capabilities == {
        "search_estate_notices",
        "fetch_notice",
        "probe_source",
    }
    assert claim_capabilities == {
        "search_estate_claims",
        "fetch_claim_detail",
        "probe_source",
    }

    census = PublicRecordsCensus(catalog_path)
    notice_target = census.list_targets(
        state="MD",
        domain="court",
        role="estate_legal_notices",
    )[0]
    claim_target = census.list_targets(
        state="MD",
        domain="court",
        role="estate_claim_index",
    )[0]
    assert md.NOTICE_SOURCE_ID in notice_target["source_ids"]
    assert md.CLAIM_SOURCE_ID in claim_target["source_ids"]

    plan = build_search_plan(
        "Susan Taylor",
        jurisdictions=["24"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    planned_sources = {row["source_id"]: row for row in plan["sources"]}
    assert planned_sources[md.NOTICE_SOURCE_ID]["access"]["mode"] == "allowed"
    assert planned_sources[md.CLAIM_SOURCE_ID]["access"]["mode"] == "allowed"
    route_groups = {
        group["primary_source_id"]: group
        for group in plan["complementary_routes"]
    }
    notice_complements = {
        value["source_id"]
        for value in route_groups[md.NOTICE_SOURCE_ID]["complements"]
    }
    claim_complements = {
        value["source_id"]
        for value in route_groups[md.CLAIM_SOURCE_ID]["complements"]
    }
    assert {
        "us-md-estate-search",
        "us-md-register-of-wills-offices",
        md.CLAIM_SOURCE_ID,
    } <= notice_complements
    assert {
        "us-md-estate-search",
        "us-md-register-of-wills-offices",
        md.NOTICE_SOURCE_ID,
    } <= claim_complements


def test_notice_and_claim_ingestion_preserves_source_occurrences_snapshot_only(
    tmp_path: Path,
) -> None:
    notice_result = PublicRecordsResult.success(
        md._query(
            md.NOTICE_SOURCE_ID,
            "notices",
            {"last_name": "Taylor"},
        ),
        [_notice_record()],
        retrieved_at=RETRIEVED_AT,
        raw_artifact_refs=[md.NOTICE_SEARCH_URL],
        warnings=md.NOTICE_WARNINGS,
    )
    claim_result = PublicRecordsResult.success(
        md._query(
            md.CLAIM_SOURCE_ID,
            "claims",
            {"last_name": "Smith"},
        ),
        [_claim_record()],
        retrieved_at=RETRIEVED_AT,
        raw_artifact_refs=[md.CLAIM_SEARCH_URL],
        warnings=md.CLAIM_WARNINGS,
    )
    court_db = tmp_path / "courts.db"
    notice_report = ingest_envelope(
        notice_result.to_dict(),
        court_db=court_db,
    )
    claim_report = ingest_envelope(
        claim_result.to_dict(),
        court_db=court_db,
    )
    assert notice_report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"estate_legal_notice": 1},
    }
    assert claim_report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"estate_claim_index_entry": 1},
    }
    assert notice_report["projected"]["cases"] == 0
    assert claim_report["projected"]["cases"] == 0
    assert notice_report["canonical_refs"] == []
    assert claim_report["canonical_refs"] == []


def test_monitor_handlers_separate_stable_contract_from_rolling_results(
    monkeypatch,
) -> None:
    def fake_execute(
        args: Any,
        **_kwargs: Any,
    ) -> PublicRecordsResult:
        if args.command == "probe-notices":
            record = {
                "source_id": md.NOTICE_SOURCE_ID,
                "record_kind": "source_probe",
                "status": "ok",
                "operation_states": {
                    "default_rolling_search": "available",
                    "full_notice_text": "available",
                    "native_notice_identity": "available",
                    "dynamic_native_pagination": "available",
                    "county_publication_death_party_filters": "available",
                },
                "search_result_count": 1818,
                "current_page_count": 20,
                "sample_notice_id": "177286",
                "sample_notice_title": "PUBLIC NOTICE OF CAVEAT",
                "observed_notice_titles": ["PUBLIC NOTICE OF CAVEAT"],
                "effective_parameters": {
                    "published_from_raw": "06/30/2026",
                    "published_to_raw": "07/30/2026",
                },
                "source_result_marker": "a" * 64,
                "result_schema_fingerprint": "b" * 64,
            }
            return PublicRecordsResult.success(
                md._query(md.NOTICE_SOURCE_ID, "probe-notices", {}),
                [record],
                retrieved_at=RETRIEVED_AT,
            )
        record = {
            "source_id": md.CLAIM_SOURCE_ID,
            "record_kind": "source_probe",
            "status": "ok",
            "operation_states": {
                "claimant_and_decedent_roles": "available",
                "person_and_corporation_fields": "available",
                "claim_detail": "available",
                "dynamic_native_pagination": "available",
                "linked_and_migrated_filters": "available",
            },
            "search_result_count": 4127,
            "sample_record_id": "270350434",
            "sample_source_partition": "row",
            "sample_claim_type": "DEBT",
            "sample_claim_status": "OPEN",
            "source_latest_data_raw": (
                "7/29/2026 4:00:00 PM (rownetwebalt)"
            ),
            "source_latest_data_at": "2026-07-29T20:00:00Z",
            "application_instance": "rownetwebalt",
            "source_result_marker": "c" * 64,
            "result_schema_fingerprint": "d" * 64,
            "detail_schema_fingerprint": "e" * 64,
        }
        return PublicRecordsResult.success(
            md._query(md.CLAIM_SOURCE_ID, "probe-claims", {}),
            [record],
            retrieved_at=RETRIEVED_AT,
        )

    monkeypatch.setattr(md, "execute", fake_execute)
    notice_context = ProbeContext(
        source_id=md.NOTICE_SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    claim_context = ProbeContext(
        source_id=md.CLAIM_SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    notice = public_records_monitor.probe_maryland_estate_notices(
        notice_context
    )
    claim = public_records_monitor.probe_maryland_estate_claims(claim_context)
    assert notice.status == "ok"
    assert claim.status == "ok"
    assert notice.details["stable_contract"]["identity"][
        "notice_occurrence"
    ] == ["notice_id"]
    assert claim.details["stable_contract"]["identity"][
        "claim_occurrence"
    ] == ["source_partition", "RecordId"]
    assert notice.details["rolling_observation"][
        "search_result_count"
    ] == 1818
    assert claim.details["rolling_observation"][
        "source_latest_data_at"
    ] == "2026-07-29T20:00:00Z"


def test_monitor_registry_and_citations_cover_both_sources() -> None:
    notice_handler = public_records_monitor.HANDLER_REGISTRY[
        md.NOTICE_SOURCE_ID
    ]
    claim_handler = public_records_monitor.HANDLER_REGISTRY[
        md.CLAIM_SOURCE_ID
    ]
    assert notice_handler.handler is (
        public_records_monitor.probe_maryland_estate_notices
    )
    assert claim_handler.handler is (
        public_records_monitor.probe_maryland_estate_claims
    )
    assert notice_handler.expected_requests == 2
    assert claim_handler.expected_requests == 4

    urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert urls[f"STATECOURT_SOURCE:{md.NOTICE_SOURCE_ID}"] == (
        md.NOTICE_SEARCH_URL
    )
    assert urls[f"STATECOURT_SOURCE:{md.CLAIM_SOURCE_ID}"] == (
        md.CLAIM_SEARCH_URL
    )
