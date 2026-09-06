from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tools import kofile_publicsearch


FIXTURE_DIR = Path("tests/fixtures/public_records/bexar_courts")
BOOTSTRAP_HTML = (FIXTURE_DIR / "bootstrap.html").read_text(encoding="utf-8")
SEARCH_RESPONSE = json.loads(
    (FIXTURE_DIR / "search_response.json").read_text(encoding="utf-8")
)
DETAIL_RESPONSE = json.loads(
    (FIXTURE_DIR / "detail_response.json").read_text(encoding="utf-8")
)


class FakeCookieJar(dict):
    def get_dict(self):
        return dict(self)


@dataclass
class FakeResponse:
    status_code: int
    text: str = ""
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)


class FakeSession:
    def __init__(
        self,
        *,
        image_status: int = 200,
        image_content: bytes = b"\x89PNG\r\nfixture",
    ):
        self.cookies = FakeCookieJar()
        self.image_status = image_status
        self.image_content = image_content
        self.calls = []
        self.bootstrap_calls = 0

    def get(self, url, *, timeout, headers):
        self.calls.append(
            {
                "url": url,
                "timeout": timeout,
                "headers": dict(headers),
                "cookies": dict(self.cookies),
            }
        )
        if url.endswith("/"):
            self.bootstrap_calls += 1
            self.cookies["authToken"] = "anonymous-token-1"
            self.cookies["authToken.sig"] = "signature-1"
            return FakeResponse(200, text=BOOTSTRAP_HTML)
        if "/files/documents/" in url:
            if not (
                self.cookies.get("authToken") == "anonymous-token-1"
                and self.cookies.get("authToken.sig") == "signature-1"
            ):
                return FakeResponse(401)
            return FakeResponse(
                self.image_status,
                content=self.image_content,
                headers={
                    "Content-Type": "image/png",
                    "ETag": '"fixture-etag"',
                },
            )
        raise AssertionError(f"unexpected HTTP GET {url}")


class FakeWebSocket:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def send(self, value):
        self.sent.append(json.loads(value))

    def recv(self, *, timeout):
        if not self.responses:
            raise TimeoutError
        return json.dumps(self.responses.pop(0))


class WebSocketFactory:
    def __init__(self, *response_groups):
        self.response_groups = [list(group) for group in response_groups]
        self.calls = []
        self.sockets = []

    def __call__(self, url, **kwargs):
        if not self.response_groups:
            raise AssertionError("unexpected WebSocket connection")
        socket = FakeWebSocket(self.response_groups.pop(0))
        self.calls.append({"url": url, **kwargs})
        self.sockets.append(socket)
        return socket


def _client(*response_groups, session=None):
    factory = WebSocketFactory(*response_groups)
    client = kofile_publicsearch.KofilePublicSearchClient(
        "https://bexardistrict.tx.publicsearch.us",
        session=session or FakeSession(),
        websocket_factory=factory,
        timeout=2,
    )
    return client, factory


def test_parse_hydrated_state_preserves_string_and_converts_undefined():
    state = kofile_publicsearch.parse_hydrated_state(BOOTSTRAP_HTML)

    assert state["configuration"]["tenantId"] == "48029dc"
    assert (
        state["search"]["departmentDateRanges"]["HC"]["certifiedDate"]
        is None
    )
    assert state["literal"] == "undefined remains text"


def test_parse_hydrated_state_accepts_script_attributes_and_whitespace():
    html = BOOTSTRAP_HTML.replace(
        "<script>",
        '<script nonce="fixture">',
    ).replace(";</script>", ";\n</script>")

    state = kofile_publicsearch.parse_hydrated_state(html)

    assert state["configuration"]["tenantId"] == "48029dc"


def test_search_uses_versioned_protocol_and_source_offset_pagination():
    client, factory = _client([SEARCH_RESPONSE])

    page = client.search(
        department="HC",
        limit=2,
        offset=0,
        search_value="SMITH",
        workspace_id="fixture-workspace",
    )

    assert [row["id"] for row in page.records] == [101, 102]
    assert page.total_count == 3
    assert page.next_offset == 2
    assert page.response_type == kofile_publicsearch.SEARCH_SUCCESS_TYPE
    request = factory.sockets[0].sent[0]
    assert request["type"] == kofile_publicsearch.SEARCH_REQUEST_TYPE
    assert request["payload"] == {
        "workspaceID": "fixture-workspace",
        "query": {
            "limit": 2,
            "offset": 0,
            "department": "HC",
            "searchOcrText": False,
            "searchType": "quickSearch",
            "searchValue": "SMITH",
        },
    }
    assert request["authToken"] == "anonymous-token-1"
    assert factory.calls[0]["additional_headers"]["Cookie"] == (
        "authToken=anonymous-token-1; authToken.sig=signature-1"
    )
    assert client.request_count == 2


def test_ocr_date_range_uses_advanced_search_shape():
    client, factory = _client([SEARCH_RESPONSE])

    client.search(
        department="HC",
        limit=2,
        offset=7,
        search_value="jury verdict",
        search_ocr_text=True,
        recorded_date_range="19190101,19191231",
        workspace_id="ocr-workspace",
    )

    query = factory.sockets[0].sent[0]["payload"]["query"]
    assert query == {
        "limit": 2,
        "offset": 7,
        "department": "HC",
        "searchOcrText": True,
        "searchType": "advancedSearch",
        "recordedDateRange": "19190101,19191231",
        "ocrText": "jury verdict",
    }


def test_fulfilled_zero_is_authoritative_no_results_page():
    response = {
        "type": kofile_publicsearch.SEARCH_SUCCESS_TYPE,
        "payload": {
            "data": {"byOrder": [], "byHash": {}},
            "meta": {"numRecords": 0, "statistics": {}},
        },
    }
    client, _factory = _client([response])

    page = client.search(
        department="HC",
        limit=50,
        search_value="NO SUCH PARTY",
    )

    assert page.records == ()
    assert page.total_count == 0
    assert page.next_offset is None


def test_unexpected_search_protocol_version_is_source_changed():
    changed = {
        "type": "@kofile/FETCH_DOCUMENTS_FULFILLED/v7",
        "payload": {},
    }
    client, _factory = _client([changed])

    with pytest.raises(
        kofile_publicsearch.KofileSourceChangedError
    ) as raised:
        client.search(
            department="HC",
            limit=1,
            search_value="SMITH",
        )

    assert raised.value.code == "search_protocol_version_changed"
    assert raised.value.details["observed"].endswith("/v7")


def test_detail_request_uses_exact_native_document_id():
    client, factory = _client([DETAIL_RESPONSE])

    detail = client.fetch_document(102)

    assert detail["id"] == 102
    assert detail["rsId"] == "BexarTXCivilCaseFiles-012294"
    request = factory.sockets[0].sent[0]
    assert request["type"] == kofile_publicsearch.DETAIL_REQUEST_TYPE
    assert request["payload"] == {"id": 102}


def test_page_fetch_refreshes_signed_url_and_reuses_anonymous_cookie():
    session = FakeSession()
    client, factory = _client([DETAIL_RESPONSE], session=session)
    client.bootstrap()

    page = client.fetch_page_image(102, 2)

    assert session.bootstrap_calls == 2
    assert page.page_number == 2
    assert page.source_url.endswith("502_2.png?exp=2000000000&sig=page-two")
    assert page.content == b"\x89PNG\r\nfixture"
    assert page.etag == '"fixture-etag"'
    assert session.calls[-1]["cookies"] == {
        "authToken": "anonymous-token-1",
        "authToken.sig": "signature-1",
    }
    assert factory.sockets[0].sent[0]["type"] == "fetch-a-document"
    assert client.request_count == 4


def test_signed_image_access_failure_is_not_no_results():
    session = FakeSession(image_status=401)
    client, _factory = _client([DETAIL_RESPONSE], session=session)

    with pytest.raises(kofile_publicsearch.KofileAccessError) as raised:
        client.fetch_page_image(102, 1)

    assert raised.value.code == "anonymous_access_denied"
