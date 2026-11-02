import json
import sqlite3
import sys

import pytest

from tools import graph_tools


@pytest.fixture
def graph_db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_a TEXT NOT NULL,
            person_b TEXT NOT NULL,
            relationship_type TEXT,
            description TEXT,
            strength TEXT,
            created_at TEXT,
            valid_from TEXT,
            valid_until TEXT,
            profile_id TEXT
        );

        CREATE TABLE name_aliases (
            canonical_name TEXT NOT NULL,
            alias TEXT UNIQUE,
            alias_type TEXT,
            entity_id INTEGER
        );

        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE entity_relations (
            id INTEGER PRIMARY KEY,
            entity_a_id INTEGER NOT NULL,
            entity_b_id INTEGER NOT NULL,
            relation_type TEXT,
            description TEXT
        );
    """)
    yield db
    db.close()


def _add_connection(db, person_a, person_b, valid_from=None, valid_until=None):
    db.execute(
        """
        INSERT INTO connections (
            person_a, person_b, relationship_type, description, strength,
            created_at, valid_from, valid_until
        ) VALUES (?, ?, 'controls', 'fixture edge', 'medium',
                  '2026-01-01', ?, ?)
        """,
        (person_a, person_b, valid_from, valid_until),
    )
    db.commit()


def test_alias_variants_collapse_to_one_node(graph_db):
    graph_db.executemany(
        "INSERT INTO name_aliases (canonical_name, alias, alias_type) VALUES (?, ?, ?)",
        [
            (
                "Palantir Technologies Inc.",
                "Palantir Technologies",
                "organization",
            ),
            ("Palantir Technologies Inc.", "Palantir", "organization"),
        ],
    )
    _add_connection(graph_db, "Palantir Technologies", "Investor")
    _add_connection(graph_db, "Palantir", "Customer")

    adj, nodes = graph_tools.build_graph(graph_db, all_profiles=True)

    assert "Palantir Technologies Inc." in nodes
    assert "Palantir Technologies" not in nodes
    assert "Palantir" not in nodes
    assert set(adj["Palantir Technologies Inc."]) == {"Investor", "Customer"}


def test_directed_and_undirected_adjacency_cover_both_edge_sources(graph_db):
    _add_connection(graph_db, "Connection A", "Connection B")
    graph_db.executemany(
        "INSERT INTO entities (id, name) VALUES (?, ?)",
        [(1, "Entity A"), (2, "Entity B")],
    )
    graph_db.execute(
        """
        INSERT INTO entity_relations (
            id, entity_a_id, entity_b_id, relation_type, description
        ) VALUES (1, 1, 2, 'owns', 'fixture entity relation')
        """
    )
    graph_db.commit()

    undirected, undirected_nodes = graph_tools.build_graph(
        graph_db, all_profiles=True
    )
    directed, directed_nodes = graph_tools.build_graph(
        graph_db, all_profiles=True, directed=True
    )

    assert "Connection B" in undirected["Connection A"]
    assert "Connection A" in undirected["Connection B"]
    assert "Entity B" in undirected["Entity A"]
    assert "Entity A" in undirected["Entity B"]
    assert "Connection B" in directed["Connection A"]
    assert "Connection A" not in directed.get("Connection B", {})
    assert "Entity B" in directed["Entity A"]
    assert "Entity A" not in directed.get("Entity B", {})
    assert directed_nodes == undirected_nodes


def test_paths_output_writes_valid_json(
    graph_db, monkeypatch, tmp_path, capsys
):
    _add_connection(graph_db, "Source", "Middle")
    _add_connection(graph_db, "Middle", "Target")
    adj, nodes = graph_tools.build_graph(graph_db, all_profiles=True)
    output = tmp_path / "path.json"
    monkeypatch.setattr(
        graph_tools,
        "build_graph",
        lambda **kwargs: (adj, nodes),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graph_tools.py",
            "paths",
            "Source",
            "Target",
            "--output",
            str(output),
        ],
    )

    graph_tools.main()

    payload = json.loads(output.read_text())
    assert payload["path"] == ["Source", "Middle", "Target"]
    assert payload["hops"] == 2
    assert payload["found"] is True
    assert "saved to" in capsys.readouterr().out


def test_as_of_policy_strict_and_lenient(graph_db, capsys):
    _add_connection(graph_db, "Dated A", "Dated B", valid_from="2020-01-01")
    _add_connection(graph_db, "Undated A", "Undated B")

    lenient, _ = graph_tools.build_graph(
        graph_db,
        as_of="2026-01-01",
        all_profiles=True,
    )
    lenient_warning = capsys.readouterr().err

    strict, _ = graph_tools.build_graph(
        graph_db,
        as_of="2026-01-01",
        as_of_policy="strict",
        all_profiles=True,
    )
    strict_warning = capsys.readouterr().err

    assert "Dated B" in lenient["Dated A"]
    assert "Undated B" in lenient["Undated A"]
    assert "Dated B" in strict["Dated A"]
    assert "Undated A" not in strict
    assert (
        "as-of 2026-01-01 (lenient): 1/2 edges undated and included "
        "— dates cover 50.0% of the graph"
    ) in lenient_warning
    assert (
        "as-of 2026-01-01 (strict): 1/2 edges undated and excluded "
        "— dates cover 50.0% of the graph"
    ) in strict_warning


def test_lenient_as_of_drops_undated_edges_that_ended_before_the_date(graph_db):
    _add_connection(graph_db, "Ended A", "Ended B", valid_until="2020-01-01")
    _add_connection(graph_db, "Open A", "Open B")

    lenient, _ = graph_tools.build_graph(graph_db, as_of="2026-01-01", all_profiles=True)

    assert "Ended A" not in lenient
    assert "Open B" in lenient["Open A"]


@pytest.mark.parametrize("command", ["centrality", "stats"])
def test_as_of_subcommands_forward_policy(command, monkeypatch, capsys):
    captured = {}

    def fake_build_graph(**kwargs):
        captured.update(kwargs)
        return {}, set()

    monkeypatch.setattr(graph_tools, "build_graph", fake_build_graph)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graph_tools.py",
            command,
            "--as-of",
            "2026-01-01",
            "--as-of-policy",
            "strict",
            "--json",
        ],
    )

    graph_tools.main()

    assert captured["as_of"] == "2026-01-01"
    assert captured["as_of_policy"] == "strict"
    json.loads(capsys.readouterr().out)


def test_alias_schema_mismatch_warns(graph_db, capsys):
    graph_db.execute("DROP TABLE name_aliases")

    graph_tools.build_graph(graph_db, all_profiles=True)

    assert "Warning: could not load name aliases:" in capsys.readouterr().err
