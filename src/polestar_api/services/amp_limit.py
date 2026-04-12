"""Amp limit service — get/set battery charge amperage limit."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import encode
from ..models.charging import AmpLimitResponse
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.AmpLimitService"
_STREAM_TIMEOUT = 10.0


class AmpLimitServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get(self) -> AmpLimitResponse:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel, f"{_SVC}/GetAmpLimit",
                    wrap_chronos(self._vin), metadata=metadata,
                ):
                    break
        except TimeoutError:
            pass
        if data is None:
            return AmpLimitResponse()
        return AmpLimitResponse.from_bytes(data)

    async def set(self, amperage: int) -> AmpLimitResponse:
        # APK: REQUEST=1 (ChronosRequest), AMP_LIMIT=2
        payload = encode({"amp_limit": (2, "int32")}, {"amp_limit": amperage})
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/SetAmpLimit",
            wrap_chronos(self._vin, payload), metadata=metadata,
        )
        return AmpLimitResponse.from_bytes(data)
