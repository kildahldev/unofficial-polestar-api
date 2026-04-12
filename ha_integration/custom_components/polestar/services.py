"""Service registration for the Polestar integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    ATTR_ENTITY_ID,
    ATTR_LOCATION_ID,
    ATTR_TIMER_ID,
    ATTR_VIN,
    DOMAIN,
    SERVICE_CANCEL_OTA,
    SERVICE_CLEAR_CHARGE_TIMER,
    SERVICE_CREATE_CHARGE_LOCATION,
    SERVICE_DELETE_CHARGE_LOCATION,
    SERVICE_DELETE_CLIMATE_TIMER,
    SERVICE_SCHEDULE_OTA,
    SERVICE_SET_CHARGE_TIMER,
    SERVICE_START_CLIMATE,
    SERVICE_UPDATE_CHARGE_LOCATION,
)
from .coordinator import PolestarCoordinator
from polestar_api.models.climatization import HeatingIntensity

_TARGET_SCHEMA = {
    vol.Exclusive(ATTR_VIN, "target"): cv.string,
    vol.Exclusive(ATTR_ENTITY_ID, "target"): cv.entity_id,
}

_HEATING_OPTIONS = {
    "unspecified": HeatingIntensity.UNSPECIFIED,
    "off": HeatingIntensity.OFF,
    "level1": HeatingIntensity.LEVEL1,
    "level2": HeatingIntensity.LEVEL2,
    "level3": HeatingIntensity.LEVEL3,
}


SERVICE_SCHEMAS: dict[str, vol.Schema] = {
    SERVICE_START_CLIMATE: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Optional("temperature"): vol.Coerce(float),
            vol.Optional("front_left_seat"): vol.In(list(_HEATING_OPTIONS)),
            vol.Optional("front_right_seat"): vol.In(list(_HEATING_OPTIONS)),
            vol.Optional("rear_left_seat"): vol.In(list(_HEATING_OPTIONS)),
            vol.Optional("rear_right_seat"): vol.In(list(_HEATING_OPTIONS)),
            vol.Optional("steering_wheel"): vol.In(list(_HEATING_OPTIONS)),
        }
    ),
    SERVICE_SET_CHARGE_TIMER: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Optional("start_time"): cv.time,
            vol.Optional("stop_time"): cv.time,
            vol.Optional("enabled"): cv.boolean,
        }
    ),
    SERVICE_CLEAR_CHARGE_TIMER: vol.Schema(_TARGET_SCHEMA),
    SERVICE_CREATE_CHARGE_LOCATION: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Required("alias"): cv.string,
            vol.Optional("amp_limit", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=32)),
            vol.Optional("minimum_soc", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional("optimised_charging", default=False): cv.boolean,
        }
    ),
    SERVICE_UPDATE_CHARGE_LOCATION: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Required(ATTR_LOCATION_ID): cv.string,
            vol.Optional("alias"): cv.string,
            vol.Optional("amp_limit"): vol.All(vol.Coerce(int), vol.Range(min=0, max=32)),
            vol.Optional("minimum_soc"): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional("optimised_charging"): cv.boolean,
        }
    ),
    SERVICE_DELETE_CHARGE_LOCATION: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Required(ATTR_LOCATION_ID): cv.string,
        }
    ),
    SERVICE_SCHEDULE_OTA: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Optional("delay_minutes", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }
    ),
    SERVICE_CANCEL_OTA: vol.Schema(_TARGET_SCHEMA),
    SERVICE_DELETE_CLIMATE_TIMER: vol.Schema(
        {
            **_TARGET_SCHEMA,
            vol.Optional(ATTR_TIMER_ID): cv.string,
        }
    ),
}


def async_register_services(hass: HomeAssistant) -> None:
    """Register Polestar services."""
    if hass.services.has_service(DOMAIN, SERVICE_START_CLIMATE):
        return

    def bind(handler):
        async def _wrapped(call: ServiceCall) -> None:
            await handler(hass, call)

        return _wrapped

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CLIMATE,
        bind(_async_handle_start_climate),
        schema=SERVICE_SCHEMAS[SERVICE_START_CLIMATE],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHARGE_TIMER,
        bind(_async_handle_set_charge_timer),
        schema=SERVICE_SCHEMAS[SERVICE_SET_CHARGE_TIMER],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CHARGE_TIMER,
        bind(_async_handle_clear_charge_timer),
        schema=SERVICE_SCHEMAS[SERVICE_CLEAR_CHARGE_TIMER],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_CHARGE_LOCATION,
        bind(_async_handle_create_charge_location),
        schema=SERVICE_SCHEMAS[SERVICE_CREATE_CHARGE_LOCATION],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CHARGE_LOCATION,
        bind(_async_handle_update_charge_location),
        schema=SERVICE_SCHEMAS[SERVICE_UPDATE_CHARGE_LOCATION],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_CHARGE_LOCATION,
        bind(_async_handle_delete_charge_location),
        schema=SERVICE_SCHEMAS[SERVICE_DELETE_CHARGE_LOCATION],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCHEDULE_OTA,
        bind(_async_handle_schedule_ota),
        schema=SERVICE_SCHEMAS[SERVICE_SCHEDULE_OTA],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_OTA,
        bind(_async_handle_cancel_ota),
        schema=SERVICE_SCHEMAS[SERVICE_CANCEL_OTA],
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_CLIMATE_TIMER,
        bind(_async_handle_delete_climate_timer),
        schema=SERVICE_SCHEMAS[SERVICE_DELETE_CLIMATE_TIMER],
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister Polestar services when the last entry unloads."""
    for service_name in SERVICE_SCHEMAS:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)


def _iter_coordinators(hass: HomeAssistant) -> list[PolestarCoordinator]:
    """Return all active coordinators."""
    coordinators: list[PolestarCoordinator] = []
    for value in hass.data.get(DOMAIN, {}).values():
        if not isinstance(value, dict):
            continue
        coordinators.extend(value.get("coordinators", {}).values())
    return coordinators


def _normalise_service_data(call: ServiceCall) -> dict[str, Any]:
    """Return service data with entity target merged in when present."""
    data = dict(call.data)
    target = getattr(call, "target", None) or {}
    entity_id = target.get("entity_id")
    if entity_id is not None and ATTR_ENTITY_ID not in data:
        data[ATTR_ENTITY_ID] = entity_id
    return data


def _resolve_entity_id(value: Any) -> str | None:
    """Extract a single entity id from a service payload value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        if len(value) != 1:
            raise ServiceValidationError("Exactly one entity_id must be provided")
        first = next(iter(value))
        if not isinstance(first, str):
            raise ServiceValidationError("entity_id must be a string")
        return first
    raise ServiceValidationError("entity_id must be a string or a single-item list")


def _resolve_coordinator(hass: HomeAssistant, data: dict[str, Any]) -> PolestarCoordinator:
    """Resolve a coordinator from service target data."""
    vin = data.get(ATTR_VIN)
    entity_id = _resolve_entity_id(data.get(ATTR_ENTITY_ID))

    if vin:
        for coordinator in _iter_coordinators(hass):
            if coordinator.vehicle.vin == vin:
                return coordinator
        raise ServiceValidationError(f"Unknown Polestar VIN: {vin}")

    if entity_id:
        entity_entry = er.async_get(hass).async_get(entity_id)
        if entity_entry is None:
            raise ServiceValidationError(f"Unknown entity_id: {entity_id}")

        for coordinator in _iter_coordinators(hass):
            if entity_entry.unique_id.startswith(f"{coordinator.vehicle.vin}_"):
                return coordinator

        raise ServiceValidationError(f"Entity {entity_id} is not managed by the Polestar integration")

    raise ServiceValidationError("Either vin or entity_id must be provided")


def _timer_id_from_entity_id(hass: HomeAssistant, coordinator: PolestarCoordinator, entity_id: str) -> str | None:
    """Resolve a parking climate timer id from a calendar entity id."""
    entity_entry = er.async_get(hass).async_get(entity_id)
    if entity_entry is None:
        return None

    suffix = entity_entry.unique_id.removeprefix(f"{coordinator.vehicle.vin}_")
    if not suffix.startswith("parking_climate_timer_"):
        return None

    try:
        slot = int(suffix.rsplit("_", 1)[1]) - 1
    except ValueError:
        return None

    timers = sorted(coordinator.data.climate_timers if coordinator.data else [], key=lambda timer: timer.index)
    for timer in timers:
        if timer.index == slot:
            return timer.timer_id
    return None


async def _async_handle_start_climate(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    await coordinator.async_start_climate(
        temperature=data.get("temperature"),
        front_left_seat=_HEATING_OPTIONS.get(data.get("front_left_seat")),
        front_right_seat=_HEATING_OPTIONS.get(data.get("front_right_seat")),
        rear_left_seat=_HEATING_OPTIONS.get(data.get("rear_left_seat")),
        rear_right_seat=_HEATING_OPTIONS.get(data.get("rear_right_seat")),
        steering_wheel=_HEATING_OPTIONS.get(data.get("steering_wheel")),
    )


async def _async_handle_set_charge_timer(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    if not any(key in data for key in ("start_time", "stop_time", "enabled")):
        raise ServiceValidationError("At least one of start_time, stop_time, or enabled must be provided")
    await coordinator.async_set_charge_timer(
        start=data.get("start_time"),
        stop=data.get("stop_time"),
        activated=data.get("enabled"),
    )


async def _async_handle_clear_charge_timer(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = _resolve_coordinator(hass, _normalise_service_data(call))
    await coordinator.async_clear_charge_timer()


async def _async_handle_create_charge_location(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    await coordinator.async_create_charge_location(
        alias=data["alias"],
        amp_limit=data["amp_limit"],
        minimum_soc=data["minimum_soc"],
        optimised_charging=data["optimised_charging"],
    )


async def _async_handle_update_charge_location(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    await coordinator.async_update_charge_location(
        location_id=data[ATTR_LOCATION_ID],
        alias=data.get("alias"),
        amp_limit=data.get("amp_limit"),
        minimum_soc=data.get("minimum_soc"),
        optimised_charging=data.get("optimised_charging"),
    )


async def _async_handle_delete_charge_location(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    await coordinator.async_delete_charge_location(data[ATTR_LOCATION_ID])


async def _async_handle_schedule_ota(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    await coordinator.async_schedule_ota(relative_time=data["delay_minutes"] * 60)


async def _async_handle_cancel_ota(hass: HomeAssistant, call: ServiceCall) -> None:
    coordinator = _resolve_coordinator(hass, _normalise_service_data(call))
    await coordinator.async_cancel_ota()


async def _async_handle_delete_climate_timer(hass: HomeAssistant, call: ServiceCall) -> None:
    data = _normalise_service_data(call)
    coordinator = _resolve_coordinator(hass, data)
    timer_id = data.get(ATTR_TIMER_ID)
    entity_id = _resolve_entity_id(data.get(ATTR_ENTITY_ID))
    if timer_id is None and entity_id is not None:
        timer_id = _timer_id_from_entity_id(hass, coordinator, entity_id)
    if timer_id is None:
        raise HomeAssistantError("timer_id is required unless entity_id targets a Polestar parking climate timer calendar")
    await coordinator.async_delete_climate_timer(timer_id)
