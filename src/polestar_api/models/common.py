"""Common types shared across services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage


@dataclass(frozen=True)
class Timestamp(ProtoMessage, schema={1: "seconds", 2: "nanos"}):
    seconds: int = 0
    nanos: int = 0


@dataclass(frozen=True)
class TimestampShort(ProtoMessage, schema={1: "seconds"}):
    """Timestamp with uint32 seconds (max Feb 2106)."""
    seconds: int = 0


class ResponseStatusCode(IntEnum):
    UNDEFINED = 0
    SUCCESS = 1
    WARNING = 2
    ERROR = 3


@dataclass(frozen=True)
class ResponseStatusDetail(ProtoMessage, schema={1: "name", 2: "value"}):
    name: str = ""
    value: str = ""


@dataclass(frozen=True)
class ResponseStatus(ProtoMessage, schema={1: "status", 2: "status_code"}):
    status: ResponseStatusCode = ResponseStatusCode.UNDEFINED
    status_code: int = 0


@dataclass(frozen=True)
class Coordinate(ProtoMessage, schema={1: "longitude", 2: "latitude"}):
    longitude: float = 0.0
    latitude: float = 0.0


class Weekday(IntEnum):
    UNSPECIFIED = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


@dataclass(frozen=True)
class DailyTime(ProtoMessage, schema={1: "hour", 2: "minute"}):
    hour: int = 0
    minute: int = 0


@dataclass(frozen=True)
class Location(ProtoMessage, schema={
    1: "timestamp",
    2: "coordinate",
    3: "altitude",
    4: "heading",
    5: "speed",
}):
    timestamp: Timestamp | None = None
    coordinate: Coordinate | None = None
    altitude: int = 0
    heading: int = 0
    speed: int = 0
