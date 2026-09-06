from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import pytest

from tools import query_md_mdp_parcel_points as mdp
from tools.public_records_http import PaginationError
from tools.public_records_store import canonical_property_ref


def _metadata(*, max_record_count: int = 2) -> dict[str, Any]:
    fields = [
        {
            "name": field_name,
            "alias": field_name,
            "type": (
                "esriFieldTypeOID"
                if field_name == mdp.OBJECT_ID_FIELD
                else "esriFieldTypeString"
            ),
        }
        for field_name in mdp.REQUIRED_FIELDS
    ]
    return {
        "name": mdp.LAYER_NAME,
        "type": "Feature Layer",
        "geometryType": mdp.GEOMETRY_TYPE,
        "objectIdField": mdp.OBJECT_ID_FIELD,
        "fields": fields,
        "capabilities": "Map,Query,Data",
        "maxRecordCount": max_record_count,
        "sourceSpatialReference": {
            "wkid": 102100,
            "latestWkid": 3857,
        },
        "advancedQueryCapabilities": {
            "supportsPagination": True,
            "supportsOrderBy": True,
            "supportsStatistics": True,
        },
    }


def _feature(object_id: int, account_id: str) -> dict[str, Any]:
    return {
        "attributes": {
            "OBJECTID": object_id,
            "JURSCODE": "1901",
            "ACCTID": account_id,
            "ADDRESS": "100 TEST POINT RD",
        },
        "geometry": {
            "x": -76.634,
            "y": 38.301,
        },
    }


class FakeClient:
    def __init__(self) -> None:
        self.request_count = 0
        self.features = [
            _feature(1, "1901000047"),
            _feature(2, "1901000047"),
            _feature(3, "1901000048"),
        ]

    def fetch_metadata(self):
        self.request_count += 1
        return _metadata()

    def fetch_boundary(self, _where, *, parameters=None):
        del parameters
        self.request_count += 1
        return 3

    def fetch_count(self, where, *, parameters=None):
        del parameters
        self.request_count += 1
        boundaries = [
            int(value)
            for value in re.findall(r"OBJECTID<=([0-9]+)", where)
        ]
        maximum = min(boundaries) if boundaries else 3
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
        features = tuple(self.features[offset : offset + record_count])
        return mdp.FeaturePage(
            features=features,
            exceeded_transfer_limit=(
                offset + len(features) < len(self.features)
            ),
        )


def _representative_feature() -> dict[str, Any]:
    return {
        "attributes": {
            "OBJECTID": 1,
            "JURSCODE": "1901",
            "ACCTID": "1901000047",
            "DIGXCORD": 1324567.25,
            "DIGYCORD": 321234.5,
            "CT2020": "24037990100",
            "BG2020": "240379901001",
            "GEOGCODE": "01",
            "OOI": "H",
            "RESITYP": "STD",
            "ADDRESS": "100 TEST POINT RD",
            "STRTNUM": 100,
            "STRTDIR": None,
            "STRTNAM": "TEST POINT",
            "STRTTYP": "RD",
            "STRTSFX": None,
            "STRTUNT": "UNIT 4",
            "ADDRTYP": "S",
            "CITY": "LEONARDTOWN",
            "ZIPCODE": "20650",
            "OWNADD1": "PO BOX 123",
            "OWNADD2": "ATTN TAX DESK",
            "OWNCITY": "LEONARDTOWN",
            "OWNSTATE": "MD",
            "OWNERZIP": "20650",
            "OWNZIP2": "0123",
            "PREMSNUM": "100",
            "PREMSDIR": None,
            "PREMSNAM": "TEST POINT",
            "PREMSTYP": "RD",
            "PREMCITY": "LEONARDTOWN",
            "PREMZIP": "20650",
            "PREMZIP2": "0001",
            "LEGAL1": "LOT 4",
            "LEGAL2": "TEST POINT SUB",
            "LEGAL3": None,
            "DR1LIBER": "01234",
            "DR1FOLIO": "0567",
            "TOWNCODE": "001",
            "DESCTOWN": "LEONARDTOWN",
            "SUBDIVSN": "0042",
            "DSUBCODE": "190042",
            "DESCSUBD": "TEST POINT SUBDIVISION",
            "PLAT": "000321",
            "PLTLIBER": "0000123",
            "PLTFOLIO": "0045",
            "SECTION": "A",
            "BLOCK": "B",
            "LOT": "4",
            "MAP": "0012",
            "GRID": "0003",
            "PARCEL": "0042",
            "ZONING": "RL",
            "ZNCHGDAT": "20200102",
            "RZREALDAT": None,
            "CIUSE": None,
            "DESCCIUSE": None,
            "EXCLASS": None,
            "DESCEXCL": None,
            "LU": "R",
            "DESCLU": "Residential",
            "ACRES": 1.25,
            "LANDAREA": 54450,
            "LUOM": "S",
            "WIDTH": 150,
            "DEPTH": 363,
            "PFUW": "Y",
            "PFUS": "Y",
            "PFLW": "N",
            "PFSP": "Y",
            "PFSU": "N",
            "PERMITTYP": "NEW",
            "YEARBLT": "1998",
            "SQFTSTRC": 2400,
            "STRUGRAD": "A",
            "DESCGRAD": "Good",
            "STRUCNST": "FR",
            "DESCCNST": "Frame",
            "STRUSTYL": "COL",
            "DESCSTYL": "Colonial",
            "STRUBLDG": "SFD",
            "DESCBLDG": "Single Family Detached",
            "BLDG_STORY": 2,
            "BLDG_UNITS": 1,
            "LASTINSP": "202401",
            "LASTASSD": "202402",
            "ASSESSOR": "0012",
            "GR1LIBR1": "01000",
            "GR1FOLO1": "0200",
            "CONVEY1": 1,
            "TRADATE": "20240517",
            "CONSIDR1": 425000,
            "NFMLNDVL": 125000,
            "NFMIMPVL": 300000,
            "NFMTTLVL": 425000,
            "PTYPE": 1,
            "SDATWEBADR": (
                "https://sdat.dat.maryland.gov/RealProperty/Pages/default.aspx"
            ),
            "MDPVDATE": "07/2026",
            "SDATDATE": "06/2026",
        },
        "geometry": {
            "x": -76.634,
            "y": 38.301,
        },
    }


def test_source_identity_declares_distinct_representation_and_exact_join() -> None:
    metadata = mdp.SOURCE_METADATA.to_dict()["metadata"]

    assert mdp.SOURCE_ID == "us-md-mdp-parcel-points"
    assert mdp.RECORD_IDENTITY_SOURCE_ID == "us-md-sdat-property-hidden"
    assert metadata["record_identity_source_id"] == (
        mdp.RECORD_IDENTITY_SOURCE_ID
    )
    assert metadata["record_identity_field"] == "ACCTID"
    assert metadata["related_representation"] == {
        "source_id": mdp.RECORD_IDENTITY_SOURCE_ID,
        "relationship": "same_authority_dataset_alternative_representation",
        "join_field": "ACCTID",
        "independent_corroboration": False,
    }


def test_metadata_contract_uses_live_capabilities_and_page_ceiling() -> None:
    contract = mdp.metadata_contract(_metadata(max_record_count=2_000))

    assert contract.object_id_field == "OBJECTID"
    assert contract.geometry_type == "esriGeometryPoint"
    assert contract.max_record_count == 2_000
    assert contract.spatial_reference["latestWkid"] == 3857
    assert len(contract.schema_fingerprint) == 64


def test_query_builder_combines_exact_and_classification_filters() -> None:
    args = mdp.build_parser().parse_args(
        [
            "query",
            "--account",
            "19-01-000047",
            "--parcel",
            "0042",
            "--address",
            "O'Neil Road",
            "--match",
            "exact",
            "--county-code",
            "19",
            "--map",
            "0012",
            "--plat",
            "000321",
            "--grid",
            "0003",
            "--land-use",
            "R",
            "--zoning",
            "RL",
        ]
    )
    spec = mdp._query_spec(args)

    assert "(ACCTID='1901000047')" in spec.where
    assert "(UPPER(PARCEL)='0042')" in spec.where
    assert "(UPPER(ADDRESS)='O''NEIL ROAD')" in spec.where
    assert "(JURSCODE LIKE '19%')" in spec.where
    assert "(UPPER(MAP)='0012')" in spec.where
    assert "(UPPER(PLAT)='000321')" in spec.where
    assert "(UPPER(GRID)='0003')" in spec.where
    assert "(UPPER(LU)='R')" in spec.where
    assert "(UPPER(ZONING)='RL')" in spec.where
    assert args.limit is None


def test_native_account_parcel_address_and_spatial_queries() -> None:
    account = mdp.build_parser().parse_args(
        ["account", "19-01-000047"]
    )
    parcel = mdp.build_parser().parse_args(["parcel", "0042"])
    address = mdp.build_parser().parse_args(
        ["address", "100 TEST POINT RD", "--match", "exact"]
    )
    point = mdp.build_parser().parse_args(["point", "-76.634", "38.301"])

    assert mdp._query_spec(account).where == "(ACCTID='1901000047')"
    assert mdp._query_spec(parcel).where == "(UPPER(PARCEL)='0042')"
    assert mdp._query_spec(address).where == (
        "(UPPER(ADDRESS)='100 TEST POINT RD')"
    )
    assert mdp._query_spec(point).return_geometry is True
    assert mdp._query_spec(point).geometry_parameters["inSR"] == 4326


def test_normalization_separates_occurrence_from_shared_account_identity() -> None:
    contract = mdp.metadata_contract(_metadata())
    record = mdp.normalize_feature(
        _representative_feature(),
        contract=contract,
        geometry_requested=True,
    )

    assert record["source_id"] == mdp.SOURCE_ID
    assert record["record_identity_source_id"] == (
        mdp.RECORD_IDENTITY_SOURCE_ID
    )
    assert record["canonical_ref"] == canonical_property_ref(
        mdp.RECORD_IDENTITY_SOURCE_ID,
        "24037",
        "parcel",
        "1901000047",
    )
    assert record["representation_ref"] == canonical_property_ref(
        mdp.SOURCE_ID,
        "24037",
        "parcel_feature",
        "OBJECTID:1",
    )
    assert record["record_identity"]["field"] == "ACCTID"
    assert record["complements"] == [
        {
            "source_id": mdp.RECORD_IDENTITY_SOURCE_ID,
            "relationship": (
                "same_authority_dataset_alternative_representation"
            ),
            "join_field": "ACCTID",
            "join_value": "1901000047",
            "independent_corroboration": False,
        }
    ]
    assert record["feature_occurrence"]["object_id"] == 1
    assert record["jurisdiction"]["sdat_county_code"] == "19"
    assert record["published_identifiers"]["parcel"] == "0042"
    assert record["published_identifiers"]["map"] == "0012"
    assert record["deed_reference"] == {
        "liber": "01234",
        "folio": "0567",
        "instrument_copy_in_source": False,
    }
    assert record["land_use"]["land_use_description"] == "Residential"
    assert record["land"]["acres"] == 1.25
    assert record["structure"]["year_built"] == 1998
    assert record["structure"]["square_feet"] == 2400
    assert record["structure"]["building_style"]["description"] == "Colonial"
    assert record["structure"]["building_type"]["code"] == "SFD"
    assert record["transfer"]["transfer_date"] == "2024-05-17"
    assert record["transfer"]["consideration"] == 425000
    assert record["appraisal"]["new_appraised_full_value"] == 425000
    assert record["freshness"]["mdp_product_publication_date"] == {
        "raw": "07/2026",
        "normalized": "2026-07",
        "precision": "month",
    }
    assert record["geometry"] == {"x": -76.634, "y": 38.301}
    assert record["geometry_role"] == "published_parcel_point"
    assert record["situs_address"]["raw"] == "100 TEST POINT RD"


def test_owner_name_is_not_inferred_from_mailing_address_fields() -> None:
    record = mdp.normalize_feature(
        _representative_feature(),
        contract=mdp.metadata_contract(_metadata()),
        geometry_requested=False,
    )

    assert record["owners"] == []
    assert record["owner_visibility"] == {
        "state": "not_published_in_representation",
        "current_owner_name_field_present": False,
        "owner_mailing_address_field_present": True,
        "mailing_address_establishes_ownership": False,
    }
    assert record["mailing_address"]["raw_address"] == (
        "PO BOX 123, ATTN TAX DESK"
    )
    assert record["mailing_address"]["raw"] == (
        "PO BOX 123, ATTN TAX DESK"
    )
    assert record["mailing_address"]["ownership_assertion"] is False
    assert record["mailing_address"]["current_owner_name_published"] is False
    assert (
        record["source_semantics"]["mailing_address_is_ownership_assertion"]
        is False
    )


def test_complete_traversal_and_bound_continuation_cursor() -> None:
    spec = mdp.QuerySpec(
        where="1=1",
        geometry_parameters={},
        return_geometry=False,
    )
    complete = mdp.fetch_feature_batch(
        FakeClient(),
        operation="list",
        spec=spec,
        limit=None,
        cursor=None,
    )
    assert [mdp._feature_object_id(item) for item in complete.features] == [
        1,
        2,
        3,
    ]
    assert complete.next_cursor is None
    assert complete.transfer_limit_pages == 1

    first = mdp.fetch_feature_batch(
        FakeClient(),
        operation="list",
        spec=spec,
        limit=2,
        cursor=None,
    )
    assert first.next_cursor
    cursor_state = mdp._decode_cursor(first.next_cursor)
    assert cursor_state is not None
    assert cursor_state.boundary_object_id == 3
    assert cursor_state.total_count == 3
    assert cursor_state.offset == 2
    assert cursor_state.last_object_id == 2

    second = mdp.fetch_feature_batch(
        FakeClient(),
        operation="list",
        spec=spec,
        limit=2,
        cursor=first.next_cursor,
    )
    assert [mdp._feature_object_id(item) for item in second.features] == [3]
    assert second.next_cursor is None


def test_cursor_is_bound_to_query_and_schema() -> None:
    first_spec = mdp.QuerySpec(
        where="(JURSCODE LIKE '19%')",
        geometry_parameters={},
        return_geometry=False,
    )
    first = mdp.fetch_feature_batch(
        FakeClient(),
        operation="query",
        spec=first_spec,
        limit=1,
        cursor=None,
    )

    with pytest.raises(mdp.MarylandParcelPointsError, match="different"):
        mdp.fetch_feature_batch(
            FakeClient(),
            operation="query",
            spec=mdp.QuerySpec(
                where="(JURSCODE LIKE '16%')",
                geometry_parameters={},
                return_geometry=False,
            ),
            limit=1,
            cursor=first.next_cursor,
        )

    changed = FakeClient()

    def changed_metadata():
        metadata = deepcopy(_metadata())
        metadata["fields"].append(
            {
                "name": "NEW_PUBLISHED_FIELD",
                "alias": "NEW_PUBLISHED_FIELD",
                "type": "esriFieldTypeString",
            }
        )
        return metadata

    changed.fetch_metadata = changed_metadata
    with pytest.raises(mdp.MarylandParcelPointsError, match="schema changed"):
        mdp.fetch_feature_batch(
            changed,
            operation="query",
            spec=first_spec,
            limit=1,
            cursor=first.next_cursor,
        )


def test_cursor_validates_bounded_population_and_consumed_prefix() -> None:
    spec = mdp.QuerySpec(
        where="1=1",
        geometry_parameters={},
        return_geometry=False,
    )
    first = mdp.fetch_feature_batch(
        FakeClient(),
        operation="list",
        spec=spec,
        limit=1,
        cursor=None,
    )

    population_changed = FakeClient()
    population_count = population_changed.fetch_count

    def changed_count(where, *, parameters=None):
        if where.count("OBJECTID<=") == 1:
            return 4
        return population_count(where, parameters=parameters)

    population_changed.fetch_count = changed_count
    with pytest.raises(mdp.MarylandParcelPointsError, match="population changed"):
        mdp.fetch_feature_batch(
            population_changed,
            operation="list",
            spec=spec,
            limit=1,
            cursor=first.next_cursor,
        )

    prefix_changed = FakeClient()
    prefix_count = prefix_changed.fetch_count

    def changed_prefix_count(where, *, parameters=None):
        if where.count("OBJECTID<=") == 2:
            return 0
        return prefix_count(where, parameters=parameters)

    prefix_changed.fetch_count = changed_prefix_count
    with pytest.raises(mdp.MarylandParcelPointsError, match="ordering changed"):
        mdp.fetch_feature_batch(
            prefix_changed,
            operation="list",
            spec=spec,
            limit=1,
            cursor=first.next_cursor,
        )


def test_exceeded_transfer_limit_cannot_hide_an_incomplete_page() -> None:
    client = FakeClient()

    def incomplete_page(**_kwargs):
        return mdp.FeaturePage(
            features=(client.features[0],),
            exceeded_transfer_limit=True,
        )

    client.fetch_page = incomplete_page
    with pytest.raises(PaginationError, match="incomplete bounded page"):
        mdp.fetch_feature_batch(
            client,
            operation="list",
            spec=mdp.QuerySpec(
                where="1=1",
                geometry_parameters={},
                return_geometry=False,
            ),
            limit=2,
            cursor=None,
        )
