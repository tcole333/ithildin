from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_palm_beach_property_appraiser as palm
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "palm_beach_property_appraiser"
)


def _metadata() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8"))


def _features() -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / "features.json").read_text(encoding="utf-8"))


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=palm.SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_keeps_rolling_counts_and_sample_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 3

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 0

        def fetch_metadata(self, layer_url=palm.LAYER_URL):
            self.request_count += 1
            metadata = _metadata()
            if layer_url == palm.QSALES_LAYER_URL:
                metadata["id"] = 0
                metadata["name"] = palm.QSALES_LAYER_NAME
                metadata["maxRecordCount"] = 2_000
            return metadata

        def fetch_count(
            self,
            where,
            *,
            parameters=None,
            query_url=palm.QUERY_URL,
        ):
            del parameters
            self.request_count += 1
            if where == "PARID IS NULL":
                return 0
            if query_url == palm.QSALES_QUERY_URL:
                return marker
            return marker

        def fetch_distinct_count(self, field_name, *, query_url=palm.QUERY_URL):
            del query_url
            self.request_count += 1
            return marker - (1 if field_name == "PARID" else 0)

    def fake_batch(client, **_kwargs):
        client.request_count += 4
        metadata = _metadata()
        contract = palm.metadata_contract(metadata)
        feature = _features()[0]
        feature["attributes"]["OBJECTID"] = marker
        return palm.FeatureBatch(
            features=(feature,),
            contract=contract,
            boundary_object_id=marker,
            total_count=marker,
            next_cursor=None,
            requests_made=4,
        )

    monkeypatch.setattr(palm, "PalmBeachPropertyClient", FakeClient)
    monkeypatch.setattr(palm, "fetch_feature_batch", fake_batch)

    first = public_records_monitor.probe_palm_beach_property_appraiser(
        _context()
    )
    marker = 4
    second = public_records_monitor.probe_palm_beach_property_appraiser(
        _context()
    )

    assert first.status == "ok"
    assert first.result_count == 3
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["schema_contract"] == second.details["schema_contract"]
    assert first.details["rolling_observation"] != (
        second.details["rolling_observation"]
    )
    assert first.details["requests_made"] == 11
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    comparison = compare_probes(
        {
            "probe_id": 1,
            "status": first.status,
            "schema_sha256": first.schema_sha256,
            "artifact_sha256": first.artifact_sha256,
        },
        {
            "probe_id": 2,
            "status": second.status,
            "schema_sha256": second.schema_sha256,
            "artifact_sha256": second.artifact_sha256,
        },
    )
    assert comparison["drift_detected"] is False


def test_catalog_census_and_handler_capture_operation_specific_access(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    decision = catalog.require_machine_acquisition(palm.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    manifest = catalog.show_source(palm.SOURCE_ID)["current_manifest"]
    assert manifest["source_status"] == "active"
    assert manifest["stable_keys"] == ["objectid_feature_occurrence"]
    assert manifest["operation_access"] == {
        "parcel_details_metadata": "anonymous",
        "parcel_details_query": "anonymous",
        "parcel_details_statistics": "anonymous",
        "qsales_metadata_and_query": "anonymous",
        "advertised_flat_file_directory": "public_page",
        "current_cloud_drive_flat_file_transfer": (
            "consent_discrepancy_not_automated"
        ),
    }
    assert manifest["identity_contract"][
        "candidate_exact_tax_account_join"
    ] == "PARCEL_NUMBER"
    assert manifest["identity_contract"]["published_geometry_or_group_identifier"] == (
        "PARID"
    )
    assert manifest["identity_contract"][
        "candidate_parcel_join_uniqueness_assumed"
    ] is False
    assert manifest["representations"][1]["independent_corroboration"] is False
    assert manifest["transport_contract"][
        "service_max_record_count_is_transport_page_size_not_result_cap"
    ] is True
    assert manifest["probe_evidence"]["rolling_observations"][
        "counts_are_snapshot_observations_not_stable_contract"
    ] is True

    for role in ("assessment_roll", "parcel_geometry"):
        targets = census.list_targets(
            state="FL",
            domain="property",
            role=role,
        )
        assert any(palm.SOURCE_ID in target["source_ids"] for target in targets)

    handler = public_records_monitor.HANDLER_REGISTRY[palm.SOURCE_ID]
    assert handler.handler is (
        public_records_monitor.probe_palm_beach_property_appraiser
    )
    assert handler.expected_requests == 11
    assert handler.sample_bytes is None


def test_docs_and_citation_capture_verified_contract_and_alternatives() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"PROPERTY_SOURCE:{palm.SOURCE_ID}"] == palm.LAYER_URL

    module = (ROOT / "docs" / "modules" / "property.md").read_text(
        encoding="utf-8"
    )
    reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    for text in (module, reference, roadmap):
        assert "query_palm_beach_property_appraiser.py" in text
        assert "QSALES" in text
        assert "CONFID_FLG" in text
    assert "04-36-43-25-00-000-5040" in module
    assert "consent" in module.casefold()
    assert "same-publisher" in roadmap
