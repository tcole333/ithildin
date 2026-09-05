from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path

import pytest

from tools.public_records_shapefile import (
    ParcelShapefileError,
    inspect_shapefile_dataset,
    iter_shapefile_features,
    search_shapefile_dataset,
)


BAKER_MEMBER_STEM = "baker_2026pin"
BAKER_SOURCE_ID = "us-fl-dor-property-roll"
BAKER_RELEASE_ID = "gis-pin:2026F:12:gis-pin"
BAKER_CRS = (
    'PROJCS["NAD_1983_2011_StatePlane_Florida_North",'
    'AUTHORITY["EPSG","6441"]]'
)


def _dbf_bytes(
    rows: list[tuple[bool, str, str]],
    *,
    parcel_field: str = "PARCELNO",
) -> bytes:
    fields = (
        (parcel_field, "C", 26, 0),
        ("LABEL", "C", 24, 0),
    )
    record_length = 1 + sum(field[2] for field in fields)
    header_length = 32 + 32 * len(fields) + 1
    header = bytearray(32)
    header[0] = 0x03
    header[1:4] = bytes((126, 7, 30))
    struct.pack_into("<I", header, 4, len(rows))
    struct.pack_into("<H", header, 8, header_length)
    struct.pack_into("<H", header, 10, record_length)
    header[29] = 0x03
    descriptors = bytearray()
    for name, field_type, length, decimals in fields:
        descriptor = bytearray(32)
        descriptor[: len(name)] = name.encode("ascii")
        descriptor[11] = ord(field_type)
        descriptor[16] = length
        descriptor[17] = decimals
        descriptors.extend(descriptor)
    records = bytearray()
    for deleted, parcel, label in rows:
        records.extend(b"*" if deleted else b" ")
        records.extend(parcel.encode("utf-8").ljust(26, b" "))
        records.extend(label.encode("utf-8").ljust(24, b" "))
    return (
        bytes(header)
        + bytes(descriptors)
        + b"\r"
        + bytes(records)
        + b"\x1a"
    )


def _polygon_content(parts: list[list[tuple[float, float]]]) -> bytes:
    points = [point for part in parts for point in part]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    offsets = []
    offset = 0
    for part in parts:
        offsets.append(offset)
        offset += len(part)
    output = io.BytesIO()
    output.write(struct.pack("<i", 5))
    output.write(struct.pack("<4d", min(xs), min(ys), max(xs), max(ys)))
    output.write(struct.pack("<2i", len(parts), len(points)))
    output.write(struct.pack(f"<{len(offsets)}i", *offsets))
    for x, y in points:
        output.write(struct.pack("<2d", x, y))
    return output.getvalue()


def _polygon_z_content(
    parts: list[list[tuple[float, float, float, float | None]]],
) -> bytes:
    points = [point for part in parts for point in part]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    measures = [
        point[3] if point[3] is not None else -1.0e39
        for point in points
    ]
    offsets = []
    offset = 0
    for part in parts:
        offsets.append(offset)
        offset += len(part)
    output = io.BytesIO()
    output.write(struct.pack("<i", 15))
    output.write(struct.pack("<4d", min(xs), min(ys), max(xs), max(ys)))
    output.write(struct.pack("<2i", len(parts), len(points)))
    output.write(struct.pack(f"<{len(offsets)}i", *offsets))
    for x, y, _z, _measure in points:
        output.write(struct.pack("<2d", x, y))
    output.write(struct.pack("<2d", min(zs), max(zs)))
    output.write(struct.pack(f"<{len(zs)}d", *zs))
    published_measures = [
        value for value in measures if value >= -1.0e38
    ]
    output.write(
        struct.pack(
            "<2d",
            min(published_measures),
            max(published_measures),
        )
    )
    output.write(struct.pack(f"<{len(measures)}d", *measures))
    return output.getvalue()


def _null_content() -> bytes:
    return struct.pack("<i", 0)


def _shape_header(
    *,
    file_length_bytes: int,
    shape_type: int = 5,
) -> bytes:
    header = bytearray(100)
    struct.pack_into(">i", header, 0, 9994)
    struct.pack_into(">i", header, 24, file_length_bytes // 2)
    struct.pack_into("<i", header, 28, 1000)
    struct.pack_into("<i", header, 32, shape_type)
    struct.pack_into("<4d", header, 36, 0.0, 0.0, 30.0, 30.0)
    struct.pack_into("<4d", header, 68, 0.0, 0.0, 0.0, 0.0)
    return bytes(header)


def _shp_and_shx(
    contents: list[bytes],
    *,
    shape_type: int = 5,
) -> tuple[bytes, bytes]:
    shp_size = 100 + sum(8 + len(content) for content in contents)
    shp = io.BytesIO()
    shp.write(
        _shape_header(
            file_length_bytes=shp_size,
            shape_type=shape_type,
        )
    )
    shx = io.BytesIO()
    shx_size = 100 + 8 * len(contents)
    shx.write(
        _shape_header(
            file_length_bytes=shx_size,
            shape_type=shape_type,
        )
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


def _baker_archive(path: Path) -> Path:
    square_a = [
        (0.0, 0.0),
        (0.0, 2.0),
        (2.0, 2.0),
        (2.0, 0.0),
        (0.0, 0.0),
    ]
    square_b = [
        (10.0, 10.0),
        (10.0, 12.0),
        (12.0, 12.0),
        (12.0, 10.0),
        (10.0, 10.0),
    ]
    square_c = [
        (20.0, 20.0),
        (20.0, 21.0),
        (21.0, 21.0),
        (21.0, 20.0),
        (20.0, 20.0),
    ]
    contents = [
        _polygon_content([square_a, square_b]),
        _polygon_content([square_c]),
        _null_content(),
        _polygon_content([square_b]),
    ]
    shp, shx = _shp_and_shx(contents)
    dbf = _dbf_bytes(
        [
            (False, "000000000007005946", "multipart"),
            (False, "000000000007005946", "repeated parcel"),
            (False, "", "blank parcel key"),
            (True, "011S20000000000032", "deleted source row"),
        ]
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{BAKER_MEMBER_STEM}.shp", shp)
        archive.writestr(f"{BAKER_MEMBER_STEM}.shx", shx)
        archive.writestr(f"{BAKER_MEMBER_STEM}.dbf", dbf)
        archive.writestr(f"{BAKER_MEMBER_STEM}.prj", BAKER_CRS)
        archive.writestr(f"{BAKER_MEMBER_STEM}.cpg", "UTF-8")
    return path


def test_inspection_preserves_release_member_schema_and_crs_identity(
    tmp_path: Path,
) -> None:
    archive = _baker_archive(tmp_path / "baker_2026pin.shp.zip")

    inspection = inspect_shapefile_dataset(
        archive,
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
        parcel_fields=["PARCELNO"],
    )

    assert inspection.source_id == BAKER_SOURCE_ID
    assert inspection.release_id == BAKER_RELEASE_ID
    assert inspection.release_identity_state == "caller_supplied"
    assert inspection.members.shp == f"{BAKER_MEMBER_STEM}.shp"
    assert inspection.feature_count == 4
    assert inspection.alignment_state == "shp_shx_dbf_counts_aligned"
    assert inspection.parcel_join_fields == ("PARCELNO",)
    assert len(inspection.artifact_sha256) == 64
    assert len(inspection.member_identity_sha256) == 64
    assert len(inspection.schema_fingerprint) == 64
    assert inspection.crs.wkt == BAKER_CRS
    assert inspection.crs.byte_sha256 is not None
    assert inspection.crs.authority_candidates == ("EPSG:6441",)
    assert inspection.crs.to_dict()["transformed"] is False


def test_stream_retains_multipart_repeated_blank_and_deleted_occurrences(
    tmp_path: Path,
) -> None:
    archive = _baker_archive(tmp_path / "baker_2026pin.shp.zip")

    records = list(
        iter_shapefile_features(
            archive,
            source_id=BAKER_SOURCE_ID,
            release_id=BAKER_RELEASE_ID,
            parcel_fields=["PARCELNO"],
        )
    )

    assert len(records) == 4
    assert [record["feature_occurrence"]["feature_ordinal"] for record in records] == [
        0,
        1,
        2,
        3,
    ]
    assert len(
        {
            record["feature_occurrence"]["occurrence_id"]
            for record in records
        }
    ) == 4
    assert records[0]["source_lineage"]["release_id"] == BAKER_RELEASE_ID
    assert records[0]["source_lineage"]["members"]["shp"] == (
        f"{BAKER_MEMBER_STEM}.shp"
    )
    assert len(records[0]["source_lineage"]["artifact_sha256"]) == 64
    assert records[0]["geometry"]["multipart"] is True
    assert len(records[0]["geometry"]["parts"]) == 2
    assert records[0]["geometry"]["parts"][0]["coordinates_native"][0] == [
        0.0,
        0.0,
    ]
    assert records[0]["parcel_join"]["selected"]["value"] == (
        "000000000007005946"
    )
    assert records[1]["parcel_join"]["selected"]["value"] == (
        "000000000007005946"
    )
    assert (
        records[0]["feature_occurrence"]["occurrence_id"]
        != records[1]["feature_occurrence"]["occurrence_id"]
    )
    assert records[2]["parcel_join"]["state"] == "source_join_key_blank"
    assert records[2]["parcel_join"]["candidates"] == [
        {
            "field": "PARCELNO",
            "raw_value": None,
            "value": None,
            "state": "blank_in_source",
        }
    ]
    assert records[2]["geometry"] is None
    assert records[2]["geometry_state"] == "null_shape"
    assert records[3]["dbf_record"]["deleted"] is True


def test_search_cursor_resumes_at_repeated_parcel_occurrence(
    tmp_path: Path,
) -> None:
    archive = _baker_archive(tmp_path / "baker_2026pin.shp.zip")
    first = search_shapefile_dataset(
        archive,
        "000000000007005946",
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
        parcel_fields=["PARCELNO"],
        fields=["PARCELNO"],
        match="exact",
        limit=1,
        scan_limit=10,
    )

    assert len(first.records) == 1
    assert first.records[0]["feature_occurrence"]["feature_ordinal"] == 0
    assert first.next_cursor is not None
    assert first.stop_reason == "result_limit"

    second = search_shapefile_dataset(
        archive,
        "000000000007005946",
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
        parcel_fields=["PARCELNO"],
        fields=["PARCELNO"],
        match="exact",
        limit=10,
        scan_limit=10,
        cursor=first.next_cursor,
    )

    assert len(second.records) == 1
    assert second.records[0]["feature_occurrence"]["feature_ordinal"] == 1
    assert second.next_cursor is None
    assert second.exhausted is True


def test_cursor_is_bound_to_artifact_member_schema_and_query(
    tmp_path: Path,
) -> None:
    archive = _baker_archive(tmp_path / "baker_2026pin.shp.zip")
    first = search_shapefile_dataset(
        archive,
        "000000000007005946",
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
        fields=["PARCELNO"],
        limit=1,
    )
    assert first.next_cursor is not None

    with pytest.raises(ParcelShapefileError) as changed_query:
        search_shapefile_dataset(
            archive,
            "011S20000000000032",
            source_id=BAKER_SOURCE_ID,
            release_id=BAKER_RELEASE_ID,
            fields=["PARCELNO"],
            limit=1,
            cursor=first.next_cursor,
        )

    assert changed_query.value.code == "shapefile_cursor_context_changed"

    changed_archive = _baker_archive(tmp_path / "baker_changed.zip")
    with zipfile.ZipFile(changed_archive, "a") as output:
        output.writestr("release-note.txt", "different archive occurrence")
    with pytest.raises(ParcelShapefileError) as changed_artifact:
        search_shapefile_dataset(
            changed_archive,
            "000000000007005946",
            source_id=BAKER_SOURCE_ID,
            release_id=BAKER_RELEASE_ID,
            fields=["PARCELNO"],
            limit=1,
            cursor=first.next_cursor,
        )

    assert changed_artifact.value.code == "shapefile_cursor_context_changed"


def test_scan_limit_returns_resumable_feature_boundary(
    tmp_path: Path,
) -> None:
    archive = _baker_archive(tmp_path / "baker_2026pin.shp.zip")
    first = search_shapefile_dataset(
        archive,
        "does not occur",
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
        fields=["LABEL"],
        limit=10,
        scan_limit=2,
    )

    assert first.records == ()
    assert first.scanned_count == 2
    assert first.stop_reason == "scan_limit"
    assert first.next_cursor is not None

    second = search_shapefile_dataset(
        archive,
        "does not occur",
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
        fields=["LABEL"],
        limit=10,
        scan_limit=2,
        cursor=first.next_cursor,
    )

    assert second.records == ()
    assert second.start_feature_ordinal == 2
    assert second.scanned_count == 2
    assert second.exhausted is True


def test_direct_sidecar_set_uses_composite_artifact_identity(
    tmp_path: Path,
) -> None:
    archive = _baker_archive(tmp_path / "baker_2026pin.shp.zip")
    with zipfile.ZipFile(archive) as source:
        for member in source.namelist():
            (tmp_path / member).write_bytes(source.read(member))

    inspection = inspect_shapefile_dataset(
        tmp_path / f"{BAKER_MEMBER_STEM}.shp",
        source_id=BAKER_SOURCE_ID,
        release_id=BAKER_RELEASE_ID,
    )

    assert inspection.container == "sidecar_set"
    assert inspection.artifact_identity_kind == "sidecar_set_manifest_sha256"
    assert inspection.feature_count == 4


def test_multipart_polygon_z_preserves_z_and_measure_arrays(
    tmp_path: Path,
) -> None:
    first = [
        (0.0, 0.0, 5.0, 100.0),
        (0.0, 1.0, 6.0, None),
        (1.0, 1.0, 7.0, 102.0),
        (0.0, 0.0, 5.0, 100.0),
    ]
    second = [
        (2.0, 2.0, 8.0, 200.0),
        (2.0, 3.0, 9.0, 201.0),
        (3.0, 3.0, 10.0, 202.0),
        (2.0, 2.0, 8.0, 200.0),
    ]
    shp, shx = _shp_and_shx(
        [_polygon_z_content([first, second])],
        shape_type=15,
    )
    archive = tmp_path / "polygon-z.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("parcel.shp", shp)
        output.writestr("parcel.shx", shx)
        output.writestr(
            "parcel.dbf",
            _dbf_bytes([(False, "P-Z", "polygon z")]),
        )
        output.writestr("parcel.prj", 'GEOGCS["Example native CRS"]')

    record = next(iter_shapefile_features(archive))
    geometry = record["geometry"]

    assert geometry["shape_type_name"] == "PolygonZ"
    assert geometry["coordinate_dimensions"] == ["x", "y", "z"]
    assert geometry["multipart"] is True
    assert len(geometry["parts"]) == 2
    assert geometry["parts"][0]["coordinates_native"][1] == [0.0, 1.0, 6.0]
    assert geometry["parts"][0]["measures"][1] is None
    assert geometry["parts"][1]["measures"][2] == 202.0


def test_shx_and_dbf_count_mismatch_is_not_silently_aligned(
    tmp_path: Path,
) -> None:
    contents = [_null_content(), _null_content()]
    shp, shx = _shp_and_shx(contents)
    archive = tmp_path / "mismatch.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("parcel.shp", shp)
        output.writestr("parcel.shx", shx)
        output.writestr(
            "parcel.dbf",
            _dbf_bytes([(False, "P-1", "one row")]),
        )

    with pytest.raises(ParcelShapefileError) as caught:
        inspect_shapefile_dataset(archive)

    assert caught.value.code == "shapefile_feature_table_count_mismatch"
