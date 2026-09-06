from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

from tools import query_txgio_land_parcels as txgio
from tools.public_records_bulk import ArtifactProbe, DownloadResult
from tools.public_records_http import RetryPolicy


class FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {}
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


def _collection(
    collection_id: str,
    *,
    publication_date: str,
    acquisition_date: str,
) -> dict:
    return {
        "collection_id": collection_id,
        "name": "Land Parcels",
        "publication_date": publication_date,
        "acquisition_date": acquisition_date,
        "counties": "Kenedy, King",
        "public": True,
        "authoritative": False,
        "availability": "Download",
        "file_type": "GDB,SHP",
        "spatial_reference": "4326",
        "source_name": "Various Appraisal Districts",
        "source_abbreviation": "Various Appraisal Districts",
        "license_name": "Creative Commons Zero v1.0 Universal",
        "license_abbreviation": "CC0-1.0",
        "license_url": "https://spdx.org/licenses/CC0-1.0.html",
        "resource_types": "LP",
        "s_three_key": "stratmap-2025-land-parcels",
        "supplemental_report_url": "https://example.test/report.zip",
        "popup_link": txgio.CURRENT_MAPSERVER_URL,
        "wms_link": None,
    }


def _resource(
    collection_id: str,
    *,
    resource_id: str,
    fips: str,
    county: str,
    size: int,
) -> dict:
    return {
        "resource_id": resource_id,
        "resource": (
            f"https://data.geographic.texas.gov/{collection_id}/resources/"
            f"stratmap25-landparcels_{fips}_lp.zip"
        ),
        "filesize": size,
        "area_type_id": f"area-{fips}",
        "area_type_name": county,
        "collection_id": collection_id,
        "resource_type_name": "Land Parcel",
        "resource_type_abbreviation": "LP",
        "area_type": "county",
    }


class PagingTransport:
    def __init__(self):
        self.calls = []
        self.current_id = "0fa04328-872e-481c-b453-126a74777593"
        self.old_id = "d0f7da13-ab09-4994-a16f-d52589e2476e"

    def request(self, method, url, *, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if url == txgio.COLLECTIONS_ENDPOINT:
            return FakeResponse(
                {
                    "count": 2,
                    "next": (
                        "https://api.tnris.org/api/v1/collections/?page=2"
                    ),
                    "previous": None,
                    "results": [
                        _collection(
                            self.current_id,
                            publication_date="2025-09-11",
                            acquisition_date="2025-06-01",
                        )
                    ],
                }
            )
        if url.endswith("/collections/?page=2"):
            return FakeResponse(
                {
                    "count": 2,
                    "next": None,
                    "previous": txgio.COLLECTIONS_ENDPOINT,
                    "results": [
                        _collection(
                            self.old_id,
                            publication_date="2024-09-12",
                            acquisition_date="2024-07-01",
                        )
                    ],
                }
            )
        if url == txgio.RESOURCES_ENDPOINT:
            assert params == {"collection_id": self.current_id}
            return FakeResponse(
                {
                    "count": 2,
                    "next": None,
                    "previous": None,
                    "results": [
                        _resource(
                            self.current_id,
                            resource_id="resource-king",
                            fips="48269",
                            county="King",
                            size=697553,
                        ),
                        _resource(
                            self.current_id,
                            resource_id="resource-kenedy",
                            fips="48261",
                            county="Kenedy",
                            size=334740,
                        ),
                    ],
                }
            )
        raise AssertionError(f"unexpected request: {method} {url} {params}")


def _client(transport=None):
    return txgio.TxGIODataHubClient(
        transport=transport or PagingTransport(),
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )


def _dbf_bytes(
    fields: list[tuple[str, str, int, int]],
    rows: list[dict[str, object]],
) -> bytes:
    header_length = 32 + len(fields) * 32 + 1
    record_length = 1 + sum(field[2] for field in fields)
    header = bytearray(32)
    header[0] = 0x03
    header[1:4] = bytes((125, 3, 20))
    header[4:8] = struct.pack("<I", len(rows))
    header[8:10] = struct.pack("<H", header_length)
    header[10:12] = struct.pack("<H", record_length)

    descriptors = bytearray()
    for name, field_type, length, decimals in fields:
        descriptor = bytearray(32)
        encoded_name = name.encode("ascii")
        descriptor[: len(encoded_name)] = encoded_name
        descriptor[11] = ord(field_type)
        descriptor[16] = length
        descriptor[17] = decimals
        descriptors.extend(descriptor)

    records = bytearray()
    for row in rows:
        record = bytearray(b" ")
        for name, field_type, length, decimals in fields:
            value = row.get(name)
            if value is None:
                encoded = b" " * length
            elif field_type in {"N", "F"}:
                text = (
                    f"{float(value):.{decimals}f}"
                    if decimals
                    else str(int(value))
                )
                encoded = text.rjust(length).encode("ascii")
            else:
                encoded = str(value).encode("utf-8")[:length].ljust(length)
            record.extend(encoded)
        assert len(record) == record_length
        records.extend(record)
    return bytes(header + descriptors + b"\r" + records + b"\x1a")


def _shp_header() -> bytes:
    header = bytearray(100)
    header[0:4] = struct.pack(">i", 9994)
    header[24:28] = struct.pack(">i", 50)
    header[28:32] = struct.pack("<i", 1000)
    header[32:36] = struct.pack("<i", 5)
    header[36:68] = struct.pack("<4d", -98.0, 26.5, -97.4, 27.3)
    return bytes(header)


def _artifact(
    tmp_path: Path,
    *,
    occurrence_field: str = "OBJECTID_1",
    multiple_metadata_files: bool = False,
    date_acquired: int = 20250101,
    tax_year: int | str = 2025,
    year_built: int | str | None = "1990",
) -> Path:
    fields = [
        ("Prop_ID", "C", 10, 0),
        ("GEO_ID", "C", 50, 0),
        ("OWNER_NAME", "C", 60, 0),
        ("NAME_CARE", "C", 60, 0),
        ("LEGAL_AREA", "F", 19, 4),
        ("LGL_AREA_U", "C", 8, 0),
        ("GIS_AREA", "F", 19, 4),
        ("GIS_AREA_U", "C", 8, 0),
        ("LEGAL_DESC", "C", 100, 0),
        ("STAT_LAND_", "C", 5, 0),
        ("LOC_LAND_U", "C", 5, 0),
        ("LAND_VALUE", "F", 19, 2),
        ("IMP_VALUE", "F", 19, 2),
        ("MKT_VALUE", "F", 19, 2),
        ("SITUS_ADDR", "C", 100, 0),
        ("SITUS_NUM", "C", 15, 0),
        ("SITUS_STRE", "C", 10, 0),
        ("SITUS_ST_1", "C", 60, 0),
        ("SITUS_ST_2", "C", 60, 0),
        ("SITUS_CITY", "C", 60, 0),
        ("SITUS_STAT", "C", 2, 0),
        ("SITUS_ZIP", "C", 5, 0),
        ("MAIL_ADDR", "C", 100, 0),
        ("MAIL_LINE1", "C", 60, 0),
        ("MAIL_LINE2", "C", 60, 0),
        ("MAIL_CITY", "C", 60, 0),
        ("MAIL_STAT", "C", 2, 0),
        ("MAIL_ZIP", "C", 5, 0),
        ("SOURCE", "C", 60, 0),
        ("DATE_ACQ", "N", 10, 0),
        ("FIPS", "C", 5, 0),
        ("COUNTY", "C", 60, 0),
        ("TAX_YEAR", "N", 10, 0),
        ("YEAR_BUILT", "C", 10, 0),
        (occurrence_field, "N", 10, 0),
        ("Shape_Leng", "F", 19, 8),
        ("Shape_Area", "F", 19, 8),
    ]
    common = {
        "Prop_ID": "15271",
        "GEO_ID": "131-0001-0000-01-00",
        "OWNER_NAME": "KING RANCH INC",
        "NAME_CARE": "KING RANCH INC",
        "LEGAL_AREA": 25644.0,
        "LGL_AREA_U": "Acres",
        "GIS_AREA": 25601.5,
        "GIS_AREA_U": "Acres",
        "LEGAL_DESC": "ABS 0001 J J BALLI",
        "STAT_LAND_": "A1",
        "LOC_LAND_U": "RANCH",
        "LAND_VALUE": 100000,
        "IMP_VALUE": 5000,
        "MKT_VALUE": 105000,
        "SITUS_ADDR": "1 RANCH RD, SARITA, TX 78385",
        "SITUS_NUM": "1",
        "SITUS_ST_1": "RANCH RD",
        "SITUS_CITY": "SARITA",
        "SITUS_STAT": "TX",
        "SITUS_ZIP": "78385",
        "MAIL_ADDR": "3 RIVERWAY, HOUSTON, TX 77056",
        "MAIL_LINE1": "3 RIVERWAY",
        "MAIL_CITY": "HOUSTON",
        "MAIL_STAT": "TX",
        "MAIL_ZIP": "77056",
        "SOURCE": "KENEDY APPRAISAL DISTRICT",
        "DATE_ACQ": date_acquired,
        "FIPS": "48261",
        "COUNTY": "KENEDY",
        "TAX_YEAR": tax_year,
        "YEAR_BUILT": year_built,
        "Shape_Leng": 1.2,
        "Shape_Area": 2.3,
    }
    rows = [
        {**common, occurrence_field: 438},
        {**common, occurrence_field: 439},
        {
            **common,
            "Prop_ID": "15276",
            "GEO_ID": "131-0001-0002-01-00",
            "OWNER_NAME": "SANTA FE EAST CATTLE COMPANY",
            "NAME_CARE": None,
            occurrence_field: 263,
        },
    ]
    name = "stratmap25-landparcels_48261_kenedy_202503"
    artifact = tmp_path / "stratmap25-landparcels_48261_lp.zip"
    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"fgdb/{name}.gdb/gdb", b"fixture")
        archive.writestr(f"shp/{name}.CPG", "UTF-8")
        archive.writestr(f"shp/{name}.dbf", _dbf_bytes(fields, rows))
        archive.writestr(f"shp/{name}.prj", 'GEOGCS["GCS_WGS_1984"]')
        archive.writestr(f"shp/{name}.shp", _shp_header())
        archive.writestr(f"shp/{name}.shp.xml", "<metadata/>")
        if multiple_metadata_files:
            archive.writestr(f"shp/{name}_conversion.csv.xml", "<conversion/>")
            archive.writestr(f"shp/{name}_metadata.xml", "<metadata/>")
        archive.writestr(f"shp/{name}.shx", b"fixture")
    return artifact


def _args(*argv: str):
    return txgio.build_parser().parse_args(list(argv))


class FakeBulkClient:
    def __init__(self, *, size=334740):
        self.size = size
        self.probe_calls = []
        self.download_calls = []

    def probe(self, artifact, *, sample_bytes):
        self.probe_calls.append((artifact, sample_bytes))
        return ArtifactProbe(
            url=artifact.url,
            http_status=206,
            content_length=self.size,
            media_type="application/zip",
            etag='"fixture"',
            last_modified="Thu, 11 Sep 2025 00:00:00 GMT",
            accept_ranges=True,
            source_sha256=None,
            sample_size=sample_bytes,
            sample_sha256="1" * 64,
            signature_hex="504b0304",
            format_hint="zip",
        )

    def download(self, artifact, destination, *, resume, max_bytes):
        self.download_calls.append((artifact, destination, resume, max_bytes))
        return DownloadResult(
            path=str(destination),
            url=artifact.url,
            size=self.size,
            sha256="2" * 64,
            expected_sha256=artifact.expected_sha256,
            etag='"fixture"',
            last_modified="Thu, 11 Sep 2025 00:00:00 GMT",
            resumed_from=0,
            reused_existing=False,
        )


def test_client_exhausts_collection_pagination_and_sorts_latest_first():
    transport = PagingTransport()
    releases = _client(transport).releases()

    assert [record["publication_date"] for record in releases] == [
        "2025-09-11",
        "2024-09-12",
    ]
    assert transport.calls[0]["params"] == {"search": "land parcels"}
    assert transport.calls[1]["params"] == {}


def test_resources_preserve_all_counties_sizes_and_native_ids():
    transport = PagingTransport()
    resources = _client(transport).resources(transport.current_id)

    assert [record["county_fips"] for record in resources] == ["48261", "48269"]
    assert [record["expected_size"] for record in resources] == [334740, 697553]
    assert resources[0]["resource_id"] == "resource-kenedy"


def test_statewide_aggregate_is_distinct_from_county_resources():
    collection_id = "0fa04328-872e-481c-b453-126a74777593"
    record = txgio._resource_record(
        {
            "resource_id": "resource-state",
            "resource": (
                f"https://data.geographic.texas.gov/{collection_id}/resources/"
                "stratmap25-landparcels_48_lp.zip"
            ),
            "filesize": 2770387484,
            "area_type_id": "area-48",
            "area_type_name": "Texas",
            "collection_id": collection_id,
            "resource_type_name": "Land Parcel",
            "resource_type_abbreviation": "LP",
            "area_type": "state",
        },
        collection_id,
    )

    assert record["scope"] == "state"
    assert record["jurisdiction_fips"] == "48"
    assert record["county_fips"] is None


def test_manifest_selects_latest_release_and_one_county():
    transport = PagingTransport()
    result = txgio.execute(
        _args("manifest", "--county", "Kenedy"),
        access_contract={"allowed": True},
        client=_client(transport),
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["collection"]["collection_id"] == transport.current_id
    artifacts = record["manifest"]["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["metadata"]["county_fips"] == "48261"
    assert record["manifest"]["release"]["coverage"]["county_count"] == 1


def test_manifest_without_county_keeps_every_resource():
    transport = PagingTransport()
    result = txgio.execute(
        _args("manifest"),
        access_contract={"allowed": True},
        client=_client(transport),
        log_results=False,
    )

    assert len(result.records[0]["manifest"]["artifacts"]) == 2
    assert result.records[0]["manifest"]["release"]["coverage"][
        "county_fips"
    ] == ("48261", "48269")


def test_probe_uses_exact_county_artifact_and_validates_size():
    transport = PagingTransport()
    bulk = FakeBulkClient()
    result = txgio.execute(
        _args("probe", "--county", "48261", "--sample-bytes", "128"),
        access_contract={"allowed": True},
        client=_client(transport),
        bulk_client=bulk,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert bulk.probe_calls[0][1] == 128
    assert bulk.probe_calls[0][0].filename.endswith("_48261_lp.zip")
    assert result.records[0]["probe"]["format_hint"] == "zip"


def test_probe_reports_api_and_artifact_size_drift():
    transport = PagingTransport()
    result = txgio.execute(
        _args("probe", "--county", "Kenedy"),
        access_contract={"allowed": True},
        client=_client(transport),
        bulk_client=FakeBulkClient(size=334741),
        log_results=False,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "txgio_artifact_size_changed"


def test_transfer_client_uses_publisher_bulk_downloader_user_agent():
    client = txgio._bulk_client(_args("probe", "--county", "Kenedy"))

    assert client.user_agent == txgio.DOWNLOAD_USER_AGENT


def test_county_selector_accepts_terminal_county_label():
    resources = [
        {
            "county_name": "Kenedy",
            "area_name": "Kenedy",
            "jurisdiction_fips": "48261",
        }
    ]

    assert txgio._select_resources(resources, "Kenedy County") == resources


def test_inspection_maps_published_schema_and_accepts_additive_fields(tmp_path):
    inspection = txgio.inspect_local_dataset(_artifact(tmp_path))

    assert inspection.dbf.record_count == 3
    assert inspection.shapefile["shape_type_role"] == "polygon"
    assert inspection.compatibility["search_ready"] is True
    assert inspection.compatibility["logical_to_physical"]["PROP_ID"] == "Prop_ID"
    assert inspection.compatibility["logical_to_physical"]["LGL_AREA_UNIT"] == (
        "LGL_AREA_U"
    )
    assert inspection.compatibility["additional_snapshot_fields"] == [
        "OBJECTID_1",
        "Shape_Leng",
        "Shape_Area",
    ]
    assert inspection.compatibility["feature_identity"][
        "feature_occurrence_field"
    ] == "OBJECTID_1"


def test_inspection_selects_shapefile_sidecar_among_multiple_xml_files(tmp_path):
    inspection = txgio.inspect_local_dataset(
        _artifact(tmp_path, multiple_metadata_files=True)
    )

    assert inspection.metadata_member.endswith(".shp.xml")
    assert len(inspection.supporting_metadata_members) == 2
    assert all(
        not member.endswith(".shp.xml")
        for member in inspection.supporting_metadata_members
    )


def test_inspection_accepts_valid_zip_with_extensionless_destination(tmp_path):
    artifact = _artifact(tmp_path)
    extensionless = tmp_path / "downloaded-artifact"
    artifact.rename(extensionless)

    inspection = txgio.inspect_local_dataset(extensionless)

    assert inspection.path == str(extensionless.resolve())
    assert inspection.dbf.record_count == 3


def test_inspection_and_records_use_historical_objectid_field(tmp_path):
    artifact = _artifact(tmp_path, occurrence_field="OBJECTID")
    inspection = txgio.inspect_local_dataset(artifact)
    records, _, _ = txgio.search_local_dataset(
        artifact,
        "KING",
        field="owner",
        limit=1,
    )

    assert inspection.compatibility["feature_identity"][
        "feature_occurrence_field"
    ] == "OBJECTID"
    assert records[0]["feature_occurrence"]["native_object_id"] == "438"


def test_owner_search_preserves_repeated_features_without_duplicate_parcel_claim(
    tmp_path,
):
    records, cursor, inspection = txgio.search_local_dataset(
        _artifact(tmp_path),
        "KING RANCH",
        field="owner",
    )

    assert cursor is None
    assert len(records) == 2
    assert records[0]["canonical_ref"] == records[1]["canonical_ref"]
    assert records[0]["feature_ref"] != records[1]["feature_ref"]
    assert records[0]["parcel_join_key"]["uniqueness_in_artifact"] == (
        "not_assumed"
    )
    assert records[0]["assessment"]["market_value"] == 105000.0
    assert records[0]["date_acquired"] == "2025-01-01"
    assert records[0]["date_acquired_precision"] == "day"
    assert records[0]["geometry_available"]["dbf_record_index"] == 0
    assert records[0]["artifact_snapshot"]["sha256"] == (
        inspection.artifact_sha256
    )


def test_cross_release_dates_and_year_types_are_normalized(tmp_path):
    artifact = _artifact(
        tmp_path,
        date_acquired=202304,
        tax_year="2023",
        year_built=0,
    )

    records, _, _ = txgio.search_local_dataset(
        artifact,
        "KING",
        field="owner",
        limit=1,
    )

    assert records[0]["date_acquired"] == "2023-04"
    assert records[0]["date_acquired_precision"] == "month"
    assert records[0]["assessment"]["tax_year"] == 2023
    assert records[0]["year_built"] is None


def test_local_search_cursor_is_bound_to_query_and_artifact(tmp_path):
    artifact = _artifact(tmp_path)
    first, cursor, _ = txgio.search_local_dataset(
        artifact,
        "KING",
        field="owner",
        limit=1,
    )
    second, next_cursor, _ = txgio.search_local_dataset(
        artifact,
        "KING",
        field="owner",
        limit=1,
        cursor=cursor,
    )

    assert first[0]["feature_occurrence"]["native_object_id"] == "438"
    assert second[0]["feature_occurrence"]["native_object_id"] == "439"
    assert next_cursor is None

    result = txgio.execute(
        _args(
            "search",
            str(artifact),
            "SANTA",
            "--field",
            "owner",
            "--limit",
            "1",
            "--cursor",
            cursor,
        ),
        log_results=False,
    )
    assert result.status.value == "unavailable"
    assert result.errors[0].code == "txgio_cursor_query_changed"


def test_dbf_cursor_resumes_with_a_direct_record_seek(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)
    _, cursor, _ = txgio.search_local_dataset(
        artifact,
        "KING",
        field="owner",
        limit=1,
    )
    observed = {}
    original = txgio._dbf_rows

    def recording_rows(stream, schema, *, start_row=0):
        observed["start_row"] = start_row
        yield from original(stream, schema, start_row=start_row)

    monkeypatch.setattr(txgio, "_dbf_rows", recording_rows)

    txgio.search_local_dataset(
        artifact,
        "KING",
        field="owner",
        limit=1,
        cursor=cursor,
    )

    assert observed["start_row"] == 1


def test_exact_parcel_search_ignores_identifier_punctuation(tmp_path):
    records, cursor, _ = txgio.search_local_dataset(
        _artifact(tmp_path),
        "131000100000100",
        field="parcel",
        match="exact",
    )

    assert cursor is None
    assert len(records) == 2
    assert records[0]["parcel_identifiers"]["geo_id"] == "131-0001-0000-01-00"


def test_parcel_search_rejects_query_that_normalizes_to_empty(tmp_path):
    result = txgio.execute(
        _args(
            "search",
            str(_artifact(tmp_path)),
            "...",
            "--field",
            "parcel",
        ),
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "txgio_query_empty"


def test_sources_and_alternatives_are_network_free():
    sources = txgio.execute(_args("sources"), log_results=False)
    alternatives = txgio.execute(_args("alternatives"), log_results=False)

    assert sources.records[0]["declared_schema"]["native_identity_fields"] == (
        "FIPS",
        "PROP_ID",
        "GEO_ID",
    )
    assert alternatives.records[0]["integration"] == "implemented"
    assert alternatives.records[1]["url"] == txgio.APPRAISAL_DIRECTORY_URL


def test_download_passes_resume_and_max_bytes_to_transfer():
    transport = PagingTransport()
    bulk = FakeBulkClient()
    result = txgio.execute(
        _args(
            "download",
            "--county",
            "48261",
            "--destination",
            "/tmp/txgio-fixture.zip",
            "--max-download-bytes",
            "400000",
        ),
        access_contract={"allowed": True},
        client=_client(transport),
        bulk_client=bulk,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert bulk.download_calls[0][2:] == (True, 400000)
    assert result.raw_artifact_refs == ("/tmp/txgio-fixture.zip",)
