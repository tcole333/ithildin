from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_lincoln_propertyweb as propertyweb
from tools.public_records_contract import ResultStatus
from tools.public_records_http import SourceSchemaError


FIXTURES = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_lincoln_propertyweb"
)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads(fixture_text(name))


def parse_args(*values: str) -> Any:
    return propertyweb.build_parser().parse_args(list(values))


class FixtureClient:
    def __init__(self) -> None:
        self.home = propertyweb.parse_home_contract(fixture_text("home.html"))
        self.pages = {
            1: propertyweb.parse_search_page(
                fixture_json("search_page_1.json"),
                source_url=f"{propertyweb.SEARCH_URL}?f=TEST&pn=1",
                requested_page=1,
            ),
            2: propertyweb.parse_search_page(
                fixture_json("search_page_2.json"),
                source_url=f"{propertyweb.SEARCH_URL}?f=TEST&pn=2",
                requested_page=2,
            ),
        }
        self.search_calls: list[int] = []
        self.search_terms: list[str] = []
        self.detail_calls: list[tuple[str, str, str | None]] = []

    def home_contract(self, *, refresh: bool = False) -> propertyweb.HomeContract:
        return self.home

    def search_page(self, **kwargs: Any) -> propertyweb.SearchPage:
        page = int(kwargs["page"])
        self.search_calls.append(page)
        self.search_terms.append(str(kwargs["term"]))
        return self.pages[page]

    def detail(
        self,
        property_quick_ref: str,
        party_quick_ref: str,
        *,
        effective_date: str | None = None,
    ) -> propertyweb.HTMLPage:
        self.detail_calls.append((property_quick_ref, party_quick_ref, effective_date))
        return propertyweb.HTMLPage(
            fixture_text("detail.html"),
            (
                f"{propertyweb.BASE_URL}/Property-Detail/"
                f"PropertyQuickRefID/{property_quick_ref}/"
                f"PartyQuickRefID/{party_quick_ref}"
            ),
        )

    def fetch_document(
        self,
        kind: str,
        *,
        parameters: dict[str, Any],
        maximum_bytes: int,
    ) -> propertyweb.PDFArtifact:
        content = b"%PDF-1.7\nfixture artifact\n%%EOF\n"
        return propertyweb.PDFArtifact(
            content=content,
            source_url=(f"{propertyweb.GENERATED_DOCUMENT_URL}/fixture-{kind}.pdf/"),
            media_type="application/pdf",
            generated_filename=f"fixture-{kind}.pdf",
            generator_url=propertyweb.DOCUMENT_GENERATORS.get(kind),
            generation_parameters=parameters,
            retrieval_mode="same_session_filename_generation_then_pdf",
        )


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        content: bytes,
        content_type: str,
        json_value: Any = None,
        status_code: int = 200,
    ) -> None:
        self.url = url
        self.content = content
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(content)),
        }
        self.encoding = "utf-8"
        self.status_code = status_code
        self.history: list[Any] = []
        self._json_value = json_value
        self.closed = False

    def json(self) -> Any:
        if self._json_value is None:
            return json.loads(self.content)
        return self._json_value

    def iter_content(self, chunk_size: int) -> Any:
        for index in range(0, len(self.content), chunk_size):
            yield self.content[index : index + chunk_size]

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


class NoWait:
    def wait(self) -> None:
        return None


def test_sources_describe_distinct_components_and_join_keys() -> None:
    payload = propertyweb.execute(
        parse_args("sources"),
        log_results=False,
    )

    assert payload["source"]["source_id"] == propertyweb.SOURCE_ID
    assert payload["observed_contract"]["search"]["native_page_size"] == 25
    assert (
        payload["observed_contract"]["documents"]["session_lineage"]
        == "filename generation and PDF fetch use one cookie session"
    )
    complements = {
        item.get("source_id") or item.get("kind"): item
        for item in payload["complements"]
    }
    assert "map_number" in complements[propertyweb.TAXLOT_WFS_SOURCE_ID]["join_keys"]
    assert "sale_instrument" in complements[propertyweb.RECORDER_SOURCE_ID]["join_keys"]


def test_home_contract_derives_tax_year_and_structural_fingerprint() -> None:
    contract = propertyweb.parse_home_contract(fixture_text("home.html"))

    assert contract.tax_year == 2026
    assert len(contract.source_html_sha256) == 64
    assert len(contract.schema_fingerprint) == 64

    with pytest.raises(SourceSchemaError, match="current tax year"):
        propertyweb.parse_home_contract(
            fixture_text("home.html").replace('value="2026"', 'value=""')
        )


def test_search_parser_and_normalizer_preserve_native_ids_and_values() -> None:
    page = propertyweb.parse_search_page(
        fixture_json("search_page_1.json"),
        source_url=f"{propertyweb.SEARCH_URL}?f=TEST&pn=1",
        requested_page=1,
    )
    record = propertyweb.normalize_search_record(
        page.raw_records[0],
        source_url=page.source_url,
        native_page=1,
        native_position=1,
        schema_fingerprint=page.schema_fingerprint,
    )

    assert page.record_count == 5
    assert page.has_more is True
    assert len(page.schema_fingerprint) == 64
    assert record["property_quick_ref"] == "R452940"
    assert record["party_quick_ref"] == "O0064958"
    assert record["map_number"] == "07-11-03-DC-05800-00"
    assert record["market_value"] == 1204130
    assert record["native_fields"]["PropertyValue"] == 415550.0
    assert record["detail_url"].endswith(
        "/PropertyQuickRefID/R452940/PartyQuickRefID/O0064958/"
    )
    assert record["canonical_ref"].startswith("PROPERTY:")
    assert (
        record["join_candidates"][propertyweb.TAXLOT_WFS_SOURCE_ID]["map_number"]
        == "07-11-03-DC-05800-00"
    )


def test_search_trims_selector_consistently_for_request_and_query_contract() -> None:
    client = FixtureClient()
    result = propertyweb.execute(
        parse_args("search", "  TEST  ", "--limit", "1"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert client.search_terms == ["TEST"]
    assert result.to_dict()["query"]["query"]["parameters"]["term"] == "TEST"


def test_search_cursor_is_query_bound_offset_aware_and_snapshot_guarded() -> None:
    client = FixtureClient()
    first = propertyweb.execute(
        parse_args("search", "TEST", "--limit", "2"),
        client=client,
        log_results=False,
    )
    first_payload = first.to_dict()

    assert first.status == ResultStatus.OK
    assert [row["property_quick_ref"] for row in first_payload["records"]] == [
        "R452940",
        "R452941",
    ]
    assert first.next_cursor is not None

    second = propertyweb.execute(
        parse_args(
            "search",
            "TEST",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert [row["property_quick_ref"] for row in second.to_dict()["records"]] == [
        "R452942",
        "R452943",
    ]
    assert client.search_calls == [1, 1, 2]

    mismatched = propertyweb.execute(
        parse_args(
            "search",
            "OTHER",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatched.status == ResultStatus.SOURCE_CHANGED
    assert mismatched.errors[0].code == "cursor_query_mismatch"

    changed_client = FixtureClient()
    changed_records = [dict(row) for row in changed_client.pages[1].raw_records]
    changed_records[0]["OwnerName"] = "CHANGED OWNER"
    changed_client.pages[1] = replace(
        changed_client.pages[1],
        raw_records=tuple(changed_records),
        snapshot_fingerprint=propertyweb.sha256_fingerprint(changed_records),
    )
    changed = propertyweb.execute(
        parse_args(
            "search",
            "TEST",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=changed_client,
        log_results=False,
    )
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_search_authoritative_empty_is_not_a_transport_failure() -> None:
    empty = propertyweb.parse_search_page(
        fixture_json("search_empty.json"),
        source_url=f"{propertyweb.SEARCH_URL}?f=NO-MATCH&pn=1",
        requested_page=1,
    )
    client = FixtureClient()
    client.pages = {1: empty}

    result = propertyweb.execute(
        parse_args("search", "NO-MATCH"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_invalid_cursor_returns_structured_source_mismatch() -> None:
    result = propertyweb.execute(
        parse_args(
            "search",
            "TEST",
            "--cursor",
            "another-adapter:v1:not-a-cursor",
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "cursor_source_mismatch"


def test_detail_parser_preserves_all_property_tax_and_join_components() -> None:
    source_url = (
        f"{propertyweb.BASE_URL}/Property-Detail/"
        "PropertyQuickRefID/R452940/PartyQuickRefID/O0064958"
    )
    detail = propertyweb.parse_detail_page(
        fixture_text("detail.html"),
        source_url,
        expected_property_quick_ref="R452940",
        expected_party_quick_ref="O0064958",
    )

    assert detail["native_ids"] == {
        "property_quick_ref": "R452940",
        "party_quick_ref": "O0064958",
        "property_id": "61623",
        "property_owner_id": "143319",
        "party_id": "208038",
    }
    assert detail["tax_year"] == 2026
    assert detail["effective_date"] == "2026-07-29"
    assert detail["owner_name"] == "EUGENE L & KAREN L SCRUTTON LLC"
    assert detail["mailing_address_lines"] == [
        "3264 NW JETTY AVE",
        "LINCOLN CITY, OR 97367",
    ]
    assert detail["map_number"] == "07-11-03-DC-05800-00"
    assert (
        detail["join_candidates"][propertyweb.TAXLOT_WFS_SOURCE_ID]["map_number"]
        == "07-11-03-DC-05800-00"
    )
    assert detail["legal_description"].startswith("WECOMA BEACH")
    assert detail["taxing_districts"][1]["code"] == "614"
    assert detail["related_properties"][0]["property_quick_ref"] == "R111111"
    assert detail["exemptions"][0]["records"][0]["type"] == "VETERANS"

    improvement = detail["improvements"][0]
    assert improvement["improvement_type"] == "R: RESIDENTIAL"
    assert improvement["bedrooms"] == 3
    assert improvement["segments"][0]["year_built"] == 1940
    assert improvement["segments"][0]["details"]["eff_yr_built"] == "2000"
    assert detail["land_segments"][0]["land_size_value"] == 0.11

    assert detail["value_history"][0]["value_state"] == "in_process"
    assert detail["value_history"][0]["real_market_value"] == 1204130
    sale = detail["sales_history"][0]
    assert sale["instrument_number"] == "202501695"
    assert sale["recorder_join_candidate"]["instrument_number"] == "2025-001695"

    assert detail["bills"][0]["tax_year"] == 2025
    assert detail["bills"][0]["installments"][0]["total_billed"] == 2260.89
    assert detail["tax_due_summary"]["total_due"] == 0
    assert detail["payment_history"][0]["transaction_id"] == "1496170"
    assert detail["payment_history"][1]["tax_year_label"] == "2000"

    documents = detail["document_representations"]
    kinds = {item["document_kind"] for item in documents}
    assert {
        "property_detail_html",
        "taxlot_map",
        "appraisal_card",
        "account_summary",
        "tax_statement",
        "payment_receipt",
    }.issubset(kinds)
    historical = next(
        item
        for item in documents
        if item["document_kind"] == "tax_statement" and item["tax_year"] == 2021
    )
    assert historical["retrieval_mode"] == "direct_historical_pdf"
    assert len(detail["source_html_sha256"]) == 64
    assert len(detail["response_schema_fingerprint"]) == 64


def test_document_client_uses_one_session_and_validates_pdf() -> None:
    filenames = fixture_json("generator_filenames.json")
    pdf = b"%PDF-1.7\nsame-session fixture\n%%EOF\n"
    session = FakeSession(
        [
            FakeResponse(
                url=propertyweb.HOME_URL,
                content=fixture_text("home.html").encode(),
                content_type="text/html; charset=utf-8",
            ),
            FakeResponse(
                url=propertyweb.DOCUMENT_GENERATORS["appraisal-card"],
                content=json.dumps(filenames["appraisal-card"]).encode(),
                content_type="application/json",
                json_value=filenames["appraisal-card"],
            ),
            FakeResponse(
                url=(
                    f"{propertyweb.GENERATED_DOCUMENT_URL}/"
                    f"{filenames['appraisal-card']}/"
                ),
                content=pdf,
                content_type="application/pdf",
            ),
        ]
    )
    client = propertyweb.PropertyWebClient(
        session=session,
        rate_limiter=NoWait(),
    )

    artifact = client.fetch_document(
        "appraisal-card",
        parameters={
            "PropertyID": "61623",
            "TaxYear": "2026",
            "ReportFormatID": "502405",
        },
        maximum_bytes=100_000,
    )

    assert artifact.content == pdf
    assert artifact.generated_filename == filenames["appraisal-card"]
    assert artifact.retrieval_mode == ("same_session_filename_generation_then_pdf")
    assert [call["method"] for call in session.calls] == ["GET", "POST", "GET"]
    assert session.calls[1]["data"]["PropertyID"] == "61623"
    assert session.calls[2]["stream"] is True


def test_document_client_rejects_non_pdf_and_honors_byte_bound() -> None:
    filename = "AppraisalCard-61623-2026-502405.pdf"
    session = FakeSession(
        [
            FakeResponse(
                url=propertyweb.HOME_URL,
                content=fixture_text("home.html").encode(),
                content_type="text/html",
            ),
            FakeResponse(
                url=propertyweb.DOCUMENT_GENERATORS["appraisal-card"],
                content=json.dumps(filename).encode(),
                content_type="application/json",
                json_value=filename,
            ),
            FakeResponse(
                url=f"{propertyweb.GENERATED_DOCUMENT_URL}/{filename}/",
                content=b"<html>not a PDF</html>",
                content_type="text/html",
            ),
        ]
    )
    client = propertyweb.PropertyWebClient(
        session=session,
        rate_limiter=NoWait(),
    )

    with pytest.raises(SourceSchemaError, match="not a PDF"):
        client.fetch_document(
            "appraisal-card",
            parameters={
                "PropertyID": "61623",
                "TaxYear": "2026",
                "ReportFormatID": "502405",
            },
            maximum_bytes=100_000,
        )


def test_document_command_hashes_and_optionally_saves_artifact(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "receipt.pdf"
    args = parse_args(
        "document",
        "receipt",
        "R452940",
        "1496170",
        "--destination",
        str(destination),
    )
    result = propertyweb.execute(
        args,
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]
    content = destination.read_bytes()

    assert result.status == ResultStatus.OK
    assert content.startswith(b"%PDF-")
    assert record["local_path"] == str(destination)
    assert record["sha256"] == hashlib.sha256(content).hexdigest()
    assert record["generation_parameters"] == {
        "QuickRefID": "R452940",
        "TransactionID": "1496170",
    }


def test_explicit_output_writes_json_result(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "sources.json"
    args = parse_args("sources", "--output", str(output))
    value = propertyweb.execute(args, log_results=False)
    propertyweb._emit(value, args)

    assert json.loads(output.read_text())["source"]["source_id"] == (
        propertyweb.SOURCE_ID
    )
    assert "saved to" in capsys.readouterr().out


@pytest.mark.live_data
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_PROPERTYWEB") != "1",
    reason=("set RUN_LIVE_OR_LINCOLN_PROPERTYWEB=1 for official PropertyWeb probes"),
)
def test_live_search_and_detail_contract() -> None:
    client = propertyweb.PropertyWebClient()
    try:
        home = client.home_contract()
        page = client.search_page(
            term=propertyweb.PROBE_PROPERTY_QUICK_REF,
            tax_year=home.tax_year,
            property_value_tax_year=home.tax_year,
            page=1,
            sort_type=propertyweb.SORT_TYPES["property_id"],
            sort_order=propertyweb.SORT_ORDERS["asc"],
            property_types=propertyweb.DEFAULT_PROPERTY_TYPES,
        )
        assert any(
            raw["PropertyQuickRefID"] == propertyweb.PROBE_PROPERTY_QUICK_REF
            for raw in page.raw_records
        )
        html = client.detail(
            propertyweb.PROBE_PROPERTY_QUICK_REF,
            propertyweb.PROBE_PARTY_QUICK_REF,
        )
        detail = propertyweb.parse_detail_page(
            html.html,
            html.source_url,
            expected_property_quick_ref=propertyweb.PROBE_PROPERTY_QUICK_REF,
            expected_party_quick_ref=propertyweb.PROBE_PARTY_QUICK_REF,
        )
        assert detail["property_id"] == propertyweb.PROBE_PROPERTY_ID
        assert detail["map_number"] == "07-11-03-DC-05800-00"
        assert detail["value_history"]
        assert detail["sales_history"]
        assert detail["payment_history"]
    finally:
        client.close()


@pytest.mark.live_data
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_LINCOLN_PROPERTYWEB") != "1",
    reason=("set RUN_LIVE_OR_LINCOLN_PROPERTYWEB=1 for official PropertyWeb probes"),
)
def test_live_all_published_pdf_representations() -> None:
    client = propertyweb.PropertyWebClient()
    try:
        page = client.detail(
            propertyweb.PROBE_PROPERTY_QUICK_REF,
            propertyweb.PROBE_PARTY_QUICK_REF,
        )
        detail = propertyweb.parse_detail_page(
            page.html,
            page.source_url,
            expected_property_quick_ref=propertyweb.PROBE_PROPERTY_QUICK_REF,
            expected_party_quick_ref=propertyweb.PROBE_PARTY_QUICK_REF,
        )
        representations = detail["document_representations"]
        generated_kinds = {
            "appraisal_card": "appraisal-card",
            "account_summary": "account-summary",
            "tax_statement": "tax-statement",
            "payment_receipt": "receipt",
        }
        for document_kind, fetch_kind in generated_kinds.items():
            representation = next(
                item
                for item in representations
                if item["document_kind"] == document_kind
                and item["retrieval_mode"]
                == "same_session_filename_generation_then_pdf"
            )
            artifact = client.fetch_document(
                fetch_kind,
                parameters=representation["generation_parameters"],
                maximum_bytes=propertyweb.DEFAULT_MAX_DOCUMENT_BYTES,
            )
            assert artifact.content.startswith(b"%PDF-")
            assert artifact.generated_filename
            assert artifact.retrieval_mode == (
                "same_session_filename_generation_then_pdf"
            )
            assert len(hashlib.sha256(artifact.content).hexdigest()) == 64

        historical = next(
            item
            for item in representations
            if item["document_kind"] == "tax_statement"
            and item["retrieval_mode"] == "direct_historical_pdf"
        )
        artifact = client.fetch_document(
            "historical-tax-statement",
            parameters=historical["generation_parameters"],
            maximum_bytes=propertyweb.DEFAULT_MAX_DOCUMENT_BYTES,
        )
        assert artifact.content.startswith(b"%PDF-")
        assert artifact.generated_filename is None
        assert artifact.retrieval_mode == "direct_historical_pdf"
        assert len(hashlib.sha256(artifact.content).hexdigest()) == 64
    finally:
        client.close()
