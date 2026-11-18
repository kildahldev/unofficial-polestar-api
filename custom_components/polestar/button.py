"""Button platform for Polestar integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from polestar_api.models.honkflash import HonkFlashAction

from .const import DOMAIN
from .entity import PolestarEntity, async_filter_supported_entities, async_remove_registered_entities

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PolestarButtonDescription(ButtonEntityDescription):
    """Button description with press callable."""

    press_fn: Callable[[PolestarButton], Awaitable[Any]]
    capability: str | None = None
    fetch_attr: str | None = None


BUTTONS: tuple[PolestarButtonDescription, ...] = (
    PolestarButtonDescription(
        key="flash",
        name="Flash lights",
        icon="mdi:car-light-high",
        press_fn=lambda button: button.coordinator.async_run_command(
            lambda: button._vehicle.honk_flash(action=HonkFlashAction.FLASH),
            error_message="Flash lights command failed",
            capability="flash",
        ),
        capability="flash",
    ),
    PolestarButtonDescription(
        key="honk",
        name="Honk",
        icon="mdi:bugle",
        press_fn=lambda button: button.coordinator.async_run_command(
            lambda: button._vehicle.honk_flash(action=HonkFlashAction.HONK),
            error_message="Honk command failed",
            capability="honk",
        ),
        capability="honk",
    ),
    PolestarButtonDescription(
        key="honk_flash",
        name="Honk and flash",
        icon="mdi:bugle",
        press_fn=lambda button: button.coordinator.async_run_command(
            lambda: button._vehicle.honk_flash(action=HonkFlashAction.HONK_AND_FLASH),
            error_message="Honk and flash command failed",
            capability="honk_flash",
        ),
        capability="honk_flash",
    ),
    PolestarButtonDescription(
        key="wakeup",
        name="Refresh",
        icon="mdi:refresh",
        press_fn=lambda button: button.coordinator.async_request_refresh(),
    ),
    PolestarButtonDescription(
        key="open_windows",
        fetch_attr="window_control",
        name="Open windows",
        icon="mdi:window-open",
        press_fn=lambda button: button.coordinator.async_open_windows(),
        capability="open_windows",
    ),
    PolestarButtonDescription(
        key="close_windows",
        fetch_attr="window_control",
        name="Close windows",
        icon="mdi:window-closed",
        press_fn=lambda button: button.coordinator.async_close_windows(),
        capability="close_windows",
    ),
)

# Buttons replaced by other entities; their registry entries are removed at setup.
REMOVED_BUTTON_KEYS = ("unlock_trunk",)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar buttons."""
    data = hass.data[DOMAIN][entry.entry_id]
    for coordinator in data["coordinators"].values():
        async_remove_registered_entities(
            hass, "button", [f"{coordinator.vehicle.vin}_{key}" for key in REMOVED_BUTTON_KEYS]
        )
        entities = [PolestarButton(coordinator, desc) for desc in BUTTONS]
        async_add_entities(async_filter_supported_entities(hass, coordinator, "button", entities))


class PolestarButton(PolestarEntity, ButtonEntity):
    """Polestar button entity."""

    entity_description: PolestarButtonDescription

    def __init__(self, coordinator, description: PolestarButtonDescription) -> None:
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

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self)
