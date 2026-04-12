"""Odometer — simple odometer reading from the odometer service."""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import ProtoMessage
from .common import Timestamp


@dataclass(frozen=True)
class OdometerStatus(ProtoMessage, schema={
    1: "timestamp",
    2: "odometer_meters",
    3: "trip_meter_manual_km",
    4: "trip_meter_automatic_km",
}):
    """Odometer and trip meter readings from the DT odometer service.

    Field 2 is odometer in **meters** (per Odometer.ODOMETER_METERS_FIELD_NUMBER).
    """

    timestamp: Timestamp | None = None
    odometer_meters: int = 0
    trip_meter_manual_km: float = 0.0
    trip_meter_automatic_km: float = 0.0

    @property
    def odometer_km(self) -> float:
        return self.odometer_meters / 1000.0
