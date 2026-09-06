from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_yamhill_property as yamhill


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_yamhill_property"
)


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text())


def page(name: str, route: str) -> yamhill.HTMLPage:
    source_url = f"{yamhill.ASCEND_ROOT_URL}{route}"
    return yamhill.HTMLPage(
        html=fixture_text(name),
        source_url=source_url,
        request_url=(
            f"{yamhill.ASCEND_ROOT_URL}(S(fixture-session))/{route}"
        ),
    )


class FakeAscendClient:
    def __init__(self, *, exact_search: bool = False, changed: bool = False) -> None:
        self.exact_search = exact_search
        self.changed = changed
        self.search_calls: list[dict[str, str]] = []
        self.detail_calls: list[tuple[str, int | None]] = []

    def fetch_home(self) -> yamhill.HTMLPage:
        return page("default.html", "default.aspx")

    def search(self, **parameters: str) -> yamhill.HTMLPage:
        self.search_calls.append(dict(parameters))
        if self.exact_search:
            return page("detail_41270.html", "ParcelInfo.aspx?parcel_number=41270")
        result = fixture_text("search_main.html")
        if self.changed:
            result = result.replace(
                "2012 N MAIN ST, NEWBERG, OR 97132",
                "2012 N MAIN STREET, NEWBERG, OR 97132",
            )
        return yamhill.HTMLPage(
            html=result,
            source_url=f"{yamhill.ASCEND_ROOT_URL}results.aspx",
            request_url=(
                f"{yamhill.ASCEND_ROOT_URL}(S(fixture-session))/results.aspx"
            ),
        )

    def detail(
        self,
        account_number: str,
        *,
        tax_year: int | None = None,
    ) -> tuple[yamhill.HTMLPage, yamhill.HTMLPage | None]:
        self.detail_calls.append((account_number, tax_year))
        detail = page(
            "detail_41270.html",
            f"ParcelInfo.aspx?parcel_number={account_number}",
        )
        installment = (
            page("installments_2025.html", "installments.aspx")
            if tax_year is not None
            else None
        )
        return detail, installment


class FakeArcGISClient:
    def __init__(
        self,
        config: yamhill.ArcGISSource,
        features: list[Mapping[str, Any]],
        *,
        page_size: int = 1,
        missing_field: str | None = None,
    ) -> None:
        self.config = config
        self.features = [deepcopy(dict(feature)) for feature in features]
        self.page_size = page_size
        self.missing_field = missing_field
        self.where_calls: list[str] = []
        self.record_count_calls: list[int] = []

    def fetch_metadata(self) -> dict[str, Any]:
        metadata = deepcopy(fixture_json("arcgis_metadata.json")[self.config.source_id])
        metadata["fields"] = [
            {
                "name": field,
                "alias": field,
                "type": (
                    "esriFieldTypeOID"
                    if field == self.config.object_id_field
                    else "esriFieldTypeString"
                ),
                "nullable": field != self.config.object_id_field,
            }
            for field in self.config.required_fields
            if field != self.missing_field
        ]
        return metadata

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        oid_field = self.config.object_id_field
        minimum_match = re.search(
            rf"{re.escape(oid_field)}\s*>\s*([0-9]+)",
            where,
        )
        maximum_match = re.search(
            rf"{re.escape(oid_field)}\s*<=\s*([0-9]+)",
            where,
        )
        exact_match = re.search(
            rf"{re.escape(oid_field)}\s*=\s*([0-9]+)",
            where,
        )
        minimum = int(minimum_match.group(1)) if minimum_match else None
        maximum = int(maximum_match.group(1)) if maximum_match else None
        exact = int(exact_match.group(1)) if exact_match else None
        return [
            feature
            for feature in self.features
            if (
                (minimum is None or feature["properties"][oid_field] > minimum)
                and (
                    maximum is None
                    or feature["properties"][oid_field] <= maximum
                )
                and (
                    exact is None or feature["properties"][oid_field] == exact
                )
            )
        ]

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
        oid_field = self.config.object_id_field
        features = self._filtered(where)
        features.sort(
            key=lambda feature: feature["properties"][oid_field],
            reverse=descending,
        )
        return tuple(features[:record_count])


class FakeDiscoveryClient:
    def __init__(self, items: list[Mapping[str, Any]] | None = None) -> None:
        self.items = items

    def fetch_items(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(
            self.items
            if self.items is not None
            else fixture_json("permit_discovery.json")["results"]
        )


class FakeStreamResponse:
    def __init__(
        self,
        chunks: list[bytes],
        *,
        content_length: int | None = None,
    ) -> None:
        self.url = (
            "https://ascendweb.co.yamhill.or.us/"
            "AcsendWeb/(S(fixture))/results.aspx"
        )
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.encoding = "utf-8"
        self.chunks = chunks
        self.closed = False

    @property
    def text(self) -> str:
        raise AssertionError("bounded reader must not materialize response.text")

    def iter_content(self, *, chunk_size: int) -> Any:
        assert chunk_size == 64 * 1024
        yield from self.chunks

    def close(self) -> None:
        self.closed = True


def args_for(*values: str) -> Any:
    return yamhill.build_parser().parse_args(list(values))


def test_sources_keep_four_components_and_representation_semantics_distinct():
    payload = yamhill.execute(args_for("sources"), log_results=False)

    assert payload["platform_family"] == "yamhill_county_property_components"
    assert {source["source_id"] for source in payload["sources"]} == set(
        yamhill.SOURCE_IDS
    )
    by_id = {source["source_id"]: source for source in payload["sources"]}
    assert by_id[yamhill.TAXLOT_SOURCE_ID]["metadata"][
        "representation_role"
    ] == "canonical_current_taxlots"
    assert by_id[yamhill.RETIRED_SOURCE_ID]["metadata"][
        "representation_role"
    ] == "retired_taxlot_lineage"
    assert "not_independent_corroboration" in by_id[
        yamhill.RETIRED_SOURCE_ID
    ]["metadata"]["overlap_interpretation"]
    ascend_complements = by_id[yamhill.ASCEND_SOURCE_ID][
        "complementary_sources"
    ]
    assert any(
        item.get("kind") == "assessment_public_information_request"
        for item in ascend_complements
    )
    assert any(
        item.get("kind") == "assessment_data_extracts"
        for item in ascend_complements
    )
    assert {
        item["scope"] for item in payload["process_learnings"]
    } == {
        "native_session_contract",
        "complete_table_continuation",
        "representation_identity",
        "annual_source_discovery",
    }


def test_source_command_reports_observed_contract_and_catalog_identity():
    payload = yamhill.execute(
        args_for(
            "source",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    source = payload["records"][0]
    assert source["source_id"] == yamhill.ASCEND_SOURCE_ID
    assert source["catalog_metadata"]["auth"] == "none"
    assert source["observed_contract"]["platform_version"] == "4.0.3.0"
    assert source["observed_contract"]["representative_complete_search"][
        "record_count"
    ] == 887


def test_ascend_home_parses_native_typo_path_form_and_version():
    contract = yamhill.parse_ascend_home(fixture_text("default.html"))

    assert contract.version == "4.0.3.0"
    assert "mParcelID2" in contract.form_fields
    assert "mAlternateParcelID" in contract.form_fields
    assert contract.source_url == yamhill.ASCEND_HOME_URL
    assert yamhill._canonical_ascend_url(
        "https://ascendweb.co.yamhill.or.us/"
        "AcsendWeb/(S(abc123))/ParcelInfo.aspx?parcel_number=41270"
    ) == (
        "https://ascendweb.co.yamhill.or.us/"
        "AcsendWeb/ParcelInfo.aspx?parcel_number=41270"
    )
    assert "(S(abc123))" in yamhill._ascend_request_url(
        "https://ascendweb.co.yamhill.or.us/"
        "AcsendWeb/(S(abc123))/ParcelInfo.aspx?parcel_number=41270"
    )


def test_ascend_html_reader_streams_with_bound_and_always_closes():
    response = FakeStreamResponse(
        [b"<html>", b"fixture", b"</html>"],
        content_length=20,
    )
    result = yamhill.AscendWebClient._page(response)

    assert result.html == "<html>fixture</html>"
    assert result.body_bytes == 20
    assert response.closed
    assert "(S(" not in result.source_url

    overflow = FakeStreamResponse([b"1234", b"5678"])
    with pytest.raises(yamhill.SourceSchemaError) as error:
        yamhill.AscendWebClient._read_html(
            overflow,
            maximum_bytes=6,
        )
    assert "while streaming" in str(error.value)
    assert overflow.closed

    declared = FakeStreamResponse([b"unused"], content_length=100)
    with pytest.raises(yamhill.SourceSchemaError) as error:
        yamhill.AscendWebClient._read_html(
            declared,
            maximum_bytes=6,
        )
    assert "declared adapter bound" in str(error.value)
    assert declared.closed


def test_ascend_detail_preserves_parties_values_taxes_receipts_and_sales():
    record = yamhill.parse_ascend_detail(
        fixture_text("detail_41270.html"),
        source_url=(
            f"{yamhill.ASCEND_DETAIL_URL}?parcel_number=41270"
        ),
        installment_html=fixture_text("installments_2025.html"),
        installment_source_url=f"{yamhill.ASCEND_ROOT_URL}installments.aspx",
    )

    assert record["account_number"] == "41270"
    assert record["alternate_map_taxlot"] == "R3218AB 00301"
    assert [party["role"] for party in record["parties"]] == [
        "owner",
        "owner",
        "owner",
        "buyer",
        "buyer",
    ]
    assessed = next(
        item
        for item in record["value_history"]
        if item["value_code"] == "AVR"
    )
    assert assessed["values_by_tax_year"]["2025"]["amount"] == 169_823
    assert record["tax_rate"]["total_rate_value"] == 16.1366
    assert record["receipts"][0]["receipt_number"] == "1350159"
    assert record["receipts"][0]["amount_applied_value"] == 2740.37
    assert record["sales"][0]["recording_number"] == "2026-03177"
    assert record["sales"][1]["sale_amount_value"] == 350_000
    assert record["property_details"]["living_area_sq_ft"]["value"] == 896
    assert record["property_details"]["year_built"]["value"] == 1952
    installment = record["installment_detail"]["rows"][0]
    assert installment["tca_district"] == "29.0"
    assert installment["charged_value"] == 2740.37
    assert installment["due_date_iso"] == "2025-11-15"
    assert record["join_candidates"][yamhill.HELION_SOURCE_ID][
        "recording_numbers"
    ][:2] == ["2026-03177", "2024-00119"]


def test_ascend_complete_table_continuation_is_query_and_snapshot_bound():
    client = FakeAscendClient()
    first = yamhill.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
        ),
        client=client,
        access_decision={"review_id": 260, "disposition": "allowed"},
        log_results=False,
    ).to_dict()

    assert [record["account_number"] for record in first["records"]] == [
        "41216",
        "41270",
    ]
    assert first["next_cursor"]
    assert first["records"][0]["retrieval_snapshot"][
        "native_response"
    ] == "complete_search_table"
    assert first["query"]["query"]["metadata"]["access_decision"] == {
        "review_id": 260,
        "disposition": "allowed",
    }

    second = yamhill.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=client,
        log_results=False,
    ).to_dict()
    assert [record["account_number"] for record in second["records"]] == [
        "41252"
    ]
    assert second["next_cursor"] is None

    mismatch = yamhill.execute(
        args_for(
            "search",
            "FIRST",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=client,
        log_results=False,
    ).to_dict()
    assert mismatch["status"] == "unavailable"
    assert mismatch["errors"][0]["code"] == "cursor_query_mismatch"

    changed = yamhill.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=FakeAscendClient(changed=True),
        log_results=False,
    ).to_dict()
    assert changed["status"] == "source_changed"
    assert changed["errors"][0]["code"] == "cursor_snapshot_changed"


def test_omitted_limit_exhausts_ascend_snapshot_and_arcgis_pages():
    ascend_args = args_for(
        "search",
        "MAIN",
        "--source",
        yamhill.ASCEND_SOURCE_ID,
        "--field",
        "address",
    )
    assert ascend_args.limit is None
    ascend = yamhill.execute(
        ascend_args,
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert [row["account_number"] for row in ascend["records"]] == [
        "41216",
        "41270",
        "41252",
    ]
    assert ascend["next_cursor"] is None
    assert ascend["query"]["query"]["requested_limit"] is None

    arc_client = FakeArcGISClient(
        yamhill.TAXLOTS,
        _current_features(3),
        page_size=1,
    )
    arcgis_result = yamhill.execute(
        args_for(
            "search",
            "LUTZE",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "owner",
        ),
        client=arc_client,
        log_results=False,
    ).to_dict()
    assert len(arcgis_result["records"]) == 3
    assert arcgis_result["next_cursor"] is None
    assert arcgis_result["query"]["query"]["requested_limit"] is None
    assert arcgis_result["records"][0]["retrieval_snapshot"][
        "pages_fetched"
    ] == 3
    assert max(arc_client.record_count_calls) == 1


def test_exact_ascend_search_and_detail_use_rich_account_representation():
    exact = yamhill.execute(
        args_for(
            "search",
            "41270",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "10",
        ),
        client=FakeAscendClient(exact_search=True),
        log_results=False,
    ).to_dict()
    assert exact["status"] == "ok"
    assert exact["records"][0]["record_kind"] == "property_account"
    assert exact["records"][0]["retrieval_snapshot"]["native_response"] == (
        "exact_account_detail"
    )

    client = FakeAscendClient()
    detail = yamhill.execute(
        args_for(
            "detail",
            "41270",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--tax-year",
            "2025",
        ),
        client=client,
        log_results=False,
    ).to_dict()
    assert detail["status"] == "ok"
    assert client.detail_calls == [("41270", 2025)]
    assert detail["records"][0]["installment_detail"]["rows"][0][
        "tax_year"
    ] == "2025"


def _current_features(count: int = 3) -> list[dict[str, Any]]:
    first = fixture_json("current_feature.json")
    features = [first]
    for offset in range(1, count):
        feature = deepcopy(first)
        feature["id"] = first["id"] + offset
        feature["properties"]["objectid"] = first["id"] + offset
        feature["properties"]["globalid"] = f"fixture-global-{offset}"
        features.append(feature)
    return features


def test_current_taxlot_normalization_joins_ascend_and_recorder():
    client = FakeArcGISClient(yamhill.TAXLOTS, _current_features(1))
    payload = yamhill.execute(
        args_for(
            "detail",
            "41270",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "account",
            "--geometry",
        ),
        client=client,
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    assert payload["query"]["query"]["requested_limit"] is None
    assert payload["next_cursor"] is None
    record = payload["records"][0]
    assert record["object_id"] == 5_144_427
    assert record["map_taxlot"] == "R3218AB 00301"
    assert record["latest_deed_or_sale"]["recording_number"] == "2026-03177"
    assert record["geometry"]["type"] == "Polygon"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["join_candidates"][yamhill.ASCEND_SOURCE_ID][
        "account_number"
    ] == "41270"
    assert record["join_candidates"][yamhill.HELION_SOURCE_ID][
        "recording_number"
    ] == "2026-03177"


def test_arcgis_cursor_keeps_query_schema_and_high_water_boundary():
    original = _current_features(3)
    first_client = FakeArcGISClient(
        yamhill.TAXLOTS,
        original,
        page_size=1,
    )
    first = yamhill.execute(
        args_for(
            "search",
            "LUTZE",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "owner",
            "--limit",
            "1",
        ),
        client=first_client,
        log_results=False,
    ).to_dict()
    boundary = first["records"][0]["retrieval_snapshot"][
        "boundary_object_id"
    ]
    assert boundary == 5_144_429
    assert first["next_cursor"]

    new_feature = deepcopy(original[-1])
    new_feature["id"] = boundary + 10
    new_feature["properties"]["objectid"] = boundary + 10
    second_client = FakeArcGISClient(
        yamhill.TAXLOTS,
        [*original, new_feature],
        page_size=1,
    )
    second = yamhill.execute(
        args_for(
            "search",
            "LUTZE",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "owner",
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=second_client,
        log_results=False,
    ).to_dict()
    assert second["records"][0]["object_id"] == 5_144_428
    assert second["records"][0]["retrieval_snapshot"][
        "boundary_object_id"
    ] == boundary
    assert any(
        f"objectid <= {boundary}" in where
        for where in second_client.where_calls
    )

    mismatch = yamhill.execute(
        args_for(
            "search",
            "TRUST",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "owner",
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=second_client,
        log_results=False,
    ).to_dict()
    assert mismatch["status"] == "unavailable"
    assert mismatch["errors"][0]["code"] == "cursor_query_mismatch"


def test_arcgis_cursor_detects_schema_change():
    client = FakeArcGISClient(
        yamhill.TAXLOTS,
        _current_features(2),
        page_size=1,
    )
    first = yamhill.execute(
        args_for(
            "search",
            "41270",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    ).to_dict()

    changed_client = FakeArcGISClient(
        yamhill.TAXLOTS,
        _current_features(2),
        page_size=1,
        missing_field="maptaxlot",
    )
    changed = yamhill.execute(
        args_for(
            "search",
            "41270",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "1",
            "--cursor",
            first["next_cursor"],
        ),
        client=changed_client,
        log_results=False,
    ).to_dict()
    assert changed["status"] == "source_changed"
    assert changed["errors"][0]["code"] == "source_schema_changed"


def test_retired_taxlot_preserves_lineage_as_same_system_representation():
    feature = fixture_json("retired_feature.json")
    payload = yamhill.execute(
        args_for(
            "detail",
            "P4952",
            "--source",
            yamhill.RETIRED_SOURCE_ID,
            "--field",
            "map_taxlot",
            "--geometry",
        ),
        client=FakeArcGISClient(yamhill.RETIRED_TAXLOTS, [feature]),
        log_results=False,
    ).to_dict()

    record = payload["records"][0]
    assert record["status"] == "retired_representation"
    assert record["lineage"]["parent_taxlot"] == "R6701 00400"
    assert record["lineage"]["retired_by_global_id"] == (
        "{F9168690-8DF0-49E3-BEF7-95379DC2E0B6}"
    )
    assert record["representation"]["group"] == yamhill.REPRESENTATION_GROUP
    assert "not_independent_corroboration" in record["representation"][
        "overlap_interpretation"
    ]


def test_permit_normalization_and_org_discovery_preserve_annual_identity():
    features = fixture_json("permit_features.json")["features"]
    payload = yamhill.execute(
        args_for(
            "search",
            "245158",
            "--source",
            yamhill.PERMIT_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "2",
            "--geometry",
        ),
        client=FakeArcGISClient(yamhill.PERMITS, features),
        log_results=False,
    ).to_dict()

    first = payload["records"][0]
    assert first["native_permit_id"] == "979-25-001787-ELEC"
    assert first["publication_year"] == 2026
    assert first["permit"]["issue_date"]["utc_date"] == "2025-06-16"
    assert first["join_candidates"][yamhill.TAXLOT_SOURCE_ID] == {
        "account_number": "245158",
        "map_taxlot": "R6801 00600",
        "relationship": "current_taxlot_and_geometry_context",
    }

    discovery = yamhill.parse_permit_discovery(
        fixture_json("permit_discovery.json")["results"]
    )
    assert discovery["selected"]["year"] == 2026
    assert discovery["selected"]["item_id"] == yamhill.PERMITS.service_item_id
    assert discovery["rollover_observed"] is False

    future = deepcopy(fixture_json("permit_discovery.json")["results"][0])
    future.update(
        {
            "id": "future-item",
            "title": "2027 Permits",
            "modified": 1800000000000,
            "url": (
                "https://services6.arcgis.com/toubSXwoan3LMhOW/"
                "arcgis/rest/services/2027_Permits/FeatureServer"
            ),
        }
    )
    rollover = yamhill.parse_permit_discovery(
        [*fixture_json("permit_discovery.json")["results"], future]
    )
    assert rollover["selected"]["year"] == 2027
    assert rollover["rollover_observed"] is True


def test_probe_reports_counts_schema_and_permit_discovery():
    features = fixture_json("permit_features.json")["features"]
    payload = yamhill.execute(
        args_for("probe", "--source", yamhill.PERMIT_SOURCE_ID),
        client=FakeArcGISClient(yamhill.PERMITS, features),
        discovery_client=FakeDiscoveryClient(),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    probe = payload["records"][0]
    assert probe["component_total_count"] == 2
    assert probe["max_record_count"] == 2000
    assert probe["annual_discovery"]["selected"]["year"] == 2026
    assert probe["annual_discovery"]["rollover_observed"] is False


def test_permit_probe_returns_source_change_on_newer_official_annual_item():
    features = fixture_json("permit_features.json")["features"]
    current = fixture_json("permit_discovery.json")["results"][0]
    future = deepcopy(current)
    future.update(
        {
            "id": "future-item",
            "title": "2027 Permits",
            "modified": 1800000000000,
            "url": (
                "https://services6.arcgis.com/toubSXwoan3LMhOW/"
                "arcgis/rest/services/2027_Permits/FeatureServer"
            ),
        }
    )
    payload = yamhill.execute(
        args_for("probe", "--source", yamhill.PERMIT_SOURCE_ID),
        client=FakeArcGISClient(yamhill.PERMITS, features),
        discovery_client=FakeDiscoveryClient([current, future]),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "source_changed"
    assert payload["errors"][0]["code"] == "annual_permit_rollover"
    assert payload["errors"][0]["details"]["selected"]["year"] == 2027
    assert payload["records"][0]["annual_discovery"][
        "rollover_observed"
    ] is True


LIVE = os.environ.get("OSINT_LIVE_TESTS") == "1"


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_ascend_exact_detail_sentinel():
    payload = yamhill.execute(
        args_for(
            "detail",
            "41270",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--tax-year",
            "2025",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    record = payload["records"][0]
    assert record["alternate_map_taxlot"] == "R3218AB 00301"
    assert "2026-03177" in record["join_candidates"][
        yamhill.HELION_SOURCE_ID
    ]["recording_numbers"]
    assert record["installment_detail"]["rows"][0]["tax_year"] == "2025"


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_ascend_complete_main_search_returns_bounded_window():
    payload = yamhill.execute(
        args_for(
            "search",
            "MAIN",
            "--source",
            yamhill.ASCEND_SOURCE_ID,
            "--field",
            "address",
            "--limit",
            "2",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 2
    assert payload["next_cursor"]
    snapshot = payload["records"][0]["retrieval_snapshot"]
    assert snapshot["native_response"] == "complete_search_table"
    assert snapshot["total_matching_records"] >= 800


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_current_taxlot_exact_account_geometry():
    payload = yamhill.execute(
        args_for(
            "detail",
            "41270",
            "--source",
            yamhill.TAXLOT_SOURCE_ID,
            "--field",
            "account",
            "--geometry",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    record = payload["records"][0]
    assert record["object_id"] == 5_144_427
    assert record["geometry"]["type"] == "Polygon"
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["latest_deed_or_sale"]["recording_number"] == "2026-03177"


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_retired_taxlot_probe_preserves_lineage_component():
    payload = yamhill.execute(
        args_for(
            "probe",
            "--source",
            yamhill.RETIRED_SOURCE_ID,
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    probe = payload["records"][0]
    assert probe["component_total_count"] >= 800
    assert probe["layer_name"] == "TAXLOTS - RETIRED"


@pytest.mark.skipif(not LIVE, reason="set OSINT_LIVE_TESTS=1 for live source checks")
def test_live_permit_probe_discovers_current_annual_item():
    payload = yamhill.execute(
        args_for(
            "probe",
            "--source",
            yamhill.PERMIT_SOURCE_ID,
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    discovery = payload["records"][0]["annual_discovery"]
    assert discovery["selected"]["year"] >= 2026
    assert discovery["organization_id"] == yamhill.ARCGIS_ORG_ID
