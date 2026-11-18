"""Binary sensor platform for Polestar integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from polestar_api.models.exterior import OpenStatus
from polestar_api.models.health import LowVoltageBatteryWarning, ServiceWarning

from .const import DOMAIN
from .coordinator import PolestarVehicleData
from .entity import PolestarEntity, async_filter_supported_entities, async_remove_registered_entities
from .utils import alarm_triggered, in_use, level_problem as _level_problem, light_attributes, state_icon

PARALLEL_UPDATES = 0


def _safe(fn: Callable[[PolestarVehicleData], Any], data: PolestarVehicleData) -> bool | None:
    try:
        return fn(data)
    except (AttributeError, TypeError):
        return None


def _is_open(status: OpenStatus | None) -> bool | None:
    if status is None or status == OpenStatus.UNSPECIFIED:
        return None
    return status != OpenStatus.CLOSED


@dataclass(frozen=True, kw_only=True)
class PolestarBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with value extractor."""

    value_fn: Callable[[PolestarVehicleData], bool | None]
    icon_on: str | None = None
    icon_off: str | None = None
    fetch_attr: str | None = None
    attrs_fn: Callable[[PolestarVehicleData], dict[str, Any]] | None = None
    required_data: Callable[[PolestarVehicleData], bool] | None = None


BINARY_SENSORS: tuple[PolestarBinarySensorDescription, ...] = (
    PolestarBinarySensorDescription(
        key="is_plugged_in",
        translation_key="is_plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda d: d.battery.is_plugged_in if d.battery else None,
    ),
    PolestarBinarySensorDescription(
        key="any_door_open",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        translation_key="any_door_open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: d.exterior.any_door_open if d.exterior else None,
    ),
    PolestarBinarySensorDescription(
        key="alarm_triggered",
        translation_key="alarm_triggered",
        device_class=BinarySensorDeviceClass.PROBLEM,  # shows OK / Problem
        value_fn=lambda d: alarm_triggered(d.exterior),
    ),
    PolestarBinarySensorDescription(
        key="door_front_left",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        translation_key="door_front_left",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.front_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_front_right",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        translation_key="door_front_right",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.front_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_rear_left",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        translation_key="door_rear_left",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.rear_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_rear_right",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        translation_key="door_rear_right",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.rear_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_front_left",
        translation_key="window_front_left",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.front_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_front_right",
        translation_key="window_front_right",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.front_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_rear_left",
        translation_key="window_rear_left",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.rear_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_rear_right",
        translation_key="window_rear_right",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.rear_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="hood",
        translation_key="hood",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.hood.status.open_status),
    ),
    PolestarBinarySensorDescription(
        key="tailgate",
        translation_key="tailgate",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.tailgate.status.open_status),
    ),
    PolestarBinarySensorDescription(
        key="tank_lid",
        translation_key="tank_lid",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.tank_lid.open_status),
    ),
    PolestarBinarySensorDescription(
        key="available",
        translation_key="available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.availability.is_available if d.availability else None,
    ),
    PolestarBinarySensorDescription(
        key="at_charge_location",
        fetch_attr="current_charge_location",
        translation_key="at_charge_location",
        icon="mdi:map-marker-radius",
        value_fn=lambda d: (
            bool(d.current_charge_location.get("location_id")) if d.current_charge_location is not None else None
        ),
    ),
    PolestarBinarySensorDescription(
        key="tyre_warning",
        fetch_attr="tyre_warning",
        icon_off="mdi:car-tire-alert",
        icon_on="mdi:alert-circle",
        translation_key="tyre_warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.any_tyre_warning if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="light_failure",
        fetch_attr="light_warnings",
        icon_off="mdi:car-light-alert",
        icon_on="mdi:alert-circle",
        translation_key="light_failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.any_light_failure if d.health else None,
        attrs_fn=lambda d: light_attributes(d.health) if d.health else {},
    ),
    PolestarBinarySensorDescription(
        key="brake_fluid_problem",
        icon_off="mdi:car-brake-fluid-level",
        icon_on="mdi:alert-circle",
        translation_key="brake_fluid_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _level_problem(d.health.brake_fluid_level_warning) if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="washer_fluid_problem",
        # Hidden when the car answers the health request but never reports a washer fluid level.
        required_data=lambda d: d.health is None
        or d.health.washer_fluid_level_warning.name != "UNSPECIFIED",
        icon_off="mdi:wiper-wash",
        icon_on="mdi:alert-circle",
        translation_key="washer_fluid_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: _level_problem(d.health.washer_fluid_level_warning) if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="in_use",
        translation_key="in_use",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=lambda d: in_use(d.availability),
    ),
    PolestarBinarySensorDescription(
        key="service_required",
        fetch_attr="service_warning",
        icon_off="mdi:car-wrench",
        icon_on="mdi:alert-circle",
        translation_key="service_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.service_warning not in {ServiceWarning.UNSPECIFIED, ServiceWarning.NO_WARNING} if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="low_voltage_battery",
        icon_off="mdi:car-battery",
        icon_on="mdi:battery-alert",
        translation_key="low_voltage_battery",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.low_voltage_battery_warning == LowVoltageBatteryWarning.TOO_LOW if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="climate_active",
        translation_key="climate_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.climate.is_active if d.climate else None,
    ),
    PolestarBinarySensorDescription(
        # Read-only: the official app's "SetPrivacySettingState" write path
        # was not directly observed, so this integration does not expose a
        # way to change this from Home Assistant — see the library docs.
        key="remote_function_data_sharing",
        translation_key="remote_function_data_sharing",
        value_fn=lambda d: d.remote_function_data_sharing.enabled if d.remote_function_data_sharing else None,
    ),
)


# Replaced by the Charging and Air Purification switches and by Available / Connection (19 Nov 2026).
REMOVED_BINARY_SENSOR_KEYS = ("is_charging", "precleaning_running", "connected")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    for coordinator in data["coordinators"].values():
        async_remove_registered_entities(
            hass, "binary_sensor", [f"{coordinator.vehicle.vin}_{key}" for key in REMOVED_BINARY_SENSOR_KEYS]
        )
        entities = [PolestarBinarySensor(coordinator, desc) for desc in BINARY_SENSORS]
        async_add_entities(async_filter_supported_entities(hass, coordinator, "binary_sensor", entities))


class PolestarBinarySensor(PolestarEntity, BinarySensorEntity):
    """Polestar binary sensor entity."""

    entity_description: PolestarBinarySensorDescription

    def __init__(self, coordinator, description: PolestarBinarySensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.required_fetch = description.fetch_attr
        self.required_data = description.required_data
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        if fn is None or self.coordinator.data is None:
            return None
        return fn(self.coordinator.data) or None

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return _safe(self.entity_description.value_fn, self.coordinator.data)

    @property
    def icon(self) -> str | None:
        description = self.entity_description
        return state_icon(self.is_on, description.icon_on, description.icon_off, super().icon)
