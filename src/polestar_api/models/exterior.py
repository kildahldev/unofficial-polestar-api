"""Exterior status — doors, windows, locks, sunroof, hood, tailgate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage


class LockStatus(IntEnum):
    UNSPECIFIED = 0
    UNLOCKED = 1
    LOCKED = 2


class OpenStatus(IntEnum):
    UNSPECIFIED = 0
    OPEN = 1
    CLOSED = 2
    AJAR = 3


class AlarmStatus(IntEnum):
    UNSPECIFIED = 0
    TRIGGERED = 1
    OFF = 2


@dataclass(frozen=True)
class DoorStatus(ProtoMessage, schema={1: "lock_status", 2: "open_status", 3: "alarm_status"}):
    lock_status: LockStatus = LockStatus.UNSPECIFIED
    open_status: OpenStatus = OpenStatus.UNSPECIFIED
    alarm_status: AlarmStatus = AlarmStatus.UNSPECIFIED


@dataclass(frozen=True)
class WindowStatus(ProtoMessage, schema={1: "open_status"}):
    open_status: OpenStatus = OpenStatus.UNSPECIFIED


@dataclass(frozen=True)
class CentralLockStatus(ProtoMessage, schema={1: "lock_status"}):
    lock_status: LockStatus = LockStatus.UNSPECIFIED


@dataclass(frozen=True)
class DoorsStatus(ProtoMessage, schema={1: "front_left", 2: "front_right", 3: "rear_left", 4: "rear_right"}):
    front_left: DoorStatus | None = None
    front_right: DoorStatus | None = None
    rear_left: DoorStatus | None = None
    rear_right: DoorStatus | None = None


@dataclass(frozen=True)
class WindowsStatus(ProtoMessage, schema={1: "front_left", 2: "front_right", 3: "rear_left", 4: "rear_right"}):
    front_left: WindowStatus | None = None
    front_right: WindowStatus | None = None
    rear_left: WindowStatus | None = None
    rear_right: WindowStatus | None = None


@dataclass(frozen=True)
class SunroofStatus(ProtoMessage, schema={1: "open_status"}):
    open_status: OpenStatus = OpenStatus.UNSPECIFIED


@dataclass(frozen=True)
class HoodStatus(ProtoMessage, schema={1: "status"}):
    status: DoorStatus | None = None


@dataclass(frozen=True)
class TailgateStatus(ProtoMessage, schema={1: "status"}):
    status: DoorStatus | None = None


@dataclass(frozen=True)
class TankLidStatus(ProtoMessage, schema={1: "open_status"}):
    open_status: OpenStatus = OpenStatus.UNSPECIFIED


@dataclass(frozen=True)
class ExteriorStatus(ProtoMessage, schema={
    1: "central_lock",
    2: "doors",
    3: "windows",
    4: "sunroof",
    5: "hood",
    6: "tailgate",
    7: "tank_lid",
}):
    central_lock: CentralLockStatus | None = None
    doors: DoorsStatus | None = None
    windows: WindowsStatus | None = None
    sunroof: SunroofStatus | None = None
    hood: HoodStatus | None = None
    tailgate: TailgateStatus | None = None
    tank_lid: TankLidStatus | None = None

    @property
    def is_locked(self) -> bool:
        return self.central_lock is not None and self.central_lock.lock_status == LockStatus.LOCKED

    @property
    def any_door_open(self) -> bool:
        if self.doors is None:
            return False
        for door in (self.doors.front_left, self.doors.front_right, self.doors.rear_left, self.doors.rear_right):
            if door and door.open_status == OpenStatus.OPEN:
                return True
        return False
