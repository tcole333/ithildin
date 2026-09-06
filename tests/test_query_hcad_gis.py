from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import requests

from tools import query_hcad_gis as hcad_gis
from tools.public_records_bulk import ArtifactProbe
from tools.public_records_http import RetryPolicy


class FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {}
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


class ManifestTransport:
    def request(self, method, url, *, params=None, headers=None, timeout=None):
        assert method == "GET"
        assert params == {}
        if url == hcad_gis.LAST_UPDATE_ENDPOINT:
            return FakeResponse([{"lastUpdatedDate": "July 24, 2026"}])
        if url == hcad_gis.FILES_ENDPOINT:
            return FakeResponse(
                [
                    _artifact_row(
                        "Parcels.zip",
                        "Tax parcels",
                        "Contains parcel polygons and HCAD account number",
                    ),
                    _artifact_row(
                        "City.zip",
                        "City boundary",
                        "Contains city polygons",
                    ),
                ]
            )
        if url == hcad_gis.PUBLIC_ENDPOINT:
            return FakeResponse(
                [
                    _artifact_row(
                        "GIS_Public.zip",
                        "GIS Public",
                        "Contains all files for download",
                        subcategory="All Shapefiles",
                    )
                ]
            )
        if url == hcad_gis.PRIOR_YEAR_ENDPOINT:
            return FakeResponse(
                [
                    _artifact_row(
                        "Parcels_2025_Oct.zip",
                        "Tax parcels 2025",
                        "Parcel polygons as of October, 2025",
                        subcategory="Prior Year Shapefiles",
                    ),
                    _artifact_row(
                        "Parcels_2024_Oct.zip",
                        "Tax parcels 2024",
                        "Parcel polygons as of October, 2024",
                        subcategory="Prior Year Shapefiles",
                    ),
                ]
            )
        raise AssertionError(f"unexpected request {url}")


def _artifact_row(
    filename: str,
    label: str,
    description: str,
    *,
    subcategory: str = "Shapefiles",
) -> dict:
    return {
        "taxYear": "ALL       ",
        "category": "GIS",
        "subCategory": subcategory,
        "downloadLinkText": f"{label}\r\n",
        "description": f"{description}\r\n",
        "downloadLink": f"https://download.hcad.org/data/GIS/{filename}",
        "filename": filename,
    }


def _manifest_client():
    return hcad_gis.HCADGISManifestClient(
        transport=ManifestTransport(),
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )


def _args(*argv: str):
    return hcad_gis.build_parser().parse_args(list(argv))


class FakeBulkClient:
    def __init__(self):
        self.probe_calls = []

    def probe(self, artifact, *, sample_bytes):
        self.probe_calls.append((artifact, sample_bytes))
        return ArtifactProbe(
            url=artifact.url,
            http_status=206,
            content_length=206062595,
            media_type="application/x-zip-compressed",
            etag='"fixture"',
            last_modified="Fri, 24 Jul 2026 20:01:33 GMT",
            accept_ranges=True,
            source_sha256=None,
            sample_size=sample_bytes,
            sample_sha256="a" * 64,
            signature_hex="504b0304",
            format_hint="zip",
            headers={},
        )


def _field(name: str) -> dict:
    return {
        "name": name,
        "type": ("esriFieldTypeOID" if name == "OBJECTID" else "esriFieldTypeString"),
        "alias": name,
    }


def _feature(object_id: int, account: str, owner: str) -> dict:
    return {
        "attributes": {
            "OBJECTID": object_id,
            "LOWPARCELID": account,
            "HCAD_NUM": account,
            "acct_num": account,
            "tax_year": "2025",
            "owner_name_1": owner,
            "owner_name_2": None,
            "owner_name_3": None,
            "owner_pct_1": 1.0,
            "mail_addr_1": "7906 WOODSMAN TRL",
            "mail_addr_2": "",
            "mail_city": "HOUSTON",
            "mail_state": "TX",
            "mail_zip": "77040-2729",
            "site_str_num": 7906,
            "site_str_name": "WOODSMAN",
            "site_str_sfx": "TRL",
            "site_city": "HOUSTON",
            "site_county": "HARRIS",
            "site_zip": "77040",
            "land_value": 53962.0,
            "bld_value": 124062.0,
            "impr_value": 124062.0,
            "total_appraised_val": 178024.0,
            "total_market_val": 178024.0,
            "legal_dscr_1": "LT 749 BLK 19",
            "legal_dscr_2": "WOODLAND OAKS SEC 3",
            "GlobalID": f"{{fixture-{object_id}}}",
            "Stacked": 1,
            "new_owner_date": 763344000000,
        },
        "geometry": {
            "rings": [
                [
                    [-95.5, 29.8],
                    [-95.4, 29.8],
                    [-95.4, 29.9],
                    [-95.5, 29.8],
                ]
            ]
        },
    }


class FakeArcGISClient:
    page_size = 2

    def __init__(self):
        self.features = [
            _feature(1, "1144740190749", "HILL GERALD B"),
            _feature(2, "1144740190749", "HILL GERALD B"),
            _feature(3, "9999999999999", "ANOTHER OWNER"),
        ]
        self.metadata = {
            "id": 0,
            "name": "HCAD Parcels",
            "objectIdField": None,
            "maxRecordCount": 1000,
            "advancedQueryCapabilities": {
                "supportsOrderBy": True,
                "supportsPagination": True,
            },
            "extent": {
                "spatialReference": {
                    "wkid": 102740,
                    "latestWkid": 2278,
                }
            },
            "fields": [_field(name) for name in hcad_gis.MAP_REQUIRED_FIELDS],
        }

    def fetch_metadata(self):
        return self.metadata

    def _filtered(self, where: str):
        rows = list(self.features)
        exact = re.search(r"OBJECTID = (\d+)", where)
        if exact:
            rows = [
                row
                for row in rows
                if row["attributes"]["OBJECTID"] == int(exact.group(1))
            ]
        if "1144740190749" in where:
            rows = [
                row for row in rows if row["attributes"]["HCAD_NUM"] == "1144740190749"
            ]
        lower_bound = re.search(r"OBJECTID > (\d+)", where)
        if lower_bound:
            rows = [
                row
                for row in rows
                if row["attributes"]["OBJECTID"] > int(lower_bound.group(1))
            ]
        upper_bound = re.search(r"OBJECTID <= (\d+)", where)
        if upper_bound:
            rows = [
                row
                for row in rows
                if row["attributes"]["OBJECTID"] <= int(upper_bound.group(1))
            ]
        return rows

    def fetch_count(self, where):
        return len(self._filtered(where))

    def fetch_page(
        self,
        *,
        where,
        record_count,
        return_geometry,
        descending=False,
    ):
        rows = sorted(
            self._filtered(where),
            key=lambda row: row["attributes"]["OBJECTID"],
            reverse=descending,
        )[:record_count]
        if return_geometry:
            return tuple(rows)
        return tuple(
            {
                "attributes": row["attributes"],
            }
            for row in rows
        )


class StreamFailureResponse:
    status_code = 200
    headers = {}
    history = ()
    url = hcad_gis.MAPSERVER_LAYER_URL

    def __init__(self):
        self.closed = False

    def iter_content(self, *, chunk_size):
        assert chunk_size == 64 * 1024
        raise requests.ConnectionError("stream disconnected")
        yield b""

    def close(self):
        self.closed = True


class StreamFailureSession:
    def __init__(self):
        self.responses = []

    def request(self, method, url, **kwargs):
        assert method == "GET"
        assert url == hcad_gis.MAPSERVER_LAYER_URL
        assert kwargs["stream"] is True
        response = StreamFailureResponse()
        self.responses.append(response)
        return response


def test_manifest_client_discovers_current_and_historical_releases():
    client = _manifest_client()
    releases, by_release = hcad_gis.release_inventory(client)

    assert releases[0]["release_id"] == "current:2026-07-24"
    assert releases[0]["component_artifact_count"] == 2
    assert releases[0]["combined_bundle_count"] == 1
    assert [release.get("snapshot_year") for release in releases[1:]] == [
        2025,
        2024,
    ]
    assert len(by_release["current:2026-07-24"]) == 3
    assert by_release["parcels:2025-10"][0]["date_precision"] == "month"


def test_manifest_keeps_component_and_combined_artifact_roles_separate():
    releases, by_release = hcad_gis.release_inventory(_manifest_client())
    record = hcad_gis.normalize_manifest(
        releases[0],
        by_release["current:2026-07-24"],
    )

    artifacts = record["manifest"]["artifacts"]
    assert len(artifacts) == 3
    assert {artifact["metadata"]["artifact_role"] for artifact in artifacts} == {
        "current_component",
        "current_combined_bundle",
    }
    assert (
        record["manifest"]["metadata"]["combined_bundle_is_acquisition_redundancy"]
        is True
    )


def test_probe_defaults_to_current_parcels_not_combined_bundle():
    bulk = FakeBulkClient()
    result = hcad_gis.execute(
        _args("probe"),
        access_contract={"allowed": True},
        manifest_client=_manifest_client(),
        bulk_client=bulk,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0]["selected_artifact"]["filename"] == "Parcels.zip"
    assert bulk.probe_calls[0][0].filename == "Parcels.zip"


def test_historical_manifest_selects_one_october_snapshot():
    result = hcad_gis.execute(
        _args("manifest", "--year", "2024"),
        access_contract={"allowed": True},
        manifest_client=_manifest_client(),
        log_results=False,
    )

    assert result.status.value == "ok"
    manifest = result.records[0]["manifest"]
    assert manifest["release"]["release_id"] == "parcels:2024-10"
    assert manifest["artifacts"][0]["filename"] == "Parcels_2024_Oct.zip"


def test_account_cursor_preserves_duplicate_features_and_snapshot_boundary():
    client = FakeArcGISClient()
    first = hcad_gis.execute(
        _args("account", "114-474-019-0749", "--limit", "1"),
        access_contract={"allowed": True},
        arcgis_client=client,
        log_results=False,
    )
    second = hcad_gis.execute(
        _args(
            "account",
            "114-474-019-0749",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        access_contract={"allowed": True},
        arcgis_client=client,
        log_results=False,
    )

    assert first.status.value == "ok"
    assert first.next_cursor.startswith("hcad-parcels-arcgis:v1:")
    assert second.next_cursor is None
    assert first.records[0]["canonical_ref"] == second.records[0]["canonical_ref"]
    assert first.records[0]["feature_ref"] != second.records[0]["feature_ref"]
    assert first.records[0]["assessment"]["tax_year"] == 2025
    assert first.records[0]["new_owner_date"] == "1994-03-11"
    assert first.records[0]["retrieval"]["boundary_object_id"] == 2


def test_objectid_geometry_query_normalizes_feature():
    result = hcad_gis.execute(
        _args("objectid", "1", "--geometry"),
        access_contract={"allowed": True},
        arcgis_client=FakeArcGISClient(),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0]["feature_occurrence"]["object_id"] == 1
    assert result.records[0]["geometry_crs"] == "EPSG:4326"
    assert result.records[0]["situs_address"]["raw"].startswith("7906 WOODSMAN TRL")


def test_fallback_join_field_tracks_the_identifier_that_was_selected():
    feature = _feature(4, "fallback-id", "FALLBACK OWNER")
    feature["attributes"]["HCAD_NUM"] = " "
    feature["attributes"]["acct_num"] = None

    record = hcad_gis._normalize_feature(
        feature,
        schema_fingerprint="a" * 64,
    )

    assert record["native_parcel_id"] == "fallback-id"
    assert record["parcel_join_key"] == {
        "county_geoid": hcad_gis.COUNTY_GEOID,
        "field": "LOWPARCELID",
        "value": "fallback-id",
        "uniqueness_in_layer": "not_assumed",
    }


def test_stream_disconnect_is_retried_and_returned_in_result_envelope():
    session = StreamFailureSession()
    client = hcad_gis.arcgis_keyset.BoundedArcGISClient(
        hcad_gis.MAP_MANIFEST,
        session=session,
        minimum_interval=0,
        retry_attempts=2,
        sleeper=lambda _delay: None,
    )

    result = hcad_gis.execute(
        _args("objectid", "1"),
        access_contract={"allowed": True},
        arcgis_client=client,
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "transport_error"
    assert result.errors[0].details["bytes_read"] == 0
    assert len(session.responses) == 2
    assert all(response.closed for response in session.responses)


def test_metadata_contract_accepts_oid_field_declared_only_in_fields():
    schema, maximum = hcad_gis.arcgis_keyset.metadata_contract(
        hcad_gis.MAP_MANIFEST,
        FakeArcGISClient().metadata,
    )

    assert len(schema) == 64
    assert maximum == 1000


def test_multi_term_address_query_requires_each_term():
    where = hcad_gis._where(
        "address",
        "7906 WOODSMAN",
        "contains",
    )

    assert "site_str_num = 7906" in where
    assert ") AND (" in where
    assert "WOODSMAN" in where


def test_inspect_recognizes_file_geodatabase_without_filename_suffix(
    tmp_path: Path,
):
    artifact = tmp_path / "downloaded-hcad-artifact"
    with zipfile.ZipFile(
        artifact,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("Parcels.gdb/gdb", b"\x03\x00\x00\x00")
        archive.writestr(
            "Parcels.gdb/a0000000d.gdbtable",
            b"fixture",
        )

    inspection = hcad_gis.inspect_local_artifact(artifact)

    assert inspection["representation"] == "file_geodatabase"
    assert inspection["file_geodatabases"] == ["Parcels.gdb"]
    assert inspection["parcel_join_field"] == "HCAD_NUM"


def test_sources_and_alternatives_are_network_free():
    source = hcad_gis.execute(_args("sources"), log_results=False)
    alternatives = hcad_gis.execute(
        _args("alternatives"),
        log_results=False,
    )

    assert source.records[0]["parcel_join_field"] == "HCAD_NUM"
    assert alternatives.records[0]["integration"].startswith("implemented")
    assert alternatives.records[2]["url"] == hcad_gis.TXGIO_SOURCE_URL
