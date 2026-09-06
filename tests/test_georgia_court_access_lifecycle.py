from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_georgia_court_access as georgia
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import (
    PublicRecordsResult,
    sha256_fingerprint,
)
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.2},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_record(
    source_id: str,
    marker: str,
    *,
    record_count: int,
) -> dict[str, Any]:
    stable_contract: dict[str, Any] = {
        "source": georgia.SOURCE_METADATA_BY_ID[source_id].to_dict(),
        "jurisdiction": georgia.JURISDICTION.to_dict(),
        "court_identity": {
            "fields": ["county_geoid", "court_class"],
            "format": "GA-COURT:<county_geoid>:<court_class>",
        },
        "record_kind": (
            "case_access_acquisition_handoff"
            if source_id == georgia.EACCESS_SOURCE_ID
            else "efile_provider_directory_entry"
        ),
        "stable_identity": ["canonical_ref"],
        "snapshot_semantics": {
            "snapshot_only": True,
            "case_projection": False,
            "filing_projection": False,
        },
    }
    schema_contract: dict[str, Any] = {
        "record_fields": ["canonical_ref", "court", "source_id"],
        "court_fields": ["county_geoid", "court_class", "court_id"],
        "stable_identity": ["canonical_ref"],
        "snapshot_only": True,
        "case_projection": False,
        "filing_projection": False,
    }
    rolling: dict[str, Any] = {
        "record_count": record_count,
        "court_class_counts": {
            "state": record_count - 159,
            "superior": 159,
        },
        "published_superior_county_count": 159,
        "missing_superior_counties": [],
        "unexpected_superior_counties": [],
        "canonical_court_identity_sha256": marker * 64,
        "source_artifacts": [
            {
                "source_url": georgia.SOURCE_METADATA_BY_ID[
                    source_id
                ].base_url,
                "sha256": marker * 64,
                "byte_length": 100_000 + record_count,
            }
        ],
    }
    if source_id == georgia.EACCESS_SOURCE_ID:
        stable_contract.update(
            {
                "access": {
                    "account_required": True,
                    "directory_handoff": True,
                    "case_search_completed": False,
                },
                "provider_selection_page": {
                    "published_url": georgia.EACCESS_VENDOR_PUBLISHED_URL,
                    "canonical_url": georgia.EACCESS_VENDOR_URL,
                },
            }
        )
        rolling.update(
            {
                "published_route_kind_counts": {
                    "direct_provider": 193,
                    "provider_selection_page": 37,
                },
                "provider_candidate_counts": {
                    "peachcourt": 205,
                    "researchga": 62,
                },
                "source_published_http_routes": [],
                "provider_selection_copy": [
                    "Choose your e-Filing Vendor from the options below."
                ],
            }
        )
        requests_made = 2
    else:
        stable_contract.update(
            {
                "filing": {
                    "account_required_to_initiate": True,
                    "filing_initiated": False,
                    "case_evidence": False,
                },
                "blank_cell_semantics": "not_listed",
            }
        )
        rolling.update(
            {
                "provider_state_counts": {
                    "greenfiling_infotrack": {
                        "available": 59,
                        "not_listed": 171,
                    },
                    "odyssey_efilega": {
                        "available": 2,
                        "mandatory": 59,
                        "not_listed": 169,
                    },
                    "peachcourt": {
                        "mandatory": 209,
                        "not_listed": 21,
                    },
                },
                "listed_provider_route_count": 329,
                "source_published_http_route_count": 61,
                "unexpected_published_states": [],
                "division_qualified_labels": [],
                "published_provider_dates_present": False,
            }
        )
        requests_made = 1
    return {
        "canonical_ref": f"STATECOURT:{source_id}/probe",
        "source_id": source_id,
        "record_kind": "source_probe",
        "status": "ok",
        "source_url": georgia.SOURCE_METADATA_BY_ID[source_id].base_url,
        "snapshot_only": True,
        "stable_contract": stable_contract,
        "schema_contract": schema_contract,
        "stable_schema_sha256": sha256_fingerprint(schema_contract),
        "rolling_observation": rolling,
        "source_snapshot_sha256": marker * 64,
        "requests_made": requests_made,
    }


@pytest.mark.parametrize(
    "source_id",
    [georgia.EACCESS_SOURCE_ID, georgia.EFILE_SOURCE_ID],
)
def test_monitor_separates_contract_from_rolling_directory_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
) -> None:
    state = {"marker": "a", "record_count": 230}
    calls: list[Any] = []

    def fake_execute(args: Any, **_: Any) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.source == source_id
        assert args.minimum_interval == 0.2
        calls.append(args)
        return PublicRecordsResult.success(
            georgia.build_query(args),
            [
                _probe_record(
                    source_id,
                    state["marker"],
                    record_count=state["record_count"],
                )
            ],
        )

    monkeypatch.setattr(georgia, "execute", fake_execute)

    first = public_records_monitor.probe_georgia_court_access_directory(
        _context(source_id)
    )
    state.update(marker="b", record_count=231)
    second = public_records_monitor.probe_georgia_court_access_directory(
        _context(source_id)
    )

    assert len(calls) == 2
    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.result_count == 230
    assert second.result_count == 231
    assert first.details["requests_made"] == (
        2 if source_id == georgia.EACCESS_SOURCE_ID else 1
    )


def test_catalog_census_and_shared_operations_match_directory_contracts(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    eaccess = catalog.show_source(
        georgia.EACCESS_SOURCE_ID
    )["current_manifest"]
    efile = catalog.show_source(
        georgia.EFILE_SOURCE_ID
    )["current_manifest"]

    for source_id, manifest in (
        (georgia.EACCESS_SOURCE_ID, eaccess),
        (georgia.EFILE_SOURCE_ID, efile),
    ):
        assert catalog.require_machine_acquisition(source_id)[
            "allowed"
        ] is True
        assert manifest["stable_keys"] == ["canonical_ref"]
        assert manifest["identity_contract"][
            "source_identity_fields"
        ] == ["canonical_ref"]
        assert manifest["identity_contract"]["storage_semantics"] == (
            "source_snapshot_only"
        )
        assert manifest["identity_contract"]["case_projection"] is False
        assert manifest["identity_contract"]["filing_projection"] is False
        capabilities = {
            item["name"]: item["details"]
            for item in manifest["capabilities"]
        }
        assert capabilities["query_shared_court_records"][
            "shared_operations"
        ] == ["search", "discovery", "probe"]
        assert capabilities["ingest_state_court_records"][
            "projection"
        ] == "source_snapshot_only"
        assert capabilities["ingest_state_court_records"][
            "case_rows_created"
        ] is False
        association = manifest["census_associations"][0]
        assert association["jurisdiction_geoid"] == "13"
        assert association["role"] == "court_directory"
        assert association["coverage"]["snapshot_only"] is True
        assert association["coverage"][
            "published_superior_county_count"
        ] == 159
        assert all(
            complement["dataset_equivalent"] is False
            for complement in manifest["official_complements"]
        )

    assert eaccess["publication_contract"][
        "case_search_completed"
    ] is False
    assert eaccess["endpoints"]["provider_selection_published"] == (
        georgia.EACCESS_VENDOR_PUBLISHED_URL
    )
    assert eaccess["probe_evidence"]["observed_record_count"] == 230
    assert eaccess["probe_evidence"][
        "source_published_http_route_count"
    ] == 2

    assert efile["publication_contract"]["blank_cell_semantics"] == (
        "not_listed"
    )
    assert efile["publication_contract"]["filing_initiated"] is False
    assert efile["publication_contract"]["case_evidence"] is False
    assert efile["endpoints"]["odyssey_efilega"] == (
        georgia.ODYSSEY_EFILEGA_URL
    )
    assert efile["probe_evidence"]["provider_state_counts"][
        "peachcourt"
    ] == {"mandatory": 209, "not_listed": 21}

    audit = audit_catalog(db_path=catalog_path)
    mismatched_sources = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert not set(georgia.SOURCE_IDS) & mismatched_sources


def test_monitor_registry_has_source_specific_request_budgets() -> None:
    eaccess = public_records_monitor.HANDLER_REGISTRY[
        georgia.EACCESS_SOURCE_ID
    ]
    efile = public_records_monitor.HANDLER_REGISTRY[
        georgia.EFILE_SOURCE_ID
    ]

    assert eaccess.handler is (
        public_records_monitor.probe_georgia_court_access_directory
    )
    assert eaccess.endpoint == georgia.EACCESS_URL
    assert eaccess.expected_requests == 2
    assert eaccess.sentinel_record_count == 1

    assert efile.handler is (
        public_records_monitor.probe_georgia_court_access_directory
    )
    assert efile.endpoint == georgia.EFILE_URL
    assert efile.expected_requests == 1
    assert efile.sentinel_record_count == 1


def test_citations_and_docs_cover_both_directory_sources() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{georgia.EACCESS_SOURCE_ID}"
    ] == georgia.EACCESS_URL
    assert source_urls[
        f"STATECOURT_SOURCE:{georgia.EFILE_SOURCE_ID}"
    ] == georgia.EFILE_URL

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## Georgia AOC eAccess and eFile provider directories" in legal
    assert "blank provider cells are represented as `not_listed`" in legal
    assert "### Georgia AOC court-access provider directories" in (
        tool_reference
    )
    assert georgia.EACCESS_SOURCE_ID in tool_reference
    assert georgia.EFILE_SOURCE_ID in tool_reference
    assert "Georgia AOC eAccess and eFile provider routing" in roadmap
    assert "routing-matrix absence and presentation anomalies" in roadmap
