"""Base entity for Polestar integration."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
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
    the coordinator reports a matching value, when the command later turns
    out to have failed, or after `_OPTIMISTIC_TTL` seconds if the car never
    confirms it (the state is rewritten at that point).
    """

    _OPTIMISTIC_TTL = 60.0
    _optimistic_value: Any = None
    _optimistic_deadline: float = 0.0
    _cancel_optimistic_timer: Callable[[], None] | None = None

    def _set_optimistic(self, value: Any) -> None:
        self._cancel_timer()
        self._optimistic_value = value
        self._optimistic_deadline = time.monotonic() + self._OPTIMISTIC_TTL
        self._cancel_optimistic_timer = async_call_later(self.hass, self._OPTIMISTIC_TTL, self._optimistic_expired)
        self.async_write_ha_state()

    def _cancel_timer(self) -> None:
        if self._cancel_optimistic_timer is not None:
            self._cancel_optimistic_timer()
            self._cancel_optimistic_timer = None

    def _drop_optimistic(self) -> None:
        self._cancel_timer()
        self._optimistic_deadline = 0.0
        self._optimistic_value = None

    def _clear_optimistic(self) -> None:
        self._drop_optimistic()
        self.async_write_ha_state()

    @callback
    def _optimistic_expired(self, _now: Any) -> None:
        self._cancel_optimistic_timer = None
        self._clear_optimistic()

    def _handle_command_failure(self) -> None:
        if self._optimistic_deadline:
            self._clear_optimistic()

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_timer()
        await super().async_will_remove_from_hass()

    def _resolve_optimistic(self, real_value: Any) -> Any:
        if self._optimistic_deadline == 0.0:
            return real_value
        if real_value == self._optimistic_value or time.monotonic() >= self._optimistic_deadline:
            self._drop_optimistic()
            return real_value
        return self._optimistic_value


class PolestarEntity(CoordinatorEntity[PolestarCoordinator]):
    """Base class for all Polestar entities."""

    _attr_has_entity_name = True
    required_fetch: str | None = None
    required_data: Callable[[Any], bool] | None = None

    def __init__(self, coordinator: PolestarCoordinator) -> None:
        super().__init__(coordinator)
        self._vehicle = coordinator.vehicle

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_command_failure_listener(self._handle_command_failure))

    def _handle_command_failure(self) -> None:
        """A command that was accepted later failed; subclasses revert any local override."""

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


@callback
def async_filter_supported_entities(
    hass: HomeAssistant,
    coordinator: PolestarCoordinator,
    domain: str,
    entities: list[PolestarEntity],
) -> list[PolestarEntity]:
    """Drop entities whose data the car does not support and disable them in the registry.

    Entities disabled here carry ``disabled_by=INTEGRATION`` and are re-enabled
    automatically once the car starts supporting them; entities the user
    disabled are left untouched.
    """
    registry = er.async_get(hass)
    supported: list[PolestarEntity] = []
    for entity in entities:
        attr = entity.required_fetch
        check = entity.required_data
        if attr is None and check is None:
            supported.append(entity)
            continue
        is_supported = attr is None or coordinator.is_fetch_supported(attr)
        if is_supported and check is not None and coordinator.data is not None:
            try:
                is_supported = bool(check(coordinator.data))
            except (AttributeError, TypeError):
                pass
        entity_id = registry.async_get_entity_id(domain, DOMAIN, entity.unique_id)
        entry = registry.async_get(entity_id) if entity_id else None
        if is_supported:
            if entry is not None and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
                registry.async_update_entity(entity_id, disabled_by=None)
            supported.append(entity)
        elif entry is not None and entry.disabled_by is None:
            registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    return supported


@callback
def async_remove_registered_entities(hass: HomeAssistant, domain: str, unique_ids: list[str]) -> None:
    """Remove registry entries for entities this integration no longer provides."""
    registry = er.async_get(hass)
    for unique_id in unique_ids:
        entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
        if entity_id is not None:
            registry.async_remove(entity_id)
