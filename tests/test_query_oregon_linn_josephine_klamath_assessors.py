from __future__ import annotations

import copy
import json
import os
import re
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_linn_josephine_klamath_assessors as adapter
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import TransportError


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_linn_josephine_klamath_assessors"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text())


def _feature_name(config: adapter.SourceConfig) -> str:
    return {
        adapter.LINN_SOURCE_ID: "linn_feature",
        adapter.JOSEPHINE_SOURCE_ID: "josephine_feature",
        adapter.KLAMATH_SOURCE_ID: "klamath_feature",
    }[config.source_id]


def _feature(config: adapter.SourceConfig) -> dict[str, Any]:
    return _fixture(_feature_name(config))


def _declared_field_names(config: adapter.SourceConfig) -> set[str]:
    fields = set(config.required_fields)
    fields.update(config.native_id_fields)
    fields.update(config.update_fields)
    for columns in config.search_fields.values():
        fields.update(column.name for column in columns)
    mapping = config.fields
    for value in (
        mapping.accounts,
        mapping.map_taxlots,
        mapping.owners,
        mapping.mailing_lines,
        mapping.acreage,
        mapping.property_class,
    ):
        fields.update(value)
    for value in (
        mapping.mailing_city,
        mapping.mailing_state,
        mapping.mailing_zip,
        mapping.mailing_csz,
        mapping.situs,
        mapping.situs_city,
        mapping.situs_state,
        mapping.situs_zip,
        mapping.assessed_value,
        mapping.market_value,
        mapping.market_land,
        mapping.market_improvements,
        mapping.sale_price,
        mapping.sale_date,
        mapping.sale_year,
        mapping.sale_month,
        mapping.instrument,
        mapping.deed_type,
        mapping.sale_type,
        mapping.year_built,
        mapping.property_type,
        mapping.legal,
        mapping.tax_amount,
        mapping.tax_code,
        *mapping.native_links.values(),
    ):
        if value:
            fields.add(value)
    return fields


def _metadata(config: adapter.SourceConfig) -> dict[str, Any]:
    return {
        "name": config.expected_layer_name,
        "serviceItemId": config.service_item_id,
        "objectIdField": (
            None if config is adapter.LINN else config.object_id_field
        ),
        "geometryType": "esriGeometryPolygon",
        "maxRecordCount": config.max_page_size,
        "extent": {"spatialReference": {"wkid": config.source_wkid}},
        "advancedQueryCapabilities": {
            "supportsPagination": True,
            "supportsOrderBy": True,
        },
        "fields": [
            {
                "name": field_name,
                "alias": field_name,
                "type": (
                    "esriFieldTypeOID"
                    if field_name == config.object_id_field
                    else "esriFieldTypeString"
                ),
            }
            for field_name in sorted(_declared_field_names(config))
        ],
        "editingInfo": (
            {
                "lastEditDate": 1784961975133,
                "schemaLastEditDate": 1784961975133,
                "dataLastEditDate": 1784961975133,
            }
            if config is adapter.KLAMATH
            else None
        ),
    }


def _args(
    command: str = "scan",
    *,
    source: str = adapter.LINN_SOURCE_ID,
    query: str | None = None,
    **overrides: Any,
) -> Namespace:
    values = {
        "command": command,
        "source": source,
        "query": query,
        "field": "all" if command == "scan" else command,
        "limit": 100,
        "cursor": None,
        "geometry": False,
        "page_size": 2,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "retry_attempts": 1,
        "all_sources": False,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


class FakeClient:
    def __init__(
        self,
        config: adapter.SourceConfig,
        features: list[Mapping[str, Any]],
        *,
        metadata: Mapping[str, Any] | Exception | None = None,
        item_metadata: Mapping[str, Any] | None = None,
        page_size: int = 2,
    ) -> None:
        self.config = config
        self.features = sorted(
            copy.deepcopy(features),
            key=lambda row: row["attributes"][config.object_id_field],
        )
        self.metadata = (
            metadata
            if isinstance(metadata, Exception)
            else copy.deepcopy(metadata or _metadata(config))
        )
        self.item_metadata = copy.deepcopy(item_metadata)
        self.page_size = page_size
        self.calls: list[tuple[str, Any]] = []

    def fetch_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("metadata", None))
        if isinstance(self.metadata, Exception):
            raise self.metadata
        return self.metadata

    def fetch_item_metadata(self) -> Mapping[str, Any] | None:
        self.calls.append(("item", None))
        return self.item_metadata

    def _rows(self, where: str) -> list[Mapping[str, Any]]:
        match = re.search(r"\bOBJECTID\s*>\s*(\d+)", where)
        anchor = int(match.group(1)) if match else -1
        return [
            row
            for row in self.features
            if row["attributes"]["OBJECTID"] > anchor
        ]

    def fetch_count(self, where: str) -> int:
        self.calls.append(("count", where))
        return len(self._rows(where))

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        out_fields: str = "*",
    ) -> tuple[Mapping[str, Any], ...]:
        self.calls.append(
            (
                "page",
                {
                    "where": where,
                    "record_count": record_count,
                    "return_geometry": return_geometry,
                    "out_fields": out_fields,
                },
            )
        )
        rows = copy.deepcopy(self._rows(where)[:record_count])
        if not return_geometry:
            for row in rows:
                row.pop("geometry", None)
        return tuple(rows)

    def fetch_latest_update(self, field_name: str) -> Mapping[str, Any] | None:
        self.calls.append(("latest_update", field_name))
        candidates = [
            row
            for row in self.features
            if row["attributes"].get(field_name) is not None
        ]
        return copy.deepcopy(candidates[-1]) if candidates else None


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "log_search", lambda *_args, **_kwargs: None)


def test_verified_source_packet_retains_three_distinct_county_identities() -> None:
    packet = _fixture("verified_sources")

    assert packet["observed_at"] == "2026-07-29"
    assert set(packet["sources"]) == set(adapter.SOURCES)
    assert len({config.county_geoid for config in adapter.SOURCES.values()}) == 3
    for config in adapter.SOURCES.values():
        observed = packet["sources"][config.source_id]
        assert observed["county_geoid"] == config.county_geoid
        assert observed["layer_name"] == config.expected_layer_name
        assert observed["service_item_id"] == config.service_item_id
        assert observed["count"] == config.baseline_count
        assert observed["max_record_count"] == config.max_page_size
        assert observed["source_wkid"] == config.source_wkid
        assert (
            observed["schema_fingerprint"]
            == config.expected_schema_fingerprint
        )
        assert observed["supported_query_formats"] == ["JSON", "geoJSON", "PBF"]


def test_wrong_state_same_name_candidate_is_rejected_by_positive_evidence() -> None:
    fixture = _fixture("benton_washington_false_lead")
    expected = fixture["expected_oregon_identity"]

    evidence = adapter.candidate_jurisdiction_evidence(
        fixture["candidate"],
        expected_extent=tuple(expected["expected_extent"]),
        official_hosts=expected["official_hosts"],
    )

    assert fixture["candidate"]["title"] == "Benton_County_Parcels"
    assert evidence["owner"] == "YakimaGIS"
    assert evidence["official_host_matches"] is False
    assert evidence["extent_matches"] is False
    assert evidence["verified"] is False
    assert (
        evidence["decision_basis"]
        == "insufficient_positive_jurisdiction_evidence"
    )


@pytest.mark.parametrize("config", (adapter.LINN, adapter.KLAMATH))
def test_selected_item_identity_has_positive_jurisdiction_evidence(
    config: adapter.SourceConfig,
) -> None:
    item = _fixture("verified_sources")["sources"][config.source_id]["item"]
    identity = adapter._item_identity(config, item)

    assert identity["item_id"] == config.service_item_id
    assert identity["jurisdiction_evidence"]["extent_matches"] is True
    assert identity["jurisdiction_evidence"]["verified"] is True


def test_josephine_identity_uses_official_host_and_layer_service_item() -> None:
    identity = adapter._item_identity(adapter.JOSEPHINE, None)

    assert identity["item_id"] == adapter.JOSEPHINE_ITEM_ID
    assert identity["identity_source"] == (
        "layer_serviceItemId_and_official_county_host"
    )
    assert identity["jurisdiction_evidence"]["official_service_host"] == (
        "gis.co.josephine.or.us"
    )


def test_linn_normalization_preserves_owner_values_sale_updates_and_native_row() -> None:
    record = adapter._normalize_feature(
        adapter.LINN,
        _feature(adapter.LINN),
        schema_value=adapter.LINN.expected_schema_fingerprint,
        geometry_requested=True,
    )

    assert record["native_id"] == "16S04W03 00101"
    assert record["assessment_account_ids"] == ["761920"]
    assert record["owners"][0]["raw_name"] == "BEAR THAREN J & MARCIA"
    assert record["mailing_address"]["raw"] == "30595 WYATT DR"
    assert record["situs_address"]["raw"] == "30595 WYATT DR"
    assert record["assessment"]["assessed_value"] == 308457
    assert record["assessment"]["market_or_appraised_total"] == 872860
    assert record["assessment"]["market_or_appraised_land"] == 439320
    assert record["assessment"]["market_or_appraised_improvements"] == 433540
    assert record["sale"]["price"] == 797500
    assert record["sale"]["date"]["date_iso"] == "2019-10"
    assert record["sale"]["date"]["precision"] == "month"
    assert record["sale"]["instrument"] == "2019-17518"
    assert record["update_evidence"]["observations"][0]["source_field"] == (
        "LASTUPDATE"
    )
    assert record["source_geometry_crs"] == "EPSG:2913"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["native_fields"]["UNMAPPED_NATIVE_NOTE"] == "retained verbatim"


def test_josephine_normalization_preserves_tax_sale_and_detail_join() -> None:
    record = adapter._normalize_feature(
        adapter.JOSEPHINE,
        _feature(adapter.JOSEPHINE),
        schema_value=adapter.JOSEPHINE.expected_schema_fingerprint,
        geometry_requested=True,
    )

    assert record["native_id"] == "R333020"
    assert record["map_taxlot_ids"] == [
        "41091400000709",
        "4109140000070900",
        "000709",
    ]
    assert record["owners"][0]["raw_name"] == "JACKSON, BILLY JO"
    assert record["assessment"]["assessed_value"] == 66650
    assert record["assessment"]["market_or_appraised_total"] == 167030
    assert record["sale"]["date"]["date_iso"] == "2018-07-13"
    assert record["sale"]["price"] == 50000
    assert record["sale"]["instrument"] == "18-008857"
    assert record["sale"]["deed_type"] == "WD"
    assert record["tax"]["published_amount"] == 569.68
    assert record["official_links"]["property_detail"].endswith("/R333020")
    assert (
        record["update_evidence"]["explicit_row_update_field_published"]
        is False
    )
    assert record["native_fields"]["UNMAPPED_NATIVE_NOTE"] == "retained verbatim"


def test_klamath_normalization_preserves_assessor_recorder_and_tax_map_links() -> None:
    record = adapter._normalize_feature(
        adapter.KLAMATH,
        _feature(adapter.KLAMATH),
        schema_value=adapter.KLAMATH.expected_schema_fingerprint,
        geometry_requested=True,
    )

    assert record["native_id"] == "871965"
    assert record["map_taxlot_ids"] == [
        "4114-00500-00401",
        "1841.00S14.00E0500--000000401",
        "41S14E0500",
        "41S14E05",
    ]
    assert record["owners"][0]["raw_name"] == (
        "JOHNSON THOMAS E & JOHNSON BECKY L"
    )
    assert record["assessment"]["assessed_value"] == 70924
    assert record["assessment"]["market_or_appraised_total"] == 348160
    assert record["sale"]["date"]["date_iso"] == "2006-08-11"
    assert record["sale"]["price"] == 305000
    assert set(record["official_links"]) == {
        "property_detail",
        "recorder_document",
        "current_tax_map",
        "historical_tax_map",
    }
    rdate = record["update_evidence"]["observations"][0]
    assert rdate == {
        "source_field": "RDATE",
        "raw_value": 20260724,
        "normalized": "2026-07-24",
        "value_kind": "source_date",
    }
    assert record["native_fields"]["UNMAPPED_NATIVE_NOTE"] == "retained verbatim"


def test_search_sql_uses_each_countys_native_fields_and_escapes_quotes() -> None:
    linn = adapter._where(
        adapter.LINN,
        selector="O'Brien",
        search_field="owner",
    )
    josephine = adapter._where(
        adapter.JOSEPHINE,
        selector="R333020",
        search_field="account",
    )
    klamath = adapter._where(
        adapter.KLAMATH,
        selector="871965",
        search_field="account",
    )

    assert "UPPER(OWNER1) LIKE '%O''BRIEN%'" in linn
    assert josephine == "UPPER(ACCOUNT) = 'R333020'"
    assert klamath == "PROP_ID = 871965"


def test_keyset_cursor_resumes_after_object_id_without_offset_drift() -> None:
    rows = []
    for oid in range(1, 6):
        row = _feature(adapter.LINN)
        row["attributes"]["OBJECTID"] = oid
        row["attributes"]["PIN"] = f"PIN-{oid}"
        rows.append(row)
    client = FakeClient(adapter.LINN, rows, page_size=1)

    first = adapter.execute(
        _args(limit=2, page_size=1),
        client=client,
        log_results=False,
    )
    assert isinstance(first, PublicRecordsResult)
    first_payload = first.to_dict()
    assert [row["object_id"] for row in first_payload["records"]] == [1, 2]
    assert first_payload["next_cursor"]
    assert first_payload["records"][0]["retrieval_snapshot"] == {
        "total_matching_records": 5,
        "start_object_id_exclusive": None,
        "end_object_id_inclusive": 2,
        "returned_records": 2,
        "remaining_after_anchor": 3,
        "continuation_available": True,
        "pages_fetched": 2,
        "schema_fingerprint": first_payload["records"][0]["provenance"][
            "schema_fingerprint"
        ],
        "service_data_last_edit": None,
    }

    second = adapter.execute(
        _args(limit=2, page_size=1, cursor=first_payload["next_cursor"]),
        client=client,
        log_results=False,
    )
    second_payload = second.to_dict()
    assert [row["object_id"] for row in second_payload["records"]] == [3, 4]
    page_calls = [details for kind, details in client.calls if kind == "page"]
    assert "OBJECTID > 2" in page_calls[2]["where"]
    assert all("resultOffset" not in details for details in page_calls)


def test_cursor_is_bound_to_source_and_query() -> None:
    rows = []
    for oid in (1, 2):
        row = _feature(adapter.LINN)
        row["attributes"]["OBJECTID"] = oid
        row["attributes"]["PIN"] = f"PIN-{oid}"
        rows.append(row)
    first = adapter.execute(
        _args(limit=1),
        client=FakeClient(adapter.LINN, rows),
        log_results=False,
    ).to_dict()
    result = adapter.execute(
        _args(
            command="owner",
            query="BEAR",
            limit=1,
            cursor=first["next_cursor"],
        ),
        client=FakeClient(adapter.LINN, [_feature(adapter.LINN)]),
        log_results=False,
    ).to_dict()

    assert result["status"] == "source_changed"
    assert result["errors"][0]["code"] == "cursor_query_mismatch"


def test_probe_packet_contains_schema_count_update_and_complement_evidence() -> None:
    verified = _fixture("verified_sources")
    for config in (adapter.LINN, adapter.JOSEPHINE, adapter.KLAMATH):
        item = verified["sources"][config.source_id]["item"]
        result = adapter.execute(
            _args(
                command="probe",
                source=config.source_id,
                query=None,
            ),
            client=FakeClient(config, [_feature(config)], item_metadata=item),
            log_results=False,
        )
        payload = result.to_dict()
        assert payload["status"] == "ok"
        record = payload["records"][0]
        assert record["layer_identity"]["object_id_field"] == "OBJECTID"
        assert record["component_total_count"] == 1
        assert record["source_crs"] == config.source_crs
        assert record["schema_fingerprint"]
        assert record["representative_row"]["geometry_crs"] == "EPSG:4326"
        assert record["complementary_sources"]


def test_transport_failure_is_not_reported_as_no_results() -> None:
    result = adapter.execute(
        _args(),
        client=FakeClient(
            adapter.LINN,
            [],
            metadata=TransportError("offline", url=adapter.LINN.layer_url),
        ),
        log_results=False,
    ).to_dict()

    assert result["status"] == "unavailable"
    assert result["records"] == []
    assert result["errors"][0]["code"] == "transport_error"


def test_sources_expose_native_update_fields_and_useful_official_complements() -> None:
    payload = adapter.execute(_args(command="sources", query=None))

    assert isinstance(payload, dict)
    assert adapter.CATALOG_METADATA is adapter.SOURCE_CATALOG_METADATA
    assert payload["source_family_id"] == adapter.SOURCE_FAMILY_ID
    assert payload["umbrella_source_id"] == adapter.SOURCE_FAMILY_ID
    assert payload["umbrella_source_id_is_external_source"] is False
    assert not adapter.SOURCE_FAMILY_ID.startswith("us-")
    assert {source["source_id"] for source in payload["sources"]} == set(
        adapter.SOURCES
    )
    assert {
        learning["scope"] for learning in payload["process_learnings"]
    } >= {
        "jurisdiction_validation",
        "county_field_maps",
        "paging",
        "complementary_records",
    }
    klamath = next(
        source
        for source in payload["sources"]
        if source["source_id"] == adapter.KLAMATH_SOURCE_ID
    )
    assert klamath["update_fields"] == ["RDATE", "DDate", "Heliondate"]
    assert {
        source["source_id"] for source in klamath["complementary_sources"]
    } >= {
        adapter.KLAMATH_PROPERTY_DETAIL_SOURCE_ID,
        adapter.KLAMATH_TAX_MAP_SOURCE_ID,
        adapter.KLAMATH_RECORDER_SOURCE_ID,
        adapter.KLAMATH_RECORDS_REQUEST_SOURCE_ID,
    }


@pytest.mark.skipif(
    os.environ.get("RUN_OREGON_ASSESSOR_LIVE") != "1",
    reason="set RUN_OREGON_ASSESSOR_LIVE=1 for official endpoint probes",
)
def test_live_probe_all_three_official_sources() -> None:
    payload = adapter.execute(
        _args(command="probe", query=None, all_sources=True),
        log_results=False,
    )

    assert isinstance(payload, dict)
    assert payload["status"] == "ok"
    assert len(payload["components"]) == 3
    for component in payload["components"]:
        assert component["status"] == "ok"
        probe = component["records"][0]
        assert probe["component_total_count"] > 0
        assert probe["schema_baseline"]["matches"] is True
        assert probe["representative_row"]["geometry_crs"] == "EPSG:4326"
