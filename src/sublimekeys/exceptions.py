class SublimeKeysError(Exception):
    """Base class for all sublimekeys errors."""


class NetworkError(SublimeKeysError):
    """Raised when a request to the SublimeKeys API fails to complete
    (unreachable host, timeout, connection reset, ...)."""


class LeaseError(SublimeKeysError):
    """Raised when a cached offline lease fails verification — malformed,
    tampered, expired, or scoped to a different license/machine/product."""
