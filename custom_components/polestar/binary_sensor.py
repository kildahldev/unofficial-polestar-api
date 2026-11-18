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
from .entity import PolestarEntity, async_filter_supported_entities
from .utils import state_icon

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


BINARY_SENSORS: tuple[PolestarBinarySensorDescription, ...] = (
    PolestarBinarySensorDescription(
        key="is_charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda d: d.battery.is_charging if d.battery else None,
    ),
    PolestarBinarySensorDescription(
        key="is_plugged_in",
        name="Plugged in",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda d: d.battery.is_plugged_in if d.battery else None,
    ),
    PolestarBinarySensorDescription(
        key="is_locked",
        name="Locked",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda d: not d.exterior.is_locked if d.exterior else None,
    ),
    PolestarBinarySensorDescription(
        key="any_door_open",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        name="Any door open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: d.exterior.any_door_open if d.exterior else None,
    ),
    PolestarBinarySensorDescription(
        key="door_front_left",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        name="Front left door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.front_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_front_right",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        name="Front right door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.front_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_rear_left",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        name="Rear left door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.rear_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_rear_right",
        icon_on="mdi:car-door-lock-open",
        icon_off="mdi:car-door",
        name="Rear right door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.rear_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_front_left",
        name="Front left window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.front_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_front_right",
        name="Front right window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.front_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_rear_left",
        name="Rear left window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.rear_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="window_rear_right",
        name="Rear right window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.windows.rear_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="hood",
        name="Hood",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.hood.status.open_status),
    ),
    PolestarBinarySensorDescription(
        key="tailgate",
        name="Tailgate",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.tailgate.status.open_status),
    ),
    PolestarBinarySensorDescription(
        key="sunroof",
        fetch_attr="sunroof",
        name="Sunroof",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.sunroof.open_status),
    ),
    PolestarBinarySensorDescription(
        key="tank_lid",
        name="Charging lid",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.tank_lid.open_status),
    ),
    PolestarBinarySensorDescription(
        key="connected",
        fetch_attr="connectivity",
        name="Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.connectivity.is_connected if d.connectivity else None,
    ),
    PolestarBinarySensorDescription(
        key="available",
        name="Available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.availability.is_available if d.availability else None,
    ),
    PolestarBinarySensorDescription(
        key="at_charge_location",
        fetch_attr="current_charge_location",
        name="At charge location",
        icon="mdi:map-marker-radius",
        value_fn=lambda d: (
            bool(d.current_charge_location.get("location_id")) if d.current_charge_location is not None else None
        ),
    ),
    PolestarBinarySensorDescription(
        key="tyre_warning",
        icon_off="mdi:car-tire-alert",
        icon_on="mdi:alert-circle",
        name="Tyre warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.any_tyre_warning if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="light_failure",
        icon_off="mdi:car-light-alert",
        icon_on="mdi:alert-circle",
        name="Light failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.any_light_failure if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="service_required",
        icon_off="mdi:car-wrench",
        icon_on="mdi:alert-circle",
        name="Service required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.service_warning not in {ServiceWarning.UNSPECIFIED, ServiceWarning.NO_WARNING} if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="low_voltage_battery",
        icon_off="mdi:car-battery",
        icon_on="mdi:battery-alert",
        name="Low-voltage battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda d: d.health.low_voltage_battery_warning == LowVoltageBatteryWarning.TOO_LOW if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="climate_active",
        name="Climate active",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.climate.is_active if d.climate else None,
    ),
    PolestarBinarySensorDescription(
        key="precleaning_running",
        fetch_attr="precleaning",
        name="Pre-cleaning running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.precleaning.is_running if d.precleaning else None,
    ),
    PolestarBinarySensorDescription(
        # Read-only: the official app's "SetPrivacySettingState" write path
        # was not directly observed, so this integration does not expose a
        # way to change this from Home Assistant — see the library docs.
        key="remote_function_data_sharing",
        name="Remote function data sharing",
        value_fn=lambda d: d.remote_function_data_sharing.enabled if d.remote_function_data_sharing else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    for coordinator in data["coordinators"].values():
        entities = [PolestarBinarySensor(coordinator, desc) for desc in BINARY_SENSORS]
        async_add_entities(async_filter_supported_entities(hass, coordinator, "binary_sensor", entities))


class PolestarBinarySensor(PolestarEntity, BinarySensorEntity):
    """Polestar binary sensor entity."""

    entity_description: PolestarBinarySensorDescription

    def __init__(self, coordinator, description: PolestarBinarySensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.required_fetch = description.fetch_attr
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return _safe(self.entity_description.value_fn, self.coordinator.data)

    @property
    def icon(self) -> str | None:
        description = self.entity_description
        return state_icon(self.is_on, description.icon_on, description.icon_off, super().icon)
