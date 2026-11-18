"""Lock platform for Polestar integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from polestar_api.models.exterior import LockStatus

from .const import DOMAIN
from .entity import PolestarEntity

PARALLEL_UPDATES = 1

# How long to keep showing locking/unlocking while waiting for the car to confirm.
PENDING_TIMEOUT = 60.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Polestar locks."""
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        lock(coordinator)
        for coordinator in data["coordinators"].values()
        for lock in (PolestarLock, PolestarTailgateLock)
    ]
    async_add_entities(entities)


class PolestarLock(PolestarEntity, LockEntity):
    """Polestar central lock."""

    _attr_name = "Lock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_lock"
        self._pending_locked: bool | None = None
        self._cancel_pending_timeout: Callable[[], None] | None = None

    @property
    def is_locking(self) -> bool:
        return self._pending_locked is True

    @property
    def is_unlocking(self) -> bool:
        return self._pending_locked is False

    def _start_pending(self, locked: bool) -> None:
        """Show locking/unlocking until the car reports the new state or the timeout expires."""
        self._clear_pending()
        if self.is_locked == locked:
            return
        self._pending_locked = locked
        self._cancel_pending_timeout = async_call_later(self.hass, PENDING_TIMEOUT, self._pending_expired)
        self.async_write_ha_state()

    def _clear_pending(self) -> None:
        if self._cancel_pending_timeout is not None:
            self._cancel_pending_timeout()
            self._cancel_pending_timeout = None
        self._pending_locked = None

    @callback
    def _pending_expired(self, _now: Any) -> None:
        self._cancel_pending_timeout = None
        self._pending_locked = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._pending_locked is not None and self.is_locked == self._pending_locked:
            self._clear_pending()
        super()._handle_coordinator_update()

    def _handle_command_failure(self) -> None:
        if self._pending_locked is not None:
            self._clear_pending()
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._clear_pending()
        await super().async_will_remove_from_hass()

    @property
    def is_locked(self) -> bool | None:
        if self.coordinator.data and self.coordinator.data.exterior:
            return self.coordinator.data.exterior.is_locked
        return None

    async def async_lock(self, **kwargs: Any) -> None:
        self._start_pending(True)
        try:
            await self.coordinator.async_run_command(
                self._vehicle.lock,
                error_message="Lock command failed",
                capability="lock",
            )
        except Exception:
            self._clear_pending()
            self.async_write_ha_state()
            raise
        # Fallback refresh in background — exterior stream will usually
        # push the update before this fires.
        self.coordinator.async_refresh_exterior_after_command()

    async def async_unlock(self, **kwargs: Any) -> None:
        self._start_pending(False)
        try:
            await self.coordinator.async_run_command(
                self._vehicle.unlock,
                error_message="Unlock command failed",
                capability="unlock",
            )
        except Exception:
            self._clear_pending()
            self.async_write_ha_state()
            raise
        self.coordinator.async_refresh_exterior_after_command()


class PolestarTailgateLock(PolestarLock):
    """Boot (tailgate) lock, replacing the old "Unlock trunk" button.

    The car unlocks the boot with its own trunk-unlock command, and relocks it with the
    normal lock command (the Polestar app has no separate lock-boot command either), so
    locking this entity locks the whole car.
    """

    _attr_name = "Boot lock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._vehicle.vin}_tailgate_lock"

    @property
    def is_locked(self) -> bool | None:
        exterior = self.coordinator.data.exterior if self.coordinator.data else None
        status = exterior.tailgate.status if exterior is not None and exterior.tailgate is not None else None
        if status is None or status.lock_status == LockStatus.UNSPECIFIED:
            return None
        return status.lock_status == LockStatus.LOCKED

    async def async_unlock(self, **kwargs: Any) -> None:
        self._start_pending(False)
        try:
            await self.coordinator.async_unlock_trunk()
        except Exception:
            self._clear_pending()
            self.async_write_ha_state()
            raise
