from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_delaware_opinions


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "delaware_opinions"
)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _complete_first_page() -> str:
    rows = "".join(
        (
            "<tr>"
            f"<td><a href='/opinions/download.aspx?id={398000 + index}'>"
            f"Fixture Opinion {index}</a></td>"
            "<td><span>06/20/2026</span></td>"
            f"<td><span>FIX-{index:02d}</span></td>"
            "<td><span>Superior Court</span></td>"
            "<td><span>Civil</span></td>"
            "<td><span>Fixture J.</span></td>"
            "<td><span>Order</span></td>"
            "</tr>"
        )
        for index in range(1, 24)
    )
    return _fixture("index_page_1.html").replace(
        "</tbody>",
        f"{rows}</tbody>",
        1,
    )


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes | None = None
    url: str | None = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = self.text.encode()


class QueueSession:
    def __init__(self, responses: list[FixtureResponse]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method,
        url,
        *,
        params=None,
        headers=None,
        timeout=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected Delaware Opinions request")
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def _parse(*values: str):
    return query_delaware_opinions.build_parser().parse_args(list(values))


def _client(*responses: FixtureResponse):
    session = QueueSession(list(responses))
    return (
        query_delaware_opinions.DelawareOpinionsClient(
            session=session,
            minimum_interval=0,
        ),
        session,
    )


def test_index_parser_normalizes_official_metadata_and_evidence_scope():
    page = query_delaware_opinions.parse_index_page(
        _fixture("index_page_1.html"),
        source_url=query_delaware_opinions.INDEX_URL,
        expected_page=1,
    )

    assert page.source_total == 26
    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.page_size == 25
    assert len(page.records) == 2
    record = page.records[0]
    assert record["canonical_ref"] == "DEOPINION:398840"
    assert record["document_date"] == "2026-07-28"
    assert record["raw_case_number"] == "4373-LM"
    assert record["court"]["court_id"] == "de-court-of-chancery"
    assert record["judicial_officer"] == "Mitchell M."
    assert record["judicial_officer_name"] == "Mitchell M."
    assert record["judicial_officer_title"] is None
    assert record["publication_kind"] == "decision"
    assert record["documents"][0]["source_url"].endswith("id=398840")
    assert record["source_scope"]["courtconnect_docket_metadata"] is False
    assert record["source_scope"]["clerk_certified_record"] is False


def test_no_results_is_authoritative_and_preserves_native_page_size():
    page = query_delaware_opinions.parse_index_page(
        _fixture("no_results.html")
    )

    assert page.records == ()
    assert page.source_total == 0
    assert page.total_pages == 0
    assert page.page_size == 100
    assert page.authoritative_empty is True


def test_source_filter_error_is_not_misreported_as_no_results():
    with pytest.raises(
        query_delaware_opinions.DelawareOpinionsSelectionError
    ) as caught:
        query_delaware_opinions.parse_index_page(
            _fixture("filter_error.html")
        )

    assert caught.value.code == "source_rejected_filters"
    assert "To date" in str(caught.value)


def test_missing_result_header_is_explicit_source_drift():
    with pytest.raises(
        query_delaware_opinions.DelawareOpinionsSourceChangedError
    ) as caught:
        query_delaware_opinions.parse_index_page(
            _fixture("source_drift.html")
        )

    assert caught.value.code == "index_table_missing"
    assert caught.value.status.value == "source_changed"


def test_options_parser_exposes_source_native_values():
    options = query_delaware_opinions.parse_options_page(
        _fixture("options.html")
    )

    assert {row["option_group"] for row in options} == {
        "court",
        "revision_period",
        "year",
        "page_size",
    }
    assert any(
        row["option_group"] == "court"
        and row["native_value"] == "Court of Chancery"
        for row in options
    )
    assert any(
        row["option_group"] == "revision_period"
        and row["native_value"] == "date"
        for row in options
    )


def test_client_follows_every_native_page_without_an_adapter_cap():
    client, session = _client(
        FixtureResponse(
            _complete_first_page(),
            url=f"{query_delaware_opinions.INDEX_URL}?page=1",
        ),
        FixtureResponse(
            _fixture("index_page_2.html"),
            url=f"{query_delaware_opinions.INDEX_URL}?page=2",
        ),
    )

    fetched = client.search(
        "Intel",
        period="year",
        year="2026",
        page_size=25,
    )

    assert len(fetched.records) == 26
    assert fetched.pages_fetched == 2
    assert fetched.source_pages == 2
    assert fetched.next_url is None
    assert [call["params"]["page"] for call in session.calls] == [1, 2]
    assert all("limit" not in call["params"] for call in session.calls)


def test_all_pages_rejects_incomplete_unique_collection():
    client, _session = _client(
        FixtureResponse(_fixture("index_page_1.html")),
        FixtureResponse(_fixture("index_page_2.html")),
    )

    with pytest.raises(
        query_delaware_opinions.DelawareOpinionsSourceChangedError
    ) as caught:
        client.search(period="year", year="2026", page_size=25)

    assert caught.value.code == "collection_incomplete"
    assert caught.value.details["source_total"] == 26
    assert caught.value.details["unique_records"] == 3


def test_all_pages_rejects_changed_pagination_metadata():
    client, _session = _client(
        FixtureResponse(_complete_first_page()),
        FixtureResponse(
            _fixture("index_page_2.html").replace(
                "26 Opinions",
                "27 Opinions",
            )
        ),
    )

    with pytest.raises(
        query_delaware_opinions.DelawareOpinionsSourceChangedError
    ) as caught:
        client.search(period="year", year="2026", page_size=25)

    assert caught.value.code == "pagination_metadata_changed"


def test_one_page_mode_returns_native_continuation():
    client, session = _client(
        FixtureResponse(
            _fixture("index_page_1.html"),
            url=f"{query_delaware_opinions.INDEX_URL}?page=1",
        )
    )

    fetched = client.search(
        period="year",
        year="2026",
        page=1,
        page_size=25,
    )

    assert fetched.pages_fetched == 1
    assert fetched.next_url is not None
    assert "page=2" in fetched.next_url
    assert session.calls[0]["params"]["results"] == 25


def test_execute_converts_dates_and_applies_transparent_judge_postfilter():
    client, session = _client(
        FixtureResponse(
            _fixture("index_page_1.html"),
            url=query_delaware_opinions.INDEX_URL,
        )
    )

    result = query_delaware_opinions.execute(
        _parse(
            "search",
            "--judge",
            "Mitchell",
            "--revised-after",
            "2026-07-01",
            "--revised-before",
            "2026-07-15",
            "--page",
            "1",
            "--page-size",
            "25",
        ),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert [record["native_document_id"] for record in result.records] == [
        "398840"
    ]
    params = session.calls[0]["params"]
    assert params["ss"] == "Mitchell"
    assert params["period"] == "date"
    assert params["from"] == "07/01/2026"
    assert params["to"] == "07/15/2026"
    assert any("filtering removed 1 records" in value for value in result.warnings)


def test_caller_limit_is_applied_only_after_all_pages_are_fetched():
    client, session = _client(
        FixtureResponse(_complete_first_page()),
        FixtureResponse(_fixture("index_page_2.html")),
    )

    result = query_delaware_opinions.execute(
        _parse(
            "search",
            "Intel",
            "--year",
            "2026",
            "--page-size",
            "25",
            "--limit",
            "2",
        ),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert len(session.calls) == 2
    assert all("limit" not in call["params"] for call in session.calls)
    assert result.warnings[-1] == (
        "Caller limit returned 2 of 26 matched archive records fetched."
    )


class BombClient:
    def __getattr__(self, name):
        raise AssertionError(f"client must not be used: {name}")


def test_catalog_denial_is_propagated_before_any_acquisition():
    result = query_delaware_opinions.execute(
        _parse("search", "Intel", "--year", "2026"),
        access_decision={
            "allowed": False,
            "access_class": "C",
            "reason_code": "interactive_route",
            "reason": "interactive acquisition selected",
        },
        client=BombClient(),
        log_results=False,
    )

    assert result.status.value == "human_required"
    assert result.records == ()
    assert result.errors[0].code == "interactive_route"


def test_download_writes_validated_pdf_and_emits_hash_receipt(tmp_path):
    content = b"%PDF-1.6\nfixture Delaware opinion\n%%EOF"
    client, session = _client(
        FixtureResponse(
            content=content,
            url=(
                f"{query_delaware_opinions.DOWNLOAD_URL}"
                "?id=398840"
            ),
            headers={
                "Content-Type": "application/pdf; charset=binary",
                "Content-Disposition": 'inline; filename="nvidia v6.pdf"',
                "ETag": '"fixture-etag"',
            },
        )
    )
    destination = tmp_path / "opinion.pdf"

    result = query_delaware_opinions.execute(
        _parse("download", "398840", str(destination)),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert destination.read_bytes() == content
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    receipt = result.records[0]["artifact_receipt"]
    assert receipt["filename"] == "nvidia v6.pdf"
    assert receipt["bytes"] == len(content)
    assert receipt["sha256"] == hashlib.sha256(content).hexdigest()
    assert session.calls[0]["headers"]["Accept"] == "application/pdf"


def test_non_pdf_download_is_source_changed_and_not_written(tmp_path):
    client, _ = _client(
        FixtureResponse(
            text="<html>access interstitial</html>",
            headers={"Content-Type": "text/html"},
        )
    )
    destination = tmp_path / "not-an-opinion.pdf"

    result = query_delaware_opinions.execute(
        _parse("download", "398840", str(destination)),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "download_not_pdf"
    assert destination.exists() is False


def test_document_404_is_authoritative_empty_but_index_404_is_source_drift(
    tmp_path,
):
    download_client, _ = _client(FixtureResponse(status_code=404))
    download = query_delaware_opinions.execute(
        _parse("download", "398840", str(tmp_path / "missing.pdf")),
        access_decision={"allowed": True},
        client=download_client,
        log_results=False,
    )
    index_client, _ = _client(FixtureResponse(status_code=404))
    search = query_delaware_opinions.execute(
        _parse("search", "Intel", "--year", "2026"),
        access_decision={"allowed": True},
        client=index_client,
        log_results=False,
    )

    assert download.status.value == "no_results"
    assert download.errors == ()
    assert search.status.value == "source_changed"
    assert search.errors[0].code == "endpoint_not_found"


def test_access_failure_is_explicit_and_never_an_empty_result():
    client, _ = _client(FixtureResponse(status_code=403))

    result = query_delaware_opinions.execute(
        _parse("search", "Intel", "--year", "2026"),
        access_decision={"allowed": True},
        client=client,
        log_results=False,
    )

    assert result.status.value == "restricted"
    assert result.errors[0].code == "source_access_failed"


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_DE_OPINIONS") != "1",
    reason="set RUN_LIVE_DE_OPINIONS=1 for official-site probe",
)
def test_live_stable_metadata_and_pdf_sentinel():
    client = query_delaware_opinions.DelawareOpinionsClient()
    try:
        record = client.probe()
    finally:
        client.close()

    assert record["native_document_id"] == "398840"
    assert record["caption"] == "Intel Corp vs Nvidia Corp"
    assert record["raw_case_number"] == "4373-LM"
    assert record["probe"]["pdf_media_type"] == "application/pdf"
    assert record["probe"]["pdf_bytes"] > 1_000
    assert len(record["probe"]["pdf_sha256"]) == 64
