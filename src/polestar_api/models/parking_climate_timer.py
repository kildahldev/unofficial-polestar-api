"""Parking climate timer models (chronos service)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .common import Weekday
from .climatization import HeatingIntensity


class BatteryPreconditioning(IntEnum):
    UNDEFINED = 0
    OFF = 1
    WHEN_PLUGGED = 2
    ON = 3


@dataclass(frozen=True)
class SeatHeatingSettings:
    """Per-seat heating intensity for timer defaults."""
    front_left: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    front_right: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_left: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    rear_right: HeatingIntensity = HeatingIntensity.UNSPECIFIED


@dataclass(frozen=True)
class ParkingClimateTimerSettings:
    """Default climate settings applied when a parking climate timer fires."""
    seat_heating: SeatHeatingSettings = SeatHeatingSettings()
    steering_wheel_heating: HeatingIntensity = HeatingIntensity.UNSPECIFIED
    temperature_celsius: float = 0.0
    is_temperature_requested: bool = False
    battery_preconditioning: BatteryPreconditioning = BatteryPreconditioning.UNDEFINED


@dataclass(frozen=True)
class ParkingClimateTimer:
    """A scheduled parking climate timer."""
    timer_id: str = ""
    index: int = 0
    ready_at_hour: int = 0
    ready_at_minute: int = 0
    activated: bool = False
    repeat: bool = False
    weekdays: tuple[Weekday, ...] = ()
