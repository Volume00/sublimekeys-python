"""Thin stdlib-only HTTP JSON client — deliberately no `requests` dependency,
matching the license server's own minimal-dependency style. This is also
where the server's one REST inconsistency gets papered over: /activate
raises HTTPException (404/403, body {"detail": "..."}) while /verify always
returns HTTP 200 with valid:false. Callers of this module see one shape
either way.
"""

import json
import urllib.error
import urllib.request

from .exceptions import NetworkError

DEFAULT_BASE_URL = "https://api.sublimearts.io"


class HttpClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post_json(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body)

    def get_json(self, path: str) -> dict:
        return self._request("GET", path, None)

    def _request(self, method: str, path: str, body: dict | None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode())
                message = payload.get("detail", str(e))
            except (ValueError, OSError):
                message = str(e)
            return {"valid": False, "message": message, "email": None,
                    "expires_at": None, "lease": None}
        except urllib.error.URLError as e:
            raise NetworkError(str(e))
        except TimeoutError as e:
            raise NetworkError(str(e))
