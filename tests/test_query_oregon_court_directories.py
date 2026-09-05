from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_court_directories as directory
from tools.public_records_contract import ResultStatus
from tools.public_records_http import (
    RestrictedHTTPError,
    SourceResponseError,
)


FIXTURES = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_court_directories"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def batch(source_id: str) -> directory.SharePointItemBatch:
    source = directory.SOURCES_BY_ID[source_id]
    file_name = {
        directory.STATE_COURT_SOURCE_ID: "state_courts.xml",
        directory.STATE_JUDGE_SOURCE_ID: "state_judges.xml",
        directory.LOCAL_COURT_SOURCE_ID: "local_courts.xml",
        directory.LOCAL_JUDGE_SOURCE_ID: "local_judges.xml",
    }[source_id]
    return directory.parse_list_items_xml(
        fixture(file_name),
        source=source,
        view=source.default_view,
    )


class FakeClient:
    def __init__(
        self,
        *,
        batches: dict[str, directory.SharePointItemBatch] | None = None,
    ) -> None:
        self.batches = batches or {
            source_id: batch(source_id) for source_id in directory.SOURCE_IDS
        }
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def items(
        self,
        source: directory.SourceDefinition,
        view: directory.ViewDefinition,
    ) -> directory.SharePointItemBatch:
        value = self.batches[source.source_id]
        return replace(value, view=view)

    def views(
        self,
        source: directory.SourceDefinition,
    ) -> tuple[directory.SharePointView, ...]:
        return directory.parse_view_collection_xml(fixture("views.xml"))

    def probe(
        self,
        source: directory.SourceDefinition,
        view: directory.ViewDefinition,
    ) -> dict[str, Any]:
        views = self.views(source)
        return {
            "list_schema": directory.parse_list_schema_xml(fixture("list_schema.xml")),
            "views": views,
            "live_view": next(
                candidate
                for candidate in views
                if candidate.view_id.casefold() == view.view_id.casefold()
            ),
            "view_schema": directory.parse_view_schema_xml(fixture("view_schema.xml")),
            "batch": replace(self.batches[source.source_id], view=view),
        }


def parse_args(*values: str):
    return directory.build_parser().parse_args(values)


def test_four_source_components_are_distinct_and_include_tax_views():
    assert directory.SOURCE_IDS == (
        "us-or-state-court-directory",
        "us-or-state-judge-directory",
        "us-or-local-court-registry",
        "us-or-local-judge-registry",
    )
    assert len(directory.SOURCES_BY_ID) == 4
    state_judges = directory.SOURCES_BY_ID[directory.STATE_JUDGE_SOURCE_ID]
    assert {view.key for view in state_judges.views} >= {
        "judges",
        "presiding-judges",
        "supreme",
        "court-of-appeals",
        "tax-regular",
        "tax",
        "tax-magistrate",
    }
    assert all(
        source.source_metadata.metadata["platform_family"] == "sharepoint_soap_lists"
        for source in directory.SOURCE_DEFINITIONS
    )


def test_get_list_items_body_matches_browser_shape():
    body = directory.build_get_list_items_envelope(
        "Municipal & Justice Court Registry",
        "{9DFB7517-70A9-4D79-B6EB-0CF31F83E107}",
    )
    assert "GetListItems" in body
    assert "Municipal &amp; Justice Court Registry" in body
    assert "{9DFB7517-70A9-4D79-B6EB-0CF31F83E107}" in body
    assert "IncludeAttachmentUrls" in body
    assert "TRUE" in body
    root = ET.fromstring(body)
    operation = next(
        element for element in root.iter() if element.tag.endswith("GetListItems")
    )
    assert operation.find(f"{{{directory.SHAREPOINT_NAMESPACE}}}listName") is not None
    assert operation.find(f"{{{directory.SHAREPOINT_NAMESPACE}}}viewName") is not None
    assert (
        operation.find(f".//{{{directory.SHAREPOINT_NAMESPACE}}}IncludeAttachmentUrls")
        is not None
    )


def test_parses_views_and_preserves_unconfigured_live_views():
    views = directory.parse_view_collection_xml(fixture("views.xml"))
    assert len(views) == 3
    assert views[0].display_name == "Judges"
    assert views[2].default_view is True
    records = directory._view_records(  # noqa: SLF001
        directory.SOURCES_BY_ID[directory.STATE_JUDGE_SOURCE_ID],
        views,
    )
    assert any(
        record["display_name"] == "New Source View" and record["configured"] is False
        for record in records
    )


def test_parses_list_and_view_schema_fingerprints():
    list_schema = directory.parse_list_schema_xml(fixture("list_schema.xml"))
    view_schema = directory.parse_view_schema_xml(fixture("view_schema.xml"))
    assert list_schema.title == "Judges"
    assert list_schema.item_count == 211
    assert [field["StaticName"] for field in list_schema.fields] == [
        "FirstName",
        "Title",
    ]
    assert view_schema.display_name == "Judges"
    assert view_schema.fields == (
        "FirstName",
        "Title",
        "Term_x0020_Expires",
    )
    assert len(list_schema.schema_fingerprint) == 64
    assert len(view_schema.schema_fingerprint) == 64


def test_soap_fault_is_an_explicit_source_failure():
    with pytest.raises(SourceResponseError, match="List does not exist"):
        directory.parse_view_collection_xml(fixture("fault.xml"))


def test_state_court_normalization_preserves_identity_and_raw_fields():
    records = directory.normalize_batch(batch(directory.STATE_COURT_SOURCE_ID))
    deschutes = next(record for record in records if record["county"] == "Deschutes")
    assert deschutes["court_name"] == "Deschutes County Circuit Court"
    assert deschutes["county_fips"] == "41017"
    assert deschutes["judicial_district"] == "11"
    assert deschutes["administrator"]["full_name"] == "Zoe Wild"
    assert deschutes["physical_address"]["city"] == "Bend"
    assert deschutes["sharepoint_item_id"] == "41"
    assert deschutes["sharepoint_unique_id"] == "EAFCC48B-A85A-43CB-9510-37270F78CD9C"
    assert (
        deschutes["raw_sharepoint_fields"]["ows_Company_x0020_Name"]
        == "Deschutes County Circuit Court"
    )
    assert (
        deschutes["decoded_sharepoint_fields"]["Company Name"]
        == "Deschutes County Circuit Court"
    )


def test_state_judge_normalization_preserves_term_and_vacancy():
    records = directory.normalize_batch(batch(directory.STATE_JUDGE_SOURCE_ID))
    judge = next(record for record in records if not record["vacant"])
    vacancy = next(record for record in records if record["vacant"])
    assert judge["full_name"] == "Example Q Judge"
    assert judge["term_expires"] == "2031-01-06"
    assert judge["presiding"] is True
    assert judge["judicial_district"] == "11"
    assert vacancy["last_name"] == "Vacant"


def test_local_court_normalization_deduplicates_website_and_preserves_source():
    records = directory.normalize_batch(batch(directory.LOCAL_COURT_SOURCE_ID))
    bend = next(record for record in records if record["court_name"].startswith("Bend"))
    assert bend["court_types"] == ["Municipal Court"]
    assert bend["counties"] == ["Deschutes"]
    assert bend["county_fips"] == ["41017"]
    assert bend["website_urls"] == ["http://www.bendoregon.gov/municipalcourt"]
    assert (
        bend["website_source_value"] == "http://www.bendoregon.gov/municipalcourt, "
        "http://www.bendoregon.gov/municipalcourt"
    )
    assert bend["certified_date"] == "2026-04-30"


def test_local_judge_normalization_preserves_assignment_and_multicounty():
    records = directory.normalize_batch(batch(directory.LOCAL_JUDGE_SOURCE_ID))
    erin = next(record for record in records if record["full_name"] == "Erin Zemper")
    adam = next(record for record in records if record["full_name"] == "Adam R Thayne")
    assert erin["court"]["native_id"] == "15"
    assert erin["court"]["name"] == "Bend Municipal Court"
    assert erin["oregon_state_bar_number"] == "044628"
    assert erin["term_began"] == "2025-04-16"
    assert erin["term_ends"] == "2027-04-16"
    assert adam["court"]["counties"] == ["Washington", "Yamhill"]
    assert adam["court"]["county_fips"] == ["41067", "41071"]


def test_list_cursor_is_query_snapshot_and_anchor_bound():
    client = FakeClient()
    first_args = parse_args(
        "list",
        "--source",
        directory.LOCAL_COURT_SOURCE_ID,
        "--limit",
        "1",
    )
    first = directory.execute(first_args, client=client, log_results=False)
    assert first.status == ResultStatus.OK
    assert len(first.records) == 1
    assert first.next_cursor

    second_args = parse_args(
        "list",
        "--source",
        directory.LOCAL_COURT_SOURCE_ID,
        "--limit",
        "1",
        "--cursor",
        str(first.next_cursor),
    )
    second = directory.execute(second_args, client=client, log_results=False)
    assert second.status == ResultStatus.OK
    assert len(second.records) == 1
    assert second.records[0]["canonical_ref"] != first.records[0]["canonical_ref"]

    changed_rows = [
        dict(row) for row in client.batches[directory.LOCAL_COURT_SOURCE_ID].rows
    ]
    changed_rows[0]["ows_Modified"] = "2026-07-29 12:00:00"
    changed_batch = replace(
        client.batches[directory.LOCAL_COURT_SOURCE_ID],
        rows=tuple(changed_rows),
    )
    changed_client = FakeClient(
        batches={
            **client.batches,
            directory.LOCAL_COURT_SOURCE_ID: changed_batch,
        }
    )
    changed = directory.execute(
        second_args,
        client=changed_client,
        log_results=False,
    )
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_cursor_rejects_different_search_query():
    client = FakeClient()
    first = directory.execute(
        parse_args(
            "search",
            "Court",
            "--source",
            directory.LOCAL_COURT_SOURCE_ID,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )
    assert first.next_cursor
    changed = directory.execute(
        parse_args(
            "search",
            "Bend",
            "--source",
            directory.LOCAL_COURT_SOURCE_ID,
            "--limit",
            "1",
            "--cursor",
            str(first.next_cursor),
        ),
        client=client,
        log_results=False,
    )
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_query_mismatch"


def test_search_uses_semantic_fields_and_authoritative_empty():
    client = FakeClient()
    result = directory.execute(
        parse_args(
            "search",
            "Deschutes",
            "--source",
            directory.LOCAL_COURT_SOURCE_ID,
            "--field",
            "county",
        ),
        client=client,
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert [record["court_name"] for record in result.records] == [
        "Bend Municipal Court"
    ]

    empty = directory.execute(
        parse_args(
            "search",
            "Not A Real Court",
            "--source",
            directory.LOCAL_COURT_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )
    assert empty.status == ResultStatus.NO_RESULTS
    assert empty.errors == ()


def test_discovery_emits_candidates_without_creating_requests():
    result = directory.execute(
        parse_args("discovery", "--query", "Bend"),
        client=FakeClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    candidate = result.records[0]
    assert candidate["candidate_url"] == ("http://www.bendoregon.gov/municipalcourt")
    assert candidate["court"]["name"] == "Bend Municipal Court"
    assert candidate["infra_request_created"] is False
    assert candidate["discovered_from"]["sharepoint_item_id"] == "15"
    assert candidate["registry_candidate_key"].startswith("ORCOURTDIR-DISCOVERY-COURT:")
    assert (
        candidate["registry_identity"]["court_canonical_ref"]
        == (candidate["court"]["canonical_ref"])
    )
    assert candidate["discovered_from"]["schema_fingerprint"] == (
        batch(directory.LOCAL_COURT_SOURCE_ID).schema_fingerprint
    )


def test_incomplete_rowset_returns_partial_not_authoritative_empty():
    source = directory.SOURCES_BY_ID[directory.LOCAL_COURT_SOURCE_ID]
    incomplete = directory.parse_list_items_xml(
        fixture("incomplete.xml"),
        source=source,
        view=source.default_view,
    )
    result = directory.execute(
        parse_args(
            "list",
            "--source",
            directory.LOCAL_COURT_SOURCE_ID,
        ),
        client=FakeClient(
            batches={
                **{source_id: batch(source_id) for source_id in directory.SOURCE_IDS},
                directory.LOCAL_COURT_SOURCE_ID: incomplete,
            }
        ),
        log_results=False,
    )
    assert result.status == ResultStatus.PARTIAL
    assert result.errors[0].code == "sharepoint_rowset_incomplete"
    assert len(result.records) == 1


def test_raw_guid_view_selector_is_available_for_live_discovery():
    args = parse_args(
        "list",
        "--source",
        directory.STATE_JUDGE_SOURCE_ID,
        "--view",
        "{99999999-9999-9999-9999-999999999999}",
    )
    result = directory.execute(args, client=FakeClient(), log_results=False)
    assert result.status == ResultStatus.OK
    assert result.query.query.parameters["view"]["view_id"] == (
        "{99999999-9999-9999-9999-999999999999}"
    )


def test_probe_preserves_observed_counts_without_treating_them_as_limits():
    result = directory.execute(
        parse_args(
            "probe",
            "--source",
            directory.STATE_JUDGE_SOURCE_ID,
        ),
        client=FakeClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    checks = result.records[0]["checks"]
    assert checks["reported_item_count"] == 2
    assert checks["parsed_item_count"] == 2
    assert checks["complete_response"] is True
    assert "native_result_limit" not in checks
    assert result.records[0]["list"]["source_reported_item_count"] == 211


def test_access_decision_mismatch_and_human_required_are_explicit():
    args = parse_args(
        "list",
        "--source",
        directory.LOCAL_COURT_SOURCE_ID,
    )
    mismatch = directory.execute(
        args,
        catalog_decision={
            "source_id": directory.STATE_JUDGE_SOURCE_ID,
            "allowed": True,
        },
        client=FakeClient(),
        log_results=False,
    )
    assert mismatch.status == ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == "catalog_decision_source_mismatch"

    human = directory.execute(
        args,
        access_decision={
            "source_id": directory.LOCAL_COURT_SOURCE_ID,
            "allowed": False,
            "automation_disposition": "human_required",
            "reason_code": "review_required",
        },
        client=FakeClient(),
        log_results=False,
    )
    assert human.status == ResultStatus.HUMAN_REQUIRED
    assert human.errors[0].code == "review_required"


class FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.headers: dict[str, str] = {}


class RecordingSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_client_bootstraps_page_then_posts_without_soap_action():
    session = RecordingSession(
        [
            FakeResponse(200, "<html>Oregon Judicial Department</html>"),
            FakeResponse(200, fixture("local_courts.xml")),
        ]
    )
    client = directory.OregonCourtDirectoryClient(
        session=session,
        minimum_interval=0,
        max_attempts=1,
    )
    source = directory.SOURCES_BY_ID[directory.LOCAL_COURT_SOURCE_ID]
    result = client.items(source, source.default_view)
    assert len(result.rows) == 2
    assert [request["method"] for request in session.requests] == ["GET", "POST"]
    post = session.requests[1]
    assert post["url"] == directory.LISTS_URL
    assert post["headers"]["Referer"] == directory.OTHER_COURTS_PAGE_URL
    assert post["headers"]["Content-Type"] == "text/xml; charset=utf-8"
    assert all(key.casefold() != "soapaction" for key in post["headers"])
    assert b"GetListItems" in post["data"]


def test_client_maps_401_to_restricted_failure():
    session = RecordingSession([FakeResponse(401, "Unauthorized")])
    client = directory.OregonCourtDirectoryClient(
        session=session,
        minimum_interval=0,
        max_attempts=1,
    )
    source = directory.SOURCES_BY_ID[directory.LOCAL_COURT_SOURCE_ID]
    with pytest.raises(RestrictedHTTPError):
        client.items(source, source.default_view)


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official Oregon SOAP probes",
)
def test_live_local_court_probe():
    result = directory.execute(
        parse_args(
            "probe",
            "--source",
            directory.LOCAL_COURT_SOURCE_ID,
            "--minimum-interval",
            "0",
            "--max-attempts",
            "1",
        ),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert result.records[0]["checks"]["parsed_item_count"] > 100
