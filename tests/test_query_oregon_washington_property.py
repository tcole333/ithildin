from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_washington_property as washco
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RestrictedHTTPError, RetryPolicy


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_washington_property"
)
LIVE = os.environ.get("LIVE_PUBLIC_RECORDS") == "1"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads(fixture_text(name))


def parse_args(*values: str) -> Any:
    return washco.build_parser().parse_args(list(values))


def artifact(
    *,
    url: str = "https://example.test/source",
    content: bytes = b"{}",
    content_type: str = "application/json",
) -> washco.ResponseArtifact:
    return washco.ResponseArtifact(
        content=content,
        source_url=url,
        headers={
            "content-type": content_type,
            "content-length": str(len(content)),
        },
        status_code=200,
    )


class FixtureSurveyClient:
    def survey_search(
        self,
        kind: washco.SurveyKind,
        filters: dict[str, str],
    ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
        assert kind.key == "survey"
        assert filters
        return fixture_json("survey_search.json"), artifact()

    def survey_detail(
        self,
        kind: washco.SurveyKind,
        uid: str,
    ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
        name = "plat_detail.json" if kind.key == "plat" else "survey_detail.json"
        return fixture_json(name), artifact(url=f"https://example.test/{uid}")


class FixtureArcGISClient:
    def __init__(self, page_name: str) -> None:
        self.page_name = page_name
        self.queries: list[dict[str, Any]] = []

    def layer_metadata(self, config: washco.ArcGISLayer) -> dict[str, Any]:
        assert config.key == "taxlots"
        return fixture_json("taxlot_layer.json")

    def arcgis_query(
        self,
        config: washco.ArcGISLayer,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
        self.queries.append(dict(params))
        if params.get("returnCountOnly") == "true":
            return fixture_json("arcgis_count.json"), artifact()
        return fixture_json(self.page_name), artifact(
            url=f"{config.layer_url}/query"
        )


class FixtureIntermapClient:
    def text(self, url: str, **_kwargs: Any) -> tuple[str, washco.ResponseArtifact]:
        html = fixture_text("intermap_assessment.html")
        return html, artifact(
            url=url,
            content=html.encode(),
            content_type="text/html",
        )


class FakeResponse:
    def __init__(
        self,
        *,
        content: bytes,
        url: str = "https://example.test/result",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = headers or {
            "content-type": "application/json",
            "content-length": str(len(content)),
        }
        self.chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size: int) -> Any:
        del chunk_size
        if self.chunks is not None:
            yield from self.chunks
            return
        yield self.content

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


def client_for(session: FakeSession) -> washco.WashingtonClient:
    return washco.WashingtonClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )


def test_sources_keep_components_lineage_and_alternatives_distinct() -> None:
    payload = washco.source_manifest()
    source_ids = {item["source_id"] for item in payload["sources"]}

    assert source_ids == set(washco.SOURCES)
    assert washco.SURVEY_API_SOURCE_ID != washco.SURVEY_MAP_SOURCE_ID
    assert washco.TAXLOT_SOURCE_ID != washco.PORTLAND_REGIONAL_SOURCE_ID
    assert (
        payload["arcgis_components"]["taxlots"]["sort_tuple"]
        == ["TLNO", "OBJECTID"]
    )
    taxlot_source = next(
        item
        for item in payload["sources"]
        if item["source_id"] == washco.TAXLOT_SOURCE_ID
    )
    assert "Not all tax lots" in taxlot_source["metadata"]["publisher_note"]
    alternatives = {
        item["name"] for item in payload["complementary_sources"]
    }
    assert "Washington County Recording and Copy Requests" in alternatives
    assert "Washington County Accela Citizen Access" in alternatives


def test_survey_api_cursor_uses_complete_numeric_sort_tuple() -> None:
    client = FixtureSurveyClient()
    first = washco.execute(
        parse_args(
            "survey-search",
            "survey",
            "SURVEYOR",
            "--field",
            "surveyorname",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )

    assert first.status == ResultStatus.OK
    assert [
        row["native_ids"]["Surveynumber"] for row in first.to_dict()["records"]
    ] == [9, 10]
    assert first.next_cursor

    second = washco.execute(
        parse_args(
            "survey-search",
            "survey",
            "SURVEYOR",
            "--field",
            "surveyorname",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert [
        row["native_ids"]["Surveynumber"] for row in second.to_dict()["records"]
    ] == [35242]
    assert second.next_cursor is None


def test_survey_api_cursor_rejects_different_query() -> None:
    client = FixtureSurveyClient()
    first = washco.execute(
        parse_args("survey-search", "survey", "ONE", "--limit", "1"),
        client=client,
        log_results=False,
    )
    second = washco.execute(
        parse_args(
            "survey-search",
            "survey",
            "TWO",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert second.status == ResultStatus.SOURCE_CHANGED
    assert second.errors[0].code == "cursor_query_mismatch"


def test_omitted_limit_returns_complete_survey_response() -> None:
    args = parse_args(
        "survey-search",
        "survey",
        "SURVEYOR",
        "--field",
        "surveyorname",
    )
    result = washco.execute(
        args,
        client=FixtureSurveyClient(),
        log_results=False,
    )

    assert args.limit is None
    assert [
        row["native_ids"]["Surveynumber"] for row in result.to_dict()["records"]
    ] == [9, 10, 35242]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None


def test_survey_detail_preserves_ids_dates_and_resolves_official_pdf() -> None:
    result = washco.execute(
        parse_args("survey-detail", "survey", "35242"),
        client=FixtureSurveyClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["native_ids"]["Surveynumber"] == 35242
    assert record["normalized_dates"]["Filed"].startswith("2026-07-27")
    assert record["native_fields"]["Client"] == "HARVEY BUSINESS TRUST"
    assert record["resolved_documents"][0]["resolved_url"].endswith(
        "/survey/surveys/40000/35242.pdf"
    )

    plat = washco.execute(
        parse_args("survey-detail", "plat", "2026-021"),
        client=FixtureSurveyClient(),
        log_results=False,
    ).to_dict()["records"][0]
    assert plat["native_ids"]["DocNumber"] == "2026028787"
    assert plat["resolved_documents"][0]["resolved_url"].endswith(
        "/survey/plats/2026-021.pdf"
    )


def test_survey_document_uses_browser_headers_streams_and_closes(
    tmp_path: Path,
) -> None:
    detail = fixture_text("survey_detail.json").encode()
    pdf = b"%PDF-1.7\nfixture survey\n%%EOF\n"
    responses = [
        FakeResponse(content=detail),
        FakeResponse(
            content=pdf,
            headers={
                "content-type": "application/pdf",
                "content-length": str(len(pdf)),
            },
        ),
    ]
    session = FakeSession(responses)
    destination = tmp_path / "35242.pdf"

    result = washco.execute(
        parse_args(
            "survey-document",
            "survey",
            "35242",
            "--destination",
            str(destination),
        ),
        client=client_for(session),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == pdf
    assert record["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert session.calls[0]["headers"]["Origin"].endswith(
        "washingtoncountyor.gov"
    )
    assert session.calls[0]["headers"]["Referer"] == washco.SURVEY_APP_URL
    assert all(response.closed for response in responses)


def test_bounded_transport_closes_non_2xx_and_maps_access_state() -> None:
    response = FakeResponse(
        content=b"forbidden",
        status_code=403,
        headers={"content-type": "text/plain", "content-length": "9"},
    )
    client = client_for(FakeSession([response]))

    with pytest.raises(RestrictedHTTPError):
        client.request(
            "GET",
            "https://example.test/restricted",
            maximum_bytes=100,
        )
    assert response.closed is True


def test_bounded_transport_rejects_declared_and_observed_overflow() -> None:
    declared = FakeResponse(
        content=b"",
        headers={"content-type": "application/pdf", "content-length": "101"},
    )
    with pytest.raises(washco.ResponseTooLargeError):
        client_for(FakeSession([declared])).request(
            "GET",
            "https://example.test/large",
            maximum_bytes=100,
        )
    assert declared.closed is True

    streamed = FakeResponse(
        content=b"",
        headers={"content-type": "application/pdf"},
        chunks=[b"a" * 60, b"b" * 60],
    )
    with pytest.raises(washco.ResponseTooLargeError):
        client_for(FakeSession([streamed])).request(
            "GET",
            "https://example.test/streamed",
            maximum_bytes=100,
        )
    assert streamed.closed is True


def test_arcgis_query_preserves_native_ids_crs_geometry_and_full_cursor() -> None:
    client = FixtureArcGISClient("arcgis_page_one.json")
    first = washco.execute(
        parse_args(
            "taxlots",
            "--where",
            "1=1",
            "--limit",
            "2",
            "--geometry",
        ),
        client=client,
        log_results=False,
    )
    payload = first.to_dict()

    assert first.status == ResultStatus.OK
    assert payload["records"][0]["native_ids"] == {
        "TLNO": "2N2330002700",
        "MAPNO": "2N23300",
        "TLNO5": 2700,
        "OBJECTID": 100,
    }
    assert payload["records"][0]["geometry_representation"] == {
        "included": True,
        "source_crs": "EPSG:2913",
        "returned_crs": {"wkid": 4326, "latestWkid": 4326},
    }
    assert first.next_cursor
    assert client.queries[1]["orderByFields"] == "TLNO ASC,OBJECTID ASC"

    second_client = FixtureArcGISClient("arcgis_page_two.json")
    second = washco.execute(
        parse_args(
            "taxlots",
            "--where",
            "1=1",
            "--limit",
            "2",
            "--geometry",
            "--cursor",
            first.next_cursor,
        ),
        client=second_client,
        log_results=False,
    )
    assert [
        row["native_ids"]["OBJECTID"] for row in second.to_dict()["records"]
    ] == [102]
    anchored_where = second_client.queries[1]["where"]
    assert "TLNO > '2N2330002701'" in anchored_where
    assert "TLNO = '2N2330002701' AND OBJECTID > 101" in anchored_where


def test_omitted_limit_exhausts_arcgis_keyset_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExhaustiveArcGISClient(FixtureArcGISClient):
        def __init__(self) -> None:
            super().__init__("arcgis_page_one.json")
            self.page_index = 0

        def arcgis_query(
            self,
            config: washco.ArcGISLayer,
            params: dict[str, Any],
        ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
            self.queries.append(dict(params))
            if params.get("returnCountOnly") == "true":
                return {"count": 3}, artifact()
            payload = fixture_json("arcgis_page_one.json")
            pages = (payload["features"][:2], payload["features"][2:])
            payload["features"] = pages[self.page_index]
            self.page_index += 1
            return payload, artifact(url=f"{config.layer_url}/query")

    monkeypatch.setattr(washco, "DEFAULT_PAGE_SIZE", 2)
    client = ExhaustiveArcGISClient()
    args = parse_args("taxlots", "--where", "1=1")
    result = washco.execute(args, client=client, log_results=False)

    assert args.limit is None
    assert [
        row["native_ids"]["OBJECTID"] for row in result.to_dict()["records"]
    ] == [100, 101, 102]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None
    assert [query["resultRecordCount"] for query in client.queries[1:]] == [2, 2]
    assert "TLNO > '2N2330002701'" in client.queries[2]["where"]


def test_arcgis_cursor_detects_matching_count_change() -> None:
    first = washco.execute(
        parse_args("taxlots", "--where", "1=1", "--limit", "2"),
        client=FixtureArcGISClient("arcgis_page_one.json"),
        log_results=False,
    )

    class ChangedCountClient(FixtureArcGISClient):
        def arcgis_query(
            self,
            config: washco.ArcGISLayer,
            params: dict[str, Any],
        ) -> tuple[dict[str, Any], washco.ResponseArtifact]:
            if params.get("returnCountOnly") == "true":
                return {"count": 4}, artifact()
            return super().arcgis_query(config, params)

    second = washco.execute(
        parse_args(
            "taxlots",
            "--where",
            "1=1",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=ChangedCountClient("arcgis_page_two.json"),
        log_results=False,
    )
    assert second.status == ResultStatus.SOURCE_CHANGED
    assert second.errors[0].code == "cursor_snapshot_changed"


def test_arcgis_raw_where_and_exact_join_are_retained() -> None:
    client = FixtureArcGISClient("arcgis_page_one.json")
    result = washco.execute(
        parse_args(
            "taxlots",
            "2N2330002700",
            "--field",
            "TLNO",
            "--match",
            "exact",
            "--where",
            "MAPNO = '2N23300'",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    count_where = client.queries[0]["where"]
    assert "MAPNO = '2N23300'" in count_where
    assert "UPPER(TLNO) = UPPER('2N2330002700')" in count_where
    joins = result.to_dict()["records"][0]["join_candidates"]
    assert joins[washco.INTERMAP_SOURCE_ID]["TLNO"] == "2N2330002700"


def test_intermap_parser_preserves_native_html_tables_links_and_ids() -> None:
    result = washco.execute(
        parse_args(
            "intermap",
            "2N2330002700",
            "--report",
            "assessment",
            "--include-raw-html",
        ),
        client=FixtureIntermapClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["native_ids"] == {
        "IDValue": "2N2330002700",
        "TLNO": "2N2330002700",
        "account": "R2069997",
    }
    representation = record["native_representation"]
    assert representation["raw_html"].startswith("<!doctype html>")
    assert len(representation["html_sha256"]) == 64
    tax_map_link = next(
        link for link in representation["links"] if link["text"] == "Tax maps"
    )
    assert "IDValue=2N2330002700" in tax_map_link["resolved_url"]


def test_tax_account_parser_preserves_statement_and_payment_ids() -> None:
    html = fixture_text("tax_account.html")
    record = washco.parse_tax_account(
        html,
        source_url=(
            f"{washco.TAX_BASE_URL}/Property-Detail/"
            "PropertyQuickRefID/R2069997"
        ),
        requested_account="R2069997",
    )

    assert record["native_ids"]["PropertyQuickRefID"] == "R2069997"
    assert record["owner_name"] == "CRABB, JOHN & DAVIS, TASSY LEI"
    assert record["displayed_real_market_value"] == "$2,300,360"
    current = record["tax_statements"][0]
    assert current["PropertyID"] == "137120"
    assert current["PartyID"] == "782035"
    assert current["retrieval_mode"] == "same_session_post_filename_then_pdf"
    historical = record["tax_statements"][1]
    assert historical["resolved_url"].endswith(
        "/TaxStatements/2019/R2069997.pdf"
    )
    assert record["payment_receipts"][0]["transactionID"] == "4441216"


def test_generated_tax_statement_keeps_one_session_and_closes_all(
    tmp_path: Path,
) -> None:
    html = fixture_text("tax_account.html").encode()
    filename = b'"TaxStatement-137120-2025-11-15-2025.pdf"'
    pdf = b"%PDF-1.7\nfixture tax statement\n%%EOF\n"
    responses = [
        FakeResponse(
            content=html,
            headers={
                "content-type": "text/html",
                "content-length": str(len(html)),
            },
        ),
        FakeResponse(content=filename),
        FakeResponse(
            content=pdf,
            headers={
                "content-type": "application/pdf",
                "content-length": str(len(pdf)),
            },
        ),
    ]
    session = FakeSession(responses)
    destination = tmp_path / "statement.pdf"

    result = washco.execute(
        parse_args(
            "tax-statement",
            "R2069997",
            "2025",
            "--destination",
            str(destination),
        ),
        client=client_for(session),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["retrieval_mode"] == "same_session_post_filename_then_pdf"
    assert record["native_ids"]["PropertyID"] == "137120"
    assert record["native_ids"]["PartyID"] == "782035"
    assert destination.read_bytes() == pdf
    assert [call["method"] for call in session.calls] == ["GET", "POST", "GET"]
    assert session.calls[1]["data"]["EffectiveDate"] == "11-15-2025"
    assert all(response.closed for response in responses)


def test_historical_tax_statement_uses_direct_published_pdf(
    tmp_path: Path,
) -> None:
    html = fixture_text("tax_account.html").encode()
    pdf = b"%PDF-1.6\nhistorical fixture\n%%EOF\n"
    responses = [
        FakeResponse(
            content=html,
            headers={
                "content-type": "text/html",
                "content-length": str(len(html)),
            },
        ),
        FakeResponse(
            content=pdf,
            headers={
                "content-type": "application/pdf",
                "content-length": str(len(pdf)),
            },
        ),
    ]
    session = FakeSession(responses)

    result = washco.execute(
        parse_args(
            "tax-statement",
            "R2069997",
            "2019",
            "--destination",
            str(tmp_path / "2019.pdf"),
        ),
        client=client_for(session),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["retrieval_mode"] == "direct_historical_pdf"
    assert [call["method"] for call in session.calls] == ["GET", "GET"]
    assert session.calls[1]["url"].endswith(
        "/TaxStatements/2019/R2069997.pdf"
    )


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_survey_search_and_detail() -> None:
    with washco.WashingtonClient(minimum_interval=0.25) as client:
        search = washco.execute(
            parse_args("survey-search", "survey", washco.PROBE_SURVEY),
            client=client,
            log_results=False,
        )
        detail = washco.execute(
            parse_args("survey-detail", "survey", washco.PROBE_SURVEY),
            client=client,
            log_results=False,
        )
        plat = washco.execute(
            parse_args("survey-detail", "plat", washco.PROBE_PLAT),
            client=client,
            log_results=False,
        )
        taxlot = washco.execute(
            parse_args("survey-detail", "taxlot", washco.PROBE_TAXLOT),
            client=client,
            log_results=False,
        )

    assert search.status == ResultStatus.OK
    assert search.to_dict()["records"][0]["native_ids"]["Surveynumber"] == 35242
    record = detail.to_dict()["records"][0]
    assert record["native_ids"]["Surveynumber"] == 35242
    assert record["resolved_documents"][0]["native_filename"] == "35242.pdf"
    plat_record = plat.to_dict()["records"][0]
    assert plat_record["native_ids"]["Platname"] == washco.PROBE_PLAT
    assert plat_record["native_ids"]["DocNumber"] == "2026028787"
    assert (
        taxlot.to_dict()["records"][0]["native_ids"]["ACCOUNT"]
        == washco.PROBE_ACCOUNT
    )


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_all_arcgis_component_contracts_publish_cursor_and_id_fields() -> None:
    with washco.WashingtonClient(minimum_interval=0.1) as client:
        for config in washco.ARCGIS_LAYERS.values():
            metadata = client.layer_metadata(config)
            published = {
                str(field["name"])
                for field in metadata["fields"]
                if isinstance(field, dict) and field.get("name")
            }
            assert set(config.sort_fields).issubset(published), config.key
            assert set(config.native_id_fields).issubset(published), config.key


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_taxlot_and_situs_exact_join() -> None:
    with washco.WashingtonClient(minimum_interval=0.25) as client:
        taxlot = washco.execute(
            parse_args(
                "taxlots",
                washco.PROBE_TAXLOT,
                "--field",
                "TLNO",
            ),
            client=client,
            log_results=False,
        )
        situs_args = parse_args(
            "situs",
            washco.PROBE_TAXLOT,
            "--field",
            "TAXLOT",
        )
        situs = washco.execute(situs_args, client=client, log_results=False)

    assert taxlot.status == ResultStatus.OK
    assert taxlot.to_dict()["records"][0]["native_ids"]["TLNO"] == washco.PROBE_TAXLOT
    assert situs.status == ResultStatus.OK
    assert (
        situs.to_dict()["records"][0]["native_fields"]["TAXLOT"]
        == washco.PROBE_TAXLOT
    )
    assert (
        situs.to_dict()["records"][0]["join_candidates"][washco.TAX_SOURCE_ID][
            "derived_property_quick_ref_candidate"
        ]
        == washco.PROBE_ACCOUNT
    )


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_intermap_and_tax_account() -> None:
    with washco.WashingtonClient(minimum_interval=0.25) as client:
        intermap = washco.execute(
            parse_args(
                "intermap",
                washco.PROBE_TAXLOT,
                "--report",
                "assessment",
            ),
            client=client,
            log_results=False,
        )
        account = washco.execute(
            parse_args("tax-account", washco.PROBE_ACCOUNT),
            client=client,
            log_results=False,
        )

    assert intermap.status == ResultStatus.OK
    assert (
        intermap.to_dict()["records"][0]["native_ids"]["account"]
        == washco.PROBE_ACCOUNT
    )
    assert account.status == ResultStatus.OK
    assert (
        account.to_dict()["records"][0]["native_ids"]["PropertyQuickRefID"]
        == washco.PROBE_ACCOUNT
    )


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_survey_pdf_is_bounded_and_attributable(tmp_path: Path) -> None:
    destination = tmp_path / "35242.pdf"
    with washco.WashingtonClient(minimum_interval=0.25) as client:
        result = washco.execute(
            parse_args(
                "survey-document",
                "survey",
                washco.PROBE_SURVEY,
                "--destination",
                str(destination),
            ),
            client=client,
            log_results=False,
        )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["byte_length"] == 7_889_301
    assert (
        record["sha256"]
        == "685f2c48336e90ce76c0dd11557e26920836c6272d353872377b9d6c09728672"
    )
    assert destination.read_bytes().startswith(b"%PDF")


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_plat_pdf_is_bounded_and_attributable(tmp_path: Path) -> None:
    destination = tmp_path / "2026-021.pdf"
    with washco.WashingtonClient(minimum_interval=0.25) as client:
        result = washco.execute(
            parse_args(
                "survey-document",
                "plat",
                washco.PROBE_PLAT,
                "--destination",
                str(destination),
            ),
            client=client,
            log_results=False,
        )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["native_ids"]["DocNumber"] == "2026028787"
    assert record["byte_length"] == 4_102_330
    assert (
        record["sha256"]
        == "df5a663427ed4f6f1a83f6fb3e2635325c1e048c71270413a7fe6f5574183ea8"
    )
    assert destination.read_bytes().startswith(b"%PDF")


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_generated_tax_statement_preserves_session_lineage(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "R2069997-2025.pdf"
    with washco.WashingtonClient(minimum_interval=0.25) as client:
        result = washco.execute(
            parse_args(
                "tax-statement",
                washco.PROBE_ACCOUNT,
                "2025",
                "--destination",
                str(destination),
            ),
            client=client,
            log_results=False,
        )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["retrieval_mode"] == "same_session_post_filename_then_pdf"
    assert record["byte_length"] == 107_447
    assert (
        record["sha256"]
        == "01e79a05289731827cae0a23b3bc176efc413d5358abe391ef5ef59800f6d1dc"
    )
    assert destination.read_bytes().startswith(b"%PDF")
