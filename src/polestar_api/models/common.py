"""Common types shared across services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum

from ..wire import ProtoMessage


@dataclass(frozen=True)
class Timestamp(ProtoMessage, schema={1: "seconds", 2: "nanos"}):
    seconds: int = 0
    nanos: int = 0

    def to_datetime(self) -> datetime | None:
        """Return the timestamp as an aware UTC datetime, or ``None`` if unset (0)."""
        if not self.seconds and not self.nanos:
            return None
        try:
            return datetime.fromtimestamp(self.seconds + self.nanos / 1e9, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None


@dataclass(frozen=True)
class TimestampShort(ProtoMessage, schema={1: "seconds"}):
    """Timestamp with uint32 seconds (max Feb 2106)."""
    seconds: int = 0


class ResponseStatusCode(IntEnum):
    UNDEFINED = 0
    SUCCESS = 1
    WARNING = 2
    ERROR = 3


class ChronosStatus(IntEnum):
    """Command delivery lifecycle (chronos.proto.messages.common.v1.Status).

    Chronos command responses (e.g. SetTargetSoc) report where the command is
    in the SENT -> DELIVERED -> SYNCED pipeline, not a simple success/error.
    The exact value seen depends on car state/timing at response time.
    """

    UNKNOWN_ERROR = 0
    SENT = 1
    DELIVERED = 2
    SUCCESS = 3
    SYNCED = 4
    CAR_OFFLINE = 5
    CAR_ERROR = 6
    ERROR = 7
    REPLACED = 8


# Lifecycle states that mean the command was accepted/applied (not an error).
CHRONOS_SUCCESS_STATES = frozenset(
    {
        ChronosStatus.SENT,
        ChronosStatus.DELIVERED,
        ChronosStatus.SUCCESS,
        ChronosStatus.SYNCED,
        ChronosStatus.REPLACED,
    }
)


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
class VehicleRequest(ProtoMessage, schema={1: "id", 2: "vin"}):
    """Generic vehicle request envelope used by most services."""
    id: str = ""
    vin: str = ""


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
    # Not part of the Location proto schema: set by the parser from the
    # LastParkedLocation wrapper (field 3). ``None`` when not reported.
    stale: bool | None = None


def _timestamp_key(timestamp: Timestamp | None) -> tuple[int, int] | None:
    if timestamp is None:
        return None
    return (timestamp.seconds, timestamp.nanos)


def select_location_update(previous: Location | None, new: Location | None) -> Location | None:
    """Decide whether a location update should be applied.

    Returns *new* if it should replace *previous*, or ``None`` if it should be
    ignored: it is older than the stored one, or carries identical position,
    timestamp and staleness (so listeners aren't notified for no change).
    """
    if new is None:
        return None
    if previous is None:
        return new
    old_ts = _timestamp_key(previous.timestamp)
    new_ts = _timestamp_key(new.timestamp)
    if old_ts is not None and new_ts is not None and new_ts < old_ts:
        return None
    if (
        new.coordinate == previous.coordinate
        and new_ts == old_ts
        and new.stale == previous.stale
    ):
        return None
    return new
