import socket

import pytest

from tests.conftest import _is_loopback_address


@pytest.mark.parametrize("address", [("127.0.0.1", 80), ("::1", 80, 0, 0), ("localhost", 80)])
def test_local_fixture_addresses_allowed(address):
    assert _is_loopback_address(address)


@pytest.mark.parametrize("address", [("192.0.2.1", 80), ("example.com", 80), ("127.0.0.1.example.com", 80), "127.0.0.1", ()])
def test_external_or_malformed_addresses_rejected(address):
    assert not _is_loopback_address(address)


def test_offline_guard_rejects_external_connection_before_dns(request):
    if not request.config.getoption("offline"):
        pytest.skip("Exercises the explicit --offline guard")
    with pytest.raises(AssertionError, match="External network"):
        socket.create_connection(("no-dns-request.example.invalid", 80))
    with socket.socket() as sock, pytest.raises(AssertionError, match="External network"):
        sock.connect(("192.0.2.1", 80))
