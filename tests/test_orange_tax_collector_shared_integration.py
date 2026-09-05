from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_orange_tax_collector as orange
from tools import query_property
from tools.public_records_contract import sha256_fingerprint


ACCOUNT = "012027000000001"
FORMATTED_ACCOUNT = "01-20-27-0000-00001"
ACCOUNT_TOKEN = (
    "b3JhbmdlOnJlYWxfZXN0YXRlOnBhcmVudHM6"
    "NTRjNWMzMGEtZDg1My0xMWVmLWIxZjktY2Y2ZTU3ZjIyODNi"
)


def _shared(command: str, *values: str):
    return query_property.build_parser().parse_args([command, *values])


def _translated(command: str, adapter_command: str, *values: str):
    args = _shared(
        command,
        *values,
        "--source",
        orange.SOURCE_ID,
    )
    return query_property._orange_tax_collector_args(
        args,
        adapter_command,
    )


def test_shared_routes_keep_live_portal_and_exact_account_semantics() -> None:
    routes = query_property.LIVE_ROUTES[orange.SOURCE_ID]

    assert {
        "search",
        "owner",
        "address",
        "account",
        "parcel",
        "discovery",
        "releases",
        "manifest",
        "probe",
        "download",
    } <= set(routes)
    assert "bill" not in routes

    for operation in ("search", "owner", "address"):
        translated = routes[operation].translate(
            _shared(
                operation,
                "ORANGE COUNTY BCC",
                "--source",
                orange.SOURCE_ID,
                "--jurisdiction",
                "12095",
            ),
            routes[operation].adapter_command,
        )
        assert translated.command == "search"
        assert translated.query == "ORANGE COUNTY BCC"

    for operation in ("account", "parcel"):
        translated = routes[operation].translate(
            _shared(
                operation,
                FORMATTED_ACCOUNT,
                "--source",
                orange.SOURCE_ID,
                "--county",
                "Orange County",
            ),
            routes[operation].adapter_command,
        )
        assert translated.command == "account"
        assert translated.account_or_token == FORMATTED_ACCOUNT

    discovery = _translated("discovery", "sources")
    assert discovery.command == "sources"
    with pytest.raises(ValueError, match="15-digit parcel account"):
        _translated("parcel", "account", ACCOUNT_TOKEN)


def test_local_historical_routes_require_explicit_artifact_and_dataset(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "TaxPaymentTape.zip"

    owner = _translated(
        "owner",
        "search",
        "LEWIS THOMAS",
        "--artifact-path",
        str(artifact),
        "--dataset-type",
        "current",
        "--tax-year",
        "2019",
        "--limit",
        "7",
    )
    assert owner.command == "bulk-search"
    assert owner.dataset == "current"
    assert owner.artifact == artifact
    assert owner.owner == "LEWIS THOMAS"
    assert owner.tax_year == 2019
    assert owner.limit == 7

    parcel = _translated(
        "parcel",
        "account",
        FORMATTED_ACCOUNT,
        "--artifact-path",
        str(artifact),
        "--dataset-type",
        "delinquent",
    )
    assert parcel.command == "bulk-search"
    assert parcel.dataset == "delinquent"
    assert parcel.account == FORMATTED_ACCOUNT

    address = _translated(
        "address",
        "search",
        "BRANTLEY HALL",
        "--artifact-path",
        str(artifact),
        "--dataset-type",
        "current",
    )
    assert address.command == "bulk-search"
    assert address.query == "BRANTLEY HALL"

    certificate = _translated(
        "search",
        "search",
        "230000001",
        "--artifact-path",
        str(artifact),
        "--dataset-type",
        "delinquent",
        "--search-field",
        "certificate",
    )
    assert certificate.command == "bulk-search"
    assert certificate.certificate == "230000001"


def test_shared_bulk_control_routes_map_to_historical_operations(
    tmp_path: Path,
) -> None:
    releases = _translated("releases", "bulk-manifest")
    manifest = _translated("manifest", "bulk-manifest")
    assert releases.command == manifest.command == "bulk-manifest"

    probe = _translated(
        "probe",
        "bulk-probe",
        "--dataset-type",
        "delinquent",
        "--range-bytes",
        "128",
    )
    assert probe.command == "bulk-probe"
    assert probe.dataset == "delinquent"
    assert probe.sample_bytes == 128

    destination = tmp_path / "TaxPaymentTape.zip"
    download = _translated(
        "download",
        "bulk-download",
        "--dataset-type",
        "current",
        "--destination",
        str(destination),
        "--no-resume",
        "--expected-sha256",
        "a" * 64,
        "--max-download-bytes",
        "40000000",
    )
    assert download.command == "bulk-download"
    assert download.dataset == "current"
    assert download.destination == destination
    assert download.resume is False
    assert download.expected_sha256 == "a" * 64
    assert download.max_download_bytes == 40_000_000


def test_guidance_keeps_parcel_account_object_bill_and_rows_distinct() -> None:
    guidance = query_property._source_guidance(orange.SOURCE_ID)

    assert guidance["publication_paths"]["historical_bulk"][
        "publication_state"
    ] == "fixed_historical_snapshot"
    identity = guidance["native_identity"]
    assert identity["parcel_join"] != identity["portal_occurrence"]
    assert identity["portal_occurrence"] != identity["account_locator"]
    assert identity["account_locator"] != identity["bill_occurrence"]
    assert identity["bulk_row_occurrence"] == [
        "artifact SHA-256",
        "archive member path",
        "source row number",
    ]
    assert any(
        "bill detail" in operation
        for operation in guidance["direct_only_operations"]
    )
    assert guidance["official_complements"] == [
        "us-fl-dor-property-roll",
        "us-fl-orange-official-records",
        "us-fl-orange-comptroller-tax-deed-sales",
    ]
    assert "labels the bulk downloads Daily" in guidance["note"]
    assert "fixed 2020 snapshots" in guidance["note"]


def _landing_html(note: str) -> str:
    return f"""
      <p>{note}</p>
      <a href="{orange.CURRENT_LAYOUT_URL}">Layout for Current</a>
      <a href="{orange.CURRENT_ROLL_URL}">
        Daily Real Estate Update as of 02/17/20
      </a>
      <a href="{orange.DELINQUENT_LAYOUT_URL}">Layout for Delinquent</a>
      <a href="{orange.DELINQUENT_ROLL_URL}">
        Daily Delinquent Update as of 02/17/20
      </a>
    """


def _monitor_context() -> public_records_monitor.ProbeContext:
    return public_records_monitor.ProbeContext(
        source_id=orange.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=1,
        max_attempts=1,
        sample_bytes=64,
    )


def test_monitor_separates_contract_rolling_and_historical_observations(
    monkeypatch,
) -> None:
    state = {
        "owner": "ORANGE COUNTY BCC",
        "bill_status": "Paid",
        "landing_note": "first retrieval",
        "artifact_etag": '"fixed-etag"',
        "artifact_sample_revision": "initial",
    }

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 0

        def bulk_landing_html(self):
            self.request_count += 1
            return (
                orange.OFFICIAL_TAX_ROLL_PAGE,
                _landing_html(state["landing_note"]),
            )

        def search(self, query: str, *, limit: int):
            assert query == ACCOUNT
            assert limit == orange.ALGOLIA_HITS_PER_PAGE
            self.request_count += 1
            hit = {
                "source_id": orange.SOURCE_ID,
                "record_kind": "property_tax_account_search_hit",
                "parcel_join": {
                    "normalized_15_digit_account": ACCOUNT,
                    "formatted_account": FORMATTED_ACCOUNT,
                    "exact": True,
                },
                "native_account_id": FORMATTED_ACCOUNT,
                "algolia_object_id": (
                    "/Taxsys-GovHub/v0/items/"
                    "orange:real_estate:parents:"
                    "54c5c30a-d853-11ef-b1f9-cf6e57f2283b"
                ),
                "taxsys_account_token": ACCOUNT_TOKEN,
                "owners": [{"raw_name": state["owner"]}],
            }
            return orange.PortalSearchResult(
                records=(hit,),
                next_cursor=None,
                total_hits=1,
                pages_fetched=1,
                requests_made=1,
                response_contract_fingerprints=("stable-search-shape",),
            )

        def history_html(self, token: str):
            assert token == ACCOUNT_TOKEN
            self.request_count += 1
            return "https://example.test/history", "<table></table>"

    def fake_history(
        _html: str,
        *,
        account_token: str,
        parcel_account: str,
        source_url: str,
    ) -> list[dict[str, Any]]:
        assert account_token == ACCOUNT_TOKEN
        assert parcel_account == ACCOUNT
        return [
            {
                "source_id": orange.SOURCE_ID,
                "record_kind": "property_tax_bill_history",
                "parcel_join": {
                    "normalized_15_digit_account": parcel_account
                },
                "taxsys_account_token": account_token,
                "bill_uuid": "ca0e3d54-aad7-11f0-bb75-005056815849",
                "bill_status": state["bill_status"],
                "source_url": source_url,
            }
        ]

    def fake_bulk_probe(
        artifact,
        context: public_records_monitor.ProbeContext,
        *,
        user_agent: str,
    ):
        assert user_agent == orange.USER_AGENT
        publication = next(
            publication
            for publication in orange.BULK_PUBLICATIONS.values()
            if publication.data_url == artifact.url
        )
        sample_size = context.sample_bytes or 4096
        return (
            {
                "url": artifact.url,
                "http_status": 200,
                "content_length": publication.observed_data_size,
                "media_type": "application/zip",
                "etag": state["artifact_etag"],
                "last_modified": "Mon, 17 Feb 2020 12:00:00 GMT",
                "accept_ranges": True,
                "source_sha256": None,
                "sample_size": sample_size,
                "sample_sha256": (
                    f"{publication.dataset}-"
                    f"{state['artifact_sample_revision']}-sample"
                ),
                "signature_hex": "504b0304",
                "format_hint": "zip",
                "headers": {},
            },
            2,
        )

    monkeypatch.setattr(orange, "OrangeTaxPortalClient", FakeClient)
    monkeypatch.setattr(orange, "parse_bill_history_html", fake_history)
    monkeypatch.setattr(
        public_records_monitor,
        "_counted_bulk_probe",
        fake_bulk_probe,
    )

    first = public_records_monitor.probe_orange_tax_collector(
        _monitor_context()
    )
    state.update(
        {
            "owner": "CURRENT ACCOUNT LABEL",
            "bill_status": "Open",
            "landing_note": "second retrieval",
        }
    )
    second = public_records_monitor.probe_orange_tax_collector(
        _monitor_context()
    )

    assert first.status == second.status == "ok"
    assert first.result_count == second.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    first_historical = first.details["historical_artifact_observations"]
    second_historical = second.details["historical_artifact_observations"]
    assert first_historical["landing"]["page_sha256"] != (
        second_historical["landing"]["page_sha256"]
    )
    assert first_historical["full_bulk_artifacts_downloaded"] == 0
    assert first_historical["bulk_artifact_sample_bytes_read"] == 128
    assert first.details["requests_made"] == 7
    assert first.details["portal_requests"] == 3
    assert first.details["bulk_probe_requests"] == 4
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )

    identity = first.details["stable_contract"]["identity"]
    assert identity["parcel_join"] != identity["portal_occurrence"]
    assert identity["portal_occurrence"] != identity["account_locator"]
    assert identity["account_locator"] != identity["bill_occurrence"]

    state["artifact_etag"] = '"changed-etag"'
    third = public_records_monitor.probe_orange_tax_collector(
        _monitor_context()
    )
    assert third.schema_sha256 == second.schema_sha256
    assert third.artifact_sha256 == second.artifact_sha256
    assert (
        third.details["artifact_transport_observations"]["current"]["etag"]
        == '"changed-etag"'
    )
    assert third.details["stable_contract"] == second.details[
        "stable_contract"
    ]

    state["artifact_sample_revision"] = "changed"
    fourth = public_records_monitor.probe_orange_tax_collector(
        _monitor_context()
    )
    assert fourth.schema_sha256 == third.schema_sha256
    assert fourth.artifact_sha256 != third.artifact_sha256

    spec = public_records_monitor.HANDLER_REGISTRY[orange.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_orange_tax_collector
    assert spec.expected_requests == 7
    assert spec.sample_bytes == 64


def test_monitor_preserves_orange_source_change_status() -> None:
    observation = public_records_monitor._exception_observation(
        orange.OrangeTaxSourceChanged(
            "changed",
            details={"component": "historical_data_zip"},
        ),
        endpoint=orange.ALGOLIA_URL,
        latency_ms=1,
    )

    assert observation.status == "source_changed"
    assert observation.details["error"]["code"] == (
        "orange_tax_source_changed"
    )
