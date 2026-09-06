from __future__ import annotations

import csv
import io
import json
import sqlite3
import struct
import zipfile
from pathlib import Path

import pytest

from tools import ingest_fl_dor_property
from tools.fl_dor_property_common import resolve_county


NAL_HEADER = [
    "CO_NO",
    "PARCEL_ID",
    "FILE_T",
    "ASMNT_YR",
    "DOR_UC",
    "JV",
    "LND_VAL",
    "EFF_YR_BLT",
    "ACT_YR_BLT",
    "OWN_NAME",
    "OWN_ADDR1",
    "OWN_ADDR2",
    "OWN_CITY",
    "OWN_STATE",
    "OWN_ZIPCD",
    "S_LEGAL",
    "PHY_ADDR1",
    "PHY_ADDR2",
    "PHY_CITY",
    "PHY_ZIPCD",
    "ALT_KEY",
    "SEQ_NO",
    "RS_ID",
    "MP_ID",
    "STATE_PAR_ID",
]
SDF_HEADER = [
    "CO_NO",
    "PARCEL_ID",
    "ASMNT_YR",
    "ATV_STRT",
    "GRP_NO",
    "DOR_UC",
    "NBRHD_CD",
    "MKT_AR",
    "CENSUS_BK",
    "SALE_ID_CD",
    "SAL_CHG_CD",
    "VI_CD",
    "OR_BOOK",
    "OR_PAGE",
    "CLERK_NO",
    "QUAL_CD",
    "SALE_YR",
    "SALE_MO",
    "SALE_PRC",
    "MULTI_PAR_SAL",
    "RS_ID",
    "MP_ID",
    "STATE_PARCEL_ID",
]


def _csv_bytes(header: list[str], rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def _nal_archive(path: Path) -> Path:
    rows = [
        {
            "CO_NO": "12",
            "PARCEL_ID": "000000000007005946",
            "FILE_T": "R",
            "ASMNT_YR": "2026",
            "DOR_UC": "098",
            "JV": "298238",
            "LND_VAL": "298238",
            "EFF_YR_BLT": "1998",
            "ACT_YR_BLT": "1997",
            "OWN_NAME": "FLORIDA GULF AND ATLANTIC RAIL",
            "OWN_ADDR1": "245  RIVERSIDE AVE",
            "OWN_ADDR2": "STE 250",
            "OWN_CITY": "JACKSONVILLE",
            "OWN_STATE": "FL",
            "OWN_ZIPCD": "32202",
            "S_LEGAL": "LEG RAILROAD PROPERTY",
            "PHY_ADDR1": "12345 RAILROAD",
            "PHY_ADDR2": "",
            "PHY_CITY": "MACCLENNY",
            "PHY_ZIPCD": "32063",
            "ALT_KEY": "ALT-946",
            "SEQ_NO": "1",
            "RS_ID": "2DCE",
            "MP_ID": "009DB791",
            "STATE_PAR_ID": "C12-001-033-6145-7",
        },
        {
            "CO_NO": "12",
            "PARCEL_ID": "011S20000000000032",
            "FILE_T": "R",
            "ASMNT_YR": "2026",
            "DOR_UC": "002",
            "JV": "181000",
            "LND_VAL": "50000",
            "EFF_YR_BLT": "",
            "ACT_YR_BLT": "",
            "OWN_NAME": "",
            "OWN_ADDR1": "",
            "OWN_ADDR2": "",
            "OWN_CITY": "",
            "OWN_STATE": "",
            "OWN_ZIPCD": "",
            "S_LEGAL": "LOT 32",
            "PHY_ADDR1": "32 TEST ROAD",
            "PHY_ADDR2": "",
            "PHY_CITY": "MACCLENNY",
            "PHY_ZIPCD": "32063",
            "ALT_KEY": "ALT-032",
            "SEQ_NO": "2",
            "RS_ID": "2DCE",
            "MP_ID": "00B2CA75",
            "STATE_PAR_ID": "C12-001-171-7237-9",
        },
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "NAL12P202601.csv",
            _csv_bytes(NAL_HEADER, rows),
        )
    return path


def _sdf_archive(path: Path) -> Path:
    rows = [
        {
            "CO_NO": "12",
            "PARCEL_ID": "011S20000000000032",
            "ASMNT_YR": "2026",
            "ATV_STRT": "1",
            "GRP_NO": "2",
            "DOR_UC": "002",
            "NBRHD_CD": "21900",
            "MKT_AR": "02",
            "CENSUS_BK": "",
            "SALE_ID_CD": "66949",
            "SAL_CHG_CD": "",
            "VI_CD": "I",
            "OR_BOOK": "",
            "OR_PAGE": "",
            "CLERK_NO": "202600001484",
            "QUAL_CD": "18",
            "SALE_YR": "2026",
            "SALE_MO": "03",
            "SALE_PRC": "181000",
            "MULTI_PAR_SAL": "",
            "RS_ID": "2DCE",
            "MP_ID": "00B2CA75",
            "STATE_PARCEL_ID": "C12-001-171-7237-9",
        },
        {
            "CO_NO": "12",
            "PARCEL_ID": "011S20010400000074",
            "ASMNT_YR": "2026",
            "ATV_STRT": "8",
            "GRP_NO": "2",
            "DOR_UC": "000",
            "NBRHD_CD": "20300",
            "MKT_AR": "02",
            "CENSUS_BK": "",
            "SALE_ID_CD": "65428",
            "SAL_CHG_CD": "",
            "VI_CD": "V",
            "OR_BOOK": "1500",
            "OR_PAGE": "22",
            "CLERK_NO": "",
            "QUAL_CD": "14",
            "SALE_YR": "2025",
            "SALE_MO": "07",
            "SALE_PRC": "100",
            "MULTI_PAR_SAL": "",
            "RS_ID": "2DCE",
            "MP_ID": "00B2CA76",
            "STATE_PARCEL_ID": "C12-001-171-7238-7",
        },
        {
            "CO_NO": "12",
            "PARCEL_ID": "011S20010400000240",
            "ASMNT_YR": "2026",
            "ATV_STRT": "1",
            "GRP_NO": "3",
            "DOR_UC": "001",
            "NBRHD_CD": "20300",
            "MKT_AR": "02",
            "CENSUS_BK": "",
            "SALE_ID_CD": "UNDATED-1",
            "SAL_CHG_CD": "",
            "VI_CD": "I",
            "OR_BOOK": "",
            "OR_PAGE": "",
            "CLERK_NO": "",
            "QUAL_CD": "14",
            "SALE_YR": "",
            "SALE_MO": "",
            "SALE_PRC": "25000",
            "MULTI_PAR_SAL": "",
            "RS_ID": "2DCE",
            "MP_ID": "000172FE",
            "STATE_PARCEL_ID": "C12-000-009-4974-3",
        },
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "SDF12P202601.csv",
            _csv_bytes(SDF_HEADER, rows),
        )
    return path


def _dbf_bytes(parcel_ids: list[str]) -> bytes:
    field_length = 26
    record_length = 1 + field_length
    header_length = 32 + 32 + 1
    header = bytearray(32)
    header[0] = 0x03
    header[1:4] = bytes((126, 7, 30))
    struct.pack_into("<I", header, 4, len(parcel_ids))
    struct.pack_into("<H", header, 8, header_length)
    struct.pack_into("<H", header, 10, record_length)
    descriptor = bytearray(32)
    descriptor[:8] = b"PARCELNO"
    descriptor[11] = ord("C")
    descriptor[16] = field_length
    records = b"".join(
        b" " + value.encode().ljust(field_length, b" ")
        for value in parcel_ids
    )
    return bytes(header) + bytes(descriptor) + b"\r" + records + b"\x1a"


def _polygon_content(points: list[tuple[float, float]]) -> bytes:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    output = io.BytesIO()
    output.write(struct.pack("<i", 5))
    output.write(struct.pack("<4d", min(xs), min(ys), max(xs), max(ys)))
    output.write(struct.pack("<2i", 1, len(points)))
    output.write(struct.pack("<i", 0))
    for x, y in points:
        output.write(struct.pack("<2d", x, y))
    return output.getvalue()


def _shape_header(*, file_length_bytes: int) -> bytes:
    header = bytearray(100)
    struct.pack_into(">i", header, 0, 9994)
    struct.pack_into(">i", header, 24, file_length_bytes // 2)
    struct.pack_into("<i", header, 28, 1000)
    struct.pack_into("<i", header, 32, 5)
    struct.pack_into("<4d", header, 36, 0.0, 0.0, 31.0, 31.0)
    return bytes(header)


def _shp_and_shx(contents: list[bytes]) -> tuple[bytes, bytes]:
    shp_size = 100 + sum(8 + len(content) for content in contents)
    shp = io.BytesIO()
    shp.write(_shape_header(file_length_bytes=shp_size))
    shx = io.BytesIO()
    shx.write(
        _shape_header(file_length_bytes=100 + 8 * len(contents))
    )
    offset_bytes = 100
    for record_number, content in enumerate(contents, start=1):
        shp.write(struct.pack(">2i", record_number, len(content) // 2))
        shp.write(content)
        shx.write(
            struct.pack(
                ">2i",
                offset_bytes // 2,
                len(content) // 2,
            )
        )
        offset_bytes += 8 + len(content)
    return shp.getvalue(), shx.getvalue()


def _gis_archive(path: Path) -> Path:
    squares = [
        [
            (offset, offset),
            (offset, offset + 1.0),
            (offset + 1.0, offset + 1.0),
            (offset + 1.0, offset),
            (offset, offset),
        ]
        for offset in (0.0, 10.0, 20.0)
    ]
    contents = [
        _polygon_content(squares[0]),
        _polygon_content(squares[1]),
        _polygon_content(squares[2]),
        struct.pack("<i", 0),
    ]
    shp, shx = _shp_and_shx(contents)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "baker_2026pin.dbf",
            _dbf_bytes(
                [
                    "000000000007005946",
                    "011S20000000000032",
                    "000000000007005946",
                    "",
                ]
            ),
        )
        archive.writestr(
            "baker_2026pin.prj",
            'PROJCS["NAD_1983_2011_StatePlane_Florida_North",'
            'AUTHORITY["EPSG","6441"]]',
        )
        archive.writestr("baker_2026pin.cpg", "UTF-8")
        archive.writestr("baker_2026pin.shp", shp)
        archive.writestr("baker_2026pin.shx", shx)
    return path


def _args(
    dataset_type: str,
    archive: Path,
    property_db: Path,
    *extra: str,
):
    return ingest_fl_dor_property.build_parser().parse_args(
        [
            "ingest",
            "--type",
            dataset_type,
            "--archive",
            str(archive),
            "--property-db",
            str(property_db),
            "--retrieved-at",
            "2026-07-30T00:00:00Z",
            *extra,
        ]
    )


def _counts(path: Path) -> dict[str, int]:
    db = sqlite3.connect(path)
    try:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "source_observation",
                "parcel_snapshot",
                "parcel_alias",
                "parcel_address",
                "ownership_assertion",
                "assessment",
                "sale_event",
                "recorded_instrument",
                "parcel_geometry",
            )
        }
    finally:
        db.close()


def test_dor_county_numbers_are_crosswalked_not_used_as_fips() -> None:
    assert resolve_county("12") == (12, "Baker", "12003")
    assert resolve_county("12003") == (12, "Baker", "12003")
    assert resolve_county("003") == (12, "Baker", "12003")
    assert resolve_county("Miami-Dade") == (23, "Dade", "12086")


def test_nal_stream_projects_assessment_observations_and_is_idempotent(
    tmp_path: Path,
) -> None:
    archive = _nal_archive(tmp_path / "baker-nal.zip")
    db_path = tmp_path / "property.db"
    args = _args(
        "nal",
        archive,
        db_path,
        "--county",
        "12003",
        "--tax-year",
        "2026",
        "--batch-size",
        "1",
    )

    first = ingest_fl_dor_property.execute(args)
    first_counts = _counts(db_path)
    second = ingest_fl_dor_property.execute(args)
    second_counts = _counts(db_path)

    assert first["release"]["county_dor_number"] == 12
    assert first["release"]["release_id"] == "nal:2026P:12:nal"
    assert len(first["release"]["release_identity_sha256"]) == 64
    assert first["schema"]["header_fields"] == NAL_HEADER
    assert first["counts"]["rows_processed"] == 2
    assert first["counts"]["owners_upserted"] == 1
    assert first["counts"]["assessments_upserted"] == 2
    assert first["exhausted"] is True
    assert second["archive_observation_inserted"] is False
    assert second["counts"]["observations_inserted"] == 0
    assert second_counts == first_counts
    assert first_counts == {
        "source_observation": 3,
        "parcel_snapshot": 2,
        "parcel_alias": 8,
        "parcel_address": 3,
        "ownership_assertion": 1,
        "assessment": 2,
        "sale_event": 0,
        "recorded_instrument": 0,
        "parcel_geometry": 0,
    }

    db = sqlite3.connect(db_path)
    try:
        db.row_factory = sqlite3.Row
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, raw_json
            FROM parcel_snapshot
            WHERE native_parcel_id='000000000007005946'
            """
        ).fetchone()
        assessment = db.execute(
            """
            SELECT land_value_minor, market_value_minor, assessment_class
            FROM assessment
            WHERE parcel_id=(
                SELECT parcel_id FROM parcel_snapshot
                WHERE native_parcel_id='000000000007005946'
            )
            """
        ).fetchone()
        assert parcel["jurisdiction_geoid"] == "12003"
        raw = json.loads(parcel["raw_json"])
        assert raw["legal_description"] == "LEG RAILROAD PROPERTY"
        assert raw["building"]["actual_year_built"] == "1997"
        assert raw["raw_fields"]["OWN_ADDR1"] == "245  RIVERSIDE AVE"
        assert raw["source_omission_state"]["representation"] == (
            "publisher_omitted_records_remain_absent"
        )
        assert assessment["land_value_minor"] == 29_823_800
        assert assessment["market_value_minor"] == 29_823_800
        assert assessment["assessment_class"] == "098"
    finally:
        db.close()


def test_sdf_stream_preserves_instrument_references_without_title_projection(
    tmp_path: Path,
) -> None:
    archive = _sdf_archive(tmp_path / "baker-sdf.zip")
    db_path = tmp_path / "property.db"
    args = _args("sdf", archive, db_path, "--county", "Baker")

    first = ingest_fl_dor_property.execute(args)
    first_counts = _counts(db_path)
    second = ingest_fl_dor_property.execute(args)

    assert first["schema"]["header_fields"] == SDF_HEADER
    assert first["counts"]["rows_processed"] == 3
    assert first["counts"]["sale_events_upserted"] == 3
    assert first["counts"]["instrument_references_preserved"] == 2
    assert first["counts"]["recorded_instruments_upserted"] == 0
    assert second["counts"]["observations_inserted"] == 0
    assert _counts(db_path) == first_counts
    assert first_counts["sale_event"] == 3
    assert first_counts["recorded_instrument"] == 0

    db = sqlite3.connect(db_path)
    try:
        raw_json, derivation, sale_date = db.execute(
            """
            SELECT raw_json, derivation, sale_date
            FROM sale_event
            WHERE consideration_minor=18100000
            """
        ).fetchone()
        raw = json.loads(raw_json)
        assert derivation == "assessment_sales_file"
        assert sale_date == "2026-03"
        reference = raw["sale"]["instrument_reference"]
        assert reference["clerk_instrument_number"] == "202600001484"
        assert reference["recorded_title_evidence"] is False
        assert (
            db.execute(
                "SELECT COUNT(*) FROM sale_event WHERE sale_date IS NULL"
            ).fetchone()[0]
            == 1
        )
    finally:
        db.close()


def test_gis_pin_projects_native_geometry_without_losing_occurrences(
    tmp_path: Path,
) -> None:
    archive = _gis_archive(tmp_path / "baker-gis.zip")
    db_path = tmp_path / "property.db"
    args = _args("gis-pin", archive, db_path, "--county", "003")

    first = ingest_fl_dor_property.execute(args)
    first_counts = _counts(db_path)
    second = ingest_fl_dor_property.execute(args)

    assert first["counts"]["rows_processed"] == 4
    assert first["counts"]["gis_join_rows_preserved"] == 3
    assert first["counts"]["gis_unjoinable_rows_preserved"] == 1
    assert first["counts"]["parcels_upserted"] == 2
    assert first["counts"]["geometries_upserted"] == 2
    assert first["counts"]["gis_repeated_join_parcels"] == 1
    assert first["counts"]["gis_null_geometry_occurrences"] == 1
    assert first["schema"]["join"] == {
        "gis_field": "PARCELNO",
        "nal_field": "PARCEL_ID",
        "relationship": "publisher_declared_join_key",
    }
    assert first["schema"]["geometry_projection"]["status"] == (
        "decoded_native_crs"
    )
    assert (
        'AUTHORITY["EPSG","6441"]'
        in first["schema"]["shapefile"]["crs"]["wkt"]
    )
    assert second["counts"]["observations_inserted"] == 0
    assert (
        second["counts"]["geometry_projection_observations_inserted"]
        == 0
    )
    assert _counts(db_path) == first_counts
    assert first_counts["source_observation"] == 6
    assert first_counts["parcel_snapshot"] == 2
    assert first_counts["parcel_geometry"] == 2

    db = sqlite3.connect(db_path)
    try:
        rows = db.execute(
            """
            SELECT source_native_id, raw_json
            FROM source_observation
            WHERE record_kind='florida_dor_gis_pin_feature_occurrence'
              AND source_native_id LIKE '%:000000000007005946'
            ORDER BY source_native_id
            """
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] != rows[1][0]
        assert {
            json.loads(row[1])["source_row_number"]
            for row in rows
        } == {0, 2}
        blank = db.execute(
            """
            SELECT raw_json FROM source_observation
            WHERE record_kind='florida_dor_gis_pin_feature_occurrence'
              AND source_native_id LIKE '%:blank'
            """
        ).fetchone()
        assert json.loads(blank[0])["join"]["join_state"] == (
            "source_join_key_blank"
        )
        projection = db.execute(
            """
            SELECT raw_json
            FROM source_observation
            WHERE record_kind=
                'florida_dor_gis_pin_parcel_geometry_projection'
            """
        ).fetchone()
        projected = json.loads(projection[0])
        assert projected["geometry"]["representation"] == (
            "source_feature_collection"
        )
        assert len(projected["geometry"]["features"]) == 2
        assert projected["geometry"]["union_or_dissolve_applied"] is False
        geometries = db.execute(
            """
            SELECT geometry_ref, geometry_format, crs
            FROM parcel_geometry
            ORDER BY geometry_id
            """
        ).fetchall()
        assert {row[2] for row in geometries} == {"EPSG:6441"}
        assert {
            row[1] for row in geometries
        } == {
            "esri_shapefile_native_geometry_json",
            "esri_shapefile_native_feature_collection_json",
        }
    finally:
        db.close()


def test_gis_pin_checkpoint_reconciles_later_repeated_features(
    tmp_path: Path,
) -> None:
    archive = _gis_archive(tmp_path / "baker-gis.zip")
    db_path = tmp_path / "property.db"

    first = ingest_fl_dor_property.execute(
        _args("gis-pin", archive, db_path, "--limit", "1")
    )
    second = ingest_fl_dor_property.execute(
        _args("gis-pin", archive, db_path, "--start-row", "1")
    )

    assert first["counts"]["rows_processed"] == 1
    assert first["next_checkpoint_row"] == 1
    assert first["exhausted"] is False
    assert second["counts"]["rows_processed"] == 3
    assert second["next_checkpoint_row"] is None
    assert second["exhausted"] is True

    db = sqlite3.connect(db_path)
    try:
        geometry = db.execute(
            """
            SELECT geometry_ref, geometry_format
            FROM parcel_geometry g
            JOIN parcel_snapshot p ON p.parcel_id=g.parcel_id
            WHERE p.native_parcel_id='000000000007005946'
            """
        ).fetchone()
        assert geometry[0].endswith("#/geometry")
        assert geometry[1] == (
            "esri_shapefile_native_feature_collection_json"
        )
    finally:
        db.close()


def test_caller_selected_checkpoint_has_no_hidden_default_ceiling(
    tmp_path: Path,
) -> None:
    archive = _nal_archive(tmp_path / "baker-nal.zip")
    db_path = tmp_path / "property.db"

    first = ingest_fl_dor_property.execute(
        _args("nal", archive, db_path, "--limit", "1")
    )
    second = ingest_fl_dor_property.execute(
        _args("nal", archive, db_path, "--start-row", "1")
    )

    assert first["counts"]["rows_processed"] == 1
    assert first["next_checkpoint_row"] == 1
    assert first["exhausted"] is False
    assert second["counts"]["rows_processed"] == 1
    assert second["next_checkpoint_row"] is None
    assert second["exhausted"] is True
    assert _counts(db_path)["parcel_snapshot"] == 2


def test_archive_identity_and_header_mismatches_fail_before_projection(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "NAL12P202601.csv",
            "CO_NO,PARCEL_ID,ASMNT_YR\n12,ABC,2026\n",
        )
    db_path = tmp_path / "property.db"

    with pytest.raises(
        ingest_fl_dor_property.FloridaDORIngestError,
        match="lacks required columns",
    ):
        ingest_fl_dor_property.execute(
            _args("nal", archive_path, db_path)
        )
    assert not db_path.exists()

    valid_archive = _nal_archive(tmp_path / "valid.zip")
    with pytest.raises(
        ingest_fl_dor_property.FloridaDORIngestError,
        match="conflicts with --county",
    ):
        ingest_fl_dor_property.execute(
            _args("nal", valid_archive, db_path, "--county", "Broward")
        )
