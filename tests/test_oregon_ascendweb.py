from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import oregon_ascendweb as family
from tools import query_oregon_wasco_property as wasco
from tools import query_oregon_yamhill_property as yamhill


FIXTURES = Path(__file__).parent / "fixtures" / "public_records"


def fixture(path: str) -> str:
    return (FIXTURES / path).read_text()


class FakeStreamResponse:
    def __init__(
        self,
        url: str,
        body: bytes,
        *,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        content_length: int | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self.encoding = "utf-8"
        self.history: list[Any] = []
        self.body = body
        self.closed = False

    @property
    def text(self) -> str:
        raise AssertionError("bounded transport must not materialize response.text")

    def iter_content(self, *, chunk_size: int):
        assert chunk_size == 64 * 1024
        for start in range(0, len(self.body), 7):
            yield self.body[start : start + 7]

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeStreamResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeStreamResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        return None


def test_manifests_keep_verified_tenant_roots_aliases_and_versions_distinct():
    yamhill_contract = yamhill.YAMHILL_ASCEND_MANIFEST.contract_record()
    wasco_contract = wasco.ASCEND_MANIFEST.contract_record()

    assert yamhill_contract["tenant_root_path"] == "/AcsendWeb/"
    assert wasco_contract["tenant_root_path"] == "/webtax/"
    assert yamhill_contract["submit_value"] == "Account Info"
    assert wasco_contract["submit_value"] == "Parcel Info"
    assert yamhill_contract["observed_versions"] == ["4.0.3.0"]
    assert wasco_contract["observed_versions"] == ["4.0.2.7"]


def test_shared_home_parser_validates_two_live_verified_form_contracts():
    yamhill_home = family.parse_home(
        yamhill.YAMHILL_ASCEND_MANIFEST,
        fixture("oregon_yamhill_property/default.html"),
    )
    wasco_home = family.parse_home(
        wasco.ASCEND_MANIFEST,
        fixture("oregon_wasco_property/default.html"),
    )

    assert yamhill_home.version == "4.0.3.0"
    assert wasco_home.version == "4.0.2.7"
    assert "mAlternateParcelID" in yamhill_home.form_fields
    assert "mAlternateParcelID" in wasco_home.form_fields
    assert yamhill_home.schema_fingerprint != wasco_home.schema_fingerprint


def test_canonicalization_removes_only_declared_session_segment():
    native = (
        "https://public.co.wasco.or.us/webtax/"
        "(S(fixture))/ParcelInfo.aspx?parcel_number=9450"
    )
    assert family.canonical_url(wasco.ASCEND_MANIFEST, native) == (
        "https://public.co.wasco.or.us/webtax/"
        "ParcelInfo.aspx?parcel_number=9450"
    )
    assert "(S(fixture))" in family.request_url(wasco.ASCEND_MANIFEST, native)
    with pytest.raises(ValueError, match="response host"):
        family.canonical_url(
            wasco.ASCEND_MANIFEST,
            "https://example.com/webtax/default.aspx",
        )
    with pytest.raises(ValueError, match="response path"):
        family.canonical_url(
            wasco.ASCEND_MANIFEST,
            "https://public.co.wasco.or.us/other/default.aspx",
        )


def test_client_replays_hidden_state_and_tenant_aliases_with_injected_limiter():
    home_url = (
        f"{wasco.ASCEND_ROOT_URL}(S(session))/default.aspx"
    )
    result_url = (
        f"{wasco.ASCEND_ROOT_URL}(S(session))/results.aspx"
    )
    session = FakeSession(
        [
            FakeStreamResponse(
                home_url,
                fixture("oregon_wasco_property/default.html").encode(),
            ),
            FakeStreamResponse(
                result_url,
                fixture("oregon_wasco_property/search_main.html").encode(),
            ),
        ]
    )
    sleeps: list[float] = []
    client = family.AscendWebClient(
        wasco.ASCEND_MANIFEST,
        session=session,
        minimum_interval=1,
        retry_attempts=1,
        sleeper=sleeps.append,
        clock=lambda: 0,
    )

    page = client.search(account="9450", city="DUFUR")

    assert page.source_url == f"{wasco.ASCEND_ROOT_URL}results.aspx"
    assert len(session.calls) == 2
    posted = session.calls[1]["data"]
    assert posted["__VIEWSTATE"] == "view"
    assert posted["mParcelID2"] == "9450"
    assert posted["mCity"] == "DUFUR"
    assert posted["mSubmit"] == "Parcel Info"
    assert sleeps == [1]


def test_non_success_error_excerpt_is_stream_bounded_and_closes_response():
    response = FakeStreamResponse(
        wasco.ASCEND_MANIFEST.home_url,
        b"x" * 50_000,
        status_code=500,
    )
    session = FakeSession([response])
    manifest = family.AscendTenantManifest(
        **{
            **wasco.ASCEND_MANIFEST.__dict__,
            "maximum_error_bytes": 32,
        }
    )
    client = family.AscendWebClient(
        manifest,
        session=session,
        minimum_interval=0,
        retry_attempts=1,
    )

    with pytest.raises(wasco.ascend.HTTPStatusError) as error:
        client.fetch_home()

    assert response.closed
    assert len(error.value.details["response_text"]) <= 33


def test_complete_table_cursor_binds_query_schema_and_snapshot():
    source_url = f"{wasco.ASCEND_ROOT_URL}results.aspx"
    parsed = family.parse_search(
        wasco.ASCEND_MANIFEST,
        fixture("oregon_wasco_property/search_main.html"),
        source_url=source_url,
    )
    first = family.slice_complete_search(
        wasco.ASCEND_MANIFEST,
        parsed,
        cursor_prefix=wasco.ASCEND_CURSOR_PREFIX,
        criteria={"value": "MAIN", "field": "address"},
        limit=1,
        cursor=None,
    )
    changed = family.parse_search(
        wasco.ASCEND_MANIFEST,
        fixture("oregon_wasco_property/search_main.html").replace(
            "SECOND OBSERVED PARTY",
            "CHANGED PARTY",
        ),
        source_url=source_url,
    )

    with pytest.raises(wasco.SourceSchemaError, match="snapshot changed"):
        family.slice_complete_search(
            wasco.ASCEND_MANIFEST,
            changed,
            cursor_prefix=wasco.ASCEND_CURSOR_PREFIX,
            criteria={"value": "MAIN", "field": "address"},
            limit=1,
            cursor=first.next_cursor,
        )
