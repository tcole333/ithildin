from __future__ import annotations

import pytest

from tools import query_property
from tools import query_washington_digital_archives_land as land
from tools.public_records_contract import PublicRecordsResult, ResultStatus


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_translate_owner_limit_cursor_and_native_page_size() -> None:
    routes = query_property.LIVE_ROUTES[land.SOURCE_ID]
    translated = routes["owner"].translate(
        _parse(
            "owner",
            "SMITH",
            "--source",
            land.SOURCE_ID,
            "--jurisdiction",
            "53001",
            "--search-field",
            "grantor",
            "--tax-year",
            "2020",
            "--limit",
            "9",
            "--max-records",
            "7",
            "--page-size",
            "1000",
            "--cursor",
            "cursor-v2",
        ),
        routes["owner"].adapter_command,
    )

    assert set(routes) == {"search", "owner", "instrument"}
    assert translated.command == "search"
    assert translated.county == "adams"
    assert translated.last_name == "SMITH"
    assert translated.first_name is None
    assert translated.middle_name is None
    assert translated.party_role == "grantor"
    assert translated.start_year == translated.end_year == 2020
    assert translated.limit == 7
    assert translated.page_size == 200
    assert translated.cursor == "cursor-v2"
    assert translated.shared_expected_county_geoid == "53001"

    company = routes["owner"].translate(
        _parse(
            "owner",
            "ACME HOLDINGS, LLC",
            "--source",
            land.SOURCE_ID,
            "--jurisdiction",
            "53001",
            "--search-field",
            "company",
        ),
        routes["owner"].adapter_command,
    )
    assert company.last_name == "ACME HOLDINGS, LLC"
    assert company.first_name is None
    assert company.middle_name is None


def test_shared_instrument_requires_exact_record_id_and_validates_county() -> None:
    route = query_property.LIVE_ROUTES[land.SOURCE_ID]["instrument"]
    translated = route.translate(
        _parse(
            "instrument",
            "64742C2528B8C19D43FCC54D20DC97D0",
            "--source",
            land.SOURCE_ID,
            "--county",
            "Adams County",
        ),
        route.adapter_command,
    )

    assert translated.command == "detail"
    assert translated.record_id == "64742C2528B8C19D43FCC54D20DC97D0"
    assert translated.shared_expected_county_geoid == "53001"
    with pytest.raises(ValueError, match="exact 32-hex"):
        route.translate(
            _parse(
                "instrument",
                "324744",
                "--source",
                land.SOURCE_ID,
                "--jurisdiction",
                "53001",
            ),
            route.adapter_command,
        )
    with pytest.raises(ValueError, match="different counties"):
        route.translate(
            _parse(
                "instrument",
                "64742C2528B8C19D43FCC54D20DC97D0",
                "--source",
                land.SOURCE_ID,
                "--jurisdiction",
                "53001",
                "--county",
                "Benton",
            ),
            route.adapter_command,
        )


def test_uncovered_county_returns_recorder_guidance_separate_from_assessor() -> None:
    route = query_property.LIVE_ROUTES[land.SOURCE_ID]["owner"]
    translated = route.translate(
        _parse(
            "owner",
            "SMITH",
            "--source",
            land.SOURCE_ID,
            "--jurisdiction",
            "53019",
        ),
        route.adapter_command,
    )
    result = route.adapter.execute(translated)
    error = result.errors[0]

    assert result.status == ResultStatus.UNAVAILABLE
    assert error.code == "county_not_in_digital_archives_land_series"
    recorder = error.details["recorder_alternative"]
    assert recorder["county_key"] == "ferry"
    assert "complementary_sources" not in recorder
    assert [
        dict(item) for item in error.details["assessor_alternatives"]
    ] == [
        {
            "kind": "assessor_parcel_search",
            "url": "https://ferrywa-taxsifter.publicaccessnow.com/",
            "relationship": (
                "parcel, owner, assessment, sale, and tax pivot; separate "
                "from recorded-instrument evidence"
            ),
        }
    ]

    guidance = query_property._source_guidance(land.SOURCE_ID)
    assert guidance["unified_operations"] == ["instrument", "owner", "search"]
    assert any(
        item["county_key"] == "ferry"
        for item in guidance["official_recorder_alternatives"]
    )
    assert any(
        item["county_key"] == "ferry"
        for item in guidance["official_assessor_complements"]
    )
    assert "not assessor ownership records" in guidance["note"]


def test_shared_wrapper_rejects_detail_from_another_county(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = query_property.LIVE_ROUTES[land.SOURCE_ID]["instrument"]
    translated = route.translate(
        _parse(
            "instrument",
            "64742C2528B8C19D43FCC54D20DC97D0",
            "--source",
            land.SOURCE_ID,
            "--jurisdiction",
            "53005",
        ),
        route.adapter_command,
    )
    observed_query = land._build_query(
        title=land.TITLES_BY_KEY["adams"],
        operation="detail",
        parameters={
            "record_id": "64742C2528B8C19D43FCC54D20DC97D0",
        },
        requested_limit=1,
    )
    monkeypatch.setattr(
        land,
        "execute",
        lambda _args: PublicRecordsResult.success(
            observed_query,
            [
                {
                    "record_kind": "recorded_land_record",
                    "native_record_id": (
                        "64742C2528B8C19D43FCC54D20DC97D0"
                    ),
                }
            ],
        ),
    )

    result = route.adapter.execute(translated)

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "record_outside_requested_county"
    assert result.errors[0].details == {
        "requested_county_geoid": "53005",
        "observed_county_geoid": "53001",
    }
