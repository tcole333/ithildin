from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import public_records_search_plan
from tools import query_ohio_pax_recorders as pax
from tools import query_property
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_pax_recorders"
)
SOURCE_IDS = {
    pax.DELAWARE_SOURCE_ID,
    pax.LICKING_SOURCE_ID,
    pax.LICKING_DETAIL_SOURCE_ID,
}


def _fixture_text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


class FakeMonitorClient:
    rolling_marker = "first"

    def __init__(self, **_kwargs: Any) -> None:
        self.request_count = 0
        self.closed = False
        self.config = pax.parse_search_config(
            _fixture_text("delaware_search.html"),
            f"{pax.DELAWARE.pax_root}views/search",
        )
        payload = json.loads(_fixture_text("delaware_detail_all.json"))
        batch = pax.parse_detail_response(
            json.dumps(json.dumps(payload)),
            pax.DELAWARE,
            f"{pax.DELAWARE.pax_root}api/SearchDetail",
        )
        self.delaware_record = deepcopy(dict(batch.records[0]))
        self.delaware_record["instrument_number"] = pax.DELAWARE_SENTINEL

    def close(self) -> None:
        self.closed = True

    def entry_access(self, tenant: pax.PAXTenant) -> dict[str, Any]:
        self.request_count += 1
        assert tenant.source_id == pax.LICKING_SOURCE_ID
        return pax.parse_entry_access(
            _fixture_text("licking_entry.html"),
            tenant.pax_root,
        )

    def bootstrap(self, tenant: pax.PAXTenant) -> pax.PAXSessionConfig:
        self.request_count += 2
        assert tenant.source_id == pax.DELAWARE_SOURCE_ID
        return replace(
            self.config,
            version=f"2025.7.7.{self.rolling_marker}",
            data_current_through=(
                "2026-07-19"
                if self.rolling_marker == "first"
                else "2026-07-30"
            ),
        )

    def search_detail(
        self,
        tenant: pax.PAXTenant,
        _selectors: dict[str, Any],
        _config: pax.PAXSessionConfig,
        *,
        first_record: int,
        last_record: int,
    ) -> pax.DetailBatch:
        self.request_count += 1
        assert tenant.source_id == pax.DELAWARE_SOURCE_ID
        assert first_record == 1
        assert last_record > first_record
        record = deepcopy(self.delaware_record)
        return pax.DetailBatch(
            records=(record,),
            total_results=1,
            filtered_results=1,
            first_position=1,
            last_position=1,
            source_url=f"{tenant.pax_root}api/SearchDetail",
        )

    def image_detail(
        self,
        tenant: pax.PAXTenant,
        _config: pax.PAXSessionConfig,
        *,
        reference_id: str,
        instrument: str,
    ) -> dict[str, Any]:
        self.request_count += 1
        assert tenant.source_id == pax.DELAWARE_SOURCE_ID
        return {
            "instrument_reference_id": reference_id,
            "instrument_number": instrument,
            "has_image": True,
            "page_count": 14 if self.rolling_marker == "first" else 15,
            "source_response_schema_fingerprint": "b" * 64,
        }

    def licking_exact(
        self,
        tenant: pax.PAXTenant,
        instrument: str,
    ) -> dict[str, Any]:
        self.request_count += 1
        record = pax.parse_licking_exact(
            _fixture_text("licking_exact.html"),
            (
                "https://apps.lickingcounty.gov/recorder/record-search/"
                f"?instrument={pax.LICKING_SENTINEL}"
            ),
            expected_instrument=pax.LICKING_SENTINEL,
        )
        assert record is not None
        normalized = deepcopy(record)
        normalized["instrument_number"] = instrument
        normalized["source_record_id"] = instrument
        normalized["source_url"] = tenant.exact_detail_url_template.format(
            instrument=instrument
        )
        normalized["page_count"] = (
            1 if self.rolling_marker == "first" else 2
        )
        return normalized

    def document_sample(
        self,
        tenant: pax.PAXTenant,
        instrument: str,
        *,
        sample_bytes: int,
        config: pax.PAXSessionConfig | None = None,
        reference_id: str | None = None,
    ) -> pax.BinaryDocument:
        self.request_count += 1
        assert sample_bytes == 4096
        content = (
            b"%PDF-1.7\n"
            + self.rolling_marker.encode("utf-8")
            + b"\n%%EOF\n"
        )
        if tenant.source_id == pax.DELAWARE_SOURCE_ID:
            assert config is not None
            assert reference_id
            source_url = tenant.pax_root
        else:
            source_url = tenant.exact_document_url_template.format(
                instrument=instrument
            )
        return pax.BinaryDocument(
            content=content,
            source_url=source_url,
            headers={
                "content-type": "application/pdf",
                "content-length": str(len(content)),
                "etag": self.rolling_marker,
            },
        )


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.2},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=(
            None if source_id == pax.LICKING_SOURCE_ID else 4096
        ),
    )


@pytest.mark.parametrize(
    ("source_id", "expected_requests", "sample_bytes"),
    [
        (pax.DELAWARE_SOURCE_ID, 5, 4096),
        (pax.LICKING_SOURCE_ID, 1, None),
        (pax.LICKING_DETAIL_SOURCE_ID, 2, 4096),
    ],
)
def test_monitor_registry_and_component_request_budgets(
    source_id: str,
    expected_requests: int,
    sample_bytes: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pax, "OhioPAXClient", FakeMonitorClient)

    observation = (
        public_records_monitor.probe_ohio_pax_recorder_component(
            _context(source_id)
        )
    )
    spec = public_records_monitor.HANDLER_REGISTRY[source_id]

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert observation.details["rolling_observation"]["requests_made"] == (
        expected_requests
    )
    assert spec.expected_requests == expected_requests
    assert spec.sample_bytes == sample_bytes
    assert spec.handler is (
        public_records_monitor.probe_ohio_pax_recorder_component
    )


def test_monitor_hashes_full_stable_contract_not_rolling_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pax, "OhioPAXClient", FakeMonitorClient)
    source_id = pax.LICKING_DETAIL_SOURCE_ID
    FakeMonitorClient.rolling_marker = "first"
    first = public_records_monitor.probe_ohio_pax_recorder_component(
        _context(source_id)
    )
    FakeMonitorClient.rolling_marker = "second"
    rolling = public_records_monitor.probe_ohio_pax_recorder_component(
        _context(source_id)
    )

    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    assert first.details["stable_contract"] == rolling.details[
        "stable_contract"
    ]
    assert first.details["rolling_observation"] != rolling.details[
        "rolling_observation"
    ]
    assert compare_probes(
        first.to_dict(),
        rolling.to_dict(),
    )["drift_detected"] is False

    original_tenant = pax.TENANTS_BY_QUERY_SOURCE[source_id]
    changed_tenant = replace(
        original_tenant,
        exact_document_url_template=(
            "https://apps.lickingcounty.gov/recorder/record-search/"
            "document-v2?instrument={instrument}"
        ),
    )
    monkeypatch.setitem(
        pax.TENANTS_BY_QUERY_SOURCE,
        source_id,
        changed_tenant,
    )
    contract_change = (
        public_records_monitor.probe_ohio_pax_recorder_component(
            _context(source_id)
        )
    )

    assert contract_change.schema_sha256 == rolling.schema_sha256
    assert contract_change.artifact_sha256 != rolling.artifact_sha256
    assert compare_probes(
        rolling.to_dict(),
        contract_change.to_dict(),
    )["drift_detected"] is True


def test_catalog_census_search_plan_and_shared_operations(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)
    manifests = {
        source_id: catalog.show_source(source_id)["current_manifest"]
        for source_id in SOURCE_IDS
    }

    assert all(
        catalog.require_machine_acquisition(source_id)["allowed"]
        for source_id in SOURCE_IDS
    )
    assert manifests[pax.DELAWARE_SOURCE_ID]["stable_keys"] == [
        "instrument_reference_id"
    ]
    assert manifests[pax.DELAWARE_SOURCE_ID]["identity_contract"][
        "searchable_locators"
    ] == ["instrument_number", "book_page", "document_id"]
    assert manifests[pax.DELAWARE_SOURCE_ID]["identity_contract"][
        "session_and_ticket_values"
    ] == "transport_only"
    assert manifests[pax.LICKING_SOURCE_ID]["identity_contract"][
        "exact_representation_source_id"
    ] == pax.LICKING_DETAIL_SOURCE_ID
    exact_identity = manifests[pax.LICKING_DETAIL_SOURCE_ID][
        "identity_contract"
    ]
    assert exact_identity == {
        "stable_key": "instrument_number",
        "record_identity_source_id": pax.LICKING_SOURCE_ID,
        "representation_source_id": pax.LICKING_DETAIL_SOURCE_ID,
        "independent_corroboration": False,
    }

    route_operations = {
        source_id: set(query_property.LIVE_ROUTES[source_id])
        for source_id in SOURCE_IDS
    }
    for source_id, manifest in manifests.items():
        capability = next(
            item
            for item in manifest["capabilities"]
            if item["name"] == "query_shared_property_records"
        )
        assert set(capability["details"]["shared_operations"]) == (
            route_operations[source_id]
        )

    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        row["source_id"]
        for row in audit["shared_adapter_operation_mismatches"]
    }
    assert not (SOURCE_IDS & mismatches)

    licking_target = next(
        target
        for target in census.list_targets(
            state="OH",
            domain="property",
            role="land_records_index",
        )
        if target["geoid"] == "39089"
    )
    assert {
        pax.LICKING_SOURCE_ID,
        pax.LICKING_DETAIL_SOURCE_ID,
        "us-oh-licking-county-recorder-archives",
    } <= set(licking_target["source_ids"])

    plan = public_records_search_plan.build_search_plan(
        "EXAMPLE LLC",
        jurisdictions=("39089", "39041"),
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
        profiles_dir=tmp_path / "profiles",
    )
    recorder_task_ids = {
        task["task_id"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "recorder"
        for task in stage["tasks"]
    }
    assert {
        (
            "recorder.us-oh-delaware-county-recorder-pax."
            "search_instruments"
        ),
        (
            "recorder.us-oh-licking-county-recorder-pax."
            "search_instruments"
        ),
        (
            "recorder.us-oh-licking-county-recorder-instrument-detail."
            "fetch_instrument"
        ),
    } <= recorder_task_ids


def test_source_urls_docs_and_citation_registry_cover_components() -> None:
    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[f"PROPERTY_SOURCE:{pax.DELAWARE_SOURCE_ID}"] == (
        pax.DELAWARE.pax_root
    )
    assert source_urls[f"PROPERTY_SOURCE:{pax.LICKING_SOURCE_ID}"] == (
        pax.LICKING.pax_root
    )
    assert source_urls[
        f"PROPERTY_SOURCE:{pax.LICKING_DETAIL_SOURCE_ID}"
    ] == "https://apps.lickingcounty.gov/recorder/record-search/"

    source_config = yaml.safe_load(
        (
            ROOT / "config" / "public_records_sources.yaml"
        ).read_text(encoding="utf-8")
    )
    source_ids = [source["source_id"] for source in source_config["sources"]]
    assert all(source_ids.count(source_id) == 1 for source_id in SOURCE_IDS)

    property_docs = (
        ROOT / "docs" / "modules" / "property.md"
    ).read_text(encoding="utf-8")
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    citations = (
        ROOT / "web" / "src" / "lib" / "citations.ts"
    ).read_text(encoding="utf-8")
    for content in (property_docs, tool_reference):
        assert "query_ohio_pax_recorders.py" in content
        assert pax.DELAWARE_SOURCE_ID in content
        assert pax.LICKING_DETAIL_SOURCE_ID in content
        assert "InstrumentReferenceId" in content
    assert "Ohio DTS/PAX recorder adapter and shared lifecycle" in roadmap
    assert 'id: "ohio_pax_record"' in citations
    assert 'id: "ohio_pax_document"' in citations
