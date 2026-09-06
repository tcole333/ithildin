from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools import query_palm_beach_property_appraiser as palm
from tools.public_records_store import canonical_property_ref


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "palm_beach_property_appraiser"
)


def _metadata() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8"))


def _features() -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / "features.json").read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self) -> None:
        self.request_count = 0
        self.features = _features()

    def fetch_metadata(self, layer_url: str = palm.LAYER_URL):
        self.request_count += 1
        metadata = _metadata()
        if layer_url == palm.QSALES_LAYER_URL:
            metadata["id"] = 0
            metadata["name"] = palm.QSALES_LAYER_NAME
            metadata["maxRecordCount"] = 2_000
        return metadata

    def fetch_boundary(self, _where, *, parameters=None):
        del parameters
        self.request_count += 1
        return 3

    def fetch_count(self, where, *, parameters=None, query_url=palm.QUERY_URL):
        del parameters, query_url
        self.request_count += 1
        boundaries = [
            int(value)
            for value in re.findall(r"OBJECTID<=([0-9]+)", where)
        ]
        maximum = boundaries[-1] if boundaries else 3
        return len(
            [
                feature
                for feature in self.features
                if feature["attributes"]["OBJECTID"] <= maximum
            ]
        )

    def fetch_page(
        self,
        *,
        where,
        offset,
        record_count,
        return_geometry,
        parameters=None,
    ):
        del where, return_geometry, parameters
        self.request_count += 1
        return tuple(self.features[offset : offset + record_count])


def test_contract_and_normalization_preserve_occurrence_and_redaction() -> None:
    contract = palm.metadata_contract(_metadata())
    first, second, redacted = [
        palm.normalize_feature(
            feature,
            contract=contract,
            geometry_requested=True,
        )
        for feature in _features()
    ]

    assert contract.max_record_count == 2
    assert first["native_parcel_id"] == second["native_parcel_id"]
    assert first["feature_ref"] != second["feature_ref"]
    assert first["canonical_ref"] == canonical_property_ref(
        palm.SOURCE_ID,
        palm.COUNTY_GEOID,
        "parcel_feature",
        "OBJECTID:1",
    )
    assert first["parcel_join_key"]["uniqueness_in_layer"] == "not_assumed"
    assert first["published_identifiers"] == {
        "parcel_number": "04364325000005040",
        "parid": "GEOMETRY-GROUP-7",
        "parid_role": "published_geometry_or_group_identifier",
        "parid_uniqueness_assumed": False,
    }
    assert first["last_sale"]["recorded_title_evidence"] is False
    assert first["last_sale"]["book_page_pivot"]["source_id"] == (
        palm.CLERK_SOURCE_ID
    )
    assert redacted["owners"] == []
    assert redacted["situs_address"] is None
    assert redacted["publisher_redaction_state"]["confidential_flag"] == "Y"
    assert set(
        redacted["publisher_redaction_state"]["blank_owner_or_address_fields"]
    ) == {
        "OWNER_NAME1",
        "OWNER_NAME2",
        "SITE_ADDR_STR",
        "PADDR1",
        "PADDR2",
        "PADDR3",
    }


def test_complete_and_bounded_traversal_use_live_page_size_and_bound_cursor() -> None:
    complete = palm.fetch_feature_batch(
        FakeClient(),
        operation="list",
        spec=palm.QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=None,
        cursor=None,
    )
    assert [palm._feature_object_id(item) for item in complete.features] == [
        1,
        2,
        3,
    ]
    assert complete.next_cursor is None

    client = FakeClient()
    first = palm.fetch_feature_batch(
        client,
        operation="list",
        spec=palm.QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=1,
        cursor=None,
    )
    assert first.next_cursor
    second = palm.fetch_feature_batch(
        client,
        operation="list",
        spec=palm.QuerySpec(
            where="1=1",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=1,
        cursor=first.next_cursor,
    )
    assert palm._feature_object_id(first.features[0]) == 1
    assert palm._feature_object_id(second.features[0]) == 2


def test_cursor_is_bound_to_query_and_schema() -> None:
    first = palm.fetch_feature_batch(
        FakeClient(),
        operation="owner",
        spec=palm.QuerySpec(
            where="OWNER_NAME1 LIKE '%EXAMPLE%'",
            geometry_parameters={},
            return_geometry=False,
        ),
        limit=1,
        cursor=None,
    )
    with pytest.raises(palm.PalmBeachPropertyError, match="different"):
        palm.fetch_feature_batch(
            FakeClient(),
            operation="owner",
            spec=palm.QuerySpec(
                where="OWNER_NAME1 LIKE '%ANOTHER%'",
                geometry_parameters={},
                return_geometry=False,
            ),
            limit=1,
            cursor=first.next_cursor,
        )

    changed = FakeClient()
    original_fetch = changed.fetch_metadata

    def changed_metadata(layer_url=palm.LAYER_URL):
        metadata = deepcopy(original_fetch(layer_url))
        metadata["fields"].append(
            {
                "name": "NEW_FIELD",
                "alias": "NEW_FIELD",
                "type": "esriFieldTypeString",
            }
        )
        return metadata

    changed.fetch_metadata = changed_metadata
    with pytest.raises(
        palm.PalmBeachPropertyError,
        match="schema changed",
    ):
        palm.fetch_feature_batch(
            changed,
            operation="owner",
            spec=palm.QuerySpec(
                where="OWNER_NAME1 LIKE '%EXAMPLE%'",
                geometry_parameters={},
                return_geometry=False,
            ),
            limit=1,
            cursor=first.next_cursor,
        )


def test_native_selectors_and_defaults_are_not_artificial_bounds() -> None:
    parcel = palm.build_parser().parse_args(
        ["parcel", "04364325000005040"]
    )
    dashed_parcel = palm.build_parser().parse_args(
        ["parcel", "04-36-43-25-00-000-5040"]
    )
    explicit_sale = palm.build_parser().parse_args(
        ["sale", "5021/1011", "--field", "book-page"]
    )
    detected_sale = palm.build_parser().parse_args(
        ["sale", "5021/1011"]
    )
    point = palm.build_parser().parse_args(["point", "-80.1", "26.7"])

    assert parcel.limit is None
    assert parcel.minimum_interval == 0
    assert palm._query_spec(parcel).where == (
        "PARCEL_NUMBER='04364325000005040'"
    )
    assert palm._query_spec(dashed_parcel).where == (
        "PARCEL_NUMBER='04364325000005040'"
    )
    assert palm.build_query(dashed_parcel).query.parameters["query"] == (
        "04-36-43-25-00-000-5040"
    )
    assert palm._query_spec(explicit_sale).where == (
        "BOOK='5021' AND PAGE='1011'"
    )
    assert palm._query_spec(detected_sale).where == (
        "BOOK='5021' AND PAGE='1011'"
    )
    assert palm._query_spec(point).return_geometry is True


def test_parcel_selector_normalization_is_exact_and_pcn_shaped() -> None:
    exact = palm.build_parser().parse_args(
        [
            "search",
            "04 36 43 25 00 000 5040",
            "--field",
            "parcel",
            "--match",
            "exact",
        ]
    )
    contains = palm.build_parser().parse_args(
        [
            "search",
            "04-36-43",
            "--field",
            "parcel",
            "--match",
            "contains",
        ]
    )

    assert palm._query_spec(exact).where == (
        "PARCEL_NUMBER='04364325000005040'"
    )
    assert palm._query_spec(contains).where == (
        "PARCEL_NUMBER LIKE '%04-36-43%'"
    )
