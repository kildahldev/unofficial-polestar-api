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
from homeassistant.core import HomeAssistant
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
from .utils import (
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

# (key, name, assumed power in kW) for the "time to reach target SOC" sensors below.
# Names are kept short and punctuation-free so the generated entity_id matches the key.
CHARGING_TIME_TIERS: tuple[tuple[str, str, float], ...] = (
    ("charging_time_domestic_power", "Charging time domestic power", 7.0),
    ("charging_time_low_power", "Charging time low power", 22.0),
    ("charging_time_fast_power", "Charging time fast power", 100.0),
    ("charging_time_ultrafast_power", "Charging time ultrafast power", 300.0),
)


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


def _energy_needed_kwh(data: PolestarVehicleData, capacity_kwh: float) -> float | None:
    """Energy needed to reach target SOC, estimated from usable capacity and current/target charge levels."""
    if data.battery is None or data.target_soc is None:
        return None
    current = data.battery.charge_level
    target = data.target_soc.target_level
    if target <= current:
        return None
    return capacity_kwh * (target - current) / 100


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
        key="target_soc",
        name="Target SOC",
        icon="mdi:battery-charging-high",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.target_soc.target_level if d.target_soc else None,
        attrs_fn=lambda d: {"mode": enum_name(d.target_soc.setting_type)} if d.target_soc else {},
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
        icon="mdi:power-plug-battery",
        name="Charging status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargingStatus),
        value_fn=lambda d: enum_name(d.battery.charging_status) if d.battery else None,
    ),
    PolestarSensorDescription(
        key="charger_connection",
        icon="mdi:ev-plug-type2",
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
        fetch_attr="avg_consumption",
        name="Average consumption",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
        icon="mdi:lightning-bolt",
        value_fn=lambda d: d.battery.avg_consumption if d.battery else None,
    ),
    PolestarSensorDescription(
        key="avg_consumption_auto",
        fetch_attr="avg_consumption_auto",
        name="Average consumption (auto)",
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
        name="Average consumption since charge",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergyDistance.KILO_WATT_HOUR_PER_100_KM,
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
        value_fn=lambda d: (d.dashboard.dashboard_data.trip_meter_auto_km if d.dashboard and d.dashboard.dashboard_data else None) or (d.odometer.trip_meter_automatic_km if d.odometer and d.odometer.trip_meter_automatic_km is not None else None),
    ),
    PolestarSensorDescription(
        key="heading",
        # The C3 location service sends only a position, so these stay 0 on it.
        required_data=_location_reports_motion,
        name="Heading",
        native_unit_of_measurement="°",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.heading if d.location else None,
    ),
    PolestarSensorDescription(
        key="speed",
        # The C3 location service sends only a position, so these stay 0 on it.
        required_data=_location_reports_motion,
        name="Speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.location.speed if d.location else None,
    ),
    PolestarSensorDescription(
        key="altitude",
        # The C3 location service sends only a position, so these stay 0 on it.
        required_data=_location_reports_motion,
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
        requires_combustion_engine=True,
        native_unit_of_measurement="h",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:engine",
        value_fn=lambda d: d.health.engine_hours_to_service if d.health else None,
    ),
    PolestarSensorDescription(
        key="outside_temperature",
        name="Outside temperature",
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
        name="Front left tyre pressure",
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
        name="Front right tyre pressure",
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
        name="Rear left tyre pressure",
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
        name="Rear right tyre pressure",
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
        name="Air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.precleaning.measured_air_quality_index if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="pm25",
        fetch_attr="precleaning",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="µg/m³",
        value_fn=lambda d: d.precleaning.measured_particulate_matter_2_5 if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_runtime_left",
        fetch_attr="precleaning",
        name="Pre-cleaning runtime left",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.precleaning.runtime_left_minutes if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_start_reason",
        fetch_attr="precleaning",
        name="Pre-cleaning start reason",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=enum_options(PreCleaningStartReason),
        value_fn=lambda d: enum_name(d.precleaning.start_reason) if d.precleaning else None,
    ),
    PolestarSensorDescription(
        key="precleaning_error",
        fetch_attr="precleaning",
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
        icon="mdi:air-conditioner",
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
        key="climate_time_remaining",
        name="Climate time remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: climate_minutes_remaining(d.climate, dt_util.utcnow().timestamp()),
    ),
    PolestarSensorDescription(
        key="climate_ends_at",
        name="Climate ends at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _timestamp_or_none(climate_end_time(d.climate)),
    ),
    PolestarSensorDescription(
        key="climate_current_temperature",
        name="Climate current temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.climate.current_temperature_celsius if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_target_temperature",
        name="Climate target temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.climate.target_temperature_celsius if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_front_left_seat",
        name="Climate front left seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.front_left_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_front_right_seat",
        name="Climate front right seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.front_right_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_rear_left_seat",
        fetch_attr="rear_seat_heating",
        name="Climate rear left seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.rear_left_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_rear_right_seat",
        fetch_attr="rear_seat_heating",
        name="Climate rear right seat",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:car-seat-heater",
        value_fn=lambda d: _heating_intensity_name(d.climate.rear_right_seat) if d.climate else None,
    ),
    PolestarSensorDescription(
        key="climate_steering_wheel",
        name="Climate steering wheel",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "level1", "level2", "level3"],
        icon="mdi:steering",
        value_fn=lambda d: _heating_intensity_name(d.climate.steering_wheel) if d.climate else None,
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
        fetch_attr="charge_locations",
        name="Charge locations",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d.charge_locations) if d.charge_locations is not None else None,
        attrs_fn=lambda d: {"locations": [serialize_charge_location(location) for location in d.charge_locations or ()]},
    ),
    PolestarSensorDescription(
        key="current_charge_location",
        fetch_attr="current_charge_location",
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
    for coordinator in data["coordinators"].values():
        entities = [PolestarSensor(coordinator, desc) for desc in SENSORS]
        entities.extend(
            PolestarChargingTimeSensor(coordinator, key, name, power_kw)
            for key, name, power_kw in CHARGING_TIME_TIERS
        )
        async_add_entities(async_filter_supported_entities(hass, coordinator, "sensor", entities))
        info_entities: list[SensorEntity] = [PolestarVinSensor(coordinator), PolestarVehicleInfoSensor(coordinator)]
        vehicle = coordinator.vehicle
        if getattr(vehicle, "battery_capacity_kwh", None):
            info_entities.append(PolestarBatteryCapacitySensor(coordinator))
        if getattr(vehicle, "internet_activation", None):
            info_entities.append(PolestarInternetActivationSensor(coordinator))
        async_add_entities(info_entities)


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
        return _safe(self.entity_description.value_fn, self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None or self.entity_description.attrs_fn is None:
            return {}
        return self.entity_description.attrs_fn(self.coordinator.data)


class PolestarVinSensor(PolestarEntity, SensorEntity):
    """The VIN, with the registration plate (if known) as an attribute."""

    _attr_name = "VIN"
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

    _attr_name = "Battery Capacity"
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

    _attr_name = "Internet Activation"
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

    _attr_name = "Vehicle Info"
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


class PolestarChargingTimeSensor(PolestarEntity, SensorEntity):
    """Estimated time to reach the target SOC at a fixed assumed charging power.

    Uses the vehicle's usable battery capacity (looked up by model, since the
    API never reports it) rather than an active charging session, so it has a
    value whether or not the car is currently plugged in.
    """

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:ev-station"
    required_fetch = "target_soc"

    def __init__(self, coordinator, key: str, name: str, power_kw: float) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_{key}"
        self._attr_name = name
        self._power_kw = power_kw

    @property
    def native_value(self) -> StateType | None:
        if self.coordinator.data is None:
            return None
        capacity_kwh = _vehicle_capacity_kwh(self._vehicle)
        energy_kwh = _safe(lambda d: _energy_needed_kwh(d, capacity_kwh), self.coordinator.data)
        if energy_kwh is None:
            return None
        return round(energy_kwh / self._power_kw * 60)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "assumed_power_kw": self._power_kw,
            "assumed_battery_capacity_kwh": _vehicle_capacity_kwh(self._vehicle),
        }
