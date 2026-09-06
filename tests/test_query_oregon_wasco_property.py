from __future__ import annotations

import argparse
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_wasco_property as wasco


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_wasco_property"
)


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def page(name: str, route: str) -> wasco.ascend.HTMLPage:
    native = (
        f"{wasco.ASCEND_ROOT_URL}(S(fixture-session))/{route}"
    )
    return wasco.ascend.HTMLPage(
        html=fixture_text(name),
        source_url=wasco.ascend.canonical_url(wasco.ASCEND_MANIFEST, native),
        request_url=native,
    )


class FakeAscendClient:
    def __init__(self, *, changed: bool = False) -> None:
        self.changed = changed
        self.search_calls: list[dict[str, str]] = []

    def fetch_home(self) -> wasco.ascend.HTMLPage:
        return page("default.html", "default.aspx")

    def search(self, **kwargs: str) -> wasco.ascend.HTMLPage:
        self.search_calls.append(dict(kwargs))
        html = fixture_text("search_main.html")
        if self.changed:
            html = html.replace("SECOND OBSERVED PARTY", "CHANGED PARTY")
        return wasco.ascend.HTMLPage(
            html=html,
            source_url=f"{wasco.ASCEND_ROOT_URL}results.aspx",
            request_url=(
                f"{wasco.ASCEND_ROOT_URL}(S(fixture-session))/results.aspx"
            ),
        )

    def detail(
        self,
        account_number: str,
        *,
        tax_year: int | None = None,
    ) -> tuple[wasco.ascend.HTMLPage, wasco.ascend.HTMLPage | None]:
        assert account_number == "9450"
        detail = page(
            "detail_9450.html",
            "ParcelInfo.aspx?parcel_number=9450",
        )
        installment = (
            page("installments_2025.html", "parcelinfo.aspx")
            if tax_year is not None
            else None
        )
        return detail, installment

    def close(self) -> None:
        return None


def taxlot_feature() -> dict[str, Any]:
    return {
        "attributes": {
            "OBJECTID": wasco.TAXLOT_SENTINEL_OBJECT_ID,
            "AccountNum": 9450,
            "MapTaxlot": wasco.TAXLOT_SENTINEL_MAP,
            "Taxpayer": "DILLON JOHN",
            "MailingAddress1": "PO BOX 357",
            "MailingAddress2": None,
            "MailingAddress3": None,
            "MailingCity": "DUFUR",
            "MailingState": "Oregon",
            "MailingZIP": "97021",
            "CalculatedAcres": 0.46278017,
        },
        "geometry": {"rings": [[[-121.0, 45.0], [-121.1, 45.0]]]},
    }


def survey_feature(
    source_id: str,
    object_id: int = 1,
) -> dict[str, Any]:
    values: dict[str, Any] = {"OBJECTID": object_id}
    if source_id == wasco.ROAD_RECORDS_SOURCE_ID:
        values["ANNO"] = "A-444"
    elif source_id == wasco.FILE_CABINET_SOURCE_ID:
        values["ANNO"] = "CS 1701"
    elif source_id == wasco.ROLL_MAPS_SOURCE_ID:
        values["ANNO"] = "F-16-10"
    elif source_id == wasco.COMMISSIONERS_SOURCE_ID:
        values["ANNO"] = "K-431"
    elif source_id == wasco.LAND_CORNERS_SOURCE_ID:
        values.update(
            {
                "ANNO": "LC 179",
                "DESCRIPTION": "RE-MONUMENTED CORNERS",
                "WEB_COLOR": "RED",
                "SCAN_NAM": "LC0179",
                "ToAttach": "LC0179.tif",
            }
        )
    elif source_id == wasco.PLATS_SOURCE_ID:
        values.update(
            {
                "PlatName": "1999-0014",
                "DocNumber": None,
                "Source": None,
                "SourceType": "Partition",
            }
        )
    elif source_id == wasco.SUBDIVISIONS_SOURCE_ID:
        values.update({"Shape__Length": 616.5, "LINETYPE": 40})
    elif source_id == wasco.SURVEY_BOOK_SOURCE_ID:
        values.update(
            {
                "ANNO": "BK 07 PG 166",
                "COMMENTS": " ",
                "FILEONLY": "07-166.tif",
            }
        )
    return {
        "attributes": values,
        "geometry": {"x": -121.1, "y": 45.2},
    }


class FakeArcGISClient:
    def __init__(
        self,
        manifest: wasco.arcgis.ArcGISLayerManifest,
        features: list[Mapping[str, Any]],
        *,
        page_size: int = 2,
        missing_field: str | None = None,
        attachments: tuple[Mapping[str, Any], ...] = (),
    ) -> None:
        self.manifest = manifest
        self.features = [deepcopy(dict(feature)) for feature in features]
        self.page_size = page_size
        self.missing_field = missing_field
        self.attachments = attachments
        self.where_calls: list[str] = []
        self.record_count_calls: list[int] = []

    def fetch_metadata(self) -> dict[str, Any]:
        fields = []
        for name in self.manifest.required_fields:
            if name == self.missing_field:
                continue
            fields.append(
                {
                    "name": name,
                    "alias": name,
                    "type": (
                        "esriFieldTypeOID"
                        if name == self.manifest.object_id_field
                        else "esriFieldTypeString"
                    ),
                    "nullable": name != self.manifest.object_id_field,
                }
            )
        return {
            "id": self.manifest.layer_id,
            "name": self.manifest.expected_layer_name,
            "serviceItemId": self.manifest.service_item_id,
            "objectIdField": self.manifest.object_id_field,
            "fields": fields,
            "spatialReference": {
                "wkid": self.manifest.source_crs_wkids[0],
                "latestWkid": self.manifest.source_crs_wkids[0],
            },
            "advancedQueryCapabilities": {
                "supportsOrderBy": True,
                "supportsPagination": True,
            },
            "maxRecordCount": self.page_size,
            "hasAttachments": self.manifest.has_attachments,
        }

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        rows = list(self.features)
        account = re.search(r"AccountNum\s*=\s*([0-9]+)", where)
        if account:
            rows = [
                feature
                for feature in rows
                if wasco.arcgis.feature_attributes(feature).get("AccountNum")
                == int(account.group(1))
            ]
        lower = re.search(r"OBJECTID\s*>\s*([0-9]+)", where)
        upper = re.search(r"OBJECTID\s*<=\s*([0-9]+)", where)
        exact = re.search(r"OBJECTID\s*=\s*([0-9]+)", where)
        if lower:
            rows = [
                feature
                for feature in rows
                if wasco.arcgis.feature_attributes(feature)["OBJECTID"]
                > int(lower.group(1))
            ]
        if upper:
            rows = [
                feature
                for feature in rows
                if wasco.arcgis.feature_attributes(feature)["OBJECTID"]
                <= int(upper.group(1))
            ]
        if exact:
            rows = [
                feature
                for feature in rows
                if wasco.arcgis.feature_attributes(feature)["OBJECTID"]
                == int(exact.group(1))
            ]
        return rows

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
        rows = sorted(
            self._filtered(where),
            key=lambda value: wasco.arcgis.feature_attributes(value)["OBJECTID"],
            reverse=descending,
        )
        return tuple(rows[:record_count])

    def fetch_attachments(
        self,
        object_id: int,
    ) -> tuple[Mapping[str, Any], ...]:
        assert object_id == 1
        return self.attachments

    def close(self) -> None:
        return None


def args_for(*values: str) -> argparse.Namespace:
    return wasco.build_parser().parse_args(list(values))


def test_sources_keep_all_ten_components_and_alternatives_distinct():
    payload = wasco.sources_payload()

    assert len(payload["sources"]) == 10
    assert {source["source_id"] for source in payload["sources"]} == set(
        wasco.SOURCE_IDS
    )
    by_id = {source["source_id"]: source for source in payload["sources"]}
    land = by_id[wasco.LAND_CORNERS_SOURCE_ID]
    assert land["metadata"]["native_contract"]["has_attachments"] is True
    assert land["metadata"]["identity_pattern"] == r"^LC\s*[0-9]+$"
    assert any(
        route["kind"] == "oregon_historical_county_records_inventory"
        for route in payload["complementary_routes"]
    )


def test_ascend_manifest_preserves_cookieless_path_aliases_and_version():
    native = (
        f"{wasco.ASCEND_ROOT_URL}(S(abc123))/"
        "ParcelInfo.aspx?parcel_number=9450"
    )
    assert wasco.ascend.canonical_url(wasco.ASCEND_MANIFEST, native) == (
        f"{wasco.ASCEND_ROOT_URL}ParcelInfo.aspx?parcel_number=9450"
    )
    assert "(S(abc123))" in wasco.ascend.request_url(
        wasco.ASCEND_MANIFEST,
        native,
    )
    contract = wasco.ascend.parse_home(
        wasco.ASCEND_MANIFEST,
        fixture_text("default.html"),
    )
    assert contract.version == "4.0.2.7"
    assert contract.form_action == "./default.aspx"
    assert wasco.ASCEND_MANIFEST.form_aliases["alternate"] == "mAlternateParcelID"


def test_complete_search_preserves_repeated_account_observations_and_cursor():
    parsed = wasco.ascend.parse_search(
        wasco.ASCEND_MANIFEST,
        fixture_text("search_main.html"),
        source_url=f"{wasco.ASCEND_ROOT_URL}results.aspx",
    )
    assert parsed.total_count == 3
    assert [record["account_number"] for record in parsed.records] == [
        "9450",
        "60748",
        "60748",
    ]
    assert parsed.records[1]["native_position"] != parsed.records[2]["native_position"]

    first = wasco.ascend.slice_complete_search(
        wasco.ASCEND_MANIFEST,
        parsed,
        cursor_prefix=wasco.ASCEND_CURSOR_PREFIX,
        criteria={"value": "MAIN", "field": "address"},
        limit=2,
        cursor=None,
    )
    second = wasco.ascend.slice_complete_search(
        wasco.ASCEND_MANIFEST,
        parsed,
        cursor_prefix=wasco.ASCEND_CURSOR_PREFIX,
        criteria={"value": "MAIN", "field": "address"},
        limit=2,
        cursor=first.next_cursor,
    )
    assert len(first.records) == 2
    assert [row["name"] for row in second.records] == ["SECOND OBSERVED PARTY"]
    with pytest.raises(ValueError, match="different criteria"):
        wasco.ascend.slice_complete_search(
            wasco.ASCEND_MANIFEST,
            parsed,
            cursor_prefix=wasco.ASCEND_CURSOR_PREFIX,
            criteria={"value": "DIFFERENT", "field": "address"},
            limit=2,
            cursor=first.next_cursor,
        )


def test_omitted_limit_exhausts_ascend_snapshot_and_arcgis_pages():
    ascend_args = args_for(
        "search",
        "MAIN",
        "--source",
        wasco.ASCEND_SOURCE_ID,
        "--field",
        "address",
    )
    assert ascend_args.limit is None
    ascend_result = wasco.execute(
        ascend_args,
        client=FakeAscendClient(),
        log_results=False,
    ).to_dict()
    assert [row["account_number"] for row in ascend_result["records"]] == [
        "9450",
        "60748",
        "60748",
    ]
    assert ascend_result["next_cursor"] is None
    assert ascend_result["query"]["query"]["requested_limit"] is None

    source_id = wasco.ROAD_RECORDS_SOURCE_ID
    features = [
        survey_feature(source_id, object_id=index)
        for index in range(1, 5)
    ]
    arc_client = FakeArcGISClient(
        wasco.ARCGIS_MANIFESTS[source_id],
        features,
        page_size=2,
    )
    arcgis_result = wasco.execute(
        args_for(
            "search",
            "*",
            "--source",
            source_id,
            "--field",
            "all",
        ),
        client=FakeAscendClient(),
        arcgis_clients={source_id: arc_client},
        log_results=False,
    ).to_dict()
    assert [row["object_id"] for row in arcgis_result["records"]] == [
        1,
        2,
        3,
        4,
    ]
    assert arcgis_result["next_cursor"] is None
    assert arcgis_result["query"]["query"]["requested_limit"] is None
    assert max(arc_client.record_count_calls) == 2


def test_detail_preserves_absent_party_section_values_receipts_and_sales():
    record = wasco.parse_ascend_detail(
        fixture_text("detail_9450.html"),
        source_url=f"{wasco.ASCEND_MANIFEST.detail_url}?parcel_number=9450",
        installment_html=fixture_text("installments_2025.html"),
        installment_source_url=f"{wasco.ASCEND_ROOT_URL}parcelinfo.aspx",
    )

    assert record["account_number"] == "9450"
    assert record["normalized_map_taxlot"] == "1S 13E 25 CB 6000"
    assert record["party_section_observed"] is False
    assert record["parties"] == []
    assert list(record["value_history"][0]["values_by_tax_year"]) == [
        "2025",
        "2024",
        "2023",
        "2022",
        "2021",
    ]
    assert len(record["receipts"]) == 7
    assert record["receipts"][0]["receipt_number"] == "578125"
    assert len(record["sales"]) == 3
    assert record["sales"][0]["recording_number"] == "000027323"
    assert record["sales"][0]["excise_number"] == "2007001823"
    assert record["installment_detail"]["rows"][0]["balance_due_value"] == 0


def test_wasco_taxlot_normalization_is_explicit_and_non_destructive_on_unknown():
    assert (
        wasco.normalize_wasco_taxlot("01S13 E25CB06000 00")
        == "1S 13E 25 CB 6000"
    )
    assert (
        wasco.normalize_wasco_taxlot("1S 13E 25 CB 6000")
        == "1S 13E 25 CB 6000"
    )
    assert wasco.normalize_wasco_taxlot("NONSTANDARD") == "NONSTANDARD"


def test_exact_account_join_validates_account_and_normalized_taxlot():
    tax_client = FakeArcGISClient(
        wasco.TAXLOT_MANIFEST,
        [taxlot_feature()],
    )
    result = wasco.execute(
        args_for("account", "9450", "--geometry"),
        client=FakeAscendClient(),
        arcgis_clients={wasco.TAXLOT_SOURCE_ID: tax_client},
        log_results=False,
    ).to_dict()

    assert result["status"] == "ok"
    record = result["records"][0]
    assert record["join_validation"]["status"] == "exact"
    assert record["join_validation"]["account_number_equal"] is True
    assert record["taxlot"]["taxpayer"] == "DILLON JOHN"
    assert record["taxlot"]["geometry_crs"] == "EPSG:4326"
    assert tax_client.record_count_calls == [1, 2]


def test_taxlot_join_fails_closed_when_map_taxlot_disagrees():
    feature = taxlot_feature()
    feature["attributes"]["MapTaxlot"] = "2S 13E 25 CB 6000"
    result = wasco.execute(
        args_for("account", "9450"),
        client=FakeAscendClient(),
        arcgis_clients={
            wasco.TAXLOT_SOURCE_ID: FakeArcGISClient(
                wasco.TAXLOT_MANIFEST,
                [feature],
            )
        },
        log_results=False,
    ).to_dict()
    assert result["status"] == "source_changed"
    assert result["errors"][0]["code"] == "source_schema_changed"


def test_survey_layers_keep_identity_patterns_and_attachment_capability():
    expected = {
        wasco.ROAD_RECORDS_SOURCE_ID: (47, 835, False),
        wasco.FILE_CABINET_SOURCE_ID: (48, 3402, False),
        wasco.ROLL_MAPS_SOURCE_ID: (50, 2976, False),
        wasco.COMMISSIONERS_SOURCE_ID: (52, 74, False),
        wasco.LAND_CORNERS_SOURCE_ID: (53, 1394, True),
        wasco.PLATS_SOURCE_ID: (54, 1279, False),
        wasco.SUBDIVISIONS_SOURCE_ID: (55, 1607, False),
        wasco.SURVEY_BOOK_SOURCE_ID: (56, 4158, True),
    }
    for source_id, (layer_id, count, attachments) in expected.items():
        definition = wasco.SURVEY_LAYERS[source_id]
        assert definition.layer_id == layer_id
        assert definition.observed_count == count
        assert definition.has_attachments is attachments
        assert definition.identity_pattern


def test_survey_search_uses_keyset_cursor_and_preserves_native_identity():
    source_id = wasco.ROAD_RECORDS_SOURCE_ID
    features = [
        survey_feature(source_id, object_id=index)
        for index in range(1, 5)
    ]
    for index, feature in enumerate(features, start=1):
        feature["attributes"]["ANNO"] = f"A-{440 + index}"
    fake = FakeArcGISClient(
        wasco.ARCGIS_MANIFESTS[source_id],
        features,
        page_size=2,
    )
    first = wasco.execute(
        args_for(
            "search",
            "*",
            "--source",
            source_id,
            "--field",
            "all",
            "--limit",
            "2",
        ),
        client=FakeAscendClient(),
        arcgis_clients={source_id: fake},
        log_results=False,
    ).to_dict()
    second = wasco.execute(
        args_for(
            "search",
            "*",
            "--source",
            source_id,
            "--field",
            "all",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ),
        client=FakeAscendClient(),
        arcgis_clients={source_id: fake},
        log_results=False,
    ).to_dict()
    assert [row["object_id"] for row in first["records"]] == [1, 2]
    assert [row["object_id"] for row in second["records"]] == [3, 4]
    assert first["records"][0]["native_identity"] == "A-441"


def test_land_corner_attachment_listing_emits_direct_source_download_url():
    source_id = wasco.LAND_CORNERS_SOURCE_ID
    fake = FakeArcGISClient(
        wasco.ARCGIS_MANIFESTS[source_id],
        [survey_feature(source_id)],
        attachments=(
            {
                "id": 1,
                "name": "LC0179.tif",
                "contentType": "image/tiff",
                "size": 106800,
            },
        ),
    )
    result = wasco.execute(
        args_for("attachments", source_id, "1"),
        client=FakeAscendClient(),
        arcgis_clients={source_id: fake},
        log_results=False,
    ).to_dict()
    assert result["status"] == "ok"
    attachment = result["records"][0]
    assert attachment["name"] == "LC0179.tif"
    assert attachment["download_url"].endswith("/53/1/attachments/1")


def test_probe_detects_missing_required_survey_field():
    source_id = wasco.SURVEY_BOOK_SOURCE_ID
    fake = FakeArcGISClient(
        wasco.ARCGIS_MANIFESTS[source_id],
        [survey_feature(source_id)],
        missing_field="FILEONLY",
    )
    result = wasco.execute(
        args_for("probe", "--source", source_id),
        client=FakeAscendClient(),
        arcgis_clients={source_id: fake},
        log_results=False,
    ).to_dict()
    assert result["status"] == "source_changed"
    assert "FILEONLY" in str(result["errors"][0]["details"])


LIVE = pytest.mark.skipif(
    os.getenv("OSINT_LIVE_TESTS") != "1",
    reason="set OSINT_LIVE_TESTS=1 for public Wasco source probes",
)


@LIVE
def test_live_ascend_home_and_exact_detail_sentinel():
    client = wasco.AscendWebClient(minimum_interval=0)
    try:
        home = client.fetch_home()
        contract = wasco.ascend.parse_home(
            wasco.ASCEND_MANIFEST,
            home.html,
            source_url=home.source_url,
        )
        detail, _ = client.detail(wasco.ASCEND_SENTINEL_ACCOUNT)
        record = wasco.parse_ascend_detail(
            detail.html,
            source_url=detail.source_url,
        )
    finally:
        client.close()
    assert contract.version == wasco.ASCEND_VERSION_OBSERVED
    assert record["normalized_map_taxlot"] == wasco.TAXLOT_SENTINEL_MAP
    assert record["party_section_observed"] is False


@LIVE
def test_live_taxlot_exact_join_sentinel():
    client = wasco.WascoArcGISClient(
        wasco.TAXLOT_MANIFEST,
        minimum_interval=0,
    )
    try:
        metadata = client.fetch_metadata()
        wasco.arcgis.metadata_contract(wasco.TAXLOT_MANIFEST, metadata)
        page_records = client.fetch_page(
            where="AccountNum = 9450",
            record_count=2,
            return_geometry=False,
        )
    finally:
        client.close()
    assert len(page_records) == 1
    values = wasco.arcgis.feature_attributes(page_records[0])
    assert values["OBJECTID"] == wasco.TAXLOT_SENTINEL_OBJECT_ID
    assert values["MapTaxlot"] == wasco.TAXLOT_SENTINEL_MAP


@LIVE
def test_live_taxlot_search_default_exhausts_exact_account():
    payload = wasco.execute(
        args_for(
            "search",
            wasco.ASCEND_SENTINEL_ACCOUNT,
            "--source",
            wasco.TAXLOT_SOURCE_ID,
            "--field",
            "account",
            "--minimum-interval",
            "0",
        ),
        log_results=False,
    ).to_dict()

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 1
    assert payload["next_cursor"] is None
    assert payload["query"]["query"]["requested_limit"] is None


@LIVE
def test_live_all_survey_layer_contracts_and_attachment_sentinels():
    for source_id in wasco.SURVEY_SOURCE_IDS:
        manifest = wasco.ARCGIS_MANIFESTS[source_id]
        client = wasco.WascoArcGISClient(manifest, minimum_interval=0)
        try:
            metadata = client.fetch_metadata()
            wasco.arcgis.metadata_contract(manifest, metadata)
            assert client.fetch_count("1=1") > 0
            if source_id in {
                wasco.LAND_CORNERS_SOURCE_ID,
                wasco.SURVEY_BOOK_SOURCE_ID,
            }:
                assert client.fetch_attachments(1)
        finally:
            client.close()
