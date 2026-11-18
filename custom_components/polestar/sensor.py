"""Sensor platform for Polestar integration."""

from __future__ import annotations

import time

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    MATCH_ALL,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from polestar_api.models.availability import UnavailableReason, UsageMode
from polestar_api.models.battery import (
    ChargerConnectionStatus,
    ChargerPowerStatus,
    ChargingStatus,
    ChargingType,
)
from polestar_api.models.climate import (
    ClimatizationRequestType,
    ClimatizationRunningStatus,
    HeatOrCoolAction,
)
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.models.health import (
    BrakeFluidLevelWarning,
    LowVoltageBatteryWarning,
    ServiceWarning,
    WasherFluidLevelWarning,
)
from polestar_api.models.ota import SoftwareState
from polestar_api.models.precleaning import PreCleaningErrorType, PreCleaningStartReason

from .const import CONF_REGISTRATION_PLATE, DOMAIN
from .coordinator import PolestarVehicleData
from .entity import PolestarEntity, async_filter_supported_entities
from . import geocode
from .utils import (
    connection_text,
    last_seen,
    flatten_attributes,
    weather_attributes,
    climate_end_time,
    climate_minutes_remaining,
    enum_name,
    enum_options,
    serialize_charge_location,
)

PARALLEL_UPDATES = 0


def _safe(fn: Callable[[PolestarVehicleData], Any], data: PolestarVehicleData) -> Any:
    try:
        return fn(data)
    except (AttributeError, TypeError, ValueError):
        return None


def _heating_intensity_name(value: HeatingIntensity | None) -> str | None:
    if value is None:
        return None
    if value in (HeatingIntensity.UNSPECIFIED, HeatingIntensity.OFF):
        return "off"
    return value.name.lower()


def _location_reports_motion(data: PolestarVehicleData) -> bool:
    location = data.location
    return location is None or any((location.heading, location.speed, location.altitude))


def _timestamp_or_none(seconds: float | None):
    return dt_util.utc_from_timestamp(seconds) if seconds is not None else None


# Usable capacity, kWh. The API never reports this, so approximate per model
# (matched against Vehicle.model_name, e.g. "Polestar 4") and fall back to the
# Polestar 4 figure, the only model exercised against this repo's live tests.
BATTERY_CAPACITY_KWH_BY_MODEL: dict[str, float] = {
    "polestar 2": 79.0,
    "polestar 3": 105.0,
    "polestar 4": 94.0,
}
DEFAULT_BATTERY_CAPACITY_KWH = 94.0

def _battery_capacity_kwh(model_name: str | None) -> float:
    if model_name:
        name = model_name.casefold()
        for key, capacity in BATTERY_CAPACITY_KWH_BY_MODEL.items():
            if key in name:
                return capacity
    return DEFAULT_BATTERY_CAPACITY_KWH


def _vehicle_capacity_kwh(vehicle) -> float:
    """The car's own battery capacity from C3 when it reports one, else the per-model table."""
    reported = getattr(vehicle, "battery_capacity_kwh", None)
    return reported if reported else _battery_capacity_kwh(vehicle.model_name)


def _build_week(structure_week: str | None) -> str | None:
    """``202611`` -> ``2026-W11`` (the production structure week); anything else is returned as is."""
    if structure_week and len(structure_week) == 6 and structure_week.isdigit():
        return f"{structure_week[:4]}-W{structure_week[4:]}"
    return structure_week


def _current_charge_location_state(data: PolestarVehicleData) -> str | None:
    location_id = (data.current_charge_location or {}).get("location_id")
    if not location_id:
        return None
    for location in data.charge_locations or ():
        if location.location_id == location_id:
            return location.location_alias or location.location_id
    return location_id


def _current_charge_location_attrs(data: PolestarVehicleData) -> dict[str, Any]:
    current = data.current_charge_location or {}
    location_id = current.get("location_id")
    if not location_id:
        return {}
    attrs: dict[str, Any] = {
        "location_id": location_id,
        "arrived_at": current.get("arrived_at"),
    }
    for location in data.charge_locations or ():
        if location.location_id == location_id:
            attrs.update(serialize_charge_location(location))
            break
    return attrs


@dataclass(frozen=True, kw_only=True)
class PolestarSensorDescription(SensorEntityDescription):
    """Sensor entity description with value extractor."""

    value_fn: Callable[[PolestarVehicleData], StateType | None]
    attrs_fn: Callable[[PolestarVehicleData], dict[str, Any]] | None = None
    fetch_attr: str | None = None
    required_data: Callable[[PolestarVehicleData], bool] | None = None
    requires_combustion_engine: bool = False


SENSORS: tuple[PolestarSensorDescription, ...] = (
    PolestarSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.battery.charge_level if d.battery else None,
    ),
    PolestarSensorDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: d.battery.range_km if d.battery else None,
    ),
    PolestarSensorDescription(
        key="target_soc",
        translation_key="target_soc",
        icon="mdi:battery-charging-high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.target_soc.target_level if d.target_soc else None,
        attrs_fn=lambda d: {"mode": enum_name(d.target_soc.setting_type)} if d.target_soc else {},
    ),
    PolestarSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.battery.power_watts if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_current",
        translation_key="charging_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda d: d.battery.current_amps if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_voltage",
        translation_key="charging_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda d: d.battery.voltage_volts if d.battery else None,
    ),
    PolestarSensorDescription(
        key="time_to_full",
        translation_key="time_to_full",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: d.battery.time_to_full if d.battery else None,
    ),
    PolestarSensorDescription(
        key="time_to_target",
        translation_key="time_to_target",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery.time_to_target if d.battery else None,
    ),
    PolestarSensorDescription(
        key="time_to_min_soc",
        translation_key="time_to_min_soc",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery.time_to_min_soc if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_status",
        icon="mdi:power-plug-battery",
        translation_key="charging_status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargingStatus),
        value_fn=lambda d: enum_name(d.battery.charging_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charger_connection",
        icon="mdi:ev-plug-type2",
        translation_key="charger_connection",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargerConnectionStatus),
        value_fn=lambda d: enum_name(d.battery.charger_connection_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_type",
        translation_key="charging_type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(ChargingType),
        value_fn=lambda d: enum_name(d.battery.charging_type) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charger_power_status",
        translation_key="charger_power_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(ChargerPowerStatus),
        value_fn=lambda d: enum_name(d.battery.charger_power_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption",
        fetch_attr="avg_consumption",
        translation_key="avg_consumption",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption_auto",
        fetch_attr="avg_consumption_auto",
        translation_key="avg_consumption_auto",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption_auto if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption_since_charge",
        fetch_attr="avg_consumption_since_charge",
        translation_key="avg_consumption_since_charge",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption_since_charge if d.battery else None,
    ),
    PolestarSensorDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: d.odometer.odometer_km if d.odometer else None,
    ),
    PolestarSensorDescription(
        key="trip_meter_manual",
        translation_key="trip_meter_manual",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: (d.dashboard.dashboard_data.trip_meter_manual_km if d.dashboard and d.dashboard.dashboard_data else None) or (d.odometer.trip_meter_manual_km if d.odometer and d.odometer.trip_meter_manual_km else None),
    ),
    PolestarSensorDescription(
        key="trip_meter_auto",
        translation_key="trip_meter_auto",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: (d.dashboard.dashboard_data.trip_meter_auto_km if d.dashboard and d.dashboard.dashboard_data else None) or (d.odometer.trip_meter_automatic_km if d.odometer and d.odometer.trip_meter_automatic_km is not None else None),
    ),
    PolestarSensorDescription(
        key="heading",
        # The C3 location service sends only a position, so these stay 0 on it.
        required_data=_location_reports_motion,
        translation_key="heading",
        native_unit_of_measurement="°",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.heading if d.location else None,
    ),
    PolestarSensorDescription(
        key="speed",
        # The C3 location service sends only a position, so these stay 0 on it.
        required_data=_location_reports_motion,
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.speed if d.location else None,
    ),
    PolestarSensorDescription(
        key="altitude",
        # The C3 location service sends only a position, so these stay 0 on it.
        required_data=_location_reports_motion,
        translation_key="altitude",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.altitude if d.location else None,
    ),
    PolestarSensorDescription(
        key="distance_to_service",
        translation_key="distance_to_service",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:wrench-clock",
        value_fn=lambda d: d.health.distance_to_service_km if d.health else None,
    ),
    PolestarSensorDescription(
        key="days_to_service",
        translation_key="days_to_service",
        native_unit_of_measurement="d",
        icon="mdi:wrench-clock",
        value_fn=lambda d: d.health.days_to_service if d.health else None,
    ),
    PolestarSensorDescription(
        key="engine_hours_to_service",
        translation_key="engine_hours_to_service",
        requires_combustion_engine=True,
        native_unit_of_measurement="h",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:engine",
        value_fn=lambda d: d.health.engine_hours_to_service if d.health else None,
    ),
    PolestarSensorDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.weather.temperature_celsius if d.weather else None,
        attrs_fn=lambda d: weather_attributes(d.weather),
    ),
    PolestarSensorDescription(
        key="fl_tyre_pressure",
        fetch_attr="tyre_pressure",
        icon="mdi:tire",
        translation_key="fl_tyre_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda d: d.health.front_left_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="fr_tyre_pressure",
        fetch_attr="tyre_pressure",
        icon="mdi:tire",
        translation_key="fr_tyre_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda d: d.health.front_right_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="rl_tyre_pressure",
        fetch_attr="tyre_pressure",
        icon="mdi:tire",
        translation_key="rl_tyre_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda d: d.health.rear_left_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="rr_tyre_pressure",
        fetch_attr="tyre_pressure",
        icon="mdi:tire",
        translation_key="rr_tyre_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        suggested_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda d: d.health.rear_right_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="air_quality_index",
        fetch_attr="precleaning",
        translation_key="air_quality_index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precleaning.measured_air_quality_index if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="pm25",
        fetch_attr="precleaning",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="µg/m³",
        value_fn=lambda d: d.precleaning.measured_particulate_matter_2_5 if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_runtime_left",
        fetch_attr="precleaning",
        translation_key="precleaning_runtime_left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.precleaning.runtime_left_minutes if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_start_reason",
        fetch_attr="precleaning",
        translation_key="precleaning_start_reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(PreCleaningStartReason),
        value_fn=lambda d: enum_name(d.precleaning.start_reason) if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_error",
        fetch_attr="precleaning",
        translation_key="precleaning_error",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(PreCleaningErrorType),
        value_fn=lambda d: enum_name(d.precleaning.error) if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="software_version",
        translation_key="software_version",
        icon="mdi:update",
        value_fn=lambda d: d.software.new_sw_version if d.software else None,
    ),
    PolestarSensorDescription(
        key="software_state",
        translation_key="software_state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(SoftwareState, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.software.state, allow_unspecified=True) if d.software else None,
    ),
    PolestarSensorDescription(
        key="climate_running_status",
        icon="mdi:air-conditioner",
        translation_key="climate_running_status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ClimatizationRunningStatus, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.climate.running_status, allow_unspecified=True) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_request_type",
        translation_key="climate_request_type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(ClimatizationRequestType, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.climate.request_type, allow_unspecified=True) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_time_remaining",
        translation_key="climate_time_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: climate_minutes_remaining(d.climate, dt_util.utcnow().timestamp()),
    ),
    PolestarSensorDescription(
        key="climate_ends_at",
        translation_key="climate_ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _timestamp_or_none(climate_end_time(d.climate)),
    ),
    PolestarSensorDescription(
        key="climate_current_temperature",
        translation_key="climate_current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.climate.current_temperature_celsius if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_target_temperature",
        translation_key="climate_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.climate.target_temperature_celsius if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_front_left_seat",
        translation_key="climate_front_left_seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.front_left_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_front_right_seat",
        translation_key="climate_front_right_seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.front_right_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_rear_left_seat",
        fetch_attr="rear_seat_heating",
        translation_key="climate_rear_left_seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.rear_left_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_rear_right_seat",
        fetch_attr="rear_seat_heating",
        translation_key="climate_rear_right_seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.rear_right_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_steering_wheel",
        translation_key="climate_steering_wheel",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:steering",
        value_fn=lambda d: _heating_intensity_name(d.climate.steering_wheel) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="connection",
        translation_key="connection",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car-connected",
        value_fn=lambda d: connection_text(d, lambda moment: dt_util.as_local(moment).strftime("%H:%M"))[:255],
    ),
    PolestarSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:car-wireless",
        value_fn=last_seen,
    ),
    PolestarSensorDescription(
        key="availability_unavailable_reason",
        translation_key="availability_unavailable_reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(UnavailableReason),
        value_fn=lambda d: enum_name(d.availability.unavailable_reason) if d.availability else None,
    ),
    PolestarSensorDescription(
        key="availability_usage_mode",
        translation_key="availability_usage_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(UsageMode),
        value_fn=lambda d: enum_name(d.availability.usage_mode) if d.availability else None,
    ),
    PolestarSensorDescription(
        key="charge_locations",
        fetch_attr="charge_locations",
        translation_key="charge_locations",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.charge_locations) if d.charge_locations is not None else None,
        attrs_fn=lambda d: {"locations": [serialize_charge_location(location) for location in d.charge_locations or ()]},
    ),
    PolestarSensorDescription(
        key="current_charge_location",
        fetch_attr="current_charge_location",
        translation_key="current_charge_location",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_current_charge_location_state,
        attrs_fn=_current_charge_location_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    for coordinator in data["coordinators"].values():
        entities = [PolestarSensor(coordinator, desc) for desc in SENSORS]
        async_add_entities(async_filter_supported_entities(hass, coordinator, "sensor", entities))
        info_entities: list[SensorEntity] = [PolestarVinSensor(coordinator), PolestarVehicleInfoSensor(coordinator)]
        vehicle = coordinator.vehicle
        if getattr(vehicle, "battery_capacity_kwh", None):
            info_entities.append(PolestarBatteryCapacitySensor(coordinator))
        if getattr(vehicle, "internet_activation", None):
            info_entities.append(PolestarInternetActivationSensor(coordinator))
        async_add_entities(info_entities)
        async_add_entities([PolestarLocationAddress(coordinator)])


class PolestarSensor(PolestarEntity, SensorEntity):
    """Polestar sensor entity."""

    entity_description: PolestarSensorDescription

    def __init__(self, coordinator, description: PolestarSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.required_fetch = description.fetch_attr
        self.required_data = description.required_data
        self.requires_combustion_engine = description.requires_combustion_engine
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def native_value(self) -> StateType | None:
        if self.coordinator.data is None:
            return None
        value = _safe(self.entity_description.value_fn, self.coordinator.data)
        if value is None and self.entity_description.key == "software_version":
            return self.coordinator.installed_version_cache  # OTA service empty: use the car record
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None or self.entity_description.attrs_fn is None:
            return {}
        return self.entity_description.attrs_fn(self.coordinator.data)


class PolestarVinSensor(PolestarEntity, SensorEntity):
    """The VIN, with the registration plate (if known) as an attribute."""

    _attr_translation_key = "vin"
    _attr_icon = "mdi:card-account-details-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_vin"

    @property
    def native_value(self) -> str:
        return self._vehicle.vin

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self._vehicle
        plate = self.coordinator.config_entry.options.get(CONF_REGISTRATION_PLATE) or v.registration_no
        attrs: dict[str, Any] = {
            "model": v.model_name,
            "model_year": str(v.model_year) if v.model_year else None,  # text, so no thousands separator
            "structure_week": v.structure_week,
            "build_week": _build_week(v.structure_week),
            "powertrain": v.engine_type,
            "drivetrain": v.drivetrain_type,
        }
        if plate:
            attrs["registration_plate"] = plate
        return {k: val for k, val in attrs.items() if val}


class PolestarBatteryCapacitySensor(PolestarEntity, SensorEntity):
    """Battery capacity as the car reports it (gross, from the C3 car-information service)."""

    _attr_translation_key = "battery_capacity"
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_battery_capacity"

    @property
    def native_value(self) -> float | None:
        return getattr(self._vehicle, "battery_capacity_kwh", None)


class PolestarInternetActivationSensor(PolestarEntity, SensorEntity):
    """The car's mobile-network activation status (``acceptance_not_needed``, ...), read when the entry loads."""

    _attr_translation_key = "internet_activation"
    _attr_icon = "mdi:sim"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_internet_activation"

    @property
    def native_value(self) -> str | None:
        info = getattr(self._vehicle, "internet_activation", None) or {}
        status = info.get("status")
        return status.lower() if status else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = getattr(self._vehicle, "internet_activation", None) or {}
        return {"as_of": info["timestamp"]} if info.get("timestamp") else {}


class PolestarVehicleInfoSensor(PolestarEntity, SensorEntity):
    """Everything the app and C3 report about the car, as attributes. Disabled by default.

    For testing on other cars and markets (for example whether the performance software
    upgrade is applied). The VIN, prices, order numbers and addresses are not included.
    """

    _attr_translation_key = "vehicle_info"
    _attr_icon = "mdi:text-box-search-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _unrecorded_attributes = frozenset({MATCH_ALL})  # one attribute per field: keep them out of the database

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_vehicle_info"

    @property
    def native_value(self) -> str:
        return "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self._vehicle
        return {
            "powertrain": v.engine_type,
            "drivetrain": v.drivetrain_type,
            "digital_key_type": v.digital_key_type,
            "has_performance_software_upgrade": v.has_performance_software_upgrade,
            "supports_engine_start": v.supports_engine_start,
            **flatten_attributes(
                {
                    "app": {
                        "slug": v.slug,
                        "pno34": v.pno34,
                        "structure_week": v.structure_week,
                        "is_primary_driver": v.is_primary_driver,
                        "is_bst_edition": v.is_bst_edition,
                        "internet_activation": getattr(v, "internet_activation", None),
                    },
                    "order": getattr(v, "order_specification", None),
                    "c3": getattr(v, "car_capabilities", None) or {},
                }
            ),
        }




class PolestarLocationAddress(PolestarEntity, SensorEntity):
    """Street address of the car's position (OpenStreetMap Nominatim); a Home Assistant zone it is inside wins."""

    _attr_translation_key = "location_address"
    _attr_icon = "mdi:map-marker"
    _MIN_SECONDS_BETWEEN_LOOKUPS = 60  # Nominatim asks for at most one request a second; a moving car changes often

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_location_address"
        self._last_key: tuple[float, float] | None = None
        self._last_lookup = 0.0
        self._cached: str | None = None
        self._cached_attrs: dict[str, Any] = {}

    @property
    def native_value(self) -> str | None:
        return self._cached

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._cached_attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._maybe_geocode()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_background_task(self._maybe_geocode(), name="polestar-geocode")
        super()._handle_coordinator_update()

    def _position(self) -> tuple[float, float] | None:
        data = self.coordinator.data
        for attr in ("location", "parked_location"):
            coord = getattr(getattr(data, attr, None), "coordinate", None)
            lat, lon = getattr(coord, "latitude", None), getattr(coord, "longitude", None)
            if lat is not None and lon is not None and (lat or lon):
                return lat, lon
        return None

    def _zones(self) -> list[dict[str, Any]]:
        zones = []
        for state in self.hass.states.async_all("zone"):
            attrs = state.attributes
            zones.append({
                "name": attrs.get("friendly_name") or state.name,
                "latitude": attrs.get("latitude"), "longitude": attrs.get("longitude"),
                "radius": attrs.get("radius"), "passive": attrs.get("passive"),
                "is_home": state.entity_id == "zone.home",
            })
        return zones

    async def _maybe_geocode(self) -> None:
        position = self._position()
        if position is None:
            return
        lat, lon = position
        key = (round(lat, 4), round(lon, 4))  # about 10 m: ignore GPS jitter
        if key == self._last_key and self._cached is not None:
            return
        zone = geocode.zone_name(lat, lon, self._zones())
        if zone is not None:
            self._last_key, self._cached, self._cached_attrs = key, zone, {"zone": zone}
            self.async_write_ha_state()
            return
        now = time.monotonic()
        if self._cached is not None and now - self._last_lookup < self._MIN_SECONDS_BETWEEN_LOOKUPS:
            return
        self._last_lookup = now
        params = {"format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "zoom": "18", "addressdetails": "1"}
        try:
            async with async_get_clientsession(self.hass).get(
                geocode.NOMINATIM_URL, params=params, headers={"User-Agent": "polestar-ha-integration/1.0"}, timeout=15
            ) as resp:
                if resp.status != 200:
                    return
                reply = await resp.json()
        except Exception:  # noqa: BLE001 - an address is a nicety; never let it break the sensor
            return
        text, details = geocode.pretty_address(reply)
        self._last_key, self._cached = key, text
        self._cached_attrs = {**details, "display_name": reply.get("display_name")}
        self.async_write_ha_state()
