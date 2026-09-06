from __future__ import annotations

from tools import query_acris
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


class FakeACRIS:
    max_records = 50_000

    def __init__(self):
        self.calls = []

    def query(self, dataset_id, parameters, *, requested_limit, cursor=None):
        self.calls.append((dataset_id, dict(parameters), requested_limit, cursor))
        where = parameters.get("$where", "")
        if dataset_id == query_acris.PARTIES_ID and " IN " not in where:
            return _fetch(
                [{"document_id": "2024001", "party_type": "2", "name": "BUYER LLC"}],
                next_cursor="socrata:offset:1",
            )
        if dataset_id == query_acris.MASTER_ID:
            return _fetch(
                [
                    {
                        "document_id": "2024001",
                        "crfn": "2024000000001",
                        "doc_type": "DEED",
                        "document_date": "2024-01-02T00:00:00.000",
                    }
                ]
            )
        if dataset_id == query_acris.PARTIES_ID:
            return _fetch(
                [
                    {"document_id": "2024001", "party_type": "1", "name": "SELLER LLC"},
                    {"document_id": "2024001", "party_type": "2", "name": "BUYER LLC"},
                ]
            )
        if dataset_id == query_acris.LEGALS_ID:
            return _fetch(
                [
                    {
                        "document_id": "2024001",
                        "borough": "1",
                        "block": "123",
                        "lot": "45",
                    }
                ]
            )
        raise AssertionError(dataset_id)


def test_party_search_returns_enriched_document_records(monkeypatch):
    monkeypatch.setattr(query_acris, "log_search", lambda *args, **kwargs: None)
    args = query_acris.build_parser().parse_args(
        ["party", "BUYER LLC", "--exact", "--limit", "1"]
    )
    source = FakeACRIS()

    result = query_acris.execute(
        args,
        source=source,
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.OK
    assert result.next_cursor == "acris:exact:socrata:offset:1"
    assert result.records[0]["master"]["crfn"] == "2024000000001"
    assert [party["name"] for party in result.records[0]["parties"]] == [
        "SELLER LLC",
        "BUYER LLC",
    ]
    assert result.records[0]["legals"][0]["block"] == "123"
    assert result.records[0]["matched_parties"][0]["name"] == "BUYER LLC"
    assert result.records[0]["enrichment_complete"] is True


def test_party_continuation_unwraps_the_exact_mode_cursor(monkeypatch):
    monkeypatch.setattr(query_acris, "log_search", lambda *args, **kwargs: None)
    args = query_acris.build_parser().parse_args(
        [
            "party",
            "BUYER LLC",
            "--exact",
            "--limit",
            "1",
            "--cursor",
            "acris:exact:socrata:offset:100",
        ]
    )
    source = FakeACRIS()

    query_acris.execute(args, source=source, access_decision=ALLOWED)

    assert source.calls[0][3] == "socrata:offset:100"


def test_transport_failure_is_unavailable_not_no_results(monkeypatch):
    monkeypatch.setattr(query_acris, "log_search", lambda *args, **kwargs: None)
    args = query_acris.build_parser().parse_args(
        ["party", "BUYER LLC", "--exact"]
    )

    class BrokenSource:
        def query(self, *args, **kwargs):
            raise TransportError("connection failed", url="https://example.invalid")

    result = query_acris.execute(
        args,
        source=BrokenSource(),
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_missing_document_id_is_source_changed_not_no_results(monkeypatch):
    monkeypatch.setattr(query_acris, "log_search", lambda *args, **kwargs: None)
    args = query_acris.build_parser().parse_args(
        ["party", "BUYER LLC", "--exact"]
    )

    class ChangedSchema:
        def query(self, *args, **kwargs):
            return _fetch([{"party_type": "2", "name": "BUYER LLC"}])

    result = query_acris.execute(
        args,
        source=ChangedSchema(),
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "normalization_failed"


def test_enrichment_failure_preserves_primary_hits_as_partial(monkeypatch):
    monkeypatch.setattr(query_acris, "log_search", lambda *args, **kwargs: None)
    args = query_acris.build_parser().parse_args(
        ["party", "BUYER LLC", "--exact"]
    )

    class EnrichmentFailure:
        calls = 0
        max_records = 50_000

        def query(self, dataset_id, parameters, *, requested_limit, cursor=None):
            self.calls += 1
            if self.calls == 1:
                return _fetch(
                    [
                        {
                            "document_id": "2024001",
                            "party_type": "2",
                            "name": "BUYER LLC",
                        }
                    ]
                )
            raise TransportError("enrichment failed", url="https://example.invalid")

    result = query_acris.execute(
        args,
        source=EnrichmentFailure(),
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.records[0]["document_id"] == "2024001"
    assert result.records[0]["enrichment_complete"] is False
    assert result.errors[0].code == "transport_error"


def test_interactive_catalog_mode_returns_without_source_request(monkeypatch):
    monkeypatch.setattr(query_acris, "log_search", lambda *args, **kwargs: None)
    args = query_acris.build_parser().parse_args(["party", "BUYER LLC", "--exact"])
    decision = {
        "source_id": query_acris.SOURCE_ID,
        "allowed": False,
        "access_class": "C",
        "automation_disposition": "prohibited",
        "reason": "automation prohibited by reviewed terms",
        "reason_code": "automation_not_approved",
    }

    def deny(_args):
        raise AcquisitionUnavailableError(decision)

    monkeypatch.setattr(query_acris, "_require_access", deny)

    class MustNotRun:
        def query(self, *args, **kwargs):
            raise AssertionError("network source was unexpectedly called")

    result = query_acris.execute(args, source=MustNotRun())

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].category == "access"


def test_source_context_uses_user_cap_and_reviewed_page_bound():
    args = query_acris.build_parser().parse_args(
        [
            "party",
            "BUYER LLC",
            "--max-records",
            "90000",
            "--page-size",
            "70000",
            "--minimum-interval",
            "0",
        ]
    )

    source = query_acris._ACRISSource(
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


def test_richmond_bbl_is_reported_as_outside_coverage_without_a_query(
    monkeypatch,
):
    logged = []
    monkeypatch.setattr(
        query_acris,
        "log_search",
        lambda *args, **kwargs: logged.append(args),
    )
    args = query_acris.build_parser().parse_args(
        [
            "address",
            "--borough",
            "5",
            "--block",
            "1",
            "--lot",
            "1",
        ]
    )

    class MustNotRun:
        def query(self, *args, **kwargs):
            raise AssertionError("out-of-coverage source query was attempted")

    result = query_acris.execute(
        args,
        source=MustNotRun(),
        access_decision=ALLOWED,
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "outside_source_coverage"
    assert logged[0][2] is None
