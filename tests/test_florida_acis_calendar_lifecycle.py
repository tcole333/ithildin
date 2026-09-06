from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools.public_records_http import PaginatedFetch
from tools.public_records_monitor import ProbeContext, probe_florida_acis
from tools.query_florida_acis import ACISCourt


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "us-fl-acis"
SECOND_DCA_UUID = "8f454fb9-4c7f-43df-856b-ab373e71c27f"
CALENDAR_EVENT_UUID = "39a9537b-2a08-4c3b-a78b-bb6acaaeb537"


def _page(
    records: list[dict[str, Any]],
    *,
    schema_fingerprint: str,
) -> PaginatedFetch:
    return PaginatedFetch(
        records=tuple(records),
        next_cursor=None,
        schema={"record": "fixture"},
        schema_fingerprint=schema_fingerprint,
        pages_fetched=1,
        requests_made=1,
    )


def _courts() -> tuple[ACISCourt, ...]:
    names = (
        "Supreme Court of Florida",
        "1st District Court of Appeal",
        "2nd District Court of Appeal",
        "3rd District Court of Appeal",
        "4th District Court of Appeal",
        "5th District Court of Appeal",
        "6th District Court of Appeal",
    )
    resource_ids = (
        "68f021c4-6a44-4735-9a76-5360b2e8af13",
        "b82b30d5-bd3c-46d7-9451-1cb05e470873",
        SECOND_DCA_UUID,
        "00000000-0000-0000-0000-000000000004",
        "00000000-0000-0000-0000-000000000005",
        "00000000-0000-0000-0000-000000000006",
        "00000000-0000-0000-0000-000000000007",
    )
    return tuple(
        ACISCourt(
            resource_uuid=resource_id,
            external_id=str(index),
            display_name=name,
            active=True,
            raw={
                "resourceID": resource_id,
                "externalIdentifier": str(index),
                "displayName": name,
                "active": True,
            },
        )
        for index, (resource_id, name) in enumerate(
            zip(resource_ids, names, strict=True),
            start=1,
        )
    )


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {}},
        timeout=5.0,
        max_attempts=1,
        sample_bytes=None,
    )


def test_acis_manifest_extends_one_source_with_appellate_calendar_coverage():
    config = yaml.safe_load(
        (ROOT / "config" / "public_records_sources.yaml").read_text(
            encoding="utf-8"
        )
    )
    matches = [
        source for source in config["sources"] if source["source_id"] == SOURCE_ID
    ]

    assert len(matches) == 1
    source = matches[0]
    assert source["record_identity_source_id"] == SOURCE_ID
    assert "appellate_calendars" in source["roles"]
    assert {
        "calendar_event_uuid",
        "calendar_hearing_order",
    }.issubset(source["stable_keys"])

    capabilities = {
        capability["name"]: capability.get("details", {})
        for capability in source["capabilities"]
    }
    assert capabilities["list_calendar_session_types"]["adapter_command"] == (
        "calendar-types"
    )
    calendar = capabilities["search_appellate_calendars"]
    assert calendar["adapter_command"] == "calendar"
    assert calendar["unified_route"] == "query_state_courts.py calendar"
    assert calendar["event_identity_fields"] == ["calendar_event_uuid"]
    assert calendar["hearing_occurrence_identity_fields"] == [
        "calendar_event_uuid",
        "case_instance_uuid",
        "order",
    ]
    assert capabilities["probe_source"]["adapter_command"] == (
        "public_records_monitor.py run us-fl-acis"
    )

    associations = [
        association
        for association in source["census_associations"]
        if association["role"] == "appellate_calendars"
    ]
    assert len(associations) == 1
    assert associations[0]["jurisdiction_geoid"] == "12"
    assert associations[0]["coverage"]["represented_courts"] == (
        "Florida Supreme Court and six District Courts of Appeal"
    )
    assert associations[0]["coverage"]["record_grain"] == (
        "published_calendar_event_with_case_hearings"
    )
    assert associations[0]["coverage_gaps"]

    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == source["official_url"]


def test_acis_calendar_monitor_separates_contract_from_rolling_hearings(
    monkeypatch: pytest.MonkeyPatch,
):
    rolling = {"hearing_count": 1}

    class FakeClient:
        def __init__(self, **_kwargs):
            self.request_count = 0

        def courts(self):
            self.request_count += 1
            return _courts()

        def session_types(self):
            self.request_count += 1
            return (
                {
                    "courtSessionTypeID": "1000003",
                    "courtSessionTypeName": "Oral Argument",
                    "courtSessionTypeComment": "Oral Argument",
                },
                {
                    "courtSessionTypeID": "1000004",
                    "courtSessionTypeName": "Conference",
                    "courtSessionTypeComment": "Conference",
                },
            )

        def search_calendar_events(self, **kwargs):
            assert kwargs == {
                "court": SECOND_DCA_UUID,
                "after": "2026-08-19",
                "before": "2026-08-19",
                "session_type": "1000003",
                "event_name": "Khouzam",
                "requested_limit": 1,
                "page_size": 25,
            }
            self.request_count += 1
            return _page(
                [
                    {
                        "eventUUID": CALENDAR_EVENT_UUID,
                        "eventName": "Oral Argument Khouzam, Labrit, Guard",
                        "courtID": "3",
                        "courtAbbreviation": "2nd District Court of Appeal",
                        "courtSessionType": "Oral Argument",
                        "panelFlag": True,
                        "startDate": "2026-08-19T13:30:00.000+00:00",
                    }
                ],
                schema_fingerprint="b" * 64,
            )

        def event_hearings(self, court_resource_uuid, event_uuid, **kwargs):
            assert court_resource_uuid == SECOND_DCA_UUID
            assert event_uuid == CALENDAR_EVENT_UUID
            assert kwargs == {"requested_limit": None, "page_size": 25}
            self.request_count += 1
            hearings = [
                {
                    "startDate": "2026-08-19T13:30:00.000+00:00",
                    "hearingType": "Oral Argument",
                    "hearingStatus": "Scheduled",
                    "orderBy": index,
                    "event": {"panelFlag": True},
                    "caseHeader": {
                        "caseInstanceUUID": (
                            f"00000000-0000-0000-0000-{index:012d}"
                        ),
                        "caseNumber": f"2D2025-{index:04d}",
                        "caseTitle": f"Example {index}",
                        "courtID": "3",
                    },
                }
                for index in range(1, rolling["hearing_count"] + 1)
            ]
            return _page(hearings, schema_fingerprint="c" * 64)

    monkeypatch.setattr(
        public_records_monitor,
        "FloridaACISClient",
        FakeClient,
    )
    first = probe_florida_acis(_context())

    rolling["hearing_count"] = 2
    second = probe_florida_acis(_context())

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["requests_made"] == 4
    assert first.details["stable_contract"]["calendar_capability"] == (
        "appellate_calendar_events_with_case_hearing_hydration"
    )
    assert first.details["artifact_identity"]["event_uuid"] == CALENDAR_EVENT_UUID
    assert first.details["rolling_observation"]["case_count"] == 1
    assert second.details["rolling_observation"]["case_count"] == 2
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )


def test_acis_calendar_probe_is_registered_as_one_bounded_source_probe():
    handler = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]

    assert handler.capability == "probe_source"
    assert handler.expected_requests == 4
    assert handler.sentinel_record_count == 1
    assert handler.handler is probe_florida_acis
