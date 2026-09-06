from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_ohio_franklin_sales_gis as sales
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_sales_gis"
)


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def metadata_fixture() -> dict[str, Any]:
    return {
        "id": 0,
        "name": "Sales Details",
        "type": "Feature Layer",
        "displayField": "CNVYNAME",
        "geometryType": "esriGeometryPoint",
        "objectIdField": "OBJECTID",
        "globalIdField": "GlobalID",
        "serviceItemId": sales.ITEM_ID,
        "maxRecordCount": 2000,
        "extent": {
            "xmin": 1756950.0,
            "ymin": 653964.0,
            "xmax": 1895128.0,
            "ymax": 781092.0,
            "spatialReference": {"wkid": 102723, "latestWkid": 3735},
        },
        "advancedQueryCapabilities": {
            "supportsOrderBy": True,
            "supportsPagination": True,
            "supportsStatistics": True,
        },
        "fields": [
            {
                "name": field,
                "alias": field,
                "type": (
                    "esriFieldTypeOID"
                    if field == "OBJECTID"
                    else (
                        "esriFieldTypeGlobalID"
                        if field == "GlobalID"
                        else "esriFieldTypeString"
                    )
                ),
                "nullable": field not in {"OBJECTID", "GlobalID"},
            }
            for field in sales.FIELDS
        ],
        "indexes": [
            {"name": "R340_pk", "fields": "OBJECTID", "isUnique": True},
            {"name": "UUID_340", "fields": "GlobalID", "isUnique": False},
        ],
    }


class FakeFranklinSalesClient:
    def __init__(
        self,
        *,
        page_size: int = 1,
        missing_field: str | None = None,
        features: list[dict[str, Any]] | None = None,
    ) -> None:
        self.features = deepcopy(
            features
            if features is not None
            else fixture_json("features.json")["features"]
        )
        self.page_size = page_size
        self.missing_field = missing_field
        self.metadata_calls = 0
        self.count_calls: list[str] = []
        self.page_calls: list[dict[str, Any]] = []
        self.statistics_calls = 0
        self.distinct_count_calls: list[str] = []
        self.closed = False

    @property
    def request_count(self) -> int:
        return (
            self.metadata_calls
            + len(self.count_calls)
            + len(self.page_calls)
            + self.statistics_calls
            + len(self.distinct_count_calls)
        )

    def close(self) -> None:
        self.closed = True

    def fetch_metadata(self) -> dict[str, Any]:
        self.metadata_calls += 1
        metadata = metadata_fixture()
        if self.missing_field is not None:
            metadata["fields"] = [
                field
                for field in metadata["fields"]
                if field["name"] != self.missing_field
            ]
        return metadata

    @staticmethod
    def _sql_value(value: str) -> str:
        return value.replace("''", "'")

    @staticmethod
    def _millis(value: str) -> int:
        parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        exact_object = re.search(r"\bOBJECTID\s*=\s*([0-9]+)", where)
        minimum_object = re.search(r"\bOBJECTID\s*>\s*([0-9]+)", where)
        maximum_object = re.search(r"\bOBJECTID\s*<=\s*([0-9]+)", where)
        upper_likes = re.findall(
            r"UPPER\(([A-Za-z0-9_]+)\)\s+LIKE\s+'%((?:''|[^'])*)%'",
            where,
        )
        upper_exact = re.findall(
            r"UPPER\(([A-Za-z0-9_]+)\)\s*=\s*'((?:''|[^'])*)'",
            where,
        )
        null_fields = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s+IS\s+NULL",
            where,
        )
        blank_fields = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*''",
            where,
        )
        start_match = re.search(
            r"SALEDATE\s*>=\s*DATE\s*'([0-9]{4}-[0-9]{2}-[0-9]{2})'",
            where,
        )
        end_match = re.search(
            r"SALEDATE\s*<\s*DATE\s*'([0-9]{4}-[0-9]{2}-[0-9]{2})'",
            where,
        )

        selected: list[Mapping[str, Any]] = []
        for feature in self.features:
            attributes = feature["attributes"]
            object_id = attributes["OBJECTID"]
            if exact_object and object_id != int(exact_object.group(1)):
                continue
            if minimum_object and object_id <= int(minimum_object.group(1)):
                continue
            if maximum_object and object_id > int(maximum_object.group(1)):
                continue
            if any(attributes.get(field) is not None for field in null_fields):
                continue
            if any(attributes.get(field) != "" for field in blank_fields):
                continue
            if upper_likes and not any(
                self._sql_value(needle).upper()
                in str(attributes.get(field) or "").upper()
                for field, needle in upper_likes
            ):
                continue
            if any(
                str(attributes.get(field) or "").upper()
                != self._sql_value(expected).upper()
                for field, expected in upper_exact
            ):
                continue
            sale_date = attributes.get("SALEDATE")
            if start_match and (
                sale_date is None
                or sale_date < self._millis(start_match.group(1))
            ):
                continue
            if end_match and (
                sale_date is None
                or sale_date >= self._millis(end_match.group(1))
            ):
                continue
            selected.append(feature)
        return selected

    def fetch_count(self, where: str) -> int:
        self.count_calls.append(where)
        return len(self._filtered(where))

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        records = deepcopy(self._filtered(where))
        records.sort(
            key=lambda feature: feature["attributes"]["OBJECTID"],
            reverse=descending,
        )
        selected = records[:record_count]
        if not return_geometry:
            for feature in selected:
                feature.pop("geometry", None)
        self.page_calls.append(
            {
                "where": where,
                "record_count": record_count,
                "return_geometry": return_geometry,
                "descending": descending,
                "returned_object_ids": [
                    feature["attributes"]["OBJECTID"] for feature in selected
                ],
            }
        )
        return tuple(selected)

    def fetch_coverage_statistics(self) -> Mapping[str, Any]:
        self.statistics_calls += 1
        sale_dates = [
            feature["attributes"]["SALEDATE"]
            for feature in self.features
            if feature["attributes"].get("SALEDATE") is not None
        ]
        last_updates = [
            feature["attributes"]["LASTUPDATE"]
            for feature in self.features
            if feature["attributes"].get("LASTUPDATE") is not None
        ]
        return {
            "sale_date_min": min(sale_dates),
            "sale_date_max": max(sale_dates),
            "last_update_min": min(last_updates),
            "last_update_max": max(last_updates),
        }

    def fetch_distinct_count(self, field: str) -> int:
        self.distinct_count_calls.append(field)
        return len(
            {
                feature["attributes"].get(field)
                for feature in self.features
                if feature["attributes"].get(field) is not None
            }
        )


def args_for(*values: str) -> Any:
    return sales.build_parser().parse_args(list(values))


def test_source_and_layers_are_network_free_and_define_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sales,
        "_new_client",
        lambda _args: pytest.fail("network-free operations opened a client"),
    )

    source = sales.execute(args_for("source"), log_results=False).records[0]
    layers = sales.execute(args_for("layers"), log_results=False).records[0]

    assert source["source"]["source_id"] == sales.SOURCE_ID
    assert source["identity_contract"]["occurrence"].startswith("GlobalID")
    assert source["identity_contract"]["sale_business_join"] == (
        "ConveyanceNum plus PARCELID only when both are nonblank"
    )
    relationships = {
        item["source_id"]: item for item in source["source_relationships"]
    }
    assert relationships["us-oh-franklin-county-auditor-bulk"][
        "independent_corroboration_for_overlapping_fields"
    ] is False
    assert "us-oh-franklin-county-recorder-publicsearch" in relationships
    assert layers["canonical_layer"]["id"] == 0
    assert [item["id"] for item in layers["renderer_aliases"]] == [1, 2, 3, 4]
    assert all(
        item["independent_corroboration"] is False
        for item in layers["renderer_aliases"]
    )


def test_schema_validates_official_layer_identity_and_all_fields() -> None:
    result = sales.execute(
        args_for("schema"),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["layer_name"] == "Sales Details"
    assert record["service_item_id"] == sales.ITEM_ID
    assert record["geometry_type"] == "esriGeometryPoint"
    assert record["maximum_page_size"] == 2000
    assert record["field_count"] == len(sales.FIELDS)
    assert re.fullmatch(r"[0-9a-f]{64}", record["schema_fingerprint"])


def test_missing_required_field_reports_source_changed() -> None:
    result = sales.execute(
        args_for("schema"),
        client=FakeFranklinSalesClient(missing_field="ValidSale"),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["missing_fields"] == ("ValidSale",)


def test_sale_normalization_keeps_occurrence_and_business_identities_separate() -> None:
    result = sales.execute(
        args_for("parcel", "010-000006"),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )
    record = result.records[0]

    assert record["record_kind"] == "county_auditor_sale_feature_occurrence"
    assert record["source_record_id"] == "1"
    assert record["native_id"] == "{0A9D3B4A-060D-4B4F-A84B-DF332C586A1F}"
    assert record["occurrence_identity"]["identity_basis"] == "GlobalID"
    assert record["parcel_identity"]["parcel_id"] == "010-000006"
    assert record["sale_identity"]["conveyance_number"] == "00004012"
    assert record["sale_identity"]["parcel_id"] == "010-000006"
    assert record["sale"]["price"] == 800000.0
    assert record["sale"]["date_iso"].startswith("2024-03-19")
    assert record["sale"]["valid_sale"] == "Y"
    assert record["sale"]["qualification_preserved"] is True
    assert record["parties"]["grantee_names"] == (
        "LAMAR EQUITY INVESTMENTS LLC",
    )
    assert record["situs_address_observation"]["raw"] == (
        "1110 N CASSADY AVE"
    )
    assert record["improvements"]["year_built"] == 1950
    assert "geometry" not in record


def test_positive_price_invalid_qualification_remains_in_results() -> None:
    result = sales.execute(
        args_for("validity", "N"),
        client=FakeFranklinSalesClient(page_size=1),
        log_results=False,
    )

    assert [record["source_record_id"] for record in result.records] == ["2", "3"]
    positive = result.records[1]
    assert positive["sale"]["price"] == 15000.0
    assert positive["sale"]["date_iso"].startswith("2024-01-11")
    assert positive["sale"]["valid_sale"] == "N"


def test_blank_business_keys_do_not_erase_attributable_occurrence() -> None:
    result = sales.execute(
        args_for("search", "4", "--field", "object-id"),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )
    record = result.records[0]

    assert record["identity_state"] == "occurrence_only"
    assert record["parcel_id"] is None
    assert record["conveyance_number"] is None
    assert record["parcel_identity"] is None
    assert record["sale_identity"] is None
    assert record["occurrence_identity"]["identity_basis"] == (
        "service_item_layer_object_id"
    )
    assert record["native_id"] == f"{sales.ITEM_ID}:0:OBJECTID:4"


def test_partial_business_keys_retain_the_usable_parcel_join() -> None:
    features = fixture_json("features.json")["features"]
    features[3]["attributes"]["PARCELID"] = "010-999999"
    result = sales.execute(
        args_for("search", "4", "--field", "object-id"),
        client=FakeFranklinSalesClient(features=features),
        log_results=False,
    )
    record = result.records[0]

    assert record["identity_state"] == "occurrence_and_parcel_key"
    assert record["parcel_identity"]["parcel_id"] == "010-999999"
    assert record["sale_identity"] is None


@pytest.mark.parametrize(
    ("arguments", "expected_ids"),
    [
        (("party", "LAMAR"), ["1"]),
        (("conveyance", "00000502"), ["3"]),
        (("search", "WHEATLAND", "--field", "address"), ["3"]),
        (("search", "00004012", "--field", "conveyance"), ["1"]),
        (
            (
                "date-range",
                "--start",
                "2024-01-01",
                "--end",
                "2024-12-31",
            ),
            ["1", "3"],
        ),
    ],
)
def test_verified_selectors(arguments: tuple[str, ...], expected_ids: list[str]) -> None:
    result = sales.execute(
        args_for(*arguments),
        client=FakeFranklinSalesClient(page_size=1),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["source_record_id"] for record in result.records] == expected_ids


def test_omitted_limit_exhausts_and_verifies_the_objectid_snapshot() -> None:
    client = FakeFranklinSalesClient(page_size=1)

    result = sales.execute(
        args_for("validity", "N"),
        client=client,
        log_results=False,
    )

    assert [record["source_record_id"] for record in result.records] == ["2", "3"]
    assert result.next_cursor is None
    snapshot = result.records[0]["retrieval_snapshot"]
    assert snapshot["records_inside_objectid_boundary"] == 2
    assert snapshot["native_pagination_complete"] is True
    assert snapshot["native_pages_fetched"] == 3
    assert snapshot["caller_window_applied_during_native_keyset_traversal"] is False


def test_explicit_limit_uses_bounded_native_window_and_bound_cursor() -> None:
    first_client = FakeFranklinSalesClient(page_size=100)
    first = sales.execute(
        args_for("validity", "N", "--limit", "1"),
        client=first_client,
        log_results=False,
    )

    assert [record["source_record_id"] for record in first.records] == ["2"]
    assert first.next_cursor is not None
    assert first.next_cursor.startswith(sales.CURSOR_PREFIX)
    assert first_client.request_count == 4
    snapshot = first.records[0]["retrieval_snapshot"]
    assert snapshot["native_pages_fetched"] == 1
    assert snapshot["native_pagination_complete"] is False
    assert snapshot["caller_window_applied_during_native_keyset_traversal"] is True

    second_client = FakeFranklinSalesClient(page_size=100)
    second = sales.execute(
        args_for(
            "validity",
            "N",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=second_client,
        log_results=False,
    )

    assert [record["source_record_id"] for record in second.records] == ["3"]
    assert second.next_cursor is None
    assert second_client.request_count == 4

    mismatched = sales.execute(
        args_for(
            "validity",
            "Y",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )
    assert mismatched.status == ResultStatus.UNAVAILABLE
    assert mismatched.errors[0].code == "invalid_cursor"


def test_geometry_is_opt_in_and_transformed_contract_is_explicit() -> None:
    result = sales.execute(
        args_for("parcel", "010-000006", "--geometry"),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )
    record = result.records[0]

    assert record["geometry"] == {"x": -82.9296517456, "y": 39.993610513}
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry_role"] == "county_auditor_sale_location_point"


def test_probe_separates_stable_contract_from_rolling_coverage() -> None:
    client = FakeFranklinSalesClient()
    result = sales.execute(
        args_for("probe"),
        client=client,
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["service_item_id"] == sales.ITEM_ID
    assert record["layer_id"] == 0
    assert record["record_count"] == 4
    assert record["identity_audit"] == {
        "distinct_global_id_occurrences": 4,
        "null_global_id_occurrences": 0,
        "null_parcel_id_occurrences": 0,
        "blank_parcel_id_occurrences": 0,
        "null_conveyance_number_occurrences": 0,
        "blank_conveyance_number_occurrences": 1,
    }
    assert record["rolling_coverage"]["sale_date_min_iso"].startswith(
        "2023-05-16"
    )
    assert record["rolling_coverage"]["sale_date_max_iso"].startswith(
        "2024-03-19"
    )
    assert record["probe_request_count"] == sales.PROBE_EXPECTED_REQUESTS == 10
    assert client.request_count == 10


def test_probe_rejects_duplicate_preferred_occurrence_ids() -> None:
    features = fixture_json("features.json")["features"]
    features[1]["attributes"]["GlobalID"] = features[0]["attributes"][
        "GlobalID"
    ]

    result = sales.execute(
        args_for("probe"),
        client=FakeFranklinSalesClient(features=features),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["record_count"] == 4
    assert result.errors[0].details["null_global_id_count"] == 0
    assert result.errors[0].details["populated_global_id_count"] == 4
    assert result.errors[0].details["distinct_global_id_count"] == 3
    assert result.errors[0].details["url"] == sales.LAYER_URL


def test_probe_allows_null_global_id_when_fallback_identity_is_available() -> None:
    features = fixture_json("features.json")["features"]
    features[3]["attributes"]["GlobalID"] = None
    client = FakeFranklinSalesClient(features=features)

    probe = sales.execute(
        args_for("probe"),
        client=client,
        log_results=False,
    )
    occurrence = sales.execute(
        args_for("search", "4", "--field", "object-id"),
        client=FakeFranklinSalesClient(features=features),
        log_results=False,
    ).records[0]

    assert probe.status == ResultStatus.OK
    assert probe.records[0]["identity_audit"] == {
        "distinct_global_id_occurrences": 3,
        "null_global_id_occurrences": 1,
        "null_parcel_id_occurrences": 0,
        "blank_parcel_id_occurrences": 0,
        "null_conveyance_number_occurrences": 0,
        "blank_conveyance_number_occurrences": 1,
    }
    assert probe.records[0]["probe_request_count"] == 10
    assert occurrence["occurrence_identity"]["identity_basis"] == (
        "service_item_layer_object_id"
    )
    assert occurrence["native_id"] == f"{sales.ITEM_ID}:0:OBJECTID:4"


def test_count_validates_schema_then_uses_one_count_request() -> None:
    client = FakeFranklinSalesClient()
    result = sales.execute(
        args_for("count"),
        client=client,
        log_results=False,
    )

    assert result.records[0]["record_count"] == 4
    assert client.request_count == 2


def test_date_range_without_bounds_and_cursor_without_limit_are_explicit_failures() -> None:
    no_bounds = sales.execute(
        args_for("date-range"),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )
    no_limit = sales.execute(
        args_for("validity", "N", "--cursor", sales.CURSOR_PREFIX + "bad"),
        client=FakeFranklinSalesClient(),
        log_results=False,
    )

    assert no_bounds.status == ResultStatus.UNAVAILABLE
    assert no_bounds.errors[0].code == "date_range_required"
    assert no_limit.status == ResultStatus.UNAVAILABLE
    assert no_limit.errors[0].code == "cursor_requires_limit"
