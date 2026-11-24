"""Switch platform for Polestar integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PolestarCoordinator, PolestarVehicleData
from .entity import OptimisticStateMixin, PolestarEntity


@dataclass(frozen=True, kw_only=True)
class PolestarSwitchDescription(SwitchEntityDescription):
    """Switch description with on/off callables and state extractor."""

    is_on_fn: Callable[[PolestarVehicleData], bool | None]
    turn_on_fn: Callable[[PolestarCoordinator], Awaitable[Any]]
    turn_off_fn: Callable[[PolestarCoordinator], Awaitable[Any]]
    capability: str | None = None


SWITCHES: tuple[PolestarSwitchDescription, ...] = (
    PolestarSwitchDescription(
        key="climate",
        name="Climate",
        icon="mdi:air-conditioner",
        is_on_fn=lambda d: d.climate.is_active if d.climate else None,
        turn_on_fn=lambda c: c.async_start_climate(),
        turn_off_fn=lambda c: c.async_stop_climate(),
        capability="climate",
    ),
    PolestarSwitchDescription(
        key="precleaning",
        name="Pre-cleaning",
        icon="mdi:air-purifier",
        is_on_fn=lambda d: d.precleaning.is_running if d.precleaning else None,
        turn_on_fn=lambda c: c.async_start_precleaning(),
        turn_off_fn=lambda c: c.async_stop_precleaning(),
        capability="precleaning",
    ),
    PolestarSwitchDescription(
        key="charging",
        name="Charging",
        icon="mdi:ev-station",
        is_on_fn=lambda d: d.battery.is_charging if d.battery else None,
        turn_on_fn=lambda c: c.async_start_charging(),
        turn_off_fn=lambda c: c.async_stop_charging(),
        capability="charging",
    ),
    PolestarSwitchDescription(
        key="charge_timer",
        name="Charge timer",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: d.charge_timer.timer.activated if d.charge_timer and d.charge_timer.timer else None,
        turn_on_fn=lambda c: c.async_set_charge_timer(activated=True),
        turn_off_fn=lambda c: c.async_set_charge_timer(activated=False),
        capability="charge_timer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar switches."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for desc in SWITCHES:
            entities.append(PolestarSwitch(coordinator, desc))
    async_add_entities(entities)


class PolestarSwitch(OptimisticStateMixin, PolestarEntity, SwitchEntity):
    """Polestar switch entity."""

    entity_description: PolestarSwitchDescription

    def __init__(self, coordinator, description: PolestarSwitchDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    @property
    def available(self) -> bool:
        """Return False if the car doesn't support this command."""
        cap = self.entity_description.capability
        if cap and not self.coordinator.is_command_supported(cap):
            return False
        return super().available

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        try:
            real_value = self.entity_description.is_on_fn(self.coordinator.data)
        except (AttributeError, TypeError):
            return None
        return self._resolve_optimistic(real_value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set_optimistic(True)
        try:
            await self.entity_description.turn_on_fn(self.coordinator)
        except Exception:
            self._clear_optimistic()
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set_optimistic(False)
        try:
            await self.entity_description.turn_off_fn(self.coordinator)
        except Exception:
            self._clear_optimistic()
            raise
