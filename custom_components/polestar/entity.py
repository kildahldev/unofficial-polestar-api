"""Base entity for Polestar integration."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PolestarCoordinator

if TYPE_CHECKING:
    from polestar_api.vehicle import Vehicle


class OptimisticStateMixin:
    """Show a locally-set value instantly, ahead of the next confirmed refresh.

    The Polestar cloud backend can take several seconds to reflect a command.
    Call `_set_optimistic(value)` right after a command succeeds to display
    the new value immediately, and read state through `_resolve_optimistic`
    instead of the raw coordinator value. The override is dropped as soon as
    the coordinator reports a matching value, or after `_OPTIMISTIC_TTL`
    seconds if the backend never confirms it.
    """

    _OPTIMISTIC_TTL = 10.0
    _optimistic_value: Any = None
    _optimistic_deadline: float = 0.0

    def _set_optimistic(self, value: Any) -> None:
        self._optimistic_value = value
        self._optimistic_deadline = time.monotonic() + self._OPTIMISTIC_TTL
        self.async_write_ha_state()

    def _clear_optimistic(self) -> None:
        self._optimistic_value = None
        self._optimistic_deadline = 0.0
        self.async_write_ha_state()

    def _resolve_optimistic(self, real_value: Any) -> Any:
        if self._optimistic_deadline == 0.0:
            return real_value
        if real_value == self._optimistic_value or time.monotonic() >= self._optimistic_deadline:
            self._optimistic_deadline = 0.0
            self._optimistic_value = None
            return real_value
        return self._optimistic_value


class PolestarEntity(CoordinatorEntity[PolestarCoordinator]):
    """Base class for all Polestar entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PolestarCoordinator) -> None:
        super().__init__(coordinator)
        self._vehicle = coordinator.vehicle

    @property
    def device_info(self) -> DeviceInfo:
        v = self._vehicle
        name_parts = [_device_name_prefix(v.model_name)]
        if v.registration_no:
            name_parts.append(f"({v.registration_no})")
        else:
            name_parts.append(f"({v.vin[-6:]})")

        return DeviceInfo(
            identifiers={(DOMAIN, v.vin)},
            name=" ".join(name_parts),
            manufacturer="Polestar",
            model=v.model_name,
            serial_number=v.vin,
            sw_version=(
                self.coordinator.installed_version_cache
                or (
                    self.coordinator.data.software.new_sw_version
                    if self.coordinator.data and self.coordinator.data.software
                    else None
                )
            ),
        )


def _device_name_prefix(model_name: str | None) -> str:
    """Return a stable device-name prefix without duplicating the brand."""
    if not model_name:
        return "Polestar"

    if model_name.casefold().startswith("polestar "):
        return model_name

    return f"Polestar {model_name}"
