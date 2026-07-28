import sqlite3

from tools import parse_email_chain


def test_get_ocr_text_prefers_canonical_kabass_over_legacy(tmp_path, monkeypatch):
    kabass = tmp_path / "kabass.db"
    db = sqlite3.connect(kabass)
    db.execute(
        "CREATE TABLE documents "
        "(file_key TEXT, full_text TEXT, page_number INTEGER)"
    )
    db.execute(
        "INSERT INTO documents VALUES (?, ?, ?)",
        ("EFTA02391470", "Its a problem for me.....", 1),
    )
    db.commit()
    db.close()

    legacy = tmp_path / "documents.db"
    db = sqlite3.connect(legacy)
    db.execute("CREATE TABLE documents (bates_id TEXT, ocr_text TEXT)")
    db.execute(
        "INSERT INTO documents VALUES (?, ?)",
        ("EFTA02391470", "Its a problem for me"),
    )
    db.commit()
    db.close()

    monkeypatch.setattr(parse_email_chain, "KABASS_DB", kabass)
    monkeypatch.setattr(parse_email_chain, "DOCUMENTS_DB", str(legacy))

    assert (
        parse_email_chain.get_ocr_text("EFTA02391470")
        == "Its a problem for me....."
    )


def test_get_ocr_text_falls_back_to_legacy_when_kabass_missing(
    tmp_path, monkeypatch
):
    legacy = tmp_path / "documents.db"
    db = sqlite3.connect(legacy)
    db.execute("CREATE TABLE documents (bates_id TEXT, ocr_text TEXT)")
    db.execute(
        "INSERT INTO documents VALUES (?, ?)",
        ("EFTA00000001", "Legacy OCR text"),
    )
    db.commit()
    db.close()

    monkeypatch.setattr(parse_email_chain, "KABASS_DB", tmp_path / "missing.db")
    monkeypatch.setattr(parse_email_chain, "DOCUMENTS_DB", str(legacy))

    assert parse_email_chain.get_ocr_text("EFTA00000001") == "Legacy OCR text"
