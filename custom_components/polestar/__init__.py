"""Polestar integration for Home Assistant."""

from __future__ import annotations

import sys
from pathlib import Path

# The polestar_api library is vendored under vendor/ rather than installed
# from PyPI, so this integration's fixes don't depend on a release of the
# separate unofficial-polestar-api project. Must run before any import
# (direct or transitive, e.g. via .coordinator) resolves "polestar_api".
_VENDOR_DIR = Path(__file__).parent / "vendor"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

import logging  # noqa: E402

from homeassistant.components.http import StaticPathConfig  # noqa: E402
from homeassistant.config_entries import ConfigEntry  # noqa: E402
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady  # noqa: E402
from homeassistant.helpers import config_validation as cv  # noqa: E402
from homeassistant.helpers.typing import ConfigType  # noqa: E402

from .const import CONF_DEMO, CONF_VIN, DOMAIN, PLATFORMS  # noqa: E402
from .coordinator import PolestarCoordinator  # noqa: E402
from .demo import DemoVehicle  # noqa: E402
from polestar_api import PolestarApi, Vehicle  # noqa: E402
from polestar_api.exceptions import ApiError, AuthError  # noqa: E402
from .services import async_register_services  # noqa: E402
from .token_store import HassTokenStore  # noqa: E402

_LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Polestar services once, independently of any config entry."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Polestar from a config entry."""
    if entry.data.get(CONF_DEMO):
        return await _async_setup_demo(hass, entry)

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    configured_vin = entry.data[CONF_VIN]

    token_store = HassTokenStore(hass, entry.entry_id)
    api = PolestarApi(email, password, token_store=token_store)

    try:
        await api.async_init()
        try:
            vehicles = await api.get_vehicles()
        except ApiError as err:
            failure = (
                f"HTTP {err.status_code}"
                if err.status_code is not None
                else "GraphQL/API error"
            )
            _LOGGER.warning("Vehicle list lookup failed (%s); using configured VIN", failure)
            vehicles = []
    except AuthError as err:
        await api.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except Exception as err:
        await api.close()
        raise ConfigEntryNotReady(str(err)) from err

    vehicle = next((v for v in vehicles if v.vin == configured_vin), None)

    if vehicle is None:
        # Guest / linked accounts don't appear in the VDMS vehicle list.
        # Create a Vehicle directly — gRPC access is validated at runtime.
        _LOGGER.info(
            "VIN %s not in VDMS vehicle list (guest/linked account), "
            "creating vehicle directly",
            configured_vin,
        )
        vehicle = Vehicle(vin=configured_vin, connection=api._connection)

    await vehicle.async_load_car_information()

    coordinator = PolestarCoordinator(hass, vehicle, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_streams()
    coordinators: dict[str, PolestarCoordinator] = {vehicle.vin: coordinator}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
    }

    _async_remove_replaced_entities(hass, vehicle.vin)
    await _async_register_static_path(hass)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


# Entities replaced by binary problem sensors (and the Lock entity): their unique ID suffixes.
_REPLACED_ENTITY_SUFFIXES = (
    "service_warning",
    "brake_fluid_warning",
    "washer_fluid_warning",
    "low_voltage_battery_warning",
    "is_locked",
)


def _async_remove_replaced_entities(hass: HomeAssistant, vin: str) -> None:
    """Remove the old enum warning sensors and the Locked binary sensor from the registry."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    for domain in ("sensor", "binary_sensor"):
        for suffix in _REPLACED_ENTITY_SUFFIXES:
            entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{vin}_{suffix}")
            if entity_id:
                registry.async_remove(entity_id)
                _LOGGER.info("Removed replaced entity %s", entity_id)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_setup_demo(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a demo vehicle with fake data."""
    vehicle = DemoVehicle()
    coordinator = PolestarCoordinator(hass, vehicle, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_streams()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": None,
        "coordinators": {vehicle.vin: coordinator},
    }

    await _async_register_static_path(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """Register the integration's static/ directory once."""
    key = f"{DOMAIN}_static_registered"
    if hass.data.get(key) or not STATIC_DIR.is_dir():
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/{DOMAIN}/static", str(STATIC_DIR), cache_headers=False)]
    )
    hass.data[key] = True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        for coordinator in data["coordinators"].values():
            await coordinator.async_shutdown()
        if data["api"] is not None:
            await data["api"].close()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up stored tokens when entry is removed."""
    token_store = HassTokenStore(hass, entry.entry_id)
    await token_store.remove()
