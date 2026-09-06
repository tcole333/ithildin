from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_franklin_probate as probate
from tools import query_state_courts
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.seed_public_records_catalog import DEFAULT_CONFIG_PATH, seed_catalog


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_probate"
)
SOURCE_ID = probate.SOURCE_ID
RETRIEVED_AT = "2026-07-31T12:00:00Z"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _index_record() -> dict[str, Any]:
    return dict(
        probate.parse_index_page(
            _fixture("name-page-1.html"),
            source_url=probate._index_url("name", "LUPO"),
            operation="name",
        ).records[0]
    )


def _case_record() -> dict[str, Any]:
    record = probate.parse_detail_page(
        _fixture("case-detail.html"),
        source_url=probate._detail_url(
            "PBCaseTypeE.ndm/ESTATE_DETAIL",
            "617503;;",
        ),
    )
    assert record is not None
    return record


def _docket_records() -> list[dict[str, Any]]:
    return probate.parse_docket_page(
        _fixture("docket.html"),
        source_url=probate._detail_url(
            "PBDocket.ndm/input",
            "617503;;",
        ),
        case_number="617503",
    )


def _fiduciary_record() -> dict[str, Any]:
    return probate.parse_fiduciaries_page(
        _fixture("fiduciaries.html"),
        source_url=probate._detail_url(
            "PBFidy.ndm/input",
            "617503;;",
        ),
        case_number="617503",
    )[0]


def _fiduciary_detail_record() -> dict[str, Any]:
    record = probate.parse_detail_page(
        _fixture("fiduciary-detail.html"),
        source_url=probate._detail_url(
            "PBFidDetail.ndm/FID_DETAIL",
            "617503;;02",
        ),
        record_kind="probate_fiduciary_detail",
    )
    assert record is not None
    return record


def _envelope(
    records: list[dict[str, Any]],
    *,
    operation: str = "fixture",
) -> dict[str, Any]:
    return PublicRecordsResult.success(
        probate._query(operation, {"fixture": True}),
        records,
        retrieved_at=RETRIEVED_AT,
    ).to_dict()


def test_shared_search_keeps_exhaustive_default_and_explicit_cursor_window() -> None:
    route = query_state_courts.LIVE_ROUTES[SOURCE_ID]["search"]
    parser = query_state_courts.build_parser()
    first_url = probate._index_url("name", "SMITH")
    first_page = probate.parse_index_page(
        _fixture("name-page-1.html"),
        source_url=first_url,
        operation="name",
    )
    assert first_page.next_url is not None
    pages = {
        first_url: _fixture("name-page-1.html"),
        first_page.next_url: _fixture("name-page-2.html"),
    }

    default_args = parser.parse_args(
        ["search", "SMITH", "--source", SOURCE_ID]
    )
    default_direct = route.translate(default_args, route.adapter_command)
    assert default_direct.command == "name"
    assert default_direct.limit is None
    assert default_direct.cursor is None
    exhaustive = probate.collect_index(
        _IndexClient(pages),
        operation=default_direct.command,
        initial_url=first_url,
        parameters={"term": default_direct.term},
        limit=default_direct.limit,
        cursor=default_direct.cursor,
    )
    assert [record["case_number"] for record in exhaustive.records] == [
        "617503",
        "620001",
        "620002",
        "620003",
    ]
    assert exhaustive.native_pages_exhausted is True
    assert exhaustive.next_cursor is None

    limited_args = parser.parse_args(
        ["search", "SMITH", "--source", SOURCE_ID, "--limit", "1"]
    )
    limited_direct = route.translate(limited_args, route.adapter_command)
    first_window = probate.collect_index(
        _IndexClient(pages),
        operation=limited_direct.command,
        initial_url=first_url,
        parameters={"term": limited_direct.term},
        limit=limited_direct.limit,
        cursor=limited_direct.cursor,
    )
    assert [record["case_number"] for record in first_window.records] == [
        "617503"
    ]
    assert first_window.next_cursor is not None

    resumed_args = parser.parse_args(
        [
            "search",
            "SMITH",
            "--source",
            SOURCE_ID,
            "--limit",
            "2",
            "--cursor",
            first_window.next_cursor,
        ]
    )
    resumed_direct = route.translate(resumed_args, route.adapter_command)
    assert resumed_direct.limit == 2
    assert resumed_direct.cursor == first_window.next_cursor
    resumed = probate.collect_index(
        _IndexClient(pages),
        operation=resumed_direct.command,
        initial_url=first_url,
        parameters={"term": resumed_direct.term},
        limit=resumed_direct.limit,
        cursor=resumed_direct.cursor,
    )
    assert [record["case_number"] for record in resumed.records] == [
        "620001",
        "620002",
    ]


class _IndexClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def index_page(self, operation: str, url: str) -> probate.IndexPage:
        return probate.parse_index_page(
            self.pages[url],
            source_url=url,
            operation=operation,
        )


@pytest.mark.parametrize(
    ("shared_field", "query", "direct_command", "attribute", "expected"),
    [
        ("case-number", "617503", "number", "case_number", "617503"),
        ("attorney", "ARTZ", "attorney", "term", "ARTZ"),
        ("fiduciary", "ARTZ", "fiduciary", "term", "ARTZ"),
        ("opened", "2023-01-04", "opened", "open_date", "2023-01-04"),
        ("case-type", "E", "type", "case_type", "E"),
    ],
)
def test_shared_search_fields_reach_each_native_probate_index(
    shared_field: str,
    query: str,
    direct_command: str,
    attribute: str,
    expected: str,
) -> None:
    route = query_state_courts.LIVE_ROUTES[SOURCE_ID]["search"]
    args = query_state_courts.build_parser().parse_args(
        [
            "search",
            query,
            "--source",
            SOURCE_ID,
            "--search-field",
            shared_field,
        ]
    )

    translated = route.translate(args, route.adapter_command)

    assert translated.command == direct_command
    assert getattr(translated, attribute) == expected
    assert translated.limit is None


@pytest.mark.parametrize(
    ("operation", "selector"),
    [("case", "617503 A"), ("docket", "617503/A")],
)
def test_shared_exact_case_routes_preserve_case_number_and_suffix(
    operation: str,
    selector: str,
) -> None:
    routes = query_state_courts.LIVE_ROUTES[SOURCE_ID]
    args = query_state_courts.build_parser().parse_args(
        [
            operation,
            selector,
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "39049",
            "--court-id",
            probate.COURT_ID,
        ]
    )

    translated = routes[operation].translate(
        args,
        routes[operation].adapter_command,
    )

    assert translated.command == operation
    assert translated.case_number == "617503"
    assert translated.suffix == "A"
    assert set(routes) == {"search", "case", "docket", "discovery", "probe"}
    assert {"documents", "download"}.isdisjoint(routes)


def test_shared_route_validates_franklin_jurisdiction_and_probate_court() -> None:
    route = query_state_courts.LIVE_ROUTES[SOURCE_ID]["case"]
    parser = query_state_courts.build_parser()

    wrong_county = parser.parse_args(
        [
            "case",
            "617503",
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "39035",
        ]
    )
    with pytest.raises(ValueError, match="39049"):
        route.translate(wrong_county, route.adapter_command)

    wrong_court = parser.parse_args(
        [
            "case",
            "617503",
            "--source",
            SOURCE_ID,
            "--court-id",
            "oh-franklin-county-common-pleas",
        ]
    )
    with pytest.raises(ValueError, match=probate.COURT_ID):
        route.translate(wrong_court, route.adapter_command)


def test_case_index_docket_and_fiduciary_records_project_without_documents(
    tmp_path: Path,
) -> None:
    records = [
        _index_record(),
        _case_record(),
        *_docket_records(),
        _fiduciary_record(),
        _fiduciary_detail_record(),
    ]
    court_db = tmp_path / "state-courts.db"

    report = ingest_envelope(_envelope(records), court_db=court_db)

    assert report["projected"] == {
        "courts": 7,
        "related_courts": 0,
        "cases": 7,
        "related_cases": 0,
        "case_relations": 0,
        "parties": 2,
        "attorneys": 1,
        "representations": 1,
        "judicial_officers": 0,
        "assignments": 0,
        "claims": 0,
        "docket_entries": 3,
        "case_events": 0,
        "documents": 0,
        "restriction_events": 0,
    }
    assert report["snapshot_only"] == {
        "record_count": 0,
        "record_kinds": {},
    }

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        court = db.execute(
            "SELECT court_id, county_geoid, court_level, division FROM court"
        ).fetchone()
        assert dict(court) == {
            "court_id": probate.COURT_ID,
            "county_geoid": "39049",
            "court_level": "county",
            "division": "probate",
        }

        case = db.execute(
            """
            SELECT raw_case_number, source_internal_id, caption, case_type,
                   filing_date, disposition_date, status, raw_json
            FROM case_record
            """
        ).fetchone()
        assert case["raw_case_number"] == "617503"
        assert case["source_internal_id"] == "617503;;"
        assert case["caption"] == "LUPO, THERESA E."
        assert case["case_type"] == "ESTATE"
        assert case["filing_date"] == "2023-01-04"
        assert case["disposition_date"] is None
        assert case["status"] == "open"
        raw_case = json.loads(case["raw_json"])
        assert raw_case["aka_raw"] == "THERESA E. LUPO; THERESA LUPO"
        assert raw_case["bond_amount_raw"] == "$25,000.00"
        assert raw_case["case_subtype"] == "ANCILLARY ADMINISTRATION"

        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_source_occurrence").fetchone()[0] == 7
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM attorney").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_representation").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM docket_entry").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 0

        party = db.execute(
            "SELECT sequence_no, role, raw_name FROM case_party"
        ).fetchone()
        assert dict(party) == {
            "sequence_no": 2,
            "role": "fiduciary",
            "raw_name": "ARTZ, BRIAN S.",
        }
        attorney = db.execute(
            "SELECT source_id, raw_name, bar_id FROM attorney"
        ).fetchone()
        assert dict(attorney) == {
            "source_id": SOURCE_ID,
            "raw_name": "ARTZ, BRIAN S.",
            "bar_id": "0002003",
        }

        docket = db.execute(
            """
            SELECT native_entry_id, event_type, raw_text, raw_json
            FROM docket_entry
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [row["event_type"] for row in docket] == [
            "probate_docket_entry",
            "probate_docket_entry",
            "probate_docket_summary",
        ]
        assert docket[2]["raw_text"] == "DEPOSIT REMAINING"
        first_raw = json.loads(docket[0]["raw_json"])
        second_raw = json.loads(docket[1]["raw_json"])
        summary_raw = json.loads(docket[2]["raw_json"])
        assert second_raw["reference_raw"] == "06/08/2026"
        assert second_raw["receipt_raw"] == "R-101"
        assert summary_raw["cost_raw"] == "170.21"
        assert len(
            first_raw["franklin_probate_source_fields"]["source_rows"]
        ) == 3
    finally:
        db.close()


def test_attorney_profiles_and_source_metadata_remain_snapshot_only(
    tmp_path: Path,
) -> None:
    attorney_index = dict(
        probate.parse_index_page(
            _fixture("attorney-index.html"),
            source_url=probate._index_url("attorney", "ARTZ"),
            operation="attorney",
        ).records[0]
    )
    attorney_detail = probate.parse_detail_page(
        _fixture("attorney-detail.html"),
        source_url=probate._detail_url(
            "PBAttyDetail.ndm/ATTY_DETAIL",
            "617503;;02",
        ),
        record_kind="probate_attorney_detail",
    )
    attorney_profile = probate.parse_detail_page(
        _fixture("attorney-detail.html"),
        source_url=(
            probate.NETDATA_BASE_URL
            + "PBAttyForm.ndm/ATTY_FORM?string=0002003"
        ),
        record_kind="probate_attorney_profile",
    )
    assert attorney_detail is not None
    assert attorney_profile is not None
    attorney_detail.update(
        case_number="617503",
        case_suffix=None,
        fiduciary_number="02",
        source_native_id="617503;;02",
    )
    records = [
        probate._source_record(),
        probate.parse_landing_page(_fixture("landing.html")),
        attorney_index,
        attorney_detail,
        attorney_profile,
    ]
    court_db = tmp_path / "state-courts.db"

    report = ingest_envelope(
        _envelope(records, operation="source-metadata"),
        court_db=court_db,
    )

    assert report["snapshot_only"] == {
        "record_count": 5,
        "record_kinds": {
            "probate_attorney_detail": 1,
            "probate_attorney_index": 1,
            "probate_attorney_profile": 1,
            "source_capabilities": 1,
            "source_landing": 1,
        },
    }
    assert all(count == 0 for count in report["projected"].values())

    db = sqlite3.connect(court_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 1
        for table in (
            "court",
            "case_record",
            "case_party",
            "attorney",
            "case_representation",
            "docket_entry",
            "document_artifact",
        ):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        db.close()


def test_monitor_separates_stable_contract_from_rolling_probate_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = {
        "record_kind": "source_probe",
        "source_id": SOURCE_ID,
        "status": "available",
        "sentinel_case_number": probate.PROBE_CASE_NUMBER,
        "sentinel_case_name": "ESTATE OF FIXTURE PERSON",
        "sentinel_status_code": "CL",
        "sentinel_docket_records": 164,
        "sentinel_fiduciaries": 3,
        "sentinel_fiduciary_number": "02",
        "sentinel_attorney_number": "0012345",
        "landing_search_methods": 6,
        "routes_exercised": [
            "official_landing",
            "exact_case_number",
            "case_type_detail",
            "docket",
            "fiduciaries",
            "fiduciary_detail",
            "attorney_detail",
        ],
        "request_count": 7,
        "literal_person_selector": "617503;;02",
    }
    rolling = {
        **base,
        "sentinel_status_code": "RO",
        "sentinel_docket_records": 165,
        "sentinel_fiduciaries": 4,
    }
    queued = [base, rolling, rolling]

    def fake_execute(args):
        assert args.command == "probe"
        assert args.minimum_interval == 0
        record = queued.pop(0)
        return PublicRecordsResult.success(
            probate._query(
                "probe",
                {"sentinel_case_number": probate.PROBE_CASE_NUMBER},
            ),
            [record],
            retrieved_at=RETRIEVED_AT,
        )

    monkeypatch.setattr(probate, "execute", fake_execute)
    context = public_records_monitor.ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = public_records_monitor.probe_franklin_probate(context)
    second = public_records_monitor.probe_franklin_probate(context)
    monkeypatch.setitem(
        probate.INDEX_ROUTES,
        "name",
        "ChangedNameIndex.ndm/input",
    )
    route_changed = public_records_monitor.probe_franklin_probate(context)

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert route_changed.artifact_sha256 != second.artifact_sha256
    assert first.details["rolling_observation"]["request_count"] == 7
    assert "literal_person_selector" not in first.details["rolling_observation"]


def test_catalog_monitor_and_citation_share_the_probate_source_identity(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == SOURCE_ID
    )
    roles = set(source["roles"])
    capabilities = {
        capability["name"] if isinstance(capability, dict) else capability
        for capability in source["capabilities"]
    }

    assert source["record_identity_source_id"] == SOURCE_ID
    assert source["jurisdiction_geoids"] == ["39049"]
    assert source["official_url"] == probate.LANDING_URL
    assert source["platform_family"] == "franklin_county_netdata"
    assert source["source_status"] == "active"
    assert {
        "trial_case_index",
        "probate_case_metadata",
        "case_parties",
        "attorney_appearances",
        "docket_entries",
    } <= roles
    assert "public_documents" not in roles
    assert {
        "case_number_plus_suffix",
        "case_scoped_docket_occurrence",
        "case_scoped_fiduciary_number",
        "attorney_number",
    } <= set(source["stable_keys"])
    assert {
        "search_cases",
        "fetch_case",
        "list_docket_entries",
        "search_attorneys",
        "search_fiduciaries",
        "query_shared_state_courts",
        "ingest_state_court_records",
        "probe_source",
    } <= capabilities
    assert {"list_document_index", "fetch_document"}.isdisjoint(capabilities)
    shared = next(
        capability
        for capability in source["capabilities"]
        if isinstance(capability, dict)
        and capability["name"] == "query_shared_state_courts"
    )
    assert shared["details"]["shared_operations"] == [
        "search",
        "case",
        "docket",
        "discovery",
        "probe",
    ]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog_detail = PublicRecordsCatalog(catalog_path).show_source(SOURCE_ID)
    assert catalog_detail["source"]["source_id"] == SOURCE_ID
    assert catalog_detail["source"]["official_url"] == probate.LANDING_URL

    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert spec.source_id == SOURCE_ID
    assert spec.capability == "probe_source"
    assert spec.endpoint == probate.LANDING_URL
    assert spec.expected_requests == 7
    assert spec.sentinel_record_count == 1
    assert spec.sample_bytes is None
    assert spec.handler is getattr(
        public_records_monitor,
        "probe_franklin_probate",
    )

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == probate.LANDING_URL
