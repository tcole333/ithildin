from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from tools import query_palm_beach_official_records as recorder


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/palm_beach_official_records"
)
HOME = (FIXTURE_DIR / "home.html").read_text(encoding="utf-8")
DETAIL_DEED = (FIXTURE_DIR / "detail-deed.html").read_text(encoding="utf-8")
DETAIL_MORTGAGE = (FIXTURE_DIR / "detail-mortgage.html").read_text(
    encoding="utf-8"
)
IMAGE_DETAILS = (FIXTURE_DIR / "image-details.html").read_text(
    encoding="utf-8"
)
PNG = b"\x89PNG\r\n\x1a\nfixture-image"


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)


class QueueSession:
    def __init__(self, responses: list[FixtureResponse]):
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method,
        url,
        *,
        params=None,
        data=None,
        timeout=None,
        allow_redirects=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "data": dict(data or {}),
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected Palm Beach recorder request")
        return self.responses.pop(0)


def fixture_client(responses):
    return recorder.PalmBeachRecorderClient(
        QueueSession(responses),
        minimum_interval=0,
        max_attempts=1,
    )


def test_parse_deed_preserves_instrument_parties_parcel_and_image_state():
    record = recorder.parse_document_detail(
        DETAIL_DEED,
        document_id=recorder.SENTINEL_DOCUMENT_ID,
    )

    assert record["canonical_ref"] == (
        "PROPERTY:us-fl-palm-beach-official-records/12099/"
        "instrument/19860255822"
    )
    assert record["evidence_ref"] == record["canonical_ref"]
    assert record["instrument_number"] == "19860255822"
    assert record["book_type"] == "O"
    assert record["book"] == "5021"
    assert record["page"] == "1011"
    assert record["recording_date"] == "1986-09-30"
    assert record["document_type"] == "DEED"
    assert record["page_count"] == 1
    assert record["indexed_name_count"] == 3
    assert record["grantors"] == ["ROBERT C MALT & CO"]
    assert record["grantees"] == ["PESCHEK JEFFREY", "STIYER ANN F"]
    assert record["parties"][0] == {
        "name": "ROBERT C MALT & CO",
        "role": "grantor",
        "raw_role": "Grantor",
    }
    assert record["parcel_ids"] == ["00424411190010180"]
    assert record["parcel_ids_normalized"] == ["00424411190010180"]
    assert record["legal_descriptions"] == ["L18 B1 VICTORIA WOODS 1"]
    assert record["image_access"] == {
        "status": "available_online",
        "online_page_count": 1,
        "media_type_observed": "image/png",
        "endpoint": recorder.IMAGE_URL,
        "record_specific": True,
    }
    assert record["property_links"]["property_appraiser"].startswith(
        "https://pbcpao.gov/"
    )
    assert record["property_links"]["tax_collector"].startswith(
        "https://pbctax.publicaccessnow.com/"
    )
    assert "DocumentAndInfoByBookPage" in record["source_url"]


def test_parse_mortgage_preserves_consideration_and_hyphenated_parcel():
    record = recorder.parse_document_detail(
        DETAIL_MORTGAGE,
        document_id="28466780",
    )

    assert record["instrument_number"] == "20260277555"
    assert record["document_type"] == "MORTGAGE"
    assert record["consideration"] == 250000.0
    assert record["consideration_raw"] == "$250,000.00"
    assert record["consideration_label"] == "Mortgage Consideration"
    assert record["parcel_ids"] == ["00-42-46-29-12-000-3090"]
    assert record["parcel_ids_normalized"] == ["00424629120003090"]
    assert record["image_access"]["online_page_count"] == 6


def test_detail_without_instrument_is_source_drift():
    broken = DETAIL_DEED.replace("19860255822", "not-a-number")

    with pytest.raises(
        recorder.PalmBeachRecorderSourceChanged,
        match="numeric instrument",
    ):
        recorder.parse_document_detail(broken, document_id="6402430")


def test_client_accepts_once_and_resolves_exact_instrument():
    session = QueueSession(
        [
            FixtureResponse(text=HOME),
            FixtureResponse(),
            FixtureResponse(text=recorder.SENTINEL_DOCUMENT_ID),
            FixtureResponse(),
            FixtureResponse(status_code=302),
            FixtureResponse(text=DETAIL_DEED),
            FixtureResponse(text=IMAGE_DETAILS),
        ]
    )
    client = recorder.PalmBeachRecorderClient(
        session,
        minimum_interval=0,
        max_attempts=1,
    )

    record = client.instrument(recorder.SENTINEL_INSTRUMENT)

    assert record is not None
    assert record["instrument_number"] == recorder.SENTINEL_INSTRUMENT
    assert [call["method"] for call in session.calls] == [
        "GET",
        "POST",
        "GET",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert session.calls[1]["url"] == recorder.DISCLAIMER_URL
    assert session.calls[2]["params"] == {
        "cfnNumber": recorder.SENTINEL_INSTRUMENT
    }
    assert session.calls[3]["url"] == recorder.SET_SESSION_DOCUMENT_URL
    assert session.calls[3]["data"]["documentId"] == (
        recorder.SENTINEL_DOCUMENT_ID
    )
    assert session.calls[4]["url"] == recorder.DETAIL_URL
    assert session.calls[4]["allow_redirects"] is False
    assert session.calls[5]["url"] == recorder.DOCUMENT_INFORMATION_URL
    assert session.calls[6]["url"] == recorder.DOCUMENT_DETAILS_URL
    assert session.calls[6]["data"]["id"] == recorder.SENTINEL_DOCUMENT_ID


def test_client_book_page_uses_native_book_type_and_empty_is_no_result():
    session = QueueSession(
        [
            FixtureResponse(text=HOME),
            FixtureResponse(),
            FixtureResponse(text=""),
        ]
    )
    client = recorder.PalmBeachRecorderClient(
        session,
        minimum_interval=0,
        max_attempts=1,
    )

    assert client.book_page(5021, 1011) is None
    assert session.calls[2]["params"] == {
        "bookPageNumber": "5021/1011",
        "bookType": 3,
    }


def test_image_validates_png_and_preserves_hash():
    session = QueueSession(
        [
            FixtureResponse(
                content=PNG,
                headers={"Content-Type": "image/png"},
            )
        ]
    )
    client = recorder.PalmBeachRecorderClient(
        session,
        minimum_interval=0,
        max_attempts=1,
    )
    record = recorder.parse_document_detail(
        DETAIL_DEED,
        document_id=recorder.SENTINEL_DOCUMENT_ID,
    )

    artifact = client.image(record, 1)

    assert artifact.content == PNG
    assert artifact.media_type == "image/png"
    assert artifact.sha256 == hashlib.sha256(PNG).hexdigest()
    assert session.calls[0]["params"]["pageNum"] == 1


def test_non_png_image_response_preserves_record_specific_unavailability():
    session = QueueSession(
        [
            FixtureResponse(
                content=b"<html>not available</html>",
                headers={"Content-Type": "text/html"},
            )
        ]
    )
    client = recorder.PalmBeachRecorderClient(
        session,
        minimum_interval=0,
        max_attempts=1,
    )
    record = recorder.parse_document_detail(
        DETAIL_DEED,
        document_id=recorder.SENTINEL_DOCUMENT_ID,
    )

    with pytest.raises(
        recorder.PalmBeachImageUnavailable,
        match="did not return a public PNG",
    ) as error:
        client.image(record, 1)

    assert error.value.record["instrument_number"] == "19860255822"


def test_routes_keep_discovery_bulk_images_property_tax_and_court_distinct():
    routes = recorder.source_routes()

    portal = routes["official_record_portal"]
    assert portal["interactive_discovery"]["captcha_observed"] is True
    assert portal["exact_machine_routes"]["instrument_number"].endswith(
        "/Document/DirectNavByCFN"
    )
    complements = {
        item["kind"]: item for item in routes["complementary_routes"]
    }
    assert {
        item["source_id"] for item in routes["complementary_routes"]
    } == {
        "us-fl-palm-beach-official-records-daily-index",
        "us-fl-palm-beach-official-records-cd-archive",
        "us-fl-palm-beach-records-service",
        "us-fl-palm-beach-property-appraiser",
        "us-fl-dor-property-roll",
        "us-fl-palm-beach-tax-collector",
        "us-fl-palm-beach-tax-deeds",
        "us-fl-palm-beach-ecaseview",
    }
    ftp = complements["paid_daily_official_index"]
    assert ftp["format"] == "pipe-delimited daily .dat"
    assert ftp["images_included"] is False
    assert ftp["retention"] == "not less than 45 days"
    assert ftp["annual_fee_usd"] == 600
    assert complements["official_index_and_images_cd_archive"][
        "coverage"
    ] == "1968-present"
    assert complements["palm_beach_property_appraiser"][
        "relationship"
    ] == "parcel_owner_value_and_sale_context"
    assert complements["palm_beach_tax_deeds"]["url"] == (
        "https://taxdeed.mypalmbeachclerk.com/"
    )
    assert complements["palm_beach_ecaseview"]["source_id"] == (
        "us-fl-palm-beach-ecaseview"
    )


def test_execute_exact_no_result_is_authoritative(monkeypatch):
    class FakeClient:
        def instrument(self, instrument_number):
            assert instrument_number == "19000000000"
            return None

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    args = recorder.build_parser().parse_args(
        ["instrument", "19000000000"]
    )

    result = recorder.execute(args, client=FakeClient())

    assert result.status == recorder.ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_execute_downloads_image_and_returns_artifact_receipt(
    monkeypatch,
    tmp_path,
):
    record = recorder.parse_document_detail(
        DETAIL_DEED,
        document_id=recorder.SENTINEL_DOCUMENT_ID,
    )

    class FakeClient:
        def instrument(self, instrument_number):
            assert instrument_number == recorder.SENTINEL_INSTRUMENT
            return record

        def image(self, selected_record, page_number):
            assert selected_record["canonical_ref"] == record["canonical_ref"]
            assert page_number == 1
            return recorder.DocumentImage(
                content=PNG,
                media_type="image/png",
                page_number=1,
                sha256=hashlib.sha256(PNG).hexdigest(),
            )

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    destination = tmp_path / "page-1.png"
    args = recorder.build_parser().parse_args(
        [
            "image",
            "--instrument",
            recorder.SENTINEL_INSTRUMENT,
            "--document-output",
            str(destination),
        ]
    )

    result = recorder.execute(args, client=FakeClient())

    assert result.status == recorder.ResultStatus.OK
    assert destination.read_bytes() == PNG
    artifact = result.records[0]
    assert artifact["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert artifact["document_output"] == str(destination)
    assert urlparse(artifact["source_url"]).hostname == (
        "erec.mypalmbeachclerk.com"
    )
    assert result.raw_artifact_refs == (str(destination),)


def test_image_selector_rejects_ambiguous_instrument_and_book(monkeypatch):
    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    args = recorder.build_parser().parse_args(
        [
            "image",
            "--instrument",
            recorder.SENTINEL_INSTRUMENT,
            "--book",
            "5021",
            "--record-page",
            "1011",
            "--document-output",
            "/tmp/unused.png",
        ]
    )

    result = recorder.execute(args, client=object())

    assert result.status == recorder.ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "invalid_source_query"
