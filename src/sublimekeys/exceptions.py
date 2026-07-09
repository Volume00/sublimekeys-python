class SublimeKeysError(Exception):
    """Base class for all sublimekeys errors."""


class NetworkError(SublimeKeysError):
    """Raised when a request to the SublimeKeys API fails to complete
    (unreachable host, timeout, connection reset, ...), including when
    retries for a transient failure are exhausted."""


class ServerError(NetworkError):
    """Raised when the API responds with a 5xx status after retries are
    exhausted. A subclass of NetworkError so existing `except NetworkError`
    handlers keep working unchanged; callers who want to distinguish "server
    is having a bad day" from "couldn't reach the server at all" can catch
    this specifically."""


class LeaseError(SublimeKeysError):
    """Raised when a cached offline lease fails verification — malformed,
    tampered, expired, or scoped to a different license/machine/product."""
