import json

from tools import query_md_mdp_parcel_points as mdp
from tools import query_md_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


ACCOUNT_ID = "1901000047"
COUNTY_GEOID = "24037"
POINT_SOURCE_ID = "us-md-mdp-parcel-points"
CANONICAL_SOURCE_ID = "us-md-sdat-property-hidden"


def _point_envelope(*, object_id: int = 321) -> dict:
    contract = mdp.LayerContract(
        schema_fingerprint="a" * 64,
        field_names=mdp.REQUIRED_FIELDS,
        max_record_count=2_000,
        object_id_field=mdp.OBJECT_ID_FIELD,
        geometry_type=mdp.GEOMETRY_TYPE,
        spatial_reference={"wkid": 102100, "latestWkid": 3857},
    )
    record = mdp.normalize_feature(
        {
            "attributes": {
                "OBJECTID": object_id,
                "JURSCODE": "1901",
                "ACCTID": ACCOUNT_ID,
                "DIGXCORD": 1324567.25,
                "DIGYCORD": 321234.5,
                "ADDRESS": "100 TEST POINT RD",
                "STRTNUM": 100,
                "STRTNAM": "TEST POINT",
                "STRTTYP": "RD",
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
                "LEGAL1": "LOT 4",
                "LEGAL2": "TEST POINT SUB",
                "DR1LIBER": "01234",
                "DR1FOLIO": "0567",
                "PLAT": "000321",
                "PLTLIBER": "0000123",
                "PLTFOLIO": "0045",
                "MAP": "0012",
                "GRID": "0003",
                "PARCEL": "0042",
                "ZONING": "RL",
                "LU": "R",
                "DESCLU": "Residential",
                "ACRES": 1.25,
                "LANDAREA": 54450,
                "LUOM": "S",
                "YEARBLT": "1998",
                "SQFTSTRC": 2400,
                "STRUCNST": "FR",
                "DESCCNST": "Frame",
                "STRUSTYL": "COL",
                "DESCSTYL": "Colonial",
                "STRUBLDG": "SFD",
                "DESCBLDG": "Single Family Detached",
                "GR1LIBR1": "01000",
                "GR1FOLO1": "0200",
                "CONVEY1": 1,
                "TRADATE": "20240517",
                "CONSIDR1": 425000,
                "NFMLNDVL": 125000,
                "NFMIMPVL": 300000,
                "NFMTTLVL": 425000,
                "MDPVDATE": "07/2026",
                "SDATDATE": "06/2026",
            },
            "geometry": {
                "x": -76.634,
                "y": 38.301,
            },
        },
        contract=contract,
        geometry_requested=True,
    )
    query = PublicRecordsQuery(
        source=mdp.SOURCE_METADATA,
        jurisdiction=mdp.JURISDICTION,
        query=QueryMetadata(
            operation="account",
            parameters={"account": ACCOUNT_ID},
            requested_limit=1,
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
        warnings=mdp.SOURCE_WARNINGS,
    ).to_dict()


def _canonical_envelope() -> dict:
    fields = query_md_property.FIELDS
    record = query_md_property._normalize_record(
        {
            fields["jurisdiction_code"]: "SMCO",
            fields["county_name"]: "St. Mary's County",
            fields["account_id"]: ACCOUNT_ID,
            fields["county_code"]: "19",
            fields["district"]: "01",
            fields["account_number"]: "000047",
            fields["address"]: "100 TEST POINT RD",
            fields["unit"]: "UNIT 4",
            fields["city"]: "LEONARDTOWN",
            fields["postal_code"]: "20650",
            fields["longitude"]: "-76.634",
            fields["latitude"]: "38.301",
            fields["current_land"]: "130000",
            fields["current_improvements"]: "305000",
            fields["current_total"]: "435000",
            fields["assessment_cycle_year"]: "2026",
            fields["source_updated"]: "20260715",
        },
        response_schema_fingerprint="b" * 64,
    )
    query = query_md_property.build_query(
        "parcel",
        ACCOUNT_ID,
        county_code="19",
        limit=1,
        cursor=None,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:05:00Z",
    ).to_dict()


def _durable_counts(db) -> dict[str, int]:
    tables = (
        "parcel_snapshot",
        "parcel_alias",
        "parcel_address",
        "assessment",
        "sale_event",
        "parcel_geometry",
        "ownership_assertion",
        "recorded_instrument",
        "instrument_parcel",
    )
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _assert_point_children_and_evidence(db, *, parcel_id: int) -> None:
    aliases = {
        (row["alias_type"], row["alias_value"], row["source_id"])
        for row in db.execute(
            """
            SELECT alias_type, alias_value, source_id
            FROM parcel_alias
            WHERE parcel_id=?
            """,
            (parcel_id,),
        ).fetchall()
    }
    assert {
        ("md_jurisdiction_code", "1901", POINT_SOURCE_ID),
        ("md_map", "0012", POINT_SOURCE_ID),
        ("md_grid", "0003", POINT_SOURCE_ID),
        ("md_parcel", "0042", POINT_SOURCE_ID),
        ("md_plat", "000321", POINT_SOURCE_ID),
    }.issubset(aliases)

    point_addresses = db.execute(
        """
        SELECT address_role, raw_address, source_id
        FROM parcel_address
        WHERE parcel_id=? AND source_id=?
        ORDER BY address_role
        """,
        (parcel_id, POINT_SOURCE_ID),
    ).fetchall()
    assert {
        (row["address_role"], row["raw_address"], row["source_id"])
        for row in point_addresses
    } == {
        ("mailing", "PO BOX 123, ATTN TAX DESK", POINT_SOURCE_ID),
        ("situs", "100 TEST POINT RD UNIT 4", POINT_SOURCE_ID),
    }

    assessment = db.execute(
        """
        SELECT source_id, tax_year, land_value_minor,
               improvement_value_minor, total_value_minor,
               market_value_minor
        FROM assessment
        WHERE parcel_id=? AND source_id=?
        """,
        (parcel_id, POINT_SOURCE_ID),
    ).fetchone()
    assert tuple(assessment) == (
        POINT_SOURCE_ID,
        "",
        12_500_000,
        30_000_000,
        42_500_000,
        42_500_000,
    )

    sale = db.execute(
        """
        SELECT source_id, native_sale_id, sale_date,
               consideration_minor, derivation, instrument_id
        FROM sale_event
        WHERE parcel_id=? AND source_id=?
        """,
        (parcel_id, POINT_SOURCE_ID),
    ).fetchone()
    assert tuple(sale) == (
        POINT_SOURCE_ID,
        "deed:01000:0200",
        "2024-05-17",
        42_500_000,
        "mdp_parcel_points_transfer_reference",
        None,
    )

    geometry = db.execute(
        """
        SELECT source_id, geometry_format, crs, source_resolution,
               snapshot_date
        FROM parcel_geometry
        WHERE parcel_id=? AND source_id=?
        """,
        (parcel_id, POINT_SOURCE_ID),
    ).fetchone()
    assert tuple(geometry) == (
        POINT_SOURCE_ID,
        "geojson_point",
        "EPSG:4326",
        "published_parcel_point",
        "2026-06",
    )

    assert (
        db.execute(
            "SELECT COUNT(*) FROM ownership_assertion WHERE parcel_id=?",
            (parcel_id,),
        ).fetchone()[0]
        == 0
    )
    assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 0

    observation = db.execute(
        """
        SELECT source_native_id, record_kind, raw_json
        FROM source_observation
        WHERE source_id=? AND record_kind='parcel_assessment_point_snapshot'
        ORDER BY observation_id
        LIMIT 1
        """,
        (POINT_SOURCE_ID,),
    ).fetchone()
    assert observation["source_native_id"] == "OBJECTID:321"
    assert observation["record_kind"] == "parcel_assessment_point_snapshot"
    raw = json.loads(observation["raw_json"])
    assert raw["structure"]["building_type"]["code"] == "SFD"
    assert raw["land"]["acres"] == 1.25
    assert raw["land_use"]["zoning_code"] == "RL"
    assert raw["deed_reference"] == {
        "liber": "01234",
        "folio": "0567",
        "instrument_copy_in_source": False,
    }
    assert raw["plat_reference"] == {
        "plat": "000321",
        "liber": "0000123",
        "folio": "0045",
    }
    assert raw["raw_attributes"]["YEARBLT"] == "1998"
    assert raw["raw_attributes"]["DR1LIBER"] == "01234"
    assert raw["raw_attributes"]["PLAT"] == "000321"
    assert raw["mailing_address"]["ownership_assertion"] is False
    assert raw["mailing_address"]["current_owner_name_published"] is False


def test_points_first_shell_is_adopted_by_canonical_sdat_record(tmp_path) -> None:
    db_path = tmp_path / "property.db"
    point_envelope = _point_envelope()
    canonical_envelope = _canonical_envelope()

    point_report = ingest_property_envelope(point_envelope, db_path=db_path)
    point_projection = point_report["records"][0]
    parcel_id = int(point_projection["parcel_id"])
    assert point_projection["parcel_placeholder_created"] == 1
    assert point_projection["parcel_anchor_source_id"] == POINT_SOURCE_ID
    assert point_projection["owners_upserted"] == 0
    assert (
        point_projection["owner_visibility_state"]
        == "not_published_in_representation"
    )
    assert point_projection["recorded_instruments_upserted"] == 0

    db = connect_property(db_path)
    try:
        shell = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            WHERE parcel_id=?
            """,
            (parcel_id,),
        ).fetchone()
        assert tuple(shell) == (
            POINT_SOURCE_ID,
            COUNTY_GEOID,
            ACCOUNT_ID,
            "",
        )
        _assert_point_children_and_evidence(db, parcel_id=parcel_id)
    finally:
        db.close()

    canonical_report = ingest_property_envelope(
        canonical_envelope,
        db_path=db_path,
    )
    canonical_projection = canonical_report["records"][0]
    assert canonical_projection["parcel_id"] == parcel_id
    assert canonical_projection["parcel_shell_adopted"] == 1
    assert (
        canonical_projection["parcel_shell_source_id_adopted"]
        == POINT_SOURCE_ID
    )

    db = connect_property(db_path)
    try:
        adopted = db.execute(
            """
            SELECT parcel_id, source_id, jurisdiction_geoid,
                   native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(adopted) == (
            parcel_id,
            CANONICAL_SOURCE_ID,
            COUNTY_GEOID,
            ACCOUNT_ID,
            "2026",
        )
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        _assert_point_children_and_evidence(db, parcel_id=parcel_id)
        counts_before_rerun = _durable_counts(db)
    finally:
        db.close()

    rerun_point = ingest_property_envelope(point_envelope, db_path=db_path)
    assert rerun_point["records"][0]["parcel_id"] == parcel_id
    assert rerun_point["records"][0]["parcel_placeholder_created"] == 0
    assert (
        rerun_point["records"][0]["parcel_anchor_source_id"]
        == CANONICAL_SOURCE_ID
    )
    rerun_canonical = ingest_property_envelope(
        canonical_envelope,
        db_path=db_path,
    )
    assert rerun_canonical["records"][0]["parcel_shell_adopted"] == 0

    db = connect_property(db_path)
    try:
        assert _durable_counts(db) == counts_before_rerun
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
    finally:
        db.close()


def test_points_reverse_order_reuses_canonical_parcel_and_is_idempotent(
    tmp_path,
) -> None:
    db_path = tmp_path / "property.db"
    point_envelope = _point_envelope()
    canonical_envelope = _canonical_envelope()

    canonical_report = ingest_property_envelope(
        canonical_envelope,
        db_path=db_path,
    )
    parcel_id = int(canonical_report["records"][0]["parcel_id"])
    point_report = ingest_property_envelope(point_envelope, db_path=db_path)
    point_projection = point_report["records"][0]

    assert point_projection["parcel_id"] == parcel_id
    assert point_projection["parcel_placeholder_created"] == 0
    assert point_projection["parcel_anchor_source_id"] == CANONICAL_SOURCE_ID

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            WHERE parcel_id=?
            """,
            (parcel_id,),
        ).fetchone()
        assert tuple(parcel) == (
            CANONICAL_SOURCE_ID,
            COUNTY_GEOID,
            ACCOUNT_ID,
            "2026",
        )
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        _assert_point_children_and_evidence(db, parcel_id=parcel_id)
        counts_before_rerun = _durable_counts(db)
    finally:
        db.close()

    ingest_property_envelope(canonical_envelope, db_path=db_path)
    rerun_point = ingest_property_envelope(point_envelope, db_path=db_path)
    assert rerun_point["records"][0]["parcel_id"] == parcel_id
    assert rerun_point["records"][0]["parcel_placeholder_created"] == 0

    db = connect_property(db_path)
    try:
        assert _durable_counts(db) == counts_before_rerun
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
    finally:
        db.close()
