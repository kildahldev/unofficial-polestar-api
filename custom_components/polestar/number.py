"""Number platform for Polestar integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import PolestarCoordinator, PolestarVehicleData
from .entity import PolestarEntity
from polestar_api.models.parking_climate_timer import ParkingClimateTimerSettings


@dataclass(frozen=True, kw_only=True)
class PolestarNumberDescription(NumberEntityDescription):
    """Number description with value extractor and setter."""

    value_fn: Callable[[PolestarCoordinator], float | None]
    set_fn: Callable[[PolestarCoordinator, float], Awaitable[Any] | None]
    restore_state: bool = False


NUMBERS: tuple[PolestarNumberDescription, ...] = (
    PolestarNumberDescription(
        key="target_soc",
        name="Target SOC",
        icon="mdi:battery-charging-high",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=20,
        native_max_value=100,
        native_step=1,
        value_fn=lambda c: c.data.target_soc.target_level if c.data and c.data.target_soc else None,
        set_fn=lambda c, val: c.async_set_target_soc(int(val)),
    ),
    PolestarNumberDescription(
        key="amp_limit",
        name="Charging amp limit",
        icon="mdi:current-ac",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=6,
        native_max_value=32,
        native_step=1,
        value_fn=lambda c: c.data.amp_limit.amperage_limit if c.data and c.data.amp_limit else None,
        set_fn=lambda c, val: c.async_set_amp_limit(int(val)),
    ),
    PolestarNumberDescription(
        key="climate_target_temperature",
        name="Climate target temperature",
        icon="mdi:thermometer-auto",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=30,
        native_step=0.5,
        value_fn=lambda c: c.climate_preferences.target_temperature,
        set_fn=lambda c, val: None,
        restore_state=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for desc in NUMBERS:
            entities.append(PolestarNumber(coordinator, desc))
        entities.append(PolestarTimerTemperatureNumber(coordinator))
    async_add_entities(entities)


class PolestarNumber(PolestarEntity, RestoreEntity, NumberEntity):
    """Polestar number entity."""

    entity_description: PolestarNumberDescription

    def __init__(self, coordinator: PolestarCoordinator, description: PolestarNumberDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Restore helper state for non-API-backed number entities."""
        await super().async_added_to_hass()
        if not self.entity_description.restore_state:
            return

        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in {"unknown", "unavailable"}:
            return

        try:
            restored = float(last_state.state)
        except ValueError:
            return

        if self.entity_description.key == "climate_target_temperature":
            self.coordinator.climate_preferences.target_temperature = restored

    @property
    def native_value(self) -> float | None:
        try:
            return self.entity_description.value_fn(self.coordinator)
        except (AttributeError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        if self.entity_description.key == "climate_target_temperature":
            self.coordinator.climate_preferences.target_temperature = value
            self.async_write_ha_state()
            return

        result = self.entity_description.set_fn(self.coordinator, value)
        if result is not None:
            await result


class PolestarTimerTemperatureNumber(PolestarEntity, NumberEntity):
    """API-backed number entity for parking climate timer target temperature."""

    _attr_name = "Timer target temperature"
    _attr_icon = "mdi:thermometer-auto"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 15.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5

    def __init__(self, coordinator: PolestarCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_timer_target_temperature"

    @property
    def _settings(self) -> ParkingClimateTimerSettings | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.climate_timer_settings

    @property
    def available(self) -> bool:
        return super().available and self._settings is not None

    @property
    def native_value(self) -> float | None:
        settings = self._settings
        if settings is None:
            return None
        return settings.temperature_celsius

    async def async_set_native_value(self, value: float) -> None:
        settings = self._settings
        if settings is None:
            return
        updated = replace(settings, temperature_celsius=value, is_temperature_requested=True)
        await self.coordinator.async_set_climate_timer_settings(updated)
