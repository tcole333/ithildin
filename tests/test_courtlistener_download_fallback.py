from argparse import Namespace
from types import SimpleNamespace

import pytest

from tools import query_courtlistener


def test_pdf_extraction_falls_back_to_pdftotext(monkeypatch):
    monkeypatch.setattr(
        query_courtlistener,
        "_extract_pages_pymupdf",
        lambda _path: (_ for _ in ()).throw(ImportError("no pymupdf")),
    )
    monkeypatch.setattr(
        query_courtlistener,
        "_extract_pages_pdftotext",
        lambda _path: ["First page text", "Second page text"],
    )

    method, pages, reason = query_courtlistener._extract_pdf_pages("filing.pdf")

    assert method == "pdftotext"
    assert pages == ["First page text", "Second page text"]
    assert reason == "no pymupdf"


def test_pdftotext_page_boundaries_are_preserved(monkeypatch):
    monkeypatch.setattr(
        query_courtlistener.shutil,
        "which",
        lambda command: "/opt/bin/pdftotext" if command == "pdftotext" else None,
    )
    completed = SimpleNamespace(
        returncode=0,
        stdout="First page\fSecond page\f",
        stderr="",
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed

    monkeypatch.setattr(query_courtlistener.subprocess, "run", fake_run)

    assert query_courtlistener._extract_pages_pdftotext("filing.pdf") == [
        "First page",
        "Second page",
    ]
    assert calls == [
        (
            ["/opt/bin/pdftotext", "-layout", "filing.pdf", "-"],
            {
                "check": False,
                "capture_output": True,
                "text": True,
                "timeout": 120,
            },
        )
    ]


def test_extraction_quality_flags_header_only_pdf():
    quality = query_courtlistener._extraction_quality(
        ["Case header 1"] * 63
    )

    assert quality == {
        "page_count": 63,
        "text_chars": 693,
        "substantive_pages": 0,
        "needs_ocr": True,
    }


def test_download_reports_pdftotext_fallback_and_ocr_need(
    monkeypatch, tmp_path, capsys
):
    class Response:
        status_code = 200

        @staticmethod
        def iter_content(chunk_size):
            assert chunk_size == 8192
            yield b"%PDF-test"

    monkeypatch.setattr("requests.get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(
        query_courtlistener,
        "_extract_pdf_pages",
        lambda _path: (
            "pdftotext",
            ["Court filing header"] * 5,
            "No module named 'pymupdf'",
        ),
    )
    pdf_path = tmp_path / "filing.pdf"

    query_courtlistener.cmd_download(
        Namespace(
            url="recap/example.pdf",
            output_file=str(pdf_path),
            extract_text=True,
        )
    )

    assert pdf_path.read_bytes() == b"%PDF-test"
    extracted = pdf_path.with_suffix(".txt").read_text()
    assert "Court filing header" in extracted
    assert "--- PAGE BREAK ---" in extracted
    captured = capsys.readouterr()
    assert "Extracted text via pdftotext" in captured.out
    assert "used pdftotext fallback" in captured.err
    assert "likely needs OCR" in captured.err


def test_extraction_failure_is_not_silently_ignored(monkeypatch):
    monkeypatch.setattr(
        query_courtlistener,
        "_extract_pages_pymupdf",
        lambda _path: (_ for _ in ()).throw(ImportError("no pymupdf")),
    )
    monkeypatch.setattr(
        query_courtlistener,
        "_extract_pages_pdftotext",
        lambda _path: (_ for _ in ()).throw(FileNotFoundError("no pdftotext")),
    )

    with pytest.raises(RuntimeError, match="both PyMuPDF.*pdftotext"):
        query_courtlistener._extract_pdf_pages("filing.pdf")
