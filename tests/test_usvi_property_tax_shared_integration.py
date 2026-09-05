from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_property
from tools import query_usvi_property_tax as usvi
from tools import source_report
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult, sha256_fingerprint
from tools.public_records_monitor import ProbeContext, probe_usvi_property_tax
from tools.public_records_search_plan import build_search_plan
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


SOURCE_ID = usvi.SOURCE_ID
PARCEL = usvi.PROBE_PARCEL_NUMBER
TAX_YEAR = usvi.PROBE_TAX_YEAR
FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "usvi_property_tax"
)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _detail_record() -> dict[str, Any]:
    records, _total, _has_next, _argument = usvi.parse_search_page(
        _fixture("search_page_1.html")
    )
    record = dict(records[0])
    record.update(
        {
            "record_kind": "parcel_assessment_tax_detail",
            "canonical_ref": usvi._child_ref(  # noqa: SLF001
                "parcel_assessment_tax_detail",
                f"{PARCEL}|tax-year:{TAX_YEAR}",
            ),
            "components": {
                "valuation": usvi.parse_valuation_component(
                    _fixture("valuation.html"),
                    parcel_number=PARCEL,
                ),
                "land": {
                    "record_kind": "parcel_land_component",
                    "published_text": "source land text",
                    "recorded_title_evidence": False,
                },
                "sales": {
                    "record_kind": "parcel_sales_component",
                    "published_text": "source assessor sales text",
                    "recorded_title_evidence": False,
                },
            },
            "recorded_title_evidence": False,
        }
    )
    return record


def _envelope(
    record: dict[str, Any],
    *,
    operation: str = "parcel",
    retrieved_at: str = "2026-07-30T12:00:00Z",
) -> dict[str, Any]:
    query = usvi._make_query(  # noqa: SLF001
        operation=operation,
        parameters={
            "parcel_number": record.get("formatted_parcel_number"),
            "tax_year": record.get("tax_year"),
        },
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def test_shared_router_exposes_native_fields_without_default_result_cap(
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
        ),
        routes["search"].adapter_command,
    )
    legal = routes["search"].translate(
        _shared_args(
            "search",
            "ST JAMES",
            "--source",
            SOURCE_ID,
            "--search-field",
            "legal",
            "--tax-year",
            TAX_YEAR,
            "--limit",
            "7",
        ),
        routes["search"].adapter_command,
    )
    owner = routes["owner"].translate(
        _shared_args("owner", "SMITH", "--source", SOURCE_ID),
        routes["owner"].adapter_command,
    )
    address = routes["address"].translate(
        _shared_args("address", "ESTATE NAZARETH", "--source", SOURCE_ID),
        routes["address"].adapter_command,
    )
    parcel = routes["parcel"].translate(
        _shared_args(
            "parcel",
            PARCEL,
            "--source",
            SOURCE_ID,
            "--tax-year",
            TAX_YEAR,
        ),
        routes["parcel"].adapter_command,
    )
    destination = tmp_path / "bill.html"
    artifact = routes["download"].translate(
        _shared_args(
            "download",
            PARCEL,
            "--source",
            SOURCE_ID,
            "--tax-year",
            TAX_YEAR,
            "--artifact-kind",
            "bill",
            "--statement",
            "24457395",
            "--destination",
            str(destination),
        ),
        routes["download"].adapter_command,
    )

    assert set(routes) == {
        "search",
        "owner",
        "address",
        "parcel",
        "download",
        "probe",
    }
    assert unbounded.command == "search"
    assert unbounded.field == "owner"
    assert unbounded.limit is None
    assert legal.field == "legal"
    assert legal.tax_year == TAX_YEAR
    assert legal.limit == 7
    assert owner.field == "owner"
    assert address.field == "address"
    assert parcel.command == "parcel"
    assert parcel.parcel_number == PARCEL
    assert artifact.command == "artifact"
    assert artifact.kind == "bill"
    assert artifact.statement == "24457395"
    assert artifact.destination == destination

    guidance = query_property._source_guidance(SOURCE_ID)
    failover = next(
        value
        for value in guidance["official_complements"]
        if value["kind"] == "same_tenant_failover"
    )
    assert guidance["record_identity"] == (
        "formatted_parcel_number_plus_tax_year"
    )
    assert failover["independent_evidence"] is False


def test_projection_is_tax_year_specific_and_assessment_owner_is_not_title(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    envelope = _envelope(_detail_record())
    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    projected = first["records"][0]
    assert projected["owner_assertion_basis"] == (
        "assessment_roll_tax_year_observation"
    )
    assert projected["payer_names_projected_as_owners"] is False
    assert projected["recorded_instruments_upserted"] == 0
    assert projected["title_assertions_upserted"] == 0
    assert projected["sales_upserted"] == 0
    assert second["records"][0]["parcel_id"] == projected["parcel_id"]

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT native_parcel_id, roll_year
            FROM parcel_snapshot
            WHERE source_id=?
            ORDER BY roll_year
            """,
            (SOURCE_ID,),
        ).fetchall()
        assessments = db.execute(
            """
            SELECT a.tax_year, a.land_value_minor, a.improvement_value_minor,
                   a.total_value_minor, a.assessed_value_minor
            FROM assessment a
            WHERE a.source_id=?
            ORDER BY a.tax_year
            """,
            (SOURCE_ID,),
        ).fetchall()
        owner = db.execute(
            """
            SELECT oa.assertion_type, oa.raw_owner_name, oa.confidence,
                   p.roll_year
            FROM ownership_assertion oa
            JOIN parcel_snapshot p USING(parcel_id)
            WHERE oa.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchall()
        tax_events = db.execute(
            """
            SELECT event_type, tax_year, native_event_id
            FROM tax_account_event
            WHERE source_id=?
            ORDER BY event_type, tax_year, native_event_id
            """,
            (SOURCE_ID,),
        ).fetchall()
        aliases = db.execute(
            """
            SELECT alias_type, alias_value, effective_from
            FROM parcel_alias
            WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchall()
        prohibited_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "recorded_instrument",
                "instrument_party",
                "instrument_parcel",
                "sale_event",
            )
        }
    finally:
        db.close()

    assert [tuple(row) for row in parcels] == [
        (PARCEL, "2025"),
        (PARCEL, TAX_YEAR),
    ]
    assert [tuple(row) for row in assessments] == [
        ("2025", 1_700_000_000, 50_000_000, 1_750_000_000, None),
        (
            TAX_YEAR,
            1_700_000_000,
            50_000_000,
            1_750_000_000,
            1_750_000_000,
        ),
    ]
    assert [tuple(row) for row in owner] == [
        ("assessment_roll", "GSJVI LLC", "high", TAX_YEAR)
    ]
    assert {
        (row["event_type"], row["tax_year"], row["native_event_id"])
        for row in tax_events
    } >= {
        ("property_tax_statement", "2025", "24372908"),
        ("property_tax_statement", TAX_YEAR, "24457395"),
        ("property_tax_payment", "2025", "1786629"),
    }
    assert [tuple(row) for row in aliases] == [
        ("capture_cama_tax_year_parcel_id", "1614772", TAX_YEAR)
    ]
    assert prohibited_counts == {
        "recorded_instrument": 0,
        "instrument_party": 0,
        "instrument_parcel": 0,
        "sale_event": 0,
    }


def test_projection_rejects_mismatched_observation_identity(
    tmp_path: Path,
) -> None:
    record = _detail_record()
    record["observation_identity"] = {
        **record["observation_identity"],
        "tax_year": "2025",
    }
    with pytest.raises(
        ValueError,
        match="observation identity disagrees",
    ):
        ingest_property_envelope(
            _envelope(record),
            db_path=tmp_path / "property.db",
        )


def test_retrieved_print_view_projects_as_document_not_instrument(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "bill.html"
    content = _fixture("artifact.html").encode()
    destination.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    canonical_ref = usvi._child_ref(  # noqa: SLF001
        "property_tax_bill_print_view",
        f"{PARCEL}|tax-year:{TAX_YEAR}|statement:24457395",
    )
    artifact = {
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_bill_print_view",
        "canonical_ref": canonical_ref,
        "native_document_id": canonical_ref,
        "artifact_kind": "bill",
        "formatted_parcel_number": PARCEL,
        "tax_year": TAX_YEAR,
        "statement_number": "24457395",
        "media_type": "text/html",
        "sha256": digest,
        "byte_length": len(content),
        "destination": str(destination),
        "source_url": usvi.BASE_URL + "CZ_ReceiptPrint.aspx",
        "session_guid_persisted": False,
    }
    result = ingest_property_envelope(
        _envelope(artifact, operation="artifact"),
        db_path=tmp_path / "property.db",
        raw_artifact_path=destination,
    )
    assert result["records"][0]["artifacts_upserted"] == 1

    db = connect_property(tmp_path / "property.db")
    try:
        document = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, storage_path,
                   acquisition_method, rights_tier, access_state
            FROM document_artifact
            """
        ).fetchone()
        instrument_count = db.execute(
            "SELECT COUNT(*) FROM recorded_instrument"
        ).fetchone()[0]
    finally:
        db.close()
    assert tuple(document) == (
        canonical_ref,
        digest,
        "text/html",
        str(destination),
        "direct_official_print_view_download",
        "official_public_assessment_tax_print_view",
        "public",
    )
    assert instrument_count == 0


def test_monitor_hashes_contract_separately_from_rolling_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _detail_record()
    observed: list[dict[str, Any]] = []
    closed: list[bool] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            observed.append(kwargs)
            self.request_count = 0

        def close(self) -> None:
            closed.append(True)

    def fake_detail(
        client: FakeClient,
        **kwargs: Any,
    ) -> dict[str, Any]:
        assert kwargs["component_names"] == ("valuation",)
        client.request_count = 5
        return json.loads(json.dumps(record))

    monkeypatch.setattr(usvi, "CaptureCAMAClient", FakeClient)
    monkeypatch.setattr(usvi, "fetch_parcel_detail", fake_detail)
    context = ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.2}},
        timeout=10,
        max_attempts=3,
        sample_bytes=None,
    )
    first = probe_usvi_property_tax(context)
    record["current_published_observation"]["total_due"] = "$1.00"
    second = probe_usvi_property_tax(context)
    record["components"]["valuation"]["statements"][0]["published_fields"][
        "New Source Column"
    ] = "value"
    schema_changed = probe_usvi_property_tax(context)
    monkeypatch.setattr(
        usvi,
        "FAILOVER_BASE_URL",
        "https://alternate.example.test/CAMA/CAPortal/",
    )
    route_changed = probe_usvi_property_tax(context)

    assert [value["request_budget"] for value in observed] == [5, 5, 5, 5]
    assert len(closed) == 4
    assert first.artifact_sha256 == sha256_fingerprint(
        first.details["stable_contract"]
    )
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert schema_changed.schema_sha256 != second.schema_sha256
    assert schema_changed.artifact_sha256 == second.artifact_sha256
    assert route_changed.artifact_sha256 != first.artifact_sha256
    assert first.details["stable_contract"]["monitor"] == {
        "request_budget": 5,
        "components_fetched": ["valuation"],
        "large_artifacts_fetched": False,
    }
    assert (
        public_records_monitor.HANDLER_REGISTRY[SOURCE_ID].expected_requests
        == 5
    )


def test_catalog_census_report_plan_and_citation_cover_cama(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    db = sqlite3.connect(catalog_path)
    try:
        roles = db.execute(
            """
            SELECT t.role
            FROM source_census_target_sources a
            JOIN source_census_targets t USING(census_target_id)
            WHERE a.source_id=?
            ORDER BY t.role
            """,
            (SOURCE_ID,),
        ).fetchall()
    finally:
        db.close()
    assert [row[0] for row in roles] == ["assessment_roll", "tax_collection"]

    report = source_report.check_public_records_catalog(catalog_path)
    report_row = next(
        value
        for value in report.values()
        if isinstance(value, dict) and value.get("source_id") == SOURCE_ID
    )
    assert report_row["query_tool"] == "tools/query_property.py"
    assert report_row["status"] == "configured"

    plan = build_search_plan(
        "EXAMPLE OWNER",
        jurisdictions=["78"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    source = next(
        row for row in plan["sources"] if row["source_id"] == SOURCE_ID
    )
    capabilities = {
        task["capability"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    complement_group = next(
        row
        for row in plan["complementary_routes"]
        if row["primary_source_id"] == SOURCE_ID
    )
    assert source["requested_jurisdiction_coverage"]["status"] == "matched"
    assert {
        "search_owner",
        "search_address",
        "search_assessment_records",
        "search_tax_accounts",
        "fetch_parcel",
        "fetch_bills",
        "fetch_payment_history",
        "download_document",
    } <= capabilities
    assert {
        value["source_id"] for value in complement_group["complements"]
    } == {"us-vi-recorder-of-deeds-countyfusion"}

    source_urls = json.loads(
        (
            Path(__file__).parents[1]
            / "web"
            / "src"
            / "data"
            / "source-urls.json"
        ).read_text()
    )
    assert source_urls[f"PROPERTY_SOURCE:{SOURCE_ID}"] == usvi.AUTHORITY_URL
