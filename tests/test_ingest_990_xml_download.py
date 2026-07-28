import argparse
import io
import json
import zipfile
from datetime import date

from tools import ingest_990_xml


def _zip_with_member(name, data):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr(name, data)
    return payload.getvalue()


def test_index_years_include_current_calendar_year():
    years = list(ingest_990_xml.index_years(date(2026, 7, 28)))

    assert years[0] == 2017
    assert years[-1] == 2026
    assert 2027 not in years


def test_official_batch_extracts_object_xml(tmp_path, monkeypatch):
    xml = b'<?xml version="1.0"?><Return/>'
    archive = _zip_with_member("nested/123_public.xml", xml)
    fetched = []

    def fake_fetch(url, desc=""):
        fetched.append((url, desc))
        return archive

    monkeypatch.setattr(ingest_990_xml, "BATCH_CACHE", tmp_path / "batches")
    monkeypatch.setattr(ingest_990_xml, "_fetch", fake_fetch)

    result = ingest_990_xml._fetch_xml_irs_batch(
        {
            "year": "2025",
            "batch_id": "2025_TEOS_XML_11A",
            "object_id": "123",
        }
    )

    assert result == xml
    assert fetched == [
        (
            "https://apps.irs.gov/pub/epostcard/990/xml/2025/"
            "2025_TEOS_XML_11A.zip",
            "2025_TEOS_XML_11A.zip",
        )
    ]


def test_download_uses_official_batch_without_propublica_delay(
    tmp_path, monkeypatch
):
    xml = b'<?xml version="1.0"?><Return/>'
    fallback_calls = []
    sleep_calls = []
    monkeypatch.setattr(ingest_990_xml, "XML_CACHE", tmp_path / "xml")
    monkeypatch.setattr(
        ingest_990_xml,
        "_fetch_xml_irs_batch",
        lambda _target: xml,
    )
    monkeypatch.setattr(
        ingest_990_xml,
        "_fetch_xml_propublica",
        lambda object_id: fallback_calls.append(object_id),
    )
    monkeypatch.setattr(
        ingest_990_xml.time,
        "sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    paths = ingest_990_xml.download_xmls(
        [
            {
                "year": "2025",
                "batch_id": "2025_TEOS_XML_11A",
                "object_id": "123",
                "tax_period": "202412",
                "return_type": "990",
            }
        ]
    )

    assert fallback_calls == []
    assert sleep_calls == []
    assert paths == [tmp_path / "xml" / "123_public.xml"]
    assert paths[0].read_bytes() == xml


def test_ingest_writes_requested_result_artifact(tmp_path, monkeypatch):
    output = tmp_path / "ingest.json"
    monkeypatch.setattr(ingest_990_xml, "ingest_ein", lambda _ein, _label: 3)

    ingest_990_xml.cmd_ingest(
        argparse.Namespace(
            ein="332149093",
            tracked=False,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text()) == {
        "ein": "332149093",
        "label": "332149093",
        "filings_stored": 3,
    }
