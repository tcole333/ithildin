from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_deschutes_property
from tools import ingest_property_records


FIXTURE_DIR = Path("tests/fixtures/public_records/deschutes_property")
SERVICE_METADATA = json.loads(
    (FIXTURE_DIR / "service_metadata.json").read_text(encoding="utf-8")
)
PARCEL_BUNDLE = json.loads(
    (FIXTURE_DIR / "parcel_141031B000700.json").read_text(encoding="utf-8")
)


def _args(
    command: str = "parcel",
    query: str | None = query_deschutes_property.PROBE_TAXLOT,
    **overrides: Any,
) -> Namespace:
    values = {
        "command": command,
        "query": query,
        "field": "parcel" if command == "parcel" else "auto",
        "limit": 100,
        "cursor": None,
        "geometry": False,
        "page_size": 1_000,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "retry_attempts": 3,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _field_definitions(table_id: int) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "alias": name,
            "type": (
                "esriFieldTypeOID"
                if name == "OBJECTID"
                else "esriFieldTypeString"
            ),
            "nullable": name != "OBJECTID",
        }
        for name in query_deschutes_property._required_fields(table_id)
    ]


def _relationships() -> list[dict[str, Any]]:
    return [
        {
            "id": table.relationship_id,
            "name": table.relationship_name,
            "relatedTableId": table.table_id,
            "cardinality": table.cardinality,
            "role": "esriRelRoleOrigin",
            "keyField": "TAXLOT",
            "composite": False,
        }
        for table in query_deschutes_property.DECLARED_RELATIONSHIPS
    ]


def _metadata(table_id: int) -> dict[str, Any]:
    return {
        "id": table_id,
        "name": query_deschutes_property._expected_name(table_id),
        "objectIdField": "OBJECTID",
        "maxRecordCount": 2_000,
        "fields": _field_definitions(table_id),
        "relationships": _relationships() if table_id == 0 else [],
        "editingInfo": {"dataLastEditDate": 1_785_230_430_195},
    }


def _feature_taxlot(
    table_id: int,
    feature: Mapping[str, Any],
) -> str | None:
    attributes = feature["attributes"]
    if table_id == 0:
        field = "TAXLOT"
    else:
        field = next(
            table.join_field
            for table in query_deschutes_property.TABLES.values()
            if table.table_id == table_id
        )
    value = attributes.get(field)
    return str(value).upper() if value not in (None, "") else None


class FixtureClient:
    def __init__(self) -> None:
        self.page_size = 1_000
        self.service_metadata = deepcopy(SERVICE_METADATA)
        self.metadata = {
            table_id: _metadata(table_id)
            for table_id in range(10)
        }
        self.data: dict[int, list[dict[str, Any]]] = {
            0: [deepcopy(PARCEL_BUNDLE["taxlot"])]
        }
        for key, table in query_deschutes_property.TABLES.items():
            self.data[table.table_id] = deepcopy(
                PARCEL_BUNDLE["components"][key]
            )
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def fetch_service_metadata(self) -> Mapping[str, Any]:
        self.calls.append(("service_metadata", {}))
        return self.service_metadata

    def fetch_metadata(self, table_id: int) -> Mapping[str, Any]:
        self.calls.append(("metadata", {"table_id": table_id}))
        return self.metadata[table_id]

    def _filtered(
        self,
        table_id: int,
        where: str,
    ) -> list[dict[str, Any]]:
        records = list(self.data.get(table_id, []))
        if where == "1=1":
            return records
        in_values = re.findall(r"'([^']*)'", where) if " IN (" in where else []
        if in_values:
            selected = {value.upper() for value in in_values}
            return [
                feature
                for feature in records
                if _feature_taxlot(table_id, feature) in selected
            ]
        if "account_id =" in where:
            account_id = int(where.rsplit("=", 1)[1].strip())
            return [
                feature
                for feature in records
                if int(feature["attributes"].get("account_id", -1))
                == account_id
            ]
        if table_id == query_deschutes_property.TABLES["owners"].table_id:
            selector = "VACH" if "VACH" in where else ""
            return [
                feature
                for feature in records
                if selector in str(feature["attributes"].get("NAME", "")).upper()
            ]
        if table_id == query_deschutes_property.TABLES["account"].table_id:
            selector = "BUGGY WHIP" if "BUGGY WHIP" in where else ""
            return [
                feature
                for feature in records
                if selector
                in str(feature["attributes"].get("Address", "")).upper()
            ]
        if table_id == query_deschutes_property.TABLES["mailing"].table_id:
            selector = "BUGGY WHIP" if "BUGGY WHIP" in where else ""
            return [
                feature
                for feature in records
                if selector
                in str(feature["attributes"].get("M_ADDRESS", "")).upper()
            ]
        if table_id == query_deschutes_property.TABLES["sales"].table_id:
            selector = "VACH" if "VACH" in where else ""
            return [
                feature
                for feature in records
                if selector
                in " ".join(
                    str(feature["attributes"].get(field, "")).upper()
                    for field in ("Seller_1", "Buyer_1", "Seller_2", "Buyer_2")
                )
            ]
        if table_id == 0:
            quoted = {value.upper() for value in re.findall(r"'([^']*)'", where)}
            if quoted:
                return [
                    feature
                    for feature in records
                    if any(
                        str(feature["attributes"].get(field, "")).upper()
                        in quoted
                        for field in ("TAXLOT", "MAPNUMBER", "PARCEL")
                    )
                ]
        return records

    def _page_records(
        self,
        table_id: int,
        where: str,
        distinct_field: str | None,
    ) -> list[dict[str, Any]]:
        records = self._filtered(table_id, where)
        if distinct_field:
            values = sorted(
                {
                    str(feature["attributes"][distinct_field]).upper()
                    for feature in records
                    if feature["attributes"].get(distinct_field) not in (None, "")
                }
            )
            return [
                {"attributes": {distinct_field: value}}
                for value in values
            ]
        return sorted(
            records,
            key=lambda feature: int(feature["attributes"]["OBJECTID"]),
        )

    def fetch_count(
        self,
        table_id: int,
        where: str,
        *,
        distinct_field: str | None = None,
    ) -> int:
        self.calls.append(
            (
                "count",
                {
                    "table_id": table_id,
                    "where": where,
                    "distinct_field": distinct_field,
                },
            )
        )
        return len(self._page_records(table_id, where, distinct_field))

    def fetch_page(
        self,
        table_id: int,
        *,
        where: str,
        offset: int,
        record_count: int,
        out_fields: str = "*",
        return_geometry: bool = False,
        distinct_field: str | None = None,
    ) -> tuple[Mapping[str, Any], ...]:
        self.calls.append(
            (
                "page",
                {
                    "table_id": table_id,
                    "where": where,
                    "offset": offset,
                    "record_count": record_count,
                    "out_fields": out_fields,
                    "return_geometry": return_geometry,
                    "distinct_field": distinct_field,
                },
            )
        )
        records = deepcopy(
            self._page_records(table_id, where, distinct_field)[
                offset : offset + record_count
            ]
        )
        if not return_geometry:
            for record in records:
                record.pop("geometry", None)
        return tuple(records)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_deschutes_property,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_sources_preserve_eight_relationships_and_sales_complement() -> None:
    payload = query_deschutes_property.execute(_args(command="sources", query=None))

    assert payload["source_id"] == "us-or-deschutes-county-taxlots"
    assert payload["jurisdiction"]["jurisdiction_id"] == "41017"
    assert len(payload["declared_relationships"]) == 8
    assert {
        relationship["relationship_id"]
        for relationship in payload["declared_relationships"]
    } == set(range(8))
    assert payload["keyed_complements"] == [
        {
            "component": "sales",
            "table_id": 8,
            "table_name": "GIS_SALES",
            "provenance_kind": "same_service_taxlot_key_complement",
            "declared_relationship": False,
            "relationship_id": None,
            "relationship_name": None,
            "declared_cardinality": None,
            "origin_layer_id": 0,
            "origin_key": "TAXLOT",
            "destination_key": "Taxlot",
        }
    ]


def test_parcel_hydration_normalizes_all_published_components() -> None:
    result = query_deschutes_property.execute(
        _args(geometry=True),
        client=FixtureClient(),
    )

    assert result.status.value == "ok"
    assert result.query.jurisdiction.jurisdiction_id == "41017"
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-or-deschutes-county-taxlots/41017/"
        "parcel/141031B000700"
    )
    assert record["native_parcel_id"] == "141031B000700"
    assert record["alternate_parcel_ids"] == (
        "141031B0000",
        "00700",
    )
    assert record["assessment_account_ids"] == ("135278",)
    assert record["owners"][0]["raw_name"] == "VACH,MARIE FLORENCE"
    assert record["situs_address"]["raw"] == "14987 BUGGY WHIP"
    assert record["situs_address"]["raw_address"] == "14987 BUGGY WHIP"
    assert record["mailing_address"]["raw"] == "14987 BUGGY WHIP"
    assert record["mailing_address"]["postal_code"] == "97759"
    assert record["assessment"] == {
        "land_value": 323710,
        "improvement_value": 460800,
        "parcel_value": 784510,
        "assessed_value": 293430,
        "assessment_class": "401",
        "currency": "USD",
        "roll_period": "current_published_roll",
    }
    assert record["physical_characteristics"]["bedrooms"] == 4
    assert record["improvements"][0]["improvement_id"] == 150617
    assert record["property_class_observations"][0]["stat_class"] == "143"
    assert record["active_account_crossrefs"] == (
        {"account_id": 135278, "account_status": "A"},
    )
    assert record["retired_account_history"] == ()
    assert len(record["sale_history"]) == 2
    assert record["last_sale"]["source_document_ref"] == "2018-38616"
    assert record["last_sale"]["sale_date"] == "2018-09-17"
    assert record["last_sale"]["consideration"] == 395000
    assert record["last_sale"]["declared_arcgis_relationship"] is False
    assert record["related_components"]["sales"]["declared_relationship"] is False
    assert record["related_components"]["sales"]["record_count"] == 1
    assert len(record["relationship_contracts"]) == 8
    assert record["source_lineage"]["sales_relationship_status"] == (
        "same_service_taxlot_key_complement"
    )
    assert json.loads(
        query_deschutes_property.canonical_json(record["geometry"])
    ) == PARCEL_BUNDLE["taxlot"]["geometry"]
    assert record["geometry_crs"] == "EPSG:4326"
    assert record["snapshot_complete"] is True


@pytest.mark.parametrize(
    ("field", "selector", "table_id", "distinct_field"),
    [
        ("owner", "VACH", 5, "MAP_TAXLOT"),
        ("address", "14987 BUGGY WHIP", 1, "TaxLot"),
        ("mailing", "14987 BUGGY WHIP", 4, "MAP_TAXLOT"),
        ("sale-party", "VACH", 8, "Taxlot"),
    ],
)
def test_search_uses_verified_distinct_taxlot_indexes(
    field: str,
    selector: str,
    table_id: int,
    distinct_field: str,
) -> None:
    client = FixtureClient()
    result = query_deschutes_property.execute(
        _args(
            command="search",
            query=selector,
            field=field,
            limit=1,
        ),
        client=client,
    )

    assert result.status.value == "ok"
    assert result.records[0]["native_parcel_id"] == "141031B000700"
    index_calls = [
        details
        for operation, details in client.calls
        if operation == "count"
        and details["table_id"] == table_id
        and details["distinct_field"] is not None
    ]
    assert index_calls
    assert index_calls[0]["distinct_field"] == distinct_field


def test_account_search_unions_active_and_retired_indexes_without_duplication() -> None:
    client = FixtureClient()
    client.data[2].append(
        {
            "attributes": {
                "OBJECTID": 99999,
                "taxlot": "141031B000700",
                "year": 1999,
                "account_id": 135278,
            }
        }
    )

    result = query_deschutes_property.execute(
        _args(
            command="search",
            query="135278",
            field="account",
            limit=10,
        ),
        client=client,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["retired_account_history"] == (
        {"account_id": 135278, "year": 1999},
    )
    account_index_tables = {
        details["table_id"]
        for operation, details in client.calls
        if operation == "count"
        and details["distinct_field"] is not None
    }
    assert {2, 9}.issubset(account_index_tables)


def test_cursor_is_query_bound_and_resumes_from_verified_taxlot_anchor() -> None:
    client = FixtureClient()
    extra_owner = deepcopy(client.data[5][0])
    extra_owner["attributes"].update(
        {
            "OBJECTID": 6000,
            "MAP_TAXLOT": "141031B000800",
            "NAME": "VACH SECOND OWNER",
        }
    )
    client.data[5].append(extra_owner)
    plan = query_deschutes_property._search_plan("search", "VACH", "owner")

    first = query_deschutes_property._fetch_distinct_slice(
        client,
        plan,
        limit=1,
        cursor=None,
        geometry=False,
    )
    assert first.taxlots == ("141031B000700",)
    assert first.next_cursor is not None

    second = query_deschutes_property._fetch_distinct_slice(
        client,
        plan,
        limit=1,
        cursor=first.next_cursor,
        geometry=False,
    )
    assert second.taxlots == ("141031B000800",)
    boundary_calls = [
        details
        for operation, details in client.calls
        if operation == "page"
        and details["table_id"] == 5
        and details["offset"] == 0
        and details["record_count"] == 1
        and details["distinct_field"] == "MAP_TAXLOT"
    ]
    assert len(boundary_calls) >= 2

    with pytest.raises(
        query_deschutes_property.DeschutesSelectionError,
        match="different Deschutes property search",
    ):
        query_deschutes_property._fetch_distinct_slice(
            client,
            query_deschutes_property._search_plan(
                "search",
                "DIFFERENT",
                "owner",
            ),
            limit=1,
            cursor=first.next_cursor,
            geometry=False,
        )


def test_count_drift_is_partial_and_disables_continuation() -> None:
    class DriftingClient(FixtureClient):
        def __init__(self) -> None:
            super().__init__()
            extra_owner = deepcopy(self.data[5][0])
            extra_owner["attributes"].update(
                {
                    "OBJECTID": 6000,
                    "MAP_TAXLOT": "141031B000800",
                    "NAME": "VACH SECOND OWNER",
                }
            )
            self.data[5].append(extra_owner)
            self.distinct_counts = [2, 3]

        def fetch_count(
            self,
            table_id: int,
            where: str,
            *,
            distinct_field: str | None = None,
        ) -> int:
            if table_id == 5 and distinct_field == "MAP_TAXLOT":
                return self.distinct_counts.pop(0)
            return super().fetch_count(
                table_id,
                where,
                distinct_field=distinct_field,
            )

    batch = query_deschutes_property._fetch_distinct_slice(
        DriftingClient(),
        query_deschutes_property._search_plan("search", "VACH", "owner"),
        limit=1,
        cursor=None,
        geometry=False,
    )

    assert batch.taxlots == ("141031B000700",)
    assert batch.next_cursor is None
    assert batch.errors[0].code == "count_changed_during_traversal"


def test_declared_one_to_one_cardinality_violation_is_visible_partial() -> None:
    client = FixtureClient()
    duplicate = deepcopy(client.data[4][0])
    duplicate["attributes"]["OBJECTID"] = 99999
    duplicate["attributes"]["M_ADDRESS"] = "SECOND PUBLISHED MAILING ROW"
    client.data[4].append(duplicate)

    result = query_deschutes_property.execute(_args(), client=client)

    assert result.status.value == "partial"
    assert result.records[0]["snapshot_complete"] is False
    assert result.records[0]["related_components"]["mailing"]["record_count"] == 2
    assert "declared_cardinality_exceeded" in {
        error.code for error in result.errors
    }


def test_access_decision_is_injected_enforced_and_applied_to_client() -> None:
    decision = {
        "source_id": query_deschutes_property.SOURCE_ID,
        "allowed": True,
        "limits": {
            "maximum_page_size": 750,
            "minimum_interval_seconds": 0.4,
        },
    }
    result = query_deschutes_property.execute(
        _args(),
        access_decision=decision,
        client=FixtureClient(),
    )

    assert result.status.value == "ok"
    assert result.query.query.to_dict()["metadata"]["access_decision"] == decision

    owned_client = query_deschutes_property._client(
        _args(page_size=1_500, minimum_interval=0.1),
        decision,
    )
    assert owned_client.page_size == 750
    assert owned_client._rate_limiter.minimum_interval == 0.4

    denied = query_deschutes_property.execute(
        _args(),
        access_decision={
            "source_id": query_deschutes_property.SOURCE_ID,
            "allowed": False,
            "reason_code": "review_required",
            "reason": "route review pending",
            "access_class": "C",
        },
        client=FixtureClient(),
    )
    assert denied.status.value == "human_required"
    assert denied.errors[0].code == "review_required"


def test_probe_verifies_inventory_counts_and_sales_provenance() -> None:
    result = query_deschutes_property.execute(
        _args(command="probe", query=None),
        client=FixtureClient(),
    )

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["component_counts"]["taxlot"] == 1
    assert probe["component_counts"]["owners"] == 1
    assert len(probe["declared_relationships"]) == 8
    assert probe["sales_relationship_status"] == {
        "component": "sales",
        "declared_arcgis_relationship": False,
        "provenance_kind": "same_service_taxlot_key_complement",
        "join": "Taxlot -> TAXLOT",
    }
    assert probe["sentinel"]["last_sale"]["source_document_ref"] == "2018-38616"


def test_normalized_envelope_projects_through_property_ingester(
    tmp_path: Path,
) -> None:
    result = query_deschutes_property.execute(
        _args(geometry=True),
        client=FixtureClient(),
    )
    envelope = result.to_dict()
    property_db = tmp_path / "property.db"

    summary = ingest_property_records.ingest_property_envelope(
        envelope,
        db_path=property_db,
    )

    assert summary["records_seen"] == 1
    assert summary["records_ingested"] == 1
    projection = summary["records"][0]
    assert projection["addresses_inserted"] == 2
    assert projection["owners_upserted"] == 1
    assert projection["assessments_upserted"] == 1
    assert projection["sales_upserted"] == 2
    assert projection["geometry_upserted"] == 1
    db = sqlite3.connect(property_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 2
        assert (
            db.execute("SELECT COUNT(*) FROM ownership_assertion").fetchone()[0]
            == 1
        )
    finally:
        db.close()


def test_relationship_schema_change_is_explicit_source_change() -> None:
    client = FixtureClient()
    client.metadata[0]["relationships"].append(
        {
            "id": 8,
            "name": "Unexpected sales relation",
            "relatedTableId": 8,
            "cardinality": "esriRelCardinalityOneToOne",
            "role": "esriRelRoleOrigin",
            "keyField": "TAXLOT",
        }
    )

    result = query_deschutes_property.execute(_args(), client=client)

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert "Sales table relationship status changed" in result.errors[0].message


def test_sql_generation_escapes_quotes_and_auto_routes_selectors() -> None:
    owner = query_deschutes_property._search_plan(
        "search",
        "O'NEIL",
        "owner",
    )
    assert "O''NEIL" in owner.where
    assert "O'NEIL" not in owner.where
    assert query_deschutes_property._auto_field("135278") == "account"
    assert (
        query_deschutes_property._auto_field("141031B000700")
        == "parcel"
    )
    assert (
        query_deschutes_property._auto_field("14987 BUGGY WHIP")
        == "address"
    )
    assert query_deschutes_property._auto_field("VACH") == "owner"


def test_cli_sources_writes_atomic_json(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "sources.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/query_deschutes_property.py",
            "sources",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source_id"] == query_deschutes_property.SOURCE_ID
    assert not list(output.parent.glob(f".{output.name}.*.tmp"))


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DESCHUTES_PROPERTY") != "1",
    reason="set RUN_LIVE_DESCHUTES_PROPERTY=1 for the official live probe",
)
def test_live_official_probe() -> None:
    result = query_deschutes_property.execute(
        _args(
            command="probe",
            query=None,
            timeout=45.0,
            minimum_interval=0.1,
        )
    )

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["component_counts"]["taxlot"] > 100_000
    assert probe["component_counts"]["sales"] > 100_000
    assert probe["sentinel"]["native_parcel_id"] == "141031B000700"
    assert (
        probe["sentinel"]["source_lineage"][
            "sales_declared_arcgis_relationship"
        ]
        is False
    )
