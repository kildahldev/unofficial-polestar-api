"""Shared invocation request/response models for remote commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage


@dataclass(frozen=True)
class InvocationRequest(ProtoMessage, schema={1: "vin"}):
    """Shared mdapi command envelope carrying the vehicle VIN."""

    vin: str = ""


class InvocationStatus(IntEnum):
    UNKNOWN_ERROR = 0
    SENT = 1
    CAR_OFFLINE = 2
    DELIVERED = 4
    DELIVERY_TIMEOUT = 5
    SUCCESS = 6
    RESPONSE_TIMEOUT = 7
    UNKNOWN_CAR_ERROR = 8
    NOT_ALLOWED_PRIVACY_ENABLED = 9
    NOT_ALLOWED_WRONG_USAGE_MODE = 10
    INVOCATION_SPECIFIC_ERROR = 11
    NOT_ALLOWED_CONFLICTING_INVOCATION = 12


@dataclass(frozen=True)
class InvocationResponse(ProtoMessage, schema={
    1: "id",
    2: "vin",
    3: "status",
    4: "message",
    5: "timestamp",
}):
    """Common mdapi response envelope returned by command RPCs."""

    id: str = ""
    vin: str = ""
    status: InvocationStatus = InvocationStatus.UNKNOWN_ERROR
    message: str = ""
    timestamp: int = 0
