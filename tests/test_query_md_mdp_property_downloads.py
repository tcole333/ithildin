from __future__ import annotations

import zipfile
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

import pytest

from tools import query_md_mdp_property_downloads as mdp
from tools.public_records_bulk import ArchiveSafetyError, DownloadResult
from tools.public_records_contract import ResultStatus


def _official_manifest_html() -> str:
    links = [
        (
            "https://www.dropbox.com/scl/fi/i08w46iye7mkeb15la9fk/"
            "February_2026_Parcels.zip?dl=0"
            "&rlkey=r8y6lzyhj5sqf5mse62vonb4e&st=zbqc3fcv",
            "February 2026 Statewide Geodatabase",
        ),
        (
            "https://www.dropbox.com/scl/fi/risudsvjyaf90aykh28qq/"
            "MdPropertyView_2026_Schema.xlsx?dl=0"
            "&rlkey=2o9a15msupnx4xds3ustrnfzn&st=pg05e3jq",
            "MdProperty View 2026 Schema",
        ),
        (
            "https://www.dropbox.com/scl/fi/o55ooy50vn2i8klewrgrc/"
            "2026-Q1-Statewide-CAMA.zip?dl=0"
            "&rlkey=punproxpop8ppcofu6jrj0b3k&st=no4kl74m",
            "2026 First Quarter Statewide CAMA",
        ),
        (
            "https://www.dropbox.com/scl/fi/eysx4zxql6odgiq544pn8/"
            "2025-Q1-Statewide-CAMA.zip?dl=0"
            "&rlkey=xhz4ge8qs3rsjybuhoxf3arog&st=5oe75jla",
            "2025 First Quarter Statewide CAMA",
        ),
        (
            "https://www.dropbox.com/scl/fi/1qgagcipvz774w34uuv3o/"
            "2025-Q2-Statewide-CAMA.gdb.zip?dl=0"
            "&rlkey=zifa6ugb4uerdxbv8ugaxmewf&st=y792v4pk",
            "2025 Second Quarter Statewide CAMA",
        ),
        (
            "https://www.dropbox.com/scl/fi/mkg2ek9fyyumkj2ornoum/"
            "2025-Q3-Statewide-CAMA.gdb.zip?dl=0"
            "&rlkey=9irv3rx7nclfe8c6lo09z44te&st=dou3678u",
            "2025 Third Quarter Statewide CAMA",
        ),
        (
            "https://www.dropbox.com/scl/fi/6i9nqgmncc7epwcq4h4zu/"
            "2025-Q4-Statewide-CAMA.zip?dl=0"
            "&rlkey=8d0qbxiqd851tl1jvy12q0yh4&st=070pq9gx",
            "2025 Fourth Quarter Statewide CAMA",
        ),
        (
            "https://www.dropbox.com/scl/fi/bolrr1fpz1zv7bqbcbol5/"
            "2024Q2_CAMA_Core.zip?dl=0"
            "&rlkey=bvzdrbpz4jls2nk5rsh4pldkp",
            "2024 Second Quarter CAMA Core",
        ),
        (
            "https://www.dropbox.com/scl/fi/zr0vbom5xxwb2l9st5m9s/"
            "2024Q2_CAMA_Bldg.zip?dl=0"
            "&rlkey=emnuqofz2hee5biyz5o2v4bx0",
            "2024 Second Quarter CAMA Building",
        ),
        (
            "https://www.dropbox.com/scl/fi/hgyrd6hmck1ny2b5atzow/"
            "2024Q2_CAMA_Land.zip?dl=0"
            "&rlkey=tbuve11z84f71od3jrb5phko1",
            "2024 Second Quarter CAMA Land",
        ),
        (
            "https://www.dropbox.com/scl/fi/bxepz2afd5d0eqclgrbou/"
            "2024Q2_CAMA_Suba.zip?dl=0"
            "&rlkey=wpsqirajldqtut8lrdmu07tfe",
            "2024 Second Quarter CAMA Subareas",
        ),
        (
            "https://www.dropbox.com/s/l4icoj0yrksiqzt/2020_CAMA.zip",
            "2020 Statewide CAMA",
        ),
        (
            "https://www.dropbox.com/s/bxpg5ral71aropz/"
            "2017_CAMA_Core.zip",
            "2017 CAMA Core",
        ),
        (
            "https://www.dropbox.com/s/dwip6teenp44s3b/"
            "2017_CAMA_Bldg.zip",
            "2017 CAMA Building",
        ),
        (
            "https://www.dropbox.com/s/003sqhtbwn22bfj/"
            "2017_CAMA_Land.zip",
            "2017 CAMA Land",
        ),
        (
            "https://www.dropbox.com/s/3nkyfmajxrfv92e/"
            "2017_CAMA_Suba.zip",
            "2017 CAMA Subareas",
        ),
        (
            "https://www.dropbox.com/scl/fi/uf9ldo51yu2o3704vs37o/"
            "Property_Sales_0126.zip?dl=0"
            "&rlkey=2li5dd4mlhttcpacca0qq6j6x&st=s882ecpz",
            "January 2026",
        ),
        (
            "https://www.dropbox.com/scl/fi/5n199yacfp8kdwrw7y7yk/"
            "Property_Sales_0226.zip?dl=0"
            "&rlkey=0ct1yaju1hrn7wp11uxsn2imr&st=qhbpmczq",
            "February 2026",
        ),
        (
            "https://www.dropbox.com/scl/fi/ncwwqsvhelcgg1gnef61n/"
            "PropertySales_2026_Schema.xlsx?dl=0"
            "&rlkey=w2zibh9pmadhrq49b6nfclbx2&st=xhcuwa3x",
            "Property Sales 2026 Schema",
        ),
    ]
    return "\n".join(
        '<a href="{}">{}</a>'.format(
            url.replace("&", "&amp;"),
            label,
        )
        for url, label in links
    )


def _snapshot() -> mdp.ManifestSnapshot:
    return mdp.parse_release_manifest(_official_manifest_html())


def _args(command: str, **overrides: Any) -> Namespace:
    values: dict[str, Any] = {
        "command": command,
        "source": mdp.PARCEL_SOURCE_ID,
        "release": None,
        "year": None,
        "component": None,
        "include_schema": True,
        "limit": None,
        "cursor": None,
        "sample_bytes": 64,
        "timeout": 5.0,
        "retry_attempts": 1,
        "chunk_size": 1024,
        "minimum_interval": 0.0,
        "destination": None,
        "resume": True,
        "expected_sha256": None,
        "max_download_bytes": None,
        "inspect": False,
        "artifact": None,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_manifest_discovers_three_families_and_all_live_slots() -> None:
    snapshot = _snapshot()

    assert len(snapshot.releases) == 19
    assert len(snapshot.by_source(mdp.PARCEL_SOURCE_ID)) == 2
    assert len(snapshot.by_source(mdp.CAMA_SOURCE_ID)) == 14
    assert len(snapshot.by_source(mdp.SALES_SOURCE_ID)) == 3

    assert snapshot.by_id("parcels-2026-02").filename == (
        "February_2026_Parcels.zip"
    )
    assert snapshot.by_id("cama-2026-q1-statewide").component == (
        "statewide_bundle"
    )
    assert snapshot.by_id("cama-2024-q2-building").release_group_id == (
        "cama-2024-q2"
    )
    assert snapshot.by_id("sales-2026-02").month == 2
    assert snapshot.by_id("sales-schema-2026").schema_reference is True


def test_manifest_error_page_is_not_mistaken_for_an_empty_release() -> None:
    with pytest.raises(
        mdp.MarylandMDPDownloadError,
        match="did not expose every recognized",
    ):
        mdp.parse_release_manifest(
            "<html><title>Temporary service page</title></html>"
        )


def test_dropbox_transport_resolution_preserves_publisher_link_identity() -> None:
    share_url = (
        "https://www.dropbox.com/scl/fi/i08w46iye7mkeb15la9fk/"
        "February_2026_Parcels.zip?dl=0"
        "&rlkey=r8y6lzyhj5sqf5mse62vonb4e&st=first"
    )
    changed_tracking = share_url.replace("st=first", "st=second")

    metadata = mdp.dropbox_link_metadata(share_url)
    changed_metadata = mdp.dropbox_link_metadata(changed_tracking)
    download_url = mdp.dropbox_download_url(share_url)
    query = parse_qs(urlsplit(download_url).query)

    assert metadata["link_type"] == "scl_file"
    assert metadata["share_token"] == "i08w46iye7mkeb15la9fk"
    assert metadata["filename"] == "February_2026_Parcels.zip"
    assert metadata["provider_link_id"] == changed_metadata[
        "provider_link_id"
    ]
    assert query["dl"] == ["1"]
    assert query["rlkey"] == ["r8y6lzyhj5sqf5mse62vonb4e"]
    assert query["st"] == ["first"]

    legacy = mdp.dropbox_download_url(
        "https://www.dropbox.com/s/l4icoj0yrksiqzt/2020_CAMA.zip"
    )
    assert parse_qs(urlsplit(legacy).query)["dl"] == ["1"]


def test_manifest_records_keep_release_and_semantic_identities_separate() -> None:
    snapshot = _snapshot()
    parcel = snapshot.by_id("parcels-2026-02")
    building = snapshot.by_id("cama-2024-q2-building")
    sales = snapshot.by_id("sales-2026-02")
    sales_schema = snapshot.by_id("sales-schema-2026")
    assert parcel is not None
    assert building is not None
    assert sales is not None
    assert sales_schema is not None

    parcel_record = parcel.manifest_record(snapshot)
    building_record = building.manifest_record(snapshot)
    sales_record = sales.manifest_record(snapshot)
    schema_record = sales_schema.manifest_record(snapshot)

    assert parcel_record["identity_contract"][
        "record_identity_source_id"
    ] == mdp.SDAT_PROPERTY_IDENTITY_SOURCE_ID
    assert parcel_record["identity_contract"][
        "semantic_record_key"
    ] == "ACCTID"
    assert parcel_record["identity_contract"]["release_slot_key"] == [
        "source_id",
        "release_id",
    ]
    assert parcel_record["identity_contract"]["provider_link_key"] == (
        "provider_link_id"
    )
    assert parcel_record["identity_contract"][
        "published_link_occurrence_key"
    ] == ["source_id", "release_id", "provider_link_id"]
    assert building_record["identity_contract"]["component"] == "building"
    assert building_record["identity_contract"]["component_contract"][
        "record_grain"
    ] == "multiple_records_per_parcel_account"
    assert building_record["identity_contract"]["component_contract"][
        "component_occurrence_key"
    ] == ["artifact_sha256", "archive_member_path", "row_ordinal"]
    assert building_record["identity_contract"]["component_contract"][
        "joins"
    ]["subareas"] == "CAMALINK"
    assert sales_record["identity_contract"][
        "semantic_transaction_candidate"
    ] == ["ACCTID", "TRADATE", "CONSIDR1"]
    assert sales_record["identity_contract"][
        "monthly_release_rows_may_repeat"
    ] is True
    assert sales_record["identity_contract"][
        "artifact_occurrence_key"
    ] == "artifact_sha256"
    assert sales_record["identity_contract"][
        "transport_validator_occurrence_key"
    ] == "validator_occurrence_id"
    assert sales_record["identity_contract"]["row_occurrence"] == [
        "artifact_sha256",
        "archive_member_path",
        "row_ordinal",
    ]
    assert schema_record["record_kind"] == "bulk_schema_manifest"
    assert schema_record["identity_contract"][
        "semantic_rows_exposed"
    ] is False
    assert parcel_record["provider_link"]["provider_link_id"] not in (
        parcel_record["release_id"],
        parcel_record["identity_contract"]["semantic_record_key"],
    )


def test_default_selection_uses_latest_data_not_schema_workbook() -> None:
    snapshot = _snapshot()

    parcel = mdp._one_release(
        snapshot,
        source_id=mdp.PARCEL_SOURCE_ID,
        release_id=None,
        year=None,
        component=None,
    )
    cama = mdp._one_release(
        snapshot,
        source_id=mdp.CAMA_SOURCE_ID,
        release_id=None,
        year=None,
        component=None,
    )
    sales = mdp._one_release(
        snapshot,
        source_id=mdp.SALES_SOURCE_ID,
        release_id=None,
        year=None,
        component=None,
    )

    assert parcel.release_id == "parcels-2026-02"
    assert cama.release_id == "cama-2026-q1-statewide"
    assert sales.release_id == "sales-2026-02"
    assert not any(
        release.schema_reference for release in (parcel, cama, sales)
    )


def test_explicit_schema_release_can_be_prepared() -> None:
    result = mdp.execute(
        _args(
            "prepare",
            source=mdp.SALES_SOURCE_ID,
            release="sales-schema-2026",
        ),
        manifest_snapshot=_snapshot(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records[0]["schema_reference"] is True
    assert result.records[0]["prepared_transfer"][
        "expected_filename"
    ] == "PropertySales_2026_Schema.xlsx"


def test_manifest_cursor_is_bound_to_release_set_and_selection() -> None:
    snapshot = _snapshot()
    tracking_only = mdp.parse_release_manifest(
        _official_manifest_html().replace(
            "st=zbqc3fcv",
            "st=publisher-updated",
        )
    )
    assert tracking_only.fingerprint == snapshot.fingerprint
    releases = mdp._selected_releases(
        snapshot,
        source_id=None,
        release_id=None,
        year=None,
        component=None,
        include_schema=True,
    )
    first, cursor = mdp._manifest_page(
        snapshot,
        releases,
        limit=4,
        cursor=None,
    )
    second, _ = mdp._manifest_page(
        snapshot,
        releases,
        limit=4,
        cursor=cursor,
    )

    assert len(first) == 4
    assert len(second) == 4
    assert {item.release_id for item in first}.isdisjoint(
        item.release_id for item in second
    )

    changed = mdp.parse_release_manifest(
        _official_manifest_html().replace(
            "i08w46iye7mkeb15la9fk",
            "replacement-provider-token",
        )
    )
    changed_releases = mdp._selected_releases(
        changed,
        source_id=None,
        release_id=None,
        year=None,
        component=None,
        include_schema=True,
    )
    with pytest.raises(
        mdp.CursorError,
        match="release listing changed",
    ):
        mdp._manifest_page(
            changed,
            changed_releases,
            limit=4,
            cursor=cursor,
        )

    cursor_payload = mdp._decode_cursor(cursor)
    cursor_payload["offset"] = len(releases) + 1
    with pytest.raises(mdp.CursorError, match="exceeds the selection"):
        mdp._manifest_page(
            snapshot,
            releases,
            limit=4,
            cursor=mdp._encode_cursor(cursor_payload),
        )


def test_manifest_page_rejects_a_nonpositive_limit() -> None:
    snapshot = _snapshot()
    with pytest.raises(mdp.SelectionError, match="positive integer"):
        mdp._manifest_page(
            snapshot,
            snapshot.releases,
            limit=0,
            cursor=None,
        )


def test_prepare_resolves_exact_publisher_link_without_network() -> None:
    result = mdp.execute(
        _args(
            "prepare",
            source=mdp.SALES_SOURCE_ID,
            release="sales-2026-02",
        ),
        manifest_snapshot=_snapshot(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    transfer = result.records[0]["prepared_transfer"]
    assert transfer["expected_filename"] == "Property_Sales_0226.zip"
    assert parse_qs(urlsplit(transfer["download_url"]).query)["dl"] == [
        "1"
    ]
    assert transfer["authority"].startswith(
        "Maryland Department of Planning"
    )
    assert transfer["transport_provider"] == "Dropbox"
    assert transfer["provider_revision"].startswith("observe_")


class _FakeProbe:
    format_hint = "zip"

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": "https://content.dropbox.test/artifact",
            "http_status": 206,
            "content_length": 987654,
            "media_type": "application/zip",
            "etag": '"provider-etag"',
            "last_modified": "Thu, 30 Jul 2026 12:00:00 GMT",
            "accept_ranges": True,
            "source_sha256": None,
            "sample_size": 64,
            "sample_sha256": "a" * 64,
            "signature_hex": "504b0304",
            "format_hint": "zip",
            "headers": {
                "content-disposition": (
                    'attachment; filename="Property_Sales_0226.zip"'
                )
            },
        }


class _FakeTransfer:
    def __init__(self) -> None:
        self.artifact: Any = None
        self.sample_bytes: int | None = None

    def probe(
        self,
        artifact: Any,
        *,
        sample_bytes: int,
    ) -> _FakeProbe:
        self.artifact = artifact
        self.sample_bytes = sample_bytes
        return _FakeProbe()


def test_probe_binds_transport_validators_to_observation_not_release() -> None:
    transfer = _FakeTransfer()
    result = mdp.execute(
        _args(
            "probe",
            source=mdp.SALES_SOURCE_ID,
            release="sales-2026-02",
        ),
        manifest_snapshot=_snapshot(),
        transfer_client=transfer,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert transfer.sample_bytes == 64
    assert parse_qs(urlsplit(transfer.artifact.url).query)["dl"] == [
        "1"
    ]
    observation = result.records[0][
        "validator_occurrence_identity"
    ]
    assert observation["etag"] == '"provider-etag"'
    assert observation["provider_revision_field_published"] is True
    assert observation["meaning"] == (
        "observed_transport_validators_not_release_slot_identity"
    )


class _HTMLProbe(_FakeProbe):
    format_hint = None

    def to_dict(self) -> dict[str, Any]:
        value = super().to_dict()
        value.update(
            {
                "media_type": "text/html",
                "signature_hex": "3c21646f63747970",
                "format_hint": None,
            }
        )
        return value


class _HTMLTransfer(_FakeTransfer):
    def probe(
        self,
        artifact: Any,
        *,
        sample_bytes: int,
    ) -> _HTMLProbe:
        self.artifact = artifact
        self.sample_bytes = sample_bytes
        return _HTMLProbe()


def test_probe_surfaces_provider_error_page_as_source_change() -> None:
    result = mdp.execute(
        _args(
            "probe",
            source=mdp.SALES_SOURCE_ID,
            release="sales-2026-02",
        ),
        manifest_snapshot=_snapshot(),
        transfer_client=_HTMLTransfer(),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == (
        "maryland_mdp_download_source_changed"
    )
    assert result.errors[0].details["media_type"] == "text/html"


class _EmptyZipProbe(_FakeProbe):
    format_hint = None

    def to_dict(self) -> dict[str, Any]:
        value = super().to_dict()
        value.update(
            {
                "signature_hex": "504b050600000000",
                "format_hint": None,
            }
        )
        return value


class _EmptyZipTransfer(_FakeTransfer):
    def probe(
        self,
        artifact: Any,
        *,
        sample_bytes: int,
    ) -> _EmptyZipProbe:
        self.artifact = artifact
        self.sample_bytes = sample_bytes
        return _EmptyZipProbe()


def test_probe_accepts_a_valid_empty_zip_container_signature() -> None:
    result = mdp.execute(
        _args(
            "probe",
            source=mdp.SALES_SOURCE_ID,
            release="sales-2026-02",
        ),
        manifest_snapshot=_snapshot(),
        transfer_client=_EmptyZipTransfer(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records[0]["format_expectation"][
        "zip_container_signature_observed"
    ] is True


class _FakeDownloadTransfer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.artifact: Any = None

    def download(
        self,
        artifact: Any,
        destination: str,
        *,
        resume: bool,
        max_bytes: int | None,
    ) -> DownloadResult:
        self.artifact = artifact
        assert destination == str(self.path)
        assert resume is True
        assert max_bytes is None
        self.path.write_bytes(b"PK\x03\x04")
        return DownloadResult(
            path=str(self.path),
            url=artifact.url,
            size=123,
            sha256="b" * 64,
            expected_sha256=artifact.expected_sha256,
            etag='"download-etag"',
            last_modified="Thu, 30 Jul 2026 13:00:00 GMT",
            resumed_from=0,
            reused_existing=False,
        )


def test_download_receipt_keeps_digest_occurrence_separate(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "Property_Sales_0226.zip"
    transfer = _FakeDownloadTransfer(destination)
    result = mdp.execute(
        _args(
            "download",
            source=mdp.SALES_SOURCE_ID,
            release="sales-2026-02",
            destination=str(destination),
        ),
        manifest_snapshot=_snapshot(),
        transfer_client=transfer,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    identity = result.records[0]["artifact_occurrence_identity"]
    assert identity["artifact_sha256"] == "b" * 64
    assert identity["etag"] == '"download-etag"'
    assert identity["interchangeable_with_release_slot"] is False
    assert result.records[0]["release_id"] == "sales-2026-02"
    assert result.records[0]["release_id"] != identity["artifact_sha256"]
    assert result.records[0]["integrity_validation"][
        "expected_sha256_verified"
    ] is False


def _write_zip(path: Path, members: Mapping[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for member_path, body in members.items():
            archive.writestr(member_path, body)


def test_local_parcel_inspection_keeps_shared_acctid_identity(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "February_2026_Parcels.zip"
    _write_zip(
        artifact,
        {
            "February_2026_Parcels.gdb/a00000001.gdbtable": "table",
            "README.txt": "notes",
        },
    )

    inspection = mdp.inspect_local_artifact(
        artifact,
        source_id=mdp.PARCEL_SOURCE_ID,
    )
    geodatabase_member = next(
        member
        for member in inspection["members"]
        if ".gdb/" in member["path"]
    )

    assert geodatabase_member["classification"]["role"] == (
        "parcel_file_geodatabase_member"
    )
    assert geodatabase_member["classification"][
        "semantic_record_key"
    ] == "ACCTID"
    assert inspection["identity_contract"][
        "record_identity_source_id"
    ] == mdp.SDAT_PROPERTY_IDENTITY_SOURCE_ID
    assert inspection["publisher_filename"] == (
        "February_2026_Parcels.zip"
    )
    readme = next(
        member
        for member in inspection["members"]
        if member["path"] == "README.txt"
    )
    assert readme["classification"]["data_candidate"] is False
    assert readme["classification"]["semantic_record_key"] is None


def test_local_inspection_rejects_unsafe_archive_member_paths(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "February_2026_Parcels.zip"
    _write_zip(artifact, {"../outside.gdbtable": "table"})

    with pytest.raises(ArchiveSafetyError, match="escape"):
        mdp.inspect_local_artifact(
            artifact,
            source_id=mdp.PARCEL_SOURCE_ID,
        )


def test_local_cama_inspection_classifies_component_occurrences(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "2024Q2_CAMA_Bldg.zip"
    _write_zip(
        artifact,
        {
            "CAMA_Bldg.gdb/a00000001.gdbtable": "table",
            "CAMA_Bldg.gdb/a00000001.gdbtablx": "index",
            "README.txt": "notes",
        },
    )

    inspection = mdp.inspect_local_artifact(
        artifact,
        source_id=mdp.CAMA_SOURCE_ID,
        release_id="cama-2024-q2-building",
    )

    assert inspection["release_group_id"] == "cama-2024-q2"
    assert inspection["component_counts"]["building"] == 2
    assert inspection["identity_contract"]["component"] == "building"
    assert inspection["identity_contract"]["component_contract"][
        "joins"
    ]["subareas"] == "CAMALINK"
    assert len(
        {
            member["member_occurrence_id"]
            for member in inspection["members"]
        }
    ) == 3
    assert all(
        len(member["member_occurrence_id"]) == 64
        for member in inspection["members"]
    )
    readme = next(
        member
        for member in inspection["members"]
        if member["path"] == "README.txt"
    )
    assert readme["classification"]["role"] == (
        "cama_component_support_member"
    )
    assert readme["classification"]["component"] is None


def test_statewide_cama_geodatabase_member_stays_a_data_candidate(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "2026-Q1-Statewide-CAMA.zip"
    _write_zip(
        artifact,
        {
            "Statewide-CAMA.gdb/a00000001.gdbtable": "table",
            "README.txt": "notes",
        },
    )

    inspection = mdp.inspect_local_artifact(
        artifact,
        source_id=mdp.CAMA_SOURCE_ID,
    )
    table = next(
        member
        for member in inspection["members"]
        if member["path"].endswith(".gdbtable")
    )

    assert table["classification"]["role"] == (
        "cama_statewide_data_candidate"
    )
    assert table["classification"]["component"] is None
    assert table["classification"]["row_schema_verified"] is False


def test_local_sales_inspection_does_not_invent_row_identity(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "Property_Sales_0226.zip"
    _write_zip(
        artifact,
        {
            "Property_Sales_0226.csv": (
                "ACCTID,TRADATE,CONSIDR1\n"
                "0100000001,2026-02-01,450000\n"
            ),
            "README.txt": "publisher notes",
        },
    )

    inspection = mdp.inspect_local_artifact(
        artifact,
        source_id=mdp.SALES_SOURCE_ID,
    )
    rows = next(
        member
        for member in inspection["members"]
        if member["path"].endswith(".csv")
    )

    assert rows["classification"]["role"] == (
        "property_sales_rows_candidate"
    )
    assert rows["classification"]["row_schema_verified"] is False
    assert inspection["row_search_performed"] is False
    assert inspection["identity_contract"][
        "source_issued_transaction_identifier_verified"
    ] is False
    assert inspection["identity_contract"][
        "semantic_transaction_candidate"
    ] == ["ACCTID", "TRADATE", "CONSIDR1"]
    readme = next(
        member
        for member in inspection["members"]
        if member["path"] == "README.txt"
    )
    assert readme["classification"]["data_candidate"] is False
    assert readme["classification"]["transaction_identity"] is None


def test_schema_workbook_inspection_stays_at_artifact_grain(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "PropertySales_2026_Schema.xlsx"
    _write_zip(
        workbook,
        {
            "[Content_Types].xml": "<Types/>",
            "xl/workbook.xml": "<workbook/>",
        },
    )

    inspection = mdp.inspect_local_artifact(
        workbook,
        source_id=mdp.SALES_SOURCE_ID,
    )

    assert inspection["schema_reference"] is True
    assert inspection["identity_contract"]["record_grain"] == (
        "publisher_schema_artifact"
    )
    assert inspection["identity_contract"][
        "semantic_rows_exposed"
    ] is False
    assert set(inspection["role_counts"]) == {"schema_workbook_part"}


def test_schema_workbook_requires_xlsx_container_members(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "PropertySales_2026_Schema.xlsx"
    _write_zip(workbook, {"not-a-workbook.txt": "placeholder"})

    with pytest.raises(
        mdp.MarylandMDPDownloadError,
        match="not a recognized XLSX workbook",
    ):
        mdp.inspect_local_artifact(
            workbook,
            source_id=mdp.SALES_SOURCE_ID,
        )


def test_source_contracts_expose_join_and_complement_roles() -> None:
    records = {
        record["source_id"]: record
        for record in mdp.source_records()
    }

    assert records[mdp.PARCEL_SOURCE_ID]["identity_contract"][
        "record_identity_source_id"
    ] == mdp.SDAT_PROPERTY_IDENTITY_SOURCE_ID
    assert records[mdp.CAMA_SOURCE_ID]["identity_contract"][
        "building_subarea_join_key"
    ] == "CAMALINK"
    assert records[mdp.CAMA_SOURCE_ID]["identity_contract"][
        "components"
    ]["land"]["scope"] == "property_land_characteristic_not_building"
    assert records[mdp.SALES_SOURCE_ID]["identity_contract"][
        "monthly_release_rows_may_repeat"
    ] is True
    assert all(
        record["capabilities"]["row_search"] is False
        for record in records.values()
    )


def test_main_does_not_require_manifest_only_namespace_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mdp,
        "execute",
        lambda args: SimpleNamespace(status=ResultStatus.OK),
    )
    monkeypatch.setattr(mdp, "_emit", lambda result, args: None)

    assert mdp.main(["sources"]) == 0
