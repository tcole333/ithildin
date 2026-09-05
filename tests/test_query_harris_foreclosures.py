from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_harris_foreclosures as frcl


FIXTURE_DIR = Path("tests/fixtures/public_records/harris_foreclosures")
FORM = (FIXTURE_DIR / "search-form.html").read_text(encoding="utf-8")
SENTINEL = (FIXTURE_DIR / "sentinel-result.html").read_text(encoding="utf-8")
NO_RESULTS = (FIXTURE_DIR / "no-results.html").read_text(encoding="utf-8")
PAGE_1 = (FIXTURE_DIR / "page-1.html").read_text(encoding="utf-8")
PAGE_2 = (FIXTURE_DIR / "page-2.html").read_text(encoding="utf-8")
PDF_BYTES = (FIXTURE_DIR / "sentinel.pdf").read_bytes()


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    url: str = frcl.SEARCH_URL
    headers: dict[str, str] = field(default_factory=dict)


class QueueSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method,
        url,
        *,
        data=None,
        timeout=None,
        allow_redirects=None,
    ):
        self.calls.append({
            "method": method,
            "url": url,
            "data": dict(data or {}),
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        })
        if not self.responses:
            raise AssertionError("unexpected foreclosure request")
        return self.responses.pop(0)


def fixture_client(session):
    return frcl.HarrisForeclosureClient(
        session,
        minimum_interval=0,
        max_retries=0,
    )


def allowed():
    return {
        "allowed": True,
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
    }


def test_parse_notice_uses_property_identity_and_non_title_scope():
    payload = frcl.parse_search_page(SENTINEL, frcl.SEARCH_URL)

    assert payload["source_reported_total_results"] == 1
    assert payload["coverage"] == {
        "postings_accepted_through": "2026-07-28",
        "postings_accepted_through_raw": "7/28/2026",
        "document_images_available_from": "2013-12-03",
        "document_images_available_from_raw": "12/3/2013",
    }
    record = payload["results"][0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-tx-harris-clerk-foreclosures/48201/"
        "foreclosure-notice/FRCL-2026-4797"
    )
    assert record["evidence_ref"] == record["canonical_ref"]
    assert record["record_kind"] == "foreclosure_notice"
    assert record["record_scope"] == "proposed_sale_notice"
    assert record["sale_date"] == "2026-08-04"
    assert record["file_date"] == "2026-07-08"
    assert record["page_count"] == 2
    assert record["document_access"]["authentication"] == "anonymous"
    assert record["document_access"]["format"] == "pdf"
    assert record["projection"]["projectable_as_recorded_instrument"] is False
    assert record["projection"]["scope"] == "event_document_only"


def test_parse_authoritative_no_results():
    payload = frcl.parse_search_page(NO_RESULTS, frcl.SEARCH_URL)

    assert payload["source_reported_total_results"] == 0
    assert payload["results"] == []


def test_parser_exposes_native_postback_pages():
    payload = frcl.parse_search_page(PAGE_1, frcl.SEARCH_URL)

    assert payload["available_postback_pages"] == {2}
    assert payload["results"][0]["document_id"] == "FRCL-2026-4797"


def test_exact_search_bootstraps_form_and_posts_document_id():
    session = QueueSession([
        FixtureResponse(FORM),
        FixtureResponse(SENTINEL),
    ])

    payload = fixture_client(session).search(
        document_id=frcl.SENTINEL_DOCUMENT_ID
    )

    assert len(payload["results"]) == 1
    assert [call["method"] for call in session.calls] == ["GET", "POST"]
    post = session.calls[1]["data"]
    assert post["__VIEWSTATE"] == "viewstate"
    assert post[frcl.DOCUMENT_FIELD] == frcl.SENTINEL_DOCUMENT_ID
    assert post[frcl.SEARCH_BUTTON] == "Search"


def test_file_date_search_preserves_radio_and_follows_every_source_page():
    session = QueueSession([
        FixtureResponse(FORM),
        FixtureResponse(FORM),
        FixtureResponse(FORM),
        FixtureResponse(PAGE_1),
        FixtureResponse(PAGE_2),
    ])

    payload = fixture_client(session).search(file_date="2026-07")

    assert [row["document_id"] for row in payload["results"]] == [
        "FRCL-2026-4797",
        "FRCL-2026-4798",
    ]
    assert payload["coverage"]["pages_fetched"] == 2
    assert payload["coverage"]["adapter_truncated"] is False
    assert payload["pagination"]["adapter_followed_all_source_pages"] is True
    assert session.calls[1]["data"]["__EVENTTARGET"] == frcl.YEAR_FIELD
    assert session.calls[1]["data"][frcl.DATE_KIND_FIELD] == "FileDate"
    assert session.calls[2]["data"]["__EVENTTARGET"] == frcl.MONTH_FIELD
    assert session.calls[3]["data"][frcl.SEARCH_BUTTON] == "Search"
    assert session.calls[4]["data"]["__EVENTTARGET"] == frcl.GRID_EVENT_TARGET
    assert session.calls[4]["data"]["__EVENTARGUMENT"] == "Page$2"


def test_full_search_rejects_missing_next_page_when_total_is_unreconciled():
    page_without_next = PAGE_1.replace(
        (
            "javascript:__doPostBack("
            "'ctl00$ContentPlaceHolder1$GridView1','Page$2')"
        ),
        "#missing-next",
    )
    assert page_without_next != PAGE_1
    assert (
        frcl.parse_search_page(
            page_without_next,
            frcl.SEARCH_URL,
        )["available_postback_pages"]
        == set()
    )
    session = QueueSession([
        FixtureResponse(FORM),
        FixtureResponse(page_without_next),
    ])

    with pytest.raises(
        frcl.HarrisForeclosureSourceChanged,
        match="did not reconcile",
    ):
        fixture_client(session).search(document_id="FRCL-2026")


def test_full_search_rejects_changed_total_on_later_page():
    session = QueueSession([
        FixtureResponse(FORM),
        FixtureResponse(PAGE_1),
        FixtureResponse(PAGE_2.replace("2 Row(s)", "3 Row(s)")),
    ])

    with pytest.raises(
        frcl.HarrisForeclosureSourceChanged,
        match="total changed",
    ):
        fixture_client(session).search(document_id="FRCL-2026")


def test_execute_returns_no_results_not_failure(monkeypatch):
    args = frcl.build_parser().parse_args([
        "search",
        "--document-id",
        "FRCL-2013-999999999",
    ])

    class FakeClient:
        def search(self, **_kwargs):
            return {
                "results": [],
                "coverage": {
                    "source_reported_total_results": 0,
                    "adapter_truncated": False,
                },
                "pagination": {
                    "adapter_followed_all_source_pages": True,
                },
            }

    monkeypatch.setattr(frcl, "_log", lambda *_args: None)
    result = frcl.execute(
        args,
        access_decision=allowed(),
        client=FakeClient(),
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()
    assert result.query.query.metadata["access_decision"]["allowed"] is True


def test_execute_marks_user_limited_date_search_partial(monkeypatch):
    args = frcl.build_parser().parse_args([
        "search",
        "--file-date",
        "2026-07",
        "--limit",
        "1",
    ])
    record = frcl.parse_search_page(SENTINEL, frcl.SEARCH_URL)["results"][0]

    class FakeClient:
        def search(self, **kwargs):
            assert kwargs["limit"] == 1
            return {
                "results": [record],
                "coverage": {
                    "source_reported_total_results": 2,
                    "adapter_truncated": True,
                },
                "pagination": {
                    "adapter_followed_all_source_pages": False,
                },
            }

    monkeypatch.setattr(frcl, "_log", lambda *_args: None)
    result = frcl.execute(
        args,
        access_decision=allowed(),
        client=FakeClient(),
    )

    assert result.status.value == "partial"
    assert len(result.records) == 1
    assert result.query.query.requested_limit == 1


def test_execute_honors_denied_catalog_decision(monkeypatch):
    args = frcl.build_parser().parse_args([
        "search",
        "--document-id",
        frcl.SENTINEL_DOCUMENT_ID,
    ])
    decision = {
        "allowed": False,
        "access_class": "D",
        "automation_disposition": "unclear",
        "reason_code": "licensed_contract_required",
        "reason": "fixture denial",
    }
    monkeypatch.setattr(frcl, "_log", lambda *_args: None)

    result = frcl.execute(args, access_decision=decision)

    assert result.status.value == "restricted"
    assert result.errors[0].code == "licensed_contract_required"
    assert result.errors[0].details["access_decision"]["allowed"] is False
    assert result.query.query.metadata["access_decision"]["reason"] == (
        "fixture denial"
    )


def test_download_writes_pdf_and_returns_hash_receipt(monkeypatch, tmp_path):
    args = frcl.build_parser().parse_args([
        "download",
        frcl.SENTINEL_DOCUMENT_ID,
        "--destination",
        str(tmp_path / "notice.pdf"),
    ])
    record = frcl.parse_search_page(SENTINEL, frcl.SEARCH_URL)["results"][0]

    class FakeClient:
        def search(self, **kwargs):
            assert kwargs == {"document_id": frcl.SENTINEL_DOCUMENT_ID}
            return {"results": [record]}

        def fetch_pdf(self, url):
            assert url == record["document_access"]["document_url"]
            return frcl.PDFResponse(
                url=url,
                content=PDF_BYTES,
                media_type="Application/pdf; charset=utf-8",
                headers={},
            )

    monkeypatch.setattr(frcl, "_log", lambda *_args: None)
    result = frcl.execute(
        args,
        access_decision=allowed(),
        client=FakeClient(),
    )

    assert result.status.value == "ok"
    destination = tmp_path / "notice.pdf"
    assert destination.read_bytes() == PDF_BYTES
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    receipt = result.records[0]["artifact_receipt"]
    assert receipt["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
    assert receipt["size"] == len(PDF_BYTES)
    document = result.records[0]["documents"][0]
    assert document["document_type"] == "foreclosure_notice_pdf"
    assert document["authentication"] == "anonymous"


def test_sentinel_checks_stable_index_fields_and_pdf_signature():
    record = frcl.parse_search_page(SENTINEL, frcl.SEARCH_URL)["results"][0]

    class FakeClient:
        def search(self, **kwargs):
            assert kwargs == {"document_id": frcl.SENTINEL_DOCUMENT_ID}
            return {"results": [record]}

        def fetch_pdf(self, url):
            return frcl.PDFResponse(
                url=url,
                content=PDF_BYTES,
                media_type="application/pdf",
                headers={},
            )

    payload = frcl.run_sentinel(FakeClient())

    assert payload["status"] == "ok"
    assert [check["name"] for check in payload["checks"]] == [
        "notice_index",
        "anonymous_notice_pdf",
    ]
    assert payload["checks"][1]["pdf_signature"] == "%PDF-"
