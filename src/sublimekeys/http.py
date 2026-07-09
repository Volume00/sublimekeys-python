"""Thin stdlib-only HTTP JSON client — deliberately no `requests` dependency,
matching the license server's own minimal-dependency style. This is also
where the server's one REST inconsistency gets papered over: /activate
raises HTTPException (404/403, body {"detail": "..."}) while /verify always
returns HTTP 200 with valid:false. Callers of this module see one shape
either way.

Transient failures (connection errors, timeouts, 5xx responses) are retried
with exponential backoff — a flaky wifi handoff or a momentary server blip
shouldn't surface as a hard failure to the caller. 4xx responses (wrong key,
bad request) are never retried — retrying a permanent rejection just delays
the inevitable and wastes the user's time.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .exceptions import NetworkError, ServerError

DEFAULT_BASE_URL = "https://api.sublimearts.io"


class HttpClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = time.sleep  # overridable in tests

    def post_json(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body)

    def get_json(self, path: str) -> dict:
        return self._request("GET", path, None)

    def _request(self, method: str, path: str, body: dict | None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}

        attempt = 0
        while True:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code >= 500 and attempt < self.max_retries:
                    self._sleep(self.backoff_base * (2 ** attempt))
                    attempt += 1
                    continue
                try:
                    payload = json.loads(e.read().decode())
                    message = payload.get("detail", str(e))
                except (ValueError, OSError):
                    message = str(e)
                if e.code >= 500:
                    raise ServerError(f"{e.code} {message}")
                return {"valid": False, "message": message, "email": None,
                        "expires_at": None, "lease": None}
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < self.max_retries:
                    self._sleep(self.backoff_base * (2 ** attempt))
                    attempt += 1
                    continue
                raise NetworkError(str(e))
