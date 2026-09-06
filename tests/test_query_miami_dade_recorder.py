from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_miami_dade_recorder as recorder
from tools.public_records_http import RetryPolicy, TransportError


FIXTURE_DIR = Path("tests/fixtures/public_records/miami_dade_recorder")
DOCUMENT_TYPES = json.loads(
    (FIXTURE_DIR / "document_types.json").read_text(encoding="utf-8")
)
PUBLIC_HYDRATE = json.loads(
    (FIXTURE_DIR / "public_hydrate.json").read_text(encoding="utf-8")
)
FINANCIAL = json.loads(
    (FIXTURE_DIR / "financial.json").read_text(encoding="utf-8")
)
COMMERCIAL_LOOKUP = json.loads(
    (FIXTURE_DIR / "commercial_lookup.json").read_text(encoding="utf-8")
)
AUTH_KEY = "11111111-1111-4111-8111-111111111111"


@dataclass
class FixtureResponse:
    payload: Any = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    content: bytes = b""

    def json(self):
        return self.payload


class QueueTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, *, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected recorder request")
        return self.responses.pop(0)


def fixture_client(transport):
    return recorder.MiamiDadeRecorderClient(
        transport=transport,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )


class FakeClient:
    def __init__(self):
        self.calls = []
        self.commercial_payload = COMMERCIAL_LOOKUP
        self.image_download = recorder.DocumentDownload(
            content=b"%PDF-1.4\nfixture-pdf",
            media_type="application/pdf",
            filename="Document_35134_800.pdf",
            etag='"35134:800:O:False"',
        )
        self.error = None

    def _maybe_raise(self):
        if self.error is not None:
            raise self.error

    def document_types(self):
        self._maybe_raise()
        self.calls.append(("document-types",))
        return DOCUMENT_TYPES

    def hydrate_qs(self, token):
        self._maybe_raise()
        self.calls.append(("hydrate-qs", token))
        return PUBLIC_HYDRATE

    def parties(self, cfn_master_id):
        self._maybe_raise()
        self.calls.append(("parties", cfn_master_id))
        return PUBLIC_HYDRATE["recordingModels"]

    def financial(self, cfn_master_id, document_type, recording_date):
        self._maybe_raise()
        self.calls.append(
            ("financial", cfn_master_id, document_type, recording_date)
        )
        return FINANCIAL

    def document_image(self, **kwargs):
        self._maybe_raise()
        self.calls.append(("image", kwargs))
        return self.image_download

    def commercial_lookup(self, **kwargs):
        self._maybe_raise()
        self.calls.append(("commercial", kwargs))
        return self.commercial_payload


def _execute(args, monkeypatch, client):
    logged = []
    monkeypatch.setattr(
        recorder,
        "log_search",
        lambda *values: logged.append(values),
    )
    result = recorder.execute(
        args,
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )
    return result, logged


def test_source_split_and_query_routes_are_explicit_without_auth_key():
    public_args = recorder.build_parser().parse_args(
        ["hydrate-qs", "issued-token"]
    )
    commercial_args = recorder.build_parser().parse_args(
        ["cfn", "2026", "55844"]
    )

    public_query = recorder.build_query(public_args)
    commercial_query = recorder.build_query(commercial_args)

    assert public_query.source.source_id == recorder.PUBLIC_SOURCE_ID
    assert public_query.source.metadata["record_identity_source_id"] == (
        recorder.CANONICAL_SOURCE_ID
    )
    assert public_query.query.parameters["route"] == (
        recorder.ROUTE_ISSUED_RESULT_HYDRATION
    )
    assert commercial_query.source.source_id == recorder.CANONICAL_SOURCE_ID
    assert commercial_query.source.metadata["record_identity_source_id"] == (
        recorder.CANONICAL_SOURCE_ID
    )
    assert commercial_query.query.parameters == {
        "route": recorder.ROUTE_COMMERCIAL_API,
        "parameter1": "2026",
        "parameter2": "R55844",
        "credential_env": recorder.COMMERCIAL_AUTH_ENV,
    }
    assert AUTH_KEY not in commercial_query.to_json()


def test_public_client_uses_only_verified_sessionless_routes():
    transport = QueueTransport(
        [
            FixtureResponse(DOCUMENT_TYPES),
            FixtureResponse(PUBLIC_HYDRATE),
            FixtureResponse(PUBLIC_HYDRATE["recordingModels"]),
            FixtureResponse(FINANCIAL),
        ]
    )
    client = fixture_client(transport)

    assert client.document_types() == tuple(DOCUMENT_TYPES)
    assert client.hydrate_qs("issued-token") == PUBLIC_HYDRATE
    assert len(client.parties(50126241)) == 2
    assert client.financial(50126241, "DEED - DEE", "2026-01-27") == FINANCIAL

    assert [call["url"] for call in transport.calls] == [
        recorder.PUBLIC_DOCUMENT_TYPES_API,
        recorder.PUBLIC_RESULTS_API,
        recorder.PUBLIC_PARTIES_API,
        recorder.PUBLIC_FINANCIAL_API,
    ]
    assert transport.calls[1]["params"] == {"qs": "issued-token"}
    assert transport.calls[2]["method"] == "POST"
    assert transport.calls[2]["headers"]["Content-Length"] == "0"
    assert all(
        "x-recaptcha-token" not in {
            key.lower() for key in call["headers"]
        }
        for call in transport.calls
    )


def test_public_hydration_normalizes_document_group_party_and_folio_hierarchy():
    records = recorder._public_hydration_records(PUBLIC_HYDRATE)

    assert len(records) == 1
    document = records[0]
    assert document["canonical_ref"] == (
        "RECORDER:us-fl-miami-dade-official-records-public/"
        "12086/cfn/2026R55844"
    )
    assert document["native_document_id"] == "2026R55844"
    assert document["source_id"] == recorder.PUBLIC_SOURCE_ID
    assert document["record_identity_source_id"] == (
        recorder.CANONICAL_SOURCE_ID
    )
    assert document["issued_search_token"] == "fixture-issued-token"
    assert document["record_kind"] == recorder.RECORD_KIND_INSTRUMENT
    assert document["instrument_type"] == "DEE"
    assert document["is_conveyance"] is True
    assert document["book"] == 35134
    assert document["page"] == 800
    assert document["book_type"] == "O"
    assert document["execution_date"] is None
    assert document["execution_date_raw"] == "1/1/1900 12:00:00 AM"
    assert document["recording_date"] == "2026-01-27"
    assert document["recording_date_raw"] == "1/27/2026 12:00:00 AM"
    assert document["consideration"] == 210000
    assert document["legal_description_raw"] == "UNIT 308"
    assert document["source_url"].endswith(
        "recordpage?qs=fixture-issued-token"
    )
    assert document["groups"][0]["folio"] == "0141380670370"
    assert [
        party["party_code_raw"]
        for party in document["groups"][0]["parties"]
    ] == ["D", "R"]
    assert [
        (party["name"], party["role"], party["raw_role_code"])
        for party in document["parties"]
    ] == [
        ("FANNIE MAE", "direct", "D"),
        ("PACHON JORGE", "reverse", "R"),
    ]
    assert document["parcels"] == [
        {
            "native_parcel_id": "0141380670370",
            "link_method": "source_index_folio",
            "link_confidence": 1.0,
            "legal_description_raw": "UNIT 308",
            "address": {
                "raw": "501 SW 1 ST 308",
                "street": "501 SW 1 ST",
                "unit": "308",
            },
            "group_id": 1,
        }
    ]
    assert document["raw_rows"] == PUBLIC_HYDRATE["recordingModels"]


def test_commercial_response_normalizes_document_and_retains_lookup_images():
    records = recorder._commercial_records(COMMERCIAL_LOOKUP)

    assert len(records) == 1
    document = records[0]
    assert document["source_id"] == recorder.CANONICAL_SOURCE_ID
    assert document["record_identity_source_id"] == (
        recorder.CANONICAL_SOURCE_ID
    )
    assert document["source_route"] == recorder.ROUTE_COMMERCIAL_API
    assert document["record_kind"] == recorder.RECORD_KIND_INSTRUMENT
    assert document["native_document_id"] == "2026R55844"
    assert document["instrument_type"] == "DEE"
    assert document["is_conveyance"] is True
    assert document["execution_date"] is None
    assert document["recording_date"] == "2026-01-27"
    assert document["recording_date_raw"] == "2026-01-27T00:00:00-05:00"
    assert document["parcels"][0]["native_parcel_id"] == "0141380670370"
    assert document["commercial_lookup_images"] == [
        "official-record-image-reference"
    ]
    assert document["commercial_response"] == {
        "status": "OK",
        "description": "Records returned",
        "units_balance": 41,
    }


@pytest.mark.parametrize(
    ("argv", "parameter1", "parameter2"),
    [
        (["cfn", "2026", "55844"], "2026", "R55844"),
        (["book-page", "35134", "800"], "35134", "800"),
        (["folio", "01-4138-067-0370"], "0141380670370", "FN"),
    ],
)
def test_commercial_selectors_load_env_key_without_exposing_it(
    argv,
    parameter1,
    parameter2,
    monkeypatch,
):
    monkeypatch.setenv(recorder.COMMERCIAL_AUTH_ENV, AUTH_KEY)
    monkeypatch.setattr(recorder, "load_env_file", lambda: None)
    client = FakeClient()
    args = recorder.build_parser().parse_args(argv)

    result, logged = _execute(args, monkeypatch, client)

    assert result.status.value == "ok"
    assert client.calls == [
        (
            "commercial",
            {
                "parameter1": parameter1,
                "parameter2": parameter2,
                "auth_key": AUTH_KEY,
            },
        )
    ]
    serialized = json.dumps(result.to_dict())
    assert AUTH_KEY not in serialized
    assert AUTH_KEY not in logged[0][0]
    assert logged[0][1:] == (recorder.CANONICAL_SOURCE_ID, 1)


def test_missing_commercial_credential_is_explicit_and_makes_no_request(
    monkeypatch,
):
    monkeypatch.delenv(recorder.COMMERCIAL_AUTH_ENV, raising=False)
    monkeypatch.setattr(recorder, "load_env_file", lambda: None)
    client = FakeClient()
    args = recorder.build_parser().parse_args(["cfn", "2026", "55844"])

    result, logged = _execute(args, monkeypatch, client)

    assert result.status.value == "restricted"
    assert result.errors[0].code == "commercial_credential_missing"
    assert result.errors[0].details["credential_env"] == (
        recorder.COMMERCIAL_AUTH_ENV
    )
    assert client.calls == []
    assert logged[0][1:] == (recorder.CANONICAL_SOURCE_ID, None)


def test_financial_command_returns_source_scoped_supplement(monkeypatch):
    client = FakeClient()
    args = recorder.build_parser().parse_args(
        [
            "financial",
            "50126241",
            "--doc-type",
            "DEED - DEE",
            "--recording-date",
            "2026-01-27",
        ]
    )

    result, logged = _execute(args, monkeypatch, client)

    assert result.status.value == "ok"
    assert result.records[0]["source_id"] == recorder.PUBLIC_SOURCE_ID
    assert result.records[0]["record_identity_source_id"] == (
        recorder.CANONICAL_SOURCE_ID
    )
    assert result.records[0]["record_kind"] == (
        recorder.RECORD_KIND_FINANCIAL_DETAIL
    )
    assert result.records[0]["mortgage_or_deed_amount"] == 210000
    assert result.records[0]["consideration"] == 0
    assert logged[0][1:] == (recorder.PUBLIC_SOURCE_ID, 1)


def test_image_command_validates_and_writes_pdf_with_audit_metadata(
    tmp_path,
    monkeypatch,
):
    client = FakeClient()
    destination = tmp_path / "record.pdf"
    args = recorder.build_parser().parse_args(
        [
            "image",
            "35134",
            "800",
            "--book-type",
            "O",
            "--document-output",
            str(destination),
        ]
    )

    result, logged = _execute(args, monkeypatch, client)

    assert destination.read_bytes() == client.image_download.content
    assert result.status.value == "ok"
    record = result.records[0]
    assert record["source_id"] == recorder.PUBLIC_SOURCE_ID
    assert record["record_identity_source_id"] == (
        recorder.CANONICAL_SOURCE_ID
    )
    assert record["record_kind"] == recorder.RECORD_KIND_DOCUMENT_ARTIFACT
    assert record["canonical_ref"].endswith("/O/35134/800")
    assert record["sha256"] == hashlib.sha256(
        client.image_download.content
    ).hexdigest()
    assert record["source_url"].endswith(
        "sBook=35134&sPage=800&sBookType=O&redact=false"
    )
    assert logged[0][1:] == (recorder.PUBLIC_SOURCE_ID, 1)


def test_transport_failure_is_not_logged_as_authoritative_zero(monkeypatch):
    client = FakeClient()
    client.error = TransportError(
        "network unavailable",
        url=recorder.PUBLIC_RESULTS_API,
    )
    args = recorder.build_parser().parse_args(
        ["hydrate-qs", "issued-token"]
    )

    result, logged = _execute(args, monkeypatch, client)

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert logged[0][1:] == (recorder.PUBLIC_SOURCE_ID, None)


def test_binary_client_rejects_non_pdf_response():
    transport = QueueTransport(
        [
            FixtureResponse(
                payload=None,
                headers={"Content-Type": "text/html"},
                content=b"<html>not a PDF</html>",
            )
        ]
    )
    client = fixture_client(transport)

    with pytest.raises(recorder.SourceSchemaError):
        client.document_image(book="35134", page="800", book_type="O")


def test_document_type_and_nonconveyance_records_are_classified_explicitly():
    type_records = recorder._document_type_records(DOCUMENT_TYPES)
    assert all(
        record["record_kind"] == recorder.RECORD_KIND_DOCUMENT_TYPE
        for record in type_records
    )
    assert all(
        record["record_identity_source_id"]
        == recorder.CANONICAL_SOURCE_ID
        for record in type_records
    )

    mortgage_row = dict(PUBLIC_HYDRATE["recordingModels"][0])
    mortgage_row["cfN_SEQ"] = 55845
    mortgage_row["doC_TYPE"] = "MORTGAGE - MOR"
    mortgage_record = recorder.normalize_documents(
        [mortgage_row],
        source_id=recorder.PUBLIC_SOURCE_ID,
        route=recorder.ROUTE_RECORD_DETAIL,
    )[0]

    assert mortgage_record["instrument_type"] == "MOR"
    assert mortgage_record["is_conveyance"] is False
    assert recorder._document_type("MOR_I - MOR_I")["code"] == "MOR_I"


def test_folio_normalization_produces_exact_county_identifier():
    assert recorder.normalize_folio("01-4138-067-0370") == "0141380670370"
    assert recorder.normalize_folio(141380670370) == "0141380670370"
    with pytest.raises(ValueError, match="exceeds 13 digits"):
        recorder.normalize_folio("12345678901234")
