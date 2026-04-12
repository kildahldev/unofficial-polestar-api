"""Config flow for Polestar integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from polestar_api import PolestarApi
from polestar_api.auth import MemoryTokenStore
from polestar_api.exceptions import AuthError

from .const import CONF_DEMO, CONF_VIN, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_VIN): str,
        vol.Optional(CONF_DEMO, default=False): bool,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class PolestarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Polestar."""

    VERSION = 2

    def __init__(self) -> None:
        self._email: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            vin = user_input[CONF_VIN].upper().strip()
            demo = user_input.get(CONF_DEMO, False)

            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()

            if demo:
                return self.async_create_entry(
                    title=f"Polestar Demo ({vin})",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_VIN: vin,
                        CONF_DEMO: True,
                    },
                )

            api = PolestarApi(email, password, token_store=MemoryTokenStore())
            try:
                await api.async_init()
                vehicles = await api.get_vehicles()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "cannot_connect"
            else:
                if not any(v.vin == vin for v in vehicles):
                    errors["base"] = "vin_not_found"
                else:
                    await api.close()
                    return self.async_create_entry(
                        title=f"Polestar ({vin})",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_VIN: vin,
                        },
                    )
            finally:
                try:
                    await api.close()
                except Exception:
                    pass

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
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
