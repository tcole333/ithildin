from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace

import pytest

from tools import (
    query_arlington_property,
    query_delaware_courts,
    query_delaware_firstmap,
    query_delaware_opinions,
    query_denver_county_court,
    query_denver_property,
    query_pa_opinions,
    query_pa_ujs,
    query_reeves_records,
)
from tools.public_records_contract import ResultStatus


MODULES = (
    query_arlington_property,
    query_pa_ujs,
    query_pa_opinions,
    query_delaware_courts,
    query_delaware_firstmap,
    query_delaware_opinions,
    query_denver_county_court,
    query_denver_property,
    query_reeves_records,
)


class _Parser:
    def parse_args(self):
        return Namespace(
            timeout=1.0,
            minimum_interval=0.0,
            max_attempts=1,
            retry_backoff=0.0,
            limit=1,
            offset=0,
            page_size=1,
            max_records=None,
            doc_id=1,
            page_number=1,
        )

    def error(self, message):
        raise AssertionError(message)


@pytest.mark.parametrize("module", MODULES)
def test_direct_cli_main_returns_nonzero_for_structured_failure(
    module,
    monkeypatch,
):
    monkeypatch.setattr(module, "build_parser", lambda: _Parser())
    monkeypatch.setattr(
        module,
        "execute",
        lambda _args: SimpleNamespace(status=ResultStatus.SOURCE_CHANGED),
    )
    monkeypatch.setattr(module, "_emit", lambda _result, _args: None)

    assert module.main() == 1


@pytest.mark.parametrize("module", MODULES)
def test_direct_cli_main_returns_zero_for_success(module, monkeypatch):
    monkeypatch.setattr(module, "build_parser", lambda: _Parser())
    monkeypatch.setattr(
        module,
        "execute",
        lambda _args: SimpleNamespace(status=ResultStatus.OK),
    )
    monkeypatch.setattr(module, "_emit", lambda _result, _args: None)

    assert module.main() == 0
