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
from .entity import PolestarEntity


@dataclass(frozen=True, kw_only=True)
class PolestarButtonDescription(ButtonEntityDescription):
    """Button description with press callable."""

    press_fn: Callable[[PolestarButton], Awaitable[Any]]


BUTTONS: tuple[PolestarButtonDescription, ...] = (
    PolestarButtonDescription(
        key="flash",
        name="Flash lights",
        icon="mdi:car-light-high",
        press_fn=lambda button: button.coordinator.async_run_command(
            lambda: button._vehicle.honk_flash(action=HonkFlashAction.FLASH),
            error_message="Flash lights command failed",
        ),
    ),
    PolestarButtonDescription(
        key="honk",
        name="Honk",
        icon="mdi:bugle",
        press_fn=lambda button: button.coordinator.async_run_command(
            lambda: button._vehicle.honk_flash(action=HonkFlashAction.HONK),
            error_message="Honk command failed",
        ),
    ),
    PolestarButtonDescription(
        key="honk_flash",
        name="Honk and flash",
        icon="mdi:bugle",
        press_fn=lambda button: button.coordinator.async_run_command(
            lambda: button._vehicle.honk_flash(action=HonkFlashAction.HONK_AND_FLASH),
            error_message="Honk and flash command failed",
        ),
    ),
    PolestarButtonDescription(
        key="wakeup",
        name="Refresh",
        icon="mdi:refresh",
        press_fn=lambda button: button.coordinator.async_request_refresh(),
    ),
    PolestarButtonDescription(
        key="open_windows",
        name="Open windows",
        icon="mdi:window-open",
        press_fn=lambda button: button.coordinator.async_open_windows(),
    ),
    PolestarButtonDescription(
        key="close_windows",
        name="Close windows",
        icon="mdi:window-closed",
        press_fn=lambda button: button.coordinator.async_close_windows(),
    ),
    PolestarButtonDescription(
        key="unlock_trunk",
        name="Unlock trunk",
        icon="mdi:car-back",
        press_fn=lambda button: button.coordinator.async_unlock_trunk(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar buttons."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for coordinator in data["coordinators"].values():
        for desc in BUTTONS:
            entities.append(PolestarButton(coordinator, desc))
    async_add_entities(entities)


class PolestarButton(PolestarEntity, ButtonEntity):
    """Polestar button entity."""

    entity_description: PolestarButtonDescription

    def __init__(self, coordinator, description: PolestarButtonDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._vehicle.vin}_{description.key}"

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self)
