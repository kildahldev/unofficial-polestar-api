"""Lock/unlock request and response models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import ResponseStatus
from .exterior import ExteriorStatus


class LockFeedback(IntEnum):
    UNSPECIFIED = 0
    IDLE = 1
    SILENT = 2
    NORMAL = 3


class LockAlarmLevel(IntEnum):
    UNSPECIFIED = 0
    IDLE = 1
    REDUCED = 2
    NORMAL = 3


@dataclass(frozen=True)
class CarLockRequest(ProtoMessage, schema={1: "feedback", 2: "alarm_level", 3: "uuid"}):
    feedback: LockFeedback = LockFeedback.UNSPECIFIED
    alarm_level: LockAlarmLevel = LockAlarmLevel.UNSPECIFIED
    uuid: str = ""


@dataclass(frozen=True)
class CarLockResponse(ProtoMessage, schema={1: "response_status", 2: "exterior_status"}):
    response_status: ResponseStatus | None = None
    exterior_status: ExteriorStatus | None = None


class UnlockFeedback(IntEnum):
    UNSPECIFIED = 0
    IDLE = 1
    SILENT = 2
    NORMAL = 3


@dataclass(frozen=True)
class CarUnlockRequest(ProtoMessage, schema={1: "feedback", 2: "uuid"}):
    feedback: UnlockFeedback = UnlockFeedback.UNSPECIFIED
    uuid: str = ""


@dataclass(frozen=True)
class CarUnlockResponse(ProtoMessage, schema={1: "response_status", 2: "exterior_status"}):
    response_status: ResponseStatus | None = None
    exterior_status: ExteriorStatus | None = None


@dataclass(frozen=True)
class TrunkUnlockRequest(ProtoMessage, schema={1: "uuid"}):
    uuid: str = ""


@dataclass(frozen=True)
class TrunkUnlockResponse(ProtoMessage, schema={1: "response_status", 2: "exterior_status"}):
    response_status: ResponseStatus | None = None
    exterior_status: ExteriorStatus | None = None
