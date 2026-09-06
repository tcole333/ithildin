from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools import query_orange_tax_collector as orange
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


ACCOUNT = "012027000000001"
FORMATTED_ACCOUNT = "01-20-27-0000-00001"
TOKEN = "orange-taxsys-account-token"
BILL_UUID = "ca0e3d54-aad7-11f0-bb75-005056815849"
DETAIL_BILL_UUID = "da0e3d54-aad7-11f0-bb75-005056815849"


def _parcel_join(*, exact: bool = True) -> dict[str, Any]:
    return {
        "normalized_15_digit_account": ACCOUNT,
        "formatted_account": FORMATTED_ACCOUNT,
        "exact": exact,
    }


def _envelope(*records: dict[str, Any]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=orange.SOURCE_METADATA,
        jurisdiction=orange.JURISDICTION,
        query=QueryMetadata(
            operation="test_orange_tax_ingestion",
            parameters={"account": ACCOUNT},
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _records() -> list[dict[str, Any]]:
    return [
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "historical_bulk_manifest",
            "release_id": "orange-current-tax-roll-2020-02-17",
            "publication_state": "fixed_historical_snapshot",
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "property_tax_bill_history",
            "parcel_join": _parcel_join(exact=False),
            "bill_uuid": "ba0e3d54-aad7-11f0-bb75-005056815849",
            "status": {"raw": "Open", "retrieved_state": True},
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "property_tax_account_search_hit",
            "canonical_ref": "property:orange:account",
            "parcel_join": _parcel_join(),
            "native_account_id": FORMATTED_ACCOUNT,
            "algolia_object_id": (
                "/Taxsys-GovHub/v0/items/"
                "orange:real_estate:parents:"
                "54c5c30a-d853-11ef-b1f9-cf6e57f2283b"
            ),
            "taxsys_account_token": TOKEN,
            "owners": [
                {
                    "name": "SEARCH OWNER",
                    "assertion_type": "tax_account_owner_label",
                }
            ],
            "situs_entities": [
                {
                    "address": "100 MAIN ST",
                    "city": "ORLANDO",
                    "state": "FL",
                    "zip": "32801",
                    "country": "US",
                }
            ],
            "billing_entities": [
                {
                    "address": "PO BOX 100",
                    "city": "ORLANDO",
                    "state": "FL",
                    "zip": "32802",
                    "country": "US",
                }
            ],
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "property_tax_bill_history",
            "canonical_ref": f"property:orange:bill:{BILL_UUID}",
            "parcel_join": _parcel_join(),
            "taxsys_account_token": TOKEN,
            "bill_uuid": BILL_UUID,
            "tax_year": 2024,
            "balance_due": {
                "raw": "$0.00",
                "decimal": "0.00",
                "currency": "USD",
            },
            "status": {
                "raw": "Paid",
                "amount_raw": "$2,500.00",
                "amount_decimal": "2500.00",
                "retrieved_state": True,
            },
            "payment": {
                "date": {"raw": "11/15/2024", "iso": "2024-11-15T00:00:00"},
                "receipt_number": "R-2024-100",
                "occurrence_key": [BILL_UUID, "R-2024-100", "11/15/2024"],
            },
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "property_tax_certificate_history",
            "parcel_join": _parcel_join(),
            "taxsys_account_token": TOKEN,
            "bill_uuid": BILL_UUID,
            "certificate_number": "CERT-HISTORY-1",
            "certificate_status": "Redeemed",
            "status_date": {"raw": "03/01/2025", "iso": "2025-03-01T00:00:00"},
            "face_value": {
                "raw": "$2,400.00",
                "decimal": "2400.00",
                "currency": "USD",
            },
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "property_tax_bill_detail",
            "parcel_join": _parcel_join(),
            "native_account_id": FORMATTED_ACCOUNT,
            "taxsys_account_token": TOKEN,
            "bill_uuid": DETAIL_BILL_UUID,
            "tax_year": 2023,
            "owners": [
                {
                    "raw_name": "DETAIL OWNER",
                    "role": "published_tax_account_owner",
                }
            ],
            "mailing_address": {"raw": "200 OAK AVE, ORLANDO FL 32803"},
            "situs_address": {"raw": "300 PINE ST, ORLANDO FL 32804"},
            "amount_due": {
                "raw": "$125.50",
                "decimal": "125.50",
                "currency": "USD",
                "retrieved_state": True,
            },
            "status": {"raw": "Open", "retrieved_state": True},
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "historical_current_tax_roll_row",
            "publication_date": "2020-02-17",
            "publication_state": "fixed_historical_snapshot",
            "parcel_join": _parcel_join(),
            "native_parcel_number": FORMATTED_ACCOUNT,
            "tax_summary_id": "SUMMARY-CURRENT-1",
            "tax_year": 2019,
            "status_code": "PAID",
            "owners": [{"raw_name": "HISTORICAL ROLL OWNER"}],
            "values": {
                "total": {"raw": "100000", "decimal": "100000"},
                "exempt": {"raw": "25000", "decimal": "25000"},
                "taxable": {"raw": "75000", "decimal": "75000"},
            },
            "tax": {
                "balance_due": {"raw": "0", "decimal": "0"},
                "amount_paid": {"raw": "2500", "decimal": "2500"},
            },
            "payment": {
                "date": {"raw": "11/15/2019", "iso": "2019-11-15T00:00:00"},
                "validation_number": "VALID-CURRENT-1",
                "paid_by_label": "CURRENT ROLL PAYER",
            },
            "identity_contract": {
                "tax_summary_id": "SUMMARY-CURRENT-1",
                "payment_validation_number": "VALID-CURRENT-1",
                "row_occurrence": {
                    "artifact_sha256": "a" * 64,
                    "archive_member_path": "TaxPaymentTape.txt",
                    "source_row_number": 20,
                    "occurrence_id": "current-row-occurrence",
                },
            },
            "raw": {
                "TaxSummaryId": "SUMMARY-CURRENT-1",
                "ValidationNumber": "VALID-CURRENT-1",
            },
        },
        {
            "source_id": orange.SOURCE_ID,
            "record_kind": "historical_delinquent_tax_roll_row",
            "publication_date": "2020-02-17",
            "publication_state": "fixed_historical_snapshot",
            "parcel_join": _parcel_join(),
            "native_parcel_number": FORMATTED_ACCOUNT,
            "tax_summary_id": "SUMMARY-DELINQUENT-1",
            "tax_year": 2018,
            "status_code": "DELINQUENT",
            "tax_deed_status": "APPLIED",
            "owners": [{"raw_name": "DELINQUENT ROLL OWNER"}],
            "buyers": [{"raw_name": "CERTIFICATE BUYER"}],
            "values": {
                "total": {"raw": "90000", "decimal": "90000"},
                "exempt": {"raw": "10000", "decimal": "10000"},
                "taxable": {"raw": "80000", "decimal": "80000"},
            },
            "tax": {
                "payoff_due": {"raw": "3500", "decimal": "3500"},
            },
            "payment": {
                "payment_date": {
                    "raw": "04/01/2020",
                    "iso": "2020-04-01T00:00:00",
                },
                "payment_code": "REDEEMED",
                "validation_number": "VALID-DELINQUENT-1",
            },
            "certificate": {
                "year": 2019,
                "number": "CERT-BULK-1",
                "sequence": 2,
                "face_value": {"raw": "3000", "decimal": "3000"},
                "issue_date": {
                    "raw": "06/01/2019",
                    "iso": "2019-06-01T00:00:00",
                },
                "purchase_date": {
                    "raw": "06/02/2019",
                    "iso": "2019-06-02T00:00:00",
                },
                "bidder_number": "BID-9",
            },
            "tax_deed": {
                "year": 2020,
                "number": "TD-8",
                "sequence": 1,
                "status": "APPLIED",
                "application_date": {
                    "raw": "05/01/2020",
                    "iso": "2020-05-01T00:00:00",
                },
                "redemption_date": {"raw": None, "iso": None},
            },
            "identity_contract": {
                "certificate": {
                    "year": 2019,
                    "number": "CERT-BULK-1",
                    "sequence": 2,
                },
                "tax_deed": {"year": 2020, "number": "TD-8", "sequence": 1},
                "tax_summary_id": "SUMMARY-DELINQUENT-1",
                "payment_validation_number": "VALID-DELINQUENT-1",
                "row_occurrence": {
                    "artifact_sha256": "b" * 64,
                    "archive_member_path": "DelinquentRealEstate.txt",
                    "source_row_number": 30,
                    "occurrence_id": "delinquent-row-occurrence",
                },
            },
            "raw": {
                "TaxSummaryID": "SUMMARY-DELINQUENT-1",
                "Validation No": "VALID-DELINQUENT-1",
                "Buyer Name1": "CERTIFICATE BUYER",
            },
        },
    ]


def test_orange_rows_preserve_occurrences_and_project_tax_lineage(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    artifact_path = tmp_path / "TaxPaymentTape.zip"
    artifact_bytes = b"PK\x03\x04orange-tax-fixture"
    artifact_path.write_bytes(artifact_bytes)

    summary = ingest_property_envelope(
        _envelope(*_records()),
        db_path=db_path,
        raw_artifact_path=artifact_path,
    )

    assert summary["projection_supported"] is True
    assert summary["records_seen"] == 8
    assert summary["records_ingested"] == 6
    assert summary["records_preserved_without_projection"] == 2
    assert {skip["reason"] for skip in summary["projection_skips"]} == {
        "orange_tax_metadata_or_transport_observation",
        "orange_tax_record_lacks_exact_15_digit_parcel_join",
    }
    assert {
        record["parcel_anchor_source_id"] for record in summary["records"]
    } == {orange.SOURCE_ID}

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            WHERE native_parcel_id=?
            """,
            (ACCOUNT,),
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            (orange.SOURCE_ID, "12095", ACCOUNT, "")
        ]

        owners = db.execute(
            """
            SELECT raw_owner_name
            FROM ownership_assertion
            WHERE source_id=?
            ORDER BY raw_owner_name
            """,
            (orange.SOURCE_ID,),
        ).fetchall()
        assert [row["raw_owner_name"] for row in owners] == [
            "DETAIL OWNER",
            "SEARCH OWNER",
        ]
        assert not {
            "CURRENT ROLL PAYER",
            "CERTIFICATE BUYER",
            "HISTORICAL ROLL OWNER",
            "DELINQUENT ROLL OWNER",
        } & {row["raw_owner_name"] for row in owners}

        addresses = db.execute(
            """
            SELECT address_role, raw_address
            FROM parcel_address
            WHERE source_id=?
            ORDER BY address_role, raw_address
            """,
            (orange.SOURCE_ID,),
        ).fetchall()
        assert [(row["address_role"], row["raw_address"]) for row in addresses] == [
            ("mailing", "200 OAK AVE, ORLANDO FL 32803"),
            ("mailing", "PO BOX 100"),
            ("situs", "100 MAIN ST"),
            ("situs", "300 PINE ST, ORLANDO FL 32804"),
        ]

        events = db.execute(
            """
            SELECT event_type, native_event_id, event_date, amount_minor, raw_json
            FROM tax_account_event
            WHERE source_id=?
            ORDER BY tax_event_id
            """,
            (orange.SOURCE_ID,),
        ).fetchall()
        assert len(events) == 10
        native_event_ids = {row["native_event_id"] for row in events}
        assert {
            BILL_UUID,
            "R-2024-100",
            "CERT-HISTORY-1",
            DETAIL_BILL_UUID,
            "current-row-occurrence",
            "VALID-CURRENT-1",
            "delinquent-row-occurrence",
            "VALID-DELINQUENT-1",
            "CERT-BULK-1",
            "2020:TD-8:1",
        } == native_event_ids
        assert {
            row["event_type"] for row in events
        } >= {"tax_certificate_state", "tax_deed_state", "property_tax_payment"}
        payment = next(
            row
            for row in events
            if row["native_event_id"] == "VALID-CURRENT-1"
        )
        assert payment["event_date"] == "2019-11-15"
        assert payment["amount_minor"] == 250000
        assert json.loads(payment["raw_json"])["payment"][
            "paid_by_label"
        ] == "CURRENT ROLL PAYER"

        assessments = db.execute(
            """
            SELECT tax_year, total_value_minor, exempt_value_minor, raw_json
            FROM assessment
            WHERE source_id=?
            ORDER BY tax_year
            """,
            (orange.SOURCE_ID,),
        ).fetchall()
        assert [
            (
                row["tax_year"],
                row["total_value_minor"],
                row["exempt_value_minor"],
                json.loads(row["raw_json"])["taxable_value_decimal"],
            )
            for row in assessments
        ] == [
            ("2018", 9000000, 1000000, "80000"),
            ("2019", 10000000, 2500000, "75000"),
        ]

        assert (
            db.execute(
                "SELECT COUNT(*) FROM recorded_instrument WHERE source_id=?",
                (orange.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )

        observations = db.execute(
            """
            SELECT record_kind, source_native_id, raw_artifact_path,
                   raw_artifact_sha256, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind!='query_envelope'
            """,
            (orange.SOURCE_ID,),
        ).fetchall()
        assert len(observations) == 8
        assert {
            row["record_kind"] for row in observations
        } == {record["record_kind"] for record in _records()}
        assert {
            row["raw_artifact_path"] for row in observations
        } == {str(artifact_path.resolve())}
        assert {
            row["raw_artifact_sha256"] for row in observations
        } == {hashlib.sha256(artifact_bytes).hexdigest()}
        search_observation = next(
            row
            for row in observations
            if row["record_kind"] == "property_tax_account_search_hit"
        )
        search_raw = json.loads(search_observation["raw_json"])
        assert search_raw["algolia_object_id"] == (
            search_observation["source_native_id"]
        )
        assert search_raw["taxsys_account_token"] == TOKEN
    finally:
        db.close()


def test_shared_orange_ingest_passes_the_local_zip_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_path = tmp_path / "TaxPaymentTape.zip"
    captured: dict[str, Any] = {}
    result = PublicRecordsResult.success(
        PublicRecordsQuery(
            source=orange.SOURCE_METADATA,
            jurisdiction=orange.JURISDICTION,
            query=QueryMetadata(operation="search"),
        ),
        [],
        retrieved_at="2026-07-30T12:00:00Z",
    )

    monkeypatch.setattr(
        query_property,
        "_live_result",
        lambda _args: (result, True),
    )

    def fake_ingest(
        envelope: dict[str, Any],
        *,
        db_path: str,
        raw_artifact_path: str | None,
    ) -> dict[str, Any]:
        captured.update(
            {
                "envelope": envelope,
                "db_path": db_path,
                "raw_artifact_path": raw_artifact_path,
            }
        )
        return {"status": "ok"}

    monkeypatch.setattr(query_property, "ingest_property_envelope", fake_ingest)
    args = query_property.build_parser().parse_args(
        [
            "search",
            ACCOUNT,
            "--source",
            orange.SOURCE_ID,
            "--artifact-path",
            str(artifact_path),
            "--dataset-type",
            "current",
            "--property-db",
            str(tmp_path / "property.db"),
            "--ingest",
        ]
    )

    payload = query_property.execute(args)

    assert payload["ingest"] == {"status": "ok"}
    assert captured["raw_artifact_path"] == str(artifact_path)
