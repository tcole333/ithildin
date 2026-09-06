from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_deschutes_laserfiche as weblink
from tools.public_records_contract import ResultStatus
from tools.public_records_http import (
    MinimumIntervalRateLimiter,
    RetryPolicy,
    SourceResponseError,
    SourceSchemaError,
)


FIXTURE_DIR = Path("tests/fixtures/public_records/deschutes_laserfiche")


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def json_fixture(name: str) -> Mapping[str, Any]:
    return json.loads(fixture(name))


def parse_args(*values: str):
    return weblink.build_parser().parse_args(list(values))


class FakeResponse:
    def __init__(
        self,
        url: str,
        body: bytes | str,
        *,
        status_code: int = 200,
        content_type: str = "application/json; charset=utf-8",
        headers: Mapping[str, str] | None = None,
        history: tuple[Any, ...] = (),
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.content = body.encode() if isinstance(body, str) else body
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(self.content)),
            **dict(headers or {}),
        }
        self.history = history
        self.closed = False

    def iter_content(self, chunk_size: int = 64 * 1024):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]

    def close(self) -> None:
        self.closed = True


class QueueSession:
    def __init__(self, expected: list[tuple[str, str, FakeResponse]]) -> None:
        self.expected = list(expected)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        assert self.expected, f"unexpected request {method} {url}"
        expected_method, expected_url, response = self.expected.pop(0)
        assert (method, url) == (expected_method, expected_url)
        self.calls.append({"method": method, "url": url, **kwargs})
        return response

    def close(self) -> None:
        self.closed = True


def account_page() -> weblink.AccountDocumentPage:
    return weblink.parse_account_documents_page(
        fixture("account_documents.html"),
        f"{weblink.DIAL_BASE_URL}/Real/DevelopmentDocs/135278",
        expected_account_id="135278",
    )


def viewer_contract(document_id: str = "1383062") -> weblink.ViewerContract:
    return weblink.parse_viewer_contract(
        fixture("viewer.html"),
        f"{weblink.VIEWER_URL}?id={document_id}",
    )


def electronic_document() -> dict[str, Any]:
    return weblink.parse_document_info(
        json_fixture("document_info_electronic.json"),
        weblink.DOCUMENT_INFO_URL,
        expected_document_id="1383062",
        viewer_contract=viewer_contract(),
    )


def imaged_document() -> dict[str, Any]:
    return weblink.parse_document_info(
        json_fixture("document_info_imaged.json"),
        weblink.DOCUMENT_INFO_URL,
        expected_document_id="333623",
        viewer_contract=viewer_contract("333623"),
    )


class StaticClient:
    def __init__(
        self,
        *,
        page: weblink.AccountDocumentPage | None = None,
        artifact: weblink.BinaryArtifact | None = None,
    ) -> None:
        self.page = page or account_page()
        self.documents = {
            "1383062": electronic_document(),
            "333623": imaged_document(),
            "1298977": {
                **electronic_document(),
                "native_document_id": "1298977",
                "laserfiche_entry_id": "1298977",
                "source_url": f"{weblink.VIEWER_URL}?id=1298977",
                "map_taxlot": weblink.PROBE_TAXLOT,
            },
        }
        self.folder = weblink.parse_folder_metadata(
            json_fixture("folder_metadata.json"),
            weblink.FOLDER_METADATA_URL,
            folder_id="1378494",
        )
        self.artifact = artifact or weblink.BinaryArtifact(
            content=b"%PDF-1.4\nfixture\n%%EOF\n",
            source_url=(
                f"{weblink.BASE_URL}ElectronicFile.aspx?"
                "docid=1383062&dbid=0&repo=LFCDD"
            ),
            media_type="application/pdf",
            filename="fixture.pdf",
            retrieval_mode="electronic_file",
            generation_token=None,
            etag='"fixture"',
            last_modified=None,
        )
        self.hydrated: list[str] = []

    def account_page(self, account_id: str) -> weblink.AccountDocumentPage:
        assert account_id == "135278"
        return self.page

    def document_info(self, document_id: str) -> dict[str, Any]:
        self.hydrated.append(document_id)
        return dict(self.documents[document_id])

    def folder_metadata(self, folder_id: str) -> dict[str, Any]:
        assert folder_id in {"1378494", "333580"}
        return dict(self.folder)

    def download_document(self, document: Mapping[str, Any], **_: Any):
        assert document["laserfiche_entry_id"] in {"1383062", "333623"}
        if document["laserfiche_entry_id"] == "333623":
            return replace(
                self.artifact,
                retrieval_mode="generated_pdf_from_imaged_pages",
                generation_token="11111111-2222-3333-4444-555555555555",
            )
        return self.artifact

    def close(self) -> None:
        pass


def test_client_default_rate_limiter_uses_injected_sleeper() -> None:
    delays: list[float] = []
    client = weblink.DeschutesWebLinkClient(
        session=QueueSession([]),
        sleeper=delays.append,
    )

    client.rate_limiter.wait()
    client.rate_limiter.wait()

    assert len(delays) == 1
    assert 0 < delays[0] <= weblink.DEFAULT_MINIMUM_INTERVAL


def test_sources_describe_identity_access_and_complements() -> None:
    payload = weblink.execute(parse_args("sources"), log_results=False)

    assert payload["source"]["source_id"] == "us-or-deschutes-cdd-weblink"
    assert payload["identity_model"]["document_identity"] == (
        "laserfiche_entry_id"
    )
    assert payload["identity_model"]["property_join_identifiers"] == [
        "deschutes_dial_account_id",
        "map_taxlot",
    ]
    viewer = payload["observed_contract"]["viewer"]["public_capabilities_observed"]
    assert viewer["document_export"] is True
    assert viewer["repository_search"] is False
    complements = {item.get("source_id"): item for item in payload["complements"]}
    assert complements[weblink.DIAL_SOURCE_ID]["join_keys"] == [
        "deschutes_dial_account_id",
        "map_taxlot",
    ]
    assert any(
        item.get("kind") == weblink.OREGON_EPERMITTING_COMPLEMENT_KEY
        for item in payload["complements"]
    )
    assert any(
        item.get("kind") == "official_public_records_request"
        for item in payload["complements"]
    )


def test_account_page_preserves_property_joins_and_laserfiche_identity() -> None:
    page = account_page()

    assert page.account_id == "135278"
    assert page.map_taxlot == "141031B000700"
    assert page.mailing_name == "VACH, MARIE FLORENCE"
    assert [record["laserfiche_entry_id"] for record in page.records] == [
        "1383062",
        "1298977",
        "333623",
    ]
    first = page.records[0]
    assert first["deschutes_dial_account_id"] == "135278"
    assert first["native_document_id"] == "1383062"
    assert first["document_identifiers"] == {
        "laserfiche_entry_id": "1383062"
    }
    assert first["property_identifiers"] == {
        "deschutes_dial_account_id": "135278",
        "map_taxlot": "141031B000700",
    }
    assert first["canonical_ref"].endswith("/document/1383062")
    assert first["date_uploaded"] == "2025-11-24"
    assert page.schema_fingerprint
    assert page.snapshot_fingerprint


def test_account_parser_aggregates_duplicate_document_occurrences() -> None:
    html = fixture("account_documents.html").replace(
        "DocView.aspx?id=1298977",
        "DocView.aspx?id=1383062",
    )
    page = weblink.parse_account_documents_page(
        html,
        f"{weblink.DIAL_BASE_URL}/Real/DevelopmentDocs/135278",
    )

    assert len(page.records) == 2
    assert len(page.records[0]["dial_index_occurrences"]) == 2


def test_account_parser_rejects_wrong_account_and_changed_viewer_route() -> None:
    with pytest.raises(SourceSchemaError, match="different property account"):
        weblink.parse_account_documents_page(
            fixture("account_documents.html"),
            f"{weblink.DIAL_BASE_URL}/Real/DevelopmentDocs/999999",
            expected_account_id="999999",
        )

    changed = fixture("account_documents.html").replace(
        "weblink.deschutes.org/cdd/DocView.aspx",
        "example.com/cdd/DocView.aspx",
        1,
    )
    with pytest.raises(
        weblink.WebLinkSelectionError,
        match="verified official hosts",
    ):
        weblink.parse_account_documents_page(
            changed,
            f"{weblink.DIAL_BASE_URL}/Real/DevelopmentDocs/135278",
        )


def test_viewer_contract_records_public_capabilities() -> None:
    contract = viewer_contract()

    assert contract.repository_name == "LFCDD"
    assert contract.virtual_directory == "CDD"
    assert contract.has_export_rights is True
    assert contract.has_search_rights is False
    assert contract.show_browse_link is False
    assert contract.schema_fingerprint


def test_viewer_contract_detects_failed_cookie_handshake() -> None:
    with pytest.raises(SourceSchemaError, match="cookie handshake"):
        weblink.parse_viewer_contract(
            fixture("cookie_error.html"),
            f"{weblink.VIEWER_URL}?id=1383062",
        )


def test_electronic_document_metadata_is_normalized() -> None:
    record = electronic_document()

    assert record["laserfiche_entry_id"] == "1383062"
    assert record["parent_folder_id"] == "1378494"
    assert record["map_taxlot"] == "141031B000700"
    assert record["case_number"] == "247-16-000505-SEP"
    assert record["accela_document_id"] == "A01000014439641C6ELNSAX78JACGN"
    assert record["created_at"] == "2025-11-24T17:11:14-08:00"
    assert record["retrieval_mode"] == "electronic_file"
    assert record["electronic_file_url"].endswith(
        "ElectronicFile.aspx?docid=1383062&dbid=0&repo=LFCDD"
    )
    assert record["viewer_contract"]["repository_name"] == "LFCDD"
    assert record["source_data_fingerprint"]


def test_imaged_document_metadata_selects_pdf_generation() -> None:
    record = imaged_document()

    assert record["laserfiche_entry_id"] == "333623"
    assert record["page_count"] == 5
    assert record["has_imaged_pages"] is True
    assert record["extension"] is None
    assert record["barcode"] == "141031B000700BU20070419065355"
    assert record["retrieval_mode"] == "generated_pdf_from_imaged_pages"
    assert record["electronic_file_url"] is None
    assert record["generated_pdf_route"].endswith(
        "PDF10/{generation_token}/333623"
    )


def test_document_parser_rejects_identity_mismatch() -> None:
    with pytest.raises(SourceSchemaError, match="different document entry"):
        weblink.parse_document_info(
            json_fixture("document_info_electronic.json"),
            weblink.DOCUMENT_INFO_URL,
            expected_document_id="999999",
        )


def test_folder_metadata_preserves_source_native_folder_id_and_path() -> None:
    record = weblink.parse_folder_metadata(
        json_fixture("folder_metadata.json"),
        weblink.FOLDER_METADATA_URL,
        folder_id="1378494",
    )

    assert record["laserfiche_folder_id"] == "1378494"
    assert record["folder_name"] == "2025-11"
    assert record["laserfiche_path"] == "\\Property Files\\Finalized\\2025-11"
    assert record["canonical_ref"].endswith("/folder/1378494")
    assert record["modified_at"].endswith("-07:00")


def test_account_continuation_is_typed_query_and_snapshot_bound() -> None:
    client = StaticClient()
    first = weblink.execute(
        parse_args("account", "135278", "--limit", "2"),
        client=client,
        log_results=False,
    )

    assert first.status == ResultStatus.OK
    assert [record["laserfiche_entry_id"] for record in first.records] == [
        "1383062",
        "1298977",
    ]
    assert first.next_cursor.startswith(weblink.CURSOR_PREFIX)

    second = weblink.execute(
        parse_args(
            "account",
            "135278",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert [record["laserfiche_entry_id"] for record in second.records] == [
        "333623"
    ]
    assert second.next_cursor is None


def test_account_continuation_rejects_query_and_snapshot_changes() -> None:
    first = weblink.execute(
        parse_args("account", "135278", "--limit", "1"),
        client=StaticClient(),
        log_results=False,
    )
    assert first.next_cursor

    mismatch = weblink.execute(
        parse_args(
            "account",
            "135278",
            "--limit",
            "1",
            "--hydrate",
            "--cursor",
            first.next_cursor,
        ),
        client=StaticClient(),
        log_results=False,
    )
    assert mismatch.status == ResultStatus.SOURCE_CHANGED
    assert mismatch.errors[0].code == "cursor_query_mismatch"

    changed_page = replace(account_page(), snapshot_fingerprint="changed")
    changed = weblink.execute(
        parse_args(
            "account",
            "135278",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=StaticClient(page=changed_page),
        log_results=False,
    )
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_account_hydration_is_limited_to_returned_slice() -> None:
    client = StaticClient()
    result = weblink.execute(
        parse_args("account", "135278", "--limit", "1", "--hydrate"),
        client=client,
        log_results=False,
    )

    assert client.hydrated == ["1383062"]
    assert result.records[0]["weblink_metadata"]["laserfiche_entry_id"] == (
        "1383062"
    )


def test_document_operation_verifies_dial_account_link() -> None:
    result = weblink.execute(
        parse_args(
            "document",
            "1383062",
            "--account",
            "135278",
            "--taxlot",
            "141031B000700",
        ),
        client=StaticClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["verified_property_link"]["verification"] == (
        "dial_account_document_index"
    )
    assert record["property_identifiers"]["deschutes_dial_account_id"] == (
        "135278"
    )
    assert record["native_document_id"] == "1383062"


def test_document_operation_returns_no_results_for_wrong_taxlot() -> None:
    result = weblink.execute(
        parse_args("document", "1383062", "--taxlot", "999999"),
        client=StaticClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()


def test_folder_operation_returns_public_record_envelope() -> None:
    result = weblink.execute(
        parse_args("folder", "1378494"),
        client=StaticClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.query.query.operation == "folder"
    assert result.records[0]["laserfiche_folder_id"] == "1378494"


def test_download_operation_writes_atomic_artifact_and_receipt(tmp_path: Path) -> None:
    destination = tmp_path / "document.pdf"
    result = weblink.execute(
        parse_args(
            "download",
            "1383062",
            "--account",
            "135278",
            "--destination",
            str(destination),
        ),
        client=StaticClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes().startswith(b"%PDF-")
    record = result.records[0]
    assert record["retrieval_mode"] == "electronic_file"
    assert record["size_bytes"] == destination.stat().st_size
    assert record["sha256"]
    assert result.raw_artifact_refs == (str(destination.resolve()),)


def test_client_downloads_electronic_file_with_bounded_stream() -> None:
    source_url = (
        f"{weblink.BASE_URL}ElectronicFile.aspx?"
        "docid=1383062&dbid=0&repo=LFCDD"
    )
    pdf = b"%PDF-1.4\nfixture\n%%EOF\n"
    response = FakeResponse(
        source_url,
        pdf,
        content_type="application/pdf",
        headers={
            "Content-Disposition": (
                "inline; filename*=UTF-8''A01000014439641C6ELNSAX78JACGN.pdf"
            ),
            "ETag": '"1383157"',
        },
    )
    session = QueueSession([("GET", source_url, response)])
    client = weblink.DeschutesWebLinkClient(
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=MinimumIntervalRateLimiter(0),
    )

    artifact = client.download_document(
        electronic_document(),
        maximum_bytes=1024,
        poll_attempts=1,
        poll_interval=0,
    )

    assert artifact.content == pdf
    assert artifact.filename == "A01000014439641C6ELNSAX78JACGN.pdf"
    assert artifact.etag == '"1383157"'
    assert response.closed is True
    assert session.expected == []


def test_artifact_validation_detects_html_and_pdf_mismatch_without_mime_help() -> None:
    client = weblink.DeschutesWebLinkClient(
        session=QueueSession([]),
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=MinimumIntervalRateLimiter(0),
    )
    source_url = (
        f"{weblink.BASE_URL}ElectronicFile.aspx?"
        "docid=1383062&dbid=0&repo=LFCDD"
    )

    with pytest.raises(SourceSchemaError, match="non-document page"):
        client._read_artifact(
            FakeResponse(
                source_url,
                "<html><body>session error</body></html>",
                content_type="application/octet-stream",
            ),
            request_url=source_url,
            maximum_bytes=1024,
            retrieval_mode="electronic_file",
            expected_extension="pdf",
        )

    with pytest.raises(SourceSchemaError, match="invalid bytes"):
        client._read_artifact(
            FakeResponse(
                source_url,
                b"not a pdf",
                content_type="application/octet-stream",
            ),
            request_url=source_url,
            maximum_bytes=1024,
            retrieval_mode="electronic_file",
            expected_extension="pdf",
        )


def test_client_generates_pdf_for_imaged_document() -> None:
    token = "11111111-2222-3333-4444-555555555555"
    generated_url = f"{weblink.BASE_URL}PDF10/{token}/333623"
    pdf = b"%PDF-1.6\nfive page fixture\n%%EOF\n"
    session = QueueSession(
        [
            (
                "POST",
                weblink.GENERATE_PDF_URL,
                FakeResponse(
                    weblink.GENERATE_PDF_URL,
                    f"{token}\r\n<html></html>",
                    content_type="text/plain; charset=utf-8",
                ),
            ),
            (
                "POST",
                weblink.PDF_PROGRESS_URL,
                FakeResponse(
                    weblink.PDF_PROGRESS_URL,
                    json.dumps(
                        {
                            "data": {
                                "errMsg": None,
                                "success": True,
                                "finished": True,
                                "completion": 0,
                            }
                        }
                    ),
                ),
            ),
            (
                "GET",
                generated_url,
                FakeResponse(
                    generated_url,
                    pdf,
                    content_type="application/pdf",
                    headers={
                        "Content-Disposition": (
                            'inline; filename="141031B000700BU20070419065355.pdf"'
                        )
                    },
                ),
            ),
        ]
    )
    client = weblink.DeschutesWebLinkClient(
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=MinimumIntervalRateLimiter(0),
    )

    artifact = client.download_document(
        imaged_document(),
        maximum_bytes=1024,
        poll_attempts=2,
        poll_interval=0,
    )

    assert artifact.content == pdf
    assert artifact.retrieval_mode == "generated_pdf_from_imaged_pages"
    assert artifact.generation_token == token
    assert artifact.filename == "141031B000700BU20070419065355.pdf"
    assert session.calls[0]["params"]["PageRange"] == "1 - 5"
    assert session.calls[1]["json"] == {"Key": token}
    assert session.expected == []


def test_generated_pdf_polling_is_bounded() -> None:
    token = "11111111-2222-3333-4444-555555555555"
    pending = json.dumps(
        {
            "data": {
                "errMsg": None,
                "success": False,
                "finished": False,
                "completion": 25,
            }
        }
    )
    session = QueueSession(
        [
            (
                "POST",
                weblink.GENERATE_PDF_URL,
                FakeResponse(
                    weblink.GENERATE_PDF_URL,
                    token,
                    content_type="text/plain",
                ),
            ),
            (
                "POST",
                weblink.PDF_PROGRESS_URL,
                FakeResponse(weblink.PDF_PROGRESS_URL, pending),
            ),
            (
                "POST",
                weblink.PDF_PROGRESS_URL,
                FakeResponse(weblink.PDF_PROGRESS_URL, pending),
            ),
        ]
    )
    client = weblink.DeschutesWebLinkClient(
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=MinimumIntervalRateLimiter(0),
        sleeper=lambda _: None,
    )

    with pytest.raises(
        weblink.TransportError,
        match="did not finish within the poll bound",
    ):
        client.download_document(
            imaged_document(),
            maximum_bytes=1024,
            poll_attempts=2,
            poll_interval=0,
        )


def test_response_bound_rejects_declared_and_streamed_overflow() -> None:
    declared = FakeResponse(
        weblink.DOCUMENT_INFO_URL,
        b"small",
        headers={"Content-Length": "1000"},
    )
    with pytest.raises(SourceResponseError, match="requested byte bound"):
        weblink._bounded_response(
            declared,
            maximum_bytes=10,
            request_url=weblink.DOCUMENT_INFO_URL,
        )
    assert declared.closed is True

    streamed = FakeResponse(
        weblink.DOCUMENT_INFO_URL,
        b"x" * 20,
        headers={"Content-Length": "not-a-number"},
    )
    with pytest.raises(SourceResponseError, match="exceeded"):
        weblink._bounded_response(
            streamed,
            maximum_bytes=10,
            request_url=weblink.DOCUMENT_INFO_URL,
        )
    assert streamed.closed is True


def test_probe_represents_both_storage_modes_offline() -> None:
    result = weblink.execute(
        parse_args("probe", "--with-download"),
        client=StaticClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["electronic_document"]["retrieval_mode"] == "electronic_file"
    assert record["imaged_document"]["retrieval_mode"] == (
        "generated_pdf_from_imaged_pages"
    )
    assert {item["retrieval_mode"] for item in record["downloads"]} == {
        "electronic_file",
        "generated_pdf_from_imaged_pages",
    }


def test_cli_parser_exposes_account_metadata_folder_download_and_probe() -> None:
    assert parse_args("account", "135278").command == "account"
    assert parse_args("document", "1383062").command == "document"
    assert parse_args("folder", "1378494").command == "folder"
    download = parse_args(
        "download",
        "333623",
        "--destination",
        "/tmp/deschutes-333623.pdf",
    )
    assert download.max_bytes == weblink.DEFAULT_MAX_DOCUMENT_BYTES
    assert parse_args("probe").with_download is False


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DESCHUTES_WEBLINK") != "1",
    reason="set RUN_LIVE_DESCHUTES_WEBLINK=1 for official live probes",
)
def test_live_account_discovery_has_verified_sentinels() -> None:
    client = weblink.DeschutesWebLinkClient(timeout=60)
    try:
        page = client.account_page(weblink.PROBE_ACCOUNT_ID)
    finally:
        client.close()

    ids = {record["laserfiche_entry_id"] for record in page.records}
    assert page.account_id == weblink.PROBE_ACCOUNT_ID
    assert page.map_taxlot == weblink.PROBE_TAXLOT
    assert len(ids) >= 2
    assert weblink.PROBE_ELECTRONIC_DOCUMENT_ID in ids
    assert weblink.PROBE_IMAGED_DOCUMENT_ID in ids


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DESCHUTES_WEBLINK") != "1",
    reason="set RUN_LIVE_DESCHUTES_WEBLINK=1 for official live probes",
)
def test_live_document_and_folder_metadata_cover_both_storage_modes() -> None:
    client = weblink.DeschutesWebLinkClient(timeout=60)
    try:
        folder = client.folder_metadata(weblink.PROBE_PARENT_FOLDER_ID)
        electronic = client.document_info(weblink.PROBE_ELECTRONIC_DOCUMENT_ID)
        imaged = client.document_info(weblink.PROBE_IMAGED_DOCUMENT_ID)
    finally:
        client.close()

    assert electronic["map_taxlot"] == weblink.PROBE_TAXLOT
    assert electronic["retrieval_mode"] == "electronic_file"
    assert imaged["map_taxlot"] == weblink.PROBE_TAXLOT
    assert imaged["page_count"] == 5
    assert imaged["retrieval_mode"] == "generated_pdf_from_imaged_pages"
    assert folder["laserfiche_path"].endswith("2025-11")


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DESCHUTES_WEBLINK") != "1",
    reason="set RUN_LIVE_DESCHUTES_WEBLINK=1 for official live probes",
)
def test_live_downloads_validate_electronic_and_generated_pdfs() -> None:
    client = weblink.DeschutesWebLinkClient(timeout=60)
    try:
        documents = [
            client.document_info(weblink.PROBE_ELECTRONIC_DOCUMENT_ID),
            client.document_info(weblink.PROBE_IMAGED_DOCUMENT_ID),
        ]
        artifacts = [
            client.download_document(
                document,
                maximum_bytes=20 * 1024 * 1024,
                poll_attempts=60,
                poll_interval=0.5,
            )
            for document in documents
        ]
    finally:
        client.close()

    assert all(artifact.content.startswith(b"%PDF-") for artifact in artifacts)
    assert {artifact.retrieval_mode for artifact in artifacts} == {
        "electronic_file",
        "generated_pdf_from_imaged_pages",
    }
