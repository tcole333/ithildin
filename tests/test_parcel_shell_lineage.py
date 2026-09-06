from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    SourceMetadata,
)
from tools.public_records_store import connect_property


NY_SALESWEB_SOURCE_ID = "us-ny-orpts-sales-web"
NY_STATEWIDE_SOURCE_ID = "us-ny-statewide-parcels"
NJ_SR1A_SOURCE_ID = "us-nj-treasury-sr1a-sales"
NJ_STATEWIDE_SOURCE_ID = "us-nj-njgin-parcels-modiv"


def _envelope(
    *,
    source_id: str,
    source_name: str,
    source_role: str,
    jurisdiction_id: str,
    jurisdiction_name: str,
    state_code: str,
    record: dict,
    retrieved_at: str,
) -> dict:
    query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=source_id,
            name=source_name,
            source_role=source_role,
            base_url=f"https://example.test/{source_id}",
        ),
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id=jurisdiction_id,
            name=jurisdiction_name,
            state_code=state_code,
        ),
        query=QueryMetadata(
            operation="lineage-fixture",
            parameters={"native_id": record.get("native_id")},
            requested_limit=1,
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def _ny_salesweb_envelope() -> dict:
    swis_print_key_id = "01010041.00-2-12.7"
    return _envelope(
        source_id=NY_SALESWEB_SOURCE_ID,
        source_name="New York ORPTS SalesWeb",
        source_role="statewide_property_transfer_index",
        jurisdiction_id="36001",
        jurisdiction_name="Albany County, New York",
        state_code="NY",
        retrieved_at="2026-07-30T12:00:00Z",
        record={
            "source_id": NY_SALESWEB_SOURCE_ID,
            "record_type": "property_sale",
            "native_record_id": "2047101021",
            "sale_record_id": "2047101021",
            "jurisdiction": {
                "state_code": "NY",
                "state_fips": "36",
                "county_name": "Albany",
                "county_geoid": "36001",
                "municipality": "Albany",
            },
            "transaction": {
                "sale_date": {"iso": "2025-05-01"},
                "sale_price_dollars": "450000",
                "report_type_code": "1",
                "deed": {
                    "book": "123",
                    "page": "45",
                    "document_number": "2025-100",
                    "deed_date": {"iso": "2025-04-30"},
                },
            },
            "parties": {
                "seller": {"name": "SELLER LLC"},
                "buyer": {"name": "BUYER LLC"},
            },
            "property": {
                "address": {
                    "street_number": "10",
                    "street": "MAIN ST",
                    "postal_code": "12207",
                    "state": "NY",
                },
                "parcel_identifiers": {
                    "salesweb_parcel_id": "1001",
                    "swis": "010100",
                    "print_key": "41.00-2-12.7",
                    "swis_print_key_id": swis_print_key_id,
                },
                "roll_year": "2024",
                "assessed_value_dollars": {"total": "300000"},
                "property_class": {"on_last_roll": {"code": "411"}},
            },
            "source_processing": {
                "load_date": {"iso": "2025-05-05"},
            },
            "source_record": {
                "endpoint": "https://example.test/ny-salesweb/2047101021",
            },
        },
    )


def _ny_statewide_envelope() -> dict:
    return _envelope(
        source_id=NY_STATEWIDE_SOURCE_ID,
        source_name="New York Statewide Parcel Map",
        source_role="statewide_parcel_assessment_centroid",
        jurisdiction_id="36001",
        jurisdiction_name="Albany County, New York",
        state_code="NY",
        retrieved_at="2026-07-30T12:05:00Z",
        record={
            "source_id": NY_STATEWIDE_SOURCE_ID,
            "record_type": "statewide_annual_parcel_assessment_centroid",
            "native_id": "01010000004100000002001270000000",
            "native_id_type": "swis_sbl_id",
            "component": "centroids",
            "component_role": "annual_assessment_centroid",
            "component_coverage": "all_counties",
            "jurisdiction": {
                "state_code": "NY",
                "state_fips": "36",
                "county_name": "Albany",
                "county_geoid": "36001",
            },
            "parcel_identifiers": {
                "swis": "010100",
                "sbl": "00004100000002001270000000",
                "print_key": "41.00-2-12.7",
                "swis_sbl_id": "01010000004100000002001270000000",
                "swis_print_key_id": "01010041.00-2-12.7",
            },
            "cross_component_join_keys": [
                {
                    "field": "SWIS_PRINT_KEY_ID",
                    "value": "01010041.00-2-12.7",
                }
            ],
            "situs_address": {
                "raw": "10 MAIN ST",
                "city": "Albany",
                "state": "NY",
                "postal_code": "12207",
            },
            "mailing_addresses": {},
            "owners": [],
            "assessment": {
                "roll_year": "2025",
                "total_assessed_value": "310000",
                "full_market_value": "460000",
                "property_class": "411",
            },
        },
    )


def _nj_sr1a_envelope() -> dict:
    return _envelope(
        source_id=NJ_SR1A_SOURCE_ID,
        source_name="New Jersey Treasury SR1A",
        source_role="statewide_property_sale_return_index",
        jurisdiction_id="34013",
        jurisdiction_name="Essex County, New Jersey",
        state_code="NJ",
        retrieved_at="2026-07-30T13:00:00Z",
        record={
            "source_id": NJ_SR1A_SOURCE_ID,
            "record_type": "property_sale",
            "native_record_id": "0703:1234567:A123:0042:250617",
            "sale_record_id": "0703:1234567:A123:0042:250617",
            "source_occurrence_id": (
                "sr1a-annual-2025:0703:1234567:A123:0042:250617"
            ),
            "jurisdiction": {
                "state_code": "NJ",
                "state_fips": "34",
                "county_name": "Essex",
                "county_geoid": "34013",
                "municipality_code": "0703",
            },
            "transaction": {
                "verified_sale_price_dollars": "745000",
                "qualification_codes": "Q1",
            },
            "deed": {
                "book": "A123",
                "page": "0042",
                "deed_date": "2025-06-10",
                "recorded_date": "2025-06-17",
            },
            "parties": {
                "grantor": {
                    "name": "ALPHA OWNER LLC",
                    "mailing_address": {
                        "street": "10 OLD ROAD",
                        "city_state": "NEWARK NJ",
                        "postal_code": "07101",
                    },
                },
                "grantee": {
                    "name": "BETA BUYER LLC",
                    "mailing_address": {
                        "street": "20 NEW ROAD",
                        "city_state": "CALDWELL NJ",
                        "postal_code": "07006",
                    },
                },
            },
            "property": {
                "parcel": {
                    "block": "14",
                    "block_suffix": "",
                    "lot": "6",
                    "lot_suffix": "",
                },
                "additional_parcels": [],
                "location": "35 HILLSIDE AVE",
                "assessment_year": "2025",
                "property_class": "2",
                "main_assessed_value_dollars": {
                    "land": "150000",
                    "building": "350000",
                    "total": "500000",
                },
            },
            "source_processing": {
                "last_update_date": "2025-06-20",
            },
            "source_record": {
                "archive_url": "https://example.test/nj-sr1a/Sales2025.zip",
            },
        },
    )


def _nj_statewide_envelope() -> dict:
    return _envelope(
        source_id=NJ_STATEWIDE_SOURCE_ID,
        source_name="New Jersey NJGIN Parcels and MOD-IV",
        source_role="statewide_parcel_and_assessment_join",
        jurisdiction_id="34013",
        jurisdiction_name="Essex County, New Jersey",
        state_code="NJ",
        retrieved_at="2026-07-30T13:05:00Z",
        record={
            "source_id": NJ_STATEWIDE_SOURCE_ID,
            "record_type": "statewide_parcel_modiv_observation",
            "native_parcel_id": "0703_14_6",
            "jurisdiction": {
                "state_code": "NJ",
                "state_fips": "34",
                "county_name": "Essex",
                "county_geoid": "34013",
                "municipality_code": "0703",
            },
            "parcel_identifiers": {
                "pams_pin": "070314060000",
                "pin_nodup": "0703_14_6",
                "gis_pin": "0703_14_6",
                "municipality_code": "0703",
                "block": "14",
                "lot": "6",
            },
            "classification": {"property_class": "2"},
            "assessment": {
                "land_value": "160000",
                "improvement_value": "360000",
                "net_assessed_value": "520000",
            },
            "owner_observation": {"visibility_state": "redacted_by_source"},
            "situs_address": {
                "raw": "35 HILLSIDE AVE",
                "state": "NJ",
            },
            "source_dates": {
                "parcel_last_update": "2026-01-15",
            },
        },
    )


def _table_counts(db) -> dict[str, int]:
    tables = (
        "parcel_snapshot",
        "parcel_alias",
        "parcel_address",
        "assessment",
        "sale_event",
        "recorded_instrument",
        "instrument_party",
        "instrument_parcel",
    )
    return {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _assert_child_lineage(db, *, parcel_id: int, source_id: str) -> None:
    for table in ("parcel_alias", "parcel_address", "assessment", "sale_event"):
        source_ids = {
            row["source_id"]
            for row in db.execute(
                f"SELECT source_id FROM {table} WHERE parcel_id=?",
                (parcel_id,),
            ).fetchall()
        }
        assert source_id in source_ids
    instrument_source_ids = {
        row["source_id"]
        for row in db.execute(
            """
            SELECT ri.source_id
            FROM instrument_parcel ip
            JOIN recorded_instrument ri USING(instrument_id)
            WHERE ip.parcel_id=?
            """,
            (parcel_id,),
        ).fetchall()
    }
    assert source_id in instrument_source_ids
    assert (
        db.execute(
            "SELECT COUNT(*) FROM source_observation WHERE source_id=?",
            (source_id,),
        ).fetchone()[0]
        >= 1
    )


def test_ny_salesweb_shell_is_source_attributed_and_promoted_by_exact_join(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    salesweb = _ny_salesweb_envelope()
    statewide = _ny_statewide_envelope()

    first_sale = ingest_property_envelope(salesweb, db_path=db_path)
    shell_id = int(first_sale["records"][0]["parcel_id"])
    assert first_sale["records"][0]["parcel_placeholder_created"] == 1

    db = connect_property(db_path)
    try:
        shell = db.execute(
            "SELECT source_id, native_parcel_id FROM parcel_snapshot WHERE parcel_id=?",
            (shell_id,),
        ).fetchone()
        assert tuple(shell) == (
            NY_SALESWEB_SOURCE_ID,
            "01010041.00-2-12.7",
        )
        _assert_child_lineage(
            db,
            parcel_id=shell_id,
            source_id=NY_SALESWEB_SOURCE_ID,
        )
    finally:
        db.close()

    promoted = ingest_property_envelope(statewide, db_path=db_path)
    projection = promoted["records"][0]
    assert projection["parcel_id"] == shell_id
    assert projection["parcel_shell_adopted"] == 1
    assert (
        projection["parcel_shell_source_id_adopted"]
        == NY_SALESWEB_SOURCE_ID
    )

    db = connect_property(db_path)
    try:
        promoted_row = db.execute(
            """
            SELECT parcel_id, source_id, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(promoted_row) == (
            shell_id,
            NY_STATEWIDE_SOURCE_ID,
            "01010000004100000002001270000000",
        )
        _assert_child_lineage(
            db,
            parcel_id=shell_id,
            source_id=NY_SALESWEB_SOURCE_ID,
        )
        counts_before_rerun = _table_counts(db)
    finally:
        db.close()

    assert (
        ingest_property_envelope(salesweb, db_path=db_path)["records"][0][
            "parcel_placeholder_created"
        ]
        == 0
    )
    assert (
        ingest_property_envelope(statewide, db_path=db_path)["records"][0][
            "parcel_shell_adopted"
        ]
        == 0
    )
    db = connect_property(db_path)
    try:
        assert _table_counts(db) == counts_before_rerun
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
    finally:
        db.close()


def test_nj_sr1a_shell_is_source_attributed_and_promoted_without_relabeling(
    tmp_path,
):
    db_path = tmp_path / "property.db"
    sr1a = _nj_sr1a_envelope()
    statewide = _nj_statewide_envelope()

    first_sale = ingest_property_envelope(sr1a, db_path=db_path)
    assert first_sale["records"][0]["parcel_placeholders_created"] == 1

    db = connect_property(db_path)
    try:
        shell_id = int(
            db.execute(
                "SELECT parcel_id FROM parcel_snapshot WHERE native_parcel_id=?",
                ("0703_14_6",),
            ).fetchone()[0]
        )
        shell = db.execute(
            "SELECT source_id, native_parcel_id FROM parcel_snapshot WHERE parcel_id=?",
            (shell_id,),
        ).fetchone()
        assert tuple(shell) == (NJ_SR1A_SOURCE_ID, "0703_14_6")
        _assert_child_lineage(
            db,
            parcel_id=shell_id,
            source_id=NJ_SR1A_SOURCE_ID,
        )
    finally:
        db.close()

    promoted = ingest_property_envelope(statewide, db_path=db_path)
    projection = promoted["records"][0]
    assert projection["parcel_id"] == shell_id
    assert projection["parcel_shell_adopted"] == 1
    assert projection["parcel_shell_source_id_adopted"] == NJ_SR1A_SOURCE_ID

    db = connect_property(db_path)
    try:
        promoted_row = db.execute(
            """
            SELECT parcel_id, source_id, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchone()
        assert tuple(promoted_row) == (
            shell_id,
            NJ_STATEWIDE_SOURCE_ID,
            "0703_14_6",
        )
        _assert_child_lineage(
            db,
            parcel_id=shell_id,
            source_id=NJ_SR1A_SOURCE_ID,
        )
        counts_before_rerun = _table_counts(db)
    finally:
        db.close()

    assert (
        ingest_property_envelope(sr1a, db_path=db_path)["records"][0][
            "parcel_placeholders_created"
        ]
        == 0
    )
    assert (
        ingest_property_envelope(statewide, db_path=db_path)["records"][0][
            "parcel_shell_adopted"
        ]
        == 0
    )
    db = connect_property(db_path)
    try:
        assert _table_counts(db) == counts_before_rerun
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
    finally:
        db.close()
