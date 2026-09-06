from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_md_plats as plats
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "public_records" / "md_plats"
RESULTS_URL = (
    "https://plats.msa.maryland.gov/pages/"
    "results.aspx?cid=MO&adv=1&id=fixture"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _parse_shared(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _search_record(index: int = 0) -> dict[str, Any]:
    page = plats.parse_results_page(
        _fixture("results_page1.html"),
        source_url=RESULTS_URL,
        county_code="MO",
        county_name="Montgomery County",
        selection_fingerprint="fixture-selection",
    )
    return dict(page.records[index])


def _detail_record(name: str = "detail_image.html") -> dict[str, Any]:
    return plats.parse_plat_detail(
        _fixture(name),
        source_url=(
            "https://plats.msa.maryland.gov/pages/"
            "unit.aspx?cid=MO&qualifier=C&series=1136&unit=1"
            if name == "detail_image.html"
            else
            "https://plats.msa.maryland.gov/pages/"
            "unit.aspx?cid=MO&qualifier=C&series=2139&unit=140"
        ),
        county_code="MO",
    )


def _envelope(
    record: dict[str, Any],
    *,
    operation: str,
) -> dict[str, Any]:
    query = plats._query(
        operation=operation,
        parameters={"fixture": True},
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=plats.SOURCE_ID,
        catalog_decision={
            "allowed": True,
            "limits": {"minimum_interval_seconds": 0.25},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_shared_routes_expose_plat_operations_and_distinct_complements() -> None:
    routes = query_property.LIVE_ROUTES[plats.SOURCE_ID]
    guidance = query_property._source_guidance(plats.SOURCE_ID)

    assert set(routes) == {
        "discovery",
        "download",
        "instrument",
        "probe",
        "search",
        "subdivision",
        "survey",
    }
    assert "owner" not in routes
    assert "parcel" not in routes
    assert guidance["native_keys"] == [
        "county_code",
        "archive_qualifier",
        "archive_series",
        "archive_unit",
    ]
    assert set(guidance["official_complements"]) == {
        "us-md-land-records",
        "us-md-mdp-parcel-points",
        "us-md-mdp-cama-downloads",
        "us-md-mdp-property-sales-downloads",
    }
    assert "recorded-title" in guidance["note"]
    assert "parcel-owner" in guidance["note"]


def test_shared_search_exhausts_by_default_and_limits_only_when_explicit() -> None:
    unbounded = query_property._md_plats_args(
        _parse_shared(
            "subdivision",
            "Timberland Estates",
            "--source",
            plats.SOURCE_ID,
            "--county",
            "Montgomery County",
        ),
        "subdivision",
    )
    bounded = query_property._md_plats_args(
        _parse_shared(
            "search",
            "Timberland Estates",
            "--source",
            plats.SOURCE_ID,
            "--jurisdiction",
            "24031",
            "--limit",
            "1",
            "--cursor",
            "cursor-value",
        ),
        "search",
    )

    assert unbounded.command == "search"
    assert unbounded.county == "MO"
    assert unbounded.mode == "advanced"
    assert unbounded.description == "Timberland Estates"
    assert unbounded.include_no_images is True
    assert unbounded.limit is None
    assert unbounded.cursor is None
    assert bounded.limit == 1
    assert bounded.cursor == "cursor-value"
    assert bounded.include_no_images is True


def test_shared_exact_accession_and_reference_searches_remain_distinct() -> None:
    detail = query_property._md_plats_args(
        _parse_shared(
            "instrument",
            "MO:C1136-1",
            "--source",
            plats.SOURCE_ID,
        ),
        "instrument",
    )
    book_page = query_property._md_plats_args(
        _parse_shared(
            "search",
            "222/17",
            "--source",
            plats.SOURCE_ID,
            "--county-code",
            "MO",
            "--search-field",
            "book-page",
        ),
        "search",
    )
    plat_reference = query_property._md_plats_args(
        _parse_shared(
            "instrument",
            "22281",
            "--source",
            plats.SOURCE_ID,
            "--jurisdiction",
            "24031",
        ),
        "instrument",
    )

    assert (
        detail.command,
        detail.county,
        detail.qualifier,
        detail.series,
        detail.unit,
    ) == ("plat", "MO", "C", "1136", "1")
    assert (book_page.mode, book_page.book, book_page.page) == (
        "basic",
        "222",
        "17",
    )
    assert (plat_reference.mode, plat_reference.plat) == ("basic", "22281")


def test_ingestion_preserves_metadata_only_occurrence_without_title_claims(
    tmp_path: Path,
) -> None:
    database = tmp_path / "property.db"
    record = _search_record(1)

    summary = ingest_property_envelope(
        _envelope(record, operation="search"),
        db_path=database,
    )

    projection = summary["records"][0]
    assert projection["native_plat_id"] == "MO:C2139-140"
    assert projection["result_occurrence_id"] == (
        record["result_occurrence"]["occurrence_identity"]
    )
    assert projection["metadata_only"] is True
    assert projection["recorded_instruments_upserted"] == 0
    assert projection["recorded_title_assertions_upserted"] == 0
    assert projection["parcel_owner_assertions_upserted"] == 0
    assert projection["parcel_links_upserted"] == 0

    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        observation = db.execute(
            """
            SELECT source_native_id, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind=?
            ORDER BY observation_id DESC
            LIMIT 1
            """,
            (plats.SOURCE_ID, "recorded_plat_search_occurrence"),
        ).fetchone()
        raw = json.loads(observation["raw_json"])
        assert observation["source_native_id"] == (
            record["result_occurrence"]["occurrence_identity"]
        )
        assert raw["record_identity"]["county_code"] == "MO"
        assert raw["record_identity"]["archive_qualifier"] == "C"
        assert raw["record_identity"]["archive_series"] == "2139"
        assert raw["record_identity"]["archive_unit"] == "140"
        assert raw["developer_owner"].startswith("Elliott")
        assert db.execute(
            "SELECT count(*) FROM recorded_instrument"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM parcel_snapshot"
        ).fetchone()[0] == 0


def test_ingestion_preserves_each_published_artifact_representation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "property.db"
    detail = _detail_record()

    first = ingest_property_envelope(
        _envelope(detail, operation="plat"),
        db_path=database,
    )
    second = ingest_property_envelope(
        _envelope(detail, operation="plat"),
        db_path=database,
    )

    assert first["records"][0]["metadata_only"] is False
    assert first["records"][0]["artifacts_upserted"] == 2
    assert second["records"][0]["artifacts_upserted"] == 2
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        artifacts = db.execute(
            """
            SELECT native_document_id, instrument_id, sha256, mime_type,
                   acquisition_method, source_url
            FROM document_artifact
            WHERE source_id=?
            ORDER BY native_document_id
            """,
            (plats.SOURCE_ID,),
        ).fetchall()
        assert len(artifacts) == 2
        assert all(row["native_document_id"].startswith("MO:C1136-1:") for row in artifacts)
        assert all(row["instrument_id"] is None for row in artifacts)
        assert all(row["sha256"] is None for row in artifacts)
        assert {row["mime_type"] for row in artifacts} == {
            "application/pdf",
            "image/tiff",
        }
        assert {
            row["acquisition_method"] for row in artifacts
        } == {"source_published_plat_representation"}
        representations = db.execute(
            """
            SELECT representation_type, structured_json
            FROM evidence_representation
            ORDER BY representation_id
            """
        ).fetchall()
        assert len(representations) == 2
        assert {
            row["representation_type"] for row in representations
        } == {"plat_artifact_metadata"}
        roles = {
            json.loads(row["structured_json"])["artifact"][
                "artifact_role"
            ]
            for row in representations
        }
        assert roles == {"compiled_pdf", "direct_scan"}


def test_monitor_separates_rolling_totals_from_contract_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    total = 601
    detail = _detail_record()
    sample = _search_record()

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.closed = False

        def counties(self):
            return tuple(
                plats.CountyRoute(
                    code=code,
                    name=name,
                    search_url=plats.SEARCH_URL_TEMPLATE.format(
                        county_code=code
                    ),
                )
                for code, (_geoid, name) in plats.COUNTY_GEOIDS.items()
            )

        def search(self, _selection, *, limit):
            assert limit == 1
            return SimpleNamespace(
                records=(sample,),
                next_cursor="fixture-cursor",
                pages_fetched=1,
                requests_made=4,
                source_image_result_count=500,
                source_total_result_count=total,
                source_total_pages=(total + 299) // 300,
                form_contract_fingerprint="a" * 64,
                result_schema_fingerprints=("b" * 64,),
            )

        def fetch_plat(self, county, qualifier, series, unit):
            assert (county, qualifier, series, unit) == (
                "MO",
                "C",
                "1136",
                "1",
            )
            return detail

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(plats, "MarylandPlatsClient", FakeClient)
    first = public_records_monitor.probe_maryland_plats(_context())
    total = 602
    second = public_records_monitor.probe_maryland_plats(_context())

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.details["requests_made"] == 6
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    comparison = compare_probes(
        {
            "probe_id": 1,
            "status": first.status,
            "schema_sha256": first.schema_sha256,
            "artifact_sha256": first.artifact_sha256,
        },
        {
            "probe_id": 2,
            "status": second.status,
            "schema_sha256": second.schema_sha256,
            "artifact_sha256": second.artifact_sha256,
        },
    )
    assert comparison["drift_detected"] is False


def test_catalog_handler_citation_and_docs_capture_verified_contract(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = catalog.show_source(plats.SOURCE_ID)["current_manifest"]

    assert manifest["source_status"] == "active"
    assert manifest["automation_disposition"] == "allowed_with_limits"
    assert manifest["identity_contract"]["record_identity"] == [
        "county_code",
        "archive_qualifier",
        "archive_series",
        "archive_unit",
    ]
    assert (
        manifest["identity_contract"][
            "developer_owner_is_recorded_title_assertion"
        ]
        is False
    )
    assert manifest["probe_evidence"]["jurisdictions_in_selector"] == 24
    assert manifest["capabilities"][1]["details"]["exhaustive_by_default"] is True
    handler = public_records_monitor.HANDLER_REGISTRY[plats.SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_maryland_plats
    assert handler.expected_requests == 6

    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        source_urls[f"PROPERTY_SOURCE:{plats.SOURCE_ID}"]
        == plats.INDEX_URL
    )
    for relative_path in (
        "docs/modules/property.md",
        "docs/TOOL_REFERENCE.md",
        "docs/PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md",
        "research/OSINT_RESOURCES.md",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "query_md_plats.py" in content
        assert plats.SOURCE_ID in content
        assert "metadata-only" in content

