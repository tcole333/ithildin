import argparse
import json
from types import SimpleNamespace

from squarelet.exceptions import SquareletError

from tools import query_muckrock


def _api_error(status_code):
    return SquareletError(
        response=SimpleNamespace(
            status_code=status_code,
            text="temporary upstream failure",
        )
    )


class _Communication(SimpleNamespace):
    def get_files(self):
        return []


class _Request(SimpleNamespace):
    def get_communications(self):
        return self.communications


def _request(communications):
    return _Request(
        id=72901,
        title="Public records request",
        status="done",
        agency={"id": 1, "name": "Example Agency"},
        datetime_submitted="2020-01-01T00:00:00Z",
        datetime_done="2020-01-02T00:00:00Z",
        tracking_id="",
        slug="public-records-request",
        requested_docs="Records",
        communications=communications,
    )


def test_request_retries_transient_503_then_writes_detail(
    tmp_path, monkeypatch
):
    calls = []
    sleeps = []
    foia = _request([])

    def retrieve(request_id):
        calls.append(request_id)
        if len(calls) == 1:
            raise _api_error(503)
        return foia

    client = SimpleNamespace(
        requests=SimpleNamespace(retrieve=retrieve),
    )
    monkeypatch.setattr(
        query_muckrock.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )
    output = tmp_path / "request.json"

    result = query_muckrock.cmd_request(
        client,
        argparse.Namespace(
            request_id=72901,
            output=str(output),
            json_out=False,
        ),
    )

    assert result == 0
    assert calls == [72901, 72901]
    assert sleeps == [1.0]
    assert json.loads(output.read_text())["id"] == 72901


def test_request_detail_preserves_public_communication_body():
    body = "The delivery password is provided separately in this message."
    communication = _Communication(
        id=1107116,
        datetime="2020-01-02T00:00:00Z",
        from_user=1,
        to_user=2,
        subject="Records delivery",
        communication=body,
        response=True,
        status="done",
        files=[],
    )

    detail, files = query_muckrock._request_detail(
        SimpleNamespace(),
        _request([communication]),
    )

    assert files == []
    assert detail["communications"][0]["body"] == body
