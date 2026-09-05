from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_florida_ninth_opinions as ninth
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "public_records"
    / "florida_ninth_opinions"
    / "page-0.html"
)


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=ninth.SOURCE_ID,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.5},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_separates_archive_contract_from_rolling_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "html_suffix": b"<!-- first snapshot -->",
        "pdf": b"%PDF-1.7\nfirst fixture",
    }
    clients: list[Any] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.closed = False
            clients.append(self)

        def index(self, query: str | None, *, page: int) -> ninth.Artifact:
            assert query is None
            assert page == 0
            return ninth.Artifact(
                content=FIXTURE.read_bytes() + rolling["html_suffix"],
                source_url=f"{ninth.INDEX_URL}?page=0",
                media_type="text/html",
                headers={"content-type": "text/html"},
            )

        def document(self, url: str) -> ninth.Artifact:
            assert url == (
                "https://ninthcircuit.org/sites/default/files/06-45.pdf"
            )
            return ninth.Artifact(
                content=rolling["pdf"],
                source_url=url,
                media_type="application/pdf",
                headers={"content-type": "application/pdf"},
            )

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(ninth, "FloridaNinthOpinionsClient", FakeClient)
    first = public_records_monitor.probe_florida_ninth_opinions(_context())

    rolling.update(
        html_suffix=b"<!-- second snapshot -->",
        pdf=b"%PDF-1.7\nsecond fixture",
    )
    second = public_records_monitor.probe_florida_ninth_opinions(_context())

    assert first.status == "ok"
    assert first.result_count == 2
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    assert first.details["stable_contract"]["identity"]["stable_keys"] == [
        "native_document_id",
        "document_url",
    ]
    assert first.details["stable_contract"]["scope"] == {
        "publication_types": [
            "circuit_appellate_opinion",
            "certiorari_opinion",
            "writ_opinion",
        ],
        "general_trial_order_feed": False,
        "complete_trial_docket": False,
    }
    assert first.details["requests_made"] == 2
    assert all(client.closed for client in clients)
    assert all(
        client.kwargs["minimum_interval"] == 0.5 for client in clients
    )


def test_catalog_census_and_citation_preserve_the_narrow_source_role(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    decision = catalog.require_machine_acquisition(ninth.SOURCE_ID)
    assert decision["allowed"] is True
    source = catalog.show_source(ninth.SOURCE_ID)
    manifest = source["current_manifest"]

    assert manifest["stable_keys"] == [
        "native_document_id",
        "document_url",
    ]
    assert manifest["identity_contract"]["case_projection"] is False
    assert (
        manifest["publication_contract"]["record_grain"]
        == "official_opinion_index_occurrence_and_pdf"
    )
    assert manifest["publication_contract"]["general_trial_order_feed"] is False
    assert manifest["publication_contract"]["complete_trial_docket"] is False

    capabilities = {
        item["name"]: item["details"] for item in manifest["capabilities"]
    }
    assert capabilities["search_opinions"]["adapter_tool"] == (
        "query_florida_ninth_opinions.py"
    )
    assert capabilities["query_shared_state_courts"]["shared_operations"] == [
        "search"
    ]
    assert capabilities["ingest_state_court_records"]["projection"] == (
        "source_snapshot_only"
    )
    assert capabilities["probe_source"]["expected_requests"] == 2

    associations = manifest["census_associations"]
    assert len(associations) == 1
    assert associations[0]["jurisdiction_geoid"] == "12"
    assert associations[0]["role"] == "appellate_opinions"
    assert associations[0]["coverage"]["county_geoids"] == [
        "12095",
        "12097",
    ]
    assert associations[0]["coverage"]["court_level"] == "circuit_appellate"
    assert associations[0]["coverage_gaps"]

    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"STATECOURT_SOURCE:{ninth.SOURCE_ID}"] == (
        ninth.INDEX_URL
    )


def test_monitor_registration_is_bounded_and_visible() -> None:
    handler = public_records_monitor.HANDLER_REGISTRY[ninth.SOURCE_ID]

    assert handler.capability == "probe_source"
    assert handler.endpoint == ninth.INDEX_URL
    assert handler.expected_requests == 2
    assert handler.sentinel_record_count == 1
    assert handler.handler is public_records_monitor.probe_florida_ninth_opinions
