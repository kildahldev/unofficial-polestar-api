"""Sensor platform for Polestar integration."""

from __future__ import annotations

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
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

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
from polestar_api.models.health import (
    BrakeFluidLevelWarning,
    LowVoltageBatteryWarning,
    ServiceWarning,
    WasherFluidLevelWarning,
)
from polestar_api.models.ota import SoftwareState
from polestar_api.models.precleaning import PreCleaningErrorType, PreCleaningStartReason

from .const import DOMAIN
from .coordinator import PolestarVehicleData
from .entity import PolestarEntity
from .utils import enum_name, enum_options, serialize_charge_location


def _safe(fn: Callable[[PolestarVehicleData], Any], data: PolestarVehicleData) -> Any:
    try:
        return fn(data)
    except (AttributeError, TypeError, ValueError):
        return None


def _current_charge_location_state(data: PolestarVehicleData) -> str | None:
    location_id = data.current_charge_location.get("location_id")
    if not location_id:
        return None
    for location in data.charge_locations:
        if location.location_id == location_id:
            return location.location_alias or location.location_id
    return location_id


def _current_charge_location_attrs(data: PolestarVehicleData) -> dict[str, Any]:
    location_id = data.current_charge_location.get("location_id")
    if not location_id:
        return {}
    attrs: dict[str, Any] = {
        "location_id": location_id,
        "arrived_at": data.current_charge_location.get("arrived_at"),
    }
    for location in data.charge_locations:
        if location.location_id == location_id:
            attrs.update(serialize_charge_location(location))
            break
    return attrs


@dataclass(frozen=True, kw_only=True)
class PolestarSensorDescription(SensorEntityDescription):
    """Sensor entity description with value extractor."""

    value_fn: Callable[[PolestarVehicleData], StateType | None]
    attrs_fn: Callable[[PolestarVehicleData], dict[str, Any]] | None = None


SENSORS: tuple[PolestarSensorDescription, ...] = (
    PolestarSensorDescription(
        key="battery_level",
        name="Battery level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.battery.charge_level if d.battery else None,
    ),
    PolestarSensorDescription(
        key="range",
        name="Range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: d.battery.range_km if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_power",
        name="Charging power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.battery.power_watts if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_current",
        name="Charging current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda d: d.battery.current_amps if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_voltage",
        name="Charging voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_fn=lambda d: d.battery.voltage_volts if d.battery else None,
    ),
    PolestarSensorDescription(
        key="time_to_full",
        name="Time to full charge",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: d.battery.time_to_full if d.battery else None,
    ),
    PolestarSensorDescription(
        key="time_to_target",
        name="Time to target charge",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery.time_to_target if d.battery else None,
    ),
    PolestarSensorDescription(
        key="time_to_min_soc",
        name="Time to minimum SoC",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery.time_to_min_soc if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_status",
        name="Charging status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargingStatus),
        value_fn=lambda d: enum_name(d.battery.charging_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charger_connection",
        name="Charger connection",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargerConnectionStatus),
        value_fn=lambda d: enum_name(d.battery.charger_connection_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charging_type",
        name="Charging type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(ChargingType),
        value_fn=lambda d: enum_name(d.battery.charging_type) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charger_power_status",
        name="Charger power status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(ChargerPowerStatus),
        value_fn=lambda d: enum_name(d.battery.charger_power_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption",
        name="Average consumption",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh/100km",
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption_auto",
        name="Average consumption (auto)",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh/100km",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption_auto if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption_since_charge",
        name="Average consumption since charge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kWh/100km",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption_since_charge if d.battery else None,
    ),
    PolestarSensorDescription(
        key="odometer",
        name="Odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: d.odometer.odometer_km if d.odometer else None,
    ),
    PolestarSensorDescription(
        key="trip_meter_manual",
        name="Trip meter (manual)",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: (d.dashboard.dashboard_data.trip_meter_manual_km if d.dashboard and d.dashboard.dashboard_data else None) or (d.odometer.trip_meter_manual_km if d.odometer and d.odometer.trip_meter_manual_km else None),
    ),
    PolestarSensorDescription(
        key="trip_meter_auto",
        name="Trip meter (auto)",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda d: (d.dashboard.dashboard_data.trip_meter_auto_km if d.dashboard and d.dashboard.dashboard_data else None) or (d.odometer.trip_meter_automatic_km if d.odometer and d.odometer.trip_meter_automatic_km else None),
    ),
    PolestarSensorDescription(
        key="heading",
        name="Heading",
        native_unit_of_measurement="°",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.heading if d.location else None,
    ),
    PolestarSensorDescription(
        key="speed",
        name="Speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.speed if d.location else None,
    ),
    PolestarSensorDescription(
        key="altitude",
        name="Altitude",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.altitude if d.location else None,
    ),
    PolestarSensorDescription(
        key="distance_to_service",
        name="Distance to service",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        icon="mdi:wrench-clock",
        value_fn=lambda d: d.health.distance_to_service_km if d.health else None,
    ),
    PolestarSensorDescription(
        key="days_to_service",
        name="Days to service",
        native_unit_of_measurement="d",
        icon="mdi:wrench-clock",
        value_fn=lambda d: d.health.days_to_service if d.health else None,
    ),
    PolestarSensorDescription(
        key="engine_hours_to_service",
        name="Engine hours to service",
        native_unit_of_measurement="h",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:engine",
        value_fn=lambda d: d.health.engine_hours_to_service if d.health else None,
    ),
    PolestarSensorDescription(
        key="service_warning",
        name="Service warning",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ServiceWarning),
        value_fn=lambda d: enum_name(d.health.service_warning) if d.health else None,
    ),
    PolestarSensorDescription(
        key="brake_fluid_warning",
        name="Brake fluid warning",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(BrakeFluidLevelWarning),
        value_fn=lambda d: enum_name(d.health.brake_fluid_level_warning) if d.health else None,
    ),
    PolestarSensorDescription(
        key="washer_fluid_warning",
        name="Washer fluid warning",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(WasherFluidLevelWarning),
        value_fn=lambda d: enum_name(d.health.washer_fluid_level_warning) if d.health else None,
    ),
    PolestarSensorDescription(
        key="low_voltage_battery_warning",
        name="Low-voltage battery warning",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(LowVoltageBatteryWarning),
        value_fn=lambda d: enum_name(d.health.low_voltage_battery_warning) if d.health else None,
    ),
    PolestarSensorDescription(
        key="outside_temperature",
        name="Outside temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.weather.temperature_celsius if d.weather else None,
    ),
    PolestarSensorDescription(
        key="fl_tyre_pressure",
        name="Front left tyre pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        value_fn=lambda d: d.health.front_left_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="fr_tyre_pressure",
        name="Front right tyre pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        value_fn=lambda d: d.health.front_right_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="rl_tyre_pressure",
        name="Rear left tyre pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        value_fn=lambda d: d.health.rear_left_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="rr_tyre_pressure",
        name="Rear right tyre pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.KPA,
        value_fn=lambda d: d.health.rear_right_tyre_pressure_kpa if d.health else None,
    ),
    PolestarSensorDescription(
        key="air_quality_index",
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precleaning.measured_air_quality_index if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="pm25",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="µg/m³",
        value_fn=lambda d: d.precleaning.measured_particulate_matter_2_5 if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_runtime_left",
        name="Pre-cleaning runtime left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.precleaning.runtime_left_minutes if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_start_reason",
        name="Pre-cleaning start reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(PreCleaningStartReason),
        value_fn=lambda d: enum_name(d.precleaning.start_reason) if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_error",
        name="Pre-cleaning error",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(PreCleaningErrorType),
        value_fn=lambda d: enum_name(d.precleaning.error) if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="software_version",
        name="Software version",
        icon="mdi:update",
        value_fn=lambda d: d.software.new_sw_version if d.software else None,
    ),
    PolestarSensorDescription(
        key="software_state",
        name="Software state",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(SoftwareState, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.software.state, allow_unspecified=True) if d.software else None,
    ),
    PolestarSensorDescription(
        key="climate_running_status",
        name="Climate running status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ClimatizationRunningStatus, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.climate.running_status, allow_unspecified=True) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_request_type",
        name="Climate request type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(ClimatizationRequestType, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.climate.request_type, allow_unspecified=True) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_heat_or_cool_action",
        name="Climate heat or cool action",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(HeatOrCoolAction, exclude_unspecified=False),
        value_fn=lambda d: enum_name(d.climate.heat_or_cool_action, allow_unspecified=True) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_time_remaining",
        name="Climate time remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.climate.time_remaining if d.climate else None,
    ),
    PolestarSensorDescription(
        key="availability_unavailable_reason",
        name="Unavailable reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(UnavailableReason),
        value_fn=lambda d: enum_name(d.availability.unavailable_reason) if d.availability else None,
    ),
    PolestarSensorDescription(
        key="availability_usage_mode",
        name="Usage mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(UsageMode),
        value_fn=lambda d: enum_name(d.availability.usage_mode) if d.availability else None,
    ),
    PolestarSensorDescription(
        key="charge_locations",
        name="Charge locations",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.charge_locations),
        attrs_fn=lambda d: {"locations": [serialize_charge_location(location) for location in d.charge_locations]},
    ),
    PolestarSensorDescription(
        key="current_charge_location",
        name="Current charge location",
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
    entities = []
    for coordinator in data["coordinators"].values():
        for desc in SENSORS:
            entities.append(PolestarSensor(coordinator, desc))
    async_add_entities(entities)


class PolestarSensor(PolestarEntity, SensorEntity):
    """Polestar sensor entity."""

    entity_description: PolestarSensorDescription

    def __init__(self, coordinator, description: PolestarSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def native_value(self) -> StateType | None:
        if self.coordinator.data is None:
            return None
        return _safe(self.entity_description.value_fn, self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None or self.entity_description.attrs_fn is None:
            return {}
        return self.entity_description.attrs_fn(self.coordinator.data)
