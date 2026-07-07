"""Export API errors."""

from __future__ import annotations


class GhostDQAPIError(Exception):
    """Raised when the Ingest API returns a non-2xx status code.

    Attributes:
        status_code: HTTP status code from the failed response.
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
