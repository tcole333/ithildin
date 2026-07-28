from __future__ import annotations

import argparse
import json

from tools import query_edgar


def _args(output):
    return argparse.Namespace(
        cik="123",
        limit=5,
        start=None,
        end=None,
        detail=True,
        output=str(output),
        json_out=False,
    )


def test_insider_detail_follows_xsl_display_link_and_writes_transactions(
    tmp_path, monkeypatch
):
    accession = "0000000123-24-000001"
    accession_path = accession.replace("-", "")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/123/{accession_path}/"
    )
    display_path = (
        f"/Archives/edgar/data/123/{accession_path}/"
        "xslF345X05/ownership.xml"
    )
    raw_url = (
        f"https://www.sec.gov/Archives/edgar/data/123/{accession_path}/"
        "ownership.xml"
    )
    submissions = {
        "name": "REPORTING OWNER",
        "cik": "123",
        "filings": {
            "recent": {
                "form": ["4"],
                "filingDate": ["2024-01-10"],
                "accessionNumber": [accession],
                "primaryDocument": ["xslF345X05/ownership.xml"],
            }
        },
    }
    ownership_xml = b"""<?xml version="1.0"?>
    <ownershipDocument xmlns="urn:sec:ownership">
      <issuer>
        <issuerName>Example Issuer</issuerName>
        <issuerTradingSymbol>EXM</issuerTradingSymbol>
      </issuer>
      <reportingOwnerRelationship>
        <isDirector>1</isDirector>
      </reportingOwnerRelationship>
      <nonDerivativeTransaction>
        <securityTitle><value>Common Stock</value></securityTitle>
        <transactionDate><value>2024-01-09</value></transactionDate>
        <transactionCoding><transactionCode>S</transactionCode></transactionCoding>
        <transactionAmounts>
          <transactionShares><value>250</value></transactionShares>
          <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
          <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
        </transactionAmounts>
      </nonDerivativeTransaction>
    </ownershipDocument>
    """
    calls = []

    def fake_request(url, params=None, accept="application/json", **_kwargs):
        calls.append((url, accept))
        if url == f"{query_edgar.SUBMISSIONS_URL}/CIK0000000123.json":
            return submissions
        if url == index_url:
            return f'<html><a href="{display_path}">Form 4</a></html>'.encode()
        if url == raw_url:
            return ownership_xml
        raise AssertionError(f"unexpected SEC URL: {url}")

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    output = tmp_path / "insider.json"

    query_edgar.cmd_insider(_args(output))

    result = json.loads(output.read_text())
    detail = result["filings"][0]["detail"]
    assert detail["status"] == "parsed"
    assert detail["source_url"] == raw_url
    assert detail["roles"] == ["Director"]
    assert detail["transactions"] == [
        {
            "security_type": "non_derivative",
            "security": "Common Stock",
            "date": "2024-01-09",
            "code": "S",
            "action": "Sale",
            "shares": "250",
            "price_per_share": "12.50",
            "direction": "Disposed",
        }
    ]
    assert calls == [
        (
            f"{query_edgar.SUBMISSIONS_URL}/CIK0000000123.json",
            "application/json",
        ),
        (index_url, "text/html"),
        (raw_url, "application/xml"),
    ]


def test_ownership_xml_candidates_reject_external_and_auxiliary_first():
    index_url = (
        "https://www.sec.gov/Archives/edgar/data/123/000000012324000001/"
    )
    index_html = """
      <a href="FilingSummary.xml">summary</a>
      <a href="https://example.com/ownership.xml">external</a>
      <a href="xslF345X05/ownership.xml?output=1">ownership</a>
    """

    assert query_edgar._ownership_xml_candidates(
        index_url,
        index_html,
        "xslF345X05/ownership.xml",
    ) == [
        (
            "https://www.sec.gov/Archives/edgar/data/123/"
            "000000012324000001/ownership.xml"
        ),
        (
            "https://www.sec.gov/Archives/edgar/data/123/"
            "000000012324000001/FilingSummary.xml"
        ),
    ]
