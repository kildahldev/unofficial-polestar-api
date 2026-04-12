"""HA-specific token persistence using homeassistant.helpers.storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from polestar_api.auth import TokenData

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

STORAGE_VERSION = 1


class HassTokenStore:
    """Stores Polestar auth tokens in HA's .storage/ directory."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.tokens.{entry_id}")

    async def load(self) -> TokenData | None:
        data = await self._store.async_load()
        if data is None:
            return None
        return TokenData.from_dict(data)

    async def save(self, tokens: TokenData) -> None:
        await self._store.async_save(tokens.to_dict())

    async def remove(self) -> None:
        await self._store.async_remove()
