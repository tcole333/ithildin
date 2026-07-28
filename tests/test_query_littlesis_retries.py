import io
from urllib.error import HTTPError

from tools import query_littlesis


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    @staticmethod
    def read():
        return b'{"data": [{"id": "123"}]}'


def test_request_retries_http_500_with_bounded_backoff(monkeypatch):
    calls = []
    sleeps = []

    def urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        if len(calls) < 3:
            raise HTTPError(
                request.full_url,
                500,
                "Internal Server Error",
                hdrs=None,
                fp=io.BytesIO(b"temporary failure"),
            )
        return _Response()

    monkeypatch.setattr(query_littlesis, "urlopen", urlopen)
    monkeypatch.setattr(
        query_littlesis.time,
        "sleep",
        lambda seconds: sleeps.append(seconds),
    )

    result = query_littlesis._request(
        "/entities/search",
        {"q": "Brad Karp"},
    )

    assert result == {"data": [{"id": "123"}]}
    assert len(calls) == 3
    assert sleeps == [3, 6]
