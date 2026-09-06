from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_palm_beach_property_appraiser as appraiser
from tools import query_palm_beach_tax_deeds as tax_deeds
from tools.ingest_property_records import PropertyIngestError, ingest_property_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "public_records"


def _envelope(
    source_metadata,
    jurisdiction,
    operation: str,
    *records: dict[str, Any],
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=source_metadata,
        jurisdiction=jurisdiction,
        query=QueryMetadata(operation=operation),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _tax_deed_detail() -> dict[str, Any]:
    html = (
        FIXTURE_ROOT
        / "palm_beach_tax_deeds"
        / "detail-43079.html"
    ).read_text(encoding="utf-8")
    return tax_deeds.parse_detail(
        html,
        portal_row_id=tax_deeds.SENTINEL_ROW_ID,
    )


def _appraiser_record() -> dict[str, Any]:
    fixture_dir = FIXTURE_ROOT / "palm_beach_property_appraiser"
    metadata = json.loads(
        (fixture_dir / "metadata.json").read_text(encoding="utf-8")
    )
    features = json.loads(
        (fixture_dir / "features.json").read_text(encoding="utf-8")
    )
    return appraiser.normalize_feature(
        features[0],
        contract=appraiser.metadata_contract(metadata),
        geometry_requested=True,
    )


def test_tax_deed_case_projects_event_roles_and_source_attributed_shell(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    detail = _tax_deed_detail()
    summary = ingest_property_envelope(
        _envelope(
            tax_deeds.SOURCE_METADATA,
            tax_deeds.JURISDICTION,
            "detail",
            detail,
        ),
        db_path=db_path,
    )

    assert summary["projection_supported"] is True
    assert summary["records_ingested"] == 1
    result = summary["records"][0]
    assert result["parcel_placeholder_created"] == 1
    assert result["parcel_link_method"] == "exact_source_pcn_candidate"
    assert result["parties_upserted"] == 4
    assert result["representations_upserted"] == 4
    assert result["current_ownership_assertions_created"] == 0

    db = connect_property(db_path)
    try:
        jurisdiction = db.execute(
            "SELECT name, jurisdiction_type, parent_geoid, state_code, county_code "
            "FROM jurisdiction WHERE geoid='12099'"
        ).fetchone()
        assert tuple(jurisdiction) == ("Palm Beach County", "county", "12", "FL", "099")
        observation = db.execute(
            "SELECT raw_json FROM source_observation WHERE source_id=? "
            "AND record_kind='tax_deed_case_occurrence'",
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert json.loads(observation["raw_json"])["jurisdiction"] == (
            detail["jurisdiction"]
        )
        shell = db.execute(
            """
            SELECT source_id, native_parcel_id, raw_json
            FROM parcel_snapshot
            WHERE native_parcel_id=?
            """,
            (detail["parcel_id_normalized"],),
        ).fetchone()
        assert shell["source_id"] == tax_deeds.SOURCE_ID
        assert json.loads(shell["raw_json"])["placeholder_state"] == (
            "tax_deed_pcn_pending_property_appraiser_or_dor"
        )
        assert (
            db.execute(
                """
                SELECT COUNT(*)
                FROM parcel_snapshot
                WHERE source_id=?
                """,
                (appraiser.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )

        event = db.execute(
            """
            SELECT event_id, native_event_id, submitted_date, approved_date,
                   last_update_date, status
            FROM property_event
            WHERE source_id=?
            """,
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert event["native_event_id"] == detail["native_event_id"]
        assert event["submitted_date"] is None
        assert event["approved_date"] is None
        assert event["last_update_date"] is None
        assert event["status"] == "LANDS AVAILABLE"

        parties = db.execute(
            """
            SELECT role, raw_name, assertion_type
            FROM property_event_party
            WHERE event_id=?
            ORDER BY sequence_no
            """,
            (event["event_id"],),
        ).fetchall()
        assert [row["role"] for row in parties] == [
            "applicant",
            "source_reported_property_owner",
            "source_reported_property_owner",
            "source_reported_property_owner",
        ]
        assert all(
            row["assertion_type"] != "current_recorded_title_owner"
            for row in parties
        )
        assert (
            db.execute(
                """
                SELECT COUNT(*)
                FROM ownership_assertion
                WHERE source_id=?
                """,
                (tax_deeds.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )

        representations = db.execute(
            """
            SELECT representation_kind, source_state
            FROM property_event_representation
            WHERE event_id=?
            ORDER BY representation_id
            """,
            (event["event_id"],),
        ).fetchall()
        assert [row["source_state"] for row in representations] == [
            "public",
            "public_pdf",
            "image_not_available",
            "public_pdf",
        ]
        tax_event = db.execute(
            """
            SELECT event_type, event_date, status
            FROM tax_account_event
            WHERE source_id=?
            """,
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert tuple(tax_event) == (
            "tax_deed_case_status",
            "2023-10-18",
            "LANDS AVAILABLE",
        )
    finally:
        db.close()


@pytest.mark.parametrize(
    "jurisdiction",
    [
        {"state_code": "FL"},
        {"state_code": "FL", "county_fips": "099"},
        {"state_code": "FL", "county_fips": "12086"},
        {"state_code": "FL", "state_fips": "12"},
        {"state_code": "FL", "county_fips": "12099", "county_geoid": "12086"},
    ],
)
def test_tax_deed_rejects_missing_ambiguous_or_out_of_scope_county(
    tmp_path: Path, jurisdiction: dict[str, str]
) -> None:
    db_path = tmp_path / "property.db"
    detail = _tax_deed_detail()
    detail["jurisdiction"] = jurisdiction
    with pytest.raises(PropertyIngestError, match="GEOID"):
        ingest_property_envelope(
            _envelope(tax_deeds.SOURCE_METADATA, tax_deeds.JURISDICTION, "detail", detail),
            db_path=db_path,
        )
    db = connect_property(db_path)
    try:
        for table in ("jurisdiction", "source_observation", "property_event", "parcel_snapshot"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        db.close()


def test_tax_deed_still_accepts_legacy_record_jurisdiction(tmp_path: Path) -> None:
    detail = _tax_deed_detail()
    detail["jurisdiction"] = {
        "county_geoid": "12099",
        "state_fips": "12",
        "state_code": "FL",
        "county_name": "Palm Beach",
    }
    summary = ingest_property_envelope(
        _envelope(tax_deeds.SOURCE_METADATA, tax_deeds.JURISDICTION, "detail", detail),
        db_path=tmp_path / "property.db",
    )
    assert summary["records_ingested"] == 1
    assert summary["records"][0]["current_ownership_assertions_created"] == 0


def test_later_appraiser_observation_adopts_tax_deed_shell_with_provenance(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    detail = _tax_deed_detail()
    ingest_property_envelope(
        _envelope(
            tax_deeds.SOURCE_METADATA,
            tax_deeds.JURISDICTION,
            "detail",
            detail,
        ),
        db_path=db_path,
    )
    db = connect_property(db_path)
    try:
        shell_parcel_id = db.execute(
            """
            SELECT parcel_id
            FROM parcel_snapshot
            WHERE source_id=? AND native_parcel_id=?
            """,
            (tax_deeds.SOURCE_ID, detail["parcel_id_normalized"]),
        ).fetchone()["parcel_id"]
    finally:
        db.close()

    appraiser_summary = ingest_property_envelope(
        _envelope(
            appraiser.SOURCE_METADATA,
            appraiser.JURISDICTION,
            "parcel",
            _appraiser_record(),
        ),
        db_path=db_path,
    )
    appraiser_result = appraiser_summary["records"][0]
    assert appraiser_result["parcel_shells_adopted"] == 1
    assert appraiser_result["parcel_shell_source_ids_adopted"] == [
        tax_deeds.SOURCE_ID
    ]
    assert appraiser_result["parcel_shells_repointed"] == 0
    assert appraiser_result["parcel_shell_source_ids_repointed"] == []
    assert appraiser_result["tax_deed_shell_links_adopted"] == 1

    db = connect_property(db_path)
    try:
        papa_parcel = db.execute(
            """
            SELECT parcel_id
            FROM parcel_snapshot
            WHERE source_id=? AND native_parcel_id=?
            """,
            (appraiser.SOURCE_ID, detail["parcel_id_normalized"]),
        ).fetchone()
        shell = db.execute(
            """
            SELECT parcel_id
            FROM parcel_snapshot
            WHERE source_id=? AND native_parcel_id=?
            """,
            (tax_deeds.SOURCE_ID, detail["parcel_id_normalized"]),
        ).fetchone()
        assert papa_parcel is not None
        assert papa_parcel["parcel_id"] == shell_parcel_id
        assert shell is None

        link = db.execute(
            """
            SELECT pe.source_id, pepl.parcel_id
            FROM property_event_parcel_link pepl
            JOIN property_event pe ON pe.event_id=pepl.event_id
            WHERE pe.source_id=?
            """,
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert link["source_id"] == tax_deeds.SOURCE_ID
        assert link["parcel_id"] == papa_parcel["parcel_id"]
        tax_event = db.execute(
            """
            SELECT source_id, parcel_id
            FROM tax_account_event
            WHERE source_id=?
            """,
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert tax_event["source_id"] == tax_deeds.SOURCE_ID
        assert tax_event["parcel_id"] == papa_parcel["parcel_id"]
        alias = db.execute(
            """
            SELECT source_id, parcel_id
            FROM parcel_alias
            WHERE alias_type='palm_beach_pcn' AND alias_value=?
            """,
            (detail["parcel_id"],),
        ).fetchone()
        assert alias["source_id"] == tax_deeds.SOURCE_ID
        assert alias["parcel_id"] == papa_parcel["parcel_id"]
        assert (
            db.execute(
                """
                SELECT COUNT(*)
                FROM source_observation
                WHERE source_id=?
                  AND record_kind='tax_deed_case_occurrence'
                """,
                (tax_deeds.SOURCE_ID,),
            ).fetchone()[0]
            == 1
        )
    finally:
        db.close()


def test_downloaded_tax_deed_pdf_is_a_separate_idempotent_artifact(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    detail = _tax_deed_detail()
    document = next(
        value
        for value in detail["documents"]
        if value["native_document_id"] == tax_deeds.SENTINEL_DOCUMENT_ID
    )
    pdf = b"%PDF-1.7\nfixture tax deed document\n%%EOF"
    destination = tmp_path / "tax-certificate.pdf"
    artifact = tax_deeds._artifact_record(
        detail,
        document,
        tax_deeds.PDFArtifact(
            content=pdf,
            media_type="application/pdf",
            content_disposition="inline; filename=TaxCertificate.pdf",
            sha256=hashlib.sha256(pdf).hexdigest(),
        ),
        destination,
    )
    envelope = _envelope(
        tax_deeds.SOURCE_METADATA,
        tax_deeds.JURISDICTION,
        "document",
        artifact,
    )
    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    assert first["records"][0]["parent_case_identity_preserved"] is True
    assert first["records"][0]["artifact_id"] == (
        second["records"][0]["artifact_id"]
    )

    db = connect_property(db_path)
    try:
        row = db.execute(
            """
            SELECT native_document_id, instrument_id, sha256, mime_type,
                   storage_path, acquisition_method, rights_tier, access_state
            FROM document_artifact
            WHERE source_id=?
            """,
            (tax_deeds.SOURCE_ID,),
        ).fetchone()
        assert row["native_document_id"] == tax_deeds.SENTINEL_DOCUMENT_ID
        assert row["instrument_id"] is None
        assert row["sha256"] == artifact["sha256"]
        assert row["mime_type"] == "application/pdf"
        assert row["storage_path"] == str(destination)
        assert row["acquisition_method"] == "direct_source_pdf_download"
        assert row["rights_tier"] == "official_public_record_uncertified"
        assert row["access_state"] == "public"
        assert (
            db.execute(
                """
                SELECT COUNT(*)
                FROM document_artifact
                WHERE source_id=?
                """,
                (tax_deeds.SOURCE_ID,),
            ).fetchone()[0]
            == 1
        )
    finally:
        db.close()
