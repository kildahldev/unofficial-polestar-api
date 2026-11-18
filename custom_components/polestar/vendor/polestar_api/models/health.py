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
    REGULAR_MAINTENANCE_OVERDUE = 9
    ENGINE_HOURS_OVERDUE = 10
    DISTANCE_DRIVEN_OVERDUE = 11


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
    CRITICALLY_LOW = 3


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


class TpmsSensorMeasurement(IntEnum):
    """How the tyre pressure monitoring system measures (direct sensors vs indirect via ABS)."""

    UNSPECIFIED = 0
    DIRECT = 1
    INDIRECT_PERCENTAGE = 2
    BASIC = 3


class TpmsStatus(IntEnum):
    UNSPECIFIED = 0
    OK = 1
    FAILURE = 2
    TEMPORARILY_UNAVAILABLE = 3
    UNAVAILABLE_DUE_TO_MISSING_CALIBRATION = 4
    UNAVAILABLE_DUE_TO_FOUR_MISSING_SENSORS = 5
    UNAVAILABLE_DUE_TO_INCOMPATIBLE_TYRES = 6
    UNAVAILABLE_DUE_TO_SOFTWARE_UPGRADE = 7


class TyrePressureValueStatus(IntEnum):
    """Validity of an individual ``*_tyre_pressure_kpa`` reading."""

    UNSPECIFIED = 0
    OK = 1
    UNVERIFIED = 2
    INVALID = 3
    NOT_AVAILABLE = 4


@dataclass(frozen=True)
class TyreStatus(ProtoMessage, schema={
    1: "front_left_value_status",
    2: "front_right_value_status",
    3: "rear_left_value_status",
    4: "rear_right_value_status",
    5: "value_status_updated_at",
    6: "sensor_measurement",
    7: "system_status",
}):
    """``Health.tyre_status`` (field 47): TPMS health and per-wheel reading validity."""

    front_left_value_status: TyrePressureValueStatus = TyrePressureValueStatus.UNSPECIFIED
    front_right_value_status: TyrePressureValueStatus = TyrePressureValueStatus.UNSPECIFIED
    rear_left_value_status: TyrePressureValueStatus = TyrePressureValueStatus.UNSPECIFIED
    rear_right_value_status: TyrePressureValueStatus = TyrePressureValueStatus.UNSPECIFIED
    value_status_updated_at: Timestamp | None = None
    sensor_measurement: TpmsSensorMeasurement = TpmsSensorMeasurement.UNSPECIFIED
    system_status: TpmsStatus = TpmsStatus.UNSPECIFIED

    @property
    def all_values_ok(self) -> bool:
        return all(
            getattr(self, f) == TyrePressureValueStatus.OK
            for f in ("front_left_value_status", "front_right_value_status", "rear_left_value_status", "rear_right_value_status")
        )


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
    # Tyre pressure warnings. Wire order is front-right, rear-right, front-left,
    # rear-left (right side first) -- verified by setting each tyre to a
    # distinct pressure and matching the raw kPa fields 39-42 below.
    9: "front_right_tyre_pressure_warning",
    10: "rear_right_tyre_pressure_warning",
    11: "front_left_tyre_pressure_warning",
    12: "rear_left_tyre_pressure_warning",
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
    # Same right-side-first wire order as the warnings above (see note there).
    39: "front_right_tyre_pressure_kpa",
    40: "rear_right_tyre_pressure_kpa",
    41: "front_left_tyre_pressure_kpa",
    42: "rear_left_tyre_pressure_kpa",
    43: "front_tyres_reference_pressure_kpa",
    44: "rear_tyres_reference_pressure_kpa",
    # TPMS status
    47: "tyre_status",
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
    # Recommended (placard) pressures for the fitted tyres
    front_tyres_reference_pressure_kpa: float = 0.0
    rear_tyres_reference_pressure_kpa: float = 0.0
    # TPMS status
    tyre_status: TyreStatus | None = None

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
