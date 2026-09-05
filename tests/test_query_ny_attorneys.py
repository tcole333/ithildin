from __future__ import annotations

import base64
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_ny_attorneys as ny
from tools.public_records_contract import ResultStatus
from tools.public_records_http import (
    PaginatedFetch,
    RestrictedHTTPError,
    inferred_schema,
    schema_fingerprint,
)


FIXTURES = Path(__file__).parent / "fixtures" / "ny_attorneys"
LIVE = os.environ.get("LIVE_PUBLIC_RECORDS") == "1"


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def parse_args(*values: str) -> Any:
    return ny.build_parser().parse_args(list(values))


class FixtureClient:
    def __init__(
        self,
        *,
        page_size: int = 1,
        rows_updated_at: int | None = None,
        missing_field: str | None = None,
    ) -> None:
        self.page_size = page_size
        self.records = fixture_json("records.json")
        self.metadata = fixture_json("metadata.json")
        if rows_updated_at is not None:
            self.metadata["rowsUpdatedAt"] = rows_updated_at
        if missing_field:
            self.metadata["columns"] = [
                column
                for column in self.metadata["columns"]
                if column["fieldName"] != missing_field
            ]
        self.metadata_calls = 0
        self.count_calls: list[str] = []
        self.query_calls: list[dict[str, Any]] = []

    def dataset_metadata(self) -> Mapping[str, Any]:
        self.metadata_calls += 1
        return deepcopy(self.metadata)

    def _filtered(self, where: str) -> list[dict[str, Any]]:
        if where == "1=1":
            return deepcopy(self.records)
        registration = re.search(r"registration_number=([0-9]+)", where)
        if registration:
            return [
                deepcopy(row)
                for row in self.records
                if row["registration_number"] == registration.group(1)
            ]
        required_values = set(
            re.findall(r"'%?([A-Z][A-Z .,&'-]*?)%?'", where)
        )
        filtered = []
        for row in self.records:
            searchable = " ".join(
                str(value).upper() for value in row.values() if value
            )
            if all(value in searchable for value in required_values):
                filtered.append(deepcopy(row))
        return filtered

    def count(self, where: str) -> int:
        self.count_calls.append(where)
        if where == "1=1":
            return 432_566
        return len(self._filtered(where))

    def query(
        self,
        parameters: Mapping[str, Any],
        *,
        requested_limit: int | None = None,
    ) -> PaginatedFetch:
        call = {
            "parameters": dict(parameters),
            "requested_limit": requested_limit,
        }
        self.query_calls.append(call)
        rows = self._filtered(str(parameters["$where"]))
        offset = int(parameters.get("$offset") or 0)
        remaining = rows[offset:]
        selected = (
            remaining
            if requested_limit is None
            else remaining[:requested_limit]
        )
        schema = inferred_schema(selected)
        pages = (
            max(1, (len(selected) + self.page_size - 1) // self.page_size)
            if selected
            else 1
        )
        return PaginatedFetch(
            records=tuple(selected),
            next_cursor=None,
            schema=schema,
            schema_fingerprint=schema_fingerprint(schema),
            pages_fetched=pages,
            requests_made=pages,
        )


def test_source_manifest_separates_primary_and_complementary_coverage() -> None:
    payload = ny.source_manifest()

    assert payload["primary_source"]["dataset_id"] == "eqw2-r5nb"
    assert payload["coverage"]["identity_key"] == "registration_number"
    assert len(payload["coverage"]["published_fields"]) == 20
    assert payload["pagination"]["transport_batch_size"] == 1_000
    assert payload["pagination"]["bounded_probe_records"] == 2
    capabilities = {item["name"] for item in payload["capabilities"]}
    assert "NY Open Data Socrata API" in capabilities
    assert "Unified Court System interactive directory" in capabilities
    assert "22 NYCRR 118.2 written request" in capabilities
    assert "Appellate Division discipline sources" in capabilities
    assert "NYSCEF case filings" in capabilities


def test_direct_adapter_adds_no_unpublished_pacing_default() -> None:
    args = parse_args("search", "Karp")

    assert args.minimum_interval == 0


def test_name_and_structured_filters_build_source_native_soql() -> None:
    args = parse_args(
        "search",
        "Brad O'Karp",
        "--match",
        "exact",
        "--company",
        "Paul Weiss",
        "--year-admitted",
        "1986",
        "--department",
        "1",
    )
    where = ny._search_where(args)

    assert "upper(first_name) = 'BRAD'" in where
    assert "upper(last_name) = 'O''KARP'" in where
    assert "upper(company_name) = 'PAUL WEISS'" in where
    assert "year_admitted=1986" in where
    assert "judicial_department_of_admission=1" in where


def test_registration_normalizes_identity_status_office_and_routes() -> None:
    result = ny.execute(
        parse_args("registration", "2064509"),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["name"]["display"] == "BRAD SCOTT KARP"
    assert record["native_ids"]["registration_number"] == "2064509"
    assert record["registration"]["status"] == "Currently registered"
    assert record["registration"]["year_admitted"] == 1986
    assert (
        record["registration"]["judicial_department_label"]
        == "First Judicial Department"
    )
    assert record["registration"]["next_registration"]["year_month"] == "2028-07"
    assert (
        record["organization"]["name"]
        == "PAUL WEISS RIFKIND WHARTON & GARRISON"
    )
    assert record["office"]["new_york_county_or_out_of_state"] == "New York"
    assert {
        route["name"] for route in record["complementary_routes"]
    } == {
        "Unified Court System interactive Attorney Directory",
        "22 NYCRR 118.2 written-request registration data",
        "Appellate Division public discipline sources",
        "NYSCEF civil case filings",
    }


def test_registration_preserves_whole_organization_name_with_comma() -> None:
    result = ny.execute(
        parse_args("registration", "1281450"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.records[0]["organization"]["name"] == "JASON KARP, ESQ."


def test_omitted_limit_exhausts_matches_and_preserves_transport_batch() -> None:
    client = FixtureClient(page_size=1)
    args = parse_args(
        "search",
        "Karp",
        "--field",
        "last-name",
        "--match",
        "exact",
        "--page-size",
        "1",
    )
    result = ny.execute(args, client=client, log_results=False)

    assert args.limit is None
    assert [row["source_record_id"] for row in result.records] == [
        "1281450",
        "1370170",
        "2064509",
    ]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None
    assert result.query.query.metadata["transport_page_size"] == 1
    assert client.query_calls[0]["requested_limit"] is None


def test_explicit_limit_retains_query_bound_snapshot_cursor() -> None:
    client = FixtureClient()
    first = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )

    assert [row["source_record_id"] for row in first.records] == ["1281450"]
    assert first.next_cursor
    second = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert [row["source_record_id"] for row in second.records] == ["1370170"]
    assert second.next_cursor
    assert client.query_calls[1]["parameters"]["$offset"] == 1


def test_cursor_rejects_different_query_and_changed_dataset_snapshot() -> None:
    first = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
        ),
        client=FixtureClient(),
        log_results=False,
    )

    mismatch = ny.execute(
        parse_args(
            "search",
            "Brad",
            "--field",
            "first-name",
            "--match",
            "exact",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    changed = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=FixtureClient(rows_updated_at=1785387838),
        log_results=False,
    )

    assert mismatch.status == ResultStatus.SOURCE_CHANGED
    assert mismatch.errors[0].code == "cursor_snapshot_changed"
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_cursor_binds_declared_schema_and_matching_total() -> None:
    first = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert first.next_cursor is not None

    changed_schema = FixtureClient()
    changed_schema.metadata["columns"][0]["description"] = (
        "Changed registration identity description"
    )
    schema_result = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=changed_schema,
        log_results=False,
    )

    class ChangedTotalClient(FixtureClient):
        def count(self, where: str) -> int:
            count = super().count(where)
            return count if where == "1=1" else count + 1

    total_result = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=ChangedTotalClient(),
        log_results=False,
    )

    assert schema_result.status == ResultStatus.SOURCE_CHANGED
    assert schema_result.errors[0].code == "cursor_snapshot_changed"
    assert schema_result.errors[0].details["field"] == "schema"
    assert total_result.status == ResultStatus.SOURCE_CHANGED
    assert total_result.errors[0].code == "cursor_snapshot_changed"
    assert total_result.errors[0].details["field"] == "total"


def test_cursor_rejects_mutated_offset_with_stale_checksum() -> None:
    first = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert first.next_cursor is not None

    encoded = first.next_cursor[len(ny.CURSOR_PREFIX) :]
    payload = json.loads(
        base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        ).decode("utf-8")
    )
    payload["offset"] = 2
    mutated = ny.CURSOR_PREFIX + (
        base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        .decode("ascii")
        .rstrip("=")
    )
    result = ny.execute(
        parse_args(
            "search",
            "Karp",
            "--field",
            "last-name",
            "--match",
            "exact",
            "--limit",
            "1",
            "--cursor",
            mutated,
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "cursor_invalid"


def test_registration_no_result_is_not_a_source_failure() -> None:
    result = ny.execute(
        parse_args("registration", "9999999"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()


def test_missing_declared_field_is_source_changed() -> None:
    result = ny.execute(
        parse_args("registration", "2064509"),
        client=FixtureClient(missing_field="status"),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["missing_fields"] == ("status",)


def test_probe_is_bounded_and_reports_full_dataset_coverage() -> None:
    client = FixtureClient()
    result = ny.execute(
        parse_args("probe", "--page-size", "17"),
        client=client,
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert result.query.query.requested_limit == 2
    assert client.query_calls[0]["requested_limit"] == 2
    assert client.metadata_calls == 2
    assert client.count_calls == [
        f"registration_number={int(ny.PROBE_REGISTRATION_NUMBER)}",
        "1=1",
    ]
    assert len(client.query_calls) == 1
    assert record["total_registration_rows"] == 432_566
    assert record["declared_field_count"] == 20
    assert record["transport_page_size"] == 17
    assert record["requests_made"] == 5
    assert record["request_breakdown"] == {
        "initial_metadata": 1,
        "matching_count": 1,
        "sentinel_query": 1,
        "final_metadata": 1,
        "total_count": 1,
    }
    assert (
        record["sentinel"]["native_ids"]["registration_number"]
        == ny.PROBE_REGISTRATION_NUMBER
    )


def test_http_access_failure_preserves_structured_status() -> None:
    class RestrictedClient(FixtureClient):
        def query(
            self,
            parameters: Mapping[str, Any],
            *,
            requested_limit: int | None = None,
        ) -> PaginatedFetch:
            del parameters, requested_limit
            raise RestrictedHTTPError(403, url=ny.QUERY_URL)

    result = ny.execute(
        parse_args("registration", "2064509"),
        client=RestrictedClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.RESTRICTED
    assert result.errors[0].code == "access_restricted"


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_exact_name_and_registration_lookup() -> None:
    search = ny.execute(
        parse_args(
            "search",
            "Brad Karp",
            "--match",
            "exact",
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )
    registration = ny.execute(
        parse_args(
            "registration",
            ny.PROBE_REGISTRATION_NUMBER,
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )

    assert search.status == ResultStatus.OK
    assert [
        row["native_ids"]["registration_number"] for row in search.records
    ] == [ny.PROBE_REGISTRATION_NUMBER]
    assert search.next_cursor is None
    assert search.query.query.requested_limit is None
    assert registration.status == ResultStatus.OK
    assert (
        registration.records[0]["organization"]["name"]
        == "PAUL WEISS RIFKIND WHARTON & GARRISON"
    )


@pytest.mark.skipif(not LIVE, reason="set LIVE_PUBLIC_RECORDS=1")
def test_live_probe_reports_current_schema_and_coverage() -> None:
    result = ny.execute(
        parse_args("probe", "--minimum-interval", "0.05"),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert result.status == ResultStatus.OK
    assert record["declared_field_count"] == 20
    assert record["total_registration_rows"] > 400_000
    assert record["dataset_id"] == "eqw2-r5nb"
    assert record["sentinel"]["registration"]["status"] == "Currently registered"
