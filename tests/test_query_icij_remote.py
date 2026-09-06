import sys

import pytest

from tools import query_icij


NODE_HTML = """
<html><body><script>
document.body.nodeData = [
  {
    "id": 200,
    "linkurious_id": "officer-link",
    "data": {
      "categories": ["Officer"],
      "properties": {"name": "EXAMPLE OFFICER", "node_id": 200},
      "statistics": {"degree": 1}
    },
    "edges": [{
      "id": "edge-1",
      "source": "officer-link",
      "target": "entity-link",
      "data": {"type": "officer_of", "properties": {"sourceID": "Panama Papers"}}
    }]
  },
  {
    "id": 100,
    "linkurious_id": "entity-link",
    "data": {
      "categories": ["Entity"],
      "properties": {"name": "EXAMPLE ENTITY LTD.", "node_id": 100},
      "statistics": {"degree": 1}
    }
  }
];
</script></body></html>
"""


def test_reconcile_parses_current_types_schema(monkeypatch):
    monkeypatch.setattr(
        query_icij,
        "_do_reconcile_request",
        lambda queries, timeout=30: {
            "q0": {
                "result": [{
                    "id": "82004676",
                    "name": "Liquid Funding, Ltd.",
                    "description": "Entity node extracted from the Paradise Papers.",
                    "score": 77.7,
                    "match": False,
                    "types": [{"name": "Entity"}],
                }]
            }
        },
    )

    result = query_icij.reconcile_name("Liquid Funding")

    assert result[0]["type"] == ["Entity"]
    assert result[0]["description"].startswith("Entity node")


def test_node_page_parser_extracts_main_node_and_first_hop_edge():
    graph = query_icij._parse_node_page(NODE_HTML, "100")

    assert graph["main"]["id"] == 100
    assert len(graph["connections"]) == 1
    assert graph["connections"][0] == {
        "from_name": "EXAMPLE OFFICER",
        "from_id": "200",
        "from_types": ["Officer"],
        "rel_type": "officer_of",
        "to_name": "EXAMPLE ENTITY LTD.",
        "to_id": "100",
        "to_types": ["Entity"],
        "properties": {"sourceID": "Panama Papers"},
    }


def test_remote_officers_preserves_role_and_source(monkeypatch):
    graph = query_icij._parse_node_page(NODE_HTML, "100")
    monkeypatch.setattr(query_icij, "_resolve_remote_node", lambda value, node_type=None: ("100", None))
    monkeypatch.setattr(query_icij, "get_remote_node", lambda node_id: graph)

    result = query_icij.remote_officers("EXAMPLE ENTITY LTD.")

    assert result == [{
        "entity_name": "EXAMPLE ENTITY LTD.",
        "entity_id": "100",
        "jurisdiction": None,
        "role": "officer_of",
        "officer_name": "EXAMPLE OFFICER",
        "officer_id": "200",
        "source": "Panama Papers",
        "resolved_candidate": None,
    }]


def test_search_defaults_to_remote_reconciliation(monkeypatch, capsys):
    monkeypatch.setattr(
        query_icij,
        "reconcile_name",
        lambda name, limit, node_type: [{"name": name, "id": "1", "type": ["Officer"]}],
    )
    monkeypatch.setattr(
        query_icij,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("local Neo4j must not run")),
    )
    monkeypatch.setattr(query_icij, "log_search", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["query_icij.py", "search", "Indyke", "--json"])

    query_icij.main()

    assert '"name": "Indyke"' in capsys.readouterr().out


def test_reconcile_transport_failure_is_not_reported_as_zero_results(monkeypatch):
    error = query_icij.URLError("offline")
    monkeypatch.setattr(
        query_icij,
        "_do_reconcile_request",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(query_icij.ICIJRemoteError, match="failed: offline"):
        query_icij.reconcile_name("Liquid Funding")


def test_reconcile_response_is_bounded(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            assert size == query_icij.MAX_RECONCILE_BYTES + 1
            return b"x" * size

    monkeypatch.setattr(query_icij, "urlopen", lambda request, timeout: FakeResponse())
    monkeypatch.setattr(query_icij.time, "sleep", lambda delay: None)

    with pytest.raises(query_icij.ICIJRemoteError, match="reconciliation response exceeds"):
        query_icij._do_reconcile_request({"q0": {"query": "Liquid Funding"}})


def test_batch_reconcile_transport_failure_uses_remote_error(monkeypatch):
    monkeypatch.setattr(
        query_icij,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(query_icij.URLError("offline")),
    )
    monkeypatch.setattr(query_icij.time, "sleep", lambda delay: None)

    with pytest.raises(query_icij.ICIJRemoteError, match="failed: offline"):
        query_icij.reconcile_batch(["Liquid Funding"])


def test_fuzzy_name_is_not_silently_traversed(monkeypatch):
    monkeypatch.setattr(
        query_icij,
        "reconcile_name",
        lambda *args, **kwargs: [{
            "id": "10023453",
            "name": "PROTON FINANCIAL COMPANY LTD.",
            "score": 71.0,
            "match": False,
        }],
    )

    with pytest.raises(query_icij.ICIJRemoteError, match="only fuzzy candidates") as exc_info:
        query_icij._resolve_remote_node("Financial Trust Company", node_type="Entity")

    assert "10023453" in str(exc_info.value)
    assert "numeric node ID" in str(exc_info.value)


def test_exact_name_can_resolve_to_remote_node(monkeypatch):
    monkeypatch.setattr(
        query_icij,
        "reconcile_name",
        lambda *args, **kwargs: [{
            "id": "82004676",
            "name": "Liquid Funding, Ltd.",
            "score": 77.7,
            "match": False,
        }],
    )

    assert query_icij._resolve_remote_node("liquid funding, ltd.") == (
        "82004676",
        {
            "id": "82004676",
            "name": "Liquid Funding, Ltd.",
            "score": 77.7,
            "match": False,
        },
    )


def test_remote_node_rejects_oversized_response_before_read(monkeypatch):
    class FakeResponse:
        headers = {"Content-Length": str(query_icij.MAX_NODE_PAGE_BYTES + 1)}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            raise AssertionError("oversized response must not be read")

    monkeypatch.setattr(query_icij, "urlopen", lambda request, timeout: FakeResponse())
    monkeypatch.setattr(query_icij.time, "sleep", lambda delay: None)

    with pytest.raises(query_icij.ICIJRemoteError, match="safety limit"):
        query_icij.get_remote_node("10023453")


def test_remote_node_rejects_invalid_content_length(monkeypatch):
    class FakeResponse:
        headers = {"Content-Length": "unknown"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(query_icij, "urlopen", lambda request, timeout: FakeResponse())
    monkeypatch.setattr(query_icij.time, "sleep", lambda delay: None)

    with pytest.raises(query_icij.ICIJRemoteError, match="invalid Content-Length"):
        query_icij.get_remote_node("10023453")
