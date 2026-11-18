"""Lock/unlock request and response models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .invocation import InvocationRequest, InvocationResponse


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


class LockType(IntEnum):
    LOCK = 0
    LOCK_REDUCED_GUARD = 1


@dataclass(frozen=True)
class CarLockRequest(ProtoMessage, schema={1: "request", 2: "lock_type"}):
    request: InvocationRequest | None = None
    lock_type: LockType = LockType.LOCK


@dataclass(frozen=True)
class CarLockResponse(ProtoMessage, schema={1: "response", 2: "lock_error"}):
    response: InvocationResponse | None = None
    lock_error: int = 0


class UnlockFeedback(IntEnum):
    UNSPECIFIED = 0
    IDLE = 1
    SILENT = 2
    NORMAL = 3


class UnlockType(IntEnum):
    UNLOCK_TYPE_UNSPECIFIED = 0
    UNLOCK_TYPE_TRUNK_ONLY = 1


@dataclass(frozen=True)
class CarUnlockRequest(ProtoMessage, schema={1: "request", 2: "unlock_type"}):
    request: InvocationRequest | None = None
    unlock_type: UnlockType = UnlockType.UNLOCK_TYPE_UNSPECIFIED


@dataclass(frozen=True)
class CarUnlockResponse(ProtoMessage, schema={1: "response", 2: "ready_to_unlock_until"}):
    response: InvocationResponse | None = None
    ready_to_unlock_until: int = 0


@dataclass(frozen=True)
class TrunkUnlockResponse(ProtoMessage, schema={1: "response", 2: "ready_to_unlock_until"}):
    response: InvocationResponse | None = None
    ready_to_unlock_until: int = 0
