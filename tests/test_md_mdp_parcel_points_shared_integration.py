from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_md_mdp_parcel_points as mdp
from tools import query_property
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import sha256_fingerprint
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=mdp.SOURCE_ID,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_shared_routes_keep_record_and_occurrence_identity_distinct() -> None:
    routes = query_property.LIVE_ROUTES[mdp.SOURCE_ID]
    guidance = query_property._source_guidance(mdp.SOURCE_ID)

    assert sorted(routes) == [
        "account",
        "address",
        "bbox",
        "count",
        "discovery",
        "freshness",
        "land-use",
        "map",
        "parcel",
        "point",
        "probe",
        "search",
        "survey",
    ]
    assert guidance["record_identity"] == {
        "source_id": mdp.RECORD_IDENTITY_SOURCE_ID,
        "field": "ACCTID",
        "relationship": "exact_cross_representation_parcel_account_join",
    }
    assert guidance["feature_occurrence_identity"] == "OBJECTID"
    assert "not independent corroboration" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "selector", "adapter_command", "native_command"),
    [
        ("account", "1901000047", "account", "account"),
        ("parcel", "1901000047", "account", "account"),
        ("address", "100 MAIN ST", "address", "address"),
        ("map", "1901000047", "map", "account"),
        ("land-use", "R", "land-use", "query"),
        ("survey", "1234", "survey", "query"),
        ("bbox", "-76.8,38.1,-76.5,38.4", "bbox", "bbox"),
    ],
)
def test_shared_routes_translate_statewide_selectors(
    operation: str,
    selector: str,
    adapter_command: str,
    native_command: str,
) -> None:
    translated = query_property._md_mdp_parcel_points_args(
        _parse(
            operation,
            selector,
            "--source",
            mdp.SOURCE_ID,
            "--jurisdiction",
            "24037",
            "--limit",
            "7",
            "--cursor",
            "cursor-value",
            "--minimum-interval",
            "0.4",
        ),
        adapter_command,
    )

    assert translated.command == native_command
    assert translated.county_code == "19"
    assert translated.limit == 7
    assert translated.cursor == "cursor-value"
    assert translated.minimum_interval == 0.4
    assert translated.geometry is (operation == "map")


def test_shared_search_preserves_acctid_local_parcel_and_objectid_roles() -> None:
    account = query_property._md_mdp_parcel_points_args(
        _parse(
            "search",
            "1901000047",
            "--source",
            mdp.SOURCE_ID,
            "--search-field",
            "acctid",
        ),
        "search",
    )
    local_parcel = query_property._md_mdp_parcel_points_args(
        _parse(
            "search",
            "0042",
            "--source",
            mdp.SOURCE_ID,
            "--search-field",
            "local-parcel",
        ),
        "search",
    )
    occurrence = query_property._md_mdp_parcel_points_args(
        _parse(
            "search",
            "42",
            "--source",
            mdp.SOURCE_ID,
            "--search-field",
            "objectid",
        ),
        "search",
    )

    assert (account.command, account.selector) == ("account", "1901000047")
    assert (local_parcel.command, local_parcel.selector) == ("parcel", "0042")
    assert (occurrence.command, occurrence.objectid) == ("objectid", 42)


def test_shared_point_flags_count_filters_and_county_names_are_supported() -> None:
    point = query_property._md_mdp_parcel_points_args(
        _parse(
            "point",
            "--source",
            mdp.SOURCE_ID,
            "--longitude",
            "-76.63",
            "--latitude",
            "38.30",
            "--county",
            "St. Mary's County",
            "--geometry",
        ),
        "point",
    )
    count = query_property._md_mdp_parcel_points_args(
        _parse(
            "count",
            "R",
            "--source",
            mdp.SOURCE_ID,
            "--search-field",
            "zoning",
            "--county-code",
            "19",
        ),
        "count",
    )

    assert (point.longitude, point.latitude) == (-76.63, 38.3)
    assert point.county_code == "19"
    assert point.geometry is True
    assert count.command == "count"
    assert count.zoning == "R"
    assert count.county_code == "19"


def test_monitor_separates_stable_contract_from_rolling_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 10

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 0

        def fetch_metadata(self) -> dict[str, Any]:
            self.request_count += 1
            return {"name": mdp.LAYER_NAME}

    contract = SimpleNamespace(
        schema_fingerprint="a" * 64,
        field_names=mdp.REQUIRED_FIELDS,
        object_id_field=mdp.OBJECT_ID_FIELD,
        geometry_type=mdp.GEOMETRY_TYPE,
        spatial_reference={"wkid": 4326},
        max_record_count=2_000,
    )

    def fake_probe(client, _metadata, _contract):
        client.request_count += 3
        return {
            "source_id": mdp.SOURCE_ID,
            "rolling_observations": {
                "feature_count": marker,
                "maximum_object_id": marker + 100,
                "sample": {"OBJECTID": marker},
            },
        }

    monkeypatch.setattr(mdp, "MarylandParcelPointsClient", FakeClient)
    monkeypatch.setattr(mdp, "metadata_contract", lambda _metadata: contract)
    monkeypatch.setattr(mdp, "_probe_record", fake_probe)

    first = public_records_monitor.probe_maryland_mdp_parcel_points(_context())
    marker = 11
    second = public_records_monitor.probe_maryland_mdp_parcel_points(_context())

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["rolling_observation"] != second.details["rolling_observation"]
    assert first.details["requests_made"] == 4
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


def test_catalog_handler_docs_and_citation_capture_the_source(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = catalog.show_source(mdp.SOURCE_ID)["current_manifest"]

    assert manifest["record_identity_source_id"] == mdp.RECORD_IDENTITY_SOURCE_ID
    assert manifest["identity_contract"] == {
        "feature_occurrence_identity": "OBJECTID",
        "cross_representation_record_identity": "ACCTID",
        "record_identity_source_id": mdp.RECORD_IDENTITY_SOURCE_ID,
        "local_map_grid_parcel_plat_values": "typed_published_coordinates",
        "related_representation_independent_corroboration": False,
    }
    assert manifest["publication_contract"]["current_owner_name_field_present"] is False
    handler = public_records_monitor.HANDLER_REGISTRY[mdp.SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_maryland_mdp_parcel_points
    assert handler.expected_requests == 4

    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"PROPERTY_SOURCE:{mdp.SOURCE_ID}"] == mdp.LAYER_URL

    for relative_path in (
        "docs/modules/property.md",
        "docs/TOOL_REFERENCE.md",
        "docs/PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md",
        "research/OSINT_RESOURCES.md",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "query_md_mdp_parcel_points.py" in content
        assert mdp.SOURCE_ID in content
        assert "ACCTID" in content
        assert "OBJECTID" in content
