"""Historical and nonannual analysis must stay bound to its selected accession."""

import sys
from contextlib import nullcontext
from types import SimpleNamespace
import json

import pandas as pd
import pytest

from tools import query_edgar as edgar


class Statement:
    def to_dataframe(self):
        return pd.DataFrame([{"label": "Revenue", "concept": "Revenue", "2020": 12}])


def _filing(accession, form):
    return SimpleNamespace(
        accession_no=accession, form=form, filing_date="2020-03-01",
        company="Fixture Co", homepage_url="https://www.sec.gov/Archives/edgar/data/42/",
        obj=lambda: SimpleNamespace(**{
            section: Statement() for section in
            ("income_statement", "balance_sheet", "cashflow_statement")
        }),
    )


@pytest.fixture
def catalog(monkeypatch):
    rows = [
        _filing("0000000042-26-000001", "10-K"),
        _filing("0000000042-20-000002", "10-Q"),
        _filing("0000000042-19-000003", "10-K"),
    ]
    calls = []

    class Company:
        cik = 42
        name = "Fixture Co"

        def __init__(self, _identifier):
            pass

        def get_filings(self, **filters):
            calls.append(filters)
            return [r for r in rows
                    if r.accession_no == filters.get("accession_number", r.accession_no)
                    and r.form == filters.get("form", r.form)]

    monkeypatch.setitem(sys.modules, "edgar", SimpleNamespace(Company=Company))
    monkeypatch.setattr(edgar, "_edgartools_import_lock", nullcontext)
    monkeypatch.setattr(edgar, "_configure_edgartools_data_dir", lambda: "/unused")
    monkeypatch.setattr(edgar, "_ensure_edgartools_migration_markers", lambda _: None)
    return rows, calls, Company


@pytest.mark.parametrize("index", [1, 2])
@pytest.mark.parametrize("selector", ["accession", "url"])
def test_three_statements_retain_selected_filing(catalog, tmp_path, index, selector):
    rows, calls, _ = catalog
    selected = rows[index]
    value = selected.accession_no if selector == "accession" else (
        "https://www.sec.gov/Archives/edgar/data/42/"
        + selected.accession_no.replace("-", "") + "/selected.htm"
    )
    for section in ("income_statement", "balance_sheet", "cashflow_statement"):
        output = tmp_path / f"{section}.json"
        args = SimpleNamespace(
            ticker="42" if selector == "accession" else None,
            form=None, index=0, section=section, lines=100,
            output=str(output), json_out=False, **{selector: value},
        )
        assert edgar.cmd_sections(args) is None
        saved = json.loads(output.read_text())
        assert saved["accession"] == selected.accession_no
        assert saved["form"] == selected.form
    assert calls == [{"accession_number": selected.accession_no}] * 3


def test_missing_accession_never_falls_back_to_latest(catalog):
    filing, _ = edgar._get_edgartools_filing("42", accession="0000000042-18-000009")
    assert filing is None


def test_wrong_returned_accession_is_rejected(catalog, monkeypatch):
    rows, _, company = catalog
    monkeypatch.setattr(company, "get_filings", lambda self, **kwargs: [rows[0]])
    with pytest.raises(ValueError, match="different accession"):
        edgar._get_edgartools_filing("42", accession=rows[1].accession_no)


def test_url_company_and_explicit_form_must_match(catalog):
    rows, _, _ = catalog
    with pytest.raises(ValueError, match="CIK"):
        edgar._get_edgartools_filing(
            "42", url="https://www.sec.gov/Archives/edgar/data/99/000000004220000002/x.htm",
        )
    with pytest.raises(ValueError, match="not requested 10-K"):
        edgar._get_edgartools_filing("42", form="10-K", accession=rows[1].accession_no)


@pytest.mark.parametrize("url", [
    "https://example.com/Archives/edgar/data/42/000000004220000002/x.htm",
    "https://www.sec.gov/Archives/edgar/data/42/",
    "https://user@www.sec.gov/Archives/edgar/data/42/000000004220000002/x.htm",
])
def test_unsupported_url_identity_is_rejected(url):
    with pytest.raises(ValueError):
        edgar._filing_url_identity(url)


def test_cli_rejects_combined_stable_and_index_selectors(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["query_edgar.py", "sections", "42",
                                    "--accession", "0000000042-20-000002", "--index", "0"])
    with pytest.raises(SystemExit) as exc:
        edgar.main()
    assert exc.value.code == 2


def test_cli_url_without_ticker_keeps_quarterly_accession(catalog, monkeypatch, tmp_path):
    output = tmp_path / "quarterly-income.json"
    monkeypatch.setattr(sys, "argv", ["query_edgar.py", "sections", "--url",
                        "https://www.sec.gov/Archives/edgar/data/42/000000004220000002/q.htm",
                        "--section", "income_statement", "--output", str(output)])
    edgar.main()
    saved = json.loads(output.read_text())
    assert saved["form"] == "10-Q"
    assert saved["accession"] == "0000000042-20-000002"
