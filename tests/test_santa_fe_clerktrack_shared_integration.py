from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_property
from tools import query_santa_fe_clerktrack as clerktrack
from tools import source_report
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)
from tools.public_records_contract import (
    PublicRecordsResult,
    ResultStatus,
    sha256_fingerprint,
)
from tools.public_records_monitor import (
    ProbeContext,
    probe_santa_fe_clerktrack,
)
from tools.public_records_search_plan import build_search_plan
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


SOURCE_ID = clerktrack.SOURCE_ID
FIXTURE_DIR = Path(
    "tests/fixtures/public_records/santa_fe_clerktrack"
)


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _source_records() -> tuple[
    dict[str, Any],
    dict[str, Any],
    clerktrack.SearchForm,
    clerktrack.IndexRow,
    clerktrack.DetailFields,
    str,
]:
    form = clerktrack.parse_search_form(fixture("search_form.html"))
    page = clerktrack.parse_results_page(
        fixture("instrument_result.html")
    )
    listing = page.rows[0]
    detail = clerktrack.parse_detail_page(fixture("detail.html"))
    index_record = clerktrack.normalize_index_row(
        listing,
        search_form=form,
        results_schema_fingerprint=page.schema_fingerprint,
    )
    detail_record = clerktrack.normalize_detail(
        listing,
        detail,
        search_form=form,
    )
    return (
        index_record,
        detail_record,
        form,
        listing,
        detail,
        page.schema_fingerprint,
    )


def _envelope(
    record: dict[str, Any],
    *,
    operation: str,
    retrieved_at: str,
) -> dict[str, Any]:
    query = clerktrack._build_query(
        operation,
        {"instrument_number": clerktrack.PROBE_INSTRUMENT},
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def test_shared_router_exposes_only_verified_clerktrack_surfaces() -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    unbounded = routes["search"].translate(
        _shared_args(
            "search",
            "MAYNARD*",
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "35049",
            "--search-field",
            "grantor",
            "--from-date",
            "1998-04-01",
            "--to-date",
            "1998-04-30",
        ),
        routes["search"].adapter_command,
    )
    bounded = routes["search"].translate(
        _shared_args(
            "search",
            "1477/604",
            "--source",
            SOURCE_ID,
            "--search-field",
            "book-page",
            "--limit",
            "7",
            "--cursor",
            "sfc-clerktrack:v2:cursor",
        ),
        routes["search"].adapter_command,
    )
    exact = routes["detail"].translate(
        _shared_args(
            "detail",
            clerktrack.PROBE_INSTRUMENT,
            "--source",
            SOURCE_ID,
            "--county",
            "Santa Fe County",
        ),
        routes["detail"].adapter_command,
    )
    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "routes",
            "--source",
            SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    probe = routes["probe"].translate(
        _shared_args("probe", "--source", SOURCE_ID),
        routes["probe"].adapter_command,
    )

    assert set(routes) == {
        "search",
        "owner",
        "instrument",
        "detail",
        "discovery",
        "probe",
    }
    assert unbounded.command == "search"
    assert unbounded.name == "MAYNARD*"
    assert unbounded.party_role == "grantor"
    assert unbounded.from_date == "1998-04-01"
    assert unbounded.to_date == "1998-04-30"
    assert unbounded.limit is None
    assert bounded.book == "1477"
    assert bounded.page == "604"
    assert bounded.limit == 7
    assert bounded.cursor == "sfc-clerktrack:v2:cursor"
    assert exact.command == "detail"
    assert exact.instrument == clerktrack.PROBE_INSTRUMENT
    assert discovery.command == "routes"
    assert probe.command == "probe"

    discovery_result = routes["discovery"].adapter.execute(
        discovery,
        access_decision={},
    )
    assert discovery_result.status == ResultStatus.OK
    route_rows = {
        row["route_id"]
        for row in discovery_result.records[0]["routes"]
    }
    assert clerktrack.TREASURER_ROUTE_ID in route_rows


@pytest.mark.parametrize(
    ("search_field", "selector", "attribute", "expected"),
    [
        ("instrument", "1019405", "instrument", "1019405"),
        ("book", "1477", "book", "1477"),
        ("page", "604", "page", "604"),
        (
            "document-type",
            "QUITCLAIM DEED",
            "document_type",
            ["QUITCLAIM DEED"],
        ),
        ("legal", "SEC 31", "legal", "SEC 31"),
        ("subdivision", "TEST", "subdivision", "TEST"),
        ("lot", "12", "lot", "12"),
        ("block", "2", "block", "2"),
        ("tract", "A", "tract", "A"),
        ("section", "31", "section", "31"),
        ("township", "10N", "township", "10N"),
        ("range", "07E", "range_value", "07E"),
        ("unit", "4", "unit", "4"),
        (
            "additional-info",
            "PLAT BK 214 PG 9",
            "additional_info",
            "PLAT BK 214 PG 9",
        ),
    ],
)
def test_shared_search_preserves_each_verified_selector(
    search_field: str,
    selector: str,
    attribute: str,
    expected: Any,
) -> None:
    route = query_property.LIVE_ROUTES[SOURCE_ID]["search"]
    translated = route.translate(
        _shared_args(
            "search",
            selector,
            "--source",
            SOURCE_ID,
            "--search-field",
            search_field,
        ),
        route.adapter_command,
    )
    assert getattr(translated, attribute) == expected


def test_ingestion_preserves_index_snapshots_and_detail_roles_without_title(
    tmp_path: Path,
) -> None:
    (
        index_record,
        detail_record,
        _form,
        _listing,
        _detail,
        _results_schema,
    ) = _source_records()
    db_path = tmp_path / "property.db"

    index_result = ingest_property_envelope(
        _envelope(
            index_record,
            operation="search",
            retrieved_at="2026-07-31T12:00:00Z",
        ),
        db_path=db_path,
    )
    detail_result = ingest_property_envelope(
        _envelope(
            detail_record,
            operation="detail",
            retrieved_at="2026-07-31T12:01:00Z",
        ),
        db_path=db_path,
    )
    trailing_index_result = ingest_property_envelope(
        _envelope(
            index_record,
            operation="search",
            retrieved_at="2026-07-31T12:02:00Z",
        ),
        db_path=db_path,
    )

    assert index_result["records"][0][
        "index_party_snapshots_upserted"
    ] == 2
    assert detail_result["records"][0]["detail_parties_upserted"] == 4
    assert trailing_index_result["records"][0][
        "recorded_instruments_upserted"
    ] == 0
    assert detail_result["records"][0]["documents_upserted"] == 0
    assert detail_result["records"][0][
        "ownership_assertions_upserted"
    ] == 0

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, book, page, recording_date,
                   legal_description_raw, raw_json
            FROM recorded_instrument
            """
        ).fetchone()
        parties = db.execute(
            """
            SELECT role, raw_name
            FROM instrument_party
            ORDER BY
                CASE role
                    WHEN 'grantor_display_snapshot' THEN 1
                    WHEN 'grantee_display_snapshot' THEN 2
                    WHEN 'grantor' THEN 3
                    WHEN 'grantee' THEN 4
                    ELSE 5
                END,
                sequence_no
            """
        ).fetchall()
        observations = db.execute(
            """
            SELECT record_kind, COUNT(*) AS count
            FROM source_observation
            WHERE source_id=?
            GROUP BY record_kind
            ORDER BY record_kind
            """,
            (SOURCE_ID,),
        ).fetchall()
        empty_projection_counts = {
            table: db.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in (
                "document_artifact",
                "parcel_snapshot",
                "instrument_parcel",
                "ownership_assertion",
                "sale_event",
                "assessment",
            )
        }
    finally:
        db.close()

    assert tuple(instrument)[:7] == (
        SOURCE_ID,
        "35049",
        clerktrack.PROBE_INSTRUMENT,
        clerktrack.PROBE_DOCUMENT_TYPE,
        clerktrack.PROBE_BOOK,
        clerktrack.PROBE_PAGE,
        clerktrack.PROBE_RECORDING_DATE,
    )
    stored_record = json.loads(instrument["raw_json"])
    stored_legal = json.loads(instrument["legal_description_raw"])
    assert stored_record["record_kind"] == "recorded_instrument_detail"
    assert stored_record["submitter"] is None
    assert stored_record["address"] is None
    assert stored_record["location"] is None
    assert stored_legal["legal_information"] == [
        "SEC: 31 RANGE: 07E TWSHP: 10N"
    ]
    assert stored_legal["additional_descriptions"] == [
        "PLAT BK 214 PG 9"
    ]
    assert stored_legal["cross_source_join_keys"]["book_page"] == (
        "1477/604"
    )
    assert [tuple(row) for row in parties] == [
        (
            "grantor_display_snapshot",
            "MAYNARD, TODD S, MAYNARD, BRENDA A",
        ),
        (
            "grantee_display_snapshot",
            "MAYNARD, ROBERT G, MAYNARD, ELIZABETH S",
        ),
        ("grantor", "MAYNARD, BRENDA A"),
        ("grantor", "MAYNARD, TODD S"),
        ("grantee", "MAYNARD, ELIZABETH S"),
        ("grantee", "MAYNARD, ROBERT G"),
    ]
    assert [tuple(row) for row in observations] == [
        ("query_envelope", 3),
        ("recorded_instrument_detail", 1),
        ("recorded_instrument_index", 2),
    ]
    assert empty_projection_counts == {
        "document_artifact": 0,
        "parcel_snapshot": 0,
        "instrument_parcel": 0,
        "ownership_assertion": 0,
        "sale_event": 0,
        "assessment": 0,
    }


def test_ingestion_requires_published_detail_party_roles(
    tmp_path: Path,
) -> None:
    _index_record, detail_record, *_rest = _source_records()
    detail_record["parties"][0]["role"] = "owner"

    with pytest.raises(
        PropertyIngestError,
        match="published grantor or grantee",
    ):
        ingest_property_envelope(
            _envelope(
                detail_record,
                operation="detail",
                retrieved_at="2026-07-31T12:01:00Z",
            ),
            db_path=tmp_path / "property.db",
        )


def test_monitor_hashes_contracts_separately_from_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        _index_record,
        _detail_record,
        initial_form,
        listing,
        initial_detail,
        results_schema,
    ) = _source_records()
    current_form = initial_form
    current_detail = initial_detail
    observed_budgets: list[int | None] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            observed_budgets.append(kwargs.get("request_budget"))
            self.request_count = 5
            self.last_results_schema_fingerprint = results_schema

        def detail(self, _instrument: str):
            return listing, current_detail, current_form

        def close(self) -> None:
            return None

    monkeypatch.setattr(clerktrack, "ClerkTrackClient", FakeClient)
    context = ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.25}
        },
        timeout=10.0,
        max_attempts=3,
        sample_bytes=None,
    )
    first = probe_santa_fe_clerktrack(context)
    current_form = replace(
        initial_form,
        index_through_date="2026-08-01",
        index_through_date_raw="Last Index Date: 8/1/2026",
    )
    current_detail = replace(initial_detail, submitter="ANOTHER SUBMITTER")
    rolling_changed = probe_santa_fe_clerktrack(context)
    current_form = replace(
        current_form,
        schema_fingerprint="changed-search-form-schema",
    )
    form_changed = probe_santa_fe_clerktrack(context)
    monkeypatch.setattr(
        clerktrack,
        "SOURCE_ROUTES",
        tuple(
            {
                **route,
                "url": "https://alternate.example.test/treasurer",
            }
            if route["route_id"] == clerktrack.TREASURER_ROUTE_ID
            else route
            for route in clerktrack.SOURCE_ROUTES
        ),
    )
    route_changed = probe_santa_fe_clerktrack(context)

    assert observed_budgets == [5, 5, 5, 5]
    assert first.details["stable_contract"]["monitor"] == {
        "request_budget": 5,
        "image_fetched": False,
        "copy_purchased": False,
    }
    assert first.details["list_detail_agreement"] is True
    assert first.artifact_sha256 == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.artifact_sha256 == rolling_changed.artifact_sha256
    assert first.schema_sha256 == rolling_changed.schema_sha256
    assert (
        first.details["rolling_observation"]
        != rolling_changed.details["rolling_observation"]
    )
    assert form_changed.artifact_sha256 != rolling_changed.artifact_sha256
    assert form_changed.schema_sha256 != rolling_changed.schema_sha256
    assert route_changed.artifact_sha256 != form_changed.artifact_sha256
    assert (
        public_records_monitor.HANDLER_REGISTRY[SOURCE_ID].expected_requests
        == 5
    )


def test_monitor_rejects_dynamic_list_detail_disagreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        _index_record,
        _detail_record,
        form,
        listing,
        detail,
        results_schema,
    ) = _source_records()

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 5
            self.last_results_schema_fingerprint = results_schema

        def detail(self, _instrument: str):
            return listing, replace(detail, page="999"), form

        def close(self) -> None:
            return None

    monkeypatch.setattr(clerktrack, "ClerkTrackClient", FakeClient)
    context = ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {}},
        timeout=10.0,
        max_attempts=1,
        sample_bytes=None,
    )
    with pytest.raises(ValueError, match="list/detail identities disagree"):
        probe_santa_fe_clerktrack(context)


def test_catalog_census_source_report_search_plan_and_citation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    db = sqlite3.connect(catalog_path)
    try:
        associations = db.execute(
            """
            SELECT s.source_id, j.geoid, t.domain, t.role
            FROM source_census_target_sources a
            JOIN sources s USING(source_id)
            JOIN source_census_targets t USING(census_target_id)
            JOIN jurisdictions j USING(jurisdiction_id)
            WHERE s.source_id=?
            ORDER BY t.role
            """,
            (SOURCE_ID,),
        ).fetchall()
    finally:
        db.close()
    assert associations == [
        (SOURCE_ID, "35049", "property", "land_records_index")
    ]

    report = source_report.check_public_records_catalog(catalog_path)
    report_row = next(
        value
        for value in report.values()
        if isinstance(value, dict) and value.get("source_id") == SOURCE_ID
    )
    assert report_row["query_tool"] == "tools/query_property.py"
    assert report_row["status"] == "configured"

    plan = build_search_plan(
        "EXAMPLE HOLDINGS LLC",
        jurisdictions=["35049"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert set(tasks) == {
        "search_instruments",
        "search_parties",
        "fetch_instrument",
    }
    assert tasks["search_instruments"]["capability_details"][
        "adapter_tool"
    ] == "query_property.py"
    assert tasks["search_instruments"]["capability_details"][
        "adapter_command"
    ] == "search"
    assert tasks["search_parties"]["capability_details"][
        "adapter_command"
    ] == "owner"
    assert tasks["fetch_instrument"]["capability_details"][
        "adapter_command"
    ] == "instrument"
    assert {
        f"recorder.{SOURCE_ID}.search_instruments",
        f"recorder.{SOURCE_ID}.search_parties",
    } <= set(tasks["fetch_instrument"]["depends_on"])

    citation_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text()
    )
    assert citation_urls[f"PROPERTY_SOURCE:{SOURCE_ID}"] == (
        "https://www.santafecountynm.gov/clerk/divisions/"
        "public-records-access"
    )


def test_route_lineage_separates_same_clerk_and_distinct_offices() -> None:
    routes = {
        route["route_id"]: route
        for route in clerktrack.SOURCE_ROUTES
    }
    for source_id in (
        "us-nm-santa-fe-clerktrack-detail",
        "us-nm-santa-fe-clerktrack-public-images",
        "us-nm-santa-fe-clerktrack-index-books",
        "us-nm-santa-fe-clerk-copy-request",
    ):
        assert routes[source_id]["independent_evidence"] is False
    assert routes[clerktrack.ASSESSOR_LAYER_SOURCE_ID][
        "independent_evidence"
    ] is True
    assert routes[clerktrack.TREASURER_ROUTE_ID][
        "relationship_to_primary"
    ] == "field_matched_distinct_tax_record"
