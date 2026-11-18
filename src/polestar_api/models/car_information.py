"""Car information — model name, model year, market and registration from the MyCars service."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Annotated

from ..wire import Float32, ProtoMessage


class EngineType(IntEnum):
    """C3 EngineType (what the car is powered by)."""
    UNSPECIFIED = 0
    ELECTRIC = 1
    DIESEL = 2
    PETROL = 3
    PETROL_HYBRID = 4
    DIESEL_HYBRID = 5


class DrivetrainType(IntEnum):
    UNSPECIFIED = 0
    AWD = 1
    RWD = 2
    FWD = 3


class RemoteHonkFlashType(IntEnum):
    """What the car can do with the horn and lights from the app."""
    UNSPECIFIED = 0
    NONE = 1
    HONK_AND_FLASH = 2
    HONK_AND_OR_FLASH = 3
    FLASH = 4
    HONK = 5

    @property
    def can_honk(self) -> bool | None:
        """True or False when the car says; None when it does not say."""
        if self is RemoteHonkFlashType.UNSPECIFIED:
            return None
        return self in (self.HONK_AND_FLASH, self.HONK_AND_OR_FLASH, self.HONK)

    @property
    def can_flash(self) -> bool | None:
        if self is RemoteHonkFlashType.UNSPECIFIED:
            return None
        return self in (self.HONK_AND_FLASH, self.HONK_AND_OR_FLASH, self.FLASH)

    @property
    def can_honk_and_flash(self) -> bool | None:
        if self is RemoteHonkFlashType.UNSPECIFIED:
            return None
        return self in (self.HONK_AND_FLASH, self.HONK_AND_OR_FLASH)


class RemoteLockType(IntEnum):
    """The strongest remote lock the car offers."""
    UNSPECIFIED = 0
    NONE = 1
    LOCK = 2
    LOCK_REDUCED_GUARD = 3


class DigitalKeyType(IntEnum):
    UNSPECIFIED = 0
    NONE = 1
    POLESTAR_1 = 2
    POLESTAR_2 = 3
    CCC = 4


@dataclass(frozen=True)
class Propulsion(ProtoMessage, schema={
    1: "drivetrain_type",
    4: "fuel_tank_volume",
    5: "battery_capacity_kwh",
    6: "engine_type",
}):
    """Powertrain of the car. A car with no fuel tank volume has no tank."""

    drivetrain_type: DrivetrainType = DrivetrainType.UNSPECIFIED
    fuel_tank_volume: int = 0
    battery_capacity_kwh: Annotated[float, Float32] = 0.0
    engine_type: EngineType = EngineType.UNSPECIFIED


@dataclass(frozen=True)
class DigitalKey(ProtoMessage, schema={1: "type"}):
    type: DigitalKeyType = DigitalKeyType.UNSPECIFIED


@dataclass(frozen=True)
class TargetChargeLevelSettings(ProtoMessage, schema={3: "supports_target_charge_level_presets"}):
    """Whether the app offers the daily / long drive target charge level presets."""

    supports_target_charge_level_presets: bool = False


@dataclass(frozen=True)
class ChargingCapabilities(ProtoMessage, schema={
    8: "target_charge_level_settings",
    16: "max_number_of_locations",
}):
    """What the car supports for charging.

    A car that returns no location limit, or 0, has no saved charge locations (Polestar
    answers those requests with "Validation failed").
    """

    target_charge_level_settings: TargetChargeLevelSettings | None = None
    max_number_of_locations: int = 0


@dataclass(frozen=True)
class ParkingClimatizationTimers(ProtoMessage, schema={7: "max_number"}):
    max_number: int = 0


@dataclass(frozen=True)
class ParkingClimatizationCapabilities(ProtoMessage, schema={
    9: "supports_rear_seats_settings",
    13: "timers",
}):
    """What the car supports for parking climate: rear seat heating and how many timers."""

    supports_rear_seats_settings: bool = False
    timers: ParkingClimatizationTimers | None = None


@dataclass(frozen=True)
class LocksCapabilities(ProtoMessage, schema={
    1: "lock_type",
    5: "supports_window_control",
    6: "supports_sunroof_control",
    7: "supports_trunk_control",
    8: "reports_key_fob_battery_level",
    9: "remote_lock_unlock_requires_wakeup",
    10: "supports_trunk_unlock",
}):
    """What the car supports for locks, windows and roof. A feature the car does not send is not supported."""

    lock_type: RemoteLockType = RemoteLockType.UNSPECIFIED
    supports_window_control: bool = False
    supports_sunroof_control: bool = False
    supports_trunk_control: bool = False
    reports_key_fob_battery_level: bool = False
    remote_lock_unlock_requires_wakeup: bool = False
    supports_trunk_unlock: bool = False

    @property
    def supports_reduced_alarm_lock(self) -> bool | None:
        """True or False when the car says which lock it offers; None when it does not say."""
        if self.lock_type is RemoteLockType.UNSPECIFIED:
            return None
        return self.lock_type is RemoteLockType.LOCK_REDUCED_GUARD


@dataclass(frozen=True)
class AirPurificationCapabilities(ProtoMessage, schema={
    1: "supports_remote_start",
    2: "supports_internal_measurement",
    3: "supports_external_measurement",
}):
    """What the car can do for air purification. Cars without the feature (a Polestar 2 without the
    Plus pack) do not send this message at all."""

    supports_remote_start: bool = False
    supports_internal_measurement: bool = False
    supports_external_measurement: bool = False

    @property
    def any_supported(self) -> bool:
        return self.supports_remote_start or self.supports_internal_measurement or self.supports_external_measurement


@dataclass(frozen=True)
class CarDetails(ProtoMessage, schema={
    1: "vin",
    5: "vehicle_type_code",
    6: "vehicle_type_name",
    7: "model_year",
    9: "consumer_software_version",
    10: "market",
    16: "honk_flash_type",
    20: "reports_avg_electric_consumption",
    23: "reports_tyre_pressure_warning",
    26: "supports_driving_journal",
    27: "supports_engine_start",
    29: "supports_stolen_vehicle_tracking",
    32: "supports_update_status",
    33: "supports_remote_ota_install_schedule",
    57: "supports_full_ota_updates",
    73: "reports_light_warnings",
    34: "air_purification",
    35: "charging",
    36: "locks",
    37: "parking_climatization",
    39: "digital_key",
    40: "propulsion",
    43: "num_doors",
    70: "has_performance_software_upgrade",
    48: "reports_avg_electric_consumption_last_trip",
    49: "reports_avg_electric_consumption_last_charge",
    50: "reports_tyre_pressure_in_kpa",
    87: "reports_service_warning",
}):
    """Identity of a car. ``vehicle_type_name`` is the model name, e.g. ``Polestar 4``."""

    vin: str = ""
    vehicle_type_code: str = ""
    vehicle_type_name: str = ""
    model_year: str = ""
    consumer_software_version: str = ""
    market: str = ""
    reports_avg_electric_consumption: bool = False
    reports_avg_electric_consumption_last_trip: bool = False
    reports_avg_electric_consumption_last_charge: bool = False
    air_purification: AirPurificationCapabilities | None = None
    charging: ChargingCapabilities | None = None
    locks: LocksCapabilities | None = None
    parking_climatization: ParkingClimatizationCapabilities | None = None
    supports_engine_start: bool = False
    digital_key: DigitalKey | None = None
    propulsion: Propulsion | None = None
    num_doors: int = 0
    has_performance_software_upgrade: bool = False
    reports_tyre_pressure_warning: bool = False
    reports_tyre_pressure_in_kpa: bool = False
    reports_service_warning: bool = False
    honk_flash_type: RemoteHonkFlashType = RemoteHonkFlashType.UNSPECIFIED
    supports_driving_journal: bool = False
    supports_stolen_vehicle_tracking: bool = False
    supports_update_status: bool = False
    supports_remote_ota_install_schedule: bool = False
    supports_full_ota_updates: bool = False
    # The light types the car can warn about, packed as C3 enum numbers. Only "is it empty" matters here.
    reports_light_warnings: bytes = b""


@dataclass(frozen=True)
class MyCar(ProtoMessage, schema={
    1: "car",
    2: "user_is_linked",
    3: "user_is_owner",
    4: "registration_plate",
}):
    """One car on the account, as returned by ``car_information.CarInformation/GetMyCars``."""

    car: CarDetails | None = None
    user_is_linked: bool = False
    user_is_owner: bool = False
    registration_plate: str = ""
