from __future__ import annotations

import json
import sqlite3
import struct
import zipfile
from pathlib import Path

import pytest

from tools import query_michigan_eaton_parcels as eaton
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_store import connect_property


def _artifact(tmp_path: Path) -> Path:
    fields = [
        ("PARCELID", "C", 18, 0),
        ("LOWPARCELI", "C", 8, 0),
        ("LPARCEL", "C", 24, 0),
        ("SITEADDRES", "C", 50, 0),
        ("ZONING_COD", "C", 12, 0),
        ("OWNERNME1", "C", 35, 0),
        ("OWNERNME2", "C", 35, 0),
        ("CNTASSDVAL", "N", 12, 0),
        ("CNTTXBLVAL", "N", 12, 0),
        ("CLASSCD", "C", 5, 0),
        ("CLASSDSCRP", "C", 30, 0),
        ("BSAOnline", "C", 90, 0),
        ("Acreage", "N", 12, 4),
    ]
    row = {
        "PARCELID": "04008075016000",
        "LOWPARCELI": "160-00",
        "LPARCEL": "040-080-750-160-00",
        "SITEADDRES": "504 BURGENSTOCK DR, LANSING, MI 48917",
        "ZONING_COD": "NONE",
        "OWNERNME1": "LAWRENCE, TYRONE",
        "OWNERNME2": "LAWRENCE, WINIFRED",
        "CNTASSDVAL": 186100,
        "CNTTXBLVAL": 143685,
        "CLASSCD": "407",
        "CLASSDSCRP": "RESIDENTIAL CONDOMINIUMS",
        "BSAOnline": (
            "https://bsaonline.com/SiteSearch/SiteSearchDetails"
            "?uid=418&ReferenceKey=040-080-750-160-00"
        ),
        "Acreage": 0.0394,
    }
    header_length = 32 + len(fields) * 32 + 1
    record_length = 1 + sum(field[2] for field in fields)
    header = bytearray(32)
    header[0] = 0x03
    header[1:4] = bytes((126, 7, 1))
    header[4:8] = struct.pack("<I", 1)
    header[8:10] = struct.pack("<H", header_length)
    header[10:12] = struct.pack("<H", record_length)
    descriptors = bytearray()
    record = bytearray(b" ")
    for name, field_type, length, decimals in fields:
        descriptor = bytearray(32)
        descriptor[: len(name)] = name.encode("ascii")
        descriptor[11] = ord(field_type)
        descriptor[16] = length
        descriptor[17] = decimals
        descriptors.extend(descriptor)

        value = row[name]
        if field_type == "N":
            text = (
                f"{float(value):.{decimals}f}"
                if decimals
                else str(int(value))
            )
            encoded = text.rjust(length).encode("ascii")
        else:
            encoded = str(value).encode()[:length].ljust(length)
        record.extend(encoded)
    dbf = bytes(header + descriptors + b"\r" + record + b"\x1a")

    shp = bytearray(100)
    shp[0:4] = struct.pack(">i", 9994)
    shp[24:28] = struct.pack(">i", 50)
    shp[28:32] = struct.pack("<i", 1000)
    shp[32:36] = struct.pack("<i", 5)
    shp[36:68] = struct.pack("<4d", 1.0, 2.0, 3.0, 4.0)

    artifact = tmp_path / "TaxParcel.zip"
    with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("TaxParcel.cpg", "UTF-8")
        archive.writestr("TaxParcel.dbf", dbf)
        archive.writestr("TaxParcel.shp", bytes(shp))
        archive.writestr("TaxParcel.shx", b"index")
        archive.writestr("TaxParcel.prj", 'PROJCS["fixture"]')
    return artifact


def _parse(*argv: str):
    return query_property.build_parser().parse_args(list(argv))


def test_shared_routes_translate_snapshot_and_live_metadata(tmp_path):
    artifact = _artifact(tmp_path)
    owner = _parse(
        "owner",
        "lawrence",
        "--source",
        eaton.SOURCE_ID,
        "--jurisdiction",
        "26045",
        "--artifact-path",
        str(artifact),
        "--limit",
        "7",
    )
    translated = query_property._michigan_eaton_parcel_args(owner, "search")

    assert translated.command == "search"
    assert translated.artifact == str(artifact)
    assert translated.field == "owner"
    assert translated.match == "contains"
    assert translated.limit == 7

    freshness = _parse(
        "freshness",
        "*",
        "--source",
        eaton.SOURCE_ID,
        "--jurisdiction",
        "26",
    )
    metadata = query_property._michigan_eaton_parcel_args(
        freshness,
        "metadata",
    )
    assert metadata.command == "metadata"
    assert "freshness" in query_property.LIVE_ROUTES[eaton.SOURCE_ID]


def test_shared_route_requires_artifact_and_eaton_scope():
    missing_artifact = _parse(
        "owner",
        "smith",
        "--source",
        eaton.SOURCE_ID,
    )
    with pytest.raises(ValueError, match="--artifact-path"):
        query_property._michigan_eaton_parcel_args(
            missing_artifact,
            "search",
        )

    wrong_county = _parse(
        "parcel",
        "123",
        "--source",
        eaton.SOURCE_ID,
        "--jurisdiction",
        "26125",
        "--artifact-path",
        "/tmp/TaxParcel.zip",
    )
    with pytest.raises(ValueError, match="Eaton County"):
        query_property._michigan_eaton_parcel_args(wrong_county, "search")


def test_shared_query_and_ingest_project_snapshot_semantics(
    tmp_path,
    monkeypatch,
):
    artifact = _artifact(tmp_path)
    catalog_db = tmp_path / "catalog.db"
    property_db = tmp_path / "property.db"
    monkeypatch.setattr(eaton, "log_search", lambda *args, **kwargs: None)
    args = _parse(
        "owner",
        "lawrence",
        "--source",
        eaton.SOURCE_ID,
        "--jurisdiction",
        "26045",
        "--artifact-path",
        str(artifact),
        "--catalog-db",
        str(catalog_db),
        "--property-db",
        str(property_db),
        "--ingest",
    )

    payload = query_property.execute(args)

    assert payload["status"] == "ok"
    assert payload["records"][0]["native_parcel_id"] == "040-080-750-160-00"
    assert payload["ingest"]["records_ingested"] == 1
    assert payload["ingest"]["raw_artifact_sha256"] == (
        payload["records"][0]["artifact_snapshot"]["sha256"]
    )

    db = connect_property(property_db)
    try:
        parcel = db.execute(
            """
            SELECT * FROM parcel_snapshot
            WHERE source_id=? AND native_parcel_id=?
            """,
            (eaton.SOURCE_ID, "040-080-750-160-00"),
        ).fetchone()
        assert parcel["jurisdiction_geoid"] == "26045"
        assert parcel["roll_year"] == ""
        assert parcel["effective_from"] == "2026-07-01"

        owners = db.execute(
            """
            SELECT raw_owner_name, assertion_type
            FROM ownership_assertion
            WHERE parcel_id=? ORDER BY raw_owner_name
            """,
            (parcel["parcel_id"],),
        ).fetchall()
        assert [(row["raw_owner_name"], row["assertion_type"]) for row in owners] == [
            ("LAWRENCE, TYRONE", "assessment_roll"),
            ("LAWRENCE, WINIFRED", "assessment_roll"),
        ]

        address = db.execute(
            "SELECT * FROM parcel_address WHERE parcel_id=?",
            (parcel["parcel_id"],),
        ).fetchone()
        assert address["address_role"] == "situs"
        assert address["raw_address"].startswith("504 BURGENSTOCK")

        assessment = db.execute(
            "SELECT * FROM assessment WHERE parcel_id=?",
            (parcel["parcel_id"],),
        ).fetchone()
        assert assessment["tax_year"] == ""
        assert assessment["assessed_value_minor"] == 18_610_000
        raw_assessment = json.loads(assessment["raw_json"])
        assert raw_assessment["taxable_value"] == 143685

        observation = db.execute(
            """
            SELECT raw_artifact_path, raw_artifact_sha256
            FROM source_observation
            WHERE source_id=? AND record_kind='parcel_assessment_snapshot'
            """,
            (eaton.SOURCE_ID,),
        ).fetchone()
        assert observation["raw_artifact_path"] == str(artifact.resolve())
        assert observation["raw_artifact_sha256"]

        for table in (
            "recorded_instrument",
            "sale_event",
            "tax_account_event",
            "parcel_geometry",
        ):
            count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0
    finally:
        db.close()


def test_nonparcel_eaton_records_are_preserved_without_projection(tmp_path):
    property_db = tmp_path / "property.db"
    envelope = {
        "schema_version": "public-records-result/1.0",
        "retrieved_at": "2026-07-30T00:00:00Z",
        "status": "ok",
        "query": {
            "schema_version": "public-records-query/1.0",
            "source": {
                "source_id": eaton.SOURCE_ID,
                "name": "Eaton County Parcel Shapefile",
                "source_role": "county_bulk_snapshot",
                "base_url": eaton.ITEM_PAGE_URL,
                "dataset_id": eaton.ITEM_ID,
                "metadata": {},
            },
            "jurisdiction": {
                "jurisdiction_id": "26045",
                "name": "Eaton County",
                "country_code": "US",
                "state_code": "MI",
                "county_fips": "26045",
                "locality": None,
                "metadata": {},
            },
            "query": {
                "operation": "metadata",
                "parameters": {},
                "requested_limit": None,
                "cursor": None,
                "metadata": {},
            },
            "fingerprint": "fixture-query",
        },
        "records": [
            {
                "canonical_ref": "MI-EATON-PARCEL-METADATA:1782910860000",
                "source_id": eaton.SOURCE_ID,
                "record_kind": "bulk_dataset_metadata",
                "schema_fingerprint": "fixture-schema",
                "source_url": eaton.ITEM_PAGE_URL,
                "license": {
                    "published_text": "Fixture license",
                    "attribution": "Eaton County GIS",
                },
            }
        ],
        "next_cursor": None,
        "raw_artifact_refs": [eaton.ITEM_API_URL],
        "warnings": [],
        "errors": [],
    }

    result = ingest_property_envelope(envelope, db_path=property_db)

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "eaton_non_parcel_source_metadata_observation"
    )
    db = sqlite3.connect(property_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 2
    finally:
        db.close()


def test_shared_guidance_keeps_declared_and_observed_scope_separate():
    guidance = query_property._source_guidance(eaton.SOURCE_ID)

    assert guidance["mode"] == (
        "unified_local_search_of_official_county_bulk_snapshot"
    )
    assert guidance["bulk_workflow"]["shared_artifact_selector"] == (
        "--artifact-path FILE"
    )
    assert "Assessment year is left unset" in guidance["note"]
    assert guidance["unified_operations"] == [
        "account",
        "address",
        "freshness",
        "map",
        "owner",
        "parcel",
        "probe",
        "search",
    ]
