from __future__ import annotations

import base64
import json
import sqlite3
import struct
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools.public_records_filegdb import (
    CURSOR_PREFIX,
    BackendFeaturePage,
    BackendStatus,
    ExtractedFeature,
    GDALCLIBackend,
    FileGDBDependencyError,
    FileGDBError,
    _gdal_version_pair,
    _parse_geopackage_geometry,
    _read_geopackage_page,
    _validate_linear_wkb,
    inspect_filegdb_container,
    inspect_filegdb_dataset,
    read_filegdb_features,
)


SOURCE_ID = "us-tx-hcad-parcel-gis"
RELEASE_ID = "hcad-gis:2026-current:parcels"


def _filegdb_archive(
    path: Path,
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    parcel_content: bytes = b"parcel features",
) -> Path:
    with zipfile.ZipFile(path, "w", compression) as archive:
        archive.writestr("Parcels.gdb/gdb", b"\x03\x00\x00\x00")
        archive.writestr(
            "Parcels.gdb/a00000001.gdbtable",
            b"system table",
        )
        archive.writestr(
            "Parcels.gdb/a0000000d.gdbtable",
            parcel_content,
        )
        archive.writestr(
            "Parcels.gdb/a0000000d.gdbtablx",
            b"parcel index",
        )
    return path


def _metadata(
    *,
    geometry_type: str = "MultiPolygon",
) -> dict:
    return {
        "description": "fixture",
        "driverShortName": "OpenFileGDB",
        "driverLongName": "ESRI File Geodatabase",
        "layers": [
            {
                "name": "Parcels",
                "fidColumnName": "OBJECTID",
                "featureCount": 4,
                "fields": [
                    {
                        "name": "HCAD_NUM",
                        "type": "String",
                        "nullable": True,
                        "uniqueConstraint": False,
                    },
                    {
                        "name": "SITE_ADDR",
                        "type": "String",
                        "nullable": True,
                        "uniqueConstraint": False,
                    },
                ],
                "geometryFields": [
                    {
                        "name": "SHAPE",
                        "type": geometry_type,
                        "nullable": True,
                        "coordinateSystem": {
                            "wkt": 'PROJCRS["NAD83 / Texas South Central (ftUS)"]',
                            "projjson": {
                                "type": "ProjectedCRS",
                                "id": {
                                    "authority": "EPSG",
                                    "code": 2278,
                                },
                            },
                            "dataAxisToSRSAxisMapping": [1, 2],
                        },
                    }
                ],
                "metadata": {"fixture": "HCAD"},
            }
        ],
        "metadata": {},
        "domains": {},
        "relationships": {},
    }


def _geometry(x: float) -> dict:
    wkb = (
        b"\x01"
        + struct.pack("<I", 1)
        + struct.pack("<2d", x, x + 1)
    )
    return {
        "encoding": "ogc_wkb",
        "wkb_base64": base64.b64encode(wkb).decode("ascii"),
        "wkb_byte_length": len(wkb),
        "wkb_sha256": "fixture",
        "coordinates": "published_native_crs",
        "transformed": False,
    }


def _geopackage_point_blob(x: float, y: float) -> bytes:
    wkb = b"\x01" + struct.pack("<I", 1) + struct.pack("<2d", x, y)
    return (
        b"GP"
        + bytes((0, 0x03))
        + struct.pack("<i", 2278)
        + struct.pack("<4d", x, x, y, y)
        + wkb
    )


def _geopackage_blob(wkb: bytes, *, srs_id: int = 2278) -> bytes:
    return b"GP" + bytes((0, 0x01)) + struct.pack("<i", srs_id) + wkb


def _write_materialized_point_page(
    path: Path,
    *,
    geometry_blob: bytes | None,
    geometry_type: str = "POINT",
    z: int = 0,
    m: int = 0,
) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT,
                column_name TEXT,
                geometry_type_name TEXT,
                srs_id INTEGER,
                z INTEGER,
                m INTEGER
            );
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT,
                srs_id INTEGER,
                organization TEXT,
                organization_coordsys_id INTEGER,
                definition TEXT,
                description TEXT
            );
            CREATE TABLE __ithildin_filegdb_page__ (
                fid INTEGER PRIMARY KEY,
                geom BLOB,
                __ithildin_source_fid__ INTEGER,
                hcad_num TEXT,
                site_addr TEXT
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES (
                'NAD83 / Texas South Central (ftUS)',
                2278,
                'EPSG',
                2278,
                'fixture',
                'fixture'
            );
            """
        )
        connection.execute(
            """
            INSERT INTO gpkg_geometry_columns VALUES (
                '__ithildin_filegdb_page__', 'geom', ?, 2278, ?, ?
            )
            """,
            (geometry_type, z, m),
        )
        connection.execute(
            """
            INSERT INTO __ithildin_filegdb_page__
                (fid, geom, __ithildin_source_fid__, hcad_num, site_addr)
            VALUES (1, ?, 101, '1144740190749', '100 MAIN ST')
            """,
            (geometry_blob,),
        )
        connection.commit()
    finally:
        connection.close()


class FakeBackend:
    def __init__(
        self,
        features: list[ExtractedFeature] | None = None,
        *,
        metadata: dict | None = None,
    ) -> None:
        self.features = features or []
        self.metadata = metadata or _metadata()

    def status(self) -> BackendStatus:
        return BackendStatus(
            available=True,
            backend="fixture-openfilegdb",
            ogrinfo_path="/fixture/ogrinfo",
            ogr2ogr_path="/fixture/ogr2ogr",
            gdal_version="GDAL 3.12.0",
            openfilegdb_driver=True,
            reason=None,
            inspection_available=True,
            extraction_available=True,
            ogr2ogr_version="GDAL 3.12.0",
            ogr2ogr_openfilegdb_driver=True,
            gpkg_write_driver=True,
            inspection_reason=None,
            extraction_reason=None,
        )

    def inspect(self, container):
        return self.metadata

    def extract_page(
        self,
        container,
        layer,
        *,
        offset,
        limit,
        include_geometry,
    ) -> BackendFeaturePage:
        selected = []
        for feature in self.features[offset : offset + limit]:
            selected.append(
                ExtractedFeature(
                    native_fid=feature.native_fid,
                    attributes=feature.attributes,
                    geometry=(
                        feature.geometry if include_geometry else None
                    ),
                    materialized_ordinal=len(selected),
                )
            )
        return BackendFeaturePage(
            features=tuple(selected),
            requested_offset=offset,
            requested_limit=limit,
            materialized_schema={
                "fixture": True,
                "geometry_included": include_geometry,
            },
            backend=self.status().to_dict(),
        )


class MissingBackend(FakeBackend):
    def status(self) -> BackendStatus:
        return BackendStatus(
            available=False,
            backend="gdal-openfilegdb-cli",
            ogrinfo_path=None,
            ogr2ogr_path=None,
            gdal_version=None,
            openfilegdb_driver=False,
            reason="ogrinfo is required for FileGDB inspection",
            inspection_available=False,
            extraction_available=False,
            ogr2ogr_version=None,
            ogr2ogr_openfilegdb_driver=False,
            gpkg_write_driver=False,
            inspection_reason="ogrinfo is required for FileGDB inspection",
            extraction_reason=(
                "FileGDB inspection capability is unavailable: "
                "ogrinfo is required for FileGDB inspection"
            ),
        )


class MutatingInspectBackend(FakeBackend):
    def inspect(self, container):
        with zipfile.ZipFile(container.path, "a") as archive:
            archive.writestr(
                "Parcels.gdb/inspection-mutation.gdbtable",
                b"changed during inspect",
            )
        return super().inspect(container)


class MutatingExtractBackend(FakeBackend):
    def extract_page(
        self,
        container,
        layer,
        *,
        offset,
        limit,
        include_geometry,
    ) -> BackendFeaturePage:
        page = super().extract_page(
            container,
            layer,
            offset=offset,
            limit=limit,
            include_geometry=include_geometry,
        )
        with zipfile.ZipFile(container.path, "a") as archive:
            archive.writestr(
                "Parcels.gdb/extraction-mutation.gdbtable",
                b"changed during extract",
            )
        return page


class RaisingInspectBackend(FakeBackend):
    def inspect(self, container):
        raise FileGDBError(
            "fixture_backend_inspection_failed",
            "fixture inspection failure",
        )


class MutatingRaisingInspectBackend(FakeBackend):
    def inspect(self, container):
        with zipfile.ZipFile(container.path, "a") as archive:
            archive.writestr(
                "Parcels.gdb/raising-inspection-mutation.gdbtable",
                b"changed before inspection failure",
            )
        raise FileGDBError(
            "fixture_backend_inspection_failed",
            "fixture inspection failure",
        )


class RaisingExtractBackend(FakeBackend):
    def extract_page(
        self,
        container,
        layer,
        *,
        offset,
        limit,
        include_geometry,
    ) -> BackendFeaturePage:
        raise FileGDBError(
            "fixture_backend_extraction_failed",
            "fixture extraction failure",
        )


class MutatingRaisingExtractBackend(RaisingExtractBackend):
    def extract_page(
        self,
        container,
        layer,
        *,
        offset,
        limit,
        include_geometry,
    ) -> BackendFeaturePage:
        with zipfile.ZipFile(container.path, "a") as archive:
            archive.writestr(
                "Parcels.gdb/raising-extraction-mutation.gdbtable",
                b"changed before extraction failure",
            )
        return super().extract_page(
            container,
            layer,
            offset=offset,
            limit=limit,
            include_geometry=include_geometry,
        )


def _features() -> list[ExtractedFeature]:
    return [
        ExtractedFeature(
            native_fid=101,
            attributes={
                "HCAD_NUM": "1144740190749",
                "SITE_ADDR": "100 MAIN ST",
            },
            geometry=_geometry(1.0),
            materialized_ordinal=0,
        ),
        ExtractedFeature(
            native_fid=205,
            attributes={
                "HCAD_NUM": "1144740190749",
                "SITE_ADDR": "100 MAIN ST UNIT B",
            },
            geometry=_geometry(2.0),
            materialized_ordinal=1,
        ),
        ExtractedFeature(
            native_fid=309,
            attributes={"HCAD_NUM": "   ", "SITE_ADDR": "UNJOINED"},
            geometry=None,
            materialized_ordinal=2,
        ),
        ExtractedFeature(
            native_fid=411,
            attributes={"HCAD_NUM": None, "SITE_ADDR": "NULL JOIN"},
            geometry=_geometry(4.0),
            materialized_ordinal=3,
        ),
    ]


def test_container_preserves_archive_and_gdb_member_identity(tmp_path: Path):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    inspection = inspect_filegdb_container(artifact)

    assert inspection.container == "zip"
    assert inspection.gdb_member == "Parcels.gdb"
    assert inspection.available_gdb_members == ("Parcels.gdb",)
    assert inspection.gdal_datasource.endswith(
        "/Parcels.zip/Parcels.gdb"
    )
    assert len(inspection.artifact_sha256) == 64
    assert len(inspection.gdb_member_identity_sha256) == 64
    assert {
        member["path"] for member in inspection.gdb_members
    } == {
        "Parcels.gdb/gdb",
        "Parcels.gdb/a00000001.gdbtable",
        "Parcels.gdb/a0000000d.gdbtable",
        "Parcels.gdb/a0000000d.gdbtablx",
    }


def test_gdb_logical_identity_is_stable_across_zip_recompression(
    tmp_path: Path,
):
    stored = _filegdb_archive(
        tmp_path / "stored.zip",
        compression=zipfile.ZIP_STORED,
    )
    deflated = _filegdb_archive(
        tmp_path / "deflated.zip",
        compression=zipfile.ZIP_DEFLATED,
    )
    changed = _filegdb_archive(
        tmp_path / "changed.zip",
        compression=zipfile.ZIP_DEFLATED,
        parcel_content=b"different parcel features",
    )

    stored_inspection = inspect_filegdb_container(stored)
    deflated_inspection = inspect_filegdb_container(deflated)
    changed_inspection = inspect_filegdb_container(changed)

    assert stored_inspection.artifact_sha256 != (
        deflated_inspection.artifact_sha256
    )
    assert stored_inspection.gdb_member_identity_sha256 == (
        deflated_inspection.gdb_member_identity_sha256
    )
    assert stored_inspection.gdb_member_identity_sha256 != (
        changed_inspection.gdb_member_identity_sha256
    )
    assert all(
        member.get("content_sha256")
        for member in stored_inspection.gdb_members
        if member["kind"] == "file"
    )
    assert all(
        "compressed_size" in member and "crc32" in member
        for member in deflated_inspection.gdb_members
        if member["kind"] == "file"
    )


@pytest.mark.parametrize(
    "members",
    [
        [("Parcels.gdb", b"not a directory")],
        [
            ("Parcels.gdb", b"namespace collision"),
            ("Parcels.gdb/a00000001.gdbtable", b"system table"),
        ],
        [
            ("wrapper", b"ancestor collision"),
            ("wrapper/Parcels.gdb/a00000001.gdbtable", b"system table"),
        ],
    ],
)
def test_zip_gdb_root_rejects_regular_file_namespace_collisions(
    tmp_path: Path,
    members: list[tuple[str, bytes]],
):
    artifact = tmp_path / "collision.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        for member, content in members:
            archive.writestr(member, content)

    with pytest.raises(FileGDBError) as raised:
        inspect_filegdb_container(artifact)

    assert raised.value.code == "filegdb_member_namespace_collision"


def test_zip_gdb_root_requires_a_descendant_regular_member(tmp_path: Path):
    artifact = tmp_path / "empty-gdb.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("Parcels.gdb/", b"")

    with pytest.raises(FileGDBError) as raised:
        inspect_filegdb_container(artifact)

    assert raised.value.code == "filegdb_member_empty"


def test_gdal_version_contract_tracks_ogrinfo_json_capability():
    assert _gdal_version_pair("GDAL 3.12.0, released 2026/01/01") == (3, 12)
    assert _gdal_version_pair("unknown build") is None


def test_unparseable_gdal_version_is_not_assumed_supported(monkeypatch):
    backend = GDALCLIBackend(
        ogrinfo="/fixture/ogrinfo",
        ogr2ogr="/fixture/ogr2ogr",
    )

    def fake_run(command, *, operation):
        stdout = (
            "vendor build without version"
            if "--version" in command
            else "  OpenFileGDB -vector- (rov): fixture"
        )
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(backend, "_run", fake_run)
    status = backend.status()

    assert status.available is False
    assert status.openfilegdb_driver is True
    assert status.reason == "GDAL version could not be verified"


def test_ogrinfo_only_backend_can_still_inspect_filegdb(
    tmp_path: Path,
    monkeypatch,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    backend = GDALCLIBackend(ogrinfo="/fixture/ogrinfo")
    monkeypatch.setattr(
        "tools.public_records_filegdb.shutil.which",
        lambda executable: None,
    )

    def fake_run(command, *, operation):
        if "--version" in command:
            stdout = "GDAL 3.12.0"
        elif "--formats" in command:
            stdout = "  OpenFileGDB -vector- (rov): fixture"
        elif "-json" in command:
            stdout = json.dumps(_metadata())
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(backend, "_run", fake_run)

    status = backend.status()
    inspection = inspect_filegdb_dataset(
        artifact,
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        backend=backend,
    )

    assert status.inspection_available is True
    assert status.extraction_available is False
    assert status.available is False
    assert status.ogr2ogr_path is None
    assert inspection.layer("Parcels").feature_count == 4


@pytest.mark.parametrize(
    ("ogr2ogr_version", "ogr2ogr_formats", "expected_reason"),
    [
        (
            "vendor build without version",
            (
                "  OpenFileGDB -vector- (rov): fixture\n"
                "  GPKG -vector- (rw+v): fixture"
            ),
            "ogr2ogr GDAL version could not be verified",
        ),
        (
            "GDAL 3.12.0",
            "  OpenFileGDB -vector- (rov): fixture",
            "GPKG write driver is not available to ogr2ogr",
        ),
        (
            "GDAL 3.12.0",
            "  GPKG -vector- (rw+v): fixture",
            "OpenFileGDB read driver is not available to ogr2ogr",
        ),
    ],
)
def test_extraction_verifies_ogr2ogr_version_and_gpkg_write_capability(
    monkeypatch,
    ogr2ogr_version: str,
    ogr2ogr_formats: str,
    expected_reason: str,
):
    backend = GDALCLIBackend(
        ogrinfo="/fixture/ogrinfo",
        ogr2ogr="/fixture/ogr2ogr",
    )

    def fake_run(command, *, operation):
        if command[0] == "/fixture/ogrinfo":
            stdout = (
                "GDAL 3.12.0"
                if "--version" in command
                else "  OpenFileGDB -vector- (rov): fixture"
            )
        else:
            stdout = (
                ogr2ogr_version
                if "--version" in command
                else ogr2ogr_formats
            )
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(backend, "_run", fake_run)
    status = backend.status()

    assert status.inspection_available is True
    assert status.extraction_available is False
    assert status.available is False
    assert status.extraction_reason == expected_reason


def test_backend_status_accepts_verified_extraction_capabilities(monkeypatch):
    backend = GDALCLIBackend(
        ogrinfo="/fixture/ogrinfo",
        ogr2ogr="/fixture/ogr2ogr",
    )

    def fake_run(command, *, operation):
        stdout = (
            "GDAL 3.12.0"
            if "--version" in command
            else (
                "  OpenFileGDB -vector- (rov): fixture\n"
                "  GPKG -vector- (rw+v): fixture"
            )
        )
        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(backend, "_run", fake_run)
    status = backend.status()

    assert status.inspection_available is True
    assert status.extraction_available is True
    assert status.available is True
    assert status.ogr2ogr_version == "GDAL 3.12.0"
    assert status.gpkg_write_driver is True
    assert status.reason is None


def test_dataset_schema_separates_native_fid_from_parcel_join(tmp_path: Path):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    inspection = inspect_filegdb_dataset(
        artifact,
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        backend=FakeBackend(),
    )
    layer = inspection.layer("parcels")

    assert layer.fid_column_name == "OBJECTID"
    assert layer.parcel_join_fields == ("HCAD_NUM",)
    assert layer.feature_count == 4
    assert layer.geometry_fields[0]["type"] == "MultiPolygon"
    assert inspection.container.gdb_member == "Parcels.gdb"


def test_structural_identity_is_stable_across_join_interpretations(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    metadata = json.loads(json.dumps(_metadata()))
    metadata["layers"][0]["fields"].append(
        {
            "name": "PARCEL_ID",
            "type": "String",
            "nullable": True,
            "uniqueConstraint": False,
        }
    )
    feature = ExtractedFeature(
        native_fid=101,
        attributes={
            "HCAD_NUM": "1144740190749",
            "PARCEL_ID": "P-101",
            "SITE_ADDR": "100 MAIN ST",
        },
        geometry=_geometry(1.0),
        materialized_ordinal=0,
    )
    backend = FakeBackend([feature], metadata=metadata)

    first = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        parcel_fields=["HCAD_NUM", "PARCEL_ID"],
        backend=backend,
    )
    reversed_joins = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        parcel_fields=["PARCEL_ID", "HCAD_NUM"],
        backend=backend,
    )

    assert first.layer.schema_fingerprint == (
        reversed_joins.layer.schema_fingerprint
    )
    assert first.inspection.dataset_schema_fingerprint == (
        reversed_joins.inspection.dataset_schema_fingerprint
    )
    assert first.records[0]["feature_occurrence"]["occurrence_id"] == (
        reversed_joins.records[0]["feature_occurrence"]["occurrence_id"]
    )
    assert first.query_fingerprint != reversed_joins.query_fingerprint
    assert [
        item["field"]
        for item in first.records[0]["parcel_join"]["candidates"]
    ] == ["HCAD_NUM", "PARCEL_ID"]
    assert [
        item["field"]
        for item in reversed_joins.records[0]["parcel_join"]["candidates"]
    ] == ["PARCEL_ID", "HCAD_NUM"]


def test_maryland_acctid_uses_same_source_neutral_join_contract(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "February_2026_Parcels.zip")
    metadata = json.loads(json.dumps(_metadata()))
    metadata["layers"][0]["name"] = "February_2026_Parcels"
    metadata["layers"][0]["fields"][0]["name"] = "ACCTID"
    coordinate_system = metadata["layers"][0]["geometryFields"][0][
        "coordinateSystem"
    ]
    coordinate_system["wkt"] = 'PROJCRS["NAD83 / Maryland"]'
    coordinate_system["projjson"]["id"]["code"] = 26985
    metadata["layers"].append(
        {
            "name": "LandUseLookup",
            "featureCount": 2,
            "fields": [
                {
                    "name": "CODE",
                    "type": "String",
                    "nullable": False,
                    "uniqueConstraint": True,
                }
            ],
            "geometryFields": [],
        }
    )

    inspection = inspect_filegdb_dataset(
        artifact,
        source_id="us-md-mdp-parcel-downloads",
        release_id="mdp-parcels:2026-02",
        parcel_fields=["ACCTID"],
        backend=FakeBackend(metadata=metadata),
    )
    layer = inspection.layer("February_2026_Parcels")

    assert layer.parcel_join_fields == ("ACCTID",)
    assert inspection.layer("LandUseLookup").parcel_join_fields == ()
    assert layer.fid_column_name == "OBJECTID"
    assert layer.geometry_fields[0]["coordinateSystem"]["projjson"][
        "id"
    ] == {"authority": "EPSG", "code": 26985}


def test_missing_backend_is_explicit_but_container_remains_inspectable(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    assert inspect_filegdb_container(artifact).gdb_member == "Parcels.gdb"
    with pytest.raises(FileGDBDependencyError) as raised:
        inspect_filegdb_dataset(
            artifact,
            backend=MissingBackend(),
        )

    assert raised.value.code == "filegdb_backend_unavailable"
    assert raised.value.details["dependency"][
        "openfilegdb_documentation"
    ].startswith("https://gdal.org/")


def test_mutation_during_backend_inspection_is_rejected(tmp_path: Path):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    with pytest.raises(FileGDBError) as raised:
        inspect_filegdb_dataset(
            artifact,
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=MutatingInspectBackend(),
        )

    assert raised.value.code == "filegdb_artifact_changed_during_decode"
    assert raised.value.details["operation"] == "backend inspection"


def test_mutation_during_feature_extraction_is_rejected(tmp_path: Path):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    with pytest.raises(FileGDBError) as raised:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=MutatingExtractBackend(_features()),
        )

    assert raised.value.code == "filegdb_artifact_changed_during_decode"
    assert raised.value.details["operation"] == "feature page extraction"


def test_mutation_is_reinspected_when_backend_inspection_raises(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    with pytest.raises(FileGDBError) as raised:
        inspect_filegdb_dataset(
            artifact,
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=MutatingRaisingInspectBackend(),
        )

    assert raised.value.code == "filegdb_artifact_changed_during_decode"
    assert raised.value.details["operation"] == "backend inspection"


def test_mutation_is_reinspected_when_feature_extraction_raises(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    with pytest.raises(FileGDBError) as raised:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=MutatingRaisingExtractBackend(_features()),
        )

    assert raised.value.code == "filegdb_artifact_changed_during_decode"
    assert raised.value.details["operation"] == "feature page extraction"


def test_backend_failure_is_preserved_when_artifact_is_unchanged(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")

    with pytest.raises(FileGDBError) as inspection_error:
        inspect_filegdb_dataset(
            artifact,
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=RaisingInspectBackend(),
        )
    assert inspection_error.value.code == "fixture_backend_inspection_failed"

    with pytest.raises(FileGDBError) as extraction_error:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=RaisingExtractBackend(_features()),
        )
    assert extraction_error.value.code == "fixture_backend_extraction_failed"


def test_feature_pages_retain_repeated_blank_and_null_join_values(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    backend = FakeBackend(_features())

    first = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        limit=2,
        backend=backend,
    )

    assert len(first.records) == 2
    assert first.next_cursor.startswith(CURSOR_PREFIX)
    assert {
        row["feature_occurrence"]["native_fid"] for row in first.records
    } == {101, 205}
    assert len(
        {
            row["feature_occurrence"]["occurrence_id"]
            for row in first.records
        }
    ) == 2
    assert all(
        row["parcel_join"]["selected"]["value"] == "1144740190749"
        for row in first.records
    )

    second = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        limit=2,
        cursor=first.next_cursor,
        backend=backend,
    )

    assert second.next_cursor is None
    assert second.exhausted is True
    assert second.records[0]["parcel_join"]["state"] == (
        "source_join_key_blank_or_null"
    )
    assert second.records[0]["parcel_join"]["candidates"][0] == {
        "field": "HCAD_NUM",
        "raw_value": "   ",
        "value": None,
        "state": "blank_in_source",
    }
    assert second.records[1]["parcel_join"]["candidates"][0]["state"] == (
        "null_in_source"
    )


@pytest.mark.parametrize(
    ("native_fids", "expected_code"),
    [
        ([205, 101], "filegdb_native_fid_order_invalid"),
        ([101, 101], "filegdb_native_fid_duplicated"),
        (["101"], "filegdb_native_fid_invalid"),
    ],
)
def test_backend_page_requires_integer_unique_strictly_ordered_native_fids(
    tmp_path: Path,
    native_fids: list,
    expected_code: str,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    features = [
        ExtractedFeature(
            native_fid=native_fid,
            attributes={
                "HCAD_NUM": f"parcel-{index}",
                "SITE_ADDR": f"{index} TEST ST",
            },
            geometry=None,
            materialized_ordinal=index,
        )
        for index, native_fid in enumerate(native_fids)
    ]

    with pytest.raises(FileGDBError) as raised:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=FakeBackend(features),
        )

    assert raised.value.code == expected_code


def test_cursor_native_fid_boundary_rejects_cross_page_regression(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    backend = FakeBackend(_features())
    first = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        limit=1,
        backend=backend,
    )
    original = backend.features[1]
    backend.features[1] = ExtractedFeature(
        native_fid=50,
        attributes=original.attributes,
        geometry=original.geometry,
        materialized_ordinal=original.materialized_ordinal,
    )

    with pytest.raises(FileGDBError) as raised:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            limit=1,
            cursor=first.next_cursor,
            backend=backend,
        )

    assert raised.value.code == "filegdb_native_fid_order_invalid"
    assert raised.value.details["cross_page_boundary"] is True


def test_cursor_binds_release_artifact_layer_schema_and_geometry_query(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    backend = FakeBackend(_features())
    first = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        limit=1,
        backend=backend,
    )

    with pytest.raises(FileGDBError) as release_error:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id="different-release",
            limit=1,
            cursor=first.next_cursor,
            backend=backend,
        )
    assert release_error.value.code == "filegdb_cursor_context_changed"
    assert "release_id" in release_error.value.details["mismatches"]

    with pytest.raises(FileGDBError) as query_error:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            limit=1,
            cursor=first.next_cursor,
            include_geometry=False,
            backend=backend,
        )
    assert query_error.value.code == "filegdb_cursor_context_changed"
    assert "query_fingerprint" in query_error.value.details["mismatches"]

    with zipfile.ZipFile(artifact, "a") as archive:
        archive.writestr(
            "Parcels.gdb/a0000000d.spx",
            b"changed artifact",
        )
    with pytest.raises(FileGDBError) as artifact_error:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            limit=1,
            cursor=first.next_cursor,
            backend=backend,
        )
    assert artifact_error.value.code == "filegdb_cursor_context_changed"
    assert "artifact_sha256" in artifact_error.value.details["mismatches"]


def test_extended_geometry_family_is_not_claimed(tmp_path: Path):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    backend = FakeBackend(
        _features(),
        metadata=_metadata(geometry_type="CurvePolygon"),
    )

    with pytest.raises(FileGDBError) as raised:
        read_filegdb_features(
            artifact,
            layer="Parcels",
            source_id=SOURCE_ID,
            release_id=RELEASE_ID,
            backend=backend,
        )

    assert raised.value.code == "filegdb_geometry_family_unsupported"
    assert raised.value.details["geometry_type"] == "CurvePolygon"


def test_geopackage_geometry_parser_preserves_native_wkb_and_srs():
    wkb = (
        b"\x01"
        + struct.pack("<I", 1)
        + struct.pack("<2d", 3_000_000.25, 13_800_000.75)
    )
    flags = 0x03  # little endian, XY envelope
    blob = (
        b"GP"
        + bytes((0, flags))
        + struct.pack("<i", 2278)
        + struct.pack(
            "<4d",
            3_000_000.25,
            3_000_000.25,
            13_800_000.75,
            13_800_000.75,
        )
        + wkb
    )

    geometry = _parse_geopackage_geometry(blob)

    assert geometry["gpkg_header"]["srs_id"] == 2278
    assert geometry["gpkg_header"]["envelope"] == [
        3_000_000.25,
        3_000_000.25,
        13_800_000.75,
        13_800_000.75,
    ]
    assert base64.b64decode(geometry["wkb_base64"]) == wkb
    assert geometry["wkb_type_code"] == 1
    assert geometry["coordinates"] == "published_native_crs"
    assert geometry["transformed"] is False


def test_recursive_wkb_validation_accepts_iso_and_ewkb_dimensions():
    iso_point_z = (
        b"\x01"
        + struct.pack("<I", 1001)
        + struct.pack("<3d", 1.0, 2.0, 3.0)
    )
    ewkb_line_m = (
        b"\x01"
        + struct.pack("<I", 0x40000002)
        + struct.pack("<I", 2)
        + struct.pack("<6d", 1.0, 2.0, 7.0, 3.0, 4.0, 8.0)
    )
    ewkb_point_z = (
        b"\x01"
        + struct.pack("<I", 0x80000001)
        + struct.pack("<3d", 5.0, 6.0, 9.0)
    )
    collection = (
        b"\x01"
        + struct.pack("<I", 7)
        + struct.pack("<I", 3)
        + iso_point_z
        + ewkb_line_m
        + ewkb_point_z
    )

    validation = _validate_linear_wkb(collection)

    assert validation["top_level_family"] == "GeometryCollection"
    assert validation["geometry_count"] == 4
    assert validation["max_depth"] == 1
    assert validation["families"] == [
        "GeometryCollection",
        "Point",
        "LineString",
    ]
    assert validation["coordinate_dimensions"] == ["XY", "XYZ", "XYM"]


def test_geopackage_wkb_rejects_embedded_ewkb_srid():
    ewkb_point = (
        b"\x01"
        + struct.pack("<I", 0x20000001)
        + struct.pack("<I", 4326)
        + struct.pack("<2d", 1.0, 2.0)
    )

    with pytest.raises(FileGDBError) as raised:
        _parse_geopackage_geometry(_geopackage_blob(ewkb_point))

    assert raised.value.code == "filegdb_wkb_embedded_srid_unsupported"
    assert raised.value.details["embedded_srid"] == 4326


def test_generic_collection_cannot_hide_nonlinear_or_extended_wkb():
    circular_string = b"\x01" + struct.pack("<I", 8)
    collection = (
        b"\x01"
        + struct.pack("<I", 7)
        + struct.pack("<I", 1)
        + circular_string
    )
    blob = (
        b"GP"
        + bytes((0, 0x01))
        + struct.pack("<i", 2278)
        + collection
    )

    with pytest.raises(FileGDBError) as nonlinear:
        _parse_geopackage_geometry(blob)
    assert nonlinear.value.code == (
        "filegdb_wkb_geometry_family_unsupported"
    )
    assert nonlinear.value.details["base_type_code"] == 8

    point = b"\x01" + struct.pack("<I", 1) + struct.pack("<2d", 1.0, 2.0)
    extended_blob = (
        b"GP"
        + bytes((0, 0x21))
        + struct.pack("<i", 2278)
        + point
    )
    with pytest.raises(FileGDBError) as extended:
        _parse_geopackage_geometry(extended_blob)
    assert extended.value.code == (
        "filegdb_gpkg_extended_geometry_unsupported"
    )


@pytest.mark.parametrize(
    ("wkb_type", "coordinates", "z", "m", "expected_axis"),
    [
        (1001, (1.0, 2.0, 3.0), 0, 0, "Z"),
        (2001, (1.0, 2.0, 3.0), 0, 0, "M"),
        (1, (1.0, 2.0), 1, 0, "Z"),
    ],
)
def test_geopackage_column_enforces_z_and_m_constraints(
    tmp_path: Path,
    wkb_type: int,
    coordinates: tuple[float, ...],
    z: int,
    m: int,
    expected_axis: str,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    inspection = inspect_filegdb_dataset(
        artifact,
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        backend=FakeBackend(metadata=_metadata(geometry_type="Point")),
    )
    gpkg = tmp_path / "dimension-mismatch.gpkg"
    wkb = (
        b"\x01"
        + struct.pack("<I", wkb_type)
        + struct.pack(f"<{len(coordinates)}d", *coordinates)
    )
    _write_materialized_point_page(
        gpkg,
        geometry_blob=_geopackage_blob(wkb),
        z=z,
        m=m,
    )

    with pytest.raises(FileGDBError) as raised:
        _read_geopackage_page(
            gpkg,
            source_layer=inspection.layer("Parcels"),
            include_geometry=True,
        )

    assert raised.value.code == (
        "filegdb_materialized_geometry_dimension_mismatch"
    )
    assert raised.value.details["axis"] == expected_axis


def test_generic_geometry_source_rejects_extended_materialized_family(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    inspection = inspect_filegdb_dataset(
        artifact,
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        backend=FakeBackend(metadata=_metadata(geometry_type="Geometry")),
    )
    gpkg = tmp_path / "extended-schema.gpkg"
    _write_materialized_point_page(
        gpkg,
        geometry_blob=None,
        geometry_type="CURVEPOLYGON",
    )

    with pytest.raises(FileGDBError) as raised:
        _read_geopackage_page(
            gpkg,
            source_layer=inspection.layer("Parcels"),
            include_geometry=True,
        )

    assert raised.value.code == (
        "filegdb_materialized_geometry_family_unsupported"
    )
    assert raised.value.details["materialized_geometry_type"] == (
        "CURVEPOLYGON"
    )


def test_materialized_page_restores_source_fields_and_native_fids(
    tmp_path: Path,
):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    inspection = inspect_filegdb_dataset(
        artifact,
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        backend=FakeBackend(metadata=_metadata(geometry_type="Point")),
    )
    layer = inspection.layer("Parcels")
    gpkg = tmp_path / "page.gpkg"
    connection = sqlite3.connect(gpkg)
    try:
        connection.executescript(
            """
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT,
                column_name TEXT,
                geometry_type_name TEXT,
                srs_id INTEGER,
                z INTEGER,
                m INTEGER
            );
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT,
                srs_id INTEGER,
                organization TEXT,
                organization_coordsys_id INTEGER,
                definition TEXT,
                description TEXT
            );
            CREATE TABLE __ithildin_filegdb_page__ (
                fid INTEGER PRIMARY KEY,
                geom BLOB,
                __ithildin_source_fid__ INTEGER,
                hcad_num TEXT,
                site_addr TEXT
            );
            INSERT INTO gpkg_geometry_columns VALUES (
                '__ithildin_filegdb_page__',
                'geom',
                'POINT',
                2278,
                0,
                0
            );
            INSERT INTO gpkg_spatial_ref_sys VALUES (
                'NAD83 / Texas South Central (ftUS)',
                2278,
                'EPSG',
                2278,
                'fixture',
                'fixture'
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO __ithildin_filegdb_page__
                (fid, geom, __ithildin_source_fid__, hcad_num, site_addr)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    _geopackage_point_blob(1.0, 2.0),
                    101,
                    "1144740190749",
                    "100 MAIN ST",
                ),
                (
                    2,
                    _geopackage_point_blob(3.0, 4.0),
                    205,
                    "   ",
                    "UNJOINED",
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    features, schema = _read_geopackage_page(
        gpkg,
        source_layer=layer,
        include_geometry=True,
    )

    assert [feature.native_fid for feature in features] == [101, 205]
    assert features[0].attributes == {
        "HCAD_NUM": "1144740190749",
        "SITE_ADDR": "100 MAIN ST",
    }
    assert features[1].attributes["HCAD_NUM"] == "   "
    assert features[0].geometry["gpkg_header"]["srs_id"] == 2278
    assert schema["source_fid_column"] == "OBJECTID"
    assert schema["geometry_field"]["geometry_type_name"] == "POINT"


def test_cursor_is_opaque_json_bound_to_artifact(tmp_path: Path):
    artifact = _filegdb_archive(tmp_path / "Parcels.zip")
    page = read_filegdb_features(
        artifact,
        layer="Parcels",
        source_id=SOURCE_ID,
        release_id=RELEASE_ID,
        limit=1,
        backend=FakeBackend(_features()),
    )
    token = page.next_cursor.removeprefix(CURSOR_PREFIX)
    payload = json.loads(
        base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    )

    assert payload["artifact_sha256"] == (
        page.inspection.container.artifact_sha256
    )
    assert payload["gdb_member"] == "Parcels.gdb"
    assert payload["layer"] == "Parcels"
    assert payload["next_offset"] == 1
    assert payload["last_native_fid"] == 101
