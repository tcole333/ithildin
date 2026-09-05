from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_jackson_property_events as jackson


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_jackson_property_events"
)


def load_features(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / name).read_text())["features"]


class FakeClient:
    def __init__(
        self,
        config: jackson.SourceConfig,
        features: list[Mapping[str, Any]],
        *,
        page_size: int = 2,
        total_count: int | None = None,
        missing_field: str | None = None,
    ) -> None:
        self.config = config
        self.features = [deepcopy(dict(feature)) for feature in features]
        self.page_size = page_size
        self.total_count = (
            len(self.features) if total_count is None else total_count
        )
        self.missing_field = missing_field
        self.where_calls: list[str] = []

    def fetch_metadata(self) -> dict[str, Any]:
        fields = []
        for name in self.config.required_fields:
            if name == self.missing_field:
                continue
            fields.append(
                {
                    "name": name,
                    "alias": name,
                    "type": (
                        "esriFieldTypeOID"
                        if name == "OBJECTID"
                        else "esriFieldTypeString"
                    ),
                    "nullable": name != "OBJECTID",
                }
            )
        return {
            "id": self.config.layer_id,
            "name": self.config.expected_layer_name,
            "serviceItemId": self.config.service_item_id,
            "geometryType": "esriGeometryPoint",
            "maxRecordCount": 2_000,
            "advancedQueryCapabilities": {
                "supportsOrderBy": True,
                "supportsPagination": True,
            },
            "dateFieldsTimeReference": {
                "timeZone": self.config.source_time_zone,
                "respectsDaylightSaving": (
                    self.config.source_time_respects_daylight_saving
                ),
            },
            "fields": fields,
        }

    def fetch_count(self, where: str) -> int:
        self.where_calls.append(where)
        return self.total_count

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        self.where_calls.append(where)
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        anchor = int(match.group(1)) if match else None
        features = [
            feature
            for feature in self.features
            if anchor is None
            or feature["attributes"]["OBJECTID"] > anchor
        ]
        features.sort(
            key=lambda feature: feature["attributes"]["OBJECTID"],
            reverse=descending,
        )
        return tuple(features[:record_count])


def args_for(*values: str):
    return jackson.build_parser().parse_args(list(values))


def test_sources_keep_three_components_and_complements_distinct():
    payload = jackson.execute(
        args_for("sources"),
        log_results=False,
    )

    assert payload["platform_family"] == (
        "jackson_county_arcgis_property_events"
    )
    assert {source["source_id"] for source in payload["sources"]} == set(
        jackson.SOURCE_IDS
    )
    for source in payload["sources"]:
        complement_kinds = {
            item["kind"] for item in source["complementary_sources"]
        }
        assert "jackson_county_taxlots" in complement_kinds
        assert "accela_record_detail" in complement_kinds
        assert "jackson_county_public_records_request" in complement_kinds
    by_id = {source["source_id"]: source for source in payload["sources"]}
    building_accela = next(
        item
        for item in by_id[jackson.BUILDING_SOURCE_ID][
            "complementary_sources"
        ]
        if item["kind"] == "accela_record_detail"
    )
    code_accela = next(
        item
        for item in by_id[jackson.CODE_SOURCE_ID]["complementary_sources"]
        if item["kind"] == "accela_record_detail"
    )
    assert building_accela["observed_access"].startswith(
        "anonymous_record_detail"
    )
    assert "documents" in building_accela["observed_additional_depth"]
    assert code_accela["observed_access"].startswith(
        "linked_av_route_redirected"
    )
    assert {
        learning["scope"] for learning in payload["process_learnings"]
    } == {
        "component_identity",
        "event_and_observation_identity",
        "detail_depth",
    }


def test_building_normalization_preserves_event_and_observation_identity():
    client = FakeClient(
        jackson.BUILDING,
        load_features("building_sample.json"),
    )
    result = jackson.execute(
        args_for(
            "search",
            "hvac",
            "--field",
            "description",
            "--source",
            jackson.BUILDING_SOURCE_ID,
            "--limit",
            "2",
            "--geometry",
        ),
        client=client,
        access_decision={"review_id": 501, "disposition": "allowed"},
        log_results=False,
    )
    payload = result.to_dict()

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 2
    first, second = payload["records"]
    assert first["native_event_id"] == second["native_event_id"]
    assert first["object_id"] != second["object_id"]
    assert first["canonical_ref"] != second["canonical_ref"]
    assert first["permit"] == {
        "estimated_cost": 500.0,
        "currency": "USD",
    }
    assert first["parcel_join_evidence"]["published_location"] == {
        "raw": "37-2W-23DA-2200",
        "normalized_candidate": "372W23DA2200",
        "source_field": "LOCDESC",
        "basis": "published_taxlot_centroid_location",
    }
    assert first["event_dates"]["submitted"]["utc_date"] == "2026-07-28"
    assert first["geometry_crs"] == "EPSG:4326"
    assert first["detail_representations"][0]["kind"] == (
        "accela_record_detail"
    )
    assert payload["query"]["query"]["metadata"]["access_decision"] == {
        "review_id": 501,
        "disposition": "allowed",
    }


def test_code_compliance_normalization_retains_owner_and_accela_keys():
    client = FakeClient(
        jackson.CODE_COMPLIANCE,
        load_features("code_compliance_sample.json"),
    )
    result = jackson.execute(
        args_for(
            "person",
            "VOLPE",
            "--source",
            jackson.CODE_SOURCE_ID,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["record_kind"] == "code_compliance_observation"
    assert record["people"] == [
        {
            "raw_name": "VOLPE CHRISTOPHER J ET AL",
            "role": "published_owner",
            "assertion_type": "published_property_event",
        }
    ]
    assert record["status"] == "Assigned"
    assert record["event_dates"]["last_update"]["utc_date"] == "2026-07-28"
    assert record["accela_identifiers"] == {
        "perid1": "26CAP",
        "perid2": "00000",
        "perid3": "006IG",
        "case_key": None,
    }
    assert record["raw_attributes"]["VIOLATIONID"] == "439-26-00925-COD"


def test_keyset_cursor_continues_when_component_count_changes():
    features = load_features("building_sample.json")
    first_client = FakeClient(jackson.BUILDING, features, page_size=1)
    first = jackson.execute(
        args_for(
            "search",
            "Residential",
            "--field",
            "type",
            "--source",
            jackson.BUILDING_SOURCE_ID,
            "--limit",
            "1",
        ),
        client=first_client,
        log_results=False,
    ).to_dict()

    assert first["records"][0]["object_id"] == 762838
    assert first["next_cursor"]

    added = deepcopy(features[-1])
    added["attributes"]["OBJECTID"] = 762841
    second_client = FakeClient(
        jackson.BUILDING,
        [*features, added],
        page_size=1,
    )
    second = jackson.execute(
        args_for(
            "search",
            "Residential",
            "--field",
            "type",
            "--source",
            jackson.BUILDING_SOURCE_ID,
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=second_client,
        log_results=False,
    ).to_dict()

    assert second["status"] == "ok"
    assert second["records"][0]["object_id"] == 762839
    assert second["records"][0]["retrieval_snapshot"][
        "count_changed_since_cursor"
    ]
    assert any("count changed" in warning for warning in second["warnings"])
    assert any("OBJECTID > 762838" in where for where in second_client.where_calls)


def test_cursor_is_bound_to_query_criteria():
    client = FakeClient(
        jackson.LAND_USE,
        load_features("land_use_sample.json"),
        page_size=1,
    )
    first = jackson.execute(
        args_for(
            "search",
            "Zoning",
            "--field",
            "type",
            "--source",
            jackson.LAND_USE_SOURCE_ID,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    ).to_dict()
    mismatched = jackson.execute(
        args_for(
            "search",
            "Withdrawn",
            "--field",
            "status",
            "--source",
            jackson.LAND_USE_SOURCE_ID,
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=client,
        log_results=False,
    ).to_dict()

    assert mismatched["status"] == "unavailable"
    assert mismatched["errors"][0]["code"] == "cursor_query_mismatch"


def test_missing_required_field_is_reported_as_source_change():
    client = FakeClient(
        jackson.BUILDING,
        load_features("building_sample.json"),
        missing_field="PERMITID",
    )
    payload = jackson.execute(
        args_for(
            "record",
            "TMP-00001-26-001660",
            "--source",
            jackson.BUILDING_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    ).to_dict()

    assert payload["status"] == "source_changed"
    assert payload["errors"][0]["code"] == "source_schema_changed"
    assert payload["errors"][0]["details"]["missing_fields"] == ["PERMITID"]


def test_probe_reports_stable_contract_and_rolling_boundaries():
    client = FakeClient(
        jackson.CODE_COMPLIANCE,
        load_features("code_compliance_sample.json"),
        total_count=47_616,
    )
    payload = jackson.execute(
        args_for(
            "probe",
            "--source",
            jackson.CODE_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    ).to_dict()
    probe = payload["records"][0]

    assert payload["status"] == "ok"
    assert probe["component_total_count"] == 47_616
    assert probe["service_item_id"] == "0fcc9165da494f1d848bb34d082d29b1"
    assert probe["source_crs"] == "EPSG:6827"
    assert probe["first_ordered_observation"]["object_id"] == 33775
    assert probe["last_ordered_observation"]["object_id"] == 33777
    assert len(probe["complementary_sources"]) == 4


def test_sql_builder_escapes_apostrophes_and_exact_map_taxlot():
    person_where = jackson._where(
        jackson.BUILDING,
        operation="person",
        selector="O'Brien",
        search_field="person",
    )
    map_where = jackson._where(
        jackson.BUILDING,
        operation="map-taxlot",
        selector="37-2W-23DA-2200",
        search_field="map_taxlot",
    )

    assert "O''BRIEN" in person_where
    assert "LIKE" in person_where
    assert map_where == "UPPER(LOCDESC) = '37-2W-23DA-2200'"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for official live probes",
)
@pytest.mark.parametrize("source_id", jackson.SOURCE_IDS)
def test_live_component_probe(source_id):
    payload = jackson.execute(
        args_for(
            "probe",
            "--source",
            source_id,
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    assert payload["records"][0]["component_total_count"] > 0
