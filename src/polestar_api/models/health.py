"""Health status — service warnings, fluid levels, tyre pressure, lights, 12V battery."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Timestamp


class ServiceWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    UNKNOWN_WARNING = 2
    REGULAR_MAINTENANCE_ALMOST_TIME = 3
    ENGINE_HOURS_ALMOST_TIME = 4
    DISTANCE_DRIVEN_ALMOST_TIME = 5
    REGULAR_MAINTENANCE_TIME = 6
    ENGINE_HOURS_TIME = 7
    DISTANCE_DRIVEN_TIME = 8


class ExteriorLightWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    FAILURE = 2


class TyrePressureWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    VERY_LOW_PRESSURE = 2
    LOW_PRESSURE = 3
    HIGH_PRESSURE = 4


class BrakeFluidLevelWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    TOO_LOW = 2


class EngineCoolantLevelWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    TOO_LOW = 2


class OilLevelWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    SERVICE_REQUIRED = 2
    TOO_LOW = 3
    TOO_HIGH = 4


class WasherFluidLevelWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    TOO_LOW = 2


class LowVoltageBatteryWarning(IntEnum):
    UNSPECIFIED = 0
    NO_WARNING = 1
    TOO_LOW = 2


@dataclass(frozen=True)
class Health(ProtoMessage, schema={
    1: "timestamp",
    # Service
    2: "engine_hours_to_service",
    3: "days_to_service",
    4: "distance_to_service_km",
    5: "service_warning",
    # Fluids
    6: "brake_fluid_level_warning",
    7: "engine_coolant_level_warning",
    8: "oil_level_warning",
    13: "washer_fluid_level_warning",
    # Tyre pressure warnings
    9: "front_left_tyre_pressure_warning",
    10: "front_right_tyre_pressure_warning",
    11: "rear_left_tyre_pressure_warning",
    12: "rear_right_tyre_pressure_warning",
    # Brake lights
    14: "brake_light_left_warning",
    15: "brake_light_center_warning",
    16: "brake_light_right_warning",
    # Fog lights
    17: "fog_light_front_warning",
    18: "fog_light_rear_warning",
    # Position lights
    19: "position_light_front_left_warning",
    20: "position_light_front_right_warning",
    21: "position_light_rear_left_warning",
    22: "position_light_rear_right_warning",
    # Beams
    23: "high_beam_left_warning",
    24: "high_beam_right_warning",
    25: "low_beam_left_warning",
    26: "low_beam_right_warning",
    # Daytime running
    27: "daytime_running_light_left_warning",
    28: "daytime_running_light_right_warning",
    # Turn indicators
    30: "turn_indication_front_left_warning",
    31: "turn_indication_front_right_warning",
    32: "turn_indication_rear_left_warning",
    33: "turn_indication_rear_right_warning",
    # Other lights
    34: "registration_plate_light_warning",
    35: "side_mark_lights_warning",
    # 12V battery
    38: "low_voltage_battery_warning",
    # Tyre pressure values (kPa)
    39: "front_left_tyre_pressure_kpa",
    40: "front_right_tyre_pressure_kpa",
    41: "rear_left_tyre_pressure_kpa",
    42: "rear_right_tyre_pressure_kpa",
}):
    timestamp: Timestamp | None = None
    # Service
    engine_hours_to_service: int = 0
    days_to_service: int = 0
    distance_to_service_km: int = 0
    service_warning: ServiceWarning = ServiceWarning.UNSPECIFIED
    # Fluids
    brake_fluid_level_warning: BrakeFluidLevelWarning = BrakeFluidLevelWarning.UNSPECIFIED
    engine_coolant_level_warning: EngineCoolantLevelWarning = EngineCoolantLevelWarning.UNSPECIFIED
    oil_level_warning: OilLevelWarning = OilLevelWarning.UNSPECIFIED
    washer_fluid_level_warning: WasherFluidLevelWarning = WasherFluidLevelWarning.UNSPECIFIED
    # Tyre pressure warnings
    front_left_tyre_pressure_warning: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    front_right_tyre_pressure_warning: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    rear_left_tyre_pressure_warning: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    rear_right_tyre_pressure_warning: TyrePressureWarning = TyrePressureWarning.UNSPECIFIED
    # Brake lights
    brake_light_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    brake_light_center_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    brake_light_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # Fog lights
    fog_light_front_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    fog_light_rear_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # Position lights
    position_light_front_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    position_light_front_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    position_light_rear_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    position_light_rear_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # Beams
    high_beam_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    high_beam_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    low_beam_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    low_beam_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # Daytime running
    daytime_running_light_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    daytime_running_light_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # Turn indicators
    turn_indication_front_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    turn_indication_front_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    turn_indication_rear_left_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    turn_indication_rear_right_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # Other lights
    registration_plate_light_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    side_mark_lights_warning: ExteriorLightWarning = ExteriorLightWarning.UNSPECIFIED
    # 12V battery
    low_voltage_battery_warning: LowVoltageBatteryWarning = LowVoltageBatteryWarning.UNSPECIFIED
    # Tyre pressure values (kPa)
    front_left_tyre_pressure_kpa: float = 0.0
    front_right_tyre_pressure_kpa: float = 0.0
    rear_left_tyre_pressure_kpa: float = 0.0
    rear_right_tyre_pressure_kpa: float = 0.0

    @property
    def any_light_failure(self) -> bool:
        for name in self._schema.values():
            if name.endswith("_warning") and ("light" in name or "beam" in name or "running" in name or "turn" in name):
                if getattr(self, name) == ExteriorLightWarning.FAILURE:
                    return True
        return False

    @property
    def any_tyre_warning(self) -> bool:
        return any(
            getattr(self, f) != TyrePressureWarning.UNSPECIFIED
            and getattr(self, f) != TyrePressureWarning.NO_WARNING
            for f in (
                "front_left_tyre_pressure_warning",
                "front_right_tyre_pressure_warning",
                "rear_left_tyre_pressure_warning",
                "rear_right_tyre_pressure_warning",
            )
        )
