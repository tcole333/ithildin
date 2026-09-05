from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from tools import query_nyc_pip as pip
from tools import public_records_monitor
from tools import query_property
from tools import source_report
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import PaginatedFetch
from tools.public_records_monitor import ProbeContext
from tools.public_records_search_plan import build_search_plan
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


SOURCE_ID = pip.SOURCE_ID
FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "public_records" / "nyc_pip"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _normalize(component: str, feature: dict[str, Any]) -> dict[str, Any]:
    return pip.normalize_feature(
        feature,
        pip.LAYER_SPECS[component],
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint=f"{component}-schema",
    )


def _metadata(component: str) -> dict[str, Any]:
    metadata = copy.deepcopy(_fixture("source_contract.json")["layers"][component])
    metadata["fields"] = [
        {
            "name": field,
            "type": (
                "esriFieldTypeOID" if field == "OBJECTID" else "esriFieldTypeString"
            ),
            "nullable": field != "OBJECTID",
        }
        for field in pip.LAYER_SPECS[component].required_fields
    ]
    return metadata


class _MonitorClient:
    def __init__(self, component: str, records: list[dict[str, Any]]) -> None:
        self.component = component
        self.records = records
        self.request_count = 0
        self.page_size = 1
        self.calls: list[dict[str, Any]] = []

    def metadata(self) -> dict[str, Any]:
        self.request_count += 1
        return _metadata(self.component)

    def query(self, **kwargs: Any) -> PaginatedFetch:
        self.request_count += 1
        self.calls.append(kwargs)
        return PaginatedFetch(
            records=self.records,
            next_cursor=None,
            schema={"component": self.component, "fields": ["stable"]},
            schema_fingerprint=f"{self.component}-response-schema",
            pages_fetched=1,
            requests_made=1,
        )


def _monitor_clients(
    raw: dict[str, Any] | None = None,
) -> dict[str, _MonitorClient]:
    bundle = copy.deepcopy(raw or _fixture("sentinel_bundle.json"))
    return {
        component: _MonitorClient(
            component,
            list(value if isinstance(value, list) else [value]),
        )
        for component, value in (
            ("detail", bundle["detail"]),
            ("tax_lot", bundle["tax_lot"]),
            ("current_assessment", bundle["current_assessment"]),
            ("assessment_history", bundle["assessment_history"]),
            ("exemptions", bundle["exemptions"]),
        )
    }


def _sentinel_records() -> list[dict[str, Any]]:
    raw = _fixture("sentinel_bundle.json")
    detail = _normalize("detail", copy.deepcopy(raw["detail"]))
    detail_duplicate_feature = copy.deepcopy(raw["detail"])
    detail_duplicate_feature["attributes"]["OBJECTID"] = 124751
    detail_duplicate_feature["attributes"]["BLDG_STORY"] = 99
    detail_duplicate = _normalize("detail", detail_duplicate_feature)

    tax_lot = _normalize("tax_lot", copy.deepcopy(raw["tax_lot"]))
    current = _normalize(
        "current_assessment", copy.deepcopy(raw["current_assessment"])
    )
    lower_period_feature = copy.deepcopy(raw["current_assessment"])
    lower_period_feature["attributes"].update(
        {"OBJECTID": 1, "PERIOD": "2", "MARKET_VALUE": 1}
    )
    lower_period = _normalize("current_assessment", lower_period_feature)
    higher_period_feature = copy.deepcopy(raw["current_assessment"])
    higher_period_feature["attributes"].update(
        {"OBJECTID": 999999, "PERIOD": "4", "MARKET_VALUE": 77000000}
    )
    higher_period = _normalize("current_assessment", higher_period_feature)
    history = [
        _normalize("assessment_history", copy.deepcopy(feature))
        for feature in raw["assessment_history"]
    ]

    exemptions = [
        _normalize("exemptions", copy.deepcopy(raw["synthetic_exemption"]))
    ]
    duplicate_exemption_feature = copy.deepcopy(raw["synthetic_exemption"])
    duplicate_exemption_feature["attributes"]["OBJECTID"] = 902
    exemptions.append(_normalize("exemptions", duplicate_exemption_feature))
    pip._annotate_exemption_duplicate_ordinals(
        exemptions,
        complete_exact_bbl_result=True,
    )
    return [
        detail_duplicate,
        detail,
        tax_lot,
        lower_period,
        current,
        higher_period,
        *history,
        *exemptions,
    ]


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    return PublicRecordsResult.success(
        pip.build_query("bbl", selector=pip.PROBE_BBL),
        records,
        retrieved_at="2026-07-31T12:00:00Z",
    ).to_dict()


def test_shared_router_exposes_all_pip_components_without_an_implicit_window() -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    assert set(routes) == {
        "parcel",
        "owner",
        "address",
        "detail",
        "map",
        "assessment",
        "history",
        "exemptions",
        "discovery",
        "probe",
    }

    parcel = routes["parcel"].translate(
        _shared_args("parcel", "1-01386-0010", "--source", SOURCE_ID),
        routes["parcel"].adapter_command,
    )
    lot = routes["parcel"].translate(
        _shared_args(
            "parcel",
            "Manhattan/1386/10",
            "--source",
            SOURCE_ID,
        ),
        routes["parcel"].adapter_command,
    )
    owner = routes["owner"].translate(
        _shared_args(
            "owner",
            "BOLT 1 L.P.",
            "--source",
            SOURCE_ID,
            "--search-field",
            "exact",
        ),
        routes["owner"].adapter_command,
    )
    history = routes["history"].translate(
        _shared_args("history", pip.PROBE_BBL, "--source", SOURCE_ID),
        routes["history"].adapter_command,
    )
    bounded = routes["exemptions"].translate(
        _shared_args(
            "exemptions",
            pip.PROBE_BBL,
            "--source",
            SOURCE_ID,
            "--limit",
            "7",
            "--max-records",
            "11",
        ),
        routes["exemptions"].adapter_command,
    )

    assert parcel.command == "bbl"
    assert parcel.query == pip.PROBE_BBL
    assert getattr(parcel, "limit", None) is None
    assert getattr(parcel, "max_records", None) is None
    assert lot.command == "lot"
    assert (lot.borough, lot.block, lot.lot) == ("Manhattan", "1386", "10")
    assert owner.command == "owner"
    assert owner.match == "exact"
    assert owner.limit is None
    assert owner.max_records is None
    assert history.command == "assessment-history"
    assert history.limit is None
    assert history.max_records is None
    assert bounded.command == "exemptions"
    assert bounded.limit == 7
    assert bounded.max_records == 11


def test_ingest_preserves_occurrences_and_projects_only_deterministic_current_data(
    tmp_path: Path,
) -> None:
    records = _sentinel_records()
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope(records), db_path=db_path)

    assert report["records_ingested"] == len(records)
    assert all(row["recorded_instruments_upserted"] == 0 for row in report["records"])
    assert all(row["sales_upserted"] == 0 for row in report["records"])
    assert all(row["title_assertions_upserted"] == 0 for row in report["records"])
    assert all(row["document_artifacts_upserted"] == 0 for row in report["records"])

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT native_parcel_id, roll_year, observation_id, raw_json
            FROM parcel_snapshot WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        observations = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind != 'query_envelope'
            ORDER BY observation_id
            """,
            (SOURCE_ID,),
        ).fetchall()
        owners = db.execute(
            "SELECT * FROM ownership_assertion WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchall()
        addresses = db.execute(
            "SELECT * FROM parcel_address WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchall()
        assessments = db.execute(
            "SELECT * FROM assessment WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchall()
        geometry = db.execute(
            "SELECT * FROM parcel_geometry WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()
        instruments = db.execute(
            "SELECT count(*) AS n FROM recorded_instrument WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()["n"]
        sales = db.execute(
            "SELECT count(*) AS n FROM sale_event WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()["n"]
        artifacts = db.execute(
            "SELECT count(*) AS n FROM document_artifact WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()["n"]
    finally:
        db.close()

    parcel_raw = json.loads(parcel["raw_json"])
    assert parcel["native_parcel_id"] == pip.PROBE_BBL
    assert parcel["roll_year"] == ""
    assert parcel["observation_id"] is None
    assert parcel_raw["record_kind"] == "nyc_dof_pip_parcel_identity"
    assert "building" not in parcel_raw

    assert len(observations) == len(records)
    occurrence_ids = {row["source_native_id"] for row in observations}
    assert f"detail:{pip.PROBE_BBL}:124750" in occurrence_ids
    assert f"detail:{pip.PROBE_BBL}:124751" in occurrence_ids
    assert f"current_assessment:{pip.PROBE_BBL}:139025" in occurrence_ids
    assert f"assessment_history:{pip.PROBE_BBL}:12796579" in occurrence_ids
    assert f"exemptions:{pip.PROBE_BBL}:901" in occurrence_ids
    assert f"exemptions:{pip.PROBE_BBL}:902" in occurrence_ids

    assert len(owners) == 1
    assert owners[0]["raw_owner_name"] == "BOLT 1 L.P."
    assert owners[0]["assertion_type"] == "assessment_roll"
    assert len(addresses) == 1
    assert addresses[0]["raw_address"] == "9 EAST 71 STREET, NEW YORK, NY, 10021"

    assert len(assessments) == 1
    assessment_raw = json.loads(assessments[0]["raw_json"])
    assert assessment_raw["projection_choice"] == {
        "object_id": "999999",
        "period": "4",
        "representation": "current_assessment",
        "same_assessment_key": (
            f"US-NYC-DOF:ASSESSMENT:{pip.PROBE_BBL}:2027:4"
        ),
        "tax_year": "2027",
    }
    assert assessments[0]["market_value_minor"] == 7_700_000_000
    assert geometry["geometry_ref"].endswith(
        f":tax_lot:{pip.PROBE_BBL}:1775#/geometry"
    )

    history_rows = [
        json.loads(row["raw_json"])
        for row in observations
        if row["record_kind"] == "nyc_dof_historical_assessment_observation"
    ]
    assert {row["assessment"]["representation"] for row in history_rows} == {
        "assessment_history"
    }
    exemption_rows = [
        json.loads(row["raw_json"])
        for row in observations
        if row["record_kind"] == "nyc_dof_exemption_observation"
    ]
    assert [
        row["exemption_identity"]["duplicate_ordinal"] for row in exemption_rows
    ] == [1, 2]
    assert all("PARID_ORG" in row["raw_attributes"] for row in exemption_rows)
    assert instruments == sales == artifacts == 0


def test_monitor_uses_fixed_native_bounds_and_separates_stable_from_rolling_hashes() -> None:
    context = ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5.0,
        max_attempts=7,
        sample_bytes=None,
    )
    clients = _monitor_clients()
    first = public_records_monitor.probe_nyc_pip(context, clients=clients)

    assert first.status == "ok"
    assert first.details["requests_made"] == 10
    assert first.details["request_counts"] == {
        component: 2 for component in pip.BUNDLE_LAYER_KEYS
    }
    for component, client in clients.items():
        assert client.request_count == 2
        assert len(client.calls) == 1
        call = client.calls[0]
        native_page_size = _metadata(component)["maxRecordCount"]
        assert call["requested_limit"] == native_page_size
        assert call["max_records"] == native_page_size
        assert call["cursor"] is None

    changed = _fixture("sentinel_bundle.json")
    changed["detail"]["attributes"]["OWNER"] = "ROLLING OWNER"
    changed["current_assessment"]["attributes"].update(
        {"OBJECTID": 139026, "MARKET_VALUE": 123, "TAXYR": 2029}
    )
    extra_current = copy.deepcopy(changed["current_assessment"])
    extra_current["attributes"]["OBJECTID"] = 139027
    changed["current_assessment"] = [changed["current_assessment"], extra_current]
    changed["assessment_history"][0]["attributes"]["TAXYR"] = 2029
    second = public_records_monitor.probe_nyc_pip(
        context,
        clients=_monitor_clients(changed),
    )

    assert second.artifact_sha256 == first.artifact_sha256
    assert second.schema_sha256 == first.schema_sha256
    assert second.details["stable_contract_hashes"] == first.details[
        "stable_contract_hashes"
    ]
    for rolling_key in (
        "owners_sha256",
        "values_sha256",
        "years_sha256",
        "counts_sha256",
        "object_ids_sha256",
    ):
        assert second.details["rolling_hashes"][rolling_key] != first.details[
            "rolling_hashes"
        ][rolling_key]

    registered = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert registered.handler is public_records_monitor.probe_nyc_pip
    assert registered.expected_requests == 10


def test_catalog_census_search_plan_report_and_citation_cover_all_five_boroughs(
    tmp_path: Path,
) -> None:
    source_config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    manifests = [
        source
        for source in source_config["sources"]
        if source["source_id"] == SOURCE_ID
    ]
    assert len(manifests) == 1
    manifest = manifests[0]
    assert manifest["jurisdiction_geoids"] == [
        "36005",
        "36047",
        "36061",
        "36081",
        "36085",
    ]
    assert {capability["name"] for capability in manifest["capabilities"]} >= {
        "search_owner",
        "search_address",
        "fetch_parcel",
        "fetch_detail",
        "fetch_geometry",
        "fetch_current_assessment",
        "fetch_assessment_history",
        "fetch_exemptions",
        "discover_layers",
        "query_shared_property_records",
        "ingest_property_records",
        "probe_source",
    }
    complements = {
        complement["source_id"]: complement
        for complement in manifest["official_complements"]
    }
    assert complements["us-nyc-acris"][
        "independent_evidence_for_same_acris_record"
    ] is False
    assert complements["us-ny-richmond-county-clerk-land-documents"] == {
        "source_id": "us-ny-richmond-county-clerk-land-documents",
        "authority": "Richmond County Clerk",
        "url": "https://richmondcountyclerk.com/Search/SearchIndex",
        "coverage": ["Staten_Island"],
        "relationship": "field_matched_complete_recorded_instrument",
        "independent_publisher_lineage": True,
        "field_matched_role": "recorded_instrument",
        "duplicate_corroboration_for_pip_observation": False,
    }

    census = yaml.safe_load(
        Path("config/public_records_census.yaml").read_text(encoding="utf-8")
    )
    borough_geoids = {"36005", "36047", "36061", "36081", "36085"}
    jurisdiction_geoids = {
        row["geoid"] for row in census["additional_jurisdictions"]
    }
    assert borough_geoids <= jurisdiction_geoids
    borough_targets = {
        (row["jurisdiction_geoid"], row["role"])
        for row in census["additional_targets"]
        if row["jurisdiction_geoid"] in borough_geoids
    }
    assert borough_targets == {
        (geoid, role)
        for geoid in borough_geoids
        for role in ("assessment_roll", "parcel_geometry")
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "BOLT 1 L.P.",
        addresses=["9 EAST 71 STREET, NEW YORK, NY 10021"],
        jurisdictions=["36061"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    tasks = {
        task["task_id"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    }
    assert {
        f"property.{SOURCE_ID}.search_owner",
        f"property.{SOURCE_ID}.search_address",
        f"property.{SOURCE_ID}.fetch_parcel",
        f"property.{SOURCE_ID}.fetch_detail",
        f"property.{SOURCE_ID}.fetch_geometry",
        f"property.{SOURCE_ID}.fetch_current_assessment",
        f"property.{SOURCE_ID}.fetch_assessment_history",
        f"property.{SOURCE_ID}.fetch_exemptions",
    } <= tasks

    report = source_report.check_public_records_catalog(catalog_path)
    source_health = report["Public records / NYC Property Information Portal"]
    assert source_health["source_id"] == SOURCE_ID
    assert source_health["status"] == "configured"
    assert source_health["query_tool"] == "tools/query_property.py"

    citation_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert citation_urls[f"PROPERTY_SOURCE:{SOURCE_ID}"] == pip.PIP_URL
