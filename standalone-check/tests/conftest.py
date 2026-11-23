"""Ordinary tests have no permission to call providers or the network."""
import socket
import pytest

@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Network use is forbidden in synthetic tests")
    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket, "create_connection", reject)
    for name in ("STANDALONE_CHECK_BASE_URL", "STANDALONE_CHECK_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
