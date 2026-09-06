from __future__ import annotations

import copy
import re

import pytest

from tools import query_montana_cadastral as mt
from tools.public_records_bulk import ArtifactProbe
from tools.public_records_http import SourceSchemaError


def _layer(*, missing=()):
    fields = [
        {
            "name": name,
            "alias": name,
            "type": (
                "esriFieldTypeOID"
                if name == "OBJECTID"
                else (
                    "esriFieldTypeGlobalID"
                    if name == "GlobalID"
                    else "esriFieldTypeString"
                )
            ),
            "nullable": True,
        }
        for name in mt.REQUIRED_FIELDS
        if name not in set(missing)
    ]
    return {
        "id": 1,
        "name": "Montana Parcels",
        "type": "Feature Layer",
        "geometryType": "esriGeometryPolygon",
        "capabilities": "Map,Query,Data",
        "maxRecordCount": 2000,
        "currentVersion": 11.5,
        "supportedQueryFormats": "JSON, geoJSON, PBF",
        "advancedQueryCapabilities": {
            "supportsOrderBy": True,
            "supportsPagination": True,
        },
        "extent": {
            "spatialReference": {"wkid": 103093, "latestWkid": 6514}
        },
        "fields": fields,
    }


def _snapshot(*, total=3, with_parcel_id=2, maximum=3, tax_year=2026):
    return mt._compatible_snapshot(
        _layer(),
        total_features=total,
        features_with_parcel_id=with_parcel_id,
        edge={"OBJECTID": maximum, "TaxYear": tax_year},
    )


def _feature(
    object_id,
    *,
    parcel_id=None,
    global_id=None,
    owner="OWNER",
    geometry=False,
):
    attributes = {
        name: None
        for name in mt.QUERY_FIELDS
    }
    attributes.update(
        {
            "OBJECTID": object_id,
            "GlobalID": global_id,
            "PARCELID": parcel_id,
            "COUNTYCD": 55,
            "CountyName": "Petroleum",
            "CountyAbbr": "PE",
            "TaxYear": 2026,
            "PropertyID": 1000 + object_id,
            "AssessmentCode": f"000{object_id}",
            "OwnerName": owner,
            "TotalValue": 100_000,
            "AddressLine1": "1 MAIN ST",
        }
    )
    result = {"attributes": attributes}
    if geometry:
        result["geometry"] = {
            "rings": [[[-110.0, 47.0], [-110.1, 47.0], [-110.0, 47.0]]]
        }
    return result


class FakeQueryClient:
    def __init__(self, features, *, page_size=2, snapshot=None):
        self.features = copy.deepcopy(list(features))
        self.page_size = page_size
        self.snapshot = snapshot or _snapshot(
            total=len(self.features),
            with_parcel_id=sum(
                feature["attributes"]["PARCELID"] is not None
                for feature in self.features
            ),
            maximum=max(
                feature["attributes"]["OBJECTID"] for feature in self.features
            ),
        )
        self.page_calls = []

    def fetch_snapshot(self):
        return self.snapshot

    def fetch_count(self, where, spatial_parameters=None):
        match = re.search(r"OBJECTID > (\d+)", where)
        threshold = int(match.group(1)) if match else 0
        return sum(
            feature["attributes"]["OBJECTID"] > threshold
            for feature in self.features
        )

    def fetch_page(
        self,
        *,
        where,
        record_count,
        return_geometry,
        spatial_parameters=None,
    ):
        self.page_calls.append(
            {
                "where": where,
                "record_count": record_count,
                "return_geometry": return_geometry,
                "spatial_parameters": dict(spatial_parameters or {}),
            }
        )
        match = re.search(r"OBJECTID > (\d+)", where)
        threshold = int(match.group(1)) if match else 0
        selected = [
            feature
            for feature in self.features
            if feature["attributes"]["OBJECTID"] > threshold
        ][:record_count]
        if return_geometry:
            for feature in selected:
                feature.setdefault(
                    "geometry",
                    {
                        "rings": [
                            [[-110.0, 47.0], [-110.1, 47.0], [-110.0, 47.0]]
                        ]
                    },
                )
        return tuple(selected)


def _entry(
    name,
    *,
    size=100,
    directory=False,
    root=mt.BULK_ROOT,
    modified="07/30/2026 01:00 AM",
):
    return mt.DirectoryEntry(
        name=name,
        url=f"{root}{name}{'/' if directory else ''}",
        modified_local=modified,
        modified_sort="2026-07-30T01:00:00",
        size=None if directory else size,
        is_directory=directory,
    )


class FakeDirectoryClient:
    def __init__(self):
        self.page_size = 500
        self.root = (
            _entry("MontanaCadastral_GDB.zip", size=865_314_016),
            _entry("MontanaCadastral_SHP.zip", size=1_035_457_833),
        )
        self.parcels = (
            *(
                _entry(
                    county.directory,
                    directory=True,
                    root=mt.PARCEL_ROOT,
                )
                for county in mt.COUNTIES
            ),
            _entry(
                "Statewide",
                directory=True,
                root=mt.PARCEL_ROOT,
            ),
            _entry(
                "MontanaCadastral_ParcelMetadata.xml",
                size=35_129,
                root=mt.PARCEL_ROOT,
            ),
        )
        self.petroleum = (
            _entry(
                "MontanaCadastral_ParcelMetadata.xml",
                size=35_129,
                root=f"{mt.PARCEL_ROOT}Petroleum/",
            ),
            _entry(
                "Petroleum_GDB.zip",
                size=971_096,
                root=f"{mt.PARCEL_ROOT}Petroleum/",
            ),
            _entry(
                "Petroleum_SHP.zip",
                size=1_164_421,
                root=f"{mt.PARCEL_ROOT}Petroleum/",
            ),
        )
        self.orion = (
            *(
                _entry(
                    f"COUNTY{county.prefix}.ZIP",
                    size=10_000 + county.prefix,
                    root=mt.ORION_ROOT,
                )
                for county in mt.COUNTIES
            ),
            _entry("STATE-WIDE.ZIP", size=1_718_586_421, root=mt.ORION_ROOT),
            _entry("BEGIN HERE.zip", size=459_582, root=mt.ORION_ROOT),
            _entry("ChangeLog.txt", size=2_995, root=mt.ORION_ROOT),
            _entry("CountyNumber.pdf", size=20_656, root=mt.ORION_ROOT),
            _entry("Orion_Diagram.pdf", size=55_544, root=mt.ORION_ROOT),
        )

    def fetch_directory(self, url):
        return {
            mt.BULK_ROOT: self.root,
            mt.PARCEL_ROOT: self.parcels,
            f"{mt.PARCEL_ROOT}Petroleum/": self.petroleum,
            mt.ORION_ROOT: self.orion,
        }[url]


class FakeBulkClient:
    def __init__(self):
        self.calls = []

    def probe(self, artifact, *, sample_bytes):
        self.calls.append((artifact, sample_bytes))
        return ArtifactProbe(
            url=artifact.url,
            http_status=200,
            content_length=artifact.expected_size,
            media_type="application/zip",
            etag='"fixture"',
            last_modified=artifact.last_modified,
            accept_ranges=True,
            source_sha256=None,
            sample_size=sample_bytes,
            sample_sha256="a" * 64,
            signature_hex="504b0304",
            format_hint="zip",
        )


def test_directory_parser_preserves_size_and_publisher_local_marker():
    body = """<pre>
 7/7/2026 10:26 PM        &lt;dir&gt; <A HREF="/Parcels/Petroleum/">Petroleum</A><br>
 7/7/2026 10:15 AM      1164421 <A HREF="/Parcels/Petroleum/Petroleum_SHP.zip">Petroleum_SHP.zip</A><br>
</pre>"""

    entries = mt.parse_directory_listing(body, mt.PARCEL_ROOT)

    assert entries[0].name == "Petroleum"
    assert entries[0].is_directory is True
    assert entries[1].size == 1_164_421
    assert entries[1].modified_sort == "2026-07-07T10:15:00"
    assert entries[1].url.endswith("/Parcels/Petroleum/Petroleum_SHP.zip")


def test_directory_parser_rejects_non_listing_html():
    with pytest.raises(SourceSchemaError):
        mt.parse_directory_listing("<html>blocked</html>", mt.PARCEL_ROOT)


def test_official_county_crosswalk_resolves_name_abbreviation_and_prefix():
    assert len(mt.COUNTIES) == 56
    assert mt._county_from_selector("Petroleum").prefix == 55
    assert mt._county_from_selector("PE").directory == "Petroleum"
    assert mt._county_from_selector("55").name == "Petroleum"
    assert mt._county_from_selector("Butte-Silver Bow").prefix == 1


def test_snapshot_validates_schema_and_tracks_nullable_parcel_ids():
    snapshot = _snapshot(total=920_595, with_parcel_id=886_422, maximum=920_595)

    assert snapshot.native_page_size == 2000
    assert snapshot.total_features - snapshot.features_with_parcel_id == 34_173
    assert re.fullmatch(r"[0-9a-f]{64}", snapshot.schema_fingerprint)
    assert re.fullmatch(r"[0-9a-f]{64}", snapshot.data_fingerprint)


def test_snapshot_rejects_missing_identity_field():
    with pytest.raises(SourceSchemaError) as error:
        mt._compatible_snapshot(
            _layer(missing={"GlobalID"}),
            total_features=3,
            features_with_parcel_id=2,
            edge={"OBJECTID": 3, "TaxYear": 2026},
        )

    assert error.value.details["missing_fields"] == ["GlobalID"]


def test_owner_selection_escapes_sql_and_uses_orion_county_prefix():
    args = mt.build_parser().parse_args(
        ["owner", "O'NEIL", "--county", "Petroleum"]
    )

    selection = mt._selection_from_args(args)

    assert "O''NEIL" in selection.where
    assert "COUNTYCD=55" in selection.where
    assert "DbaName" in selection.where


def test_point_selection_uses_wgs84_intersection():
    args = mt.build_parser().parse_args(
        ["point", "-110.7", "46.9", "--county", "PE"]
    )

    selection = mt._selection_from_args(args)

    assert selection.where == "(COUNTYCD=55)"
    assert selection.spatial_parameters == {
        "geometry": "-110.7,46.9",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }


def test_keyset_cursor_continues_without_repeating_occurrences(monkeypatch):
    monkeypatch.setattr(mt, "log_search", lambda *_args, **_kwargs: None)
    features = [
        _feature(1, parcel_id="A", global_id="{A}"),
        _feature(2, parcel_id=None, global_id="{B}"),
        _feature(3, parcel_id="C", global_id="{C}"),
    ]
    first_args = mt.build_parser().parse_args(
        ["search", "--county", "Petroleum", "--limit", "1"]
    )
    first = mt.execute(
        first_args,
        client=FakeQueryClient(features),
        log_results=False,
    )
    second_args = mt.build_parser().parse_args(
        [
            "search",
            "--county",
            "Petroleum",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )
    second_client = FakeQueryClient(features)
    second = mt.execute(second_args, client=second_client, log_results=False)

    assert first.status.value == "ok"
    assert first.records[0]["identity"]["object_id"] == 1
    assert first.next_cursor.startswith(mt.CURSOR_PREFIX)
    assert second.status.value == "ok"
    assert second.records[0]["identity"]["object_id"] == 2
    assert "OBJECTID > 1" in second_client.page_calls[0]["where"]


def test_cursor_is_bound_to_query_criteria():
    selection = mt.Selection("COUNTYCD=55", {})
    snapshot = _snapshot()
    cursor = mt._encode_cursor(
        mt.CursorState(
            criteria_fingerprint=mt._criteria_fingerprint(
                selection,
                operation="search",
                return_geometry=False,
            ),
            last_object_id=1,
            total_count=3,
            schema_fingerprint=snapshot.schema_fingerprint,
            data_fingerprint=snapshot.data_fingerprint,
        )
    )
    state = mt._decode_cursor(cursor)

    with pytest.raises(mt.MontanaCadastralError) as error:
        mt._validate_cursor(
            state,
            criteria="0" * 64,
            snapshot=snapshot,
        )

    assert error.value.code == "cursor_query_mismatch"


def test_normalization_falls_back_to_objectid_when_join_keys_are_absent():
    snapshot = _snapshot(total=1, with_parcel_id=0, maximum=7)
    record = mt._normalize_feature(
        _feature(7, parcel_id=None, global_id=None),
        snapshot=snapshot,
        geometry_requested=False,
    )

    assert record["source_record_id"] == "OBJECTID-7"
    assert record["identity"]["occurrence_key"] == "OBJECTID"
    assert record["identity"]["parcel_join_key_present"] is False
    assert record["canonical_ref"].endswith("/OBJECTID-7")


def test_county_parcel_manifest_uses_exact_listing_release_identity():
    manifest = mt.build_bulk_manifest(
        FakeDirectoryClient(),
        dataset_type="parcel-shp",
        county=mt._county_from_selector("Petroleum"),
    )

    assert manifest.release.release_id == (
        "parcel-shp:petroleum:20260730T010000:1164421"
    )
    assert manifest.artifacts[0].filename == "Petroleum_SHP.zip"
    assert manifest.artifacts[0].expected_size == 1_164_421
    assert manifest.artifacts[1].filename == (
        "MontanaCadastral_ParcelMetadata.xml"
    )
    assert manifest.metadata["rolling_alias"] is True


def test_orion_manifest_uses_verified_county_prefix_and_schema_documents():
    manifest = mt.build_bulk_manifest(
        FakeDirectoryClient(),
        dataset_type="orion",
        county=mt._county_from_selector("Petroleum"),
    )

    assert manifest.artifacts[0].filename == "COUNTY55.ZIP"
    assert {artifact.artifact_id for artifact in manifest.artifacts} == {
        "data",
        "setup-and-data-dictionary",
        "change-log",
        "county-number-crosswalk",
        "database-diagram",
    }
    assert "CountyNumber.pdf" in manifest.schema["county_crosswalk_url"]


def test_release_discovery_reconciles_all_56_counties():
    record = mt.discover_releases(FakeDirectoryClient())

    assert record["parcel_county_directory_count"] == 56
    assert record["orion_county_archive_count"] == 56
    assert record["missing_parcel_county_directories"] == []
    assert record["missing_orion_county_prefixes"] == []
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        record["release_discovery_fingerprint"],
    )


def test_artifact_probe_is_bounded_and_selects_data_archive(monkeypatch):
    monkeypatch.setattr(mt, "log_search", lambda *_args, **_kwargs: None)
    args = mt.build_parser().parse_args(
        [
            "artifact-probe",
            "--dataset",
            "parcel-shp",
            "--county",
            "Petroleum",
            "--range-bytes",
            "32",
        ]
    )
    bulk = FakeBulkClient()

    result = mt.execute(
        args,
        client=FakeDirectoryClient(),
        bulk_client=bulk,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert bulk.calls[0][0].filename == "Petroleum_SHP.zip"
    assert bulk.calls[0][1] == 32
    assert result.records[0]["probe"]["format_hint"] == "zip"


def test_alternatives_route_missing_instrument_history_to_local_systems():
    routes = mt.alternative_routes()

    assert any(route["url"] == mt.PLSS_ROOT for route in routes)
    local = next(
        route
        for route in routes
        if route["name"].startswith("County assessor")
    )
    assert "mortgage" in local["relationship"]
    assert "lien" in local["relationship"]

