from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_harris_court_bulk, query_state_courts
from tools.public_records_contract import PublicRecordsResult
from tools.seed_public_records_catalog import seed_catalog


def _parse(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_shared_routes_expose_only_truthful_artifact_operations() -> None:
    routes = query_state_courts.LIVE_ROUTES[
        query_state_courts.HARRIS_COURT_BULK_SOURCE_ID
    ]
    guidance = query_state_courts._source_guidance(
        query_state_courts.HARRIS_COURT_BULK_SOURCE_ID
    )

    assert sorted(routes) == [
        "discovery",
        "documents",
        "download",
        "probe",
    ]
    assert guidance["unified_operations"] == sorted(routes)
    assert "ingest_harris_court_bulk.py" in guidance["archive_ingest"]
    assert "streaming ingester" in guidance["note"]
    assert "search" not in routes
    assert "case" not in routes
    assert "docket" not in routes


def test_discovery_translation_has_no_default_cap_and_supports_source_filters() -> None:
    all_artifacts = query_state_courts._harris_court_bulk_args(
        _parse(
            "discovery",
            "*",
            "--source",
            query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
        ),
        "list",
    )
    civil = query_state_courts._harris_court_bulk_args(
        _parse(
            "discovery",
            "Civil",
            "--source",
            query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
            "--case-type",
            "activity",
            "--after",
            "2026-07-01",
            "--limit",
            "7",
        ),
        "list",
    )
    filename = query_state_courts._harris_court_bulk_args(
        _parse(
            "discovery",
            "HistoricalCurrent",
            "--source",
            query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
        ),
        "list",
    )

    assert all_artifacts.command == "list"
    assert all_artifacts.section is None
    assert all_artifacts.family is None
    assert all_artifacts.result_limit is None
    assert civil.section == "Civil"
    assert civil.family == "activity"
    assert civil.published_after == "2026-07-01"
    assert civil.result_limit == 7
    assert filename.text_filter == "HistoricalCurrent"


def test_inspect_probe_and_download_translate_exact_artifact_operations(
    tmp_path: Path,
) -> None:
    locator = r"Civil\2024-08-15 FIELD_CODES.xlsx"
    inspect = query_state_courts._harris_court_bulk_args(
        _parse(
            "documents",
            locator,
            "--source",
            query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
        ),
        "inspect",
    )
    probe = query_state_courts._harris_court_bulk_args(
        _parse(
            "probe",
            "--source",
            query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
        ),
        "sentinel",
    )
    destination = tmp_path / "FIELD_CODES.xlsx"
    download = query_state_courts._harris_court_bulk_args(
        _parse(
            "download",
            locator,
            "--source",
            query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
            "--destination",
            str(destination),
        ),
        "download",
    )

    assert inspect.command == "inspect"
    assert inspect.artifact == locator
    assert inspect.sample_bytes == query_harris_court_bulk.DEFAULT_SAMPLE_BYTES
    assert probe.command == "sentinel"
    assert download.command == "download"
    assert download.artifact == locator
    assert download.destination == destination


def test_download_requires_caller_destination() -> None:
    args = _parse(
        "download",
        r"Civil\2024-08-15 FIELD_CODES.xlsx",
        "--source",
        query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
    )

    with pytest.raises(ValueError, match="requires --destination"):
        query_state_courts._harris_court_bulk_args(args, "download")


@pytest.mark.parametrize(
    ("operation", "selector", "direct_command"),
    [
        ("discovery", "*", "list"),
        (
            "documents",
            r"Civil\2024-08-15 FIELD_CODES.xlsx",
            "inspect",
        ),
        ("probe", "*", "sentinel"),
        (
            "download",
            r"Civil\2024-08-15 FIELD_CODES.xlsx",
            "download",
        ),
    ],
)
def test_shared_routes_invoke_the_corresponding_direct_artifact_operation(
    tmp_path: Path,
    monkeypatch,
    operation: str,
    selector: str,
    direct_command: str,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    calls = []

    def fake_execute(args, **_kwargs):
        calls.append(args)
        return PublicRecordsResult.success(
            query_harris_court_bulk.build_query(args),
            [],
        )

    monkeypatch.setattr(query_harris_court_bulk, "execute", fake_execute)
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)
    argv = [
        operation,
        selector,
        "--source",
        query_state_courts.HARRIS_COURT_BULK_SOURCE_ID,
        "--catalog-db",
        str(catalog_path),
    ]
    if operation == "download":
        argv.extend(["--destination", str(tmp_path / "artifact.xlsx")])
    if operation == "discovery":
        argv.extend(["--limit", "1"])

    payload = query_state_courts.execute(_parse(*argv))

    assert payload["status"] == "no_results"
    assert calls[0].command == direct_command
    if operation == "discovery":
        assert payload["query"]["query"]["requested_limit"] == 1
