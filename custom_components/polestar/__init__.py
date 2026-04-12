"""Polestar integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import CONF_DEMO, CONF_VIN, DOMAIN, PLATFORMS
from .coordinator import PolestarCoordinator
from .demo import DemoVehicle
from polestar_api import PolestarApi
from polestar_api.exceptions import AuthError
from .services import async_register_services, async_unregister_services
from .token_store import HassTokenStore

_LOGGER = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


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
        vehicles = await api.get_vehicles()
    except AuthError as err:
        await api.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except Exception:
        await api.close()
        raise

    vehicle = next((v for v in vehicles if v.vin == configured_vin), None)

    if vehicle is None:
        await api.close()
        raise ConfigEntryAuthFailed(
            f"VIN {configured_vin} not found on this account"
        )

    coordinator = PolestarCoordinator(hass, vehicle, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_streams()
    coordinators: dict[str, PolestarCoordinator] = {vehicle.vin: coordinator}

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
    }

    async_register_services(hass)
    await _async_register_static_path(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


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

    async_register_services(hass)
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
        if not hass.data[DOMAIN]:
            async_unregister_services(hass)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up stored tokens when entry is removed."""
    token_store = HassTokenStore(hass, entry.entry_id)
    await token_store.remove()
