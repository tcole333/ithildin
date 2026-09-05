from pathlib import Path

import pytest

from tools import query_property
from tools import query_los_angeles_ttc
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    SourceMetadata,
)
from tools.public_records_store import connect_property
from tools.query_nc_property import _normalize_feature, build_query
from tools.seed_public_records_catalog import seed_catalog


def _seed_property(path):
    db = connect_property(path)
    try:
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
            ) VALUES ('37', 'North Carolina', 'state', NULL, 'NC', NULL)
            """
        )
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
            ) VALUES ('37005', 'Alleghany County', 'county', '37', 'NC', '005')
            """
        )
        parcel_id = db.execute(
            """
            INSERT INTO parcel_snapshot(
                source_id, jurisdiction_geoid, native_parcel_id, roll_year,
                effective_from
            ) VALUES (
                'us-nc-onemap-parcels', '37005', '3013467134', '2025',
                '2025-01-31'
            )
            """
        ).lastrowid
        db.execute(
            """
            INSERT INTO parcel_alias(
                parcel_id, alias_type, alias_value, source_id
            ) VALUES (?, 'source_alternate', 'ALT-3013', 'us-nc-onemap-parcels')
            """,
            (parcel_id,),
        )
        db.execute(
            """
            INSERT INTO ownership_assertion(
                parcel_id, source_id, assertion_type, raw_owner_name,
                normalized_owner_name, effective_from, confidence, claim_type
            ) VALUES (
                ?, 'us-nc-onemap-parcels', 'assessment_roll',
                'SMITH, THOMAS', 'SMITH THOMAS', '2025-01-31',
                'high', 'direct_quote'
            )
            """,
            (parcel_id,),
        )
        db.execute(
            """
            INSERT INTO parcel_address(
                parcel_id, address_role, raw_address, normalized_address,
                city, state, postal_code, source_id, effective_from
            ) VALUES (
                ?, 'situs', '100 Main St', '100 MAIN ST',
                'Sparta', 'NC', '28675', 'us-nc-onemap-parcels', '2025-01-31'
            )
            """,
            (parcel_id,),
        )
        db.execute(
            """
            INSERT INTO parcel_geometry(
                parcel_id, geometry_ref, geometry_format, crs,
                accuracy_disclaimer, source_id, snapshot_date
            ) VALUES (
                ?, 'source-observation-sha256:abc', 'esri_json', 'source_defined',
                'source mapping geometry', 'us-nc-onemap-parcels', '2025-01-31'
            )
            """,
            (parcel_id,),
        )
        db.execute(
            """
            INSERT INTO sale_event(
                parcel_id, source_id, native_sale_id, sale_date,
                derivation
            ) VALUES (
                ?, 'us-nc-onemap-parcels', 'sale-1', '2024-02-08',
                'assessment_roll'
            )
            """,
            (parcel_id,),
        )
        instrument_id = db.execute(
            """
            INSERT INTO recorded_instrument(
                source_id, jurisdiction_geoid, native_document_id,
                instrument_type, execution_date, recording_date
            ) VALUES (
                'us-test-recorder', '37005', 'BK1-PG2', 'DEED',
                '2024-02-08', '2024-02-09'
            )
            """
        ).lastrowid
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name
            ) VALUES (?, 1, 'grantee', 'SMITH, THOMAS', 'SMITH THOMAS')
            """,
            (instrument_id,),
        )
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence
            ) VALUES (?, ?, 'native_parcel_id', 1.0)
            """,
            (instrument_id, parcel_id),
        )
        db.commit()
    finally:
        db.close()


def _parse(*values):
    return query_property.build_parser().parse_args(list(values))


def test_point_parser_accepts_explicit_negative_longitude() -> None:
    args = _parse(
        "point",
        "--source",
        query_property.VIRGINIA_VGIN_PARCELS_SOURCE_ID,
        "--longitude",
        "-77.6104",
        "--latitude",
        "37.7099",
    )

    assert args.query == "-77.6104,37.7099"
    assert args.longitude == pytest.approx(-77.6104)
    assert args.latitude == pytest.approx(37.7099)


def test_point_parser_rejects_partial_or_mixed_coordinate_selectors() -> None:
    with pytest.raises(SystemExit):
        _parse("point", "--longitude", "-77.6104")
    with pytest.raises(SystemExit):
        _parse(
            "point",
            "-77.6104,37.7099",
            "--longitude",
            "-77.6104",
            "--latitude",
            "37.7099",
        )


def test_washington_jurisdiction_metadata_preserves_state_and_county():
    state = query_property._jurisdiction("53")
    county = query_property._jurisdiction("53033")

    assert state.state_code == "WA"
    assert state.county_fips is None
    assert county.state_code == "WA"
    assert county.county_fips == "53033"


def test_denver_jurisdiction_metadata_preserves_state_and_county():
    state = query_property._jurisdiction("08")
    county = query_property._jurisdiction("08031")

    assert state.state_code == "CO"
    assert state.county_fips is None
    assert county.state_code == "CO"
    assert county.county_fips == "08031"


def _adapter_envelope(source_id, operation):
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=source_id,
            name=source_id,
            source_role="test_adapter",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="test",
            name="Test jurisdiction",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={},
            requested_limit=7,
        ),
    )
    return PublicRecordsResult.success(query, [])


def test_local_property_front_door_searches_all_core_views(tmp_path, monkeypatch):
    db_path = tmp_path / "property.db"
    _seed_property(db_path)
    monkeypatch.setattr(query_property, "log_search", lambda *args: None)

    owner = query_property.execute(
        _parse("owner", "smith", "--property-db", str(db_path))
    )
    searched = query_property.execute(
        _parse("search", "smith", "--property-db", str(db_path))
    )
    address = query_property.execute(
        _parse("address", "100 main", "--property-db", str(db_path))
    )
    parcel = query_property.execute(
        _parse("parcel", "ALT-3013", "--property-db", str(db_path))
    )
    instrument = query_property.execute(
        _parse("instrument", "SMITH", "--property-db", str(db_path))
    )
    chain = query_property.execute(
        _parse("chain", "3013467134", "--property-db", str(db_path))
    )
    mapped = query_property.execute(
        _parse("map", "3013467134", "--property-db", str(db_path))
    )

    assert owner["status"] == "ok"
    assert owner["records"][0]["matched_owner"]["raw_name"] == "SMITH, THOMAS"
    assert searched["status"] == "ok"
    assert searched["records"][0]["matched_owner"]["raw_name"] == ("SMITH, THOMAS")
    assert address["records"][0]["matched_address"]["postal_code"] == "28675"
    assert parcel["records"][0]["native_parcel_id"] == "3013467134"
    assert instrument["records"][0]["native_document_id"] == "BK1-PG2"
    assert chain["records"][0]["chain_analysis"]["complete_chain_claimed"] is False
    assert (
        chain["records"][0]["recorded_instruments"][0]["native_document_id"]
        == "BK1-PG2"
    )
    assert (
        "sale_without_instrument_link"
        in chain["records"][0]["chain_analysis"]["gap_flags"]
    )
    assert mapped["records"][0]["geometry"]["surveyed_legal_boundary"] is False
    assert owner["query"]["source"]["source_id"] == ("local-property-records-sidecar")


def test_local_property_cache_miss_is_partial_and_cursor_is_validated(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "property.db"
    _seed_property(db_path)
    logged = []
    monkeypatch.setattr(query_property, "log_search", lambda *args: logged.append(args))

    empty = query_property.execute(
        _parse(
            "owner",
            "NO SUCH OWNER",
            "--jurisdiction",
            "37005",
            "--property-db",
            str(db_path),
        )
    )
    bad_cursor = query_property.execute(
        _parse(
            "owner",
            "SMITH",
            "--property-db",
            str(db_path),
            "--cursor",
            "bad",
        )
    )

    assert empty["status"] == "partial"
    assert empty["errors"][0]["code"] == "local_cache_miss"
    coverage = empty["errors"][0]["details"]["coverage"]
    assert coverage["authoritative_zero"] is False
    assert coverage["sidecar"]["requested_jurisdiction_counts"]["parcels"] == 1
    assert logged[0][2] is None
    assert bad_cursor["status"] == "source_changed"
    assert bad_cursor["errors"][0]["code"] == "local_sidecar_query_failed"
    assert logged[1][2] is None


def test_local_property_preserves_exact_source_authoritative_zero(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "property.db"
    _seed_property(db_path)
    source_query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=query_property.NC_SOURCE_ID,
            name="NC OneMap",
            source_role="parcel_assessment",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="37005",
            name="Alleghany County",
            state_code="NC",
            county_fips="37005",
        ),
        query=QueryMetadata(
            operation="owner",
            parameters={
                "selector": "NO SUCH OWNER",
                "county_geoid": "37005",
                "return_geometry": False,
            },
            requested_limit=50,
        ),
    )
    ingest_property_envelope(
        PublicRecordsResult.success(
            source_query,
            [],
            retrieved_at="2026-07-28T12:00:00Z",
        ).to_dict(),
        db_path=db_path,
    )
    logged = []
    monkeypatch.setattr(
        query_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    payload = query_property.execute(
        _parse(
            "owner",
            "NO SUCH OWNER",
            "--jurisdiction",
            "37005",
            "--property-db",
            str(db_path),
        )
    )

    assert payload["status"] == "no_results"
    assert payload["warnings"][0].startswith(
        "Exact source-query zero preserved from us-nc-onemap-parcels"
    )
    assert logged[0][2] == 0


def test_local_property_uncovered_jurisdiction_is_unavailable(tmp_path, monkeypatch):
    db_path = tmp_path / "property.db"
    _seed_property(db_path)
    monkeypatch.setattr(query_property, "log_search", lambda *args: None)

    payload = query_property.execute(
        _parse(
            "owner",
            "SMITH",
            "--jurisdiction",
            "06037",
            "--property-db",
            str(db_path),
        )
    )

    assert payload["status"] == "unavailable"
    error = payload["errors"][0]
    assert error["code"] == "local_scope_not_covered"
    assert error["details"]["coverage"]["sidecar"]["requested_jurisdiction_counts"] == {
        "instruments": 0,
        "parcels": 0,
    }
    assert "discover" in error["details"]["route_guidance"]


def _live_envelope():
    query = build_query(
        "parcel",
        "3013467134",
        county_geoid="37005",
        limit=1,
        cursor=None,
        return_geometry=False,
    )
    record = _normalize_feature(
        {
            "attributes": {
                "objectid": 1,
                "parno": "3013467134",
                "ownname": "SMITH",
                "stfips": "37",
                "cntyfips": "005",
                "stcntyfips": "37005",
                "cntyname": "Alleghany",
            }
        },
        schema_fingerprint="a" * 64,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-28T12:00:00Z",
    )


@pytest.mark.parametrize(
    (
        "source_id",
        "operation",
        "selector",
        "extra_args",
        "expected_command",
        "expected_values",
    ),
    [
        (
            query_property.NC_SOURCE_ID,
            "owner",
            "SMITH",
            (),
            "owner",
            {"query": "SMITH", "geometry": False},
        ),
        (
            query_property.NC_SOURCE_ID,
            "address",
            "100 MAIN ST",
            ("--county-code", "005"),
            "address",
            {"query": "100 MAIN ST", "county_fips": "005"},
        ),
        (
            query_property.NC_SOURCE_ID,
            "parcel",
            "3013467134",
            ("--jurisdiction", "37005"),
            "parcel",
            {"query": "3013467134", "county_fips": "37005"},
        ),
        (
            query_property.NC_SOURCE_ID,
            "map",
            "3013467134",
            (),
            "parcel",
            {"query": "3013467134", "geometry": True},
        ),
        (
            query_property.BEXAR_SOURCE_ID,
            "owner",
            "TAUREAN GENERAL SERVICES",
            (),
            "owner",
            {
                "query": "TAUREAN GENERAL SERVICES",
                "geometry": False,
                "year": None,
            },
        ),
        (
            query_property.BEXAR_SOURCE_ID,
            "address",
            "26545 INTERSTATE 10 W",
            (),
            "address",
            {
                "query": "26545 INTERSTATE 10 W",
                "geometry": False,
                "year": None,
            },
        ),
        (
            query_property.BEXAR_SOURCE_ID,
            "parcel",
            "358951",
            ("--tax-year", "2026"),
            "parcel",
            {"query": "358951", "geometry": False, "year": 2026},
        ),
        (
            query_property.BEXAR_SOURCE_ID,
            "map",
            "358951",
            (),
            "parcel",
            {"query": "358951", "geometry": True, "year": None},
        ),
        (
            query_property.DENVER_PROPERTY_SOURCE_ID,
            "owner",
            "RODRIGUEZ",
            ("--jurisdiction", "08031"),
            "owner",
            {"query": "RODRIGUEZ", "geometry": False},
        ),
        (
            query_property.DENVER_PROPERTY_SOURCE_ID,
            "address",
            "16159 E RANDOLPH PL",
            (),
            "address",
            {"query": "16159 E RANDOLPH PL", "geometry": False},
        ),
        (
            query_property.DENVER_PROPERTY_SOURCE_ID,
            "parcel",
            "0017103008000",
            (),
            "parcel",
            {"query": "0017103008000", "geometry": False},
        ),
        (
            query_property.DENVER_PROPERTY_SOURCE_ID,
            "map",
            "0017103008000",
            (),
            "parcel",
            {"query": "0017103008000", "geometry": True},
        ),
        (
            query_property.DELAWARE_FIRSTMAP_SOURCE_ID,
            "parcel",
            "1001300033",
            ("--jurisdiction", "10003"),
            "pin",
            {
                "pin": "1001300033",
                "county": "New Castle",
                "geometry": False,
            },
        ),
        (
            query_property.DELAWARE_FIRSTMAP_SOURCE_ID,
            "map",
            "1001300033",
            ("--county-code", "003"),
            "pin",
            {
                "pin": "1001300033",
                "county": "New Castle",
                "geometry": True,
            },
        ),
        (
            query_property.ARLINGTON_PROPERTY_SOURCE_ID,
            "address",
            "3905 44TH ST N",
            ("--jurisdiction", "51013"),
            "address",
            {"query": "3905 44TH ST N", "geometry": False},
        ),
        (
            query_property.ARLINGTON_PROPERTY_SOURCE_ID,
            "parcel",
            "03-001-009",
            (),
            "parcel",
            {"query": "03-001-009", "geometry": False},
        ),
        (
            query_property.ARLINGTON_PROPERTY_SOURCE_ID,
            "map",
            "03001009",
            (),
            "parcel",
            {"query": "03001009", "geometry": True},
        ),
        (
            query_property.COOK_SOURCE_ID,
            "parcel",
            "01011060091001",
            ("--tax-year", "2025"),
            "parcel",
            {"query": "01011060091001", "tax_year": 2025},
        ),
        (
            query_property.MD_SOURCE_ID,
            "address",
            "7 TRAYMORE RD",
            ("--county-code", "04"),
            "address",
            {"query": "7 TRAYMORE RD", "county_code": "04"},
        ),
        (
            query_property.MD_SOURCE_ID,
            "parcel",
            "04030311078580",
            ("--jurisdiction", "24005"),
            "parcel",
            {"query": "04030311078580", "county_code": "04"},
        ),
        (
            query_property.MIAMI_DADE_PA_SOURCE_ID,
            "owner",
            "MIAMI-DADE COUNTY",
            ("--jurisdiction", "12086"),
            "owner",
            {
                "query": "MIAMI-DADE COUNTY",
                "unit": None,
                "geometry": False,
            },
        ),
        (
            query_property.MIAMI_DADE_PA_SOURCE_ID,
            "address",
            "111 NW 1 ST",
            (),
            "address",
            {"query": "111 NW 1 ST", "unit": None, "geometry": False},
        ),
        (
            query_property.MIAMI_DADE_PA_SOURCE_ID,
            "parcel",
            "0101000000020",
            (),
            "folio",
            {"query": "0101000000020", "geometry": False},
        ),
        (
            query_property.MIAMI_DADE_PA_SOURCE_ID,
            "map",
            "0101000000020",
            (),
            "folio",
            {"query": "0101000000020", "geometry": True},
        ),
        (
            query_property.EBR_SOURCE_ID,
            "owner",
            "SMITH LLC",
            (),
            "owner",
            {"query": "SMITH LLC", "parish": "ebr"},
        ),
        (
            query_property.EBR_SOURCE_ID,
            "address",
            "100 MAIN ST",
            (),
            "address",
            {"query": "100 MAIN ST", "parish": "ebr"},
        ),
        (
            query_property.EBR_SOURCE_ID,
            "parcel",
            "3076237",
            (),
            "parcel",
            {"assessment_no": "3076237", "parish": "ebr"},
        ),
        (
            query_property.ORLEANS_SOURCE_ID,
            "owner",
            "EXAMPLE HOLDINGS LLC",
            (),
            "owner",
            {
                "query": "EXAMPLE HOLDINGS LLC",
                "geometry": False,
                "tax_year": None,
            },
        ),
        (
            query_property.ORLEANS_SOURCE_ID,
            "address",
            "1300 PERDIDO ST",
            ("--geometry",),
            "address",
            {
                "query": "1300 PERDIDO ST",
                "geometry": True,
                "tax_year": None,
            },
        ),
        (
            query_property.ORLEANS_SOURCE_ID,
            "account",
            "615199817",
            (),
            "account",
            {
                "query": "615199817",
                "geometry": False,
                "tax_year": None,
            },
        ),
        (
            query_property.ORLEANS_SOURCE_ID,
            "parcel",
            "412100101",
            ("--tax-year", "2025"),
            "parcel",
            {
                "query": "412100101",
                "geometry": False,
                "tax_year": 2025,
                "timeout": 60.0,
            },
        ),
        (
            query_property.ORLEANS_SOURCE_ID,
            "map",
            "41050755",
            (),
            "parcel",
            {
                "query": "41050755",
                "geometry": True,
                "tax_year": None,
            },
        ),
        (
            query_property.ORLEANS_SOURCE_ID,
            "search",
            "EXAMPLE",
            (
                "--cursor",
                "orleans:offset:7",
                "--page-size",
                "250",
                "--max-records",
                "900",
                "--timeout",
                "12",
                "--minimum-interval",
                "0.75",
            ),
            "search",
            {
                "query": "EXAMPLE",
                "geometry": False,
                "tax_year": None,
                "cursor": "orleans:offset:7",
                "page_size": 250,
                "max_records": 900,
                "timeout": 12.0,
                "minimum_interval": 0.75,
            },
        ),
        (
            query_property.REEVES_SOURCE_ID,
            "owner",
            "THREE RIVERS ACQUISITION III LLC",
            (
                "--cursor",
                "kofile:v1:fixture",
                "--timeout",
                "12",
                "--minimum-interval",
                "0.75",
            ),
            "search",
            {
                "query": "THREE RIVERS ACQUISITION III LLC",
                "ocr": False,
                "date_from": None,
                "date_to": None,
                "offset": 0,
                "cursor": "kofile:v1:fixture",
                "timeout": 12.0,
                "minimum_interval": 0.75,
                "max_attempts": 3,
            },
        ),
        (
            "us-pa-berks-recorder-publicsearch",
            "instrument",
            "2024000062",
            (
                "--cursor",
                "kofile:v1:fixture",
                "--department",
                "MISC",
                "--timeout",
                "12",
                "--minimum-interval",
                "0.75",
            ),
            "search",
            {
                "source": "us-pa-berks-recorder-publicsearch",
                "department": "MISC",
                "query": "2024000062",
                "ocr": False,
                "date_from": None,
                "date_to": None,
                "offset": 0,
                "cursor": "kofile:v1:fixture",
                "timeout": 12.0,
                "minimum_interval": 0.75,
                "max_attempts": 3,
            },
        ),
        (
            query_property.HARRIS_RECORDER_SOURCE_ID,
            "instrument",
            "RP-2026-72194",
            ("--jurisdiction", "48201"),
            "search",
            {
                "file_number": "RP-2026-72194",
                "grantor": None,
                "grantee": None,
                "description": None,
            },
        ),
        (
            query_property.HARRIS_FORECLOSURE_SOURCE_ID,
            "search",
            "FRCL-2026-4797",
            ("--jurisdiction", "48201"),
            "search",
            {
                "document_id": "FRCL-2026-4797",
                "file_date": None,
                "sale_date": None,
            },
        ),
        (
            query_property.ACRIS_SOURCE_ID,
            "owner",
            "EXAMPLE LLC",
            (),
            "party",
            {"query": "EXAMPLE LLC", "exact": False},
        ),
        (
            query_property.ACRIS_SOURCE_ID,
            "parcel",
            "1-1386-10",
            (),
            "address",
            {"borough": "1", "block": "1386", "lot": "10"},
        ),
        (
            query_property.ACRIS_SOURCE_ID,
            "instrument",
            "2017021700466001",
            (),
            "document",
            {"document_id": "2017021700466001", "max_docs": 1},
        ),
        (
            query_property.ACRIS_SOURCE_ID,
            "chain",
            "1386-10",
            ("--jurisdiction", "36061"),
            "history",
            {"borough": "1", "block": "1386", "lot": "10"},
        ),
    ],
)
def test_live_route_matrix_translates_args_and_passes_catalog_decision(
    tmp_path,
    monkeypatch,
    source_id,
    operation,
    selector,
    extra_args,
    expected_command,
    expected_values,
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[source_id][operation]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return _adapter_envelope(source_id, expected_command)

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--catalog-db",
            str(catalog_path),
            "--limit",
            "7",
            *extra_args,
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == expected_command
    assert adapter_args.limit == 7
    assert decision["allowed"] is True
    assert decision["source_id"] == source_id
    for field, expected in expected_values.items():
        assert getattr(adapter_args, field) == expected


def test_harris_recorder_unified_lookup_has_no_default_caller_cap():
    route = query_property.LIVE_ROUTES[query_property.HARRIS_RECORDER_SOURCE_ID][
        "instrument"
    ]
    adapter_args = route.translate(
        _parse(
            "instrument",
            "RP-2026-72194",
            "--source",
            query_property.HARRIS_RECORDER_SOURCE_ID,
        ),
        route.adapter_command,
    )

    assert adapter_args.file_number == "RP-2026-72194"
    assert adapter_args.limit is None


def test_denver_property_unified_lookup_has_no_default_caller_cap():
    route = query_property.LIVE_ROUTES[query_property.DENVER_PROPERTY_SOURCE_ID][
        "owner"
    ]
    adapter_args = route.translate(
        _parse(
            "owner",
            "RODRIGUEZ",
            "--source",
            query_property.DENVER_PROPERTY_SOURCE_ID,
        ),
        route.adapter_command,
    )

    assert adapter_args.limit is None
    assert adapter_args.max_records is None


@pytest.mark.parametrize(
    (
        "source_id",
        "operation",
        "selector",
        "extra_args",
        "expected_command",
        "expected_field",
        "expected_county",
        "expected_geometry",
    ),
    [
        (
            query_property.OREGON_PORTLAND_TAXLOT_SOURCE_ID,
            "owner",
            "NORTHWEST HOLDINGS LLC",
            ("--jurisdiction", "41051"),
            "search",
            "owner",
            "41051",
            False,
        ),
        (
            query_property.query_oregon_taxlots.METRO_SOURCE_ID,
            "address",
            "123 MAIN ST",
            ("--jurisdiction", "41", "--county-fips", "067"),
            "search",
            "address",
            "067",
            False,
        ),
        (
            query_property.query_oregon_taxlots.OWRD_SOURCE_ID,
            "map",
            "21E10DC12800",
            ("--jurisdiction", "41029"),
            "parcel",
            "parcel",
            "41029",
            True,
        ),
    ],
)
def test_oregon_taxlot_routes_preserve_source_scope_and_selectors(
    source_id,
    operation,
    selector,
    extra_args,
    expected_command,
    expected_field,
    expected_county,
    expected_geometry,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            *extra_args,
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.query == selector
    assert adapter_args.source == source_id
    assert adapter_args.field == expected_field
    assert adapter_args.county == expected_county
    assert adapter_args.geometry is expected_geometry


def test_oregon_taxlot_route_passes_catalog_decision(
    tmp_path,
    monkeypatch,
):
    source_id = query_property.OREGON_PORTLAND_TAXLOT_SOURCE_ID
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[source_id]["parcel"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return _adapter_envelope(source_id, "parcel")

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "parcel",
            "R123456",
            "--source",
            source_id,
            "--jurisdiction",
            "41051",
            "--catalog-db",
            str(catalog_path),
            "--limit",
            "7",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "parcel"
    assert adapter_args.limit == 7
    assert decision["allowed"] is True
    assert decision["source_id"] == source_id


def test_oregon_sources_expose_only_published_owner_search():
    assert (
        "owner"
        in query_property.LIVE_ROUTES[query_property.OREGON_PORTLAND_TAXLOT_SOURCE_ID]
    )
    assert (
        "owner"
        not in query_property.LIVE_ROUTES[
            query_property.query_oregon_taxlots.METRO_SOURCE_ID
        ]
    )
    assert (
        "owner"
        not in query_property.LIVE_ROUTES[
            query_property.query_oregon_taxlots.OWRD_SOURCE_ID
        ]
    )


@pytest.mark.parametrize(
    ("operation", "selector", "expected_command", "expected_field", "geometry"),
    [
        ("owner", "VACH", "search", "owner", False),
        ("address", "14987 BUGGY WHIP", "search", "address", False),
        ("account", "135278", "search", "account", False),
        ("parcel", "141031B000700", "parcel", "parcel", False),
        ("map", "141031B000700", "parcel", "parcel", True),
    ],
)
def test_deschutes_routes_preserve_relationship_search_selector(
    operation,
    selector,
    expected_command,
    expected_field,
    geometry,
):
    source_id = query_property.DESCHUTES_PROPERTY_SOURCE_ID
    route = query_property.LIVE_ROUTES[source_id][operation]

    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--jurisdiction",
            "41017",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.query == selector
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is geometry


def test_deschutes_route_passes_catalog_decision(
    tmp_path,
    monkeypatch,
):
    source_id = query_property.DESCHUTES_PROPERTY_SOURCE_ID
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[source_id]["parcel"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return _adapter_envelope(source_id, "parcel")

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "parcel",
            "141031B000700",
            "--source",
            source_id,
            "--jurisdiction",
            "41017",
            "--catalog-db",
            str(catalog_path),
            "--limit",
            "7",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "parcel"
    assert adapter_args.limit == 7
    assert decision["allowed"] is True
    assert decision["source_id"] == source_id


def test_deschutes_guidance_keeps_sales_complement_distinct() -> None:
    guidance = query_property._source_guidance(
        query_property.DESCHUTES_PROPERTY_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert "query_deschutes_property.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == [
        "account",
        "address",
        "map",
        "owner",
        "parcel",
        "search",
    ]
    assert "joined separately" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "selector", "expected_field"),
    [
        ("search", "VACH 14987 BUGGY WHIP", "general"),
        ("owner", "VACH", "owner"),
        ("address", "14987 BUGGY WHIP", "situs"),
        ("subdivision", "SISTERS", "subdivision"),
        ("mobile-park", "TUMALO", "mobile-park"),
    ],
)
def test_deschutes_dial_routes_preserve_every_native_search_mode(
    operation,
    selector,
    expected_field,
):
    source_id = query_property.DESCHUTES_DIAL_SOURCE_ID
    route = query_property.LIVE_ROUTES[source_id][operation]

    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--jurisdiction",
            "41017",
            "--limit",
            "7",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "search"
    assert adapter_args.query == selector
    assert adapter_args.field == expected_field
    assert adapter_args.limit == 7


@pytest.mark.parametrize(
    ("operation", "selector", "expected_field"),
    [
        ("account", "135278", "account"),
        ("parcel", "141031B000700", "taxlot"),
    ],
)
def test_deschutes_dial_exact_routes_return_full_account_detail(
    operation,
    selector,
    expected_field,
):
    source_id = query_property.DESCHUTES_DIAL_SOURCE_ID
    route = query_property.LIVE_ROUTES[source_id][operation]

    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--county-fips",
            "017",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "account"
    assert adapter_args.selector == selector
    assert adapter_args.field == expected_field
    assert adapter_args.components == (
        query_property.query_deschutes_dial.DEFAULT_COMPONENTS
    )


def test_deschutes_dial_route_passes_catalog_decision(
    tmp_path,
    monkeypatch,
):
    source_id = query_property.DESCHUTES_DIAL_SOURCE_ID
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[source_id]["account"]
    calls = []

    def fake_execute(adapter_args, *, access_decision):
        calls.append((adapter_args, access_decision))
        return _adapter_envelope(source_id, "account")

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "account",
            "135278",
            "--source",
            source_id,
            "--jurisdiction",
            "41017",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "account"
    assert adapter_args.selector == "135278"
    assert adapter_args.field == "account"
    assert decision["allowed"] is True
    assert decision["source_id"] == source_id


def test_deschutes_dial_guidance_keeps_arcgis_provenance_separate() -> None:
    guidance = query_property._source_guidance(query_property.DESCHUTES_DIAL_SOURCE_ID)

    assert guidance["mode"] == "unified_live"
    assert "query_deschutes_dial.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == [
        "account",
        "address",
        "mobile-park",
        "owner",
        "parcel",
        "search",
        "subdivision",
    ]
    assert "separate ArcGIS parcel source" in guidance["note"]
    assert "parcel geometry" in guidance["note"]


def test_deschutes_cdd_route_preserves_account_identity_and_cursor() -> None:
    source_id = query_property.DESCHUTES_CDD_WEBLINK_SOURCE_ID
    route = query_property.LIVE_ROUTES[source_id]["account"]

    adapter_args = route.translate(
        _parse(
            "account",
            "135278",
            "--source",
            source_id,
            "--jurisdiction",
            "41017",
            "--limit",
            "7",
            "--cursor",
            "continuation",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "account"
    assert adapter_args.account_id == "135278"
    assert adapter_args.limit == 7
    assert adapter_args.cursor == "continuation"
    assert adapter_args.hydrate is False


def test_deschutes_cdd_route_uses_catalog_and_source_adapter(
    tmp_path,
    monkeypatch,
) -> None:
    source_id = query_property.DESCHUTES_CDD_WEBLINK_SOURCE_ID
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    calls = []

    def fake_execute(adapter_args):
        calls.append(adapter_args)
        return _adapter_envelope(source_id, "account")

    monkeypatch.setattr(
        query_property.query_deschutes_laserfiche,
        "execute",
        fake_execute,
    )
    payload = query_property.execute(
        _parse(
            "account",
            "135278",
            "--source",
            source_id,
            "--jurisdiction",
            "41017",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "no_results"
    assert calls[0].account_id == "135278"


def test_deschutes_cdd_guidance_keeps_discovery_and_document_routes_distinct() -> None:
    guidance = query_property._source_guidance(
        query_property.DESCHUTES_CDD_WEBLINK_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert guidance["unified_operations"] == ["account"]
    assert guidance["native_identity"] == "laserfiche_entry_id"
    assert guidance["property_join_keys"] == [
        "deschutes_dial_account_id",
        "map_taxlot",
    ]
    assert "query_deschutes_laserfiche.py" in guidance["direct_tool"]
    assert "records-request" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "selector", "expected"),
    [
        (
            "owner",
            "POLVERINO",
            {
                "last_name": "POLVERINO",
                "view": "party",
                "year": None,
                "historic_number": None,
            },
        ),
        (
            "search",
            "APARTNERS",
            {
                "last_name": "APARTNERS",
                "view": "party",
                "year": None,
                "historic_number": None,
            },
        ),
        (
            "instrument",
            "2023-002123",
            {
                "last_name": None,
                "view": "document",
                "year": 2023,
                "document_from": 2123,
                "document_to": 2123,
                "historic_number": None,
            },
        ),
        (
            "instrument",
            "BOOK 42 PAGE 7",
            {
                "last_name": None,
                "view": "document",
                "year": None,
                "historic_number": "BOOK 42 PAGE 7",
            },
        ),
    ],
)
def test_oregon_helion_unified_routes_preserve_native_selectors(
    operation,
    selector,
    expected,
):
    source_id = "us-or-wasco-helion-recorder"
    route = query_property.LIVE_ROUTES[source_id][operation]

    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--jurisdiction",
            "41065",
            "--limit",
            "9",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "search"
    assert adapter_args.source == source_id
    assert adapter_args.limit == 9
    for key, value in expected.items():
        assert getattr(adapter_args, key) == value


def test_oregon_helion_routes_validate_selected_county_context() -> None:
    source_id = "us-or-wasco-helion-recorder"
    route = query_property.LIVE_ROUTES[source_id]["owner"]

    with pytest.raises(ValueError, match="county GEOID 41065"):
        route.translate(
            _parse(
                "owner",
                "SMITH",
                "--source",
                source_id,
                "--jurisdiction",
                "41059",
            ),
            route.adapter_command,
        )


def test_oregon_helion_omitted_shared_limit_remains_exhaustive() -> None:
    source_id = "us-or-marion-clerk-recorded-documents"
    route = query_property.LIVE_ROUTES[source_id]["owner"]

    adapter_args = route.translate(
        _parse(
            "owner",
            "SMITH",
            "--source",
            source_id,
            "--jurisdiction",
            "41047",
        ),
        route.adapter_command,
    )

    assert adapter_args.limit is None


def test_oregon_helion_guidance_retains_advanced_direct_routes() -> None:
    guidance = query_property._source_guidance("us-or-umatilla-helion-recorder")
    deschutes = query_property._source_guidance("us-or-deschutes-helion-recorder")

    assert guidance["mode"] == "unified_live"
    assert "query_oregon_helion_recorder.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == [
        "instrument",
        "owner",
        "search",
    ]
    assert "taxlot" in guidance["note"]
    assert "certified-copy" in guidance["note"]
    assert "tenant form" in guidance["selector_discovery"]
    assert guidance["official_complements"] == [
        {
            "kind": "county_copy_order",
            "join_keys": ["recording_number", "party_name", "date"],
            "relationship": "document_copy_complement",
        }
    ]
    assert {item["kind"] for item in deschutes["official_complements"]} == {
        "deschutes_assessor_dial",
        "county_copy_order",
    }


@pytest.mark.parametrize(
    ("source_id", "operation", "selector", "field", "stage"),
    (
        (
            "us-or-tillamook-tax-foreclosure-publications",
            "search",
            "25-CV47055",
            "query",
            "foreclosure_list_published",
        ),
        (
            "us-or-marion-tax-foreclosure-publications",
            "owner",
            "EXAMPLE OWNER",
            "owner",
            "end_of_redemption_notice",
        ),
        (
            "us-or-clackamas-tax-foreclosure-publications",
            "address",
            "123 MAIN",
            "address",
            "auction_results",
        ),
        (
            "us-or-tillamook-tax-foreclosure-publications",
            "account",
            "787",
            "account",
            "foreclosure_list_published",
        ),
        (
            "us-or-tillamook-tax-foreclosure-publications",
            "parcel",
            "1N1005AB01100",
            "map_tax_lot",
            "foreclosure_list_published",
        ),
        (
            "us-or-multnomah-tax-foreclosure-publications",
            "parcel",
            "R264159",
            "property_id",
            "statutory_redemption_notice",
        ),
    ),
)
def test_oregon_tax_foreclosure_routes_preserve_stage_and_selector(
    source_id,
    operation,
    selector,
    field,
    stage,
) -> None:
    route = query_property.LIVE_ROUTES[source_id][operation]
    uncapped = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--process-stage",
            stage,
        ),
        route.adapter_command,
    )
    bounded = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--process-stage",
            stage,
            "--limit",
            "7",
        ),
        route.adapter_command,
    )

    assert uncapped.command == "search"
    assert uncapped.source == source_id
    assert uncapped.process_stage == stage
    assert getattr(uncapped, field) == selector
    assert uncapped.max_records is None
    assert bounded.max_records == 7


def test_oregon_tax_foreclosure_guidance_and_catalog_keep_counties_distinct(
    tmp_path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    tillamook = query_property._source_guidance(
        "us-or-tillamook-tax-foreclosure-publications"
    )
    multnomah = query_property._source_guidance(
        "us-or-multnomah-tax-foreclosure-publications"
    )

    assert tillamook["unified_operations"] == [
        "account",
        "address",
        "owner",
        "parcel",
        "search",
    ]
    assert tillamook["publication_process_stages"] == ["foreclosure_list_published"]
    assert multnomah["publication_process_stages"] == [
        "statutory_redemption_notice",
        "judgment_in_progress",
        "tax_title_inventory",
        "sale_authorization",
    ]
    assert {complement["role"] for complement in multnomah["official_complements"]} == {
        "parcel_and_tax_account_context",
        "records_request_for_unpublished_material",
        "post_sale_surplus_notices",
    }
    catalog = query_property.PublicRecordsCatalog(catalog_path)
    detail = catalog.show_source("us-or-marion-tax-foreclosure-publications")
    assert {item["geoid"] for item in detail["jurisdictions"]} == {"41", "41047"}
    assert (
        catalog.machine_acquisition_decision(
            "us-or-marion-tax-foreclosure-publications"
        )["allowed"]
        is True
    )


@pytest.mark.parametrize(
    ("operation", "expected_command", "expected_field"),
    (
        ("search", "search", "name"),
        ("owner", "search", "name"),
        ("address", "search", "address"),
        ("parcel", "search", "map"),
        ("account", "detail", None),
    ),
)
def test_oregon_helion_property_routes_preserve_common_selector_semantics(
    operation,
    expected_command,
    expected_field,
) -> None:
    source_id = "us-or-morrow-helion-property"
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "171" if operation == "account" else "SMITH",
            "--source",
            source_id,
            "--jurisdiction",
            "41049",
            "--limit",
            "17",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.source == source_id
    if expected_command == "search":
        assert adapter_args.field == expected_field
        assert adapter_args.limit == 17
        assert adapter_args.query == "SMITH"
    else:
        assert adapter_args.account == "171"
        assert adapter_args.roll_type == "R"


def test_oregon_helion_property_routes_validate_county_context() -> None:
    source_id = "us-or-columbia-helion-property"
    route = query_property.LIVE_ROUTES[source_id]["owner"]

    with pytest.raises(ValueError, match="GEOID 41009"):
        route.translate(
            _parse(
                "owner",
                "SMITH",
                "--source",
                source_id,
                "--jurisdiction",
                "41049",
            ),
            route.adapter_command,
        )


def test_oregon_helion_property_guidance_keeps_tenant_capabilities_distinct() -> None:
    columbia = query_property._source_guidance("us-or-columbia-helion-property")
    tillamook = query_property._source_guidance("us-or-tillamook-helion-property")
    umatilla = query_property._source_guidance("us-or-umatilla-helion-property")

    assert columbia["unified_operations"] == [
        "account",
        "address",
        "owner",
        "parcel",
        "search",
    ]
    assert columbia["native_search_fields"] == [
        "account",
        "name",
        "address",
        "map",
    ]
    assert "tax_account" in umatilla["native_search_fields"]
    assert "legal" in umatilla["native_search_fields"]
    assert {complement["kind"] for complement in columbia["official_complements"]} == {
        "columbia_current_noncertified_webmaps",
        "columbia_certified_tax_roll_data",
        "columbia_quarterly_property_sales",
    }
    assert {complement["kind"] for complement in tillamook["official_complements"]} >= {
        "tillamook_prior_assessment_tax_rolls",
        "tillamook_real_property_tax_foreclosure",
        "tillamook_county_real_property_sales",
    }
    assert "query_oregon_helion_property.py" in columbia["direct_tool"]


def test_benton_helion_property_is_in_shared_routes_and_guidance() -> None:
    source_id = "us-or-benton-helion-property"

    assert set(query_property.LIVE_ROUTES[source_id]) == {
        "search",
        "owner",
        "address",
        "parcel",
        "account",
    }
    guidance = query_property._source_guidance(source_id)
    assert guidance["native_search_fields"] == [
        "account",
        "tax_account",
        "name",
        "address",
        "map",
        "legal",
    ]
    assert {complement["kind"] for complement in guidance["official_complements"]} == {
        "benton_assessment_search_and_history",
        "benton_taxlot_owner_arcgis_and_bulk",
        "benton_helion_recorder",
    }


@pytest.mark.parametrize(
    ("source_id", "operation", "expected_field", "expected_geometry"),
    [
        (
            "us-or-linn-county-assessor-taxlots",
            "owner",
            "owner",
            False,
        ),
        (
            "us-or-josephine-county-assessor-taxlots",
            "address",
            "situs",
            False,
        ),
        (
            "us-or-klamath-county-assessor-taxlots",
            "map",
            "parcel",
            True,
        ),
    ],
)
def test_linn_josephine_klamath_routes_keep_county_native_fields(
    source_id,
    operation,
    expected_field,
    expected_geometry,
) -> None:
    config = query_property.query_oregon_linn_josephine_klamath_assessors.SOURCES[
        source_id
    ]
    route = query_property.LIVE_ROUTES[source_id][operation]

    adapter_args = route.translate(
        _parse(
            operation,
            "fixture",
            "--source",
            source_id,
            "--jurisdiction",
            config.county_geoid,
            "--limit",
            "13",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "search"
    assert adapter_args.source == source_id
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is expected_geometry
    assert adapter_args.limit == 13


def test_linn_josephine_klamath_guidance_retains_distinct_complements() -> None:
    linn = query_property._source_guidance("us-or-linn-county-assessor-taxlots")
    josephine = query_property._source_guidance(
        "us-or-josephine-county-assessor-taxlots"
    )
    klamath = query_property._source_guidance("us-or-klamath-county-assessor-taxlots")

    assert {item["source_id"] for item in linn["official_complements"]} == {
        "us-or-linn-county-account-detail",
        "us-or-linn-county-assessor-maps",
    }
    assert {item["source_id"] for item in josephine["official_complements"]} == {
        "us-or-josephine-property-detail",
        "us-or-josephine-digital-research-room",
    }
    assert {item["source_id"] for item in klamath["official_complements"]} == {
        "us-or-klamath-property-search-online",
        "us-or-klamath-tax-maps",
        "us-or-klamath-digital-research-room",
        "us-or-klamath-public-records-request",
    }


@pytest.mark.parametrize(
    ("source_id", "expected_module"),
    [
        ("us-or-jackson-county-accela-building-details", "building"),
        ("us-or-jackson-county-accela-planning-details", "planning"),
    ],
)
def test_jackson_accela_exact_event_route_preserves_component(
    source_id,
    expected_module,
) -> None:
    route = query_property.LIVE_ROUTES[source_id]["event"]

    adapter_args = route.translate(
        _parse(
            "event",
            "26CAP-00000-006GM",
            "--source",
            source_id,
            "--jurisdiction",
            "41029",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "record"
    assert adapter_args.module == expected_module
    assert adapter_args.cap_key == "26CAP-00000-006GM"
    guidance = query_property._source_guidance(source_id)
    assert guidance["unified_operations"] == ["event"]
    assert guidance["record_kind"].endswith("_permit_detail")


@pytest.mark.parametrize(
    (
        "source_id",
        "operation",
        "selector",
        "expected_command",
        "expected_field",
        "expected_geometry",
    ),
    [
        (
            query_property.query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID,
            "owner",
            "US DEPT OF INTERIOR",
            "search",
            "owner",
            False,
        ),
        (
            query_property.query_oregon_lane_marion_parcels.LANE_PARCELS_SOURCE_ID,
            "map",
            "1501000000100",
            "parcel",
            "parcel",
            True,
        ),
        (
            query_property.query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID,
            "instrument",
            "2024-019914",
            "sale",
            "instrument",
            False,
        ),
        (
            query_property.query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID,
            "parcel",
            "1605070001100",
            "search",
            "parcel",
            False,
        ),
        (
            query_property.query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID,
            "account",
            "510174",
            "search",
            "account",
            False,
        ),
        (
            query_property.query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID,
            "instrument",
            "35450047",
            "search",
            "instrument",
            False,
        ),
    ],
)
def test_oregon_lane_marion_routes_preserve_component_and_selector(
    source_id,
    operation,
    selector,
    expected_command,
    expected_field,
    expected_geometry,
) -> None:
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--jurisdiction",
            (
                "41047"
                if source_id
                == query_property.query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID
                else "41039"
            ),
            "--limit",
            "9",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.source == source_id
    assert adapter_args.query == selector
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is expected_geometry
    assert adapter_args.limit == 9


def test_oregon_lane_marion_routes_validate_county_context() -> None:
    source_id = query_property.query_oregon_lane_marion_parcels.MARION_PARCELS_SOURCE_ID
    route = query_property.LIVE_ROUTES[source_id]["owner"]

    with pytest.raises(ValueError, match="county GEOID 41047"):
        route.translate(
            _parse(
                "owner",
                "KCK PARTNERS",
                "--source",
                source_id,
                "--jurisdiction",
                "41039",
            ),
            route.adapter_command,
        )


def test_oregon_lane_marion_guidance_keeps_complements_distinct() -> None:
    guidance = query_property._source_guidance(
        query_property.query_oregon_lane_marion_parcels.LANE_SALES_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert "query_oregon_lane_marion_parcels.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == [
        "account",
        "address",
        "instrument",
        "map",
        "parcel",
        "search",
    ]
    assert "separate components" in guidance["note"]
    assert "annual sales downloads" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "selector", "field"),
    (
        ("search", "SMITH 123 MAIN", "query"),
        ("owner", "SMITH", "owner"),
        ("address", "123 MAIN ST", "address"),
        ("parcel", "0234101023000", "parcel"),
        ("account", "0234101023000", "parcel"),
    ),
)
def test_denver_delinquent_tax_routes_preserve_selector_and_caller_limit(
    operation,
    selector,
    field,
):
    route = query_property.LIVE_ROUTES[query_property.DENVER_DELINQUENT_TAX_SOURCE_ID][
        operation
    ]
    uncapped = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            query_property.DENVER_DELINQUENT_TAX_SOURCE_ID,
            "--tax-year",
            "2024",
        ),
        route.adapter_command,
    )
    bounded = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            query_property.DENVER_DELINQUENT_TAX_SOURCE_ID,
            "--limit",
            "7",
            "--max-records",
            "5",
        ),
        route.adapter_command,
    )

    assert uncapped.command == "search"
    assert uncapped.artifact is None
    assert getattr(uncapped, field) == selector
    assert uncapped.tax_year == 2024
    assert uncapped.max_records is None
    assert bounded.max_records == 5


@pytest.mark.parametrize(
    ("operation", "selector", "field"),
    (
        ("search", "2026-000418", "foreclosure_number"),
        ("owner", "EXAMPLE OWNER", "owner"),
        ("address", "123 MAIN ST", "street"),
    ),
)
def test_denver_foreclosure_routes_preserve_selector_without_hidden_cap(
    operation,
    selector,
    field,
):
    route = query_property.LIVE_ROUTES[query_property.DENVER_FORECLOSURE_SOURCE_ID][
        operation
    ]
    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            query_property.DENVER_FORECLOSURE_SOURCE_ID,
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "search"
    assert getattr(adapter_args, field) == selector
    assert adapter_args.limit is None
    assert adapter_args.show_all is False


def test_los_angeles_ttc_routes_preserve_component_semantics_without_default_cap():
    assessor = query_property.LIVE_ROUTES[
        query_property.LOS_ANGELES_ASSESSOR_SOURCE_ID
    ]["parcel"]
    assessor_args = assessor.translate(
        _parse(
            "parcel",
            "2004-001-003",
            "--source",
            query_property.LOS_ANGELES_ASSESSOR_SOURCE_ID,
            "--jurisdiction",
            "06037",
        ),
        assessor.adapter_command,
    )
    assert assessor_args.command == "route"
    assert assessor_args.ain == "2004-001-003"

    payment = query_property.LIVE_ROUTES[
        query_property.LOS_ANGELES_TTC_PAYMENT_SOURCE_ID
    ]["account"]
    exhaustive = payment.translate(
        _parse(
            "account",
            "2004001003",
            "--source",
            query_property.LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
        ),
        payment.adapter_command,
    )
    bounded = payment.translate(
        _parse(
            "account",
            "2004001003",
            "--source",
            query_property.LOS_ANGELES_TTC_PAYMENT_SOURCE_ID,
            "--limit",
            "2",
            "--cursor",
            "la-ttc:history:2004001003:page:3",
        ),
        payment.adapter_command,
    )
    assert exhaustive.command == "history"
    assert exhaustive.max_pages is None
    assert bounded.max_pages == 2
    assert bounded.cursor == "la-ttc:history:2004001003:page:3"

    sale = query_property.LIVE_ROUTES[query_property.LOS_ANGELES_TTC_SALE_SOURCE_ID][
        "sale"
    ]
    sale_args = sale.translate(
        _parse(
            "sale",
            "2025B",
            "--source",
            query_property.LOS_ANGELES_TTC_SALE_SOURCE_ID,
            "--max-records",
            "7",
        ),
        sale.adapter_command,
    )
    assert sale_args.command == "sale-results"
    assert sale_args.cycle == "2025B"
    assert sale_args.limit == 7

    publication = query_property.LIVE_ROUTES[
        query_property.LOS_ANGELES_TTC_SALE_SOURCE_ID
    ]["search"]
    publication_args = publication.translate(
        _parse(
            "search",
            "2025B",
            "--source",
            query_property.LOS_ANGELES_TTC_SALE_SOURCE_ID,
            "--process-stage",
            "sale-results",
        ),
        publication.adapter_command,
    )
    assert publication_args.command == "publications"
    assert publication_args.cycle == "2025B"
    assert publication_args.kind == "sale_results_excess_proceeds"


def test_los_angeles_ttc_guidance_exposes_alternate_official_routes():
    payment = query_property._source_guidance(
        query_property.LOS_ANGELES_TTC_PAYMENT_SOURCE_ID
    )
    sale = query_property._source_guidance(
        query_property.LOS_ANGELES_TTC_SALE_SOURCE_ID
    )

    assert payment["unified_operations"] == ["account", "parcel"]
    assert {item["name"] for item in payment["official_complements"]} == {
        "Annual Secured Property Tax Bill",
        "View or request a property tax bill",
        "Secured Property Tax Information Request",
    }
    assert sale["unified_operations"] == ["event", "probe", "sale", "search"]
    assert sale["official_complements"][0]["url"] == (
        query_los_angeles_ttc.AUCTION_NOTICE_URL
    )


def test_denver_delinquent_tax_ingest_projects_parcel_owner_and_tax_event(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "property.db"
    source_query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=query_property.DENVER_DELINQUENT_TAX_SOURCE_ID,
            name="Denver Delinquent Real Property Tax List",
            source_role="property_tax_delinquency_bulk",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="08031",
            name="City and County of Denver, Colorado",
            state_code="CO",
            county_fips="08031",
        ),
        query=QueryMetadata(
            operation="search",
            parameters={"parcel": "0234101023000"},
        ),
    )
    record = {
        "source_id": query_property.DENVER_DELINQUENT_TAX_SOURCE_ID,
        "record_kind": "property_tax_delinquency",
        "native_parcel_id": "0234101023000",
        "native_account_id": "0234101023000",
        "stable_account_key": "2024:0234101023000",
        "tax_year": 2024,
        "evidence_ref": "DENVER-TAX:2024:0234101023000",
        "owners": [
            {"raw_name": "EXAMPLE OWNER"},
            {"raw_name": "EXAMPLE CO-OWNER"},
        ],
        "situs_address": {
            "raw": "123 MAIN ST",
            "city": "Denver",
            "state": "CO",
        },
        "release_date": "2025-08-28",
        "delinquency_status": "delinquent_as_published",
        "amounts": {
            "total_due": 123.45,
            "tax": 100,
            "interest": 20,
            "fees": 3.45,
            "currency": "USD",
        },
        "valuation": {
            "parcel_valuation": 250_000,
            "currency": "USD",
        },
        "tax_sale_indicator": {
            "raw": "TS",
            "marked": True,
            "status": "prior_tax_sale_unredeemed",
        },
        "partial_payment_indicator": {
            "raw": None,
            "marked": False,
            "status": "not_indicated",
        },
        "release_scope_categories": ["general_real_estate_tax"],
        "publication_page": "https://example.test/denver-tax",
        "artifact_sha256": "a" * 64,
        "adapter_schema_fingerprint": "b" * 64,
    }
    envelope = PublicRecordsResult.success(
        source_query,
        [record],
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    assert first["records_ingested"] == 1
    assert first["projection_supported"] is True
    assert second["records_ingested"] == 1
    db = connect_property(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM parcel_address").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM assessment").fetchone()[0] == 1
        event = db.execute(
            """
            SELECT event_type, amount_minor, status, native_event_id
            FROM tax_account_event
            """
        ).fetchone()
        assert dict(event) == {
            "event_type": "delinquency_publication",
            "amount_minor": 12_345,
            "status": "delinquent_as_published",
            "native_event_id": "2024:0234101023000",
        }
    finally:
        db.close()

    monkeypatch.setattr(query_property, "log_search", lambda *args: None)
    local = query_property.execute(
        _parse(
            "parcel",
            "0234101023000",
            "--jurisdiction",
            "08031",
            "--tax-year",
            "2024",
            "--property-db",
            str(db_path),
        )
    )
    assert local["status"] == "ok"
    assert local["records"][0]["tax_events"][0]["amount_minor"] == 12_345


def test_harris_foreclosure_unified_lookup_has_no_default_caller_cap():
    route = query_property.LIVE_ROUTES[query_property.HARRIS_FORECLOSURE_SOURCE_ID][
        "search"
    ]
    adapter_args = route.translate(
        _parse(
            "search",
            "FRCL-2026-4797",
            "--source",
            query_property.HARRIS_FORECLOSURE_SOURCE_ID,
        ),
        route.adapter_command,
    )

    assert adapter_args.document_id == "FRCL-2026-4797"
    assert adapter_args.limit is None


def test_nc_live_route_uses_catalog_decision_and_can_ingest(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.db"
    property_path = tmp_path / "property.db"
    seed_catalog(db_path=catalog_path)
    calls = []
    monkeypatch.setattr(
        query_property.query_nc_property,
        "execute",
        lambda args, **kwargs: calls.append((args, kwargs)) or _live_envelope(),
    )

    payload = query_property.execute(
        _parse(
            "parcel",
            "3013467134",
            "--source",
            "us-nc-onemap-parcels",
            "--county-fips",
            "005",
            "--catalog-db",
            str(catalog_path),
            "--property-db",
            str(property_path),
            "--ingest",
        )
    )

    assert payload["status"] == "ok"
    assert calls[0][0].county_fips == "005"
    assert calls[0][1]["access_decision"]["allowed"] is True
    assert payload["ingest"]["records_ingested"] == 1
    db = connect_property(property_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
    finally:
        db.close()


def test_non_nc_live_route_uses_adapter_neutral_ingester(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[query_property.MD_SOURCE_ID]["parcel"]
    ingested = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda _args, **_kwargs: _adapter_envelope(
            query_property.MD_SOURCE_ID, "parcel"
        ),
    )
    monkeypatch.setattr(
        query_property,
        "ingest_property_envelope",
        lambda envelope, **kwargs: (
            ingested.append((envelope, kwargs))
            or {"status": "ok", "records_ingested": 0}
        ),
    )

    payload = query_property.execute(
        _parse(
            "parcel",
            "04030311078580",
            "--source",
            query_property.MD_SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
            "--property-db",
            str(tmp_path / "property.db"),
            "--ingest",
        )
    )

    assert payload["ingest"]["status"] == "ok"
    assert ingested[0][0]["query"]["source"]["source_id"] == (
        query_property.MD_SOURCE_ID
    )


def test_orleans_live_route_preserves_ingest_and_catalog_decision(
    tmp_path, monkeypatch
):
    catalog_path = tmp_path / "catalog.db"
    property_path = tmp_path / "property.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[query_property.ORLEANS_SOURCE_ID]["parcel"]
    dispatched = []
    ingested = []

    def fake_execute(adapter_args, *, access_decision):
        dispatched.append((adapter_args, access_decision))
        return _adapter_envelope(
            query_property.ORLEANS_SOURCE_ID,
            "parcel",
        )

    monkeypatch.setattr(route.adapter, "execute", fake_execute)
    monkeypatch.setattr(
        query_property,
        "ingest_property_envelope",
        lambda envelope, **kwargs: (
            ingested.append((envelope, kwargs))
            or {"status": "ok", "records_ingested": 0}
        ),
    )

    payload = query_property.execute(
        _parse(
            "parcel",
            "412100101",
            "--source",
            query_property.ORLEANS_SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
            "--property-db",
            str(property_path),
            "--geometry",
            "--ingest",
        )
    )

    adapter_args, decision = dispatched[0]
    assert decision["allowed"] is True
    assert decision["source_id"] == query_property.ORLEANS_SOURCE_ID
    assert adapter_args.query == "412100101"
    assert adapter_args.geometry is True
    assert payload["ingest"]["status"] == "ok"
    assert ingested[0][0]["query"]["source"]["source_id"] == (
        query_property.ORLEANS_SOURCE_ID
    )
    assert ingested[0][1]["db_path"] == str(property_path)


def test_account_operation_requires_source_when_multiple_routes_exist(
    tmp_path,
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    payload = query_property.execute(
        _parse(
            "account",
            "615199817",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "human_required"
    assert payload["query"]["source"]["source_id"] == (query_property.CATALOG_SOURCE_ID)
    assert payload["errors"][0]["code"] == "source_selection_required"
    compatible = payload["errors"][0]["details"]["compatible_sources"]
    compatible_source_ids = {item["source_id"] for item in compatible}
    account_route_source_ids = {
        source_id
        for source_id, operations in query_property.LIVE_ROUTES.items()
        if "account" in operations
    }
    assert compatible_source_ids == account_route_source_ids
    assert {
        query_property.DENVER_DELINQUENT_TAX_SOURCE_ID,
        query_property.ORLEANS_SOURCE_ID,
        *query_property.OREGON_TAXLOT_SOURCE_IDS,
    }.issubset(compatible_source_ids)


def test_orleans_catalog_decision_precedes_adapter_dispatch(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    route = query_property.LIVE_ROUTES[query_property.ORLEANS_SOURCE_ID]["owner"]

    def unexpected_dispatch(*_args, **_kwargs):
        raise AssertionError("adapter was called before catalog readiness")

    monkeypatch.setattr(route.adapter, "execute", unexpected_dispatch)
    monkeypatch.setattr(
        query_property.PublicRecordsCatalog,
        "machine_acquisition_decision",
        lambda _catalog, source_id: {
            "source_id": source_id,
            "allowed": False,
            "reason_code": "access_review_required",
            "reason": "latest source review is unavailable",
            "access_class": "B",
            "automation_disposition": "unclear",
        },
    )

    payload = query_property.execute(
        _parse(
            "owner",
            "EXAMPLE HOLDINGS LLC",
            "--source",
            query_property.ORLEANS_SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "unavailable"
    assert payload["errors"][0]["code"] == "access_review_required"


def test_bulk_source_surfaces_adapter_status_and_direct_tool_guidance(
    tmp_path, monkeypatch
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    logged = []
    monkeypatch.setattr(query_property, "log_search", lambda *args: logged.append(args))

    payload = query_property.execute(
        _parse(
            "parcel",
            "123",
            "--source",
            "us-fl-dor-property-roll",
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "unavailable"
    assert payload["records"] == []
    assert payload["errors"][0]["code"] == "capability_not_supported"
    guidance = payload["errors"][0]["details"]["source_guidance"]
    assert guidance["mode"] == "unified_bulk_release"
    assert "query_fl_dor_property.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == [
        "discovery",
        "download",
        "manifest",
        "probe",
        "releases",
    ]
    assert logged[0][2] is None


@pytest.mark.parametrize(
    ("source_id", "operation", "expected_operations"),
    [
        (query_property.COOK_SOURCE_ID, "owner", ["parcel"]),
        (
            query_property.ACRIS_SOURCE_ID,
            "address",
            ["chain", "instrument", "owner", "parcel"],
        ),
    ],
)
def test_supported_adapter_distinguishes_unsupported_capability(
    tmp_path,
    monkeypatch,
    source_id,
    operation,
    expected_operations,
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    monkeypatch.setattr(query_property, "log_search", lambda *args: None)

    payload = query_property.execute(
        _parse(
            operation,
            "SMITH",
            "--source",
            source_id,
            "--catalog-db",
            str(catalog_path),
        )
    )

    assert payload["status"] == "unavailable"
    assert payload["errors"][0]["code"] == "capability_not_supported"
    guidance = payload["errors"][0]["details"]["source_guidance"]
    assert guidance["unified_operations"] == expected_operations


def test_sources_and_direct_cli_are_discoverable(tmp_path):
    import subprocess
    import sys

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    payload = query_property.execute(
        _parse("sources", "--catalog-db", str(catalog_path))
    )
    assert payload["status"] == "ok"
    assert {record["source_id"] for record in payload["records"]} >= {
        "us-nc-onemap-parcels",
        "us-nyc-acris",
    }
    by_source = {record["source_id"]: record for record in payload["records"]}
    assert by_source[query_property.FL_SOURCE_ID]["query_guidance"]["mode"] == (
        "unified_bulk_release"
    )
    assert (
        "query_fl_dor_property.py"
        in by_source[query_property.FL_SOURCE_ID]["query_guidance"]["direct_tool"]
    )
    assert (
        by_source[query_property.MASSGIS_SOURCE_ID]["query_guidance"][
            "unified_operations"
        ]
        == []
    )
    assert (
        by_source[query_property.HARRIS_SOURCE_ID]["query_guidance"]["mode"]
        == "unified_bulk_release"
    )
    assert (
        "query_harris_property.py"
        in by_source[query_property.HARRIS_SOURCE_ID]["query_guidance"]["direct_tool"]
    )
    assert by_source[query_property.HARRIS_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == [
        "discovery",
        "download",
        "manifest",
        "probe",
        "releases",
    ]
    assert (
        "ingest_hcad_property.py"
        in by_source[query_property.HARRIS_SOURCE_ID]["query_guidance"][
            "archive_ingest"
        ]
    )
    assert (
        by_source[query_property.ACRIS_IMAGES_SOURCE_ID]["query_guidance"]["mode"]
        == "action_planning"
    )
    assert (
        "public_records_actions.py"
        in by_source[query_property.ACRIS_IMAGES_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.ACRIS_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["chain", "instrument", "owner", "parcel"]
    assert by_source[query_property.BEXAR_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["address", "map", "owner", "parcel"]
    assert (
        "query_bexar_property.py"
        in by_source[query_property.BEXAR_SOURCE_ID]["query_guidance"]["direct_tool"]
    )
    assert by_source[query_property.DENVER_PROPERTY_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["address", "map", "owner", "parcel"]
    assert (
        "query_denver_property.py"
        in by_source[query_property.DENVER_PROPERTY_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.DELAWARE_FIRSTMAP_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["map", "parcel"]
    assert (
        "query_delaware_firstmap.py"
        in by_source[query_property.DELAWARE_FIRSTMAP_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.ARLINGTON_PROPERTY_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["address", "map", "parcel"]
    assert (
        "query_arlington_property.py"
        in by_source[query_property.ARLINGTON_PROPERTY_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.MIAMI_DADE_PA_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["address", "map", "owner", "parcel"]
    assert (
        "query_miami_dade_property.py"
        in by_source[query_property.MIAMI_DADE_PA_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert (
        by_source[query_property.MIAMI_DADE_RECORDER_PUBLIC_SOURCE_ID][
            "query_guidance"
        ]["mode"]
        == "direct_live_enrichment"
    )
    assert (
        "query_miami_dade_recorder.py"
        in by_source[query_property.MIAMI_DADE_RECORDER_PUBLIC_SOURCE_ID][
            "query_guidance"
        ]["direct_tool"]
    )
    assert (
        by_source[query_property.MIAMI_DADE_RECORDER_SOURCE_ID]["query_guidance"][
            "mode"
        ]
        == "credentialed_api_and_bulk_actions"
    )
    assert by_source[query_property.ORLEANS_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == [
        "account",
        "address",
        "map",
        "owner",
        "parcel",
        "search",
    ]
    assert (
        "query_orleans_property.py"
        in by_source[query_property.ORLEANS_SOURCE_ID]["query_guidance"]["direct_tool"]
    )
    assert by_source[query_property.DESCHUTES_PROPERTY_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == [
        "account",
        "address",
        "map",
        "owner",
        "parcel",
        "search",
    ]
    assert (
        "query_deschutes_property.py"
        in by_source[query_property.DESCHUTES_PROPERTY_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.DESCHUTES_DIAL_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == [
        "account",
        "address",
        "mobile-park",
        "owner",
        "parcel",
        "search",
        "subdivision",
    ]
    assert (
        "query_deschutes_dial.py"
        in by_source[query_property.DESCHUTES_DIAL_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.DESCHUTES_CDD_WEBLINK_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["account"]
    assert (
        "query_deschutes_laserfiche.py"
        in by_source[query_property.DESCHUTES_CDD_WEBLINK_SOURCE_ID]["query_guidance"][
            "direct_tool"
        ]
    )
    assert by_source[query_property.REEVES_SOURCE_ID]["query_guidance"][
        "unified_operations"
    ] == ["instrument", "owner", "search"]
    assert (
        "query_reeves_records.py"
        in by_source[query_property.REEVES_SOURCE_ID]["query_guidance"]["direct_tool"]
    )
    govos_source = "us-pa-berks-recorder-publicsearch"
    assert by_source[govos_source]["query_guidance"]["unified_operations"] == [
        "instrument",
        "owner",
        "search",
    ]
    assert (
        "query_govos_recorders.py"
        in by_source[govos_source]["query_guidance"]["direct_tool"]
    )

    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/query_property.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "owner" in result.stdout
    assert "account" in result.stdout
    assert "chain" in result.stdout
    assert "mobile-park" in result.stdout
    assert "search" in result.stdout
    assert "subdivision" in result.stdout

    parcel_help = subprocess.run(
        [sys.executable, "tools/query_property.py", "parcel", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert parcel_help.returncode == 0, parcel_help.stderr
    assert "--county-code" in parcel_help.stdout
    assert "live pilot" not in parcel_help.stdout


@pytest.mark.parametrize(
    ("operation", "selector", "search_field", "expected_field", "geometry"),
    [
        ("search", "SMITH", None, "auto", False),
        ("owner", "SMITH", None, "owner", False),
        ("address", "MAIN", None, "address", False),
        ("account", "12345", None, "account", False),
        ("parcel", "12-34-56", None, "map_taxlot", False),
        ("parcel", "12345", "account", "account", False),
        ("parcel", "410030001234", "or-taxlot", "or_taxlot", False),
        ("map", "1234", "map-number", "map_number", True),
    ],
)
def test_benton_taxlot_routes_preserve_native_selector_and_geometry(
    operation,
    selector,
    search_field,
    expected_field,
    geometry,
):
    values = [
        operation,
        selector,
        "--source",
        query_property.OREGON_BENTON_TAXLOT_SOURCE_ID,
        "--jurisdiction",
        "41003",
    ]
    if search_field is not None:
        values.extend(["--search-field", search_field])
    route = query_property.LIVE_ROUTES[query_property.OREGON_BENTON_TAXLOT_SOURCE_ID][
        operation
    ]
    adapter_args = route.translate(
        _parse(*values),
        route.adapter_command,
    )

    assert adapter_args.command == route.adapter_command
    assert adapter_args.query == selector
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is geometry


def test_benton_bulk_and_map_routes_preserve_component_artifact_states():
    bulk_search_route = query_property.LIVE_ROUTES[
        query_property.OREGON_BENTON_BULK_SOURCE_ID
    ]["search"]
    bulk_search = bulk_search_route.translate(
        _parse(
            "search",
            "*",
            "--source",
            query_property.OREGON_BENTON_BULK_SOURCE_ID,
        ),
        bulk_search_route.adapter_command,
    )
    bulk_artifact_route = query_property.LIVE_ROUTES[
        query_property.OREGON_BENTON_BULK_SOURCE_ID
    ]["instrument"]
    bulk_artifact = bulk_artifact_route.translate(
        _parse(
            "instrument",
            "TaxlotOwners.zip",
            "--source",
            query_property.OREGON_BENTON_BULK_SOURCE_ID,
        ),
        bulk_artifact_route.adapter_command,
    )
    map_list_route = query_property.LIVE_ROUTES[
        query_property.OREGON_BENTON_MAP_SOURCE_ID
    ]["parcel"]
    map_list = map_list_route.translate(
        _parse(
            "parcel",
            "11520",
            "--source",
            query_property.OREGON_BENTON_MAP_SOURCE_ID,
            "--search-field",
            "prefix",
        ),
        map_list_route.adapter_command,
    )
    map_artifact_route = query_property.LIVE_ROUTES[
        query_property.OREGON_BENTON_MAP_SOURCE_ID
    ]["instrument"]
    map_artifact = map_artifact_route.translate(
        _parse(
            "instrument",
            "11520.pdf",
            "--source",
            query_property.OREGON_BENTON_MAP_SOURCE_ID,
        ),
        map_artifact_route.adapter_command,
    )

    assert bulk_search.command == "bulk-manifest"
    assert bulk_artifact.command == "artifact-probe"
    assert bulk_artifact.component == "bulk"
    assert bulk_artifact.artifact == "TaxlotOwners.zip"
    assert map_list.command == "maps"
    assert map_list.map_number == "11520"
    assert map_list.match == "prefix"
    assert map_artifact.command == "artifact-probe"
    assert map_artifact.component == "map"
    assert map_artifact.artifact == "11520.pdf"

    taxlot_guidance = query_property.DIRECT_TOOL_GUIDANCE[
        query_property.OREGON_BENTON_TAXLOT_SOURCE_ID
    ]
    assert taxlot_guidance["native_search_fields"] == [
        "owner",
        "address",
        "account",
        "map_taxlot",
        "or_taxlot",
        "map_number",
    ]
    assert {item["source_id"] for item in taxlot_guidance["official_complements"]} >= {
        query_property.query_oregon_benton_property.HELION_SOURCE_ID,
        query_property.query_oregon_benton_property.ACCOUNT_API_SOURCE_ID,
        query_property.OREGON_BENTON_BULK_SOURCE_ID,
        query_property.OREGON_BENTON_MAP_SOURCE_ID,
    }


@pytest.mark.parametrize(
    "operation",
    ("search", "owner", "address", "parcel", "account"),
)
def test_lincoln_propertyweb_routes_preserve_account_search_context(operation):
    route = query_property.LIVE_ROUTES[
        query_property.OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID
    ][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "R452940",
            "--source",
            query_property.OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID,
            "--jurisdiction",
            "41041",
            "--tax-year",
            "2026",
            "--limit",
            "7",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == "search"
    assert adapter_args.term == "R452940"
    assert adapter_args.tax_year == 2026
    assert adapter_args.property_value_tax_year == 2026
    assert adapter_args.limit == 7
    assert adapter_args.property_types == (
        query_property.query_oregon_lincoln_propertyweb.DEFAULT_PROPERTY_TYPES
    )


@pytest.mark.parametrize(
    ("operation", "search_field", "expected_field", "geometry"),
    (
        ("search", None, "all", False),
        ("owner", None, "owner", False),
        ("address", None, "address", False),
        ("account", None, "property", False),
        ("parcel", None, "parcel", False),
        ("parcel", "property", "property", False),
        ("map", None, "parcel", True),
    ),
)
def test_lincoln_wfs_routes_preserve_selector_and_geometry(
    operation,
    search_field,
    expected_field,
    geometry,
):
    values = [
        operation,
        "07-11-03-DC-05800-00",
        "--source",
        query_property.OREGON_LINCOLN_TAXLOT_SOURCE_ID,
        "--jurisdiction",
        "41041",
    ]
    if search_field:
        values.extend(["--search-field", search_field])
    route = query_property.LIVE_ROUTES[query_property.OREGON_LINCOLN_TAXLOT_SOURCE_ID][
        operation
    ]
    adapter_args = route.translate(
        _parse(*values),
        route.adapter_command,
    )

    assert adapter_args.command == "search"
    assert adapter_args.query == "07-11-03-DC-05800-00"
    assert adapter_args.field == expected_field
    assert adapter_args.match == "auto"
    assert adapter_args.geometry is geometry


def test_lincoln_sources_expose_distinct_shared_guidance_and_join_keys():
    propertyweb = query_property.DIRECT_TOOL_GUIDANCE[
        query_property.OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID
    ]
    taxlots = query_property.DIRECT_TOOL_GUIDANCE[
        query_property.OREGON_LINCOLN_TAXLOT_SOURCE_ID
    ]

    assert propertyweb["direct_tool"].endswith(
        "tools/query_oregon_lincoln_propertyweb.py --help"
    )
    assert {item["source_id"] for item in propertyweb["official_complements"]} == {
        query_property.OREGON_LINCOLN_TAXLOT_SOURCE_ID,
        "us-or-lincoln-helion-recorder",
    }
    assert taxlots["native_search_fields"] == [
        "address",
        "all",
        "owner",
        "parcel",
        "property",
    ]
    assert {item["source_id"] for item in taxlots["official_complements"]} == {
        query_property.OREGON_LINCOLN_PROPERTYWEB_SOURCE_ID,
        "us-or-lincoln-helion-recorder",
        "us-or-owrd-public-tax-lots",
        "us-or-ormap-cadastral-routing",
    }
    assert "CRS" in taxlots["note"]


@pytest.mark.parametrize(
    ("source_id", "operation", "expected_command", "expected_field", "geometry"),
    (
        (
            query_property.query_oregon_yamhill_property.ASCEND_SOURCE_ID,
            "account",
            "detail",
            "account",
            False,
        ),
        (
            query_property.query_oregon_yamhill_property.ASCEND_SOURCE_ID,
            "parcel",
            "search",
            "alternate",
            False,
        ),
        (
            query_property.query_oregon_yamhill_property.TAXLOT_SOURCE_ID,
            "owner",
            "search",
            "owner",
            False,
        ),
        (
            query_property.query_oregon_yamhill_property.PERMIT_SOURCE_ID,
            "event",
            "search",
            "native_id",
            False,
        ),
        (
            query_property.query_oregon_yamhill_property.RETIRED_SOURCE_ID,
            "map",
            "search",
            "map_taxlot",
            True,
        ),
    ),
)
def test_yamhill_routes_keep_component_native_fields(
    source_id,
    operation,
    expected_command,
    expected_field,
    geometry,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "R3218AB 00301",
            "--source",
            source_id,
            "--jurisdiction",
            "41071",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.source == source_id
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is geometry


@pytest.mark.parametrize(
    ("source_id", "operation", "expected_command", "expected_field", "geometry"),
    (
        (
            query_property.query_oregon_clackamas_property.ASCEND_SOURCE_ID,
            "account",
            "detail",
            "account",
            False,
        ),
        (
            query_property.query_oregon_clackamas_property.CMAP_SOURCE_ID,
            "instrument",
            "search",
            "recording",
            False,
        ),
        (
            query_property.query_oregon_clackamas_property.CMAP_SOURCE_ID,
            "map",
            "search",
            "map_taxlot",
            True,
        ),
    ),
)
def test_clackamas_routes_keep_ascend_and_cmap_distinct(
    source_id,
    operation,
    expected_command,
    expected_field,
    geometry,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "01092276",
            "--source",
            source_id,
            "--jurisdiction",
            "41005",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.source == source_id
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is geometry


@pytest.mark.parametrize(
    ("source_id", "operation", "expected_command", "expected_field", "geometry"),
    (
        (
            query_property.query_oregon_wasco_property.ASCEND_SOURCE_ID,
            "account",
            "detail",
            "account",
            False,
        ),
        (
            query_property.query_oregon_wasco_property.TAXLOT_SOURCE_ID,
            "owner",
            "search",
            "owner",
            False,
        ),
        (
            query_property.query_oregon_wasco_property.LAND_CORNERS_SOURCE_ID,
            "instrument",
            "search",
            "auto",
            False,
        ),
        (
            query_property.query_oregon_wasco_property.SURVEY_BOOK_SOURCE_ID,
            "map",
            "search",
            "auto",
            True,
        ),
    ),
)
def test_wasco_routes_keep_account_taxlot_and_survey_contracts(
    source_id,
    operation,
    expected_command,
    expected_field,
    geometry,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "LC 179",
            "--source",
            source_id,
            "--jurisdiction",
            "41065",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    assert adapter_args.source == source_id
    assert adapter_args.field == expected_field
    assert adapter_args.geometry is geometry


@pytest.mark.parametrize(
    (
        "source_id",
        "operation",
        "expected_command",
        "expected_kind_or_layer",
        "expected_field",
        "geometry",
    ),
    (
        (
            query_property.query_oregon_washington_property.SURVEY_API_SOURCE_ID,
            "search",
            "survey-search",
            "survey",
            "surveynumber",
            None,
        ),
        (
            query_property.query_oregon_washington_property.SURVEY_API_SOURCE_ID,
            "instrument",
            "survey-search",
            "plat",
            "docnumber",
            None,
        ),
        (
            query_property.query_oregon_washington_property.SURVEY_API_SOURCE_ID,
            "parcel",
            "survey-detail",
            "taxlot",
            None,
            None,
        ),
        (
            query_property.query_oregon_washington_property.SURVEY_MAP_SOURCE_ID,
            "map",
            "arcgis",
            "survey-taxlots",
            "TLID",
            True,
        ),
        (
            query_property.query_oregon_washington_property.TAXLOT_SOURCE_ID,
            "parcel",
            "taxlots",
            None,
            "TLNO",
            False,
        ),
        (
            query_property.query_oregon_washington_property.SITUS_SOURCE_ID,
            "address",
            "situs",
            None,
            "FULLADDRESS",
            False,
        ),
        (
            query_property.query_oregon_washington_property.INTERMAP_SOURCE_ID,
            "map",
            "intermap",
            None,
            None,
            None,
        ),
        (
            query_property.query_oregon_washington_property.TAX_SOURCE_ID,
            "account",
            "tax-account",
            None,
            None,
            None,
        ),
    ),
)
def test_washington_routes_preserve_component_operations(
    source_id,
    operation,
    expected_command,
    expected_kind_or_layer,
    expected_field,
    geometry,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "2N2330002700",
            "--source",
            source_id,
            "--jurisdiction",
            "41067",
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    if expected_command.startswith("survey-"):
        assert adapter_args.kind == expected_kind_or_layer
    elif expected_command == "arcgis":
        assert adapter_args.layer == expected_kind_or_layer
    if expected_field is not None:
        assert adapter_args.field == expected_field
    if geometry is not None:
        assert adapter_args.geometry is geometry
    if source_id == query_property.query_oregon_washington_property.INTERMAP_SOURCE_ID:
        assert adapter_args.report == "tax-map"
    if source_id == query_property.query_oregon_washington_property.TAX_SOURCE_ID:
        assert adapter_args.account == "2N2330002700"


def test_washington_routes_do_not_claim_unimplemented_selector_families():
    adapter = query_property.query_oregon_washington_property

    assert set(query_property.LIVE_ROUTES[adapter.SURVEY_API_SOURCE_ID]) == {
        "search",
        "parcel",
        "instrument",
    }
    assert set(query_property.LIVE_ROUTES[adapter.SURVEY_MAP_SOURCE_ID]) == {
        "search",
        "parcel",
        "map",
    }
    assert set(query_property.LIVE_ROUTES[adapter.TAXLOT_SOURCE_ID]) == {
        "search",
        "parcel",
        "map",
    }
    assert set(query_property.LIVE_ROUTES[adapter.SITUS_SOURCE_ID]) == {
        "search",
        "address",
        "parcel",
        "account",
        "map",
    }
    assert set(query_property.LIVE_ROUTES[adapter.INTERMAP_SOURCE_ID]) == {
        "parcel",
        "map",
    }
    assert set(query_property.LIVE_ROUTES[adapter.TAX_SOURCE_ID]) == {"account"}
    assert all(
        "owner" not in query_property.LIVE_ROUTES[source_id]
        for source_id in adapter.SOURCES
    )


def test_washington_guidance_exposes_native_joins_and_alternative_routes():
    adapter = query_property.query_oregon_washington_property

    for source_id in adapter.SOURCES:
        guidance = query_property.DIRECT_TOOL_GUIDANCE[source_id]
        assert guidance["direct_tool"].endswith(
            "tools/query_oregon_washington_property.py --help"
        )
        assert guidance["native_capabilities"] == adapter._capabilities(source_id)
        assert guidance["native_joins"] == adapter._joins(source_id)
        assert {
            item.get("source_id") or item.get("name")
            for item in guidance["official_complements"]
        } >= {
            adapter.PORTLAND_REGIONAL_SOURCE_ID,
            "Washington County Recording and Copy Requests",
            "Washington County Assessment and Taxation Data Requests",
            "Washington County Accela Citizen Access",
            "Washington County Casefile Archives",
        }


@pytest.mark.parametrize(
    (
        "source_id",
        "operation",
        "selector",
        "extra_args",
        "expected_command",
        "expected_field",
    ),
    (
        (
            query_property.query_oregon_washington_case_permits.CASEFILE_SOURCE_ID,
            "search",
            "S2500112",
            ("--search-field", "submittal"),
            "case-search",
            "submittal",
        ),
        (
            query_property.query_oregon_washington_case_permits.CASEFILE_SOURCE_ID,
            "parcel",
            "2N2330002700",
            (),
            "case-search",
            "taxlot",
        ),
        (
            query_property.query_oregon_washington_case_permits.CASEFILE_SOURCE_ID,
            "event",
            "L2500106",
            (),
            "case-detail",
            None,
        ),
        (
            query_property.query_oregon_washington_case_permits.TAXLOT_ACTIVITY_SOURCE_ID,
            "parcel",
            "2N2330002700",
            (),
            "taxlot-activity",
            "all",
        ),
        (
            query_property.query_oregon_washington_case_permits.BUILDING_SOURCE_ID,
            "address",
            "MAIN",
            (),
            "building-search",
            "address",
        ),
        (
            query_property.query_oregon_washington_case_permits.BUILDING_SOURCE_ID,
            "event",
            "05214429",
            (),
            "building-search",
            "permit",
        ),
        (
            query_property.query_oregon_washington_case_permits.PERMIT_REPORT_SOURCE_ID,
            "event",
            "P0138681",
            (),
            "permit-report",
            "project",
        ),
        (
            query_property.query_oregon_washington_case_permits.PERMIT_REPORT_SOURCE_ID,
            "search",
            "05214429",
            ("--search-field", "review"),
            "permit-report",
            "review",
        ),
        (
            query_property.query_oregon_washington_case_permits.ACCELA_SOURCE_ID,
            "event",
            "L2500106",
            (),
            "accela-record",
            None,
        ),
        (
            query_property.query_oregon_washington_case_permits.DOCUMENT_ROUTE_SOURCE_ID,
            "event",
            "L2500106",
            (),
            "document-routes",
            None,
        ),
    ),
)
def test_washington_case_permit_routes_preserve_component_operations(
    source_id,
    operation,
    selector,
    extra_args,
    expected_command,
    expected_field,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            source_id,
            "--jurisdiction",
            "41067",
            *extra_args,
        ),
        route.adapter_command,
    )

    assert adapter_args.command == expected_command
    if expected_command in {"case-search", "building-search", "permit-report"}:
        assert adapter_args.kind == expected_field
    elif expected_command == "taxlot-activity":
        assert adapter_args.collection == expected_field
    elif expected_command in {
        "case-detail",
        "accela-record",
        "document-routes",
    }:
        assert adapter_args.casefile == selector


def test_washington_case_permit_routes_keep_challenges_and_supporting_routes_scoped():
    adapter = query_property.query_oregon_washington_case_permits

    assert set(query_property.LIVE_ROUTES[adapter.CASEFILE_SOURCE_ID]) == {
        "search",
        "parcel",
        "event",
    }
    assert set(query_property.LIVE_ROUTES[adapter.TAXLOT_ACTIVITY_SOURCE_ID]) == {
        "search",
        "parcel",
    }
    assert set(query_property.LIVE_ROUTES[adapter.BUILDING_SOURCE_ID]) == {
        "search",
        "address",
        "parcel",
        "event",
    }
    assert set(query_property.LIVE_ROUTES[adapter.PERMIT_REPORT_SOURCE_ID]) == {
        "search",
        "event",
    }
    assert set(query_property.LIVE_ROUTES[adapter.ACCELA_SOURCE_ID]) == {"event"}
    assert set(query_property.LIVE_ROUTES[adapter.DOCUMENT_ROUTE_SOURCE_ID]) == {
        "event"
    }

    building = query_property.DIRECT_TOOL_GUIDANCE[adapter.BUILDING_SOURCE_ID]
    assert building["operation_access"]["taxlot_search"] == "anonymous"
    assert (
        building["operation_access"]["permit_number_search"]
        == "source_challenge_observed"
    )
    casefiles = query_property.DIRECT_TOOL_GUIDANCE[adapter.CASEFILE_SOURCE_ID]
    assert casefiles["operation_access"]["case_search"] == "anonymous"
    assert {item["name"] for item in casefiles["official_complements"]} >= {
        "Notices of decision",
        "Public hearings and agendas",
        "CivicWeb land-use meeting packets",
        "Legacy Laserfiche casefile route",
        "Permit records and public request route",
    }
    assert casefiles["native_joins"]


@pytest.mark.parametrize(
    (
        "source_id",
        "operation",
        "expected_field",
        "geometry",
    ),
    (
        (
            query_property.query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID,
            "owner",
            "owner",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID,
            "address",
            "address",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID,
            "account",
            "account",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID,
            "parcel",
            "property-id",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID,
            "map",
            "map-taxlot",
            True,
        ),
        (
            query_property.query_oregon_multnomah_sail.TAX_PARCEL_SOURCE_ID,
            "instrument",
            "instrument",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.SURVEY_SOURCE_ID,
            "search",
            "auto",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.SUBDIVISION_SOURCE_ID,
            "instrument",
            "survey-id",
            False,
        ),
        (
            query_property.query_oregon_multnomah_sail.CORNER_SOURCE_ID,
            "map",
            "auto",
            True,
        ),
    ),
)
def test_multnomah_sail_routes_preserve_component_operations(
    source_id,
    operation,
    expected_field,
    geometry,
):
    route = query_property.LIVE_ROUTES[source_id][operation]
    adapter_args = route.translate(
        _parse(
            operation,
            "R330254",
            "--source",
            source_id,
            "--jurisdiction",
            "41051",
        ),
        route.adapter_command,
    )

    assert route.adapter is query_property.query_oregon_multnomah_sail
    assert adapter_args.command == "search"
    assert adapter_args.source == source_id
    assert adapter_args.field == expected_field
    assert adapter_args.match == "auto"
    assert adapter_args.geometry is geometry


def test_multnomah_sail_routes_are_operation_accurate():
    adapter = query_property.query_oregon_multnomah_sail

    assert set(query_property.LIVE_ROUTES[adapter.TAX_PARCEL_SOURCE_ID]) == {
        "search",
        "owner",
        "address",
        "account",
        "parcel",
        "map",
        "instrument",
    }
    for source_id in adapter.IMAGE_SOURCE_IDS:
        assert set(query_property.LIVE_ROUTES[source_id]) == {
            "search",
            "map",
            "instrument",
        }
        assert "owner" not in query_property.LIVE_ROUTES[source_id]
        assert "parcel" not in query_property.LIVE_ROUTES[source_id]


def test_multnomah_sail_guidance_preserves_documents_joins_and_complements():
    adapter = query_property.query_oregon_multnomah_sail

    for source_id in adapter.SOURCE_IDS:
        component = adapter.COMPONENTS[source_id]
        guidance = query_property.DIRECT_TOOL_GUIDANCE[source_id]
        assert guidance["direct_tool"].endswith(
            "tools/query_oregon_multnomah_sail.py --help"
        )
        assert {"search", "record"}.issubset(guidance["native_capabilities"])
        if component.image_capable:
            assert {"image", "download"}.issubset(guidance["native_capabilities"])
            assert guidance["native_joins"] == ["OBJECTID", "SURVEYID"]
        else:
            assert "download" not in guidance["native_capabilities"]
            assert guidance["native_joins"] == [
                "PROPID",
                "MAPTAXLOT",
                "ALTACCTNUM",
                "INST_NUM",
            ]
        assert {item["relationship"] for item in guidance["official_complements"]} >= {
            "current_property_account_detail",
            "recorded_instrument_index_and_copy_route",
            "standard_bulk_report_and_custom_request_route",
            "overlapping_regional_parcel_and_context_representation",
            "survey_record_and_additional_road_information_route",
        }


def test_new_oregon_component_guidance_points_to_direct_family_tools():
    expected = {
        **{
            source_id: "query_oregon_yamhill_property.py"
            for source_id in query_property.OREGON_YAMHILL_SOURCE_IDS
        },
        **{
            source_id: "query_oregon_clackamas_property.py"
            for source_id in query_property.OREGON_CLACKAMAS_SOURCE_IDS
        },
        **{
            source_id: "query_oregon_wasco_property.py"
            for source_id in query_property.OREGON_WASCO_SOURCE_IDS
        },
        **{
            source_id: "query_oregon_washington_property.py"
            for source_id in query_property.OREGON_WASHINGTON_SOURCE_IDS
        },
        **{
            source_id: "query_oregon_washington_case_permits.py"
            for source_id in (query_property.OREGON_WASHINGTON_CASE_PERMIT_SOURCE_IDS)
        },
        **{
            source_id: "query_oregon_multnomah_sail.py"
            for source_id in query_property.OREGON_MULTNOMAH_SAIL_SOURCE_IDS
        },
    }

    for source_id, tool_name in expected.items():
        assert source_id in query_property.LIVE_ROUTES
        assert (
            tool_name in query_property.DIRECT_TOOL_GUIDANCE[source_id]["direct_tool"]
        )


def test_washington_state_parcel_representation_routes_preserve_selectors():
    adapter = query_property.query_washington_parcels
    ecology_source = adapter.ECOLOGY_SOURCE_ID
    parcel_route = query_property.LIVE_ROUTES[ecology_source]["parcel"]
    parcel_args = parcel_route.translate(
        _parse(
            "parcel",
            adapter.SENTINEL_PARCEL_ID,
            "--source",
            ecology_source,
            "--jurisdiction",
            "53001",
            "--geometry",
            "--limit",
            "7",
        ),
        parcel_route.adapter_command,
    )

    assert parcel_args.command == "search"
    assert parcel_args.representation == "ecology"
    assert parcel_args.field == "parcel"
    assert parcel_args.county == "53001"
    assert parcel_args.geometry is True
    assert parcel_args.enrich is True
    assert parcel_args.limit == 7

    dnr_source = adapter.DNR_SOURCE_ID
    count_route = query_property.LIVE_ROUTES[dnr_source]["count"]
    count_args = count_route.translate(
        _parse(
            "count",
            "King",
            "--source",
            dnr_source,
            "--jurisdiction",
            "53",
            "--search-field",
            "county",
        ),
        count_route.adapter_command,
    )
    assert count_args.command == "count"
    assert count_args.representation == "dnr"
    assert count_args.county == "King"

    wisaard_source = adapter.WISAARD_SOURCE_ID
    point_route = query_property.LIVE_ROUTES[wisaard_source]["point"]
    point_args = point_route.translate(
        _parse(
            "point",
            "--source",
            wisaard_source,
            "--geometry",
            "--",
            "-122.3321,47.6062",
        ),
        point_route.adapter_command,
    )
    assert point_args.command == "point"
    assert point_args.representation == "wisaard"
    assert point_args.longitude == pytest.approx(-122.3321)
    assert point_args.latitude == pytest.approx(47.6062)
    assert point_args.geometry is True


def test_washington_state_companion_and_lineage_routes_remain_distinct():
    adapter = query_property.query_washington_parcels

    freshness_route = query_property.LIVE_ROUTES[adapter.FRESHNESS_SOURCE_ID][
        "freshness"
    ]
    freshness_args = freshness_route.translate(
        _parse(
            "freshness",
            "San Juan",
            "--source",
            adapter.FRESHNESS_SOURCE_ID,
        ),
        freshness_route.adapter_command,
    )
    assert freshness_args.command == "county-freshness"
    assert freshness_args.county == "San Juan"

    land_use_route = query_property.LIVE_ROUTES[adapter.LAND_USE_SOURCE_ID]["land-use"]
    land_use_args = land_use_route.translate(
        _parse(
            "land-use",
            "R",
            "--source",
            adapter.LAND_USE_SOURCE_ID,
            "--county-fips",
            "001",
        ),
        land_use_route.adapter_command,
    )
    assert land_use_args.command == "land-use-codes"
    assert land_use_args.county == "001"
    assert land_use_args.code == "R"

    parity_route = query_property.LIVE_ROUTES[adapter.LINEAGE_ID]["parity"]
    parity_args = parity_route.translate(
        _parse(
            "parity",
            "wisaard",
            "--source",
            adapter.LINEAGE_ID,
        ),
        parity_route.adapter_command,
    )
    assert parity_args.command == "parity"
    assert parity_args.include_wisaard is True

    metadata_route = query_property.LIVE_ROUTES[adapter.LINEAGE_ID]["search"]
    metadata_args = metadata_route.translate(
        _parse(
            "search",
            "representations",
            "--source",
            adapter.LINEAGE_ID,
        ),
        metadata_route.adapter_command,
    )
    assert metadata_args.command == "metadata"
    assert metadata_args.representation == "all"


def test_washington_state_parcel_route_sets_and_guidance_expose_lineage():
    adapter = query_property.query_washington_parcels

    for representation in adapter.REPRESENTATIONS.values():
        assert set(query_property.LIVE_ROUTES[representation.source_id]) == {
            "search",
            "address",
            "parcel",
            "map",
            "count",
            "point",
            "bbox",
            "probe",
        }
        guidance = query_property._source_guidance(representation.source_id)
        assert guidance["lineage_id"] == adapter.LINEAGE_ID
        assert guidance["representation_role"] == representation.role
        assert "owner" not in guidance["unified_operations"]
        assert guidance["official_complements"][0]["discovered_from"] == ("DATA_LINK")

    lineage = query_property._source_guidance(adapter.LINEAGE_ID)
    assert lineage["unified_operations"] == ["parity", "probe", "search"]
    assert lineage["parity_interpretation"] == ("mirror_health_not_corroboration")
    assert query_property._source_guidance(adapter.FRESHNESS_SOURCE_ID)[
        "unified_operations"
    ] == ["freshness", "search"]
    assert query_property._source_guidance(adapter.LAND_USE_SOURCE_ID)[
        "unified_operations"
    ] == ["land-use", "search"]


def test_dc_jurisdiction_metadata_preserves_state_equivalent_identity():
    district = query_property._jurisdiction("11")
    county_equivalent = query_property._jurisdiction("11001")

    assert district.state_code == "DC"
    assert district.county_fips is None
    assert county_equivalent.state_code == "DC"
    assert county_equivalent.county_fips == "11001"


def test_dc_property_routes_preserve_component_specific_selectors():
    adapter = query_property.query_dc_property

    owner_route = query_property.LIVE_ROUTES[adapter.ITSPE_SOURCE_ID]["owner"]
    owner_args = owner_route.translate(
        _parse(
            "owner",
            "BRENTWOOD ROAD LLC",
            "--source",
            adapter.ITSPE_SOURCE_ID,
            "--jurisdiction",
            "11",
            "--limit",
            "7",
        ),
        owner_route.adapter_command,
    )
    assert owner_args.command == "assessment"
    assert owner_args.field == "owner"
    assert owner_args.limit == 7

    map_route = query_property.LIVE_ROUTES[adapter.OWNER_POLYGON_SOURCE_ID]["map"]
    map_args = map_route.translate(
        _parse(
            "map",
            adapter.PROBE_SSL,
            "--source",
            adapter.OWNER_POLYGON_SOURCE_ID,
        ),
        map_route.adapter_command,
    )
    assert map_args.command == "geometry"
    assert map_args.field == "ssl"
    assert map_args.geometry is True

    point_route = query_property.LIVE_ROUTES[adapter.OWNER_POLYGON_SOURCE_ID]["point"]
    point_args = point_route.translate(
        _parse(
            "point",
            "--source",
            adapter.OWNER_POLYGON_SOURCE_ID,
            "--",
            "-76.9927,38.9176",
        ),
        point_route.adapter_command,
    )
    assert point_args.command == "point"
    assert point_args.longitude == pytest.approx(-76.9927)
    assert point_args.latitude == pytest.approx(38.9176)
    assert point_args.geometry is True

    sale_route = query_property.LIVE_ROUTES[adapter.SALES_SOURCE_ID]["sale"]
    sale_args = sale_route.translate(
        _parse(
            "sale",
            adapter.PROBE_SSL,
            "--source",
            adapter.SALES_SOURCE_ID,
        ),
        sale_route.adapter_command,
    )
    assert sale_args.command == "sales"
    assert sale_args.ssl == adapter.PROBE_SSL

    survey_route = query_property.LIVE_ROUTES[adapter.SURVEY_SOURCE_ID]["survey"]
    survey_args = survey_route.translate(
        _parse(
            "survey",
            adapter.PROBE_SURVEY_GUID,
            "--source",
            adapter.SURVEY_SOURCE_ID,
        ),
        survey_route.adapter_command,
    )
    assert survey_args.command == "surveys"
    assert survey_args.field == "document"


def test_dc_property_route_sets_keep_recorder_and_substitutes_distinct():
    adapter = query_property.query_dc_property

    assert set(query_property.LIVE_ROUTES[adapter.ITSPE_SOURCE_ID]) == {
        "search",
        "owner",
        "address",
        "account",
        "parcel",
        "instrument",
        "count",
        "probe",
    }
    assert set(query_property.LIVE_ROUTES[adapter.OWNER_POLYGON_SOURCE_ID]) == {
        "search",
        "owner",
        "address",
        "parcel",
        "instrument",
        "map",
        "count",
        "point",
        "bbox",
        "probe",
    }
    assert set(query_property.LIVE_ROUTES[adapter.SALES_SOURCE_ID]) == {
        "search",
        "parcel",
        "sale",
        "event",
        "count",
        "probe",
    }
    assert set(query_property.LIVE_ROUTES[adapter.SURVEY_SOURCE_ID]) == {
        "search",
        "parcel",
        "survey",
        "count",
        "probe",
    }
    assert adapter.LINEAGE_ID not in query_property.LIVE_ROUTES
    assert adapter.RECORDER_SOURCE_ID not in query_property.LIVE_ROUTES

    recorder = query_property._source_guidance(adapter.RECORDER_SOURCE_ID)
    sales = query_property._source_guidance(adapter.SALES_SOURCE_ID)
    surveys = query_property._source_guidance(adapter.SURVEY_SOURCE_ID)
    polygon = query_property._source_guidance(adapter.OWNER_POLYGON_SOURCE_ID)
    assert recorder["authentication"] == "registered_user"
    assert recorder["unified_operations"] == []
    assert "actual instrument index" in recorder["note"]
    assert "do not replace" in sales["note"]
    assert "not the Recorder" in surveys["note"]
    assert "different grain" in polygon["note"]


def test_dc_property_routes_reject_non_dc_jurisdiction():
    adapter = query_property.query_dc_property
    route = query_property.LIVE_ROUTES[adapter.ITSPE_SOURCE_ID]["parcel"]

    with pytest.raises(ValueError, match="jurisdiction 11/DC"):
        route.translate(
            _parse(
                "parcel",
                adapter.PROBE_SSL,
                "--source",
                adapter.ITSPE_SOURCE_ID,
                "--jurisdiction",
                "53",
            ),
            route.adapter_command,
        )


def test_philadelphia_property_routes_preserve_component_selectors_and_limits():
    adapter = query_property.query_philadelphia_property

    owner_route = query_property.LIVE_ROUTES[adapter.SOURCE_ID]["owner"]
    owner_args = owner_route.translate(
        _parse(
            "owner",
            "PENA ROSADO",
            "--source",
            adapter.SOURCE_ID,
            "--jurisdiction",
            "42101",
            "--limit",
            "7",
        ),
        owner_route.adapter_command,
    )
    assert owner_args.command == "owner"
    assert owner_args.query == "PENA ROSADO"
    assert owner_args.limit == 7

    parcel_args = query_property.LIVE_ROUTES[adapter.SOURCE_ID]["parcel"].translate(
        _parse(
            "parcel",
            adapter.PROBE_PARCEL_NUMBER,
            "--source",
            adapter.SOURCE_ID,
        ),
        "parcel",
    )
    assert parcel_args.limit is None

    history_route = query_property.LIVE_ROUTES[adapter.HISTORY_SOURCE_ID]["parcel"]
    history_args = history_route.translate(
        _parse(
            "parcel",
            adapter.PROBE_PARCEL_NUMBER,
            "--source",
            adapter.HISTORY_SOURCE_ID,
            "--tax-year",
            "2023",
        ),
        history_route.adapter_command,
    )
    assert history_args.command == "history"
    assert history_args.from_year == 2023
    assert history_args.to_year == 2023
    assert history_args.limit is None

    dor_route = query_property.LIVE_ROUTES[adapter.DOR_SOURCE_ID]["instrument"]
    dor_args = dor_route.translate(
        _parse(
            "instrument",
            adapter.PROBE_REGISTRY_NUMBER,
            "--source",
            adapter.DOR_SOURCE_ID,
        ),
        dor_route.adapter_command,
    )
    assert dor_args.command == "parcel-shape"
    assert dor_args.by == "registry"
    assert dor_args.geometry is True


def test_philadelphia_property_route_sets_and_guidance_keep_sources_distinct():
    adapter = query_property.query_philadelphia_property

    assert set(query_property.LIVE_ROUTES[adapter.SOURCE_ID]) == {
        "search",
        "owner",
        "address",
        "account",
        "parcel",
        "instrument",
        "map",
        "probe",
    }
    assert set(query_property.LIVE_ROUTES[adapter.HISTORY_SOURCE_ID]) == {
        "search",
        "account",
        "parcel",
    }
    assert set(query_property.LIVE_ROUTES[adapter.DOR_SOURCE_ID]) == {
        "search",
        "address",
        "parcel",
        "instrument",
        "map",
    }

    current = query_property._source_guidance(adapter.SOURCE_ID)
    history = query_property._source_guidance(adapter.HISTORY_SOURCE_ID)
    dor = query_property._source_guidance(adapter.DOR_SOURCE_ID)
    assert "not independent corroboration" in current["note"]
    assert history["native_key"] == "OPA parcel number"
    assert "recorded deed descriptions" in dor["note"]


def test_philadelphia_property_routes_reject_other_jurisdictions():
    adapter = query_property.query_philadelphia_property
    route = query_property.LIVE_ROUTES[adapter.SOURCE_ID]["parcel"]

    with pytest.raises(ValueError, match="GEOID 42101"):
        route.translate(
            _parse(
                "parcel",
                adapter.PROBE_PARCEL_NUMBER,
                "--source",
                adapter.SOURCE_ID,
                "--jurisdiction",
                "42",
                "--county-fips",
                "003",
            ),
            route.adapter_command,
        )


def test_wisconsin_statewide_routes_preserve_native_fields_and_open_limit():
    adapter = query_property.query_wisconsin_parcels
    routes = query_property.LIVE_ROUTES[adapter.SOURCE_ID]

    owner_args = routes["owner"].translate(
        _parse(
            "owner",
            "EPSTEIN",
            "--source",
            adapter.SOURCE_ID,
            "--jurisdiction",
            "55001",
        ),
        routes["owner"].adapter_command,
    )
    assert owner_args.command == "owner"
    assert owner_args.query == "EPSTEIN"
    assert owner_args.county == "55001"
    assert owner_args.limit is None

    mailing_args = routes["search"].translate(
        _parse(
            "search",
            "PO BOX 100",
            "--source",
            adapter.SOURCE_ID,
            "--search-field",
            "mailing",
            "--limit",
            "7",
        ),
        routes["search"].adapter_command,
    )
    assert mailing_args.command == "mailing"
    assert mailing_args.limit == 7

    map_args = routes["map"].translate(
        _parse(
            "map",
            "001008015540000",
            "--source",
            adapter.SOURCE_ID,
        ),
        routes["map"].adapter_command,
    )
    assert map_args.command == "parcel"
    assert map_args.geometry is True


def test_wisconsin_guidance_distinguishes_lineage_and_adjacent_records():
    adapter = query_property.query_wisconsin_parcels

    guidance = query_property._source_guidance(adapter.SOURCE_ID)

    route_ids = {item["route_id"] for item in guidance["official_complements"]}
    assert "county-land-record-systems" in route_ids
    assert "dor-retr-property-search" in route_ids
    assert "same-release downloads" in guidance["note"].lower()
    assert set(guidance["unified_operations"]) == {
        "address",
        "map",
        "owner",
        "parcel",
        "probe",
        "search",
    }


def test_new_jersey_statewide_routes_translate_geoid_spatial_and_count():
    adapter = query_property.query_new_jersey_parcels
    routes = query_property.LIVE_ROUTES[adapter.SOURCE_ID]

    address_args = routes["address"].translate(
        _parse(
            "address",
            "FOREST AVE",
            "--source",
            adapter.SOURCE_ID,
            "--jurisdiction",
            "34013",
        ),
        routes["address"].adapter_command,
    )
    assert address_args.command == "address"
    assert address_args.county == "07"
    assert address_args.limit is None

    pin_args = routes["search"].translate(
        _parse(
            "search",
            "0703_14_5",
            "--source",
            adapter.SOURCE_ID,
            "--search-field",
            "pin",
            "--limit",
            "4",
        ),
        routes["search"].adapter_command,
    )
    assert pin_args.command == "pin"
    assert pin_args.query == "0703_14_5"
    assert pin_args.limit == 4

    count_args = routes["count"].translate(
        _parse(
            "count",
            "*",
            "--source",
            adapter.SOURCE_ID,
            "--county-fips",
            "013",
        ),
        routes["count"].adapter_command,
    )
    assert count_args.command == "count"
    assert count_args.county == "07"

    point_args = routes["point"].translate(
        _parse(
            "point",
            "--source",
            adapter.SOURCE_ID,
            "--",
            "-74.30143,40.55346",
        ),
        routes["point"].adapter_command,
    )
    assert point_args.command == "point"
    assert point_args.longitude == -74.30143
    assert point_args.latitude == 40.55346


def test_new_jersey_guidance_exposes_redaction_and_transaction_complements():
    adapter = query_property.query_new_jersey_parcels

    guidance = query_property._source_guidance(adapter.SOURCE_ID)

    source_ids = {item["source_id"] for item in guidance["official_complements"]}
    assert "us-nj-treasury-sr1a-sales" in source_ids
    assert "us-nj-local-assessors-tax-boards" in source_ids
    assert "us-nj-county-clerks-registers" in source_ids
    assert "source-redacted" in guidance["note"]
    assert "owner" not in guidance["unified_operations"]


def test_new_jersey_sr1a_routes_preserve_sale_and_release_selectors():
    adapter = query_property.query_new_jersey_sr1a
    routes = query_property.LIVE_ROUTES[adapter.SOURCE_ID]

    owner_args = routes["owner"].translate(
        _parse(
            "owner",
            "ALPHA OWNER LLC",
            "--source",
            adapter.SOURCE_ID,
            "--jurisdiction",
            "34013",
            "--tax-year",
            "2025",
        ),
        routes["owner"].adapter_command,
    )
    assert owner_args.command == "search"
    assert owner_args.query == "ALPHA OWNER LLC"
    assert owner_args.field == "party"
    assert owner_args.county == "07"
    assert owner_args.year == [2025]
    assert owner_args.limit is None

    parcel_args = routes["parcel"].translate(
        _parse(
            "parcel",
            "0703_14_6",
            "--source",
            adapter.SOURCE_ID,
        ),
        routes["parcel"].adapter_command,
    )
    assert parcel_args.command == "search"
    assert parcel_args.query is None
    assert parcel_args.field == "block-lot"
    assert parcel_args.municipality_code == "0703"
    assert parcel_args.block == "14"
    assert parcel_args.lot == "6"

    instrument_args = routes["instrument"].translate(
        _parse(
            "instrument",
            "A123/0042",
            "--source",
            adapter.SOURCE_ID,
        ),
        routes["instrument"].adapter_command,
    )
    assert instrument_args.command == "search"
    assert instrument_args.query is None
    assert instrument_args.deed_book == "A123"
    assert instrument_args.deed_page == "0042"

    sale_args = routes["sale"].translate(
        _parse(
            "sale",
            "BETA BUYER LLC",
            "--source",
            adapter.SOURCE_ID,
            "--search-field",
            "grantee",
            "--limit",
            "7",
        ),
        routes["sale"].adapter_command,
    )
    assert sale_args.field == "grantee"
    assert sale_args.limit == 7


def test_new_jersey_sr1a_guidance_separates_records_from_occurrences():
    guidance = query_property._source_guidance(query_property.NEW_JERSEY_SR1A_SOURCE_ID)

    assert "serial_number" in guidance["record_identity"]
    assert "release_id" in guidance["release_occurrence_identity"]
    source_ids = {item["source_id"] for item in guidance["official_complements"]}
    assert "us-nj-njgin-parcels-modiv" in source_ids
    assert "us-nj-county-clerks-registers" in source_ids
    assert "us-nj-tax-court-property-cases" in source_ids
    assert set(guidance["unified_operations"]) == {
        "address",
        "instrument",
        "owner",
        "parcel",
        "probe",
        "sale",
        "search",
    }


def test_palm_beach_recorder_routes_use_exact_instrument_or_book_page():
    source_id = query_property.PALM_BEACH_RECORDER_SOURCE_ID
    routes = query_property.LIVE_ROUTES[source_id]

    instrument_args = routes["instrument"].translate(
        _parse(
            "instrument",
            "19860255822",
            "--source",
            source_id,
            "--jurisdiction",
            "12099",
        ),
        routes["instrument"].adapter_command,
    )
    assert instrument_args.command == "instrument"
    assert instrument_args.instrument_number == "19860255822"

    book_page_args = routes["instrument"].translate(
        _parse(
            "instrument",
            "5021/1011",
            "--source",
            source_id,
            "--search-field",
            "book-page",
        ),
        routes["instrument"].adapter_command,
    )
    assert book_page_args.command == "book-page"
    assert book_page_args.book == 5021
    assert book_page_args.page == 1011

    with pytest.raises(ValueError, match="exact numeric instrument"):
        routes["instrument"].translate(
            _parse(
                "instrument",
                "ROBERT C MALT",
                "--source",
                source_id,
            ),
            routes["instrument"].adapter_command,
        )


def test_palm_beach_recorder_guidance_separates_identity_and_discovery():
    guidance = query_property._source_guidance(
        query_property.PALM_BEACH_RECORDER_SOURCE_ID
    )

    assert guidance["record_identity"] == "official_instrument_number"
    assert guidance["portal_locator"] == "native_document_id"
    assert guidance["unified_operations"] == ["instrument", "probe"]
    source_ids = {item["source_id"] for item in guidance["official_complements"]}
    assert source_ids >= {
        "us-fl-palm-beach-official-records-daily-index",
        "us-fl-palm-beach-official-records-cd-archive",
        "us-fl-palm-beach-property-appraiser",
        "us-fl-palm-beach-tax-collector",
        "us-fl-palm-beach-tax-deeds",
        "us-fl-palm-beach-ecaseview",
    }
    assert "recaptcha" in guidance["note"].casefold()


@pytest.mark.parametrize(
    ("source_id", "jurisdiction"),
    [
        (query_property.WISCONSIN_STATEWIDE_PARCELS_SOURCE_ID, "34"),
        (query_property.NEW_JERSEY_STATEWIDE_PARCELS_SOURCE_ID, "55"),
        (query_property.NEW_JERSEY_SR1A_SOURCE_ID, "55"),
    ],
)
def test_statewide_parcel_routes_reject_other_states(
    source_id,
    jurisdiction,
):
    route = query_property.LIVE_ROUTES[source_id]["parcel"]

    with pytest.raises(ValueError, match="state context"):
        route.translate(
            _parse(
                "parcel",
                "fixture",
                "--source",
                source_id,
                "--jurisdiction",
                jurisdiction,
            ),
            route.adapter_command,
        )
