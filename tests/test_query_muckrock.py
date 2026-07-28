import json
import sys
from types import SimpleNamespace

import pytest
from squarelet.exceptions import CredentialsFailedError, SquareletError

from tools import muckrock_index, query_muckrock


class FakeResults:
    def __init__(self, results, count=None, next_url=None):
        self.results = list(results)
        self.count = len(self.results) if count is None else count
        self.next_url = next_url

    def __iter__(self):
        yield from self.results


class FakeFile(SimpleNamespace):
    pass


class FakeCommunication(SimpleNamespace):
    def get_files(self):
        return FakeResults(getattr(self, "file_objects", []))


class FakeRequest(SimpleNamespace):
    def get_communications(self):
        return FakeResults(getattr(self, "communication_objects", []))


@pytest.fixture(autouse=True)
def clear_agency_cache():
    query_muckrock._agency_cache.clear()


def make_request(request_id=78799, *, agency=None, communications=None):
    return FakeRequest(
        id=request_id,
        title="USMS files re: Jeffrey Epstein",
        status="done",
        agency=agency or {"id": 14, "name": "U.S. Marshals Service"},
        datetime_submitted="2019-08-10T15:30:40-04:00",
        datetime_done="2019-11-01T12:00:00-04:00",
        tracking_id="2019USMS34199",
        slug="usms-files-re-jeffrey-epstein",
        requested_docs="Records concerning Jeffrey Epstein",
        communication_objects=communications or [],
    )


def test_create_client_requires_both_credentials(monkeypatch):
    monkeypatch.delenv("MUCKROCK_USERNAME", raising=False)
    monkeypatch.delenv("MUCKROCK_PASSWORD", raising=False)

    with pytest.raises(query_muckrock.MuckRockConfigurationError) as exc_info:
        query_muckrock._create_client()

    assert "MUCKROCK_USERNAME and MUCKROCK_PASSWORD" in str(exc_info.value)


def test_create_client_preserves_password_characters(monkeypatch):
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MUCKROCK_USERNAME", "researcher")
    monkeypatch.setenv("MUCKROCK_PASSWORD", "p@ss$word#with=punctuation")
    monkeypatch.setattr(query_muckrock, "MuckRock", fake_client)

    query_muckrock._create_client()

    assert captured == {
        "username": "researcher",
        "password": "p@ss$word#with=punctuation",
    }


def test_missing_credentials_exits_nonzero_without_output(monkeypatch, tmp_path):
    output = tmp_path / "muckrock.json"
    monkeypatch.delenv("MUCKROCK_USERNAME", raising=False)
    monkeypatch.delenv("MUCKROCK_PASSWORD", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "search",
            "epstein",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 1
    assert not output.exists()


def test_auth_failure_exits_nonzero_without_output(monkeypatch, tmp_path):
    output = tmp_path / "muckrock.json"

    def fail_auth():
        raise CredentialsFailedError("incorrect credentials")

    monkeypatch.setattr(query_muckrock, "_create_client", fail_auth)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "search",
            "epstein",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 1
    assert not output.exists()


def test_api_failure_is_not_written_as_zero_results(monkeypatch, tmp_path):
    output = tmp_path / "muckrock.json"

    class FailingRequests:
        @staticmethod
        def list(**_params):
            raise SquareletError("remote failure")

    client = SimpleNamespace(requests=FailingRequests())
    monkeypatch.setattr(query_muckrock, "_create_client", lambda: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "search",
            "epstein",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 1
    assert not output.exists()


def test_search_uses_v2_full_text_filter_and_preserves_total(
    monkeypatch, tmp_path
):
    output = tmp_path / "muckrock.json"
    calls = {}
    logged = []
    rows = [
        make_request(1),
        make_request(2),
        make_request(3),
    ]

    class FakeRequests:
        @staticmethod
        def list(**params):
            calls.update(params)
            return FakeResults(rows, count=60)

    client = SimpleNamespace(requests=FakeRequests())
    monkeypatch.setattr(query_muckrock, "_create_client", lambda: client)
    monkeypatch.setattr(
        query_muckrock,
        "_record_search",
        lambda query, count: logged.append((query, count)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "search",
            "Jeffrey Epstein",
            "--limit",
            "2",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 0
    payload = json.loads(output.read_text())
    assert calls == {"search": "Jeffrey Epstein", "page_size": 2}
    assert payload["total"] == 60
    assert payload["showing"] == 2
    assert [row["id"] for row in payload["results"]] == [1, 2]
    assert payload["results"][0]["file_count"] is None
    assert logged == [("Jeffrey Epstein", 2)]


def test_request_expands_communications_and_files(monkeypatch, tmp_path):
    output = tmp_path / "request.json"
    file_obj = FakeFile(
        id=806322,
        title="release.pdf",
        ffile="https://cdn.muckrock.com/foia_files/release.pdf",
        pages=6,
        datetime="2019-08-10T15:30:40-04:00",
        source="agency",
        description="Released records",
        doc_id="doc-1",
    )
    communication = FakeCommunication(
        id=767873,
        datetime="2019-08-10T15:30:40-04:00",
        from_user=14585,
        to_user=9913,
        subject="FOIA response",
        response=True,
        status="done",
        files=[806322],
        file_objects=[file_obj],
    )
    request = make_request(78799, communications=[communication])
    client = SimpleNamespace(
        requests=SimpleNamespace(retrieve=lambda request_id: request)
    )
    monkeypatch.setattr(query_muckrock, "_create_client", lambda: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "request",
            "78799",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 0
    payload = json.loads(output.read_text())
    assert payload["id"] == 78799
    assert payload["total_files"] == 1
    assert payload["total_pages"] == 6
    assert payload["communications"][0]["from_who"] == "14585"
    assert payload["communications"][0]["body"] == ""
    assert payload["communications"][0]["files"][0]["title"] == "release.pdf"


def test_download_uses_released_file_url(monkeypatch, tmp_path):
    file_obj = FakeFile(
        id=806322,
        title="release.pdf",
        ffile="https://cdn.muckrock.com/foia_files/release.pdf",
        pages=6,
    )
    communication = FakeCommunication(
        datetime="2019-08-10T15:30:40-04:00",
        file_objects=[file_obj],
    )
    request = make_request(78799, communications=[communication])
    client = SimpleNamespace(
        requests=SimpleNamespace(retrieve=lambda request_id: request)
    )
    downloads = []

    def fake_download(url, dest_path):
        downloads.append((url, dest_path))
        return True

    monkeypatch.setattr(query_muckrock, "_create_client", lambda: client)
    monkeypatch.setattr(query_muckrock, "_download_file", fake_download)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "download",
            "78799",
            "--dir",
            str(tmp_path),
        ],
    )

    assert query_muckrock.main() == 0
    assert downloads == [
        (
            "https://cdn.muckrock.com/foia_files/release.pdf",
            tmp_path / "78799" / "release.pdf",
        )
    ]


def test_project_uses_project_request_ids_and_counts_file_references(
    monkeypatch, tmp_path
):
    output = tmp_path / "project.json"
    communication = FakeCommunication(files=[1, 2])
    request = make_request(78799, communications=[communication])
    project = SimpleNamespace(
        id=507,
        title="Jeffrey Epstein files",
        requests=[78799],
    )
    client = SimpleNamespace(
        projects=SimpleNamespace(retrieve=lambda project_id: project),
        requests=SimpleNamespace(retrieve=lambda request_id: request),
    )
    monkeypatch.setattr(query_muckrock, "_create_client", lambda: client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "project",
            "507",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 0
    payload = json.loads(output.read_text())
    assert payload["project_id"] == 507
    assert payload["request_count"] == 1
    assert payload["requests"][0]["file_count"] == 2


def test_agency_search_uses_partial_name_filter(monkeypatch, tmp_path):
    output = tmp_path / "agencies.json"
    calls = {}
    agency = SimpleNamespace(
        id=10,
        name="Federal Bureau of Investigation",
        slug="federal-bureau-of-investigation",
        status="approved",
        jurisdiction=1,
    )

    class FakeAgencies:
        @staticmethod
        def list(**params):
            calls.update(params)
            return FakeResults([agency], count=1)

    client = SimpleNamespace(agencies=FakeAgencies())
    monkeypatch.setattr(query_muckrock, "_create_client", lambda: client)
    monkeypatch.setattr(query_muckrock, "_record_search", lambda *_args: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "agencies",
            "Federal Bureau",
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 0
    payload = json.loads(output.read_text())
    assert calls == {"name": "Federal Bureau", "page_size": 50}
    assert payload["results"][0]["id"] == 10


class FakePageManager:
    def __init__(self, pages, total=None):
        self.pages = pages
        self.total = total if total is not None else sum(map(len, pages.values()))
        self.calls = []

    def list(self, **params):
        self.calls.append(params)
        page = params["page"]
        later_pages = [number for number in self.pages if number > page]
        return FakeResults(
            self.pages.get(page, []),
            count=self.total,
            next_url="https://example.test/next" if later_pages else None,
        )


def _index_fixture_client():
    request = SimpleNamespace(
        id=137546,
        title="GEO Group environmental compliance records",
        requested_docs="Warnings and inspection records for private prisons",
        slug="geo-group-environmental-compliance-records",
        status="done",
        agency=8519,
        user=25665,
        embargo_status="public",
        datetime_submitted="2022-01-01T00:00:00-05:00",
        datetime_updated="2022-02-01T00:00:00-05:00",
        datetime_done="2022-02-01T00:00:00-05:00",
        tracking_id="EPA-2022-001",
        price="0.00",
        tags=[],
    )
    communication = SimpleNamespace(
        id=9001,
        foia=137546,
        from_user=None,
        to_user=25665,
        subject="Final response and released records",
        datetime="2022-02-01T00:00:00-05:00",
        response=True,
        autogenerated=False,
        communication="Attached are signed EPA warning letters. Password: release123",
        status="done",
        files=[7001, 7002],
    )
    unlinked_file = SimpleNamespace(
        id=7001,
        ffile="https://cdn.muckrock.com/release-warning.pdf",
        datetime="2022-02-01T00:00:00-05:00",
        title="signed-warning.pdf",
        source="EPA",
        description="Signed warning letter",
        doc_id=None,
        pages=12,
    )
    linked_file = SimpleNamespace(
        id=7002,
        ffile="https://cdn.muckrock.com/release-inspection.pdf",
        datetime="2022-02-01T00:00:00-05:00",
        title="inspection.pdf",
        source="EPA",
        description="Inspection record",
        doc_id="12345-inspection",
        pages=20,
    )
    agency = SimpleNamespace(
        id=8519,
        name="Environmental Protection Agency",
        slug="environmental-protection-agency",
        status="approved",
        jurisdiction=1,
        parent=None,
        appeal_agency=None,
        exempt=False,
        requires_proxy=False,
        types=[],
    )
    jurisdiction = SimpleNamespace(
        id=1,
        name="United States of America",
        slug="united-states-of-america",
        abbrev="US",
        level="federal",
        parent=None,
    )
    return SimpleNamespace(
        requests=FakePageManager({1: [request]}),
        communications=FakePageManager({1: [communication]}),
        files=FakePageManager({1: [unlinked_file, linked_file]}),
        agencies=FakePageManager({1: [agency]}),
        jurisdictions=FakePageManager({1: [jurisdiction]}),
    )


def test_index_crawl_links_files_and_filters_documentcloud(tmp_path):
    db_path = tmp_path / "muckrock.db"
    result = muckrock_index.crawl_index(
        _index_fixture_client(),
        db_path=db_path,
        delay=0,
    )

    assert result["rows_upserted"] == 6
    rows = muckrock_index.search_index(
        db_path=db_path,
        query="GEO Group",
        without_documentcloud=True,
        response_only=True,
    )
    assert [row["file_id"] for row in rows] == [7001]
    assert rows[0]["request_id"] == 137546
    assert rows[0]["agency_name"] == "Environmental Protection Agency"
    assert "Password: release123" in rows[0]["communication_excerpt"]
    assert rows[0]["documentcloud_unlinked"] is True

    stats = muckrock_index.index_stats(db_path)
    assert stats["counts"]["requests"] == 1
    assert stats["counts"]["communications"] == 1
    assert stats["counts"]["files"] == 2
    assert stats["documentcloud_linkage"]["documentcloud_unlinked"] == 1
    assert stats["documentcloud_linkage"]["documentcloud_linked"] == 1
    assert stats["documentcloud_linkage"]["unlinked_response_files"] == 1


def test_index_crawl_resumes_at_saved_page(tmp_path):
    db_path = tmp_path / "muckrock.db"
    first = SimpleNamespace(
        id=1,
        ffile="https://cdn.muckrock.com/one.pdf",
        title="one.pdf",
        doc_id=None,
    )
    second = SimpleNamespace(
        id=2,
        ffile="https://cdn.muckrock.com/two.pdf",
        title="two.pdf",
        doc_id=None,
    )
    manager = FakePageManager({1: [first], 2: [second]}, total=2)
    client = SimpleNamespace(files=manager)

    partial = muckrock_index.crawl_index(
        client,
        db_path=db_path,
        collections=["files"],
        max_pages=1,
        delay=0,
    )
    assert partial["collections"]["files"]["next_page"] == 2
    assert manager.calls == [
        {"page": 1, "page_size": 100, "ordering": "datetime"}
    ]

    completed = muckrock_index.crawl_index(
        client,
        db_path=db_path,
        collections=["files"],
        delay=0,
    )
    assert completed["collections"]["files"]["completed"] is True
    assert manager.calls[-1] == {
        "page": 2,
        "page_size": 100,
        "ordering": "datetime",
    }
    assert muckrock_index.index_stats(db_path)["counts"]["files"] == 2


def test_local_unlinked_search_does_not_require_api_credentials(
    monkeypatch, tmp_path
):
    db_path = tmp_path / "muckrock.db"
    muckrock_index.crawl_index(
        _index_fixture_client(),
        db_path=db_path,
        delay=0,
    )
    output = tmp_path / "results.json"
    monkeypatch.setattr(
        query_muckrock,
        "_create_client",
        lambda: pytest.fail("local index search should not authenticate"),
    )
    monkeypatch.setattr(query_muckrock, "_record_search", lambda *_args: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_muckrock.py",
            "unlinked-files",
            "EPA warning",
            "--db",
            str(db_path),
            "--output",
            str(output),
        ],
    )

    assert query_muckrock.main() == 0
    payload = json.loads(output.read_text())
    assert payload["without_documentcloud"] is True
    assert payload["responses_only"] is True
    assert [row["file_id"] for row in payload["results"]] == [7001]
