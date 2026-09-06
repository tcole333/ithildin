from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import query_washington_taxsifter as taxsifter
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)


SOURCE_ID = "us-wa-adams-county-taxsifter"
COUNTY_GEOID = "53001"
PARCEL = "2038010000001"


def _occurrence(key_id: str = "593482") -> dict[str, str]:
    return {
        "source_id": SOURCE_ID,
        "key_id": key_id,
        "type_id": "1",
        "native_id": f"keyId={key_id};typeID=1",
    }


def _join() -> dict[str, str]:
    return {
        "county_geoid": COUNTY_GEOID,
        "parcel_number": PARCEL,
    }


def _provenance(lineage_id: str) -> dict[str, Any]:
    return {
        "source_id": SOURCE_ID,
        "lineage_id": lineage_id,
        "data_current_as": "7/29/2026 3:37 PM",
        "roll_year": "2027",
    }


def _sale(
    *,
    sale_date: str,
    document: str,
    excise: str,
    price: int,
) -> dict[str, Any]:
    return {
        "parcel_number": PARCEL,
        "sale_date_iso": sale_date,
        "sale_document": document,
        "excise_number": excise,
        "grantor": "HERCULES RANCH LP",
        "grantee": "HERCULES RANCH LLC",
        "price_money": {"amount": price, "currency": "USD"},
        "recording_join": {
            "lineage_id": taxsifter.RECORDER_LINEAGE,
            "relationship": "recorded_instrument_candidate",
            "instrument_number": document,
            "excise_number": excise,
            "recording_date": sale_date,
        },
    }


def _bundle() -> dict[str, Any]:
    occurrence = _occurrence()
    parcel_join = _join()
    assessor_sale = _sale(
        sale_date="2017-02-07",
        document="3201334",
        excise="100299",
        price=275_000,
    )
    search_sale = _sale(
        sale_date="2012-10-31",
        document="WD-302329",
        excise="28671",
        price=250_000,
    )
    _, search_sale_identity = taxsifter._sale_identity(search_sale)
    assessor = {
        "canonical_ref": "taxsifter:assessor-account",
        "evidence_ref": "taxsifter:assessor-account",
        "source_id": SOURCE_ID,
        "source_url": "https://example.test/Assessor.aspx",
        "record_kind": "assessor_property_account",
        "county_geoid": COUNTY_GEOID,
        "native_parcel_id": PARCEL,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "parcel": {
            "parcel_number": PARCEL,
            "owner_name": "HERCULES RANCH LLC",
            "mailing_address": {
                "raw": "P O BOX 324, SPRAGUE WA 99032",
                "city": "SPRAGUE",
                "state": "WA",
                "postal_code": "99032",
            },
            "situs_address": "123 TEST ROAD",
            "map_number": "203801",
        },
        "market_value": {
            "tax_year": "2027",
            "fields": {
                "land": {"amount": 100_000, "currency": "USD"},
                "improvements": {"amount": 271_800, "currency": "USD"},
                "total": {"amount": 371_800, "currency": "USD"},
            },
        },
        "taxable_value": {
            "tax_year": "2027",
            "fields": {
                "total": {"amount": 340_000, "currency": "USD"},
            },
        },
        "assessment_data": {"district": "21 - EXAMPLE"},
        "ownership": [
            {
                "owner_s_name": "HERCULES RANCH LLC",
                "ownership": "100%",
            }
        ],
        "valuation_history": [
            {
                "year": "2026",
                "land_money": {"amount": 95_000, "currency": "USD"},
                "impr_money": {"amount": 250_000, "currency": "USD"},
                "total_money": {"amount": 345_000, "currency": "USD"},
                "taxable_money": {"amount": 320_000, "currency": "USD"},
            }
        ],
        "sales_history": [assessor_sale],
        "building_permits": [{"permit_no": "EX-1"}],
        "provenance": _provenance(taxsifter.ASSESSOR_LINEAGE),
    }
    treasurer = {
        "canonical_ref": "taxsifter:treasurer-account",
        "evidence_ref": "taxsifter:treasurer-account",
        "source_id": SOURCE_ID,
        "source_url": "https://example.test/Treasurer.aspx",
        "record_kind": "treasurer_tax_account",
        "county_geoid": COUNTY_GEOID,
        "native_parcel_id": PARCEL,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "tax_year": "2027",
        "current_tax_year": [
            {
                "type": "Real Property",
                "taxpayer": "HERCULES RANCH LLC",
                "statement": "20272038010000001",
                "gross_tax_money": {"amount": 1280.42, "currency": "USD"},
                "total_tax_money": {"amount": 133.25, "currency": "USD"},
            }
        ],
        "balances_due": [
            {
                "statementid": "603478",
                "taxpayer": "HERCULES RANCH LLC",
                "balance_s_due_money": {"amount": 68.12, "currency": "USD"},
                "interest_due_money": {"amount": 1.50, "currency": "USD"},
            }
        ],
        "payment_receipts": [
            {
                "receipt_number": "2027-419019",
                "receipt_date_iso": "2027-05-05",
                "total_paid_money": {"amount": 66.63, "currency": "USD"},
            }
        ],
        "statement_links": [],
        "provenance": _provenance(taxsifter.TREASURER_LINEAGE),
    }
    appraisal = {
        "canonical_ref": "taxsifter:appraisal-detail",
        "evidence_ref": "taxsifter:appraisal-detail",
        "source_id": SOURCE_ID,
        "source_url": "https://example.test/AppraisalDetails.aspx",
        "record_kind": "appraisal_detail",
        "county_geoid": COUNTY_GEOID,
        "native_parcel_id": PARCEL,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "sections": [
            {
                "id": "grdLand",
                "rows": [{"land_code": "Land60", "units": "440.00000000"}],
            }
        ],
        "provenance": _provenance(taxsifter.ASSESSOR_LINEAGE),
    }
    return {
        "canonical_ref": "taxsifter:bundle",
        "evidence_ref": "taxsifter:bundle",
        "source_id": SOURCE_ID,
        "source_url": "https://example.test/Assessor.aspx",
        "record_kind": "property_enrichment_bundle",
        "county_geoid": COUNTY_GEOID,
        "native_parcel_id": PARCEL,
        "account_occurrence": occurrence,
        "parcel_join": parcel_join,
        "representations": {
            "assessor": assessor,
            "treasurer": treasurer,
            "appraisal": appraisal,
            "permits": {
                "record_kind": "assessor_permit_section",
                "lineage_id": taxsifter.ASSESSOR_LINEAGE,
                "rows": assessor["building_permits"],
            },
            "sales": {
                "record_kind": "assessor_sales_search",
                "source_id": SOURCE_ID,
                "lineage_id": taxsifter.ASSESSOR_LINEAGE,
                "results": [
                    {
                        "sale": search_sale,
                        "sale_identity": search_sale_identity,
                    }
                ],
                "native_pagination": {
                    "state": taxsifter.SALES_PAGINATION_STATE,
                    "published_result_count": 75,
                    "returned_native_records": 20,
                    "current_response_exhaustive": False,
                    "continuation_verified": False,
                },
            },
        },
        "lineage_contract": {
            "assessor": {"lineage_id": taxsifter.ASSESSOR_LINEAGE},
            "treasurer": {"lineage_id": taxsifter.TREASURER_LINEAGE},
            "recorder": {"lineage_id": taxsifter.RECORDER_LINEAGE},
        },
    }


def _envelope(*records: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "public-records-result/1.0",
        "retrieved_at": "2026-07-30T12:00:00Z",
        "status": "ok",
        "query": {
            "source": {"source_id": SOURCE_ID},
            "fingerprint": "taxsifter-test-query",
        },
        "records": list(records),
        "next_cursor": None,
        "warnings": [],
        "errors": [],
    }


def _db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_bundle_projects_distinct_assessor_tax_value_and_sale_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"

    summary = ingest_property_envelope(_envelope(_bundle()), db_path=db_path)

    assert summary["records_ingested"] == 1
    record_summary = summary["records"][0]
    assert record_summary["account_occurrence_aliases_upserted"] == 1
    assert record_summary["tax_events_upserted"] == 3
    assert record_summary["appraisal_sections_preserved"] == 1

    db = _db(db_path)
    try:
        parcel = db.execute(
            """
            SELECT native_parcel_id, jurisdiction_geoid, source_good_through
            FROM parcel_snapshot
            """
        ).fetchone()
        assert dict(parcel) == {
            "native_parcel_id": PARCEL,
            "jurisdiction_geoid": COUNTY_GEOID,
            "source_good_through": "2026-07-29",
        }
        alias = db.execute(
            """
            SELECT alias_type, alias_value, source_id
            FROM parcel_alias
            WHERE alias_type='taxsifter_account_occurrence'
            """
        ).fetchone()
        assert dict(alias) == {
            "alias_type": "taxsifter_account_occurrence",
            "alias_value": "keyId=593482;typeID=1",
            "source_id": SOURCE_ID,
        }

        owner_rows = db.execute(
            """
            SELECT assertion_type, evidence_ref
            FROM ownership_assertion
            ORDER BY assertion_type
            """
        ).fetchall()
        assert {row["assertion_type"] for row in owner_rows} == {
            "assessment_roll",
            "tax_account",
        }
        assert {
            row["evidence_ref"]
            for row in owner_rows
            if row["assertion_type"] == "assessment_roll"
        } == {"taxsifter:assessor-account"}
        assert {
            row["evidence_ref"]
            for row in owner_rows
            if row["assertion_type"] == "tax_account"
        } == {"taxsifter:treasurer-account"}

        current_value = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor, total_value_minor,
                   market_value_minor, assessed_value_minor, source_good_through,
                   raw_json
            FROM assessment
            WHERE tax_year='2027'
            """
        ).fetchone()
        assert current_value["land_value_minor"] == 10_000_000
        assert current_value["improvement_value_minor"] == 27_180_000
        assert current_value["total_value_minor"] == 37_180_000
        assert current_value["market_value_minor"] == 37_180_000
        assert current_value["assessed_value_minor"] is None
        assert current_value["source_good_through"] == "2026-07-29"
        value_raw = json.loads(current_value["raw_json"])
        assert value_raw["taxable_value"] == 340_000
        assert value_raw["value_basis"] == "assessor_current_market_value"

        tax_rows = db.execute(
            """
            SELECT event_type, event_date, amount_minor, native_event_id, raw_json
            FROM tax_account_event
            ORDER BY event_type
            """
        ).fetchall()
        assert {row["event_type"] for row in tax_rows} == {
            "tax_balance",
            "tax_payment_receipt",
            "tax_statement",
        }
        by_type = {row["event_type"]: row for row in tax_rows}
        assert by_type["tax_balance"]["amount_minor"] == 6812
        assert by_type["tax_payment_receipt"]["amount_minor"] == 6663
        assert by_type["tax_payment_receipt"]["event_date"] == "2027-05-05"
        assert all(
            json.loads(row["raw_json"])["lineage_id"]
            == taxsifter.TREASURER_LINEAGE
            for row in tax_rows
        )

        sales = db.execute(
            """
            SELECT native_sale_id, derivation, instrument_id, raw_json
            FROM sale_event
            ORDER BY derivation
            """
        ).fetchall()
        assert {row["derivation"] for row in sales} == {
            "assessor_sale_history",
            "assessor_sales_search",
        }
        assert all(row["instrument_id"] is None for row in sales)
        assert all(
            json.loads(row["raw_json"])["lineage_id"]
            == taxsifter.ASSESSOR_LINEAGE
            for row in sales
        )
        assert db.execute("SELECT COUNT(*) FROM recorded_instrument").fetchone()[0] == 0

        raw_observation = db.execute(
            """
            SELECT raw_json
            FROM source_observation
            WHERE record_kind='property_enrichment_bundle'
            """
        ).fetchone()["raw_json"]
        assert taxsifter.SALES_PAGINATION_STATE in raw_observation
        assert '"current_response_exhaustive":false' in raw_observation
    finally:
        db.close()


def test_search_occurrences_do_not_collapse_on_shared_parcel_join(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"

    def search_record(key_id: str) -> dict[str, Any]:
        return {
            "canonical_ref": f"taxsifter:search:{key_id}",
            "evidence_ref": f"taxsifter:search:{key_id}",
            "source_id": SOURCE_ID,
            "source_url": "https://example.test/Search/Results.aspx",
            "record_kind": "property_search_result",
            "county_geoid": COUNTY_GEOID,
            "native_parcel_id": PARCEL,
            "parcel_number": PARCEL,
            "account_occurrence": _occurrence(key_id),
            "parcel_join": _join(),
            "provenance": _provenance(taxsifter.ASSESSOR_LINEAGE),
        }

    summary = ingest_property_envelope(
        _envelope(search_record("593482"), search_record("700001")),
        db_path=db_path,
    )

    assert summary["records_ingested"] == 2
    db = _db(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        aliases = db.execute(
            """
            SELECT alias_value
            FROM parcel_alias
            WHERE alias_type='taxsifter_account_occurrence'
            ORDER BY alias_value
            """
        ).fetchall()
        assert [row["alias_value"] for row in aliases] == [
            "keyId=593482;typeID=1",
            "keyId=700001;typeID=1",
        ]
        observations = db.execute(
            """
            SELECT source_id, source_native_id
            FROM source_observation
            WHERE record_kind='property_search_result'
            ORDER BY source_native_id
            """
        ).fetchall()
        assert [(row["source_id"], row["source_native_id"]) for row in observations] == [
            (SOURCE_ID, "keyId=593482;typeID=1"),
            (SOURCE_ID, "keyId=700001;typeID=1"),
        ]
    finally:
        db.close()


def test_direct_sales_use_stable_identity_and_keep_nonexhaustive_snapshot(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    sale = _sale(
        sale_date="2012-10-31",
        document="WD-302329",
        excise="28671",
        price=250_000,
    )
    native_id, identity = taxsifter._sale_identity(sale)
    record = {
        "canonical_ref": f"taxsifter:sale:{native_id}",
        "evidence_ref": f"taxsifter:sale:{native_id}",
        "source_id": SOURCE_ID,
        "source_url": "https://example.test/SalesSearch/SalesSearch.aspx",
        "record_kind": "assessor_sale_search_result",
        "county_geoid": COUNTY_GEOID,
        "native_parcel_id": PARCEL,
        "sale_identity": identity,
        "sale": sale,
        "provenance": _provenance(taxsifter.ASSESSOR_LINEAGE),
        "retrieval_snapshot": {
            "returned_records": 20,
            "native_pagination": {
                "state": taxsifter.SALES_PAGINATION_STATE,
                "published_result_count": 75,
                "returned_native_records": 20,
                "current_response_exhaustive": False,
                "continuation_verified": False,
            },
        },
    }
    envelope = _envelope(record)

    ingest_property_envelope(envelope, db_path=db_path)
    ingest_property_envelope(envelope, db_path=db_path)

    db = _db(db_path)
    try:
        sale_row = db.execute(
            """
            SELECT native_sale_id, derivation, instrument_id
            FROM sale_event
            """
        ).fetchone()
        assert dict(sale_row) == {
            "native_sale_id": native_id,
            "derivation": "assessor_sales_search",
            "instrument_id": None,
        }
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 1
        observations = db.execute(
            """
            SELECT raw_json
            FROM source_observation
            WHERE record_kind='assessor_sale_search_result'
            """
        ).fetchall()
        assert len(observations) == 2
        assert all(
            taxsifter.SALES_PAGINATION_STATE in row["raw_json"]
            for row in observations
        )
    finally:
        db.close()


def test_bundle_rejects_county_or_account_drift(tmp_path: Path) -> None:
    bundle = _bundle()
    bundle["representations"]["treasurer"]["account_occurrence"] = _occurrence(
        "999999"
    )

    with pytest.raises(
        PropertyIngestError,
        match="representations identify different accounts",
    ):
        ingest_property_envelope(
            _envelope(bundle),
            db_path=tmp_path / "property.db",
        )
