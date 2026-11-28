"""Privacy settings service — location/data sharing toggles (server-streaming)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import encode
from ..models.privacy import PrivacySetting

if TYPE_CHECKING:
    from ..connection import GrpcConnection


class PrivacyServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.privacy_settings_svc

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
