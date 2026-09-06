from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from tools import query_oregon_benton_property as benton
from tools.public_records_bulk import (
    ArtifactProbe,
    BulkTransportError,
    DownloadResult,
)
from tools.public_records_contract import ResultStatus
from tools.public_records_http import SourceSchemaError


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_benton_property"
)


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _feature(object_id: int, party_name: str) -> dict:
    feature = _json("representative_feature.json")
    feature["attributes"]["OBJECTID"] = object_id
    feature["attributes"]["Party_Name"] = party_name
    return feature


class FixtureParcelClient:
    page_size = 2

    def __init__(self, features: list[dict] | None = None) -> None:
        self.features = features or [
            _feature(1, "OWNER ONE"),
            _feature(2, "OWNER TWO"),
            _feature(3, "OWNER THREE"),
            _feature(4, "OWNER FOUR"),
        ]
        self.page_requests: list[tuple[str, int, bool]] = []

    def fetch_metadata(self) -> dict:
        return _json("layer_metadata.json")

    def fetch_service_metadata(self) -> dict:
        return _json("service_metadata.json")

    def fetch_wgs84_extent(self) -> dict:
        return _json("wgs84_extent.json")

    def _matching(self, where: str) -> list[dict]:
        anchor_match = re.search(r"OBJECTID\s*>\s*(\d+)", where)
        anchor = int(anchor_match.group(1)) if anchor_match else 0
        return [
            feature
            for feature in self.features
            if feature["attributes"]["OBJECTID"] > anchor
        ]

    def fetch_count(self, where: str) -> int:
        return len(self._matching(where))

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
    ) -> tuple[dict, ...]:
        self.page_requests.append((where, record_count, return_geometry))
        return tuple(self._matching(where)[:record_count])


class FixtureDirectoryClient:
    def listing(
        self,
        url: str,
        *,
        expected_path: str,
    ) -> benton.DirectoryListing:
        if url == benton.ASSESSMENT_DIRECTORY_URL:
            fixture = "assessment_index.html"
        elif url == benton.ASSESSMENT_MAP_DIRECTORY_URL:
            fixture = "maps_index.html"
        else:
            raise AssertionError(url)
        return benton.parse_iis_listing(
            _text(fixture),
            source_url=url,
            expected_path=expected_path,
        )


class FixtureBulkClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.probed = []

    def probe(self, artifact, *, sample_bytes: int):
        if self.error:
            raise self.error
        self.probed.append((artifact, sample_bytes))
        is_pdf = artifact.filename.casefold().endswith(".pdf")
        return ArtifactProbe(
            url=artifact.url,
            http_status=200,
            content_length=artifact.expected_size,
            media_type="application/pdf" if is_pdf else "application/zip",
            etag='"fixture"',
            last_modified=artifact.last_modified,
            accept_ranges=True,
            source_sha256=None,
            sample_size=sample_bytes,
            sample_sha256="0" * 64 if sample_bytes else None,
            signature_hex=(
                "255044462d312e36" if is_pdf else "504b030414000000"
            ),
            format_hint=None if is_pdf else "zip",
            headers={"accept-ranges": "bytes"},
        )


class FixtureDownloadClient:
    def __init__(self, archive_path: Path, digest: str) -> None:
        self.archive_path = archive_path
        self.digest = digest
        self.calls = []

    def download(
        self,
        artifact,
        destination,
        *,
        resume: bool,
        max_bytes: int | None,
    ) -> DownloadResult:
        self.calls.append((artifact, Path(destination), resume, max_bytes))
        assert artifact.expected_sha256 == self.digest
        return DownloadResult(
            path=str(self.archive_path),
            url=artifact.url,
            size=self.archive_path.stat().st_size,
            sha256=self.digest,
            expected_sha256=self.digest,
            etag='"fixture"',
            last_modified=artifact.last_modified,
            resumed_from=self.archive_path.stat().st_size,
            reused_existing=True,
        )


def test_layer_contract_derives_object_id_and_matches_observed_schema() -> None:
    metadata = _json("layer_metadata.json")
    assert metadata["objectIdField"] is None

    contract = benton._metadata_schema(metadata)

    assert contract.server_page_size == 1000
    assert contract.source_wkid == 2913
    assert contract.schema_fingerprint == benton.EXPECTED_SCHEMA_FINGERPRINT


def test_jurisdiction_identity_requires_oregon_county_signals() -> None:
    evidence = benton.jurisdiction_identity_evidence(
        service_url=benton.PARCEL_SERVICE_URL,
        service_metadata=_json("service_metadata.json"),
        wgs84_extent=_json("wgs84_extent.json"),
        source_wkid=2913,
    )
    assert evidence["verified"] is True
    assert all(evidence["signals"].values())

    wrong = _json("wrong_jurisdiction.json")
    wrong_evidence = benton.jurisdiction_identity_evidence(
        service_url=wrong["service_url"],
        service_metadata=wrong["service_metadata"],
        wgs84_extent=wrong["wgs84_extent"],
        source_wkid=wrong["source_wkid"],
    )
    assert wrong_evidence["verified"] is False
    assert wrong_evidence["signals"]["official_host_matches"] is False
    assert wrong_evidence["signals"]["wgs84_extent_matches"] is False


def test_normalization_retains_owner_party_grain_and_native_lineage() -> None:
    record = benton.normalize_taxlot_owner(
        _json("representative_feature.json"),
        source_schema_fingerprint=benton.EXPECTED_SCHEMA_FINGERPRINT,
        geometry_requested=True,
    )

    assert record["record_kind"] == "taxlot_owner_party"
    assert record["object_id"] == 107939
    assert record["account_number"] == "802377"
    assert record["map_taxlot"] == "11513A000100"
    assert record["or_taxlot"] == "0211.00S05.00W13A0--000000100"
    assert record["owner_party"]["raw_name"].startswith("NOLAN LACY MARIE")
    assert record["situs_address"]["city"] == "CORVALLIS"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["source_geometry_crs"] == "EPSG:2913"
    assert record["native_fields"]["Account_Num"] == "802377    "
    assert record["official_links"]["county_sales_api"].endswith(
        "/bcaps-sales/802377"
    )
    assert record["official_links"]["candidate_assessment_map_pdf"].endswith(
        "/11513A.pdf"
    )

    second = benton.normalize_taxlot_owner(
        _feature(107940, "NOLAN LACY MARIE"),
        source_schema_fingerprint=benton.EXPECTED_SCHEMA_FINGERPRINT,
        geometry_requested=False,
    )
    assert second["account_number"] == record["account_number"]
    assert second["map_taxlot"] == record["map_taxlot"]
    assert second["canonical_ref"] != record["canonical_ref"]


def test_selectors_cover_all_native_lookup_keys_and_escape_quotes() -> None:
    assert benton._where("802377", "account") == (
        "UPPER(Account_Num) = '802377'"
    )
    assert "MapTaxlot" in benton._where("11513A000100", "map_taxlot")
    assert "ORTaxlot" in benton._where("0211.00S", "or_taxlot")
    assert "MapNumber" in benton._where("11513A", "map_number")
    assert "Party_Name" in benton._where("O'NEIL", "owner")
    assert "O''NEIL" in benton._where("O'NEIL", "owner")
    auto = benton._where("ELLIOTT", "auto")
    assert "Party_Name" in auto
    assert "Situs_Addr1" in auto
    assert "Mail_Line1" in auto


def test_object_id_cursor_is_query_bound_and_advances_without_overlap() -> None:
    client = FixtureParcelClient()
    first = benton._fetch_parcel_batch(
        client,
        operation="scan",
        where="1=1",
        limit=2,
        cursor=None,
        return_geometry=False,
    )
    assert [benton._feature_oid(row) for row in first.features] == [1, 2]
    assert first.next_cursor
    assert first.remaining_after_anchor == 2

    second = benton._fetch_parcel_batch(
        client,
        operation="scan",
        where="1=1",
        limit=2,
        cursor=first.next_cursor,
        return_geometry=False,
    )
    assert [benton._feature_oid(row) for row in second.features] == [3, 4]
    assert second.next_cursor is None

    with pytest.raises(benton.SelectionError, match="different query"):
        benton._fetch_parcel_batch(
            client,
            operation="owner",
            where="UPPER(Party_Name) LIKE '%OWNER%'",
            limit=2,
            cursor=first.next_cursor,
            return_geometry=False,
        )


def test_iis_listing_identity_and_current_bulk_manifest() -> None:
    listing = benton.parse_iis_listing(
        _text("assessment_index.html"),
        source_url=benton.ASSESSMENT_DIRECTORY_URL,
        expected_path="/gisdata/Assessment/",
    )
    assert len(listing.entries) == 7
    assert len(listing.listing_fingerprint) == 64

    release = benton.build_bulk_manifest(listing)
    manifest = release["manifest"]
    assert [item["filename"] for item in manifest["artifacts"]] == list(
        benton.CURRENT_BULK_FILENAMES
    )
    assert [
        item["expected_size"] for item in manifest["artifacts"]
    ] == [162692007, 10994887, 11718433]
    assert manifest["metadata"]["legacy_similarly_named_artifacts_excluded"] == [
        "BentonTaxlotsGDB.zip"
    ]
    assert manifest["schema"]["source_crs"] == "EPSG:2913"


def test_iis_listing_rejects_wrong_host_and_directory_title() -> None:
    html = _text("assessment_index.html")
    with pytest.raises(SourceSchemaError, match="not hosted"):
        benton.parse_iis_listing(
            html,
            source_url="https://example.org/gisdata/Assessment/",
            expected_path="/gisdata/Assessment/",
        )
    with pytest.raises(SourceSchemaError, match="title"):
        benton.parse_iis_listing(
            html.replace("/gisdata/Assessment/</title>", "/wrong/</title>"),
            source_url=benton.ASSESSMENT_DIRECTORY_URL,
            expected_path="/gisdata/Assessment/",
        )


def test_map_filters_kinds_and_listing_bound_cursor() -> None:
    listing = benton.parse_iis_listing(
        _text("maps_index.html"),
        source_url=benton.ASSESSMENT_MAP_DIRECTORY_URL,
        expected_path="/gisdata/Assessment/AssessmentMapsPDF/",
    )
    first, cursor, remaining = benton.map_records(
        listing,
        map_number="11513A",
        match_mode="prefix",
        map_kind="assessment_map",
        updated_after=None,
        limit=1,
        cursor=None,
    )
    assert [row["filename"] for row in first] == ["11513A.pdf"]
    assert remaining == 2
    assert cursor

    second, next_cursor, remaining_second = benton.map_records(
        listing,
        map_number="11513A",
        match_mode="prefix",
        map_kind="assessment_map",
        updated_after=None,
        limit=2,
        cursor=cursor,
    )
    assert [row["filename"] for row in second] == ["11513AB.pdf"]
    assert remaining_second == 1
    assert next_cursor is None

    dated, _, _ = benton.map_records(
        listing,
        map_number="11513A",
        match_mode="prefix",
        map_kind="dated_archive",
        updated_after=None,
        limit=10,
        cursor=None,
    )
    assert [row["filename"] for row in dated] == ["11513A_12-14-2015.pdf"]

    changed = replace(listing, listing_fingerprint="a" * 64)
    with pytest.raises(benton.SelectionError, match="directory changed"):
        benton.map_records(
            changed,
            map_number="11513A",
            match_mode="prefix",
            map_kind="assessment_map",
            updated_after=None,
            limit=1,
            cursor=cursor,
        )


def test_bulk_and_map_probe_components_remain_distinct() -> None:
    parser = benton.build_parser()
    directory = FixtureDirectoryClient()
    transfer = FixtureBulkClient()

    bulk_args = parser.parse_args(
        ["probe", "--component", "bulk", "--range-bytes", "8"]
    )
    bulk = benton.execute_bulk_probe(
        bulk_args,
        directory_client=directory,
        bulk_client=transfer,
        log_results=False,
    )
    assert bulk.status == ResultStatus.OK
    assert bulk.query.source.source_id == benton.BULK_SOURCE_ID
    assert len(bulk.records[0]["artifact_probes"]) == 3

    map_args = parser.parse_args(
        [
            "probe",
            "--component",
            "maps",
            "--map-artifact",
            "10329",
            "--range-bytes",
            "8",
        ]
    )
    maps = benton.execute_map_probe(
        map_args,
        directory_client=directory,
        bulk_client=transfer,
        log_results=False,
    )
    assert maps.status == ResultStatus.OK
    assert maps.query.source.source_id == benton.MAP_SOURCE_ID
    assert maps.records[0]["pdf_count"] == 6
    assert maps.records[0]["artifact_probe"]["signature_hex"].startswith(
        "25504446"
    )


def test_probe_transport_failure_is_not_reported_as_no_results() -> None:
    parser = benton.build_parser()
    args = parser.parse_args(
        [
            "artifact-probe",
            "--component",
            "bulk",
            "--artifact",
            "TaxlotOwners.zip",
        ]
    )
    result = benton.execute_artifact_probe(
        args,
        directory_client=FixtureDirectoryClient(),
        bulk_client=FixtureBulkClient(
            error=BulkTransportError("fixture transport failure")
        ),
        log_results=False,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.status != ResultStatus.NO_RESULTS
    assert result.errors[0].code == "bulk_transport_error"


def test_download_passes_resume_and_checksum_to_shared_bulk_transport(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("TaxlotOwners.dbf", b"fixture")
        output.writestr("TaxlotOwners.shp", b"geometry")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    transfer = FixtureDownloadClient(archive, digest)
    args = benton.build_parser().parse_args(
        [
            "artifact-download",
            "--component",
            "bulk",
            "--artifact",
            "TaxlotOwners.zip",
            "--destination",
            str(archive),
            "--expected-sha256",
            digest,
            "--max-download-bytes",
            "20000000",
        ]
    )

    result = benton.execute_artifact_download(
        args,
        directory_client=FixtureDirectoryClient(),
        bulk_client=transfer,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert transfer.calls[0][2:] == (True, 20000000)
    assert result.records[0]["integrity"]["expected_checksum_matched"] is True
    assert result.records[0]["archive"]["schema"]["shapefile_datasets"] == (
        "TaxlotOwners",
    )


def test_sources_publish_distinct_components_and_official_complements() -> None:
    payload = benton._sources_payload()
    assert {source["source_id"] for source in payload["sources"]} == {
        benton.PARCEL_SOURCE_ID,
        benton.BULK_SOURCE_ID,
        benton.MAP_SOURCE_ID,
    }
    complement_ids = {
        source["source_id"] for source in payload["complementary_sources"]
    }
    assert benton.ACCOUNT_API_SOURCE_ID in complement_ids
    assert benton.HELION_SOURCE_ID in complement_ids
    assert any(
        item["scope"] == "entity_grain"
        for item in payload["process_learnings"]
    )


@pytest.mark.skipif(
    os.environ.get("RUN_BENTON_PROPERTY_LIVE") != "1",
    reason="set RUN_BENTON_PROPERTY_LIVE=1 for bounded official-source probes",
)
def test_live_benton_property_components() -> None:
    args = benton.build_parser().parse_args(
        [
            "probe",
            "--all",
            "--range-bytes",
            "8",
            "--minimum-interval",
            "0.05",
        ]
    )

    payload = benton.execute_all_probes(args, log_results=False)

    assert payload["status"] == "ok"
    parcel, bulk, maps = payload["components"]
    assert parcel["status"] == "ok"
    assert parcel["records"][0]["component_total_count"] > 100_000
    assert parcel["records"][0]["schema_baseline"]["matches"] is True
    assert bulk["status"] == "ok"
    assert len(bulk["records"][0]["artifact_probes"]) == 3
    assert maps["status"] == "ok"
    assert maps["records"][0]["pdf_count"] > 1_500
