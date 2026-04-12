"""Lock platform for Polestar integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PolestarEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar locks."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PolestarLock(coordinator)
        for coordinator in data["coordinators"].values()
    ]
    async_add_entities(entities)


class PolestarLock(PolestarEntity, LockEntity):
    """Polestar central lock."""

    _attr_name = "Lock"
    _attr_is_locking: bool = False
    _attr_is_unlocking: bool = False

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_lock"

    @property
    def is_locked(self) -> bool | None:
        if self.coordinator.data and self.coordinator.data.exterior:
            return self.coordinator.data.exterior.is_locked
        return None

    async def async_lock(self, **kwargs: Any) -> None:
        self._attr_is_locking = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_run_command(
                self._vehicle.lock,
                error_message="Lock command failed",
            )
        finally:
            self._attr_is_locking = False
            self.async_write_ha_state()
        # Fallback refresh in background — exterior stream will usually
        # push the update before this fires.
        self.coordinator.async_refresh_exterior_after_command()

    async def async_unlock(self, **kwargs: Any) -> None:
        self._attr_is_unlocking = True
        self.async_write_ha_state()
        try:
            await self.coordinator.async_run_command(
                self._vehicle.unlock,
                error_message="Unlock command failed",
            )
        finally:
            self._attr_is_unlocking = False
            self.async_write_ha_state()
        self.coordinator.async_refresh_exterior_after_command()
