from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import ingest_state_court_records
from tools import public_records_monitor
from tools import query_california_court_directory as california
from tools import query_san_diego_court_index as san_diego
from tools import query_santa_clara_court_records as santa_clara
from tools import query_state_courts
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    SourceMetadata,
)
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def _envelope(source_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=source_id,
            name=source_id,
            source_role="test",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="06",
            name="California",
            state_code="CA",
        ),
        query=QueryMetadata(operation="test", parameters={"selector": "fixture"}),
    )
    return PublicRecordsResult.success(query, records).to_dict()


def test_shared_routes_preserve_directory_publication_product_and_portal_roles() -> None:
    directory_routes = query_state_courts.LIVE_ROUTES[california.SOURCE_ID]
    assert set(directory_routes) == {"search"}
    all_args = _shared_args(
        "search",
        "all",
        "--source",
        california.SOURCE_ID,
        "--jurisdiction",
        "06",
    )
    translated = directory_routes["search"].translate(
        all_args,
        directory_routes["search"].adapter_command,
    )
    assert translated.command == "list"
    assert translated.county is None

    county_args = _shared_args(
        "search",
        "courthouses",
        "--source",
        california.SOURCE_ID,
        "--jurisdiction",
        "06085",
    )
    translated = directory_routes["search"].translate(
        county_args,
        directory_routes["search"].adapter_command,
    )
    assert translated.command == "search"
    assert translated.county == "Santa Clara"

    tentative_routes = query_state_courts.LIVE_ROUTES[
        santa_clara.TENTATIVE_SOURCE_ID
    ]
    assert set(tentative_routes) == {
        "search",
        "calendar",
        "documents",
        "download",
    }
    assert santa_clara.FAMILY_SOURCE_ID not in query_state_courts.LIVE_ROUTES
    assert santa_clara.CIVIL_INDEX_SOURCE_ID not in query_state_courts.LIVE_ROUTES
    assert santa_clara.CRIMINAL_INDEX_SOURCE_ID not in query_state_courts.LIVE_ROUTES
    assert santa_clara.PORTAL_SOURCE_ID not in query_state_courts.LIVE_ROUTES

    calendar_args = _shared_args(
        "calendar",
        "1",
        "--source",
        santa_clara.TENTATIVE_SOURCE_ID,
        "--court-id",
        santa_clara.COURT_ID,
    )
    translated = tentative_routes["calendar"].translate(
        calendar_args,
        tentative_routes["calendar"].adapter_command,
    )
    assert translated.command == "rulings"
    assert translated.department == 1


def test_san_diego_shared_routes_map_only_supported_case_index_operations() -> None:
    routes = query_state_courts.LIVE_ROUTES[san_diego.SOURCE_ID]
    assert set(routes) == {"search", "case"}

    search_args = _shared_args(
        "search",
        "Example LLC",
        "--source",
        san_diego.SOURCE_ID,
        "--case-type",
        "civil",
        "--first-name",
        "Ignored for business only when caller omits it",
        "--limit",
        "25",
    )
    translated = routes["search"].translate(
        search_args,
        routes["search"].adapter_command,
    )
    assert translated.command == "party-search"
    assert translated.case_type == "civil"
    assert translated.last_name == "Example LLC"
    assert translated.limit == 25
    assert translated.offset == 0

    case_args = _shared_args(
        "case",
        "IC810023",
        "--source",
        san_diego.SOURCE_ID,
        "--cursor",
        "sd-index:case-row-offset:50",
    )
    translated = routes["case"].translate(
        case_args,
        routes["case"].adapter_command,
    )
    assert translated.command == "case-search"
    assert translated.case_number == "IC810023"
    assert translated.case_type == "all"
    assert translated.offset == 50
    assert translated.limit is None


def test_explicit_ingest_semantics_keep_snapshots_and_project_san_diego_cases(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "court.db"
    directory_record = {
        "source_id": california.SOURCE_ID,
        "record_kind": "superior_court_directory_entry",
        "court_id": "ca-santa-clara-superior",
        "county_fips": "06085",
        "source_url": california.DIRECTORY_URL,
    }
    directory_report = ingest_state_court_records.ingest_envelope(
        _envelope(california.SOURCE_ID, [directory_record]),
        court_db=court_db,
    )
    assert directory_report["projected"]["cases"] == 0
    assert directory_report["snapshot_only"]["record_kinds"] == {
        "superior_court_directory_entry": 1
    }

    ruling_record = {
        "source_id": santa_clara.TENTATIVE_SOURCE_ID,
        "record_kind": "document_artifact",
        "department": 1,
        "source_url": (
            "https://santaclara.courts.ca.gov/system/files/"
            "tentative-ruling/dept-1.pdf"
        ),
        "court": {
            "court_id": santa_clara.COURT_ID,
            "name": santa_clara.COURT_NAME,
        },
    }
    ruling_report = ingest_state_court_records.ingest_envelope(
        _envelope(santa_clara.TENTATIVE_SOURCE_ID, [ruling_record]),
        court_db=court_db,
    )
    assert ruling_report["projected"]["cases"] == 0
    assert ruling_report["snapshot_only"]["record_kinds"] == {
        "document_artifact": 1
    }

    case_record = {
        "source_id": san_diego.SOURCE_ID,
        "record_kind": "case",
        "court": {
            "court_id": san_diego.COURT_ID,
            "native_court_id": "san-diego-superior-court",
            "name": san_diego.COURT_NAME,
            "state_code": "CA",
            "county_geoid": san_diego.COUNTY_GEOID,
            "court_level": "county_superior",
            "official_url": san_diego.COURT_OFFICIAL_URL,
        },
        "raw_case_number": "IC810023",
        "display_case_number": "IC810023",
        "caption": "Example v. Example",
        "case_type": "Civil",
        "filing_date": "2001-01-02",
        "access_state": "public",
        "certified_record": False,
        "source_url": san_diego.PROBE_DETAIL_URL,
        "parties": [],
        "docket_entries": [],
        "documents": [],
        "source_scope": {
            "record_type": "case_detail_index_metadata",
            "official_record": False,
            "docket_available": False,
            "documents_available": False,
        },
    }
    case_report = ingest_state_court_records.ingest_envelope(
        _envelope(san_diego.SOURCE_ID, [case_record]),
        court_db=court_db,
    )
    assert case_report["projected"]["cases"] == 1
    assert case_report["projected"]["docket_entries"] == 0
    assert case_report["projected"]["documents"] == 0
    with sqlite3.connect(court_db) as db:
        row = db.execute(
            """
            SELECT raw_case_number, certified_record, raw_json
            FROM case_record
            WHERE source_id=?
            """,
            (san_diego.SOURCE_ID,),
        ).fetchone()
    assert row is not None
    assert row[0] == "IC810023"
    assert row[1] == 0
    assert json.loads(row[2])["source_scope"]["official_record"] is False


def _monitor_context(source_id: str, interval: float = 0) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": interval}
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_california_directory_monitor_separates_contract_from_route_churn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {"snapshot": "a" * 64, "suffix": "first"}

    def fake_execute(args: Any, *, log_results: bool) -> PublicRecordsResult:
        assert args.command == "probe"
        assert log_results is False
        record = {
            "source_id": california.SOURCE_ID,
            "record_kind": "source_probe",
            "source_url": california.DIRECTORY_URL,
            "county_count": 58,
            "appellate_districts": [1, 2, 3, 4, 5, 6],
            "schema_fingerprint": "b" * 64,
            "snapshot_fingerprint": rolling["snapshot"],
            "sentinels": {
                "Los Angeles": {
                    "county_fips": "06037",
                    "appellate_district": 2,
                    "official_url": f"https://example.test/la/{rolling['suffix']}",
                },
                "San Mateo": {
                    "county_fips": "06081",
                    "appellate_district": 1,
                    "official_url": f"https://example.test/sm/{rolling['suffix']}",
                },
            },
        }
        return PublicRecordsResult.success(california._query(args), [record])

    monkeypatch.setattr(california, "execute", fake_execute)
    first = public_records_monitor.probe_california_court_directory(
        _monitor_context(california.SOURCE_ID)
    )
    rolling.update(snapshot="c" * 64, suffix="second")
    second = public_records_monitor.probe_california_court_directory(
        _monitor_context(california.SOURCE_ID)
    )
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    assert first.result_count == 58


def test_santa_clara_and_san_diego_monitors_hash_stable_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {"pdf_hash": "d" * 64, "last_updated": "07/30/2026"}

    class FakeSantaClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def departments(self) -> santa_clara.DepartmentDirectory:
            records = tuple(
                {
                    "department": department,
                    "record_kind": "tentative_ruling_department",
                }
                for department in sorted(santa_clara.EXPECTED_DEPARTMENTS)
            )
            return santa_clara.DepartmentDirectory(
                records=records,
                source_url=santa_clara.TENTATIVE_URL,
                schema_fingerprint="e" * 64,
            )

        def ruling_artifacts(
            self,
            _department: Any,
        ) -> santa_clara.RulingArtifactIndex:
            return santa_clara.RulingArtifactIndex(
                department=1,
                artifacts=(
                    {
                        "source_url": (
                            "https://santaclara.courts.ca.gov/system/files/"
                            "tentative-ruling/dept-1.pdf"
                        )
                    },
                ),
                source_url="https://santaclara.courts.ca.gov/dept-1",
                schema_fingerprint="f" * 64,
            )

        def pdf(self, source_url: str) -> santa_clara.PDFArtifact:
            return santa_clara.PDFArtifact(
                source_url=source_url,
                content=b"%PDF-fixture",
                media_type="application/pdf",
                sha256=rolling["pdf_hash"],
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(santa_clara, "SantaClaraCourtClient", FakeSantaClient)
    first_santa = public_records_monitor.probe_santa_clara_tentative_rulings(
        _monitor_context(santa_clara.TENTATIVE_SOURCE_ID)
    )
    rolling["pdf_hash"] = "1" * 64
    second_santa = public_records_monitor.probe_santa_clara_tentative_rulings(
        _monitor_context(santa_clara.TENTATIVE_SOURCE_ID)
    )
    assert first_santa.schema_sha256 == second_santa.schema_sha256
    assert first_santa.artifact_sha256 == second_santa.artifact_sha256
    assert first_santa.details["rolling_observation"] != (
        second_santa.details["rolling_observation"]
    )

    class FakeSanDiegoClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 6

        def probe(self) -> dict[str, san_diego.NewFilingsPage]:
            return {
                case_type: san_diego.NewFilingsPage(
                    case_type=case_type,
                    partition="a",
                    last_updated=rolling["last_updated"],
                    parties=(),
                    cases=(
                        san_diego.NewFilingCase(
                            case_number=f"{case_type}-1",
                            filing_date="2026-07-30",
                            filing_date_raw="07/30/2026",
                            category=case_type,
                            location="Central",
                            source_url=(
                                "https://www.sandiego.courts.ca.gov/"
                                f"portal/online/newfiles/{case_type}.html"
                            ),
                        ),
                    ),
                    partition_urls=(
                        "https://www.sandiego.courts.ca.gov/"
                        f"portal/online/newfiles/{case_type}.html",
                    ),
                    authoritative_empty=False,
                    schema_fingerprint="2" * 64,
                    source_url=(
                        "https://www.sandiego.courts.ca.gov/"
                        f"portal/online/newfiles/{case_type}.html"
                    ),
                )
                for case_type in san_diego.NEW_FILING_TYPE_CODES
            }

        def close(self) -> None:
            pass

    monkeypatch.setattr(san_diego, "NewFilingsClient", FakeSanDiegoClient)
    first_sd = public_records_monitor.probe_san_diego_new_filings(
        _monitor_context(san_diego.SOURCE_ID)
    )
    rolling["last_updated"] = "07/31/2026"
    second_sd = public_records_monitor.probe_san_diego_new_filings(
        _monitor_context(san_diego.SOURCE_ID)
    )
    assert first_sd.schema_sha256 == second_sd.schema_sha256
    assert first_sd.artifact_sha256 == second_sd.artifact_sha256
    assert first_sd.details["rolling_observation"] != (
        second_sd.details["rolling_observation"]
    )
    assert first_sd.result_count == 5


def test_catalog_census_monitor_and_citations_cover_all_california_components(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    for source_id in (
        california.SOURCE_ID,
        santa_clara.TENTATIVE_SOURCE_ID,
        san_diego.SOURCE_ID,
    ):
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True

    for source_id in (
        santa_clara.CIVIL_INDEX_SOURCE_ID,
        santa_clara.CRIMINAL_INDEX_SOURCE_ID,
        santa_clara.PORTAL_SOURCE_ID,
    ):
        assert catalog.machine_acquisition_decision(source_id)["allowed"] is False

    directory_manifest = catalog.show_source(california.SOURCE_ID)[
        "current_manifest"
    ]
    assert directory_manifest["identity_contract"]["shared_ingest_semantics"] == (
        "snapshot_only"
    )
    san_diego_manifest = catalog.show_source(san_diego.SOURCE_ID)[
        "current_manifest"
    ]
    assert san_diego_manifest["publication_contract"]["docket_available"] is False
    assert san_diego_manifest["publication_contract"]["documents_available"] is False

    assert (
        public_records_monitor.HANDLER_REGISTRY[california.SOURCE_ID].handler
        is public_records_monitor.probe_california_court_directory
    )
    assert (
        public_records_monitor.HANDLER_REGISTRY[
            santa_clara.TENTATIVE_SOURCE_ID
        ].handler
        is public_records_monitor.probe_santa_clara_tentative_rulings
    )
    assert (
        public_records_monitor.HANDLER_REGISTRY[san_diego.SOURCE_ID].handler
        is public_records_monitor.probe_san_diego_new_filings
    )

    source_urls_path = (
        Path(__file__).parents[1] / "web" / "src" / "data" / "source-urls.json"
    )
    source_urls = json.loads(source_urls_path.read_text(encoding="utf-8"))
    expected_urls = {
        california.SOURCE_ID: california.DIRECTORY_URL,
        santa_clara.FAMILY_SOURCE_ID: santa_clara.CASE_INFO_URL,
        santa_clara.TENTATIVE_SOURCE_ID: santa_clara.TENTATIVE_URL,
        santa_clara.CIVIL_INDEX_SOURCE_ID: santa_clara.CIVIL_PRODUCT_URL,
        santa_clara.CRIMINAL_INDEX_SOURCE_ID: santa_clara.CRIMINAL_PRODUCT_URL,
        santa_clara.PORTAL_SOURCE_ID: santa_clara.PORTAL_URL,
        san_diego.SOURCE_ID: san_diego.INDEX_HOME_URL,
    }
    for source_id, url in expected_urls.items():
        assert source_urls[f"STATECOURT_SOURCE:{source_id}"] == url
