from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_licking_property as licking
from tools import query_property
from tools.ingest_property_records import (
    PropertyIngestError,
    _licking_auditor_transfer_supports_sale_projection,
    ingest_property_envelope,
)
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_licking_property"
)
SOURCE_ID = licking.SOURCE_ID


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _records() -> list[dict[str, Any]]:
    features = json.loads(
        (FIXTURE_DIR / "features.json").read_text(encoding="utf-8")
    )["features"]
    return [
        licking._normalize_feature(
            feature,
            schema_fingerprint="a" * 64,
            geometry_requested=True,
        )
        for feature in (features[0], features[2])
    ]


def _envelope() -> dict[str, Any]:
    args = licking.build_parser().parse_args(
        ["parcel", licking.SENTINEL_PARCEL, "--geometry"]
    )
    return PublicRecordsResult.success(
        licking._build_query(args),
        _records(),
        retrieved_at="2026-07-31T12:00:00Z",
    ).to_dict()


def _feature_envelope(
    record: dict[str, Any],
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    args = licking.build_parser().parse_args(
        ["parcel", licking.SENTINEL_PARCEL, "--geometry"]
    )
    return PublicRecordsResult.success(
        licking._build_query(args),
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def test_shared_router_preserves_selectors_and_exhaustive_default() -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    unbounded = routes["search"].translate(
        _shared_args(
            "search",
            "SMITH",
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "39089",
            "--search-field",
            "owner",
        ),
        routes["search"].adapter_command,
    )
    bounded_map = routes["map"].translate(
        _shared_args(
            "map",
            licking.SENTINEL_PARCEL,
            "--source",
            SOURCE_ID,
            "--county",
            "Licking County",
            "--limit",
            "7",
        ),
        routes["map"].adapter_command,
    )
    legal = routes["legal"].translate(
        _shared_args(
            "legal",
            "LOT 12",
            "--source",
            SOURCE_ID,
        ),
        routes["legal"].adapter_command,
    )

    assert set(routes) == {
        "search",
        "owner",
        "address",
        "situs",
        "mailing",
        "parcel",
        "map",
        "fid",
        "geometry",
        "legal",
        "land-use",
        "instrument",
        "freshness",
        "discovery",
        "probe",
    }
    assert unbounded.command == "owner"
    assert unbounded.query == "SMITH"
    assert unbounded.limit is None
    assert bounded_map.command == "parcel"
    assert bounded_map.query == licking.SENTINEL_PARCEL
    assert bounded_map.geometry is True
    assert bounded_map.limit == 7
    assert legal.command == "attribute"
    assert legal.field == "legal-description"
    assert query_property._source_guidance(SOURCE_ID)["county_geoid"] == (
        "39089"
    )


def test_ingestion_projects_joinable_parcel_and_retains_null_key_occurrence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    result = ingest_property_envelope(_envelope(), db_path=db_path)

    assert result["records_seen"] == 2
    assert result["records_ingested"] == 1
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "licking_gis_occurrence_has_no_usable_parcel_join"
    )
    projected = result["records"][0]
    assert projected["feature_occurrence_id"] == (
        "{86A76591-6D08-42B0-BBA2-29EE229BD5E3}"
    )
    assert projected["owners_upserted"] == 1
    assert projected["assessments_upserted"] == 1
    assert projected["geometry_upserted"] == 1
    assert projected["transfer_observations_retained"] == 2
    assert projected["sales_upserted"] == 0
    assert projected["created_title_assertions"] == 0

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        observations = db.execute(
            """
            SELECT source_native_id, record_kind
            FROM source_observation
            WHERE source_id=? AND source_native_id IS NOT NULL
            ORDER BY observation_id
            """,
            (SOURCE_ID,),
        ).fetchall()
        title_rows = db.execute(
            """
            SELECT COUNT(*)
            FROM ownership_assertion
            WHERE assertion_type<>'assessment_roll'
            """
        ).fetchone()[0]
        sale_rows = db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0]
    finally:
        db.close()

    assert tuple(parcel) == (
        SOURCE_ID,
        "39089",
        licking.SENTINEL_PARCEL,
    )
    assert observations[0]["source_native_id"].startswith("{")
    assert observations[1]["source_native_id"].startswith("{")
    assert title_rows == 0
    assert sale_rows == 0


def test_transfer_projection_uses_published_sale_semantics() -> None:
    assert _licking_auditor_transfer_supports_sale_projection(
        {"valid_sale": "Y", "sale_amount": 0}
    )
    assert _licking_auditor_transfer_supports_sale_projection(
        {"valid_sale": None, "sale_amount": "125000.00"}
    )
    assert not _licking_auditor_transfer_supports_sale_projection(
        {"valid_sale": "N", "sale_amount": "125000.00"}
    )
    assert not _licking_auditor_transfer_supports_sale_projection(
        {"valid_sale": None, "sale_amount": "0.00"}
    )


def test_ingestion_does_not_let_an_older_complete_feature_replace_newer_state(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    newer = copy.deepcopy(_records()[1])
    newer["owner_name_observation"] = "NEWER OWNER"
    newer["assessment_value_observations"]["market_total"] = "500.00"
    older = copy.deepcopy(_records()[1])
    older["owner_name_observation"] = "OLDER OWNER"
    older["assessment_value_observations"]["market_total"] = "100.00"

    first = ingest_property_envelope(
        _feature_envelope(newer, retrieved_at="2026-08-02T00:00:00Z"),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _feature_envelope(older, retrieved_at="2026-08-01T00:00:00Z"),
        db_path=db_path,
    )

    assert first["records"][0]["owners_upserted"] == 1
    assert second["records"][0]["owners_upserted"] == 0
    assert second["records"][0]["assessments_upserted"] == 0
    assert second["records"][0]["sales_upserted"] == 0
    assert second["records"][0]["geometry_upserted"] == 0

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            "SELECT observation_id, raw_json FROM parcel_snapshot"
        ).fetchone()
        active_owners = db.execute(
            """
            SELECT raw_owner_name, observation_id
            FROM ownership_assertion
            WHERE source_id=? AND effective_to IS NULL
            """,
            (SOURCE_ID,),
        ).fetchall()
        assessment = db.execute(
            "SELECT total_value_minor, observation_id FROM assessment"
        ).fetchone()
        geometry = db.execute(
            "SELECT geometry_ref FROM parcel_geometry"
        ).fetchone()
    finally:
        db.close()

    assert json.loads(parcel["raw_json"])["owner_name_observation"] == (
        "NEWER OWNER"
    )
    assert [row["raw_owner_name"] for row in active_owners] == ["NEWER OWNER"]
    assert assessment["total_value_minor"] == 50_000
    assert assessment["observation_id"] == parcel["observation_id"]
    assert geometry["geometry_ref"] == (
        f"source-observation:{parcel['observation_id']}#/geometry"
    )


def test_ingestion_preserves_source_contract_without_property_projection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    args = licking.build_parser().parse_args(["source"])
    envelope = PublicRecordsResult.success(
        licking._build_query(args),
        [licking._source_record()],
        retrieved_at="2026-08-02T00:00:00Z",
    ).to_dict()

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["records_seen"] == 1
    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "licking_auditor_non_feature_source_observation"
    )
    db = connect_property(db_path)
    try:
        county = db.execute(
            "SELECT name FROM jurisdiction WHERE geoid='39089'"
        ).fetchone()
        observations = db.execute(
            """
            SELECT record_kind, source_native_id
            FROM source_observation
            WHERE source_id=? AND record_kind<>'query_envelope'
            """,
            (SOURCE_ID,),
        ).fetchall()
        parcel_count = db.execute(
            "SELECT COUNT(*) FROM parcel_snapshot"
        ).fetchone()[0]
    finally:
        db.close()

    assert county["name"] == "Licking County"
    assert [tuple(row) for row in observations] == [
        ("licking_auditor_source_contract", SOURCE_ID)
    ]
    assert parcel_count == 0


@pytest.mark.parametrize("record_kind", ["source", "null-parcel"])
def test_observation_only_records_reject_another_county_geoid(
    tmp_path: Path,
    record_kind: str,
) -> None:
    if record_kind == "source":
        args = licking.build_parser().parse_args(["source"])
        record = copy.deepcopy(licking._source_record())
        record["jurisdiction"]["jurisdiction_id"] = "39035"
        record["jurisdiction"]["metadata"]["county_geoid"] = "39035"
        envelope = PublicRecordsResult.success(
            licking._build_query(args),
            [record],
            retrieved_at="2026-08-02T00:00:00Z",
        ).to_dict()
    else:
        record = copy.deepcopy(_records()[0])
        record["jurisdiction"]["county_geoid"] = "39035"
        envelope = _feature_envelope(
            record,
            retrieved_at="2026-08-02T00:00:00Z",
        )

    with pytest.raises(PropertyIngestError, match="out-of-scope county GEOID"):
        ingest_property_envelope(envelope, db_path=tmp_path / "property.db")


def test_catalog_monitor_and_citations_share_the_licking_source_id() -> None:
    catalog = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    manifest = next(
        item for item in catalog["sources"] if item["source_id"] == SOURCE_ID
    )
    citation_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    associations = {
        item["role"]: item for item in manifest["census_associations"]
    }

    assert manifest["adapter_version"] == 1
    assert manifest["source_status"] == "active"
    assert set(associations) == {"assessment_roll", "parcel_geometry"}
    assert all(
        item["jurisdiction_geoid"] == "39089"
        for item in associations.values()
    )
    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_ohio_licking_auditor_gis
    assert spec.expected_requests == 4
    assert citation_urls[f"PROPERTY_SOURCE:{SOURCE_ID}"] == licking.VIEWER_URL


def test_monitor_rejects_actual_probe_request_count_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = licking.build_parser().parse_args(["probe"])
    result = PublicRecordsResult.success(
        licking._build_query(args),
        [
            {
                "source_id": SOURCE_ID,
                "probe_request_count": 5,
            }
        ],
        retrieved_at="2026-08-02T00:00:00Z",
    )
    monkeypatch.setattr(licking, "execute", lambda *args, **kwargs: result)
    context = public_records_monitor.ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=1,
        max_attempts=1,
        sample_bytes=None,
    )

    with pytest.raises(ValueError, match="request contract changed"):
        public_records_monitor.probe_ohio_licking_auditor_gis(context)
