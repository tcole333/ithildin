from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools import query_ohio_pax_recorders as pax
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_pax_recorders"
)


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _fixture_text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _delaware_record() -> dict[str, Any]:
    payload = json.loads(_fixture_text("delaware_detail_all.json"))
    batch = pax.parse_detail_response(
        json.dumps(json.dumps(payload)),
        pax.DELAWARE,
        f"{pax.DELAWARE.pax_root}api/SearchDetail",
    )
    return dict(batch.records[0])


def _licking_exact_record() -> dict[str, Any]:
    record = pax.parse_licking_exact(
        _fixture_text("licking_exact.html"),
        (
            "https://apps.lickingcounty.gov/recorder/record-search/"
            f"?instrument={pax.LICKING_SENTINEL}"
        ),
        expected_instrument=pax.LICKING_SENTINEL,
    )
    assert record is not None
    return dict(record)


def _envelope(
    *,
    query_source_id: str,
    record: dict[str, Any],
    operation: str = "instrument",
    retrieved_at: str = "2026-07-30T12:00:00Z",
) -> dict[str, Any]:
    tenant = pax.TENANTS_BY_QUERY_SOURCE[query_source_id]
    query = pax._query(
        tenant,
        operation,
        parameters={"instrument": record.get("instrument_number")},
        query_source_id=query_source_id,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def test_shared_router_preserves_component_and_exhaustive_default() -> None:
    delaware_routes = query_property.LIVE_ROUTES[pax.DELAWARE_SOURCE_ID]
    licking_routes = query_property.LIVE_ROUTES[pax.LICKING_SOURCE_ID]
    exact_routes = query_property.LIVE_ROUTES[pax.LICKING_DETAIL_SOURCE_ID]

    unbounded = delaware_routes["search"].translate(
        _shared_args(
            "search",
            "EXAMPLE LLC",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--jurisdiction",
            "39041",
            "--search-field",
            "grantor",
        ),
        delaware_routes["search"].adapter_command,
    )
    bounded = delaware_routes["search"].translate(
        _shared_args(
            "search",
            "123/456",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--county",
            "Delaware",
            "--search-field",
            "book-page",
            "--limit",
            "7",
            "--cursor",
            "continuation",
        ),
        delaware_routes["search"].adapter_command,
    )
    exact = exact_routes["instrument"].translate(
        _shared_args(
            "instrument",
            pax.LICKING_SENTINEL,
            "--source",
            pax.LICKING_DETAIL_SOURCE_ID,
            "--jurisdiction",
            "39089",
        ),
        exact_routes["instrument"].adapter_command,
    )

    assert set(delaware_routes) == {
        "search",
        "instrument",
        "download",
        "probe",
    }
    assert set(licking_routes) == {"search", "probe"}
    assert set(exact_routes) == {"instrument", "download", "probe"}
    assert unbounded.source == pax.DELAWARE_SOURCE_ID
    assert unbounded.name == "EXAMPLE LLC"
    assert unbounded.party == "first"
    assert unbounded.limit is None
    assert bounded.book == "123"
    assert bounded.page == "456"
    assert bounded.limit == 7
    assert bounded.cursor == "continuation"
    assert exact.command == "document-info"
    assert exact.source == pax.LICKING_DETAIL_SOURCE_ID
    assert exact.instrument == pax.LICKING_SENTINEL

    guidance = query_property._source_guidance(
        pax.LICKING_DETAIL_SOURCE_ID
    )
    assert guidance["record_identity_source_id"] == pax.LICKING_SOURCE_ID
    assert guidance["independent_corroboration"] is False


def test_licking_representations_deduplicate_on_pax_instrument_identity(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    exact_record = _licking_exact_record()
    pax_record = deepcopy(exact_record)
    pax_record.update(
        source_id=pax.LICKING_SOURCE_ID,
        record_identity_source_id=pax.LICKING_SOURCE_ID,
        representation_source_id=pax.LICKING_SOURCE_ID,
        representation_kind="pax_detail_html",
        source_url=pax.LICKING.pax_root,
        portal_url=pax.LICKING.pax_root,
    )
    pax_record.pop("document", None)

    first = ingest_property_envelope(
        _envelope(
            query_source_id=pax.LICKING_SOURCE_ID,
            record=pax_record,
        ),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _envelope(
            query_source_id=pax.LICKING_DETAIL_SOURCE_ID,
            record=exact_record,
            retrieved_at="2026-07-30T12:01:00Z",
        ),
        db_path=db_path,
    )

    assert first["records_ingested"] == 1
    assert second["records_ingested"] == 1
    assert first["records"][0]["record_identity_source_id"] == (
        pax.LICKING_SOURCE_ID
    )
    assert second["records"][0]["representation_source_id"] == (
        pax.LICKING_DETAIL_SOURCE_ID
    )
    assert first["records"][0]["instrument_id"] == second["records"][0][
        "instrument_id"
    ]
    assert second["records"][0]["ownership_assertions_upserted"] == 0
    assert second["records"][0]["sales_upserted"] == 0
    assert second["records"][0]["parcels_upserted"] == 0

    db = connect_property(db_path)
    try:
        instruments = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, recording_date, source_url
            FROM recorded_instrument
            """
        ).fetchall()
        detail_observations = db.execute(
            """
            SELECT source_id, source_native_id, schema_fingerprint
            FROM source_observation
            WHERE record_kind='recorded_instrument_detail'
            ORDER BY observation_id
            """
        ).fetchall()
        artifact = db.execute(
            """
            SELECT source_id, native_document_id, sha256, mime_type,
                   page_count, source_url
            FROM document_artifact
            """
        ).fetchone()
        party_count = db.execute(
            "SELECT COUNT(*) FROM instrument_party"
        ).fetchone()[0]
        assertion_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "parcel_snapshot",
                "ownership_assertion",
                "sale_event",
                "assessment",
            )
        }
    finally:
        db.close()

    assert len(instruments) == 1
    assert tuple(instruments[0])[:5] == (
        pax.LICKING_SOURCE_ID,
        "39089",
        pax.LICKING_SENTINEL,
        "DEED",
        "2025-04-11",
    )
    assert instruments[0]["source_url"].endswith(
        f"?instrument={pax.LICKING_SENTINEL}"
    )
    assert [
        (row["source_id"], row["source_native_id"])
        for row in detail_observations
    ] == [
        (pax.LICKING_SOURCE_ID, pax.LICKING_SENTINEL),
        (pax.LICKING_DETAIL_SOURCE_ID, pax.LICKING_SENTINEL),
    ]
    assert all(row["schema_fingerprint"] for row in detail_observations)
    assert artifact["source_id"] == pax.LICKING_DETAIL_SOURCE_ID
    assert artifact["native_document_id"] == (
        f"{pax.LICKING_SENTINEL}:official-public-pdf"
    )
    assert artifact["sha256"] is None
    assert artifact["mime_type"] == "application/pdf"
    assert artifact["page_count"] == 13
    assert artifact["source_url"].endswith(
        f"document?instrument={pax.LICKING_SENTINEL}"
    )
    assert party_count == len(exact_record["party_occurrences"])
    assert assertion_counts == {
        "parcel_snapshot": 0,
        "ownership_assertion": 0,
        "sale_event": 0,
        "assessment": 0,
    }


def test_exact_document_enriches_one_representation_artifact(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    exact_record = _licking_exact_record()
    ingest_property_envelope(
        _envelope(
            query_source_id=pax.LICKING_DETAIL_SOURCE_ID,
            record=exact_record,
        ),
        db_path=db_path,
    )
    content = b"%PDF-1.7\nOhio recorder fixture\n%%EOF\n"
    destination = tmp_path / "licking.pdf"
    destination.write_bytes(content)
    document_record = {
        "canonical_ref": (
            f"OHREC_DOCUMENT:39089:{pax.LICKING_SENTINEL}:instrument"
        ),
        "evidence_ref": (
            f"PAXDOC:39089:{pax.LICKING_SENTINEL}:instrument"
        ),
        "source_id": pax.LICKING_SOURCE_ID,
        "record_identity_source_id": pax.LICKING_SOURCE_ID,
        "representation_source_id": pax.LICKING_DETAIL_SOURCE_ID,
        "source_url": (
            "https://apps.lickingcounty.gov/recorder/record-search/"
            f"document?instrument={pax.LICKING_SENTINEL}"
        ),
        "record_kind": "recorded_instrument_document",
        "representation_kind": "official_public_pdf",
        "instrument_number": pax.LICKING_SENTINEL,
        "instrument_reference_id": None,
        "media_type": "application/pdf",
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "local_path": str(destination),
    }
    report = ingest_property_envelope(
        _envelope(
            query_source_id=pax.LICKING_DETAIL_SOURCE_ID,
            record=document_record,
            operation="download",
            retrieved_at="2026-07-30T12:05:00Z",
        ),
        db_path=db_path,
    )

    assert report["records_ingested"] == 1
    assert report["records"][0]["record_identity_source_id"] == (
        pax.LICKING_SOURCE_ID
    )
    assert report["records"][0]["representation_source_id"] == (
        pax.LICKING_DETAIL_SOURCE_ID
    )

    db = connect_property(db_path)
    try:
        instrument_count = db.execute(
            "SELECT COUNT(*) FROM recorded_instrument"
        ).fetchone()[0]
        artifacts = db.execute(
            """
            SELECT source_id, sha256, storage_path, acquisition_method,
                   acquired_at, instrument_id
            FROM document_artifact
            """
        ).fetchall()
    finally:
        db.close()

    assert instrument_count == 1
    assert len(artifacts) == 1
    assert artifacts[0]["source_id"] == pax.LICKING_DETAIL_SOURCE_ID
    assert artifacts[0]["sha256"] == hashlib.sha256(content).hexdigest()
    assert artifacts[0]["storage_path"] == str(destination)
    assert artifacts[0]["acquisition_method"] == "official_public_pdf"
    assert artifacts[0]["acquired_at"] == "2026-07-30T12:05:00Z"
    assert artifacts[0]["instrument_id"] is not None


def test_delaware_projection_keys_on_reference_and_drops_session_urls(
    tmp_path: Path,
) -> None:
    record = _delaware_record()
    record["source_url"] = (
        f"{pax.DELAWARE.pax_root}api/Image/session-ticket-value"
    )
    record["portal_url"] = pax.DELAWARE.pax_root
    report = ingest_property_envelope(
        _envelope(
            query_source_id=pax.DELAWARE_SOURCE_ID,
            record=record,
        ),
        db_path=tmp_path / "property.db",
    )
    projection = report["records"][0]

    assert projection["canonical_ref"].endswith(
        f"/instrument/{record['instrument_reference_id']}"
    )
    assert projection["ownership_assertions_upserted"] == 0
    db = connect_property(tmp_path / "property.db")
    try:
        instrument = db.execute(
            """
            SELECT source_id, native_document_id, consideration_minor,
                   source_url, raw_json
            FROM recorded_instrument
            """
        ).fetchone()
        observation = db.execute(
            """
            SELECT source_id, source_native_id, source_url
            FROM source_observation
            WHERE record_kind='recorded_instrument_detail'
            """
        ).fetchone()
    finally:
        db.close()

    assert instrument["source_id"] == pax.DELAWARE_SOURCE_ID
    assert instrument["native_document_id"] == (
        record["instrument_reference_id"]
    )
    assert instrument["consideration_minor"] == 15_000_000
    assert json.loads(instrument["raw_json"])["instrument_number"] == (
        record["instrument_number"]
    )
    assert instrument["source_url"] == pax.DELAWARE.pax_root
    assert observation["source_id"] == pax.DELAWARE_SOURCE_ID
    assert observation["source_native_id"] == (
        record["instrument_reference_id"]
    )
    assert observation["source_url"] == pax.DELAWARE.pax_root
    assert "session-ticket-value" not in observation["source_url"]
