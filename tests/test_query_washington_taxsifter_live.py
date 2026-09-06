from __future__ import annotations

import os
from argparse import Namespace

import pytest

from tools import query_washington_taxsifter as adapter
from tools.public_records_contract import ResultStatus


LIVE = os.environ.get("RUN_LIVE_WASHINGTON_TAXSIFTER") == "1"


def _args(command: str, county: str, **overrides):
    values = {
        "command": command,
        "county": county,
        "source": None,
        "query": adapter.TENANTS_BY_KEY[county].sentinel_query,
        "data_link": None,
        "operations": "assessor",
        "limit": 1,
        "cursor": None,
        "verified": False,
        "timeout": 30.0,
        "minimum_interval": 0.25,
        "retry_attempts": 3,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.mark.skipif(
    not LIVE,
    reason=("set RUN_LIVE_WASHINGTON_TAXSIFTER=1 for official county probes"),
)
@pytest.mark.parametrize("county", adapter.VERIFIED_TENANT_KEYS)
def test_live_verified_deployment_search_and_disclaimer_session(county: str) -> None:
    result = adapter.execute(
        _args("search", county),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records
    assert result.records[0]["native_parcel_id"]
    assert result.records[0]["operation_links"]["assessor"]


@pytest.mark.skipif(
    not LIVE,
    reason=("set RUN_LIVE_WASHINGTON_TAXSIFTER=1 for official county probes"),
)
@pytest.mark.parametrize("county", ("adams", "douglas"))
def test_live_rich_detail_operation(county: str) -> None:
    result = adapter.execute(
        _args("detail", county, operations="assessor,treasurer,appraisal"),
        log_results=False,
    )

    assert result.status in {ResultStatus.OK, ResultStatus.PARTIAL}
    assert result.records
    bundle = result.records[0]
    assert bundle["representations"]["assessor"]["parcel"]["parcel_number"]
    assert bundle["representations"]["assessor"]["provenance"]["data_current_as"]


@pytest.mark.skipif(
    not LIVE,
    reason=("set RUN_LIVE_WASHINGTON_TAXSIFTER=1 for official county probes"),
)
def test_live_mason_challenge_remains_tenant_scoped() -> None:
    result = adapter.execute(
        _args("search", "mason"),
        log_results=False,
    )

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "source_challenge_required"
