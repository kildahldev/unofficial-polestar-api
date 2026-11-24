"""HA-specific token persistence using homeassistant.helpers.storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.storage import Store

from polestar_api.auth import TokenData

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

STORAGE_VERSION = 1
_EMAIL_KEY = "email"


class HassTokenStore:
    """Stores Polestar auth tokens in HA's .storage/ directory.

    Tokens are tagged with the account email they were issued for. If the
    configured email changes (e.g. via reauth or reconfigure), tokens issued
    for the previous account are ignored so the new account is always
    authenticated from scratch instead of silently refreshing the old session.
    """

    def __init__(
        self, hass: HomeAssistant, entry_id: str, email: str | None = None
    ) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.tokens.{entry_id}")
        self._email = email

    async def load(self) -> TokenData | None:
        data = await self._store.async_load()
        if data is None:
            return None
        stored_email = data.get(_EMAIL_KEY)
        # Tokens saved before email tagging existed have no email; keep using them.
        if (
            self._email is not None
            and stored_email is not None
            and stored_email.casefold() != self._email.casefold()
        ):
            return None
        return TokenData.from_dict(data)

    async def save(self, tokens: TokenData) -> None:
        data = tokens.to_dict()
        if self._email is not None:
            data[_EMAIL_KEY] = self._email
        await self._store.async_save(data)

    async def remove(self) -> None:
        await self._store.async_remove()
