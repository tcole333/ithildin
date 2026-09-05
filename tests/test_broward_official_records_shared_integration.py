from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import query_broward_official_records as broward
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURE_ROOT = Path(
    "tests/fixtures/public_records/broward_official_records"
)
GRID = json.loads(
    (FIXTURE_ROOT / "grid-name.json").read_text(encoding="utf-8")
)
DETAIL_HTML = (FIXTURE_ROOT / "detail.html").read_text(encoding="utf-8")


def _shared_args(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _detail_record() -> dict:
    exact_search = copy.deepcopy(GRID)
    exact_search["data"] = [
        row
        for row in exact_search["data"]
        if row["InstrumentNumber"] == "114957232"
    ][:1]
    exact_search.update(
        {
            "total": 1,
            "search_kind": "instrument",
            "exact_match_found": True,
            "truncated": False,
        }
    )
    return broward.normalize_detail(
        {
            "found": True,
            "instrument_number": "114957232",
            "search": exact_search,
            "detail": {
                "source_url": (
                    "https://officialrecords.broward.org/"
                    "AcclaimWeb/Details/"
                ),
                "details_url": (
                    "https://officialrecords.broward.org/AcclaimWeb/"
                    "details/documentdetails/36534745/50/1/100"
                ),
                "details_html": DETAIL_HTML,
                "rendered": {
                    "fields": {},
                    "table_rows": [],
                    "anchors": [
                        {
                            "text": "Property Appraiser",
                            "href": broward.PROPERTY_APPRAISER_URL,
                        },
                        {
                            "text": "Map",
                            "href": broward.PROPERTY_MAP_URL,
                        },
                        {
                            "text": "Tax Collector",
                            "href": broward.TAX_COLLECTOR_URL,
                        },
                    ],
                    "retrieval_token": "session-token",
                },
            },
            "image": {
                "available": True,
                "state": "public_pdf",
                "page_count": 3,
                "viewer_url": (
                    "https://officialrecords.broward.org/AcclaimWeb/"
                    "Image/DocumentImage1/session-token"
                ),
                "pdf_url": (
                    "https://officialrecords.broward.org/AcclaimWeb/"
                    "Image/DocumentPdfAllPages/session-pdf-token"
                ),
            },
        }
    )


def _detail_envelope() -> dict:
    args = broward.build_parser().parse_args(["detail", "114957232"])
    return PublicRecordsResult.success(
        broward.build_query(args),
        [_detail_record()],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _download_envelope(destination: Path) -> dict:
    digest = "a" * 64
    record = broward._download_record(
        {
            "instrument_number": "114957232",
            "destination": str(destination),
            "byte_count": 4321,
            "sha256": digest,
            "mime_type": "application/pdf",
            "page_count": 3,
            "source_url": broward.SEARCH_URL,
        }
    )
    args = broward.build_parser().parse_args(
        ["download", "114957232", str(destination)]
    )
    return PublicRecordsResult.success(
        broward.build_query(args),
        [record],
        retrieved_at="2026-07-30T12:05:00Z",
        raw_artifact_refs=(str(destination),),
    ).to_dict()


def test_shared_routes_keep_party_parcel_and_instrument_semantics_distinct():
    routes = query_property.LIVE_ROUTES[broward.SOURCE_ID]

    party = routes["search"].translate(
        _shared_args(
            "search",
            "EPSTEIN, JEFFREY",
            "--source",
            broward.SOURCE_ID,
            "--jurisdiction",
            "12011",
            "--search-field",
            "grantor",
            "--limit",
            "7",
        ),
        routes["search"].adapter_command,
    )
    assert party.command == "name"
    assert party.name == "EPSTEIN, JEFFREY"
    assert party.direction == "grantor"
    assert party.limit == 7
    assert party.max_pages == 10

    parcel = routes["parcel"].translate(
        _shared_args(
            "parcel",
            "514223CB0580",
            "--source",
            broward.SOURCE_ID,
            "--county-fips",
            "011",
        ),
        routes["parcel"].adapter_command,
    )
    assert parcel.command == "parcel"
    assert parcel.parcel_id == "514223CB0580"

    instrument = routes["instrument"].translate(
        _shared_args(
            "instrument",
            "114957232",
            "--source",
            broward.SOURCE_ID,
        ),
        routes["instrument"].adapter_command,
    )
    assert instrument.command == "detail"
    assert instrument.instrument_number == "114957232"
    assert set(routes) == {"search", "parcel", "instrument", "probe"}
    assert "address" not in routes

    guidance = query_property._source_guidance(broward.SOURCE_ID)
    assert guidance["record_identity"] == "instrument_number"
    assert guidance["browser_session"]["document_pdf"].startswith(
        "viewer and all-pages PDF URLs"
    )
    complement_kinds = {
        item["kind"] for item in guidance["official_complements"]
    }
    assert {
        "broward_property_appraiser",
        "florida_dor_property_bulk",
        "online_certified_copy_order",
        "search_copy_and_archive_service",
    }.issubset(complement_kinds)


def test_shared_broward_routes_validate_geography_and_selector_types():
    route = query_property.LIVE_ROUTES[broward.SOURCE_ID]["instrument"]
    with pytest.raises(ValueError, match="numeric instrument"):
        route.translate(
            _shared_args(
                "instrument",
                "O/24460/287",
                "--source",
                broward.SOURCE_ID,
            ),
            route.adapter_command,
        )
    with pytest.raises(ValueError, match="Broward County GEOID"):
        route.translate(
            _shared_args(
                "instrument",
                "114957232",
                "--source",
                broward.SOURCE_ID,
                "--jurisdiction",
                "12099",
            ),
            route.adapter_command,
        )


def test_broward_projection_preserves_index_links_without_ownership(
    tmp_path: Path,
):
    db_path = tmp_path / "property.db"

    first = ingest_property_envelope(_detail_envelope(), db_path=db_path)
    second = ingest_property_envelope(_detail_envelope(), db_path=db_path)

    projection = first["records"][0]
    assert projection["official_instrument_number"] == "114957232"
    assert projection["parties_upserted"] == 2
    assert projection["parcels_linked"] == 1
    assert projection["parcel_stubs_created"] == 1
    assert projection["artifacts_upserted"] == 1
    assert projection["ownership_assertions_upserted"] == 0
    assert projection["sales_upserted"] == 0
    assert second["records"][0]["parcel_stubs_created"] == 0
    assert second["records"][0]["instrument_id"] == projection["instrument_id"]

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT native_document_id, instrument_type, recording_date,
                   consideration_minor, raw_json
            FROM recorded_instrument
            WHERE source_id=?
            """,
            (broward.SOURCE_ID,),
        ).fetchone()
        assert tuple(instrument)[:4] == (
            "114957232",
            "Deed Transfers of Real Property",
            "2018-03-20",
            99_000_000,
        )
        raw_instrument = json.loads(instrument["raw_json"])
        assert raw_instrument["property_links"] == {
            "property_appraiser": broward.PROPERTY_APPRAISER_URL,
            "property_map": broward.PROPERTY_MAP_URL,
            "tax_collector": broward.TAX_COLLECTOR_URL,
        }
        assert raw_instrument["image_access"][
            "retrieval_url_ephemeral"
        ] is True

        parties = db.execute(
            """
            SELECT role, raw_name
            FROM instrument_party
            ORDER BY sequence_no
            """
        ).fetchall()
        assert [tuple(row) for row in parties] == [
            ("grantor", "EPSTEIN,JEFFREY M"),
            ("grantee", "SAKHUJA,SIMMI"),
        ]

        link = db.execute(
            """
            SELECT p.source_id, p.native_parcel_id, ip.link_method,
                   ip.link_confidence
            FROM instrument_parcel ip
            JOIN parcel_snapshot p USING(parcel_id)
            """
        ).fetchone()
        assert tuple(link) == (
            broward.SOURCE_ID,
            "514223CB0580",
            "exact_source_index_parcel_id",
            1.0,
        )

        artifact = db.execute(
            """
            SELECT native_document_id, sha256, mime_type, page_count,
                   source_url, acquisition_method, access_state
            FROM document_artifact
            """
        ).fetchone()
        assert tuple(artifact) == (
            "114957232:online-pdf",
            None,
            "application/pdf",
            3,
            (
                "https://officialrecords.broward.org/AcclaimWeb/"
                "details/documentdetails/36534745/50/1/100"
            ),
            "browser_session_image_availability_metadata",
            "public",
        )
        assert "session-pdf-token" not in artifact["source_url"]
        assert db.execute(
            "SELECT COUNT(*) FROM ownership_assertion"
        ).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM parcel_address"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_broward_download_is_a_separate_idempotent_artifact(
    tmp_path: Path,
):
    db_path = tmp_path / "property.db"
    destination = tmp_path / "114957232.pdf"
    ingest_property_envelope(_detail_envelope(), db_path=db_path)

    first = ingest_property_envelope(
        _download_envelope(destination),
        db_path=db_path,
    )
    second = ingest_property_envelope(
        _download_envelope(destination),
        db_path=db_path,
    )

    assert first["records"][0]["artifacts_upserted"] == 1
    assert second["records"][0]["artifact_id"] == first["records"][0][
        "artifact_id"
    ]

    db = connect_property(db_path)
    try:
        downloaded = db.execute(
            """
            SELECT native_document_id, sha256, storage_path,
                   acquisition_method, acquired_at
            FROM document_artifact
            WHERE sha256 IS NOT NULL
            """
        ).fetchone()
        assert tuple(downloaded) == (
            "114957232",
            "a" * 64,
            str(destination),
            "browser_session_pdf_download",
            "2026-07-30T12:05:00Z",
        )
        instrument = db.execute(
            """
            SELECT instrument_type, consideration_minor
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument) == (
            "Deed Transfers of Real Property",
            99_000_000,
        )
    finally:
        db.close()
