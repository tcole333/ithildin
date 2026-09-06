from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import requests

from tools import query_oregon_court_documents as oregon_docs
from tools.ingest_state_court_records import validate_envelope


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_court_documents"
)
COA_OPINIONS = "us-or-law-library-coa-opinions"
SUPREME_OPINIONS = "us-or-law-library-supreme-opinions"
SUPREME_BRIEFS = "us-or-law-library-supreme-briefs"
COA_ORDERS = "us-or-law-library-coa-orders-interest"


def _json_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def _bytes_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@dataclass
class FixtureResponse:
    payload: Any = None
    content: bytes | None = None
    text: str = ""
    url: str | None = None
    status_code: int = 200
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/json"}
    )

    def __post_init__(self) -> None:
        if self.content is None:
            if self.payload is not None:
                self.content = json.dumps(self.payload).encode()
            else:
                self.content = self.text.encode()
        if not self.text and self.content is not None:
            self.text = self.content.decode(errors="replace")

    def json(self) -> Any:
        if isinstance(self.payload, BaseException):
            raise self.payload
        if self.payload is None:
            return json.loads(self.text)
        return self.payload


class QueueSession:
    def __init__(self, responses: list[Any]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method, url, *, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError(f"unexpected CONTENTdm request: {url}")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if response.url is None:
            response.url = url
        return response

    def close(self):
        self.closed = True


def _client(*responses: Any):
    session = QueueSession(list(responses))
    return (
        oregon_docs.OregonCourtDocumentsClient(
            session=session,
            minimum_interval=0,
            sleeper=lambda _delay: None,
        ),
        session,
    )


def _parse(*values: str):
    return oregon_docs.build_parser().parse_args(list(values))


def _search_response(name: str) -> FixtureResponse:
    return FixtureResponse(payload=_json_fixture(name))


def _single_result_payload(
    *,
    alias: str = "p17027coll5",
    item_id: str = "42527",
    title: str = "A182332, Opinion",
    total: int = 1,
) -> dict[str, Any]:
    return {
        "totalResults": total,
        "items": [
            {
                "collectionAlias": alias,
                "itemId": item_id,
                "filetype": "pdf",
                "thumbnailUri": (
                    f"/api/singleitem/collection/{alias}/id/"
                    f"{item_id}/thumbnail"
                ),
                "metadataFields": [
                    {"field": "title", "value": title}
                ],
                "title": title,
            }
        ],
        "fields": {},
        "filters": [],
        "facets": {},
        "facetFields": {},
        "sortFields": [],
    }


def test_sources_preserve_all_distinct_collection_aliases():
    result = oregon_docs.execute(
        _parse("sources"),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert {
        record["source_id"]: record["collection_alias"]
        for record in result.records
    } == {
        "us-or-law-library-supreme-opinions": "p17027coll3",
        "us-or-law-library-coa-opinions": "p17027coll5",
        "us-or-law-library-tax-court-decisions": "p17027coll6",
        "us-or-law-library-supreme-briefs": "p17027coll7",
        "us-or-law-library-coa-briefs": "p17027coll8",
        "us-or-law-library-coa-orders-interest": "p17027coll17",
        "us-or-law-library-multnomah-presiding-orders": "p17027coll15",
    }
    assert all(
        record["component_source_id"] == record["source_id"]
        for record in result.records
    )
    validate_envelope(result.to_dict())


def test_search_cli_accepts_one_native_term_and_one_field():
    args = _parse(
        "search",
        "State v. Wear",
        "--source",
        COA_OPINIONS,
        "--field",
        "subjec",
    )

    assert args.query_text == "State v. Wear"
    assert args.field == "subjec"
    with pytest.raises(SystemExit):
        _parse(
            "search",
            "State",
            "Wear",
            "--source",
            COA_OPINIONS,
        )
    with pytest.raises(SystemExit):
        _parse(
            "search",
            "Wear",
            "--source",
            COA_OPINIONS,
            "--field",
            "subjec/dated",
        )


def test_search_uses_selected_alias_and_source_native_path():
    client, session = _client(
        FixtureResponse(payload=_single_result_payload())
    )
    result = oregon_docs.execute(
        _parse(
            "search",
            "State v. Wear",
            "--source",
            COA_OPINIONS,
            "--field",
            "subjec",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.query.source.source_id == COA_OPINIONS
    assert result.records[0]["canonical_ref"] == (
        f"ORCOURT-DOC:{COA_OPINIONS}:42527"
    )
    url = session.calls[0]["url"]
    assert "/collection/p17027coll5/" in url
    assert "/field/subjec/searchterm/State%20v.%20Wear/" in url
    assert url.count("/searchterm/") == 1
    assert result.records[0]["download_uri"].endswith(
        "/collection/p17027coll5/id/42527/download"
    )


def test_latest_uses_collection_native_date_field_and_descending_sort():
    client, session = _client(
        FixtureResponse(
            payload=_single_result_payload(
                alias="p17027coll3",
                item_id="18161",
                title="S072132, Opinion",
            )
        )
    )
    result = oregon_docs.execute(
        _parse(
            "latest",
            "--source",
            SUPREME_OPINIONS,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert "/order/dated/ad/desc" in session.calls[0]["url"]
    assert "/searchterm/" not in session.calls[0]["url"]
    assert result.query.query.parameters["sort"] == "dated:desc"


def test_short_native_pages_continue_until_frozen_count_is_reached():
    client, session = _client(
        _search_response("search_page_1.json"),
        _search_response("search_page_2.json"),
        _search_response("search_page_3.json"),
    )
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]

    batch = client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=None,
    )

    assert [record["item_id"] for record in batch.records] == [
        "101",
        "102",
        "103",
        "104",
        "105",
    ]
    assert batch.snapshot_total == 5
    assert batch.pages_fetched == 3
    assert batch.next_cursor is None
    assert batch.incomplete_error is None
    assert [call["url"].rsplit("/start/", 1)[1] for call in session.calls] == [
        "1",
        "2",
        "4",
    ]


def test_cursor_resume_replays_anchor_and_returns_only_unconsumed_items():
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]
    first_client, _ = _client(_search_response("search_page_1.json"))
    first = first_client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=2,
    )

    assert first.next_cursor is not None
    next_start, total, anchor = oregon_docs._decode_cursor(
        first.next_cursor,
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
    )
    assert (next_start, total, anchor) == (3, 5, "102")

    resumed_client, session = _client(
        _search_response("search_page_2.json"),
        _search_response("search_page_3.json"),
    )
    resumed = resumed_client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=3,
        cursor=first.next_cursor,
    )

    assert [record["item_id"] for record in resumed.records] == [
        "103",
        "104",
        "105",
    ]
    assert resumed.next_cursor is None
    assert "/start/2" in session.calls[0]["url"]
    assert "/start/4" in session.calls[1]["url"]


def test_cursor_is_bound_to_source_alias_query_field_and_sort():
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]
    cursor = oregon_docs._encode_cursor(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        next_start=3,
        snapshot_total=5,
        anchor_item_id="102",
    )

    with pytest.raises(
        oregon_docs.OregonCourtDocumentsSelectionError
    ) as caught:
        oregon_docs._decode_cursor(
            cursor,
            spec,
            query_text="another query",
            field="all",
            sort=spec.search_sort,
        )

    assert caught.value.code == "cursor_query_mismatch"


def test_cursor_anchor_change_is_explicit_source_changed():
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]
    cursor = oregon_docs._encode_cursor(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        next_start=3,
        snapshot_total=5,
        anchor_item_id="102",
    )
    reordered = _json_fixture("search_page_2.json")
    reordered["items"][0]["itemId"] = "999"
    client, _ = _client(FixtureResponse(payload=reordered))

    batch = client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=2,
        cursor=cursor,
    )

    assert batch.records == ()
    assert batch.incomplete_error is not None
    assert batch.incomplete_error.code == "cursor_anchor_changed"
    assert batch.incomplete_error.status.value == "source_changed"
    assert batch.next_cursor == cursor


def test_count_drift_is_partial_and_preserves_frozen_cursor():
    changed = _json_fixture("search_page_2.json")
    changed["totalResults"] = 6
    client, _ = _client(
        _search_response("search_page_1.json"),
        FixtureResponse(payload=changed),
    )
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]

    batch = client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=None,
    )

    assert [record["item_id"] for record in batch.records] == ["101", "102"]
    assert batch.snapshot_total == 5
    assert batch.incomplete_error is not None
    assert batch.incomplete_error.code == "source_count_drift"
    assert batch.incomplete_error.status.value == "partial"
    assert batch.next_cursor is not None


def test_repeated_native_page_is_partial_not_false_exhaustion():
    client, _ = _client(
        _search_response("search_page_1.json"),
        _search_response("search_page_1.json"),
    )
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]

    batch = client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=None,
    )

    assert batch.incomplete_error is not None
    assert batch.incomplete_error.code == "repeated_page"
    assert batch.incomplete_error.status.value == "partial"
    assert [record["item_id"] for record in batch.records] == ["101", "102"]


def test_duplicate_item_across_pages_is_partial():
    duplicate = _json_fixture("search_page_2.json")
    duplicate["items"][1]["itemId"] = "101"
    client, _ = _client(
        _search_response("search_page_1.json"),
        FixtureResponse(payload=duplicate),
    )
    spec = oregon_docs.COLLECTIONS[COA_OPINIONS]

    batch = client.search(
        spec,
        query_text="fixture",
        field="all",
        sort=spec.search_sort,
        limit=None,
    )

    assert batch.incomplete_error is not None
    assert batch.incomplete_error.code == "duplicate_item"
    assert [record["item_id"] for record in batch.records] == ["101", "102"]


def test_opinion_item_preserves_structured_metadata_and_full_text():
    client, _ = _client(
        FixtureResponse(payload=_json_fixture("opinion_item.json"))
    )
    result = oregon_docs.execute(
        _parse("item", "42527", "--source", COA_OPINIONS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["canonical_ref"] == (
        f"ORCOURT-DOC:{COA_OPINIONS}:42527"
    )
    assert record["case_number"] == "A182332"
    assert record["normalized_metadata"]["case_name"] == "State v. Wear"
    assert record["normalized_metadata"]["citation"] == "351 Or App 714"
    assert record["document_date"] == "2026-07-29"
    assert "STATE OF OREGON" in record["full_text"]
    assert record["full_text_sha256"] == hashlib.sha256(
        record["full_text"].encode()
    ).hexdigest()
    assert record["metadata_by_label"]["Author"] == "Aoyagi"
    validate_envelope(result.to_dict())


def test_brief_schema_keeps_missing_optional_fields_as_null():
    client, _ = _client(
        FixtureResponse(payload=_json_fixture("brief_item.json"))
    )
    result = oregon_docs.execute(
        _parse("item", "29902", "--source", SUPREME_BRIEFS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["record_kind"] == "supreme_court_brief"
    assert record["case_number"] == "S071535"
    assert record["document_type"] == "Answering brief"
    assert record["normalized_metadata"]["citation"] == "375 Or 293"
    assert "parties" not in record["normalized_metadata"]
    assert record["full_text"].startswith("RESPONDENT'S ANSWERING BRIEF")


def test_order_schema_preserves_order_specific_fields():
    client, _ = _client(
        FixtureResponse(payload=_json_fixture("order_item.json"))
    )
    result = oregon_docs.execute(
        _parse("item", "25", "--source", COA_ORDERS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["title"] == "Bailey and Bailey"
    assert record["case_number"] == "A185034"
    assert record["document_type"] == "Attorney Fees"
    assert record["normalized_metadata"]["disposition"] == "Allowed"
    assert record["normalized_metadata"]["amount_awarded"] == "$3,920"


def test_compound_item_fetches_pages_in_order_and_combines_full_text():
    client, session = _client(
        FixtureResponse(payload=_json_fixture("compound_item.json")),
        FixtureResponse(payload=_json_fixture("compound_page_1.json")),
        FixtureResponse(payload=_json_fixture("compound_page_2.json")),
    )
    spec = oregon_docs.COLLECTIONS[SUPREME_OPINIONS]

    record = client.fetch_item(spec, "18161")

    assert record["canonical_ref"] == (
        f"ORCOURT-DOC:{SUPREME_OPINIONS}:18161"
    )
    assert record["is_compound"] is True
    assert record["page_count"] == 2
    assert [page["page_id"] for page in record["compound_pages"]] == [
        "18141",
        "18142",
    ]
    assert record["compound_pages"][0]["parent_item_id"] == "18161"
    assert record["full_text"] == (
        _json_fixture("compound_page_1.json")["text"]
        + "\n\n"
        + _json_fixture("compound_page_2.json")["text"]
    )
    assert len(session.calls) == 3


def test_missing_item_fields_is_explicit_source_change():
    payload = _json_fixture("opinion_item.json")
    payload.pop("fields")
    client, _ = _client(FixtureResponse(payload=payload))

    result = oregon_docs.execute(
        _parse("item", "42527", "--source", COA_OPINIONS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "sequence_field_changed"
    assert result.records == ()


@pytest.mark.parametrize(
    ("source_id", "item_id", "fixture_name"),
    [
        (COA_OPINIONS, "42527", "opinion_item.json"),
        (SUPREME_OPINIONS, "18161", "compound_item.json"),
    ],
)
def test_download_handles_ordinary_and_compound_pdf_routes_atomically(
    tmp_path,
    source_id,
    item_id,
    fixture_name,
):
    content = _bytes_fixture("minimal.pdf")
    client, session = _client(
        FixtureResponse(payload=_json_fixture(fixture_name)),
        FixtureResponse(
            content=content,
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": (
                    f'attachment; filename="{item_id}.pdf"'
                ),
            },
        ),
    )
    destination = tmp_path / f"{item_id}.pdf"

    result = oregon_docs.execute(
        _parse(
            "download",
            item_id,
            str(destination),
            "--source",
            source_id,
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert destination.read_bytes() == content
    sha256 = hashlib.sha256(content).hexdigest()
    receipt = result.records[0]
    assert receipt["canonical_ref"] == (
        f"ORCOURT-ARTIFACT:{source_id}:{sha256}"
    )
    assert receipt["document_canonical_ref"] == (
        f"ORCOURT-DOC:{source_id}:{item_id}"
    )
    assert receipt["sha256"] == sha256
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    assert len(session.calls) == 2
    assert session.calls[1]["url"] == (
        f"{oregon_docs.API_BASE_URL}/collection/"
        f"{oregon_docs.COLLECTIONS[source_id].alias}/id/{item_id}/download"
    )
    assert session.calls[1]["headers"]["Accept"] == "application/pdf"
    assert not list(tmp_path.glob("*.part"))


def test_non_pdf_download_is_source_changed_and_leaves_no_destination(
    tmp_path,
):
    client, _ = _client(
        FixtureResponse(payload=_json_fixture("opinion_item.json")),
        FixtureResponse(
            content=b"<html>interstitial</html>",
            headers={"Content-Type": "text/html"},
        ),
    )
    destination = tmp_path / "invalid.pdf"

    result = oregon_docs.execute(
        _parse(
            "download",
            "42527",
            str(destination),
            "--source",
            COA_OPINIONS,
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "download_not_pdf"
    assert destination.exists() is False


def test_transport_failure_retries_and_never_becomes_no_results():
    client, session = _client(
        requests.ConnectionError("offline"),
        requests.ConnectionError("offline"),
        requests.ConnectionError("offline"),
    )

    result = oregon_docs.execute(
        _parse("item", "42527", "--source", COA_OPINIONS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "transport_error"
    assert result.errors[0].retryable is True
    assert len(session.calls) == 3


def test_single_source_probe_preserves_transport_failure_status():
    client, _ = _client(
        requests.ConnectionError("offline"),
        requests.ConnectionError("offline"),
        requests.ConnectionError("offline"),
    )

    result = oregon_docs.execute(
        _parse("probe", "--source", COA_OPINIONS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "transport_error"


def test_access_failure_is_explicit():
    client, _ = _client(
        FixtureResponse(status_code=403)
    )

    result = oregon_docs.execute(
        _parse("item", "42527", "--source", COA_OPINIONS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "restricted"
    assert result.errors[0].code == "source_access_failed"


class BombClient:
    def __getattr__(self, name):
        raise AssertionError(f"client must not be used: {name}")


def test_catalog_decision_is_injected_before_acquisition():
    result = oregon_docs.execute(
        _parse(
            "search",
            "Wear",
            "--source",
            COA_OPINIONS,
        ),
        catalog_decision={
            "source_id": COA_OPINIONS,
            "allowed": False,
            "access_class": "C",
            "reason_code": "interactive_route",
            "reason": "fixture catalog route",
        },
        client=BombClient(),
        log_results=False,
    )

    assert result.status.value == "human_required"
    assert result.errors[0].code == "interactive_route"


def test_catalog_decision_must_match_source_component():
    result = oregon_docs.execute(
        _parse(
            "search",
            "Wear",
            "--source",
            COA_OPINIONS,
        ),
        catalog_decision={
            "source_id": SUPREME_OPINIONS,
            "allowed": True,
        },
        client=BombClient(),
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "catalog_decision_source_mismatch"


def test_catalog_decision_can_bind_catalog_scoped_sources_command():
    result = oregon_docs.execute(
        _parse("sources"),
        catalog_decision={
            "source_id": oregon_docs.CATALOG_SOURCE_ID,
            "allowed": True,
        },
        client=BombClient(),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 7


def test_direct_cli_contract_remains_usable_without_catalog_decision():
    client, _ = _client(
        FixtureResponse(payload=_single_result_payload())
    )

    result = oregon_docs.execute(
        _parse(
            "search",
            "A182332",
            "--source",
            COA_OPINIONS,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0]["source_id"] == COA_OPINIONS


def test_partial_pagination_result_is_a_valid_shared_envelope():
    changed = _json_fixture("search_page_2.json")
    changed["totalResults"] = 6
    client, _ = _client(
        _search_response("search_page_1.json"),
        FixtureResponse(payload=changed),
    )

    result = oregon_docs.execute(
        _parse(
            "search",
            "fixture",
            "--source",
            COA_OPINIONS,
            "--limit",
            "100",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "partial"
    assert result.errors[0].code == "source_count_drift"
    assert result.next_cursor is not None
    validate_envelope(result.to_dict())


def test_malformed_search_envelope_is_source_changed():
    payload = _json_fixture("search_page_1.json")
    payload.pop("totalResults")
    client, _ = _client(FixtureResponse(payload=payload))

    result = oregon_docs.execute(
        _parse(
            "search",
            "fixture",
            "--source",
            COA_OPINIONS,
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "integer_field_changed"
    assert result.records == ()


def test_probe_verifies_exact_sentinel_metadata_and_identity():
    client, _ = _client(
        FixtureResponse(payload=_single_result_payload()),
        FixtureResponse(payload=_json_fixture("opinion_item.json")),
    )

    result = oregon_docs.execute(
        _parse("probe", "--source", COA_OPINIONS),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["sentinel_item_id"] == "42527"
    assert record["sentinel_query"] == "A182332"
    assert record["sentinel_canonical_ref"] == (
        f"ORCOURT-DOC:{COA_OPINIONS}:42527"
    )
    assert record["download_uri"].endswith(
        "/collection/p17027coll5/id/42527/download"
    )


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OR_COURT_DOCUMENTS") != "1",
    reason="set RUN_LIVE_OR_COURT_DOCUMENTS=1 for official API probes",
)
@pytest.mark.parametrize("source_id", tuple(oregon_docs.COLLECTIONS))
def test_live_exact_collection_sentinels(source_id):
    client = oregon_docs.OregonCourtDocumentsClient()
    try:
        record = client.probe(oregon_docs.COLLECTIONS[source_id])
    finally:
        client.close()

    assert record["source_id"] == source_id
    assert record["sentinel_item_id"] == (
        oregon_docs.COLLECTIONS[source_id].sentinel_item_id
    )
    assert record["metadata_field_count"] > 0
    assert record["download_uri"].endswith("/download")
