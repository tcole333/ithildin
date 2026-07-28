from __future__ import annotations

from tools import query_la_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_contract import ResultStatus
from tools.public_records_http import PaginatedFetch, TransportError, inferred_schema, schema_fingerprint


ALLOWED = {
    "allowed": True,
    "limits": {
        "require_complete_pagination": True,
    },
}


def _fetch(records, *, next_cursor=None, truncated=False):
    schema = inferred_schema(records)
    return PaginatedFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        schema=schema,
        schema_fingerprint=schema_fingerprint(schema),
        pages_fetched=1,
        requests_made=1,
        truncated_by_cap=truncated,
    )


class FakeEBR:
    def __init__(self):
        self.calls = []

    def query(
        self,
        parish,
        dataset_key,
        parameters,
        *,
        requested_limit,
        cursor=None,
    ):
        self.calls.append(
            (parish, dataset_key, dict(parameters), requested_limit, cursor)
        )
        if dataset_key == "tax_roll":
            return _fetch(
                [
                    {
                        "assessment_no_new": "3076237",
                        "taxpayer_name": "SMITH LLC",
                        "tax_year": "2025",
                    }
                ],
                next_cursor="socrata:offset:1",
            )
        if dataset_key == "tax_parcel":
            return _fetch(
                [
                    {
                        "assessment_num": "030-7623-7",
                        "owner": "SMITH LLC",
                        "physical_address": "100 MAIN ST",
                    }
                ],
                next_cursor="socrata:offset:1",
            )
        if dataset_key == "property_info":
            return _fetch(
                [{"full_address": "100 MAIN ST", "zoning_type": "C1"}]
            )
        return _fetch([])


def test_owner_search_preserves_dataset_provenance_and_composite_cursor(monkeypatch):
    monkeypatch.setattr(
        query_la_property,
        "log_search",
        lambda *args, **kwargs: None,
    )
    args = query_la_property.build_parser().parse_args(
        ["owner", "SMITH", "--limit", "1"]
    )
    source = FakeEBR()

    result = query_la_property.execute(
        args,
        source=source,
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.OK
    assert [record["dataset"] for record in result.records] == [
        "tax_roll",
        "tax_parcel",
    ]
    assert result.next_cursor.startswith("ebr:")
    decoded = query_la_property._decode_cursor(result.next_cursor)
    assert decoded == {
        "tax_parcel": "socrata:offset:1",
        "tax_roll": "socrata:offset:1",
    }


def test_composite_cursor_is_routed_to_each_dataset(monkeypatch):
    monkeypatch.setattr(
        query_la_property,
        "log_search",
        lambda *args, **kwargs: None,
    )
    cursor = query_la_property._encode_cursor(
        {
            "tax_roll": "socrata:offset:10",
            "tax_parcel": "socrata:offset:20",
        }
    )
    args = query_la_property.build_parser().parse_args(
        ["owner", "SMITH", "--cursor", cursor]
    )
    source = FakeEBR()

    query_la_property.execute(
        args,
        source=source,
        access_decision=ALLOWED,
    )

    assert source.calls[0][4] == "socrata:offset:10"
    assert source.calls[1][4] == "socrata:offset:20"


def test_one_dataset_failure_is_partial_and_not_a_false_zero(monkeypatch):
    monkeypatch.setattr(
        query_la_property,
        "log_search",
        lambda *args, **kwargs: None,
    )
    args = query_la_property.build_parser().parse_args(["owner", "SMITH"])

    class PartialEBR(FakeEBR):
        def query(
            self,
            parish,
            dataset_key,
            parameters,
            *,
            requested_limit,
            cursor=None,
        ):
            if dataset_key == "tax_parcel":
                raise TransportError(
                    "parcel dataset unavailable",
                    url="https://example.invalid",
                )
            return super().query(
                parish,
                dataset_key,
                parameters,
                requested_limit=requested_limit,
                cursor=cursor,
            )

    result = query_la_property.execute(
        args,
        source=PartialEBR(),
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 1
    assert result.records[0]["dataset"] == "tax_roll"
    assert result.errors[0].code == "transport_error"


def test_all_authoritative_empty_pages_are_no_results(monkeypatch):
    monkeypatch.setattr(
        query_la_property,
        "log_search",
        lambda *args, **kwargs: None,
    )
    args = query_la_property.build_parser().parse_args(["address", "NO SUCH ST"])

    class EmptyEBR:
        def query(self, *args, **kwargs):
            return _fetch([])

    result = query_la_property.execute(
        args,
        source=EmptyEBR(),
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_details_adds_property_info_join(monkeypatch):
    monkeypatch.setattr(
        query_la_property,
        "log_search",
        lambda *args, **kwargs: None,
    )
    args = query_la_property.build_parser().parse_args(["details", "3076237"])

    result = query_la_property.execute(
        args,
        source=FakeEBR(),
        access_decision=ALLOWED,
    )

    assert [record["dataset"] for record in result.records] == [
        "tax_roll",
        "tax_parcel",
        "property_info",
    ]
    assert result.records[-1]["record"]["zoning_type"] == "C1"


def test_interactive_catalog_mode_returns_without_source_request(monkeypatch):
    monkeypatch.setattr(
        query_la_property,
        "log_search",
        lambda *args, **kwargs: None,
    )
    args = query_la_property.build_parser().parse_args(["owner", "SMITH"])
    decision = {
        "source_id": query_la_property.SOURCE_ID,
        "allowed": False,
        "access_class": "C",
        "automation_disposition": "prohibited",
        "reason": "automation prohibited by reviewed terms",
        "reason_code": "automation_not_approved",
    }

    def deny(_args):
        raise AcquisitionUnavailableError(decision)

    monkeypatch.setattr(query_la_property, "_require_access", deny)

    class MustNotRun:
        def query(self, *args, **kwargs):
            raise AssertionError("network source was unexpectedly called")

    result = query_la_property.execute(args, source=MustNotRun())

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].category == "access"


def test_source_context_uses_user_cap_and_reviewed_page_bound():
    args = query_la_property.build_parser().parse_args(
        [
            "owner",
            "SMITH",
            "--max-records",
            "90000",
            "--page-size",
            "70000",
            "--minimum-interval",
            "0",
        ]
    )

    source = query_la_property._EBRSource(
        args,
        {
            "limits": {
                "maximum_page_size": 50_000,
                "require_complete_pagination": True,
            }
        },
    )

    assert source.max_records == 90_000
    assert source.page_size == 50_000
    assert source.minimum_interval == 0
