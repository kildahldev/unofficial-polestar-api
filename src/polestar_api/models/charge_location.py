"""Charge location models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from .common import Weekday


class ChargeLocationType(IntEnum):
    UNSPECIFIED = 0
    RECENT = 1
    SAVED = 2
    SAVED_3RD_PARTY = 3


class OptimisedChargingType(IntEnum):
    UNAVAILABLE = 0
    INTELLIGENT_TIMER = 1
    PRICED_OPTIMIZED = 2


@dataclass(frozen=True)
class ChargeLocationTimer:
    """A charge timer associated with a specific charge location."""
    id: str = ""
    activated: bool = False
    start_hour: int = 0
    start_minute: int = 0
    stop_hour: int = 0
    stop_minute: int = 0
    active_days: tuple[Weekday, ...] = ()


@dataclass(frozen=True)
class ChargeLocationDepartureTime:
    """A departure time associated with a specific charge location."""
    id: str = ""
    activated: bool = False
    hour: int = 0
    minute: int = 0
    active_days: tuple[Weekday, ...] = ()


@dataclass(frozen=True)
class ChargeLocation:
    """A saved charge location with per-location charging settings."""
    location_id: str = ""
    location_alias: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    amp_limit: int = 0
    minimum_soc: int = 0
    is_optimised_charging_enabled: bool = False
    is_bidirectional_charging_enabled: bool = False
    available_optimised_charging: OptimisedChargingType = OptimisedChargingType.UNAVAILABLE
    location_type: ChargeLocationType = ChargeLocationType.UNSPECIFIED
    charge_timers: tuple[ChargeLocationTimer, ...] = ()
    departure_times: tuple[ChargeLocationDepartureTime, ...] = ()
