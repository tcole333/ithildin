from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

import pytest

from tools import query_orange_tax_collector as orange
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


ACCOUNT = "012027000000001"
FORMATTED_ACCOUNT = "01-20-27-0000-00001"
PARENT_UUID = "54c5c30a-d853-11ef-b1f9-cf6e57f2283b"
SEMANTIC_ID = f"orange:real_estate:parents:{PARENT_UUID}"
OBJECT_ID = f"/Taxsys-GovHub/v0/items/{SEMANTIC_ID}"
BILL_UUID = "ca0e3d54-aad7-11f0-bb75-005056815849"


def _hit() -> dict[str, Any]:
    return {
        "child_groups": [
            {
                "children": [
                    {
                        "external_id": FORMATTED_ACCOUNT,
                        "custom_parameters": {
                            "roll_year": "2025",
                            "external_type": "Account",
                            "custom_payable_type": "accounts",
                        },
                        "external_id_tokens": [ACCOUNT],
                    }
                ]
            }
        ],
        "custom_parameters": {
            "public_url": (
                f"/public/real_estate/parcels/{FORMATTED_ACCOUNT}/"
                f"bills?parcel={PARENT_UUID}"
            ),
            "custom_payable_type": "parents",
            "alternate_keys": [
                {
                    "external_id": "6431",
                    "external_type": "Alternate Key",
                }
            ],
            "external_type": "Account",
            "entities": [
                {
                    "external_id": (
                        "ORANGE COUNTY BCC, PO BOX 1393, "
                        "ORLANDO, FL 32802-1393"
                    ),
                    "address": "PO BOX 1393",
                    "province": "",
                    "external_type": "Owner/Address",
                    "country": "",
                    "state": "FL",
                    "zip": "32802-1393",
                    "name": "ORANGE COUNTY BCC",
                    "city": "ORLANDO",
                },
                {
                    "external_id": "OAK LN, Mount Dora, 32757",
                    "address": "OAK LN",
                    "province": "",
                    "external_type": "Address",
                    "country": "",
                    "state": "",
                    "zip": "32757",
                    "name": "",
                    "city": "Mount Dora",
                },
            ],
        },
        "display_name": "ORANGE COUNTY BCC",
        "display_type": "property_tax",
        "external_id": FORMATTED_ACCOUNT,
        "item_category": "Real Estate",
        "objectID": OBJECT_ID,
        "_highlightResult": {},
    }


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        body: Any = None,
        text: str = "",
        content_type: str = "application/json",
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.text = text
        self.headers = {"Content-Type": content_type}

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("not JSON")
        return self._body


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def _search_response(
    hits: list[dict[str, Any]],
    *,
    query: str,
    page: int = 0,
    nb_pages: int = 1,
    nb_hits: int | None = None,
) -> FakeResponse:
    return FakeResponse(
        body={
            "results": [
                {
                    "hits": hits,
                    "nbHits": len(hits) if nb_hits is None else nb_hits,
                    "page": page,
                    "nbPages": nb_pages,
                    "hitsPerPage": orange.ALGOLIA_HITS_PER_PAGE,
                    "query": query,
                    "params": "",
                    "index": orange.ALGOLIA_INDEX,
                }
            ]
        }
    )


def _client(session: FakeSession) -> orange.OrangeTaxPortalClient:
    return orange.OrangeTaxPortalClient(
        session=session,
        timeout=1,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )


def test_account_normalization_and_taxsys_identity_are_separate() -> None:
    assert orange.normalize_account(FORMATTED_ACCOUNT) == ACCOUNT
    assert orange.format_account(ACCOUNT) == FORMATTED_ACCOUNT

    semantic_id, token = orange.account_token_from_object_id(OBJECT_ID)

    assert semantic_id == SEMANTIC_ID
    assert orange.validate_account_token(token) == SEMANTIC_ID
    assert token == (
        "b3JhbmdlOnJlYWxfZXN0YXRlOnBhcmVudHM6"
        "NTRjNWMzMGEtZDg1My0xMWVmLWIxZjktY2Y2ZTU3ZjIyODNi"
    )
    with pytest.raises(orange.OrangeTaxQueryError, match="15 digits"):
        orange.normalize_account("6431")


def test_live_algolia_shape_preserves_account_owner_situs_and_ids() -> None:
    record = orange.normalize_portal_hit(_hit())

    assert record["parcel_join"]["normalized_15_digit_account"] == ACCOUNT
    assert record["native_account_id"] == FORMATTED_ACCOUNT
    assert record["algolia_object_id"] == OBJECT_ID
    assert record["taxsys_parent_uuid"] == PARENT_UUID
    assert record["alternate_keys"][0]["external_id"] == "6431"
    assert record["roll_year"] == 2025
    assert record["owners"][0]["raw_name"] == "ORANGE COUNTY BCC"
    assert record["owners"][0]["name"] == "ORANGE COUNTY BCC"
    assert record["owners"][0]["external_id"] == (
        _hit()["custom_parameters"]["entities"][0]["external_id"]
    )
    assert record["owners"][0]["assertion_type"] == "tax_account_owner_label"
    assert record["owners"][0]["title_caveat"] == "not_a_title_chain"
    assert record["situs_entities"][0]["address"] == "OAK LN"


def test_portal_missing_owner_name_does_not_promote_composite_address_label() -> None:
    hit = _hit()
    hit["custom_parameters"]["entities"][0]["name"] = ""

    owner = orange.normalize_portal_hit(hit)["owners"][0]

    assert owner["raw_name"] is None
    assert owner["name"] is None
    assert owner["external_id"] == (
        "ORANGE COUNTY BCC, PO BOX 1393, ORLANDO, FL 32802-1393"
    )
    assert owner["assertion_type"] == "tax_account_owner_label"
    assert owner["title_caveat"] == "not_a_title_chain"


def test_portal_search_posts_verified_index_contract_and_binds_cursor() -> None:
    second_hit = _hit()
    second_hit["objectID"] = (
        "/Taxsys-GovHub/v0/items/orange:real_estate:parents:"
        "11111111-2222-4333-8444-555555555555"
    )
    second_hit["external_id"] = "01-20-27-0000-00002"
    first_session = FakeSession(
        [
            _search_response(
                [_hit(), second_hit],
                query=ACCOUNT,
                nb_hits=2,
            )
        ]
    )

    first = _client(first_session).search(ACCOUNT, limit=1)

    assert len(first.records) == 1
    assert first.next_cursor is not None
    call = first_session.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == orange.ALGOLIA_URL
    assert call["headers"]["X-Algolia-Application-Id"] == (
        orange.ALGOLIA_APPLICATION_ID
    )
    assert call["headers"]["X-Algolia-API-Key"] == (
        orange.ALGOLIA_PUBLIC_SEARCH_KEY
    )
    request = call["json"]["requests"][0]
    assert request["indexName"] == orange.ALGOLIA_INDEX
    params = request["params"]
    assert "hitsPerPage=15" in params
    assert "page=0" in params

    second_session = FakeSession(
        [
            _search_response(
                [_hit(), second_hit],
                query=ACCOUNT,
                nb_hits=2,
            )
        ]
    )
    second = _client(second_session).search(
        ACCOUNT,
        limit=1,
        cursor=first.next_cursor,
    )
    assert second.records[0]["parcel_join"][
        "normalized_15_digit_account"
    ] == "012027000000002"

    with pytest.raises(
        orange.OrangeTaxQueryError,
        match="different query or index",
    ):
        _client(FakeSession([])).search(
            "different",
            limit=1,
            cursor=first.next_cursor,
        )


def test_portal_cursor_continues_at_next_page_on_exact_page_boundary() -> None:
    hits: list[dict[str, Any]] = []
    for index in range(15):
        hit = _hit()
        hit["external_id"] = f"{index + 1:015d}"
        hit["objectID"] = (
            "/Taxsys-GovHub/v0/items/orange:real_estate:parents:"
            f"00000000-0000-4000-8000-{index + 1:012d}"
        )
        hits.append(hit)
    first_session = FakeSession(
        [
            _search_response(
                hits,
                query="owner",
                page=0,
                nb_pages=2,
                nb_hits=16,
            )
        ]
    )
    first = _client(first_session).search("owner", limit=15)

    assert len(first.records) == 15
    assert first.next_cursor is not None

    second_session = FakeSession(
        [
            _search_response(
                [_hit()],
                query="owner",
                page=1,
                nb_pages=2,
                nb_hits=16,
            )
        ]
    )
    second = _client(second_session).search(
        "owner",
        limit=15,
        cursor=first.next_cursor,
    )
    assert len(second.records) == 1
    params = second_session.calls[0]["json"]["requests"][0]["params"]
    assert "page=1" in params


def test_portal_access_failure_is_not_an_empty_result() -> None:
    session = FakeSession([FakeResponse(status_code=403)])

    with pytest.raises(orange.OrangeTaxRestricted):
        _client(session).search(ACCOUNT, limit=1)


def test_client_uses_verified_direct_anonymous_taxsys_routes() -> None:
    token = orange.account_token_from_object_id(OBJECT_ID)[1]
    session = FakeSession(
        [
            FakeResponse(
                text="<table><thead><th>Bill</th></thead></table>",
                content_type="text/html",
            ),
            FakeResponse(
                text="<html><h1>Bill</h1></html>",
                content_type="text/html",
            ),
        ]
    )
    client = _client(session)

    history_url, _ = client.history_html(token)
    bill_url, _ = client.bill_html(token, BILL_UUID)

    assert history_url == (
        f"{orange.TAXSYS_ROOT}/property-tax/{token}/load-bill-history"
    )
    assert bill_url == (
        f"{orange.TAXSYS_ROOT}/property-tax/{token}/bills/{BILL_UUID}"
    )
    assert session.calls[0]["headers"]["Referer"] == (
        orange.GOVHUB_PORTAL_URL
    )


def _history_html(token: str) -> str:
    bill_url = (
        "https://county-taxes.net/fl-orange/property-tax/"
        f"{token}/bills/{BILL_UUID}"
    )
    return f"""
    <table class="table table-hover bills">
      <thead><tr>
        <th>Bill</th><th class="balance">Amount due</th>
        <th class="status">Status</th>
      </tr></thead>
      <tbody class="grouped">
        <tr class="regular">
          <th class="description">
            <a href="{bill_url}">2023 Annual bill</a>
          </th>
          <td class="balance">$0.00</td>
          <td class="status">
            <span class="label">Paid</span>
            <span translate="no">$23.55</span>
          </td>
          <td class="as-of"><time>09/12/2024</time></td>
          <td class="message">
            <span class="label">Receipt</span>
            <span translate="no">#2002-10083274</span>
          </td>
          <td><a class="print-link-with-icon"
            href="{bill_url}/print">Print</a></td>
        </tr>
      </tbody>
      <tbody class="grouped">
        <tr class="certificate">
          <th class="description">
            <a href="{bill_url}#certificate">
              Certificate <span>#230000001</span>
            </a>
          </th>
          <td class="status"><span class="label">Redeemed</span></td>
          <td class="as-of">06/22/2023</td>
          <td class="message">
            <span class="label">Face</span> <span>$4,563.70</span>,
            <span class="label">Rate</span> <span>5.75%</span>
          </td>
        </tr>
      </tbody>
    </table>
    """


def test_history_parser_keeps_bill_receipt_and_certificate_separate() -> None:
    token = orange.account_token_from_object_id(OBJECT_ID)[1]

    records = orange.parse_bill_history_html(
        _history_html(token),
        account_token=token,
        parcel_account=ACCOUNT,
        source_url="https://example.test/history",
    )

    assert [record["record_kind"] for record in records] == [
        "property_tax_bill_history",
        "property_tax_certificate_history",
    ]
    bill, certificate = records
    assert bill["bill_uuid"] == BILL_UUID
    assert bill["payment"]["receipt_number"] == "2002-10083274"
    assert bill["payment"]["date"]["iso"] == "2024-09-12T00:00:00"
    assert certificate["bill_uuid"] == BILL_UUID
    assert certificate["certificate_number"] == "230000001"
    assert certificate["certificate_status"] == "Redeemed"
    assert certificate["face_value"]["decimal"] == "4563.70"
    assert certificate["interest_rate"]["percent_decimal"] == "5.75"
    assert bill["parcel_join"]["normalized_15_digit_account"] == ACCOUNT


def _bill_html(token: str) -> str:
    bill_url = (
        "https://county-taxes.net/iframe-taxsys/"
        "orange.county-taxes.com/govhub/property-tax/"
        f"{token}/bills/{BILL_UUID}"
    )
    return f"""
    <!doctype html><html><body>
      <section class="content-card account property-tax details">
        <div class="account-header">
          <h1>Real Estate Account #{FORMATTED_ACCOUNT}</h1>
        </div>
        <div class="content-group individual-bill individual-bill-re">
          <h2 id="bill">2025 Annual bill</h2>
          <table class="bills"><tbody><tr>
            <th class="description">2025 Annual bill</th>
            <td class="alternate">6431</td>
            <td class="escrow">&mdash;</td>
            <td class="millage">11 ORG</td>
            <td class="balance">$0.00</td>
            <td><span class="emphasized-status">no balance due</span></td>
          </tr></tbody></table>
          <a class="print-link-with-icon" href="{bill_url}/print">
            Print (PDF)
          </a>
          <div class="advalorem">
            <table>
              <tbody class="taxing-authority"><tr>
                <th class="name">COUNTY FIRE</th>
                <td class="millage">2.8437</td>
                <td class="assessed">$295,217.00</td>
                <td class="exemption">$295,217.00</td>
                <td class="taxable">$0.00</td>
                <td class="tax">$0.00</td>
              </tr></tbody>
              <tfoot><tr>
                <td class="millage">16.0858</td>
                <td class="tax">$0.00</td>
              </tr></tfoot>
            </table>
          </div>
          <div class="nonadvalorem">
            <table><tfoot><tr>
              <th class="no-taxes">No Non-Ad Valorem assessments.</th>
            </tr></tfoot></table>
          </div>
        </div>
        <div class="content-group details parcel">
          <div class="owners">
            <div class="row address selected">
              <div class="label">Owner:</div>
              <div class="value"><div class="owner">
                ORANGE COUNTY BCC
              </div></div>
            </div>
            <div class="row address">
              <div class="label">Owner Address:</div>
              <div class="value">PO BOX 1393 ORLANDO, FL 32802-1393</div>
            </div>
            <div class="row address situs">
              <div class="label">Situs:</div>
              <div class="value">OAK LN Mount Dora 32757</div>
            </div>
          </div>
          <div class="account-details">
            <div class="row"><div class="label">Account</div>
              <div class="value">{FORMATTED_ACCOUNT}</div></div>
            <div class="row"><div class="label">Alternate Key</div>
              <div class="value">6431</div></div>
            <div class="row"><div class="label">Millage code</div>
              <div class="value">11 ORG - 11 ORG-FIRE SJWM</div></div>
            <div class="row"><div class="label">Millage rate</div>
              <div class="value">16.0858</div></div>
          </div>
          <div class="parcel-values">
            <div class="row"><div class="label">Assessed value:</div>
              <div class="value">$295,217</div></div>
          </div>
          <div class="bill-details">
            <div class="row"><div class="label">Ad valorem:</div>
              <div class="value">$0.00</div></div>
            <div class="row"><div class="label">Total tax:</div>
              <div class="value">$0.00</div></div>
          </div>
          <div class="legal">
            <div id="truncated-legal-description">
              THE S 327.69 FT OF NW1/4 OF NW1/4 OF SEC 01-20-27
            </div>
          </div>
          <div class="location">
            <div class="row"><div class="label">Block:</div>
              <div class="value">00</div></div>
            <div class="row"><div class="label">Use code:</div>
              <div class="value">1</div></div>
          </div>
          <div class="exemptions">
            <div class="row">
              <div class="label">LOCAL GOVERNMENT PROPERTY</div>
              <div class="value">$295,217</div>
            </div>
          </div>
          <a href="https://ocpaweb.ocpafl.org/propertycard/{ACCOUNT}">
            Property Appraiser Details
          </a>
        </div>
      </section>
    </body></html>
    """


def test_bill_parser_extracts_bill_parcel_values_and_tax_rows() -> None:
    token = orange.account_token_from_object_id(OBJECT_ID)[1]

    record = orange.parse_bill_detail_html(
        _bill_html(token),
        account_token=token,
        bill_uuid=BILL_UUID,
        source_url="https://example.test/bill",
    )

    assert record["bill_uuid"] == BILL_UUID
    assert record["tax_year"] == 2025
    assert record["parcel_join"]["normalized_15_digit_account"] == ACCOUNT
    assert record["alternate_key"] == "6431"
    assert record["amount_due"]["decimal"] == "0.00"
    assert record["owners"][0]["raw_name"] == "ORANGE COUNTY BCC"
    assert record["owners"][0]["title_caveat"] == "not_a_title_chain"
    assert record["situs_address"]["raw"] == "OAK LN Mount Dora 32757"
    assert record["parcel_values"]["assessed_value"]["decimal"] == "295217"
    assert record["tax_amounts"]["total_tax"]["decimal"] == "0.00"
    assert record["ad_valorem"]["rows"][0]["taxing_authority"] == (
        "COUNTY FIRE"
    )
    assert record["ad_valorem"]["total"]["millage"] == "16.0858"
    assert record["non_ad_valorem"]["empty_message"] == (
        "No Non-Ad Valorem assessments."
    )
    assert record["exemptions"][0]["amount_decimal"] == "295217"
    assert record["location"]["use_code"] == "1"
    assert "THE S 327.69 FT" in record["legal_description_raw"]
    assert record["property_appraiser_url"].startswith(
        "https://ocpaweb.ocpafl.org/"
    )


def test_historical_manifest_preserves_2020_snapshot_state() -> None:
    manifests = orange.historical_bulk_manifest()

    assert len(orange.CURRENT_HEADERS) == 38
    assert len(orange.DELINQUENT_HEADERS) == 54
    assert len(manifests) == 2
    current = manifests[0]
    assert current["release"]["effective_at"] == "2020-02-17"
    assert current["metadata"]["publication_state"] == (
        "fixed_historical_snapshot"
    )
    assert current["metadata"]["not_a_live_cadence"] is True
    assert current["metadata"]["observed_artifact"][
        "line_count_including_header"
    ] == 464_380
    assert current["metadata"]["observed_artifact"][
        "data_row_count"
    ] == 464_379
    assert current["artifacts"][0]["expected_sha256"] is None
    assert current["artifacts"][0]["metadata"]["observed_sha256"] == (
        orange.BULK_PUBLICATIONS["current"].observed_data_sha256
    )


def test_bulk_landing_parser_requires_all_four_official_links() -> None:
    html = f"""
      <a href="{orange.CURRENT_LAYOUT_URL}">Layout for Current</a>
      <a href="{orange.CURRENT_ROLL_URL}">
        Daily Real Estate Update as of 02/17/20
      </a>
      <a href="{orange.DELINQUENT_LAYOUT_URL}">Layout for Delinquent</a>
      <a href="{orange.DELINQUENT_ROLL_URL}">
        Daily Delinquent Update as of 02/17/20
      </a>
    """

    observation = orange.parse_bulk_landing_page(html)

    assert observation["label_dates"] == ["02/17/20"]
    assert observation["publication_state"] == "fixed_historical_snapshot"
    assert len(observation["artifacts"]) == 4
    with pytest.raises(orange.OrangeTaxSourceChanged):
        orange.parse_bulk_landing_page(
            f'<a href="{orange.CURRENT_ROLL_URL}">one link</a>'
        )


def _csv_zip(
    path: Path,
    *,
    member_name: str,
    headers: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(headers),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, stream.getvalue())


def _current_row(
    *,
    tax_summary_id: str,
    owner: str = "LEWIS THOMAS M",
) -> dict[str, str]:
    row = dict.fromkeys(orange.CURRENT_HEADERS, "")
    row.update(
        {
            "ParcelNumber": ACCOUNT,
            "Folio": "6431",
            "TaxYear": "2019",
            "MillCode": "11",
            "CityCode": "U",
            "StatusCode": "A",
            "TotalValue": "113671.00",
            "ExemptValue": "0.00",
            "TaxableValue": "113671.00",
            "OwnerName": owner,
            "Address1": "103 BRANTLEY HALL LN",
            "Address2": "LONGWOOD FL 327794801",
            "Legal1": "THE S 656.09 FT OF NW1/4",
            "IsInstallment": "0",
            "IsDelinquent": "0",
            "GrossTaxDue": "2523.55",
            "BalanceDue": "2498.31",
            "NovemberAmountDue": "2422.61",
            "DatePaid": "01/01/1900",
            "AmountPaid": "0.00",
            "IsBankrupt": "0",
            "IsLitigationPending": "0",
            "IsFloridaTaking": "0",
            "IsLeasehold": "0",
            "TaxSummaryId": tax_summary_id,
        }
    )
    return row


def _delinquent_row() -> dict[str, str]:
    row = dict.fromkeys(orange.DELINQUENT_HEADERS, "")
    row.update(
        {
            "Cert Year": "2015",
            "Cert No": "0019206",
            "Cert Seq": "0",
            "Parcel No": "062330626202020",
            "Tax Deed Year": "2014",
            "Tax Deed No": "0019687",
            "Tax Deed Seq": "0",
            "Tax Deed Status": "Redeemed",
            "Tax Year": "2014",
            "Status Code": "Redeemed",
            "Gross Taxes": "884.82",
            "Certificate Face Value": "987.94",
            "Total Value": "36077.00",
            "Exempt Value": "0.00",
            "Taxable Value": "36077.00",
            "Owner1": "DEBENEDETTO JANICE",
            "MailingAddress1": "4B FLAMINGO TER",
            "MailingAddress2": "MANCHESTER NJ 08759-5336",
            "Legal Description": "ORANGE TREE VILLAGE NO 1",
            "Payoff Date": "02/17/2020",
            "Payoff Amount Due": "0.00",
            "Payoff Interest": "0.00",
            "Payoff Amount Due Next Month": "0.00",
            "Payoff Interest Next Month": "0.00",
            "Payment Code": "R",
            "Bidder Number": "2550443",
            "Buyer Name1": "CAZ CREEK FUNDING I LLC",
            "Cert Issue Date": "05/31/2015",
            "Tax Deed Application Date": "05/12/2016",
            "Tax Deed Redemption Date": "11/10/2016",
            "Property Use Code": "400",
            "Situs Street Number": "2796",
            "Situs Street Name": "CURRY FORD",
            "Situs Street Type": "RD",
            "Situs City": "ORLANDO",
            "Situs ZipCode": "32806",
            "TaxSummaryID": "4828777",
        }
    )
    return row


def test_current_bulk_inspect_and_search_preserve_occurrence_identity(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "TaxPaymentTape.zip"
    _csv_zip(
        artifact,
        member_name="TaxPaymentTape.txt",
        headers=orange.CURRENT_HEADERS,
        rows=[
            _current_row(tax_summary_id="7049108"),
            _current_row(
                tax_summary_id="7049109",
                owner="LEWIS THOMAS M JR",
            ),
        ],
    )

    inspection = orange.inspect_bulk_artifact(
        artifact,
        dataset="current",
    )
    criteria = orange.BulkSearchCriteria(account=FORMATTED_ACCOUNT)
    first, cursor, metadata = orange.search_bulk_artifact(
        artifact,
        dataset="current",
        criteria=criteria,
        limit=1,
    )

    assert inspection["row_count"] == 2
    assert inspection["tax_year_counts"] == {"2019": 2}
    assert inspection["matches_observed_artifact"] is False
    assert first[0]["parcel_join"]["normalized_15_digit_account"] == ACCOUNT
    assert first[0]["tax_summary_id"] == "7049108"
    assert first[0]["payment"]["date"]["iso"] is None
    assert first[0]["identity_contract"]["row_occurrence"][
        "source_row_number"
    ] == 2
    assert metadata["schema_fingerprint"] == (
        orange.BULK_PUBLICATIONS["current"].schema_fingerprint
    )
    assert cursor is not None

    second, next_cursor, _ = orange.search_bulk_artifact(
        artifact,
        dataset="current",
        criteria=criteria,
        limit=1,
        cursor=cursor,
    )
    assert second[0]["tax_summary_id"] == "7049109"
    assert second[0]["identity_contract"]["row_occurrence"][
        "occurrence_id"
    ] != first[0]["identity_contract"]["row_occurrence"]["occurrence_id"]
    assert next_cursor is None


def test_bulk_cursor_binds_criteria_artifact_and_schema(tmp_path: Path) -> None:
    first_artifact = tmp_path / "one.zip"
    second_artifact = tmp_path / "two.zip"
    _csv_zip(
        first_artifact,
        member_name="TaxPaymentTape.txt",
        headers=orange.CURRENT_HEADERS,
        rows=[
            _current_row(tax_summary_id="1"),
            _current_row(tax_summary_id="2"),
        ],
    )
    _csv_zip(
        second_artifact,
        member_name="TaxPaymentTape.txt",
        headers=orange.CURRENT_HEADERS,
        rows=[
            _current_row(tax_summary_id="1"),
            _current_row(tax_summary_id="changed"),
        ],
    )
    criteria = orange.BulkSearchCriteria(account=ACCOUNT)
    _, cursor, _ = orange.search_bulk_artifact(
        first_artifact,
        dataset="current",
        criteria=criteria,
        limit=1,
    )
    assert cursor is not None

    with pytest.raises(orange.OrangeTaxQueryError, match="different"):
        orange.search_bulk_artifact(
            first_artifact,
            dataset="current",
            criteria=orange.BulkSearchCriteria(owner="LEWIS"),
            limit=1,
            cursor=cursor,
        )
    with pytest.raises(orange.OrangeTaxQueryError, match="different"):
        orange.search_bulk_artifact(
            second_artifact,
            dataset="current",
            criteria=criteria,
            limit=1,
            cursor=cursor,
        )


def test_delinquent_bulk_parser_keeps_certificate_deed_buyer_and_row_ids(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "DelinquentRealEstateTaxData.zip"
    _csv_zip(
        artifact,
        member_name="DelinquentRealEstateTaxData.csv",
        headers=orange.DELINQUENT_HEADERS,
        rows=[_delinquent_row()],
    )

    records, cursor, _ = orange.search_bulk_artifact(
        artifact,
        dataset="delinquent",
        criteria=orange.BulkSearchCriteria(certificate="0019206"),
    )

    assert cursor is None
    assert len(records) == 1
    record = records[0]
    assert record["parcel_join"]["normalized_15_digit_account"] == (
        "062330626202020"
    )
    assert record["certificate"]["number"] == "0019206"
    assert record["certificate"]["face_value"]["decimal"] == "987.94"
    assert record["tax_deed"]["number"] == "0019687"
    assert record["tax_deed"]["status"] == "Redeemed"
    assert record["buyers"][0]["raw_name"] == "CAZ CREEK FUNDING I LLC"
    assert record["buyers"][0]["title_caveat"] == "not_a_title_chain"
    assert record["tax_summary_id"] == "4828777"
    assert record["identity_contract"]["row_occurrence"][
        "source_row_number"
    ] == 2


def test_bulk_header_mismatch_is_source_changed(tmp_path: Path) -> None:
    artifact = tmp_path / "bad.zip"
    headers = tuple(
        "ChangedParcel" if header == "ParcelNumber" else header
        for header in orange.CURRENT_HEADERS
    )
    row = dict.fromkeys(headers, "")
    _csv_zip(
        artifact,
        member_name="TaxPaymentTape.txt",
        headers=headers,
        rows=[row],
    )

    with pytest.raises(orange.OrangeTaxSourceChanged, match="header changed"):
        orange.inspect_bulk_artifact(artifact, dataset="current")


def test_cli_exposes_current_and_historical_operations() -> None:
    parser = orange.build_parser()

    assert parser.parse_args(["sources"]).command == "sources"
    assert parser.parse_args(["search", ACCOUNT]).limit == 15
    assert parser.parse_args(["account", ACCOUNT]).command == "account"
    assert parser.parse_args(["history", ACCOUNT]).command == "history"
    assert parser.parse_args(
        ["bill", ACCOUNT, BILL_UUID]
    ).command == "bill"
    manifest = parser.parse_args(["bulk-manifest"])
    assert manifest.command == "bulk-manifest"
    assert manifest.verify_page is False
    assert parser.parse_args(
        ["bulk-probe", "current"]
    ).artifact_role == "data"
    assert parser.parse_args(
        ["bulk-inspect", "delinquent", "/tmp/example.zip"]
    ).dataset == "delinquent"


def test_sources_result_states_bulk_is_historical() -> None:
    args = orange.build_parser().parse_args(["sources"])

    result = orange.execute(args)
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["historical_bulk"]["publication_state"] == (
        "fixed_historical_snapshot"
    )
    assert record["current_portal"]["search"] is True
