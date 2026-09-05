from __future__ import annotations

import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_clackamas_property as clackamas


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_clackamas_property"
)


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text())


def page(name: str, route: str) -> clackamas.HTMLPage:
    source_url = f"{clackamas.ASCEND_ROOT_URL}{route}"
    return clackamas.HTMLPage(
        html=fixture_text(name),
        source_url=source_url,
        request_url=source_url,
    )


class FakeAscendClient:
    def __init__(self, *, changed_search: bool = False) -> None:
        self.changed_search = changed_search
        self.search_calls: list[dict[str, str]] = []
        self.detail_calls: list[tuple[str, int | None]] = []

    def fetch_home(self) -> clackamas.HTMLPage:
        return page("ascend_home.html", "")

    def search(self, **parameters: str) -> clackamas.HTMLPage:
        self.search_calls.append(dict(parameters))
        if parameters.get("account"):
            return page(
                "ascend_detail_01092276.html",
                "ParcelInfo.aspx?parcel_number=01092276",
            )
        html = fixture_text("ascend_search_main.html")
        if self.changed_search:
            html = html.replace("1020 W MAIN ST", "1022 W MAIN ST")
        return clackamas.HTMLPage(
            html=html,
            source_url=f"{clackamas.ASCEND_ROOT_URL}results.aspx",
            request_url=f"{clackamas.ASCEND_ROOT_URL}results.aspx",
        )

    def detail(
        self,
        account_number: str,
        *,
        tax_year: int | None = None,
    ) -> tuple[clackamas.HTMLPage, clackamas.HTMLPage | None]:
        self.detail_calls.append((account_number, tax_year))
        detail = page(
            "ascend_detail_01092276.html",
            f"ParcelInfo.aspx?parcel_number={account_number}",
        )
        installment = (
            page("ascend_installments_2025.html", "installments.aspx")
            if tax_year is not None
            else None
        )
        return detail, installment


class FakeCMapClient:
    def __init__(
        self,
        features: list[Mapping[str, Any]] | None = None,
        *,
        page_size: int = 1,
        missing_field: str | None = None,
    ) -> None:
        source = features or fixture_json("cmap_features.json")["features"]
        self.features = [deepcopy(dict(feature)) for feature in source]
        self.page_size = page_size
        self.missing_field = missing_field
        self.where_calls: list[str] = []
        self.record_count_calls: list[int] = []

    def fetch_metadata(self) -> dict[str, Any]:
        metadata = deepcopy(fixture_json("cmap_metadata.json"))
        if self.missing_field:
            metadata["fields"] = [
                field
                for field in metadata["fields"]
                if field["name"] != self.missing_field
            ]
        return metadata

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        exact_account = re.search(
            r"PARCEL_NUMBER\s*=\s*'([^']+)'",
            where,
        )
        exact_taxlot = re.search(r"TLNO\s*=\s*'([^']+)'", where)
        exact_object = re.search(r"\bOBJECTID\s*=\s*([0-9]+)", where)
        minimum = re.search(r"\bOBJECTID\s*>\s*([0-9]+)", where)
        maximum = re.search(r"\bOBJECTID\s*<=\s*([0-9]+)", where)
        records: list[Mapping[str, Any]] = []
        for feature in self.features:
            attrs = feature["attributes"]
            object_id = attrs["OBJECTID"]
            if exact_account and attrs["PARCEL_NUMBER"] != exact_account.group(1):
                continue
            if exact_taxlot and attrs["TLNO"] != exact_taxlot.group(1):
                continue
            if exact_object and object_id != int(exact_object.group(1)):
                continue
            if minimum and object_id <= int(minimum.group(1)):
                continue
            if maximum and object_id > int(maximum.group(1)):
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
        records = self._filtered(where)
        records.sort(
            key=lambda feature: feature["attributes"]["OBJECTID"],
            reverse=descending,
        )
        return tuple(records[:record_count])


def args_for(*values: str) -> Any:
    return clackamas.build_parser().parse_args(list(values))


def test_sources_and_source_cli_namespaces_do_not_require_transport_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[str] = []

    monkeypatch.setattr(
        clackamas,
        "_emit",
        lambda value, args: emitted.append(args.command),
    )
    monkeypatch.setattr(sys, "argv", ["query_oregon_clackamas_property.py", "sources"])
    clackamas.main()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_oregon_clackamas_property.py",
            "source",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
        ],
    )
    clackamas.main()

    assert emitted == ["sources", "source"]


def test_sources_keep_component_specific_owner_behavior_and_routes():
    payload = clackamas.execute(args_for("sources"), log_results=False)

    assert payload["platform_family"] == "clackamas_county_property_components"
    assert {source["source_id"] for source in payload["sources"]} == set(
        clackamas.SOURCE_IDS
    )
    by_id = {source["source_id"]: source for source in payload["sources"]}
    assert by_id[clackamas.ASCEND_SOURCE_ID]["metadata"][
        "owner_name_behavior"
    ] == "source_native_taxpayer_and_owner_party_rows_observed"
    assert by_id[clackamas.CMAP_SOURCE_ID]["metadata"][
        "owner_name_behavior"
    ] == "no_owner_field_in_layer_schema"
    assert "different county components" in payload[
        "component_reconciliation"
    ]["interpretation"]
    routes = by_id[clackamas.CMAP_SOURCE_ID][
        "complementary_official_routes"
    ]
    assert {
        route["kind"] for route in routes
    } >= {
        "county_gis_downloads",
        "county_measure_50_value_history",
        "county_online_tax_statements",
        "county_recording_research_and_copies",
    }


def test_source_contract_retains_live_manifest_and_observations():
    ascend = clackamas.execute(
        args_for("source", "--source", clackamas.ASCEND_SOURCE_ID),
        log_results=False,
    ).to_dict()["records"][0]
    cmap = clackamas.execute(
        args_for("source", "--source", clackamas.CMAP_SOURCE_ID),
        log_results=False,
    ).to_dict()["records"][0]

    assert ascend["observed_contract"]["platform_version"] == "4.5.0.0"
    assert ascend["observed_contract"]["representative_complete_search"] == {
        "street": "MAIN",
        "native_input": "%MAIN%",
        "record_count": 982,
        "native_count_wording": (
            "982 records returned from your search input."
        ),
    }
    assert ascend["observed_contract"]["native_manifest"]["form_aliases"][
        "account"
    ] == "_ctl0:MainContent:mParcelID2"
    assert ascend["observed_contract"]["value_column_labels"] == [
        "Tax Year 1",
        "Tax Year 2",
        "Tax Year 3",
        "Tax Year 4",
        "Tax Year 5",
    ]
    assert cmap["observed_contract"]["component_count"] == 163_925
    assert cmap["observed_contract"]["max_record_count"] == 2_000
    assert cmap["observed_contract"]["native_manifest"][
        "service_item_id"
    ] == clackamas.CMAP_ITEM_ID
    assert cmap["observed_contract"]["native_crs_wkids"] == [102100, 3857]


def test_ascend_home_and_search_use_prefixed_contract_and_complete_table_count():
    home = clackamas.parse_ascend_home(fixture_text("ascend_home.html"))
    search = clackamas.parse_ascend_search(
        fixture_text("ascend_search_main.html"),
        source_url=f"{clackamas.ASCEND_ROOT_URL}results.aspx",
    )

    assert home.version == "4.5.0.0"
    assert home.form_action == "./"
    assert "_ctl0:MainContent:mParcelID2" in home.form_fields
    assert "_ctl0:MainContent:mAlternateParcelID" not in home.form_fields
    assert search.total_count == 3
    assert [row["account_number"] for row in search.records] == [
        "01092276",
        "01090001",
        "01090002",
    ]
    assert search.records[0]["party_name"] == (
        "MOLALLA APARTMENTS LIMITED PARTNERSHIP"
    )


def test_ascend_detail_retains_element_identity_native_year_labels_and_parties():
    record = clackamas.parse_ascend_detail(
        fixture_text("ascend_detail_01092276.html"),
        source_url=(
            f"{clackamas.ASCEND_DETAIL_URL}?parcel_number=01092276"
        ),
        installment_html=fixture_text("ascend_installments_2025.html"),
        installment_source_url=(
            f"{clackamas.ASCEND_ROOT_URL}installments.aspx"
        ),
    )

    assert record["account_number"] == "01092276"
    assert record["alternate_map_taxlot"] == "52E08C 01500"
    assert record["identity_contract"]["mode"] == "elements"
    assert [party["role"] for party in record["parties"]] == [
        "taxpayer",
        "owner",
    ]
    assert record["parties"][1]["name"] == (
        "MOLALLA APARTMENTS LIMITED PARTNERSHIP"
    )
    assert record["value_column_contract"][
        "calendar_years_identified_in_response"
    ] is False
    assert record["value_history"][0]["native_columns"][0] == {
        "native_label": "Tax Year 1",
        "raw": "$14,748,081",
        "amount": 14_748_081,
    }
    assert record["receipts"][1]["amount_applied_value"] == 6003.82
    assert record["sales"][0]["recording_number"] == "2022-037981"
    assert record["sales"][0]["sale_amount_value"] == 1_220_000
    assert record["installment_detail"]["rows"][0]["tax_year"] == "2025"


def test_ascend_cursor_is_criteria_schema_and_snapshot_bound():
    first = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
        ),
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert [record["account_number"] for record in first["records"]] == [
        "01092276",
        "01090001",
    ]
    assert first["next_cursor"]

    second = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert [record["account_number"] for record in second["records"]] == [
        "01090002"
    ]
    assert second["next_cursor"] is None

    mismatch = clackamas.execute(
        args_for(
            "search",
            "FIRST",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert mismatch["status"] == "unavailable"
    assert mismatch["errors"][0]["code"] == "cursor_query_mismatch"

    changed = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=FakeAscendClient(changed_search=True),
        log_results=False,
    ).to_dict()
    assert changed["status"] == "source_changed"
    assert changed["errors"][0]["code"] == "source_schema_changed"


def test_omitted_limit_exhausts_ascend_snapshot_and_cmap_pages():
    ascend_args = args_for(
        "search",
        "MAIN",
        "--source",
        clackamas.ASCEND_SOURCE_ID,
        "--field",
        "address",
    )
    assert ascend_args.limit is None
    ascend = clackamas.execute(
        ascend_args,
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert [row["account_number"] for row in ascend["records"]] == [
        "01092276",
        "01090001",
        "01090002",
    ]
    assert ascend["next_cursor"] is None
    assert ascend["query"]["query"]["requested_limit"] is None

    cmap_client = FakeCMapClient(page_size=1)
    cmap = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--field",
            "address",
        ),
        client=cmap_client,
        log_results=False,
    ).to_dict()
    assert len(cmap["records"]) == 3
    assert cmap["next_cursor"] is None
    assert cmap["query"]["query"]["requested_limit"] is None
    assert max(cmap_client.record_count_calls) == 1


def test_exact_ascend_search_and_detail_use_rich_account_representation():
    exact = clackamas.execute(
        args_for(
            "search",
            "01092276",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "5",
        ),
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert exact["status"] == "ok"
    assert exact["records"][0]["record_kind"] == "property_account"
    assert exact["records"][0]["retrieval_snapshot"]["native_response"] == (
        "exact_account_detail"
    )

    client = FakeAscendClient()
    detail = clackamas.execute(
        args_for(
            "detail",
            "01092276",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--tax-year",
            "2025",
        ),
        client=client,
        log_results=False,
    ).to_dict()
    assert detail["status"] == "ok"
    assert client.detail_calls == [("01092276", 2025)]
    assert detail["records"][0]["installment_detail"]["rows"][0][
        "tax_year"
    ] == "2025"


def test_cmap_normalization_preserves_geometry_values_and_join_keys():
    payload = clackamas.execute(
        args_for(
            "detail",
            "01092276",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--field",
            "account",
            "--geometry",
        ),
        client=FakeCMapClient(),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    record = payload["records"][0]
    assert record["object_id"] == 109_341
    assert record["account_number"] == "01092276"
    assert record["map_taxlot"] == "52E08C 01500"
    assert record["assessment_values"]["assessed"] == 7_152_819
    assert record["latest_sale_or_deed"]["document_number"] == "2022-037981"
    assert record["geometry"]["rings"]
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["owner_name_component_behavior"]["owner_field_present"] is False
    assert record["join_candidates"][clackamas.ASCEND_SOURCE_ID] == {
        "account_number": "01092276",
        "map_taxlot": "52E08C 01500",
        "relationship": "exact_account_and_normalized_taxlot_join",
    }


def test_cmap_cursor_preserves_object_id_snapshot_boundary():
    first_client = FakeCMapClient(page_size=1)
    first = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "1",
        ),
        client=first_client,
        log_results=False,
    ).to_dict()
    boundary = first["records"][0]["retrieval_snapshot"][
        "boundary_object_id"
    ]
    assert boundary == 109_343
    assert first["next_cursor"]

    features = fixture_json("cmap_features.json")["features"]
    added = deepcopy(features[-1])
    added["attributes"]["OBJECTID"] = boundary + 100
    second_client = FakeCMapClient([*features, added], page_size=1)
    second = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=second_client,
        log_results=False,
    ).to_dict()

    assert second["records"][0]["object_id"] == 109_342
    assert second["records"][0]["retrieval_snapshot"][
        "boundary_object_id"
    ] == boundary
    assert any(
        f"OBJECTID <= {boundary}" in where
        for where in second_client.where_calls
    )


def test_cmap_cursor_detects_declared_schema_change():
    first = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "1",
        ),
        client=FakeCMapClient(page_size=1),
        log_results=False,
    ).to_dict()
    changed = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=FakeCMapClient(page_size=1, missing_field="TLNO"),
        log_results=False,
    ).to_dict()

    assert changed["status"] == "source_changed"
    assert changed["errors"][0]["code"] == "source_schema_changed"


def test_account_command_reconciles_exact_account_and_normalized_taxlot():
    payload = clackamas.execute(
        args_for("account", "01092276", "--geometry"),
        client={
            clackamas.ASCEND_SOURCE_ID: FakeAscendClient(),
            clackamas.CMAP_SOURCE_ID: FakeCMapClient(),
        },
        log_results=False,
    )

    assert payload["status"] == "ok"
    assert payload["reconciliation"]["account_exact"] is True
    assert payload["reconciliation"]["map_taxlot_matches"] is True
    assert payload["reconciliation"]["ascend_map_taxlot"] == "52E08C 01500"
    assert payload["reconciliation"]["owner_name_behavior"][
        "cmap_owner_field_present"
    ] is False
    assert {
        component["query"]["source"]["source_id"]
        for component in payload["components"]
    } == set(clackamas.SOURCE_IDS)
    cmap_component = next(
        component
        for component in payload["components"]
        if component["query"]["source"]["source_id"]
        == clackamas.CMAP_SOURCE_ID
    )
    assert cmap_component["query"]["query"]["requested_limit"] is None
    assert cmap_component["next_cursor"] is None


def test_account_command_returns_structured_failure_for_blank_account():
    payload = clackamas.execute(
        args_for("account", " "),
        client={},
        log_results=False,
    )

    assert payload["status"] == "unavailable"
    assert payload["errors"][0]["code"] == "blank_query"


def test_probe_all_validates_versions_schema_count_and_sentinel():
    payload = clackamas.execute(
        args_for("probe", "--all"),
        client={
            clackamas.ASCEND_SOURCE_ID: FakeAscendClient(),
            clackamas.CMAP_SOURCE_ID: FakeCMapClient(),
        },
        log_results=False,
    )

    assert payload["status"] == "ok"
    by_source = {
        component["query"]["source"]["source_id"]: component
        for component in payload["components"]
    }
    ascend_probe = by_source[clackamas.ASCEND_SOURCE_ID]["records"][0]
    cmap_probe = by_source[clackamas.CMAP_SOURCE_ID]["records"][0]
    assert ascend_probe["platform_version"] == "4.5.0.0"
    assert ascend_probe["broad_search"]["record_count"] == 3
    assert ascend_probe["sentinel"]["map_taxlot"] == "52E08C 01500"
    assert cmap_probe["max_record_count"] == 2000
    assert cmap_probe["component_total_count"] == 3
    assert cmap_probe["sentinel"][0]["object_id"] == 109_341


LIVE = os.environ.get("OSINT_LIVE_TESTS") == "1"


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_ascend_detail_sentinel():
    payload = clackamas.execute(
        args_for(
            "detail",
            "01092276",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    record = payload["records"][0]
    assert record["account_number"] == "01092276"
    assert record["alternate_map_taxlot"] == "52E08C 01500"
    assert {"taxpayer", "owner"} <= {
        party["role"] for party in record["parties"]
    }


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_ascend_main_complete_table():
    payload = clackamas.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            clackamas.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "1",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    assert payload["records"][0]["retrieval_snapshot"][
        "total_matching_records"
    ] > 0


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_cmap_metadata_count_and_sentinel():
    payload = clackamas.execute(
        args_for(
            "probe",
            "--source",
            clackamas.CMAP_SOURCE_ID,
            "--no-broad-search",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    probe = payload["records"][0]
    assert probe["component_total_count"] > 100_000
    assert probe["max_record_count"] == 2000
    assert probe["sentinel"][0]["map_taxlot"] == "52E08C 01500"


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_exact_account_join():
    payload = clackamas.execute(
        args_for(
            "account",
            "01092276",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    )

    assert payload["status"] == "ok"
    assert payload["reconciliation"]["account_exact"] is True
    assert payload["reconciliation"]["map_taxlot_matches"] is True
