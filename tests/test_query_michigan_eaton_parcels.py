from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path
from types import SimpleNamespace

from tools import query_michigan_eaton_parcels as eaton
from tools.public_records_contract import ResultStatus


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "michigan_eaton_parcels"
)


def _item(name: str = "item.json") -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text())


class _ItemClient:
    def __init__(self, payload: dict):
        self.payload = payload

    def fetch_item(self) -> dict:
        eaton._validate_item(self.payload)
        return dict(self.payload)


class _BulkProbeClient:
    def __init__(self, *, size: int = 4096, format_hint: str = "zip"):
        self.size = size
        self.format_hint = format_hint

    def probe(self, artifact, *, sample_bytes):
        return SimpleNamespace(
            format_hint=self.format_hint,
            content_length=self.size,
            to_dict=lambda: {
                "url": artifact.url,
                "http_status": 206,
                "content_length": self.size,
                "sample_size": sample_bytes,
                "format_hint": self.format_hint,
            },
        )


def _dbf_bytes(
    fields: list[tuple[str, str, int, int]],
    rows: list[dict[str, object]],
    *,
    update=(2026, 7, 1),
) -> bytes:
    header_length = 32 + len(fields) * 32 + 1
    record_length = 1 + sum(field[2] for field in fields)
    header = bytearray(32)
    header[0] = 0x03
    header[1:4] = bytes((update[0] - 1900, update[1], update[2]))
    header[4:8] = struct.pack("<I", len(rows))
    header[8:10] = struct.pack("<H", header_length)
    header[10:12] = struct.pack("<H", record_length)

    descriptors = bytearray()
    for name, field_type, length, decimals in fields:
        descriptor = bytearray(32)
        encoded_name = name.encode("ascii")
        descriptor[: len(encoded_name)] = encoded_name
        descriptor[11] = ord(field_type)
        descriptor[16] = length
        descriptor[17] = decimals
        descriptors.extend(descriptor)

    records = bytearray()
    for row in rows:
        record = bytearray(b" ")
        for name, field_type, length, decimals in fields:
            value = row.get(name)
            if value is None:
                encoded = b" " * length
            elif field_type == "N":
                if decimals:
                    text = f"{float(value):.{decimals}f}"
                else:
                    text = str(int(value))
                encoded = text.rjust(length).encode("ascii")
            else:
                encoded = str(value).encode("utf-8")[:length].ljust(length)
            record.extend(encoded)
        assert len(record) == record_length
        records.extend(record)
    return bytes(header + descriptors + b"\r" + records + b"\x1a")


def _shp_header() -> bytes:
    header = bytearray(100)
    header[0:4] = struct.pack(">i", 9994)
    header[24:28] = struct.pack(">i", 50)
    header[28:32] = struct.pack("<i", 1000)
    header[32:36] = struct.pack("<i", 5)
    header[36:68] = struct.pack("<4d", 1.0, 2.0, 3.0, 4.0)
    return bytes(header)


def _artifact(tmp_path: Path, *, include_bsa: bool = True) -> Path:
    fields = [
        ("PARCELID", "C", 18, 0),
        ("LOWPARCELI", "C", 8, 0),
        ("LPARCEL", "C", 24, 0),
        ("CNVYNAME", "C", 40, 0),
        ("SITEADDRES", "C", 50, 0),
        ("ZONING_COD", "C", 12, 0),
        ("OWNERNME1", "C", 35, 0),
        ("OWNERNME2", "C", 35, 0),
        ("CNTASSDVAL", "N", 12, 0),
        ("CNTTXBLVAL", "N", 12, 0),
        ("CLASSCD", "C", 5, 0),
        ("CLASSDSCRP", "C", 30, 0),
        ("BSAOnline", "C", 90, 0),
        ("Acreage", "N", 12, 4),
    ]
    if not include_bsa:
        fields = [field for field in fields if field[0] != "BSAOnline"]
    rows = [
        {
            "PARCELID": "04008075016000",
            "LOWPARCELI": "160-00",
            "LPARCEL": "040-080-750-160-00",
            "CNVYNAME": "Verndale Lakes",
            "SITEADDRES": "504 BURGENSTOCK DR, LANSING, MI 48917",
            "ZONING_COD": "NONE",
            "OWNERNME1": "LAWRENCE, TYRONE",
            "OWNERNME2": "LAWRENCE, WINIFRED",
            "CNTASSDVAL": 186100,
            "CNTTXBLVAL": 143685,
            "CLASSCD": "407",
            "CLASSDSCRP": "RESIDENTIAL CONDOMINIUMS",
            "BSAOnline": (
                "https://bsaonline.com/SiteSearch/SiteSearchDetails"
                "?uid=418&ReferenceKey=040-080-750-160-00"
            ),
            "Acreage": 0.0394,
        },
        {
            "PARCELID": "01000640000202",
            "LOWPARCELI": "002-02",
            "LPARCEL": "010-006-400-002-02",
            "SITEADDRES": "13219 SAUBEE RD, LAKE ODESSA, MI 48849",
            "ZONING_COD": "LA",
            "OWNERNME1": "GENDA, LAWRENCE",
            "CNTASSDVAL": 88000,
            "CNTTXBLVAL": 58807,
            "CLASSCD": "401",
            "CLASSDSCRP": "RESIDENTIAL-IMPROVED",
            "BSAOnline": (
                "https://bsaonline.com/SiteSearch/SiteSearchDetails"
                "?uid=418&ReferenceKey=010-006-400-002-02"
            ),
            "Acreage": 2.9546,
        },
        {
            "PARCELID": "02000010000100",
            "LOWPARCELI": "001-00",
            "LPARCEL": "020-000-100-001-00",
            "SITEADDRES": "1 MAIN ST, CHARLOTTE, MI 48813",
            "OWNERNME1": "SMITH HOLDINGS LLC",
            "CNTASSDVAL": 100000,
            "CNTTXBLVAL": 90000,
            "CLASSCD": "201",
            "CLASSDSCRP": "COMMERCIAL",
            "BSAOnline": (
                "https://bsaonline.com/SiteSearch/SiteSearchDetails"
                "?uid=418&ReferenceKey=020-000-100-001-00"
            ),
            "Acreage": 1.0,
        },
    ]
    dbf = _dbf_bytes(fields, rows)
    artifact = tmp_path / "TaxParcel.zip"
    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("TaxParcel.cpg", "UTF-8")
        archive.writestr("TaxParcel.dbf", dbf)
        archive.writestr("TaxParcel.shp", _shp_header())
        archive.writestr("TaxParcel.shx", b"index")
        archive.writestr("TaxParcel.prj", 'PROJCS["fixture"]')
    return artifact


def _args(*argv: str):
    return eaton.build_parser().parse_args(list(argv))


def test_metadata_preserves_license_attribution_and_declared_scope():
    result = eaton.execute(
        _args("metadata"),
        client=_ItemClient(_item()),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["item"]["id"] == eaton.ITEM_ID
    assert "GEOSPATIAL DATA LICENSE" in record["license"]["published_text"]
    assert record["license"]["attribution"] == "© ecgis, 2018"
    assert record["publisher_declared_attribute_scope"]["roles"] == (
        "parcel_geometry",
        "parcel_identifier",
        "current_information_url",
    )
    assert record["current_artifact_attribute_scope"]["status"] == (
        "inspect_downloaded_dbf"
    )


def test_item_identity_change_is_reported_as_source_changed():
    result = eaton.execute(
        _args("metadata"),
        client=_ItemClient(_item("item_changed.json")),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


def test_probe_validates_zip_signature_and_item_size():
    result = eaton.execute(
        _args("probe", "--sample-bytes", "64"),
        client=_ItemClient(_item()),
        bulk_client=_BulkProbeClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    probe = result.records[0]
    assert probe["artifact_probe"]["format_hint"] == "zip"
    assert probe["artifact_probe"]["sample_size"] == 64


def test_probe_reports_item_and_artifact_size_mismatch():
    result = eaton.execute(
        _args("probe"),
        client=_ItemClient(_item()),
        bulk_client=_BulkProbeClient(size=4097),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "eaton_download_size_changed"


def test_inspection_detects_current_expanded_snapshot_fields(tmp_path):
    artifact = _artifact(tmp_path)
    inspection = eaton.inspect_local_dataset(artifact)

    assert inspection.dbf.record_count == 3
    assert inspection.dbf.last_update == "2026-07-01"
    assert inspection.shapefile["shape_type_role"] == "polygon"
    roles = inspection.compatibility["verified_snapshot_roles"]
    assert roles["assessment_roll_owner_names"] == ["OWNERNME1", "OWNERNME2"]
    assert roles["county_assessed_and_taxable_values"] == [
        "CNTASSDVAL",
        "CNTTXBLVAL",
    ]
    assert inspection.compatibility["publisher_description_comparison"]["status"] == (
        "current_dbf_contains_additional_snapshot_fields"
    )


def test_local_owner_search_normalizes_snapshot_without_title_claim(tmp_path):
    artifact = _artifact(tmp_path)
    records, cursor, inspection = eaton.search_local_dataset(
        artifact,
        "lawrence",
        field="owner",
        limit=1,
    )

    assert len(records) == 1
    assert cursor is not None
    record = records[0]
    assert record["native_parcel_id"] == "040-080-750-160-00"
    assert [owner["raw_name"] for owner in record["owners"]] == [
        "LAWRENCE, TYRONE",
        "LAWRENCE, WINIFRED",
    ]
    assert record["assessment"]["assessed_value"] == 186100
    assert record["assessment"]["taxable_value"] == 143685
    assert record["assessment"]["tax_year"] is None
    assert record["classification"]["zoning_code"] == "NONE"
    assert record["snapshot_completeness"]["does_not_establish"] == [
        "legal_boundary",
        "recorded_title",
        "assessment_tax_year_when_not_declared",
    ]
    assert record["artifact_snapshot"]["sha256"] == inspection.artifact_sha256


def test_local_search_cursor_is_bound_to_snapshot_and_criteria(tmp_path):
    artifact = _artifact(tmp_path)
    first, cursor, _ = eaton.search_local_dataset(
        artifact,
        "lawrence",
        field="owner",
        limit=1,
    )
    second, next_cursor, _ = eaton.search_local_dataset(
        artifact,
        "lawrence",
        field="owner",
        limit=1,
        cursor=cursor,
    )

    assert first[0]["native_parcel_id"] == "040-080-750-160-00"
    assert second[0]["native_parcel_id"] == "010-006-400-002-02"
    assert next_cursor is None

    result = eaton.execute(
        _args(
            "search",
            str(artifact),
            "lawrence",
            "--field",
            "address",
            "--limit",
            "1",
            "--cursor",
            cursor,
        ),
        log_results=False,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "eaton_cursor_query_changed"


def test_punctuation_insensitive_exact_parcel_search(tmp_path):
    artifact = _artifact(tmp_path)
    records, cursor, _ = eaton.search_local_dataset(
        artifact,
        "04008075016000",
        field="parcel",
        match="exact",
        limit=5,
    )

    assert cursor is None
    assert [record["native_parcel_id"] for record in records] == [
        "040-080-750-160-00"
    ]


def test_search_reports_missing_publisher_declared_bsa_field(tmp_path):
    artifact = _artifact(tmp_path, include_bsa=False)
    result = eaton.execute(
        _args("search", str(artifact), "smith"),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "eaton_dbf_declared_fields_missing"


def test_sources_and_alternatives_are_network_free():
    sources = eaton.execute(_args("sources"), log_results=False)
    alternatives = eaton.execute(_args("alternatives"), log_results=False)

    assert sources.records[0]["snapshot_semantics"]["assessment_year"] == (
        "not_declared_in_current_dbf"
    )
    bsa = alternatives.records[0]
    assert bsa["complement_id"] == "bsa-current-detail"
    assert "human verification" in bsa["access_observation"]


def test_search_envelope_references_the_local_artifact(tmp_path):
    artifact = _artifact(tmp_path)
    result = eaton.execute(
        _args(
            "search",
            str(artifact),
            "SMITH",
            "--field",
            "owner",
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.raw_artifact_refs == (str(artifact.resolve()),)
    assert result.records[0]["source_id"] == eaton.SOURCE_ID
