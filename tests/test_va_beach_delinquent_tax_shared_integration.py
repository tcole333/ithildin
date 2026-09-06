from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import query_property
from tools import query_va_beach_delinquent_tax as va_tax
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_DIR = Path("tests/fixtures/public_records/va_beach_delinquent_tax")
LAYER = json.loads((FIXTURE_DIR / "layer.json").read_text(encoding="utf-8"))
PAGE_1 = json.loads(
    (FIXTURE_DIR / "page_1.json").read_text(encoding="utf-8")
)


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _normalized_installments() -> list[dict]:
    snapshot = va_tax.inspect_layer_metadata(LAYER)
    first_feature = copy.deepcopy(PAGE_1["features"][0])
    second_feature = copy.deepcopy(first_feature)
    second_feature["attributes"]["OBJECTID"] = 99
    second_feature["attributes"]["Installment"] = "1"
    return [
        va_tax.normalize_feature(first_feature, snapshot=snapshot),
        va_tax.normalize_feature(second_feature, snapshot=snapshot),
    ]


def _envelope(records: list[dict] | None = None) -> dict:
    query = va_tax.build_query(
        "parcel",
        va_tax.SearchCriteria(gpin="14469645070000"),
        limit=None,
        cursor=None,
    )
    return PublicRecordsResult.success(
        query,
        records if records is not None else _normalized_installments(),
        retrieved_at="2026-07-30T22:24:07Z",
        warnings=va_tax.SOURCE_WARNINGS,
    ).to_dict()


def test_shared_routes_and_guidance_preserve_source_roles() -> None:
    routes = query_property.LIVE_ROUTES[va_tax.SOURCE_ID]
    guidance = query_property._source_guidance(va_tax.SOURCE_ID)

    assert sorted(routes) == [
        "address",
        "discovery",
        "event",
        "owner",
        "parcel",
        "probe",
        "search",
    ]
    assert guidance["record_identity"] == [
        "bill_number",
        "installment",
        "GPIN",
        "tax_year",
    ]
    assert guidance["parcel_join"] == (
        "GPIN within Virginia Beach GEOID 51810"
    )
    complement_roles = {
        route["role"] for route in guidance["official_complements"]
    }
    assert complement_roles == {
        "current_tax_account_detail_and_payment_history",
        "assessment_and_current_owner_context",
        "recorded_deeds_judgments_and_ucc",
        "circuit_court_case_index",
        "general_district_court_case_index",
        "tax_sale_notices_and_auction_links",
    }
    assert "occurrence key remains separate" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "selector", "adapter_command"),
    (
        ("search", "NOVAK", "search"),
        ("owner", "NOVAK", "owner"),
        ("address", "SHERRY AVE", "address"),
        ("parcel", "14469645070000", "parcel"),
        ("event", "1125000027", "bill"),
    ),
)
def test_shared_selectors_translate_without_an_implicit_result_cap(
    operation: str,
    selector: str,
    adapter_command: str,
) -> None:
    route = query_property.LIVE_ROUTES[va_tax.SOURCE_ID][operation]
    translated = route.translate(
        _parse(
            operation,
            selector,
            "--source",
            va_tax.SOURCE_ID,
            "--jurisdiction",
            "51810",
            "--tax-year",
            "2025",
            "--page-size",
            "37",
        ),
        route.adapter_command,
    )

    assert translated.command == adapter_command
    assert translated.query == selector
    assert translated.tax_year == 2025
    assert translated.limit is None
    assert translated.page_size == 37


def test_shared_search_field_limit_and_cursor_reach_native_semantics() -> None:
    route = query_property.LIVE_ROUTES[va_tax.SOURCE_ID]["search"]
    translated = route.translate(
        _parse(
            "search",
            "1125000027",
            "--source",
            va_tax.SOURCE_ID,
            "--search-field",
            "bill",
            "--limit",
            "9",
            "--max-records",
            "4",
            "--cursor",
            "va-beach-delinquent-tax:v1:cursor",
        ),
        route.adapter_command,
    )

    assert translated.command == "bill"
    assert translated.query == "1125000027"
    assert translated.limit == 4
    assert translated.cursor == "va-beach-delinquent-tax:v1:cursor"


def test_shared_execute_passes_the_reviewed_catalog_decision(
    monkeypatch,
) -> None:
    decision = {
        "allowed": True,
        "reason_code": "automated_access_supported",
        "limits": {"maximum_page_size": 250},
    }
    observed = {}

    class FakeCatalog:
        def __init__(self, _path):
            pass

        def show_source(self, source_id):
            assert source_id == va_tax.SOURCE_ID
            return {"source_id": source_id}

        def machine_acquisition_decision(self, source_id):
            assert source_id == va_tax.SOURCE_ID
            return decision

    def fake_execute(args, *, access_decision=None, **_kwargs):
        observed["args"] = args
        observed["access_decision"] = access_decision
        result = PublicRecordsResult.success(
            va_tax.build_query(
                args.command,
                va_tax._criteria_from_args(args),
                limit=args.limit,
                cursor=args.cursor,
            ),
            [_normalized_installments()[0]],
            retrieved_at="2026-07-30T22:24:07Z",
        )
        observed["expected"] = result.to_dict()
        return result

    monkeypatch.setattr(query_property, "PublicRecordsCatalog", FakeCatalog)
    monkeypatch.setattr(va_tax, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "event",
            "1125000027",
            "--source",
            va_tax.SOURCE_ID,
            "--tax-year",
            "2025",
        )
    )

    assert observed["args"].command == "bill"
    assert observed["args"].tax_year == 2025
    assert observed["access_decision"] is decision
    assert payload == observed["expected"]


def test_sidecar_keeps_installment_occurrences_separate_from_the_gpin_join(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    envelope = _envelope()

    first = ingest_property_envelope(envelope, db_path=db_path)
    second = ingest_property_envelope(envelope, db_path=db_path)

    assert first["records_ingested"] == 2
    assert second["records_ingested"] == 2
    assert {
        record["native_event_id"] for record in first["records"]
    } == {
        "1125000027:1:14469645070000:2025",
        "1125000027:2:14469645070000:2025",
    }
    assert {
        record["parcel_join_gpin"] for record in first["records"]
    } == {"14469645070000"}

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, jurisdiction_geoid, native_parcel_id, roll_year
            FROM parcel_snapshot
            """
        ).fetchall()
        assert [dict(row) for row in parcels] == [
            {
                "parcel_id": parcels[0]["parcel_id"],
                "jurisdiction_geoid": "51810",
                "native_parcel_id": "14469645070000",
                "roll_year": "2025",
            }
        ]
        parcel_id = int(parcels[0]["parcel_id"])

        events = db.execute(
            """
            SELECT event_type, event_date, amount_minor, status,
                   native_event_id, raw_json
            FROM tax_account_event
            WHERE parcel_id=?
            ORDER BY native_event_id
            """,
            (parcel_id,),
        ).fetchall()
        assert len(events) == 2
        assert [row["native_event_id"] for row in events] == [
            "1125000027:1:14469645070000:2025",
            "1125000027:2:14469645070000:2025",
        ]
        assert {row["event_type"] for row in events} == {
            "delinquency_current_extract"
        }
        assert {row["event_date"] for row in events} == {None}
        assert {row["amount_minor"] for row in events} == {145678}
        first_raw = json.loads(events[0]["raw_json"])
        assert first_raw["occurrence_identity"] == {
            "bill_number": "1125000027",
            "gpin": "14469645070000",
            "installment": "1",
            "tax_year": "2025",
        }
        assert first_raw["parcel_join"] == {
            "gpin": "14469645070000",
            "jurisdiction_geoid": "51810",
        }

        aliases = db.execute(
            """
            SELECT alias_type, alias_value, effective_from
            FROM parcel_alias
            WHERE parcel_id=?
            """,
            (parcel_id,),
        ).fetchall()
        assert [dict(row) for row in aliases] == [
            {
                "alias_type": "tax_bill",
                "alias_value": "1125000027",
                "effective_from": "2025",
            }
        ]
        assert (
            db.execute(
                "SELECT COUNT(*) FROM ownership_assertion WHERE parcel_id=?",
                (parcel_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            db.execute(
                "SELECT COUNT(*) FROM parcel_address WHERE parcel_id=?",
                (parcel_id,),
            ).fetchone()[0]
            == 2
        )
    finally:
        db.close()


def test_sidecar_rejects_a_collapsed_or_mismatched_occurrence_key(
    tmp_path: Path,
) -> None:
    record = _normalized_installments()[0]
    record["native_event_id"] = record["bill_number"]

    with pytest.raises(
        PropertyIngestError,
        match="bill/installment/GPIN/tax-year occurrence key",
    ):
        ingest_property_envelope(
            _envelope([record]),
            db_path=tmp_path / "property.db",
        )


def test_related_route_records_are_preserved_without_parcel_projection(
    tmp_path: Path,
) -> None:
    envelope = PublicRecordsResult.success(
        va_tax.build_query("routes", None, limit=None, cursor=None),
        [va_tax._routes_record()],
        retrieved_at="2026-07-30T22:24:07Z",
    ).to_dict()

    result = ingest_property_envelope(
        envelope,
        db_path=tmp_path / "property.db",
    )

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 0
    assert result["records_preserved_without_projection"] == 1
    assert result["projection_skips"][0]["reason"] == (
        "record_is_not_a_tax_delinquency_installment"
    )
