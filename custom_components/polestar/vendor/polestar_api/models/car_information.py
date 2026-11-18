"""Car information — model name, model year, market and registration from the MyCars service."""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import ProtoMessage


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
class LocksCapabilities(ProtoMessage, schema={5: "supports_window_control", 6: "supports_sunroof_control"}):
    """What the car supports for locks, windows and roof. A feature the car does not send is not supported."""

    supports_window_control: bool = False
    supports_sunroof_control: bool = False


@dataclass(frozen=True)
class CarDetails(ProtoMessage, schema={
    1: "vin",
    5: "vehicle_type_code",
    6: "vehicle_type_name",
    7: "model_year",
    9: "consumer_software_version",
    10: "market",
    20: "reports_avg_electric_consumption",
    35: "charging",
    36: "locks",
    37: "parking_climatization",
    48: "reports_avg_electric_consumption_last_trip",
    49: "reports_avg_electric_consumption_last_charge",
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
    charging: ChargingCapabilities | None = None
    locks: LocksCapabilities | None = None
    parking_climatization: ParkingClimatizationCapabilities | None = None


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
