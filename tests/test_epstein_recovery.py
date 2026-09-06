from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from types import SimpleNamespace

import pytest

from tools.epstein_recovery import (
    INFOPATH_SIGNATURE,
    RecoveryError,
    audit_base64_ocr,
    command_decode_infopath,
    command_ledger,
    emit,
    parse_infopath_attachment,
    parse_pages,
    run_command,
    safe_artifact_name,
    validate_recovered_body,
)


def _infopath_candidate(
    body: bytes,
    filename: str = "example.xml",
    *,
    declared_size: int | None = None,
) -> str:
    filename_bytes = (filename + "\0").encode("utf-16le")
    header = struct.pack(
        "<4sIIIII",
        INFOPATH_SIGNATURE,
        0x14,
        1,
        0,
        len(body) if declared_size is None else declared_size,
        len(filename) + 1,
    )
    return base64.b64encode(header + filename_bytes + body).decode("ascii")


def test_parse_infopath_attachment_requires_exact_header_and_size():
    body = b'<?xml version="1.0"?><root>ok</root>'
    parsed = parse_infopath_attachment(_infopath_candidate(body))

    assert parsed["original_filename"] == "example.xml"
    assert parsed["declared_file_size"] == len(body)
    assert parsed["body"] == body
    assert parsed["signature_hex"] == INFOPATH_SIGNATURE.hex()


def test_parse_infopath_attachment_rejects_declared_size_mismatch():
    candidate = _infopath_candidate(b"abc", declared_size=4)

    with pytest.raises(RecoveryError, match="size mismatch"):
        parse_infopath_attachment(candidate)


def test_parse_infopath_attachment_rejects_ambiguous_ocr_glyph():
    candidate = _infopath_candidate(b"abc")
    damaged = candidate[:10] + "?" + candidate[11:]

    with pytest.raises(RecoveryError, match="non-Base64 glyphs"):
        parse_infopath_attachment(damaged)


def test_recovered_pdf_requires_real_pdf_signature():
    validation = validate_recovered_body(b"%PDF#\xb11.5\nnot-a-pdf", "policy.pdf")

    assert validation["format_valid"] is False
    assert validation["pdf_header"] is False
    assert "lacks %PDF- header" in validation["failure"]


def test_recovered_pdf_accepts_qpdf_warning_only_exit(monkeypatch):
    monkeypatch.setattr(
        "tools.epstein_recovery.shutil.which",
        lambda _name: "/usr/bin/qpdf",
    )
    monkeypatch.setattr(
        "tools.epstein_recovery.run_command",
        lambda _command, timeout=120: SimpleNamespace(
            returncode=3,
            stdout="PDF Version: 1.5",
            stderr="qpdf: operation succeeded with warnings",
        ),
    )

    validation = validate_recovered_body(
        b"%PDF-1.5\n1 0 obj\n<<>>\nendobj\n%%EOF\n",
        "policy.pdf",
    )

    assert validation["format_valid"] is True
    assert validation["qpdf"]["status"] == "warning"
    assert "warnings" in validation["warning"]


def test_decode_infopath_writes_nothing_when_body_format_is_invalid(tmp_path):
    candidate_path = tmp_path / "hybrid.b64"
    candidate_path.write_text(
        _infopath_candidate(b"%PDF#\xb11.5\nnot-a-pdf", "policy.pdf"),
        encoding="ascii",
    )
    artifact_dir = tmp_path / "artifacts"
    args = argparse.Namespace(
        candidate=str(candidate_path),
        artifact_dir=str(artifact_dir),
        write_artifact=True,
        source_ref="EFTA00147557",
    )

    with pytest.raises(RecoveryError, match="failed filename/format validation"):
        command_decode_infopath(args)

    assert not artifact_dir.exists()


def test_audit_base64_ocr_removes_only_documented_wrapping_noise():
    audit, candidate = audit_base64_ocr(
        "QUJD-\nREVG-\nEFTA00147557\nR0hJ.JA-\n",
        expected_width=4,
        minimum_line_chars=4,
    )

    assert candidate == "QUJDREVGR0hJ?JA"
    assert audit["continuation_hyphens_removed"] == 3
    assert audit["bates_footers_removed"] == 1
    assert audit["invalid_glyph_histogram"] == {".": 1}
    assert audit["strict_base64_alphabet"] is False


def test_parse_pages_accepts_single_or_closed_range():
    assert parse_pages("3") == (3, 3)
    assert parse_pages("3-29") == (3, 29)

    with pytest.raises(argparse.ArgumentTypeError):
        parse_pages("29-3")


def test_safe_artifact_name_drops_path_and_uses_content_hash():
    result = safe_artifact_name("../../unsafe/attachment.PDF", "a" * 64)

    assert result == "recovered-aaaaaaaaaaaaaaaa.pdf"
    assert "/" not in result


def test_run_command_replaces_non_utf8_diagnostics():
    result = run_command(
        [
            sys.executable,
            "-c",
            "import os; os.write(2, b'bad-\\x89-diagnostic')",
        ]
    )

    assert result.returncode == 0
    assert result.stderr == "bad-\ufffd-diagnostic"


def test_ledger_actionable_filter(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "schema_version": "test",
                "as_of_utc": "2026-01-01T00:00:00Z",
                "records": [
                    {"efta_id": "EFTA00000001", "queue_decision": "exclude"},
                    {"efta_id": "EFTA00000002", "queue_decision": "active"},
                    {
                        "efta_id": "EFTA00000003",
                        "queue_decision": "narrow_follow_up",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        ledger=str(ledger_path),
        status=None,
        actionable=True,
    )

    result = command_ledger(args)

    assert result["count"] == 2
    assert [record["efta_id"] for record in result["records"]] == [
        "EFTA00000002",
        "EFTA00000003",
    ]


def test_emit_uses_explicit_queue_count(tmp_path, capsys):
    output_path = tmp_path / "queue.json"
    args = argparse.Namespace(output=str(output_path), json_out=False)

    emit({"records": [{}, {}], "count": 2}, args, "queue")

    assert "2 results" in capsys.readouterr().out
    assert json.loads(output_path.read_text(encoding="utf-8"))["count"] == 2
