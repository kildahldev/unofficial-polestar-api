"""Privacy settings service — location/data sharing toggles (server-streaming)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import encode
from ..models.privacy import PrivacySetting, PrivacySettingType

if TYPE_CHECKING:
    from ..connection import GrpcConnection

# The server sends every setting right away (one per message), then keeps the
# stream open. A poll reads until it goes quiet, then closes the stream.
_STREAM_TIMEOUT = 10.0
_IDLE_TIMEOUT = 2.0


class PrivacyServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.privacy_settings_svc

    async def get(self) -> dict[PrivacySettingType, PrivacySetting] | None:
        """Read the current settings once, keyed by type; ``None`` if none arrived."""
        settings: dict[PrivacySettingType, PrivacySetting] = {}
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT) as deadline:
                async for setting in self.stream():
                    settings[setting.setting_type] = setting
                    deadline.reschedule(asyncio.get_running_loop().time() + _IDLE_TIMEOUT)
        except TimeoutError:
            pass
        return settings or None

    async def stream(self) -> AsyncIterator[PrivacySetting]:
        """Stream settings; each message carries ONE setting (merge by type)."""
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetPrivacySettingsV2Stream",
            encode({"vin": (1, "string")}, {"vin": self._vin}),
            metadata=metadata,
        ):
            yield PrivacySetting.from_bytes(data)
