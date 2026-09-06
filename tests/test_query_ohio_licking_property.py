from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_ohio_licking_property as licking
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_licking_property"
)


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FakeLickingPropertyClient:
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
        self.closed = False

    @property
    def request_count(self) -> int:
        return self.metadata_calls + len(self.count_calls) + len(self.page_calls)

    def close(self) -> None:
        self.closed = True

    def fetch_metadata(self) -> dict[str, Any]:
        self.metadata_calls += 1
        metadata = deepcopy(fixture_json("metadata.json"))
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

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        exact_object = re.search(r"\bOBJECTID\s*=\s*([0-9]+)", where)
        minimum_object = re.search(r"\bOBJECTID\s*>\s*([0-9]+)", where)
        maximum_object = re.search(r"\bOBJECTID\s*<=\s*([0-9]+)", where)
        parcel_exact = re.search(
            r"\bParcel\s*=\s*'((?:''|[^'])*)'",
            where,
        )
        upper_likes = re.findall(
            r"UPPER\(([A-Za-z0-9_.]+)\)\s+LIKE\s+'%((?:''|[^'])*)%'",
            where,
        )
        upper_exact = re.findall(
            r"UPPER\(([A-Za-z0-9_.]+)\)\s*=\s*'((?:''|[^'])*)'",
            where,
        )
        nonnull_fields = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_.()]*)\s+IS\s+NOT\s+NULL",
            where,
        )
        numeric_minimums = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_.()]*)\s*>=\s*(-?[0-9.]+)",
            where,
        )
        numeric_maximums = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_.()]*)\s*<=\s*(-?[0-9.]+)",
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
            if "Parcel IS NULL" in where and attributes.get("Parcel") is not None:
                continue
            if parcel_exact and attributes.get("Parcel") != self._sql_value(
                parcel_exact.group(1)
            ):
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
            if any(attributes.get(field) is None for field in nonnull_fields):
                continue
            if any(
                float(attributes.get(field)) < float(minimum)
                for field, minimum in numeric_minimums
            ):
                continue
            if any(
                float(attributes.get(field)) > float(maximum)
                for field, maximum in numeric_maximums
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


def args_for(*values: str) -> Any:
    return licking.build_parser().parse_args(list(values))


def test_source_record_is_network_free_and_declares_identity_and_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        licking,
        "_new_client",
        lambda _args: pytest.fail("source should not open a network client"),
    )

    result = licking.execute(args_for("source"), log_results=False)
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["source"]["source_id"] == licking.SOURCE_ID
    assert record["identity_contract"]["occurrence"].startswith("GlobalID")
    assert record["identity_contract"]["parcel_business_key"] == (
        "Parcel when nonblank"
    )
    assert record["identity_contract"]["live_audit_2026_07_31"] == {
        "total_occurrences": 83796,
        "nonnull_parcel_values": 82604,
        "unique_nonnull_parcel_values": 82604,
        "null_parcel_occurrences": 1192,
        "empty_string_parcel_occurrences": 0,
        "null_global_id_occurrences": 0,
    }
    relationships = {
        relationship["source_id"]: relationship
        for relationship in record["source_relationships"]
    }
    assert relationships["us-oh-ogrip-statewide-parcels"][
        "independent_corroboration_for_overlapping_fields"
    ] is False
    assert relationships["us-oh-licking-county-recorder-pax"]["role"] == (
        "recorded_instrument_and_party_evidence"
    )


def test_metadata_contract_validates_layer_identity_fields_and_indexes() -> None:
    result = licking.execute(
        args_for("metadata"),
        client=FakeLickingPropertyClient(),
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["service_item_id"] == licking.ITEM_ID
    assert record["layer_name"] == "Parcels"
    assert record["maximum_page_size"] == 100000
    assert record["field_count"] == len(licking.FIELDS)
    indexed = {
        index["fields"]: index["is_unique"]
        for index in record["declared_indexes"]
    }
    assert indexed == {"OBJECTID": True, "GlobalID": True, "Parcel": False}
    assert re.fullmatch(r"[0-9a-f]{64}", record["schema_fingerprint"])


def test_missing_required_field_is_source_changed() -> None:
    result = licking.execute(
        args_for("metadata"),
        client=FakeLickingPropertyClient(missing_field="GlobalID"),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["missing_fields"] == ("GlobalID",)


def test_exact_parcel_normalizes_assessment_and_transfer_observations() -> None:
    result = licking.execute(
        args_for("parcel", licking.SENTINEL_PARCEL),
        client=FakeLickingPropertyClient(page_size=1),
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["record_kind"] == (
        "county_assessor_parcel_feature_occurrence"
    )
    assert record["source_record_id"] == "3"
    assert record["native_id"] == "{86A76591-6D08-42B0-BBA2-29EE229BD5E3}"
    assert record["occurrence_identity"]["identity_basis"] == "GlobalID"
    assert record["parcel_identity"]["parcel_number"] == (
        licking.SENTINEL_PARCEL
    )
    assert record["owner_name_observation"] == "SMITH MARYLOUISE LINDEMUTH"
    assert record["assessment_owner_semantics"] == (
        "assessment_roll_observation_not_title"
    )
    assert record["assessment_value_observations"]["market_total"] == 50200
    assert record["improvements"] == {
        "dwelling": "Single Family",
        "year_built": 1900,
        "living_area_sq_ft": 1916,
    }
    assert record["recent_transfer_observations"][0]["date_iso"].startswith(
        "2016-06-06"
    )
    assert record["recent_transfer_observations"][0]["sale_amount"] == 0.0
    assert record["recorded_title_evidence"] is False
    assert "geometry" not in record


def test_null_parcel_feature_remains_an_attributable_occurrence() -> None:
    result = licking.execute(
        args_for("occurrence", "1"),
        client=FakeLickingPropertyClient(),
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["identity_state"] == "occurrence_only"
    assert record["parcel_number"] is None
    assert record["parcel_identity"] is None
    assert record["occurrence_identity"]["identity_basis"] == "GlobalID"
    assert record["canonical_ref"] == record["occurrence_identity"][
        "canonical_ref"
    ]


def test_duplicate_parcel_values_are_not_collapsed() -> None:
    features = fixture_json("features.json")["features"]
    duplicate = deepcopy(features[2])
    duplicate["attributes"]["OBJECTID"] = 5
    duplicate["attributes"]["GlobalID"] = (
        "{11111111-2222-3333-4444-555555555555}"
    )
    features.append(duplicate)

    result = licking.execute(
        args_for("parcel", licking.SENTINEL_PARCEL),
        client=FakeLickingPropertyClient(page_size=1, features=features),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["source_record_id"] for record in result.records] == ["3", "5"]
    assert len({record["canonical_ref"] for record in result.records}) == 2
    assert {
        record["parcel_identity"]["canonical_ref"] for record in result.records
    } == {result.records[0]["parcel_identity"]["canonical_ref"]}


@pytest.mark.parametrize(
    ("arguments", "expected_object_ids"),
    [
        (("owner", "smith"), ["2", "3"]),
        (("situs", "10034"), ["3"]),
        (("mailing", "columbus"), ["2", "3"]),
        (
            (
                "value",
                "--field",
                "market-total",
                "--minimum",
                "100000",
                "--maximum",
                "1100000",
            ),
            ["2", "4"],
        ),
        (("attribute", "land-use", "vacant land"), ["2"]),
        (("attribute", "class", "residential", "--match", "exact"), ["4"]),
    ],
)
def test_search_operations_return_all_matching_occurrences(
    arguments: tuple[str, ...],
    expected_object_ids: list[str],
) -> None:
    result = licking.execute(
        args_for(*arguments),
        client=FakeLickingPropertyClient(page_size=1),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["source_record_id"] for record in result.records] == (
        expected_object_ids
    )


def test_explicit_window_is_applied_only_after_native_exhaustion() -> None:
    client = FakeLickingPropertyClient(page_size=1)
    result = licking.execute(
        args_for("list", "--limit", "1", "--page-size", "1"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["source_record_id"] for record in result.records] == ["1"]
    assert result.next_cursor is not None
    traversal_calls = [call for call in client.page_calls if not call["descending"]]
    assert [
        object_id
        for call in traversal_calls
        for object_id in call["returned_object_ids"]
    ] == [1, 2, 3, 4]
    assert traversal_calls[-1]["returned_object_ids"] == []
    snapshot = result.records[0]["retrieval_snapshot"]
    assert snapshot["native_pages_fetched"] == 5
    assert snapshot["native_pagination_complete"] is True
    assert snapshot["caller_window_applied_after_native_exhaustion"] is True


def test_cursor_reacquires_complete_membership_before_returning_next_window() -> None:
    client = FakeLickingPropertyClient(page_size=1)
    first = licking.execute(
        args_for("list", "--limit", "1"),
        client=client,
        log_results=False,
    )
    first_page_call_count = len(client.page_calls)

    second = licking.execute(
        args_for("list", "--limit", "1", "--cursor", first.next_cursor),
        client=client,
        log_results=False,
    )

    assert [record["source_record_id"] for record in first.records] == ["1"]
    assert [record["source_record_id"] for record in second.records] == ["2"]
    assert second.next_cursor is not None
    second_traversal = [
        call
        for call in client.page_calls[first_page_call_count:]
        if not call["descending"]
    ]
    assert [
        object_id
        for call in second_traversal
        for object_id in call["returned_object_ids"]
    ] == [1, 2, 3, 4]


def test_cursor_rejects_changed_selector_and_changed_membership() -> None:
    client = FakeLickingPropertyClient(page_size=1)
    first = licking.execute(
        args_for("owner", "smith", "--limit", "1"),
        client=client,
        log_results=False,
    )

    changed_selector = licking.execute(
        args_for(
            "owner",
            "temple",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert changed_selector.status == ResultStatus.UNAVAILABLE
    assert changed_selector.errors[0].code == "cursor_query_mismatch"

    client.features[2]["attributes"]["GlobalID"] = (
        "{AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE}"
    )
    changed_membership = licking.execute(
        args_for(
            "owner",
            "smith",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert changed_membership.status == ResultStatus.UNAVAILABLE
    assert changed_membership.errors[0].code == "cursor_membership_changed"


def test_geometry_is_returned_only_when_requested() -> None:
    client = FakeLickingPropertyClient()
    without_geometry = licking.execute(
        args_for("parcel", licking.SENTINEL_PARCEL),
        client=client,
        log_results=False,
    )
    with_geometry = licking.execute(
        args_for("parcel", licking.SENTINEL_PARCEL, "--geometry"),
        client=client,
        log_results=False,
    )

    assert "geometry" not in without_geometry.records[0]
    assert with_geometry.records[0]["geometry"]["rings"]
    assert with_geometry.records[0]["geometry_crs"] == "EPSG:4326"
    assert with_geometry.records[0]["geometry_role"] == (
        "county_assessor_parcel_mapping_polygon"
    )


def test_authoritative_empty_query_is_no_results() -> None:
    result = licking.execute(
        args_for("parcel", "DOES-NOT-EXIST"),
        client=FakeLickingPropertyClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_probe_has_a_fixed_four_request_contract_and_validates_sentinel() -> None:
    client = FakeLickingPropertyClient()
    result = licking.execute(
        args_for("probe"),
        client=client,
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert client.request_count == 4
    assert record["probe_request_count"] == 4
    assert record["record_count"] == 4
    assert record["null_parcel_occurrence_count"] == 1
    assert record["sentinel_parcel"] == licking.SENTINEL_PARCEL
    assert record["sentinel_occurrence_identity"]["object_id"] == 3


def test_probe_reports_actual_request_attempt_count() -> None:
    class OneExtraAttemptClient(FakeLickingPropertyClient):
        def fetch_metadata(self) -> dict[str, Any]:
            self.metadata_calls += 1
            return super().fetch_metadata()

    client = OneExtraAttemptClient()
    result = licking.execute(
        args_for("probe"),
        client=client,
        log_results=False,
    )

    assert client.request_count == 5
    assert result.records[0]["probe_request_count"] == 5


def test_parser_has_no_implicit_limit_and_rejects_inverted_value_range() -> None:
    args = args_for("owner", "SMITH")
    assert args.limit is None
    assert args.page_size == licking.DEFAULT_PAGE_SIZE

    with pytest.raises(SystemExit) as error:
        licking.main(
            [
                "value",
                "--field",
                "market-total",
                "--minimum",
                "200",
                "--maximum",
                "100",
            ]
        )
    assert error.value.code == 2
