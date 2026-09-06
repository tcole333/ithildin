from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_denver_property
from tools.public_records_catalog import AcquisitionUnavailableError
from tools.public_records_http import PaginatedFetch, TransportError


def _args(
    command: str = "owner",
    query: str | None = "RODRIGUEZ",
    **overrides,
) -> Namespace:
    values = {
        "command": command,
        "query": query,
        "limit": None,
        "cursor": None,
        "geometry": False,
        "page_size": 2_000,
        "max_records": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "catalog_db": "unused.db",
        "catalog_config": "unused.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _feature(**overrides):
    attributes = {
        "OBJECTID": 991475,
        "SCHEDNUM": "0017103008000",
        "MAPNUM": "00171",
        "BLKNUM": "03",
        "PARCELNUM": "008",
        "APPENDAGE": "000",
        "PARCEL_SOURCE": None,
        "SYSTEM_START_DATE": 1_291_766_400_000,
        "OWNER_NAME": "RODRIGUEZ,BRANDON",
        "OWNER_ADDRESS_LINE1": "16159 RANDOLPH PL",
        "OWNER_ADDRESS_LINE2": None,
        "OWNER_CITY": "DENVER",
        "OWNER_STATE": "CO",
        "OWNER_ZIP": "80239-7035",
        "SITUS_ADDRESS_ID": 175748,
        "SITUS_ADDRESS_LINE1": "16159 E RANDOLPH PL",
        "SITUS_ADDRESS_LINE2": None,
        "SITUS_CITY": "DENVER",
        "SITUS_STATE": "CO",
        "SITUS_ZIP": "80239-7035",
        "SITUS_ADDR_NBR": "16159",
        "SITUS_ADDR_NBR_SUFFIX": None,
        "SITUS_STR_NAME_PRE_MOD": None,
        "SITUS_STR_NAME_PRE_DIR": "E",
        "SITUS_STR_NAME_PRE_TYPE": None,
        "SITUS_STR_NAME": "RANDOLPH",
        "SITUS_STR_NAME_POST_TYPE": "PL",
        "SITUS_STR_NAME_POST_DIR": None,
        "SITUS_STR_NAME_POST_MOD": None,
        "SITUS_UNIT_TYPE": None,
        "SITUS_UNIT_IDENT": None,
        "TAX_DIST": "DENV",
        "SITUS_X_COORD": 3197146,
        "SITUS_Y_COORD": 1716270,
        "PROP_CLASS": "1212",
        "D_CLASS": "113",
        "D_CLASS_CN": "SFR Grade C",
        "DCL12": "11",
        "ZONE_ID": "SSU",
        "ZONE_10": "PUD",
        "APPRAISED_LAND_VALUE": 71900,
        "APPRAISED_IMP_VALUE": 431800,
        "APPRAISED_TOTAL_VALUE": 503700,
        "ASSESSED_LAND_VALUE_LOCAL": 4400,
        "ASSESSED_BLDG_VALUE_LOCAL": 26430,
        "ASSESSED_TOTAL_VALUE_LOCAL": 30830,
        "EXEMPT_AMT_LOCAL": 0,
        "TAXABLE_AMT_LOCAL": 30830,
        "ASSESSED_LAND_VALUE_SCH": 5070,
        "ASSESSED_BLDG_VALUE_SCH": 30440,
        "ASSESSED_TOTAL_VALUE_SCH": 35510,
        "EXEMPT_AMT_SCH": 0,
        "TAXABLE_AMT_SCH": 35510,
        "LAND_AREA": 4891,
        "RES_ORIG_YEAR_BUILT": 2005,
        "RES_ABOVE_GRADE_AREA": 1812,
        "COM_ORIG_YEAR_BUILT": None,
        "COM_GROSS_AREA": None,
        "COM_NET_AREA": None,
        "COM_STRUCTURE_TYPE": None,
        "LEGAL_DESC": "PARKFIELD FLG NO 12 B2 L8",
        "TOT_UNITS": 1,
        "RECEPTION_NUM": "2026006375",
        "ASAL_INSTR": "SW: SPECIAL WARRANTY",
        "SALE_DATE": 1_767_139_200_000,
        "SALE_MONTHDAY": "1231",
        "SALE_YEAR": 2025,
        "SALE_PRICE": 500000,
        "GlobalID": "b974bfab-6d0f-4f3c-9c3e-047c774f5d98",
        "Shape__Area": 4888.50927734375,
        "Shape__Length": 288.61744639956692,
    }
    attributes.update(overrides)
    return {"attributes": attributes}


def _fetch(records, **overrides) -> PaginatedFetch:
    values = {
        "records": records,
        "next_cursor": None,
        "schema": {"kind": "test"},
        "schema_fingerprint": "denver-schema",
        "pages_fetched": 1,
        "requests_made": 1,
    }
    values.update(overrides)
    return PaginatedFetch(**values)


class FakeClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        query_denver_property,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_owner_query_normalizes_assessment_sale_and_recorder_join():
    client = FakeClient(_fetch([_feature()]))

    result = query_denver_property.execute(
        _args(limit=25),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    assert result.query.jurisdiction.jurisdiction_id == "08031"
    assert client.calls[0]["where"] == (
        "UPPER(OWNER_NAME) LIKE '%RODRIGUEZ%'"
    )
    assert client.calls[0]["parameters"] == {
        "orderByFields": "OBJECTID"
    }
    assert client.calls[0]["requested_limit"] == 25
    record = result.records[0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-co-denver-parcels/08031/"
        "parcel/0017103008000"
    )
    assert record["native_parcel_id"] == "0017103008000"
    assert record["alternate_parcel_ids"] == ("008",)
    assert record["source_last_updated"] == "2010-12-08"
    assert record["owners"][0] == {
        "raw_name": "RODRIGUEZ,BRANDON",
        "role": "primary_assessor_owner",
        "assertion_type": "assessment_roll",
        "confidence": "high",
        "title_caveat": "not_proof_of_legal_or_beneficial_ownership",
    }
    assert record["assessment"]["appraised_total_value"] == 503700
    assert record["assessment"]["parcel_value"] == 503700
    assert record["assessment"]["assessed_value"] == 30830
    assert record["assessment"]["assessment_class"] == "1212"
    assert record["assessment"]["local"]["taxable_amount"] == 30830
    assert record["physical_characteristics"][
        "residential_original_year_built"
    ] == 2005
    assert record["last_sale"] == {
        "source_document_ref": "2026006375",
        "instrument_type": "SW: SPECIAL WARRANTY",
        "sale_date": "2025-12-31",
        "sale_month_day_raw": "1231",
        "sale_year": 2025,
        "consideration": 500000,
        "currency": "USD",
    }
    assert record["recorder_join"]["source_id"] == (
        "us-co-denver-recorder-publicsearch"
    )
    assert record["recorder_join"]["instrument_number"] == "2026006375"
    assert record["response_schema_fingerprint"] == "denver-schema"
    assert record["adapter_schema_fingerprint"] == (
        query_denver_property.ADAPTER_SCHEMA_FINGERPRINT
    )
    assert "not proof of legal or beneficial ownership" in result.warnings[0]


def test_omitted_limit_fetches_without_an_adapter_record_ceiling():
    client = FakeClient(_fetch([_feature()]))

    result = query_denver_property.execute(
        _args(limit=None, max_records=None),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.query.query.requested_limit is None
    assert client.calls[0]["requested_limit"] is None


def test_query_modes_use_verified_native_fields_and_escape_literals():
    assert query_denver_property._where(
        "address", "16159 E Randolph Pl"
    ) == (
        "UPPER(SITUS_ADDRESS_LINE1) LIKE '%16159 E RANDOLPH PL%' "
        "OR UPPER(SITUS_ADDRESS_LINE2) LIKE '%16159 E RANDOLPH PL%'"
    )
    assert query_denver_property._where(
        "parcel", "0017103008000"
    ) == (
        "SCHEDNUM='0017103008000' OR PARCELNUM='0017103008000'"
    )
    assert query_denver_property._where("objectid", "000991475") == (
        "OBJECTID=991475"
    )
    assert query_denver_property._where("owner", "O'NEIL") == (
        "UPPER(OWNER_NAME) LIKE '%O''NEIL%'"
    )
    with pytest.raises(ValueError, match="numeric"):
        query_denver_property._where("objectid", "not-a-number")


def test_probe_uses_stable_schedule_sentinel_and_one_record():
    client = FakeClient(_fetch([_feature()]))

    result = query_denver_property.execute(
        _args(command="probe", query=None, limit=500),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "ok"
    assert client.calls[0]["where"] == (
        f"SCHEDNUM='{query_denver_property.PROBE_SCHEDULE_NUMBER}'"
    )
    assert client.calls[0]["requested_limit"] == 1
    assert result.query.query.requested_limit == 1


def test_client_honors_source_native_page_size_without_hidden_record_cap():
    client = query_denver_property._client(
        _args(page_size=50_000, max_records=None),
        {
            "allowed": True,
            "limits": {
                "maximum_page_size": 10_000,
                "minimum_interval_seconds": 0,
            },
        },
    )

    assert client.page_size == 2_000
    assert client.max_records is None


def test_caller_cap_produces_partial_result_and_continuation():
    client = FakeClient(
        _fetch(
            [_feature()],
            next_cursor="arcgis:offset:1",
            truncated_by_cap=True,
            warnings=("configured cap reached",),
        )
    )

    result = query_denver_property.execute(
        _args(limit=10, max_records=1),
        access_decision={"allowed": True},
        client=client,
    )

    assert result.status.value == "partial"
    assert result.next_cursor == "arcgis:offset:1"
    assert "configured cap reached" in result.warnings


def test_geometry_is_opt_in_and_preserves_source_crs():
    feature = {
        **_feature(),
        "geometry": {
            "rings": [
                [
                    [3197146.0, 1716270.0],
                    [3197147.0, 1716270.0],
                    [3197146.0, 1716270.0],
                ]
            ]
        },
    }
    client = FakeClient(_fetch([feature]))

    result = query_denver_property.execute(
        _args(geometry=True),
        access_decision={"allowed": True},
        client=client,
    )

    assert client.calls[0]["return_geometry"] is True
    assert result.to_dict()["records"][0]["geometry"] == feature["geometry"]
    assert result.records[0]["geometry_format"] == "esri_json"
    assert result.records[0]["geometry_crs"] == "EPSG:2877"


def test_sale_date_falls_back_to_source_year_and_monthday():
    record = query_denver_property._normalize_feature(
        _feature(
            SALE_DATE=None,
            SALE_YEAR=2024.0,
            SALE_MONTHDAY="0208",
        ),
        response_schema_fingerprint="schema",
    )

    assert record["last_sale"]["sale_date"] == "2024-02-08"


def test_authoritative_empty_and_transport_failure_are_distinct(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_denver_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    empty = query_denver_property.execute(
        _args(query="NO SUCH OWNER"),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([])),
    )
    assert empty.status.value == "no_results"
    assert logged[-1][2] == 0

    unavailable = query_denver_property.execute(
        _args(),
        access_decision={"allowed": True},
        client=FakeClient(
            error=TransportError(
                "network unavailable",
                url=query_denver_property.LAYER_URL,
            )
        ),
    )
    assert unavailable.status.value == "unavailable"
    assert unavailable.errors[0].code == "transport_error"
    assert logged[-1][2] is None


def test_unavailable_access_decision_prevents_client_construction(monkeypatch):
    decision = {
        "source_id": query_denver_property.SOURCE_ID,
        "allowed": False,
        "reason": "review missing",
        "reason_code": "access_review_required",
    }
    monkeypatch.setattr(
        query_denver_property,
        "_access_contract",
        lambda args: (_ for _ in ()).throw(
            AcquisitionUnavailableError(decision)
        ),
    )
    monkeypatch.setattr(
        query_denver_property,
        "_client",
        lambda *args: pytest.fail("network client was unexpectedly built"),
    )

    result = query_denver_property.execute(_args())

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "access_review_required"


def test_search_log_uses_query_fingerprint(monkeypatch):
    logged = []
    monkeypatch.setattr(
        query_denver_property,
        "log_search",
        lambda *args: logged.append(args),
    )

    result = query_denver_property.execute(
        _args(),
        access_decision={"allowed": True},
        client=FakeClient(_fetch([_feature()])),
    )

    logged_query = json.loads(logged[0][0])
    assert logged_query["fingerprint"] == result.query.fingerprint
    assert logged[0][1:] == (query_denver_property.SOURCE_ID, 1)


def test_direct_script_help_and_cli_surface():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(project_root / "tools/query_denver_property.py"),
            "--help",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "City and County of Denver" in result.stdout
    parser = query_denver_property.build_parser()
    parsed = parser.parse_args(
        [
            "parcel",
            "0017103008000",
            "--geometry",
            "--max-records",
            "2500",
        ]
    )
    assert parsed.command == "parcel"
    assert parsed.geometry is True
    assert parsed.limit is None
    assert parsed.max_records == 2500
