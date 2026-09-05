from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

import pytest

from tools import query_new_jersey_parcels as nj
from tools.public_records_http import SourceSchemaError


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "new_jersey_parcels"
)


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


def _item_metadata(*, service_url=nj.DEFAULT_SERVICE_URL, modified=200):
    return {
        "id": nj.ITEM_ID,
        "type": "Feature Service",
        "owner": "NJOGIS",
        "access": "public",
        "url": service_url,
        "modified": modified,
    }


def _layer_metadata(*, data_version=100, missing=()):
    fields = [
        {
            "name": name,
            "type": (
                "esriFieldTypeOID"
                if name == "OBJECTID"
                else "esriFieldTypeString"
            ),
            "length": None if name == "OBJECTID" else 80,
        }
        for name in nj.REQUIRED_FIELDS
        if name not in set(missing)
    ]
    return {
        "name": nj.SOURCE_LAYER_NAME,
        "id": 0,
        "serviceItemId": nj.ITEM_ID,
        "objectIdField": "OBJECTID",
        "geometryType": nj.SOURCE_GEOMETRY_TYPE,
        "maxRecordCount": 2_000,
        "supportedQueryFormats": "JSON, geoJSON, PBF",
        "advancedQueryCapabilities": {
            "supportsOrderBy": True,
            "supportsPagination": True,
        },
        "editingInfo": {"dataLastEditDate": data_version},
        "fields": fields,
    }


def _snapshot(*, data_version=100, layer_url=nj.DEFAULT_LAYER_URL):
    return nj._compatible_snapshot(
        _item_metadata(
            service_url=layer_url.removesuffix("/0"),
            modified=200,
        ),
        _layer_metadata(data_version=data_version),
        layer_url,
    )


class FakeClient:
    def __init__(
        self,
        features,
        *,
        page_size=2,
        snapshots=None,
        full_counts=None,
    ):
        self.features = copy.deepcopy(features)
        self.page_size = page_size
        self.snapshots = list(snapshots or [_snapshot()])
        self.full_counts = list(full_counts or [])
        self.snapshot_calls = 0
        self.full_count_calls = 0
        self.count_calls = []
        self.page_calls = []

    def fetch_snapshot(self):
        index = min(self.snapshot_calls, len(self.snapshots) - 1)
        self.snapshot_calls += 1
        return self.snapshots[index]

    def fetch_count(self, where, spatial_parameters=None):
        self.count_calls.append(
            {
                "where": where,
                "spatial_parameters": dict(spatial_parameters or {}),
            }
        )
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        if match:
            threshold = int(match.group(1))
            return sum(
                feature["attributes"]["OBJECTID"] > threshold
                for feature in self.features
            )
        if self.full_counts:
            index = min(
                self.full_count_calls, len(self.full_counts) - 1
            )
            count = self.full_counts[index]
            self.full_count_calls += 1
            return count
        self.full_count_calls += 1
        return len(self.features)

    def fetch_page(
        self,
        *,
        where,
        record_count,
        return_geometry,
        spatial_parameters=None,
    ):
        self.page_calls.append(
            {
                "where": where,
                "record_count": record_count,
                "return_geometry": return_geometry,
                "spatial_parameters": dict(spatial_parameters or {}),
            }
        )
        match = re.search(r"OBJECTID > ([0-9]+)", where)
        threshold = int(match.group(1)) if match else -1
        return tuple(
            feature
            for feature in self.features
            if feature["attributes"]["OBJECTID"] > threshold
        )[:record_count]


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(nj, "log_search", lambda *_args, **_kwargs: None)


@pytest.fixture
def features():
    return _load("features.json")


def test_omitted_limit_exhausts_selected_matches(features):
    client = FakeClient(features, page_size=2)
    args = nj.build_parser().parse_args(["search", "--all"])

    result = nj.execute(args, client=client)

    assert result.status.value == "ok"
    assert result.query.query.requested_limit is None
    assert [record["object_id"] for record in result.records] == [1, 2, 799]
    assert result.next_cursor is None
    assert [call["record_count"] for call in client.page_calls] == [2, 1]
    assert "OBJECTID > 2" in client.page_calls[1]["where"]
    assert result.records[0]["source_snapshot"]["pages_fetched"] == 2
    assert result.records[0]["source_snapshot"][
        "reported_total_matches"
    ] == 3


def test_bounded_query_returns_and_resumes_keyset_cursor(features):
    first_client = FakeClient(features)
    first_args = nj.build_parser().parse_args(
        ["search", "--all", "--limit", "2"]
    )

    first = nj.execute(first_args, client=first_client)

    assert [record["object_id"] for record in first.records] == [1, 2]
    assert first.next_cursor

    second_client = FakeClient(features)
    second_args = nj.build_parser().parse_args(
        [
            "search",
            "--all",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ]
    )
    second = nj.execute(second_args, client=second_client)

    assert second.status.value == "ok"
    assert [record["object_id"] for record in second.records] == [799]
    assert second.next_cursor is None
    assert "OBJECTID > 2" in second_client.page_calls[0]["where"]


def test_cursor_rejects_different_query_criteria(features):
    first = nj.execute(
        nj.build_parser().parse_args(
            ["search", "--county", "Essex", "--limit", "1"]
        ),
        client=FakeClient(features),
    )
    args = nj.build_parser().parse_args(
        [
            "search",
            "--county",
            "Middlesex",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )

    result = nj.execute(args, client=FakeClient(features))

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "cursor_query_mismatch"


def test_cursor_rejects_source_refresh(features):
    first = nj.execute(
        nj.build_parser().parse_args(
            ["search", "--all", "--limit", "1"]
        ),
        client=FakeClient(features, snapshots=[_snapshot(data_version=100)]),
    )
    args = nj.build_parser().parse_args(
        [
            "search",
            "--all",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )

    result = nj.execute(
        args,
        client=FakeClient(
            features,
            snapshots=[_snapshot(data_version=101)],
        ),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "cursor_snapshot_changed"


def test_cursor_rejects_official_item_service_migration(features):
    first = nj.execute(
        nj.build_parser().parse_args(
            ["search", "--all", "--limit", "1"]
        ),
        client=FakeClient(features),
    )
    args = nj.build_parser().parse_args(
        [
            "search",
            "--all",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )

    result = nj.execute(
        args,
        client=FakeClient(
            features,
            snapshots=[
                _snapshot(
                    layer_url=(
                        "https://services.example.test/Replacement/"
                        "FeatureServer/0"
                    )
                )
            ],
        ),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "cursor_service_changed"


def test_source_change_during_exhaustive_query_is_partial(features):
    client = FakeClient(features, full_counts=[3, 4])
    args = nj.build_parser().parse_args(["search", "--all"])

    result = nj.execute(args, client=client)

    assert result.status.value == "partial"
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert result.errors[0].code == "source_changed_during_traversal"


def test_county_filter_uses_native_parcel_code_not_joined_name(features):
    client = FakeClient(features)
    args = nj.build_parser().parse_args(
        [
            "search",
            "--county",
            "Essex County",
            "--has-modiv",
            "no",
            "--limit",
            "1",
        ]
    )

    result = nj.execute(args, client=client)

    assert result.status.value == "ok"
    where = client.count_calls[0]["where"]
    assert "PCL_MUN LIKE '07%'" in where
    assert "GIS_PIN IS NULL" in where
    assert "COUNTY=" not in where


def test_municipality_name_filter_reports_partial_join_coverage(features):
    client = FakeClient(features)
    args = nj.build_parser().parse_args(
        [
            "address",
            "FOREST AVE",
            "--municipality",
            "CALDWELL",
            "--limit",
            "1",
        ]
    )

    result = nj.execute(args, client=client)

    assert result.status.value == "ok"
    assert any(
        "municipality-code" in warning for warning in result.warnings
    )
    assert "UPPER(MUN_NAME)" in client.count_calls[0]["where"]


def test_block_lot_preserves_source_native_identifiers(features):
    client = FakeClient(features)
    args = nj.build_parser().parse_args(
        [
            "block-lot",
            "--municipality-code",
            "1225",
            "--block",
            "299",
            "--lot",
            "1.02",
            "--qualifier",
            "C0304",
            "--limit",
            "1",
        ]
    )

    nj.execute(args, client=client)

    where = client.count_calls[0]["where"]
    assert "PCL_MUN='1225'" in where
    assert "PCLBLOCK='299'" in where
    assert "PCLLOT='1.02'" in where
    assert "PCLQCODE='C0304'" in where


def test_pin_matches_all_three_source_pin_representations(features):
    client = FakeClient(features)
    args = nj.build_parser().parse_args(
        ["pin", "0703_14_6", "--limit", "1"]
    )

    nj.execute(args, client=client)

    where = client.count_calls[0]["where"]
    assert "PAMS_PIN='0703_14_6'" in where
    assert "PIN_NODUP='0703_14_6'" in where
    assert "GIS_PIN='0703_14_6'" in where


def test_point_query_preserves_spatial_contract_and_geometry(features):
    client = FakeClient(features)
    args = nj.build_parser().parse_args(
        ["point", "-74.30143", "40.55346", "--limit", "1"]
    )

    result = nj.execute(args, client=client)

    call = client.page_calls[0]
    assert call["return_geometry"] is True
    assert call["spatial_parameters"] == {
        "geometry": "-74.30143,40.55346",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }
    assert result.records[0]["geometry_crs"] == "EPSG:4326"


def test_normalization_preserves_assessment_sale_and_redaction(features):
    result = nj.execute(
        nj.build_parser().parse_args(
            ["search", "--all", "--limit", "2"]
        ),
        client=FakeClient(features),
    )
    record = result.records[1]

    assert record["canonical_ref"].startswith(
        "PROPERTY:us-nj-njgin-parcels-modiv/34013/parcel/"
    )
    assert record["jurisdiction"]["county_name"] == "Essex"
    assert record["jurisdiction"]["county_geoid"] == "34013"
    assert record["owner_observation"] == {
        "raw_name": None,
        "visibility_state": "redacted_by_source",
        "source_field": "OWNER_NAME",
        "policy_url": nj.LANDING_URL,
    }
    assert record["assessment"]["net_assessed_value"] == 502600
    assert record["assessment"]["last_year_tax"] == 16002.78
    assert record["last_sale_and_deed_reference"]["sale_price"] == 675000
    assert record["last_sale_and_deed_reference"]["deed_date"] == "2008-07-29"
    assert record["physical_characteristics"]["additional_lots"] == ("14/5A",)


def test_parcel_without_modiv_keeps_derived_county_identity(features):
    result = nj.execute(
        nj.build_parser().parse_args(["search", "--all"]),
        client=FakeClient(features),
    )
    record = result.records[2]

    assert record["modiv_join"]["state"] == "parcel_without_joined_modiv"
    assert record["jurisdiction"]["county_name"] == "Essex"
    assert record["jurisdiction"]["county_geoid"] == "34013"
    assert record["jurisdiction"]["municipality_code"] == "0703"
    assert record["jurisdiction"]["municipality_name"] is None
    assert record["assessment"]["net_assessed_value"] is None


def test_alternatives_keep_bulk_sales_assessor_and_instruments_distinct():
    args = nj.build_parser().parse_args(["alternatives"])

    result = nj.execute(args)

    source_ids = {record["source_id"] for record in result.records}
    assert "us-nj-njgin-modiv-tax-list" in source_ids
    assert "us-nj-treasury-modiv-files" in source_ids
    assert "us-nj-treasury-sr1a-sales" in source_ids
    assert "us-nj-local-assessors-tax-boards" in source_ids
    assert "us-nj-county-clerks-registers" in source_ids
    sr1a = next(
        record
        for record in result.records
        if record["source_id"] == "us-nj-treasury-sr1a-sales"
    )
    assert "grantor and grantee" in sr1a["adds"]


def test_count_without_filters_is_a_cheap_statewide_count(features):
    client = FakeClient(features, full_counts=[3_478_727])
    args = nj.build_parser().parse_args(["count"])

    result = nj.execute(args, client=client)

    assert result.status.value == "ok"
    assert result.records[0]["count"] == 3_478_727
    assert result.records[0]["where"] == "1=1"
    assert client.page_calls == []


def test_search_without_selector_requires_explicit_all(features):
    args = nj.build_parser().parse_args(["search"])

    result = nj.execute(args, client=FakeClient(features))

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "missing_search_selector"


def test_source_snapshot_requires_every_preserved_field():
    with pytest.raises(SourceSchemaError) as raised:
        nj._compatible_snapshot(
            _item_metadata(),
            _layer_metadata(missing={"DEED_PAGE"}),
            nj.DEFAULT_LAYER_URL,
        )

    assert raised.value.details["missing_fields"] == ["DEED_PAGE"]


def test_source_snapshot_accepts_current_official_contract():
    snapshot = nj._compatible_snapshot(
        _item_metadata(),
        _layer_metadata(data_version=1775046615578),
        nj.DEFAULT_LAYER_URL,
    )

    assert snapshot.layer_url == nj.DEFAULT_LAYER_URL
    assert snapshot.native_page_size == 2_000
    assert snapshot.dataset_version == 1775046615578
    assert re.fullmatch(r"[0-9a-f]{64}", snapshot.schema_fingerprint)


def test_client_resolves_layer_url_from_current_arcgis_item(monkeypatch):
    replacement_service = (
        "https://services.example.test/NJGIN/FeatureServer"
    )
    item = _item_metadata(service_url=replacement_service)
    layer = _layer_metadata()
    calls = []
    client = nj.NewJerseyParcelClient(minimum_interval=0)

    def fake_request(url, *, params):
        calls.append((url, params))
        if url == nj.ITEM_API_URL:
            return item
        if url == f"{replacement_service}/0":
            return layer
        raise AssertionError(url)

    monkeypatch.setattr(client, "_request_json", fake_request)

    snapshot = client.fetch_snapshot()

    assert snapshot.layer_url == f"{replacement_service}/0"
    assert client.layer_url == f"{replacement_service}/0"
    assert [call[0] for call in calls] == [
        nj.ITEM_API_URL,
        f"{replacement_service}/0",
    ]


def test_parser_has_no_implicit_result_limit():
    args = nj.build_parser().parse_args(
        ["address", "304 MAPLE HILL DR"]
    )

    assert args.limit is None
    assert args.page_size == 2_000


@pytest.mark.skipif(
    os.getenv("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official endpoint probes",
)
def test_live_probe_resolves_current_item_and_known_parcel():
    args = nj.build_parser().parse_args(["probe"])

    result = nj.execute(args)

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["native_parcel_id"] == nj.PROBE_PIN
    assert record["situs_address"]["raw"] == nj.PROBE_ADDRESS
    assert record["source_snapshot"]["resolved_layer_url"].startswith(
        "https://services"
    )
    assert record["owner_observation"]["visibility_state"] == (
        "redacted_by_source"
    )
