from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from tools import query_govos_recorders as govos
from tools import query_reeves_records as recorder
from tools.kofile_publicsearch import (
    KofileBootstrap,
    KofilePageImage,
    KofileSearchPage,
)
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/reeves_records")
SEARCH_RECORD = json.loads(
    (FIXTURE_DIR / "search_record.json").read_text()
)
DOCUMENT_DETAIL = json.loads(
    (FIXTURE_DIR / "document_detail.json").read_text()
)
PAGE_BYTES = b"\x89PNG\r\n\x1a\nshared-recorder-fixture"


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def bootstrap(self, *, force=False):
        self.calls.append(("bootstrap", force))
        return KofileBootstrap(
            state={},
            auth_token="transient-token",
            ip="203.0.113.50",
            tenant_id="42011",
            department_codes=("RP", "MISC", "UCC"),
            department_date_ranges={
                "RP": {"recordedDateRange": "19000101,20260729"}
            },
        )

    def search(self, **kwargs):
        self.calls.append(("search", kwargs))
        return KofileSearchPage(
            records=(SEARCH_RECORD,),
            total_count=1,
            statistics={},
            offset=kwargs.get("offset", 0),
            limit=kwargs.get("limit", 1),
            next_offset=None,
            response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
        )

    def fetch_document(self, doc_id):
        self.calls.append(("document", doc_id))
        return DOCUMENT_DETAIL

    def fetch_page_image(self, doc_id, page_number):
        self.calls.append(("page", doc_id, page_number))
        return KofilePageImage(
            document=DOCUMENT_DETAIL,
            page_number=page_number,
            source_url="https://example.invalid/transient-signed-page",
            media_type="image/png",
            content=PAGE_BYTES,
            etag='"fixture"',
        )

    def close(self):
        self.calls.append(("close",))


def _parse(*values: str):
    return govos.build_parser().parse_args(list(values))


def test_tenant_catalog_has_unique_source_and_jurisdiction_identity():
    assert len(govos.TENANTS) == 7
    assert len(govos.TENANTS_BY_SOURCE) == 7
    assert len({tenant.county_geoid for tenant in govos.TENANTS}) == 7
    assert govos.TENANTS_BY_SOURCE[
        "us-pa-berks-recorder-publicsearch"
    ].supported_departments == ("RP", "MISC")
    kent = govos.TENANTS_BY_SOURCE[
        "us-de-kent-recorder-publicsearch"
    ]
    assert kent.supported_departments == ("RP", "UCC")
    assert "full-history complement" in kent.coverage
    denver = govos.TENANTS_BY_SOURCE[
        "us-co-denver-recorder-publicsearch"
    ]
    assert denver.supported_departments == ("RP", "MAR", "MISC")
    assert denver.county_geoid == "08031"
    assert denver.probe_document_id == 293353911
    franklin = govos.TENANTS_BY_SOURCE[
        "us-oh-franklin-county-recorder-publicsearch"
    ]
    assert franklin.jurisdiction_name == "Franklin County, Ohio"
    assert franklin.county_geoid == "39049"
    assert franklin.state_code == "OH"
    assert franklin.supported_departments == ("RP",)
    assert franklin.base_url == "https://franklin.oh.publicsearch.us"
    assert franklin.probe_instrument_number == "202607290091301"
    assert franklin.probe_document_id == 323279115
    assert franklin.probe_page_count == 6
    assert franklin.probe_page_sha256 == (
        "2e7e562081d4fd72b0728d7996c2a098"
        "c45a8f9fdbdc8ae1cc05872727c7c228"
    )


def test_franklin_tenant_uses_existing_govos_identity_and_query_contract(
    monkeypatch,
):
    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)
    source_id = "us-oh-franklin-county-recorder-publicsearch"

    result = govos.execute(
        _parse(
            "search",
            "--source",
            source_id,
            "202607290091301",
            "--limit",
            "1",
        ),
        client=FakeClient(),
    )

    assert result.status is ResultStatus.OK
    assert result.query.source.source_id == source_id
    assert result.query.jurisdiction.county_fips == "39049"
    record = result.to_dict()["records"][0]
    assert record["source_id"] == source_id
    assert record["native_document_id"] == "RP:20798096"
    assert record["canonical_ref"].startswith(
        f"PROPERTY:{source_id}/39049/"
    )
    assert record["source_url"] == (
        "https://franklin.oh.publicsearch.us/"
        "doc/20798096?department=RP"
    )


def test_omitted_limit_delegates_to_exhaustive_shared_engine():
    args = _parse(
        "search",
        "--source",
        "us-oh-franklin-county-recorder-publicsearch",
        "202607290091301",
    )

    assert args.limit is None


def test_search_cursor_is_bound_to_source_department_and_query(monkeypatch):
    class PagedClient(FakeClient):
        def __init__(self, total_count=2) -> None:
            super().__init__()
            self.total_count = total_count

        def search(self, **kwargs):
            self.calls.append(("search", kwargs))
            offset = kwargs.get("offset", 0)
            next_offset = offset + 1
            return KofileSearchPage(
                records=(SEARCH_RECORD,),
                total_count=self.total_count,
                statistics={},
                offset=offset,
                limit=kwargs.get("limit", 1),
                next_offset=(
                    next_offset if next_offset < self.total_count else None
                ),
                response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
            )

    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)
    source_id = "us-pa-berks-recorder-publicsearch"
    initial = govos.execute(
        _parse(
            "search",
            "--source",
            source_id,
            "18-06481",
            "--limit",
            "1",
        ),
        client=PagedClient(),
    )
    cursor = initial.next_cursor

    assert cursor is not None
    assert cursor.startswith(recorder.SEARCH_CURSOR_PREFIX)

    replay_selections = (
        (
            "--source",
            "us-oh-franklin-county-recorder-publicsearch",
            "18-06481",
        ),
        (
            "--source",
            source_id,
            "--department",
            "MISC",
            "18-06481",
        ),
        ("--source", source_id, "DIFFERENT QUERY"),
    )
    for selection in replay_selections:
        client = PagedClient()
        result = govos.execute(
            _parse(
                "search",
                *selection,
                "--limit",
                "1",
                "--cursor",
                cursor,
            ),
            client=client,
        )
        assert result.status is ResultStatus.UNAVAILABLE
        assert result.errors[0].code == "cursor_query_mismatch"
        assert client.calls == []


def test_search_cursor_anchors_source_total(monkeypatch):
    class PagedClient(FakeClient):
        def __init__(
            self,
            total_count,
            response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
        ) -> None:
            super().__init__()
            self.total_count = total_count
            self.response_type = response_type

        def search(self, **kwargs):
            self.calls.append(("search", kwargs))
            offset = kwargs.get("offset", 0)
            return KofileSearchPage(
                records=(SEARCH_RECORD,),
                total_count=self.total_count,
                statistics={},
                offset=offset,
                limit=kwargs.get("limit", 1),
                next_offset=(offset + 1 if offset + 1 < self.total_count else None),
                response_type=self.response_type,
            )

    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)
    source_id = "us-pa-berks-recorder-publicsearch"
    selection = (
        "search",
        "--source",
        source_id,
        "18-06481",
        "--limit",
        "1",
    )
    initial = govos.execute(_parse(*selection), client=PagedClient(2))
    cursor = initial.next_cursor
    assert cursor is not None

    resumed = govos.execute(
        _parse(*selection, "--cursor", cursor),
        client=PagedClient(2),
    )
    assert resumed.status is ResultStatus.OK
    assert resumed.next_cursor is None

    changed = govos.execute(
        _parse(*selection, "--cursor", cursor),
        client=PagedClient(3),
    )
    assert changed.status is ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "search_cursor_snapshot_changed"

    changed_protocol = govos.execute(
        _parse(*selection, "--cursor", cursor),
        client=PagedClient(
            2,
            response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v7",
        ),
    )
    assert changed_protocol.status is ResultStatus.SOURCE_CHANGED
    assert changed_protocol.errors[0].code == "search_cursor_snapshot_changed"


def test_all_tenants_build_distinct_query_and_record_identity(monkeypatch):
    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)

    for tenant in govos.TENANTS:
        args = _parse(
            "search",
            "--source",
            tenant.source_id,
            tenant.probe_instrument_number,
            "--limit",
            "1",
        )
        result = govos.execute(args, client=FakeClient())
        record = result.to_dict()["records"][0]

        assert result.query.source.source_id == tenant.source_id
        assert result.query.source.base_url == tenant.base_url
        assert result.query.jurisdiction.county_fips == tenant.county_geoid
        assert record["source_id"] == tenant.source_id
        assert record["department_code"] == tenant.department
        assert record["native_document_id"] == "RP:20798096"
        assert record["canonical_ref"].startswith(
            f"PROPERTY:{tenant.source_id}/{tenant.county_geoid}/"
        )
        assert record["source_url"].startswith(
            f"{tenant.base_url}/doc/20798096"
        )


def test_shared_search_uses_selected_source_department_and_canonical_identity(
    monkeypatch,
):
    client = FakeClient()
    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)
    args = _parse(
        "search",
        "--source",
        "us-pa-berks-recorder-publicsearch",
        "--department",
        "MISC",
        "18-06481",
        "--limit",
        "10000",
    )

    result = govos.execute(args, client=client)

    assert result.status is ResultStatus.OK
    assert result.query.query.requested_limit == 10000
    assert result.query.query.parameters["department"] == "MISC"
    assert result.query.jurisdiction.county_fips == "42011"
    record = result.to_dict()["records"][0]
    assert record["source_id"] == "us-pa-berks-recorder-publicsearch"
    assert record["canonical_ref"].startswith(
        "PROPERTY:us-pa-berks-recorder-publicsearch/42011/"
    )
    assert record["source_url"] == (
        "https://berks.pa.publicsearch.us/"
        "doc/20798096?department=MISC"
    )
    assert client.calls[0][1]["department"] == "MISC"


def test_tenant_specific_department_mismatch_is_structured(monkeypatch):
    client = FakeClient()
    logged = []
    monkeypatch.setattr(
        recorder,
        "log_search",
        lambda *values: logged.append(values),
    )
    args = _parse(
        "search",
        "--source",
        "us-pa-berks-recorder-publicsearch",
        "--department",
        "UCC",
        "EXAMPLE",
    )

    result = govos.execute(args, client=client)

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "department_not_supported"
    assert result.errors[0].details["supported_departments"] == (
        "RP",
        "MISC",
    )
    assert result.query.query.parameters["department"] == "UCC"
    assert len(logged) == 1
    assert logged[0][1:] == (
        "us-pa-berks-recorder-publicsearch",
        None,
    )
    assert client.calls == []


def test_probe_uses_tenant_sentinel_and_validates_page_digest(monkeypatch):
    source_id = "us-pa-berks-recorder-publicsearch"
    original = govos.TENANTS_BY_SOURCE[source_id]
    fixture_tenant = replace(
        original,
        probe_instrument_number="18-06481",
        probe_document_id=20798096,
        probe_page_count=36,
        probe_page_sha256=hashlib.sha256(PAGE_BYTES).hexdigest(),
    )
    monkeypatch.setitem(
        govos.TENANTS_BY_SOURCE,
        source_id,
        fixture_tenant,
    )
    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)
    client = FakeClient()

    result = govos.execute(
        _parse("probe", "--source", source_id),
        client=client,
    )

    assert result.status is ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["probe"]["page_1"] == {
        "sha256": hashlib.sha256(PAGE_BYTES).hexdigest(),
        "size": len(PAGE_BYTES),
        "media_type": "image/png",
    }
    assert [call[0] for call in client.calls] == [
        "bootstrap",
        "search",
        "document",
        "page",
    ]
