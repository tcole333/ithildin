from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools import oregon_county_property_projection as projection
from tools import ingest_property_records as property_ingest
from tools import query_oregon_clackamas_property as clackamas
from tools import query_oregon_multnomah_sail as multnomah
from tools import query_oregon_wasco_property as wasco
from tools import query_oregon_washington_case_permits as washington_cases
from tools import query_oregon_washington_property as washington
from tools import query_oregon_yamhill_property as yamhill


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "public_records"
WASHINGTON_CASE_FIXTURE_ROOT = (
    Path(__file__).parent / "fixtures" / "washington_county_case_permits"
)


def fixture_text(county: str, name: str) -> str:
    return (FIXTURE_ROOT / county / name).read_text()


def fixture_json(county: str, name: str) -> Any:
    return json.loads((FIXTURE_ROOT / county / name).read_text())


def test_source_sets_are_explicit_disjoint_and_complete() -> None:
    assert not (
        projection.ASSESSOR_SOURCE_IDS
        & projection.PROPERTY_EVENT_SOURCE_IDS
    )
    assert not (
        projection.ASSESSOR_SOURCE_IDS
        & projection.OBSERVATION_ONLY_SOURCE_IDS
    )
    assert not (
        projection.PROPERTY_EVENT_SOURCE_IDS
        & projection.OBSERVATION_ONLY_SOURCE_IDS
    )
    assert projection.SUPPORTED_SOURCE_IDS == (
        projection.ASSESSOR_SOURCE_IDS
        | projection.PROPERTY_EVENT_SOURCE_IDS
        | projection.OBSERVATION_ONLY_SOURCE_IDS
    )
    assert projection.WASCO_SURVEY_SOURCE_IDS == frozenset(
        wasco.SURVEY_SOURCE_IDS
    )
    assert projection.WASHINGTON_PROPERTY_SOURCE_IDS == frozenset(
        washington.SOURCES
    )
    assert projection.MULTNOMAH_PROPERTY_SOURCE_IDS == frozenset(
        multnomah.SOURCE_IDS
    )
    assert projection.WASHINGTON_CASE_PERMIT_SOURCE_IDS == frozenset(
        washington_cases.SOURCES
    )


def test_yamhill_account_fixture_projects_real_years_owners_and_sales() -> None:
    native = yamhill.parse_ascend_detail(
        fixture_text("oregon_yamhill_property", "detail_41270.html"),
        source_url=f"{yamhill.ASCEND_DETAIL_URL}?parcel_number=41270",
    )
    before = deepcopy(native)

    decision = projection.project_record(native)

    assert decision.kind == "assessor"
    record = decision.record
    assert record["native_parcel_id"] == "41270"
    assert record["jurisdiction"]["county_geoid"] == "41071"
    assert [owner["raw_name"] for owner in record["owners"]] == [
        "LUTZE ALBERT L CO-TRUSTEE",
        "LUTZE JUDY A CO-TRUSTEE",
        "LUTZE ALBERT & JUDY FAMILY RL TRUST",
    ]
    assert all(owner["role"] == "owner" for owner in record["owners"])
    assert record["assessment_history"][0] == {
        "tax_year": "2025",
        "assessed_value": 169_823,
        "market_value": 354_775,
        "source_value_observations": {
            "assessed_value": {
                "value_type": "Assessed Value",
                "value_code": "AVR",
                "amount": 169_823,
                "raw": "$169,823",
            },
            "market_value": {
                "value_type": "Real Market Total",
                "value_code": "MKTTL",
                "amount": 354_775,
                "raw": "$354,775",
            },
        },
    }
    assert record["sale_history"][1]["consideration"] == 350_000
    assert record["sale_history"][1]["source_document_ref"] == "2024-00119"
    assert record["situs_address"]["raw"].startswith("1802 N MAIN ST")
    assert record["parties"] == native["parties"]
    assert record["value_history"] == native["value_history"]
    assert native == before


def test_clackamas_account_does_not_invent_years_from_native_placeholders() -> None:
    native = clackamas.parse_ascend_detail(
        fixture_text(
            "oregon_clackamas_property",
            "ascend_detail_01092276.html",
        ),
        source_url=(
            f"{clackamas.ASCEND_DETAIL_URL}?parcel_number=01092276"
        ),
    )

    record = projection.project_assessor_record(native)

    assert record["native_parcel_id"] == "01092276"
    assert record["jurisdiction"]["county_geoid"] == "41005"
    assert [owner["raw_name"] for owner in record["owners"]] == [
        "MOLALLA APARTMENTS LIMITED PARTNERSHIP"
    ]
    assert "assessment_history" not in record
    assert record["value_history"][0]["native_columns"][0][
        "native_label"
    ] == "Tax Year 1"
    assert record["sale_history"][0]["sale_date"] == "2022-06-28"
    assert record["sale_history"][0]["consideration"] == 1_220_000
    assert record["situs_address"]["raw"] == (
        "1000 W MAIN ST, MOLALLA, OR 97038"
    )


def test_wasco_account_projects_published_years_without_owner_inference() -> None:
    native = wasco.parse_ascend_detail(
        fixture_text("oregon_wasco_property", "detail_9450.html"),
        source_url=f"{wasco.ASCEND_MANIFEST.detail_url}?parcel_number=9450",
    )

    record = projection.project_assessor_record(native)

    assert record["native_parcel_id"] == "9450"
    assert record["jurisdiction"]["county_geoid"] == "41065"
    assert record["owners"] == []
    assert record["party_section_observed"] is False
    assert record["assessment_history"][0]["market_value"] == 450_000
    assert record["assessment_history"][0]["assessed_value"] == 333_835
    assert record["sale_history"][0]["sale_date"] == "2007-04-06"
    assert record["sale_history"][0]["source_document_ref"] == "000027323"


def test_yamhill_taxlot_fixture_keeps_native_evidence_and_join_aliases() -> None:
    feature = fixture_json(
        "oregon_yamhill_property",
        "current_feature.json",
    )
    native = yamhill._normalize_taxlot(
        yamhill.TAXLOTS,
        feature,
        schema_value="fixture-schema",
        geometry_requested=True,
    )

    record = projection.project_assessor_record(native)

    assert record["native_parcel_id"] == "5144427"
    assert {
        "41270",
        "R3218AB 00301",
        "R3218AB00301",
        "1a1ff27a-6ad3-48c2-8180-42f7e7ef2f7f",
    } <= set(record["alternate_parcel_ids"])
    assert record["owners"][0]["raw_name"] == (
        "LUTZE ALBERT & JUDY FAMILY RL TRUST"
    )
    assert record["situs_address"] == {
        "raw": "1802 N MAIN ST",
        "country": "US",
        "city": "NEWBERG",
        "state": "OR",
        "postal_code": "97132",
    }
    assert record["mailing_address"]["raw"] == "1802 N MAIN ST"
    assert record["last_sale"]["source_document_ref"] == "2026-03177"
    assert record["last_sale"]["sale_date"] == "2026-04-07"
    assert record["raw_attributes"] == native["raw_attributes"]
    assert record["geometry"] == native["geometry"]


def test_retired_yamhill_taxlot_keeps_owner_rows_without_current_owner_projection() -> None:
    feature = fixture_json(
        "oregon_yamhill_property",
        "retired_feature.json",
    )
    native = yamhill._normalize_taxlot(
        yamhill.RETIRED_TAXLOTS,
        feature,
        schema_value="fixture-schema",
        geometry_requested=True,
    )

    record = projection.project_assessor_record(native)

    assert native["owners"][0]["name"] == "PUBLISHED OWNER"
    assert record["owners"] == []
    assert record["snapshot_complete"] is False
    assert record["projection_metadata"] == {
        "owner_projection": "not_projected_from_retired_representation",
        "published_owner_rows_preserved": True,
    }
    assert record["lineage"]["parent_taxlot"] == "R6701 00400"


def test_clackamas_cmap_fixture_projects_values_without_owner_claim() -> None:
    feature = fixture_json(
        "oregon_clackamas_property",
        "cmap_features.json",
    )["features"][0]
    native = clackamas._normalize_cmap(
        feature,
        schema_fingerprint="fixture-schema",
        geometry_requested=True,
    )

    record = projection.project_assessor_record(native)

    assert record["native_parcel_id"] == "109341"
    assert {"01092276", "52E08C 01500", "52E08C01500"} <= set(
        record["alternate_parcel_ids"]
    )
    assert record["owners"] == []
    assert record["assessment"]["land_value"] == 2_672_651
    assert record["assessment"]["improvement_value"] == 12_075_430
    assert record["assessment"]["market_value"] == 14_748_081
    assert record["assessment"]["assessed_value"] == 7_152_819
    assert record["last_sale"]["source_document_ref"] == "2022-037981"
    assert record["last_sale"]["sale_date"] == "2022-06-28"
    assert record["owner_name_component_behavior"][
        "owner_field_present"
    ] is False


def test_wasco_taxlot_projects_taxpayer_as_evidence_not_owner() -> None:
    feature = {
        "attributes": {
            "OBJECTID": 6_575_814,
            "AccountNum": 9450,
            "MapTaxlot": "1S 13E 25 CB 6000",
            "Taxpayer": "DILLON JOHN",
            "MailingAddress1": "PO BOX 357",
            "MailingAddress2": None,
            "MailingAddress3": None,
            "MailingCity": "DUFUR",
            "MailingState": "Oregon",
            "MailingZIP": "97021",
            "CalculatedAcres": 0.46278017,
        },
        "geometry": {"rings": [[[-121.0, 45.0], [-121.1, 45.0]]]},
    }
    native = wasco._normalize_taxlot(
        feature,
        schema_value="fixture-schema",
        geometry_requested=True,
    )

    record = projection.project_assessor_record(native)

    assert record["native_parcel_id"] == "6575814"
    assert {"9450", "1S 13E 25 CB 6000", "1S13E25CB6000"} <= set(
        record["alternate_parcel_ids"]
    )
    assert record["taxpayer"] == "DILLON JOHN"
    assert record["owners"] == []
    assert record["mailing_address"] == {
        "raw": "PO BOX 357",
        "country": "US",
        "city": "DUFUR",
        "state": "Oregon",
        "postal_code": "97021",
    }


def test_yamhill_permit_fixture_projects_event_and_exact_taxlot_candidate() -> None:
    feature = fixture_json(
        "oregon_yamhill_property",
        "permit_features.json",
    )["features"][0]
    native = yamhill._normalize_permit(
        yamhill.PERMITS,
        feature,
        schema_value="fixture-schema",
        geometry_requested=True,
    )
    before = deepcopy(native)

    decision = projection.project_record(native)

    assert decision.kind == "property_event"
    record = decision.record
    assert record["native_event_id"] == "979-25-001787-ELEC"
    assert record["source_record_id"] == "1"
    assert record["jurisdiction"]["county_geoid"] == "41071"
    assert record["event_type"] == "assessment_permit"
    assert record["description"] == "10.066 kw ground mounted solar system"
    assert record["event_dates"]["approved"] == {
        "raw": 1_750_032_000_000,
        "utc_datetime": "2025-06-16T00:00:00Z",
        "utc_date": "2025-06-16",
        "source_semantics": "issue_date",
    }
    assert record["parcel_join_evidence"]["published_location"] == {
        "raw": "R6801 00600",
        "normalized_candidate": "R680100600",
    }
    assert [person["raw_name"] for person in record["people"]] == [
        "FOSTER KIMBERLY D",
        "FOSTER MARK E",
    ]
    assert record["address"]["raw"] == "47484 SW HEBO RD"
    assert record["raw_attributes"] == native["raw_attributes"]
    assert native == before


def test_washington_casefile_projects_dated_planning_event() -> None:
    payload = json.loads(
        (WASHINGTON_CASE_FIXTURE_ROOT / "case_exact.json").read_text()
    )
    raw = payload["data"][0]
    schema, fingerprint = washington_cases._schema_bundle(payload["data"])
    native = washington_cases._case_record(
        raw,
        source_url=washington_cases.CASEFILE_SEARCH_URL,
        operation="case_detail",
        schema=schema,
        fingerprint=fingerprint,
    )
    before = deepcopy(native)

    decision = projection.project_record(native)

    assert decision.kind == "property_event"
    record = decision.record
    assert record["native_event_id"] == "L2500106"
    assert record["source_record_id"] == "S2500112"
    assert record["jurisdiction"]["county_geoid"] == "41067"
    assert record["event_type"] == "planning_casefile"
    assert record["event_dates"]["submitted"]["utc_date"] == "2025-04-22"
    assert record["event_dates"]["last_update"]["utc_date"] == "2025-04-23"
    assert record["parcel_join_evidence"]["published_location"] == {
        "raw": "2N2330002700",
        "normalized_candidate": "2N2330002700",
    }
    assert [person["role"] for person in record["people"]] == [
        "applicant",
        "assigned_staff",
    ]
    assert {item["kind"] for item in record["detail_representations"]} == {
        "api_representation",
        "interactive_casefile",
        "accela_detail",
    }
    assert native == before


def test_washington_inspection_report_projects_dated_event() -> None:
    payload = json.loads(
        (WASHINGTON_CASE_FIXTURE_ROOT / "report_inspection.json").read_text()
    )
    raw = payload["data"][0]
    schema, fingerprint = washington_cases._schema_bundle(payload["data"])
    native_id = washington_cases._report_native_id("inspection", raw)
    native = {
        "canonical_ref": washington_cases._native_ref(
            washington_cases.PERMIT_REPORT_SOURCE_ID,
            "inspection_report",
            native_id,
        ),
        "source_id": washington_cases.PERMIT_REPORT_SOURCE_ID,
        "record_kind": "inspection_report",
        "native_record_id": native_id,
        "status": raw["Insp_Result"],
        "type": raw["Insp_ID"],
        "description": raw["Insp_Comments"],
        "dates": washington_cases._report_dates("inspection", raw),
        "joins": washington_cases._report_joins("inspection", raw),
        "source_urls": {
            "api_representation": washington_cases.PERMIT_REPORT_URL,
        },
        "schema": schema,
        "schema_fingerprint": fingerprint,
        "source_native": raw,
    }

    decision = projection.project_record(native)

    assert decision.kind == "property_event"
    assert decision.record["event_type"] == "permit_inspection"
    assert (
        decision.record["event_dates"]["last_update"]["utc_date"]
        == "2006-09-07"
    )
    assert decision.record["people"] == [
        {
            "raw_name": "jp",
            "role": "inspector",
            "assertion_type": "published_planning_or_permit_record",
        }
    ]
    assert decision.record["parcel_join_evidence"]["published_taxlots"] == []


@pytest.mark.parametrize(
    ("source_id", "record"),
    (
        (
            washington_cases.CASEFILE_SOURCE_ID,
            {
                "record_kind": "casefile_staff_vocabulary",
                "native_record_id": "KELLIEC",
            },
        ),
        (
            washington_cases.TAXLOT_ACTIVITY_SOURCE_ID,
            {
                "record_kind": "taxlot_projects",
                "native_record_id": "P0138681",
            },
        ),
        (
            washington_cases.BUILDING_SOURCE_ID,
            {
                "record_kind": "building_permit_type",
                "native_record_id": "Building|Residential|New",
            },
        ),
        (
            washington_cases.PERMIT_REPORT_SOURCE_ID,
            {
                "record_kind": "people_report",
                "native_record_id": "JOHN CRABB|Applicant",
                "dates": {},
            },
        ),
        (
            washington_cases.ACCELA_SOURCE_ID,
            {
                "record_kind": "accela_document_detail",
                "native_record_id": "628906",
                "casefile_number": "L2500106",
                "document_number": "628906",
            },
        ),
        (
            washington_cases.DOCUMENT_ROUTE_SOURCE_ID,
            {
                "record_kind": "casefile_document_routes",
                "native_record_id": "L2500106",
                "casefile_number": "L2500106",
            },
        ),
    ),
)
def test_washington_supporting_records_remain_observations(
    source_id: str,
    record: dict[str, Any],
) -> None:
    native = {"source_id": source_id, **record}

    decision = projection.project_record(native)

    assert decision.kind == "observation_only"
    assert decision.source_native_id
    assert decision.observation_kind == record["record_kind"]


def test_projected_records_satisfy_shared_ingester_contracts(tmp_path: Path) -> None:
    taxlot_feature = fixture_json(
        "oregon_yamhill_property",
        "current_feature.json",
    )
    taxlot_native = yamhill._normalize_taxlot(
        yamhill.TAXLOTS,
        taxlot_feature,
        schema_value="fixture-schema",
        geometry_requested=True,
    )
    taxlot = projection.project_assessor_record(taxlot_native)
    permit_feature = fixture_json(
        "oregon_yamhill_property",
        "permit_features.json",
    )["features"][0]
    permit_native = yamhill._normalize_permit(
        yamhill.PERMITS,
        permit_feature,
        schema_value="fixture-schema",
        geometry_requested=True,
    )
    permit = projection.project_yamhill_permit_record(permit_native)
    retrieved_at = "2026-07-30T12:00:00Z"
    database = property_ingest.connect_property(tmp_path / "property.db")
    try:
        with database:
            assessor_result = property_ingest._ingest_assessor_record(
                database,
                envelope={
                    "query": {"fingerprint": "fixture-taxlot-query"},
                    "retrieved_at": retrieved_at,
                    "status": "ok",
                    "warnings": [],
                },
                record=taxlot,
                source_id=yamhill.TAXLOT_SOURCE_ID,
                raw_artifact_path=None,
                raw_artifact_sha256=None,
            )
            event_result = property_ingest._ingest_property_event_record(
                database,
                envelope={
                    "query": {"fingerprint": "fixture-permit-query"},
                    "retrieved_at": retrieved_at,
                    "status": "ok",
                    "warnings": [],
                },
                record=permit,
                source_id=yamhill.PERMIT_SOURCE_ID,
                raw_artifact_path=None,
                raw_artifact_sha256=None,
                expected_geoid="41071",
                parcel_alias_source_id=yamhill.TAXLOT_SOURCE_ID,
            )
    finally:
        database.close()

    assert assessor_result["owners_upserted"] == 3
    assert assessor_result["geometry_upserted"] == 1
    assert event_result["parties_upserted"] == 2
    assert event_result["parcel_link_method"] == (
        "unresolved_published_map_taxlot"
    )


def test_all_wasco_survey_sources_are_observations_not_title_records() -> None:
    for source_id in sorted(projection.WASCO_SURVEY_SOURCE_IDS):
        native = {
            "source_id": source_id,
            "source_record_id": "17",
            "object_id": 17,
            "record_kind": "source_native_survey_reference",
            "native_identity": "1999-0014",
            "attributes": {
                "OBJECTID": 17,
                "DocNumber": "1999-0014",
            },
        }
        before = deepcopy(native)

        decision = projection.project_record(native)

        assert decision.kind == "observation_only"
        assert decision.source_id == source_id
        assert decision.source_native_id == "17"
        assert decision.observation_kind == (
            projection.WASCO_SURVEY_OBSERVATION_CLASSES[source_id]
        )
        assert decision.reason == (
            "wasco_survey_reference_not_assessor_or_title_projection"
        )
        assert decision.record == before
        assert "sale_history" not in decision.record
        assert "deed_history" not in decision.record
        assert "native_event_id" not in decision.record
        assert native == before


def test_washington_intermap_assessment_projects_published_values_and_joins() -> None:
    source_url = washington.intermap_url(
        washington.PROBE_TAXLOT,
        "assessment",
    )
    representation = washington.parse_html_representation(
        fixture_text(
            "oregon_washington_property",
            "intermap_assessment.html",
        ),
        source_url=source_url,
        include_raw_html=True,
    )
    native = {
        "record_type": "intermap_assessment_report",
        "report": "assessment",
        "native_ids": {
            "IDValue": washington.PROBE_TAXLOT,
            "TLNO": washington.PROBE_TAXLOT,
            "account": washington.PROBE_ACCOUNT,
        },
        "native_representation": representation,
        "source_id": washington.INTERMAP_SOURCE_ID,
        "source_url": source_url,
    }

    decision = projection.project_record(native)

    assert decision.kind == "assessor"
    record = decision.record
    assert record["native_parcel_id"] == washington.PROBE_TAXLOT
    assert washington.PROBE_ACCOUNT in record["alternate_parcel_ids"]
    assert record["jurisdiction"]["county_geoid"] == "41067"
    assert record["situs_address"]["raw"] == "12311 NW JACKSON QUARRY RD"
    assert record["assessment"]["market_value"] == 2_300_360
    assert record["assessment"]["assessed_value"] == 1_337_020
    assert record["legal_description"] == "1997-051 PARTITION PLAT, LOT 3"
    assert record["snapshot_complete"] is False
    assert record["native_representation"]["raw_html"].startswith("<!doctype")


def test_washington_tax_account_projects_owner_value_and_statement_year() -> None:
    source_url = (
        f"{washington.TAX_BASE_URL}/Property-Detail/"
        f"PropertyQuickRefID/{washington.PROBE_ACCOUNT}"
    )
    native = washington.parse_tax_account(
        fixture_text(
            "oregon_washington_property",
            "tax_account.html",
        ),
        source_url=source_url,
        requested_account=washington.PROBE_ACCOUNT,
    )

    decision = projection.project_record(native)

    assert decision.kind == "assessor"
    record = decision.record
    assert record["native_parcel_id"] == washington.PROBE_ACCOUNT
    assert record["jurisdiction"]["county_geoid"] == "41067"
    assert record["owners"] == [
        {
            "raw_name": "CRABB, JOHN & DAVIS, TASSY LEI",
            "confidence": "high",
        }
    ]
    assert record["assessment"] == {
        "tax_year": "2025",
        "market_value": 2_300_360,
        "parcel_value": 2_300_360,
        "source_display_field": "displayed_real_market_value",
    }
    assert record["legal_description"].startswith("1997-051 PARTITION PLAT")
    assert record["tax_statements"] == native["tax_statements"]
    assert record["snapshot_complete"] is True


@pytest.mark.parametrize(
    ("source_id", "record", "expected_kind", "expected_native_id"),
    (
        (
            washington.SURVEY_API_SOURCE_ID,
            {
                "record_type": "survey_explorer_survey",
                "native_ids": {"Surveynumber": 35242},
            },
            "survey_explorer_survey",
            "survey_explorer_survey:35242",
        ),
        (
            washington.SURVEY_MAP_SOURCE_ID,
            {
                "record_type": "washington_county_arcgis_surveys",
                "layer_key": "surveys",
                "native_ids": {"OBJECTID": 42, "SurvNum": 35242},
            },
            "survey_explorer_surveys_geometry_index",
            "surveys:42",
        ),
        (
            washington.TAXLOT_SOURCE_ID,
            {
                "record_type": "washington_county_arcgis_taxlots",
                "layer_key": "taxlots",
                "native_ids": {
                    "TLNO": washington.PROBE_TAXLOT,
                    "OBJECTID": 100,
                },
            },
            "washington_county_arcgis_taxlots",
            washington.PROBE_TAXLOT,
        ),
        (
            washington.SITUS_SOURCE_ID,
            {
                "record_type": "washington_county_arcgis_situs",
                "layer_key": "situs",
                "native_ids": {"SITUS_ID": 77, "OBJECTID": 12},
            },
            "washington_county_arcgis_situs",
            "77",
        ),
    ),
)
def test_washington_survey_and_geometry_sources_remain_observations(
    source_id,
    record,
    expected_kind,
    expected_native_id,
) -> None:
    native = {
        **record,
        "source_id": source_id,
        "native_fields": {"preserved": True},
    }

    decision = projection.project_record(native)

    assert decision.kind == "observation_only"
    assert decision.observation_kind == expected_kind
    assert decision.source_native_id == expected_native_id
    assert decision.reason == (
        "washington_county_index_or_document_observation"
    )
    assert decision.record == native
    assert "native_parcel_id" not in decision.record


def test_washington_tax_map_and_tax_statement_are_document_observations() -> None:
    tax_map = {
        "source_id": washington.INTERMAP_SOURCE_ID,
        "record_type": "intermap_tax-map_report",
        "report": "tax-map",
        "native_ids": {
            "TLNO": washington.PROBE_TAXLOT,
            "IDValue": washington.PROBE_TAXLOT,
        },
        "native_representation": {
            "media_type": "text/html",
            "links": [{"resolved_url": "https://example.test/tax-map.pdf"}],
        },
    }
    statement = {
        "source_id": washington.TAX_SOURCE_ID,
        "record_type": "washington_county_tax_statement",
        "native_ids": {
            "PropertyQuickRefID": washington.PROBE_ACCOUNT,
            "tax_year": 2025,
            "generated_filename": "statement.pdf",
        },
        "media_type": "application/pdf",
        "sha256": "a" * 64,
    }

    tax_map_decision = projection.project_record(tax_map)
    statement_decision = projection.project_record(statement)

    assert tax_map_decision.kind == "observation_only"
    assert tax_map_decision.observation_kind == "intermap_tax-map_report"
    assert tax_map_decision.source_native_id == (
        f"tax-map:{washington.PROBE_TAXLOT}"
    )
    assert statement_decision.kind == "observation_only"
    assert statement_decision.observation_kind == (
        "washington_county_tax_statement"
    )
    assert statement_decision.source_native_id == (
        f"{washington.PROBE_ACCOUNT}:2025:statement.pdf"
    )


def test_multnomah_sail_tax_parcel_projects_assessor_grain_and_native_joins() -> None:
    feature = fixture_json(
        "oregon_multnomah_sail",
        "features.json",
    )[multnomah.TAX_PARCEL_SOURCE_ID][0]
    native = multnomah.normalize_feature(
        multnomah.COMPONENTS[multnomah.TAX_PARCEL_SOURCE_ID],
        feature,
        schema_fingerprint="fixture-schema",
        geometry_requested=True,
    )

    decision = projection.project_record(native)

    assert decision.kind == "assessor"
    record = decision.record
    assert record["native_parcel_id"] == "R330254"
    assert {
        "1S1E21CB -04600",
        "1S1E21CB04600",
        "R991212410",
        "1",
    }.issubset(record["alternate_parcel_ids"])
    assert record["jurisdiction"]["county_geoid"] == "41051"
    assert record["owners"] == [
        {"raw_name": "LUMEN TECHNOLOGIES INC", "confidence": "high"}
    ]
    assert record["situs_address"] == {
        "raw": "8021-8025 SW CAPITOL HILL RD",
        "country": "US",
        "city": "PORTLAND",
        "state": "OR",
        "postal_code": "97219",
    }
    assert record["mailing_address"]["raw"] == "1025 ELDORADO BLVD"
    assert record["assessment"]["tax_year"] == "2025"
    assert record["assessment"]["land_value"] == 0
    assert record["assessment"]["improvement_value"] == 0
    assert record["assessment"]["assessed_value"] == 0
    assert record["last_sale"]["source_document_ref"] == "BP23830216"
    assert record["last_sale"]["source_document_date"] == "2011-11-23"
    assert record["representations"][0]["representation_kind"] == (
        "county_assessor_map_pdf"
    )
    assert record["snapshot_complete"] is True
    assert record["raw_attributes"] == native["raw_attributes"]


@pytest.mark.parametrize(
    "source_id",
    multnomah.IMAGE_SOURCE_IDS,
)
def test_multnomah_sail_survey_and_document_sources_remain_observations(
    source_id: str,
) -> None:
    feature = fixture_json(
        "oregon_multnomah_sail",
        "features.json",
    )[source_id][0]
    native = multnomah.normalize_feature(
        multnomah.COMPONENTS[source_id],
        feature,
        schema_fingerprint="fixture-schema",
        geometry_requested=True,
    )

    decision = projection.project_record(native)

    assert decision.kind == "observation_only"
    assert decision.reason == "multnomah_sail_non_assessor_representation"
    assert decision.observation_kind == native["record_kind"]
    assert decision.source_native_id == native["source_record_id"]
    assert decision.record == native
    assert decision.record["representations"][0]["join_field"] == "SURVEYID"
    assert "native_parcel_id" not in decision.record


def test_multnomah_sail_download_remains_a_distinct_document_observation() -> None:
    native = {
        "record_kind": "sail_document_artifact",
        "source_id": multnomah.SURVEY_SOURCE_ID,
        "survey_document_id": multnomah.KNOWN_SURVEY_ID,
        "representation_index": 1,
        "document_url": (
            "https://www4.multco.us/Surveyimages/Survey/"
            "04000-05999/05335.PDF"
        ),
        "sha256": multnomah.KNOWN_SURVEY_PDF_SHA256,
    }

    decision = projection.project_record(native)

    assert decision.kind == "observation_only"
    assert decision.observation_kind == "sail_document_artifact"
    assert decision.source_native_id == (
        "sail_document_artifact:05335:1:"
        f"{multnomah.KNOWN_SURVEY_PDF_SHA256}"
    )


def test_projection_rejects_source_mismatch_and_unknown_source() -> None:
    record = {
        "source_id": projection.YAMHILL_ASCEND_SOURCE_ID,
        "account_number": "1",
    }
    with pytest.raises(
        projection.PropertyProjectionError,
        match="does not match",
    ):
        projection.project_record(
            record,
            source_id=projection.CLACKAMAS_ASCEND_SOURCE_ID,
        )

    with pytest.raises(
        projection.PropertyProjectionError,
        match="unsupported",
    ):
        projection.project_record(
            {"source_id": "us-or-example-unknown"},
        )
