from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_marion_downloads as marion
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _row(columns: tuple[str, ...], **values: Any) -> list[str]:
    row = [""] * len(columns)
    for name, value in values.items():
        row[columns.index(name)] = str(value)
    return row


def _sales_record() -> dict[str, Any]:
    release = marion.Release(
        source_id=marion.SALES_SOURCE_ID,
        release_id="sales-2021",
        label="2021 sales",
        url="https://example.test/2021sales.csv",
        coverage_start=2021,
        coverage_end=2021,
        publication_kind="annual_csv",
        format="csv",
        schema_profile="sales_csv_abbreviated_v2",
    )
    values = _row(
        marion.SALES_V2_COLUMNS,
        account_number="510174",
        map_taxlot="032W290000400",
        sale_date="03/04/2021",
        instrument_number="2021-12345",
        deed_reel_page="4455/47",
        document_type_code="WD",
        document_type_description="Warranty Deed",
        sale_price="2545000",
        condition_code="A",
        situs_address="100 SAMPLE RD",
        grantor_name="SAMPLE FARMS LLC",
        grantee_name="KCK PARTNERS LLC",
    )
    return marion._normalize_sale_row(
        values,
        raw_header=marion.SALES_V2_RAW_HEADER,
        canonical_columns=marion.SALES_V2_COLUMNS,
        release=release,
        artifact_sha256="a" * 64,
        member_occurrence_id="sales-member",
        row_number=2,
    )


def _assessment_record() -> dict[str, Any]:
    raw_header = (
        "TYYYY",
        "RDATE",
        "TXID",
        "ACCOUNT_ID",
        "TXCD",
        "PCLS",
        "PCLSD",
        "AV",
        "RMVLAND",
        "RMVIMPR",
        "SITUSSTR",
        "SITUSCITY",
        "SITUSZIP",
        "BOOKPG",
        "SALEPR",
        "SALE_GRANTEE",
        "SALE_GRANTOR",
    )
    values = _row(
        raw_header,
        TYYYY="2026",
        RDATE="20260701",
        TXID="R10174",
        ACCOUNT_ID="510174",
        TXCD="001",
        PCLS="550",
        PCLSD="Farm",
        AV="276968",
        RMVLAND="1508580",
        RMVIMPR="325000",
        SITUSSTR="100 SAMPLE RD",
        SITUSCITY="SALEM",
        SITUSZIP="97301",
        BOOKPG="35450047",
        SALEPR="2545000",
        SALE_GRANTEE="KCK PARTNERS LLC",
        SALE_GRANTOR="SAMPLE FARMS LLC",
    )
    release = marion.Release(
        source_id=marion.ASSESSMENT_SOURCE_ID,
        release_id="comprehensive-current",
        label="Comprehensive",
        url=marion.COMPREHENSIVE_URL,
        coverage_start=None,
        coverage_end=None,
        publication_kind="monthly_current_snapshot",
        format="zip",
        schema_profile="comprehensive_assessment_v1",
    )
    return marion._normalize_assessment_row(
        values,
        raw_header=raw_header,
        release=release,
        artifact_sha256="b" * 64,
        member_occurrence_id="assessment-member",
        row_number=2,
    )


def _envelope(record: dict[str, Any]) -> dict[str, Any]:
    source_id = record["source_id"]
    args = marion.build_parser().parse_args(
        [
            "search",
            "fixture",
            "--source",
            source_id,
            "--artifact",
            "/tmp/marion-fixture",
        ]
    )
    return PublicRecordsResult.success(
        marion._build_query(args),
        [record],
        raw_artifact_refs=("/tmp/marion-fixture",),
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def test_shared_routes_expose_only_source_supported_operations() -> None:
    sales_routes = query_property.LIVE_ROUTES[marion.SALES_SOURCE_ID]
    assessment_routes = query_property.LIVE_ROUTES[
        marion.ASSESSMENT_SOURCE_ID
    ]

    assert sorted(sales_routes) == [
        "account",
        "address",
        "discovery",
        "download",
        "instrument",
        "manifest",
        "parcel",
        "probe",
        "releases",
        "sale",
        "search",
    ]
    assert sorted(assessment_routes) == [
        "account",
        "address",
        "discovery",
        "download",
        "instrument",
        "manifest",
        "parcel",
        "probe",
        "releases",
        "search",
    ]
    assert "owner" not in sales_routes
    assert "owner" not in assessment_routes
    assert "sale" not in assessment_routes


def test_shared_translation_preserves_local_artifact_and_release_selectors(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "2021sales.csv"
    search = query_property._oregon_marion_download_args(
        _parse(
            "instrument",
            "2021-12345",
            "--source",
            marion.SALES_SOURCE_ID,
            "--jurisdiction",
            "41047",
            "--artifact-path",
            str(artifact),
            "--limit",
            "7",
        ),
        "search",
    )
    manifest = query_property._oregon_marion_download_args(
        _parse(
            "manifest",
            "sales-2020",
            "--source",
            marion.SALES_SOURCE_ID,
            "--tax-year",
            "2020",
        ),
        "manifest",
    )

    assert search.command == "search"
    assert search.query == "2021-12345"
    assert search.field == "instrument"
    assert search.match == "exact"
    assert search.artifact == str(artifact)
    assert search.limit == 7
    assert manifest.command == "manifest"
    assert manifest.release == "sales-2020"
    assert manifest.year == 2020


def test_shared_translation_rejects_cross_county_and_unpublished_owner_scope() -> None:
    with pytest.raises(ValueError, match="Marion County"):
        query_property._oregon_marion_download_args(
            _parse(
                "account",
                "510174",
                "--source",
                marion.ASSESSMENT_SOURCE_ID,
                "--county",
                "Lane",
            ),
            "search",
        )

    guidance = query_property._source_guidance(
        marion.ASSESSMENT_SOURCE_ID
    )
    assert "owner" not in guidance["unified_operations"]
    assert guidance["official_complements"]
    assert "omitted since February 1, 2015" in guidance["note"]


def test_shared_ingestion_keeps_sale_occurrence_assessment_and_owner_scopes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    artifact_path = tmp_path / "marion-source-artifact"
    artifact_path.write_bytes(b"marion fixture")
    sale_record = _sales_record()
    assessment_record = _assessment_record()

    sale_report = ingest_property_envelope(
        _envelope(sale_record),
        db_path=db_path,
        raw_artifact_path=artifact_path,
    )
    assert sale_report["projection_supported"] is True
    assert sale_report["records"][0]["sales_upserted"] == 1
    assert sale_report["records"][0]["owners_upserted"] == 0
    assert sale_report["records"][0]["parcel_placeholder_created"] is True
    assert sale_report["records"][0]["parcel_anchor_source_id"] == (
        marion.SALES_SOURCE_ID
    )

    db = connect_property(db_path)
    try:
        parcel_shell = db.execute(
            """
            SELECT source_id, native_parcel_id, raw_json
            FROM parcel_snapshot
            WHERE parcel_id=?
            """,
            (sale_report["records"][0]["parcel_id"],),
        ).fetchone()
        assert parcel_shell["source_id"] == marion.SALES_SOURCE_ID
        assert parcel_shell["native_parcel_id"] == "032W290000400"
        shell_raw = json.loads(parcel_shell["raw_json"])
        assert shell_raw["parcel_shell"] == {
            "state": "sale_source_anchor",
            "source_id": marion.SALES_SOURCE_ID,
            "candidate_related_source_ids": [
                marion.MARION_PARCELS_SOURCE_ID,
                marion.ASSESSMENT_SOURCE_ID,
            ],
            "join_keys": sale_record["join_keys"],
        }
    finally:
        db.close()

    assessment_report = ingest_property_envelope(
        _envelope(assessment_record),
        db_path=db_path,
        raw_artifact_path=artifact_path,
    )

    assert assessment_report["projection_supported"] is True
    assert assessment_report["records"][0]["assessments_upserted"] == 1
    assert assessment_report["records"][0]["owners_upserted"] == 0
    assert assessment_report["records"][0]["sales_upserted"] == 0
    assert assessment_report["records"][0]["parcel_id"] == (
        sale_report["records"][0]["parcel_id"]
    )

    db = connect_property(db_path)
    try:
        adopted_parcel = db.execute(
            """
            SELECT source_id, native_parcel_id, roll_year
            FROM parcel_snapshot
            WHERE parcel_id=?
            """,
            (sale_report["records"][0]["parcel_id"],),
        ).fetchone()
        assert tuple(adopted_parcel) == (
            marion.ASSESSMENT_SOURCE_ID,
            "510174",
            "2026",
        )
        aliases = {
            (row["alias_type"], row["alias_value"], row["source_id"])
            for row in db.execute(
                """
                SELECT alias_type, alias_value, source_id
                FROM parcel_alias
                WHERE parcel_id=?
                """,
                (sale_report["records"][0]["parcel_id"],),
            ).fetchall()
        }
        assert (
            "map_taxlot",
            "032W290000400",
            marion.SALES_SOURCE_ID,
        ) in aliases
        assert (
            "assessment_account",
            "510174",
            marion.SALES_SOURCE_ID,
        ) in aliases
        sale = db.execute(
            """
            SELECT source_id, native_sale_id, sale_date,
                   consideration_minor, derivation, raw_json
            FROM sale_event
            WHERE source_id=?
            """,
            (marion.SALES_SOURCE_ID,),
        ).fetchone()
        assert tuple(sale)[:5] == (
            marion.SALES_SOURCE_ID,
            sale_record["native_sale_id"],
            "2021-03-04",
            254_500_000,
            "assessor_sale_analysis",
        )
        sale_raw = json.loads(sale["raw_json"])
        assert sale_raw["transaction_parties"] == (
            sale_record["transaction_parties"]
        )

        observation = db.execute(
            """
            SELECT source_native_id, raw_artifact_path, raw_artifact_sha256
            FROM source_observation
            WHERE source_id=?
            """,
            (marion.SALES_SOURCE_ID,),
        ).fetchone()
        assert tuple(observation) == (
            sale_record["source_occurrence_id"],
            str(artifact_path),
            sale_report["raw_artifact_sha256"],
        )

        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor, assessment_class
            FROM assessment
            WHERE source_id=?
            """,
            (marion.ASSESSMENT_SOURCE_ID,),
        ).fetchone()
        assert tuple(assessment) == (
            "2026",
            150_858_000,
            32_500_000,
            183_358_000,
            27_696_800,
            "550",
        )
        assert db.execute(
            """
            SELECT COUNT(*)
            FROM ownership_assertion
            WHERE source_id=?
            """,
            (marion.ASSESSMENT_SOURCE_ID,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM recorded_instrument"
        ).fetchone()[0] == 0
    finally:
        db.close()
