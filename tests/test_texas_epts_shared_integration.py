from __future__ import annotations

import json
from pathlib import Path

import yaml

from tools import query_property
from tools import query_texas_epts as epts


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _source_manifest() -> dict[str, object]:
    config = yaml.safe_load(
        (PROJECT_ROOT / "config/public_records_sources.yaml").read_text(
            encoding="utf-8"
        )
    )
    return next(
        source
        for source in config["sources"]
        if source["source_id"] == epts.SOURCE_ID
    )


def test_catalog_separates_request_acquisition_from_local_processing() -> None:
    source = _source_manifest()
    capabilities = {
        capability["name"]: capability["details"]
        for capability in source["capabilities"]
    }

    assert source["access_class"] == "C"
    assert source["automation_disposition"] == "not_applicable"
    assert source["platform_family"] == (
        "official_public_information_request_and_local_artifact"
    )
    assert capabilities["prepare_public_information_request"][
        "submission_performed"
    ] is False
    assert capabilities["inspect_local_artifact"]["exact_header_validation"] is True
    assert capabilities["parse_local_artifact"][
        "source_occurrences_preserved"
    ] is True
    assert source["implementation_maturity"][
        "delivered_real_world_specimen_validation"
    ] == "pending_first_delivery"


def test_shared_source_guidance_routes_to_the_direct_local_workflow() -> None:
    guidance = query_property._source_guidance(epts.SOURCE_ID)

    assert guidance["mode"] == "request_handoff_and_local_artifact"
    assert guidance["direct_tool"].endswith("tools/query_texas_epts.py --help")
    assert guidance["operations"]["request-plan"].endswith("without submission")
    assert guidance["unified_operations"] == []
    assert "public statewide download was found" in guidance["note"]


def test_property_citation_resolves_to_the_official_source_page() -> None:
    mappings = json.loads(
        (PROJECT_ROOT / "web/src/data/source-urls.json").read_text(
            encoding="utf-8"
        )
    )

    assert mappings[f"PROPERTY_SOURCE:{epts.SOURCE_ID}"] == epts.LANDING_URL
