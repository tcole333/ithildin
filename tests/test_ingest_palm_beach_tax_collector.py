from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools import query_palm_beach_property_appraiser as papa
from tools import query_palm_beach_tax_collector as tax
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_property


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "palm_beach_tax_collector"
)
PAPA_FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "palm_beach_property_appraiser"
)


def _json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _envelope(*records: dict[str, Any]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=tax.SOURCE_METADATA,
        jurisdiction=tax.JURISDICTION,
        query=QueryMetadata(
            operation="test_tax_account_lifecycle",
            parameters={"pcn": tax.SENTINEL_PCN},
        ),
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _records() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    settings = tax.parse_search_settings(_json("search-settings.json"))
    rows, total = tax.parse_search_page(_json("search-exact.json"))
    search = tax.normalize_search_result(
        rows[0],
        criteria=tax.SENTINEL_PCN,
        native_page=1,
        native_row=1,
        settings=settings,
        source_reported_total=total,
    )
    account = tax.normalize_account(
        pcn=tax.SENTINEL_PCN,
        alternate_key="1081671",
        sections={
            462: _json("account-462.json"),
            465: _json("account-465.json"),
        },
    )
    bill = next(
        record
        for record in tax.normalize_bills(
            _json("bills.json"),
            pcn=tax.SENTINEL_PCN,
            alternate_key="1081671",
        )
        if record["tax_year"] == "2018"
    )
    payment = tax.normalize_payment(
        _json("payment-page.json")["Data"][0],
        pcn=tax.SENTINEL_PCN,
        alternate_key="1081671",
        native_page=1,
        native_row=1,
    )
    return search, account, bill, payment


def _papa_record() -> dict[str, Any]:
    metadata = json.loads(
        (PAPA_FIXTURE_DIR / "metadata.json").read_text(encoding="utf-8")
    )
    features = json.loads(
        (PAPA_FIXTURE_DIR / "features.json").read_text(encoding="utf-8")
    )
    return papa.normalize_feature(
        features[0],
        contract=papa.metadata_contract(metadata),
        geometry_requested=True,
    )


def _papa_envelope(record: dict[str, Any]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=papa.SOURCE_METADATA,
        jurisdiction=papa.JURISDICTION,
        query=QueryMetadata(
            operation="test_exact_pcn_shell_adoption",
            parameters={"pcn": tax.SENTINEL_PCN},
        ),
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:05:00Z",
    ).to_dict()


def test_tax_account_bill_and_payment_project_without_identity_conflation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    search, account, bill, payment = _records()

    summary = ingest_property_envelope(
        _envelope(search, account, bill, payment),
        db_path=db_path,
    )

    assert summary["projection_supported"] is True
    assert summary["records_seen"] == 4
    assert summary["records_ingested"] == 3
    assert summary["records_preserved_without_projection"] == 1
    assert summary["projection_skips"][0]["record_kind"] == (
        "tax_account_search_result"
    )
    assert {
        result["source_occurrence_id"] for result in summary["records"]
    } == {
        account["source_occurrence_id"],
        bill["source_occurrence_id"],
        payment["source_occurrence_id"],
    }
    assert next(
        result
        for result in summary["records"]
        if result["source_occurrence_id"] == payment["source_occurrence_id"]
    )["payer_projected_as_owner"] is False

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT native_parcel_id, roll_year
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (tax.SOURCE_ID,),
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            (tax.SENTINEL_PCN, "")
        ]

        aliases = db.execute(
            """
            SELECT alias_type, alias_value
            FROM parcel_alias
            WHERE source_id=?
            ORDER BY alias_type
            """,
            (tax.SOURCE_ID,),
        ).fetchall()
        assert [tuple(row) for row in aliases] == [
            ("palm_beach_formatted_pcn", "04-36-43-25-00-000-5040"),
            ("pbc_tax_account_alternate_key", "1081671"),
        ]

        owners = db.execute(
            """
            SELECT assertion_type, raw_owner_name
            FROM ownership_assertion
            WHERE source_id=?
            """,
            (tax.SOURCE_ID,),
        ).fetchall()
        assert [tuple(row) for row in owners] == [
            ("tax_account", "PRIEST DANNY")
        ]
        assert all(row["raw_owner_name"] != "ACME ESCROW LLC" for row in owners)

        events = db.execute(
            """
            SELECT event_type, event_date, native_event_id, amount_minor, raw_json
            FROM tax_account_event
            WHERE source_id=?
            ORDER BY event_type
            """,
            (tax.SOURCE_ID,),
        ).fetchall()
        assert [
            (row["event_type"], row["event_date"])
            for row in events
        ] == [
            ("property_tax_installment_snapshot", None),
            ("property_tax_payment", "2024-11-15"),
            ("tax_account_snapshot", None),
        ]
        bill_event = next(
            row
            for row in events
            if row["event_type"] == "property_tax_installment_snapshot"
        )
        assert bill_event["amount_minor"] == 115000
        assert "LANDS AVALABLE-TAXES HAVE BEEN OMITTED" in (
            bill_event["raw_json"]
        )
        payment_event = next(
            row for row in events if row["event_type"] == "property_tax_payment"
        )
        payment_raw = json.loads(payment_event["raw_json"])
        assert payment_raw["payer_observation"] == {
            "raw_name": "ACME ESCROW LLC",
            "role": "source_observed_payer",
            "owner_or_title_role": False,
            "masked": False,
        }
        assert payment_event["amount_minor"] == 123456

        observations = db.execute(
            """
            SELECT record_kind
            FROM source_observation
            WHERE source_id=? AND record_kind!='query_envelope'
            ORDER BY record_kind
            """,
            (tax.SOURCE_ID,),
        ).fetchall()
        assert [row["record_kind"] for row in observations] == [
            "property_tax_account_snapshot",
            "property_tax_bill_snapshot",
            "property_tax_payment",
            "tax_account_search_result",
        ]
    finally:
        db.close()


def test_exact_papa_record_adopts_tax_shell_and_preserves_source_children(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    _search, account, bill, payment = _records()
    ingest_property_envelope(
        _envelope(account, bill, payment),
        db_path=db_path,
    )

    db = connect_property(db_path)
    try:
        shell = db.execute(
            """
            SELECT parcel_id, source_id
            FROM parcel_snapshot
            WHERE native_parcel_id=?
            """,
            (tax.SENTINEL_PCN,),
        ).fetchone()
        shell_parcel_id = int(shell["parcel_id"])
        assert shell["source_id"] == tax.SOURCE_ID
    finally:
        db.close()

    papa_summary = ingest_property_envelope(
        _papa_envelope(_papa_record()),
        db_path=db_path,
    )
    papa_result = papa_summary["records"][0]
    assert papa_result["parcel_id"] == shell_parcel_id
    assert papa_result["parcel_shells_adopted"] == 1
    assert papa_result["parcel_shells_repointed"] == 0
    assert papa_result["parcel_shell_source_ids_adopted"] == [
        tax.SOURCE_ID
    ]

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id, roll_year
            FROM parcel_snapshot
            WHERE native_parcel_id=?
            """,
            (tax.SENTINEL_PCN,),
        ).fetchall()
        assert [tuple(row) for row in parcels] == [
            (shell_parcel_id, papa.SOURCE_ID, "")
        ]

        tax_child_parcel_ids = {
            int(row["parcel_id"])
            for row in db.execute(
                """
                SELECT parcel_id FROM tax_account_event WHERE source_id=?
                UNION
                SELECT parcel_id FROM ownership_assertion WHERE source_id=?
                UNION
                SELECT parcel_id FROM parcel_alias WHERE source_id=?
                """,
                (tax.SOURCE_ID, tax.SOURCE_ID, tax.SOURCE_ID),
            )
        }
        assert tax_child_parcel_ids == {shell_parcel_id}

        papa_projection = db.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM assessment
                 WHERE parcel_id=? AND source_id=?) AS assessments,
                (SELECT COUNT(*) FROM parcel_geometry
                 WHERE parcel_id=? AND source_id=?) AS geometries,
                (SELECT COUNT(*) FROM ownership_assertion
                 WHERE parcel_id=? AND source_id=?) AS owners
            """,
            (
                shell_parcel_id,
                papa.SOURCE_ID,
                shell_parcel_id,
                papa.SOURCE_ID,
                shell_parcel_id,
                papa.SOURCE_ID,
            ),
        ).fetchone()
        assert tuple(papa_projection) == (1, 1, 1)

        papa_addresses = db.execute(
            """
            SELECT address_role, raw_address
            FROM parcel_address
            WHERE parcel_id=? AND source_id=?
            ORDER BY address_role
            """,
            (shell_parcel_id, papa.SOURCE_ID),
        ).fetchall()
        assert [tuple(row) for row in papa_addresses] == [
            ("mailing", "EXAMPLE OWNER, PO BOX 100"),
            ("situs", "100 MAIN ST"),
        ]

        observation_sources = {
            row["source_id"]
            for row in db.execute(
                """
                SELECT DISTINCT source_id
                FROM source_observation
                WHERE source_id IN (?, ?)
                  AND record_kind!='query_envelope'
                """,
                (tax.SOURCE_ID, papa.SOURCE_ID),
            )
        }
        assert observation_sources == {tax.SOURCE_ID, papa.SOURCE_ID}
    finally:
        db.close()
