from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_washington_case_permits as washco
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RestrictedHTTPError, RetryPolicy
from tools.query_oregon_washington_property import ResponseTooLargeError


FIXTURES = Path(__file__).parent / "fixtures" / "washington_county_case_permits"
LIVE = os.environ.get("LIVE_PUBLIC_RECORDS") == "1"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads(fixture_text(name))


def parse_args(*values: str) -> Any:
    return washco.build_parser().parse_args(list(values))


def artifact(
    *,
    url: str = "https://example.test/source",
    content: bytes = b"{}",
    content_type: str = "application/json",
    headers: Mapping[str, str] | None = None,
) -> washco.ResponseArtifact:
    return washco.ResponseArtifact(
        content=content,
        source_url=url,
        headers={
            "content-type": content_type,
            "content-length": str(len(content)),
            **dict(headers or {}),
        },
        status_code=200,
    )


class FixtureClient:
    def __init__(self) -> None:
        self.api_calls: list[dict[str, Any]] = []
        self.download_target: str | None = None

    def api_json(
        self,
        url: str,
        *,
        parameters: Mapping[str, Any],
        referer: str,
    ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
        self.api_calls.append(
            {"url": url, "parameters": dict(parameters), "referer": referer}
        )
        if url == washco.CASEFILE_SEARCH_URL:
            filename = (
                "case_taxlot.json"
                if parameters.get("searchby") == "search-taxlot"
                else "case_exact.json"
            )
        elif url == washco.CASEFILE_REVIEW_URL:
            filename = "case_review.json"
        elif url == washco.CASEFILE_DECISION_URL:
            filename = "case_decisions.json"
        elif url == washco.STAFF_URL:
            filename = "staff.json"
        elif url == washco.TAXLOT_ACTIVITY_URL:
            filename = "taxlot_activity.json"
        elif url == washco.BUILDING_TYPES_URL:
            filename = "building_types.json"
        elif url == washco.BUILDING_SEARCH_URL:
            filename = (
                "building_challenge.json"
                if parameters.get("searchby") != "search-taxlot"
                else "building_taxlot.json"
            )
        elif url == washco.PERMIT_REPORT_URL:
            filename = f"report_{parameters['searchby']}.json"
        else:
            raise AssertionError(f"unexpected fixture URL: {url}")
        payload = fixture_json(filename)
        source_artifact = artifact(
            url=f"{url}?fixture=1",
            content=json.dumps(payload).encode(),
        )
        washco._raise_api_error(payload, source_artifact.source_url)
        return payload, source_artifact

    def accela_detail(
        self,
        cap_parts: tuple[str, str, str],
    ) -> tuple[str, washco.ResponseArtifact]:
        assert cap_parts == ("25PLN", "00000", "00371")
        html = fixture_text("accela_record.html")
        return html, artifact(
            url=(
                "https://permits.washingtoncountyor.gov/CitizenAccess/"
                "Cap/CapDetail.aspx?fixture=1"
            ),
            content=html.encode(),
            content_type="text/html",
        )

    def accela_attachment_list(
        self,
        attachment_url: str,
        *,
        referer: str,
    ) -> tuple[str, washco.ResponseArtifact]:
        assert "AttachmentsList.aspx" in attachment_url
        assert "CapDetail.aspx" in referer
        html = fixture_text("accela_attachments.html")
        return html, artifact(
            url=attachment_url,
            content=html.encode(),
            content_type="text/html",
        )

    def accela_document_detail(
        self,
        document_number: str,
        *,
        referer: str,
    ) -> tuple[str, washco.ResponseArtifact]:
        assert document_number == "628906"
        assert "AttachmentsList.aspx" in referer
        html = fixture_text("accela_document.html")
        return html, artifact(
            url=f"{washco.ACCELA_DOCUMENT_DETAIL_URL}?documentNo={document_number}",
            content=html.encode(),
            content_type="text/html",
        )

    def accela_download(
        self,
        listing: washco.ResponseArtifact,
        event_target: str,
        *,
        maximum_bytes: int,
    ) -> washco.ResponseArtifact:
        assert "AttachmentsList.aspx" in listing.source_url
        assert maximum_bytes > 100
        self.download_target = event_target
        pdf = b"%PDF-1.7\nfixture\n%%EOF\n"
        return artifact(
            url=listing.source_url,
            content=pdf,
            content_type="application/pdf",
            headers={"content-disposition": 'attachment; filename="notice.pdf"'},
        )


class FakeResponse:
    def __init__(
        self,
        *,
        content: bytes,
        status_code: int = 200,
        url: str = "https://example.test/result",
        headers: Mapping[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.url = url
        self.headers = dict(
            headers
            or {
                "content-type": "application/json",
                "content-length": str(len(content)),
            }
        )
        self.chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size: int) -> Any:
        del chunk_size
        if self.chunks is not None:
            yield from self.chunks
        else:
            yield self.content

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def bounded_client(session: FakeSession) -> washco.CasePermitClient:
    return washco.CasePermitClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )


def test_source_manifest_keeps_six_components_and_operation_access_distinct() -> None:
    payload = washco.source_manifest()
    source_ids = {item["source_id"] for item in payload["sources"]}

    assert source_ids == set(washco.SOURCES)
    assert len(source_ids) == 6
    building = next(
        item
        for item in payload["sources"]
        if item["source_id"] == washco.BUILDING_SOURCE_ID
    )
    operation_access = building["metadata"]["operation_access"]
    assert operation_access["taxlot_search"] == "anonymous"
    assert operation_access["permit_types"] == "anonymous"
    assert (
        operation_access["permit_number_search"]
        == "source_challenge_observed"
    )
    assert washco.PERMIT_REPORT_SOURCE_ID != washco.BUILDING_SOURCE_ID
    assert payload["sentinel_joins"]["accela_cap_id"] == "25PLN-00000-00371"


def test_exact_casefile_preserves_cap_taxlot_activity_and_dates() -> None:
    result = washco.execute(
        parse_args("case-detail", "L2500106"),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["native_ids"]["accela_cap_id"] == "25PLN-00000-00371"
    assert record["joins"]["taxlots"] == ["2N2330002700"]
    assert record["joins"]["activities"] == ["HR25-0008"]
    assert record["dates"]["submitted"]["iso_date"] == "2025-04-22"
    assert record["dates"]["accepted"]["iso_date"] == "2025-04-30"
    assert record["source_native"]["StaffEmail"].endswith(
        "@washingtoncountyor.gov"
    )


def test_casefile_taxlot_cursor_uses_snapshot_and_rejects_changed_query() -> None:
    client = FixtureClient()
    first = washco.execute(
        parse_args(
            "case-search",
            "taxlot",
            "2N2330002700",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    assert [
        item["native_record_id"] for item in first.to_dict()["records"]
    ] == ["L0800049", "L1900098"]
    assert first.next_cursor

    second = washco.execute(
        parse_args(
            "case-search",
            "taxlot",
            "2N2330002700",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert [
        item["native_record_id"] for item in second.to_dict()["records"]
    ] == ["L2500106"]

    changed = washco.execute(
        parse_args(
            "case-search",
            "taxlot",
            "DIFFERENT",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_omitted_limit_returns_complete_casefile_response() -> None:
    args = parse_args("case-search", "taxlot", "2N2330002700")
    result = washco.execute(
        args,
        client=FixtureClient(),
        log_results=False,
    )

    assert args.limit is None
    assert [
        item["native_record_id"] for item in result.to_dict()["records"]
    ] == ["L0800049", "L1900098", "L2500106"]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None


def test_current_review_and_decision_feeds_are_structured_case_operations() -> None:
    review = washco.execute(
        parse_args("case-review"),
        client=FixtureClient(),
        log_results=False,
    ).to_dict()["records"][0]
    decision = washco.execute(
        parse_args("case-decisions"),
        client=FixtureClient(),
        log_results=False,
    ).to_dict()["records"][0]

    assert review["record_kind"] == "applications_under_review"
    assert review["native_record_id"] == "L2600121"
    assert review["dates"]["accepted"]["iso_date"] == "2026-05-21"
    assert review["taxlot"] == "2N4350001000"
    assert decision["record_kind"] == "recent_decisions"
    assert decision["dates"]["decision"]["iso_date"] == "2026-07-23"
    assert decision["taxlot"] == "3S103C002100"


def test_staff_vocabulary_preserves_native_initials() -> None:
    result = washco.execute(
        parse_args("case-staff"),
        client=FixtureClient(),
        log_results=False,
    )
    records = result.to_dict()["records"]

    assert [item["native_record_id"] for item in records] == [
        "KELLIEC",
        "ANNEE",
    ]
    assert records[0]["name"] == "Kellie Crowdis"


def test_taxlot_project_activity_keeps_collections_and_join_fields() -> None:
    result = washco.execute(
        parse_args(
            "taxlot-activity",
            "2N2330002700",
            "--collection",
            "all",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    records = result.to_dict()["records"]

    assert result.status == ResultStatus.OK
    assert {item["record_kind"] for item in records} == {
        "taxlot_projects",
        "taxlot_activity",
    }
    activity = next(
        item for item in records if item["record_kind"] == "taxlot_activity"
    )
    assert activity["joins"]["activity_or_permit_number"] == "L1800121"
    assert activity["project"]["number"] == "D0004370"
    assert activity["activity"]["status"] == "Approved"


def test_building_taxlot_and_types_remain_anonymous_capabilities() -> None:
    client = FixtureClient()
    taxlot = washco.execute(
        parse_args("building-search", "taxlot", "2N2330002700"),
        client=client,
        log_results=False,
    )
    types = washco.execute(
        parse_args("building-types"),
        client=client,
        log_results=False,
    )

    assert taxlot.status == ResultStatus.OK
    first = taxlot.to_dict()["records"][0]
    assert first["permit_number"] == "05214429"
    assert first["joins"]["project_number"] == "P0138681"
    assert types.status == ResultStatus.OK
    assert len(types.records) == 2
    assert all(call["referer"] == washco.BUILDING_APP_URL for call in client.api_calls)


def test_challenge_is_scoped_to_specific_building_operation() -> None:
    client = FixtureClient()
    challenged = washco.execute(
        parse_args("building-search", "permit", "05214429"),
        client=client,
        log_results=False,
    )
    available = washco.execute(
        parse_args("building-types"),
        client=client,
        log_results=False,
    )

    assert challenged.status == ResultStatus.HUMAN_REQUIRED
    assert challenged.errors[0].code == "source_challenge_required"
    assert challenged.errors[0].details["interactive_route"] == washco.BUILDING_APP_URL
    assert available.status == ResultStatus.OK
    assert available.query.source.source_id == washco.BUILDING_SOURCE_ID


@pytest.mark.parametrize(
    ("kind", "identifier", "join_key", "join_value"),
    [
        ("project", "P0138681", "project_number", "P0138681"),
        ("activity", "HR25-0008", "project_or_casefile", "L2500106"),
        ("people", "HR25-0008", None, None),
        ("inspection", "05214429", "permit_number", "05214429"),
        ("review", "05214429", "permit_number", "05214429"),
    ],
)
def test_permit_report_operations_preserve_native_schema_and_joins(
    kind: str,
    identifier: str,
    join_key: str | None,
    join_value: str | None,
) -> None:
    result = washco.execute(
        parse_args("permit-report", kind, identifier),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["record_kind"] == f"{kind}_report"
    assert len(record["schema_fingerprint"]) == 64
    assert record["source_native"]
    if join_key:
        assert record["joins"][join_key] == join_value
    if kind == "project":
        assert record["joins"]["activity_or_permit_numbers"] == [
            "05214429",
            "05229066",
        ]
    if kind == "inspection":
        assert record["dates"]["inspection"]["iso_date"] == "2006-09-07"


def test_accela_attachment_parser_keeps_document_numbers_and_postbacks() -> None:
    documents = washco.parse_accela_attachments(
        fixture_text("accela_attachments.html"),
        "https://example.test/AttachmentsList.aspx",
    )

    assert [item["document_number"] for item in documents] == [
        "628906",
        "628907",
    ]
    assert documents[0]["record_number"] == "L2500106"
    assert documents[0]["latest_update"]["iso_date"] == "2025-07-02"
    assert documents[0]["binary_download_available"] is True
    assert (
        documents[0]["download_event_target"]
        == "attachmentList$gdvAttachmentList$ctl02$lnkFileName"
    )


def test_accela_record_joins_case_cap_detail_and_session_listing() -> None:
    result = washco.execute(
        parse_args("accela-record", "L2500106"),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["native_ids"]["accela_cap_id"] == "25PLN-00000-00371"
    assert record["native_record_id"] == "L2500106"
    assert record["status"] == "Approved"
    assert record["project_description"].startswith("Home Occupation")
    assert record["parcels"][0]["parcel_number"] == "2N2330002700"
    assert len(record["documents"]) == 2
    assert set(record["representations"]) == {
        "casefile_join",
        "record_detail",
        "attachment_list",
    }


def test_accela_document_detail_is_validated_against_listing() -> None:
    result = washco.execute(
        parse_args("accela-document", "L2500106", "628906"),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["document_number"] == "628906"
    assert (
        record["field_map"]["File Name"]
        == "Notice of Decision & Staff Report.pdf"
    )
    assert record["listing_metadata"]["record_number"] == "L2500106"

    missing = washco.execute(
        parse_args("accela-document", "L2500106", "999999"),
        client=FixtureClient(),
        log_results=False,
    )
    assert missing.status == ResultStatus.NO_RESULTS


def test_accela_download_uses_listed_postback_and_bounded_destination(
    tmp_path: Path,
) -> None:
    client = FixtureClient()
    destination = tmp_path / "notice.pdf"
    result = washco.execute(
        parse_args(
            "accela-download",
            "L2500106",
            "628906",
            "--destination",
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes().startswith(b"%PDF")
    assert (
        client.download_target
        == "attachmentList$gdvAttachmentList$ctl02$lnkFileName"
    )
    assert result.to_dict()["records"][0]["document"]["document_number"] == "628906"


def test_document_routes_include_structured_and_complementary_alternatives() -> None:
    result = washco.execute(
        parse_args("document-routes", "L2500106"),
        log_results=False,
    )
    routes = result.to_dict()["records"][0]["routes"]
    route_ids = {item["route_id"] for item in routes}

    assert {
        "development_applications_under_review",
        "frequently_discussed_development_applications",
        "recent_notices_of_decision",
        "public_hearing_exhibits",
        "civicweb_land_use_hearings",
        "legacy_laserfiche_casefile",
        "permit_records_and_public_request",
    }.issubset(route_ids)
    laserfiche = next(
        item for item in routes if item["route_id"] == "legacy_laserfiche_casefile"
    )
    assert "searchstring=2500106" in laserfiche["url"]


def test_api_request_uses_browser_equivalent_headers_and_closes_response() -> None:
    payload = fixture_json("case_exact.json")
    response = FakeResponse(content=json.dumps(payload).encode())
    session = FakeSession([response])
    client = bounded_client(session)

    returned, _source_artifact = client.api_json(
        washco.CASEFILE_SEARCH_URL,
        parameters={"searchby": "search-account", "account": "L2500106"},
        referer=washco.CASEFILE_APP_URL,
    )

    assert returned["total"] == 1
    headers = session.calls[0]["headers"]
    assert headers["Origin"] == washco.WEBAPPS_ORIGIN
    assert headers["Referer"] == washco.CASEFILE_APP_URL
    assert headers["X-Requested-With"] == "XMLHttpRequest"
    assert response.closed is True


def test_bounded_transport_closes_non_2xx_and_overflow() -> None:
    forbidden = FakeResponse(
        content=b"forbidden",
        status_code=403,
        headers={"content-type": "text/plain", "content-length": "9"},
    )
    with pytest.raises(RestrictedHTTPError):
        bounded_client(FakeSession([forbidden])).request(
            "GET",
            "https://example.test/restricted",
            maximum_bytes=100,
        )
    assert forbidden.closed is True

    overflow = FakeResponse(
        content=b"",
        headers={"content-type": "text/plain", "content-length": "101"},
    )
    with pytest.raises(ResponseTooLargeError):
        bounded_client(FakeSession([overflow])).request(
            "GET",
            "https://example.test/large",
            maximum_bytes=100,
        )
    assert overflow.closed is True


def test_schema_mismatch_is_not_reported_as_no_results() -> None:
    class BadTotalClient(FixtureClient):
        def api_json(
            self,
            url: str,
            *,
            parameters: Mapping[str, Any],
            referer: str,
        ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
            payload, source_artifact = super().api_json(
                url,
                parameters=parameters,
                referer=referer,
            )
            payload["total"] = 999
            return payload, source_artifact

    result = washco.execute(
        parse_args("case-detail", "L2500106"),
        client=BadTotalClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_exact_casefile_and_taxlot_history() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        detail = washco.execute(
            parse_args("case-detail", washco.PROBE_CASEFILE),
            client=client,
            log_results=False,
        )
        history = washco.execute(
            parse_args(
                "case-search",
                "taxlot",
                washco.PROBE_TAXLOT,
            ),
            client=client,
            log_results=False,
        )

    record = detail.to_dict()["records"][0]
    assert record["native_ids"]["accela_cap_id"] == "25PLN-00000-00371"
    assert record["joins"]["activities"] == ["HR25-0008"]
    assert record["joins"]["taxlots"] == ["2N2330002700"]
    assert len(history.records) == 18


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_current_review_decisions_and_staff_vocabularies() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        review = washco.execute(
            parse_args("case-review"),
            client=client,
            log_results=False,
        )
        decisions = washco.execute(
            parse_args("case-decisions"),
            client=client,
            log_results=False,
        )
        staff = washco.execute(
            parse_args("case-staff"),
            client=client,
            log_results=False,
        )

    assert review.status == ResultStatus.OK
    assert decisions.status == ResultStatus.OK
    assert staff.status == ResultStatus.OK
    assert all(item["native_record_id"] for item in review.to_dict()["records"])
    assert len(staff.records) >= 40


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_taxlot_project_activity_composite() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        result = washco.execute(
            parse_args("taxlot-activity", washco.PROBE_TAXLOT),
            client=client,
            log_results=False,
        )

    assert result.status == ResultStatus.OK
    records = result.to_dict()["records"]
    assert len(records) >= 100
    assert any(
        item["joins"]["casefile_or_development_number"] == "L2500106"
        for item in records
    )
    assert {item["record_kind"] for item in records} == {
        "taxlot_projects",
        "taxlot_activity",
    }


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_building_taxlot_types_and_scoped_challenge() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        taxlot = washco.execute(
            parse_args("building-search", "taxlot", washco.PROBE_TAXLOT),
            client=client,
            log_results=False,
        )
        types = washco.execute(
            parse_args("building-types"),
            client=client,
            log_results=False,
        )
        challenged = washco.execute(
            parse_args("building-search", "permit", washco.PROBE_PERMIT),
            client=client,
            log_results=False,
        )

    assert taxlot.status == ResultStatus.OK
    assert len(taxlot.records) == 7
    assert types.status == ResultStatus.OK
    assert len(types.records) == 40
    assert challenged.status == ResultStatus.HUMAN_REQUIRED


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_all_permit_report_operations() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        results = {
            kind: washco.execute(
                parse_args("permit-report", kind, identifier),
                client=client,
                log_results=False,
            )
            for kind, identifier in (
                ("project", washco.PROBE_PROJECT),
                ("activity", washco.PROBE_ACTIVITY),
                ("people", washco.PROBE_ACTIVITY),
                ("inspection", washco.PROBE_PERMIT),
                ("review", washco.PROBE_PERMIT),
            )
        }

    assert all(result.status == ResultStatus.OK for result in results.values())
    project = results["project"].to_dict()["records"][0]
    assert project["joins"]["activity_or_permit_numbers"] == [
        "05214429",
        "05229066",
        "05229679",
    ]
    assert results["inspection"].to_dict()["records"][0]["joins"][
        "permit_number"
    ] == washco.PROBE_PERMIT


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_accela_detail_and_session_bound_attachments() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        result = washco.execute(
            parse_args("accela-record", washco.PROBE_CASEFILE),
            client=client,
            log_results=False,
        )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["native_ids"]["accela_cap_id"] == "25PLN-00000-00371"
    assert [item["document_number"] for item in record["documents"]] == [
        "628906",
        "628907",
    ]
    assert record["parcels"][0]["parcel_number"] == washco.PROBE_TAXLOT


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_accela_document_detail() -> None:
    with washco.CasePermitClient(minimum_interval=0.25) as client:
        result = washco.execute(
            parse_args(
                "accela-document",
                washco.PROBE_CASEFILE,
                "628906",
            ),
            client=client,
            log_results=False,
        )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["field_map"]["File Name"].endswith(".pdf")
    assert record["listing_metadata"]["document_number"] == "628906"
