import json

import pytest

from tools import ingest_ohio


class FakeResponse:
    def __init__(self, status_code=200, content=b"%PDF-1.7\nfixture", content_type="application/pdf"):
        self.status_code = status_code
        self.content = content
        self.headers = {"content-type": content_type}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, timeout):
        self.urls.append((url, timeout))
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def reset_image_session(monkeypatch):
    monkeypatch.setattr(ingest_ohio, "_image_session", None)


def test_download_filing_image_writes_verified_pdf(tmp_path, monkeypatch):
    session = FakeSession([FakeResponse()])
    monkeypatch.setattr(ingest_ohio, "_image_session", session)

    result = ingest_ohio.download_filing_image("H363_1780", output_dir=tmp_path)

    assert result["status"] == "downloaded"
    assert result["document_id"] == "H363_1780"
    assert (tmp_path / "H363_1780.pdf").read_bytes().startswith(b"%PDF-")
    assert session.urls == [
        ("https://bizimage.ohiosos.gov/api/image/pdf/H363_1780", 60)
    ]


def test_download_filing_image_rejects_html_response(tmp_path, monkeypatch):
    session = FakeSession([FakeResponse(content=b"<html>challenge</html>", content_type="text/html")])
    monkeypatch.setattr(ingest_ohio, "_image_session", session)

    with pytest.raises(RuntimeError, match="not a PDF"):
        ingest_ohio.download_filing_image("F891_1891", output_dir=tmp_path)

    assert not (tmp_path / "F891_1891.pdf").exists()


def test_download_manifest_deduplicates_packet_ids(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "filings": [
            {"charter_num": "678033", "document_id": "H363_1780", "img_status": "STANDARD"},
            {"charter_num": "678033", "document_id": "H363_1780", "img_status": "STANDARD"},
            {"charter_num": "678033", "document_id": "F891_1891", "img_status": "STANDARD"},
            {"charter_num": "678033", "document_id": "000000185688", "img_status": "UNAVAILABLE"},
        ]
    }))
    session = FakeSession([FakeResponse(), FakeResponse(content=b"%PDF-1.7\nsecond")])
    monkeypatch.setattr(ingest_ohio, "_image_session", session)

    results = ingest_ohio.download_filing_manifest(
        manifest,
        output_dir=tmp_path / "pdfs",
        delay=0,
    )

    assert [row["document_id"] for row in results] == [
        "H363_1780",
        "F891_1891",
        "000000185688",
    ]
    assert [row["status"] for row in results] == [
        "downloaded",
        "downloaded",
        "unavailable",
    ]
