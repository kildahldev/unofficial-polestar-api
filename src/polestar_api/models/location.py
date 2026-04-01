"""Location request/response models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Location, ResponseStatus


class LocationType(IntEnum):
    UNDEFINED = 0
    NORMAL = 1
    EXTENDED = 2


class TripStatus(IntEnum):
    UNKNOWN = 0
    END_OF_TRIP = 1
    START_OF_TRIP = 2


@dataclass(frozen=True)
class LocationRequest(ProtoMessage, schema={1: "type"}):
    type: LocationType = LocationType.NORMAL


@dataclass(frozen=True)
class LocationResponse(ProtoMessage, schema={1: "response_status", 2: "location"}):
    response_status: ResponseStatus | None = None
    location: Location | None = None


@dataclass(frozen=True)
class LocationStatusUpdate(ProtoMessage, schema={1: "location", 2: "trip_status"}):
    location: Location | None = None
    trip_status: TripStatus = TripStatus.UNKNOWN
