"""Parking climate timer models (chronos service)."""

from __future__ import annotations

from dataclasses import dataclass

from .common import Weekday


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
