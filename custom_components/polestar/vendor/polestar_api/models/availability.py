"""Availability status — is the car reachable."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Timestamp


class AvailabilityStatus(IntEnum):
    UNSPECIFIED = 0
    AVAILABLE = 1
    UNAVAILABLE = 2


class UnavailableReason(IntEnum):
    UNSPECIFIED = 0
    NO_INTERNET = 1
    POWER_SAVING_MODE = 2
    CAR_IN_USE = 3
    OTA_INSTALLATION_IN_PROGRESS = 4
    STOLEN_VEHICLE_TRACKING_IN_PROGRESS = 5
    SERVICE_MODE_ACTIVE = 6


class UsageMode(IntEnum):
    UNSPECIFIED = 0
    ABANDONED = 1
    INACTIVE = 2
    CONVENIENCE = 3
    ACTIVE = 4
    DRIVING = 5
    ENGINE_ON = 6
    ENGINE_OFF = 7


@dataclass(frozen=True)
class Availability(ProtoMessage, schema={
    1: "timestamp",
    3: "availability_status",
    4: "unavailable_reason",
    5: "usage_mode",
}):
    timestamp: Timestamp | None = None
    availability_status: AvailabilityStatus = AvailabilityStatus.UNSPECIFIED
    unavailable_reason: UnavailableReason = UnavailableReason.UNSPECIFIED
    usage_mode: UsageMode = UsageMode.UNSPECIFIED

    @property
    def is_available(self) -> bool:
        return self.availability_status == AvailabilityStatus.AVAILABLE
