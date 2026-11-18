"""Wake-up — request the car to wake from sleep."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import ResponseStatus


class WakeUpReason(IntEnum):
    UNDEFINED = 0
    OTA_DOWNLOAD = 1


@dataclass(frozen=True)
class WakeUpRequest(ProtoMessage, schema={1: "reason"}):
    reason: WakeUpReason = WakeUpReason.UNDEFINED


@dataclass(frozen=True)
class WakeUpResponse(ProtoMessage, schema={1: "response_status"}):
    response_status: ResponseStatus | None = None
