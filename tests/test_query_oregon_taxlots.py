from __future__ import annotations

import copy
import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from tools import ingest_property_records, query_oregon_taxlots
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import TransportError


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_taxlots"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / f"{name}_feature.json").read_text())


def _args(
    command: str = "parcel",
    *,
    source: str = query_oregon_taxlots.PORTLAND_SOURCE_ID,
    query: str = "1S1E03AA00100",
    **overrides: Any,
) -> Namespace:
    values = {
        "command": command,
        "source": source,
        "query": query,
        "field": "parcel" if command == "parcel" else "auto",
        "county": None,
        "limit": 100,
        "cursor": None,
        "geometry": False,
        "page_size": 2,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "retry_attempts": 1,
        "all_sources": False,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _metadata(
    config: query_oregon_taxlots.SourceConfig,
    *,
    missing: str | None = None,
    maximum: int = 2_000,
) -> dict[str, Any]:
    fields = []
    for name in config.required_fields:
        if name == missing:
            continue
        fields.append(
            {
                "name": name,
                "alias": name,
                "type": (
                    "esriFieldTypeOID"
                    if name == config.object_id_field
                    else "esriFieldTypeString"
                ),
                "nullable": True,
            }
        )
    return {
        "name": config.name,
        "capabilities": "Map,Query,Data",
        "advancedQueryCapabilities": {
            "supportsPagination": True,
            "supportsOrderBy": True,
        },
        "maxRecordCount": maximum,
        "fields": fields,
    }


def _with_oid(
    feature: dict[str, Any],
    config: query_oregon_taxlots.SourceConfig,
    oid: int,
) -> dict[str, Any]:
    result = copy.deepcopy(feature)
    result["attributes"][config.object_id_field] = oid
    native_field = config.native_id_fields[0]
    result["attributes"][native_field] = f"{feature['attributes'][native_field]}-{oid}"
    return result


class FakeClient:
    def __init__(
        self,
        config: query_oregon_taxlots.SourceConfig,
        *,
        counts: list[int | Exception],
        pages: list[list[dict[str, Any]] | Exception],
        metadata: dict[str, Any] | Exception | None = None,
        page_size: int = 2,
    ) -> None:
        self.config = config
        self.counts = list(counts)
        self.pages = list(pages)
        self.metadata = (
            _metadata(config) if metadata is None else metadata
        )
        self.page_size = page_size
        self.calls: list[tuple[str, Any]] = []

    def fetch_metadata(self) -> dict[str, Any]:
        self.calls.append(("metadata", None))
        if isinstance(self.metadata, Exception):
            raise self.metadata
        return self.metadata

    def fetch_count(self, where: str) -> int:
        self.calls.append(("count", where))
        if not self.counts:
            raise AssertionError("unexpected count request")
        value = self.counts.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def fetch_page(self, **kwargs: Any) -> tuple[dict[str, Any], ...]:
        self.calls.append(("page", dict(kwargs)))
        if not self.pages:
            raise AssertionError("unexpected page request")
        value = self.pages.pop(0)
        if isinstance(value, Exception):
            raise value
        return tuple(value)


@pytest.fixture(autouse=True)
def _disable_search_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_oregon_taxlots,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


@pytest.mark.parametrize(
    ("source_id", "fixture_name", "county_geoid", "native_id"),
    [
        (
            query_oregon_taxlots.PORTLAND_SOURCE_ID,
            "portland",
            "41051",
            "1S1E03AA00100",
        ),
        (
            query_oregon_taxlots.METRO_SOURCE_ID,
            "metro",
            "41051",
            "21E35BB01800",
        ),
        (
            query_oregon_taxlots.OWRD_SOURCE_ID,
            "owrd",
            "41005",
            "21E10DC12800",
        ),
    ],
)
def test_all_source_mappings_preserve_identity_lineage_and_raw_fields(
    source_id: str,
    fixture_name: str,
    county_geoid: str,
    native_id: str,
) -> None:
    config = query_oregon_taxlots.SOURCES[source_id]
    feature = _fixture(fixture_name)

    record = query_oregon_taxlots._normalize_feature(
        config,
        feature,
        schema_fingerprint_value=f"{fixture_name}-schema",
        geometry_requested=True,
    )

    assert record["source_id"] == source_id
    assert record["native_parcel_id"] == native_id
    assert record["jurisdiction"]["county_geoid"] == county_geoid
    assert record["canonical_ref"].startswith(
        f"PROPERTY:{source_id}/{county_geoid}/parcel/"
    )
    assert record["source_lineage"]["publisher"] == config.publisher
    assert record["source_lineage"]["upstream_custodian"].endswith(
        "County Assessor"
    )
    assert record["raw_attributes"] == feature["attributes"]
    assert record["response_schema_fingerprint"] == f"{fixture_name}-schema"
    assert len(record["adapter_schema_fingerprint"]) == 64
    assert record["geometry"] == feature["geometry"]
    assert record["geometry_crs"] == "EPSG:4326"


def test_source_specific_normalization_surfaces_complementary_information() -> None:
    portland = query_oregon_taxlots._normalize_feature(
        query_oregon_taxlots.PORTLAND_CONFIG,
        _fixture("portland"),
        schema_fingerprint_value="p",
        geometry_requested=False,
    )
    metro = query_oregon_taxlots._normalize_feature(
        query_oregon_taxlots.METRO_CONFIG,
        _fixture("metro"),
        schema_fingerprint_value="m",
        geometry_requested=False,
    )
    owrd = query_oregon_taxlots._normalize_feature(
        query_oregon_taxlots.OWRD_CONFIG,
        _fixture("owrd"),
        schema_fingerprint_value="o",
        geometry_requested=False,
    )

    assert [owner["raw_name"] for owner in portland["owners"]] == [
        "CITY OF PORTLAND",
        "BUREAU OF ENVIRONMENTAL SERVICES",
    ]
    assert portland["assessment_history"][0]["tax_year"] == "2025"
    assert portland["last_sale"]["sale_date"] == "2020-01-01"
    assert portland["source_lineage"]["native_source"] == "Multnomah County"
    assert metro["owners"] == []
    assert metro["owner_visibility"]["state"] == "not_published_by_source"
    assert metro["assessment"]["assessed_value"] == 17_000_000
    assert metro["public_ownership"]["owner_type"] == "REGIONAL GOVERNMENT"
    assert owrd["owners"] == []
    assert owrd["mailing_address"]["city"] == "OREGON CITY"
    assert owrd["plss"]["township_range_section_quarter_key"] == (
        "21S2E10SESE"
    )
    assert owrd["source_last_updated"] == "2025-06-01"


def test_portland_normalization_drops_quote_only_unused_value_slots() -> None:
    feature = _fixture("portland")
    attributes = feature["attributes"]
    for index in (2, 3):
        attributes[f"MKTVALYR{index}"] = '""'
        attributes[f"LANDVAL{index}"] = 0.0
        attributes[f"BLDGVAL{index}"] = 0.0
        attributes[f"TOTALVAL{index}"] = 0.0
    attributes["PRPCD_DESC"] = '""'
    attributes["ACC_STATUS"] = '"'

    record = query_oregon_taxlots._normalize_feature(
        query_oregon_taxlots.PORTLAND_CONFIG,
        feature,
        schema_fingerprint_value="live-sentinel-shape",
        geometry_requested=False,
    )

    assert len(record["assessment_history"]) == 1
    assert record["assessment_history"][0]["tax_year"] == "2025"
    assert record["property_class"]["description"] is None
    assert record["account_status"] is None


def test_sources_lists_distinct_capabilities_coverage_and_owner_visibility() -> None:
    payload = query_oregon_taxlots.execute(_args(command="sources"))
    sources = {
        source["source_id"]: source for source in payload["sources"]
    }

    assert set(sources) == set(query_oregon_taxlots.SOURCES)
    assert "owner" in sources[query_oregon_taxlots.PORTLAND_SOURCE_ID][
        "search_fields"
    ]
    assert "owner" not in sources[query_oregon_taxlots.METRO_SOURCE_ID][
        "search_fields"
    ]
    assert "account" not in sources[query_oregon_taxlots.OWRD_SOURCE_ID][
        "search_fields"
    ]
    assert len(
        sources[query_oregon_taxlots.OWRD_SOURCE_ID]["coverage"]
    ) == 13
    assert all(source["warnings"] for source in sources.values())


def test_sql_literals_are_quote_safe_and_source_field_aware() -> None:
    where = query_oregon_taxlots._where(
        query_oregon_taxlots.PORTLAND_CONFIG,
        operation="search",
        selector="O'Neil",
        search_field="owner",
        county=query_oregon_taxlots._resolve_county(
            query_oregon_taxlots.PORTLAND_CONFIG,
            "Multnomah",
        ),
    )

    assert "O''NEIL" in where
    assert "O'NEIL" not in where
    assert "OWNER1" in where
    assert "OWNER2" in where
    assert "OWNER3" in where
    assert where.endswith("COUNTY = 'M'")

    with pytest.raises(
        query_oregon_taxlots.OregonTaxlotsSelectionError,
        match="searchable owner",
    ):
        query_oregon_taxlots._where(
            query_oregon_taxlots.METRO_CONFIG,
            operation="search",
            selector="Example",
            search_field="owner",
            county=None,
        )


def test_exact_parcel_uses_only_configured_parcel_fields() -> None:
    where = query_oregon_taxlots._where(
        query_oregon_taxlots.METRO_CONFIG,
        operation="parcel",
        selector="21e35bb01800",
        search_field="parcel",
        county=None,
    )

    assert where == (
        "(TLID = '21E35BB01800' OR ORTAXLOT = '21E35BB01800')"
    )
    assert "PRIMACCNUM" not in where
    assert "SITEADDR" not in where


def test_denied_and_mismatched_access_decisions_stop_before_transport() -> None:
    client = FakeClient(
        query_oregon_taxlots.PORTLAND_CONFIG,
        counts=[],
        pages=[],
    )
    denied_decision = {
        "source_id": query_oregon_taxlots.PORTLAND_SOURCE_ID,
        "allowed": False,
        "reason_code": "access_review_required",
        "reason": "review missing",
    }
    denied = query_oregon_taxlots.execute(
        _args(),
        access_decision=denied_decision,
        client=client,
    )

    assert denied.status.value == "unavailable"
    assert denied.errors[0].code == "access_review_required"
    assert denied.query.query.to_dict()["metadata"]["access_decision"] == (
        denied_decision
    )
    assert client.calls == []

    mismatch = query_oregon_taxlots.execute(
        _args(),
        access_decision={
            "source_id": query_oregon_taxlots.METRO_SOURCE_ID,
            "allowed": True,
        },
        client=client,
    )
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "catalog_decision_source_mismatch"
    assert client.calls == []


def test_allowed_access_decision_is_reflected_and_query_executes() -> None:
    feature = _fixture("portland")
    client = FakeClient(
        query_oregon_taxlots.PORTLAND_CONFIG,
        counts=[1, 1],
        pages=[[feature]],
    )
    decision = {
        "source_id": query_oregon_taxlots.PORTLAND_SOURCE_ID,
        "allowed": True,
        "limits": {"maximum_page_size": 2000},
    }

    result = query_oregon_taxlots.execute(
        _args(limit=1),
        access_decision=decision,
        client=client,
    )

    assert result.status.value == "ok"
    assert result.query.query.to_dict()["metadata"]["access_decision"] == (
        decision
    )
    assert any(call[0] == "metadata" for call in client.calls)


def test_catalog_rate_and_page_limits_are_applied_to_owned_client() -> None:
    client = query_oregon_taxlots._client(
        _args(page_size=1_500, minimum_interval=0.1),
        query_oregon_taxlots.PORTLAND_CONFIG,
        {
            "allowed": True,
            "limits": {
                "maximum_page_size": 750,
                "minimum_interval_seconds": 0.4,
            },
        },
    )

    assert client.page_size == 750
    assert client._rate_limiter.minimum_interval == 0.4


def test_cursor_is_query_bound_and_resumes_from_verified_anchor() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    first_client = FakeClient(
        config,
        counts=[3, 3],
        pages=[[_with_oid(base, config, 1), _with_oid(base, config, 2)]],
        page_size=2,
    )
    first = query_oregon_taxlots.execute(
        _args(limit=2),
        client=first_client,
    )

    assert first.status.value == "ok"
    assert first.next_cursor is not None
    cursor = query_oregon_taxlots._decode_cursor(
        first.next_cursor,
        expected_query_fingerprint=query_oregon_taxlots._criteria_fingerprint(
            config,
            operation="parcel",
            where=query_oregon_taxlots._where(
                config,
                operation="parcel",
                selector="1S1E03AA00100",
                search_field="parcel",
                county=None,
            ),
            geometry=False,
        ),
    )
    assert cursor is not None
    assert cursor.offset == 2
    assert cursor.anchor == 2

    resumed_client = FakeClient(
        config,
        counts=[3, 3],
        pages=[
            [_with_oid(base, config, 2)],
            [_with_oid(base, config, 3)],
        ],
        page_size=2,
    )
    resumed = query_oregon_taxlots.execute(
        _args(limit=2, cursor=first.next_cursor),
        client=resumed_client,
    )

    assert resumed.status.value == "ok"
    assert [record["object_id"] for record in resumed.records] == [3]
    page_calls = [
        details for operation, details in resumed_client.calls
        if operation == "page"
    ]
    assert page_calls[0]["offset"] == 1
    assert page_calls[0]["record_count"] == 1
    assert page_calls[0]["out_fields"] == "OBJECTID"
    assert page_calls[1]["offset"] == 2

    mismatch_client = FakeClient(config, counts=[], pages=[])
    mismatched = query_oregon_taxlots.execute(
        _args(
            command="search",
            query="Different",
            field="owner",
            limit=2,
            cursor=first.next_cursor,
        ),
        client=mismatch_client,
    )
    assert mismatched.status.value == "source_changed"
    assert mismatched.errors[0].code == "cursor_query_mismatch"
    assert mismatch_client.calls == []


def test_resume_anchor_change_is_explicit_source_change() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    first = query_oregon_taxlots.execute(
        _args(limit=1),
        client=FakeClient(
            config,
            counts=[2, 2],
            pages=[[_with_oid(base, config, 1)]],
            page_size=1,
        ),
    )
    changed = query_oregon_taxlots.execute(
        _args(limit=1, cursor=first.next_cursor),
        client=FakeClient(
            config,
            counts=[2],
            pages=[[_with_oid(base, config, 9)]],
            page_size=1,
        ),
    )

    assert changed.status.value == "source_changed"
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_count_change_since_cursor_is_partial_and_disables_next_cursor() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    first = query_oregon_taxlots.execute(
        _args(limit=1),
        client=FakeClient(
            config,
            counts=[2, 2],
            pages=[[_with_oid(base, config, 1)]],
            page_size=1,
        ),
    )
    resumed = query_oregon_taxlots.execute(
        _args(limit=1, cursor=first.next_cursor),
        client=FakeClient(
            config,
            counts=[3, 3],
            pages=[
                [_with_oid(base, config, 1)],
                [_with_oid(base, config, 2)],
            ],
            page_size=1,
        ),
    )

    assert resumed.status.value == "partial"
    assert [record["object_id"] for record in resumed.records] == [2]
    assert resumed.errors[0].code == "count_changed_since_cursor"
    assert resumed.next_cursor is None


def test_short_page_continues_until_count_snapshot_is_satisfied() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    client = FakeClient(
        config,
        counts=[3, 3],
        pages=[
            [_with_oid(base, config, 1)],
            [_with_oid(base, config, 2), _with_oid(base, config, 3)],
        ],
        page_size=3,
    )

    result = query_oregon_taxlots.execute(
        _args(limit=3, page_size=3),
        client=client,
    )

    assert result.status.value == "ok"
    assert [record["object_id"] for record in result.records] == [1, 2, 3]
    page_calls = [
        details for operation, details in client.calls if operation == "page"
    ]
    assert [call["record_count"] for call in page_calls] == [3, 2]
    assert [call["offset"] for call in page_calls] == [0, 1]


@pytest.mark.parametrize(
    ("pages", "expected_records"),
    [
        (
            lambda base, config: [
                [_with_oid(base, config, 1), _with_oid(base, config, 2)],
                [_with_oid(base, config, 2)],
            ],
            [1, 2],
        ),
        (
            lambda base, config: [
                [_with_oid(base, config, 2), _with_oid(base, config, 1)]
            ],
            [2],
        ),
    ],
)
def test_repeat_or_reordering_returns_partial_without_unsafe_cursor(
    pages: Any,
    expected_records: list[int],
) -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    result = query_oregon_taxlots.execute(
        _args(limit=3),
        client=FakeClient(
            config,
            counts=[3, 3],
            pages=pages(base, config),
            page_size=2,
        ),
    )

    assert result.status.value == "partial"
    assert [record["object_id"] for record in result.records] == expected_records
    assert result.errors[0].code == "pagination_repeat_or_reorder"
    assert result.next_cursor is None


def test_empty_page_before_reported_count_is_source_changed() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    result = query_oregon_taxlots.execute(
        _args(limit=2),
        client=FakeClient(
            config,
            counts=[2, 2],
            pages=[[]],
        ),
    )

    assert result.status.value == "source_changed"
    assert result.records == ()
    assert result.errors[0].code == "pagination_no_progress"


def test_count_drift_returns_records_as_partial_without_cursor() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    result = query_oregon_taxlots.execute(
        _args(limit=2),
        client=FakeClient(
            config,
            counts=[2, 3],
            pages=[
                [_with_oid(base, config, 1), _with_oid(base, config, 2)]
            ],
        ),
    )

    assert result.status.value == "partial"
    assert [record["object_id"] for record in result.records] == [1, 2]
    assert result.errors[0].code == "count_changed_during_traversal"
    assert result.next_cursor is None


def test_missing_schema_field_is_explicit_source_changed() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    client = FakeClient(
        config,
        counts=[],
        pages=[],
        metadata=_metadata(config, missing="OWNER1"),
    )

    result = query_oregon_taxlots.execute(_args(), client=client)

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert list(result.errors[0].details["missing_fields"]) == ["OWNER1"]


def test_malformed_feature_after_valid_row_preserves_partial_result() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    malformed = _with_oid(base, config, 2)
    malformed["attributes"][config.object_id_field] = None
    result = query_oregon_taxlots.execute(
        _args(limit=2),
        client=FakeClient(
            config,
            counts=[2, 2],
            pages=[[_with_oid(base, config, 1), malformed]],
        ),
    )

    assert result.status.value == "partial"
    assert [record["object_id"] for record in result.records] == [1]
    assert result.errors[0].code == "source_schema_changed"
    assert result.next_cursor is None


def test_transport_failure_is_unavailable_and_not_an_empty_result() -> None:
    error = TransportError(
        "network down",
        url=query_oregon_taxlots.PORTLAND_CONFIG.layer_url,
    )
    result = query_oregon_taxlots.execute(
        _args(),
        client=FakeClient(
            query_oregon_taxlots.PORTLAND_CONFIG,
            counts=[],
            pages=[],
            metadata=error,
        ),
    )

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_transport_failure_after_a_page_returns_partial() -> None:
    config = query_oregon_taxlots.PORTLAND_CONFIG
    base = _fixture("portland")
    error = TransportError("network down", url=config.layer_url)
    result = query_oregon_taxlots.execute(
        _args(limit=2, page_size=1),
        client=FakeClient(
            config,
            counts=[2, 2],
            pages=[[_with_oid(base, config, 1)], error],
            page_size=1,
        ),
    )

    assert result.status.value == "partial"
    assert [record["object_id"] for record in result.records] == [1]
    assert result.errors[0].code == "transport_error"
    assert result.next_cursor is None


@pytest.mark.parametrize(
    ("config", "fixture_name"),
    [
        (query_oregon_taxlots.PORTLAND_CONFIG, "portland"),
        (query_oregon_taxlots.METRO_CONFIG, "metro"),
        (query_oregon_taxlots.OWRD_CONFIG, "owrd"),
    ],
)
def test_component_probe_validates_schema_count_and_stable_sentinel(
    config: query_oregon_taxlots.SourceConfig,
    fixture_name: str,
) -> None:
    result = query_oregon_taxlots.execute(
        _args(
            command="probe",
            source=config.source_id,
            all_sources=False,
        ),
        client=FakeClient(
            config,
            counts=[600_000, 1],
            pages=[[_fixture(fixture_name)]],
        ),
    )

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["record_kind"] == "source_probe"
    assert probe["source_id"] == config.source_id
    assert probe["component_total_count"] == 600_000
    assert probe["sentinel_count"] == 1
    assert probe["sentinel"]["source_id"] == config.source_id
    assert len(probe["schema_fingerprint"]) == 64


@pytest.mark.parametrize(
    ("config", "fixture_name"),
    [
        (query_oregon_taxlots.PORTLAND_CONFIG, "portland"),
        (query_oregon_taxlots.METRO_CONFIG, "metro"),
        (query_oregon_taxlots.OWRD_CONFIG, "owrd"),
    ],
)
def test_canonical_envelope_is_compatible_with_generic_property_ingestion(
    config: query_oregon_taxlots.SourceConfig,
    fixture_name: str,
    tmp_path: Path,
) -> None:
    record = query_oregon_taxlots._normalize_feature(
        config,
        _fixture(fixture_name),
        schema_fingerprint_value=f"{fixture_name}-schema",
        geometry_requested=True,
    )
    county = query_oregon_taxlots._county_from_attributes(
        config,
        record["raw_attributes"],
    )
    query = query_oregon_taxlots._build_query(
        config,
        operation="parcel",
        selector=record["native_parcel_id"],
        search_field="parcel",
        county=county,
        limit=1,
        cursor=None,
        geometry=True,
    )
    envelope = PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()
    summary = ingest_property_records.ingest_property_envelope(
        envelope,
        db_path=tmp_path / f"{fixture_name}.db",
    )

    assert summary["status"] == "ok"
    assert summary["source_id"] == config.source_id
    assert summary["records_seen"] == 1
    assert summary["records_ingested"] == 1
    assert summary["projection_supported"] is True
    assert (
        ingest_property_records.PROPERTY_RECORD_MAPPERS[config.source_id]
        is ingest_property_records._ingest_assessor_record
    )
    assert summary["records"][0]["canonical_ref"] == record["canonical_ref"]


def test_atomic_json_output_replaces_destination_without_temp_residue(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "nested" / "result.json"
    query_oregon_taxlots._atomic_json_write(
        destination,
        {"schema_version": "test/1", "records": [1]},
    )
    query_oregon_taxlots._atomic_json_write(
        destination,
        {"schema_version": "test/2", "records": [2]},
    )

    assert json.loads(destination.read_text()) == {
        "schema_version": "test/2",
        "records": [2],
    }
    assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []


def test_parser_exposes_required_commands_and_explicit_source_selection() -> None:
    parser = query_oregon_taxlots.build_parser()

    search = parser.parse_args(
        [
            "search",
            "Portland",
            "--source",
            query_oregon_taxlots.PORTLAND_SOURCE_ID,
            "--field",
            "owner",
        ]
    )
    parcel = parser.parse_args(
        [
            "parcel",
            "21E35BB01800",
            "--source",
            query_oregon_taxlots.METRO_SOURCE_ID,
            "--geometry",
        ]
    )
    probe = parser.parse_args(["probe", "--all"])

    assert search.command == "search"
    assert search.field == "owner"
    assert parcel.command == "parcel"
    assert parcel.geometry is True
    assert probe.command == "probe"
    assert probe.all_sources is True
