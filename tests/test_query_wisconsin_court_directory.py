from __future__ import annotations

import sys
from pathlib import Path

from tools import query_state_courts
from tools import query_wisconsin_court_directory as directory
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_store import connect_courts


FIXTURE_ROOT = (
    Path("tests/fixtures/public_records/wisconsin_court_directory")
)


def _fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _fixture_pages() -> dict[str, directory.WisconsinDirectoryPage]:
    return {
        directory.CIRCUIT_COMPONENT: directory.parse_circuit_courts_page(
            _fixture("circuit.html"),
            require_complete=False,
        ),
        directory.CLERK_COMPONENT: directory.parse_clerks_page(
            _fixture("clerks.html"),
            require_complete=False,
        ),
        directory.JUDGE_COMPONENT: directory.parse_judges_page(
            _fixture("judges.html"),
            require_complete=False,
        ),
        directory.DISTRICT_COMPONENT: (
            directory.parse_administrative_districts_page(
                _fixture("districts.html"),
                require_complete=False,
            )
        ),
        directory.APPEALS_COMPONENT: directory.parse_court_of_appeals_page(
            _fixture("appeals.html"),
            require_complete=False,
        ),
        directory.STATE_OFFICE_COMPONENT: directory.parse_state_offices_page(
            _fixture("state-offices.html"),
            require_complete=False,
        ),
    }


class _FixtureClient:
    def __init__(
        self,
        pages: dict[str, directory.WisconsinDirectoryPage],
    ) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def fetch(self, component: str) -> directory.WisconsinDirectoryPage:
        self.requested.append(component)
        return self.pages[component]


def _direct_args(*values: str):
    return directory.build_parser().parse_args(list(values))


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_county_table_parsers_preserve_stable_identity_and_joint_rosters() -> None:
    clerks = directory.parse_clerks_page(
        _fixture("clerks.html"),
        require_complete=False,
    )
    dane_clerk = clerks.records[1]
    assert dane_clerk["canonical_ref"] == (
        "WI-COURT-DIRECTORY:clerks:55025"
    )
    assert dane_clerk["clerk_name"] == "Example, Dana"
    assert dane_clerk["phone"] == "(608) 266-4311"
    assert dane_clerk["website_routes"] == [
        {
            "label": "Website",
            "url": "https://courts.countyofdane.com/",
        },
    ]

    judges = directory.parse_judges_page(
        _fixture("judges.html"),
        require_complete=False,
    )
    joint = judges.records[0]
    assert joint["county"] == "Buffalo"
    assert joint["county_geoid"] == "55011"
    assert joint["source_county_label"] == "Buffalo/Pepin"
    assert joint["assigned_counties"] == ["Buffalo", "Pepin"]
    assert joint["assigned_county_geoids"] == ["55011", "55091"]
    assert joint["judges"] == ["Clark, Hon. Thomas W."]


def test_structured_directory_parsers_keep_distinct_office_roles() -> None:
    circuit = directory.parse_circuit_courts_page(
        _fixture("circuit.html"),
        require_complete=False,
    )
    adams = circuit.records[0]
    assert adams["county_geoid"] == "55001"
    assert adams["judicial_districts"] == [7]
    assert len(adams["office_locations"]) == 2
    assert adams["personnel_groups"][0]["location_index"] == 1

    districts = directory.parse_administrative_districts_page(
        _fixture("districts.html"),
        require_complete=False,
    )
    district_five = districts.records[1]
    assert district_five["district_number"] == 5
    assert "Dane" in district_five["counties"]
    assert "55025" in district_five["county_geoids"]

    appeals = directory.parse_court_of_appeals_page(
        _fixture("appeals.html"),
        require_complete=False,
    )
    district_one = appeals.records[1]
    assert district_one["district_number"] == 1
    assert district_one["counties"] == ["Milwaukee"]
    assert district_one["court_id"] == "wi-court-of-appeals-district-1"

    state_offices = directory.parse_state_offices_page(
        _fixture("state-offices.html"),
        require_complete=False,
    )
    assert [record["section_name"] for record in state_offices.records] == [
        "Office of Justices",
        "Director of State Courts",
    ]
    assert all(record["snapshot_only"] for record in state_offices.records)


def test_search_fetches_complete_components_then_filters_locally() -> None:
    pages = _fixture_pages()
    client = _FixtureClient(pages)
    result = directory.execute(
        _direct_args("search", "Dane"),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert client.requested == list(directory.COMPONENTS)
    assert {
        record["directory_component"] for record in result.records
    } == {
        directory.CIRCUIT_COMPONENT,
        directory.CLERK_COMPONENT,
        directory.JUDGE_COMPONENT,
        directory.DISTRICT_COMPONENT,
    }
    assert {record["record_kind"] for record in result.records} == {
        "circuit_court_office_directory",
        "circuit_court_clerk_directory",
        "circuit_court_judge_roster",
        "judicial_administrative_district_directory",
    }


def test_discovery_and_routes_preserve_complementary_functions() -> None:
    pages = _fixture_pages()
    result = directory.execute(
        _direct_args("discovery", "--query", "Dane"),
        client=_FixtureClient(pages),
        log_results=False,
    )
    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert {record["directory_component"] for record in result.records} == {
        directory.CLERK_COMPONENT,
        directory.JUDGE_COMPONENT,
    }

    routes = directory.source_routes()
    by_id = {record["route_id"]: record for record in routes}
    assert by_id["municipal-court-directory-pdf"]["route_kind"] == (
        "complementary_municipal_court_directory"
    )
    assert by_id["county-juror-contacts"]["route_kind"] == (
        "complementary_county_contact_directory"
    )
    assert by_id["wcca-circuit-case-search"]["related_source_id"] == (
        "us-wi-wcca-public"
    )
    assert by_id["wscca-appellate-case-search"]["related_source_id"] == (
        "us-wi-wscca-public"
    )


def test_shared_route_translates_component_and_county_geoid() -> None:
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.WISCONSIN_COURT_DIRECTORY_SOURCE_ID
    ]["search"]
    translated = route.translate(
        _shared_args(
            "search",
            "Example",
            "--source",
            directory.SOURCE_ID,
            "--jurisdiction",
            "55025",
            "--search-field",
            "clerk",
            "--limit",
            "7",
        ),
        route.adapter_command,
    )

    assert translated.command == "search"
    assert translated.county == "Dane"
    assert translated.components == [directory.CLERK_COMPONENT]
    assert translated.limit == 7
    assert query_state_courts._source_guidance(directory.SOURCE_ID)[
        "unified_operations"
    ] == ["search"]


def test_probe_cli_does_not_require_a_limit_attribute(monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(sys, "argv", ["query_wisconsin_court_directory.py", "probe"])
    monkeypatch.setattr(
        directory,
        "execute",
        lambda args: seen.append(args.command) or object(),
    )
    monkeypatch.setattr(directory, "_emit", lambda _result, _args: None)

    directory.main()

    assert seen == ["probe"]


def test_directory_ingestion_is_explicitly_snapshot_only(tmp_path: Path) -> None:
    pages = _fixture_pages()
    result = directory.execute(
        _direct_args("county", "Dane", "--component", "clerks"),
        client=_FixtureClient(pages),
        log_results=False,
    )
    db_path = tmp_path / "courts.db"
    report = ingest_envelope(result.to_dict(), court_db=db_path)

    assert report["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"circuit_court_clerk_directory": 1},
    }
    assert all(value == 0 for value in report["projected"].values())
    db = connect_courts(db_path)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 0
    finally:
        db.close()


def test_shared_live_route_ingests_only_a_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class _AllowedCatalog:
        def __init__(self, _path) -> None:
            pass

        def show_source(self, source_id: str):
            assert source_id == directory.SOURCE_ID
            return {
                "source": {
                    "source_id": directory.SOURCE_ID,
                    "name": directory.SOURCE_METADATA.name,
                    "official_url": directory.DIRECTORIES_URL,
                    "license_or_terms_url": None,
                },
                "latest_access_review": {"access_class": "A"},
            }

        def machine_acquisition_decision(self, source_id: str):
            assert source_id == directory.SOURCE_ID
            return {
                "allowed": True,
                "reason_code": "machine_access_allowed",
                "reason": "fixture",
            }

    original_execute = directory.execute

    def _fixture_execute(args):
        return original_execute(
            args,
            client=_FixtureClient(_fixture_pages()),
            log_results=False,
        )

    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        _AllowedCatalog,
    )
    monkeypatch.setattr(directory, "execute", _fixture_execute)
    db_path = tmp_path / "shared-courts.db"
    payload = query_state_courts.execute(
        _shared_args(
            "search",
            "Dane",
            "--source",
            directory.SOURCE_ID,
            "--search-field",
            "clerk",
            "--ingest",
            "--court-db",
            str(db_path),
        )
    )

    assert payload["status"] == "ok"
    assert payload["ingest"]["snapshot_only"] == {
        "record_count": 1,
        "record_kinds": {"circuit_court_clerk_directory": 1},
    }
    assert all(
        value == 0 for value in payload["ingest"]["projected"].values()
    )
