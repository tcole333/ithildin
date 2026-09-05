from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_jackson_accela as accela
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_jackson_accela"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        body: str | bytes,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.content = body.encode() if isinstance(body, str) else body
        self.text = self.content.decode("utf-8", errors="replace")
        self.url = url
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.closed = False

    def iter_content(self, chunk_size: int = 64 * 1024):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]

    def close(self) -> None:
        self.closed = True


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def fake_client(
    responses: list[FakeResponse],
) -> tuple[accela.JacksonAccelaClient, QueueSession]:
    session = QueueSession(responses)
    client = accela.JacksonAccelaClient(
        session=session,
        minimum_interval=0,
        max_attempts=1,
        sleeper=lambda _seconds: None,
    )
    return client, session


def args_for(*values: str) -> Any:
    return accela.build_parser().parse_args(values)


def page_method(html: str, method_name: str) -> FakeResponse:
    return FakeResponse(
        json.dumps({"d": html}),
        url=f"{accela.RECORD_DETAIL_URL}/{method_name}",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def record_responses() -> list[FakeResponse]:
    detail_url = accela.parse_cap_key(accela.BUILDING, "26CAP-00000-006GM").detail_url
    return [
        FakeResponse(fixture("building_detail.html"), url=detail_url),
        FakeResponse(
            fixture("attachment_list.html"),
            url=f"{accela.ATTACHMENT_LIST_URL}?fixture=1",
        ),
        page_method(fixture("processing.html"), "GetProcessingData"),
        page_method(fixture("related.html"), "GetBuildCapTree"),
        page_method(fixture("fees_unpaid.html"), "DisplayFeeNoPaid"),
        page_method(fixture("fees_paid.html"), "DisplayFeePaid"),
        FakeResponse(fixture("inspections.html"), url=detail_url),
    ]


def test_tenant_and_module_contract_preserves_native_cap_components() -> None:
    key = accela.parse_cap_key(accela.BUILDING, "26CAP-00000-006GM")
    assert key.compact == "26CAP-00000-006GM"
    assert key.detail_parameters == {
        "Module": "Building",
        "TabName": "Building",
        "capID1": "26CAP",
        "capID2": "00000",
        "capID3": "006GM",
        "agencyCode": "JACKSON_CO",
        "IsToShowInspection": "",
    }
    reparsed = accela.parse_record_url(key.detail_url)
    assert reparsed == key


def test_record_url_requires_a_verified_jackson_module() -> None:
    code_url = (
        f"{accela.RECORD_DETAIL_URL}?Module=CodeCompliance&"
        "TabName=CodeCompliance&capID1=26CAP&capID2=00000&capID3=006IG&"
        "agencyCode=JACKSON_CO&IsToShowInspection="
    )
    with pytest.raises(ValueError, match="no verified"):
        accela.parse_record_url(code_url)

    other_agency = accela.parse_cap_key(
        accela.BUILDING, "26CAP-00000-006GM"
    ).detail_url.replace("JACKSON_CO", "OTHER")
    with pytest.raises(ValueError, match="Jackson County"):
        accela.parse_record_url(other_agency)


def test_building_parser_preserves_parties_project_parcel_and_status() -> None:
    record = accela.parse_record_detail(fixture("building_detail.html"))
    detail_map = accela._field_map(record["record_details"])  # noqa: SLF001

    assert record["record_number"] == "439-26-002369-ELEC"
    assert record["record_type"] == "Residential Electrical"
    assert record["record_status"] == "Finaled"
    assert record["expiration_date"] == "01/23/2027"
    assert record["work_location"] == "2255 JOHNS PEAK RD CENTRAL POINT OR"
    assert detail_map["Applicant"] == "STEVE ROBERTS EMR UNIVERSAL LLC"
    assert detail_map["Owner"] == "LUNDIN LESLIE TRUST ET AL"
    assert "14.96kWDC" in detail_map["Project Description"]
    assert record["parcels"][0]["parcel_number"] == "37-2W-17D-500"
    assert record["parcels"][0]["attributes"] == [
        {"label": "ASSESSOR ACCOUNT NUMBER", "value": "10999888"},
        {"label": "ZONING", "value": "RR-5"},
    ]
    assert record["schema_fingerprint"]


def test_planning_parser_handles_paired_columns_and_conditions() -> None:
    record = accela.parse_record_detail(fixture("planning_detail.html"))
    sections = {
        section["section"]: {
            field["label"]: field["value"] for field in section["fields"]
        }
        for section in record["application_information"]
    }

    assert record["record_number"] == "439-ZON2014-00689"
    assert record["record_status"] == "Final Staff Approval"
    assert sections["DATES"]["Decision is Final"] == "05/29/2014"
    assert sections["GENERAL INFORMATION"]["Process Type"] == "Type I"
    assert sections["GENERAL INFORMATION"]["Zoning 1"] == "Exclusive Farm Use"
    parcel = record["parcels"][0]
    assert parcel["parcel_number"] == "35-2W-27-1200"
    assert {"label": "FLOODPLAIN", "value": "FLOODPLAIN"} in parcel["attributes"]
    assert record["conditions"]["items"][0]["name"] == "FLOODPLAIN"
    assert "mapped floodplain" in record["conditions"]["items"][0]["description"]


def test_attachment_listing_preserves_detail_and_binary_representations() -> None:
    documents = accela.parse_attachment_list(
        fixture("attachment_list.html"),
        accela.BUILDING,
        "https://example.test/attachment-list",
    )

    assert [document["document_number"] for document in documents] == [
        "16767278",
        "16767279",
    ]
    plan, permit = documents
    assert plan["description"] == "APPROVED COUNTY PV PLANS"
    assert plan["binary_download_available"] is False
    assert "documentNo=16767278" in plan["document_detail_url"]
    assert permit["file_name"] == ("std_BuildingPermit_pr_20260726_135851.pdf")
    assert permit["download_event_target"] == (
        "attachmentList$gdvAttachmentList$ctl03$lnkFileName"
    )
    assert permit["binary_download_available"] is True


def test_document_processing_related_fee_and_inspection_parsers() -> None:
    document = accela.parse_document_detail(fixture("document_detail.html"))
    processing = accela.parse_processing(fixture("processing.html"))
    related = accela.parse_related_records(fixture("related.html"))
    paid = accela.parse_fees(fixture("fees_paid.html"))
    unpaid = accela.parse_fees(fixture("fees_unpaid.html"))
    inspections = accela.parse_inspections(fixture("inspections.html"))

    assert document["field_map"]["Record Number"] == "439-26-002369-ELEC"
    assert document["field_map"]["Document Type"] == "Building Permit"
    assert [step["task_name"] for step in processing] == [
        "Application Intake",
        "Close Out",
    ]
    assert processing[0]["history"][0]["marked_status"] == ("Application Accepted")
    assert processing[1]["history"][0]["marked_by"] == "David M Jahn"
    assert [item["record_number"] for item in related] == [
        "439-26-002139-STR",
        "439-26-002369-ELEC",
    ]
    assert paid["total"] == "$105.28"
    assert len(paid["rows"]) == 2
    assert unpaid["rows"] == []
    inspection = inspections["groups"][0]["entries"][0]
    assert inspection["inspection_id"] == "7990599"
    assert inspection["status"] == "Approved"
    assert inspection["result_by"] == "David M Jahn"
    assert "InspectionDetails.aspx" in inspection["detail_url"]
    assert "ID=7990599" in inspection["detail_url"]


def test_end_to_end_record_fetch_preserves_each_representation() -> None:
    client, session = fake_client(record_responses())
    result = accela.execute(
        args_for("record", "building", "26CAP-00000-006GM"),
        client=client,
        log_results=False,
    )
    payload = result.to_dict()

    assert payload["status"] == "ok"
    record = payload["records"][0]
    assert record["native_record_id"] == "439-26-002369-ELEC"
    assert record["canonical_ref"].endswith(
        "/building_permit_detail/439-26-002369-ELEC"
    )
    assert record["record_key"]["compact"] == "26CAP-00000-006GM"
    assert record["record_detail_map"]["Owner"] == ("LUNDIN LESLIE TRUST ET AL")
    assert record["participants"] == {
        "applicant": "STEVE ROBERTS EMR UNIVERSAL LLC",
        "owner": "LUNDIN LESLIE TRUST ET AL",
        "licensed_professional": "FREDRICK WHITEHEAD 4149S",
    }
    assert "14.96kWDC" in record["project_description"]
    assert len(record["documents"]) == 2
    assert record["document_representation_summary"] == {
        "listing_complete": True,
        "document_details_fetched": False,
        "binary_documents_fetched": False,
        "detail_and_binary_commands_available": True,
    }
    assert record["processing_steps"][1]["task_name"] == "Close Out"
    assert len(record["related_records"]) == 2
    assert record["fees"]["paid"]["total"] == "$105.28"
    assert (
        record["inspections"]["groups"][0]["entries"][0]["inspection_id"] == "7990599"
    )
    assert set(record["representations"]) == {
        "record_detail",
        "attachment_list",
        "GetProcessingData",
        "GetBuildCapTree",
        "DisplayFeeNoPaid",
        "DisplayFeePaid",
        "inspections",
    }
    assert all(
        len(representation["sha256"]) == 64
        for representation in record["representations"].values()
    )
    assert session.requests[0]["method"] == "GET"
    assert session.requests[1]["headers"]["Referer"].endswith(
        "agencyCode=JACKSON_CO&IsToShowInspection="
    )
    for request in session.requests[2:6]:
        assert request["headers"]["Origin"] == accela.ROOT_URL
        assert request["headers"]["Referer"].endswith(
            "agencyCode=JACKSON_CO&IsToShowInspection="
        )
    assert session.requests[6]["data"]["__EVENTTARGET"] == (
        accela.INSPECTION_EVENT_TARGET
    )
    assert session.requests[6]["data"]["__VIEWSTATE"] == "fixture-viewstate"


def test_independent_document_detail_fetch_has_stable_provenance() -> None:
    detail_url = accela._document_detail_url(  # noqa: SLF001
        accela.BUILDING, "16767279"
    )
    client, session = fake_client(
        [FakeResponse(fixture("document_detail.html"), url=detail_url)]
    )
    result = accela.execute(
        args_for("document", "building", "16767279"),
        client=client,
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["document_number"] == "16767279"
    assert record["field_map"]["File Name"].endswith(".pdf")
    assert record["representation"]["response_url"] == detail_url
    assert record["representation"]["request_parameters"]["documentNo"] == "16767279"
    assert len(session.requests) == 1


def test_binary_download_posts_listing_state_and_writes_manifest(
    tmp_path: Path,
) -> None:
    key = accela.parse_cap_key(accela.BUILDING, "26CAP-00000-006GM")
    binary = b"%PDF-1.7\nfixture\n%%EOF\n"
    destination = tmp_path / "permit.pdf"
    client, session = fake_client(
        [
            FakeResponse(fixture("building_detail.html"), url=key.detail_url),
            FakeResponse(
                fixture("attachment_list.html"),
                url=f"{accela.ATTACHMENT_LIST_URL}?fixture=1",
            ),
            FakeResponse(
                binary,
                url=f"{accela.ATTACHMENT_LIST_URL}?fixture=1",
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Disposition": (
                        "attachment; filename=std_BuildingPermit_pr_20260726_135851.pdf"
                    ),
                },
            ),
        ]
    )
    result = accela.execute(
        args_for(
            "download",
            "building",
            "26CAP-00000-006GM",
            "16767279",
            "--destination",
            str(destination),
        ),
        client=client,
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert destination.read_bytes() == binary
    assert record["representation"]["byte_length"] == len(binary)
    assert record["representation"]["content_disposition"].startswith("attachment;")
    post = session.requests[-1]
    assert post["method"] == "POST"
    assert post["headers"]["Origin"] == accela.ROOT_URL
    assert post["headers"]["Referer"].endswith("?fixture=1")
    assert post["data"]["__VIEWSTATE"] == "attachment-viewstate"
    assert post["data"]["ACA_CS_FIELD"] == "attachment-cs"
    assert post["data"]["__EVENTTARGET"] == (
        "attachmentList$gdvAttachmentList$ctl03$lnkFileName"
    )


def test_response_bound_rejects_declared_and_streamed_oversize_bodies() -> None:
    key = accela.parse_cap_key(accela.BUILDING, "26CAP-00000-006GM")
    declared = FakeResponse(
        fixture("building_detail.html"),
        url=key.detail_url,
        headers={
            "Content-Type": "text/html; charset=utf-8",
            "Content-Length": "4097",
        },
    )
    declared_client = accela.JacksonAccelaClient(
        session=QueueSession([declared]),
        minimum_interval=0,
        max_attempts=1,
        max_response_bytes=4096,
        sleeper=lambda _seconds: None,
    )
    with pytest.raises(accela.SourceResponseError, match="byte bound") as declared_error:
        declared_client.fetch_record_page(key)
    assert declared_error.value.details == {
        "content_length": 4097,
        "maximum_bytes": 4096,
    }
    assert declared.closed is True

    streamed = FakeResponse(
        b"x" * 4097,
        url=key.detail_url,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )
    streamed_client = accela.JacksonAccelaClient(
        session=QueueSession([streamed]),
        minimum_interval=0,
        max_attempts=1,
        max_response_bytes=4096,
        sleeper=lambda _seconds: None,
    )
    with pytest.raises(accela.SourceResponseError, match="byte bound") as streamed_error:
        streamed_client.fetch_record_page(key)
    assert streamed_error.value.details == {
        "observed_bytes": 4097,
        "maximum_bytes": 4096,
    }
    assert streamed.closed is True


def test_transport_streams_responses_and_exposes_configurable_byte_bound() -> None:
    response = FakeResponse(
        fixture("document_detail.html"),
        url=accela._document_detail_url(accela.BUILDING, "16767279"),  # noqa: SLF001
    )
    client, session = fake_client([response])
    client.fetch_document_detail(accela.BUILDING, "16767279")

    assert session.requests[0]["stream"] is True
    assert response.closed is True
    args = args_for(
        "document",
        "building",
        "16767279",
        "--max-response-bytes",
        "209715200",
    )
    assert args.max_response_bytes == 209715200


def test_sources_expose_code_compliance_alternatives_and_process_learnings() -> None:
    payload = accela.sources_payload()

    assert payload["platform_family"] == "accela_citizen_access"
    assert {source["metadata"]["module"] for source in payload["sources"]} == {
        "Building",
        "Planning",
    }
    code = payload["code_compliance"]
    assert code["detail_representation_available"] is False
    assert {item["kind"] for item in code["complements"]} == {
        "official_arcgis_event_layer",
        "county_records_request",
    }
    assert code["complements"][0]["url"] == accela.CODE_ARCGIS_URL
    assert code["complements"][1]["url"] == accela.RECORDS_REQUEST_URL
    assert {item["scope"] for item in payload["process_learnings"]} == {
        "accela_tenant_contract",
        "representation_identity",
        "session_and_postback_discovery",
        "source_shell_validation",
        "alternative_source_triage",
    }


@pytest.mark.skipif(
    os.getenv("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official endpoint probes",
)
@pytest.mark.parametrize("source", [accela.BUILDING, accela.PLANNING])
def test_live_anonymous_record_and_attachment_probe(
    source: accela.SourceDefinition,
) -> None:
    client = accela.JacksonAccelaClient(minimum_interval=0.4)
    try:
        result = accela.probe_source(client, source, log_results=False)
    finally:
        client.close()

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["source_id"] == source.source_id
    assert record["native_record_id"]
    assert record["record_detail_representation"]["status_code"] == 200
    assert record["attachment_list_representation"]["status_code"] == 200
