from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import query_md_public_cases as md_cases


FIXTURE_DIR = Path("tests/fixtures/public_records/md_public_cases")
TSV_HEADER = (
    "level\tpage_num\tpar_num\tblock_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext"
)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _word(
    page: int,
    top: float,
    left: float,
    text: str,
    *,
    word_number: int = 0,
) -> str:
    return (
        f"5\t{page}\t0\t0\t0\t{word_number}\t{left:.2f}\t{top:.2f}\t"
        f"20.00\t8.10\t100\t{text}"
    )


def _line(
    rows: list[str],
    page: int,
    top: float,
    values: list[tuple[float, str]],
) -> None:
    for word_number, (left, text) in enumerate(values):
        rows.append(
            _word(
                page,
                top,
                left,
                text,
                word_number=word_number,
            )
        )


def _report_tsv() -> str:
    rows = [TSV_HEADER]
    for page in (1, 2):
        _line(
            rows,
            page,
            24,
            [
                (214, "AOC"),
                (260, "-"),
                (275, "Cases"),
                (330, "Filed"),
                (378, "Report"),
            ],
        )
        _line(
            rows,
            page,
            60,
            [
                (448, "Reporting"),
                (484, "Period:"),
                (512, "7/29/2026"),
                (546, "to"),
                (554, "7/29/2026"),
            ],
        )
        _line(rows, page, 70, [(17, "Carroll")])
        _line(
            rows,
            page,
            80,
            [
                (17, "Case"),
                (40, "Number"),
                (114, "Style"),
                (358, "Case"),
                (390, "Type"),
                (523, "File"),
                (548, "Date"),
            ],
        )

    _line(
        rows,
        1,
        100,
        [
            (17, "D-102-CV-26-009424"),
            (114, "MIDLAND"),
            (159, "CREDIT"),
            (194, "MANAGEMENT,"),
            (264, "INC."),
            (284, "vs."),
            (296, "LINDA"),
            (326, "RICCI"),
            (358, "Contract"),
            (392, "-"),
            (397, "Small"),
            (421, "Claims"),
            (448, "Consumer"),
            (488, "Debt"),
            (508, "-"),
            (523, "07/29/2026"),
        ],
    )
    _line(rows, 1, 110, [(358, "Assigned")])
    _line(
        rows,
        1,
        120,
        [
            (114, "Plaintiff"),
            (150, "Address:"),
            (271, "Defendant"),
            (311, "Address:"),
        ],
    )
    _line(
        rows,
        1,
        130,
        [
            (114, "MIDLAND"),
            (159, "CREDIT"),
            (194, "MANAGEMENT,"),
            (271, "RICCI,"),
            (300, "LINDA"),
        ],
    )
    _line(rows, 1, 140, [(114, "INC."), (271, "4005"), (292, "MEADOW"), (335, "LN")])
    _line(
        rows,
        1,
        150,
        [
            (114, "350"),
            (130, "CAMINO"),
            (169, "DE"),
            (183, "LA"),
            (198, "REINA"),
            (271, "HAMPSTEAD,"),
            (331, "MD"),
            (348, "21074-2164"),
        ],
    )
    _line(rows, 1, 160, [(114, "SUITE"), (142, "100")])
    _line(
        rows,
        1,
        170,
        [(114, "SAN"), (134, "DIEGO,"), (170, "CA"), (188, "92108")],
    )
    _line(
        rows,
        1,
        690,
        [
            (17, "D-102-CR-26-001528"),
            (114, "RAY,"),
            (140, "LOGAN"),
            (358, "Criminal"),
            (405, "-"),
            (416, "SOC"),
            (444, "-"),
            (454, "Application"),
            (523, "07/29/2026"),
        ],
    )
    _line(
        rows,
        1,
        757,
        [
            (457, "Run"),
            (474, "Date:"),
            (495, "7/30/2026"),
            (529, "12:05"),
            (550, "AM"),
        ],
    )

    _line(rows, 2, 100, [(271, "Defendant"), (311, "Address:")])
    _line(rows, 2, 110, [(271, "RAY,"), (298, "LOGAN"), (333, "TYLER")])
    _line(rows, 2, 120, [(271, "3815"), (294, "SUNNYFIELD"), (360, "COURT")])
    _line(rows, 2, 130, [(271, "HAMPSTEAD,"), (331, "MD"), (348, "21074")])
    _line(rows, 2, 140, [(17, "Charges:")])
    _line(
        rows,
        2,
        150,
        [(17, "1"), (28, "-"), (38, "ASSAULT-FIRST"), (110, "DEGREE")],
    )
    _line(
        rows,
        2,
        200,
        [
            (17, "D-121-LT-26-112742-"),
            (114, "Housing"),
            (156, "Authority"),
            (358, "Failure"),
            (400, "to"),
            (416, "Pay"),
            (440, "Rent"),
            (523, "07/29/2026"),
        ],
    )
    _line(rows, 2, 210, [(17, "001")])
    _line(
        rows,
        2,
        230,
        [
            (17, "D-121-CV-26-000084"),
            (114, "JESSICA"),
            (152, "GIROD"),
            (183, "v."),
            (196, "SCOTT"),
            (225, "ABELL"),
            (358, "Peace"),
            (390, "Order"),
            (523, "07/29/2026"),
        ],
    )
    return "\n".join(rows) + "\n"


class _Response:
    def __init__(
        self,
        content: bytes,
        *,
        status_code: int = 200,
        content_type: str = "text/html",
    ) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }


class _Session:
    def __init__(self, responses: dict[str, _Response]) -> None:
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> _Response:
        self.calls.append(url)
        return self.responses[url]


def _args(*values: str) -> Any:
    return md_cases.build_parser().parse_args(list(values))


def test_landing_discovers_script_directory_instead_of_stale_inline_pdf():
    directory_url = md_cases.discover_directory_url(_fixture("landing.html"))

    assert directory_url == "https://www.mdcourts.gov/data/case/?O=D"


def test_directory_parser_preserves_dates_modification_times_and_sizes():
    reports = md_cases.parse_report_directory(_fixture("directory.html"))

    assert [report.report_date for report in reports] == [
        "2026-07-30",
        "2026-07-29",
    ]
    assert reports[0].source_url == (
        "https://www.mdcourts.gov/data/case/file2026-07-30.pdf"
    )
    assert reports[0].last_modified_local == "2026-07-30 00:15"
    assert reports[0].size_bytes_approximate == round(2.5 * 1024 * 1024)
    assert reports[1].size_bytes_approximate == 806 * 1024


def test_client_discovers_directory_and_validates_pdf_magic():
    landing = _fixture("landing.html").encode()
    directory = _fixture("directory.html").encode()
    pdf = b"%PDF-1.7\nfixture"
    report_url = "https://www.mdcourts.gov/data/case/file2026-07-30.pdf"
    session = _Session(
        {
            md_cases.LANDING_URL: _Response(landing),
            md_cases.VERIFIED_DIRECTORY_URL: _Response(directory),
            report_url: _Response(pdf, content_type="application/pdf"),
        }
    )
    client = md_cases.MarylandPublicCasesClient(
        session=session,
        minimum_interval=0,
    )

    directory_url, reports = client.report_routes()
    downloaded = client.download(reports[0])

    assert directory_url == md_cases.VERIFIED_DIRECTORY_URL
    assert downloaded.content == pdf
    assert downloaded.media_type == "application/pdf"
    assert session.calls == [
        md_cases.LANDING_URL,
        md_cases.VERIFIED_DIRECTORY_URL,
        report_url,
    ]


def test_coordinate_parser_separates_overlapping_caption_type_and_party_columns():
    parsed = md_cases.parse_cases_filed_tsv(
        _report_tsv(),
        report_publication_date="2026-07-30",
        source_url=(
            "https://www.mdcourts.gov/data/case/file2026-07-30.pdf"
        ),
    )

    assert parsed["report"]["reporting_period_start"] == "2026-07-29"
    assert parsed["report"]["report_run_at"] == "2026-07-30T00:05:00-04:00"
    assert parsed["report"]["case_count"] == 4
    first = parsed["records"][0]
    assert first["case_caption"] == (
        "MIDLAND CREDIT MANAGEMENT, INC. vs. LINDA RICCI"
    )
    assert first["case_type"] == (
        "Contract - Small Claims Consumer Debt - Assigned"
    )
    assert first["parties"] == [
        {
            "role": "plaintiff",
            "published_name": "MIDLAND CREDIT MANAGEMENT, INC.",
            "published_name_lines": [
                "MIDLAND CREDIT MANAGEMENT,",
                "INC.",
            ],
            "published_address": (
                "350 CAMINO DE LA REINA SUITE 100 SAN DIEGO, CA 92108"
            ),
            "published_address_lines": [
                "350 CAMINO DE LA REINA",
                "SUITE 100",
                "SAN DIEGO, CA 92108",
            ],
            "published_lines": [
                "MIDLAND CREDIT MANAGEMENT,",
                "INC.",
                "350 CAMINO DE LA REINA",
                "SUITE 100",
                "SAN DIEGO, CA 92108",
            ],
        },
        {
            "role": "defendant",
            "published_name": "RICCI, LINDA",
            "published_name_lines": ["RICCI, LINDA"],
            "published_address": "4005 MEADOW LN HAMPSTEAD, MD 21074-2164",
            "published_address_lines": [
                "4005 MEADOW LN",
                "HAMPSTEAD, MD 21074-2164",
            ],
            "published_lines": [
                "RICCI, LINDA",
                "4005 MEADOW LN",
                "HAMPSTEAD, MD 21074-2164",
            ],
        },
    ]


def test_coordinate_parser_continues_case_across_pages_and_ignores_footer():
    records = md_cases.parse_cases_filed_tsv(_report_tsv())["records"]

    criminal = records[1]
    assert criminal["case_number"] == "D-102-CR-26-001528"
    assert criminal["case_type"] == "Criminal - SOC - Application"
    assert criminal["source_page_numbers"] == [1, 2]
    assert criminal["charges"] == [
        {"charge_number": 1, "description": "ASSAULT-FIRST DEGREE"}
    ]
    assert criminal["parties"][0]["published_name"] == "RAY, LOGAN TYLER"

    wrapped = records[2]
    assert wrapped["case_number"] == "D-121-LT-26-112742-001"
    assert wrapped["case_type"] == "Failure to Pay Rent"


def test_filing_date_range_filters_are_native_to_the_record_window():
    records = md_cases.parse_cases_filed_tsv(_report_tsv())["records"]

    assert all(
        md_cases._matches(
            record,
            {
                "filing_date_from": "2026-07-29",
                "filing_date_to": "2026-07-29",
            },
        )
        for record in records
    )
    assert not any(
        md_cases._matches(
            record,
            {
                "filing_date_from": "2026-07-30",
                "filing_date_to": None,
            },
        )
        for record in records
    )
    with pytest.raises(md_cases.MarylandSelectionError):
        md_cases._filters(
            _args(
                "search",
                "--filing-date-from",
                "2026-07-30",
                "--filing-date-to",
                "2026-07-29",
            )
        )


def test_filters_search_case_party_address_charge_and_free_text():
    records = md_cases.parse_cases_filed_tsv(_report_tsv())["records"]

    assert [
        record["case_number"]
        for record in records
        if md_cases._matches(
            record,
            {
                "case_number": None,
                "name": "linda ricci",
                "address": "meadow",
                "court": "carroll",
                "case_type": "consumer debt",
                "charge": None,
                "filing_date": "2026-07-29",
                "query": "midland",
            },
        )
    ] == ["D-102-CV-26-009424"]
    assert md_cases._matches(
        records[1],
        {
            "case_number": "D-102-CR-26-001528",
            "name": None,
            "address": None,
            "court": None,
            "case_type": None,
            "charge": "assault-first",
            "filing_date": None,
            "query": None,
        },
    )


def test_cursor_is_query_bound_and_all_results_removes_paging():
    records = md_cases.parse_cases_filed_tsv(_report_tsv())["records"]
    selection = {"filters": {"name": None}, "report_dates": ["2026-07-30"]}

    first, cursor = md_cases._page_records(
        records,
        selection=selection,
        cursor=None,
        limit=2,
    )
    second, next_cursor = md_cases._page_records(
        records,
        selection=selection,
        cursor=cursor,
        limit=2,
    )

    assert len(first) == 2
    assert len(second) == 2
    assert next_cursor is None
    with pytest.raises(md_cases.MarylandSelectionError, match="different"):
        md_cases._page_records(
            records,
            selection={"filters": {"name": "changed"}},
            cursor=cursor,
            limit=2,
        )
    all_records, no_cursor = md_cases._page_records(
        records,
        selection=selection,
        cursor=None,
        limit=None,
    )
    assert len(all_records) == 4
    assert no_cursor is None


def test_routes_expose_operation_roles_and_join_keys():
    result = md_cases.execute(_args("routes"), log_results=False)
    manifest = result.to_dict()["records"][0]

    assert result.status.value == "ok"
    assert manifest["source"]["source_id"] == md_cases.SOURCE_ID
    related = {
        item["source_id"]: item
        for item in manifest["related_source_routes"]
    }
    assert related["us-md-case-search"]["operation_state"] == (
        "interactive_agreement_and_captcha"
    )
    assert related["us-md-judgment-liens"]["join_keys"] == [
        "case_number",
        "party_name",
        "court_name",
    ]
    assert "published_address" in related[
        "us-md-sdat-property-hidden"
    ]["join_keys"]


def test_report_date_selection_uses_only_source_published_routes():
    routes = md_cases.parse_report_directory(_fixture("directory.html"))

    selected = md_cases._select_routes(
        routes,
        requested_dates=["2026-07-29"],
        all_current=False,
    )
    assert [route.report_date for route in selected] == ["2026-07-29"]
    with pytest.raises(md_cases.MarylandSelectionError) as error:
        md_cases._select_routes(
            routes,
            requested_dates=["2026-07-28"],
            all_current=False,
        )
    assert error.value.details["available_dates"] == [
        "2026-07-30",
        "2026-07-29",
    ]


def test_extract_pdf_tsv_invokes_layout_coordinate_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    observed: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return SimpleNamespace(
            returncode=0,
            stdout=(TSV_HEADER + "\n").encode(),
            stderr=b"",
        )

    monkeypatch.setattr(md_cases.subprocess, "run", fake_run)
    extracted = md_cases.extract_pdf_tsv(pdf, executable="/usr/bin/pdftotext")

    assert extracted.startswith("level\tpage_num")
    assert observed["command"] == [
        "/usr/bin/pdftotext",
        "-tsv",
        str(pdf.resolve()),
        "-",
    ]
    assert observed["kwargs"]["capture_output"] is True
