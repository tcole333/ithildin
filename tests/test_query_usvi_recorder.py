from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_usvi_recorder as usvi
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/usvi_recorder")


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        text: str = "<html>ok</html>",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        payload: Any = None,
        content: bytes | None = None,
    ) -> None:
        self.url = url
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}
        self._payload = payload
        self.content = content if content is not None else text.encode()

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON")
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def response(path: str, text: str = "<html>ok</html>", **kwargs):
    return FakeResponse(url=f"{usvi.COUNTYWEB}/{path}", text=text, **kwargs)


def bootstrap_responses() -> list[FakeResponse]:
    return [
        response("login.jsp", fixture("login.html")),
        response("main.jsp", "<html>guest login accepted</html>"),
        response("disclaimer.jsp", fixture("disclaimer.html")),
        response("main.jsp", "<html>disclaimer accepted</html>"),
    ]


def parse_args(*values: str):
    return usvi.build_parser().parse_args(list(values))


def parsed_records() -> list[dict[str, Any]]:
    return usvi.parse_result_list(
        fixture("result_list_1.html"),
        page_number=1,
        start_cursor=0,
    )


def test_guest_bootstrap_uses_session_token_and_exact_disclaimer_sequence():
    session = FakeSession(bootstrap_responses())
    client = usvi.USVIRecorderClient(
        session=session,
        minimum_interval=0,
        max_attempts=1,
    )

    client.bootstrap()

    assert [call[:2] for call in session.calls] == [
        ("GET", usvi.LOGIN_DISPLAY_URL),
        ("POST", usvi.LOGIN_URL),
        ("GET", usvi.DISCLAIMER_URL),
        ("POST", usvi.DISCLAIMER_URL),
    ]
    login_payload = session.calls[1][2]["data"]
    assert login_payload["scriptsupport"] == "yes"
    assert login_payload["public"] == "true"
    assert login_payload["guest"] == "false"
    assert login_payload["struts.token.name"] == "token"
    assert login_payload["token"] == "SESSION-TOKEN"
    assert session.calls[3][2]["data"] == {"cmd": "Accept"}

    client.close()
    assert session.closed is False


def test_client_closes_only_an_internally_created_session(monkeypatch):
    owned = FakeSession([])
    monkeypatch.setattr(usvi.requests, "Session", lambda: owned)
    client = usvi.USVIRecorderClient(minimum_interval=0)

    client.close()

    assert owned.closed is True


def test_search_exhausts_native_pages_and_preserves_district_identity():
    responses = [
        *bootstrap_responses(),
        response("search/SearchMain.jsp", "<html>search main</html>"),
        response("search/SearchCriteria.jsp", "<html>criteria</html>"),
        response(
            "search/dyncriteria/dynCriteria.jsp",
            fixture("search_form.html"),
        ),
        response("search/SearchResultsView.jsp", fixture("search_page_1.html")),
        response(
            "search/USVI/docs_SearchResultList.jsp",
            fixture("result_list_1.html"),
        ),
        response("search/SearchResultsView.jsp", fixture("search_page_2.html")),
        response(
            "search/USVI/docs_SearchResultList.jsp",
            fixture("result_list_2.html"),
        ),
    ]
    session = FakeSession(responses)
    client = usvi.USVIRecorderClient(
        session=session,
        minimum_interval=0,
        max_attempts=1,
    )
    selectors = {
        "names": ["SMITH"],
        "party": "both",
        "name_match": None,
        "district": None,
        "from_date": None,
        "to_date": None,
        "document_types": [],
        "document_number": None,
        "document_number_end": None,
        "book": None,
        "page": None,
        "page_end": None,
        **{key: None for key in usvi.LEGAL_ARGUMENT_FIELDS},
    }
    payload = usvi.build_search_payload(
        selectors,
        search_type="allNames",
        page_size=100,
    )

    result = client.search(search_type="allNames", payload=payload)

    assert result["total_count"] == 3
    assert result["native_page_count"] == 2
    assert len(result["records"]) == 3
    first, second = result["records"][:2]
    assert first["instrument_number"] == second["instrument_number"]
    assert first["native_document_id"] == "ST THOMAS:903442"
    assert second["native_document_id"] == "ST CROIX:803442"
    assert first["canonical_ref"] != second["canonical_ref"]
    assert "2026000625" not in first["canonical_ref"]
    navigation = next(
        call
        for call in session.calls
        if call[1] == usvi.SEARCH_RESULTS_URL
    )
    assert navigation[0] == "GET"
    assert navigation[2]["params"] == {
        "searchSessionId": "searchJobMain",
        "resultPageAction": "nav",
        "sortColumn": "allname",
        "sortDirection": "asc",
        "navDirection": "next",
        "startCursor": "0",
        "pageNumber": "",
    }


def test_authoritative_no_results_requires_source_flag_count_and_message():
    page = usvi.parse_search_page(fixture("no_results.html"))

    assert page.no_results is True
    assert page.total_count == 0
    assert page.page_count == 0

    malformed = fixture("no_results.html").replace(
        "No documents were found that match the specified criteria.",
        "Nothing here",
    )
    with pytest.raises(usvi.USVIRecorderSourceChanged):
        usvi.parse_search_page(malformed)


def test_broad_count_is_not_treated_as_a_cap_or_refinement():
    broad = fixture("search_page_1.html")
    broad = broad.replace("numRecordPages = 2", "numRecordPages = 36")
    broad = broad.replace("resultsCount = 3", "resultsCount = 3553")
    broad = broad.replace("of 3 Items", "of 3553 Items")

    page = usvi.parse_search_page(broad)

    assert page.total_count == 3553
    assert page.page_count == 36
    assert page.no_results is False


def test_result_parser_keeps_all_names_legal_fields_and_verification_state():
    record = parsed_records()[0]

    assert record["grantors"] == ["SMITH A DAVID", "SMITH DOROTHY J"]
    assert record["grantees"] == ["LEDER GREGORY"]
    assert record["parties"][0]["native_role"] == "Party 1"
    assert record["legal"]["qtr_condo"] == "VIRGIN GRAND VILLAS - ST JOHN"
    assert record["legal"]["unit"] == "3211/38"
    assert record["verified_index_row"] is True
    assert record["recording_date"] == "2026-02-05"


def test_detail_parser_preserves_native_labels_and_associated_selectors():
    detail = usvi.parse_detail_page(fixture("detail_page_1.html"))
    associated = usvi.parse_associated_documents(
        fixture("detail_page_2.html")
    )

    assert detail["document_type"] == "DEED"
    assert detail["district"] == "ST THOMAS"
    assert detail["recording_date"] == "2026-02-05"
    assert detail["instrument_date"] == "2026-01-16"
    assert detail["book"] == "42"
    assert detail["page"] == "17"
    assert detail["party_1_names"] == [
        "SMITH A DAVID",
        "SMITH DOROTHY J",
    ]
    assert detail["parties"][-1]["role"] == "grantee"
    assert detail["legal_descriptions"][0]["components"] == {
        "unit": "3211/38",
        "plot": "9",
    }
    assert associated == [
        {
            "native_inst_id": "900001",
            "instrument_number": "2025000001",
            "instrument_type": "MTG",
            "relationship": "source_associated_document",
        }
    ]


def test_search_payload_maps_native_fields_without_default_result_cap():
    args = parse_args(
        "search",
        "SMITH",
        "--party",
        "grantor",
        "--name-match",
        "exact",
        "--district",
        "ST THOMAS",
        "--date-from",
        "2025-01-01",
        "--document-type",
        "deed",
    )
    selectors = usvi.selectors_from_args(args)
    payload = usvi.build_search_payload(
        selectors,
        search_type=usvi.choose_search_type(selectors),
        page_size=args.page_size,
    )

    assert args.limit is None
    assert payload["PARTY"] == "7"
    assert payload["EXACTNAMEMATCH"] == "true"
    assert payload["MUNI"] == "ST THOMAS"
    assert payload["FROMDATE"] == "01/01/2025"
    assert payload["INSTTYPEALL"] == "false"
    assert payload["INSTTYPE"] == "DEED"
    assert payload["DISTINCTRESULTS"] == "true"
    assert payload["RECSPERPAGE"] == "100"


def test_legal_search_uses_verified_field_names_and_source_starts_with_semantics():
    args = parse_args(
        "search",
        "--parcel",
        "3-17",
        "--estate",
        "ESTATE THOMAS",
        "--unit",
        "12",
    )
    selectors = usvi.selectors_from_args(args)
    payload = usvi.build_search_payload(
        selectors,
        search_type=usvi.choose_search_type(selectors),
        page_size=100,
    )

    assert payload["SEARCHTYPE"] == "lbs"
    assert payload["LBS_LGL_ADDL_INDEX4"] == "3-17*"
    assert payload["LBS_LGL_ADDL_INDEX2"] == "ESTATE THOMAS"
    assert payload["LBS_LGL_ADDL_INDEX7"] == "12*"


def test_multiple_name_native_limit_is_visible_and_json_shape_is_preserved():
    args = parse_args(
        "search",
        "--name",
        "ONE",
        "--name",
        "TWO",
    )
    selectors = usvi.selectors_from_args(args)
    payload = usvi.build_search_payload(
        selectors,
        search_type=usvi.choose_search_type(selectors),
        page_size=100,
    )
    assert json.loads(payload["MULTIPLENAMES"]) == [
        {"type": "a", "allName": "ONE"},
        {"type": "a", "allName": "TWO"},
    ]

    too_many = ["search"] + sum(
        (["--name", f"NAME {index}"] for index in range(11)),
        [],
    )
    with pytest.raises(
        usvi.USVIRecorderQueryError,
        match="exposes 10 name rows",
    ):
        usvi.selectors_from_args(parse_args(*too_many))


class ExactClient(usvi.USVIRecorderClient):
    def __init__(self, records, responses):
        self.records = records
        self.responses = list(responses)
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return {
            "records": self.records,
            "total_count": len(self.records),
            "native_page_count": 1,
            "native_page_size": 100,
            "authoritative_no_results": not self.records,
        }

    def _request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError(f"unexpected request {method} {url}")
        return self.responses.pop(0)


def test_exact_detail_reacquisition_verifies_all_three_selectors():
    outer = (
        "<html>instId=903442 instNum=2026000625 "
        "instType=DEED</html>"
    )
    client = ExactClient(
        parsed_records(),
        [
            response("search/DocumentInfoView.jsp", outer),
            response(
                "transaction/transAddDoc.jsp",
                fixture("detail_page_1.html"),
            ),
            response(
                "transaction/transAddDoc.jsp",
                fixture("detail_page_2.html"),
            ),
        ],
    )

    record = client.select_exact(
        district="ST THOMAS",
        inst_id="903442",
        instrument_number="2026000625",
    )

    assert record["native_document_id"] == "ST THOMAS:903442"
    assert record["canonical_ref"] == usvi.instrument_ref(
        "ST THOMAS",
        "903442",
    )
    assert record["associated_documents"][0]["native_inst_id"] == "900001"
    search_payload = client.calls[0][1]["payload"]
    assert search_payload["INSTNUM"] == "2026000625"
    assert search_payload["MUNI"] == "ST THOMAS"


def test_exact_detail_reacquisition_fails_visible_on_locator_mismatch():
    client = ExactClient(parsed_records(), [])

    with pytest.raises(
        usvi.USVIRecorderQueryError,
        match="did not match district, instId, and instrument number",
    ):
        client.select_exact(
            district="ST THOMAS",
            inst_id="999999",
            instrument_number="2026000625",
        )
    assert [call[0] for call in client.calls] == ["search"]


def test_page_image_validates_json_media_signature_and_nested_identity():
    png = b"\x89PNG\r\n\x1a\nfixture-page"
    record = parsed_records()[0]
    client = ExactClient(
        [],
        [
            response(
                "search/InstrumentImageViewInternal.jsp",
                "<html>imageViewer/getPage.do</html>",
            ),
            FakeResponse(
                url=usvi.IMAGE_PAGE_STATE_URL,
                payload={
                    "numberOfPages": 6,
                    "pagePath": "NOT_USED",
                    "status": "success",
                },
                headers={"Content-Type": "application/json"},
            ),
            FakeResponse(
                url=usvi.IMAGE_PNG_URL,
                content=png,
                headers={"Content-Type": "image/png;charset=UTF-8"},
            ),
        ],
    )

    image = client.fetch_page_image(record, 1)
    artifact = usvi._page_artifact(record, image, None)

    assert image.page_count == 6
    assert image.sha256 == hashlib.sha256(png).hexdigest()
    assert artifact["representation_of"] == record["canonical_ref"]
    assert artifact["native_artifact_id"] == "ST THOMAS:903442:page:1"
    assert "not a separate instrument" in artifact["identity_note"]
    state_call = client.calls[1]
    assert state_call[2]["data"]["instnum"] == "903442"
    assert state_call[2]["data"]["pageNumber"] == "1"


class OperationClient:
    def __init__(self, records):
        self.records = records
        self.closed = False

    def instrument_types(self):
        return {"DEED": "DEED"}

    def search(self, **_kwargs):
        return {
            "records": [dict(record) for record in self.records],
            "total_count": len(self.records),
            "native_page_count": 2,
            "native_page_size": 100,
            "authoritative_no_results": not self.records,
        }

    def close(self):
        self.closed = True


def test_execute_applies_caller_window_only_after_exhaustive_native_result(monkeypatch):
    monkeypatch.setattr(usvi, "log_search", lambda *_args: None)
    client = OperationClient(
        parsed_records()
        + usvi.parse_result_list(
            fixture("result_list_2.html"),
            page_number=2,
            start_cursor=2,
        )
    )
    args = parse_args(
        "search",
        "SMITH",
        "--offset",
        "1",
        "--limit",
        "1",
    )

    result = usvi.execute(args, client=client)

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    assert result.records[0]["native_document_id"] == "ST CROIX:803442"
    assert result.records[0]["search_metadata"]["native_pages_exhausted"] is True
    assert result.next_cursor == "usvi-recorder:offset:2"
    assert client.closed is False


def test_invalid_caller_window_is_a_structured_query_failure(monkeypatch):
    monkeypatch.setattr(usvi, "log_search", lambda *_args: None)

    result = usvi.execute(
        parse_args("search", "SMITH", "--limit", "-1"),
        client=OperationClient([]),
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "source_query_not_executable"
    assert result.query.query.requested_limit is None


def test_live_document_type_vocabulary_is_used_instead_of_hardcoded_validation():
    payload = json.loads(fixture("instrument_types.json"))
    types = usvi.parse_instrument_types(payload)

    assert types == {
        "DEED": "DEED",
        "MTG": "MORTGAGE",
        "RELMTG": "RELEASE OF MORTGAGE",
    }

    class VocabularyClient:
        def instrument_types(self):
            return types

    usvi.validate_document_types(
        VocabularyClient(),
        {"document_types": ["DEED"]},
    )
    with pytest.raises(usvi.USVIRecorderQueryError, match="live source"):
        usvi.validate_document_types(
            VocabularyClient(),
            {"document_types": ["NOT-A-TYPE"]},
        )
