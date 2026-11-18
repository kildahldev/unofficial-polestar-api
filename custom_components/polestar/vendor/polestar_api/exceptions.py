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


_UNSUPPORTED_MESSAGES = ("Functionality not supported", "Method not found")


def is_unsupported_feature_error(err: BaseException) -> bool:
    """Return True if *err* means the car or backend does not offer this call.

    Polestar answers UNIMPLEMENTED with "Functionality not supported" for features
    a model lacks, and "Method not found" for endpoints it has removed.
    """
    from grpclib.const import Status
    from grpclib.exceptions import GRPCError

    return (
        isinstance(err, GRPCError)
        and err.status == Status.UNIMPLEMENTED
        and any(message in (err.message or "") for message in _UNSUPPORTED_MESSAGES)
    )


class NetworkError(PolestarError):
    """A network-level error occurred (connection refused, DNS, timeout)."""


class VehicleUnavailableError(PolestarError):
    """The vehicle is offline or in a mode that prevents communication."""
