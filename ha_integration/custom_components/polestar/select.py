"""Select platform for Polestar helper settings."""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import PolestarCoordinator
from .entity import PolestarEntity
from polestar_api.models.charging import ChargeTargetLevelSettingType
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.models.parking_climate_timer import (
    BatteryPreconditioning,
    ParkingClimateTimerSettings,
    SeatHeatingSettings,
)

_HEATING_OPTIONS = ["unspecified", "off", "level1", "level2", "level3"]
_HEATING_MAP = {
    "unspecified": HeatingIntensity.UNSPECIFIED,
    "off": HeatingIntensity.OFF,
    "level1": HeatingIntensity.LEVEL1,
    "level2": HeatingIntensity.LEVEL2,
    "level3": HeatingIntensity.LEVEL3,
}
_TARGET_SOC_OPTIONS = ["daily", "long_trip", "custom"]
_TARGET_SOC_MAP = {
    "daily": ChargeTargetLevelSettingType.DAILY,
    "long_trip": ChargeTargetLevelSettingType.LONG_TRIP,
    "custom": ChargeTargetLevelSettingType.CUSTOM,
}
_BATTERY_PRECONDITIONING_OPTIONS = ["off", "when_plugged", "on"]
_BATTERY_PRECONDITIONING_MAP = {
    "off": BatteryPreconditioning.OFF,
    "when_plugged": BatteryPreconditioning.WHEN_PLUGGED,
    "on": BatteryPreconditioning.ON,
}


@dataclass(frozen=True, kw_only=True)
class PolestarSelectDescription(SelectEntityDescription):
    """Select description for command helper state."""


SELECTS: tuple[PolestarSelectDescription, ...] = (
    PolestarSelectDescription(
        key="target_soc_setting_type",
        name="Target SOC mode",
        entity_category=EntityCategory.CONFIG,
        options=_TARGET_SOC_OPTIONS,
    ),
    PolestarSelectDescription(
        key="climate_front_left_seat",
        name="Climate front left seat heat",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="climate_front_right_seat",
        name="Climate front right seat heat",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="climate_rear_left_seat",
        name="Climate rear left seat heat",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="climate_rear_right_seat",
        name="Climate rear right seat heat",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="climate_steering_wheel",
        name="Climate steering wheel heat",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
)

# Timer settings selects — API-backed, not local preferences
TIMER_SETTINGS_SELECTS: tuple[PolestarSelectDescription, ...] = (
    PolestarSelectDescription(
        key="timer_front_left_seat",
        name="Timer front left seat heat",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="timer_front_right_seat",
        name="Timer front right seat heat",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="timer_rear_left_seat",
        name="Timer rear left seat heat",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="timer_rear_right_seat",
        name="Timer rear right seat heat",
        icon="mdi:car-seat-heater",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="timer_steering_wheel",
        name="Timer steering wheel heat",
        icon="mdi:steering",
        entity_category=EntityCategory.CONFIG,
        options=_HEATING_OPTIONS,
    ),
    PolestarSelectDescription(
        key="timer_battery_preconditioning",
        name="Timer battery preconditioning",
        icon="mdi:battery-heart-variant",
        entity_category=EntityCategory.CONFIG,
        options=_BATTERY_PRECONDITIONING_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for description in SELECTS:
            entities.append(PolestarSelect(coordinator, description))
        for description in TIMER_SETTINGS_SELECTS:
            entities.append(PolestarTimerSettingsSelect(coordinator, description))
    async_add_entities(entities)


class PolestarSelect(PolestarEntity, RestoreEntity, SelectEntity):
    """Select entity for local command preferences."""

    entity_description: PolestarSelectDescription

    def __init__(self, coordinator: PolestarCoordinator, description: PolestarSelectDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Restore helper state."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in {"unknown", "unavailable"}:
            return
        if last_state.state in self.options:
            await self.async_select_option(last_state.state)

    @property
    def current_option(self) -> str:
        key = self.entity_description.key
        if key == "target_soc_setting_type":
            return self.coordinator.target_soc_setting_type.name.lower()

        prefs = self.coordinator.climate_preferences
        if key == "climate_front_left_seat":
            return prefs.front_left_seat.name.lower()
        if key == "climate_front_right_seat":
            return prefs.front_right_seat.name.lower()
        if key == "climate_rear_left_seat":
            return prefs.rear_left_seat.name.lower()
        if key == "climate_rear_right_seat":
            return prefs.rear_right_seat.name.lower()
        return prefs.steering_wheel.name.lower()

    async def async_select_option(self, option: str) -> None:
        key = self.entity_description.key
        if key == "target_soc_setting_type":
            self.coordinator.target_soc_setting_type = _TARGET_SOC_MAP[option]
            self.async_write_ha_state()
            return

        heating = _HEATING_MAP[option]
        prefs = self.coordinator.climate_preferences
        if key == "climate_front_left_seat":
            prefs.front_left_seat = heating
        elif key == "climate_front_right_seat":
            prefs.front_right_seat = heating
        elif key == "climate_rear_left_seat":
            prefs.rear_left_seat = heating
        elif key == "climate_rear_right_seat":
            prefs.rear_right_seat = heating
        else:
            prefs.steering_wheel = heating
        self.async_write_ha_state()


class PolestarTimerSettingsSelect(PolestarEntity, SelectEntity):
    """Select entity for API-backed parking climate timer default settings."""

    entity_description: PolestarSelectDescription

    def __init__(self, coordinator: PolestarCoordinator, description: PolestarSelectDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def _settings(self) -> ParkingClimateTimerSettings | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.climate_timer_settings

    @property
    def available(self) -> bool:
        return super().available and self._settings is not None

    @property
    def current_option(self) -> str | None:
        settings = self._settings
        if settings is None:
            return None
        key = self.entity_description.key
        if key == "timer_battery_preconditioning":
            bp = settings.battery_preconditioning
            if bp == BatteryPreconditioning.UNDEFINED:
                return "off"
            return bp.name.lower()
        # Heating keys
        if key == "timer_steering_wheel":
            return settings.steering_wheel_heating.name.lower()
        seat = settings.seat_heating
        if key == "timer_front_left_seat":
            return seat.front_left.name.lower()
        if key == "timer_front_right_seat":
            return seat.front_right.name.lower()
        if key == "timer_rear_left_seat":
            return seat.rear_left.name.lower()
        return seat.rear_right.name.lower()

    async def async_select_option(self, option: str) -> None:
        settings = self._settings
        if settings is None:
            return
        key = self.entity_description.key
        if key == "timer_battery_preconditioning":
            updated = replace(settings, battery_preconditioning=_BATTERY_PRECONDITIONING_MAP[option])
        elif key == "timer_steering_wheel":
            updated = replace(settings, steering_wheel_heating=_HEATING_MAP[option])
        else:
            heating = _HEATING_MAP[option]
            seat = settings.seat_heating
            if key == "timer_front_left_seat":
                seat = replace(seat, front_left=heating)
            elif key == "timer_front_right_seat":
                seat = replace(seat, front_right=heating)
            elif key == "timer_rear_left_seat":
                seat = replace(seat, rear_left=heating)
            else:
                seat = replace(seat, rear_right=heating)
            updated = replace(settings, seat_heating=seat)
        await self.coordinator.async_set_climate_timer_settings(updated)
