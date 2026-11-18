"""Exterior status — locks, doors, windows, sunroof, hood, tailgate, tank lid."""

from __future__ import annotations

from dataclasses import dataclass, replace
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

    def merge(self, previous: DoorStatus | None) -> DoorStatus:
        """Merge a partial door update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            lock_status=self.lock_status if self.lock_status != LockStatus.UNSPECIFIED else previous.lock_status,
            open_status=self.open_status if self.open_status != OpenStatus.UNSPECIFIED else previous.open_status,
            alarm_status=self.alarm_status if self.alarm_status != AlarmStatus.UNSPECIFIED else previous.alarm_status,
        )


@dataclass(frozen=True)
class WindowStatus(ProtoMessage, schema={1: "open_status"}):
    open_status: OpenStatus = OpenStatus.UNSPECIFIED

    def merge(self, previous: WindowStatus | None) -> WindowStatus:
        """Merge a partial window update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            open_status=self.open_status if self.open_status != OpenStatus.UNSPECIFIED else previous.open_status,
        )


@dataclass(frozen=True)
class CentralLockStatus(ProtoMessage, schema={1: "lock_status"}):
    lock_status: LockStatus = LockStatus.UNSPECIFIED

    def merge(self, previous: CentralLockStatus | None) -> CentralLockStatus:
        """Merge a partial central-lock update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            lock_status=self.lock_status if self.lock_status != LockStatus.UNSPECIFIED else previous.lock_status,
        )


@dataclass(frozen=True)
class DoorsStatus(ProtoMessage, schema={1: "front_left", 2: "front_right", 3: "rear_left", 4: "rear_right"}):
    front_left: DoorStatus | None = None
    front_right: DoorStatus | None = None
    rear_left: DoorStatus | None = None
    rear_right: DoorStatus | None = None

    def merge(self, previous: DoorsStatus | None) -> DoorsStatus:
        """Merge a partial doors update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            front_left=_merge_message(self.front_left, previous.front_left),
            front_right=_merge_message(self.front_right, previous.front_right),
            rear_left=_merge_message(self.rear_left, previous.rear_left),
            rear_right=_merge_message(self.rear_right, previous.rear_right),
        )


@dataclass(frozen=True)
class WindowsStatus(ProtoMessage, schema={1: "front_left", 2: "front_right", 3: "rear_left", 4: "rear_right"}):
    front_left: WindowStatus | None = None
    front_right: WindowStatus | None = None
    rear_left: WindowStatus | None = None
    rear_right: WindowStatus | None = None

    def merge(self, previous: WindowsStatus | None) -> WindowsStatus:
        """Merge a partial windows update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            front_left=_merge_message(self.front_left, previous.front_left),
            front_right=_merge_message(self.front_right, previous.front_right),
            rear_left=_merge_message(self.rear_left, previous.rear_left),
            rear_right=_merge_message(self.rear_right, previous.rear_right),
        )


@dataclass(frozen=True)
class SunroofStatus(ProtoMessage, schema={1: "open_status"}):
    open_status: OpenStatus = OpenStatus.UNSPECIFIED

    def merge(self, previous: SunroofStatus | None) -> SunroofStatus:
        """Merge a partial sunroof update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            open_status=self.open_status if self.open_status != OpenStatus.UNSPECIFIED else previous.open_status,
        )


@dataclass(frozen=True)
class HoodStatus(ProtoMessage, schema={1: "status"}):
    status: DoorStatus | None = None

    def merge(self, previous: HoodStatus | None) -> HoodStatus:
        """Merge a partial hood update with a previous snapshot."""
        if previous is None:
            return self
        return replace(self, status=_merge_message(self.status, previous.status))


@dataclass(frozen=True)
class TailgateStatus(ProtoMessage, schema={1: "status"}):
    status: DoorStatus | None = None

    def merge(self, previous: TailgateStatus | None) -> TailgateStatus:
        """Merge a partial tailgate update with a previous snapshot."""
        if previous is None:
            return self
        return replace(self, status=_merge_message(self.status, previous.status))


@dataclass(frozen=True)
class TankLidStatus(ProtoMessage, schema={1: "open_status"}):
    open_status: OpenStatus = OpenStatus.UNSPECIFIED

    def merge(self, previous: TankLidStatus | None) -> TankLidStatus:
        """Merge a partial tank-lid update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            open_status=self.open_status if self.open_status != OpenStatus.UNSPECIFIED else previous.open_status,
        )


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

    def merge(self, previous: ExteriorStatus | None) -> ExteriorStatus:
        """Merge a partial exterior update with a previous snapshot."""
        if previous is None:
            return self
        return replace(
            self,
            central_lock=_merge_message(self.central_lock, previous.central_lock),
            doors=_merge_message(self.doors, previous.doors),
            windows=_merge_message(self.windows, previous.windows),
            sunroof=_merge_message(self.sunroof, previous.sunroof),
            hood=_merge_message(self.hood, previous.hood),
            tailgate=_merge_message(self.tailgate, previous.tailgate),
            tank_lid=_merge_message(self.tank_lid, previous.tank_lid),
        )

    @property
    def has_data(self) -> bool:
        """True when the response contains at least one populated subfield."""
        return any(
            field is not None
            for field in (
                self.central_lock,
                self.doors,
                self.windows,
                self.sunroof,
                self.hood,
                self.tailgate,
                self.tank_lid,
            )
        )

    @property
    def is_locked(self) -> bool | None:
        if self.central_lock is None or self.central_lock.lock_status == LockStatus.UNSPECIFIED:
            return None
        return self.central_lock.lock_status == LockStatus.LOCKED

    @property
    def any_door_open(self) -> bool:
        if self.doors is None:
            return False
        for door in (self.doors.front_left, self.doors.front_right, self.doors.rear_left, self.doors.rear_right):
            if door and door.open_status not in {OpenStatus.UNSPECIFIED, OpenStatus.CLOSED}:
                return True
        return False


def _merge_message(current, previous):
    """Merge a possibly partial nested exterior message."""
    if current is None:
        return previous
    if previous is None:
        return current
    merge = getattr(current, "merge", None)
    if callable(merge):
        return merge(previous)
    return current
