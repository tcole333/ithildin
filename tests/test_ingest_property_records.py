import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tools import (
    query_acris,
    query_arlington_property,
    query_bexar_property,
    query_cook_property,
    query_delaware_firstmap,
    query_denver_property,
    query_govos_recorders,
    query_harris_recorder,
    query_los_angeles_ttc,
    query_miami_dade_recorder,
    query_md_property,
    query_new_jersey_parcels,
    query_new_jersey_sr1a,
    query_oregon_benton_property,
    query_oregon_helion_property,
    query_oregon_helion_recorder,
    query_oregon_jackson_accela,
    query_oregon_lincoln_propertyweb,
    query_oregon_lincoln_taxlots,
    query_oregon_linn_josephine_klamath_assessors,
    query_oregon_lane_marion_parcels,
    query_oregon_multnomah_sail,
    query_oregon_tax_foreclosures,
    query_oregon_wasco_property,
    query_oregon_washington_case_permits,
    query_oregon_washington_property,
    query_oregon_yamhill_property,
    query_orleans_property,
    query_palm_beach_official_records,
    query_palm_beach_property_appraiser,
    query_philadelphia_property,
    query_reeves_records,
    query_wisconsin_parcels,
)
from tools.ingest_property_records import (
    GOVOS_RECORDER_SCOPES,
    PropertyIngestError,
    ingest_nc_envelope,
    ingest_property_envelope,
)
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsError,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    ResultStatus,
    SourceMetadata,
)
from tools.public_records_store import connect_property
from tools.query_nc_property import _normalize_feature, build_query


def _envelope():
    query = build_query(
        "parcel",
        "3013467134",
        county_geoid="37005",
        limit=1,
        cursor=None,
        return_geometry=True,
    )
    record = _normalize_feature(
        {
            "attributes": {
                "objectid": 6061042,
                "parno": "3013467134",
                "altparno": "ALT-3013",
                "ownname": "SMITH, THOMAS",
                "ownname2": "SMITH, JANE",
                "siteadd": "100 MAIN ST",
                "scity": "Sparta",
                "sstate": "NC",
                "szip": "28675",
                "mailadd": "PO BOX 1",
                "mcity": "Sparta",
                "mstate": "NC",
                "mzip": "28675",
                "landval": 1000.01,
                "improvval": 900.02,
                "parval": 1900.03,
                "parvaltype": "ASSESSED",
                "saledatetx": "02-08-2024",
                "sourceref": "BK-1-PG-2",
                "revdatetx": "2025-01-31",
                "reviseyear": 2025,
                "stfips": "37",
                "cntyfips": "005",
                "stcntyfips": "37005",
                "cntyname": "Alleghany",
            },
            "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
        schema_fingerprint="a" * 64,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
        warnings=("county freshness varies",),
    ).to_dict()


def _philadelphia_batch():
    return query_philadelphia_property.TraversalBatch(
        records=(),
        next_cursor=None,
        total_count=1,
        remaining_count=1,
        pages_fetched=1,
        schema_fingerprint="a" * 64,
        dataset_version=1_787_644_800_000,
    )


def _philadelphia_envelope(command: str):
    fixture_dir = Path(
        "tests/fixtures/public_records/philadelphia_property"
    )
    batch = _philadelphia_batch()
    if command == "parcel":
        feature = json.loads(
            (fixture_dir / "opa_features.json").read_text(encoding="utf-8")
        )[0]
        record = query_philadelphia_property._normalize_current(
            feature,
            batch,
            geometry_requested=True,
        )
        args = query_philadelphia_property.build_parser().parse_args(
            ["parcel", record["native_parcel_id"], "--limit", "1"]
        )
    elif command == "history":
        row = json.loads(
            (fixture_dir / "history_rows.json").read_text(encoding="utf-8")
        )[0]
        record = query_philadelphia_property._normalize_history(row, batch)
        args = query_philadelphia_property.build_parser().parse_args(
            ["history", record["native_parcel_id"], "--limit", "1"]
        )
    elif command == "parcel-shape":
        feature = json.loads(
            (fixture_dir / "dor_feature.json").read_text(encoding="utf-8")
        )
        record = query_philadelphia_property._normalize_dor(
            feature,
            batch,
            geometry_requested=True,
        )
        args = query_philadelphia_property.build_parser().parse_args(
            [
                "parcel-shape",
                record["map_registry_number"],
                "--by",
                "registry",
                "--limit",
                "1",
            ]
        )
    else:
        raise AssertionError(f"unknown Philadelphia fixture command {command}")
    return PublicRecordsResult.success(
        query_philadelphia_property.build_query(args),
        [record],
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()


def _cook_envelope():
    query = query_cook_property.build_query(
        "parcel",
        "01-01-106-009-1001",
        tax_year=2026,
        limit=1,
        cursor=None,
    )
    record = query_cook_property._normalize_record(
        {
            "pin": "01011060091001",
            "pin10": "0101106009",
            "year": "2026.0",
            "class": "599",
            "triad_name": "North",
            "triad_code": "2",
            "township_name": "Barrington",
            "township_code": "10",
            "nbhd_code": "10012",
            "tax_code": "10148",
            "zip_code": "60010",
            "lon": "-88.1331071142",
            "lat": "42.1526952977",
            "row_id": "010110600910012026",
        },
        response_schema_fingerprint="cook-response-schema",
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def _bexar_envelope():
    fixture_dir = Path("tests/fixtures/public_records/bexar")
    detail = json.loads(
        (fixture_dir / "hgo_property_detail.json").read_text(encoding="utf-8")
    )
    deeds = json.loads(
        (fixture_dir / "hgo_deed_history.json").read_text(encoding="utf-8")
    )
    geometry = json.loads(
        (fixture_dir / "arcgis_geometry.json").read_text(encoding="utf-8")
    )
    query = query_bexar_property.build_query(
        "detail",
        "358951",
        year=2026,
        limit=1,
        cursor=None,
        return_geometry=True,
    )
    record = query_bexar_property._normalize_detail(detail, deeds)
    record["geometry"] = geometry["features"][0]["geometry"]
    record["geometry_disclaimer"] = query_bexar_property.SOURCE_WARNINGS[1]
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
        warnings=query_bexar_property.SOURCE_WARNINGS,
    ).to_dict()


def _denver_property_envelope():
    query = query_denver_property.build_query(
        "parcel",
        "0017103008000",
        limit=1,
        cursor=None,
        return_geometry=True,
    )
    record = query_denver_property._normalize_feature(
        {
            "attributes": {
                "OBJECTID": 991475,
                "SCHEDNUM": "0017103008000",
                "PARCELNUM": "008",
                "SYSTEM_START_DATE": 1_291_766_400_000,
                "OWNER_NAME": "RODRIGUEZ,BRANDON",
                "OWNER_ADDRESS_LINE1": "16159 RANDOLPH PL",
                "OWNER_CITY": "DENVER",
                "OWNER_STATE": "CO",
                "OWNER_ZIP": "80239",
                "SITUS_ADDRESS_LINE1": "16159 E RANDOLPH PL",
                "SITUS_CITY": "DENVER",
                "SITUS_STATE": "CO",
                "SITUS_ZIP": "80239",
                "PROP_CLASS": "1212",
                "APPRAISED_LAND_VALUE": 71_900,
                "APPRAISED_IMP_VALUE": 431_800,
                "APPRAISED_TOTAL_VALUE": 503_700,
                "ASSESSED_TOTAL_VALUE_LOCAL": 30_830,
                "RECEPTION_NUM": "2026006375",
                "ASAL_INSTR": "SW: SPECIAL WARRANTY",
                "SALE_DATE": 1_767_139_200_000,
                "SALE_PRICE": 500_000,
                "GlobalID": "b974bfab-6d0f-4f3c-9c3e-047c774f5d98",
            },
            "geometry": {
                "rings": [
                    [
                        [3197146.0, 1716270.0],
                        [3197147.0, 1716270.0],
                        [3197146.0, 1716270.0],
                    ]
                ]
            },
        },
        response_schema_fingerprint="denver-property-schema",
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T19:00:00Z",
        warnings=query_denver_property.SOURCE_WARNINGS,
    ).to_dict()


def _arlington_property_envelope():
    query = query_arlington_property.build_query(
        "parcel",
        "03-001-009",
        limit=1,
        cursor=None,
        return_geometry=True,
    )
    record = query_arlington_property._normalize_feature(
        {
            "attributes": {
                "OBJECTID": 1,
                "RPCMSTR": "03001009",
                "PARCEL_ID": "03001009",
                "LRSN": 4234,
                "ZONING": "R-20",
                "OWN_STREET": "3905 44TH ST N",
                "OWN_CITY": "MCLEAN",
                "OWN_STATE": "VA",
                "OWN_ZIP": "22101",
                "PROPERTY_CLASS_DESC": ("510-Res - Vacant(SF & Twnhse)"),
                "NEIGHBORHOOD": 503014,
                "MAP_PAGE": "002-15",
                "LOTSIZE": 30104,
                "LEGAL_DESC": "LT 2 THETFORD SUBD",
                "CHANGE_REASON_TYPE": "01- Annual",
                "ASSESSMENT_DATE": 1_767_225_600_000,
                "IMPROVEMENT": 0,
                "LAND": 2_920_100,
                "TOTAL": 2_920_100,
                "GeoSyncDate": 1_785_303_189_000,
            },
            "geometry": {
                "rings": [
                    [
                        [-8580000.0, 4700000.0],
                        [-8579999.0, 4700000.0],
                        [-8580000.0, 4700000.0],
                    ]
                ]
            },
        },
        response_schema_fingerprint="arlington-property-schema",
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T20:00:00Z",
        warnings=query_arlington_property.SOURCE_WARNINGS,
    ).to_dict()


def _delaware_firstmap_envelope(*, blank_pin: bool = False):
    args = query_delaware_firstmap.build_parser().parse_args(
        [
            "pin",
            "1001300033",
            "--county",
            "New Castle",
            "--geometry",
        ]
    )
    pin = " " if blank_pin else "1001300033"
    polygon = {
        "attributes": {
            "OBJECTID": 18_356_825,
            "PIN": pin,
            "ACRES": 1.25,
            "COUNTY": "New Castle",
            "UPDATED": 1_700_000_000_000,
            "Shape__Area": 54_450,
            "Shape__Length": 950,
        },
        "geometry": {
            "rings": [
                [
                    [-75.6, 39.7],
                    [-75.5, 39.7],
                    [-75.6, 39.7],
                ]
            ]
        },
    }
    centroid = {
        "attributes": {
            "OBJECTID": 18_352_054,
            "PIN": "1001300033",
            "COUNTY": "New Castle",
            "LONGITUDE": -75.55,
            "LATITUDE": 39.72,
            "LAST_UPDATED": 1_710_000_000_000,
            "ZIP_CODE": "19720",
            "CENSUSBLOCK": "100030140002001",
        },
        "geometry": {"x": -75.55, "y": 39.72},
    }
    features = {
        query_delaware_firstmap.POLYGON_LAYER: [polygon],
        query_delaware_firstmap.CENTROID_LAYER: ([] if blank_pin else [centroid]),
    }
    records = query_delaware_firstmap._normalize_features(
        features,
        schema_fingerprints={
            query_delaware_firstmap.POLYGON_LAYER: "p" * 64,
            query_delaware_firstmap.CENTROID_LAYER: "c" * 64,
        },
        geometry_spatial_reference=4326,
    )
    return PublicRecordsResult.success(
        query_delaware_firstmap.build_query(args),
        records,
        retrieved_at="2026-07-29T19:30:00Z",
        warnings=query_delaware_firstmap.SOURCE_WARNINGS,
    ).to_dict()


def _orleans_envelope():
    query = query_orleans_property.build_query(
        "parcel",
        "41050755",
        tax_year=None,
        limit=1,
        cursor=None,
        return_geometry=True,
    )
    record = query_orleans_property._normalize_feature(
        {
            "attributes": {
                "OBJECTID": 106289096,
                "PARCELID": "41050755",
                "TAXBILLID": "615199817",
                "PARID": "1771-NASHVILLEAV",
                "SITEADDRESS": "1771 NASHVILLE AVE, LA, 70115",
                "SITEADDR": "1771 NASHVILLE AVE",
                "SITECITY": "NEW ORLEANS",
                "SITESTATE": "LA",
                "SITEZIP": "70115",
                "OWNERNME1": "CITY OF NEW ORLEANS",
                "PSTLADDRESS": "1300 PERDIDO ST, ROOM 5W06",
                "PSTLCITY": "NEW ORLEANS",
                "PSTLSTATE": "LA",
                "PSTLZIP5": "70112",
                "LNDVALUE": 2_250_000,
                "CNTASSDVAL": 3_447_800,
                "CLASSDSCRP": "EXEMPT",
                "LASTUPDATE": 1781531741000,
                "PRPRTYDSCRP": "PT SQS 69 70 HOME FOR CHILDREN",
                "ASS_SQFT": "94087",
            },
            "geometry": {
                "rings": [
                    [
                        [-90.1146, 29.9323],
                        [-90.1148, 29.9324],
                        [-90.1146, 29.9323],
                    ]
                ]
            },
        },
        schema_fingerprint_value="orleans-schema",
        include_geometry=True,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
        warnings=query_orleans_property.SOURCE_WARNINGS,
    ).to_dict()


def _miami_assessor_envelope():
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-fl-miami-dade-property-appraiser",
            name="Miami-Dade Property Appraiser",
            source_role="assessment_and_parcel",
            base_url="https://apps.miamidadepa.gov/PropertySearch/",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="12086",
            name="Miami-Dade County, Florida",
            state_code="FL",
            county_fips="12086",
        ),
        query=QueryMetadata(
            operation="detail",
            parameters={"selector": "0101000000020"},
            requested_limit=1,
        ),
    )
    record = {
        "source_id": "us-fl-miami-dade-property-appraiser",
        "jurisdiction": {
            "state_code": "FL",
            "state_fips": "12",
            "county_name": "Miami-Dade",
            "county_geoid": "12086",
        },
        "native_parcel_id": "0101000000020",
        "record_view": "property_detail",
        "tax_year": 2026,
        "owners": [
            {
                "raw_name": "EXAMPLE DOWNTOWN LLC",
                "confidence": "high",
                "effective_from": "2026-01-01",
            }
        ],
        "situs_address": {
            "raw": "16 SE 2 ST",
            "city": "Miami",
            "state": "FL",
            "postal_code": "33131",
        },
        "mailing_address": {
            "raw": "31 SE 5TH ST 2704",
            "city": "Miami",
            "state": "FL",
            "postal_code": "33131",
        },
        "assessment": {
            "tax_year": 2026,
            "land_value": 36_118_800,
            "improvement_value": 40_744,
            "parcel_value": 36_159_544,
            "assessed_value": 36_066_820,
            "currency": "USD",
            "assessment_class": "COMMERCIAL",
        },
        "assessment_history": [
            {
                "tax_year": 2026,
                "land_value": 36_118_800,
                "improvement_value": 40_744,
                "parcel_value": 36_159_544,
                "assessed_value": 36_066_820,
                "currency": "USD",
                "assessment_class": "COMMERCIAL",
            },
            {
                "tax_year": 2025,
                "land_value": 33_108_900,
                "improvement_value": 8_584,
                "parcel_value": 33_117_484,
                "assessed_value": 32_788_019,
                "currency": "USD",
                "assessment_class": "COMMERCIAL",
            },
        ],
        "sale_history": [
            {
                "sale_date": "2021-06-23",
                "sale_price": 46_000_000,
                "source_document_ref": "OR:32602:3521",
                "qualified_flag": "Q",
            },
            {
                "sale_date": "2013-05-24",
                "sale_price": 32_620_638,
                "source_document_ref": "OR:28688:1169",
                "qualified_flag": "U",
            },
        ],
        "geometry": {"rings": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        "geometry_format": "esri_json",
        "geometry_crs": "EPSG:4326",
        "geometry_disclaimer": "Source mapping geometry.",
        "schema_fingerprint": "miami-pa-schema",
        "source_links": {
            "record": (
                "https://apps.miamidadepa.gov/PropertySearch/#/?folio=0101000000020"
            )
        },
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def _miami_recorder_envelope():
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-fl-miami-dade-official-records-public",
            name="Miami-Dade Clerk Official Records",
            source_role="recorder_public_detail",
            base_url=("https://onlineservices.miamidadeclerk.gov/officialrecords/"),
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="12086",
            name="Miami-Dade County, Florida",
            state_code="FL",
            county_fips="12086",
        ),
        query=QueryMetadata(
            operation="hydrate",
            parameters={"selector": "2026-R-55844"},
            requested_limit=1,
        ),
    )
    record = {
        "source_id": "us-fl-miami-dade-official-records-public",
        "record_identity_source_id": "us-fl-miami-dade-official-records",
        "native_document_id": "2026-R-55844",
        "jurisdiction": {
            "state_code": "FL",
            "county_name": "Miami-Dade",
            "county_geoid": "12086",
        },
        "instrument_type": "DEED",
        "book": "35134",
        "page": "800",
        "book_type": "R",
        "execution_date": "2026-01-12",
        "recording_date": "2026-01-13",
        "consideration": 1_250_000,
        "legal_description_raw": "MIAMI NORTH PB B-41",
        "is_conveyance": True,
        "parties": [
            {
                "sequence": 1,
                "role": "direct",
                "raw_role_code": "D",
                "name": "EXAMPLE GRANTOR LLC",
                "entity_kind": "firm",
            },
            {
                "sequence": 2,
                "role": "reverse",
                "raw_role_code": "R",
                "name": "EXAMPLE DOWNTOWN LLC",
                "entity_kind": "firm",
            },
        ],
        "parcels": [
            {
                "native_parcel_id": "101000000020",
                "link_method": "source_index_folio",
                "link_confidence": 1.0,
                "address": {
                    "raw": "16 SE 2 ST",
                    "city": "Miami",
                    "state": "FL",
                    "postal_code": "33131",
                },
            }
        ],
        "source_url": ("https://onlineservices.miamidadeclerk.gov/officialrecords/"),
        "schema_fingerprint": "miami-clerk-schema",
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:05:00Z",
    ).to_dict()


def _actual_miami_recorder_envelope():
    fixture = json.loads(
        (
            Path("tests/fixtures/public_records/miami_dade_recorder")
            / "public_hydrate.json"
        ).read_text(encoding="utf-8")
    )
    args = query_miami_dade_recorder.build_parser().parse_args(
        ["hydrate-qs", "fixture-issued-token"]
    )
    query = query_miami_dade_recorder.build_query(args)
    records = query_miami_dade_recorder._public_hydration_records(fixture)
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-28T12:10:00Z",
    ).to_dict()


def _reeves_recorder_envelope():
    record = json.loads(
        (
            Path("tests/fixtures/public_records/reeves_records") / "search_record.json"
        ).read_text(encoding="utf-8")
    )
    args = query_reeves_records.build_parser().parse_args(
        ["search", "18-06481", "--limit", "1"]
    )
    query = query_reeves_records.build_query(args)
    normalized = query_reeves_records.normalize_instrument(
        record,
        schema="reeves-recorder-schema",
    )
    return PublicRecordsResult.success(
        query,
        [normalized],
        retrieved_at="2026-07-29T04:53:00Z",
    ).to_dict()


def _govos_recorder_envelope():
    source_id = "us-pa-berks-recorder-publicsearch"
    tenant = query_govos_recorders.TENANTS_BY_SOURCE[source_id]
    record = json.loads(
        (
            Path("tests/fixtures/public_records/reeves_records") / "search_record.json"
        ).read_text(encoding="utf-8")
    )
    args = query_govos_recorders.build_parser().parse_args(
        [
            "search",
            "--source",
            source_id,
            "18-06481",
            "--limit",
            "1",
        ]
    )
    query = query_reeves_records.build_query(args, tenant=tenant)
    normalized = query_reeves_records.normalize_instrument(
        record,
        schema="shared-govos-recorder-schema",
        tenant=tenant,
    )
    return PublicRecordsResult.success(
        query,
        [normalized],
        retrieved_at="2026-07-29T15:00:00Z",
    ).to_dict()


def _govos_recorder_detail_envelope():
    source_id = "us-pa-berks-recorder-publicsearch"
    tenant = query_govos_recorders.TENANTS_BY_SOURCE[source_id]
    record = json.loads(
        (
            Path("tests/fixtures/public_records/reeves_records")
            / "document_detail.json"
        ).read_text(encoding="utf-8")
    )
    args = query_govos_recorders.build_parser().parse_args(
        [
            "document",
            "--source",
            source_id,
            "20798096",
        ]
    )
    query = query_reeves_records.build_query(args, tenant=tenant)
    normalized = query_reeves_records.normalize_instrument(
        record,
        schema="shared-govos-recorder-detail-schema",
        tenant=tenant,
    )
    return PublicRecordsResult.success(
        query,
        [normalized],
        retrieved_at="2026-07-29T15:01:00Z",
    ).to_dict()


def _denver_marriage_envelope():
    source_id = "us-co-denver-recorder-publicsearch"
    args = query_govos_recorders.build_parser().parse_args(
        [
            "search",
            "--source",
            source_id,
            "--department",
            "MAR",
            "EXAMPLE",
            "--limit",
            "1",
        ]
    )
    tenant = query_govos_recorders.tenant_for_args(args)
    record = json.loads(
        (
            Path("tests/fixtures/public_records/reeves_records") / "search_record.json"
        ).read_text(encoding="utf-8")
    )
    query = query_reeves_records.build_query(args, tenant=tenant)
    normalized = query_reeves_records.normalize_instrument(
        record,
        schema="denver-marriage-index-schema",
        tenant=tenant,
    )
    return PublicRecordsResult.success(
        query,
        [normalized],
        retrieved_at="2026-07-29T18:00:00Z",
    ).to_dict()


def _harris_recorder_envelope():
    fixture_path = (
        Path("tests/fixtures/public_records/harris_recorder") / "exact-result.html"
    )
    payload = query_harris_recorder.parse_results(
        fixture_path.read_text(encoding="utf-8"),
        ("https://www.cclerk.hctx.net/Applications/WebSearch/RP_R.aspx?ID=fixture"),
        selectors={"file_number": "RP-2026-72194"},
    )
    args = query_harris_recorder.build_parser().parse_args(
        ["search", "--file-number", "RP-2026-72194"]
    )
    query = query_harris_recorder.build_query(
        args,
        access_decision={"allowed": True},
        selectors={"file_number": "RP-2026-72194"},
    )
    return PublicRecordsResult.success(
        query,
        payload["results"],
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()


def _oregon_helion_recorder_envelope():
    source_id = "us-or-wasco-helion-recorder"
    tenant = query_oregon_helion_recorder.TENANTS_BY_SOURCE[source_id]
    fixture_path = (
        Path("tests/fixtures/public_records/oregon_helion_recorder")
        / "detail_viewable.html"
    )
    source_url = f"{tenant.portal_root}Document/Details?year=2026&document=1"
    record = query_oregon_helion_recorder.parse_detail_html(
        fixture_path.read_text(encoding="utf-8"),
        tenant=tenant,
        source_url=source_url,
    )
    args = query_oregon_helion_recorder.build_parser().parse_args(
        ["detail", "--source", source_id, "2026", "1"]
    )
    query = query_oregon_helion_recorder.build_query(
        args,
        decision={"source_id": source_id, "allowed": True},
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T12:15:00Z",
    ).to_dict()


def _oregon_tax_foreclosure_envelope():
    source_id = query_oregon_tax_foreclosures.TILLAMOOK_SOURCE_ID
    record = query_oregon_tax_foreclosures.parse_tillamook_foreclosure_list(
        (
            Path("tests/fixtures/public_records/oregon_tax_foreclosures")
            / "tillamook.txt"
        ).read_text(encoding="utf-8")
    )[0]
    publication_document_id = f"{source_id}:foreclosure_list_published:fixture"
    provenance = {
        "source_id": source_id,
        "county_name": "Tillamook County",
        "publisher": "Tillamook County Assessment and Taxation",
        "publication_document_id": publication_document_id,
        "process_stage": (query_oregon_tax_foreclosures.FORECLOSURE_LIST_STAGE),
        "publication_status": "as_published",
        "publication_label": "2025 Foreclosure List",
        "publication_page_url": (
            "https://www.tillamookcounty.gov/assessment/page/"
            "real-property-tax-foreclosure"
        ),
        "document_url": "https://www.tillamookcounty.gov/fixture.pdf",
        "artifact_filename": "fixture.pdf",
        "artifact_sha256": "a" * 64,
        "artifact_size_bytes": 38_084,
        "artifact_media_type": "application/pdf",
        "artifact_page_count": 2,
        "text_state": "searchable",
        "searchable_text_char_count": 1_509,
        "page_searchable_char_counts": [800, 709],
        "text_representation": {
            "method": "llm_transcription",
            "text_sha256": "b" * 64,
            "text_artifact_path": "/tmp/tillamook-fixture.txt",
            "parent_artifact_sha256": "a" * 64,
        },
        "publication_year": 2025,
        "court_case_number": "25-CV47055",
        "general_judgment_date": "2026-01-15",
        "advertising_date": "2025-08-26",
        "deed_to_county_date": "2028-01-15",
    }
    normalized = query_oregon_tax_foreclosures._attach_provenance(
        record,
        provenance,
    )
    args = query_oregon_tax_foreclosures.build_parser().parse_args(
        [
            "search",
            "--source",
            source_id,
            "--artifact",
            "/tmp/tillamook-fixture.pdf",
            "--process-stage",
            query_oregon_tax_foreclosures.FORECLOSURE_LIST_STAGE,
            "--owner",
            "COOPER",
        ]
    )
    query = query_oregon_tax_foreclosures.build_query(
        args,
        source_id=source_id,
        inspection={"publication": provenance},
    )
    return PublicRecordsResult.success(
        query,
        [normalized],
        raw_artifact_refs=("a" * 64,),
        retrieved_at="2026-07-29T20:00:00Z",
    ).to_dict()


def _oregon_helion_property_envelope():
    source_id = "us-or-morrow-helion-property"
    tenant = query_oregon_helion_property.TENANTS_BY_SOURCE[source_id]
    raw = json.loads(
        (
            Path("tests/fixtures/public_records/oregon_helion_property")
            / "detail_morrow_171.json"
        ).read_text(encoding="utf-8")
    )
    record = query_oregon_helion_property._normalize_detail_record(
        tenant,
        raw,
    )
    args = query_oregon_helion_property.build_parser().parse_args(
        ["detail", "171", "--roll-type", "R", "--source", source_id]
    )
    query = query_oregon_helion_property._build_query(
        args,
        tenant,
        access_decision={"source_id": source_id, "allowed": True},
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T19:00:00Z",
    ).to_dict()


def _oregon_linn_josephine_klamath_envelope(source_id: str):
    module = query_oregon_linn_josephine_klamath_assessors
    fixture_by_source = {
        module.LINN_SOURCE_ID: "linn_feature.json",
        module.JOSEPHINE_SOURCE_ID: "josephine_feature.json",
        module.KLAMATH_SOURCE_ID: "klamath_feature.json",
    }
    config = module.SOURCES[source_id]
    feature = json.loads(
        (
            Path(
                "tests/fixtures/public_records/oregon_linn_josephine_klamath_assessors"
            )
            / fixture_by_source[source_id]
        ).read_text(encoding="utf-8")
    )
    record = module._normalize_feature(
        config,
        feature,
        schema_value=f"{source_id}-schema",
        geometry_requested=True,
    )
    query = module._build_query(
        config,
        operation="account",
        selector="fixture",
        search_field="account",
        limit=1,
        cursor=None,
        geometry=True,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T20:30:00Z",
    ).to_dict()


def _oregon_jackson_accela_envelope():
    source = query_oregon_jackson_accela.BUILDING
    query = query_oregon_jackson_accela._query(
        source,
        "record",
        {"cap_key": "26CAP-00000-006GM"},
    )
    record = {
        "source_id": source.source_id,
        "record_kind": source.record_kind,
        "native_record_id": "439-26-002369-ELEC",
        "record_key": {
            "module": "Building",
            "cap_id1": "26CAP",
            "cap_id2": "00000",
            "cap_id3": "006GM",
            "compact": "26CAP-00000-006GM",
        },
        "record_type": "Residential Electrical",
        "status": "Finaled",
        "work_location": "2255 JOHNS PEAK RD CENTRAL POINT OR",
        "record_details": [
            {"label": "Applicant", "value": "STEVE ROBERTS EMR UNIVERSAL LLC"},
            {"label": "Owner", "value": "LUNDIN LESLIE TRUST ET AL"},
            {"label": "Project Description", "value": "14.96kWDC PV array"},
            {"label": "Job Value", "value": "$25,000.00"},
        ],
        "participants": {
            "applicant": "STEVE ROBERTS EMR UNIVERSAL LLC",
            "owner": "LUNDIN LESLIE TRUST ET AL",
            "licensed_professional": "FREDRICK WHITEHEAD 4149S",
        },
        "project_description": "14.96kWDC PV array",
        "application_information": [
            {
                "section": "DATES",
                "fields": [
                    {"label": "Application Date", "value": "07/23/2026"},
                    {"label": "Issued Date", "value": "07/24/2026"},
                ],
            }
        ],
        "additional_information": [],
        "parcels": [
            {
                "parcel_number": "37-2W-17D-500",
                "attributes": [
                    {"label": "ASSESSOR ACCOUNT NUMBER", "value": "10999888"}
                ],
            }
        ],
        "documents": [
            {
                "document_number": "16767279",
                "document_detail_url": (
                    "https://aca-oregon.accela.com/oregon/"
                    "FileUpload/DocumentDetail.aspx?documentNo=16767279"
                ),
            }
        ],
        "representations": {
            "record_detail": {
                "kind": "record_detail",
                "request_url": "https://example.test/detail",
                "response_url": "https://example.test/detail",
                "sha256": "a" * 64,
            },
            "attachment_list": {
                "kind": "attachment_list",
                "request_url": "https://example.test/attachments",
                "response_url": "https://example.test/attachments",
                "sha256": "b" * 64,
            },
        },
        "source_urls": {
            "record_detail": "https://example.test/detail",
            "arcgis_index": source.arcgis_url,
        },
        "schema_fingerprint": "c" * 64,
        "snapshot_complete": True,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T21:00:00Z",
    ).to_dict()


def _deschutes_parcel_envelope():
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-or-deschutes-county-taxlots",
            name="Deschutes County Taxlots FeatureServer",
            source_role="assessment_roll",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="41017",
            name="Deschutes County, Oregon",
            state_code="OR",
            county_fips="41017",
        ),
        query=QueryMetadata(
            operation="parcel",
            parameters={"taxlot": "141031B000700"},
            requested_limit=1,
        ),
    )
    record = {
        "source_id": "us-or-deschutes-county-taxlots",
        "source_url": "https://example.test/deschutes-taxlots/0",
        "record_view": "full_detail",
        "snapshot_complete": True,
        "native_parcel_id": "141031B000700",
        "owners": [],
        "jurisdiction": {
            "state_code": "OR",
            "state_fips": "41",
            "county_name": "Deschutes County",
            "county_geoid": "41017",
        },
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T22:00:00Z",
    ).to_dict()


def _deschutes_cdd_envelope(record, *, operation="account"):
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-or-deschutes-cdd-weblink",
            name="Deschutes County CDD Laserfiche WebLink",
            source_role="development_documents",
            base_url="https://weblink.deschutes.org/CDD/",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="41017",
            name="Deschutes County, Oregon",
            state_code="OR",
            county_fips="41017",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={"account_id": "135278"},
            requested_limit=1,
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T22:15:00Z",
    ).to_dict()


def _oregon_lane_marion_envelope(source_id: str):
    fixture_by_source = {
        query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID: ("lane_parcel"),
        query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID: "lane_sale",
        query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID: ("marion_parcel"),
    }
    config = query_oregon_lane_marion_parcels.SOURCES[source_id]
    feature = json.loads(
        (
            Path("tests/fixtures/public_records/oregon_lane_marion")
            / f"{fixture_by_source[source_id]}.json"
        ).read_text(encoding="utf-8")
    )
    record = query_oregon_lane_marion_parcels._normalize_feature(
        config,
        feature,
        schema_value=f"{source_id}-schema",
        geometry_requested=True,
    )
    operation = (
        "sale"
        if source_id == query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID
        else "parcel"
    )
    query = query_oregon_lane_marion_parcels._build_query(
        config,
        operation=operation,
        selector=config.sentinel_value,
        search_field=config.sentinel_field,
        limit=1,
        cursor=None,
        geometry=True,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T18:30:00Z",
    ).to_dict()


def _maryland_envelope():
    fields = query_md_property.FIELDS
    query = query_md_property.build_query(
        "parcel",
        "04030311078580",
        county_code="04",
        limit=1,
        cursor=None,
    )
    record = query_md_property._normalize_record(
        {
            fields["jurisdiction_code"]: "BACO",
            fields["county_name"]: "Baltimore County",
            fields["account_id"]: "04030311078580",
            fields["property_link"]: {
                "url": "https://sdat.dat.maryland.gov/RealProperty/example"
            },
            fields["finder_link"]: {
                "url": "https://apps.planning.maryland.gov/finderonline/example"
            },
            fields["longitude"]: "-76.7068417664",
            fields["latitude"]: "39.3733046671",
            fields["county_code"]: "04",
            fields["district"]: "03",
            fields["account_number"]: "0311078580",
            fields["owner_occupancy"]: "N",
            fields["address"]: "7 TRAYMORE RD ",
            fields["city"]: "PIKESVILLE",
            fields["postal_code"]: "21208",
            fields["legal_1"]: "0.2191 AC",
            fields["legal_2"]: "7 TRAYMORE RD",
            fields["legal_3"]: "MARLBOROUGH ESTATES",
            fields["deed_liber"]: "48094",
            fields["deed_folio"]: "0187",
            fields["base_land"]: "97100",
            fields["base_improvements"]: "0",
            fields["current_land"]: "97100",
            fields["current_improvements"]: "0",
            fields["current_total"]: "97100",
            fields["assessment_cycle_year"]: "2025",
            fields["source_updated"]: "20250703",
            (
                "sales_segment_1_grantor_name_mdp_field_grntnam1_sdat_field_80"
            ): "BALTIMORE HEBREW CONGREGATION",
            (
                "sales_segment_1_transfer_number_mdp_field_transno1_sdat_field_79"
            ): "000001",
            (
                "sales_segment_1_transfer_date_yyyy_mm_dd_mdp_field_"
                "tradate_sdat_field_89"
            ): "2023.05.31",
            (
                "sales_segment_1_consideration_mdp_field_considr1_sdat_field_90"
            ): "175000",
        },
        response_schema_fingerprint="md-response-schema",
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def _acris_envelope():
    query = query_acris.build_query(
        "document",
        {"document_id": "2024001"},
        borough=None,
        requested_limit=1,
        cursor=None,
    )
    record = {
        "source_id": query_acris.SOURCE_ID,
        "document_id": "2024001",
        "crfn": "2024000000001",
        "document_type": "DEED",
        "document_type_description": "Deed",
        "master": {
            "document_id": "2024001",
            "crfn": "2024000000001",
            "doc_type": "DEED",
            "document_date": "2024-01-02T00:00:00.000",
            "recorded_datetime": "2024-01-03T10:30:00.000",
            "document_amt": "125000",
            "reel_nbr": "123",
            "reel_pg": "456",
        },
        "parties": [
            {
                "document_id": "2024001",
                "party_type": "1",
                "name": "SELLER LLC",
            },
            {
                "document_id": "2024001",
                "party_type": "2",
                "name": "BUYER LLC",
                "address_1": "100 MAIN ST",
                "city": "NEW YORK",
                "state": "NY",
                "zip": "10001",
            },
        ],
        "legals": [
            {
                "document_id": "2024001",
                "borough": "1",
                "block": "123",
                "lot": "45",
                "street_number": "100",
                "street_name": "MAIN ST",
                "unit": "2A",
            }
        ],
        "enrichment_complete": True,
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()


def test_nc_ingestion_preserves_raw_hashes_and_normalizes_model(tmp_path):
    db_path = tmp_path / "property.db"
    source_file = tmp_path / "source-envelope.json"
    envelope = _envelope()
    source_file.write_text(json.dumps(envelope), encoding="utf-8")

    first = ingest_nc_envelope(
        envelope,
        db_path=db_path,
        raw_artifact_path=source_file,
    )
    second = ingest_nc_envelope(_envelope(), db_path=db_path)

    assert first["records_ingested"] == 1
    assert len(first["envelope_sha256"]) == 64
    assert len(first["records"][0]["record_sha256"]) == 64
    assert first["records"][0]["canonical_ref"].endswith("/37005/parcel/3013467134")
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        observation = db.execute(
            """
            SELECT observation_id, raw_artifact_sha256, raw_artifact_path,
                   raw_json
            FROM source_observation
            WHERE record_kind='parcel_snapshot'
            ORDER BY observation_id LIMIT 1
            """
        ).fetchone()
        assert (
            observation["raw_artifact_sha256"]
            == hashlib.sha256(source_file.read_bytes()).hexdigest()
        )
        assert observation["raw_artifact_path"] == str(source_file.resolve())
        assert '"raw_attributes"' in observation["raw_json"]
        assert db.execute("SELECT COUNT(*) FROM parcel_alias").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 2
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == ("2025", 100001, 90002, 190003)
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        geometry = db.execute(
            "SELECT geometry_ref, geometry_format FROM parcel_geometry"
        ).fetchone()
        latest_observation_id = db.execute(
            """
            SELECT observation_id
            FROM source_observation
            WHERE record_kind='parcel_snapshot'
            ORDER BY observation_id DESC LIMIT 1
            """
        ).fetchone()["observation_id"]
        assert geometry["geometry_ref"] == (
            f"source-observation:{latest_observation_id}#/geometry"
        )
        assert geometry["geometry_format"] == "esri_json"
    finally:
        db.close()


def _lincoln_propertyweb_envelope():
    fixture_root = Path("tests/fixtures/public_records/oregon_lincoln_propertyweb")
    source_url = (
        f"{query_oregon_lincoln_propertyweb.BASE_URL}/Property-Detail/"
        "PropertyQuickRefID/R452940/PartyQuickRefID/O0064958"
    )
    record = query_oregon_lincoln_propertyweb.parse_detail_page(
        (fixture_root / "detail.html").read_text(encoding="utf-8"),
        source_url,
        expected_property_quick_ref="R452940",
        expected_party_quick_ref="O0064958",
    )
    query = query_oregon_lincoln_propertyweb._basic_query(
        "detail",
        {
            "property_quick_ref": "R452940",
            "party_quick_ref": "O0064958",
        },
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T20:00:00Z",
    ).to_dict()


def _lincoln_taxlot_envelope():
    fixture = json.loads(
        Path(
            "tests/fixtures/public_records/oregon_lincoln_taxlots/sentinel.json"
        ).read_text(encoding="utf-8")
    )
    record = query_oregon_lincoln_taxlots._normalize_feature(
        fixture["features"][0],
        geometry_requested=True,
        returned_crs=query_oregon_lincoln_taxlots.EXPECTED_RETURNED_CRS,
        schema_value=query_oregon_lincoln_taxlots.EXPECTED_SCHEMA_FINGERPRINT,
    )
    query = query_oregon_lincoln_taxlots._build_query(
        operation="search",
        selector="R452940",
        field="property",
        match="exact",
        geometry=True,
        limit=1,
        cursor=None,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T20:01:00Z",
    ).to_dict()


def _lincoln_recorder_envelope():
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-or-lincoln-helion-recorder",
            name="Lincoln County Helion Digital Research Room",
            source_role="county_recorded_instrument_index",
            base_url=("https://helion.co.lincoln.or.us/DigitalResearchRoomPublic/"),
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="41041",
            name="Lincoln County, Oregon",
            state_code="OR",
            county_fips="41041",
        ),
        query=QueryMetadata(
            operation="detail",
            parameters={"instrument_number": "2025-001695"},
        ),
    )
    record = {
        "source_id": "us-or-lincoln-helion-recorder",
        "source_url": (
            "https://helion.co.lincoln.or.us/"
            "DigitalResearchRoomPublic/Details/2025-001695"
        ),
        "record_kind": "recorded_instrument",
        "native_document_id": "2025-001695",
        "instrument_number": "2025-001695",
        "instrument_type_label": "WARRANTY DEED",
        "recording_date": "2025-02-14",
        "consideration_amount": 425000,
        "legal_descriptions": [
            {
                "property_id": "R452940",
                "map_taxlot": "07-11-03-DC-05800-00",
            }
        ],
        "parties": [
            {"sequence_no": 1, "role": "grantor", "name": "EXAMPLE SELLER"},
            {"sequence_no": 2, "role": "grantee", "name": "EXAMPLE BUYER"},
        ],
        "documents": [],
    }
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T20:02:00Z",
    ).to_dict()


def test_lincoln_propertyweb_and_wfs_project_distinct_joinable_records(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    propertyweb = ingest_property_envelope(
        _lincoln_propertyweb_envelope(),
        db_path=db_path,
    )
    taxlots = ingest_property_envelope(
        _lincoln_taxlot_envelope(),
        db_path=db_path,
    )

    assert propertyweb["records"][0]["assessments_upserted"] >= 1
    assert propertyweb["records"][0]["sales_upserted"] >= 1
    assert propertyweb["records"][0]["tax_events_upserted"] >= 1
    assert propertyweb["records"][0]["document_representations_preserved"] >= 1
    assert taxlots["records"][0]["owners_upserted"] == 1
    assert taxlots["records"][0]["geometry_upserted"] == 1
    assert taxlots["records"][0]["join_keys_preserved"] == {
        "propertyweb_property_quick_ref": "R452940",
        "propertyweb_map_number": "07-11-03-DC-05800-00",
    }

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT source_id, native_parcel_id
            FROM parcel_snapshot
            ORDER BY source_id
            """
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            ("us-or-lincoln-county-taxlots-wfs", "42750936"),
            ("us-or-lincoln-propertyweb", "R452940"),
        ]
        aliases = {
            (row["source_id"], row["alias_type"], row["alias_value"])
            for row in db.execute(
                """
                SELECT source_id, alias_type, alias_value
                FROM parcel_alias
                """
            ).fetchall()
        }
        assert (
            "us-or-lincoln-propertyweb",
            "lincoln_wfs_parcel_id",
            "07-11-03-DC-05800-00",
        ) in aliases
        assert (
            "us-or-lincoln-county-taxlots-wfs",
            "propertyweb_property_quick_ref",
            "R452940",
        ) in aliases
        geometry = db.execute(
            """
            SELECT geometry_format, crs
            FROM parcel_geometry
            """
        ).fetchone()
        assert tuple(geometry) == (
            "geojson",
            query_oregon_lincoln_taxlots.EXPECTED_RETURNED_CRS,
        )
    finally:
        db.close()


def test_lincoln_sale_instrument_links_when_recorder_arrives_later(tmp_path):
    db_path = tmp_path / "property.db"

    propertyweb = ingest_property_envelope(
        _lincoln_propertyweb_envelope(),
        db_path=db_path,
    )
    recorder = ingest_property_envelope(
        _lincoln_recorder_envelope(),
        db_path=db_path,
    )

    assert propertyweb["records"][0]["instrument_links_resolved"] == 0
    assert recorder["records"][0]["propertyweb_links_resolved"] == 1
    db = connect_property(db_path)
    try:
        sale = db.execute(
            """
            SELECT native_sale_id, derivation, instrument_id, raw_json
            FROM sale_event
            WHERE source_id='us-or-lincoln-propertyweb'
              AND native_sale_id='2025-001695'
            """
        ).fetchone()
        instrument = db.execute(
            """
            SELECT instrument_id, source_id, native_document_id
            FROM recorded_instrument
            """
        ).fetchone()
        link = db.execute(
            """
            SELECT instrument_id, parcel_id, link_method, link_confidence
            FROM instrument_parcel
            """
        ).fetchone()

        assert sale["derivation"] == "assessment_roll"
        assert sale["instrument_id"] == instrument["instrument_id"]
        assert instrument["source_id"] == "us-or-lincoln-helion-recorder"
        assert instrument["native_document_id"] == "2025-001695"
        assert link["instrument_id"] == instrument["instrument_id"]
        assert link["link_method"] == "propertyweb_sale_instrument"
        assert link["link_confidence"] == 1.0
        assert '"recorder_join_candidate"' in sale["raw_json"]
    finally:
        db.close()


def test_nc_ingestion_rejects_failure_and_wrong_source(tmp_path):
    envelope = _envelope()
    envelope["query"]["source"]["source_id"] = "us-fl-dor-property-roll"
    with pytest.raises(PropertyIngestError, match="requires source"):
        ingest_nc_envelope(envelope, db_path=tmp_path / "property.db")

    query = build_query(
        "parcel",
        "3013467134",
        county_geoid="37005",
        limit=1,
        cursor=None,
        return_geometry=False,
    )
    failure = PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="offline",
                message="offline",
                category="transport",
            )
        ],
    ).to_dict()
    with pytest.raises(PropertyIngestError, match="unsupported ingestion"):
        ingest_nc_envelope(failure, db_path=tmp_path / "property.db")


def test_generic_dispatch_ingests_cook_snapshot_without_inventing_owner(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_cook_envelope(), db_path=db_path)
    second = ingest_property_envelope(_cook_envelope(), db_path=db_path)

    assert first["source_id"] == query_cook_property.SOURCE_ID
    assert first["records"][0]["owner_visibility_state"] == (
        "not_present_in_dataset_schema"
    )
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_alias").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        assessment = db.execute(
            """
            SELECT tax_year, assessment_class, total_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == ("2026", "599", None)
        snapshot = db.execute("SELECT raw_json FROM parcel_snapshot").fetchone()
        assert '"state":"not_present_in_dataset_schema"' in snapshot["raw_json"]
    finally:
        db.close()


def test_generic_dispatch_projects_bexar_assessor_record_and_preserves_detail(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_bexar_envelope(), db_path=db_path)
    second = ingest_property_envelope(_bexar_envelope(), db_path=db_path)

    assert first["source_id"] == query_bexar_property.SOURCE_ID
    assert first["projection_supported"] is True
    assert first["records"][0]["canonical_ref"].endswith("/48029/parcel/358951")
    assert first["records"][0]["aliases_inserted"] == 1
    assert first["records"][0]["addresses_inserted"] == 2
    assert first["records"][0]["owners_upserted"] == 1
    assert first["records"][0]["assessments_upserted"] == 1
    assert first["records"][0]["geometry_upserted"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, roll_year,
                   effective_from, raw_json
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel)[:3] == ("48029", "358951", "2026")
        assert '"instrument_number":"20140198951"' in parcel["raw_json"]
        assert '"roll_history"' in parcel["raw_json"]

        alias = db.execute(
            "SELECT alias_type, alias_value FROM parcel_alias"
        ).fetchone()
        assert tuple(alias) == ("source_alternate", "05936-004-0140")

        owner = db.execute(
            """
            SELECT assertion_type, raw_owner_name, normalized_owner_name,
                   evidence_ref, source_quote
            FROM ownership_assertion
            """
        ).fetchone()
        assert tuple(owner) == (
            "assessment_roll",
            "TAUREAN GENERAL SERVICES",
            "TAUREAN GENERAL SERVICES",
            "PROPERTY:us-tx-bexar-bcad-property/48029/parcel/358951",
            "TAUREAN GENERAL SERVICES",
        )

        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, assessment_class
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2026",
            39_651_000,
            215_946_000,
            255_597_000,
            "RETAIL STORE",
        )

        addresses = {
            row["address_role"]: (
                row["raw_address"],
                row["city"],
                row["state"],
                row["postal_code"],
            )
            for row in db.execute(
                """
                SELECT address_role, raw_address, city, state, postal_code
                FROM parcel_address
                """
            ).fetchall()
        }
        assert addresses == {
            "situs": (
                "26545 INTERSTATE 10 W BOERNE, TX 78006",
                "BOERNE",
                "TX",
                "78006",
            ),
            "mailing": (
                "26545 INTERSTATE 10 W",
                "BOERNE",
                "TX",
                "78006-6500",
            ),
        }

        geometry_row = db.execute(
            "SELECT geometry_format, crs, accuracy_disclaimer FROM parcel_geometry"
        ).fetchone()
        assert tuple(geometry_row) == (
            "esri_json",
            "EPSG:4326",
            query_bexar_property.SOURCE_WARNINGS[1],
        )
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 0
    finally:
        db.close()


def test_generic_dispatch_projects_denver_assessor_and_recorder_join(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _denver_property_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _denver_property_envelope(),
        db_path=db_path,
    )

    assert first["source_id"] == query_denver_property.SOURCE_ID
    assert first["projection_supported"] is True
    projected = first["records"][0]
    assert projected["canonical_ref"].endswith("/08031/parcel/0017103008000")
    assert projected["aliases_inserted"] == 1
    assert projected["addresses_inserted"] == 2
    assert projected["owners_upserted"] == 1
    assert projected["assessments_upserted"] == 1
    assert projected["sales_upserted"] == 1
    assert projected["geometry_upserted"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, effective_from, raw_json
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel)[:3] == (
            "08031",
            "0017103008000",
            "2010-12-08",
        )
        assert '"instrument_number":"2026006375"' in parcel["raw_json"]

        alias = db.execute(
            "SELECT alias_type, alias_value FROM parcel_alias"
        ).fetchone()
        assert tuple(alias) == ("source_alternate", "008")

        assessment = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor, assessment_class
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            7_190_000,
            43_180_000,
            50_370_000,
            3_083_000,
            "1212",
        )

        sale = db.execute(
            """
            SELECT native_sale_id, sale_date, consideration_minor, derivation
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == (
            "2026006375",
            "2025-12-31",
            50_000_000,
            "assessment_roll",
        )

        geometry = db.execute(
            "SELECT geometry_format, crs FROM parcel_geometry"
        ).fetchone()
        assert tuple(geometry) == ("esri_json", "EPSG:2877")
    finally:
        db.close()


def test_generic_dispatch_projects_firstmap_geometry_without_owner_claim(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _delaware_firstmap_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _delaware_firstmap_envelope(),
        db_path=db_path,
    )

    assert first["source_id"] == query_delaware_firstmap.SOURCE_ID
    assert first["projection_supported"] is True
    projected = first["records"][0]
    assert projected["canonical_ref"].endswith("/10003/parcel/1001300033")
    assert projected["geometry_upserted"] == 1
    assert projected["owners_upserted"] == 0
    assert projected["assessments_upserted"] == 0
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, effective_from
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            "10003",
            "1001300033",
            "2024-03-09T16:00:00Z",
        )
        geometry = db.execute(
            "SELECT geometry_format, crs, accuracy_disclaimer FROM parcel_geometry"
        ).fetchone()
        assert tuple(geometry) == (
            "esri_json",
            "EPSG:4326",
            (
                "FirstMap parcel geometry is mapping data and is not a "
                "surveyed legal boundary."
            ),
        )
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 0
    finally:
        db.close()


def test_firstmap_blank_pin_feature_is_preserved_without_projection(
    tmp_path,
):
    result = ingest_property_envelope(
        _delaware_firstmap_envelope(blank_pin=True),
        db_path=tmp_path / "property.db",
    )

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == ("noncanonical_source_feature")
    assert result["projection_skips"][0]["identity_basis"] == (
        "source_object_id_fallback"
    )


def test_generic_dispatch_projects_arlington_assessment_without_owner_name(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _arlington_property_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _arlington_property_envelope(),
        db_path=db_path,
    )

    assert first["source_id"] == query_arlington_property.SOURCE_ID
    projected = first["records"][0]
    assert projected["canonical_ref"].endswith("/51013/parcel/03001009")
    assert projected["addresses_inserted"] == 1
    assert projected["owners_upserted"] == 0
    assert projected["assessments_upserted"] == 1
    assert projected["sales_upserted"] == 0
    assert projected["geometry_upserted"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, roll_year,
                   effective_from
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel)[:3] == ("51013", "03001009", "2026")
        assert parcel["effective_from"].startswith("2026-07-29T")

        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor, assessment_class
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2026",
            292_010_000,
            0,
            292_010_000,
            292_010_000,
            "510-Res - Vacant(SF & Twnhse)",
        )
        mailing = db.execute(
            """
            SELECT address_role, raw_address, city, state, postal_code
            FROM parcel_address
            """
        ).fetchone()
        assert tuple(mailing) == (
            "mailing",
            "3905 44TH ST N, MCLEAN, VA, 22101",
            "MCLEAN",
            "VA",
            "22101",
        )
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        geometry = db.execute(
            "SELECT geometry_format, crs FROM parcel_geometry"
        ).fetchone()
        assert tuple(geometry) == ("esri_json", "EPSG:3857")
    finally:
        db.close()


def test_generic_dispatch_projects_orleans_account_without_collapsing_geopin(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_orleans_envelope(), db_path=db_path)
    second = ingest_property_envelope(_orleans_envelope(), db_path=db_path)

    assert first["source_id"] == query_orleans_property.SOURCE_ID
    assert first["projection_supported"] is True
    assert first["records"][0]["aliases_inserted"] == 3
    assert first["records"][0]["owners_upserted"] == 1
    assert first["records"][0]["assessments_upserted"] == 1
    assert first["records"][0]["geometry_upserted"] == 1
    assert first["records"][0]["canonical_ref"] == (
        "PROPERTY:us-la-orleans-property-viewer/22071/account/TAXBILLID%3A615199817"
    )
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, roll_year,
                   effective_from, raw_json
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel)[:4] == (
            "22071",
            "TAXBILLID:615199817",
            "",
            "2026-06-15T13:55:41Z",
        )
        assert '"tax_bill_id":"615199817"' in parcel["raw_json"]
        assert '"geopin":"41050755"' in parcel["raw_json"]

        aliases = {
            row["alias_value"]
            for row in db.execute("SELECT alias_value FROM parcel_alias").fetchall()
        }
        assert aliases == {
            "615199817",
            "41050755",
            "1771-NASHVILLEAV",
        }

        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, assessed_value_minor,
                   assessment_class
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "",
            225_000_000,
            344_780_000,
            "EXEMPT",
        )

        owner = db.execute("SELECT evidence_ref FROM ownership_assertion").fetchone()
        assert owner["evidence_ref"] == (
            "PROPERTY:us-la-orleans-property-viewer/22071/account/TAXBILLID%3A615199817"
        )

        jurisdictions = {
            row["geoid"]: row["name"]
            for row in db.execute("SELECT geoid, name FROM jurisdiction").fetchall()
        }
        assert jurisdictions == {
            "22": "Louisiana",
            "22071": "Orleans Parish",
        }
        geometry = db.execute(
            "SELECT geometry_format, crs FROM parcel_geometry"
        ).fetchone()
        assert tuple(geometry) == ("esri_json", "EPSG:4326")
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
    finally:
        db.close()


def test_generic_assessment_value_type_does_not_become_assessment_class(
    tmp_path,
):
    envelope = json.loads(json.dumps(_orleans_envelope()))
    envelope["records"][0]["assessment"]["assessment_class"] = None

    ingest_property_envelope(
        envelope,
        db_path=tmp_path / "property.db",
    )

    db = connect_property(tmp_path / "property.db")
    try:
        row = db.execute("SELECT assessment_class, raw_json FROM assessment").fetchone()
        assert row["assessment_class"] is None
        assert '"value_type":"current_assessor_snapshot"' in row["raw_json"]
    finally:
        db.close()


def test_miami_assessor_history_and_recorder_instrument_share_folio(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    assessor_first = ingest_property_envelope(
        _miami_assessor_envelope(),
        db_path=db_path,
    )
    recorder_first = ingest_property_envelope(
        _miami_recorder_envelope(),
        db_path=db_path,
    )
    ingest_property_envelope(_miami_assessor_envelope(), db_path=db_path)
    ingest_property_envelope(_miami_recorder_envelope(), db_path=db_path)

    assert assessor_first["records"][0]["assessments_upserted"] == 2
    assert assessor_first["records"][0]["sales_upserted"] == 2
    assert assessor_first["records"][0]["geometry_upserted"] == 1
    assert recorder_first["records"][0]["parties_upserted"] == 2
    assert recorder_first["records"][0]["parcels_upserted"] == 1
    assert recorder_first["records"][0]["sales_upserted"] == 1

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id, jurisdiction_geoid, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchall()
        assert len(parcels) == 1
        assert tuple(parcels[0])[1:] == (
            "us-fl-miami-dade-property-appraiser",
            "12086",
            "0101000000020",
        )

        assessments = db.execute(
            """
            SELECT tax_year, total_value_minor, assessed_value_minor
            FROM assessment ORDER BY tax_year DESC
            """
        ).fetchall()
        assert [tuple(row) for row in assessments] == [
            ("2026", 3_615_954_400, 3_606_682_000),
            ("2025", 3_311_748_400, 3_278_801_900),
        ]

        owner = db.execute(
            """
            SELECT raw_owner_name, effective_from
            FROM ownership_assertion
            """
        ).fetchone()
        assert tuple(owner) == ("EXAMPLE DOWNTOWN LLC", "2026-01-01")

        geometry = db.execute(
            """
            SELECT geometry_format, crs FROM parcel_geometry
            """
        ).fetchone()
        assert tuple(geometry) == ("esri_json", "EPSG:4326")

        instrument = db.execute(
            """
            SELECT native_document_id, instrument_type, book, page,
                   consideration_minor
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument) == (
            "2026-R-55844",
            "DEED",
            "35134",
            "800",
            125_000_000,
        )
        parties = db.execute(
            """
            SELECT sequence_no, role, raw_name
            FROM instrument_party ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            (1, "direct", "EXAMPLE GRANTOR LLC"),
            (2, "reverse", "EXAMPLE DOWNTOWN LLC"),
        ]
        link = db.execute(
            """
            SELECT ip.parcel_id, ip.link_method, ip.link_confidence
            FROM instrument_parcel ip
            """
        ).fetchone()
        assert tuple(link) == (parcels[0]["parcel_id"], "source_index_folio", 1.0)

        sales = db.execute(
            """
            SELECT source_id, native_sale_id, sale_date, recording_date,
                   consideration_minor, derivation
            FROM sale_event ORDER BY source_id, native_sale_id
            """
        ).fetchall()
        assert len(sales) == 3
        recorder_sale = next(
            row
            for row in sales
            if row["source_id"] == "us-fl-miami-dade-official-records"
        )
        assert tuple(recorder_sale)[1:] == (
            "2026-R-55844",
            "2026-01-12",
            "2026-01-13",
            125_000_000,
            "recorded_instrument",
        )
    finally:
        db.close()


def test_miami_recorder_first_placeholder_is_promoted_by_assessor(tmp_path):
    db_path = tmp_path / "property.db"

    ingest_property_envelope(_miami_recorder_envelope(), db_path=db_path)
    ingest_property_envelope(_miami_assessor_envelope(), db_path=db_path)

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            (
                parcels[0]["parcel_id"],
                "us-fl-miami-dade-property-appraiser",
                "2026",
            )
        ]
        link = db.execute("SELECT parcel_id FROM instrument_parcel").fetchone()
        assert link["parcel_id"] == parcels[0]["parcel_id"]
    finally:
        db.close()


def test_actual_miami_recorder_adapter_output_projects_with_route_provenance(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _actual_miami_recorder_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _actual_miami_recorder_envelope(),
        db_path=db_path,
    )

    assert first["records_ingested"] == 1
    assert second["records_ingested"] == 1
    assert first["records"][0]["canonical_ref"] == (
        "PROPERTY:us-fl-miami-dade-official-records/12086/instrument/2026R55844"
    )

    db = connect_property(db_path)
    try:
        observation = db.execute(
            """
            SELECT source_id, schema_fingerprint
            FROM source_observation
            WHERE record_kind='recorded_instrument'
            ORDER BY observation_id DESC LIMIT 1
            """
        ).fetchone()
        assert observation["source_id"] == ("us-fl-miami-dade-official-records-public")
        assert observation["schema_fingerprint"]

        instrument = db.execute(
            """
            SELECT source_id, native_document_id, execution_date,
                   recording_date
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument) == (
            "us-fl-miami-dade-official-records",
            "2026R55844",
            None,
            "2026-01-27",
        )

        sale = db.execute(
            """
            SELECT source_id, native_sale_id, sale_date, execution_date,
                   recording_date
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == (
            "us-fl-miami-dade-official-records",
            "2026R55844",
            "2026-01-27",
            None,
            "2026-01-27",
        )
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
    finally:
        db.close()


def test_reeves_recorder_projects_instrument_parties_and_document_metadata(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _reeves_recorder_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _reeves_recorder_envelope(),
        db_path=db_path,
    )

    assert first["projection_supported"] is True
    assert first["records_ingested"] == 1
    assert first["records"][0]["parties_upserted"] == 3
    assert first["records"][0]["documents_upserted"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, book, page, execution_date,
                   recording_date, legal_description_raw
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument[:8]) == (
            "us-tx-reeves-county-clerk-official-records",
            "48389",
            "RP:20798096",
            "ASSIGNMENT AND BILL OF SALE",
            "OPR/1576",
            "664",
            "2018-04-16",
            "2018-04-19",
        )
        assert "MULTIPLE PROPERTIES" in instrument["legal_description_raw"]

        parties = db.execute(
            """
            SELECT sequence_no, role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            (1, "grantee", "APR OPERATING LLC"),
            (
                2,
                "grantor",
                "THREE RIVERS ACQUISITION III LLC",
            ),
            (
                3,
                "grantor",
                "THREE RIVERS OPERATING CO III LLC",
            ),
        ]

        document = db.execute(
            """
            SELECT native_document_id, instrument_id, mime_type, page_count,
                   acquisition_method, rights_tier, access_state
            FROM document_artifact
            """
        ).fetchone()
        assert tuple(document) == (
            "RP:20798096:19747017",
            first["records"][0]["instrument_id"],
            "image/png",
            36,
            "portal_metadata",
            "uncertified",
            "public",
        )
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 1
    finally:
        db.close()


def test_shared_govos_recorder_projects_with_tenant_jurisdiction(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _govos_recorder_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _govos_recorder_envelope(),
        db_path=db_path,
    )

    assert first["projection_supported"] is True
    assert first["records_ingested"] == 1
    assert first["records"][0]["parties_upserted"] == 3
    assert first["records"][0]["documents_upserted"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   source_url
            FROM recorded_instrument
            """
        ).fetchone()
        parties = db.execute(
            """
            SELECT role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
    finally:
        db.close()
    assert tuple(instrument[:3]) == (
        "us-pa-berks-recorder-publicsearch",
        "42011",
        "RP:20798096",
    )
    assert instrument["source_url"] == (
        "https://berks.pa.publicsearch.us/doc/20798096?department=RP"
    )
    assert [tuple(row) for row in parties] == [
        ("grantee", "APR OPERATING LLC"),
        ("grantor", "THREE RIVERS ACQUISITION III LLC"),
        ("grantor", "THREE RIVERS OPERATING CO III LLC"),
    ]


def test_govos_ingestion_scopes_follow_the_configured_tenant_registry():
    expected = {
        tenant.source_id: (
            tenant.county_geoid,
            tenant.jurisdiction_name,
            tenant.state_code,
        )
        for tenant in query_govos_recorders.TENANTS
    }

    assert GOVOS_RECORDER_SCOPES == expected
    assert GOVOS_RECORDER_SCOPES[
        "us-oh-franklin-county-recorder-publicsearch"
    ] == ("39049", "Franklin County, Ohio", "OH")


def test_denver_marriage_department_is_preserved_without_property_projection(
    tmp_path,
):
    result = ingest_property_envelope(
        _denver_marriage_envelope(),
        db_path=tmp_path / "property.db",
    )

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"] == [
        {
            "record_index": 0,
            "projection_skipped": True,
            "reason": "non_property_recorder_department",
            "department_code": "MAR",
            "record_kind": "recorded_instrument",
        }
    ]


def test_shared_govos_search_then_detail_preserves_identity_parties_and_label(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    search_envelope = _govos_recorder_envelope()
    detail_envelope = _govos_recorder_detail_envelope()

    search_result = ingest_property_envelope(
        search_envelope,
        db_path=db_path,
    )
    detail_result = ingest_property_envelope(
        detail_envelope,
        db_path=db_path,
    )

    assert (
        search_result["records"][0]["canonical_ref"]
        == search_envelope["records"][0]["canonical_ref"]
        == detail_envelope["records"][0]["canonical_ref"]
        == detail_result["records"][0]["canonical_ref"]
    )
    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT native_document_id, instrument_type
            FROM recorded_instrument
            """
        ).fetchone()
        party_count = db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0]
    finally:
        db.close()

    assert tuple(instrument) == (
        "RP:20798096",
        "ASSIGNMENT AND BILL OF SALE",
    )
    assert party_count == 3


def test_harris_recorder_projects_instrument_and_parties_idempotently(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _harris_recorder_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _harris_recorder_envelope(),
        db_path=db_path,
    )

    assert first["projection_supported"] is True
    assert first["records_ingested"] == 1
    assert first["records"][0]["parties_upserted"] == 3
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, book, page, recording_date,
                   legal_description_raw
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument[:7]) == (
            "us-tx-harris-clerk-real-property",
            "48201",
            "RP-2026-72194",
            "W/D",
            None,
            None,
            "2026-02-26",
        )
        assert "GALENA OAKS" in instrument["legal_description_raw"]

        parties = db.execute(
            """
            SELECT role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            ("grantor", "MARTINEZ CHRIS"),
            ("grantor", "MARTINEZ ESPERANZA"),
            ("grantee", "HOME LIQUIDATORS 2 LLC"),
        ]
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0] == 3
    finally:
        db.close()


def test_miami_search_and_detail_share_current_parcel_identity(tmp_path):
    detail = _miami_assessor_envelope()
    search = json.loads(json.dumps(detail))
    search_record = search["records"][0]
    search_record.pop("tax_year")
    search_record.pop("assessment")
    search_record.pop("assessment_history")
    search_record.pop("sale_history")
    search_record.pop("geometry")
    search_record.pop("geometry_format")
    search_record.pop("geometry_crs")
    search_record["record_view"] = "search_summary"
    search_record["raw_attributes"] = {"search_shape": True}

    for name, envelopes in (
        ("search-first.db", (search, detail)),
        ("detail-first.db", (detail, search)),
    ):
        db_path = tmp_path / name
        for envelope in envelopes:
            ingest_property_envelope(envelope, db_path=db_path)
        db = connect_property(db_path)
        try:
            rows = db.execute(
                """
                SELECT roll_year, raw_json
                FROM parcel_snapshot
                """
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["roll_year"] == "2026"
            assert '"assessment_history"' in rows[0]["raw_json"]
        finally:
            db.close()


def test_complete_assessor_snapshot_closes_superseded_owner(tmp_path):
    db_path = tmp_path / "property.db"
    first = _miami_assessor_envelope()
    second = json.loads(json.dumps(first))
    second["retrieved_at"] = "2026-08-01T15:30:00Z"
    second["records"][0]["owners"] = [
        {
            "raw_name": "NEW DOWNTOWN OWNER LLC",
            "confidence": "high",
        }
    ]

    ingest_property_envelope(first, db_path=db_path)
    result = ingest_property_envelope(second, db_path=db_path)

    assert result["records"][0]["owners_closed"] == 1
    db = connect_property(db_path)
    try:
        owners = db.execute(
            """
            SELECT raw_owner_name, effective_from, effective_to
            FROM ownership_assertion
            ORDER BY ownership_assertion_id
            """
        ).fetchall()
        assert [tuple(owner) for owner in owners] == [
            (
                "EXAMPLE DOWNTOWN LLC",
                "2026-01-01",
                "2026-08-01T15:30:00Z",
            ),
            (
                "NEW DOWNTOWN OWNER LLC",
                "2026-08-01T15:30:00Z",
                None,
            ),
        ]
        assert (
            db.execute(
                """
            SELECT raw_owner_name
            FROM ownership_assertion
            WHERE effective_to IS NULL
            """
            ).fetchone()["raw_owner_name"]
            == "NEW DOWNTOWN OWNER LLC"
        )
        assert (
            db.execute(
                """
            SELECT COUNT(*) FROM source_observation
            WHERE record_kind='parcel_snapshot'
            """
            ).fetchone()[0]
            == 2
        )
    finally:
        db.close()


def test_complete_assessor_snapshot_reconciles_changed_and_absent_addresses(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    first = _miami_assessor_envelope()
    second = json.loads(json.dumps(first))
    second["retrieved_at"] = "2026-08-02T09:45:00Z"
    second_record = second["records"][0]
    second_record["situs_address"] = {}
    second_record["mailing_address"]["postal_code"] = "33132"

    ingest_property_envelope(first, db_path=db_path)
    result = ingest_property_envelope(second, db_path=db_path)

    assert result["records"][0]["addresses_inserted"] == 1
    assert result["records"][0]["addresses_closed"] == 2
    db = connect_property(db_path)
    try:
        addresses = db.execute(
            """
            SELECT address_role, raw_address, postal_code,
                   effective_from, effective_to
            FROM parcel_address
            ORDER BY address_id
            """
        ).fetchall()
        assert [tuple(address) for address in addresses] == [
            (
                "situs",
                "16 SE 2 ST",
                "33131",
                "2026-07-28T12:00:00Z",
                "2026-08-02T09:45:00Z",
            ),
            (
                "mailing",
                "31 SE 5TH ST 2704",
                "33131",
                "2026-07-28T12:00:00Z",
                "2026-08-02T09:45:00Z",
            ),
            (
                "mailing",
                "31 SE 5TH ST 2704",
                "33132",
                "2026-08-02T09:45:00Z",
                None,
            ),
        ]
        current_addresses = db.execute(
            """
            SELECT address_role, postal_code
            FROM parcel_address
            WHERE effective_to IS NULL
            """
        ).fetchall()
        assert [tuple(address) for address in current_addresses] == [
            ("mailing", "33132")
        ]
    finally:
        db.close()


def test_assessor_sale_history_is_idempotent_when_reordered_or_date_missing(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    first = _miami_assessor_envelope()
    first["records"][0]["sale_history"].append(
        {
            "sale_price": 100,
            "source_document_ref": "OR:100:200",
            "qualified_flag": "U",
        }
    )
    second = json.loads(json.dumps(first))
    second["records"][0]["sale_history"].reverse()

    ingest_property_envelope(first, db_path=db_path)
    ingest_property_envelope(second, db_path=db_path)

    db = connect_property(db_path)
    try:
        sales = db.execute(
            """
            SELECT native_sale_id, sale_date
            FROM sale_event ORDER BY native_sale_id
            """
        ).fetchall()
        assert len(sales) == 3
        missing_date = next(
            row for row in sales if row["native_sale_id"] == "OR:100:200"
        )
        assert missing_date["sale_date"] is None
    finally:
        db.close()


def test_miami_recorder_supplements_are_preserved_without_projection(
    tmp_path,
):
    envelope = _miami_recorder_envelope()
    envelope["records"] = [
        {
            "source_id": "us-fl-miami-dade-official-records-public",
            "record_kind": "document_type_reference",
            "document_type": "DEE",
            "description": "Deed",
        }
    ]

    result = ingest_property_envelope(
        envelope,
        db_path=tmp_path / "property.db",
    )

    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"] == [
        {
            "record_index": 0,
            "projection_skipped": True,
            "reason": "supplemental_recorder_record",
            "record_kind": "document_type_reference",
        }
    ]


def test_generic_dispatch_ingests_maryland_without_backfilling_hidden_owner(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_maryland_envelope(), db_path=db_path)
    second = ingest_property_envelope(_maryland_envelope(), db_path=db_path)

    assert first["records"][0]["owner_visibility_state"] == "withheld_by_source"
    assert first["records"][0]["sales_upserted"] == 1
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_alias").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            "2025",
            9_710_000,
            0,
            9_710_000,
            9_710_000,
        )
        sale = db.execute(
            "SELECT native_sale_id, sale_date, consideration_minor, raw_json "
            "FROM sale_event"
        ).fetchone()
        assert tuple(sale)[:3] == (
            "transfer:000001",
            "2023-05-31",
            17_500_000,
        )
        assert "BALTIMORE HEBREW CONGREGATION" in sale["raw_json"]
        snapshot = db.execute("SELECT raw_json FROM parcel_snapshot").fetchone()
        assert '"state":"withheld_by_source"' in snapshot["raw_json"]
    finally:
        db.close()


def _los_angeles_ttc_envelope(
    source,
    operation,
    record,
):
    query = PublicRecordsQuery(
        source=source,
        jurisdiction=query_los_angeles_ttc.JURISDICTION,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T12:00:00Z",
        warnings=query_los_angeles_ttc.SOURCE_WARNINGS,
    ).to_dict()


def test_los_angeles_ttc_components_join_by_ain_with_separate_provenance(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    payment = {
        "canonical_ref": "PROPERTY:LA:TTC:PAYMENT",
        "source_id": query_los_angeles_ttc.PAYMENT_SOURCE_ID,
        "record_kind": "property_tax_payment",
        "native_ids": {
            "ain": "2004001003",
            "payment_id": "7",
            "group_number": "1",
            "sequence": "1",
        },
        "native_parcel_id": "2004001003",
        "ain": "2004001003",
        "formatted_ain": "2004-001-003",
        "tax_year": 2025,
        "installment_key": "2",
        "effective_date": "2026-02-01",
        "amounts": {
            "currency": "USD",
            "tax_paid": "6399.47",
            "penalty_paid": "0.00",
            "cost_paid": "0.00",
            "total_paid": "6399.47",
        },
        "account_snapshot": {
            "street_address": "8321 FAUST AVE",
            "source_last_updated": "2026-07-28",
        },
        "operation_state": "official_payment_row",
        "source_url": query_los_angeles_ttc.PAYMENT_HISTORY_URL,
    }
    sale = {
        "canonical_ref": "PROPERTY:LA:TTC:SALE",
        "source_id": query_los_angeles_ttc.SALE_SOURCE_ID,
        "record_kind": "property_tax_sale_result",
        "native_ids": {
            "ain": "2004001003",
            "item": "1520",
            "auction_cycle": "2025B",
            "sale_phase": "follow_up",
            "sale_id": "2025B:follow_up:1520:2004001003",
        },
        "native_parcel_id": "2004001003",
        "ain": "2004001003",
        "formatted_ain": "2004-001-003",
        "sale_id": "2025B:follow_up:1520:2004001003",
        "auction_cycle": "2025B",
        "sale_phase": "follow_up",
        "status": "sold_as_published",
        "amounts": {
            "currency": "USD",
            "purchase_price": "9900.00",
            "excess_proceeds": "1946.60",
        },
        "publication_date": "2026-05-13",
        "publication": {"artifact_sha256": "a" * 64},
        "excess_proceeds_state": {
            "status": "positive_amount_published",
        },
        "source_url": "https://ttc.lacounty.gov/example-sale.pdf",
    }
    assessor_attributes = json.loads(
        (
            Path("tests/fixtures/public_records/los_angeles_ttc")
            / "assessor_exact.json"
        ).read_text(encoding="utf-8")
    )["features"][0]["attributes"]
    assessor = query_los_angeles_ttc._route_record(assessor_attributes)

    payment_result = ingest_property_envelope(
        _los_angeles_ttc_envelope(
            query_los_angeles_ttc.PAYMENT_METADATA,
            "history",
            payment,
        ),
        db_path=db_path,
    )
    sale_result = ingest_property_envelope(
        _los_angeles_ttc_envelope(
            query_los_angeles_ttc.SALE_METADATA,
            "sale-results",
            sale,
        ),
        db_path=db_path,
    )
    assessor_result = ingest_property_envelope(
        _los_angeles_ttc_envelope(
            query_los_angeles_ttc.ASSESSOR_METADATA,
            "route",
            assessor,
        ),
        db_path=db_path,
    )

    assert payment_result["records"][0]["tax_events_upserted"] == 1
    assert sale_result["records"][0]["tax_events_upserted"] == 2
    assert sale_result["records"][0]["sales_upserted"] == 1
    assert assessor_result["records"][0]["geometry_upserted"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchall()
        assert [tuple(row) for row in parcel] == [
            (
                query_los_angeles_ttc.ASSESSOR_SOURCE_ID,
                "06037",
                "2004001003",
                "2026",
            )
        ]
        events = db.execute(
            """
            SELECT source_id, event_type, amount_minor, native_event_id
            FROM tax_account_event
            ORDER BY event_type
            """
        ).fetchall()
        assert [tuple(row) for row in events] == [
            (
                query_los_angeles_ttc.PAYMENT_SOURCE_ID,
                "property_tax_payment",
                639_947,
                "2004001003:7",
            ),
            (
                query_los_angeles_ttc.SALE_SOURCE_ID,
                "tax_sale_excess_proceeds",
                194_660,
                "2025B:follow_up:1520:2004001003:excess-proceeds",
            ),
            (
                query_los_angeles_ttc.SALE_SOURCE_ID,
                "tax_sale_result",
                990_000,
                "2025B:follow_up:1520:2004001003",
            ),
        ]
        sale_event = db.execute(
            """
            SELECT source_id, native_sale_id, consideration_minor, derivation
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale_event) == (
            query_los_angeles_ttc.SALE_SOURCE_ID,
            "2025B:follow_up:1520:2004001003",
            990_000,
            "tax_sale_publication",
        )
        observation_sources = {
            row["source_id"]
            for row in db.execute(
                """
                SELECT DISTINCT source_id
                FROM source_observation
                WHERE record_kind <> 'query_envelope'
                """
            )
        }
        assert observation_sources == {
            query_los_angeles_ttc.ASSESSOR_SOURCE_ID,
            query_los_angeles_ttc.PAYMENT_SOURCE_ID,
            query_los_angeles_ttc.SALE_SOURCE_ID,
        }
    finally:
        db.close()


def test_oregon_helion_projects_native_aliases_without_losing_provenance(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _oregon_helion_recorder_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _oregon_helion_recorder_envelope(),
        db_path=db_path,
    )

    assert first["projection_supported"] is True
    assert first["records_ingested"] == 1
    assert first["records"][0]["parties_upserted"] == 2
    assert first["records"][0]["documents_upserted"] == 2
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, recording_date, consideration_minor,
                   legal_description_raw, raw_json
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument[:6]) == (
            "us-or-wasco-helion-recorder",
            "41065",
            "2026-000001",
            "DEED",
            "2026-01-02",
            120_000_000,
        )
        assert "Property ID" in instrument["legal_description_raw"]
        assert '"document_image":' in instrument["raw_json"]

        parties = db.execute(
            """
            SELECT role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            ("DIRECT", "SELLER, SAMPLE"),
            ("INDIRECT", "BUYER, SAMPLE"),
        ]
        artifacts = db.execute(
            """
            SELECT native_document_id, mime_type, page_count, access_state
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
        assert [tuple(row) for row in artifacts] == [
            ("2026-000001:image", "application/pdf", 2, "public"),
            ("2026-000001:text", "text/plain", None, "public"),
        ]
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
    finally:
        db.close()


def test_oregon_tax_foreclosure_projects_stage_and_artifact_lineage(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _oregon_tax_foreclosure_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _oregon_tax_foreclosure_envelope(),
        db_path=db_path,
    )

    assert first["projection_supported"] is True
    assert first["records_ingested"] == 1
    assert first["envelope_projection"]["artifacts_upserted"] == 1
    assert first["envelope_projection"]["representations_upserted"] == 1
    assert first["records"][0]["process_stage"] == ("foreclosure_list_published")
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            query_oregon_tax_foreclosures.TILLAMOOK_SOURCE_ID,
            "41057",
            "1N1005AB01100",
            "2025",
        )
        event = db.execute(
            """
            SELECT event_type, event_date, status, native_event_id, raw_json
            FROM tax_account_event
            """
        ).fetchone()
        assert tuple(event[:3]) == (
            "foreclosure_list_published",
            "2025-08-26",
            "as_published",
        )
        assert "publication_document_id" in event["raw_json"]
        assert "parent_artifact_sha256" in event["raw_json"]
        aliases = {
            (row["alias_type"], row["alias_value"])
            for row in db.execute("SELECT alias_type, alias_value FROM parcel_alias")
        }
        assert {
            ("tax_account", "787"),
            ("property_map_id", "1N1005AB01100"),
            ("court_case_number", "25-CV47055"),
        }.issubset(aliases)
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 2
        artifact = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, page_count,
                   source_url, acquisition_method
            FROM document_artifact
            """
        ).fetchone()
        assert tuple(artifact[:4]) == (
            (
                f"{query_oregon_tax_foreclosures.TILLAMOOK_SOURCE_ID}:"
                "foreclosure_list_published:fixture"
            ),
            "a" * 64,
            "application/pdf",
            2,
        )
        assert artifact["source_url"].endswith("/fixture.pdf")
        assert artifact["acquisition_method"] == ("official_publication_inspection")
        representation = db.execute(
            """
            SELECT representation_type, content_hash, model_or_parser,
                   structured_json
            FROM evidence_representation
            """
        ).fetchone()
        assert tuple(representation[:3]) == (
            "derived_text",
            "b" * 64,
            "llm_transcription",
        )
        assert (
            '"parent_artifact_sha256":"' + ("a" * 64)
            in (representation["structured_json"])
        )
        assert '"text_state":"searchable"' in representation["structured_json"]
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 1
        assert (
            db.execute("SELECT COUNT(*) FROM evidence_representation").fetchone()[0]
            == 1
        )
    finally:
        db.close()


def test_oregon_tax_foreclosure_preserves_unparsed_artifact_without_rows(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    envelope = _oregon_tax_foreclosure_envelope()
    envelope["status"] = "partial"
    envelope["records"] = []
    envelope["errors"] = [
        {
            "code": "derived_text_needed",
            "message": "The official PDF needs a derived text representation.",
            "category": "document_representation",
            "retryable": False,
            "details": {"artifact_sha256": "a" * 64, "page_count": 2},
        }
    ]

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["records_seen"] == 0
    assert result["records_ingested"] == 0
    assert result["envelope_projection"]["artifact_sha256"] == "a" * 64
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM tax_account_event").fetchone()[0] == 0
    finally:
        db.close()


def test_oregon_helion_property_projects_account_values_sales_and_addresses(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(
        _oregon_helion_property_envelope(),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _oregon_helion_property_envelope(),
        db_path=db_path,
    )

    assert first["projection_supported"] is True
    projected = first["records"][0]
    assert projected["canonical_ref"].endswith("/41049/parcel/2S2627-DA-02000")
    assert projected["aliases_inserted"] == 1
    assert projected["addresses_inserted"] == 2
    assert projected["owners_upserted"] == 1
    assert projected["assessments_upserted"] == 2
    assert projected["sales_upserted"] == 1
    assert projected["tax_state_preserved"] is True
    assert projected["improvement_records_preserved"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            "us-or-morrow-helion-property",
            "41049",
            "2S2627-DA-02000",
            "2025",
        )
        alias = db.execute(
            "SELECT alias_type, alias_value FROM parcel_alias"
        ).fetchone()
        assert tuple(alias) == ("source_alternate", "171")

        current = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor,
                   total_value_minor, market_value_minor,
                   assessed_value_minor, assessment_class
            FROM assessment
            WHERE tax_year='2025'
            """
        ).fetchone()
        assert tuple(current) == (
            2_690_000,
            8_478_000,
            11_168_000,
            11_168_000,
            4_742_000,
            "109 - RESIDENTIAL MOBILE",
        )
        prior = db.execute(
            """
            SELECT market_value_minor, assessed_value_minor
            FROM assessment
            WHERE tax_year='2024'
            """
        ).fetchone()
        assert tuple(prior) == (10_767_000, 4_604_000)

        sale = db.execute(
            """
            SELECT native_sale_id, sale_date, consideration_minor,
                   qualification_code, derivation
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == (
            "1996-351",
            "1996-03-21",
            2_500_000,
            "16",
            "assessment_roll",
        )
        snapshot_raw = db.execute("SELECT raw_json FROM parcel_snapshot").fetchone()[0]
        assert '"current_balance_due":"729.21"' in snapshot_raw
        assert '"year_built":1978' in snapshot_raw
    finally:
        db.close()


def test_linn_josephine_and_klamath_assessor_rows_keep_county_field_maps(
    tmp_path,
):
    module = query_oregon_linn_josephine_klamath_assessors
    db_path = tmp_path / "property.db"

    results = {
        source_id: ingest_property_envelope(
            _oregon_linn_josephine_klamath_envelope(source_id),
            db_path=db_path,
        )
        for source_id in (
            module.LINN_SOURCE_ID,
            module.JOSEPHINE_SOURCE_ID,
            module.KLAMATH_SOURCE_ID,
        )
    }

    assert all(result["projection_supported"] for result in results.values())
    assert all(result["records_ingested"] == 1 for result in results.values())
    assert all(
        result["records"][0]["geometry_upserted"] == 1 for result in results.values()
    )
    assert all(
        result["records"][0]["owners_upserted"] >= 1 for result in results.values()
    )

    db = connect_property(db_path)
    try:
        parcels = {
            row["source_id"]: (
                row["jurisdiction_geoid"],
                row["native_parcel_id"],
            )
            for row in db.execute(
                """
                SELECT source_id, jurisdiction_geoid, native_parcel_id
                FROM parcel_snapshot
                """
            )
        }
        assert parcels[module.LINN_SOURCE_ID] == ("41043", "16S04W03 00101")
        assert parcels[module.JOSEPHINE_SOURCE_ID] == ("41033", "R333020")
        assert parcels[module.KLAMATH_SOURCE_ID] == ("41035", "871965")

        aliases = {
            (row["source_id"], row["alias_type"], row["alias_value"])
            for row in db.execute(
                "SELECT source_id, alias_type, alias_value FROM parcel_alias"
            )
        }
        assert (
            module.JOSEPHINE_SOURCE_ID,
            "assessment_account",
            "R333020",
        ) in aliases
        assert (
            module.KLAMATH_SOURCE_ID,
            "map_taxlot_normalized",
            "41140050000401",
        ) in aliases

        linn_assessment = db.execute(
            """
            SELECT assessed_value_minor, land_value_minor,
                   improvement_value_minor, total_value_minor
            FROM assessment WHERE source_id=?
            """,
            (module.LINN_SOURCE_ID,),
        ).fetchone()
        assert tuple(linn_assessment) == (
            30_845_700,
            43_932_000,
            43_354_000,
            87_286_000,
        )
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 0
    finally:
        db.close()


def test_jackson_accela_detail_projects_event_and_representation_lineage(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(
        _oregon_jackson_accela_envelope(),
        db_path=db_path,
    )

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 1
    projected = result["records"][0]
    assert projected["documents_listed"] == 1
    assert projected["fetched_representations_preserved"] == 2
    assert projected["representations_upserted"] == 3
    assert projected["parties_upserted"] == 3
    assert projected["parcel_link_method"] == "unresolved_published_map_taxlot"

    db = connect_property(db_path)
    try:
        event = db.execute(
            """
            SELECT source_id, native_event_id, source_record_id, record_kind,
                   event_type, description, status, submitted_date,
                   approved_date, estimated_cost_minor, address_raw,
                   map_taxlot_candidate, longitude, latitude
            FROM property_event
            """
        ).fetchone()
        assert tuple(event) == (
            query_oregon_jackson_accela.BUILDING_SOURCE_ID,
            "439-26-002369-ELEC",
            "26CAP-00000-006GM",
            "building_permit_detail",
            "Residential Electrical",
            "14.96kWDC PV array",
            "Finaled",
            "2026-07-23",
            "2026-07-24",
            2_500_000,
            "2255 JOHNS PEAK RD CENTRAL POINT OR",
            "372W17D500",
            None,
            None,
        )
        parties = {
            (row["role"], row["raw_name"], row["assertion_type"])
            for row in db.execute(
                """
                SELECT role, raw_name, assertion_type
                FROM property_event_party
                """
            )
        }
        assert (
            "owner",
            "LUNDIN LESLIE TRUST ET AL",
            "published_permit_participant",
        ) in parties
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 0
        assert {
            row["representation_kind"]
            for row in db.execute(
                "SELECT representation_kind FROM property_event_representation"
            )
        } == {"record_detail", "attachment_list", "listed_document_detail"}
    finally:
        db.close()


def test_deschutes_cdd_index_projects_document_event_and_exact_parcel_join(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    ingest_property_envelope(_deschutes_parcel_envelope(), db_path=db_path)
    record = {
        "source_id": "us-or-deschutes-cdd-weblink",
        "source_url": "https://weblink.deschutes.org/CDD/DocView.aspx?id=1383062",
        "viewer_url": "https://weblink.deschutes.org/CDD/DocView.aspx?id=1383062",
        "metadata_endpoint": (
            "https://weblink.deschutes.org/CDD/"
            "DocumentService.aspx/GetBasicDocumentInfo"
        ),
        "discovery_source_url": (
            "http://dial.deschutes.org/Real/DevelopmentDocs/135278"
        ),
        "record_kind": "development_document_reference",
        "native_document_id": "1383062",
        "laserfiche_entry_id": "1383062",
        "deschutes_dial_account_id": "135278",
        "map_taxlot": "141031B000700",
        "date_uploaded": "2025-11-24",
        "document_type": "PLANS",
        "description": "Approved site plan",
        "retrieval_state": "viewer_and_metadata_route_available",
        "account_index": {"situs_address": "14987 BUGGY WHIP DR"},
    }
    envelope = _deschutes_cdd_envelope(record)

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    assert first["projection_supported"] is True
    assert first["records_ingested"] == 1
    assert first["records"][0]["parcel_link_method"] == (
        "exact_published_map_taxlot_alias"
    )
    assert first["records"][0]["representations_upserted"] == 3
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        event = db.execute(
            """
            SELECT native_event_id, source_record_id, record_kind, event_type,
                   description, status, submitted_date, address_raw,
                   map_taxlot_candidate
            FROM property_event
            WHERE source_id='us-or-deschutes-cdd-weblink'
            """
        ).fetchone()
        assert tuple(event) == (
            "1383062",
            "1383062",
            "development_document_reference",
            "PLANS",
            "Approved site plan",
            "viewer_and_metadata_route_available",
            "2025-11-24",
            "14987 BUGGY WHIP DR",
            "141031B000700",
        )
        link = db.execute(
            """
            SELECT parcel_id, link_method
            FROM property_event_parcel_link
            """
        ).fetchone()
        assert link["parcel_id"] is not None
        assert link["link_method"] == "exact_published_map_taxlot_alias"
        assert db.execute(
            "SELECT COUNT(*) FROM property_event_representation"
        ).fetchone()[0] == 3
        assert db.execute(
            "SELECT COUNT(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_deschutes_cdd_download_projects_event_and_document_artifact(tmp_path):
    db_path = tmp_path / "property.db"
    record = {
        "source_id": "us-or-deschutes-cdd-weblink",
        "source_url": (
            "https://weblink.deschutes.org/CDD/"
            "ElectronicFile.aspx?docid=1383062&dbid=0&repo=LFCDD"
        ),
        "record_kind": "laserfiche_document_artifact",
        "native_document_id": "1383062",
        "laserfiche_entry_id": "1383062",
        "deschutes_dial_account_id": "135278",
        "map_taxlot": "141031B000700",
        "retrieval_state": "retrieved",
        "retrieval_mode": "electronic_file",
        "media_type": "application/pdf",
        "sha256": "d" * 64,
        "local_path": "/tmp/deschutes-cdd-1383062.pdf",
        "document_metadata": {
            "source_id": "us-or-deschutes-cdd-weblink",
            "source_url": (
                "https://weblink.deschutes.org/CDD/DocView.aspx?id=1383062"
            ),
            "viewer_url": (
                "https://weblink.deschutes.org/CDD/DocView.aspx?id=1383062"
            ),
            "metadata_endpoint": (
                "https://weblink.deschutes.org/CDD/"
                "DocumentService.aspx/GetBasicDocumentInfo"
            ),
            "record_kind": "laserfiche_development_document",
            "native_document_id": "1383062",
            "laserfiche_entry_id": "1383062",
            "map_taxlot": "141031B000700",
            "document_category": "Planning",
            "description": "Approved site plan",
            "created_at": "2025-11-24T10:30:00-08:00",
            "modified_at": "2025-11-25T09:00:00-08:00",
            "retrieval_state": "document_download_available",
            "retrieval_mode": "electronic_file",
            "page_count": 1,
        },
    }

    result = ingest_property_envelope(
        _deschutes_cdd_envelope(record, operation="download"),
        db_path=db_path,
    )

    assert result["records_ingested"] == 1
    assert result["records"][0]["artifacts_upserted"] == 1
    db = connect_property(db_path)
    try:
        artifact = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, page_count,
                   storage_path, acquisition_method, rights_tier, access_state
            FROM document_artifact
            """
        ).fetchone()
        assert tuple(artifact) == (
            "1383062",
            "d" * 64,
            "application/pdf",
            1,
            "/tmp/deschutes-cdd-1383062.pdf",
            "electronic_file",
            "official_county_document",
            "public",
        )
        event = db.execute(
            """
            SELECT record_kind, event_type, submitted_date, last_update_date
            FROM property_event
            """
        ).fetchone()
        assert tuple(event) == (
            "laserfiche_development_document",
            "Planning",
            "2025-11-24",
            "2025-11-25",
        )
    finally:
        db.close()


def test_lane_and_marion_assessor_records_project_accounts_values_and_sales(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    lane_source = query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID
    marion_source = query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID

    lane = ingest_property_envelope(
        _oregon_lane_marion_envelope(lane_source),
        db_path=db_path,
    )
    marion = ingest_property_envelope(
        _oregon_lane_marion_envelope(marion_source),
        db_path=db_path,
    )

    assert lane["projection_supported"] is True
    assert lane["records"][0]["owners_upserted"] == 1
    assert lane["records"][0]["addresses_inserted"] == 1
    assert lane["records"][0]["geometry_upserted"] == 1
    assert marion["records"][0]["owners_upserted"] == 1
    assert marion["records"][0]["addresses_inserted"] == 2
    assert marion["records"][0]["assessments_upserted"] == 1
    assert marion["records"][0]["sales_upserted"] == 1

    db = connect_property(db_path)
    try:
        account_aliases = {
            (row["source_id"], row["alias_value"])
            for row in db.execute(
                """
                SELECT source_id, alias_value
                FROM parcel_alias
                WHERE alias_type='assessment_account'
                """
            ).fetchall()
        }
        assert (lane_source, "0000016") in account_aliases
        assert (marion_source, "510174") in account_aliases
        assert (marion_source, "R10174") in account_aliases

        assessment = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor,
                   total_value_minor, assessed_value_minor, assessment_class
            FROM assessment
            WHERE source_id=?
            """,
            (marion_source,),
        ).fetchone()
        assert tuple(assessment) == (
            150_858_000,
            32_500_000,
            183_358_000,
            27_696_800,
            "550",
        )

        sale = db.execute(
            """
            SELECT native_sale_id, sale_date, recording_date,
                   consideration_minor, qualification_code, derivation
            FROM sale_event
            WHERE source_id=?
            """,
            (marion_source,),
        ).fetchone()
        assert tuple(sale) == (
            "35450047",
            "2013-09-19",
            "2013-09-19",
            254_500_000,
            "latest_transfer_coded_as_verified_sale",
            "assessment_roll",
        )
    finally:
        db.close()


def test_lane_recent_sale_projects_as_distinct_joined_sale_observation(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    source_id = query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID
    envelope = _oregon_lane_marion_envelope(source_id)
    native_sale_id = envelope["records"][0]["native_sale_id"]
    parcel_envelope = _oregon_lane_marion_envelope(
        query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID
    )
    parcel_record = parcel_envelope["records"][0]
    parcel_record["native_parcel_id"] = "1605070001100"
    parcel_record["canonical_ref"] = (
        "PROPERTY:us-or-lane-county-assessor-parcels/41039/parcel/1605070001100"
    )
    parcel_record["alternate_parcel_ids"] = []
    parcel_record["assessment_account_ids"] = ["0057313"]
    ingest_property_envelope(parcel_envelope, db_path=db_path)

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    assert first["projection_supported"] is True
    assert first["records"][0]["canonical_ref"].endswith(native_sale_id)
    assert first["records"][0]["aliases_inserted"] == 1
    assert first["records"][0]["addresses_inserted"] == 1
    assert first["records"][0]["sales_upserted"] == 1
    assert second["records_ingested"] == 1

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID,
            "41039",
            "1605070001100",
            "",
        )
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        alias = db.execute(
            "SELECT alias_type, alias_value FROM parcel_alias"
        ).fetchone()
        assert tuple(alias) == ("assessment_account", "0057313")
        sale = db.execute(
            """
            SELECT native_sale_id, sale_date, recording_date,
                   consideration_minor, qualification_code, derivation
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == (
            native_sale_id,
            "2024-07-10",
            "2024-07-10",
            55_600_000,
            "Y - Tried to Confirm Sale",
            "assessor_sale_analysis",
        )
        observation = db.execute(
            """
            SELECT source_native_id, record_kind
            FROM source_observation
            WHERE record_kind='sale_reference'
            ORDER BY observation_id LIMIT 1
            """
        ).fetchone()
        assert tuple(observation) == (native_sale_id, "sale_reference")
    finally:
        db.close()


def test_generic_dispatch_projects_acris_instrument_parties_and_bbl(tmp_path):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_acris_envelope(), db_path=db_path)
    second = ingest_property_envelope(_acris_envelope(), db_path=db_path)

    assert first["records"][0]["parties_upserted"] == 2
    assert first["records"][0]["parcels_upserted"] == 1
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_parcel").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 4
        instrument = db.execute(
            """
            SELECT jurisdiction_geoid, native_document_id, instrument_type,
                   execution_date, recording_date, consideration_minor
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument) == (
            "nyc-acris",
            "2024001",
            "DEED",
            "2024-01-02",
            "2024-01-03",
            12_500_000,
        )
        roles = {
            row["raw_name"]: row["role"]
            for row in db.execute(
                "SELECT raw_name, role FROM instrument_party"
            ).fetchall()
        }
        assert roles == {"SELLER LLC": "grantor", "BUYER LLC": "grantee"}
        parcel = db.execute(
            "SELECT jurisdiction_geoid, native_parcel_id FROM parcel_snapshot"
        ).fetchone()
        assert tuple(parcel) == ("36061", "1-123-45")
    finally:
        db.close()


def test_generic_dispatch_preserves_non_success_envelope_without_projection(
    tmp_path,
):
    query = query_cook_property.build_query(
        "parcel",
        "01-01-106-009-1001",
        tax_year=None,
        limit=1,
        cursor=None,
    )
    failure = PublicRecordsResult.failure(
        query,
        ResultStatus.UNAVAILABLE,
        [
            PublicRecordsError(
                code="offline",
                message="offline",
                category="transport",
            )
        ],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(failure, db_path=db_path)

    assert result["records_ingested"] == 0
    assert result["source_status"] == "unavailable"
    db = connect_property(db_path)
    try:
        observation = db.execute(
            "SELECT access_status, raw_json FROM source_observation"
        ).fetchone()
        assert observation["access_status"] == "unavailable"
        assert '"code":"offline"' in observation["raw_json"]
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
    finally:
        db.close()


def test_generic_dispatch_preserves_new_source_before_projection_mapper(tmp_path):
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id="us-test-property",
            name="Test property source",
            source_role="test",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="us-test",
            name="Test jurisdiction",
        ),
        query=QueryMetadata(
            operation="parcel",
            parameters={"selector": "P-1"},
            requested_limit=1,
        ),
    )
    envelope = PublicRecordsResult.success(
        query,
        [{"native_parcel_id": "P-1", "raw": {"field": "value"}}],
        retrieved_at="2026-07-28T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"

    result = ingest_property_envelope(envelope, db_path=db_path)

    assert result["projection_supported"] is False
    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
    finally:
        db.close()


def test_direct_cli_dispatches_canonical_envelope(tmp_path):
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parent.parent
    input_path = tmp_path / "cook-envelope.json"
    output_path = tmp_path / "ingest-summary.json"
    db_path = tmp_path / "property.db"
    input_path.write_text(json.dumps(_cook_envelope()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "tools/ingest_property_records.py",
            "ingest",
            "--input",
            str(input_path),
            "--property-db",
            str(db_path),
            "--output",
            str(output_path),
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["source_id"] == query_cook_property.SOURCE_ID
    assert summary["records_ingested"] == 1
    assert db_path.exists()


def test_direct_cli_help_uses_repository_tool_pattern():
    import subprocess
    import sys

    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/ingest_property_records.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Normalize property" in result.stdout
    assert "ingest" in result.stdout


def _benton_envelope(source, operation, records):
    query = PublicRecordsQuery(
        source=source,
        jurisdiction=query_oregon_benton_property.JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters={"selector": "fixture"},
            requested_limit=len(records),
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()


def test_benton_taxlot_owner_party_projects_aliases_owner_address_and_geometry(
    tmp_path,
):
    fixture = json.loads(
        (
            Path("tests/fixtures/public_records/oregon_benton_property")
            / "representative_feature.json"
        ).read_text(encoding="utf-8")
    )
    record = query_oregon_benton_property.normalize_taxlot_owner(
        fixture,
        source_schema_fingerprint=(
            query_oregon_benton_property.EXPECTED_SCHEMA_FINGERPRINT
        ),
        geometry_requested=True,
    )
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(
        _benton_envelope(
            query_oregon_benton_property.PARCEL_SOURCE_METADATA,
            "parcel",
            [record],
        ),
        db_path=db_path,
    )

    assert report["projection_supported"] is True
    assert report["records"][0]["source_record_kind"] == "taxlot_owner_party"
    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            query_oregon_benton_property.PARCEL_SOURCE_ID,
            "41003",
            "11513A000100",
        )
        aliases = {
            (row["alias_type"], row["alias_value"])
            for row in db.execute(
                "SELECT alias_type, alias_value FROM parcel_alias"
            ).fetchall()
        }
        assert aliases >= {
            ("account_number", "802377"),
            ("map_taxlot", "11513A000100"),
            (
                "or_taxlot",
                "0211.00S05.00W13A0--000000100",
            ),
            ("map_number", "11513A"),
            ("arcgis_object_id", "107939"),
        }
        owner = db.execute(
            """
            SELECT raw_owner_name
            FROM ownership_assertion
            """
        ).fetchone()
        assert owner["raw_owner_name"].startswith("NOLAN LACY MARIE")
        addresses = {
            row["address_role"]: row["raw_address"]
            for row in db.execute(
                "SELECT address_role, raw_address FROM parcel_address"
            ).fetchall()
        }
        assert addresses["situs"].startswith("5055 NE ELLIOTT CIR")
        assert addresses["mailing"].startswith("5055 NE ELLIOTT CIR")
        geometry = db.execute("SELECT crs FROM parcel_geometry").fetchone()
        assert geometry["crs"] == "EPSG:4326"
        observation = db.execute(
            """
            SELECT source_native_id, record_kind
            FROM source_observation
            WHERE record_kind='taxlot_owner_party'
            """
        ).fetchone()
        assert tuple(observation) == ("11513A000100", "taxlot_owner_party")
    finally:
        db.close()


def test_benton_bulk_and_map_metadata_remain_distinct_observations(tmp_path):
    fixture_root = Path("tests/fixtures/public_records/oregon_benton_property")
    assessment_listing = query_oregon_benton_property.parse_iis_listing(
        (fixture_root / "assessment_index.html").read_text(encoding="utf-8"),
        source_url=query_oregon_benton_property.ASSESSMENT_DIRECTORY_URL,
        expected_path="/gisdata/Assessment/",
    )
    bulk_record = query_oregon_benton_property.build_bulk_manifest(assessment_listing)
    map_listing = query_oregon_benton_property.parse_iis_listing(
        (fixture_root / "maps_index.html").read_text(encoding="utf-8"),
        source_url=query_oregon_benton_property.ASSESSMENT_MAP_DIRECTORY_URL,
        expected_path="/gisdata/Assessment/AssessmentMapsPDF/",
    )
    map_records, _, _ = query_oregon_benton_property.map_records(
        map_listing,
        map_number=None,
        match_mode="exact",
        map_kind="all",
        updated_after=None,
        limit=1,
        cursor=None,
    )
    db_path = tmp_path / "property.db"

    bulk_report = ingest_property_envelope(
        _benton_envelope(
            query_oregon_benton_property.BULK_SOURCE_METADATA,
            "bulk-manifest",
            [bulk_record],
        ),
        db_path=db_path,
    )
    map_report = ingest_property_envelope(
        _benton_envelope(
            query_oregon_benton_property.MAP_SOURCE_METADATA,
            "maps",
            map_records,
        ),
        db_path=db_path,
    )

    assert bulk_report["projection_skips"][0]["projection_skipped"] is True
    assert bulk_report["projection_skips"][0]["record_kind"] == "bulk_release"
    assert map_report["projection_skips"][0]["projection_skipped"] is True
    assert map_report["projection_skips"][0]["record_kind"] == "assessment_map"
    db = connect_property(db_path)
    try:
        observations = db.execute(
            """
            SELECT source_id, record_kind, source_native_id, raw_json
            FROM source_observation
            WHERE record_kind IN ('bulk_release', 'assessment_map')
            ORDER BY source_id
            """
        ).fetchall()
        assert {(row["source_id"], row["record_kind"]) for row in observations} == {
            (
                query_oregon_benton_property.BULK_SOURCE_ID,
                "bulk_release",
            ),
            (
                query_oregon_benton_property.MAP_SOURCE_ID,
                "assessment_map",
            ),
        }
        bulk_raw = json.loads(
            next(
                row["raw_json"]
                for row in observations
                if row["record_kind"] == "bulk_release"
            )
        )
        assert len(bulk_raw["manifest"]["artifacts"]) == 3
        map_raw = json.loads(
            next(
                row["raw_json"]
                for row in observations
                if row["record_kind"] == "assessment_map"
            )
        )
        assert map_raw["artifact"]["media_type"] == "application/pdf"
    finally:
        db.close()


def test_yamhill_taxlot_public_dispatch_projects_assessor_record(tmp_path):
    fixture = json.loads(
        (
            Path("tests/fixtures/public_records/oregon_yamhill_property")
            / "current_feature.json"
        ).read_text(encoding="utf-8")
    )
    record = query_oregon_yamhill_property._normalize_taxlot(
        query_oregon_yamhill_property.TAXLOTS,
        fixture,
        schema_value="fixture-schema",
        geometry_requested=True,
    )
    query = query_oregon_yamhill_property._build_query(
        query_oregon_yamhill_property.TAXLOT_SOURCE_ID,
        operation="search",
        parameters={"selector": "41270", "field": "account"},
        requested_limit=1,
        cursor=None,
        access_decision=None,
    )
    envelope = PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"

    report = ingest_property_envelope(envelope, db_path=db_path)

    assert report["projection_supported"] is True
    assert report["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            query_oregon_yamhill_property.TAXLOT_SOURCE_ID,
            "41071",
            "5144427",
        )
        owner = db.execute(
            "SELECT raw_owner_name FROM ownership_assertion"
        ).fetchone()
        assert owner["raw_owner_name"] == (
            "LUTZE ALBERT & JUDY FAMILY RL TRUST"
        )
        geometry = db.execute(
            "SELECT crs FROM parcel_geometry"
        ).fetchone()
        assert geometry["crs"] == "EPSG:4326"
    finally:
        db.close()


def test_wasco_survey_public_dispatch_preserves_observation_without_title_projection(
    tmp_path,
):
    source_id = query_oregon_wasco_property.LAND_CORNERS_SOURCE_ID
    record = {
        "source_id": source_id,
        "source_url": (
            f"{query_oregon_wasco_property.SURVEY_SERVICE_ROOT}/53"
        ),
        "source_record_id": "17",
        "object_id": 17,
        "record_kind": "land_corner_and_scan",
        "native_identity": "LC 179",
        "attributes": {
            "OBJECTID": 17,
            "ANNO": "LC 179",
            "SCAN_NAM": "LC179.TIF",
        },
    }
    query = query_oregon_wasco_property._query(
        source_id,
        "search",
        parameters={"value": "LC 179", "field": "text"},
    )
    envelope = PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"

    report = ingest_property_envelope(envelope, db_path=db_path)

    assert report["projection_supported"] is True
    assert report["records_ingested"] == 1
    assert report["records"][0]["projection"] == "observation_only"
    assert report["records"][0]["record_kind"] == (
        "land_corner_reference_with_scan"
    )
    db = connect_property(db_path)
    try:
        observation = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE record_kind='land_corner_reference_with_scan'
            """
        ).fetchone()
        assert observation["source_native_id"] == "17"
        assert json.loads(observation["raw_json"])["native_identity"] == "LC 179"
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM property_event").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 0
    finally:
        db.close()


def test_washington_public_dispatch_projects_account_and_preserves_survey_index(
    tmp_path,
):
    source_url = (
        f"{query_oregon_washington_property.TAX_BASE_URL}/Property-Detail/"
        "PropertyQuickRefID/R2069997"
    )
    account = query_oregon_washington_property.parse_tax_account(
        (
            Path("tests/fixtures/public_records/oregon_washington_property")
            / "tax_account.html"
        ).read_text(encoding="utf-8"),
        source_url=source_url,
        requested_account="R2069997",
    )
    account_query = query_oregon_washington_property._public_query(
        query_oregon_washington_property.TAX_SOURCE_ID,
        "account",
        {"PropertyQuickRefID": "R2069997"},
    )
    survey_record = {
        "source_id": query_oregon_washington_property.SURVEY_API_SOURCE_ID,
        "source_url": query_oregon_washington_property.SURVEY_APP_URL,
        "record_type": "survey_explorer_survey",
        "operation": "search",
        "native_ids": {"Surveynumber": 35242},
        "native_fields": {
            "Surveynumber": 35242,
            "Client": "HARVEY BUSINESS TRUST",
        },
        "resolved_documents": [
            {
                "native_filename": "35242.pdf",
                "resolved_url": (
                    "https://mtbachelor.co.washington.or.us/images/"
                    "survey/surveys/40000/35242.pdf"
                ),
            }
        ],
    }
    survey_query = query_oregon_washington_property._public_query(
        query_oregon_washington_property.SURVEY_API_SOURCE_ID,
        "survey_search",
        {"kind": "survey", "surveynumber": "35242"},
    )
    db_path = tmp_path / "property.db"

    account_report = ingest_property_envelope(
        PublicRecordsResult.success(
            account_query,
            [account],
            retrieved_at="2026-07-30T12:00:00Z",
        ).to_dict(),
        db_path=db_path,
    )
    survey_report = ingest_property_envelope(
        PublicRecordsResult.success(
            survey_query,
            [survey_record],
            retrieved_at="2026-07-30T12:01:00Z",
        ).to_dict(),
        db_path=db_path,
    )

    assert account_report["projection_supported"] is True
    assert account_report["records"][0]["owners_upserted"] == 1
    assert account_report["records"][0]["assessments_upserted"] == 1
    assert survey_report["projection_supported"] is True
    assert survey_report["records"][0]["projection"] == "observation_only"
    assert survey_report["records"][0]["record_kind"] == (
        "survey_explorer_survey"
    )
    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            query_oregon_washington_property.TAX_SOURCE_ID,
            "41067",
            "R2069997",
        )
        owner = db.execute(
            "SELECT raw_owner_name FROM ownership_assertion"
        ).fetchone()
        assert owner["raw_owner_name"] == (
            "CRABB, JOHN & DAVIS, TASSY LEI"
        )
        assessment = db.execute(
            """
            SELECT tax_year, market_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == ("2025", 230_036_000)
        survey = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind='survey_explorer_survey'
            """,
            (query_oregon_washington_property.SURVEY_API_SOURCE_ID,),
        ).fetchone()
        assert survey["source_native_id"] == (
            "survey_explorer_survey:35242"
        )
        assert survey["record_kind"] == "survey_explorer_survey"
        assert json.loads(survey["raw_json"])["resolved_documents"][0][
            "native_filename"
        ] == "35242.pdf"
        assert db.execute(
            "SELECT COUNT(*) FROM recorded_instrument"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_multnomah_sail_dispatch_projects_tax_parcel_and_preserves_survey(
    tmp_path,
):
    features = json.loads(
        (
            Path("tests/fixtures/public_records/oregon_multnomah_sail")
            / "features.json"
        ).read_text(encoding="utf-8")
    )
    tax_source = query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID
    survey_source = query_oregon_multnomah_sail.SURVEY_SOURCE_ID
    tax_record = query_oregon_multnomah_sail.normalize_feature(
        query_oregon_multnomah_sail.COMPONENTS[tax_source],
        features[tax_source][0],
        schema_fingerprint="fixture-tax-schema",
        geometry_requested=True,
    )
    survey_record = query_oregon_multnomah_sail.normalize_feature(
        query_oregon_multnomah_sail.COMPONENTS[survey_source],
        features[survey_source][1],
        schema_fingerprint="fixture-survey-schema",
        geometry_requested=True,
    )
    tax_query = PublicRecordsQuery(
        source=query_oregon_multnomah_sail.SOURCE_METADATA[tax_source],
        jurisdiction=query_oregon_multnomah_sail.JURISDICTION,
        query=QueryMetadata(
            operation="search",
            parameters={"field": "property-id", "query": "R330254"},
        ),
    )
    survey_query = PublicRecordsQuery(
        source=query_oregon_multnomah_sail.SOURCE_METADATA[survey_source],
        jurisdiction=query_oregon_multnomah_sail.JURISDICTION,
        query=QueryMetadata(
            operation="search",
            parameters={"field": "survey-id", "query": "05335"},
        ),
    )
    db_path = tmp_path / "property.db"

    tax_report = ingest_property_envelope(
        PublicRecordsResult.success(
            tax_query,
            [tax_record],
            retrieved_at="2026-07-30T13:00:00Z",
        ).to_dict(),
        db_path=db_path,
    )
    survey_report = ingest_property_envelope(
        PublicRecordsResult.success(
            survey_query,
            [survey_record],
            retrieved_at="2026-07-30T13:01:00Z",
        ).to_dict(),
        db_path=db_path,
    )

    assert tax_report["projection_supported"] is True
    assert tax_report["records"][0]["owners_upserted"] == 1
    assert tax_report["records"][0]["assessments_upserted"] == 1
    assert tax_report["records"][0]["sales_upserted"] == 1
    assert survey_report["projection_supported"] is True
    assert survey_report["records"][0]["projection"] == "observation_only"
    assert survey_report["records"][0]["record_kind"] == "survey_record"

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (tax_source, "41051", "R330254")
        owner = db.execute(
            "SELECT raw_owner_name FROM ownership_assertion"
        ).fetchone()
        assert owner["raw_owner_name"] == "LUMEN TECHNOLOGIES INC"
        assessment = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   assessed_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == ("2025", 0, 0, 0)
        sale = db.execute(
            """
            SELECT native_sale_id, recording_date
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == ("BP23830216", "2011-11-23")
        survey = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind='survey_record'
            """,
            (survey_source,),
        ).fetchone()
        assert survey["source_native_id"] == "7220"
        assert json.loads(survey["raw_json"])["survey_document_id"] == "05335"
        assert db.execute(
            "SELECT COUNT(*) FROM recorded_instrument"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_washington_casefile_dispatch_links_event_and_preserves_vocabulary(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    taxlot = "2N2330002700"
    intermap_record = {
        "record_type": "intermap_parcel_report",
        "report": "parcel",
        "native_ids": {"IDValue": taxlot, "TLNO": taxlot},
        "native_representation": {"field_pairs": []},
        "source_id": query_oregon_washington_property.INTERMAP_SOURCE_ID,
        "source_url": query_oregon_washington_property.intermap_url(
            taxlot,
            "parcel",
        ),
    }
    intermap_query = query_oregon_washington_property._public_query(
        query_oregon_washington_property.INTERMAP_SOURCE_ID,
        "reports",
        {"TLNO": taxlot, "reports": ["parcel"], "include_raw_html": False},
    )
    payload = json.loads(
        (
            Path("tests/fixtures/washington_county_case_permits")
            / "case_exact.json"
        ).read_text(encoding="utf-8")
    )
    schema, fingerprint = (
        query_oregon_washington_case_permits._schema_bundle(payload["data"])
    )
    case_record = query_oregon_washington_case_permits._case_record(
        payload["data"][0],
        source_url=query_oregon_washington_case_permits.CASEFILE_SEARCH_URL,
        operation="case_detail",
        schema=schema,
        fingerprint=fingerprint,
    )
    case_query = query_oregon_washington_case_permits._query(
        query_oregon_washington_case_permits.CASEFILE_SOURCE_ID,
        "case_detail",
        {"casefile": "L2500106"},
    )
    type_payload = json.loads(
        (
            Path("tests/fixtures/washington_county_case_permits")
            / "building_types.json"
        ).read_text(encoding="utf-8")
    )
    type_schema, type_fingerprint = (
        query_oregon_washington_case_permits._schema_bundle(
            type_payload["data"]
        )
    )
    type_record = query_oregon_washington_case_permits._building_record(
        type_payload["data"][0],
        kind="types",
        source_url=query_oregon_washington_case_permits.BUILDING_TYPES_URL,
        schema=type_schema,
        fingerprint=type_fingerprint,
    )
    type_query = query_oregon_washington_case_permits._query(
        query_oregon_washington_case_permits.BUILDING_SOURCE_ID,
        "building_permit_types",
        {},
    )

    ingest_property_envelope(
        PublicRecordsResult.success(
            intermap_query,
            [intermap_record],
            retrieved_at="2026-07-30T14:00:00Z",
        ).to_dict(),
        db_path=db_path,
    )
    case_report = ingest_property_envelope(
        PublicRecordsResult.success(
            case_query,
            [case_record],
            retrieved_at="2026-07-30T14:01:00Z",
        ).to_dict(),
        db_path=db_path,
    )
    type_report = ingest_property_envelope(
        PublicRecordsResult.success(
            type_query,
            [type_record],
            retrieved_at="2026-07-30T14:02:00Z",
        ).to_dict(),
        db_path=db_path,
    )

    assert case_report["projection_supported"] is True
    assert case_report["records"][0]["parties_upserted"] == 2
    assert case_report["records"][0]["parcel_link_method"] == (
        "exact_published_map_taxlot_alias"
    )
    assert case_report["records"][0]["representations_upserted"] == 3
    assert type_report["records"][0]["projection"] == "observation_only"
    assert type_report["records"][0]["record_kind"] == "building_permit_type"

    db = connect_property(db_path)
    try:
        event = db.execute(
            """
            SELECT native_event_id, source_record_id, submitted_date,
                   last_update_date, description, status
            FROM property_event
            WHERE source_id=?
            """,
            (query_oregon_washington_case_permits.CASEFILE_SOURCE_ID,),
        ).fetchone()
        assert tuple(event) == (
            "L2500106",
            "S2500112",
            "2025-04-22",
            "2025-04-23",
            'Home Occupation Permit Renewal for "Tradewest Brokerage Co."',
            "Approved",
        )
        parties = db.execute(
            """
            SELECT role, raw_name
            FROM property_event_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            ("applicant", "JOHN CRABB"),
            ("assigned_staff", "Kellie Crowdis"),
        ]
        parcel_link = db.execute(
            """
            SELECT p.source_id, p.native_parcel_id, l.link_method
            FROM property_event_parcel_link AS l
            JOIN parcel_snapshot AS p ON p.parcel_id=l.parcel_id
            """
        ).fetchone()
        assert tuple(parcel_link) == (
            query_oregon_washington_property.INTERMAP_SOURCE_ID,
            taxlot,
            "exact_published_map_taxlot_alias",
        )
        assert db.execute(
            "SELECT COUNT(*) FROM property_event_representation"
        ).fetchone()[0] == 3
        assert db.execute(
            """
            SELECT COUNT(*)
            FROM source_observation
            WHERE source_id=? AND record_kind='building_permit_type'
            """,
            (query_oregon_washington_case_permits.BUILDING_SOURCE_ID,),
        ).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM property_event").fetchone()[0] == 1
    finally:
        db.close()


def test_philadelphia_components_join_without_conflating_source_meanings(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    current_report = ingest_property_envelope(
        _philadelphia_envelope("parcel"),
        db_path=db_path,
    )
    history_report = ingest_property_envelope(
        _philadelphia_envelope("history"),
        db_path=db_path,
    )
    dor_report = ingest_property_envelope(
        _philadelphia_envelope("parcel-shape"),
        db_path=db_path,
    )

    assert current_report["records"][0]["owners_upserted"] == 1
    assert current_report["records"][0]["sales_upserted"] == 1
    assert history_report["records"][0]["assessments_upserted"] == 1
    assert dor_report["records"][0]["geometry_upserted"] == 1

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchall()
        assert len(parcels) == 1
        assert tuple(parcels[0]) == (
            parcels[0]["parcel_id"],
            query_philadelphia_property.SOURCE_ID,
            "341086700",
            "2026",
        )

        assessments = db.execute(
            """
            SELECT source_id, tax_year, total_value_minor,
                   market_value_minor, raw_json
            FROM assessment
            ORDER BY source_id
            """
        ).fetchall()
        assert len(assessments) == 2
        assessment_by_source = {row["source_id"]: row for row in assessments}
        assert (
            assessment_by_source[
                query_philadelphia_property.SOURCE_ID
            ]["market_value_minor"]
            == 19_960_000
        )
        assert (
            assessment_by_source[
                query_philadelphia_property.SOURCE_ID
            ]["total_value_minor"]
            == 19_960_000
        )
        history = assessment_by_source[
            query_philadelphia_property.HISTORY_SOURCE_ID
        ]
        assert history["tax_year"] == "2023"
        assert history["market_value_minor"] == 12_520_000
        assert json.loads(history["raw_json"])["taxable_land"] == 25_040

        sale = db.execute(
            """
            SELECT native_sale_id, recording_date, consideration_minor
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == ("062N200131", "2026-06-08", 10_000_000)

        geometries = db.execute(
            """
            SELECT source_id, geometry_format
            FROM parcel_geometry
            ORDER BY source_id
            """
        ).fetchall()
        assert [tuple(row) for row in geometries] == [
            (
                query_philadelphia_property.DOR_SOURCE_ID,
                "esri_json",
            ),
            (
                query_philadelphia_property.SOURCE_ID,
                "esri_json",
            ),
        ]
        assert db.execute(
            """
            SELECT COUNT(*)
            FROM parcel_alias
            WHERE alias_value IN ('062N200131', '1001666377')
            """
        ).fetchone()[0] >= 4
    finally:
        db.close()


def test_philadelphia_history_placeholder_is_adopted_by_current_opa(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    history_report = ingest_property_envelope(
        _philadelphia_envelope("history"),
        db_path=db_path,
    )
    placeholder_id = history_report["records"][0]["parcel_id"]
    current_report = ingest_property_envelope(
        _philadelphia_envelope("parcel"),
        db_path=db_path,
    )

    assert current_report["records"][0]["parcel_id"] == placeholder_id
    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT parcel_id, source_id, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(parcel) == (
            placeholder_id,
            query_philadelphia_property.SOURCE_ID,
            "341086700",
            "2026",
        )
        assessment_sources = db.execute(
            """
            SELECT source_id
            FROM assessment
            WHERE parcel_id=?
            ORDER BY source_id
            """,
            (placeholder_id,),
        ).fetchall()
        assert [row["source_id"] for row in assessment_sources] == [
            query_philadelphia_property.HISTORY_SOURCE_ID,
            query_philadelphia_property.SOURCE_ID,
        ]
    finally:
        db.close()


def _wisconsin_statewide_envelope():
    fixture = json.loads(
        (
            Path("tests/fixtures/public_records/wisconsin_parcels")
            / "features.json"
        ).read_text(encoding="utf-8")
    )
    snapshot = query_wisconsin_parcels.SourceSnapshot(
        schema_fingerprint="a" * 64,
        dataset_release="V1200_WisconsinParcels_2026",
        release_version=12,
        release_year=2026,
        dataset_version=1_772_582_400_000,
        page_size=2_000,
        service_item_id="fixture",
    )
    batch = query_wisconsin_parcels.TraversalBatch(
        records=tuple(fixture),
        next_cursor=None,
        total_count=len(fixture),
        remaining_count=len(fixture),
        pages_fetched=1,
        snapshot=snapshot,
    )
    records = [
        query_wisconsin_parcels._normalize_feature(
            feature,
            batch,
            geometry_requested=True,
        )
        for feature in fixture
    ]
    args = query_wisconsin_parcels.build_parser().parse_args(
        ["parcel", "fixture", "--geometry"]
    )
    return PublicRecordsResult.success(
        query_wisconsin_parcels.build_query(args),
        records,
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()


def _new_jersey_statewide_envelope():
    fixture = json.loads(
        (
            Path("tests/fixtures/public_records/new_jersey_parcels")
            / "features.json"
        ).read_text(encoding="utf-8")
    )
    snapshot = query_new_jersey_parcels.SourceSnapshot(
        schema_fingerprint="b" * 64,
        dataset_version=1_775_046_615_578,
        item_modified=1_775_046_615_578,
        layer_url=query_new_jersey_parcels.DEFAULT_LAYER_URL,
        native_page_size=2_000,
        metadata={},
        item_metadata={},
    )
    batch = query_new_jersey_parcels.TraversalBatch(
        records=tuple(fixture),
        next_cursor=None,
        total_count=len(fixture),
        remaining_count=len(fixture),
        pages_fetched=1,
        snapshot=snapshot,
    )
    records = [
        query_new_jersey_parcels._normalize_feature(
            feature,
            batch,
            geometry_requested=True,
        )
        for feature in fixture
    ]
    args = query_new_jersey_parcels.build_parser().parse_args(
        ["search", "--all", "--geometry"]
    )
    return PublicRecordsResult.success(
        query_new_jersey_parcels.build_query(args),
        records,
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()


def _put_sr1a_field(row: bytearray, field_name: str, value: str) -> None:
    field = query_new_jersey_sr1a.FIELD_BY_NAME[field_name]
    encoded = value.encode("ascii")
    assert len(encoded) <= field.width
    row[field.byte_slice] = encoded.ljust(field.width, b" ")


def _new_jersey_sr1a_envelope(tmp_path: Path):
    row = bytearray(b" " * query_new_jersey_sr1a.RECORD_WIDTH)
    values = {
        "county_code": "07",
        "district_code": "03",
        "total_assessment": "000000500000",
        "last_update_date": "062025",
        "reported_sales_price": "000750000",
        "verified_sales_price": "000745000",
        "main_value_land": "000150000",
        "main_value_building": "000350000",
        "main_value_total": "000500000",
        "sales_ratio": "07450",
        "realty_transfer_fee": "000035000",
        "serial_number": "1234567",
        "grantor_name": "ALPHA OWNER LLC",
        "grantor_street": "10 OLD ROAD",
        "grantor_city_state": "NEWARK NJ",
        "grantor_zip": "071011234",
        "grantee_name": "BETA BUYER LLC",
        "grantee_street": "20 NEW ROAD",
        "grantee_city_state": "CALDWELL NJ",
        "grantee_zip": "070061234",
        "property_location": "35 HILLSIDE AVE",
        "deed_book": "A123",
        "deed_page": "0042",
        "deed_date": "250610",
        "date_recorded": "250617",
        "block": "14",
        "lot": "6",
        "additional_block_1": "15",
        "additional_lot_1": "2",
        "additional_qualifier_1": "Q1",
        "additional_value_land_1": "000025000",
        "additional_value_building_1": "000000000",
        "additional_value_total_1": "000025000",
        "qualification_codes": "Q1",
        "assess_year": "25",
        "property_class": "2",
        "field_date": "190625",
        "year_built": "1998",
        "living_space": "0002450",
    }
    for field_name, value in values.items():
        _put_sr1a_field(row, field_name, value)
    archive_path = tmp_path / "Sales2025.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Sales2025.txt", bytes(row) + b"\r\n")
    snapshot = query_new_jersey_sr1a.parse_release_manifest(
        (
            Path("tests/fixtures/public_records/new_jersey_sr1a")
            / "manifest.html"
        ).read_text(encoding="utf-8")
    )
    release = next(
        item
        for item in snapshot.releases
        if item.release_id == "sr1a-annual-2025"
    )
    local = query_new_jersey_sr1a._local_release_from_path(
        release,
        archive_path,
    )
    record = query_new_jersey_sr1a.normalize_row(
        bytes(row),
        local=local,
        row_index=0,
    )
    args = query_new_jersey_sr1a.build_parser().parse_args(
        ["search", "ALPHA OWNER LLC", "--field", "party", "--year", "2025"]
    )
    return PublicRecordsResult.success(
        query_new_jersey_sr1a.build_query(args),
        [record],
        retrieved_at="2026-07-29T12:00:00Z",
        raw_artifact_refs=(str(archive_path),),
    ).to_dict()


def _palm_beach_recorder_envelope():
    fixture = (
        Path("tests/fixtures/public_records/palm_beach_official_records")
        / "detail-deed.html"
    ).read_text(encoding="utf-8")
    record = query_palm_beach_official_records.parse_document_detail(
        fixture,
        document_id=query_palm_beach_official_records.SENTINEL_DOCUMENT_ID,
    )
    args = query_palm_beach_official_records.build_parser().parse_args(
        [
            "instrument",
            query_palm_beach_official_records.SENTINEL_INSTRUMENT,
        ]
    )
    return PublicRecordsResult.success(
        query_palm_beach_official_records.build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _palm_beach_appraiser_envelope_for_recorder_pcn():
    fixture_dir = Path(
        "tests/fixtures/public_records/palm_beach_property_appraiser"
    )
    metadata = json.loads(
        (fixture_dir / "metadata.json").read_text(encoding="utf-8")
    )
    features = json.loads(
        (fixture_dir / "features.json").read_text(encoding="utf-8")
    )
    record = query_palm_beach_property_appraiser.normalize_feature(
        features[2],
        contract=query_palm_beach_property_appraiser.metadata_contract(
            metadata
        ),
        geometry_requested=True,
    )
    query = PublicRecordsQuery(
        source=query_palm_beach_property_appraiser.SOURCE_METADATA,
        jurisdiction=query_palm_beach_property_appraiser.JURISDICTION,
        query=QueryMetadata(
            operation="parcel",
            parameters={"pcn": record["native_parcel_id"]},
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:05:00Z",
    ).to_dict()


def _palm_beach_image_envelope(tmp_path: Path):
    fixture = (
        Path("tests/fixtures/public_records/palm_beach_official_records")
        / "detail-deed.html"
    ).read_text(encoding="utf-8")
    record = query_palm_beach_official_records.parse_document_detail(
        fixture,
        document_id=query_palm_beach_official_records.SENTINEL_DOCUMENT_ID,
    )
    content = b"\x89PNG\r\n\x1a\nfixture-image"
    destination = tmp_path / "pbc-page-1.png"
    artifact = query_palm_beach_official_records._artifact_record(
        record,
        query_palm_beach_official_records.DocumentImage(
            content=content,
            media_type="image/png",
            page_number=1,
            sha256=hashlib.sha256(content).hexdigest(),
        ),
        destination,
    )
    args = query_palm_beach_official_records.build_parser().parse_args(
        [
            "image",
            "--instrument",
            query_palm_beach_official_records.SENTINEL_INSTRUMENT,
            "--document-output",
            str(destination),
        ]
    )
    return PublicRecordsResult.success(
        query_palm_beach_official_records.build_query(args),
        [artifact],
        retrieved_at="2026-07-30T12:05:00Z",
        raw_artifact_refs=(str(destination),),
    ).to_dict()


def test_wisconsin_statewide_projection_preserves_visibility_and_nonparcels(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    report = ingest_property_envelope(
        _wisconsin_statewide_envelope(),
        db_path=db_path,
    )

    assert report["records_ingested"] == 2
    assert report["records_preserved_without_projection"] == 1
    assert report["projection_skips"][0]["reason"] == (
        "wisconsin_row_is_not_a_canonical_parcel"
    )
    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, roll_year, raw_json
            FROM parcel_snapshot
            ORDER BY native_parcel_id
            """
        ).fetchall()
        assert [
            (row["jurisdiction_geoid"], row["native_parcel_id"])
            for row in parcels
        ] == [
            ("55001", "001008015540000"),
            ("55059", "05901-122-01-103-013"),
        ]
        assert {row["roll_year"] for row in parcels} == {"2025"}
        assert any(
            '"state":"withheld_by_source"' in row["raw_json"]
            for row in parcels
        )
        owners = db.execute(
            """
            SELECT raw_owner_name
            FROM ownership_assertion
            ORDER BY raw_owner_name
            """
        ).fetchall()
        assert [row["raw_owner_name"] for row in owners] == [
            "CHARLOTTE M YOUNG EPSTEIN",
            "THOMAS J EPSTEIN",
        ]
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 1
        observation = db.execute(
            """
            SELECT record_kind
            FROM source_observation
            WHERE source_native_id='001ROW:28'
            """
        ).fetchone()
        assert observation["record_kind"] == (
            "statewide_annual_non_parcel_map_observation"
        )
    finally:
        db.close()


def test_new_jersey_statewide_projection_keeps_redaction_and_partial_join(
    tmp_path,
):
    db_path = tmp_path / "property.db"

    report = ingest_property_envelope(
        _new_jersey_statewide_envelope(),
        db_path=db_path,
    )

    assert report["records_ingested"] == 3
    assert report["records_preserved_without_projection"] == 0
    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT native_parcel_id, raw_json
            FROM parcel_snapshot
            ORDER BY native_parcel_id
            """
        ).fetchall()
        assert [row["native_parcel_id"] for row in parcels] == [
            "0703_14_5",
            "0703_14_6",
            "0703_9_10.1",
        ]
        assert db.execute(
            "SELECT COUNT(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0] == 3
        sale = db.execute(
            """
            SELECT native_sale_id, sale_date, consideration_minor, derivation
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == (
            "12151/06592",
            "2008-07-29",
            67_500_000,
            "assessment_roll",
        )
        unmatched = next(
            row
            for row in parcels
            if row["native_parcel_id"] == "0703_9_10.1"
        )
        assert '"state":"parcel_without_joined_modiv"' in unmatched["raw_json"]
        assert '"visibility_state":"redacted_by_source"' in unmatched["raw_json"]
    finally:
        db.close()


def test_new_jersey_sr1a_links_sales_without_creating_ownership_claims(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    ingest_property_envelope(
        _new_jersey_statewide_envelope(),
        db_path=db_path,
    )
    envelope = _new_jersey_sr1a_envelope(tmp_path)

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    assert first["records"][0]["sale_record_id"] == (
        "0703:1234567:A123:0042:250617"
    )
    assert first["records"][0]["parcels_linked"] == 2
    assert first["records"][0]["parcel_placeholders_created"] == 1
    assert first["records"][0]["parties_upserted"] == 2
    assert first["records"][0]["ownership_assertions_upserted"] == 0
    assert second["records"][0]["parcel_placeholders_created"] == 0

    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 4
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM instrument_parcel").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 0
        instrument = db.execute(
            """
            SELECT instrument_id, native_document_id, instrument_type, book, page,
                   execution_date, recording_date, consideration_minor
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument)[1:] == (
            "0703:1234567:A123:0042:250617",
            "sr1a_deed_index_reference",
            "A123",
            "0042",
            "2025-06-10",
            "2025-06-17",
            74_500_000,
        )
        links = db.execute(
            """
            SELECT p.native_parcel_id, ip.link_method
            FROM instrument_parcel ip
            JOIN parcel_snapshot p USING(parcel_id)
            ORDER BY p.native_parcel_id
            """
        ).fetchall()
        assert [tuple(row) for row in links] == [
            ("0703_14_6", "exact_municipality_block_lot"),
            ("0703_15_2_Q1", "exact_municipality_block_lot"),
        ]
        sr1a_sales = db.execute(
            """
            SELECT native_sale_id, derivation, instrument_id
            FROM sale_event
            WHERE source_id=?
            ORDER BY sale_event_id
            """,
            (query_new_jersey_sr1a.SOURCE_ID,),
        ).fetchall()
        assert len(sr1a_sales) == 2
        assert {
            row["derivation"] for row in sr1a_sales
        } == {"state_taxation_sale_return_index"}
        assert all(
            row["instrument_id"] == instrument["instrument_id"]
            for row in sr1a_sales
        )
    finally:
        db.close()


def test_palm_beach_recorder_uses_official_instrument_identity_and_exact_pcn(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    envelope = _palm_beach_recorder_envelope()

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    projection = first["records"][0]
    assert projection["official_instrument_number"] == "19860255822"
    assert projection["portal_document_id"] == "6402430"
    assert projection["parties_upserted"] == 3
    assert projection["parcels_linked"] == 1
    assert projection["parcel_placeholders_created"] == 1
    assert projection["sales_upserted"] == 1
    assert projection["artifacts_upserted"] == 1
    assert projection["ownership_assertions_upserted"] == 0
    assert second["records"][0]["parcel_placeholders_created"] == 0

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT native_document_id, instrument_type, book, page,
                   recording_date, raw_json
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument)[:5] == (
            "19860255822",
            "DEED",
            "5021",
            "1011",
            "1986-09-30",
        )
        assert '"native_document_id":"6402430"' in instrument["raw_json"]
        assert db.execute("SELECT COUNT(*) FROM instrument_party").fetchone()[0] == 3
        link = db.execute(
            """
            SELECT p.source_id, p.native_parcel_id, ip.link_method,
                   ip.link_confidence
            FROM instrument_parcel ip
            JOIN parcel_snapshot p USING(parcel_id)
            """
        ).fetchone()
        assert tuple(link) == (
            "us-fl-palm-beach-official-records",
            "00424411190010180",
            "exact_source_index_pcn",
            1.0,
        )
        sale = db.execute(
            """
            SELECT native_sale_id, sale_date, recording_date, derivation
            FROM sale_event
            """
        ).fetchone()
        assert tuple(sale) == (
            "19860255822",
            "1986-09-30",
            "1986-09-30",
            "recorded_instrument_index",
        )
        metadata = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, page_count,
                   acquisition_method, access_state, acquired_at
            FROM document_artifact
            """
        ).fetchone()
        assert tuple(metadata) == (
            "6402430:online-image-set",
            None,
            "image/png",
            1,
            "source_image_availability_metadata",
            "public",
            None,
        )
        assert db.execute(
            "SELECT COUNT(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_palm_beach_appraiser_adopts_recorder_shell_without_relabeling_evidence(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    ingest_property_envelope(
        _palm_beach_recorder_envelope(),
        db_path=db_path,
    )
    db = connect_property(db_path)
    try:
        shell = db.execute(
            """
            SELECT parcel_id, source_id
            FROM parcel_snapshot
            WHERE native_parcel_id='00424411190010180'
            """
        ).fetchone()
        shell_parcel_id = int(shell["parcel_id"])
        assert shell["source_id"] == (
            query_palm_beach_official_records.SOURCE_ID
        )
    finally:
        db.close()

    summary = ingest_property_envelope(
        _palm_beach_appraiser_envelope_for_recorder_pcn(),
        db_path=db_path,
    )
    projection = summary["records"][0]
    assert projection["parcel_id"] == shell_parcel_id
    assert projection["parcel_shells_adopted"] == 1
    assert projection["parcel_shell_source_ids_adopted"] == [
        query_palm_beach_official_records.SOURCE_ID
    ]

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id
            FROM parcel_snapshot
            WHERE native_parcel_id='00424411190010180'
            """
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            (
                shell_parcel_id,
                query_palm_beach_property_appraiser.SOURCE_ID,
            )
        ]
        instrument_link = db.execute(
            """
            SELECT ip.parcel_id, ri.source_id
            FROM instrument_parcel ip
            JOIN recorded_instrument ri USING(instrument_id)
            """
        ).fetchone()
        assert tuple(instrument_link) == (
            shell_parcel_id,
            query_palm_beach_official_records.SOURCE_ID,
        )
        recorder_sale = db.execute(
            """
            SELECT parcel_id, source_id
            FROM sale_event
            WHERE source_id=?
            """,
            (query_palm_beach_official_records.SOURCE_ID,),
        ).fetchone()
        assert tuple(recorder_sale) == (
            shell_parcel_id,
            query_palm_beach_official_records.SOURCE_ID,
        )
        assert (
            db.execute(
                """
                SELECT COUNT(*)
                FROM source_observation
                WHERE source_id=?
                  AND record_kind='recorded_instrument'
                """,
                (query_palm_beach_official_records.SOURCE_ID,),
            ).fetchone()[0]
            == 1
        )
    finally:
        db.close()


def test_palm_beach_downloaded_page_is_a_separate_idempotent_artifact(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    ingest_property_envelope(
        _palm_beach_recorder_envelope(),
        db_path=db_path,
    )
    envelope = _palm_beach_image_envelope(tmp_path)

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    projection = first["records"][0]
    assert projection["official_instrument_number"] == "19860255822"
    assert projection["portal_page_id"] == "6402430:normal:1"
    assert projection["artifacts_upserted"] == 1
    assert second["records"][0]["artifact_id"] == projection["artifact_id"]

    db = connect_property(db_path)
    try:
        artifacts = db.execute(
            """
            SELECT native_document_id, sha256, storage_path,
                   acquisition_method, acquired_at
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
        assert len(artifacts) == 2
        downloaded = next(
            row
            for row in artifacts
            if row["native_document_id"] == "6402430:normal:1"
        )
        assert downloaded["sha256"] == hashlib.sha256(
            b"\x89PNG\r\n\x1a\nfixture-image"
        ).hexdigest()
        assert downloaded["storage_path"].endswith("pbc-page-1.png")
        assert downloaded["acquisition_method"] == (
            "direct_source_image_download"
        )
        assert downloaded["acquired_at"] == "2026-07-30T12:05:00Z"
        instrument = db.execute(
            "SELECT native_document_id, raw_json FROM recorded_instrument"
        ).fetchone()
        assert instrument["native_document_id"] == "19860255822"
        assert '"record_kind":"recorded_instrument"' in instrument["raw_json"]
    finally:
        db.close()
