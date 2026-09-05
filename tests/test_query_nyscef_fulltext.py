from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_nyscef_fulltext as fulltext


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "nyscef_fulltext"
)


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _write_pdf(target: Path) -> Path:
    hex_text = (FIXTURE_DIR / "filing.hex").read_text(encoding="ascii")
    target.write_bytes(bytes.fromhex(hex_text))
    return target


def _extraction(*pages: str) -> fulltext.ExtractionResult:
    quality = fulltext.extraction_quality(list(pages))
    return fulltext.ExtractionResult(
        pages=list(pages),
        page_methods=["pdftotext-layout"] * len(pages),
        primary_method="pdftotext-layout",
        quality=quality,
        ocr_attempted_pages=[],
        ocr_used_pages=[],
        ocr_errors=[],
    )


def test_normalize_manifest_preserves_case_document_and_party_identity():
    normalized = fulltext.normalize_manifest(_load("documents.json"))

    assert normalized["record_count"] == 2
    assert normalized["failure_count"] == 0
    first = normalized["records"][0]
    assert (
        first["case_identity"]
        == "NYSCEF-CASE:new-york-county-supreme-court:156728/2019"
    )
    assert first["record_identity"].endswith(":1")
    assert first["docket_id"] == "AcfkebAfF6itr8YHo86mUQ=="
    assert first["filed_date_iso"] == "2019-07-10"
    assert first["listed_parties"] == [
        "Example Holdings LLC",
        "Sample Respondent",
    ]
    assert first["source_url"].startswith(
        "https://iapps.courts.state.ny.us/nyscef/ViewDocument"
    )


def test_normalize_handoff_does_not_misclassify_it_as_an_empty_manifest():
    with pytest.raises(fulltext.FullTextError, match="search handoff"):
        fulltext.normalize_manifest(_load("human-required.json"))


def test_normalize_manifest_reports_bad_rows_but_keeps_good_rows():
    payload = _load("documents.json")
    payload["documents"].append("not a document")

    normalized = fulltext.normalize_manifest(payload)

    assert normalized["record_count"] == 2
    assert normalized["failure_count"] == 1
    assert normalized["failures"][0]["ordinal"] == 3


def test_resolve_pdf_path_supports_manifest_paths_and_explicit_file_map(tmp_path):
    normalized = fulltext.normalize_manifest(_load("documents.json"))
    first_pdf = _write_pdf(tmp_path / "filing-1.pdf")
    second_pdf = _write_pdf(tmp_path / "filing-7.pdf")
    file_map = fulltext._load_file_map(str(FIXTURE_DIR / "file-map.json"))

    assert fulltext.resolve_pdf_path(
        normalized["records"][0],
        manifest_dir=FIXTURE_DIR,
        pdf_dir=tmp_path,
        file_map=file_map,
    ) == first_pdf.resolve()
    assert fulltext.resolve_pdf_path(
        normalized["records"][1],
        manifest_dir=FIXTURE_DIR,
        pdf_dir=tmp_path,
        file_map=file_map,
    ) == second_pdf.resolve()


def test_resolve_pdf_path_rejects_ambiguous_heuristic_matches(tmp_path):
    normalized = fulltext.normalize_manifest(_load("documents.json"))
    record = normalized["records"][1]
    _write_pdf(tmp_path / "7.pdf")
    _write_pdf(tmp_path / "doc-7.pdf")

    with pytest.raises(fulltext.FullTextError, match="Multiple PDF candidates"):
        fulltext.resolve_pdf_path(
            record,
            manifest_dir=FIXTURE_DIR,
            pdf_dir=tmp_path,
            file_map={},
        )


def test_extraction_quality_surfaces_sparse_pages():
    quality = fulltext.extraction_quality(
        [
            "This is a substantive filing page. " * 20,
            "",
            "Another substantive filing page. " * 20,
        ]
    )

    assert quality["page_count"] == 3
    assert quality["low_text_pages"] == [2]
    assert quality["needs_ocr"] is True


def test_auto_ocr_replaces_only_a_better_sparse_page(tmp_path, monkeypatch):
    pdf = _write_pdf(tmp_path / "filing.pdf")
    monkeypatch.setattr(
        fulltext,
        "_extract_pdftotext_pages",
        lambda _path: ["", "Existing page text " * 30],
    )
    monkeypatch.setattr(
        fulltext,
        "_ocr_page",
        lambda *_args, **_kwargs: "OCR recovered Jane Witness affidavit " * 10,
    )
    monkeypatch.setattr(
        fulltext,
        "_ocr_dependencies",
        lambda: {"pdftocairo": "/bin/pdftocairo", "tesseract": "/bin/tesseract"},
    )

    result = fulltext.extract_pdf(pdf, ocr_mode="auto")

    assert result.ocr_attempted_pages == [1]
    assert result.ocr_used_pages == [1]
    assert result.page_methods == ["tesseract-ocr", "pdftotext-layout"]
    assert result.primary_method == "pdftotext-layout+tesseract-ocr"
    assert "Jane Witness" in result.pages[0]


def test_auto_ocr_retains_text_and_records_an_ocr_error(tmp_path, monkeypatch):
    pdf = _write_pdf(tmp_path / "filing.pdf")
    monkeypatch.setattr(
        fulltext,
        "_extract_pdftotext_pages",
        lambda _path: [""],
    )
    monkeypatch.setattr(
        fulltext,
        "_ocr_page",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            fulltext.FullTextError("tesseract unavailable")
        ),
    )
    monkeypatch.setattr(
        fulltext,
        "_ocr_dependencies",
        lambda: {"pdftocairo": None, "tesseract": None},
    )

    result = fulltext.extract_pdf(pdf, ocr_mode="auto")

    assert result.ocr_attempted_pages == [1]
    assert result.ocr_used_pages == []
    assert result.ocr_errors == [
        {"page_number": 1, "error": "tesseract unavailable"}
    ]
    assert result.quality["needs_ocr"] is True


def test_store_and_search_preserve_page_evidence_and_mention_classification(
    tmp_path,
):
    normalized = fulltext.normalize_manifest(_load("documents.json"))
    pdf = _write_pdf(tmp_path / "filing.pdf")
    database = tmp_path / "corpus.db"
    connection = fulltext._database_connection(database)
    try:
        document_id, created = fulltext._store_document(
            connection,
            record=normalized["records"][1],
            pdf_path=pdf,
            extraction=_extraction(
                "AFFIDAVIT OF JANE WITNESS about Example Holdings LLC.",
                "Acme Services Inc appeared in sworn testimony.",
            ),
            manifest_path=str(FIXTURE_DIR / "documents.json"),
        )
        connection.commit()
    finally:
        connection.close()

    assert created is True
    assert document_id == 1
    result = fulltext.search_index(
        database,
        "Jane Witness",
        mode="phrase",
        mention_name="Jane Witness",
    )
    assert result["result_count"] == 1
    hit = result["results"][0]
    assert hit["page_number"] == 1
    assert hit["evidence_reference"].endswith(":7:p1")
    assert hit["mention_check"]["classification"] == "non_party_candidate"
    assert "[JANE WITNESS]" in hit["snippet"]

    listed = fulltext.search_index(
        database,
        "Example Holdings LLC",
        mode="phrase",
        mention_name="Example Holdings LLC",
    )
    assert listed["results"][0]["mention_check"] == {
        "name": "Example Holdings LLC",
        "classification": "listed_party",
        "matched_party": "Example Holdings LLC",
    }


def test_same_record_and_hash_is_incremental_not_duplicated(tmp_path):
    record = fulltext.normalize_manifest(_load("documents.json"))["records"][0]
    pdf = _write_pdf(tmp_path / "filing.pdf")
    extraction = _extraction("Verified petition text.")
    connection = fulltext._database_connection(tmp_path / "corpus.db")
    try:
        first_id, first_created = fulltext._store_document(
            connection,
            record=record,
            pdf_path=pdf,
            extraction=extraction,
            manifest_path=str(FIXTURE_DIR / "documents.json"),
        )
        second_id, second_created = fulltext._store_document(
            connection,
            record=record,
            pdf_path=pdf,
            extraction=extraction,
            manifest_path=str(FIXTURE_DIR / "documents.json"),
        )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        connection.close()

    assert (first_id, first_created) == (1, True)
    assert (second_id, second_created) == (1, False)
    assert count == 1


def test_different_pdf_hashes_remain_versions_of_one_document_record(tmp_path):
    record = fulltext.normalize_manifest(_load("documents.json"))["records"][0]
    first_pdf = _write_pdf(tmp_path / "first.pdf")
    second_pdf = _write_pdf(tmp_path / "second.pdf")
    second_pdf.write_bytes(second_pdf.read_bytes() + b"\n% later acquisition\n")
    connection = fulltext._database_connection(tmp_path / "corpus.db")
    try:
        fulltext._store_document(
            connection,
            record=record,
            pdf_path=first_pdf,
            extraction=_extraction("First artifact."),
            manifest_path=str(FIXTURE_DIR / "documents.json"),
        )
        fulltext._store_document(
            connection,
            record=record,
            pdf_path=second_pdf,
            extraction=_extraction("Second artifact."),
            manifest_path=str(FIXTURE_DIR / "documents.json"),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS artifacts,
                COUNT(DISTINCT record_identity) AS records
            FROM documents
            """
        ).fetchone()
    finally:
        connection.close()

    assert tuple(row) == (2, 1)


@pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext is not installed",
)
def test_real_pdftotext_fixture_preserves_two_pages(tmp_path):
    pdf = _write_pdf(tmp_path / "filing.pdf")

    extraction = fulltext.extract_pdf(pdf, ocr_mode="never")

    assert extraction.quality["page_count"] == 2
    assert "AFFIDAVIT OF JANE WITNESS" in extraction.pages[0]
    assert "Acme Services Inc" in extraction.pages[1]
    assert extraction.page_methods == [
        "pdftotext-layout",
        "pdftotext-layout",
    ]


@pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext is not installed",
)
def test_end_to_end_index_search_stats_and_incremental_update(tmp_path, capsys):
    manifest = tmp_path / "documents.json"
    manifest.write_text(
        (FIXTURE_DIR / "documents.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    file_map = tmp_path / "file-map.json"
    file_map.write_text(
        (FIXTURE_DIR / "file-map.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_pdf(tmp_path / "filing-1.pdf")
    _write_pdf(tmp_path / "filing-7.pdf")
    database = tmp_path / "nyscef.db"
    first_output = tmp_path / "first-index.json"
    parser = fulltext.build_parser()

    first = parser.parse_args(
        [
            "index",
            str(manifest),
            "--database",
            str(database),
            "--pdf-dir",
            str(tmp_path),
            "--file-map",
            str(file_map),
            "--ocr",
            "never",
            "--output",
            str(first_output),
        ]
    )
    first.func(first)
    first_result = json.loads(first_output.read_text())

    assert first_result["indexed_count"] == 2
    assert first_result["missing_count"] == 0
    assert first_result["failure_count"] == 0

    search = fulltext.search_index(
        database,
        "Acme Services Inc",
        mode="phrase",
        mention_name="Acme Services Inc",
    )
    assert search["result_count"] == 2
    assert {
        row["mention_check"]["classification"] for row in search["results"]
    } == {"non_party_candidate"}

    second_output = tmp_path / "second-index.json"
    second = parser.parse_args(
        [
            "index",
            str(manifest),
            "--database",
            str(database),
            "--pdf-dir",
            str(tmp_path),
            "--file-map",
            str(file_map),
            "--ocr",
            "never",
            "--output",
            str(second_output),
        ]
    )
    second.func(second)
    second_result = json.loads(second_output.read_text())
    assert second_result["indexed_count"] == 0
    assert second_result["already_indexed_count"] == 2

    stats_output = tmp_path / "stats.json"
    stats = Namespace(
        database=str(database),
        output=str(stats_output),
        json_out=False,
    )
    fulltext.cmd_stats(stats)
    corpus_stats = json.loads(stats_output.read_text())
    assert corpus_stats["documents"] == 2
    assert corpus_stats["cases"] == 1
    assert corpus_stats["document_records"] == 2
    assert corpus_stats["pages"] == 4
    assert "saved to" in capsys.readouterr().out


def test_search_filters_are_combined_with_full_text(tmp_path):
    normalized = fulltext.normalize_manifest(_load("documents.json"))
    pdf = _write_pdf(tmp_path / "filing.pdf")
    database = tmp_path / "corpus.db"
    connection = fulltext._database_connection(database)
    try:
        for record in normalized["records"]:
            fulltext._store_document(
                connection,
                record=record,
                pdf_path=pdf,
                extraction=_extraction("shared filing phrase"),
                manifest_path=str(FIXTURE_DIR / "documents.json"),
            )
        connection.commit()
    finally:
        connection.close()

    result = fulltext.search_index(
        database,
        "shared filing",
        document_type="affidavit",
        filed_by="respondent",
        filed_from="2019-07-15",
        filed_to="2019-07-31",
    )

    assert result["result_count"] == 1
    assert result["results"][0]["document_number"] == "7"


def test_database_schema_uses_fts5_and_foreign_keys(tmp_path):
    connection = fulltext._database_connection(tmp_path / "corpus.db")
    try:
        source_id = connection.execute(
            "SELECT value FROM corpus_metadata WHERE key = 'source_id'"
        ).fetchone()[0]
        fts_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'pages_fts'"
        ).fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        connection.close()

    assert source_id == "us-ny-nyscef"
    assert "fts5" in fts_sql.casefold()
    assert foreign_keys == 1


def test_parser_exposes_source_specific_workflow_commands():
    parser = fulltext.build_parser()

    assert parser.parse_args(["sources"]).command == "sources"
    assert parser.parse_args(["probe"]).command == "probe"
    assert parser.parse_args(["normalize", "manifest.json"]).command == "normalize"
    assert (
        parser.parse_args(
            [
                "extract",
                "filing.pdf",
                "--case-number",
                "156728/2019",
                "--court",
                "New York County Supreme Court",
                "--document-number",
                "7",
            ]
        ).command
        == "extract"
    )
    assert (
        parser.parse_args(
            ["index", "manifest.json", "--database", "corpus.db"]
        ).command
        == "index"
    )
    assert (
        parser.parse_args(["search", "corpus.db", "witness"]).command
        == "search"
    )
    assert parser.parse_args(["stats", "corpus.db"]).command == "stats"


def test_probe_cli_resolves_sibling_tool_imports(tmp_path):
    output = tmp_path / "probe.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(fulltext.__file__).resolve()),
            "probe",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text())
    assert result["catalog_decision"]["source_id"] == "us-ny-nyscef"
    assert result["catalog_decision"]["reason_code"] == "automation_not_approved"


def test_source_inventory_keeps_complements_distinct():
    complements = {
        row["source_id"]: row
        for row in fulltext.SOURCE_INVENTORY["complementary_sources"]
    }

    assert "us-ny-court-pass" in complements
    assert "us-ny-law-reporting-bureau" in complements
    assert "us-ny-county-clerk-court-records" in complements
    assert "us-ny-trellis" in complements
    assert complements["us-ny-court-pass"]["value"].startswith(
        "Court of Appeals"
    )


def test_fts_phrase_and_all_modes_escape_and_join_terms():
    assert fulltext._fts_query("Jane Witness", "phrase") == '"Jane Witness"'
    assert fulltext._fts_query("Jane Witness", "all") == '"Jane" AND "Witness"'
    assert fulltext._fts_query('party:"Jane Witness"', "fts") == (
        'party:"Jane Witness"'
    )


def test_read_only_search_does_not_create_missing_database(tmp_path):
    target = tmp_path / "missing.db"

    with pytest.raises(fulltext.FullTextError, match="not found"):
        fulltext.search_index(target, "anything")

    assert not target.exists()


def test_sqlite_runtime_has_fts5():
    connection = sqlite3.connect(":memory:")
    try:
        enabled = connection.execute(
            "SELECT sqlite_compileoption_used('ENABLE_FTS5')"
        ).fetchone()[0]
    finally:
        connection.close()

    assert enabled == 1
