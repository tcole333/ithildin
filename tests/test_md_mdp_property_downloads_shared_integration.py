from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_md_mdp_property_downloads as mdp
from tools import query_property
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _release(source_id: str) -> mdp.Release:
    if source_id == mdp.PARCEL_SOURCE_ID:
        return mdp.Release(
            source_id=source_id,
            release_id="parcels-2026-02",
            label="February 2026 Statewide Geodatabase",
            filename="February_2026_Parcels.zip",
            share_url=(
                "https://www.dropbox.com/scl/fi/parcel-token/"
                "February_2026_Parcels.zip?rlkey=parcel-key&dl=0"
            ),
            publication_kind="statewide_parcel_geodatabase",
            format="zip",
            schema_profile="mdproperty_view_geodatabase",
            year=2026,
            month=2,
        )
    if source_id == mdp.CAMA_SOURCE_ID:
        return mdp.Release(
            source_id=source_id,
            release_id="cama-2026-q1-statewide",
            release_group_id="cama-2026-q1",
            label="2026 First Quarter Statewide CAMA",
            filename="2026-Q1-Statewide-CAMA.zip",
            share_url=(
                "https://www.dropbox.com/scl/fi/cama-token/"
                "2026-Q1-Statewide-CAMA.zip?rlkey=cama-key&dl=0"
            ),
            publication_kind="quarterly_statewide_cama_bundle",
            format="zip",
            schema_profile="cama_statewide_bundle",
            year=2026,
            quarter=1,
            component="statewide_bundle",
        )
    return mdp.Release(
        source_id=source_id,
        release_id="sales-2026-02",
        label="February 2026",
        filename="Property_Sales_0226.zip",
        share_url=(
            "https://www.dropbox.com/scl/fi/sales-token/"
            "Property_Sales_0226.zip?rlkey=sales-key&dl=0"
        ),
        publication_kind="monthly_residential_sales_analytic_release",
        format="zip",
        schema_profile="mdp_property_sales_monthly",
        year=2026,
        month=2,
    )


def _probe_result(source_id: str) -> PublicRecordsResult:
    release = _release(source_id)
    snapshot = mdp.ManifestSnapshot(
        releases=(release,),
        landing_sha256="a" * 64,
    )
    args = mdp.build_parser().parse_args(
        ["probe", "--source", source_id]
    )
    record = {
        **release.manifest_record(snapshot),
        "record_kind": "source_probe",
        "probe_schema_version": mdp.PROBE_SCHEMA_VERSION,
        "artifact_probe": {
            "url": release.download_url,
            "http_status": 206,
            "content_length": 1_024,
            "media_type": "application/zip",
            "etag": '"fixture-etag"',
            "last_modified": "Thu, 30 Jul 2026 12:00:00 GMT",
            "accept_ranges": True,
            "sample_size": 64,
            "sample_sha256": "b" * 64,
            "signature_hex": "504b0304",
            "format_hint": "zip",
        },
        "validator_occurrence_identity": {
            "validator_occurrence_id": "c" * 64,
            "provider_revision_field_published": True,
        },
    }
    return PublicRecordsResult.success(
        mdp._build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    )


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=64,
    )


def test_shared_routes_expose_artifact_operations_without_row_search() -> None:
    for source_id in mdp.SOURCE_IDS:
        routes = query_property.LIVE_ROUTES[source_id]
        guidance = query_property._source_guidance(source_id)

        assert set(routes) == {
            "releases",
            "manifest",
            "discovery",
            "probe",
            "download",
        }
        assert guidance["row_projection"] is False
        assert "search" not in routes
        assert "owner" not in routes
        assert "sale" not in routes


def test_shared_manifest_and_cama_component_selectors_are_preserved() -> None:
    manifest = query_property._md_mdp_property_download_args(
        _parse(
            "manifest",
            "--source",
            mdp.PARCEL_SOURCE_ID,
            "--limit",
            "2",
            "--cursor",
            "cursor-value",
        ),
        "manifest",
    )
    cama = query_property._md_mdp_property_download_args(
        _parse(
            "probe",
            "--source",
            mdp.CAMA_SOURCE_ID,
            "--collection-id",
            "cama-2024-q2-building",
            "--dataset-type",
            "building",
            "--range-bytes",
            "128",
        ),
        "probe",
    )

    assert manifest.command == "manifest"
    assert manifest.source == mdp.PARCEL_SOURCE_ID
    assert manifest.limit == 2
    assert manifest.cursor == "cursor-value"
    assert manifest.include_schema is True
    assert cama.command == "probe"
    assert cama.release == "cama-2024-q2-building"
    assert cama.component == "building"
    assert cama.sample_bytes == 128


def test_shared_download_prepares_or_transfers_from_the_same_release() -> None:
    prepared = query_property._md_mdp_property_download_args(
        _parse(
            "download",
            "sales-2026-02",
            "--source",
            mdp.SALES_SOURCE_ID,
        ),
        "download",
    )
    transfer = query_property._md_mdp_property_download_args(
        _parse(
            "download",
            "--source",
            mdp.SALES_SOURCE_ID,
            "--collection-id",
            "sales-2026-02",
            "--destination",
            "/tmp/Property_Sales_0226.zip",
            "--no-resume",
            "--expected-sha256",
            "d" * 64,
            "--max-download-bytes",
            "4096",
            "--chunk-size",
            "512",
        ),
        "download",
    )

    assert (prepared.command, prepared.release) == (
        "prepare",
        "sales-2026-02",
    )
    assert transfer.command == "download"
    assert transfer.release == prepared.release
    assert transfer.destination == "/tmp/Property_Sales_0226.zip"
    assert transfer.resume is False
    assert transfer.expected_sha256 == "d" * 64
    assert transfer.max_download_bytes == 4096
    assert transfer.chunk_size == 512


def test_shared_manifest_can_inventory_one_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "February_2026_Parcels.zip"
    translated = query_property._md_mdp_property_download_args(
        _parse(
            "manifest",
            "--source",
            mdp.PARCEL_SOURCE_ID,
            "--artifact-path",
            str(artifact),
            "--collection-id",
            "parcels-2026-02",
        ),
        "manifest",
    )

    assert translated.command == "inspect"
    assert translated.artifact == str(artifact)
    assert translated.source == mdp.PARCEL_SOURCE_ID
    assert translated.release == "parcels-2026-02"


def test_shared_translation_does_not_imply_county_or_row_filtering() -> None:
    with pytest.raises(ValueError, match="statewide"):
        query_property._md_mdp_property_download_args(
            _parse(
                "manifest",
                "--source",
                mdp.PARCEL_SOURCE_ID,
                "--county",
                "Montgomery",
            ),
            "manifest",
        )
    with pytest.raises(ValueError, match="do not use row limits"):
        query_property._md_mdp_property_download_args(
            _parse(
                "probe",
                "--source",
                mdp.SALES_SOURCE_ID,
                "--limit",
                "1",
            ),
            "probe",
        )
    with pytest.raises(ValueError, match="row search"):
        query_property._md_mdp_property_download_args(
            _parse(
                "manifest",
                "--source",
                mdp.SALES_SOURCE_ID,
                "--search-field",
                "buyer",
            ),
            "manifest",
        )


@pytest.mark.parametrize("source_id", mdp.SOURCE_IDS)
def test_monitor_uses_one_non_schema_data_artifact(
    source_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = SimpleNamespace(args=None, kwargs=None)

    def fake_execute(args: Any, **kwargs: Any) -> PublicRecordsResult:
        captured.args = args
        captured.kwargs = kwargs
        return _probe_result(source_id)

    monkeypatch.setattr(mdp, "execute", fake_execute)
    observation = (
        public_records_monitor.probe_maryland_mdp_property_download(
            _context(source_id)
        )
    )

    assert captured.args.command == "probe"
    assert captured.args.source == source_id
    assert captured.args.sample_bytes == 64
    assert captured.kwargs["log_results"] is False
    assert observation.status == "ok"
    assert observation.result_count == 1
    assert observation.schema_sha256 is not None
    assert len(observation.schema_sha256) == 64
    assert observation.artifact_sha256 == "c" * 64
    assert observation.details["selected_data_artifact"] is True
    assert observation.details["schema_reference"] is False
    assert observation.details["release_id"] == _release(
        source_id
    ).release_id


def test_monitor_rejects_a_schema_workbook_as_the_data_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _probe_result(mdp.PARCEL_SOURCE_ID)
    schema_record = {
        **dict(result.records[0]),
        "schema_reference": True,
    }

    def fake_execute(args: Any, **kwargs: Any) -> PublicRecordsResult:
        return PublicRecordsResult.success(
            result.query,
            [schema_record],
            retrieved_at=result.retrieved_at,
        )

    monkeypatch.setattr(mdp, "execute", fake_execute)
    with pytest.raises(ValueError, match="schema-preview artifact"):
        public_records_monitor.probe_maryland_mdp_property_download(
            _context(mdp.PARCEL_SOURCE_ID)
        )


def test_catalog_and_monitor_register_all_three_identity_contracts(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    parcel = catalog.show_source(mdp.PARCEL_SOURCE_ID)[
        "current_manifest"
    ]
    cama = catalog.show_source(mdp.CAMA_SOURCE_ID)["current_manifest"]
    sales = catalog.show_source(mdp.SALES_SOURCE_ID)[
        "current_manifest"
    ]

    assert parcel["record_identity_source_id"] == (
        mdp.SDAT_PROPERTY_IDENTITY_SOURCE_ID
    )
    assert parcel["identity_contract"]["parcel_record_identity"] == (
        "ACCTID"
    )
    assert parcel["identity_contract"]["release_slot_identity"] == [
        "source_id",
        "release_id",
    ]
    assert parcel["identity_contract"][
        "published_link_occurrence_identity"
    ] == ["source_id", "release_id", "provider_link_id"]
    assert cama["identity_contract"]["parcel_join_key"] == "ACCTID"
    assert cama["identity_contract"]["building_subarea_join_key"] == (
        "CAMALINK"
    )
    assert sales["identity_contract"][
        "semantic_transaction_candidate"
    ] == ["ACCTID", "TRADATE", "CONSIDR1"]
    assert sales["identity_contract"][
        "source_issued_transaction_identifier_verified"
    ] is False
    assert sales["identity_contract"][
        "artifact_occurrence_identity"
    ] == "artifact_sha256"
    assert sales["identity_contract"][
        "transport_validator_occurrence_identity"
    ] == "validator_occurrence_id"

    for source_id in mdp.SOURCE_IDS:
        handler = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert handler.handler is (
            public_records_monitor.probe_maryland_mdp_property_download
        )
        assert handler.expected_requests == 3
        assert handler.sample_bytes == 64
