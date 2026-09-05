from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from tools import query_ohio_delaware_common_pleas as delaware
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_delaware_common_pleas"
)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _parse(*values: str):
    return delaware.build_parser().parse_args(list(values))


def test_source_contract_uses_requested_identity_and_browser_operations():
    metadata = delaware.SOURCE_CATALOG_METADATA[delaware.SOURCE_ID]

    assert delaware.SOURCE_ID == "us-oh-delaware-common-pleas-courtview"
    assert delaware.COURT_ID == "oh-delaware-common-pleas"
    assert metadata["platform_family"] == "equivant_courtview_wicket"
    assert metadata["paging"] == {
        "default": "exhaustive",
        "native_page_sizes": [25, 50, 75, 100],
        "cursor": "query_bound_offset_replay",
    }
    assert {
        "warmup",
        "search_party",
        "search_company",
        "case",
        "docket",
        "documents",
        "document",
    }.issubset(metadata["operations"])
    complement_ids = {
        item.get("source_id") for item in metadata["complementary_sources"]
    }
    assert {
        "us-oh-delaware-county-recorder-pax",
        "us-oh-delaware-sheriff-realauction",
    }.issubset(complement_ids)


def test_parser_has_no_default_result_cap_and_accepts_native_filters():
    args = _parse(
        "search-party",
        "--last-name",
        "Smith",
        "--first-name",
        "J",
        "--case-type",
        "CV",
        "--case-status",
        "Closed",
        "--party-type",
        "Defendant",
        "--filed-from",
        "2020-01-02",
    )

    assert args.limit is None
    assert args.cursor is None
    assert args.case_type == ["CV"]
    assert args.filed_from == "01/02/2020"


def test_probe_separates_stable_contract_from_rolling_version():
    before = delaware.normalize_probe(_fixture("probe.json"))
    changed = _fixture("probe.json")
    changed["contract"]["courtview_version"] = "1.55.00"
    changed["contract"]["copyright_year"] = 2027
    after = delaware.normalize_probe(changed)

    assert before["access_state"] == "ready"
    assert before["contract"]["native_page_sizes"] == [25, 50, 75, 100]
    assert before["contract"]["option_counts"] == {
        "case_type": 4,
        "case_status": 3,
        "party_type": 3,
        "suffix": 2,
    }
    assert before["schema_fingerprint"] == after["schema_fingerprint"]
    assert before["rolling_observations"] != after["rolling_observations"]


def test_challenge_packet_is_human_required_not_no_results():
    args = _parse("probe", "--input", str(FIXTURE_DIR / "captcha.json"))

    result = delaware.execute(args)

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.records == ()
    assert result.errors[0].code == "captcha_required"
    assert result.errors[0].details["access"]["interactive_challenge"] is True


def test_exhaustive_search_keeps_duplicate_occurrences_with_query_bound_ids():
    args = _parse("search-party", "--last-name", "Smith", "--first-name", "J")

    result = delaware.execute(
        args,
        helper_runner=lambda operation, arguments, **kwargs: _fixture("search.json"),
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 4
    assert result.next_cursor is None
    assert result.records[1]["party_name"] == result.records[2]["party_name"]
    assert result.records[1]["canonical_ref"] == result.records[2]["canonical_ref"]
    assert (
        result.records[1]["native_occurrence_id"]
        != result.records[2]["native_occurrence_id"]
    )
    assert [row["exhaustive_occurrence_ordinal"] for row in result.records] == [
        1,
        2,
        3,
        4,
    ]
    assert result.records[0]["display_case_number"] == "00 CV E 10 0434"
    assert result.records[0]["normalized_case_number"] == "00 CV E 10 0434"
    assert result.records[0]["court"] == delaware._court_payload()


def test_limit_cursor_resumes_same_query_and_rejects_different_query():
    first_args = _parse(
        "search-party", "--last-name", "Smith", "--first-name", "J", "--limit", "2"
    )
    def runner(operation, arguments, **kwargs):
        return _fixture("search.json")

    first = delaware.execute(first_args, helper_runner=runner)
    cursor = first.next_cursor
    second_args = _parse(
        "search-party",
        "--last-name",
        "Smith",
        "--first-name",
        "J",
        "--limit",
        "2",
        "--cursor",
        cursor,
    )
    second = delaware.execute(second_args, helper_runner=runner)
    mismatch_args = _parse(
        "search-party",
        "--last-name",
        "Jones",
        "--limit",
        "2",
        "--cursor",
        cursor,
    )
    mismatch = delaware.execute(mismatch_args, helper_runner=runner)

    assert first.status == ResultStatus.OK
    assert cursor.startswith(delaware.CURSOR_PREFIX)
    assert [row["exhaustive_occurrence_ordinal"] for row in second.records] == [3, 4]
    assert second.next_cursor is None
    assert mismatch.status == ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_search_packet_must_contain_every_reported_occurrence():
    packet = _fixture("search.json")
    packet["total_reported"] = 5
    args = _parse("search-company", "ACME LLC")

    result = delaware.execute(
        args,
        helper_runner=lambda operation, arguments, **kwargs: packet,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.errors[0].code == "search_incomplete"


def test_case_normalization_preserves_sections_and_court_identity():
    case = delaware.normalize_case_packet(_fixture("case.json"))

    assert case is not None
    assert case["canonical_ref"].endswith("/16%20CV%20C%2006%200330/case")
    assert case["court"]["native_court_id"] == delaware.COURT_ID
    assert case["case_type"] == "(CV) CIVIL COMMON PLEAS"
    assert case["display_case_number"] == "16 CV C 06 0330"
    assert case["normalized_case_number"] == "16 CV C 06 0330"
    assert case["file_date"] == "2016-06-03"
    assert [party["party_type"] for party in case["parties"]] == [
        "Plaintiff",
        "Defendant",
    ]
    assert len(case["docket"]) == 3
    assert case["events"][0]["result"] == "SETTLED"
    assert case["financial_tables"][0]["rows"][0][0] == "COST"


def test_unverified_case_detail_pager_is_partial_instead_of_silent_truncation():
    packet = _fixture("case.json")
    packet["case"]["detail_paging_controls"] = [
        {"title": "Go to next page", "text": ">"}
    ]

    try:
        delaware.normalize_case_packet(packet)
    except delaware.DelawareCourtViewError as error:
        assert error.status == ResultStatus.PARTIAL
        assert error.code == "case_detail_paging_unresolved"
    else:
        raise AssertionError("case detail pager was silently accepted")


def test_document_list_derives_distinct_ids_for_duplicate_docket_occurrences():
    case = delaware.normalize_case_packet(_fixture("case.json"))
    assert case is not None

    documents = delaware._document_records(case)

    assert len(documents) == 2
    assert documents[0]["document_id"].startswith("dktdoc-")
    assert documents[0]["document_id"] != documents[1]["document_id"]
    assert documents[0]["document_access_state"] == "link_present"
    assert all("?x=" not in json.dumps(record) for record in documents)
    assert all("antiCache" not in json.dumps(record) for record in documents)


def test_python_and_browser_helper_derive_the_same_document_identity():
    row = _fixture("case.json")["case"]["docket"][0]
    expected = delaware.derive_document_id("16 CV C 06 0330", row)
    script = (
        "const helper=require(" + json.dumps(str(delaware.HELPER_PATH)) + ");"
        "process.stdout.write(helper.derivedId('dktdoc',"
        "helper.docketIdentity('16 CV C 06 0330'," + json.dumps(row) + ")));"
    )

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == expected


def test_document_artifact_is_bound_to_docket_identity_and_valid_hash(tmp_path):
    case_packet = _fixture("case.json")
    row = case_packet["case"]["docket"][0]
    document_id = delaware.derive_document_id("16 CV C 06 0330", row)
    packet = {
        "operation": "document",
        "status": "ok",
        "requested_document_id": document_id,
        "case": {
            "case_number": "16 CV C 06 0330",
            "caption": case_packet["case"]["caption"],
        },
        "document": row,
        "artifact": {
            "output_path": str(tmp_path / "filing.pdf"),
            "content_type": "application/pdf",
            "byte_size": 21355,
            "sha256": "a" * 64,
        },
    }

    record = delaware.normalize_document_packet(packet)

    assert record is not None
    assert record["document_id"] == document_id
    assert record["docket_occurrence_id"].startswith("dkt-")
    assert record["document_link_present"] is True
    assert record["document_access_state"] == "retrieved"
    assert record["artifact_sha256"] == "a" * 64


def test_helper_runner_receives_browser_contract_without_transport_urls():
    args = _parse("case", "16 CV C 06 0330")
    calls = []

    def runner(operation, arguments, **kwargs):
        calls.append((operation, arguments, kwargs))
        return copy.deepcopy(_fixture("case.json"))

    result = delaware.execute(args, helper_runner=runner)

    assert result.status == ResultStatus.OK
    assert calls == [
        (
            "case",
            ["16 CV C 06 0330"],
            {"timeout": delaware.DEFAULT_BROWSER_TIMEOUT},
        )
    ]


def test_source_command_is_offline_and_exposes_official_complements():
    result = delaware.execute(_parse("source"))

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["court"]["county_geoid"] == delaware.COUNTY_FIPS
    assert record["identity_contract"]["transport_values"] == "not record identity"
    urls = {item.get("url") for item in record["complementary_sources"]}
    assert delaware.SEARCH_GUIDE_URL in urls
    assert delaware.PUBLIC_RECORDS_POLICY_URL in urls
