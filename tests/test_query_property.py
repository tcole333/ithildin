from pathlib import Path

import pytest

from tools import query_property
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
    assert address["records"][0]["matched_address"]["postal_code"] == "28675"
    assert parcel["records"][0]["native_parcel_id"] == "3013467134"
    assert instrument["records"][0]["native_document_id"] == "BK1-PG2"
    assert chain["records"][0]["chain_analysis"]["complete_chain_claimed"] is False
    assert chain["records"][0]["recorded_instruments"][0][
        "native_document_id"
    ] == "BK1-PG2"
    assert "sale_without_instrument_link" in chain["records"][0][
        "chain_analysis"
    ]["gap_flags"]
    assert mapped["records"][0]["geometry"]["surveyed_legal_boundary"] is False
    assert owner["query"]["source"]["source_id"] == (
        "local-property-records-sidecar"
    )


def test_local_property_cache_miss_is_partial_and_cursor_is_validated(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "property.db"
    _seed_property(db_path)
    logged = []
    monkeypatch.setattr(
        query_property, "log_search", lambda *args: logged.append(args)
    )

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


def test_local_property_uncovered_jurisdiction_is_unavailable(
    tmp_path, monkeypatch
):
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
    assert error["details"]["coverage"]["sidecar"][
        "requested_jurisdiction_counts"
    ] == {"instruments": 0, "parcels": 0}
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
        lambda envelope, **kwargs: ingested.append((envelope, kwargs))
        or {"status": "ok", "records_ingested": 0},
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


def test_bulk_source_surfaces_adapter_status_and_direct_tool_guidance(
    tmp_path, monkeypatch
):
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    logged = []
    monkeypatch.setattr(
        query_property, "log_search", lambda *args: logged.append(args)
    )

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
    assert payload["errors"][0]["code"] == "adapter_not_implemented"
    guidance = payload["errors"][0]["details"]["source_guidance"]
    assert guidance["mode"] == "bulk_manifest"
    assert "query_fl_dor_property.py" in guidance["direct_tool"]
    assert guidance["unified_operations"] == []
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
    assert {
        record["source_id"] for record in payload["records"]
    } >= {"us-nc-onemap-parcels", "us-nyc-acris"}
    by_source = {
        record["source_id"]: record for record in payload["records"]
    }
    assert by_source[query_property.FL_SOURCE_ID]["query_guidance"]["mode"] == (
        "bulk_manifest"
    )
    assert "query_fl_dor_property.py" in by_source[
        query_property.FL_SOURCE_ID
    ]["query_guidance"]["direct_tool"]
    assert by_source[query_property.MASSGIS_SOURCE_ID][
        "query_guidance"
    ]["unified_operations"] == []
    assert by_source[query_property.HARRIS_SOURCE_ID][
        "query_guidance"
    ]["mode"] == "bulk_manifest"
    assert "query_harris_property.py" in by_source[
        query_property.HARRIS_SOURCE_ID
    ]["query_guidance"]["direct_tool"]
    assert by_source[query_property.ACRIS_IMAGES_SOURCE_ID][
        "query_guidance"
    ]["mode"] == "action_planning"
    assert "public_records_actions.py" in by_source[
        query_property.ACRIS_IMAGES_SOURCE_ID
    ]["query_guidance"]["direct_tool"]
    assert by_source[query_property.ACRIS_SOURCE_ID][
        "query_guidance"
    ]["unified_operations"] == ["chain", "instrument", "owner", "parcel"]

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
    assert "chain" in result.stdout

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
