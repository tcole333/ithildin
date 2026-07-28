import hashlib
import json
from pathlib import Path

import pytest

from tools import query_acris, query_cook_property, query_md_property
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_nc_envelope,
    ingest_property_envelope,
)
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsError,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    ResultStatus,
    SourceMetadata,
)
from tools.public_records_store import connect_property
from tools.query_nc_property import _normalize_feature, build_query


def _envelope():
    query = build_query(
        "parcel",
        "3013467134",
        county_geoid="37005",
        limit=1,
        cursor=None,
        return_geometry=True,
    )
    record = _normalize_feature(
        {
            "attributes": {
                "objectid": 6061042,
                "parno": "3013467134",
                "altparno": "ALT-3013",
                "ownname": "SMITH, THOMAS",
                "ownname2": "SMITH, JANE",
                "siteadd": "100 MAIN ST",
                "scity": "Sparta",
                "sstate": "NC",
                "szip": "28675",
                "mailadd": "PO BOX 1",
                "mcity": "Sparta",
                "mstate": "NC",
                "mzip": "28675",
                "landval": 1000.01,
                "improvval": 900.02,
                "parval": 1900.03,
                "parvaltype": "ASSESSED",
                "saledatetx": "02-08-2024",
                "sourceref": "BK-1-PG-2",
                "revdatetx": "2025-01-31",
                "reviseyear": 2025,
                "stfips": "37",
                "cntyfips": "005",
                "stcntyfips": "37005",
                "cntyname": "Alleghany",
            },
            "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
        schema_fingerprint="a" * 64,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
        warnings=("county freshness varies",),
    ).to_dict()


def _cook_envelope():
    query = query_cook_property.build_query(
        "parcel",
        "01-01-106-009-1001",
        tax_year=2026,
        limit=1,
        cursor=None,
    )
    record = query_cook_property._normalize_record(
        {
            "pin": "01011060091001",
            "pin10": "0101106009",
            "year": "2026.0",
            "class": "599",
            "triad_name": "North",
            "triad_code": "2",
            "township_name": "Barrington",
            "township_code": "10",
            "nbhd_code": "10012",
            "tax_code": "10148",
            "zip_code": "60010",
            "lon": "-88.1331071142",
            "lat": "42.1526952977",
            "row_id": "010110600910012026",
        },
        response_schema_fingerprint="cook-response-schema",
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def _maryland_envelope():
    fields = query_md_property.FIELDS
    query = query_md_property.build_query(
        "parcel",
        "04030311078580",
        county_code="04",
        limit=1,
        cursor=None,
    )
    record = query_md_property._normalize_record(
        {
            fields["jurisdiction_code"]: "BACO",
            fields["county_name"]: "Baltimore County",
            fields["account_id"]: "04030311078580",
            fields["property_link"]: {
                "url": "https://sdat.dat.maryland.gov/RealProperty/example"
            },
            fields["finder_link"]: {
                "url": "https://apps.planning.maryland.gov/finderonline/example"
            },
            fields["longitude"]: "-76.7068417664",
            fields["latitude"]: "39.3733046671",
            fields["county_code"]: "04",
            fields["district"]: "03",
            fields["account_number"]: "0311078580",
            fields["owner_occupancy"]: "N",
            fields["address"]: "7 TRAYMORE RD ",
            fields["city"]: "PIKESVILLE",
            fields["postal_code"]: "21208",
            fields["legal_1"]: "0.2191 AC",
            fields["legal_2"]: "7 TRAYMORE RD",
            fields["legal_3"]: "MARLBOROUGH ESTATES",
            fields["deed_liber"]: "48094",
            fields["deed_folio"]: "0187",
            fields["base_land"]: "97100",
            fields["base_improvements"]: "0",
            fields["current_land"]: "97100",
            fields["current_improvements"]: "0",
            fields["current_total"]: "97100",
            fields["assessment_cycle_year"]: "2025",
            fields["source_updated"]: "20250703",
            (
                "sales_segment_1_grantor_name_mdp_field_grntnam1_sdat_field_80"
            ): "BALTIMORE HEBREW CONGREGATION",
            (
                "sales_segment_1_transfer_number_mdp_field_transno1_sdat_field_79"
            ): "000001",
            (
                "sales_segment_1_transfer_date_yyyy_mm_dd_mdp_field_"
                "tradate_sdat_field_89"
            ): "2023.05.31",
            (
                "sales_segment_1_consideration_mdp_field_considr1_sdat_field_90"
            ): "175000",
        },
        response_schema_fingerprint="md-response-schema",
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def _acris_envelope():
    query = query_acris.build_query(
        "document",
        {"document_id": "2024001"},
        borough=None,
        requested_limit=1,
        cursor=None,
    )
    record = {
        "source_id": query_acris.SOURCE_ID,
        "document_id": "2024001",
        "crfn": "2024000000001",
        "document_type": "DEED",
        "document_type_description": "Deed",
        "master": {
            "document_id": "2024001",
            "crfn": "2024000000001",
            "doc_type": "DEED",
            "document_date": "2024-01-02T00:00:00.000",
            "recorded_datetime": "2024-01-03T10:30:00.000",
            "document_amt": "125000",
            "reel_nbr": "123",
            "reel_pg": "456",
        },
        "parties": [
            {
                "document_id": "2024001",
                "party_type": "1",
                "name": "SELLER LLC",
            },
            {
                "document_id": "2024001",
                "party_type": "2",
                "name": "BUYER LLC",
                "address_1": "100 MAIN ST",
                "city": "NEW YORK",
                "state": "NY",
                "zip": "10001",
            },
        ],
        "legals": [
            {
                "document_id": "2024001",
                "borough": "1",
                "block": "123",
                "lot": "45",
                "street_number": "100",
                "street_name": "MAIN ST",
                "unit": "2A",
            }
        ],
        "enrichment_complete": True,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def test_nc_ingestion_preserves_raw_hashes_and_normalizes_model(tmp_path):
    db_path = tmp_path / "property.db"
    source_file = tmp_path / "source-envelope.json"
    envelope = _envelope()
    source_file.write_text(json.dumps(envelope), encoding="utf-8")

    first = ingest_nc_envelope(
        envelope,
        db_path=db_path,
        raw_artifact_path=source_file,
    )
    second = ingest_nc_envelope(_envelope(), db_path=db_path)

    assert first["records_ingested"] == 1
    assert len(first["envelope_sha256"]) == 64
    assert len(first["records"][0]["record_sha256"]) == 64
    assert first["records"][0]["canonical_ref"].endswith(
        "/37005/parcel/3013467134"
    )
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        observation = db.execute(
            """
            SELECT raw_artifact_sha256, raw_artifact_path, raw_json
            FROM source_observation
            WHERE record_kind='parcel_snapshot'
            ORDER BY observation_id LIMIT 1
            """
        ).fetchone()
        assert observation["raw_artifact_sha256"] == hashlib.sha256(
            source_file.read_bytes()
        ).hexdigest()
        assert observation["raw_artifact_path"] == str(source_file.resolve())
        assert '"raw_attributes"' in observation["raw_json"]
        assert db.execute("SELECT COUNT(*) FROM parcel_alias").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 2
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == ("2025", 100001, 90002, 190003)
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        geometry = db.execute(
            "SELECT geometry_ref, geometry_format FROM parcel_geometry"
        ).fetchone()
        assert geometry["geometry_ref"].startswith(
            "source-observation-sha256:"
        )
        assert geometry["geometry_format"] == "esri_json"
    finally:
        db.close()


def test_nc_ingestion_rejects_failure_and_wrong_source(tmp_path):
    envelope = _envelope()
    envelope["query"]["source"]["source_id"] = "us-fl-dor-property-roll"
    with pytest.raises(PropertyIngestError, match="requires source"):
        ingest_nc_envelope(envelope, db_path=tmp_path / "property.db")

    query = build_query(
        "parcel",
        "3013467134",
        county_geoid="37005",
        limit=1,
        cursor=None,
        return_geometry=False,
    )
    failure = PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="offline",
                message="offline",
                category="transport",
            )
        ],
    ).to_dict()
    with pytest.raises(PropertyIngestError, match="unsupported ingestion"):
        ingest_nc_envelope(failure, db_path=tmp_path / "property.db")


def test_generic_dispatch_ingests_cook_snapshot_without_inventing_owner(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_cook_envelope(), db_path=db_path)
    second = ingest_property_envelope(_cook_envelope(), db_path=db_path)

    assert first["source_id"] == query_cook_property.SOURCE_ID
    assert first["records"][0]["owner_visibility_state"] == (
        "not_present_in_dataset_schema"
    )
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_alias").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        assessment = db.execute(
            """
            SELECT tax_year, assessment_class, total_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == ("2026", "599", None)
        snapshot = db.execute(
            "SELECT raw_json FROM parcel_snapshot"
        ).fetchone()
        assert '"state":"not_present_in_dataset_schema"' in snapshot["raw_json"]
    finally:
        db.close()


def test_generic_dispatch_ingests_maryland_without_backfilling_hidden_owner(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_maryland_envelope(), db_path=db_path)
    second = ingest_property_envelope(_maryland_envelope(), db_path=db_path)

    assert first["records"][0]["owner_visibility_state"] == "withheld_by_source"
    assert first["records"][0]["sales_upserted"] == 1
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_alias").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2025",
            9_710_000,
            0,
            9_710_000,
            9_710_000,
        )
        sale = db.execute(
            "SELECT native_sale_id, sale_date, consideration_minor, raw_json "
            "FROM sale_event"
        ).fetchone()
        assert tuple(sale)[:3] == (
            "transfer:000001",
            "2023-05-31",
            17_500_000,
        )
        assert "BALTIMORE HEBREW CONGREGATION" in sale["raw_json"]
        snapshot = db.execute(
            "SELECT raw_json FROM parcel_snapshot"
        ).fetchone()
        assert '"state":"withheld_by_source"' in snapshot["raw_json"]
    finally:
        db.close()


def test_generic_dispatch_projects_acris_instrument_parties_and_bbl(tmp_path):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_acris_envelope(), db_path=db_path)
    second = ingest_property_envelope(_acris_envelope(), db_path=db_path)

    assert first["records"][0]["parties_upserted"] == 2
    assert first["records"][0]["parcels_upserted"] == 1
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_parcel").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        instrument = db.execute(
            """
            SELECT jurisdiction_geoid, native_document_id, instrument_type,
                   execution_date, recording_date, consideration_minor
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument) == (
            "nyc-acris",
            "2024001",
            "DEED",
            "2024-01-02",
            "2024-01-03",
            12_500_000,
        )
        roles = {
            row["raw_name"]: row["role"]
            for row in db.execute(
                "SELECT raw_name, role FROM instrument_party"
            ).fetchall()
        }
        assert roles == {"SELLER LLC": "grantor", "BUYER LLC": "grantee"}
        parcel = db.execute(
            "SELECT jurisdiction_geoid, native_parcel_id FROM parcel_snapshot"
        ).fetchone()
        assert tuple(parcel) == ("36061", "1-123-45")
    finally:
        db.close()


def test_generic_dispatch_preserves_non_success_envelope_without_projection(
    tmp_path,
):
    query = query_cook_property.build_query(
        "parcel",
        "01-01-106-009-1001",
        tax_year=None,
        limit=1,
        cursor=None,
    )
    failure = PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="offline",
                message="offline",
                category="transport",
            )
        ],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(failure, db_path=db_path)

    assert result["records_ingested"] == 0
    assert result["source_status"] == "unavailable"
    db = connect_property(db_path)
    try:
        observation = db.execute(
            "SELECT access_status, raw_json FROM source_observation"
        ).fetchone()
        assert observation["access_status"] == "unavailable"
        assert '"code":"offline"' in observation["raw_json"]
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
    finally:
        db.close()


def test_generic_dispatch_preserves_new_source_before_projection_mapper(tmp_path):
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-test-property",
            name="Test property source",
            source_role="test",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="us-test",
            name="Test jurisdiction",
        ),
        query=QueryMetadata(
            operation="parcel",
            parameters={"selector": "P-1"},
            requested_limit=1,
        ),
    )
    envelope = PublicRecordsResult.success(
        query,
        [{"native_parcel_id": "P-1", "raw": {"field": "value"}}],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["projection_supported"] is False
    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
    finally:
        db.close()


def test_direct_cli_dispatches_canonical_envelope(tmp_path):
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parent.parent
    input_path = tmp_path / "cook-envelope.json"
    output_path = tmp_path / "ingest-summary.json"
    db_path = tmp_path / "property.db"
    input_path.write_text(json.dumps(_cook_envelope()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/ingest_property_records.py",
            "ingest",
            "--input",
            str(input_path),
            "--property-db",
            str(db_path),
            "--output",
            str(output_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["source_id"] == query_cook_property.SOURCE_ID
    assert summary["records_ingested"] == 1
    assert db_path.exists()


def test_direct_cli_help_uses_repository_tool_pattern():
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/ingest_property_records.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Normalize property" in result.stdout
    assert "ingest" in result.stdout
