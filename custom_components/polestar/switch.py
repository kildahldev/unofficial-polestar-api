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
from .utils import charge_timer_active, climate_attributes, precleaning_attributes

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PolestarSwitchDescription(SwitchEntityDescription):
    """Switch description with on/off callables and state extractor."""

    is_on_fn: Callable[[PolestarVehicleData], bool | None]
    turn_on_fn: Callable[[PolestarCoordinator], Awaitable[Any]]
    turn_off_fn: Callable[[PolestarCoordinator], Awaitable[Any]]
    capability: str | None = None
    fetch_attr: str | None = None
    attrs_fn: Callable[[PolestarVehicleData], dict[str, Any]] | None = None


SWITCHES: tuple[PolestarSwitchDescription, ...] = (
    PolestarSwitchDescription(
        key="climate",
        translation_key="climate",
        icon="mdi:air-conditioner",
        is_on_fn=lambda d: d.climate.is_active if d.climate else None,
        turn_on_fn=lambda c: c.async_start_climate(),
        turn_off_fn=lambda c: c.async_stop_climate(),
        capability="climate",
        attrs_fn=lambda d: climate_attributes(d.climate),
    ),
    PolestarSwitchDescription(
        # The backend calls this "pre-cleaning" (invocation.InvocationService/PreCleaning); the app
        # and Volvo call it Air Purification. One switch, under the app's name. The separate
        # "Pre-cleaning" switch it used to duplicate was removed on 18 Nov 2026.
        key="air_purification",
        fetch_attr="precleaning",
        translation_key="air_purification",
        icon="mdi:air-purifier",
        is_on_fn=lambda d: d.precleaning.is_running if d.precleaning else None,
        turn_on_fn=lambda c: c.async_start_precleaning(),
        turn_off_fn=lambda c: c.async_stop_precleaning(),
        capability="precleaning",
        attrs_fn=lambda d: precleaning_attributes(d.precleaning),
    ),
    PolestarSwitchDescription(
        key="charging",
        translation_key="charging",
        icon="mdi:ev-station",
        is_on_fn=lambda d: d.battery.is_charging if d.battery else None,
        turn_on_fn=lambda c: c.async_start_charging(),
        turn_off_fn=lambda c: c.async_stop_charging(),
        capability="charging",
    ),
    PolestarSwitchDescription(
        key="charge_timer",
        translation_key="charge_timer",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: charge_timer_active(d.charge_timer),
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
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        if fn is None or self.coordinator.data is None:
            return None
        return fn(self.coordinator.data) or None

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
