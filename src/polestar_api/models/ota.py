"""OTA software update models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Timestamp


class SoftwareState(IntEnum):
    UNKNOWN = 0
    DOWNLOAD_READY = 1
    DOWNLOAD_STARTED = 2
    DOWNLOAD_COMPLETED = 3
    DOWNLOAD_FAILED = 4
    INSTALLATION_INITIATED = 5
    INSTALLATION_STARTED = 6
    INSTALLATION_ABORTED = 7
    INSTALLATION_FAILED = 8
    INSTALLATION_COMPLETED = 9
    INSTALLATION_DEFERRED = 10
    INSTALLATION_FAILED_CRITICAL = 11
    INSTALLATION_SCHEDULED = 12
    INSTALLATION_SCHEDULE_TRIGGERED = 13
    INSTALLATION_UNKNOWN = 14


class ScheduleStatus(IntEnum):
    UNKNOWN = 0
    IDLE = 1
    SCHEDULED = 2
    INSTALL = 3


class ScheduleSetBy(IntEnum):
    UNKNOWN = 0
    APP = 1
    HMI = 2
    CLOUD = 3


@dataclass(frozen=True)
class SoftwareDescription(ProtoMessage, schema={
    1: "name",
    2: "short_desc",
    3: "long_desc",
}):
    name: str = ""
    short_desc: str = ""
    long_desc: str = ""


@dataclass(frozen=True)
class ScheduleInfo(ProtoMessage, schema={2: "scheduled_at"}):
    scheduled_at: Timestamp | None = None


@dataclass(frozen=True)
class CarSoftwareInfo(ProtoMessage, schema={
    1: "software_id",
    2: "description",
    3: "qb_code",
    4: "state",
    6: "new_sw_version",
    8: "schedule_info",
    10: "state_timestamp",
}):
    software_id: str = ""
    description: SoftwareDescription | None = None
    qb_code: str = ""
    state: SoftwareState = SoftwareState.UNKNOWN
    new_sw_version: str = ""
    schedule_info: ScheduleInfo | None = None
    state_timestamp: Timestamp | None = None


@dataclass(frozen=True)
class Scheduler(ProtoMessage, schema={
    1: "status",
    2: "relative_time",
    3: "scheduled_time",
    4: "software_id",
    5: "set_by",
}):
    status: ScheduleStatus = ScheduleStatus.UNKNOWN
    relative_time: int = 0
    scheduled_time: Timestamp | None = None
    software_id: str = ""
    set_by: ScheduleSetBy = ScheduleSetBy.UNKNOWN
