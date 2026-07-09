import json
import urllib.error

import pytest

import sublimekeys.http as http_module
from sublimekeys.exceptions import NetworkError, ServerError
from sublimekeys.http import HttpClient


class FakeResponse:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeErrorBody:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data


class ScriptedTransport:
    """Replays a fixed sequence of outcomes — an exception to raise, or a
    dict to return as a successful JSON response — one per call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, req, timeout=None):
        self.calls += 1
        outcome = self.script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)


@pytest.fixture
def client(monkeypatch):
    c = HttpClient(max_retries=2, backoff_base=0.01)
    sleeps = []
    monkeypatch.setattr(c, "_sleep", lambda s: sleeps.append(s))
    c.sleeps = sleeps
    return c


def _install(monkeypatch, script):
    transport = ScriptedTransport(script)
    monkeypatch.setattr(http_module.urllib.request, "urlopen", transport)
    return transport


def test_succeeds_without_retry_on_first_try(monkeypatch, client):
    transport = _install(monkeypatch, [{"valid": True, "message": "ok"}])
    result = client.post_json("/verify", {})
    assert result == {"valid": True, "message": "ok"}
    assert transport.calls == 1
    assert client.sleeps == []


def test_retries_transient_connection_error_then_succeeds(monkeypatch, client):
    transport = _install(monkeypatch, [
        urllib.error.URLError("connection reset"),
        {"valid": True, "message": "ok"},
    ])
    result = client.post_json("/verify", {})
    assert result == {"valid": True, "message": "ok"}
    assert transport.calls == 2
    assert client.sleeps == [0.01]  # backoff_base * 2**0


def test_exhausts_retries_on_connection_error_and_raises(monkeypatch, client):
    _install(monkeypatch, [
        urllib.error.URLError("e1"),
        urllib.error.URLError("e2"),
        urllib.error.URLError("e3"),
    ])
    with pytest.raises(NetworkError):
        client.post_json("/verify", {})
    assert client.sleeps == [0.01, 0.02]  # backoff_base * 2**0, 2**1


def test_retries_5xx_then_succeeds(monkeypatch, client):
    err = urllib.error.HTTPError(
        url="https://x", code=503, msg="Service Unavailable",
        hdrs=None, fp=FakeErrorBody({"detail": "busy"}),
    )
    transport = _install(monkeypatch, [err, {"valid": True, "message": "ok"}])
    result = client.post_json("/verify", {})
    assert result == {"valid": True, "message": "ok"}
    assert transport.calls == 2


def test_exhausts_retries_on_5xx_and_raises_server_error(monkeypatch, client):
    def make_err():
        return urllib.error.HTTPError(
            url="https://x", code=500, msg="Internal Server Error",
            hdrs=None, fp=FakeErrorBody({"detail": "boom"}),
        )
    _install(monkeypatch, [make_err(), make_err(), make_err()])
    with pytest.raises(ServerError):
        client.post_json("/verify", {})


def test_4xx_is_not_retried(monkeypatch, client):
    err = urllib.error.HTTPError(
        url="https://x", code=403, msg="Forbidden",
        hdrs=None, fp=FakeErrorBody({"detail": "bad key"}),
    )
    transport = _install(monkeypatch, [err])
    result = client.post_json("/activate", {})
    assert result["valid"] is False
    assert result["message"] == "bad key"
    assert transport.calls == 1
    assert client.sleeps == []
