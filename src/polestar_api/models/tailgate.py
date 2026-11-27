"""Power tailgate control models (invocation.InvocationService/TailgateControl)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .invocation import InvocationRequest, InvocationResponse


class TailgateControlType(IntEnum):
    UNSPECIFIED = 0
    OPEN = 1
    CLOSE = 2


@dataclass(frozen=True)
class TailgateControlRequest(ProtoMessage, schema={1: "request", 2: "tailgate_control"}):
    request: InvocationRequest | None = None
    tailgate_control: TailgateControlType = TailgateControlType.UNSPECIFIED


@dataclass(frozen=True)
class TailgateControlResponse(ProtoMessage, schema={1: "response"}):
    response: InvocationResponse | None = None
