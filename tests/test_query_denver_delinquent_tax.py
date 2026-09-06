from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook

from tools import query_denver_delinquent_tax as denver_tax


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/denver_delinquent_tax"
)
RELEASE_HTML = (FIXTURE_DIR / "release.html").read_text(encoding="utf-8")
WORKBOOK_FIXTURE = json.loads(
    (FIXTURE_DIR / "workbook_rows.json").read_text(encoding="utf-8")
)


def _allowed() -> dict[str, Any]:
    return {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
        "limits": {},
    }


def _args(*values: str):
    return denver_tax.build_parser().parse_args(list(values))


def _write_workbook(
    path: Path,
    *,
    rows: list[list[Any]] | None = None,
    title: str | None = None,
) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = title or WORKBOOK_FIXTURE["sheet_title"]
    for row in rows or WORKBOOK_FIXTURE["rows"]:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()
    return path


@pytest.fixture
def workbook_path(tmp_path: Path) -> Path:
    return _write_workbook(tmp_path / "denver-tax.xlsx")


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        denver_tax,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_release_parser_resolves_exact_official_latest_artifact():
    release = denver_tax.parse_release_page(RELEASE_HTML)

    assert release.tax_year == 2024
    assert release.url == (
        "https://www.denvergov.org/files/assets/public/v/2/finance/"
        "documents/treasury/"
        "dq410coccd_644988_final-adv-to-denver-post-8.28.2025.xlsx"
    )
    assert release.filename.endswith(".xlsx")
    assert release.page_size_label == "961KB"
    assert release.release_date == "2025-08-28"
    record = release.to_record()
    assert record["source_id"] == (
        "us-co-denver-delinquent-real-property-tax-list"
    )
    assert record["stable_key_fields"] == ["tax_year", "parcel_id"]


def test_release_parser_rejects_missing_ambiguous_and_nonofficial_links():
    with pytest.raises(
        denver_tax.DenverTaxSourceChanged,
        match="no recognized",
    ):
        denver_tax.parse_release_page("<html><body>No file</body></html>")

    duplicate = RELEASE_HTML.replace(
        "</section>",
        (
            '<a title="Delinquent Real Property Tax List" '
            'href="/files/assets/public/other-2025.xlsx">'
            "Download the Delinquent Real Property Tax List</a></section>"
        ),
    )
    with pytest.raises(
        denver_tax.DenverTaxSourceChanged,
        match="ambiguous",
    ):
        denver_tax.parse_release_page(duplicate)

    nonofficial = RELEASE_HTML.replace(
        "/files/assets/public/v/2/finance/documents/treasury/"
        "dq410coccd_644988_final-adv-to-denver-post-8.28.2025.xlsx",
        "https://example.test/list.xlsx",
    )
    with pytest.raises(
        denver_tax.DenverTaxSourceChanged,
        match="official HTTPS host",
    ):
        denver_tax.parse_release_page(nonofficial)


def test_inspect_workbook_validates_schema_year_blocks_and_stable_keys(
    workbook_path: Path,
):
    result = denver_tax.inspect_workbook(
        workbook_path,
        archive_policy=denver_tax.ArchiveSafetyPolicy(
            max_members=100,
            max_total_uncompressed_bytes=10_000_000,
            max_member_uncompressed_bytes=5_000_000,
            max_compression_ratio=1_000,
        ),
    )

    assert result["data_row_count"] == 4
    assert result["rows_by_tax_year"] == {"2023": 1, "2024": 3}
    assert result["tax_year_markers"] == [
        {"row": 2, "tax_year": 2023},
        {"row": 4, "tax_year": 2024},
    ]
    assert result["schema"]["headers"] == list(
        denver_tax.EXPECTED_HEADERS
    )
    assert result["artifact_sha256"] == hashlib.sha256(
        workbook_path.read_bytes()
    ).hexdigest()
    assert result["adapter_schema_fingerprint"] == (
        denver_tax.ADAPTER_SCHEMA_FINGERPRINT
    )


def test_inspect_rejects_changed_headers_and_duplicate_stable_keys(
    tmp_path: Path,
):
    changed = [list(row) for row in WORKBOOK_FIXTURE["rows"]]
    changed[0][6] = "New Total"
    changed_path = _write_workbook(
        tmp_path / "changed.xlsx",
        rows=changed,
    )
    with pytest.raises(
        denver_tax.DenverTaxSourceChanged,
        match="recognized data sheet",
    ):
        denver_tax.inspect_workbook(changed_path)

    duplicate = [list(row) for row in WORKBOOK_FIXTURE["rows"]]
    duplicate.append(list(duplicate[4]))
    duplicate_path = _write_workbook(
        tmp_path / "duplicate.xlsx",
        rows=duplicate,
    )
    with pytest.raises(
        denver_tax.DenverTaxSourceChanged,
        match="duplicates",
    ):
        denver_tax.inspect_workbook(duplicate_path)


def test_search_without_a_caller_cap_returns_every_matching_row(
    workbook_path: Path,
):
    args = _args("search", "--artifact", str(workbook_path))

    result = denver_tax.execute(
        args,
        access_decision=_allowed(),
        client=object(),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 4
    assert result.query.query.requested_limit is None
    assert result.next_cursor is None
    record = result.records[1]
    assert record["record_kind"] == "property_tax_delinquency"
    assert record["native_parcel_id"] == "05044-12-043-000"
    assert record["native_account_id"] == "05044-12-043-000"
    assert record["stable_account_key"] == "2024:05044-12-043-000"
    assert record["tax_year"] == 2024
    assert record["owner_names"] == (
        "ALPHA HOLDINGS LLC",
        "BETA MANAGER LLC",
    )
    assert record["situs_address"]["raw"] == "926 W 10TH AVE"
    assert record["release_date"] is None
    assert record["delinquency_status"] == "delinquent_as_published"
    assert record["delinquency_category"] is None
    assert record["amounts"] == {
        "total_due": 13350.03,
        "tax": 12704.78,
        "interest": 635.25,
        "fees": 10,
        "currency": "USD",
    }
    assert record["valuation"]["parcel_valuation"] == 695410
    assert record["tax_sale_indicator"]["status"] == (
        "prior_tax_sale_unredeemed"
    )
    assert record["partial_payment_indicator"]["status"] == (
        "partially_paid"
    )
    assert record["raw"]["Owner Name"] == "ALPHA HOLDINGS LLC"
    assert record["canonical_ref"].endswith(
        "/tax-delinquency/2024%3A05044-12-043-000"
    )


def test_search_filters_and_caller_ceiling_have_resumable_cursor(
    workbook_path: Path,
):
    first = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--tax-year",
            "2024",
            "--max-records",
            "1",
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert first.status.value == "partial"
    assert [row["native_parcel_id"] for row in first.records] == [
        "05044-12-043-000"
    ]
    cursor_match = denver_tax.CURSOR_RE.fullmatch(first.next_cursor or "")
    assert cursor_match is not None
    assert cursor_match.group("row") == "6"

    resumed = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--tax-year",
            "2024",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert resumed.status.value == "ok"
    assert [row["native_parcel_id"] for row in resumed.records] == [
        "02354-12-017-000",
        "02331-09-267-267",
    ]


def test_cursor_rejects_changed_criteria_before_resuming(
    workbook_path: Path,
):
    first = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--tax-year",
            "2024",
            "--max-records",
            "1",
        ),
        access_decision=_allowed(),
        client=object(),
    )

    changed = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--owner",
            "ALPHA",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert changed.status.value == "unavailable"
    assert changed.errors[0].code == "denver_tax_cursor_criteria_mismatch"


def test_local_cursor_uses_content_identity_not_artifact_path(
    workbook_path: Path,
):
    first = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--tax-year",
            "2024",
            "--max-records",
            "1",
        ),
        access_decision=_allowed(),
        client=object(),
    )
    relocated = workbook_path.with_name("relocated-denver-tax.xlsx")
    shutil.copy2(workbook_path, relocated)

    resumed = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(relocated),
            "--tax-year",
            "2024",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert resumed.status.value == "ok"
    assert [row["native_parcel_id"] for row in resumed.records] == [
        "02354-12-017-000",
        "02331-09-267-267",
    ]


def test_local_cursor_rejects_changed_artifact_contents(
    workbook_path: Path,
):
    first = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--tax-year",
            "2024",
            "--max-records",
            "1",
        ),
        access_decision=_allowed(),
        client=object(),
    )
    changed_rows = [list(row) for row in WORKBOOK_FIXTURE["rows"]]
    changed_rows[4][0] = "CHANGED OWNER LLC"
    changed_artifact = _write_workbook(
        workbook_path.with_name("changed-artifact.xlsx"),
        rows=changed_rows,
    )

    changed = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(changed_artifact),
            "--tax-year",
            "2024",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert changed.status.value == "unavailable"
    assert changed.errors[0].code == "denver_tax_cursor_artifact_mismatch"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (
            ["--parcel", "0504412043000"],
            ["05044-12-043-000"],
        ),
        (
            ["--owner", "BETA MANAGER"],
            ["05044-12-043-000"],
        ),
        (
            ["--address", "LARIMER"],
            ["02331-09-267-267"],
        ),
        (
            ["--query", "PARK AVENUE"],
            ["02354-12-017-000"],
        ),
        (
            ["--tax-sale-only"],
            ["05044-12-043-000"],
        ),
        (
            ["--partially-paid-only"],
            ["05044-12-043-000", "02354-12-017-000"],
        ),
    ],
)
def test_fielded_filters(
    workbook_path: Path,
    arguments: list[str],
    expected: list[str],
):
    result = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            *arguments,
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert result.status.value == "ok"
    assert [row["native_parcel_id"] for row in result.records] == expected


def test_authoritative_empty_result_is_distinct_from_unavailable(
    workbook_path: Path,
):
    empty = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path),
            "--owner",
            "NO SUCH PUBLISHED OWNER",
        ),
        access_decision=_allowed(),
        client=object(),
    )
    missing = denver_tax.execute(
        _args(
            "search",
            "--artifact",
            str(workbook_path.with_name("missing.xlsx")),
        ),
        access_decision=_allowed(),
        client=object(),
    )

    assert empty.status.value == "no_results"
    assert empty.errors == ()
    assert missing.status.value == "unavailable"
    assert missing.errors[0].code == "denver_tax_unavailable"


class FakeAdapterClient:
    def __init__(
        self,
        source_workbook: Path,
        *,
        error: Exception | None = None,
    ) -> None:
        self.source_workbook = source_workbook
        self.error = error
        self.release = denver_tax.parse_release_page(RELEASE_HTML)
        self.download_calls: list[dict[str, Any]] = []

    def discover(self):
        if self.error:
            raise self.error
        return self.release

    def probe(self, release, *, sample_bytes):
        assert release == self.release
        return {
            "url": release.url,
            "http_status": 200,
            "content_length": self.source_workbook.stat().st_size,
            "media_type": denver_tax.XLSX_MEDIA_TYPE,
            "sample_size": sample_bytes,
            "sample_sha256": "a" * 64,
            "signature_hex": "504b0304",
        }

    def download_verified(
        self,
        release,
        destination,
        *,
        overwrite,
        max_bytes,
        archive_policy,
    ):
        destination = Path(destination)
        self.download_calls.append(
            {
                "release": release,
                "destination": destination,
                "overwrite": overwrite,
                "max_bytes": max_bytes,
                "archive_policy": archive_policy,
            }
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.source_workbook, destination)
        inspection = denver_tax.inspect_workbook(
            destination,
            archive_policy=archive_policy,
        )
        return {
            "release": release,
            "artifact_receipt": {
                "path": str(destination.resolve()),
                "url": release.url,
                "size": destination.stat().st_size,
                "sha256": inspection["artifact_sha256"],
                "signature_hex": "504b0304",
            },
            "workbook_inspection": inspection,
        }


def test_search_without_artifact_discovers_fetches_and_cleans_temp(
    workbook_path: Path,
):
    client = FakeAdapterClient(workbook_path)

    result = denver_tax.execute(
        _args("search", "--owner", "ALPHA"),
        access_decision=_allowed(),
        client=client,
    )

    assert result.status.value == "ok"
    assert len(client.download_calls) == 1
    temporary = client.download_calls[0]["destination"]
    assert temporary.parent.name.startswith("osint-denver-tax-")
    assert not temporary.exists()
    assert result.raw_artifact_refs == (client.release.url,)
    record = result.records[0]
    assert record["release_date"] == "2025-08-28"
    assert record["artifact_url"] == client.release.url


def test_probe_deep_checks_workbook_and_never_logs_search(
    workbook_path: Path,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        denver_tax,
        "log_search",
        lambda *values: calls.append(values),
    )
    client = FakeAdapterClient(workbook_path)

    result = denver_tax.execute(
        _args("probe"),
        access_decision=_allowed(),
        client=client,
    )

    assert result.status.value == "ok"
    assert result.records[0]["record_kind"] == "source_health_check"
    assert result.records[0]["canonical_ref"].endswith(
        "/source-health/live-release-probe"
    )
    assert result.records[0]["source_url"] == denver_tax.PUBLICATION_PAGE
    assert result.records[0]["artifact_probe"]["signature_hex"] == (
        "504b0304"
    )
    assert (
        result.records[0]["workbook_inspection"]["data_row_count"]
        == 4
    )
    assert "path" not in result.records[0]["artifact_receipt"]
    assert "artifact_path" not in result.records[0]["workbook_inspection"]
    assert (
        "path"
        not in result.records[0]["workbook_inspection"]["archive"]
    )
    assert result.raw_artifact_refs == (client.release.url,)
    assert calls == []


def test_official_latest_cursor_rejects_a_changed_release(
    workbook_path: Path,
):
    first_client = FakeAdapterClient(workbook_path)
    first = denver_tax.execute(
        _args(
            "search",
            "--tax-year",
            "2024",
            "--max-records",
            "1",
        ),
        access_decision=_allowed(),
        client=first_client,
    )
    changed_client = FakeAdapterClient(workbook_path)
    changed_client.release = denver_tax.ReleaseLink(
        tax_year=2025,
        url=first_client.release.url.replace("/v/2/", "/v/3/"),
        filename=first_client.release.filename.replace(
            "8.28.2025",
            "8.28.2026",
        ),
        link_text=first_client.release.link_text,
        page_size_label=first_client.release.page_size_label,
        release_date="2026-08-28",
    )

    changed = denver_tax.execute(
        _args(
            "search",
            "--tax-year",
            "2024",
            "--cursor",
            first.next_cursor,
        ),
        access_decision=_allowed(),
        client=changed_client,
    )

    assert changed.status.value == "unavailable"
    assert changed.errors[0].code == "denver_tax_cursor_artifact_mismatch"


def test_temporary_artifact_paths_are_sanitized_from_failures(
    workbook_path: Path,
):
    client = FakeAdapterClient(workbook_path)
    durable_hash = "b" * 64

    def fail_download(
        release,
        destination,
        *,
        overwrite,
        max_bytes,
        archive_policy,
    ):
        del overwrite, max_bytes, archive_policy
        transient = str(Path(destination).resolve())
        raise denver_tax.DenverTaxSourceChanged(
            f"could not inspect {transient}",
            details={
                "artifact_path": transient,
                "official_url": release.url,
                "sha256": durable_hash,
                "nested": {"path": transient},
            },
        )

    client.download_verified = fail_download
    result = denver_tax.execute(
        _args("search", "--owner", "ALPHA"),
        access_decision=_allowed(),
        client=client,
    )
    serialized = json.dumps(result.to_dict())

    assert result.status.value == "source_changed"
    assert "osint-denver-tax-" not in serialized
    assert client.release.url in serialized
    assert durable_hash in serialized


def test_search_logging_can_be_disabled_explicitly(
    workbook_path: Path,
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(
        denver_tax,
        "log_search",
        lambda *values: calls.append(values),
    )
    args = _args("search", "--artifact", str(workbook_path))

    denver_tax.execute(
        args,
        access_decision=_allowed(),
        client=object(),
        log_results=False,
    )
    assert calls == []

    denver_tax.execute(
        args,
        access_decision=_allowed(),
        client=object(),
        log_results=True,
    )
    assert len(calls) == 1
    assert calls[0][1] == denver_tax.SOURCE_ID
    assert calls[0][2] == 4


def test_catalog_access_decision_is_injected_and_denial_is_explicit():
    client = FakeAdapterClient(Path("unused.xlsx"))
    allowed = denver_tax.execute(
        _args("discover"),
        access_decision=_allowed(),
        client=client,
    )
    denied = denver_tax.execute(
        _args("discover"),
        access_decision={
            "allowed": False,
            "access_class": "C",
            "automation_disposition": "unclear",
            "reason": "interactive route",
            "reason_code": "interactive_route",
        },
        client=client,
    )

    assert (
        allowed.query.query.metadata["access_decision"]["access_class"]
        == "A"
    )
    assert denied.status.value == "human_required"
    assert denied.errors[0].code == "interactive_route"


def test_source_changed_failure_is_not_reported_as_empty(workbook_path: Path):
    result = denver_tax.execute(
        _args("discover"),
        access_decision=_allowed(),
        client=FakeAdapterClient(
            workbook_path,
            error=denver_tax.DenverTaxSourceChanged(
                "release link changed"
            ),
        ),
    )

    assert result.status.value == "source_changed"
    assert result.records == ()
    assert result.errors[0].code == "denver_tax_source_changed"


def test_output_flag_writes_the_public_record_envelope(
    workbook_path: Path,
    tmp_path: Path,
):
    output = tmp_path / "results.json"
    args = _args(
        "search",
        "--artifact",
        str(workbook_path),
        "--owner",
        "ALPHA",
        "--output",
        str(output),
    )
    result = denver_tax.execute(
        args,
        access_decision=_allowed(),
        client=object(),
    )

    denver_tax._emit(result, args)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["query"]["source"]["source_id"] == denver_tax.SOURCE_ID
    assert payload["records"][0]["native_parcel_id"] == (
        "05044-12-043-000"
    )


def test_cli_has_no_hidden_search_cap_and_help_is_runnable():
    args = _args("search")
    assert args.max_records is None
    assert args.artifact is None

    completed = subprocess.run(
        [
            sys.executable,
            "tools/query_denver_delinquent_tax.py",
            "search",
            "--help",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "--max-records" in completed.stdout
    assert "--artifact" in completed.stdout
