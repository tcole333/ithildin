from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_property
from tools import query_usvi_recorder as usvi
from tools import source_report
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult, sha256_fingerprint
from tools.public_records_monitor import ProbeContext, probe_usvi_recorder
from tools.public_records_search_plan import build_search_plan
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


SOURCE_ID = usvi.SOURCE_ID
DISTRICT = usvi.PROBE_DISTRICT
INST_ID = usvi.PROBE_INST_ID
INSTRUMENT_NUMBER = usvi.PROBE_INSTRUMENT_NUMBER
NATIVE_ID = f"{DISTRICT}:{INST_ID}"
CANONICAL_REF = usvi.instrument_ref(DISTRICT, INST_ID)


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _record(
    *,
    instrument_type: str = "DEED",
    recording_date: str = "2026-02-05",
    page_path: Path | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source_id": SOURCE_ID,
        "record_kind": "recorded_instrument",
        "record_scope": "recorder_instrument_detail",
        "canonical_ref": CANONICAL_REF,
        "evidence_ref": CANONICAL_REF,
        "native_document_id": NATIVE_ID,
        "native_inst_id": INST_ID,
        "district": DISTRICT,
        "instrument_number": INSTRUMENT_NUMBER,
        "document_number": INSTRUMENT_NUMBER,
        "instrument_type": instrument_type,
        "recording_date": recording_date,
        "instrument_date": "2026-02-04",
        "book": "2026",
        "page": "625",
        "parties": [
            {
                "name": "EXAMPLE GRANTOR LLC",
                "role": "grantor",
                "native_role": "Party 1",
            },
            {
                "name": "EXAMPLE GRANTEE LLC",
                "role": "grantee",
                "native_role": "Party 2",
            },
        ],
        "legal_descriptions": [
            {
                "description": "ESTATE EXAMPLE",
                "components": {
                    "parcel": "3-17",
                    "unit": "12",
                },
                "raw": "1. ESTATE EXAMPLE PARCEL: 3-17 UNIT: 12",
            }
        ],
        "associated_documents": [
            {
                "native_inst_id": "903441",
                "instrument_number": "2026000624",
                "instrument_type": "MTG",
                "relationship": "source_associated_document",
            }
        ],
        "source_locator": {
            "district": DISTRICT,
            "inst_id": INST_ID,
            "instrument_number": INSTRUMENT_NUMBER,
            "instrument_type": instrument_type,
            "search_session_id": "searchJobMain",
        },
        "source_url": usvi.LOGIN_DISPLAY_URL,
        "jurisdiction": {
            "geoid": "78",
            "name": "U.S. Virgin Islands",
            "state_code": "VI",
            "district": DISTRICT,
        },
    }
    if page_path is not None:
        record["record_scope"] = (
            "recorder_instrument_detail_with_selected_page"
        )
        record["documents"] = [
            {
                "native_artifact_id": f"{NATIVE_ID}:page:1",
                "artifact_kind": "instrument_page_image",
                "representation_of": CANONICAL_REF,
                "page_number": 1,
                "page_count": 6,
                "mime_type": "image/png",
                "byte_count": 1234,
                "sha256": "a" * 64,
                "source_url": usvi.IMAGE_PNG_URL,
                "local_path": str(page_path),
                "source_copy_status": (
                    "recorder_hosted_reference_image_not_official_record_copy"
                ),
            }
        ]
    return record


def _envelope(
    record: dict[str, Any],
    *,
    operation: str = "document",
    retrieved_at: str = "2026-07-30T12:00:00Z",
) -> dict[str, Any]:
    argv = [
        operation,
        INSTRUMENT_NUMBER,
        "--district",
        DISTRICT,
        "--inst-id",
        INST_ID,
    ]
    if operation == "page":
        argv.append("1")
    args = usvi.build_parser().parse_args(argv)
    return PublicRecordsResult.success(
        usvi.build_query(args),
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def test_shared_router_preserves_exhaustive_search_and_exact_locators(
    tmp_path: Path,
) -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    unbounded = routes["search"].translate(
        _shared_args(
            "search",
            "SMITH",
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "78",
            "--district",
            DISTRICT,
            "--from-date",
            "2025-01-01",
        ),
        routes["search"].adapter_command,
    )
    bounded = routes["search"].translate(
        _shared_args(
            "search",
            INSTRUMENT_NUMBER,
            "--source",
            SOURCE_ID,
            "--search-field",
            "document-number",
            "--page-size",
            "60",
            "--cursor",
            "usvi-recorder:offset:3",
            "--limit",
            "7",
        ),
        routes["search"].adapter_command,
    )
    exact = routes["instrument"].translate(
        _shared_args(
            "instrument",
            INSTRUMENT_NUMBER,
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "78",
            "--district",
            DISTRICT,
            "--inst-id",
            INST_ID,
        ),
        routes["instrument"].adapter_command,
    )
    destination = tmp_path / "page-1.png"
    page = routes["download"].translate(
        _shared_args(
            "download",
            INSTRUMENT_NUMBER,
            "--source",
            SOURCE_ID,
            "--district",
            DISTRICT,
            "--inst-id",
            INST_ID,
            "--page-number",
            "1",
            "--destination",
            str(destination),
            "--overwrite",
        ),
        routes["download"].adapter_command,
    )

    assert set(routes) == {
        "search",
        "owner",
        "instrument",
        "download",
        "probe",
    }
    assert unbounded.command == "search"
    assert unbounded.query == "SMITH"
    assert unbounded.page_size == 100
    assert unbounded.offset == 0
    assert unbounded.limit is None
    assert unbounded.date_from == "2025-01-01"
    assert bounded.document_number == INSTRUMENT_NUMBER
    assert bounded.page_size == 60
    assert bounded.offset == 3
    assert bounded.limit == 7
    assert exact.command == "document"
    assert exact.instrument_number == INSTRUMENT_NUMBER
    assert exact.district == DISTRICT
    assert exact.inst_id == INST_ID
    assert page.command == "page"
    assert page.page_number == 1
    assert page.destination == destination
    assert page.overwrite is True

    guidance = query_property._source_guidance(SOURCE_ID)
    publicsearch = next(
        item
        for item in guidance["official_complements"]
        if item["kind"] == "current_official_publicsearch_alternative"
    )
    assert guidance["record_identity"] == "district_plus_inst_id"
    assert "exhaust every source-reported native page" in (
        guidance["default_pagination"]
    )
    assert publicsearch["independent_evidence"] is False

    with pytest.raises(ValueError, match="--district, and --inst-id"):
        routes["instrument"].translate(
            _shared_args(
                "instrument",
                INSTRUMENT_NUMBER,
                "--source",
                SOURCE_ID,
            ),
            routes["instrument"].adapter_command,
        )


def test_projection_keeps_instrument_parties_and_reference_page_out_of_title(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    first = ingest_property_envelope(
        _envelope(_record()),
        db_path=db_path,
    )
    page_path = tmp_path / "page-1.png"
    second = ingest_property_envelope(
        _envelope(
            _record(page_path=page_path),
            operation="page",
            retrieved_at="2026-07-30T12:01:00Z",
        ),
        db_path=db_path,
    )

    assert first["records"][0]["native_instrument_identity"] == NATIVE_ID
    assert first["records"][0]["instrument_number_lookup"] == INSTRUMENT_NUMBER
    assert first["records"][0]["ownership_assertions_upserted"] == 0
    assert second["records"][0]["instrument_id"] == first["records"][0][
        "instrument_id"
    ]
    assert second["records"][0]["artifacts_upserted"] == 1

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, book, page, execution_date, recording_date,
                   legal_description_raw
            FROM recorded_instrument
            """
        ).fetchone()
        parties = db.execute(
            """
            SELECT role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        artifact = db.execute(
            """
            SELECT native_document_id, mime_type, page_count, storage_path,
                   acquisition_method, rights_tier, access_state
            FROM document_artifact
            """
        ).fetchone()
        empty_projection_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "parcel_snapshot",
                "instrument_parcel",
                "ownership_assertion",
                "sale_event",
                "assessment",
            )
        }
    finally:
        db.close()

    assert tuple(instrument)[:8] == (
        SOURCE_ID,
        "78",
        NATIVE_ID,
        "DEED",
        "2026",
        "625",
        "2026-02-04",
        "2026-02-05",
    )
    legal = json.loads(instrument["legal_description_raw"])
    assert legal[0]["components"]["parcel"] == "3-17"
    assert [tuple(row) for row in parties] == [
        ("grantor", "EXAMPLE GRANTOR LLC"),
        ("grantee", "EXAMPLE GRANTEE LLC"),
    ]
    assert tuple(artifact) == (
        f"{NATIVE_ID}:page:1",
        "image/png",
        1,
        str(page_path),
        "downloaded_page",
        "official_host_reference_image_uncertified",
        "public",
    )
    assert empty_projection_counts == {
        "parcel_snapshot": 0,
        "instrument_parcel": 0,
        "ownership_assertion": 0,
        "sale_event": 0,
        "assessment": 0,
    }


def test_projection_rejects_locator_or_nested_artifact_identity_mismatch(
    tmp_path: Path,
) -> None:
    wrong_locator = _record()
    wrong_locator["source_locator"]["inst_id"] = "OTHER"
    with pytest.raises(
        ValueError,
        match="source locator disagrees",
    ):
        ingest_property_envelope(
            _envelope(wrong_locator),
            db_path=tmp_path / "locator.db",
        )

    wrong_artifact = _record(page_path=tmp_path / "page.png")
    wrong_artifact["documents"][0]["representation_of"] = (
        "PROPERTY_RECORD:another-source:78:instrument:OTHER"
    )
    with pytest.raises(
        ValueError,
        match="must represent its selected instrument",
    ):
        ingest_property_envelope(
            _envelope(wrong_artifact, operation="page"),
            db_path=tmp_path / "artifact.db",
        )


def test_monitor_hashes_stable_contract_not_rolling_instrument_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_budgets: list[int | None] = []
    rolling_record = _record()

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            observed_budgets.append(kwargs.get("request_budget"))
            self.request_count = 12

        def select_exact(self, **_kwargs: Any) -> dict[str, Any]:
            return dict(rolling_record)

        def close(self) -> None:
            return None

    monkeypatch.setattr(usvi, "USVIRecorderClient", FakeClient)
    context = ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={
            "limits": {
                "minimum_interval_seconds": 0.2,
            }
        },
        timeout=10.0,
        max_attempts=3,
        sample_bytes=None,
    )
    first = probe_usvi_recorder(context)
    rolling_record = _record(
        instrument_type="MORTGAGE",
        recording_date="2026-07-30",
    )
    second = probe_usvi_recorder(context)
    monkeypatch.setattr(
        usvi,
        "CURRENT_PUBLICSEARCH_COMPLEMENT",
        "https://alternate.example.test/",
    )
    route_changed = probe_usvi_recorder(context)

    assert observed_budgets == [12, 12, 12]
    assert first.details["stable_contract"]["monitor"] == {
        "request_budget": 12,
        "image_fetched": False,
    }
    assert first.artifact_sha256 == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert route_changed.artifact_sha256 != first.artifact_sha256
    assert (
        public_records_monitor.HANDLER_REGISTRY[SOURCE_ID].expected_requests
        == 12
    )


def test_catalog_census_source_report_and_search_plan_include_recorder(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    db = sqlite3.connect(catalog_path)
    try:
        association = db.execute(
            """
            SELECT s.source_id, j.geoid, t.domain, t.role
            FROM source_census_target_sources a
            JOIN sources s USING(source_id)
            JOIN source_census_targets t USING(census_target_id)
            JOIN jurisdictions j USING(jurisdiction_id)
            WHERE s.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
    finally:
        db.close()
    assert association == (SOURCE_ID, "78", "property", "land_records_index")

    report = source_report.check_public_records_catalog(catalog_path)
    source_report_row = next(
        value
        for value in report.values()
        if isinstance(value, dict) and value.get("source_id") == SOURCE_ID
    )
    assert source_report_row["query_tool"] == "tools/query_property.py"
    assert source_report_row["status"] == "configured"
    assert source_report_row["probe_status"] is None

    plan = build_search_plan(
        "EXAMPLE HOLDINGS LLC",
        jurisdictions=["78"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    source = next(
        row for row in plan["sources"] if row["source_id"] == SOURCE_ID
    )
    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert source["requested_jurisdiction_coverage"]["status"] == "matched"
    assert set(tasks) == {"search_instruments", "fetch_instrument"}
    fetch_dependencies = set(tasks["fetch_instrument"]["depends_on"])
    assert {
        "property.us-census-acs5-demographics.enrich_census_geography",
        f"recorder.{SOURCE_ID}.search_instruments",
    } <= fetch_dependencies
    assert {
        dependency
        for dependency in fetch_dependencies
        if dependency.startswith(
            "property.us-vi-property-tax-capture-cama."
        )
    } == {
        "property.us-vi-property-tax-capture-cama.download_document",
        "property.us-vi-property-tax-capture-cama.fetch_bills",
        "property.us-vi-property-tax-capture-cama.fetch_parcel",
        "property.us-vi-property-tax-capture-cama.fetch_payment_history",
        "property.us-vi-property-tax-capture-cama.search_address",
        "property.us-vi-property-tax-capture-cama.search_assessment_records",
        "property.us-vi-property-tax-capture-cama.search_owner",
        "property.us-vi-property-tax-capture-cama.search_tax_accounts",
    }
