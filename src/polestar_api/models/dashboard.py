"""Dashboard — odometer, trip meters, tire pressure, warnings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage


class TyrePressureWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    SOFT_WARNING = 2
    HARD_WARNING = 3


class ServiceWarningTrigger(IntEnum):
    UNSPECIFIED = 0
    NO_REMINDER = 1
    BOOK_TIME = 4
    BOOK_ENGINE_TIME = 5
    BOOK_DISTANCE = 6
    REGULAR_MAINT_TIME = 8
    REGULAR_MAINT_ENGINE_TIME = 9
    REGULAR_MAINT_DISTANCE = 10
    OVERDUE_TIME = 12
    OVERDUE_ENGINE_TIME = 13
    OVERDUE_DISTANCE = 14


class BulbStatus(IntEnum):
    UNSPECIFIED = 0
    NO_FAULT = 1
    FAULT = 2


class FluidLevel(IntEnum):
    UNSPECIFIED = 0
    HIGH = 1
    LOW = 2


@dataclass(frozen=True)
class CarDashboardData(ProtoMessage, schema={
    5: "distance_to_empty",
    9: "engine_hours_to_service",
    11: "avg_speed_manual",
    14: "distance_to_service",
    15: "avg_fuel_consumption_manual",
    16: "fuel_amount_litres",
    17: "odometer_km",
    18: "trip_meter_manual_km",
    19: "trip_meter_auto_km",
    20: "avg_speed_auto",
    21: "avg_fuel_consumption_auto",
}):
    distance_to_empty: int = 0
    engine_hours_to_service: int = 0
    avg_speed_manual: int = 0
    distance_to_service: int = 0
    avg_fuel_consumption_manual: float = 0.0
    fuel_amount_litres: float = 0.0
    odometer_km: float = 0.0
    trip_meter_manual_km: float = 0.0
    trip_meter_auto_km: float = 0.0
    avg_speed_auto: int = 0
    avg_fuel_consumption_auto: float = 0.0


@dataclass(frozen=True)
class CarWarningsData(ProtoMessage, schema={
    1: "brake_fluid",
    2: "engine_coolant",
    6: "tyre_rear_right",
    7: "tyre_rear_left",
    8: "tyre_front_left",
    9: "tyre_front_right",
    10: "service_warning_trigger",
}):
    brake_fluid: FluidLevel = FluidLevel.UNSPECIFIED
    engine_coolant: FluidLevel = FluidLevel.UNSPECIFIED
    tyre_rear_right: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    tyre_rear_left: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    tyre_front_left: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    tyre_front_right: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    service_warning_trigger: ServiceWarningTrigger = ServiceWarningTrigger.UNSPECIFIED


@dataclass(frozen=True)
class DashboardStatus(ProtoMessage, schema={1: "dashboard_data", 2: "warnings_data"}):
    dashboard_data: CarDashboardData | None = None
    warnings_data: CarWarningsData | None = None
