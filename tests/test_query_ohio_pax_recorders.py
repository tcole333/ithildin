from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from tools import query_ohio_pax_recorders as pax
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_pax_recorders"
)


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def outer_json(value: Any) -> str:
    return json.dumps(json.dumps(value))


def args_for(*values: str) -> Any:
    return pax.build_parser().parse_args(list(values))


class FakePAXClient:
    def __init__(self) -> None:
        self.config = pax.parse_search_config(
            fixture_text("delaware_search.html"),
            "https://delaware.dts-central-oh.com/PaxWorld/views/search",
        )
        batch = pax.parse_detail_response(
            outer_json(fixture_json("delaware_detail_all.json")),
            pax.DELAWARE,
            "https://delaware.dts-central-oh.com/PaxWorld/api/SearchDetail",
        )
        self.records = [dict(record) for record in batch.records]
        self.search_calls: list[tuple[int, int, Mapping[str, Any]]] = []
        self.licking_calls: list[str] = []
        self.entry_calls: list[str] = []
        self.image_calls: list[tuple[str, str]] = []
        self.document_calls: list[tuple[str, str | None]] = []
        self.closed = False
        self.missing_licking: set[str] = set()

    def close(self) -> None:
        self.closed = True

    def entry_access(self, tenant: pax.PAXTenant) -> dict[str, Any]:
        self.entry_calls.append(tenant.source_id)
        fixture = (
            "delaware_entry.html"
            if tenant is pax.DELAWARE
            else "licking_entry.html"
        )
        return pax.parse_entry_access(
            fixture_text(fixture),
            tenant.pax_root,
        )

    def bootstrap(self, tenant: pax.PAXTenant) -> pax.PAXSessionConfig:
        assert tenant is pax.DELAWARE
        return self.config

    def search_detail(
        self,
        tenant: pax.PAXTenant,
        selectors: Mapping[str, Any],
        config: pax.PAXSessionConfig,
        *,
        first_record: int,
        last_record: int,
    ) -> pax.DetailBatch:
        assert tenant is pax.DELAWARE
        assert config == self.config
        self.search_calls.append(
            (first_record, last_record, deepcopy(dict(selectors)))
        )
        selected = deepcopy(self.records)
        instrument = selectors.get("instrument")
        if instrument:
            matching = [
                record
                for record in selected
                if record["instrument_number"] == instrument
            ]
            if not matching and instrument == pax.DELAWARE_SENTINEL:
                matching = [deepcopy(selected[0])]
                matching[0]["instrument_number"] = instrument
                matching[0]["native_detail_fields"]["Instrument"] = instrument
            selected = matching
        for index, record in enumerate(selected, 1):
            record["source_position"] = index
        page = selected[first_record - 1 : last_record]
        return pax.DetailBatch(
            records=tuple(page),
            total_results=len(selected),
            filtered_results=len(selected),
            first_position=(
                int(page[0]["source_position"]) if page else None
            ),
            last_position=(
                int(page[-1]["source_position"]) if page else None
            ),
            source_url=(
                "https://delaware.dts-central-oh.com/"
                "PaxWorld/api/SearchDetail"
            ),
        )

    def licking_exact(
        self,
        tenant: pax.PAXTenant,
        instrument: str,
    ) -> dict[str, Any] | None:
        assert tenant is pax.LICKING
        self.licking_calls.append(instrument)
        if instrument in self.missing_licking:
            return None
        record = pax.parse_licking_exact(
            fixture_text("licking_exact.html"),
            (
                "https://apps.lickingcounty.gov/recorder/record-search/"
                f"?instrument={pax.LICKING_SENTINEL}"
            ),
            expected_instrument=pax.LICKING_SENTINEL,
        )
        assert record is not None
        if instrument != pax.LICKING_SENTINEL:
            record = deepcopy(record)
            record["instrument_number"] = instrument
            record["source_record_id"] = instrument
        return record

    def image_detail(
        self,
        tenant: pax.PAXTenant,
        config: pax.PAXSessionConfig,
        *,
        reference_id: str,
        instrument: str,
    ) -> dict[str, Any]:
        assert tenant is pax.DELAWARE
        assert config == self.config
        self.image_calls.append((reference_id, instrument))
        payload = fixture_json("delaware_image_detail.json")
        payload["InstrumentNumber"] = instrument
        return pax.parse_image_detail(
            outer_json(payload),
            (
                "https://delaware.dts-central-oh.com/"
                f"PaxWorld/api/ImageDetail/{reference_id}"
            ),
            expected_instrument=instrument,
            reference_id=reference_id,
        )

    def document(
        self,
        tenant: pax.PAXTenant,
        instrument: str,
        *,
        config: pax.PAXSessionConfig | None = None,
        reference_id: str | None = None,
    ) -> pax.BinaryDocument:
        if tenant is pax.DELAWARE:
            assert config == self.config
            assert reference_id is not None
        self.document_calls.append((instrument, reference_id))
        content = b"%PDF-1.7\nfixture recorder document\n%%EOF\n"
        return pax.BinaryDocument(
            content=content,
            source_url=(
                f"https://{tenant.host}/fixture-document?"
                f"instrument={instrument}"
            ),
            headers={
                "content-type": (
                    "application/octet-stream"
                    if tenant is pax.DELAWARE
                    else "application/pdf"
                ),
                "content-length": str(len(content)),
            },
        )


def test_source_graph_keeps_family_and_county_capabilities_distinct() -> None:
    payload = pax.sources_payload()
    by_id = {
        source["source_id"]: source for source in payload["sources"]
    }

    assert payload["platform_family"] == "dts_paxworld"
    assert set(by_id) == {
        pax.DELAWARE_SOURCE_ID,
        pax.LICKING_SOURCE_ID,
    }
    assert by_id[pax.DELAWARE_SOURCE_ID]["metadata"][
        "anonymous_discovery"
    ] is True
    assert by_id[pax.DELAWARE_SOURCE_ID]["metadata"]["record_identity"] == {
        "stable_key": "InstrumentReferenceId",
        "record_identity_source_id": pax.DELAWARE_SOURCE_ID,
    }
    assert by_id[pax.LICKING_SOURCE_ID]["metadata"][
        "anonymous_discovery"
    ] is False
    assert by_id[pax.LICKING_SOURCE_ID]["metadata"]["record_identity"] == {
        "stable_key": "instrument_number",
        "record_identity_source_id": pax.LICKING_SOURCE_ID,
        "alternate_representation_source_id": pax.LICKING_DETAIL_SOURCE_ID,
    }
    exact_representation = payload["alternate_representations"][0]
    assert exact_representation["source_id"] == pax.LICKING_DETAIL_SOURCE_ID
    assert (
        exact_representation["record_identity_source_id"]
        == pax.LICKING_SOURCE_ID
    )
    assert exact_representation["independent_corroboration"] is False
    exact_relationship = next(
        item
        for item in payload["source_relationships"]
        if item["left"] == pax.LICKING_DETAIL_SOURCE_ID
    )
    assert (
        exact_relationship["relationship"]
        == "alternate_representation_same_instrument_identity"
    )
    assert exact_relationship["independent_corroboration"] is False
    licking_complements = by_id[pax.LICKING_SOURCE_ID]["metadata"][
        "complements"
    ]
    archive = next(
        item
        for item in licking_complements
        if item["relationship"]
        == "historical_recorder_archive_and_request_route"
    )
    assert archive["coverage"] == {
        "deeds": "1803-1918",
        "mortgages": "1851-1941",
    }
    assert payload["family_boundary"]["tenant_specific"]
    assert any(
        item["learning"] == "verify_indexed_routes_live"
        and "404" in item["evidence"]
        for item in payload["process_learnings"]
    )


def test_entry_pages_publish_different_login_requirements() -> None:
    delaware = pax.parse_entry_access(
        fixture_text("delaware_entry.html"),
        pax.DELAWARE.pax_root,
    )
    licking = pax.parse_entry_access(
        fixture_text("licking_entry.html"),
        pax.LICKING.pax_root,
    )

    assert delaware["login_required"] is False
    assert licking["login_required"] is True
    assert delaware["hidden_fields"]["__VIEWSTATE"] == "fixture-viewstate"
    assert delaware["form_action"] == pax.DELAWARE.pax_root


def test_search_page_config_keeps_sessions_transport_only() -> None:
    config = pax.parse_search_config(
        fixture_text("delaware_search.html"),
        "https://delaware.dts-central-oh.com/PaxWorld/views/search",
    )

    assert config.rows_per_page == 2
    assert config.data_current_through == "2026-07-19"
    assert config.version == "2025.7.7.1"
    assert config.is_guest is True
    assert config.freedom is True
    assert config.session_id not in pax.sources_payload()["sources"][0]


def test_detail_response_uses_reference_identity_not_party_rows() -> None:
    batch = pax.parse_detail_response(
        outer_json(fixture_json("delaware_detail_all.json")),
        pax.DELAWARE,
        "https://delaware.dts-central-oh.com/PaxWorld/api/SearchDetail",
    )

    assert batch.total_results == 3
    assert [record["instrument_reference_id"] for record in batch.records] == [
        "1001",
        "1000",
        "999",
    ]
    first = batch.records[0]
    assert first["instrument_number"] == "202600000003"
    assert first["source_position"] == 1
    assert first["grantors"] == ["SMITH, ALEX", "SMITH, JAMIE"]
    assert first["grantees"] == ["EXAMPLE CREDIT UNION"]
    assert first["consideration_amount"] == "150000.00"
    assert first["recorded_at_iso"] == "2026-07-17T16:46:00"
    assert first["stable_identity"]["primary"] == "instrument_reference_id"
    assert "session" not in first["stable_identity"]


def test_image_metadata_keeps_document_access_separate() -> None:
    record = pax.parse_image_detail(
        outer_json(fixture_json("delaware_image_detail.json")),
        "https://delaware.dts-central-oh.com/PaxWorld/api/ImageDetail/fixture",
        expected_instrument="202600000003",
        reference_id="1001",
    )

    assert record["instrument_reference_id"] == "1001"
    assert record["instrument_number"] == "202600000003"
    assert record["has_image"] is True
    assert record["page_count"] == 14
    assert record["source_entitlement_owned"] is True


def test_licking_exact_detail_and_authoritative_no_result() -> None:
    record = pax.parse_licking_exact(
        fixture_text("licking_exact.html"),
        (
            "https://apps.lickingcounty.gov/recorder/record-search/"
            "?instrument=202504110006201"
        ),
        expected_instrument="202504110006201",
    )
    missing = pax.parse_licking_exact(
        fixture_text("licking_no_results.html"),
        (
            "https://apps.lickingcounty.gov/recorder/record-search/"
            "?instrument=not-a-local-shape"
        ),
        expected_instrument="not-a-local-shape",
    )

    assert record is not None
    assert record["instrument_number"] == "202504110006201"
    assert record["source_id"] == pax.LICKING_SOURCE_ID
    assert record["record_identity_source_id"] == pax.LICKING_SOURCE_ID
    assert (
        record["representation_source_id"]
        == pax.LICKING_DETAIL_SOURCE_ID
    )
    assert record["recorded_at_iso"] == "2025-04-11T14:55:29"
    assert record["document_type"] == "DEED"
    assert record["grantors"] == ["BIG AMBITIONS L L C"]
    assert record["page_count"] == 13
    assert record["document"]["source_url"].endswith(
        "document?instrument=202504110006201"
    )
    assert missing is None


def test_selector_normalization_preserves_nonblank_instrument_shape() -> None:
    selectors = pax.normalize_selectors(
        {"instrument": "custom/id?value"},
    )

    assert selectors["instrument"] == "custom/id?value"
    assert selectors["search_type"] == "Instrument"


def test_native_criteria_keeps_transport_fields_out_of_record_identity() -> None:
    config = pax.parse_search_config(
        fixture_text("delaware_search.html"),
        "https://delaware.dts-central-oh.com/PaxWorld/views/search",
    )
    selectors = pax.normalize_selectors(
        {
            "name": "Example Holdings",
            "recorded_from": "2026-07-01",
            "recorded_to": "7/17/2026",
        }
    )
    criteria = pax.build_search_criteria(
        selectors,
        config,
        first_record=1,
        last_record=2,
    )

    assert criteria["NameOrganization"] == "EXAMPLE%20HOLDINGS"
    assert criteria["RecordedDate1"] == "7/1/2026"
    assert criteria["RecordedDate2"] == "7/17/2026"
    assert criteria["FirstRecordNum"] == 1
    assert criteria["LastRecordNum"] == 2
    assert criteria["SessionGuid"] == config.session_id
    assert criteria["SessionTicket"] == config.session_ticket
    assert criteria["OrderBy"] == (
        " recordeddate desc, instrumentnumber desc "
    )


def test_omitted_limit_exhausts_native_detail_total() -> None:
    client = FakePAXClient()
    result = pax.execute(
        args_for(
            "search",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--name",
            "SMITH",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert [(first, last) for first, last, _ in client.search_calls] == [
        (1, 2),
        (3, 4),
    ]
    coverage = result.records[0]["retrieval_coverage"]
    assert coverage["source_reported_total_instruments"] == 3
    assert coverage["complete_for_selected_query"] is True
    assert coverage["completion_mode"] == "source_reported_total"


def test_explicit_limit_cursor_binds_query_total_and_boundary() -> None:
    client = FakePAXClient()
    first = pax.execute(
        args_for(
            "search",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--name",
            "SMITH",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )
    assert first.status == ResultStatus.OK
    assert [record["instrument_reference_id"] for record in first.records] == [
        "1001"
    ]
    assert first.next_cursor

    second = pax.execute(
        args_for(
            "search",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--name",
            "SMITH",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert second.status == ResultStatus.OK
    assert [record["instrument_reference_id"] for record in second.records] == [
        "1000"
    ]
    assert second.next_cursor
    assert second.records[0]["retrieval_coverage"][
        "cursor_anchor_verified"
    ] is True

    mismatch = pax.execute(
        args_for(
            "search",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--name",
            "JONES",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatch.status == ResultStatus.SOURCE_CHANGED
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_licking_exact_search_works_but_name_discovery_reports_alternatives() -> None:
    client = FakePAXClient()
    exact = pax.execute(
        args_for(
            "search",
            "--source",
            pax.LICKING_SOURCE_ID,
            "--instrument",
            pax.LICKING_SENTINEL,
        ),
        client=client,
        log_results=False,
    )
    discovery = pax.execute(
        args_for(
            "search",
            "--source",
            pax.LICKING_SOURCE_ID,
            "--name",
            "SMITH",
        ),
        client=client,
        log_results=False,
    )

    assert exact.status == ResultStatus.OK
    assert exact.records[0]["instrument_number"] == pax.LICKING_SENTINEL
    assert (
        exact.records[0]["record_identity_source_id"]
        == pax.LICKING_SOURCE_ID
    )
    assert (
        exact.records[0]["representation_source_id"]
        == pax.LICKING_DETAIL_SOURCE_ID
    )
    assert discovery.status == ResultStatus.RESTRICTED
    assert discovery.errors[0].code == "account_required_for_discovery"
    alternatives = discovery.errors[0].details["official_alternatives"]
    assert any(
        item["relationship"]
        == "historical_recorder_archive_and_request_route"
        for item in alternatives
    )
    assert client.licking_calls == [pax.LICKING_SENTINEL]


def test_licking_instrument_preserves_official_no_result() -> None:
    client = FakePAXClient()
    selector = "free-form-missing"
    client.missing_licking.add(selector)

    result = pax.execute(
        args_for(
            "instrument",
            "--source",
            pax.LICKING_SOURCE_ID,
            selector,
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert not result.errors


def test_document_info_uses_native_reference_for_delaware() -> None:
    client = FakePAXClient()
    result = pax.execute(
        args_for(
            "document-info",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "202600000003",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records[0]["instrument_reference_id"] == "1001"
    assert result.records[0]["document_access"]["has_image"] is True
    assert client.image_calls == [("1001", "202600000003")]


def test_download_has_distinct_pdf_artifact_identity_and_hash(
    tmp_path: Path,
) -> None:
    client = FakePAXClient()
    destination = tmp_path / "licking.pdf"
    result = pax.execute(
        args_for(
            "download",
            "--source",
            pax.LICKING_SOURCE_ID,
            pax.LICKING_SENTINEL,
            "--destination",
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    expected = b"%PDF-1.7\nfixture recorder document\n%%EOF\n"
    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == expected
    assert result.records[0]["record_kind"] == "recorded_instrument_document"
    assert result.records[0]["canonical_ref"].startswith("OHREC_DOCUMENT:")
    assert (
        result.records[0]["record_identity_source_id"]
        == pax.LICKING_SOURCE_ID
    )
    assert (
        result.records[0]["representation_source_id"]
        == pax.LICKING_DETAIL_SOURCE_ID
    )
    assert result.records[0]["media_type"] == "application/pdf"
    assert result.records[0]["size_bytes"] == len(expected)
    assert result.records[0]["sha256"] == hashlib.sha256(expected).hexdigest()
    assert result.raw_artifact_refs == (str(destination),)


def test_probe_reports_tenant_specific_access_without_conflation() -> None:
    client = FakePAXClient()
    delaware = pax.execute(
        args_for(
            "probe",
            "--source",
            pax.DELAWARE_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )
    licking = pax.execute(
        args_for(
            "probe",
            "--source",
            pax.LICKING_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )
    licking_exact = pax.execute(
        args_for(
            "probe",
            "--source",
            pax.LICKING_DETAIL_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )

    assert delaware.status == ResultStatus.OK
    assert delaware.records[0]["pax_login_required"] is False
    assert delaware.records[0]["anonymous_detail_search_verified"] is True
    assert delaware.records[0]["anonymous_image_metadata_verified"] is True
    assert licking.status == ResultStatus.OK
    assert licking.records[0]["pax_login_required"] is True
    assert licking.records[0]["discovery_access"] == "account_required"
    assert (
        licking.records[0]["exact_representation_source_id"]
        == pax.LICKING_DETAIL_SOURCE_ID
    )
    assert "anonymous_exact_detail_verified" not in licking.records[0]
    assert licking_exact.status == ResultStatus.OK
    assert licking_exact.query.source.source_id == pax.LICKING_DETAIL_SOURCE_ID
    assert (
        licking_exact.records[0]["record_identity_source_id"]
        == pax.LICKING_SOURCE_ID
    )
    assert (
        licking_exact.records[0]["representation_source_id"]
        == pax.LICKING_DETAIL_SOURCE_ID
    )
    assert licking_exact.records[0]["independent_corroboration"] is False
    assert licking_exact.records[0]["anonymous_exact_detail_verified"] is True
    assert licking_exact.records[0]["anonymous_pdf_locator_verified"] is True


def test_selected_exact_representation_remains_the_query_source() -> None:
    result = pax.execute(
        args_for(
            "instrument",
            "--source",
            pax.LICKING_DETAIL_SOURCE_ID,
            pax.LICKING_SENTINEL,
        ),
        client=FakePAXClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.query.source.source_id == pax.LICKING_DETAIL_SOURCE_ID
    assert result.records[0]["source_id"] == pax.LICKING_SOURCE_ID
    assert (
        result.records[0]["record_identity_source_id"]
        == pax.LICKING_SOURCE_ID
    )
    assert (
        result.records[0]["representation_source_id"]
        == pax.LICKING_DETAIL_SOURCE_ID
    )


def test_parser_does_not_install_an_implicit_limit() -> None:
    args = args_for(
        "search",
        "--source",
        pax.DELAWARE_SOURCE_ID,
        "--name",
        "SMITH",
    )

    assert args.limit is None
    assert args.cursor is None


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_nonpositive_explicit_limit_is_a_structured_failure(limit: str) -> None:
    result = pax.execute(
        args_for(
            "search",
            "--source",
            pax.DELAWARE_SOURCE_ID,
            "--name",
            "SMITH",
            "--limit",
            limit,
        ),
        client=FakePAXClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "invalid_limit"


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    [
        (ResultStatus.OK, 0),
        (ResultStatus.NO_RESULTS, 0),
        (ResultStatus.PARTIAL, 0),
        (ResultStatus.SOURCE_CHANGED, 1),
    ],
)
def test_main_returns_contract_exit_code(
    status: ResultStatus,
    expected_exit: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = SimpleNamespace(status=status)
    monkeypatch.setattr(pax, "execute", lambda _args: result)
    monkeypatch.setattr(pax, "_emit", lambda _result, _args: None)

    exit_code = pax.main(
        [
            "probe",
            "--source",
            pax.DELAWARE_SOURCE_ID,
        ]
    )

    assert exit_code == expected_exit
