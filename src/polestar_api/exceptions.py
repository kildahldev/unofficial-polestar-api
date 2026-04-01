"""Exceptions for the Polestar API client."""


class PolestarError(Exception):
    """Base exception for all Polestar API errors."""


class AuthError(PolestarError):
    """Authentication failed."""


class TokenExpiredError(AuthError):
    """Token has expired and refresh failed."""


class ApiError(PolestarError):
    """An API call failed."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
