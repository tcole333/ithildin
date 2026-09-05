import json
import zipfile

from tools import epstein_derived
from tools import epstein_metadata as metadata


def _observation_map(observations):
    return {
        (item.namespace, item.field_name, item.raw_value): item
        for item in observations
    }


def test_schema_owns_artifact_metadata_tables(tmp_path):
    db_path = tmp_path / "derived.db"
    db = epstein_derived.get_db(db_path)
    epstein_derived.init_schema(db)
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    version = db.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()[0]
    db.close()

    assert epstein_derived.SCHEMA_VERSION == 2
    assert version == "2"
    assert {
        "artifact_file",
        "artifact_location",
        "artifact_metadata_observation",
    } <= tables


def test_normalize_timestamp_handles_epoch_email_iso_and_pdf_dates():
    assert metadata._normalize_timestamp(0) == "1970-01-01T00:00:00Z"
    assert (
        metadata._normalize_timestamp("Mon, 24 May 2021 18:50:00 +0000")
        == "2021-05-24T18:50:00Z"
    )
    assert metadata._normalize_timestamp("2020-01-02T03:04:05Z") == (
        "2020-01-02T03:04:05Z"
    )
    assert metadata._normalize_timestamp("D:20200102030405-05'00'") == (
        "2020-01-02T08:04:05Z"
    )


def test_email_extraction_preserves_routing_and_attachment_metadata(tmp_path):
    eml = tmp_path / "message.eml"
    eml.write_bytes(
        b"Received: from laptop.example ([203.0.113.4]); "
        b"Mon, 24 May 2021 18:51:00 +0000\r\n"
        b"Date: Mon, 24 May 2021 18:50:00 +0000\r\n"
        b"From: Sender <sender@example.com>\r\n"
        b"To: Recipient <recipient@example.com>\r\n"
        b"Message-ID: <message-1@example.com>\r\n"
        b"X-Originating-IP: [203.0.113.4]\r\n"
        b"X-Mailer: Example Mail 1.0\r\n"
        b"Subject: Metadata test\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: multipart/mixed; boundary=abc\r\n"
        b"\r\n"
        b"--abc\r\n"
        b"Content-Type: text/plain\r\n\r\nBody\r\n"
        b"--abc\r\n"
        b"Content-Type: text/plain; name=note.txt\r\n"
        b"Content-Disposition: attachment; filename=note.txt\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        b"aGVsbG8=\r\n"
        b"--abc--\r\n"
    )

    observations = metadata._extract_email(eml)
    values = _observation_map(observations)

    assert (
        "email.header",
        "message-id",
        "<message-1@example.com>",
    ) in values
    assert (
        "email.header",
        "x-originating-ip",
        "[203.0.113.4]",
    ) in values
    assert (
        "email.attachment",
        "attachment_1.filename",
        "note.txt",
    ) in values
    assert (
        "email.structure",
        "attachment_count",
        "1",
    ) in values
    assert (
        "email.analysis",
        "sent_minus_last_received_seconds",
        "-60",
    ) in values


def test_mail_sidecar_hashes_body_preview_instead_of_storing_it(tmp_path):
    sidecar = tmp_path / "message.eml.meta"
    sidecar.write_text(
        json.dumps(
            {
                "Path": "/Sent/",
                "date": 1368274705,
                "change_date": 1458651699,
                "blob_digest": "digest",
                "metadata": "private message preview",
            }
        )
    )

    observations = metadata._extract_mail_sidecar(sidecar)
    fields = {item.field_name: item for item in observations}

    assert "metadata" not in fields
    assert fields["Path"].raw_value == "/Sent/"
    assert fields["metadata_payload_length"].raw_value == str(
        len("private message preview")
    )
    assert fields["metadata_payload_sha256"].raw_value == metadata._sha256_text(
        "private message preview"
    )
    assert fields["date"].normalized_value == "2013-05-11T12:18:25Z"
    assert fields["exact_eml_companion_present"].raw_value == "false"
    assert (
        fields["exact_eml_companion_present"].namespace
        == "mail_sidecar.inventory"
    )


def test_openxml_extracts_creator_last_editor_and_dates(tmp_path):
    workbook = tmp_path / "metadata.xlsx"
    core_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <cp:coreProperties
      xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:dcterms="http://purl.org/dc/terms/">
      <dc:creator>Analyst One</dc:creator>
      <cp:lastModifiedBy>Vendor Two</cp:lastModifiedBy>
      <dcterms:created>2020-01-02T03:04:05Z</dcterms:created>
    </cp:coreProperties>"""
    app_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
      <Application>Microsoft Excel</Application>
      <Company>Example Vendor</Company>
    </Properties>"""
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("[Content_Types].xml", "<Types/>")

    observations = metadata._extract_openxml(workbook)
    values = _observation_map(observations)

    assert ("office.core", "creator", "Analyst One") in values
    assert ("office.core", "lastModifiedBy", "Vendor Two") in values
    assert ("office.app", "Application", "Microsoft Excel") in values
    created = values[("office.core", "created", "2020-01-02T03:04:05Z")]
    assert created.normalized_value == "2020-01-02T03:04:05Z"


def test_scan_content_addresses_duplicates_and_reports_layers(tmp_path, monkeypatch):
    first = tmp_path / "EFTA00000001.eml"
    second = tmp_path / "alias.eml"
    content = (
        b"Date: Mon, 24 May 2021 18:50:00 +0000\r\n"
        b"From: a@example.com\r\n"
        b"To: b@example.com\r\n"
        b"Message-ID: <same@example.com>\r\n"
        b"Subject: Same bytes\r\n\r\nBody\r\n"
    )
    first.write_bytes(content)
    second.write_bytes(content)
    db_path = tmp_path / "derived.db"
    monkeypatch.setattr(metadata, "log_search", None)
    monkeypatch.setattr(epstein_derived, "CORE_DB", tmp_path / "missing-core.db")

    scan = metadata.scan_files(
        db_path,
        [(first, "fixture"), (second, "fixture")],
        note="test",
        max_extract_bytes=metadata.DEFAULT_MAX_EXTRACT_BYTES,
    )
    stats = metadata.build_stats(db_path)
    report = metadata.build_report(
        db_path,
        reference_date="2019-07-06",
        limit=20,
        cluster_min=2,
        include_sensitive=False,
    )

    assert scan["scanned"] == 2
    assert scan["errors"] == []
    assert stats["artifacts"] == 1
    assert stats["locations"] == 2
    assert stats["duplicate_artifacts"] == 1
    assert len(report["duplicate_content"]) == 1
    assert len(report["duplicate_content"][0]["paths"]) == 2
    assert len(report["post_reference_dates"]["source_native"]) == 2
    assert "acquisition" in report["post_reference_dates"]
    assert report["coverage_gaps"]["mail_sidecars_scanned"] == 0


def test_sensitive_values_are_redacted_by_default():
    assert metadata._redact_value("GPSLatitude", "18.1", False) == (
        "[withheld-sensitive-metadata]"
    )
    assert metadata._redact_value("GPSLatitude", "18.1", True) == "18.1"
    assert metadata._redact_value("producer", "Quartz", False) == "Quartz"


def test_parse_colon_output_keeps_value_colons():
    assert metadata._parse_colon_output(
        "Title: Example\nCreationDate: 2020-01-02T03:04:05-05:00\n"
    ) == [
        ("Title", "Example"),
        ("CreationDate", "2020-01-02T03:04:05-05:00"),
    ]


def test_qpdf_exit_code_three_is_a_warning():
    assert metadata._qpdf_status(0, "No syntax errors") == "ok"
    assert metadata._qpdf_status(0, "WARNING: recoverable issue") == "warning"
    assert metadata._qpdf_status(3, "operation succeeded with warnings") == "warning"
    assert metadata._qpdf_status(2, "fatal error") == "error"
