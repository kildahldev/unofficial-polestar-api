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
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from polestar_api.models.exterior import OpenStatus
from polestar_api.models.health import LowVoltageBatteryWarning, ServiceWarning
from polestar_api.models.privacy import PrivacySettingType

from .const import DOMAIN
from .coordinator import PolestarVehicleData
from .entity import PolestarEntity


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
    attrs_fn: Callable[[PolestarVehicleData], dict[str, Any]] | None = None


def _privacy_value(setting_type: PrivacySettingType) -> Callable[[PolestarVehicleData], bool | None]:
    def value(data: PolestarVehicleData) -> bool | None:
        setting = data.privacy_settings.get(setting_type)
        return setting.enabled if setting else None

    return value


def _privacy_attrs(setting_type: PrivacySettingType) -> Callable[[PolestarVehicleData], dict[str, Any]]:
    def attrs(data: PolestarVehicleData) -> dict[str, Any]:
        setting = data.privacy_settings.get(setting_type)
        if setting is None:
            return {}
        result: dict[str, Any] = {"read_only": setting.read_only}
        if setting.service_id:
            result["service_id"] = setting.service_id
        return result

    return attrs


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
        name="Any door open",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: d.exterior.any_door_open if d.exterior else None,
    ),
    PolestarBinarySensorDescription(
        key="door_front_left",
        name="Front left door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.front_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_front_right",
        name="Front right door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.front_right.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_rear_left",
        name="Rear left door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.doors.rear_left.open_status),
    ),
    PolestarBinarySensorDescription(
        key="door_rear_right",
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
        name="Sunroof",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda d: _is_open(d.exterior.sunroof.open_status),
    ),
    PolestarBinarySensorDescription(
        key="tank_lid",
        name="Tank lid",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda d: _is_open(d.exterior.tank_lid.open_status),
    ),
    PolestarBinarySensorDescription(
        key="connected",
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
        name="At charge location",
        icon="mdi:map-marker-radius",
        value_fn=lambda d: bool(d.current_charge_location.get("location_id")),
    ),
    PolestarBinarySensorDescription(
        key="tyre_warning",
        name="Tyre warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.any_tyre_warning if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="light_failure",
        name="Light failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.any_light_failure if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="service_required",
        name="Service required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda d: d.health.service_warning not in {ServiceWarning.UNSPECIFIED, ServiceWarning.NO_WARNING} if d.health else None,
    ),
    PolestarBinarySensorDescription(
        key="low_voltage_battery",
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
        name="Pre-cleaning running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda d: d.precleaning.is_running if d.precleaning else None,
    ),
    PolestarBinarySensorDescription(
        key="location_sharing",
        name="Location sharing",
        icon="mdi:map-marker-account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_privacy_value(PrivacySettingType.VEHICLE_LOCATION_SHARING),
        attrs_fn=_privacy_attrs(PrivacySettingType.VEHICLE_LOCATION_SHARING),
    ),
    PolestarBinarySensorDescription(
        key="privacy_setting",
        name="Privacy setting",
        icon="mdi:shield-account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_privacy_value(PrivacySettingType.PRIVACY_SETTING),
        attrs_fn=_privacy_attrs(PrivacySettingType.PRIVACY_SETTING),
    ),
    PolestarBinarySensorDescription(
        key="data_sharing",
        name="Data sharing",
        icon="mdi:database-export",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_privacy_value(PrivacySettingType.VEHICLE_DATA_SHARING),
        attrs_fn=_privacy_attrs(PrivacySettingType.VEHICLE_DATA_SHARING),
    ),
)


_PRIVACY_KEYS = frozenset({"location_sharing", "privacy_setting", "data_sharing"})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for desc in BINARY_SENSORS:
            entities.append(PolestarBinarySensor(coordinator, desc))
    async_add_entities(entities)


class PolestarBinarySensor(PolestarEntity, BinarySensorEntity):
    """Polestar binary sensor entity."""

    entity_description: PolestarBinarySensorDescription

    def __init__(self, coordinator, description: PolestarBinarySensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return _safe(self.entity_description.value_fn, self.coordinator.data)

    @property
    def available(self) -> bool:
        # Privacy sensors stay unavailable until a message for their type arrives.
        if self.entity_description.key in _PRIVACY_KEYS:
            return super().available and self.is_on is not None
        return super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None or self.entity_description.attrs_fn is None:
            return {}
        return self.entity_description.attrs_fn(self.coordinator.data)
