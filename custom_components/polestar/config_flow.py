"""Config flow for Polestar integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from polestar_api import PolestarApi
from polestar_api.auth import MemoryTokenStore
from polestar_api.exceptions import AuthError

from .const import CONF_DEMO, CONF_UPDATE_INTERVAL, CONF_VIN, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_GUEST_SENTINEL = "__guest_manual_vin__"

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_DEMO, default=False): bool,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


def _vehicle_options_schema(
    vehicles: dict[str, str],
    default_interval: int = DEFAULT_UPDATE_INTERVAL,
) -> vol.Schema:
    """Schema for the vehicle picker step (owner accounts)."""
    options = dict(vehicles)
    options[_GUEST_SENTINEL] = "My vehicle is not listed (secondary user / guest)"
    return vol.Schema(
        {
            vol.Required(CONF_VIN): vol.In(options),
            vol.Optional(CONF_UPDATE_INTERVAL, default=default_interval): vol.All(
                int, vol.Range(min=60, max=86400)
            ),
        }
    )


def _guest_vin_schema(default_interval: int = DEFAULT_UPDATE_INTERVAL) -> vol.Schema:
    """Schema for the manual VIN entry step (guest accounts)."""
    return vol.Schema(
        {
            vol.Required(CONF_VIN): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=default_interval): vol.All(
                int, vol.Range(min=60, max=86400)
            ),
        }
    )


class PolestarOptionsFlow(OptionsFlow):
    """Handle options for Polestar."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_UPDATE_INTERVAL, default=current): vol.All(
                        int, vol.Range(min=60, max=86400)
                    ),
                }
            ),
        )


class PolestarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Polestar."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry):
        return PolestarOptionsFlow()

    def __init__(self) -> None:
        self._email: str | None = None
        self._password: str | None = None
        self._vehicles: dict[str, str] = {}  # vin -> display label

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Collect credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            demo = user_input.get(CONF_DEMO, False)

            if demo:
                return await self.async_step_demo_vin()

            api = PolestarApi(self._email, self._password, token_store=MemoryTokenStore())
            try:
                await api.async_init()
                vehicles = await api.get_vehicles()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "cannot_connect"
            else:
                self._vehicles = {}
                for v in vehicles:
                    label = v.vin
                    if v.model_name:
                        label = f"{v.model_name} ({v.vin})"
                    elif v.model_year:
                        label = f"Polestar {v.model_year} ({v.vin})"
                    self._vehicles[v.vin] = label

                if not self._vehicles:
                    # No vehicles found — likely a secondary user / guest account.
                    return await self.async_step_guest_vin()

                return await self.async_step_vehicle()
            finally:
                try:
                    await api.close()
                except Exception:
                    pass

        return self.async_show_form(
            step_id="user",
            data_schema=CREDENTIALS_SCHEMA,
            errors=errors,
        )

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Pick a vehicle from the discovered list."""
        if user_input is not None:
            vin = user_input[CONF_VIN]
            interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

            if vin == _GUEST_SENTINEL:
                return await self.async_step_guest_vin()

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Polestar ({vin})",
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_VIN: vin,
                },
                options={CONF_UPDATE_INTERVAL: interval},
            )

        return self.async_show_form(
            step_id="vehicle",
            data_schema=_vehicle_options_schema(self._vehicles),
        )

    async def async_step_guest_vin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual VIN entry for secondary user / guest accounts."""
        if user_input is not None:
            vin = user_input[CONF_VIN].upper().strip()
            interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Polestar ({vin})",
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_VIN: vin,
                },
                options={CONF_UPDATE_INTERVAL: interval},
            )

        return self.async_show_form(
            step_id="guest_vin",
            data_schema=_guest_vin_schema(),
        )

    async def async_step_demo_vin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """VIN entry for demo mode."""
        if user_input is not None:
            vin = user_input[CONF_VIN].upper().strip()

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Polestar Demo ({vin})",
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_VIN: vin,
                    CONF_DEMO: True,
                },
            )

        return self.async_show_form(
            step_id="demo_vin",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): str,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        self._email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            api = PolestarApi(self._email, password, token_store=MemoryTokenStore())
            try:
                await api.async_init()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "cannot_connect"
            else:
                await api.close()
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            finally:
                try:
                    await api.close()
                except Exception:
                    pass

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )
