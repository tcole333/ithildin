from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_govos_recorders as govos
from tools import query_property
from tools import query_reeves_records as recorder
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


SOURCE_ID = "us-oh-franklin-county-recorder-publicsearch"
FIXTURE_DIR = Path("tests/fixtures/public_records/reeves_records")


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _envelope(
    *,
    retrieved_at: str = "2026-07-31T12:00:00Z",
    representation: str = "search",
) -> dict[str, Any]:
    tenant = govos.TENANTS_BY_SOURCE[SOURCE_ID]
    raw_record = json.loads(
        (
            FIXTURE_DIR
            / (
                "search_record.json"
                if representation == "search"
                else "document_detail.json"
            )
        ).read_text(encoding="utf-8")
    )
    adapter_args = govos.build_parser().parse_args(
        [
            "search",
            "--source",
            SOURCE_ID,
            tenant.probe_instrument_number,
            "--limit",
            "1",
        ]
    )
    query = recorder.build_query(adapter_args, tenant=tenant)
    record = recorder.normalize_instrument(
        raw_record,
        schema="franklin-recorder-shared-fixture",
        search_metadata=(
            {
                "source_total_count": 1,
                "offset": 0,
                "limit": 1,
                "statistics": {},
                "response_type": "@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
            }
            if representation == "search"
            else None
        ),
        tenant=tenant,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at=retrieved_at,
    ).to_dict()


def test_shared_router_preserves_franklin_tenant_and_native_window() -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    translated = routes["instrument"].translate(
        _shared_args(
            "instrument",
            "202607290091301",
            "--source",
            SOURCE_ID,
            "--department",
            "RP",
            "--limit",
            "37",
            "--cursor",
            "kofile:v1:fixture",
        ),
        routes["instrument"].adapter_command,
    )

    assert set(routes) == {"search", "owner", "instrument"}
    assert translated.command == "search"
    assert translated.source == SOURCE_ID
    assert translated.department == "RP"
    assert translated.query == "202607290091301"
    assert translated.limit == 37
    assert translated.offset == 0
    assert translated.cursor == "kofile:v1:fixture"
    assert query_property._source_guidance(SOURCE_ID)["mode"] == (
        "unified_live"
    )


def test_shared_router_omitted_limit_selects_exhaustive_adapter_mode() -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    translated = routes["instrument"].translate(
        _shared_args(
            "instrument",
            "202607290091301",
            "--source",
            SOURCE_ID,
        ),
        routes["instrument"].adapter_command,
    )

    assert translated.limit is None
    assert translated.offset == 0


@pytest.mark.parametrize(
    ("source_id", "jurisdictions", "counties"),
    [
        (
            SOURCE_ID,
            ("39", "OH", "US-OH", "39049"),
            ("049", "39049", "Franklin", "Franklin County"),
        ),
        (
            "us-co-denver-recorder-publicsearch",
            ("08", "CO", "US-CO", "08031"),
            (
                "031",
                "08031",
                "Denver",
                "Denver County",
                "City and County of Denver",
            ),
        ),
    ],
)
def test_shared_govos_geography_is_derived_from_each_tenant(
    source_id: str,
    jurisdictions: tuple[str, ...],
    counties: tuple[str, ...],
) -> None:
    tenant = govos.TENANTS_BY_SOURCE[source_id]
    for jurisdiction in jurisdictions:
        translated = query_property._govos_recorder_args(
            _shared_args(
                "instrument",
                tenant.probe_instrument_number,
                "--source",
                source_id,
                "--jurisdiction",
                jurisdiction,
            ),
            "search",
        )
        assert translated.source == source_id
    for county in counties:
        translated = query_property._govos_recorder_args(
            _shared_args(
                "instrument",
                tenant.probe_instrument_number,
                "--source",
                source_id,
                "--county",
                county,
            ),
            "search",
        )
        assert translated.source == source_id


@pytest.mark.parametrize(
    ("source_id", "option", "value"),
    [
        (SOURCE_ID, "--jurisdiction", "08031"),
        (SOURCE_ID, "--county", "Denver"),
        (
            "us-co-denver-recorder-publicsearch",
            "--jurisdiction",
            "39049",
        ),
        ("us-co-denver-recorder-publicsearch", "--county", "Franklin"),
    ],
)
def test_shared_govos_geography_rejects_cross_tenant_scope(
    source_id: str,
    option: str,
    value: str,
) -> None:
    tenant = govos.TENANTS_BY_SOURCE[source_id]
    with pytest.raises(ValueError, match="serves county|does not serve"):
        query_property._govos_recorder_args(
            _shared_args(
                "instrument",
                tenant.probe_instrument_number,
                "--source",
                source_id,
                option,
                value,
            ),
            "search",
        )


def test_ingestion_projects_franklin_recorder_identity_and_parties(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    result = ingest_property_envelope(_envelope(), db_path=db_path)

    assert result["projection_supported"] is True
    assert result["records_ingested"] == 1

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
        SOURCE_ID,
        "39049",
        "RP:20798096",
    )
    assert instrument["source_url"] == (
        "https://franklin.oh.publicsearch.us/"
        "doc/20798096?department=RP"
    )
    assert [tuple(row) for row in parties] == [
        ("grantee", "APR OPERATING LLC"),
        ("grantor", "THREE RIVERS ACQUISITION III LLC"),
        ("grantor", "THREE RIVERS OPERATING CO III LLC"),
    ]


def test_older_recorder_observation_is_retained_without_replacing_projection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    newer = _envelope(retrieved_at="2026-07-31T12:00:00Z")
    older = _envelope(retrieved_at="2026-07-30T12:00:00Z")
    stale_record = older["records"][0]
    stale_record["instrument_type_label"] = "STALE INDEX LABEL"
    stale_record["schema_fingerprint"] = "older-search-schema"
    stale_record["parties"] = [
        {
            "name": "STALE INDEX PARTY",
            "role": "other",
            "sequence_no": 99,
        }
    ]
    stale_record["documents"] = [
        {
            "native_document_id": "RP:20798096:stale",
            "mime_type": "text/html",
            "access_state": "unknown",
            "source_url": "https://example.test/stale",
        }
    ]

    newer_report = ingest_property_envelope(newer, db_path=db_path)
    older_report = ingest_property_envelope(older, db_path=db_path)

    assert newer_report["records_ingested"] == 1
    assert older_report["records_ingested"] == 0
    assert older_report["projection_skips"][0]["reason"] == (
        "older_recorder_observation_preserved_without_mutation"
    )

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT instrument_type, observation_id, raw_json
            FROM recorded_instrument
            WHERE source_id=? AND native_document_id='RP:20798096'
            """,
            (SOURCE_ID,),
        ).fetchone()
        linked_observation = db.execute(
            """
            SELECT retrieved_at, schema_fingerprint
            FROM source_observation WHERE observation_id=?
            """,
            (instrument["observation_id"],),
        ).fetchone()
        record_observations = db.execute(
            """
            SELECT retrieved_at, schema_fingerprint
            FROM source_observation
            WHERE source_id=? AND source_native_id='RP:20798096'
              AND record_kind='recorded_instrument'
            ORDER BY retrieved_at
            """,
            (SOURCE_ID,),
        ).fetchall()
        parties = db.execute(
            """
            SELECT raw_name FROM instrument_party ORDER BY sequence_no
            """
        ).fetchall()
        documents = db.execute(
            """
            SELECT native_document_id, mime_type
            FROM document_artifact ORDER BY native_document_id
            """
        ).fetchall()
    finally:
        db.close()

    assert instrument["instrument_type"] == "ASSIGNMENT AND BILL OF SALE"
    assert json.loads(instrument["raw_json"])["schema_fingerprint"] == (
        "franklin-recorder-shared-fixture"
    )
    assert tuple(linked_observation) == (
        "2026-07-31T12:00:00Z",
        "franklin-recorder-shared-fixture",
    )
    assert [tuple(item) for item in record_observations] == [
        ("2026-07-30T12:00:00Z", "older-search-schema"),
        ("2026-07-31T12:00:00Z", "franklin-recorder-shared-fixture"),
    ]
    assert [item["raw_name"] for item in parties] == [
        "APR OPERATING LLC",
        "THREE RIVERS ACQUISITION III LLC",
        "THREE RIVERS OPERATING CO III LLC",
    ]
    assert [tuple(item) for item in documents] == [
        ("RP:20798096:19747017", "image/png")
    ]


@pytest.mark.parametrize(
    "ingest_order",
    (("detail", "search"), ("search", "detail")),
)
def test_detail_representation_wins_without_losing_raw_search_occurrence(
    tmp_path: Path,
    ingest_order: tuple[str, str],
) -> None:
    db_path = tmp_path / "property.db"
    envelopes = {
        "detail": _envelope(
            retrieved_at="2026-07-30T12:00:00Z",
            representation="detail",
        ),
        "search": _envelope(
            retrieved_at="2026-07-31T12:00:00Z",
            representation="search",
        ),
    }
    detail_record = envelopes["detail"]["records"][0]
    detail_record["parties"][0]["entity_kind"] = "organization"
    detail_record["parties"][0]["raw_address"] = "100 DETAIL WAY"

    sparse_search = envelopes["search"]["records"][0]
    for field in (
        "book",
        "volume",
        "page",
        "execution_date",
        "recording_date",
    ):
        sparse_search[field] = None
    sparse_search["legal_descriptions"] = []
    sparse_search["parties"][0]["entity_kind"] = None
    sparse_search["parties"][0]["raw_address"] = None
    sparse_search["page_count"] = None
    sparse_search["documents"][0]["page_count"] = None

    reports = [
        ingest_property_envelope(envelopes[key], db_path=db_path)
        for key in ingest_order
    ]

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT book, page, execution_date, recording_date,
                   legal_description_raw, observation_id, raw_json
            FROM recorded_instrument
            WHERE source_id=? AND native_document_id='RP:20798096'
            """,
            (SOURCE_ID,),
        ).fetchone()
        linked_observation = db.execute(
            """
            SELECT retrieved_at FROM source_observation WHERE observation_id=?
            """,
            (instrument["observation_id"],),
        ).fetchone()
        observations = db.execute(
            """
            SELECT retrieved_at FROM source_observation
            WHERE source_id=? AND source_native_id='RP:20798096'
              AND record_kind='recorded_instrument'
            ORDER BY retrieved_at
            """,
            (SOURCE_ID,),
        ).fetchall()
        party = db.execute(
            """
            SELECT entity_kind, raw_address FROM instrument_party
            WHERE raw_name='APR OPERATING LLC'
            """
        ).fetchone()
        artifact = db.execute(
            """
            SELECT page_count FROM document_artifact
            WHERE native_document_id='RP:20798096:19747017'
            """
        ).fetchone()
    finally:
        db.close()

    assert instrument["book"] == "OPR/1576"
    assert instrument["page"] == "664"
    assert instrument["execution_date"] == "2018-04-16"
    assert instrument["recording_date"] == "2018-04-19"
    assert "MULTIPLE PROPERTIES" in instrument["legal_description_raw"]
    assert json.loads(instrument["raw_json"])["source_representation"] == (
        "document_detail"
    )
    assert linked_observation["retrieved_at"] == "2026-07-30T12:00:00Z"
    assert [row["retrieved_at"] for row in observations] == [
        "2026-07-30T12:00:00Z",
        "2026-07-31T12:00:00Z",
    ]
    assert tuple(party) == ("organization", "100 DETAIL WAY")
    assert artifact["page_count"] == 36
    if ingest_order == ("detail", "search"):
        assert reports[1]["projection_skips"][0]["reason"] == (
            "less_complete_recorder_observation_preserved_without_mutation"
        )


def test_catalog_monitor_and_census_share_the_franklin_source_contract() -> None:
    catalog = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    manifest = next(
        item for item in catalog["sources"] if item["source_id"] == SOURCE_ID
    )
    association = manifest["census_associations"][0]

    assert manifest["source_status"] == "active"
    assert manifest["adapter_family"] == "kofile_neumo_publicsearch_ws"
    assert manifest["adapter_version"] == 1
    assert manifest["jurisdiction_geoids"] == ["39049"]
    assert association["jurisdiction_geoid"] == "39049"
    assert association["role"] == "land_records_index"
    assert SOURCE_ID in public_records_monitor.HANDLER_REGISTRY
    assert public_records_monitor.HANDLER_REGISTRY[SOURCE_ID].handler is (
        public_records_monitor.probe_govos_recorder
    )
