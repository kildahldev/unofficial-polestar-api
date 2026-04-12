"""Base entity for Polestar integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PolestarCoordinator

if TYPE_CHECKING:
    from polestar_api.vehicle import Vehicle


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
