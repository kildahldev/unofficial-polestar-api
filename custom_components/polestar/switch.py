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
from .entity import OptimisticStateMixin, PolestarEntity, async_filter_supported_entities

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PolestarSwitchDescription(SwitchEntityDescription):
    """Switch description with on/off callables and state extractor."""

    is_on_fn: Callable[[PolestarVehicleData], bool | None]
    turn_on_fn: Callable[[PolestarCoordinator], Awaitable[Any]]
    turn_off_fn: Callable[[PolestarCoordinator], Awaitable[Any]]
    capability: str | None = None
    fetch_attr: str | None = None


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
        fetch_attr="precleaning",
        name="Pre-cleaning",
        icon="mdi:air-purifier",
        is_on_fn=lambda d: d.precleaning.is_running if d.precleaning else None,
        turn_on_fn=lambda c: c.async_start_precleaning(),
        turn_off_fn=lambda c: c.async_stop_precleaning(),
        capability="precleaning",
    ),
    PolestarSwitchDescription(
        # Same backend feature as "precleaning" (invocation.InvocationService
        # /PreCleaning) under the official app's other name for it. Disabled
        # by default to avoid a confusing duplicate switch for most users;
        # enable it if you'd rather see "Air Purification" in your UI.
        key="air_purification",
        fetch_attr="precleaning",
        name="Air Purification",
        icon="mdi:air-purifier",
        entity_registry_enabled_default=False,
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
    for coordinator in data["coordinators"].values():
        entities = [PolestarSwitch(coordinator, desc) for desc in SWITCHES]
        async_add_entities(async_filter_supported_entities(hass, coordinator, "switch", entities))


class PolestarSwitch(OptimisticStateMixin, PolestarEntity, SwitchEntity):
    """Polestar switch entity."""

    entity_description: PolestarSwitchDescription

    # Climatisation and pre-cleaning starts routinely take longer than a
    # minute to be reported back, so hold the shown value across the whole
    # post-command refresh window (see _POST_COMMAND_REFRESH_DELAYS) rather
    # than falling back to the pre-command snapshot partway through it.
    _OPTIMISTIC_TTL = 130.0

    def __init__(self, coordinator, description: PolestarSwitchDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self.required_fetch = description.fetch_attr
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
