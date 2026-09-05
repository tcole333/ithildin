"""Evidence-boundary tests; all fixtures and writes are isolated in tmp_path."""

from copy import deepcopy
from email.message import Message
import html
import http.client
import json
import re
import threading
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from tools.boston_ucc_cua_bridge import (
    BridgeHandler, BridgeServer, EMPTY_MESSAGE, HEADERS, ObservationStore, ValidationError,
    render_page, validate_observation,
)


@pytest.fixture
def holder():
    return {
        "holder_id": "BH-example", "business_name": "Example LLC",
        "license_numbers": ["LB-1"], "query_input_requires_review": False,
        "query_proposal": {"command": "search-org", "query": "Example", "role": "debtor",
                           "search_type": "begins", "city": None, "state": None,
                           "since": None, "limit": 500},
        "searches": {"current": {"state": "pending"}, "lapsed": {"state": "pending"}},
    }


@pytest.fixture
def observation():
    header = [{"text": name, "links": []} for name in HEADERS]
    cells = [{"text": text, "links": []} for text in
             ["EXAMPLE LLC", "DEBTOR", "BOSTON", "MA", "UCC-1", "202600000001",
              "202600000001", "09/03/2026"]]
    cells[5]["links"] = [{"text": "202600000001", "url": "UCCFilingHistory.aspx?sysvalue=x"}]
    return {"holder_id": "BH-example", "scope": "current", "query": "Example",
            "heading": "UCC Search Results", "captured_at": "2026-09-03T20:00:00Z",
            "url": "https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx?sysvalue=x",
            "reported_count": 2, "text": "Number of records: 2", "rows": [header, cells, cells]}


def test_browser_cells_preserve_duplicate_occurrences_and_history_link(holder, observation):
    event = validate_observation(observation, {holder["holder_id"]: holder})
    assert event["state"] == "complete"
    assert event["returned_count"] == 2
    assert event["occurrences"][0] == event["occurrences"][1]
    assert event["occurrences"][0]["history_url"].startswith("https://corp.sec.state.ma.us/")
    assert event["query"] == holder["query_proposal"]
    assert event["review"]["history_state"] == "not_started"


@pytest.mark.parametrize("change,match", [
    ({"query": "Another company"}, "query"),
    ({"reported_count": 3, "text": "Number of records: 3"}, "reported_count"),
    ({"heading": "Verify you are human"}, "heading"),
    ({"text": "Number of records: 8"}, "source_quote"),
])
def test_mismatches_rejected(holder, observation, change, match):
    observation.update(change)
    with pytest.raises(ValidationError, match=match):
        validate_observation(observation, {holder["holder_id"]: holder})


def test_complete_requires_exact_eight_column_header(holder, observation):
    observation["rows"][0][5]["text"] = "Changed column"
    with pytest.raises(ValidationError, match="header"):
        validate_observation(observation, {holder["holder_id"]: holder})


def test_empty_needs_explicit_marker(holder, observation):
    observation.update(reported_count=0, rows=[], text="Number of records: 0")
    with pytest.raises(ValidationError, match="no-records marker"):
        validate_observation(observation, {holder["holder_id"]: holder})
    observation["text"] = EMPTY_MESSAGE
    assert validate_observation(observation, {holder["holder_id"]: holder})["state"] == "complete"


def test_over_500_is_partial_not_complete(holder, observation):
    observation.update(reported_count=501, text="Number of records: 501")
    result = validate_observation(observation, {holder["holder_id"]: holder})
    assert result["state"] == "partial" and result["truncated"]
    observation["truncated"] = False
    with pytest.raises(ValidationError, match="500"):
        validate_observation(observation, {holder["holder_id"]: holder})


def test_store_batch_validation_attempts_and_pending_state(tmp_path, holder, observation):
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"holders": [holder]}))
    store = ObservationStore(queue, tmp_path / "observations")
    wrong = deepcopy(observation)
    wrong["query"] = "Wrong"
    with pytest.raises(ValidationError):
        store.save(json.dumps([observation, wrong]))
    assert not store.events_path.exists()
    assert not list(store.raw_dir.iterdir())
    partial = deepcopy(observation)
    partial.update(reported_count=3, text="Number of records: 3", truncated=True)
    store.save(json.dumps([partial]))
    assert store.snapshot("current")[2] == 1
    first = store.save(json.dumps([observation]))
    second = store.save(json.dumps([observation]))
    assert first[0]["source_file"] != second[0]["source_file"]
    assert len(store.events()) == 3
    assert store.snapshot("current")[2] == 0
    assert store.snapshot("lapsed")[2] == 1
    assert json.loads(queue.read_text())["holders"][0]["searches"]["current"]["state"] == "pending"
    assert "Index" not in first[0]["review"]


@pytest.mark.parametrize("host,origin,allowed", [
    ("127.0.0.1:8768", "http://127.0.0.1:8768", True),
    ("localhost:8768", "http://localhost:8768", True),
    ("evil.example:8768", "http://evil.example:8768", False),
    ("127.0.0.1:8768", "https://evil.example", False),
    ("127.0.0.1:8768", None, False),
    ("127.0.0.1:8768", "http://127.0.0.1:9999", False),
])
def test_local_origin_boundary(host, origin, allowed):
    request = SimpleNamespace(headers=Message(), server=SimpleNamespace(server_port=8768))
    request.headers["Host"] = host
    if origin:
        request.headers["Origin"] = origin
    assert BridgeHandler.local_request(request, require_origin=True) is allowed


@pytest.mark.parametrize("input_flag", [True, False])
def test_name_review_sorted_last_and_page_escapes_queue_text(tmp_path, holder, input_flag):
    review = deepcopy(holder)
    review.update(holder_id="BH-review", business_name="<script>bad</script>",
                  query_input_requires_review=input_flag,
                  name_mode_review_reasons=["organization form not explicit"])
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"holders": [review, holder]}))
    store = ObservationStore(queue, tmp_path / "observations")
    assert store.snapshot("current")[1][0]["holder_id"] == "BH-example"
    review_request = store.snapshot("current")[1][1]
    assert review_request["name_mode_review_required"] is True
    assert review_request["query_input_requires_review"] is input_flag
    page = render_page(store, "test-token", "current")
    assert "<script>bad</script>" not in page
    assert "&lt;script&gt;bad&lt;/script&gt;" in page


@pytest.mark.integration
def test_http_nonce_large_save_and_failure_recovery(tmp_path, holder, observation):
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps({"holders": [holder]}))
    store = ObservationStore(queue, tmp_path / "evidence")
    server = BridgeServer(0, store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        conn.request("GET", "/")
        response = conn.getresponse()
        csp = response.getheader("Content-Security-Policy")
        page = response.read().decode()
        assert response.status == 200
        nonce = re.search(r'<script nonce="([^"]+)">', page)[1]
        token = re.search(r'name="csrf" value="([^"]+)"', page)[1]
        assert f"script-src 'nonce-{nonce}'" in csp and nonce != token
        assert "connect-src 'self'" in csp
        assert "script-src 'unsafe-inline'" not in csp
        assert "document.addEventListener('click'" in page

        wrong = deepcopy(observation)
        wrong["query"] = "Wrong query retained"
        body = urlencode({"csrf": token, "observations": json.dumps([wrong])})
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": origin}
        conn.request("POST", "/save", body, headers)
        response = conn.getresponse()
        error_page = response.read().decode()
        assert response.status == 400
        assert '"query": "Wrong query retained"' in html.unescape(error_page)
        assert not store.events()

        headers["Origin"] = "https://example.invalid"
        conn.request("POST", "/save", body, headers)
        response = conn.getresponse()
        response.read()
        assert response.status == 403

        observation["text"] += " observed page context" * 4000
        body = urlencode({"csrf": token, "observations": json.dumps([observation])})
        assert len(body) > 69289
        headers["Origin"] = origin
        conn.request("POST", "/save", body, headers)
        response = conn.getresponse()
        page = response.read().decode()
        assert response.status == 200 and "Saved 1 index observations" in page
        assert len(store.events()) == 1 and store.snapshot("current")[2] == 0
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
