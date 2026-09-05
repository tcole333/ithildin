from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_ohio_statewide_parcels as ohio
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_statewide_parcels"
)


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text())


class FakeOhioParcelClient:
    def __init__(
        self,
        *,
        page_size: int = 1,
        missing_field: str | None = None,
    ) -> None:
        self.features = deepcopy(fixture_json("features.json")["features"])
        self.page_size = page_size
        self.missing_field = missing_field
        self.where_calls: list[str] = []
        self.record_count_calls: list[int] = []
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def fetch_metadata(self) -> dict[str, Any]:
        metadata = deepcopy(fixture_json("metadata.json"))
        if self.missing_field is not None:
            metadata["fields"] = [
                field
                for field in metadata["fields"]
                if field["name"] != self.missing_field
            ]
        return metadata

    def fetch_distinct_counties(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    feature["attributes"]["County"]
                    for feature in self.features
                    if feature["attributes"]["County"] is not None
                }
            )
        )

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        exact_text = {
            field: re.findall(rf"\b{field}\s*=\s*'([^']*)'", where)
            for field in ("County", "LocalParcelID", "StateParcelID")
        }
        exact_object = re.search(r"\bOBJECTID\s*=\s*([0-9]+)", where)
        minimum = re.search(r"\bOBJECTID\s*>\s*([0-9]+)", where)
        maximum = re.search(r"\bOBJECTID\s*<=\s*([0-9]+)", where)
        state_prefix = re.search(
            r"\bStateParcelID\s+LIKE\s+'([^']*)%'",
            where,
        )
        upper_likes = re.findall(
            r"UPPER\(([A-Za-z0-9_]+)\)\s+LIKE\s+'%([^%]*)%'",
            where,
        )

        records: list[Mapping[str, Any]] = []
        for feature in self.features:
            attributes = feature["attributes"]
            object_id = attributes["OBJECTID"]
            if any(
                values
                and str(attributes.get(field)) not in values
                for field, values in exact_text.items()
            ):
                continue
            if exact_object and object_id != int(exact_object.group(1)):
                continue
            if minimum and object_id <= int(minimum.group(1)):
                continue
            if maximum and object_id > int(maximum.group(1)):
                continue
            if state_prefix and not str(attributes.get("StateParcelID", "")).startswith(
                state_prefix.group(1)
            ):
                continue
            if upper_likes and not any(
                value.upper() in str(attributes.get(field, "")).upper()
                for field, value in upper_likes
            ):
                continue
            records.append(feature)
        return records

    def fetch_count(self, where: str) -> int:
        self.where_calls.append(where)
        return len(self._filtered(where))

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        self.where_calls.append(where)
        self.record_count_calls.append(record_count)
        records = deepcopy(self._filtered(where))
        records.sort(
            key=lambda feature: feature["attributes"]["OBJECTID"],
            reverse=descending,
        )
        selected = records[:record_count]
        if not return_geometry:
            for feature in selected:
                feature.pop("geometry", None)
        return tuple(selected)


def args_for(*values: str) -> Any:
    return ohio.build_parser().parse_args(list(values))


def test_source_graph_is_static_and_keeps_field_domains_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ohio,
        "_new_client",
        lambda _args: pytest.fail("source graph should not open a client"),
    )

    record = ohio.execute(args_for("source"), log_results=False).to_dict()[
        "records"
    ][0]
    graph = record["source_graph"]
    by_geoid = {
        county["county_geoid"]: county for county in graph["counties"]
    }

    assert graph["observed_at"] == "2026-07-31"
    assert set(by_geoid) == {"39049", "39089", "39041"}
    assert by_geoid["39049"]["ogrip_inventory_observation"] == {
        "record_count": 454405,
        "observed_at": "2026-07-30",
    }
    assert graph["statewide_component"]["coverage"] == "all_88_ohio_counties"
    assert "owner_name" in graph["statewide_component"]["fields_not_present"]
    licking_sources = {
        item.get("source_id") or item["name"]: item
        for item in by_geoid["39089"]["assessment_and_parcel"]
    }
    assert licking_sources["us-oh-licking-county-auditor-gis"][
        "observed_status"
    ] == "available"
    ontrac = licking_sources["Licking County Auditor OnTrac"]
    assert ontrac["observed_status"] == "not_automatable_in_live_probe"
    assert ontrac["observed_at"] == "2026-07-30"
    licking_alternatives = {
        item["source_id"]: item for item in ontrac["field_matched_alternatives"]
    }
    assert "parcel_polygon" in licking_alternatives[
        "us-oh-licking-county-auditor-gis"
    ]["fields"]
    assert "parcel_polygon" in licking_alternatives[ohio.SOURCE_ID]["fields"]
    franklin_source_ids = {
        item.get("source_id")
        for item in by_geoid["39049"]["assessment_and_parcel"]
    }
    assert "us-oh-franklin-county-auditor-bulk" in franklin_source_ids
    assert "us-oh-franklin-county-auditor-sales-gis" in franklin_source_ids
    franklin_sales_gis = next(
        item
        for item in by_geoid["39049"]["assessment_and_parcel"]
        if item.get("source_id")
        == "us-oh-franklin-county-auditor-sales-gis"
    )
    assert franklin_sales_gis["url"] == (
        "https://gis.franklincountyohio.gov/hosting/rest/services/"
        "RealEstate/Sales_Information/FeatureServer/0"
    )
    assert franklin_sales_gis["integration_status"] == "implemented"
    assert franklin_sales_gis["canonical_layer"] == 0
    assert franklin_sales_gis["renderer_alias_layers"] == [1, 2, 3, 4]
    licking_archives = next(
        item
        for item in by_geoid["39089"]["recorder_and_title"]
        if item["name"] == "Licking County Archives recorder collections"
    )
    assert licking_archives["url"] == (
        "https://lickingcounty.gov/depts/records_n_archives/"
        "list_of_record_collections_by_department/recorder.htm"
    )
    assert by_geoid["39089"]["recorder_and_title"][0][
        "access"
    ] == "account_required_for_discovery"
    assert by_geoid["39041"]["recorder_and_title"][0][
        "access"
    ] == "anonymous_after_disclaimer"
    assert by_geoid["39049"]["recorder_and_title"][0][
        "platform_family"
    ] == "govos_publicsearch"


def test_live_metadata_contract_retains_identity_indexes_and_page_size() -> None:
    result = ohio.execute(
        args_for("metadata"),
        client=FakeOhioParcelClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["service_item_id"] == ohio.ITEM_ID
    assert record["layer_name"] == "Parcels"
    assert record["maximum_page_size"] == 2000
    indexed_fields = {
        index["fields"] for index in record["declared_indexes"]
    }
    assert {"County", "LocalParcelID"} <= indexed_fields
    assert re.fullmatch(r"[0-9a-f]{64}", record["schema_fingerprint"])


def test_missing_required_field_is_a_source_changed_failure() -> None:
    result = ohio.execute(
        args_for("metadata"),
        client=FakeOhioParcelClient(missing_field="StateParcelID"),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert "StateParcelID" in str(result.errors[0].details)


def test_omitted_limit_exhausts_selected_county_across_transport_pages() -> None:
    client = FakeOhioParcelClient(page_size=1)
    result = ohio.execute(
        args_for("list", "--county", "39049", "--page-size", "1"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["object_id"] for record in result.records] == [10, 20, 30]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None
    assert max(client.record_count_calls) == 1
    assert result.records[0]["retrieval_snapshot"]["pages_fetched"] == 4


def test_explicit_limit_returns_and_resumes_boundary_bound_cursor() -> None:
    client = FakeOhioParcelClient(page_size=1)
    first = ohio.execute(
        args_for("list", "--county", "Franklin", "--limit", "2"),
        client=client,
        log_results=False,
    )

    assert [record["object_id"] for record in first.records] == [10, 20]
    assert first.next_cursor is not None

    second = ohio.execute(
        args_for(
            "list",
            "--county",
            "Franklin",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert [record["object_id"] for record in second.records] == [30]
    assert second.next_cursor is None
    assert second.records[0]["retrieval_snapshot"][
        "boundary_object_id"
    ] == 30


def test_cursor_rejects_changed_geometry_selection() -> None:
    client = FakeOhioParcelClient(page_size=1)
    first = ohio.execute(
        args_for("list", "--county", "Franklin", "--limit", "1"),
        client=client,
        log_results=False,
    )
    assert first.next_cursor is not None

    changed = ohio.execute(
        args_for(
            "list",
            "--county",
            "Franklin",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
            "--geometry",
        ),
        client=client,
        log_results=False,
    )

    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "normalization_or_cursor_failed"
    assert "different criteria" in changed.errors[0].message


def test_exact_state_parcel_uses_indexed_county_and_local_id_with_geometry() -> None:
    client = FakeOhioParcelClient(page_size=2)
    result = ohio.execute(
        args_for("parcel", "39049-010-042534", "--geometry"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    assert any(
        "County='Franklin'" in where
        and "LocalParcelID='010-042534'" in where
        and "StateParcelID='39049-010-042534'" in where
        for where in client.where_calls
    )
    record = result.records[0]
    assert record["jurisdiction"]["county_geoid"] == "39049"
    assert record["parcel_identifiers"]["local_parcel_id"] == "010-042534"
    assert record["situs_address_observation"] == "84 W DODRIDGE ST"
    assert record["owner_name_observation"] is None
    assert record["assessment_value_observations"] is None
    assert record["field_presence"]["owner_name"] is False
    assert record["field_presence"]["mailing_address_observation"] == {
        "schema_available": True,
        "row_has_value": True,
    }
    assert record["mailing_address_observation"]["city"] == "COLUMBUS"
    assert record["source_freshness"]["current_to_iso"].startswith("2023-09")
    assert record["local_cama_url"].endswith("/010-042534")
    assert record["source_record_selector"] == {
        "field": "OBJECTID",
        "value": 10,
    }
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["geometry"]["rings"]


def test_geometry_is_absent_when_not_requested_even_if_fixture_has_it() -> None:
    result = ohio.execute(
        args_for("parcel", "39089-00100000601000"),
        client=FakeOhioParcelClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert "geometry" not in result.records[0]
    assert result.records[0]["local_cama_url"].startswith(
        "https://www.lickingcountyohio.us/"
    )


def test_nullable_mailing_field_does_not_block_parcel_and_reports_row_presence() -> None:
    client = FakeOhioParcelClient()
    for field_name in (
        "MailAddressAll",
        "MailNumber",
        "MailStreetPrefix",
        "MailStreetName",
        "MailStreetSuffix",
        "MailUnitNumber",
        "MailCity",
        "MailZip",
        "MailState",
    ):
        client.features[0]["attributes"][field_name] = None

    result = ohio.execute(
        args_for("parcel", "39049-010-042534"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records[0]["mailing_address_observation"]["raw"] is None
    assert result.records[0]["field_presence"]["mailing_address_observation"] == {
        "schema_available": True,
        "row_has_value": False,
    }


def test_nonpilot_geoid_uses_source_native_state_parcel_prefix() -> None:
    args = args_for("list", "--county", "39153")

    assert ohio._where("list", args) == "(1=1) AND (StateParcelID LIKE '39153-%')"


def test_address_search_and_county_filter_return_all_native_matches() -> None:
    result = ohio.execute(
        args_for("address", "dodridge", "--county", "Franklin"),
        client=FakeOhioParcelClient(page_size=2),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["object_id"] for record in result.records] == [10, 20, 30]


def test_probe_validates_target_inventory_counts_and_samples() -> None:
    result = ohio.execute(
        args_for("probe"),
        client=FakeOhioParcelClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]
    targets = {
        county["county_geoid"]: county for county in record["target_counties"]
    }

    assert result.status == ResultStatus.OK
    assert record["county_count"] == 3
    assert set(targets) == {"39049", "39089", "39041"}
    assert targets["39049"]["record_count"] == 3
    assert targets["39049"]["prior_observed_at"] == "2026-07-30"
    assert targets["39089"]["sample_state_parcel_id"].startswith("39089-")
    assert targets["39041"]["sample_state_parcel_id"].startswith("39041-")


def test_parser_uses_no_implicit_result_limit() -> None:
    args = args_for("search", "MAIN", "--county", "Franklin")

    assert args.limit is None
    assert args.page_size == ohio.DEFAULT_PAGE_SIZE
