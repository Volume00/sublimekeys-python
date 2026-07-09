import base64
import json
import urllib.error

import pytest

import sublimekeys.http as http_module
from sublimekeys.cli import main


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeResponse:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeTransport:
    def __init__(self):
        self._queue = []

    def queue_response(self, data: dict):
        self._queue.append(data)

    def __call__(self, req, timeout=None):
        if not self._queue:
            raise urllib.error.URLError("no response queued")
        return FakeResponse(self._queue.pop(0))


@pytest.fixture
def fake_transport(monkeypatch):
    transport = FakeTransport()
    monkeypatch.setattr(http_module.urllib.request, "urlopen", transport)
    return transport


def test_activate_prints_result_and_returns_zero_on_success(fake_transport, tmp_path, capsys):
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": "buyer@example.com",
        "expires_at": None, "lease": None,
    })
    code = main(["activate", "--product", "test-product", "--cache-dir", str(tmp_path), "LIC-1"])
    assert code == 0
    out = capsys.readouterr().out
    assert "valid: True" in out


def test_activate_returns_one_on_invalid(fake_transport, tmp_path, capsys):
    fake_transport.queue_response({
        "valid": False, "message": "Not found", "email": None,
        "expires_at": None, "lease": None,
    })
    code = main(["activate", "--product", "test-product", "--cache-dir", str(tmp_path), "BAD-KEY"])
    assert code == 1


def test_json_flag_prints_valid_json(fake_transport, tmp_path, capsys):
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": None,
        "expires_at": None, "lease": None,
    })
    main(["activate", "--product", "test-product", "--cache-dir", str(tmp_path), "--json", "LIC-1"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["valid"] is True


def test_machine_id_command_prints_a_stable_id(tmp_path, capsys):
    code1 = main(["machine-id", "--product", "test-product", "--cache-dir", str(tmp_path)])
    first = capsys.readouterr().out.strip()
    code2 = main(["machine-id", "--product", "test-product", "--cache-dir", str(tmp_path)])
    second = capsys.readouterr().out.strip()
    assert code1 == 0 and code2 == 0
    assert first == second
    assert len(first) > 0


def test_trial_status_returns_one_when_not_active(fake_transport, tmp_path):
    fake_transport.queue_response({"status": "none", "days_left": 0, "expires_at": None, "message": ""})
    code = main(["trial-status", "--product", "test-product", "--cache-dir", str(tmp_path)])
    assert code == 1


def test_trial_status_returns_zero_when_active(fake_transport, tmp_path):
    fake_transport.queue_response({"status": "active", "days_left": 5, "expires_at": None, "message": ""})
    code = main(["trial-status", "--product", "test-product", "--cache-dir", str(tmp_path)])
    assert code == 0


def test_missing_product_flag_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["activate", "LIC-1"])
    assert exc_info.value.code == 2
