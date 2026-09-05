from __future__ import annotations

import html
import os
from pathlib import Path

import pytest

from tools import query_orange_county_court as orange


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "orange_county_court"
RETRIEVED_AT = "2026-07-30T08:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def response(
    text: str,
    url: str,
    *,
    content_type: str = "text/html; charset=UTF-8",
) -> orange.FetchedResponse:
    return orange.FetchedResponse(
        body=text.encode(),
        url=url,
        headers={"Content-Type": content_type},
    )


def calendar_html(
    *,
    total: int,
    start: int,
    count: int,
    marker: str = "stable",
) -> str:
    rows: list[str] = []
    for offset in range(count):
        item = start + offset
        rows.append(
            f"""
            <tr>
              <td class="col_caseid">30-2026-{item:08d}-CU-BC-CJC</td>
              <td class="col_title">Example {html.escape(marker)} {item} vs. Sample LLC</td>
              <td class="col_location">CJC</td>
              <td class="col_dept">C44</td>
              <td class="col_date">07/30/26</td>
              <td class="col_time">09:00 AM</td>
              <td class="col_casetype">Breach Of Contract/Warranty</td>
              <td class="col_hearingtype">Case Management Conference</td>
            </tr>
            """
        )
    end = start + count - 1
    if total == count and start == 1:
        banner = f"{total} items found, displaying all items."
    else:
        banner = f"{total} items found, displaying {start} to {end}."
    return f"""
    <!doctype html>
    <html>
      <head><title>Superior Court of California - County of Orange</title></head>
      <body>
        <div class="validationerrorsbox"></div>
        <table id="case">
          <thead><tr>
            <th>Case ID</th><th>Title</th><th>Location</th><th>Dept</th>
            <th>Date</th><th>Time</th><th>Case Type</th>
            <th>Type of Hearing</th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        <span class="pagebanner">{banner}</span>
      </body>
    </html>
    """


class FixtureClient:
    def __init__(
        self,
        *,
        first_pages: list[str] | None = None,
        calendar_pages: dict[int, str] | None = None,
        ruling_pages: dict[str, str] | None = None,
        artifact_bytes: bytes = b"%PDF-1.7\nfixture\n%%EOF\n",
    ) -> None:
        self.first_pages = first_pages or [fixture("calendar_page_1.html")]
        self.calendar_pages = calendar_pages or {}
        self.ruling_pages = ruling_pages or {
            "civil": fixture("rulings_civil.html"),
            "family": fixture("rulings_family.html"),
            "probate": fixture("rulings_probate.html"),
        }
        self.artifact_bytes = artifact_bytes
        self.first_calls = 0
        self.page_calls: list[int] = []
        self.form_payloads: list[dict[str, str]] = []

    def calendar_landing(self) -> orange.FetchedResponse:
        return response(fixture("calendar_form.html"), orange.CALENDAR_URL)

    def calendar_first(
        self,
        form_data: dict[str, str],
    ) -> orange.FetchedResponse:
        self.form_payloads.append(dict(form_data))
        index = min(self.first_calls, len(self.first_pages) - 1)
        self.first_calls += 1
        return response(self.first_pages[index], orange.CALENDAR_URL)

    def calendar_page(
        self,
        form_data: dict[str, str],
        page: int,
    ) -> orange.FetchedResponse:
        self.form_payloads.append(dict(form_data))
        self.page_calls.append(page)
        return response(self.calendar_pages[page], orange.CALENDAR_URL)

    def page(self, url: str) -> orange.FetchedResponse:
        for division, directory_url in orange.RULING_DIRECTORY_URLS.items():
            if url == directory_url:
                return response(self.ruling_pages[division], directory_url)
        return orange.FetchedResponse(
            body=self.artifact_bytes,
            url=url,
            headers={
                "Content-Type": "application/pdf",
                "Last-Modified": "Thu, 30 Jul 2026 07:00:00 GMT",
                "ETag": '"fixture"',
            },
        )


def test_source_manifest_separates_bounds_and_complements() -> None:
    records = orange.source_records()
    family = next(
        row
        for row in records
        if row["source_id"] == orange.SOURCE_FAMILY_ID
    )
    assert set(family["component_source_ids"]) == {
        orange.CALENDAR_SOURCE_ID,
        *orange.RULING_SOURCE_IDS.values(),
        orange.CASE_NAME_SOURCE_ID,
        orange.CASE_PORTALS_SOURCE_ID,
        orange.CASE_INDEX_SOURCE_ID,
        orange.CASE_INDEX_PRODUCT_SOURCE_ID,
        orange.PROBATE_NOTES_SOURCE_ID,
        orange.RECORDS_SOURCE_ID,
    }
    calendar = next(
        row
        for row in records
        if row["source_id"] == orange.CALENDAR_SOURCE_ID
    )
    assert calendar["bounds"]["caller_limit"].startswith("optional")
    assert calendar["bounds"]["transport_page_size"] == 50
    assert "500" in calendar["bounds"]["server_behavior"]
    complements = [
        row for row in records if row["record_kind"] == "complementary_source"
    ]
    assert any(row["url"] == orange.CASE_NAME_SEARCH_URL for row in complements)
    assert any(row["url"] == orange.CASE_INDEX_ORDER_URL for row in complements)
    assert any("$50" in row["access"] for row in complements)
    assert len({row["source_id"] for row in complements}) == len(complements)


def test_parse_calendar_form_contract() -> None:
    contract = orange.parse_calendar_form(fixture("calendar_form.html"))
    assert contract.default_date_from == "2026-07-30"
    assert contract.default_date_to == "2026-09-10"
    assert contract.transport_page_size == 50
    assert contract.category_codes == orange.CATEGORY_LABELS
    assert ";jsessionid" not in contract.action_url
    assert len(contract.schema_fingerprint) == 64


def test_parse_calendar_page_normalizes_hearing_and_parties() -> None:
    page = orange.parse_calendar_page(
        fixture("calendar_page_1.html"),
        category="civil",
        retrieved_at=RETRIEVED_AT,
    )
    assert page.total == 3
    assert len(page.records) == 2
    first = page.records[0]
    assert first["case"]["case_number"] == "30-2025-01484637-CU-OE-CJC"
    assert first["case"]["title_parties"][0]["name"] == "Joe E. Kiani"
    assert first["case"]["title_parties"][1]["name"] == "Quentin Koffey"
    assert first["hearing"]["date"] == "2026-07-30"
    assert first["hearing"]["department"] == "C44"


def test_omitted_limit_exhausts_every_native_page() -> None:
    page_one = calendar_html(total=53, start=1, count=50)
    page_two = calendar_html(total=53, start=51, count=3)
    client = FixtureClient(
        first_pages=[page_one],
        calendar_pages={2: page_two},
    )
    result = orange.calendar_search(
        orange.CalendarCriteria(category="civil", title="Example"),
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 53
    assert result.next_cursor is None
    assert client.page_calls == [2]
    coverage = result.query.query.metadata["coverage"]
    assert coverage["source_total"] == 53
    assert list(coverage["pages_fetched"]) == [1, 2]
    bounds = result.query.query.metadata["bounds"]
    assert bounds["caller_limit"] is None
    assert bounds["transport_page_size"] == 50


def test_explicit_limit_issues_snapshot_bound_cursor_and_resumes() -> None:
    client = FixtureClient()
    criteria = orange.CalendarCriteria(category="civil", title="Kiani")
    first = orange.calendar_search(
        criteria,
        limit=1,
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert len(first.records) == 1
    assert first.next_cursor
    second = orange.calendar_search(
        criteria,
        limit=1,
        cursor=first.next_cursor,
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert len(second.records) == 1
    assert (
        first.records[0]["canonical_ref"]
        != second.records[0]["canonical_ref"]
    )
    assert second.next_cursor


def test_cursor_rejects_changed_criteria() -> None:
    client = FixtureClient()
    initial = orange.calendar_search(
        orange.CalendarCriteria(category="civil", title="Kiani"),
        limit=1,
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    with pytest.raises(orange.OrangeCourtSelectionError) as raised:
        orange.calendar_search(
            orange.CalendarCriteria(category="civil", title="Different"),
            limit=1,
            cursor=initial.next_cursor,
            client=client,
            retrieved_at=RETRIEVED_AT,
        )
    assert raised.value.code == "calendar_cursor_query_mismatch"


def test_traversal_detects_source_snapshot_change() -> None:
    first = calendar_html(total=51, start=1, count=50, marker="stable")
    changed = calendar_html(total=51, start=1, count=50, marker="changed")
    client = FixtureClient(
        first_pages=[first, changed],
        calendar_pages={
            2: calendar_html(total=51, start=51, count=1, marker="stable")
        },
    )
    with pytest.raises(orange.OrangeCourtSourceChangedError) as raised:
        orange.calendar_search(
            orange.CalendarCriteria(category="civil"),
            client=client,
            retrieved_at=RETRIEVED_AT,
        )
    assert raised.value.code == "orange_calendar_snapshot_changed_during_traversal"


def test_calendar_no_results_is_authoritative_empty() -> None:
    client = FixtureClient(
        first_pages=[fixture("calendar_no_results.html")]
    )
    result = orange.calendar_search(
        orange.CalendarCriteria(category="probate", title="No Such Party"),
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_ruling_directories_keep_current_components_distinct() -> None:
    civil = orange.parse_ruling_directory(
        fixture("rulings_civil.html"),
        division="civil",
        response_url=orange.RULING_DIRECTORY_URLS["civil"],
        retrieved_at=RETRIEVED_AT,
    )
    family = orange.parse_ruling_directory(
        fixture("rulings_family.html"),
        division="family",
        response_url=orange.RULING_DIRECTORY_URLS["family"],
        retrieved_at=RETRIEVED_AT,
    )
    probate = orange.parse_ruling_directory(
        fixture("rulings_probate.html"),
        division="probate",
        response_url=orange.RULING_DIRECTORY_URLS["probate"],
        retrieved_at=RETRIEVED_AT,
    )
    assert [row["department"] for row in civil] == ["CX101", "C44", "C33"]
    assert family == []
    assert [row["department"] for row in probate] == ["CM3", "CM4"]


def test_ruling_index_reports_zero_family_state_without_hiding_other_rows() -> None:
    result = orange.ruling_index(
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 5
    counts = result.query.query.metadata["directory_counts_before_filter"]
    assert dict(counts) == {"civil": 3, "family": 0, "probate": 2}
    assert any("family-law directory" in warning for warning in result.warnings)


def test_parse_ruling_text_retains_full_text_and_case_identifiers() -> None:
    parsed = orange.parse_ruling_text(fixture("ruling_text.txt"))
    assert parsed["department"] == "C44"
    assert parsed["judicial_officer"] == "Sample Judicial Officer"
    assert parsed["hearing_date"] == "2026-07-30"
    assert parsed["hearing_time"] == "1:30 PM"
    assert parsed["case_numbers"] == [
        "30-2026-01546059-CU-MC-CJC",
        "2025-01484712",
    ]
    assert "Motion to compel is denied." in parsed["text"]
    assert len(parsed["text_sha256"]) == 64


def test_ruling_document_validates_and_preserves_pdf(
    tmp_path: Path,
) -> None:
    pdf_bytes = b"%PDF-1.7\nfixture artifact\n%%EOF\n"
    client = FixtureClient(artifact_bytes=pdf_bytes)
    destination = tmp_path / "c44.pdf"
    result = orange.ruling_document(
        "civil",
        "C44",
        client=client,
        retrieved_at=RETRIEVED_AT,
        download_path=destination,
        text_extractor=lambda _: fixture("ruling_text.txt"),
    )
    assert result.status.value == "ok"
    record = result.records[0]
    assert record["department"] == "C44"
    assert record["artifact"]["sha256"] == __import__("hashlib").sha256(
        pdf_bytes
    ).hexdigest()
    assert record["artifact"]["last_modified"] == "2026-07-30T07:00:00Z"
    assert record["case_numbers"]
    assert destination.read_bytes() == pdf_bytes


def test_ruling_document_rejects_non_pdf_representation() -> None:
    client = FixtureClient(artifact_bytes=b"<html>challenge</html>")
    with pytest.raises(orange.OrangeCourtSourceChangedError) as raised:
        orange.ruling_document(
            "civil",
            "C44",
            client=client,
            retrieved_at=RETRIEVED_AT,
            include_text=False,
        )
    assert raised.value.code == "orange_ruling_artifact_not_pdf"


def test_probe_is_bounded_and_reports_component_counts() -> None:
    result = orange.probe_sources(
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    record = result.records[0]
    assert record["calendar"]["category_count"] == 6
    assert record["probe_bounds"]["calendar_pages"] == 1
    assert record["probe_bounds"]["calendar_rows_at_most"] == 50
    assert record["probe_bounds"]["ruling_artifacts_downloaded"] == 0
    assert record["tentative_rulings"]["current_directory_counts"] == {
        "civil": 3,
        "family": 0,
        "probate": 2,
    }


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official endpoint probes",
)
def test_live_probe_confirms_calendar_and_current_directories() -> None:
    result = orange.probe_sources()
    assert result.status.value == "ok"
    record = result.records[0]
    assert record["calendar"]["category_count"] == 6
    assert record["calendar"]["transport_page_size"] == 50
    assert record["tentative_rulings"]["current_directory_counts"]["civil"] > 0
    assert record["tentative_rulings"]["current_directory_counts"]["probate"] > 0
